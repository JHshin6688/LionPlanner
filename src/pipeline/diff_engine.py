import hashlib
from typing import Optional


def calculate_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def has_content_changed(
    new_syllabus_hash: str,
    new_review_hash: str,
    old_syllabus_hash: Optional[str],
    old_review_hash: Optional[str],
) -> bool:
    return new_syllabus_hash != old_syllabus_hash or new_review_hash != old_review_hash
