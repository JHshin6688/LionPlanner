"""Ask LionPlanner API — the backend the frontend chat panel calls.

Run locally with:
    uvicorn src.api.main:app --reload

Deployed via Docker (see /Dockerfile) to Fly.io by
.github/workflows/backend-deploy.yml.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.graph import build_agent_graph
from src.api.schemas import ChatRequest, ChatResponse
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


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    graph = get_graph()
    result = graph.invoke(
        {
            "query": request.query,
            "chat_history": [m.model_dump() for m in request.chat_history],
            "scheduled_courses": [c.model_dump() for c in request.scheduled_courses],
        },
        # Purely for LangSmith trace readability — has no effect if tracing is off.
        config={"run_name": "ask_lionplanner_chat", "recursion_limit": 15},
    )
    answer = result["answer"]

    try:
        save_chat_turn(request.session_id, request.query, answer)
    except Exception as exc:
        # Chat history persistence is best-effort — a Supabase hiccup shouldn't
        # break the user-facing response.
        print(f"Warning: failed to save chat turn for session {request.session_id}: {exc}")

    return ChatResponse(answer=answer, route=result["route"])
