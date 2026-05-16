from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    env_path: Path
    output_dir: Path
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
    auth_secret: str
    auth_exp_hours: int
    image_api_key: str
    image_base_url: str
    image_model: str
    image_size: str
    tts_api_key: str
    tts_base_url: str
    tts_model: str
    tts_voice: str
    ffmpeg_path: str

    @property
    def sqlalchemy_database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def embedding_provider_label(self) -> str:
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


def _resolve_first(
    names: tuple[str, ...],
    dotenv_values: dict[str, str],
    default: str | None = None,
) -> str | None:
    for name in names:
        value = dotenv_values.get(name)
        if value is not None:
            return value
    return default


def _require_first(names: tuple[str, ...], dotenv_values: dict[str, str]) -> str:
    for name in names:
        value = dotenv_values.get(name)
        if value is not None and value.strip():
            return value.strip()
    raise RuntimeError(f"Missing required config in MVP/.env: {', '.join(names)}")


def _resolve_embedding_settings(
    dotenv_values: dict[str, str],
    openai_api_key: str | None,
    openai_base_url: str,
) -> tuple[str, str | None, str]:
    embedding_base_url = _normalize_base_url(
        _require_first(("CHENFLOW_EMBEDDING_BASE_URL", "GRAPH_MVP_EMBEDDING_BASE_URL"), dotenv_values)
    )

    if _is_ollama_base_url(embedding_base_url):
        default_api_key = "ollama"
    elif _is_tei_base_url(embedding_base_url):
        default_api_key = "dummy"
    elif embedding_base_url == openai_base_url:
        default_api_key = openai_api_key or "ollama"
    else:
        default_api_key = openai_api_key

    embedding_model = _require_first(("CHENFLOW_EMBEDDING_MODEL", "GRAPH_MVP_EMBEDDING_MODEL"), dotenv_values)
    embedding_api_key = _resolve_first(
        ("CHENFLOW_EMBEDDING_API_KEY", "GRAPH_MVP_EMBEDDING_API_KEY"),
        dotenv_values,
        default_api_key,
    )
    return embedding_model, embedding_api_key, embedding_base_url


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    dotenv_values = _load_dotenv(env_path)

    openai_api_key = _require_first(("OPENAI_API_KEY",), dotenv_values)
    openai_base_url = _normalize_base_url(_require_first(("OPENAI_BASE_URL",), dotenv_values))
    embedding_model, embedding_api_key, embedding_base_url = _resolve_embedding_settings(
        dotenv_values,
        openai_api_key,
        openai_base_url,
    )

    return Settings(
        root_dir=root_dir,
        env_path=env_path,
        output_dir=root_dir / "output",
        llm_mode=_require_first(("CHENFLOW_LLM_MODE", "GRAPH_MVP_LLM_MODE"), dotenv_values).strip().lower(),
        writer_model=_require_first(("CHENFLOW_WRITER_MODEL", "GRAPH_MVP_WRITER_MODEL"), dotenv_values),
        utility_model=_require_first(("CHENFLOW_UTILITY_MODEL", "GRAPH_MVP_UTILITY_MODEL"), dotenv_values),
        embedding_model=embedding_model,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_use_system_proxy=_parse_bool(
            _resolve_first(("CHENFLOW_OPENAI_USE_SYSTEM_PROXY", "GRAPH_MVP_OPENAI_USE_SYSTEM_PROXY"), dotenv_values),
            default=False,
        ),
        llm_use_responses=_parse_bool(
            _resolve_first(("CHENFLOW_LLM_USE_RESPONSES", "GRAPH_MVP_LLM_USE_RESPONSES"), dotenv_values),
            default=True,
        ),
        llm_stream_responses=_parse_bool(
            _resolve_first(("CHENFLOW_LLM_STREAM_RESPONSES", "GRAPH_MVP_LLM_STREAM_RESPONSES"), dotenv_values),
            default=True,
        ),
        llm_request_timeout_seconds=_parse_positive_int(
            _resolve_first(("CHENFLOW_LLM_REQUEST_TIMEOUT_SECONDS", "GRAPH_MVP_LLM_REQUEST_TIMEOUT_SECONDS"), dotenv_values),
            120,
        ),
        llm_max_attempts=_parse_positive_int(
            _resolve_first(("CHENFLOW_LLM_MAX_ATTEMPTS", "GRAPH_MVP_LLM_MAX_ATTEMPTS"), dotenv_values),
            3,
        ),
        llm_retry_max_sleep_seconds=_parse_positive_int(
            _resolve_first(
                ("CHENFLOW_LLM_RETRY_MAX_SLEEP_SECONDS", "GRAPH_MVP_LLM_RETRY_MAX_SLEEP_SECONDS"),
                dotenv_values,
            ),
            120,
        ),
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        mysql_host=_require_first(("MYSQL_HOST",), dotenv_values),
        mysql_port=int(_require_first(("MYSQL_PORT",), dotenv_values)),
        mysql_user=_require_first(("MYSQL_USER",), dotenv_values),
        mysql_password=_require_first(("MYSQL_PASSWORD",), dotenv_values),
        mysql_database=_require_first(("MYSQL_DATABASE",), dotenv_values),
        auth_secret=_require_first(("AUTH_SECRET",), dotenv_values),
        auth_exp_hours=int(_require_first(("AUTH_EXP_HOURS",), dotenv_values)),
        image_api_key=_resolve_first(("CHENFLOW_IMAGE_API_KEY",), dotenv_values, "") or "",
        image_base_url=_resolve_first(("CHENFLOW_IMAGE_BASE_URL",), dotenv_values, "") or "",
        image_model=_resolve_first(("CHENFLOW_IMAGE_MODEL",), dotenv_values, "") or "",
        image_size=_resolve_first(("CHENFLOW_IMAGE_SIZE",), dotenv_values, "1024x1024") or "1024x1024",
        tts_api_key=_resolve_first(("CHENFLOW_TTS_API_KEY",), dotenv_values, "") or "",
        tts_base_url=_resolve_first(("CHENFLOW_TTS_BASE_URL",), dotenv_values, "") or "",
        tts_model=_resolve_first(("CHENFLOW_TTS_MODEL",), dotenv_values, "") or "",
        tts_voice=_resolve_first(("CHENFLOW_TTS_VOICE",), dotenv_values, "") or "",
        ffmpeg_path=_resolve_first(("CHENFLOW_FFMPEG_PATH",), dotenv_values, "ffmpeg") or "ffmpeg",
    )
