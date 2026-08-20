"""recommend_course: the one *agent* node in the graph.

The student's interest can be vague or need more than one search ("Is there
anything interesting in the intersection of AI and biology?"), so unlike the
other nodes this one gets real autonomy: it's a `langchain.agents.create_agent`
agent (built on LangGraph under the hood) that can call its tools as many
times as it needs (bounded by RECURSION_LIMIT below) before deciding it has
enough to answer.

Three tools, each giving the model something it can't reliably do on its own:
  - search_courses: semantic search over syllabi — the model has no idea what
    courses exist otherwise.
  - check_degree_path: fundamental/elective course lists for a COMS track
    (Machine Learning, NLP, Software Systems, Computer Security), from the
    same curated data src/main.py loads into Supabase from
    src/data/degree_path.json. When a student names a track, this is a more
    authoritative source than semantic search — it lets the agent recommend
    from (and say a course counts toward) the actual requirement list instead
    of guessing from topic similarity.
  - check_schedule_conflict: deterministic day/time overlap check between a
    candidate course and the student's existing schedule. LLMs are bad at
    interval arithmetic ("does Mon 10:10-11:25 overlap Mon 10:55-12:10?");
    this does the comparison in code and hands back a plain verdict, so a
    recommendation the student literally cannot take (time-wise) gets caught
    before it's suggested rather than discovered after the fact.

Generates plain text for its final answer (no `response_format`) so
src/api/main.py can stream it token-by-token — the tool-calling turns along
the way carry no visible text (the system prompt tells the model not to
narrate before calling a tool), so only the final turn actually streams
anything to the client. `cited_course_ids` is recovered from that final text
via src/agents/text_utils.py rather than self-reported by the model; see that
module's docstring for the tradeoff vs. the old structured-output approach.
"""
from typing import List

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from src.agents.message_utils import to_langchain_messages
from src.agents.state import AgentState, ScheduledCourseContext
from src.agents.text_utils import find_course_id_mentions, normalize_course_id
from src.config import get_agent_llm, get_embedding_model
from src.db.supabase_client import (
    get_course_schedule,
    get_courses_by_ids,
    get_degree_path,
    list_degree_paths,
    search_courses_by_embedding,
)

# Caps how many tool <-> reasoning round-trips the agent can take before
# LangGraph forces a stop, so a stuck agent fails fast instead of looping
# indefinitely. Each round-trip is 2 supersteps (model, tool), plus 1 for the
# initial model call - allows ~11 tool calls total (1 + 2*11 = 23 <= 24).
# Needs headroom beyond a single search: e.g. check_degree_path once, then
# check_schedule_conflict against each of that track's electives in turn.
RECURSION_LIMIT = 24

SYSTEM_PROMPT = """You are LionPlanner's course recommendation assistant for Columbia University students. \
Do not write any commentary before calling a tool — call it directly. Once you're confident, write your \
final answer citing course_id and course_title for every course you recommend. Only cite courses returned \
by one of your tools this conversation — never recommend a course you didn't look up. Never invent a \
course_title — if a tool result gives you a course_id with no title, cite it by course_id alone rather \
than guessing. If nothing relevant turns up after searching, say so plainly instead of guessing.

Tools:
- search_courses: semantic search by topic/interest. Call it more than once with a narrower or broader \
phrasing if the first results aren't a good match.
- check_degree_path: look up the fundamental (required) and elective courses for a COMS track/concentration. \
Call this whenever the student mentions a major, concentration, track, or degree requirement — prefer its \
results over a topic guess, and mention when a course counts toward the track's requirements.
- check_schedule_conflict: check whether a candidate course's meeting time conflicts with something already \
on the student's schedule. This tool already has access to the student's current schedule — never ask the \
student to tell you their schedule or meeting times, just call it with the candidate course_id. Whenever \
schedule fit matters (the student asks for something that "fits" their schedule, mentions conflicts, or \
you're about to recommend multiple candidates from search_courses/check_degree_path), check each candidate \
before finalizing your answer. If a candidate conflicts, quietly try another candidate instead of presenting \
one you already know won't work — only mention a conflict if the student asked about that specific course, \
or nothing else fits."""


def _build_search_tool(seen_course_ids: set[str]):
    @tool
    def search_courses(query: str) -> list[dict]:
        """Semantic search over Columbia course syllabi. Returns the closest-matching
        courses (course_id, course_title, department, course_level, syllabus_summary,
        schedule_time, similarity) for the given topic/interest. Call again with
        different phrasing if the results don't look relevant."""
        embedding = get_embedding_model().embed_query(query)
        results = search_courses_by_embedding(embedding, match_count=5)
        seen_course_ids.update(r["course_id"] for r in results if r.get("course_id"))
        return results

    return search_courses


def _build_degree_path_tool(seen_course_ids: set[str]):
    @tool
    def check_degree_path(track_name: str) -> dict:
        """Look up the fundamental (required) and elective courses for a Columbia
        COMS degree track/concentration, e.g. "Machine Learning", "Natural Language
        Processing", "Software Systems", "Computer Security". Call this when the
        student mentions a major, concentration, track, or degree requirement. If
        track_name doesn't match, the result lists the available track names so
        you can retry with the right one. Course entries include course_title when
        known — don't guess a title for one that comes back without it."""
        result = get_degree_path(track_name)
        if result is None:
            return {"error": f"No track found matching {track_name!r}", "available_tracks": list_degree_paths()}

        required_ids = result.get("required_courses") or []
        elective_ids = result.get("elective_courses") or []
        seen_course_ids.update(required_ids)
        seen_course_ids.update(elective_ids)

        # check_degree_path only stores course_ids - without this, the model has
        # nothing but a bare id list and tends to guess plausible-sounding
        # titles for courses it never actually looked up. Exact-match only, so
        # an id with inconsistent formatting may come back title-less.
        details = {c["course_id"]: c for c in get_courses_by_ids(required_ids + elective_ids)}
        return {
            "degree_name": result["degree_name"],
            "required_courses": [details.get(cid, {"course_id": cid}) for cid in required_ids],
            "elective_courses": [details.get(cid, {"course_id": cid}) for cid in elective_ids],
        }

    return check_degree_path


def _times_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    # "HH:MM" 24h zero-padded strings compare correctly as plain strings.
    return a_start < b_end and b_start < a_end


def _find_conflicts(candidate_schedule: list, scheduled_courses: List[ScheduledCourseContext]) -> list[dict]:
    conflicts = []
    for session in candidate_schedule or []:
        day, start, end = session.get("day"), session.get("start"), session.get("end")
        if not (day and start and end):
            continue
        for course in scheduled_courses:
            for other in course.get("schedule_time") or []:
                if other.get("day") == day and _times_overlap(start, end, other.get("start", ""), other.get("end", "")):
                    conflicts.append(
                        {
                            "day": day,
                            "candidate_time": f"{start}-{end}",
                            "conflicts_with_course_id": course["course_id"],
                            "conflicts_with_course_title": course.get("course_title"),
                            "conflicts_with_time": f"{other.get('start')}-{other.get('end')}",
                        }
                    )
    return conflicts


def _build_conflict_tool(seen_course_ids: set[str], scheduled_courses: List[ScheduledCourseContext]):
    @tool
    def check_schedule_conflict(course_id: str) -> dict:
        """Check whether a candidate course's meeting time(s) conflict with any
        course already on the student's schedule. Returns the candidate's
        meeting times, whether there's a conflict, and which scheduled course(s)
        it conflicts with, if any."""
        schedule = get_course_schedule(course_id)
        if schedule is None:
            return {"error": f"No course found with course_id {course_id!r}"}
        seen_course_ids.add(course_id)
        conflicts = _find_conflicts(schedule, scheduled_courses)
        return {
            "course_id": course_id,
            "meeting_times": schedule,
            "has_conflict": len(conflicts) > 0,
            "conflicts": conflicts,
        }

    return check_schedule_conflict


def _schedule_note(scheduled_courses: list) -> str:
    # check_schedule_conflict knowing the schedule isn't enough - the model
    # needs to be told the schedule *exists* before it'll think to call the
    # tool at all. Without this, a request like "recommend one that fits my
    # schedule" (no candidate course_id named) reads as if there's nothing to
    # check against, and the model asks the student for their schedule
    # instead of using data it already has (observed via LangSmith).
    if not scheduled_courses:
        return "The student currently has no courses on their schedule."
    listing = ", ".join(f"{c['course_id']} ({c['course_title']})" for c in scheduled_courses)
    return (
        f"The student currently has {len(scheduled_courses)} course(s) already on their schedule: {listing}. "
        "You already have this - never ask the student for their schedule. Use check_schedule_conflict with "
        "a candidate course_id to see whether it fits."
    )


def recommend_course(state: AgentState) -> dict:
    scheduled_courses = state.get("scheduled_courses") or []
    # check_schedule_conflict means the answer can now legitimately name a
    # course already on the student's schedule (to explain *what* it
    # conflicts with) without ever having "looked it up" via a tool — seed
    # the grounded set with those up front so that doesn't trip verify_grounding.
    seen_course_ids: set[str] = {c["course_id"] for c in scheduled_courses}

    agent = create_agent(
        get_agent_llm(),
        tools=[
            _build_search_tool(seen_course_ids),
            _build_degree_path_tool(seen_course_ids),
            _build_conflict_tool(seen_course_ids, scheduled_courses),
        ],
        system_prompt=f"{SYSTEM_PROMPT}\n\n{_schedule_note(scheduled_courses)}",
    )

    # chat_history always ends with the current turn's question (see
    # message_utils.py), so this alone carries the full conversation - a bare
    # follow-up like "recommend one" only makes sense with the prior turns.
    history = state.get("chat_history") or []
    messages = to_langchain_messages(history) if history else [HumanMessage(state["query"])]
    feedback = state.get("verification_feedback")
    if feedback:
        messages.append(HumanMessage(f"Correction needed on your previous attempt: {feedback}"))

    result = agent.invoke({"messages": messages}, config={"recursion_limit": RECURSION_LIMIT})
    final_message = result["messages"][-1]
    answer = final_message.content if isinstance(final_message.content, str) else final_message.text

    return {
        "answer": answer,
        "cited_course_ids": find_course_id_mentions(answer),
        "context_course_ids": [normalize_course_id(cid) for cid in seen_course_ids],
    }
