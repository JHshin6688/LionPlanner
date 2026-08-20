import argparse
import json
from typing import List
import csv

from langchain_core.tracers.context import tracing_v2_enabled

from src.web_functions.scrape import scrape_reviews, scrape_syllabus
# from src.web_functions.search import find_review_urls, find_syllabus_urls
from src.db.supabase_client import get_course_hashes, upsert_course_analysis, upsert_degree_path
from src.pipeline.analyzer_pipeline import analyze_course, build_syllabus_summary
from src.pipeline.diff_engine import calculate_hash, has_content_changed
from src.pipeline.embeddings import embed_syllabus_summary
from src.schemas.course import Course

def run_course(course: Course, force_refresh: bool = False) -> None:
    course_id = course.course_id
    course_title = course.title
    instructor = course.instructor
    department = course.department
    credits = course.credits
    course_level = course.course_level
    days_list = course.days
    time = course.time
    syllabus_url = course.syllabus_url
    review_url = course.prof_review_url

    start_time, end_time = time.split(" - ") if time else ("", "")
    time_list = [start_time, end_time]

    # days_list : Mon Wed -> ['Mon', 'Wed']
    days_list = [day for day in days_list.split(" ")] if days_list else []

    # "11:40am" -> 11:40, "2:10pm" -> 14:10
    def convert_time_to_24h_format(time_str: str) -> str:
        if not time_str:
            return ""
        time_part, period = time_str[:-2], time_str[-2:]
        hour, minute = map(int, time_part.split(":"))
        if period.lower() == "pm" and hour != 12:
            hour += 12
        elif period.lower() == "am" and hour == 12:
            hour = 0
        return f"{hour:02}:{minute:02}"
    
    time_list = [convert_time_to_24h_format(time) for time in time_list]

    schedule_time = [{"day": day, "start": time_list[0], "end": time_list[1]} for day in days_list]

    print(f"[{course_id}] Scraping Markdown from Syllabus and Review URLs...")
    raw_syllabus = scrape_syllabus([syllabus_url])
    raw_reviews = scrape_reviews([review_url])

    new_syllabus_hash = calculate_hash(raw_syllabus)
    new_review_hash = calculate_hash(raw_reviews)

    existing = get_course_hashes(course_id)
    old_syllabus_hash = existing.get("syllabus_hash") if existing else None
    old_review_hash = existing.get("review_hash") if existing else None

    if not force_refresh and not has_content_changed(
        new_syllabus_hash, new_review_hash, old_syllabus_hash, old_review_hash
    ):
        print(f"[{course_id}] Skipping LLM analysis - No content changes.")
        return

    print(f"[{course_id}] Running LangChain workload analysis...")
    analysis = analyze_course(course_id, course_title, instructor, raw_syllabus, raw_reviews)

    syllabus_summary = build_syllabus_summary(raw_syllabus)
    syllabus_summary_embedding = embed_syllabus_summary(syllabus_summary.syllabus_summary)

    upsert_course_analysis(
        course_id,
        {
            "course_title": course_title,
            "instructor_name": instructor,
            "department": department,
            "credits": credits,
            "course_level": course_level,
            "schedule_time": schedule_time,
            "syllabus_url": syllabus_url,
            "review_url": review_url,
            "raw_syllabus": raw_syllabus,
            "raw_reviews": raw_reviews,
            "syllabus_hash": new_syllabus_hash,
            "review_hash": new_review_hash,
            "workload_analysis": analysis.model_dump(),
            "syllabus_summary": syllabus_summary.syllabus_summary,
            "syllabus_summary_embedding": syllabus_summary_embedding,
        },
    )
    print(f"[{course_id}] Stored workload analysis in Supabase.")

def main() -> None:
    parser = argparse.ArgumentParser(description="LionPlanner course workload data pipeline")

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass the SHA-256 diff engine and re-run LLM analysis unconditionally",
    )
    args = parser.parse_args()
    courses = []
    degree_paths = {}

    with open("src/data/degree_path.json", "r", encoding="utf-8") as f:
        degree_path = json.load(f)
        for name, paths in degree_path.items():
            degree_paths[name] = {
                "fundamental": paths["fundamental"],
                "electives": paths["electives"]
            }

    for name, paths in degree_paths.items():
        upsert_degree_path(name, paths["fundamental"], paths["electives"])
        print(f"[{name}] Stored degree path in Supabase.")

    review_data = {}
    with open("src/data/professors.csv", "r", encoding="utf-8") as f:
        reviews = csv.reader(f)
        next(reviews)
        for row in reviews:
            instructor, review_url = row
            review_data[instructor] = review_url
            
    with open("src/data/courses.csv", "r", encoding="utf-8") as f:
        total_reader = csv.reader(f)
        next(total_reader)
        for row in total_reader:
            course_id, course_name, instructor, department, credits, course_level, days, time, syllabus_url = row
            course_data = {
                "title": course_name,
                "course_id": course_id,
                "instructor": instructor,
                "department": department,
                "credits": int(credits),
                "course_level": int(course_level),
                "days": days,
                "time": time,
                "syllabus_url": syllabus_url,
                "prof_review_url": review_data.get(instructor, "")
            }
            course = Course(**course_data)
            courses.append(course)

    # Course-DB build traces go to their own LangSmith project rather than
    # whatever LANGCHAIN_PROJECT is set to (that's for Ask LionPlanner).
    with tracing_v2_enabled(project_name="lionplanner_db"):
        for course in courses:
            run_course(course, args.force_refresh)

if __name__ == "__main__":
    main()
