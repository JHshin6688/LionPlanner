import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel

from src.config import get_analyzer_llm
from src.schemas.workload import DimensionScore, WorkloadAnalysis2, WorkloadScores, WorkloadSummary

RULES_BLOCK = """Rules:
1. Base every score strictly on evidence found in the provided syllabus and review text. Never invent facts.
2. Every `evidence_quotes` entry must be a verbatim quote copied from the provided text, never paraphrased.
3. If this dimension has no supporting evidence, set the score to 0 and leave `evidence_quotes` empty.
4. Calibrate the score against the anchor point above so scores stay comparable across different courses."""

# Per-category anchor point (unchanged from the original single-prompt anchors)
# and a fabricated one-shot example used to calibrate that category in isolation.
CATEGORY_CONFIG = {
    "exam": {
        "display_name": "Exam",
        "anchor": "Exam Score 90+: Heavy theory courses with the majority of the grade dependent on midterm/final exams.",
        "example_course": "Theoretical Foundations of Computing (fabricated example, not a real course)",
        "example_syllabus": (
            "### Grading Breakdown\n"
            "- Midterm Exam: 30%\n"
            "- Final Exam: 35%\n"
            "- Weekly Problem Sets: 20%\n"
            "- Participation: 15%\n\n"
            "**Exam Policy**: Both exams are closed-book, closed-note, and cover all lecture material "
            "cumulatively. No makeup exams offered except for documented emergencies."
        ),
        "example_reviews": (
            "## AI-Generated Summary\n"
            "Students consistently describe the exams as the deciding factor in this class. Both are "
            "closed-book and cumulative, and reviewers note that strong problem-set performance does not "
            "offset a weak exam grade.\n\n"
            "## Most Agreed Review\n"
            "Theoretical Foundations of Computing · Nov 2024\n\n"
            "The exams are everything in this class. Homework barely moves the needle - I got full marks "
            "on every problem set but still ended up with a B because I choked on the final. Study the "
            "practice exams religiously.\n\n"
            "Workload\n"
            "Midterm 30%, Final 35%, problem sets only 20%. Both exams are closed-book and cover everything "
            "cumulatively."
        ),
        "example_output": {
            "score": 93,
            "evidence_quotes": [
                "Midterm Exam 30%, Final Exam 35%",
                "The exams are everything in this class.",
            ],
            "analysis": (
                "65% of the final grade is determined by two cumulative, closed-book exams with no makeup "
                "option, and the review confirms that exam performance - not weekly homework - decides the "
                "outcome. This matches the 90+ anchor for exam-driven courses."
            ),
        },
    },
    "coding": {
        "display_name": "Coding",
        "anchor": "Coding Score 95+: Courses with six demanding C projects throughout the semester.",
        "example_course": "Systems Programming Lab (fabricated example, not a real course)",
        "example_syllabus": (
            "### Programming Projects\n"
            "| Project | Topic | Language |\n"
            "|---|---|---|\n"
            "| P1 | Shell Implementation | C |\n"
            "| P2 | Process Scheduler | C |\n"
            "| P3 | Virtual Memory Manager | C |\n"
            "| P4 | File System | C |\n"
            "| P5 | Device Driver | C |\n"
            "| P6 | Networking Stack | C |\n\n"
            "Each project builds on the previous one and requires a full working C implementation of a core "
            "OS subsystem."
        ),
        "example_reviews": (
            "## AI-Generated Summary\n"
            "Reviewers agree the six C projects define the workload of this course. Multiple reviews "
            "describe spending entire weekends debugging low-level bugs, with the virtual memory and file "
            "system projects singled out as the hardest.\n\n"
            "## Most Agreed Review\n"
            "Systems Programming Lab · Mar 2025\n\n"
            "Six C projects back to back, each one nastier than the last. The virtual memory manager alone "
            "ate two full weekends of my life chasing a segfault.\n\n"
            "Workload\n"
            "Six cumulative C projects (P1-P6), roughly 30-40 hours each once you're deep into debugging."
        ),
        "example_output": {
            "score": 95,
            "evidence_quotes": [
                "Six programming projects (P1-P6), each requiring a full C implementation of a core OS subsystem",
                "The virtual memory manager alone ate two full weekends of my life chasing a segfault.",
            ],
            "analysis": (
                "Six cumulative, low-level C implementation projects covering core OS subsystems is an "
                "unusually heavy coding load, and the review's estimate of 30-40 hours per project across two "
                "months of debugging matches the 95+ anchor for six demanding C projects."
            ),
        },
    },
    "team_project": {
        "display_name": "Team Project",
        "anchor": "Team Project Score 90+: Semester-long team capstone with weekly deliverables.",
        "example_course": "Applied Software Studio (fabricated example, not a real course)",
        "example_syllabus": (
            "### Final Team Project (40% of grade)\n"
            "- Teams of 4 design, build, and deploy a full-stack application over 10 weeks\n"
            "- **Weekly deliverables**: sprint plan, sprint review, and demo to a simulated client\n"
            "- Mandatory on-call rotation during the final two weeks of the semester"
        ),
        "example_reviews": (
            "## AI-Generated Summary\n"
            "The consensus across reviews is that the semester-long team capstone dominates the course. "
            "Students repeatedly mention weekly sprint deliverables and a simulated client demo as the "
            "main time sink, more than any individual assignment.\n\n"
            "## Most Agreed Review\n"
            "Applied Software Studio · May 2025\n\n"
            "This class is basically a part-time job for 10 weeks. Weekly sprint reviews with a 'client', "
            "constant Slack pings from teammates, and a mandatory on-call week at the end.\n\n"
            "Workload\n"
            "Team capstone (40% of grade), 4-person teams, weekly graded sprint deliverables plus a "
            "two-week on-call rotation before the final demo."
        ),
        "example_output": {
            "score": 91,
            "evidence_quotes": [
                "teams of 4 design, build, and deploy a full-stack application over 10 weeks",
                "This class is basically a part-time job for 10 weeks.",
            ],
            "analysis": (
                "A 10-week, 40%-of-grade team capstone with weekly graded deliverables and a mandatory "
                "on-call rotation matches the anchor for a semester-long team capstone with weekly "
                "deliverables, and the review confirms the project dominated students' time."
            ),
        },
    },
    "reading_essay": {
        "display_name": "Reading/Essay",
        "anchor": "Reading/Essay Score 90+: >=150 pages/week of reading with graded response essays.",
        "example_course": "Seminar in Critical Theory (fabricated example, not a real course)",
        "example_syllabus": (
            "### Weekly Readings & Responses\n"
            "- Two full academic papers assigned each week (~80-100 pages total)\n"
            "- 1500-word graded response essay due before each class discussion\n"
            "- Essays are graded on close reading and original argumentation, not summary"
        ),
        "example_reviews": (
            "## AI-Generated Summary\n"
            "Reviewers describe the reading load as the most demanding part of the course, with two dense "
            "papers assigned weekly and a graded response essay due every week. Several note that skimming "
            "is not viable if you want a good essay grade.\n\n"
            "## Most Agreed Review\n"
            "Seminar in Critical Theory · Oct 2025\n\n"
            "150 pages a week, every week, plus a 1500-word essay that actually gets graded closely. You "
            "cannot fake your way through this one.\n\n"
            "Workload\n"
            "Two papers a week (~80-100 pages total) and a weekly 1500-word response essay graded on "
            "argumentation, not summary."
        ),
        "example_output": {
            "score": 90,
            "evidence_quotes": [
                "reading two full academic papers (~80-100 pages total) plus a 1500-word graded response essay",
                "150 pages a week, every week, plus a 1500-word essay that actually gets graded closely.",
            ],
            "analysis": (
                "Roughly 150 pages of dense academic reading per week combined with a weekly graded essay "
                "meets the >=150 pages/week threshold, and the review confirms the reading volume directly "
                "translates into a comparable essay-writing burden."
            ),
        },
    },
    "lab_experiment": {
        "display_name": "Lab/Experiment",
        "anchor": "Lab/Experiment Score 90+: >=6 hours/week of mandatory in-person lab or hardware work.",
        "example_course": "Applied Circuits Lab (fabricated example, not a real course)",
        "example_syllabus": (
            "### Lab Requirements\n"
            "- **Scheduled lab session**: 3 hours/week, mandatory attendance\n"
            "- **Open lab time**: an additional 3-4 hours/week required to complete hardware builds\n"
            "- Lab notebooks and circuit boards are graded weekly"
        ),
        "example_reviews": (
            "## AI-Generated Summary\n"
            "Multiple reviews point to the mandatory lab hours as the defining workload factor. Between "
            "the scheduled session and the extra open-lab time needed to finish the hardware builds, "
            "students report spending well over 6 hours a week in the lab.\n\n"
            "## Most Agreed Review\n"
            "Applied Circuits Lab · Feb 2025\n\n"
            "Between the 3-hour scheduled lab and the extra open-lab hours to actually finish the circuit "
            "board, you're looking at 6+ hours a week minimum in that lab.\n\n"
            "Workload\n"
            "Mandatory 3-hour lab session plus 3-4 required open-lab hours weekly to complete hardware "
            "builds; notebooks graded weekly."
        ),
        "example_output": {
            "score": 92,
            "evidence_quotes": [
                "Weekly 3-hour mandatory lab sessions plus an additional 3-4 hours of required open-lab time",
                "you're looking at 6+ hours a week minimum in that lab.",
            ],
            "analysis": (
                "A mandatory 3-hour weekly lab session plus 3-4 additional required open-lab hours totals "
                "6+ hours per week of in-person hardware work, matching the >=6 hours/week anchor for "
                "lab/experiment-heavy courses."
            ),
        },
    },
}


def _category_system_prompt(config: dict) -> str:
    return f"""You are an expert academic workload analyst for Columbia University courses.

            Score the course's {config["display_name"]} workload intensity on a 0-100 scale, calibrated against this anchor point:
            - {config["anchor"]}

            {RULES_BLOCK}"""


def _category_example_human(config: dict) -> str:
    return f"""Course: {config["example_course"]}

            Refer to this course's syllabus and to student reviews about the instructor teaching this course when analyzing the {config["display_name"]} workload.
            Within the reviews, prioritize the "AI-Generated Summary" and "Most Agreed Review" sections as the most reliable signal of the instructor's typical workload.

            ## Raw Syllabus (Markdown)
            {config["example_syllabus"]}

            ## Raw Student Reviews (Markdown)
            {config["example_reviews"]}

            Analyze the {config["display_name"]} workload dimension for this course and produce the structured output."""


CATEGORY_USER_PROMPT = """Course: {{course_id}} - {{course_title}} (Instructor: {{instructor_name}})

            Refer to this course's syllabus and to student reviews about the instructor teaching this course when analyzing the {display_name} workload.
            Within the reviews, prioritize the "AI-Generated Summary" and "Most Agreed Review" sections as the most reliable signal of the instructor's typical workload.

            ## Raw Syllabus (Markdown)
            {{raw_syllabus}}

            ## Raw Student Reviews (Markdown)
            {{raw_reviews}}

            Analyze the {display_name} workload dimension for this course and produce the structured output."""



SUMMARY_SYSTEM_PROMPT = """You are an expert academic workload analyst for Columbia University courses.
            Refer to the provided workload analysis when estimating weekly out-of-class hours,
            summarizing the findings, and identifying the top stress factors. Never invent facts."""

SUMMARY_USER_PROMPT = """Course: {course_id} - {course_title} (Instructor: {instructor_name})

            ## Workload Analysis
            {workload_scores}

            Estimate the weekly out-of-class workload hours, list the top 2-3 burnout risk tags, and write a 3-line
            summary of this course."""


def build_category_chain(llm, category: str):
    config = CATEGORY_CONFIG[category]
    structured_llm = llm.with_structured_output(DimensionScore)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _category_system_prompt(config)),
            ("human", _category_example_human(config)),
            ("ai", json.dumps(config["example_output"]).replace("{", "{{").replace("}", "}}")),
            ("human", CATEGORY_USER_PROMPT.format(display_name=config["display_name"])),
        ]
    )
    return prompt | structured_llm


def build_summary_chain(llm):
    structured_llm = llm.with_structured_output(WorkloadSummary)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SUMMARY_SYSTEM_PROMPT),
            ("human", SUMMARY_USER_PROMPT),
        ]
    )
    return prompt | structured_llm


def build_analyzer_chain():
    llm = get_analyzer_llm()
    branches = {category: build_category_chain(llm, category) for category in CATEGORY_CONFIG}
    return RunnableParallel(**branches)


def analyze_course2(
    course_id: str,
    course_title: str,
    instructor_name: str,
    raw_syllabus: str,
    raw_reviews: str,
) -> WorkloadAnalysis2:
    chain = build_analyzer_chain()
    results = chain.invoke(
        {
            "course_id": course_id,
            "course_title": course_title,
            "instructor_name": instructor_name,
            "raw_syllabus": raw_syllabus or "(No syllabus text found)",
            "raw_reviews": raw_reviews or "(No review text found)",
        }
    )

    workload_scores = WorkloadScores(
        exam=results["exam"],
        coding=results["coding"],
        team_project=results["team_project"],
        reading_essay=results["reading_essay"],
        lab_experiment=results["lab_experiment"],
    )

    # run summary chain by using workload_scores as input to the summary chain
    summary_chain = build_summary_chain(get_analyzer_llm())
    workload_scores_json = workload_scores.model_dump_json()
    summary = summary_chain.invoke(
        {
            'course_id': course_id,
            'course_title': course_title,
            'instructor_name': instructor_name,
            'workload_scores': workload_scores_json,
        }
    )

    return WorkloadAnalysis2(
        workload_scores=workload_scores,
        burnout_risk_tags=summary.burnout_risk_tags,
        weekly_hours_estimated=summary.weekly_hours_estimated,
        overall_summary=summary.overall_summary,
    )
