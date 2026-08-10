from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_VUE = ROOT / "frontend" / "src" / "App.vue"
WORKBENCH_STORE = ROOT / "frontend" / "src" / "stores" / "workbench.ts"
TOONFLOW_WORKBENCH = ROOT / "frontend" / "src" / "components" / "workspace" / "ToonflowWorkbench.vue"
WORKSPACE_DIR = ROOT / "frontend" / "src" / "components" / "workspace"
PLAYWRIGHT_AUDIT = ROOT / "scripts" / "playwright_audit.mjs"


class FrontendToonflowWorkbenchTests(unittest.TestCase):
    def test_app_uses_single_toonflow_workbench_surface(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")

        self.assertIn("import ToonflowWorkbench", app_source)
        self.assertEqual(app_source.count("<ToonflowWorkbench"), 1)
        self.assertNotIn("WorkspaceSidebar", app_source)
        self.assertNotIn("WorkspaceProjectCreatePanel", app_source)
        self.assertNotIn("LongformPipelinePanel", app_source)
        self.assertNotIn("NovelEditorPanel", app_source)
        self.assertNotIn("VideoStagePage", app_source)

    def test_legacy_workspace_components_are_removed(self) -> None:
        remaining = sorted(path.name for path in WORKSPACE_DIR.glob("*.vue"))

        self.assertEqual(remaining, ["DraftReader.vue", "SeriesPlanReader.vue", "TaskCenter.vue", "ToonflowWorkbench.vue"])

    def test_toonflow_workbench_matches_project_canvas_model(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("编剧", source)
        self.assertIn("资产", source)
        self.assertIn("出片", source)
        self.assertIn("toon-canvas", source)
        self.assertIn("toon-flow-node", source)
        self.assertIn("toon-storyboard-table", source)
        self.assertIn("toon-frame-panel", source)
        self.assertIn("生产监督", source)
        self.assertNotIn("视频创作", source)
        self.assertNotIn("小说创作", source)
        self.assertNotIn("动画资产", source)

    def test_workbench_adapts_navigation_for_touch_screens(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("toon-rail__label", source)
        self.assertIn("iconPaths", source)
        self.assertIn('viewBox="0 0 24 24"', source)
        self.assertNotIn('glyph: "▱"', source)
        self.assertIn(":aria-current=\"activeModule === item.module ? 'page' : undefined\"", source)
        self.assertIn("@media (max-width: 900px)", source)
        self.assertIn("min-height: 50px", source)
        self.assertIn("scroll-snap-type: x proximity", source)

    def test_project_card_keyboard_actions_do_not_bubble_from_delete_button(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn('@keydown.enter.self.prevent="openProject(project.id)"', source)
        self.assertIn('@keydown.space.self.prevent="openProject(project.id)"', source)

    def test_agent_panel_does_not_show_fake_command_input(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertNotIn("输入生产指令", source)
        self.assertNotIn("toon-agent__input", source)
        self.assertIn("来源与预检", source)
        self.assertIn("质量复查", source)
        self.assertIn("运行记录", source)

    def test_asset_cards_wire_existing_asset_actions(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn('(e: "update-media-asset"', source)
        self.assertIn('(e: "delete-media-asset"', source)
        self.assertIn('candidate_status: locked ? "locked" : "candidate"', source)
        self.assertIn('@click="emit(\'update-media-asset\', asset.id, assetLockMeta(true))"', source)
        self.assertIn('@click="emit(\'update-media-asset\', asset.id, assetLockMeta(false))"', source)
        self.assertIn('@click="confirmDeleteMediaAsset(asset.id)"', source)
        self.assertNotIn("<span>设为采用</span>", source)
        self.assertNotIn("<span>取消采用</span>", source)
        self.assertNotIn("<span>删除候选</span>", source)

        self.assertIn('@update-media-asset="updateMediaAsset"', app_source)
        self.assertIn('@delete-media-asset="store.deleteMediaAsset"', app_source)

    def test_production_canvas_wires_video_task_actions(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn('(e: "create-video-task"', source)
        self.assertIn('(e: "delete-video-task"', source)
        self.assertIn("selectedStoryboardTasks", source)
        self.assertIn('@click="emit(\'create-video-task\', selectedStoryboard.id)"', source)
        self.assertIn('@click="confirmDeleteVideoTask(task.id)"', source)
        self.assertIn("任务 #{{ task.id }}", source)
        self.assertNotIn("Track 3 · 视频出片", source)

        self.assertIn('@create-video-task="store.createVideoTask"', app_source)
        self.assertIn('@delete-video-task="store.deleteVideoTask"', app_source)

    def test_production_canvas_wires_preflight_frame_voice_and_storyboard_actions(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        for event_name in [
            "delete-storyboard",
            "generate-character-turnaround",
            "generate-shot-first-frame",
            "generate-storyboard-voice",
            "prepare-video-production",
        ]:
            self.assertIn(f'(e: "{event_name}"', source)

        self.assertIn("执行生产预检", source)
        self.assertIn("生成三视图", source)
        self.assertIn("生成首帧", source)
        self.assertIn("生成旁白", source)
        self.assertIn(":alt=\"`${shotLabel(shot)} 首帧`\"", source)

        for binding in [
            '@delete-storyboard="store.deleteStoryboard"',
            '@generate-character-turnaround="store.generateCharacterTurnaround"',
            '@generate-shot-first-frame="store.generateShotFirstFrame"',
            '@generate-storyboard-voice="store.generateStoryboardVoice"',
            '@prepare-video-production="store.prepareVideoProduction"',
        ]:
            self.assertIn(binding, app_source)

    def test_settings_canvas_wires_project_update(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn('(e: "save-project-settings"', source)
        self.assertIn("projectSettingsPayload()", source)
        self.assertIn("settingsDraft.title", source)
        self.assertIn("settingsDraft.genre", source)
        self.assertIn("settingsDraft.world_brief", source)
        self.assertIn("settingsDraft.writing_rules", source)
        self.assertIn('@submit.prevent="saveProjectSettings()"', source)
        self.assertIn('emit("save-project-settings", payload)', source)

        self.assertIn('@save-project-settings="store.updateProject"', app_source)

    def test_production_canvas_wires_storyboard_shot_review_controls(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        for event_name in [
            "update-storyboard-shot",
            "create-storyboard-shot",
            "delete-storyboard-shot",
            "reorder-storyboard-shots",
        ]:
            self.assertIn(f'(e: "{event_name}"', source)

        for control in ["新增镜头", "保存镜头", "上移镜头", "下移镜头"]:
            self.assertIn(control, source)

        for binding in [
            '@update-storyboard-shot="store.updateStoryboardShot"',
            '@create-storyboard-shot="store.createStoryboardShot"',
            '@delete-storyboard-shot="store.deleteStoryboardShot"',
            '@reorder-storyboard-shots="store.reorderStoryboardShots"',
        ]:
            self.assertIn(binding, app_source)

    def test_video_tasks_surface_progress_failures_and_recovery(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("function taskProgressText", source)
        self.assertIn("function taskProgressPercent", source)
        self.assertIn("function taskFailureText", source)
        self.assertIn('role="progressbar"', source)
        self.assertIn("失败原因", source)
        self.assertIn("重新创建任务", source)
        self.assertIn("task.error_message", source)
        self.assertIn("task.progress.failure_stage", source)

    def test_preflight_and_review_findings_focus_correction_controls(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("function issueShotNo", source)
        self.assertIn("async function focusIssueShot", source)
        self.assertIn('document.querySelector(".toon-shot-editor")?.scrollIntoView', source)
        self.assertIn("preflightFailures", source)
        self.assertIn("preflightWarnings", source)
        self.assertIn("定位镜头", source)
        self.assertIn("recommended_rework_level", source)

    def test_destructive_workbench_actions_require_confirmation(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        for helper in [
            "confirmDeleteProject",
            "confirmDeleteStoryboard",
            "confirmDeleteMediaAsset",
            "confirmDeleteVideoTask",
        ]:
            self.assertIn(f"function {helper}", source)

    def test_project_create_restores_manual_import_and_ai_draft_modes(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("creationMode: CreationMode", source)
        self.assertIn("手动填写", source)
        self.assertIn("导入文本", source)
        self.assertIn("AI 底稿", source)
        self.assertIn('(e: "load-imported-project-draft"', source)
        self.assertIn('(e: "load-ai-project-draft"', source)
        self.assertIn("store.loadImportedProjectDraft", app_source)
        self.assertIn("store.loadAiProjectDraft", app_source)
        self.assertIn(':creation-mode="projectCreationMode"', app_source)

    def test_script_canvas_reconnects_longform_workflows(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        for event_name in [
            "generate-series-plan",
            "run-batch-generation",
            "revise-draft-version",
            "canonicalize-draft-version",
        ]:
            self.assertIn(f'(e: "{event_name}"', source)

        for label in [
            "生成长篇规划",
            "生成正文任务",
            "按反馈生成新版本",
            "定稿最新草稿",
            "visibility: \"private\"",
        ]:
            self.assertIn(label, source)

        for binding in [
            '@generate-series-plan="store.generateSeriesPlan"',
            '@run-batch-generation="store.runBatchGeneration"',
            '@revise-draft-version="store.reviseDraftVersion"',
            '@canonicalize-draft-version="store.canonicalizeDraftVersion"',
        ]:
            self.assertIn(binding, app_source)

    def test_longform_cards_open_readers_and_support_lock_unlock(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")
        app_source = APP_VUE.read_text(encoding="utf-8")

        self.assertIn("DraftReader", source)
        self.assertIn("emit('go', 'planReader')", source)
        self.assertIn("emit('go', 'draftReader')", source)
        self.assertIn('(e: "unlock-series-plan"', source)
        self.assertIn("解锁规划", source)
        self.assertIn("点击卡片查看进度与正文", source)
        self.assertIn("toon-batch-progress", source)
        self.assertIn('@unlock-series-plan="store.unlockSeriesPlan"', app_source)

    def test_agent_panel_surfaces_generation_transparency(self) -> None:
        source = TOONFLOW_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("GenerationTraceStep", source)
        self.assertIn("generationTrace", source)
        self.assertIn("生成透明度", source)
        self.assertIn("最终渲染 Prompt", source)
        self.assertIn("技术参数", source)
        self.assertIn("renderPromptSources", source)
        self.assertIn("compactJson", source)
        self.assertIn("focusTraceSource", source)

    def test_project_create_is_not_restored_as_startup_view(self) -> None:
        app_source = APP_VUE.read_text(encoding="utf-8")
        restorable_block = app_source.split("const restorableViews: ViewKey[] = [", 1)[1].split("];", 1)[0]

        self.assertNotIn('"projectCreate"', restorable_block)
        self.assertNotIn('"setupStage"', restorable_block)
        self.assertNotIn('"novelStage"', restorable_block)
        self.assertNotIn('"videoStage"', restorable_block)
        self.assertIn("window.scrollTo({ top: 0, left: 0, behavior: \"auto\" })", app_source)

    def test_startup_api_failure_is_handled_without_unhandled_rejection(self) -> None:
        store_source = WORKBENCH_STORE.read_text(encoding="utf-8")
        initialize_block = store_source.split("async function initialize() {", 1)[1].split("async function refreshCaptcha()", 1)[0]

        self.assertIn("try {", initialize_block)
        self.assertIn('error.value = err instanceof Error ? err.message : "启动工作台失败。";', initialize_block)
        self.assertNotIn("throw", initialize_block)

    def test_playwright_audit_writes_to_repo_output_directory(self) -> None:
        audit_source = PLAYWRIGHT_AUDIT.read_text(encoding="utf-8")

        self.assertIn('path.resolve("output/playwright-audit")', audit_source)
        self.assertIn('createRequire(new URL("../frontend/package.json", import.meta.url))', audit_source)
        self.assertNotIn("E:/Computer/Wyc_Xc/MVP", audit_source)


if __name__ == "__main__":
    unittest.main()
