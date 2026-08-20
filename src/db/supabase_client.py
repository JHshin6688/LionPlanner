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


def update_course_fields(course_id: str, data: dict) -> bool:
    """Patch only the given columns on an existing course row. Unlike
    upsert_course_analysis, this is a plain UPDATE (not INSERT ... ON CONFLICT
    DO UPDATE) - required for partial-column edits, since course_title/
    instructor_name/department are NOT NULL with no default, so upsert's
    speculative INSERT branch fails on them even when the row already exists
    and would ultimately just be updated."""
    client = get_supabase_client()
    payload = {
        **data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("courses").update(payload).eq("course_id", course_id).execute()
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


def get_course_schedule(course_id: str) -> Optional[list]:
    """schedule_time for a single course by exact course_id, or None if the
    course doesn't exist. Used by recommend_course's check_schedule_conflict
    tool - a direct lookup rather than relying on the course having already
    turned up in a search_courses result this turn."""
    client = get_supabase_client()
    response = (
        client.table("courses")
        .select("schedule_time")
        .eq("course_id", course_id)
        .maybe_single()
        .execute()
    )
    if not response or not response.data:
        return None
    return response.data.get("schedule_time")


def get_courses_by_ids(course_ids: list[str]) -> list[dict]:
    """course_id/course_title/department/course_level for a set of course_ids.
    Used to enrich check_degree_path's results with real titles instead of
    letting the model guess them from a bare course_id list - exact match
    only, so a track's course_id list may not 100% match rows here if the
    scraped course_id formatting differs (see text_utils.py's docstring)."""
    if not course_ids:
        return []
    client = get_supabase_client()
    response = (
        client.table("courses")
        .select("course_id, course_title, department, course_level")
        .in_("course_id", course_ids)
        .execute()
    )
    return response.data or []


def get_degree_path(degree_name: str) -> Optional[dict]:
    """Case-insensitive partial match on degree_name (e.g. "ml" matches
    "Machine Learning"), since a student's phrasing rarely matches the exact
    track name stored in the table. Returns the first match, or None."""
    client = get_supabase_client()
    response = (
        client.table("degree_path")
        .select("degree_name, required_courses, elective_courses")
        .ilike("degree_name", f"%{degree_name}%")
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def list_degree_paths() -> list[str]:
    """All available degree_path track names - e.g. so a tool can suggest
    valid options when a student's phrasing doesn't match any of them."""
    client = get_supabase_client()
    response = client.table("degree_path").select("degree_name").execute()
    return [row["degree_name"] for row in (response.data or [])]


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


def _derive_chat_title(query: str, max_length: int = 60) -> str:
    title = " ".join(query.strip().split())
    if len(title) <= max_length:
        return title
    return title[:max_length].rstrip() + "…"


def save_chat_turn(session_id: str, query: str, answer: str) -> None:
    """Append a {"user", "ai"} turn to the chats row for this session,
    creating the row (with a title derived from the first question) on the
    session's first turn."""
    client = get_supabase_client()
    turn = {"user": query, "ai": answer}
    now = datetime.now(timezone.utc).isoformat()

    existing = client.table("chats").select("turns").eq("session_id", session_id).maybe_single().execute()

    if existing and existing.data:
        turns = [*existing.data["turns"], turn]
        client.table("chats").update({"turns": turns, "updated_at": now}).eq("session_id", session_id).execute()
    else:
        client.table("chats").insert(
            {"session_id": session_id, "title": _derive_chat_title(query), "turns": [turn]}
        ).execute()