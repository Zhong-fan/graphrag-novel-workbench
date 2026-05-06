from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    openai_use_system_proxy: bool
    llm_use_responses: bool
    llm_stream_responses: bool
    llm_request_timeout_seconds: int
    llm_max_attempts: int
    llm_retry_max_sleep_seconds: int
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
    raise RuntimeError(f"MVP/.env 中 GRAPH_MVP_GRAPHRAG_INDEX_METHOD 非法: {method}")


def _is_ollama_base_url(url: str) -> bool:
    return "127.0.0.1:11434" in url or "localhost:11434" in url


def _is_tei_base_url(url: str) -> bool:
    return "127.0.0.1:8090" in url or "localhost:8090" in url


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_positive_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"Expected a positive integer, got: {value}") from exc
    if parsed <= 0:
        raise RuntimeError(f"Expected a positive integer, got: {value}")
    return parsed


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
    return dotenv_values.get(name, default)


def _require(name: str, dotenv_values: dict[str, str]) -> str:
    value = dotenv_values.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"MVP/.env 缺少必填配置: {name}")
    return value.strip()


def _resolve_embedding_settings(
    dotenv_values: dict[str, str],
    openai_api_key: str | None,
    openai_base_url: str,
) -> tuple[str, str | None, str]:
    embedding_base_url = _normalize_base_url(_require("GRAPH_MVP_EMBEDDING_BASE_URL", dotenv_values))

    if _is_ollama_base_url(embedding_base_url):
        default_api_key = "ollama"
    elif _is_tei_base_url(embedding_base_url):
        default_api_key = "dummy"
    elif embedding_base_url == openai_base_url:
        default_api_key = openai_api_key or "ollama"
    else:
        default_api_key = openai_api_key

    embedding_model = _require("GRAPH_MVP_EMBEDDING_MODEL", dotenv_values)
    embedding_api_key = _resolve("GRAPH_MVP_EMBEDDING_API_KEY", dotenv_values, default_api_key)
    return embedding_model, embedding_api_key, embedding_base_url


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    dotenv_values = _load_dotenv(env_path)

    openai_api_key = _require("OPENAI_API_KEY", dotenv_values)
    openai_base_url = _normalize_base_url(_require("OPENAI_BASE_URL", dotenv_values))
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
        llm_mode=_require("GRAPH_MVP_LLM_MODE", dotenv_values).strip().lower(),
        writer_model=_require("GRAPH_MVP_WRITER_MODEL", dotenv_values),
        utility_model=_require("GRAPH_MVP_UTILITY_MODEL", dotenv_values),
        embedding_model=embedding_model,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_use_system_proxy=_parse_bool(_resolve("GRAPH_MVP_OPENAI_USE_SYSTEM_PROXY", dotenv_values), default=False),
        llm_use_responses=_parse_bool(_resolve("GRAPH_MVP_LLM_USE_RESPONSES", dotenv_values), default=True),
        llm_stream_responses=_parse_bool(_resolve("GRAPH_MVP_LLM_STREAM_RESPONSES", dotenv_values), default=True),
        llm_request_timeout_seconds=_parse_positive_int(
            _resolve("GRAPH_MVP_LLM_REQUEST_TIMEOUT_SECONDS", dotenv_values),
            120,
        ),
        llm_max_attempts=_parse_positive_int(_resolve("GRAPH_MVP_LLM_MAX_ATTEMPTS", dotenv_values), 3),
        llm_retry_max_sleep_seconds=_parse_positive_int(
            _resolve("GRAPH_MVP_LLM_RETRY_MAX_SLEEP_SECONDS", dotenv_values),
            120,
        ),
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        mysql_host=_require("MYSQL_HOST", dotenv_values),
        mysql_port=int(_require("MYSQL_PORT", dotenv_values)),
        mysql_user=_require("MYSQL_USER", dotenv_values),
        mysql_password=_require("MYSQL_PASSWORD", dotenv_values),
        mysql_database=_require("MYSQL_DATABASE", dotenv_values),
        neo4j_uri=_require("NEO4J_URI", dotenv_values),
        neo4j_user=_require("NEO4J_USER", dotenv_values),
        neo4j_password=_require("NEO4J_PASSWORD", dotenv_values),
        neo4j_database=_require("NEO4J_DATABASE", dotenv_values),
        auth_secret=_require("AUTH_SECRET", dotenv_values),
        auth_exp_hours=int(_require("AUTH_EXP_HOURS", dotenv_values)),
        graphrag_response_type=_require("GRAPH_MVP_GRAPHRAG_RESPONSE_TYPE", dotenv_values),
        graphrag_index_method=_normalize_index_method(_require("GRAPH_MVP_GRAPHRAG_INDEX_METHOD", dotenv_values)),
        graphrag_local_embeddings=_parse_bool(_require("GRAPH_MVP_LOCAL_EMBEDDINGS", dotenv_values), default=False),
    )
