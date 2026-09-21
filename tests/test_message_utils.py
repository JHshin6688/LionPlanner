from langchain_core.messages import AIMessage, HumanMessage

from src.agents.message_utils import to_langchain_messages


def test_maps_roles_to_message_types_in_order():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "recommend one"},
    ]
    messages = to_langchain_messages(history)
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in messages] == ["hi", "hello", "recommend one"]


def test_empty_history_gives_empty_list():
    assert to_langchain_messages([]) == []
