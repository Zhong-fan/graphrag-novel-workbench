from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from app.config import Settings
from app.graphrag_service import diagnose_graphrag_error


def make_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(
        root_dir=root,
        env_path=root / ".env",
        output_dir=root / "output",
        graphrag_root=root / "workspace" / "graphrag_projects",
        llm_mode="openai",
        writer_model="writer",
        utility_model="utility",
        embedding_model="bge-m3",
        openai_api_key="key",
        openai_base_url="https://api.example.test/v1",
        openai_use_system_proxy=False,
        llm_use_responses=True,
        llm_stream_responses=True,
        llm_request_timeout_seconds=120,
        llm_max_attempts=3,
        llm_retry_max_sleep_seconds=120,
        embedding_api_key="ollama",
        embedding_base_url="http://127.0.0.1:11434/v1",
        mysql_host="127.0.0.1",
        mysql_port=3307,
        mysql_user="user",
        mysql_password="password",
        mysql_database="db",
        neo4j_uri="neo4j://127.0.0.1:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        auth_secret="secret",
        auth_exp_hours=168,
        graphrag_response_type="Multiple Paragraphs",
        graphrag_index_method="standard",
        graphrag_local_embeddings=False,
    )


class GraphRAGDiagnosticsTest(unittest.TestCase):
    def test_diagnoses_response_format_incompatibility(self) -> None:
        settings = make_settings()
        detail = diagnose_graphrag_error("Bad request: response_format is not supported", settings)

        self.assertIn("response_format", detail)
        self.assertNotIn("chat=scheme", detail)
        self.assertIn(settings.utility_model, detail)

    def test_diagnoses_embedding_provider_failure(self) -> None:
        settings = make_settings()
        detail = diagnose_graphrag_error("embedding request failed with 503 model_not_found", settings)

        self.assertTrue("模型不可用" in detail or "Embedding provider" in detail)
        self.assertIn(settings.embedding_model, detail)

    def test_diagnoses_neo4j_sync_failure(self) -> None:
        settings = make_settings()
        detail = diagnose_graphrag_error("Neo4j authentication failed", replace(settings, graphrag_local_embeddings=True))

        self.assertIn("Neo4j", detail)


if __name__ == "__main__":
    unittest.main()
