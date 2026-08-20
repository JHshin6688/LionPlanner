from pydantic import BaseModel

class Course (BaseModel):
    title : str
    course_id : str
    instructor : str
    department : str
    credits : int
    course_level : int
    days : str
    time : str
    syllabus_url : str
    prof_review_url : str