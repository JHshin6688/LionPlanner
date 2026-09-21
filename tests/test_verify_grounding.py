from src.agents.verify_grounding import (
    MAX_VERIFICATION_RETRIES,
    route_after_verification,
    verify_grounding,
)


def test_grounded_when_all_citations_were_retrieved():
    state = {"cited_course_ids": ["COMSW4111"], "context_course_ids": ["COMSW4111", "COMSW4771"]}
    assert verify_grounding(state) == {"grounded": True}


def test_grounded_when_nothing_cited():
    assert verify_grounding({"cited_course_ids": [], "context_course_ids": []}) == {"grounded": True}


def test_ungrounded_citation_triggers_retry_with_feedback():
    state = {"cited_course_ids": ["COMSW9999"], "context_course_ids": ["COMSW4111"]}
    result = verify_grounding(state)
    assert result["grounded"] is False
    assert result["verification_retries"] == 1
    assert "COMSW9999" in result["verification_feedback"]


def test_gives_up_with_fallback_answer_after_max_retries():
    state = {
        "cited_course_ids": ["COMSW9999"],
        "context_course_ids": [],
        "verification_retries": MAX_VERIFICATION_RETRIES,
    }
    result = verify_grounding(state)
    assert result["grounded"] is True  # stops looping
    assert "can't provide a grounded answer" in result["answer"]


def test_route_after_verification():
    assert route_after_verification({"grounded": True, "route": "recommend_course"}) == "done"
    assert route_after_verification({"grounded": False, "route": "recommend_course"}) == "retry_recommend_course"
    assert route_after_verification({"grounded": False, "route": "analyze_workload"}) == "retry_analyze_workload"
