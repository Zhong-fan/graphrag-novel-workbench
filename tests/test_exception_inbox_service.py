from __future__ import annotations

import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.exception_inbox_service import create_inbox_item, list_inbox_items, resolve_inbox_item
from app.models import Project, User


class ExceptionInboxServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)

    def _project(self, session) -> Project:
        user = User(email="inbox@example.com", display_name="收件箱用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
        project = Project(owner=user, title="收件箱项目", genre="青春")
        session.add(project)
        session.commit()
        return project

    def test_create_list_resolve_round_trip(self) -> None:
        with self.SessionLocal() as session:
            project = self._project(session)
            item = create_inbox_item(
                db=session,
                project=project,
                item_type="budget_approval",
                title="视频生成成本需要确认",
                reason="估算成本超阈值。",
                recommended_action="确认预算后继续。",
                options=[
                    {"label": "确认预算继续", "impact": "产生费用。"},
                    {"label": "暂不生成", "impact": "不产生费用。"},
                ],
                evidence={"generation_attempt_id": 42},
                severity="high",
            )
            session.commit()
            self.assertEqual(item.status, "open")
            self.assertEqual(len(json.loads(item.options_json)), 2)

            listed = list_inbox_items(session, project_id=project.id)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].title, "视频生成成本需要确认")

            resolved = resolve_inbox_item(session, project_id=project.id, item_id=item.id, resolution="accepted")
            session.commit()
            self.assertEqual(resolved.status, "resolved")
            self.assertEqual(resolved.resolution, "accepted")
            self.assertIsNotNone(resolved.resolved_at)
            self.assertEqual(list_inbox_items(session, project_id=project.id, status="open"), [])
            self.assertEqual(len(list_inbox_items(session, project_id=project.id, status="resolved")), 1)

    def test_identical_open_item_is_deduplicated(self) -> None:
        with self.SessionLocal() as session:
            project = self._project(session)
            first = create_inbox_item(
                db=session,
                project=project,
                item_type="repeated_quality_failure",
                title="分镜生成重复失败",
                reason="校验失败",
                recommended_action="重试",
                evidence={"storyboard_id": 3},
            )
            second = create_inbox_item(
                db=session,
                project=project,
                item_type="repeated_quality_failure",
                title="分镜生成重复失败",
                reason="校验失败",
                recommended_action="重试",
                evidence={"storyboard_id": 3},
            )
            session.commit()
            self.assertEqual(first.id, second.id)
            self.assertEqual(len(list_inbox_items(session, project_id=project.id)), 1)

    def test_resolve_unknown_item_raises(self) -> None:
        with self.SessionLocal() as session:
            project = self._project(session)
            with self.assertRaises(LookupError):
                resolve_inbox_item(session, project_id=project.id, item_id=9999, resolution="dismissed")

    def test_options_are_capped_at_three(self) -> None:
        with self.SessionLocal() as session:
            project = self._project(session)
            item = create_inbox_item(
                db=session,
                project=project,
                item_type="creative_identity",
                title="角色身份存在歧义",
                reason="两个候选都符合。",
                recommended_action="选择一个候选",
                options=[
                    {"label": "a", "impact": "i"},
                    {"label": "b", "impact": "i"},
                    {"label": "c", "impact": "i"},
                    {"label": "d", "impact": "i"},
                ],
            )
            session.commit()
            self.assertEqual(len(json.loads(item.options_json)), 3)


if __name__ == "__main__":
    unittest.main()
