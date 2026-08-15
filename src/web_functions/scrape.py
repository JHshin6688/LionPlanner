from typing import List, Optional

import requests
from firecrawl import Firecrawl

from src.config import get_firecrawl_api_key, get_jina_api_key

JINA_READER_BASE = "https://r.jina.ai/"


def scrape_markdown_with_jina(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch a clean Markdown rendering of `url` via the Jina Reader API.
    Returns None on any request failure so callers can skip bad sources."""
    headers = {}
    api_key = get_jina_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Timeout"] = "100"

    try:
        response = requests.get(f"{JINA_READER_BASE}{url}", headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException:
        return None


def scrape_markdown_with_firecrawl(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch a clean Markdown rendering of `url` via the Firecrawl API.
    Returns None on any failure (missing API key, request error, no markdown
    in the response) so callers can skip bad sources."""
    api_key = get_firecrawl_api_key()
    if not api_key:
        return None

    try:
        app = Firecrawl(api_key=api_key)
        document = app.scrape(url, formats=["markdown"], timeout=timeout * 1000)
        return document.markdown or None
    except Exception:
        return None


def scrape_markdown(url: str, timeout: int = 30) -> Optional[str]:
    """Try Firecrawl first (handles JS-rendered pages Jina can't), then fall
    back to Jina Reader if Firecrawl is unavailable or fails on this URL."""
    markdown = scrape_markdown_with_firecrawl(url, timeout=timeout)
    if markdown:
        print(f"Scraped Markdown from {url} via Firecrawl")
        return markdown
    print(f"Firecrawl failed or unavailable for {url}, falling back to Jina Reader")
    return scrape_markdown_with_jina(url, timeout=timeout)


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
