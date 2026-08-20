from typing import List, Literal

from pydantic import BaseModel


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ScheduleSessionIn(BaseModel):
    day: str
    start: str
    end: str


class ScheduledCourseIn(BaseModel):
    course_id: str
    course_title: str
    workload_analysis: dict
    schedule_time: List[ScheduleSessionIn] = []


class ChatRequest(BaseModel):
    session_id: str
    query: str
    chat_history: List[ChatMessageIn] = []
    scheduled_courses: List[ScheduledCourseIn] = []
