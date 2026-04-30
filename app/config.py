from __future__ import annotations

import os
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

    @property
    def sqlalchemy_database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


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


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    dotenv_values = _load_dotenv(env_path)

    openai_api_key = _resolve("OPENAI_API_KEY", dotenv_values)
    openai_base_url = _normalize_base_url(
        _resolve("OPENAI_BASE_URL", dotenv_values, "https://api.openai.com/v1") or "https://api.openai.com/v1"
    )

    return Settings(
        root_dir=root_dir,
        env_path=env_path,
        output_dir=root_dir / "output",
        graphrag_root=root_dir / "workspace" / "graphrag_projects",
        llm_mode=(_resolve("GRAPH_MVP_LLM_MODE", dotenv_values, "openai") or "openai").strip().lower(),
        writer_model=_resolve("GRAPH_MVP_WRITER_MODEL", dotenv_values, "gpt-5.5") or "gpt-5.5",
        utility_model=_resolve("GRAPH_MVP_UTILITY_MODEL", dotenv_values, "gpt-5.4-mini") or "gpt-5.4-mini",
        embedding_model=_resolve("GRAPH_MVP_EMBEDDING_MODEL", dotenv_values, "text-embedding-3-large")
        or "text-embedding-3-large",
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
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
    )
