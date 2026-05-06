from __future__ import annotations

from .config import Settings, load_settings
from .graph_backend import GraphBackend
from .graph_store import GraphStore
from .llm import MockLLM, OpenAIResponsesLLM
from .neo4j_store import Neo4jGraphStore
from .pipeline import ChapterPipeline
from .retriever import GraphRetriever


def build_llm(settings: Settings):
    if settings.llm_mode == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("当 GRAPH_MVP_LLM_MODE=openai 时，必须提供 OPENAI_API_KEY。")
        return OpenAIResponsesLLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            use_system_proxy=settings.openai_use_system_proxy,
            use_responses=settings.llm_use_responses,
            stream_responses=settings.llm_stream_responses,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            retry_max_sleep_seconds=settings.llm_retry_max_sleep_seconds,
        )
    return MockLLM()


def build_graph_store(settings: Settings) -> GraphBackend:
    if settings.graph_backend == "neo4j":
        return Neo4jGraphStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )
    return GraphStore(settings.state_path)


def build_pipeline(settings: Settings | None = None) -> ChapterPipeline:
    active_settings = settings or load_settings()
    return ChapterPipeline(
        settings=active_settings,
        graph_store=build_graph_store(active_settings),
        retriever=GraphRetriever(),
        llm=build_llm(active_settings),
    )
