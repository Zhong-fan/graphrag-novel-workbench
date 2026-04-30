from __future__ import annotations

from .agents import PlannerAgent, UpdaterAgent, WriterAgent
from .config import Settings
from .graph_backend import GraphBackend
from .graph_store import GraphStore
from .llm import BaseLLM
from .retriever import GraphRetriever
from .schema import ChapterDraft, ChapterPlan, ChapterRecord, ChapterRequest, ChapterUpdate, Edge, Node
from .storage import read_json, write_text


class ChapterPipeline:
    def __init__(
        self,
        *,
        settings: Settings,
        graph_store: GraphBackend,
        retriever: GraphRetriever,
        llm: BaseLLM,
    ) -> None:
        self.settings = settings
        self.graph_store = graph_store
        self.retriever = retriever
        self.llm = llm
        self.planner = PlannerAgent(settings=settings, llm=llm)
        self.writer = WriterAgent(settings=settings, llm=llm)
        self.updater = UpdaterAgent(settings=settings, llm=llm)

    def initialize_state(self) -> None:
        if self.graph_store.exists():
            return
        seed_payload = read_json(self.settings.seed_path)
        self.graph_store.save(self._seed_to_graph(seed_payload))

    def _seed_to_graph(self, payload: dict) -> object:
        from .schema import ChapterRecord, Edge, Node, StoryGraph

        return StoryGraph(
            project=payload["project"],
            nodes=[Node(**node) for node in payload["nodes"]],
            edges=[Edge(**edge) for edge in payload["edges"]],
            chapter_history=[
                ChapterRecord(**record) for record in payload.get("chapter_history", [])
            ],
        )

    def generate_chapter(self, request: ChapterRequest) -> ChapterDraft:
        graph = self.graph_store.load()
        retrieval = self.retriever.retrieve(graph, request)
        title = self._build_title(graph.project["title"], request)
        plan, planner_model = self.planner.plan(
            project=graph.project,
            request=request,
            retrieval=retrieval,
        )
        chapter_text, writer_model = self.writer.write(
            project=graph.project,
            request=request,
            retrieval=retrieval,
            plan=plan,
        )
        update, updater_model = self.updater.extract(
            request=request,
            retrieval=retrieval,
            plan=plan,
            title=title,
            chapter_text=chapter_text,
        )
        summary = update.event_summary or self._build_summary(request, retrieval)
        content = self._render_chapter_markdown(
            title=title,
            summary=summary,
            llm_text=chapter_text,
            request=request,
            retrieval=retrieval,
            plan=plan,
            update=update,
            planner_model=planner_model,
            writer_model=writer_model,
            updater_model=updater_model,
        )

        record = ChapterRecord(
            chapter_number=request.chapter_number,
            title=title,
            summary=summary,
            focus_characters=request.focus_characters,
            location=request.location,
            motif=request.motif,
            event_id=f"evt_chapter_{request.chapter_number:02d}",
        )
        self._writeback(graph, record, update)
        self.graph_store.save(graph)

        output_path = self.settings.output_dir / f"chapter_{request.chapter_number:02d}.md"
        write_text(output_path, content)
        return ChapterDraft(title=title, summary=summary, content=content)

    def _build_title(self, project_title: str, request: ChapterRequest) -> str:
        return f"第{request.chapter_number:02d}章 - {project_title}"

    def _build_summary(self, request: ChapterRequest, retrieval: object) -> str:
        focus_names = ", ".join(node.name for node in retrieval.focus_nodes if node.type == "Character")
        location_name = next(
            (node.name for node in retrieval.focus_nodes if node.id == request.location),
            request.location,
        )
        motif_name = next(
            (node.name for node in retrieval.focus_nodes if node.id == request.motif),
            request.motif,
        )
        return (
            f"{focus_names or '主要角色'}在{location_name}之中重新靠近，"
            f"{motif_name}为这一章关于“{request.premise}”的情绪走向着色。"
        )

    def _render_chapter_markdown(
        self,
        *,
        title: str,
        summary: str,
        llm_text: str,
        request: ChapterRequest,
        retrieval: object,
        plan: ChapterPlan,
        update: ChapterUpdate,
        planner_model: str,
        writer_model: str,
        updater_model: str,
    ) -> str:
        focus_names = ", ".join(node.name for node in retrieval.focus_nodes if node.type == "Character")
        related_lines: list[str] = []
        for node in retrieval.related_nodes[:5]:
            note = (
                node.attributes.get("note")
                or node.attributes.get("role")
                or node.attributes.get("summary")
            )
            related_lines.append(f"- {node.name}: {note}" if note else f"- {node.name}")
        related_snapshot = "\n".join(related_lines)
        scene_brief = "\n".join(
            f"{index}. {beat.label}：{beat.focus} 张力：{beat.tension} 转折：{beat.turn}"
            for index, beat in enumerate(plan.scene_beats, start=1)
        )
        continuity_notes = "\n".join(f"- {item}" for item in update.continuity_notes[:5])
        lines = [
            f"# {title}",
            "",
            f"> 规划模型：`{planner_model}` | 写作模型：`{writer_model}` | 回写模型：`{updater_model}`",
            "",
            "## 章节卡",
            "",
            f"- 前提：{request.premise}",
            f"- 聚焦角色：{focus_names or '无'}",
            f"- 计划中的情绪变化：{plan.emotional_shift}",
            f"- 摘要：{summary}",
            "",
            "## 场景简报",
            "",
            scene_brief or "1. 暂未生成场景简报。",
            "",
            "## 检索上下文摘要",
            "",
            related_snapshot or "- 没有检索到额外相关节点。",
            "",
            "## 结构化回写",
            "",
            f"- 事件：{update.event_name}",
            f"- 核心意象：{plan.motif_image}",
            continuity_notes or "- 暂无连续性备注。",
            "",
            "## 正文草稿",
            "",
            llm_text.strip(),
            "",
        ]
        return "\n".join(lines)

    def _writeback(self, graph: object, record: ChapterRecord, update: ChapterUpdate) -> None:
        graph.chapter_history = [
            item for item in graph.chapter_history if item.chapter_number != record.chapter_number
        ]
        GraphStore.remove_node_and_incident_edges(graph, record.event_id)

        event_node = Node(
            id=record.event_id,
            type="Event",
            name=update.event_name or record.title,
            attributes={
                "summary": record.summary,
                "chapter_number": record.chapter_number,
                **update.event_attributes,
            },
        )
        GraphStore.upsert_node(graph, event_node)
        graph.chapter_history.append(record)

        GraphStore.append_edge(
            graph,
            Edge(
                source=record.location,
                target=record.event_id,
                type="hosts",
                attributes={"chapter_number": record.chapter_number},
            ),
        )
        GraphStore.append_edge(
            graph,
            Edge(
                source=record.motif,
                target=record.event_id,
                type="colors",
                attributes={"chapter_number": record.chapter_number},
            ),
        )
        for character_id in record.focus_characters:
            GraphStore.append_edge(
                graph,
                Edge(
                    source=character_id,
                    target=record.event_id,
                    type="participates_in",
                    attributes={"chapter_number": record.chapter_number},
                ),
            )

        node_ids = {node.id for node in graph.nodes}
        for edge in update.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                continue
            GraphStore.append_edge(
                graph,
                Edge(
                    source=edge.source,
                    target=edge.target,
                    type=edge.type,
                    attributes=edge.attributes,
                ),
            )
