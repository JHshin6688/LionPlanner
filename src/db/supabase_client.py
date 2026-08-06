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
