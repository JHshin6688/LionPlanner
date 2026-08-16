"""verify_grounding: shared verification node for recommend_course and
analyze_workload (general_question skips it — it has no data to be
grounded against in the first place).

Deliberately *not* another LLM call. The specific failure this guards
against — the model citing a course it never actually retrieved/was given —
is a plain set-membership check: `cited_course_ids` (what the answer claims)
must be a subset of `context_course_ids` (what the node actually had this
turn). A second LLM "judging" the first is slower, costs another API call,
and doesn't check anything more precisely than this can. If the project
later wants to catch softer issues (tone, relevance), that's a separate,
optional LLM-judge node — this one stays cheap and deterministic.

On failure, route back to the specialist node once with feedback about which
citations were ungrounded. If it's still wrong after the retry, give up with
a plain fallback answer rather than looping forever.
"""
from src.agents.state import AgentState

MAX_VERIFICATION_RETRIES = 1


def verify_grounding(state: AgentState) -> dict:
    cited = set(state.get("cited_course_ids") or [])
    allowed = set(state.get("context_course_ids") or [])
    ungrounded = cited - allowed

    if not ungrounded:
        return {"grounded": True}

    retries = state.get("verification_retries", 0)
    if retries >= MAX_VERIFICATION_RETRIES:
        return {
            "grounded": True,  # stop retrying — "done", not "correct"
            "answer": (
                "I'm sorry, I can't provide a grounded answer based on the courses I retrieved or were given."
                "Could you please ask a more specific question or provide more context?"
            ),
        }

    return {
        "grounded": False,
        "verification_retries": retries + 1,
        "verification_feedback": (
            f"Your previous answer cited {sorted(ungrounded)}, which were not found in the retrieved "
            "or provided course data. Only cite courses you actually retrieved/were given."
        ),
    }


def route_after_verification(state: AgentState) -> str:
    if state.get("grounded"):
        return "done"
    return f"retry_{state['route']}"
