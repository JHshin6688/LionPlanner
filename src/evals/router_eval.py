"""Evaluates src/agents/router.py's analyze_query node against a hand-labeled
set of (query, chat_history, scheduled_courses) -> expected_route cases
(src/evals/datasets/router_cases.json).

Runs analyze_query directly rather than the full graph - routing is decided
entirely in that one node, so there's no reason to pay for the downstream
specialist/verification nodes just to check the route. Cheap and fast (one
Haiku call per case), safe to run often.

Usage:
    python -m src.evals.router_eval             # sync new cases, then evaluate
    python -m src.evals.router_eval --reset      # wipe & re-upload the dataset first
    python -m src.evals.router_eval --no-sync    # skip dataset sync, evaluate as-is

Results land in LangSmith (see LANGCHAIN_PROJECT in .env) as an experiment
prefixed "router-eval" against the "lionplanner-router" dataset.
"""
import argparse
import json
from pathlib import Path

from langsmith import Client
from langsmith.evaluation import evaluate

from src.agents.router import analyze_query
from src.evals.dataset_sync import sync_dataset

DATASET_NAME = "lionplanner-router"
CASES_PATH = Path(__file__).parent / "datasets" / "router_cases.json"


def _load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def _to_example(case: dict) -> tuple[dict, dict]:
    inputs = {
        "query": case["query"],
        "chat_history": case.get("chat_history"),
        "scheduled_courses": case.get("scheduled_courses") or [],
    }
    outputs = {"expected_route": case["expected_route"]}
    return inputs, outputs


def target(inputs: dict) -> dict:
    state = {
        "query": inputs["query"],
        "chat_history": inputs.get("chat_history") or [],
        "scheduled_courses": inputs.get("scheduled_courses") or [],
    }
    result = analyze_query(state)
    return {"route": result["route"]}


def route_exact_match(run, example) -> dict:
    predicted = (run.outputs or {}).get("route")
    expected = (example.outputs or {}).get("expected_route")
    return {
        "key": "route_exact_match",
        "score": int(predicted == expected),
        "comment": f"predicted={predicted!r} expected={expected!r}",
    }


def _print_summary(results) -> None:
    """Console summary so results are readable without opening LangSmith -
    the full per-case traces and comparison view still live at the URL
    `evaluate()` already printed above."""
    total = 0
    correct = 0
    misses = []
    for row in results:
        total += 1
        case_id = (row["example"].metadata or {}).get("case_id", "?")
        expected = (row["example"].outputs or {}).get("expected_route")
        predicted = (row["run"].outputs or {}).get("route")
        if predicted == expected:
            correct += 1
        else:
            misses.append((case_id, row["example"].inputs.get("query"), expected, predicted))

    print(f"\n=== router accuracy: {correct}/{total} ({correct / total:.0%}) ===")
    if misses:
        print("Misrouted cases:")
        for case_id, query, expected, predicted in misses:
            print(f"  [{case_id}] {query!r}: expected={expected} predicted={predicted}")


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
            description="Ask LionPlanner router (analyze_query) accuracy - hand-labeled query -> expected_route cases.",
            cases=cases,
            to_example=_to_example,
            reset=args.reset,
        )

    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[route_exact_match],
        experiment_prefix="router-eval",
        client=client,
    )
    _print_summary(results)


if __name__ == "__main__":
    main()
