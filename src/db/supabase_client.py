from datetime import datetime, timezone
from typing import Optional

from src.config import get_supabase_client


def get_course_hashes(course_id: str, instructor_name: str) -> Optional[dict]:
    """Return {'syllabus_hash': ..., 'review_hash': ...} for a (course,
    instructor) pairing, or None if that pairing has never been analyzed
    (i.e. no row in courses_total yet). syllabus_hash lives on courses_total,
    review_hash on review - two lookups since they're no longer one row."""
    client = get_supabase_client()
    syllabus_response = (
        client.table("courses_total")
        .select("syllabus_hash")
        .eq("course_id", course_id)
        .eq("instructor_name", instructor_name)
        .maybe_single()
        .execute()
    )
    if not syllabus_response or not syllabus_response.data:
        return None

    review_response = (
        client.table("review")
        .select("review_hash")
        .eq("instructor_name", instructor_name)
        .maybe_single()
        .execute()
    )
    return {
        "syllabus_hash": syllabus_response.data.get("syllabus_hash"),
        "review_hash": review_response.data.get("review_hash") if review_response and review_response.data else None,
    }


def get_all_workload_analyses() -> list[dict]:
    """course_id/course_title/workload_analysis for every (course, instructor)
    pairing ever analyzed (not just this semester's offerings) - used to
    audit workload_analysis contents (e.g. finding courses whose scores all
    came back 0)."""
    client = get_supabase_client()
    response = client.table("courses_total").select("course_id, course_title, workload_analysis").execute()
    return response.data or []


def upsert_review(instructor_name: str, data: dict) -> bool:
    """Insert or update the review row for this instructor (review_url,
    raw_reviews, review_hash)."""
    client = get_supabase_client()
    payload = {
        **data,
        "instructor_name": instructor_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("review").upsert(payload, on_conflict="instructor_name").execute()
    return True


def upsert_course_total(course_id: str, instructor_name: str, data: dict) -> bool:
    """Insert or update the courses_total row for this (course, instructor)
    pairing - course facts, scraped syllabus, and workload analysis. The
    durable, semester-independent cache the analysis pipeline writes to."""
    client = get_supabase_client()
    payload = {
        **data,
        "course_id": course_id,
        "instructor_name": instructor_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("courses_total").upsert(payload, on_conflict="course_id,instructor_name").execute()
    return True


def upsert_courses_semester(course_id: str, instructor_name: str, schedule_time: list) -> bool:
    """Insert or update this semester's offering row - just the (course,
    instructor) pairing plus schedule_time. Must run for every course in a
    pipeline pass even when courses_total's analysis was skipped (unchanged
    hash), since this is the only place "offered this semester" is recorded."""
    client = get_supabase_client()
    payload = {
        "course_id": course_id,
        "instructor_name": instructor_name,
        "schedule_time": schedule_time,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("courses_semester").upsert(payload, on_conflict="course_id,instructor_name").execute()
    return True


def search_courses_by_embedding(embedding: list[float], match_count: int = 5) -> list[dict]:
    """Vector-similarity search over courses_total.syllabus_summary_embedding,
    scoped to this semester's offerings, via the match_courses Postgres
    function (sql/schema_v2.sql) - supabase-py's query builder can't express
    pgvector's <=> operator directly, hence the RPC."""
    client = get_supabase_client()
    response = client.rpc(
        "match_courses",
        {"query_embedding": embedding, "match_count": match_count},
    ).execute()
    return response.data or []


def get_course_schedule(course_id: str) -> Optional[list]:
    """schedule_time for a single course by exact course_id, or None if it's
    not offered this semester. Used by recommend_course's check_schedule_conflict
    tool - a direct lookup rather than relying on the course having already
    turned up in a search_courses result this turn."""
    client = get_supabase_client()
    response = (
        client.table("courses_semester")
        .select("schedule_time")
        .eq("course_id", course_id)
        .maybe_single()
        .execute()
    )
    if not response or not response.data:
        return None
    return response.data.get("schedule_time")


def get_courses_by_ids(course_ids: list[str]) -> list[dict]:
    """course_id/course_title/department/course_level for a set of course_ids,
    scoped to this semester's offerings. Used to enrich check_degree_path's
    results with real titles instead of letting the model guess them from a
    bare course_id list - exact match only, so a track's course_id list may
    not 100% match rows here if the scraped course_id formatting differs
    (see text_utils.py's docstring)."""
    if not course_ids:
        return []
    client = get_supabase_client()
    response = (
        client.table("courses_semester_view")
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