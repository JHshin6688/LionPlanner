from datetime import datetime, timezone
from typing import Optional

from src.config import get_supabase_client


def get_course_hashes(course_id: str) -> Optional[dict]:
    """Return {'syllabus_hash': ..., 'review_hash': ...} for a course, or
    None if the course has never been stored."""
    client = get_supabase_client()
    response = (
        client.table("courses")
        .select("syllabus_hash, review_hash")
        .eq("course_id", course_id)
        .maybe_single()
        .execute()
    )
    return response.data if response else None


def upsert_course_analysis(course_id: str, data: dict) -> bool:
    """Insert or update the course row identified by course_id with the
    given column values (raw text, hashes, workload_analysis, etc.)."""
    client = get_supabase_client()
    payload = {
        **data,
        "course_id": course_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("courses").upsert(payload, on_conflict="course_id").execute()
    return True


def search_courses_by_embedding(embedding: list[float], match_count: int = 5) -> list[dict]:
    """Vector-similarity search over courses.syllabus_summary_embedding via the
    match_courses Postgres function (sql/schema2.sql) - supabase-py's query
    builder can't express pgvector's <=> operator directly, hence the RPC."""
    client = get_supabase_client()
    response = client.rpc(
        "match_courses",
        {"query_embedding": embedding, "match_count": match_count},
    ).execute()
    return response.data or []


def upsert_degree_path(degree_name: str, fundamental_courses: list, elective_courses: list) -> bool:
    """Insert or update the degree_path row identified by degree_name with the
    given fundamental and elective courses."""
    client = get_supabase_client()
    payload = {
        "degree_name": degree_name,
        "required_courses": fundamental_courses,
        "elective_courses": elective_courses,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("degree_path").upsert(payload, on_conflict="degree_name").execute()
    return True