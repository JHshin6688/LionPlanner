from typing import List, Literal

from pydantic import BaseModel


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ScheduledCourseIn(BaseModel):
    course_id: str
    course_title: str
    workload_analysis: dict


class ChatRequest(BaseModel):
    query: str
    chat_history: List[ChatMessageIn] = []
    scheduled_courses: List[ScheduledCourseIn] = []


class ChatResponse(BaseModel):
    answer: str
    route: Literal["recommend_course", "analyze_workload", "general_question"]
