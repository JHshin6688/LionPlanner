"""Ask LionPlanner API — the backend the frontend chat panel calls.

Run locally with:
    uvicorn src.api.main:app --reload

Deployed via Docker (see /Dockerfile) to Fly.io by
.github/workflows/backend-deploy.yml.
"""
import json
import os
from typing import Iterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk

from src.agents.graph import build_agent_graph
from src.api.schemas import ChatRequest
from src.db.supabase_client import save_chat_turn

app = FastAPI(title="LionPlanner Ask API")

# Comma-separated list of allowed frontend origins, e.g.
# "https://lionplanner.vercel.app,http://localhost:5173"
_frontend_origins = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_methods=["POST"],
    allow_headers=["*"],
)

_graph = None

# Nodes whose text output is the actual visible answer. analyze_query's
# classification call and verify_grounding (no LLM call at all) are
# deliberately excluded — only these three ever produce text the student
# should see.
_STREAMED_NODES = {"analyze_workload", "recommend_course", "general_question"}


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _message_text(content) -> str:
    """AIMessageChunk.content is a plain string for ordinary text streaming,
    but can be a list of content blocks in other configurations. Pull out
    just the text either way; tool_use blocks contribute nothing here."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _owning_node(ns: tuple, metadata: dict) -> Optional[str]:
    """Which top-level graph node a chunk belongs to.

    recommend_course runs a `create_agent` sub-graph internally (via a plain
    `agent.invoke()` call), so its LLM turns arrive with `ns` set to
    ("recommend_course:<task_id>",) and `metadata["langgraph_node"]` set to
    the *sub*graph's own internal node name ("model"), not "recommend_course".
    `graph.stream(..., subgraphs=True)` is required for these to be emitted
    at all - without it, recommend_course's turns never show up here, only
    the final state once the node returns.
    """
    if ns:
        return ns[0].split(":", 1)[0]
    return metadata.get("langgraph_node")


def _stream_chat(request: ChatRequest) -> Iterator[str]:
    graph = get_graph()
    initial_state = {
        "query": request.query,
        "chat_history": [m.model_dump() for m in request.chat_history],
        "scheduled_courses": [c.model_dump() for c in request.scheduled_courses],
    }
    # Purely for LangSmith trace readability — has no effect if tracing is off.
    config = {"run_name": "ask_lionplanner_chat", "recursion_limit": 15}

    streamed_text = ""
    current_message_id: Optional[str] = None
    route: Optional[str] = None
    final_state: dict = {}

    try:
        stream = graph.stream(
            initial_state, config=config, stream_mode=["messages", "values"], subgraphs=True
        )
        for ns, mode, payload in stream:
            if mode == "values":
                if not ns:  # ignore subgraph-internal state snapshots — keep only our own AgentState
                    final_state = payload
                continue

            message_chunk, metadata = payload
            if not isinstance(message_chunk, AIMessageChunk):
                continue  # excludes ToolMessage chunks (e.g. recommend_course's search_courses results)

            node = _owning_node(ns, metadata)
            if node not in _STREAMED_NODES:
                continue

            text = _message_text(message_chunk.content)
            if not text:
                continue

            route = node
            if message_chunk.id != current_message_id:
                if current_message_id is not None:
                    # A new AI turn started for a node we're already streaming.
                    # Either verify_grounding rejected the last attempt and
                    # sent it back for a retry, or (rarely, despite the
                    # no-preamble instruction) recommend_course wrote a
                    # sentence before a tool call. Either way, what was shown
                    # so far isn't the real answer — wipe it and start over.
                    streamed_text = ""
                    yield _sse({"type": "restart"})
                current_message_id = message_chunk.id

            streamed_text += text
            yield _sse({"type": "token", "delta": text})

        # verify_grounding's give-up fallback sets a fixed answer directly in
        # state without any further LLM call, so it never streams as tokens.
        # Catch that mismatch here and correct what the client is showing
        # before finishing.
        final_answer = final_state.get("answer", streamed_text)
        if final_answer != streamed_text:
            yield _sse({"type": "restart"})
            yield _sse({"type": "token", "delta": final_answer})

        route = final_state.get("route", route)
        yield _sse({"type": "done", "route": route})

        try:
            save_chat_turn(request.session_id, request.query, final_answer)
        except Exception as exc:
            # Chat history persistence is best-effort — a Supabase hiccup
            # shouldn't break the user-facing response.
            print(f"Warning: failed to save chat turn for session {request.session_id}: {exc}")
    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering (e.g. nginx) so tokens flush immediately
        },
    )
