from typing import List

import requests

from src.config import get_serper_api_key

SERPER_SEARCH_URL = "https://google.serper.dev/search"

# Not used in the current implementation, but could be useful for future enhancements
def _search(query: str, num_results: int = 5) -> List[dict]:
    response = requests.post(
        SERPER_SEARCH_URL,
        headers={"X-API-KEY": get_serper_api_key(), "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("organic", [])


def find_syllabus_urls(course_id: str, course_title: str, instructor: str, num_results: int = 5) -> List[str]:
    query = f"{course_id} {course_title} {instructor} syllabus (site:columbia.edu OR site:github.io)"
    return [result["link"] for result in _search(query, num_results) if "link" in result]

def find_review_urls(course_id: str, instructor: str, num_results: int = 5) -> List[str]:
    query = f"{instructor} {course_id} review site:culpa.info OR site:ratemyprofessors.com"
    return [result["link"] for result in _search(query, num_results) if "link" in result]
