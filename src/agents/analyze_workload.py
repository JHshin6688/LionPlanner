"""analyze_workload: a fixed workflow node — answers questions about the
workload/difficulty of the student's *current* schedule.

Unlike recommend_course, this needs no retrieval and no agent autonomy: which
data is relevant is already fully known (the courses on the schedule), so
there's nothing for a model-directed search loop to decide. The frontend
sends the scheduled courses' workload_analysis straight through in the
request, and this node makes exactly one grounded LLM call over that data.

Generates plain text (not structured output) so src/api/main.py can stream it
token-by-token; `cited_course_ids` is recovered from the text afterward via
src/agents/text_utils.py rather than self-reported by the model. See that
module's docstring for the tradeoff.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.message_utils import to_langchain_messages
from src.agents.state import AgentState
from src.agents.text_utils import find_course_id_mentions, normalize_course_id
from src.config import get_agent_llm

SYSTEM_PROMPT = """You are LionPlanner's workload analysis assistant. You are given the workload_analysis \
(exam / coding / team_project / reading_essay / lab_experiment scores, evidence quotes, and weekly-hour \
estimates) for every course currently on the student's schedule. Answer the student's question by \
reasoning over that data only — name the specific courses driving the workload, and give a concrete \
weekly-hours estimate when asked how demanding the semester will be. Never invent facts not present in \
the provided data, and never discuss a course that isn't in it. If the schedule is empty, say so instead \
of guessing. Always refer to a course by its exact course_id (e.g. COMS-W4118) at least once so it's \
identifiable."""

HUMAN_PROMPT = """Scheduled courses (JSON):
{schedule}

Student question: {query}{feedback_block}"""


def analyze_workload(state: AgentState) -> dict:
    scheduled = state.get("scheduled_courses") or []
    feedback = state.get("verification_feedback")
    feedback_block = f"\n\nCorrection needed on your previous attempt: {feedback}" if feedback else ""

    # chat_history always ends with the current turn's question (see
    # message_utils.py) - everything before that is prior conversation, which
    # goes in as plain history; the schedule data is attached only to the
    # final (current) question, not repeated on every historical turn.
    history = state.get("chat_history") or []
    prior_turns = to_langchain_messages(history[:-1]) if history else []
    latest_query = history[-1]["content"] if history else state["query"]

    human_content = HUMAN_PROMPT.format(
        schedule=scheduled or "(the student has not added any courses to their schedule yet)",
        query=latest_query,
        feedback_block=feedback_block,
    )

    llm = get_agent_llm()
    messages = [SystemMessage(SYSTEM_PROMPT), *prior_turns, HumanMessage(human_content)]
    response = llm.invoke(messages)
    answer = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "answer": answer,
        "cited_course_ids": find_course_id_mentions(answer),
        "context_course_ids": [normalize_course_id(c["course_id"]) for c in scheduled],
    }
