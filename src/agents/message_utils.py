"""Converts the plain {role, content} chat_history the frontend sends into
LangChain message objects, so every node builds on the actual conversation
instead of treating each turn as an isolated question.

chat_history always ends with the current turn's user message (see
useChat.ts's `nextMessages`), so nodes that just need "the conversation so
far, including what was just asked" can use to_langchain_messages(...)
directly with no separate `query` append.
"""
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.agents.state import ChatMessage


def to_langchain_messages(chat_history: list[ChatMessage]) -> list[BaseMessage]:
    return [
        HumanMessage(m["content"]) if m["role"] == "user" else AIMessage(m["content"]) for m in chat_history
    ]
