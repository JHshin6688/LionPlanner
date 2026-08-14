import re

# Header keywords that mark sections carrying no workload-intensity signal.
# Syllabi are scraped from arbitrary professor/department sites, so this can
# only catch generic boilerplate categories - not exact section names.
_SYLLABUS_BLOCKLIST_KEYWORDS = [
    "honesty",
    "cheating",
    "waitlist",
    "accessibility",
    "disability",
    "accommodation",
    "office hours",
    "contact",
    "staff"
]

_HEADER_RE = re.compile(r"^(#{1,6})\s+.*$", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

_REVIEW_START_MARKER = "## AI-Generated Summary"
_REVIEW_END_MARKERS = ["## Most Disagreed Review", "## All Reviews"]


def _split_into_sections(text: str) -> list[str]:
    """Split markdown into chunks starting at each header line, keeping any
    text before the first header as its own leading chunk."""
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [text]
    sections = [text[: matches[0].start()]]
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[match.start():end])
    return sections


def filter_syllabus_noise(raw_syllabus: str) -> str:
    """Strip images and boilerplate sections (honesty policy, contact info, etc.)
    that carry no workload-intensity signal, before the text reaches any LLM call."""
    if not raw_syllabus:
        return raw_syllabus

    text = _IMAGE_RE.sub("", raw_syllabus)
    kept_sections = []
    for section in _split_into_sections(text):
        stripped = section.strip()
        header_line = stripped.splitlines()[0] if stripped else ""
        header_lower = header_line.lower()
        if any(keyword in header_lower for keyword in _SYLLABUS_BLOCKLIST_KEYWORDS):
            continue
        kept_sections.append(section)

    return "".join(kept_sections).strip()


def filter_review_noise(raw_reviews: str) -> str:
    """Keep only the 'AI-Generated Summary' and 'Most Agreed Review' sections,
    the most reliable signal of an instructor's typical workload, and drop the
    surrounding nav/image/full-review-list boilerplate."""
    if not raw_reviews:
        return raw_reviews

    start = raw_reviews.find(_REVIEW_START_MARKER)
    if start == -1:
        # Page didn't match the expected CULPA layout - fall back to stripping
        # images only rather than dropping the review text entirely.
        return _IMAGE_RE.sub("", raw_reviews).strip()

    end = len(raw_reviews)
    for marker in _REVIEW_END_MARKERS:
        idx = raw_reviews.find(marker, start)
        if idx != -1:
            end = min(end, idx)

    return _IMAGE_RE.sub("", raw_reviews[start:end]).strip()
