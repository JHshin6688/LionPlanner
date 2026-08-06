from langchain_core.prompts import ChatPromptTemplate

from src.config import get_analyzer_llm
from src.schemas.workload import WorkloadAnalysis

SYSTEM_PROMPT = """You are an expert academic workload analyst for Columbia University courses.

Score the course across five dimensions (exam, coding, team_project, reading_essay, lab_experiment)
on a 0-100 workload intensity scale, calibrated against these fixed anchor points:

- Coding Score 95+: Courses like COMS 4118 (Operating Systems I) with six demanding C projects.
- Exam Score 90+: Heavy theory courses with >=60% of the grade dependent on midterm/final exams.
- Team Project Score 90+: Semester-long team capstone with weekly deliverables (e.g., COMS 4156 (Advanced Software Engineering)).
- Reading/Essay Score 90+: >=150 pages/week of reading with graded response essays.
- Lab/Experiment Score 90+: >=6 hours/week of mandatory in-person lab or hardware work.

Rules:
1. Base every score strictly on evidence found in the provided syllabus and review text. Never invent facts.
2. Every `evidence_quotes` entry must be a verbatim quote copied from the provided text, never paraphrased.
3. If a dimension has no supporting evidence, set its score to 0 and leave `evidence_quotes` empty.
4. Calibrate every score against the anchor points above so scores stay comparable across different courses.
"""

USER_PROMPT = """Course: {course_id} - {course_title} (Instructor: {instructor_name})

## Raw Syllabus (Markdown)
{raw_syllabus}

## Raw Student Reviews (Markdown)
{raw_reviews}

Analyze the workload for this course and produce the structured output."""


def build_analyzer_chain():
    structured_llm = get_analyzer_llm().with_structured_output(WorkloadAnalysis)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT),
        ]
    )
    return prompt | structured_llm


def analyze_course(
    course_id: str,
    course_title: str,
    instructor_name: str,
    raw_syllabus: str,
    raw_reviews: str,
) -> WorkloadAnalysis:
    chain = build_analyzer_chain()
    return chain.invoke(
        {
            "course_id": course_id,
            "course_title": course_title,
            "instructor_name": instructor_name,
            "raw_syllabus": raw_syllabus or "(No syllabus text found)",
            "raw_reviews": raw_reviews or "(No review text found)",
        }
    )
