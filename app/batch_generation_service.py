from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_support_generation import _replace_canonical_evolution, _snapshot_with_process
from .api_support_project import _canonical_project_evolution
from .config import Settings
from .evolution_service import EvolutionService
from .json_utils import json_loads_object
from .models import BatchGenerationJob, ChapterOutline, DraftVersion, GenerationRun, Project, ProjectChapter, SeriesPlan
from .story_service import StoryGenerationService


class BatchGenerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run_job(
        self,
        *,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        start_chapter_no: int,
        end_chapter_no: int,
    ) -> BatchGenerationJob:
        outlines = db.scalars(
            select(ChapterOutline)
            .where(
                ChapterOutline.series_plan_id == series_plan.id,
                ChapterOutline.chapter_no >= start_chapter_no,
                ChapterOutline.chapter_no <= end_chapter_no,
            )
            .order_by(ChapterOutline.chapter_no.asc())
        ).all()
        if not outlines:
            raise RuntimeError("没有找到可生成的章节概要。")
        missing_locked = [item.chapter_no for item in outlines if item.status != "outline_locked"]
        if missing_locked:
            raise RuntimeError("以下章节概要尚未锁定：" + "、".join(str(item) for item in missing_locked))

        job = BatchGenerationJob(
            project=project,
            series_plan=series_plan,
            start_chapter_no=start_chapter_no,
            end_chapter_no=end_chapter_no,
            job_status="running",
            result_summary_json=json.dumps({"generated": [], "failed": []}, ensure_ascii=False),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        generated: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        writer = StoryGenerationService(self.settings)
        evolution = EvolutionService(self.settings)

        for outline in outlines:
            job.current_chapter_no = outline.chapter_no
            db.commit()
            try:
                generation = self._generate_one(
                    db=db,
                    project=project,
                    series_plan=series_plan,
                    outline=outline,
                    writer=writer,
                    evolution=evolution,
                )
                generated.append(
                    {
                        "chapter_no": outline.chapter_no,
                        "outline_id": outline.id,
                        "generation_id": generation.id,
                        "title": generation.title,
                    }
                )
                job.result_summary_json = json.dumps({"generated": generated, "failed": failed}, ensure_ascii=False)
                db.commit()
            except Exception as exc:
                failed.append({"chapter_no": outline.chapter_no, "outline_id": outline.id, "error": str(exc)})
                job.job_status = "failed"
                job.result_summary_json = json.dumps({"generated": generated, "failed": failed}, ensure_ascii=False)
                db.commit()
                raise

        job.job_status = "completed"
        job.current_chapter_no = end_chapter_no
        job.result_summary_json = json.dumps({"generated": generated, "failed": failed}, ensure_ascii=False)
        db.commit()
        db.refresh(job)
        return job

    def _generate_one(
        self,
        *,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        outline: ChapterOutline,
        writer: StoryGenerationService,
        evolution: EvolutionService,
    ) -> GenerationRun:
        outline_payload = json_loads_object(outline.outline_json)
        project_chapter = self._ensure_project_chapter(db, project, outline, outline_payload)
        scene_card = self._build_outline_scene_card(db, project, series_plan, outline, outline_payload)
        user_prompt = self._outline_to_prompt(outline_payload)
        memories = [{"title": item.title, "content": item.content} for item in project.memories]
        title, summary, content = writer.generate(
            project_title=project.title,
            genre=project.genre,
            reference_work=project.reference_work,
            premise=project_chapter.premise,
            world_brief=project.world_brief,
            writing_rules=project.writing_rules,
            style_profile=project.style_profile,
            user_prompt=user_prompt,
            response_type="完整章节正文",
            scene_card=scene_card,
            memories=memories,
            use_refiner=True,
        )

        generation = GenerationRun(
            project=project,
            project_chapter=project_chapter,
            prompt=user_prompt,
            search_method="series_outline",
            response_type="完整章节正文",
            retrieval_context=json.dumps(
                {
                    "mode": "longform_batch_generation",
                    "series_plan_id": series_plan.id,
                    "chapter_outline_id": outline.id,
                    "chapter_no": outline.chapter_no,
                },
                ensure_ascii=False,
            ),
            scene_card=scene_card,
            evolution_snapshot=json.dumps(
                {
                    "process": {
                        "draft": {"status": "done", "message": "批量正文已生成"},
                        "refine": {"status": "done", "message": "正文已润色"},
                        "evolution": {"status": "pending", "message": "等待抽取变化"},
                    },
                    "characters": [],
                    "relationships": [],
                    "events": [],
                    "world_updates": [],
                },
                ensure_ascii=False,
            ),
            generation_trace=json.dumps(
                {
                    "project": {"id": project.id, "title": project.title},
                    "chapter": {"outline_id": outline.id, "chapter_no": outline.chapter_no, "title": outline.title},
                    "request": {"mode": "longform_batch_generation"},
                    "result": {"title": title, "summary_length": len(summary), "content_length": len(content)},
                },
                ensure_ascii=False,
            ),
            title=title,
            summary=summary,
            content=content,
        )
        db.add(generation)
        db.flush()

        try:
            evolution_payload = evolution.extract_evolution(
                project_title=project.title,
                genre=project.genre,
                premise=project_chapter.premise,
                user_prompt=user_prompt,
                title=title,
                summary=summary,
                content=content,
            )
            _replace_canonical_evolution(db, project, generation, evolution_payload)
            generation.canonicalized_at = datetime.utcnow()
            generation.evolution_snapshot = _snapshot_with_process(
                evolution_payload,
                {
                    "draft": {"status": "done", "message": "批量正文已生成"},
                    "refine": {"status": "done", "message": "正文已润色"},
                    "evolution": {"status": "done", "message": "变化抽取已完成"},
                },
            )
        except RuntimeError as exc:
            generation.evolution_snapshot = _snapshot_with_process(
                evolution.empty_payload(),
                {
                    "draft": {"status": "done", "message": "批量正文已生成"},
                    "refine": {"status": "done", "message": "正文已润色"},
                    "evolution": {"status": "failed", "message": str(exc)},
                },
            )

        version_no = (
            db.scalar(
                select(DraftVersion.version_no)
                .where(DraftVersion.chapter_outline_id == outline.id)
                .order_by(DraftVersion.version_no.desc())
                .limit(1)
            )
            or 0
        ) + 1
        draft = DraftVersion(
            project=project,
            chapter_outline=outline,
            generation_run=generation,
            version_no=version_no,
            title=title,
            summary=summary,
            content=content,
            status="draft_generated",
            revision_reason="batch_generation",
        )
        outline.status = "draft_generated"
        db.add(draft)
        db.commit()
        db.refresh(generation)
        return generation

    def _ensure_project_chapter(
        self,
        db: Session,
        project: Project,
        outline: ChapterOutline,
        outline_payload: dict[str, Any],
    ) -> ProjectChapter:
        existing = db.scalar(
            select(ProjectChapter).where(ProjectChapter.project_id == project.id, ProjectChapter.chapter_no == outline.chapter_no)
        )
        premise = self._outline_to_prompt(outline_payload)
        if existing is not None:
            existing.title = outline.title
            existing.premise = premise
            db.flush()
            return existing
        chapter = ProjectChapter(
            project=project,
            title=outline.title,
            premise=premise,
            chapter_no=outline.chapter_no,
        )
        db.add(chapter)
        db.flush()
        return chapter

    def _build_outline_scene_card(
        self,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        outline: ChapterOutline,
        outline_payload: dict[str, Any],
    ) -> str:
        character_updates, relationship_updates, story_events, world_updates = _canonical_project_evolution(db, project)
        recent_events = "\n".join(f"- {item.title}: {item.impact_summary or item.summary}" for item in story_events[:8]) or "- 暂无"
        recent_characters = "\n".join(f"- {item.character_name}: {item.summary}" for item in character_updates[:8]) or "- 暂无"
        recent_relationships = (
            "\n".join(f"- {item.source_character}->{item.target_character}: {item.summary}" for item in relationship_updates[:8])
            or "- 暂无"
        )
        recent_world = "\n".join(f"- {item.observer_group} 对 {item.subject_name}: {item.change_summary}" for item in world_updates[:8]) or "- 暂无"
        return "\n".join(
            [
                "长篇批量生成场景卡",
                f"全书规划：{series_plan.title}",
                f"章节：第 {outline.chapter_no} 章 / {outline.title}",
                "",
                "章节概要",
                self._outline_to_prompt(outline_payload),
                "",
                "最近关键事件",
                recent_events,
                "",
                "最近人物状态",
                recent_characters,
                "",
                "最近关系状态",
                recent_relationships,
                "",
                "最近外界认知",
                recent_world,
            ]
        )

    def _outline_to_prompt(self, outline_payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"本章目标：{outline_payload.get('chapter_goal', '')}",
                f"主要冲突：{outline_payload.get('conflict', '')}",
                f"情绪基调：{outline_payload.get('emotion_tone', '')}",
                f"必须发生：{outline_payload.get('must_happen', [])}",
                f"禁止发生：{outline_payload.get('must_not_happen', [])}",
                f"角色推进：{outline_payload.get('character_progress', [])}",
                f"结尾钩子：{outline_payload.get('ending_hook', '')}",
                f"预计篇幅：{outline_payload.get('estimated_length', '')}",
            ]
        ).strip()
