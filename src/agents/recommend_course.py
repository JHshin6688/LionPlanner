"""recommend_course: the one *agent* node in the graph.

The student's interest can be vague or need more than one search ("Is there anything
interesting in the intersection of AI and biology?"), so unlike the other nodes this one gets real autonomy: it's
a `langchain.agents.create_agent` agent (built on LangGraph under the hood)
that can call `search_courses` as many times as it needs (bounded by
RECURSION_LIMIT below) before deciding it has enough to answer.

Grounding is enforced by the shared verify_grounding node (src/agents/verify_grounding.py),
which checks `cited_course_ids` against `context_course_ids` — every course_id
`search_courses` actually returned this turn, tracked via the `seen_course_ids`
closure below, independent of whatever the model chooses to quote in the
answer. That's why the agent must report `cited_course_ids` explicitly via
`response_format` rather than us trying to regex course IDs out of prose.
"""
from typing import List

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.config import get_agent_llm, get_embedding_model
from src.db.supabase_client import search_courses_by_embedding

# Caps how many search_courses <-> reasoning round-trips the agent can take
# before LangGraph forces a stop, so a stuck agent fails fast instead of
# looping indefinitely. Each round-trip is 2 supersteps (model, tool), plus 1
# for the initial model call and 1 for the final structured_response
# extraction that response_format triggers — so this allows ~3 search calls
# (1 + 2*3 + 1 = 8 wasn't enough for even one; verified empirically).
RECURSION_LIMIT = 16

SYSTEM_PROMPT = """You are LionPlanner's course recommendation assistant for Columbia University students. \
Use the search_courses tool to find courses relevant to the student's interest — call it more than once \
if the first results don't look like a good match, e.g. with a narrower or broader phrasing. Once you're \
confident, answer citing course_id and course_title for every course you recommend. Only cite courses \
that search_courses actually returned this conversation — never recommend a course you didn't retrieve. \
If nothing relevant turns up after searching, say so plainly instead of guessing."""


class RecommendationResponse(BaseModel):
    answer: str = Field(..., description="The final answer shown to the student.")
    cited_course_ids: List[str] = Field(
        default_factory=list,
        description="course_id of every course mentioned in `answer`, e.g. ['COMS-W4111'].",
    )


def _build_search_tool(seen_course_ids: set[str]):
    @tool
    def search_courses(query: str) -> list[dict]:
        """Semantic search over Columbia course syllabi. Returns the closest-matching
        courses (course_id, course_title, department, course_level, syllabus_summary,
        similarity) for the given topic/interest. Call again with different phrasing
        if the results don't look relevant."""
        embedding = get_embedding_model().embed_query(query)
        results = search_courses_by_embedding(embedding, match_count=5)
        seen_course_ids.update(r["course_id"] for r in results if r.get("course_id"))
        return results

    return search_courses


def recommend_course(state: AgentState) -> dict:
    seen_course_ids: set[str] = set()
    agent = create_agent(
        get_agent_llm(),
        tools=[_build_search_tool(seen_course_ids)],
        system_prompt=SYSTEM_PROMPT,
        response_format=RecommendationResponse,
    )

    messages = [HumanMessage(state["query"])]
    feedback = state.get("verification_feedback")
    if feedback:
        messages.append(HumanMessage(f"Correction needed on your previous attempt: {feedback}"))

    result = agent.invoke({"messages": messages}, config={"recursion_limit": RECURSION_LIMIT})
    structured: RecommendationResponse = result["structured_response"]

    return {
        "answer": structured.answer,
        "cited_course_ids": structured.cited_course_ids,
        "context_course_ids": sorted(seen_course_ids),
    }
