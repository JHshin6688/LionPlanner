import os

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_supabase_client():
    """Lazily construct the Supabase client so importing this module never
    requires credentials (e.g. when only running --help)."""
    from supabase import create_client

    return create_client(
        _require_env("SUPABASE_URL"),
        _require_env("SUPABASE_SERVICE_ROLE_KEY"),
    )


def get_analyzer_llm():
    """Lazily construct the Claude chat model used for workload & syllabus analysis."""
    from langchain_anthropic import ChatAnthropic

    model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    return ChatAnthropic(
        model=model_name,
        api_key=_require_env("ANTHROPIC_API_KEY"),
        temperature=0,
    )


def get_digest_llm():
    """Lazily construct the cheap Claude model used to compress raw syllabus/review
    markdown into a workload-relevant digest before the analyzer prompts see it."""
    from langchain_anthropic import ChatAnthropic

    model_name = os.environ.get("ANTHROPIC_DIGEST_MODEL", "claude-haiku-4-5-20251001")
    return ChatAnthropic(
        model=model_name,
        api_key=_require_env("ANTHROPIC_API_KEY"),
        temperature=0,
    )


def get_agent_llm():
    """Lazily construct the Claude chat model used by the Ask LionPlanner
    multi-agent graph (src/agents/)."""
    from langchain_anthropic import ChatAnthropic

    model_name = os.environ.get("ANTHROPIC_AGENT_MODEL", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
    return ChatAnthropic(
        model=model_name,
        api_key=_require_env("ANTHROPIC_API_KEY"),
        temperature=0,
    )


def get_embedding_model():
    """Lazily construct the Voyage AI embeddings client used to embed syllabus_summary
    for RAG retrieval. Defaults to voyage-3.5, which outputs 1024-dim vectors -
    the Supabase pgvector column must match whatever dimension this model produces."""
    from langchain_voyageai import VoyageAIEmbeddings

    model_name = os.environ.get("VOYAGE_EMBEDDING_MODEL", "voyage-3.5")
    return VoyageAIEmbeddings(
        voyage_api_key=_require_env("VOYAGE_API_KEY"),
        model=model_name,
    )


def get_serper_api_key() -> str:
    return _require_env("SERPER_API_KEY")


def get_jina_api_key() -> str | None:
    return os.environ.get("JINA_API_KEY")

def get_firecrawl_api_key() -> str | None:
    return os.environ.get("FIRECRAWL_API_KEY")
