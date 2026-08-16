"""Ask LionPlanner API — the backend the frontend chat panel calls.

Run locally with:
    uvicorn src.api.main:app --reload

Deploys straightforwardly onto AWS (e.g. Lambda via Mangum behind API
Gateway, or ECS/Fargate) once the agent graph is wired to a real retriever.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.graph import build_agent_graph
from src.api.schemas import ChatRequest, ChatResponse

app = FastAPI(title="LionPlanner Ask API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to the deployed frontend origin before shipping
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
    return ChatResponse(answer=result["answer"], route=result["route"])
