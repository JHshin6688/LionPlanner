"""analyze_workload: a fixed workflow node — answers questions about the
workload/difficulty of the student's *current* schedule.

Unlike recommend_course, this needs no retrieval and no agent autonomy: which
data is relevant is already fully known (the courses on the schedule), so
there's nothing for a model-directed search loop to decide. The frontend
sends the scheduled courses' workload_analysis straight through in the
request, and this node makes exactly one grounded LLM call over that data.
"""
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import get_agent_llm

SYSTEM_PROMPT = """You are LionPlanner's workload analysis assistant. You are given the workload_analysis \
(exam / coding / team_project / reading_essay / lab_experiment scores, evidence quotes, and weekly-hour \
estimates) for every course currently on the student's schedule. Answer the student's question by \
reasoning over that data only — name the specific courses driving the workload, and give a concrete \
weekly-hours estimate when asked how demanding the semester will be. Never invent facts not present in \
the provided data, and never discuss a course that isn't in it. If the schedule is empty, say so instead \
of guessing. List the course_id of every course your answer specifically discusses in `cited_course_ids`."""

HUMAN_PROMPT = """Scheduled courses (JSON):
{schedule}

Student question: {query}{feedback_block}"""


class WorkloadAnswer(BaseModel):
    answer: str = Field(..., description="The final answer shown to the student.")
    cited_course_ids: List[str] = Field(
        default_factory=list, description="course_id of every scheduled course the answer specifically discusses."
    )


def analyze_workload(state: AgentState) -> dict:
    scheduled = state.get("scheduled_courses") or []
    feedback = state.get("verification_feedback")
    feedback_block = f"\n\nCorrection needed on your previous attempt: {feedback}" if feedback else ""

    llm = get_agent_llm().with_structured_output(WorkloadAnswer)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )
    chain = prompt | llm
    result: WorkloadAnswer = chain.invoke(
        {
            "schedule": scheduled or "(the student has not added any courses to their schedule yet)",
            "query": state["query"],
            "feedback_block": feedback_block,
        }
    )

    return {
        "answer": result.answer,
        "cited_course_ids": result.cited_course_ids,
        "context_course_ids": [c["course_id"] for c in scheduled],
    }
