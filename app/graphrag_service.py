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
from .models import (
    CharacterCard,
    CharacterStateUpdate,
    GraphWorkspace,
    Memory,
    Project,
    RelationshipStateUpdate,
    SourceDocument,
    StoryEvent,
    WorldPerceptionUpdate,
)


@dataclass
class QueryResult:
    method: str
    response_type: str
    text: str


def diagnose_graphrag_error(message: str, settings: Settings | None = None) -> str:
    normalized = message.lower()
    provider_hint = ""
    if settings is not None:
        provider_hint = (
            f"当前配置：graphrag_chat={settings.graphrag_chat_base_url} / {settings.graphrag_chat_model}"
            f" ({settings.graphrag_chat_provider_label})；"
            f"embedding={settings.embedding_base_url} / {settings.embedding_model} "
            f"({settings.embedding_provider_label})。"
        )

    if "neo4j" in normalized:
        return "GraphRAG 索引可能已完成，但 Neo4j 同步失败。请检查 NEO4J_URI、账号密码和 Neo4j 服务状态。"
    if "response_format" in normalized:
        return f"GraphRAG 索引模型不兼容 response_format。请为 GraphRAG 切换到兼容 OpenAI response_format 的 chat provider。{provider_hint}"
    if "model_not_found" in normalized or "model not found" in normalized or "404" in normalized:
        return f"模型不可用或名称不被 provider 支持。请分别检查 chat 模型和 embedding 模型配置。{provider_hint}"
    if "embedding" in normalized and any(token in normalized for token in ("503", "404", "not found", "connection", "connect")):
        return f"Embedding provider 不可用。请确认 embedding 服务已启动、base_url 含 /v1，且模型名称正确。{provider_hint}"
    if any(token in normalized for token in ("unauthorized", "invalid api key", "authentication", "401")):
        return f"API key 无效或缺失。请检查 OPENAI_API_KEY 或 GRAPH_MVP_EMBEDDING_API_KEY。{provider_hint}"
    if any(token in normalized for token in ("connection refused", "failed to establish", "name resolution", "timed out", "timeout")):
        return f"无法连接到模型或 embedding 服务。请检查网络、Docker 服务和 base_url。{provider_hint}"
    return f"GraphRAG 执行失败。请查看后端日志中的原始错误。{provider_hint}"


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
        self._remove_workspace_env(workspace)
        self._patch_settings(workspace)
        return workspace

    def rebuild_inputs(
        self,
        project: Project,
        memories: list[Memory],
        sources: list[SourceDocument],
        character_cards: list[CharacterCard] | None = None,
        character_updates: list[CharacterStateUpdate] | None = None,
        relationship_updates: list[RelationshipStateUpdate] | None = None,
        story_events: list[StoryEvent] | None = None,
        world_updates: list[WorldPerceptionUpdate] | None = None,
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
                        f"世界设定：{project.world_brief}",
                        f"用户自定义偏好：{project.writing_rules or '无'}",
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
                            f"设定标题：{memory.title}",
                            f"设定范围：{memory.memory_scope}",
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

        for card in character_cards or []:
            documents.append(
                (
                    f"character_card_{card.id:04d}.txt",
                    "\n".join(
                        [
                            f"人物姓名：{card.name}",
                            f"年龄：{card.age or '未填写'}",
                            f"性别：{card.gender or '未填写'}",
                            f"故事角色：{card.story_role or '未填写'}",
                            f"性格：{card.personality or '未填写'}",
                            f"人物背景：{card.background or '未填写'}",
                        ]
                    ),
                )
            )

        for update in (character_updates or [])[:40]:
            if getattr(update, "deleted_at", None) is not None:
                continue
            documents.append(
                (
                    f"state_character_{update.id:04d}.txt",
                    "\n".join(
                        [
                            f"角色：{update.character_name}",
                            f"当前情绪：{update.emotion_state}",
                            f"当前目标：{update.current_goal}",
                            f"自我认知变化：{update.self_view_shift}",
                            f"外界看法：{update.public_perception}",
                            f"状态摘要：{update.summary}",
                        ]
                    ),
                )
            )

        for update in (relationship_updates or [])[:40]:
            if getattr(update, "deleted_at", None) is not None:
                continue
            documents.append(
                (
                    f"state_relationship_{update.id:04d}.txt",
                    "\n".join(
                        [
                            f"来源角色：{update.source_character}",
                            f"目标角色：{update.target_character}",
                            f"变化类型：{update.change_type}",
                            f"变化方向：{update.direction}",
                            f"变化强度：{update.intensity}",
                            f"关系摘要：{update.summary}",
                        ]
                    ),
                )
            )

        for event in (story_events or [])[:40]:
            if getattr(event, "deleted_at", None) is not None:
                continue
            documents.append(
                (
                    f"story_event_{event.id:04d}.txt",
                    "\n".join(
                        [
                            f"事件标题：{event.title}",
                            f"事件摘要：{event.summary}",
                            f"影响摘要：{event.impact_summary}",
                            f"参与者：{event.participants_json}",
                            f"地点提示：{event.location_hint}",
                        ]
                    ),
                )
            )

        for update in (world_updates or [])[:40]:
            if getattr(update, "deleted_at", None) is not None:
                continue
            documents.append(
                (
                    f"world_update_{update.id:04d}.txt",
                    "\n".join(
                        [
                            f"主体：{update.subject_name}",
                            f"观察群体：{update.observer_group}",
                            f"方向：{update.direction}",
                            f"变化摘要：{update.change_summary}",
                        ]
                    ),
                )
            )

        for filename, content in documents:
            (input_dir / filename).write_text(content.strip() + "\n", encoding="utf-8")
        return workspace

    def prepare_project_inputs(
        self,
        project: Project,
        memories: list[Memory],
        sources: list[SourceDocument],
        character_cards: list[CharacterCard] | None = None,
        character_updates: list[CharacterStateUpdate] | None = None,
        relationship_updates: list[RelationshipStateUpdate] | None = None,
        story_events: list[StoryEvent] | None = None,
        world_updates: list[WorldPerceptionUpdate] | None = None,
    ) -> Path:
        return self.rebuild_inputs(
            project,
            memories,
            sources,
            character_cards=character_cards,
            character_updates=character_updates,
            relationship_updates=relationship_updates,
            story_events=story_events,
            world_updates=world_updates,
        )

    def review_payload(self, workspace: Path) -> dict[str, object]:
        input_dir = workspace / "input"
        files = sorted(item.name for item in input_dir.glob("*.txt")) if input_dir.exists() else []
        file_payloads: list[dict[str, str]] = []
        preview_blocks: list[str] = []
        for name in files:
            content = (input_dir / name).read_text(encoding="utf-8").strip()
            category = self._review_category(name)
            title = self._review_title(name, content)
            file_payloads.append(
                {
                    "filename": name,
                    "title": title,
                    "category": category,
                    "content": content,
                }
            )
        for item in file_payloads[:6]:
            preview_blocks.append(f"# {item['filename']}\n{item['content'][:1200]}")
        return {
            "workspace_path": str(workspace),
            "input_files": files,
            "files": file_payloads,
            "preview_text": "\n\n".join(preview_blocks).strip(),
        }

    def _review_category(self, filename: str) -> str:
        if filename.startswith("00_project_profile"):
            return "project"
        if filename.startswith("memory_"):
            return "memory"
        if filename.startswith("source_"):
            return "source"
        if filename.startswith("character_card_"):
            return "character"
        if filename.startswith("state_character_"):
            return "character_state"
        if filename.startswith("state_relationship_"):
            return "relationship_state"
        if filename.startswith("story_event_"):
            return "story_event"
        if filename.startswith("world_update_"):
            return "world_update"
        return "other"

    def _review_title(self, filename: str, content: str) -> str:
        first_line = next((line.strip() for line in content.splitlines() if line.strip()), filename)
        if "：" in first_line:
            return first_line.split("：", 1)[1].strip() or filename
        return first_line

    def index_project(
        self,
        project: Project,
        memories: list[Memory],
        sources: list[SourceDocument],
        workspace_record: GraphWorkspace,
        character_cards: list[CharacterCard] | None = None,
        character_updates: list[CharacterStateUpdate] | None = None,
        relationship_updates: list[RelationshipStateUpdate] | None = None,
        story_events: list[StoryEvent] | None = None,
        world_updates: list[WorldPerceptionUpdate] | None = None,
    ) -> GraphWorkspace:
        workspace = self.rebuild_inputs(
            project,
            memories,
            sources,
            character_cards=character_cards,
            character_updates=character_updates,
            relationship_updates=relationship_updates,
            story_events=story_events,
            world_updates=world_updates,
        )
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
        self._remove_workspace_env(workspace)
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

    def _remove_workspace_env(self, workspace: Path) -> None:
        workspace_env = workspace / ".env"
        if workspace_env.exists():
            workspace_env.unlink()

    def _patch_settings(self, workspace: Path) -> None:
        settings_path = workspace / "settings.yaml"
        if not settings_path.exists():
            return

        payload = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        models = payload.setdefault("models", {})

        default_chat = models.setdefault("default_chat_model", {})
        default_chat["model"] = "${GRAPHRAG_CHAT_MODEL}"
        default_chat["api_key"] = "${GRAPHRAG_CHAT_API_KEY}"
        default_chat["max_retries"] = self.settings.graphrag_chat_max_retries
        default_chat["request_timeout"] = self.settings.graphrag_chat_request_timeout_seconds
        if "api_base" in default_chat or "type" in default_chat:
            default_chat["api_base"] = "${GRAPHRAG_CHAT_API_BASE}"

        default_embedding = models.setdefault("default_embedding_model", {})
        default_embedding["model"] = "${GRAPHRAG_EMBEDDING_MODEL}"
        default_embedding["api_key"] = "${GRAPHRAG_EMBEDDING_API_KEY}"
        if "api_base" in default_embedding or "type" in default_embedding:
            default_embedding["api_base"] = "${GRAPHRAG_EMBEDDING_API_BASE}"

        extract_graph = payload.setdefault("extract_graph", {})
        extract_graph["concurrent_requests"] = self.settings.graphrag_concurrent_requests

        summarize_descriptions = payload.setdefault("summarize_descriptions", {})
        summarize_descriptions["concurrent_requests"] = self.settings.graphrag_concurrent_requests

        claim_extraction = payload.setdefault("claim_extraction", {})
        claim_extraction["concurrent_requests"] = self.settings.graphrag_concurrent_requests

        settings_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _run_graphrag_command(self, args: list[str], *, cwd: Path) -> str:
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = self.settings.openai_api_key or ""
        env["OPENAI_BASE_URL"] = self.settings.openai_base_url
        env["GRAPHRAG_CHAT_API_KEY"] = self.settings.graphrag_chat_api_key or ""
        env["GRAPHRAG_CHAT_API_BASE"] = self.settings.graphrag_chat_base_url
        env["GRAPHRAG_CHAT_MODEL"] = self.settings.graphrag_chat_model
        env["GRAPHRAG_CHAT_REQUEST_TIMEOUT_SECONDS"] = str(self.settings.graphrag_chat_request_timeout_seconds)
        env["GRAPHRAG_CHAT_MAX_RETRIES"] = str(self.settings.graphrag_chat_max_retries)
        env["GRAPHRAG_EMBEDDING_API_KEY"] = self.settings.embedding_api_key or ""
        env["GRAPHRAG_EMBEDDING_API_BASE"] = self.settings.embedding_base_url
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
            diagnosis = diagnose_graphrag_error(stderr, self.settings)
            raise RuntimeError(f"{diagnosis}\n\n原始错误：GraphRAG 命令失败：{' '.join(args)}\n{stderr}")
        return completed.stdout
