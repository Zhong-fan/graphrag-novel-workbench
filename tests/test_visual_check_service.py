from __future__ import annotations

import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.json_utils import json_dumps
from app.models import CharacterCard, MediaAsset, Project, Storyboard, StoryboardShot, User
from app.visual_check_service import (
    IDENTITY_DRIFT,
    IDENTITY_SWAP,
    VISUAL_MEDIUM_MISMATCH,
    VisualCheckService,
    medium_mismatch,
)
from app.visual_identity_regression_fixtures import VISUAL_REGRESSION_FIXTURES


class MediumMismatchTests(unittest.TestCase):
    def test_anime_project_with_live_action_frame_is_mismatch(self) -> None:
        self.assertTrue(medium_mismatch("2D动画", "live_action"))
        self.assertTrue(medium_mismatch("日系动画", "3d"))
        self.assertFalse(medium_mismatch("日系动画", "2d_anime"))

    def test_live_action_project_with_anime_frame_is_mismatch(self) -> None:
        self.assertTrue(medium_mismatch("实拍", "anime"))
        self.assertFalse(medium_mismatch("实拍", "live_action"))

    def test_unknown_medium_is_not_reported(self) -> None:
        self.assertFalse(medium_mismatch("", "live_action"))
        self.assertFalse(medium_mismatch("日系动画", ""))


class ShadowModeVisualCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)

    def _project_and_shot(self, session, *, medium: str, character_names: tuple[str, ...]):
        user = User(email="visual@example.com", display_name="视觉用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
        project = Project(owner=user, title="视觉项目", genre="青春", visual_style_medium=medium)
        session.add(project)
        session.flush()
        storyboard = Storyboard(project_id=project.id, title="视觉短片", source_chapter_ids_json="[]", status="draft", summary="")
        session.add(storyboard)
        session.flush()
        cards: list[CharacterCard] = []
        for index, name in enumerate(character_names):
            card = CharacterCard(project_id=project.id, name=name)
            session.add(card)
            cards.append(card)
        session.flush()
        bindings = [{"character_card_id": card.id} for card in cards]
        shot = StoryboardShot(
            storyboard_id=storyboard.id,
            shot_no=1,
            narration_text="",
            visual_prompt="",
            character_refs_json="[]",
            scene_refs_json="[]",
            meta_json=json_dumps({"identity_bindings": bindings}),
            status="draft",
        )
        session.add(shot)
        session.flush()
        return project, shot, cards

    def test_no_reporter_means_unverified_not_blocked(self) -> None:
        service = VisualCheckService(SimpleNamespace(), vision_reporter=None)
        with self.SessionLocal() as session:
            project, shot, _ = self._project_and_shot(session, medium="日系动画", character_names=())
            result = service.check_first_frame(
                db=session, project=project, shot=shot, first_frame_asset=MediaAsset(project_id=project.id, uri="")
            )
            self.assertFalse(result.checked)
            self.assertFalse(result.blocked)
            self.assertEqual(result.reason, "visual_check_not_configured")

    def test_every_regression_fixture_classifies_as_expected(self) -> None:
        for fixture in VISUAL_REGRESSION_FIXTURES:
            with self.subTest(fixture=fixture.name):
                service = VisualCheckService(
                    SimpleNamespace(),
                    vision_reporter=lambda asset, f=fixture: f.report,
                )
                with self.SessionLocal() as session:
                    project, shot, cards = self._project_and_shot(
                        session, medium=fixture.expected_medium, character_names=fixture.shot_character_names
                    )
                    session.flush()
                    result = service.check_first_frame(
                        db=session,
                        project=project,
                        shot=shot,
                        first_frame_asset=MediaAsset(project_id=project.id, uri=""),
                    )
                    self.assertTrue(result.checked)
                    categories = {finding.category for finding in result.findings}
                    if fixture.expected_findings:
                        self.assertTrue(result.blocked, fixture.name)
                        self.assertEqual(categories, set(fixture.expected_findings), fixture.name)
                    else:
                        self.assertFalse(result.blocked, fixture.name)
                        self.assertEqual(categories, set(), fixture.name)

    def test_fixture_catalog_is_complete(self) -> None:
        names = {fixture.name for fixture in VISUAL_REGRESSION_FIXTURES}
        for required in (
            "anime_to_live_action_drift",
            "costume_change",
            "lighting_change",
            "profile_view",
            "occlusion",
            "two_character_identity_swap",
        ):
            self.assertIn(required, names)


if __name__ == "__main__":
    unittest.main()
