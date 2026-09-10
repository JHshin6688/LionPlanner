"""Evaluates src/agents/recommend_course.py's course-recommendation agent
against a hand-built set of (query, scheduled_courses) cases
(src/evals/datasets/recommend_course_cases.json), using a mix of
deterministic checks and an LLM judge.

Runs the recommend_course node directly (not the full graph, so no
verify_grounding retry loop muddies what's being measured) against the live
Supabase/Voyage backends - this is an integration eval, not a unit test:
each case makes real tool calls and costs real API calls.

Deterministic checks (reuse the exact functions the agent's own tools call,
so they're checked against production data, not a fixture):
  - grounded: every cited_course_id was actually returned by a tool call
    this turn (same set-membership check as verify_grounding.py).
  - no_schedule_conflict: none of the recommended (not already scheduled)
    cited course_ids has a meeting time overlapping the student's
    scheduled_courses. Skipped (score=None) for cases with
    "check_no_conflict_among_cited": false in the dataset - those
    deliberately probe a real conflict the answer is supposed to disclose,
    not avoid recommending.
  - degree_track_membership: when a case sets "expected_degree_track", at
    least one cited course_id must appear in that track's required/elective
    list (the degree_path table).

LLM judge:
  - relevance_judge (1-5): does the recommendation actually fit the
    student's question and context. Each case can carry a "judge_focus"
    hint pointing at something a deterministic check can't see (e.g.
    "this candidate genuinely conflicts - does the answer disclose that?").

Usage:
    python -m src.evals.recommend_course_eval
    python -m src.evals.recommend_course_eval --reset
    python -m src.evals.recommend_course_eval --no-sync
"""
import argparse
import json
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import Client
from langsmith.evaluation import evaluate
from pydantic import BaseModel, Field

from src.agents.recommend_course import _times_overlap, recommend_course
from src.agents.text_utils import normalize_course_id
from src.config import get_agent_llm, get_supabase_client
from src.db.supabase_client import get_degree_path
from src.evals.dataset_sync import sync_dataset

DATASET_NAME = "lionplanner-recommend-course"
CASES_PATH = Path(__file__).parent / "datasets" / "recommend_course_cases.json"

_course_lookup_cache: Optional[dict[str, dict]] = None
_degree_track_cache: dict[str, Optional[set[str]]] = {}


def _load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def _to_example(case: dict) -> tuple[dict, dict]:
    inputs = {
        "query": case["query"],
        "chat_history": case.get("chat_history"),
        "scheduled_courses": case.get("scheduled_courses") or [],
    }
    outputs = {
        "scenario": case.get("scenario"),
        "expected_degree_track": case.get("expected_degree_track"),
        "check_no_conflict_among_cited": case.get("check_no_conflict_among_cited", True),
        "judge_focus": case.get("judge_focus"),
    }
    return inputs, outputs


def target(inputs: dict) -> dict:
    state = {
        "query": inputs["query"],
        "chat_history": inputs.get("chat_history") or [],
        "scheduled_courses": inputs.get("scheduled_courses") or [],
    }
    result = recommend_course(state)
    return {
        "answer": result["answer"],
        "cited_course_ids": result["cited_course_ids"],
        "context_course_ids": result["context_course_ids"],
    }


def _course_lookup() -> dict[str, dict]:
    """normalize_course_id(course_id) -> {course_id, course_title, schedule_time}
    for every course offered this semester, fetched once from the live DB.
    Keyed by normalized id since cited_course_ids (from text_utils.py) are
    normalized and not reliably reversible to the DB's spaced format."""
    global _course_lookup_cache
    if _course_lookup_cache is None:
        client = get_supabase_client()
        rows = (
            client.table("courses_semester_view")
            .select("course_id, course_title, schedule_time")
            .execute()
            .data
            or []
        )
        _course_lookup_cache = {normalize_course_id(r["course_id"]): r for r in rows}
    return _course_lookup_cache


def _degree_track_ids(track_name: str) -> Optional[set[str]]:
    if track_name not in _degree_track_cache:
        result = get_degree_path(track_name)
        if result is None:
            _degree_track_cache[track_name] = None
        else:
            ids = (result.get("required_courses") or []) + (result.get("elective_courses") or [])
            _degree_track_cache[track_name] = {normalize_course_id(cid) for cid in ids}
    return _degree_track_cache[track_name]


def grounded(run, _example) -> dict:
    outputs = run.outputs or {}
    cited = set(outputs.get("cited_course_ids") or [])
    allowed = set(outputs.get("context_course_ids") or [])
    ungrounded = cited - allowed
    return {
        "key": "grounded",
        "score": int(not ungrounded),
        "comment": f"ungrounded citations: {sorted(ungrounded)}" if ungrounded else "all cited courses were tool-retrieved",
    }


def no_schedule_conflict(run, example) -> dict:
    """Heuristic, not a validator: it flags any cited course_id whose meeting
    time overlaps the schedule, regardless of *why* it was cited. A course
    the agent correctly identifies as conflicting and excludes - citing it
    only to explain the exclusion (observed in practice: rc02, "COMS W4773
    conflicts with COMS W4111" while recommending W4772 instead) - trips
    this the same as a silently bad recommendation would. Treat a score of 0
    here as "go read the answer," not as an automatic fail; relevance_judge
    below is what actually judges whether a flagged conflict was handled
    correctly or silently ignored."""
    case_outputs = example.outputs or {}
    if not case_outputs.get("check_no_conflict_among_cited", True):
        return {"key": "no_schedule_conflict", "score": None, "comment": "skipped - this case probes conflict disclosure, not avoidance"}

    outputs = run.outputs or {}
    cited = outputs.get("cited_course_ids") or []
    scheduled = (example.inputs or {}).get("scheduled_courses") or []
    already_scheduled_ids = {normalize_course_id(c["course_id"]) for c in scheduled}
    lookup = _course_lookup()

    bad_pairs = []
    for cid in cited:
        if cid in already_scheduled_ids:
            continue
        row = lookup.get(cid)
        if not row:
            continue  # not one of this semester's offerings we can check - nothing to flag
        for candidate_session in row.get("schedule_time") or []:
            for course in scheduled:
                for other in course.get("schedule_time") or []:
                    if candidate_session.get("day") == other.get("day") and _times_overlap(
                        candidate_session.get("start", ""), candidate_session.get("end", ""),
                        other.get("start", ""), other.get("end", ""),
                    ):
                        bad_pairs.append(f"{cid} vs {course['course_id']}")

    return {
        "key": "no_schedule_conflict",
        "score": int(not bad_pairs),
        "comment": f"conflicts: {bad_pairs}" if bad_pairs else "no conflicts among newly-recommended courses",
    }


def degree_track_membership(run, example) -> dict:
    expected_track = (example.outputs or {}).get("expected_degree_track")
    if not expected_track:
        return {"key": "degree_track_membership", "score": None, "comment": "no track expected for this case"}

    track_ids = _degree_track_ids(expected_track)
    if track_ids is None:
        return {"key": "degree_track_membership", "score": None, "comment": f"track {expected_track!r} not found in degree_path table"}

    outputs = run.outputs or {}
    cited = set(outputs.get("cited_course_ids") or [])
    hit = cited & track_ids
    return {
        "key": "degree_track_membership",
        "score": int(bool(hit)),
        "comment": f"cited courses in {expected_track} track: {sorted(hit) or 'none'}",
    }


class RecommendationJudgment(BaseModel):
    relevance_score: int = Field(..., ge=1, le=5, description="1=off-topic or presents a bad recommendation as fine, 5=clearly on-topic, justified, and consistent with the student's context")
    reasoning: str = Field(..., description="One or two sentences justifying the score")


JUDGE_SYSTEM_PROMPT = """You are grading a course-recommendation chatbot's answer for LionPlanner, a Columbia \
University course-planning assistant. Score how well the answer actually serves the student on a 1-5 scale:
5 - Recommendation(s) are clearly relevant to the question, well justified, and consistent with the \
student's stated context (schedule, track, interests).
3 - Partially relevant but missing something a good advisor would have caught (weak justification, ignored \
a stated constraint).
1 - Off-topic, ignores the question, or presents something the student clearly cannot or should not take \
at face value as if it were a clean fit.
Judge only what's asked here - assume any course data the chatbot cites from its tools is accurate; you are \
scoring the reasoning and relevance, not re-verifying the underlying facts."""

JUDGE_HUMAN_PROMPT = """Student's scheduled courses: {scheduled}

Student's question: {query}

Chatbot's answer:
{answer}
{focus_block}
Score the answer."""


def relevance_judge(run, example) -> dict:
    outputs = run.outputs or {}
    answer = outputs.get("answer", "")
    inputs = example.inputs or {}
    case_outputs = example.outputs or {}
    focus = case_outputs.get("judge_focus")
    focus_block = f"\nSomething specific to check for this case: {focus}\n" if focus else ""

    llm = get_agent_llm().with_structured_output(RecommendationJudgment)
    human = JUDGE_HUMAN_PROMPT.format(
        scheduled=inputs.get("scheduled_courses") or "(none)",
        query=inputs.get("query"),
        answer=answer,
        focus_block=focus_block,
    )
    result: RecommendationJudgment = llm.invoke([SystemMessage(JUDGE_SYSTEM_PROMPT), HumanMessage(human)])
    return {"key": "relevance_judge", "score": result.relevance_score, "comment": result.reasoning}


def _print_summary(results) -> None:
    """Console summary so results are readable without opening LangSmith -
    the full per-case traces and comparison view still live at the URL
    `evaluate()` already printed above."""
    scores_by_key: dict[str, list[int]] = {}
    low_relevance = []
    for row in results:
        case_id = (row["example"].metadata or {}).get("case_id", "?")
        for eval_result in (row["evaluation_results"] or {}).get("results", []):
            if eval_result.score is None:
                continue
            scores_by_key.setdefault(eval_result.key, []).append(eval_result.score)
            if eval_result.key == "relevance_judge" and eval_result.score <= 2:
                low_relevance.append((case_id, eval_result.score, eval_result.comment))

    print("\n=== recommend_course eval summary ===")
    for key, scores in scores_by_key.items():
        avg = sum(scores) / len(scores)
        label = f"avg {avg:.2f}/5" if key == "relevance_judge" else f"{sum(scores)}/{len(scores)} passed"
        print(f"  {key}: {label}  (n={len(scores)})")
    if low_relevance:
        print("Low relevance_judge scores (<=2):")
        for case_id, score, comment in low_relevance:
            print(f"  [{case_id}] score={score}: {comment}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="wipe & re-upload the dataset before evaluating")
    parser.add_argument("--no-sync", action="store_true", help="skip dataset sync, evaluate the dataset as-is")
    args = parser.parse_args()

    client = Client()
    cases = _load_cases()

    if not args.no_sync:
        sync_dataset(
            client,
            DATASET_NAME,
            description="Ask LionPlanner recommend_course agent quality - (query, scheduled_courses) cases against live course/degree-path data.",
            cases=cases,
            to_example=_to_example,
            reset=args.reset,
        )

    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[grounded, no_schedule_conflict, degree_track_membership, relevance_judge],
        experiment_prefix="recommend-course-eval",
        client=client,
        max_concurrency=3,
    )
    _print_summary(results)


if __name__ == "__main__":
    main()
