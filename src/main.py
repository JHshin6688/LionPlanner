import argparse
import csv
import json
import sys

from langchain_core.tracers.context import tracing_v2_enabled

from src.web_functions.scrape import scrape_reviews, scrape_syllabus
from src.db.supabase_client import (
    get_course_hashes,
    upsert_course_total,
    upsert_courses_semester,
    upsert_degree_path,
    upsert_review,
)
from src.pipeline.analyzer_pipeline import analyze_course, build_syllabus_summary
from src.pipeline.diff_engine import calculate_hash, has_content_changed
from src.pipeline.embeddings import embed_syllabus_summary

COURSES_TOTAL_CSV = "src/data/courses_total.csv"
COURSES_SEMESTER_CSV = "src/data/courses_semester.csv"
PROFESSORS_CSV = "src/data/professors.csv"
PROFESSORS_SEMESTER_CSV = "src/data/professors_semester.csv"


def _load_instructor_set(csv_path: str) -> set[str]:
    with open(csv_path, "r", encoding="utf-8") as f:
        return {row["Instructor"].strip() for row in csv.DictReader(f, skipinitialspace=True)}


def _load_review_urls(csv_path: str) -> dict[str, str]:
    with open(csv_path, "r", encoding="utf-8") as f:
        return {row["Instructor"].strip(): row["Culpa URL"].strip() for row in csv.DictReader(f, skipinitialspace=True)}

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

def build_schedule_time(days: str, time: str) -> list[dict]:
    days_list = [day for day in days.split(" ")] if days else []
    start_time, end_time = time.split(" - ") if time else ("", "")
    start_time = convert_time_to_24h_format(start_time)
    end_time = convert_time_to_24h_format(end_time)
    return [{"day": day, "start": start_time, "end": end_time} for day in days_list]


def validate_instructor_coverage(courses_csv: str, professors_csv: str) -> None:
    """Every instructor referenced in courses_csv must have a row in
    professors_csv (that's where its review URL comes from) - fail fast with
    a clear message instead of hitting a missing-review_url surprise, or a
    FK violation, deep inside the pipeline."""
    course_instructors = _load_instructor_set(courses_csv)
    known_instructors = _load_instructor_set(professors_csv)
    missing = sorted(course_instructors - known_instructors)

    if missing:
        print(f"ERROR: {len(missing)} instructor(s) in {courses_csv} are missing from {professors_csv}:")
        for name in missing:
            print(f"  - {name}")
        sys.exit(1)


def scrape_course_content(syllabus_url: str, review_url: str) -> tuple[str, str, str, str]:
    """Returns (raw_syllabus, raw_reviews, syllabus_hash, review_hash)."""
    raw_syllabus = scrape_syllabus([syllabus_url])
    raw_reviews = scrape_reviews([review_url])
    return raw_syllabus, raw_reviews, calculate_hash(raw_syllabus), calculate_hash(raw_reviews)


def analyze_course_content(course_id: str, course_title: str, instructor: str, raw_syllabus: str, raw_reviews: str) -> dict:
    """Runs workload analysis + syllabus summary/embedding on already-scraped
    content. Returns the subset of a course_total row that scrape_course_content()
    doesn't already cover."""
    print(f"[{course_id}] Running LangChain workload analysis...")
    analysis = analyze_course(course_id, course_title, instructor, raw_syllabus, raw_reviews)
    syllabus_summary = build_syllabus_summary(raw_syllabus)
    syllabus_summary_embedding = embed_syllabus_summary(syllabus_summary.syllabus_summary)
    return {
        "workload_analysis": analysis.model_dump(),
        "syllabus_summary": syllabus_summary.syllabus_summary,
        "syllabus_summary_embedding": syllabus_summary_embedding,
    }


def scrape_and_analyze(course_id: str, course_title: str, instructor: str, syllabus_url: str, review_url: str) -> dict:
    """Scrape + run the full workload analysis for one (course, instructor)
    pairing, unconditionally. Used by the initial backfill, which has no
    existing hash to compare against."""
    print(f"[{course_id}] Scraping Markdown from Syllabus and Review URLs...")
    raw_syllabus, raw_reviews, syllabus_hash, review_hash = scrape_course_content(syllabus_url, review_url)
    result = analyze_course_content(course_id, course_title, instructor, raw_syllabus, raw_reviews)
    result.update(
        {
            "raw_syllabus": raw_syllabus,
            "raw_reviews": raw_reviews,
            "syllabus_hash": syllabus_hash,
            "review_hash": review_hash,
        }
    )
    return result


def store_course_analysis(
    course_id: str,
    instructor: str,
    course_title: str,
    department: str,
    credits: int,
    course_level: int,
    syllabus_url: str,
    review_url: str,
    result: dict,
) -> None:
    """Persist a scrape_and_analyze() result to the review and courses_total
    tables - the durable, semester-independent cache."""
    upsert_review(
        instructor,
        {
            "review_url": review_url,
            "raw_reviews": result["raw_reviews"],
            "review_hash": result["review_hash"],
        },
    )
    upsert_course_total(
        course_id,
        instructor,
        {
            "course_title": course_title,
            "department": department,
            "credits": credits,
            "course_level": course_level,
            "syllabus_url": syllabus_url,
            "raw_syllabus": result["raw_syllabus"],
            "syllabus_hash": result["syllabus_hash"],
            "syllabus_summary": result["syllabus_summary"],
            "syllabus_summary_embedding": result["syllabus_summary_embedding"],
            "workload_analysis": result["workload_analysis"],
        },
    )


def run_initial_backfill() -> None:
    """One-time bulk analysis of every course in courses_total.csv, assuming
    Supabase's courses_total/review tables start empty. This is deliberately
    NOT part of the regular per-semester run (main() below) - it re-analyzes
    the entire catalog unconditionally, which only makes sense as a rare,
    explicitly-triggered operation (`python -m src.main --backfill`), not
    something that runs on every pipeline invocation."""
    review_urls = _load_review_urls(PROFESSORS_CSV)

    with open(COURSES_TOTAL_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, skipinitialspace=True))

    for row in rows:
        course_id = row["CourseID"].strip()
        course_title = row["Title"].strip()
        instructor = row["Instructor"].strip()
        department = row["Department"].strip()
        credits = int(row["Credits"].strip())
        course_level = int(row["Level"].strip())
        syllabus_url = row["Syllabus URL"].strip()
        review_url = review_urls.get(instructor, "")

        result = scrape_and_analyze(course_id, course_title, instructor, syllabus_url, review_url)
        store_course_analysis(course_id, instructor, course_title, department, credits, course_level, syllabus_url, review_url, result)
        print(f"[{course_id}] Stored initial workload analysis in Supabase.")


def sync_courses_semester(force_refresh: bool = False) -> None:
    """For every course in courses_semester.csv: re-run workload analysis only
    if (a) this (course, instructor) pairing has never been analyzed
    (missing from courses_total), or (b) the freshly scraped syllabus/review
    content hashes differ from what's stored in courses_total/review. Either
    way, courses_semester is always upserted at the end - offering this
    course must be recorded even when the analysis itself was skipped."""
    review_urls = _load_review_urls(PROFESSORS_SEMESTER_CSV)

    with open(COURSES_SEMESTER_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, skipinitialspace=True))

    for row in rows:
        course_id = row["CourseID"].strip()
        course_title = row["Title"].strip()
        instructor = row["Instructor"].strip()
        department = row["Department"].strip()
        credits = int(row["Credits"].strip())
        course_level = int(row["Level"].strip())
        syllabus_url = row["Syllabus URL"].strip()
        review_url = review_urls.get(instructor, "")
        schedule_time = build_schedule_time(row["Days"], row["Time"])

        print(f"[{course_id}] Scraping Markdown to check for changes...")
        raw_syllabus, raw_reviews, new_syllabus_hash, new_review_hash = scrape_course_content(syllabus_url, review_url)

        existing = get_course_hashes(course_id, instructor)
        old_syllabus_hash = existing.get("syllabus_hash") if existing else None
        old_review_hash = existing.get("review_hash") if existing else None

        if existing and not force_refresh and not has_content_changed(
            new_syllabus_hash, new_review_hash, old_syllabus_hash, old_review_hash
        ):
            print(f"[{course_id}] No changes since last analysis - reusing courses_total.")
        else:
            reason = "new (course, instructor) pairing" if not existing else "content changed"
            print(f"[{course_id}] {reason} - running workload analysis...")
            result = analyze_course_content(course_id, course_title, instructor, raw_syllabus, raw_reviews)
            result.update(
                {
                    "raw_syllabus": raw_syllabus,
                    "raw_reviews": raw_reviews,
                    "syllabus_hash": new_syllabus_hash,
                    "review_hash": new_review_hash,
                }
            )
            store_course_analysis(course_id, instructor, course_title, department, credits, course_level, syllabus_url, review_url, result)

        upsert_courses_semester(course_id, instructor, schedule_time)
        print(f"[{course_id}] Synced courses_semester in Supabase.")


def main() -> None:
    parser = argparse.ArgumentParser(description="LionPlanner course workload data pipeline")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass the SHA-256 diff engine and re-run LLM analysis unconditionally (semester sync only)",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run the one-time bulk analysis of courses_total.csv instead of the regular semester sync",
    )
    args = parser.parse_args()

    validate_instructor_coverage(COURSES_TOTAL_CSV, PROFESSORS_CSV)
    validate_instructor_coverage(COURSES_SEMESTER_CSV, PROFESSORS_SEMESTER_CSV)

    degree_paths = {}
    with open("src/data/degree_path.json", "r", encoding="utf-8") as f:
        degree_path = json.load(f)
        for name, paths in degree_path.items():
            degree_paths[name] = {
                "fundamental": paths["fundamental"],
                "electives": paths["electives"],
            }

    for name, paths in degree_paths.items():
        upsert_degree_path(name, paths["fundamental"], paths["electives"])
        print(f"[{name}] Stored degree path in Supabase.")

    # Course-DB build traces go to their own LangSmith project rather than
    # whatever LANGCHAIN_PROJECT is set to (that's for Ask LionPlanner).
    with tracing_v2_enabled(project_name="lionplanner_db"):
        if args.backfill:
            run_initial_backfill()
        else:
            sync_courses_semester(args.force_refresh)


if __name__ == "__main__":
    main()
