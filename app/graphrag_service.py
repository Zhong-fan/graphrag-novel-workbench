from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from neo4j import GraphDatabase

from .config import Settings
from .models import GraphWorkspace, Memory, Project, SourceDocument


@dataclass
class QueryResult:
    method: str
    response_type: str
    text: str


class GraphRAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def workspace_path(self, project: Project) -> Path:
        return self.settings.graphrag_root / f"project_{project.id}"

    def ensure_workspace(self, project: Project) -> Path:
        workspace = self.workspace_path(project)
        workspace.mkdir(parents=True, exist_ok=True)
        if not (workspace / "settings.yaml").exists():
            self._run_graphrag_command(
                ["init", "--root", str(workspace), "--force"],
                cwd=self.settings.root_dir,
            )
        self._write_workspace_env(workspace)
        self._patch_settings(workspace)
        return workspace

    def rebuild_inputs(
        self,
        project: Project,
        memories: list[Memory],
        sources: list[SourceDocument],
    ) -> Path:
        workspace = self.ensure_workspace(project)
        input_dir = workspace / "input"
        if input_dir.exists():
            shutil.rmtree(input_dir)
        input_dir.mkdir(parents=True, exist_ok=True)

        documents: list[tuple[str, str]] = [
            (
                "00_project_profile.txt",
                "\n".join(
                    [
                        f"项目名：{project.title}",
                        f"类型：{project.genre}",
                        f"核心前提：{project.premise}",
                        f"世界设定：{project.world_brief}",
                        f"写作规则：{project.writing_rules}",
                        f"标点规则：{project.punctuation_rule}",
                    ]
                ),
            )
        ]

        for memory in memories:
            documents.append(
                (
                    f"memory_{memory.id:04d}.txt",
                    "\n".join(
                        [
                            f"记忆标题：{memory.title}",
                            f"记忆范围：{memory.memory_scope}",
                            f"重要度：{memory.importance}",
                            f"内容：{memory.content}",
                        ]
                    ),
                )
            )

        for source in sources:
            documents.append(
                (
                    f"source_{source.id:04d}.txt",
                    "\n".join(
                        [
                            f"资料标题：{source.title}",
                            f"资料类型：{source.source_kind}",
                            source.content,
                        ]
                    ),
                )
            )

        for filename, content in documents:
            (input_dir / filename).write_text(content.strip() + "\n", encoding="utf-8")
        return workspace

    def index_project(
        self,
        project: Project,
        memories: list[Memory],
        sources: list[SourceDocument],
        workspace_record: GraphWorkspace,
    ) -> GraphWorkspace:
        workspace = self.rebuild_inputs(project, memories, sources)
        self._run_graphrag_command(
            [
                "index",
                "--root",
                str(workspace),
                "--method",
                self.settings.graphrag_index_method,
            ],
            cwd=self.settings.root_dir,
        )
        self.sync_to_neo4j(project, workspace)
        workspace_record.workspace_path = str(workspace)
        workspace_record.neo4j_sync_status = "synced"
        workspace_record.last_indexed_at = datetime.utcnow()
        return workspace_record

    def query(self, project: Project, prompt: str, method: str, response_type: str) -> QueryResult:
        workspace = self.workspace_path(project)
        if not workspace.exists():
            raise RuntimeError("GraphRAG 工作区不存在，请先索引项目。")
        stdout = self._run_graphrag_command(
            [
                "query",
                "--root",
                str(workspace),
                "--method",
                method,
                "--query",
                prompt,
                "--response-type",
                response_type,
            ],
            cwd=self.settings.root_dir,
        )
        return QueryResult(method=method, response_type=response_type, text=stdout.strip())

    def sync_to_neo4j(self, project: Project, workspace: Path) -> None:
        entities_path = self._latest_artifact(workspace, "entities.parquet")
        relationships_path = self._latest_artifact(workspace, "relationships.parquet")
        if entities_path is None:
            return

        entities = pd.read_parquet(entities_path)
        relationships = pd.read_parquet(relationships_path) if relationships_path else pd.DataFrame()

        driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        with driver.session(database=self.settings.neo4j_database) as session:
            session.execute_write(self._write_projection, project.id, project.title, entities, relationships)
        driver.close()

    def _write_projection(self, tx, project_id: int, project_title: str, entities: pd.DataFrame, relationships: pd.DataFrame) -> None:
        tx.run("MATCH (n {project_id: $project_id}) DETACH DELETE n", project_id=project_id)
        tx.run(
            """
            CREATE (:GraphRAGProject {
              project_id: $project_id,
              title: $title,
              kind: 'project'
            })
            """,
            project_id=project_id,
            title=project_title,
        )

        for _, row in entities.iterrows():
            props = row.to_dict()
            node_id = str(props.get("id") or props.get("entity_id") or props.get("title") or props.get("name"))
            title = str(props.get("title") or props.get("name") or node_id)
            tx.run(
                """
                CREATE (:GraphRAGEntity {
                  project_id: $project_id,
                  node_id: $node_id,
                  title: $title,
                  payload_json: $payload_json
                })
                """,
                project_id=project_id,
                node_id=node_id,
                title=title,
                payload_json=json.dumps(props, ensure_ascii=False, default=str),
            )

        if relationships.empty:
            return

        for _, row in relationships.iterrows():
            props = row.to_dict()
            source = str(props.get("source") or props.get("src_id") or props.get("source_title") or "")
            target = str(props.get("target") or props.get("tgt_id") or props.get("target_title") or "")
            if not source or not target:
                continue
            tx.run(
                """
                MATCH (a:GraphRAGEntity {project_id: $project_id, node_id: $source})
                MATCH (b:GraphRAGEntity {project_id: $project_id, node_id: $target})
                CREATE (a)-[:RELATES {
                  payload_json: $payload_json
                }]->(b)
                """,
                project_id=project_id,
                source=source,
                target=target,
                payload_json=json.dumps(props, ensure_ascii=False, default=str),
            )

    def _latest_artifact(self, workspace: Path, filename: str) -> Path | None:
        matches = list(workspace.rglob(filename))
        if not matches:
            return None
        return max(matches, key=lambda item: item.stat().st_mtime)

    def _write_workspace_env(self, workspace: Path) -> None:
        content = "\n".join(
            [
                f"GRAPHRAG_API_KEY={self.settings.openai_api_key or ''}",
                f"GRAPHRAG_API_BASE={self.settings.openai_base_url}",
                f"GRAPHRAG_CHAT_MODEL={self.settings.utility_model}",
                f"GRAPHRAG_EMBEDDING_MODEL={self.settings.embedding_model}",
            ]
        )
        (workspace / ".env").write_text(content + "\n", encoding="utf-8")

    def _patch_settings(self, workspace: Path) -> None:
        settings_path = workspace / "settings.yaml"
        if not settings_path.exists():
            return

        payload = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        models = payload.setdefault("models", {})

        default_chat = models.setdefault("default_chat_model", {})
        default_chat["model"] = "${GRAPHRAG_CHAT_MODEL}"
        default_chat["api_key"] = "${GRAPHRAG_API_KEY}"
        if "api_base" in default_chat or "type" in default_chat:
            default_chat["api_base"] = "${GRAPHRAG_API_BASE}"

        default_embedding = models.setdefault("default_embedding_model", {})
        default_embedding["model"] = "${GRAPHRAG_EMBEDDING_MODEL}"
        default_embedding["api_key"] = "${GRAPHRAG_API_KEY}"
        if "api_base" in default_embedding or "type" in default_embedding:
            default_embedding["api_base"] = "${GRAPHRAG_API_BASE}"

        settings_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _run_graphrag_command(self, args: list[str], *, cwd: Path) -> str:
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = self.settings.openai_api_key or ""
        env["OPENAI_BASE_URL"] = self.settings.openai_base_url
        env["GRAPHRAG_API_KEY"] = self.settings.openai_api_key or ""
        env["GRAPHRAG_API_BASE"] = self.settings.openai_base_url
        env["GRAPHRAG_CHAT_MODEL"] = self.settings.utility_model
        env["GRAPHRAG_EMBEDDING_MODEL"] = self.settings.embedding_model
        env["GRAPH_MVP_LOCAL_EMBEDDINGS"] = "1" if self.settings.graphrag_local_embeddings else "0"
        completed = subprocess.run(
            ["python", "-m", "app.graphrag_cli", *args],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"GraphRAG 命令失败：{' '.join(args)}\n{stderr}")
        return completed.stdout
