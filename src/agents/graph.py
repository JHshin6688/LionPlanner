"""Wires the Ask LionPlanner nodes into a LangGraph state machine:

    analyze_query --route--> recommend_course (agent)  --> verify_grounding --> retry or END
                          --> analyze_workload (workflow) --> verify_grounding --> retry or END
                          --> general_question (workflow) --> END

recommend_course and analyze_workload both go through verify_grounding, which
can send them back for exactly one retry with corrective feedback before
giving up (src/agents/verify_grounding.py). general_question has nothing to
verify against, so it skips straight to END.

Every run is traced end-to-end in LangSmith as long as LANGCHAIN_TRACING_V2 /
LANGCHAIN_API_KEY are set (see .env.example) — no extra code needed here,
LangChain/LangGraph pick this up automatically. `run_name` below is just to
make individual traces easy to find in the LangSmith UI.
"""
from langgraph.graph import END, StateGraph

from src.agents.analyze_workload import analyze_workload
from src.agents.general_question import general_question
from src.agents.recommend_course import recommend_course
from src.agents.router import analyze_query
from src.agents.state import AgentState
from src.agents.verify_grounding import route_after_verification, verify_grounding


def _route_from_intent(state: AgentState) -> str:
    return state["route"]


def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("analyze_query", analyze_query)
    graph.add_node("recommend_course", recommend_course)
    graph.add_node("analyze_workload", analyze_workload)
    graph.add_node("general_question", general_question)
    graph.add_node("verify_grounding", verify_grounding)

    graph.set_entry_point("analyze_query")
    graph.add_conditional_edges(
        "analyze_query",
        _route_from_intent,
        {
            "recommend_course": "recommend_course",
            "analyze_workload": "analyze_workload",
            "general_question": "general_question",
        },
    )

    graph.add_edge("recommend_course", "verify_grounding")
    graph.add_edge("analyze_workload", "verify_grounding")
    graph.add_edge("general_question", END)

    graph.add_conditional_edges(
        "verify_grounding",
        route_after_verification,
        {
            "retry_recommend_course": "recommend_course",
            "retry_analyze_workload": "analyze_workload",
            "done": END,
        },
    )

    return graph.compile()
