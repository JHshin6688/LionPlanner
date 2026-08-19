"""analyze_query: the entry node of the Ask LionPlanner graph.

Classifies the student's question into exactly one of three routes so the
graph can dispatch to the matching specialist node. Nothing else happens
here — no retrieval, no answering.
"""
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import get_router_llm

ROUTER_SYSTEM_PROMPT = """You are the routing agent for Ask LionPlanner, a Columbia University course \
planning assistant. Read the student's question and decide which specialist should handle it. Do not \
answer the question yourself."""


class QueryRoute(BaseModel):
    route: Literal["recommend_course", "analyze_workload", "general_question"] = Field(
        ...,
        description=(
            "recommend_course: the student wants a course that teaches/covers some topic, or asks for a "
            "course recommendation matching an interest or goal.\n"
            "analyze_workload: the student asks about the workload, difficulty, or how demanding their "
            "*current schedule* (the courses already on their calendar) is or would be.\n"
            "general_question: anything else — a question the model can answer directly without looking "
            "up specific courses or the student's schedule."
        ),
    )
    reasoning: str = Field(..., description="One sentence on why this route was chosen.")


def build_router_chain():
    llm = get_router_llm()
    structured_llm = llm.with_structured_output(QueryRoute)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ROUTER_SYSTEM_PROMPT),
            ("human", "{query}"),
        ]
    )
    return prompt | structured_llm


def analyze_query(state: AgentState) -> dict:
    chain = build_router_chain()
    result: QueryRoute = chain.invoke({"query": state["query"]})
    return {"route": result.route}
