"""general_question: anything that doesn't need course-specific retrieval or
the student's schedule — answered directly by the model."""
from langchain_core.prompts import ChatPromptTemplate

from src.agents.state import AgentState
from src.config import get_agent_llm

SYSTEM_PROMPT = """You are LionPlanner, an academic planning assistant for Columbia University students. \
Answer the student's question directly and concisely. If it actually needs a course recommendation or an \
analysis of their schedule, say what you'd need instead of guessing."""


def general_question(state: AgentState) -> dict:
    llm = get_agent_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{query}"),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"query": state["query"]})
    return {"answer": response.content}
