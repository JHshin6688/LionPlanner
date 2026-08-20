"""Course-id extraction from free-text LLM output.

recommend_course and analyze_workload used to report `cited_course_ids` via
structured output (`response_format`/`with_structured_output`). That's clean
and precise, but structured output streams as JSON-field deltas, not clean
prose tokens - it's incompatible with the token-by-token streaming in
src/api/main.py. So both nodes now generate plain text, and this module
recovers `cited_course_ids` by scanning that text for course-id-shaped
substrings instead of asking the model to self-report them.

This is a real tradeoff, not a free lunch: it's a heuristic, not a
validator. course_id formatting in the scraped data isn't fully consistent
(e.g. "COMS W4180" vs "COMS-W3157"), so this can occasionally miss an
unusually-formatted id, or match a coincidental look-alike substring in
prose. verify_grounding.py's logic is unchanged - it still just checks
`cited_course_ids` against `context_course_ids` - but the precision of that
check now depends on this regex rather than the model's own structured
report.
"""
import re

# Loosely matches Columbia course-id-shaped tokens across the formats seen in
# scraped data: "COMS-W4118", "COMS W4118", "COMS4118", "COMS E6184" (E is
# Columbia's grad-level infix, W the undergrad/professional one - not just W,
# or every E-prefixed course silently fails to be recognized as cited at
# all, which doesn't just miss it - it makes grounding blind to it either
# way, since a hallucinated E-course would go undetected the same way a real
# one goes unrecognized).
#
# Deliberately NOT \b at the edges: Python's re treats Hangul as a "word"
# character, so \b silently fails to match right where a Korean particle is
# glued onto the id with no space (e.g. "COMS-W4111에" - "에" attaches
# directly, no space, because that's how Korean grammar works). That
# produced false negatives - the model correctly wrote the id, but the
# regex just didn't see it, undermining verify_grounding. Using ASCII-only
# lookarounds keeps the same intent (don't match "4118" out of "44118" or
# "COMS" out of "XCOMS") without assuming word boundaries exist in every
# language surrounding the match.
_COURSE_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2,6}[\s-]?[A-Z]?\d{3,4}(?![0-9])")


def normalize_course_id(course_id: str) -> str:
    """Collapse whitespace/hyphen differences so "COMS W4118" and
    "COMS-W4118" compare equal."""
    return re.sub(r"[\s-]+", "", course_id).upper()


def find_course_id_mentions(text: str) -> list[str]:
    """Return the normalized form of every course-id-shaped token found in
    `text`, deduplicated. Compare against a similarly-normalized
    context_course_ids list (see normalize_course_id)."""
    seen: dict[str, None] = {}
    for match in _COURSE_ID_PATTERN.finditer(text):
        seen.setdefault(normalize_course_id(match.group(0)), None)
    return list(seen)
