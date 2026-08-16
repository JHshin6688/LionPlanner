from typing import List, Literal, Optional, TypedDict


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class ScheduledCourseContext(TypedDict):
    """Minimal course info the frontend sends for whatever is currently on the
    student's calendar. Used by analyze_workload; available to every node."""

    course_id: str
    course_title: str
    workload_analysis: dict


class AgentState(TypedDict, total=False):
    # Input
    query: str
    chat_history: List[ChatMessage]
    scheduled_courses: List[ScheduledCourseContext]

    # Set by analyze_query, consumed by the graph's conditional edge
    route: Literal["recommend_course", "analyze_workload", "general_question"]

    # Set by whichever specialist node runs (recommend_course / analyze_workload)
    answer: str
    cited_course_ids: List[str]  # course_ids the answer actually cites
    context_course_ids: List[str]  # course_ids the node actually had access to this turn

    # Set by verify_grounding
    grounded: bool
    verification_retries: int
    verification_feedback: Optional[str]
