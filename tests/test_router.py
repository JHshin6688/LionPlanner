from unittest.mock import MagicMock, patch

from src.agents.router import QueryRoute, _schedule_note, analyze_query


def test_schedule_note_empty():
    assert "no courses" in _schedule_note([])


def test_schedule_note_lists_courses():
    note = _schedule_note([{"course_id": "COMS W4111", "course_title": "Databases"}])
    assert "1 course(s)" in note
    assert "COMS W4111 (Databases)" in note


def test_analyze_query_returns_route_from_llm_without_network():
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value.invoke.return_value = QueryRoute(
        route="analyze_workload", reasoning="asks about scheduled courses"
    )
    with patch("src.agents.router.get_router_llm", return_value=fake_llm):
        result = analyze_query({"query": "how hard is my schedule?", "chat_history": [], "scheduled_courses": []})
    assert result == {"route": "analyze_workload"}


def test_analyze_query_uses_chat_history_when_present():
    fake_llm = MagicMock()
    structured = fake_llm.with_structured_output.return_value
    structured.invoke.return_value = QueryRoute(route="recommend_course", reasoning="follow-up")
    history = [
        {"role": "user", "content": "I like deep learning"},
        {"role": "user", "content": "recommend one"},
    ]
    with patch("src.agents.router.get_router_llm", return_value=fake_llm):
        analyze_query({"query": "recommend one", "chat_history": history, "scheduled_courses": []})
    messages = structured.invoke.call_args.args[0]
    assert [m.content for m in messages[-2:]] == ["I like deep learning", "recommend one"]
