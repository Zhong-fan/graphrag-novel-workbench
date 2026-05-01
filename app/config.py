from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OLLAMA_EMBEDDING_MODEL = "bge-m3"
DEFAULT_OLLAMA_EMBEDDING_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_TEI_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_TEI_EMBEDDING_BASE_URL = "http://127.0.0.1:8090/v1"


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    env_path: Path
    output_dir: Path
    graphrag_root: Path
    llm_mode: str
    writer_model: str
    utility_model: str
    embedding_model: str
    openai_api_key: str | None
    openai_base_url: str
    embedding_api_key: str | None
    embedding_base_url: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    auth_secret: str
    auth_exp_hours: int
    graphrag_response_type: str
    graphrag_index_method: str
    graphrag_local_embeddings: bool

    @property
    def sqlalchemy_database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def embedding_provider_label(self) -> str:
        if self.graphrag_local_embeddings:
            return "local-fallback"
        if "127.0.0.1:11434" in self.embedding_base_url or "localhost:11434" in self.embedding_base_url:
            return "ollama"
        if "127.0.0.1:8090" in self.embedding_base_url or "localhost:8090" in self.embedding_base_url:
            return "tei-bge-m3"
        return "remote-compatible-api"


def _normalize_base_url(url: str) -> str:
    stripped = url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped
    return f"{stripped}/v1"


def _normalize_index_method(method: str) -> str:
    allowed = {"standard", "fast", "standard-update", "fast-update"}
    normalized = method.strip().lower()
    if normalized in allowed:
        return normalized
    return "fast"


def _is_ollama_base_url(url: str) -> bool:
    return "127.0.0.1:11434" in url or "localhost:11434" in url


def _is_tei_base_url(url: str) -> bool:
    return "127.0.0.1:8090" in url or "localhost:8090" in url


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def _resolve(name: str, dotenv_values: dict[str, str], default: str | None = None) -> str | None:
    return dotenv_values.get(name) or os.getenv(name) or default


def _resolve_embedding_settings(
    dotenv_values: dict[str, str],
    openai_api_key: str | None,
    openai_base_url: str,
) -> tuple[str, str | None, str]:
    embedding_base_url = _normalize_base_url(
        _resolve("GRAPH_MVP_EMBEDDING_BASE_URL", dotenv_values, DEFAULT_OLLAMA_EMBEDDING_BASE_URL)
        or DEFAULT_OLLAMA_EMBEDDING_BASE_URL
    )

    if _is_ollama_base_url(embedding_base_url):
        default_model = DEFAULT_OLLAMA_EMBEDDING_MODEL
        default_api_key = "ollama"
    elif _is_tei_base_url(embedding_base_url):
        default_model = DEFAULT_TEI_EMBEDDING_MODEL
        default_api_key = "dummy"
    elif embedding_base_url == openai_base_url:
        default_model = "text-embedding-3-large"
        default_api_key = openai_api_key or "ollama"
    else:
        default_model = "text-embedding-3-large"
        default_api_key = openai_api_key

    embedding_model = _resolve("GRAPH_MVP_EMBEDDING_MODEL", dotenv_values, default_model) or default_model
    embedding_api_key = _resolve("GRAPH_MVP_EMBEDDING_API_KEY", dotenv_values, default_api_key)
    return embedding_model, embedding_api_key, embedding_base_url


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    dotenv_values = _load_dotenv(env_path)

    openai_api_key = _resolve("OPENAI_API_KEY", dotenv_values)
    openai_base_url = _normalize_base_url(
        _resolve("OPENAI_BASE_URL", dotenv_values, "https://api.openai.com/v1") or "https://api.openai.com/v1"
    )
    embedding_model, embedding_api_key, embedding_base_url = _resolve_embedding_settings(
        dotenv_values,
        openai_api_key,
        openai_base_url,
    )

    return Settings(
        root_dir=root_dir,
        env_path=env_path,
        output_dir=root_dir / "output",
        graphrag_root=root_dir / "workspace" / "graphrag_projects",
        llm_mode=(_resolve("GRAPH_MVP_LLM_MODE", dotenv_values, "openai") or "openai").strip().lower(),
        writer_model=_resolve("GRAPH_MVP_WRITER_MODEL", dotenv_values, "gpt-5.5") or "gpt-5.5",
        utility_model=_resolve("GRAPH_MVP_UTILITY_MODEL", dotenv_values, "gpt-5.4-mini") or "gpt-5.4-mini",
        embedding_model=embedding_model,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        mysql_host=_resolve("MYSQL_HOST", dotenv_values, "127.0.0.1") or "127.0.0.1",
        mysql_port=int(_resolve("MYSQL_PORT", dotenv_values, "3306") or "3306"),
        mysql_user=_resolve("MYSQL_USER", dotenv_values, "graph_user") or "graph_user",
        mysql_password=_resolve("MYSQL_PASSWORD", dotenv_values, "graph_password") or "graph_password",
        mysql_database=_resolve("MYSQL_DATABASE", dotenv_values, "graphrag_novel") or "graphrag_novel",
        neo4j_uri=_resolve("NEO4J_URI", dotenv_values, "neo4j://127.0.0.1:7687") or "neo4j://127.0.0.1:7687",
        neo4j_user=_resolve("NEO4J_USER", dotenv_values, "neo4j") or "neo4j",
        neo4j_password=_resolve("NEO4J_PASSWORD", dotenv_values, "graphrag-password") or "graphrag-password",
        neo4j_database=_resolve("NEO4J_DATABASE", dotenv_values, "neo4j") or "neo4j",
        auth_secret=_resolve("AUTH_SECRET", dotenv_values, "replace-me-with-a-long-secret") or "replace-me-with-a-long-secret",
        auth_exp_hours=int(_resolve("AUTH_EXP_HOURS", dotenv_values, "168") or "168"),
        graphrag_response_type=_resolve("GRAPH_MVP_GRAPHRAG_RESPONSE_TYPE", dotenv_values, "Multiple Paragraphs")
        or "Multiple Paragraphs",
        graphrag_index_method=_normalize_index_method(
            _resolve("GRAPH_MVP_GRAPHRAG_INDEX_METHOD", dotenv_values, "fast") or "fast"
        ),
        graphrag_local_embeddings=_parse_bool(
            _resolve("GRAPH_MVP_LOCAL_EMBEDDINGS", dotenv_values, "false"),
            default=False,
        ),
    )
