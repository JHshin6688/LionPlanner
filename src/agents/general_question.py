"""general_question: anything that doesn't need course-specific retrieval or
the student's schedule — answered directly by the model.

Unlike recommend_course/analyze_workload, this node has no tools and never
goes through verify_grounding (see graph.py - it routes straight to END). So
any specific course_id/number it mentions is pure model recall, not looked up
against our data - Columbia's catalog changes every semester, and the model
has no way to know if a course still exists, was renumbered, or never did
(observed: it once cited a plausible-sounding COMS number for a course that
doesn't exist in our DB). The system prompt below forbids citing specific
course_ids for exactly this reason; anything requiring a real course
reference belongs in recommend_course/analyze_workload, where it can be
checked against actual data.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.message_utils import to_langchain_messages
from src.agents.state import AgentState
from src.config import get_agent_llm

SYSTEM_PROMPT = """You are LionPlanner, an academic planning assistant for Columbia University students. \
Answer the student's question directly and concisely.

Never cite a specific course_id or course number (e.g. "COMS 4180", "COMS-W3157") — you have no access to \
the actual course catalog here, so you can't verify one exists, is still offered, or hasn't been \
renumbered. Discuss topics, fields, or skills in general terms instead. If the question would genuinely \
benefit from a specific course, tell the student to ask you to recommend one (or to check on their current \
schedule's workload, if that's what they need) instead of guessing a course_id yourself."""


def general_question(state: AgentState) -> dict:
    llm = get_agent_llm()
    history = to_langchain_messages(state.get("chat_history") or [])
    messages = [SystemMessage(SYSTEM_PROMPT), *(history or [HumanMessage(state["query"])])]
    response = llm.invoke(messages)
    return {"answer": response.content}
