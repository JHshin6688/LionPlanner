from typing import List, Optional

import requests

from src.config import get_jina_api_key

JINA_READER_BASE = "https://r.jina.ai/"


def scrape_markdown(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch a clean Markdown rendering of `url` via the Jina Reader API.
    Returns None on any request failure so callers can skip bad sources."""
    headers = {}
    api_key = get_jina_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(f"{JINA_READER_BASE}{url}", headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException:
        return None


def scrape_syllabus(urls: List[str]) -> str:
    """Return the Markdown of the first URL that scrapes successfully."""
    for url in urls:
        markdown = scrape_markdown(url)
        if markdown:
            return markdown
    return ""


def scrape_reviews(urls: List[str]) -> str:
    """Concatenate all successfully scraped review pages into one Markdown block."""
    blocks = []
    for url in urls:
        markdown = scrape_markdown(url)
        if markdown:
            blocks.append(f"## Source: {url}\n\n{markdown}")
    return "\n\n---\n\n".join(blocks)
