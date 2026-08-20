"""analyze_query: the entry node of the Ask LionPlanner graph.

Classifies the student's question into exactly one of three routes so the
graph can dispatch to the matching specialist node. Nothing else happens
here — no retrieval, no answering.

Uses the full chat_history, not just the latest message: a bare follow-up
like "can you recommend one?" is only classifiable as recommend_course in
light of what was asked before it.
"""
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agents.message_utils import to_langchain_messages
from src.agents.state import AgentState
from src.config import get_router_llm

ROUTER_SYSTEM_PROMPT = """You are the routing agent for Ask LionPlanner, a Columbia University course \
planning assistant. Read the conversation so far and decide which specialist should handle the student's \
latest message — including when it's a follow-up that only makes sense in light of earlier turns (e.g. \
"can you recommend one?" after discussing a topic). Do not answer the question yourself."""


class QueryRoute(BaseModel):
    route: Literal["recommend_course", "analyze_workload", "general_question"] = Field(
        ...,
        description=(
            "recommend_course: the student wants a course that teaches/covers some topic, asks for a course "
            "recommendation matching an interest or goal, asks about degree/track/major requirements, or "
            "asks about a *specific course they name* that isn't already on their schedule — including "
            "whether it's worth taking or whether it would fit/conflict with their schedule. Anything "
            "involving a course not already on their calendar goes here, even if the question also "
            "mentions their current schedule.\n"
            "analyze_workload: the student asks about the workload, difficulty, or how demanding the "
            "courses *already on their schedule* are — no course outside their current calendar is "
            "involved.\n"
            "general_question: anything else — a question the model can answer directly without looking "
            "up specific courses or the student's schedule."
        ),
    )
    reasoning: str = Field(..., description="One sentence on why this route was chosen.")


def analyze_query(state: AgentState) -> dict:
    llm = get_router_llm().with_structured_output(QueryRoute)
    history = to_langchain_messages(state.get("chat_history") or [])
    messages = [SystemMessage(ROUTER_SYSTEM_PROMPT), *(history or [HumanMessage(state["query"])])]
    result: QueryRoute = llm.invoke(messages)
    return {"route": result.route}
