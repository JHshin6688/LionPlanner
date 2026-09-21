import json

import pytest
from pydantic import ValidationError

from src.api.main import _message_text, _sse
from src.api.schemas import ChatRequest


def test_message_text_string():
    assert _message_text("hello") == "hello"


def test_message_text_joins_text_blocks_and_skips_tool_use():
    content = [
        {"type": "text", "text": "Hello "},
        {"type": "tool_use", "name": "search"},
        {"type": "text", "text": "world"},
    ]
    assert _message_text(content) == "Hello world"


def test_message_text_unknown_type_is_empty():
    assert _message_text(None) == ""


def test_sse_framing():
    frame = _sse({"type": "token", "text": "hi"})
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    assert json.loads(frame[len("data: "):]) == {"type": "token", "text": "hi"}


def test_chat_request_defaults():
    req = ChatRequest(session_id="s1", query="hi")
    assert req.chat_history == []
    assert req.scheduled_courses == []


def test_chat_request_rejects_invalid_role():
    with pytest.raises(ValidationError):
        ChatRequest(session_id="s1", query="hi", chat_history=[{"role": "system", "content": "x"}])
