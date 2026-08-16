import hashlib
import json
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.batch_generation_service import BatchGenerationService
from app.db import Base
from app.models import BatchGenerationChapterTask, BatchGenerationJob, ChapterOutline, Project, SeriesPlan, User


class ChapterTaskRecoveryContractTests(unittest.TestCase):
    def setUp(self):
        self.service = BatchGenerationService(SimpleNamespace(writer_model="test-model"))

    def test_progress_keeps_failed_chapter_out_of_successful_count(self):
        job = SimpleNamespace(
            job_status="failed",
            current_chapter_no=12,
            chapter_tasks=[
                SimpleNamespace(chapter_no=i, status="completed", draft_version_id=i, generation_run_id=i, chapter_outline_id=i)
                for i in range(1, 12)
            ]
            + [SimpleNamespace(chapter_no=12, status="failed", draft_version_id=None, generation_run_id=None, chapter_outline_id=12, error_message="provider timeout")],
            result_summary_json="{}",
        )
        self.service._update_job_summary(job, [], [{"chapter_no": 12, "error": "provider timeout"}])
        summary = json.loads(job.result_summary_json)["summary"]
        self.assertEqual(summary["completed_chapters"], 11)
        self.assertEqual(summary["failed_chapters"], 1)
        self.assertEqual(summary["processed_chapters"], 12)
        self.assertEqual(summary["remaining_chapters"], 0)

    def test_manifest_is_canonical_and_default_steps_are_recoverable(self):
        task = SimpleNamespace()
        outline = SimpleNamespace(id=12, chapter_no=12, title="终章", outline_json='{"goal":"收束冲突"}')
        plan = SimpleNamespace(id=3, current_version_id=8)
        project = SimpleNamespace(id=7, title="测试项目", genre="悬疑")
        db = SimpleNamespace(scalar=lambda _query: None)
        self.service._resolve_task_manifest(task, project=project, series_plan=plan, outline=outline, db=db)
        self.assertEqual(len(task.manifest_fingerprint), 64)
        self.assertEqual(json.loads(task.manifest_json)["chapter"]["chapter_no"], 12)
        self.assertEqual([step["name"] for step in self.service._default_steps()], [
            "resolve_inputs", "preflight", "provider_generate", "validate_output", "persist_output",
        ])


class ChapterTaskRetryBehaviorTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.db = self.SessionLocal()
        user = User(email="chapter-retry@example.com", display_name="测试", password_hash=b"0" * 32, password_salt=b"1" * 16)
        project = Project(owner=user, title="章节恢复", genre="悬疑")
        plan = SeriesPlan(project=project, title="规划", target_chapter_count=1, theme="主题", main_conflict="冲突", ending_direction="结局", status="locked")
        outline = ChapterOutline(project=project, series_plan=plan, chapter_no=1, title="第一章", outline_json='{"goal":"开场"}', status="outline_locked")
        job = BatchGenerationJob(project=project, series_plan=plan, start_chapter_no=1, end_chapter_no=1, job_status="failed", result_summary_json="{}")
        task = BatchGenerationChapterTask(job=job, chapter_outline=outline, chapter_no=1, status="failed", error_message="timeout", current_step="provider_generate", execution_steps_json=json.dumps(BatchGenerationService._default_steps(), ensure_ascii=False), output_validity="invalid")
        self.db.add(task)
        self.db.flush()
        self.service = BatchGenerationService(SimpleNamespace(writer_model="test-model"))
        self.service._resolve_task_manifest(task, project=project, series_plan=plan, outline=outline, db=self.db)
        manifest = json.loads(task.manifest_json)
        manifest["input_state"] = "frozen_actual"
        manifest["provider_request"] = {"model": "test-model", "system_prompt": "system", "user_prompt": "chapter", "messages": []}
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        task.manifest_json = encoded
        task.manifest_fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        self.db.commit()
        self.task_id = task.id

    def tearDown(self):
        self.db.close()

    def test_same_input_retry_is_idempotency_safe(self):
        task = self.db.get(BatchGenerationChapterTask, self.task_id)
        changed = self.service.retry_chapter_task(db=self.db, task=task, mode="same_inputs")
        self.assertEqual(changed.status, "queued")
        with self.assertRaisesRegex(RuntimeError, "重复提交"):
            self.service.retry_chapter_task(db=self.db, task=changed, mode="same_inputs")

    def test_changed_input_requires_real_instruction_and_creates_replacement(self):
        task = self.db.get(BatchGenerationChapterTask, self.task_id)
        outline_two = ChapterOutline(project_id=task.job.project_id, series_plan_id=task.job.series_plan_id, chapter_no=2, title="第二章", outline_json='{"goal":"延续"}', status="draft_generated")
        downstream_job = BatchGenerationJob(project_id=task.job.project_id, series_plan_id=task.job.series_plan_id, start_chapter_no=2, end_chapter_no=2, job_status="completed", result_summary_json="{}")
        downstream = BatchGenerationChapterTask(job=downstream_job, chapter_outline=outline_two, chapter_no=2, status="completed", error_message="", output_validity="valid")
        self.db.add(downstream)
        self.db.flush()
        downstream_id = downstream.id
        with self.assertRaisesRegex(RuntimeError, "填写"):
            self.service.retry_chapter_task(db=self.db, task=task, mode="edit_inputs", input_overrides={})
        replacement = self.service.retry_chapter_task(
            db=self.db,
            task=task,
            mode="edit_inputs",
            input_overrides={"user_instruction": "加强雨夜氛围"},
        )
        self.assertNotEqual(replacement.id, task.id)
        self.assertEqual(replacement.supersedes_task_id, task.id)
        replacement_manifest = json.loads(replacement.manifest_json)
        self.assertEqual(replacement_manifest["input_state"], "planned_edited")
        self.assertEqual(replacement_manifest["input_overrides"]["user_instruction"], "加强雨夜氛围")
        invalidated = self.db.get(BatchGenerationChapterTask, downstream_id)
        self.assertEqual(invalidated.output_validity, "stale_dependency")
        self.assertIn("第 1 章", invalidated.invalidation_reason)

    def test_batch_retry_cannot_bypass_frozen_input_gate(self):
        task = self.db.get(BatchGenerationChapterTask, self.task_id)
        manifest = json.loads(task.manifest_json)
        manifest["input_state"] = "planned"
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        task.manifest_json = encoded
        task.manifest_fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "输入冻结之前"):
            self.service.retry_job(db=self.db, job=task.job)

    def test_cascade_regeneration_starts_at_earliest_stale_chapter_and_preserves_history(self):
        source = self.db.get(BatchGenerationChapterTask, self.task_id)
        outline_two = ChapterOutline(project_id=source.job.project_id, series_plan_id=source.job.series_plan_id, chapter_no=2, title="第二章", outline_json='{"goal":"延续"}', status="draft_generated")
        historical_job = BatchGenerationJob(project_id=source.job.project_id, series_plan_id=source.job.series_plan_id, start_chapter_no=2, end_chapter_no=2, job_status="completed", result_summary_json="{}")
        historical = BatchGenerationChapterTask(job=historical_job, chapter_outline=outline_two, chapter_no=2, status="completed", error_message="", output_validity="stale_dependency")
        self.db.add(historical)
        self.db.commit()
        historical_id = historical.id

        with self.assertRaisesRegex(RuntimeError, "最早失效"):
            self.service.create_stale_cascade_job(
                db=self.db,
                project=source.job.project,
                series_plan=source.job.series_plan,
                start_chapter_no=3,
            )
        job = self.service.create_stale_cascade_job(
            db=self.db,
            project=source.job.project,
            series_plan=source.job.series_plan,
            start_chapter_no=2,
        )
        self.assertEqual(job.job_status, "queued")
        self.assertEqual([task.chapter_no for task in job.chapter_tasks], [2])
        self.assertEqual(job.chapter_tasks[0].supersedes_task_id, historical_id)
        self.assertEqual(self.db.get(BatchGenerationChapterTask, historical_id).output_validity, "stale_dependency")

    def test_invalidation_keeps_execution_truth_and_records_cause(self):
        source = self.db.get(BatchGenerationChapterTask, self.task_id)
        outline_two = ChapterOutline(project_id=source.job.project_id, series_plan_id=source.job.series_plan_id, chapter_no=2, title="第二章", outline_json='{"goal":"延续"}', status="chapter_canonical")
        job = BatchGenerationJob(project_id=source.job.project_id, series_plan_id=source.job.series_plan_id, start_chapter_no=2, end_chapter_no=2, job_status="completed", result_summary_json="{}")
        completed = BatchGenerationChapterTask(job=job, chapter_outline=outline_two, chapter_no=2, status="completed", error_message="", output_validity="valid")
        self.db.add(completed)
        self.db.flush()
        completed_id = completed.id

        affected = self.service.invalidate_chapter_outputs(
            db=self.db,
            series_plan_id=source.job.series_plan_id,
            from_chapter_no=2,
            changed_chapter_no=1,
            reason="第 1 章确认了新的正文版本 v2",
            invalidated_by_draft_version_id=99,
        )
        self.db.commit()
        historical = self.db.get(BatchGenerationChapterTask, completed_id)
        self.assertEqual(affected, [2])
        self.assertEqual(historical.status, "completed")
        self.assertEqual(historical.output_validity, "stale_dependency")
        self.assertEqual(historical.invalidated_by_chapter_no, 1)
        self.assertEqual(historical.invalidated_by_draft_version_id, 99)
        self.assertIn("正文版本 v2", historical.invalidation_reason)


if __name__ == "__main__":
    unittest.main()
