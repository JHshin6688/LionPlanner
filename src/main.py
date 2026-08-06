import argparse
import json
from typing import List

from src.web_functions.scrape import scrape_reviews, scrape_syllabus
from src.web_functions.search import find_review_urls, find_syllabus_urls
from src.db.supabase_client import get_course_hashes, upsert_course_analysis
from src.pipeline.analyzer_pipeline import analyze_course
from src.pipeline.diff_engine import calculate_hash, has_content_changed
from src.schemas.course import Course

def run_course(course: Course, force_refresh: bool = False) -> None:
    course_id = course.course_id
    course_title = course.title
    instructor = course.instructor
    credits = course.credits
    course_level = course.course_level
    days = course.days
    time = course.time

    print(f"[{course_id}] Searching for syllabus and reviews...")
    syllabus_urls = find_syllabus_urls(course_id, course_title, instructor)
    review_urls = find_review_urls(course_id, instructor)

    print(f"[{course_id}] Scraping Markdown via Jina Reader...")
    raw_syllabus = scrape_syllabus(syllabus_urls)
    raw_reviews = scrape_reviews(review_urls)

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

    upsert_course_analysis(
        course_id,
        {
            "course_title": course_title,
            "instructor_name": instructor,
            "credits": credits,
            "course_level": course_level,
            "schedule_time": {"days": days, "time": time},
            "raw_syllabus": raw_syllabus,
            "raw_reviews": raw_reviews,
            "syllabus_hash": new_syllabus_hash,
            "review_hash": new_review_hash,
            "review_summary": analysis.review_summary_3lines,
            "workload_analysis": analysis.model_dump(),
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

    with open("src/courses_test.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            course = json.loads(line)
            courses.append(Course(**course))

    for course in courses:
        run_course(course, args.force_refresh)

if __name__ == "__main__":
    main()
