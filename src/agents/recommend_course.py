"""recommend_course: the one *agent* node in the graph.

The student's interest can be vague or need more than one search ("Is there
anything interesting in the intersection of AI and biology?"), so unlike the
other nodes this one gets real autonomy: it's a `langchain.agents.create_agent`
agent (built on LangGraph under the hood) that can call `search_courses` as
many times as it needs (bounded by RECURSION_LIMIT below) before deciding it
has enough to answer.

Generates plain text for its final answer (no `response_format`) so
src/api/main.py can stream it token-by-token — the tool-calling turns along
the way carry no visible text (the system prompt tells the model not to
narrate before calling the tool), so only the final turn actually streams
anything to the client. `cited_course_ids` is recovered from that final text
via src/agents/text_utils.py rather than self-reported by the model; see that
module's docstring for the tradeoff vs. the old structured-output approach.
"""
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from src.agents.state import AgentState
from src.agents.text_utils import find_course_id_mentions, normalize_course_id
from src.config import get_agent_llm, get_embedding_model
from src.db.supabase_client import search_courses_by_embedding

# Caps how many search_courses <-> reasoning round-trips the agent can take
# before LangGraph forces a stop, so a stuck agent fails fast instead of
# looping indefinitely. Each round-trip is 2 supersteps (model, tool), plus 1
# for the initial model call - allows ~6 search calls (1 + 2*6 = 13 <= 16).
RECURSION_LIMIT = 16

SYSTEM_PROMPT = """You are LionPlanner's course recommendation assistant for Columbia University students. \
Use the search_courses tool to find courses relevant to the student's interest — call it more than once \
if the first results don't look like a good match, e.g. with a narrower or broader phrasing. Do not write \
any commentary before calling the tool — call it directly. Once you're confident, write your final answer \
citing course_id and course_title for every course you recommend. Only cite courses that search_courses \
actually returned this conversation — never recommend a course you didn't retrieve. If nothing relevant \
turns up after searching, say so plainly instead of guessing."""


def _build_search_tool(seen_course_ids: set[str]):
    @tool
    def search_courses(query: str) -> list[dict]:
        """Semantic search over Columbia course syllabi. Returns the closest-matching
        courses (course_id, course_title, department, course_level, syllabus_summary,
        similarity) for the given topic/interest. Call again with different phrasing
        if the results don't look relevant."""
        embedding = get_embedding_model().embed_query(query)
        results = search_courses_by_embedding(embedding, match_count=5)
        seen_course_ids.update(r["course_id"] for r in results if r.get("course_id"))
        return results

    return search_courses


def recommend_course(state: AgentState) -> dict:
    seen_course_ids: set[str] = set()
    agent = create_agent(
        get_agent_llm(),
        tools=[_build_search_tool(seen_course_ids)],
        system_prompt=SYSTEM_PROMPT,
    )

    messages = [HumanMessage(state["query"])]
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
