import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendTaskCenterContractTests(unittest.TestCase):
    def test_storyboard_import_is_wired_end_to_end(self) -> None:
        api = (ROOT / "frontend/src/api.ts").read_text(encoding="utf-8")
        store = (ROOT / "frontend/src/stores/workbench.ts").read_text(encoding="utf-8")
        app = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        workbench = (ROOT / "frontend/src/components/workspace/ToonflowWorkbench.vue").read_text(encoding="utf-8")

        self.assertIn("/storyboards/import", api)
        self.assertIn("async function importStoryboard", store)
        self.assertIn('@import-storyboard="store.importStoryboard"', app)
        self.assertIn('@create-storyboard="store.createBriefStoryboard"', app)
        self.assertIn("submitStoryboardImport", workbench)
        self.assertIn("导入分镜 JSON", workbench)

    def test_task_center_is_independent_from_production_canvas(self) -> None:
        app = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        workbench = (ROOT / "frontend/src/components/workspace/ToonflowWorkbench.vue").read_text(encoding="utf-8")
        task_center = (ROOT / "frontend/src/components/workspace/TaskCenter.vue").read_text(encoding="utf-8")
        store = (ROOT / "frontend/src/stores/workbench.ts").read_text(encoding="utf-8")

        self.assertIn('module: "tasks"', workbench)
        self.assertIn("<TaskCenter", workbench)
        self.assertIn('@refresh-tasks="store.loadLongformState(activeProject?.project.id)"', app)
        self.assertIn("@refresh=\"emit('refresh-tasks')\"", workbench)
        self.assertIn("pollingFailures", task_center)
        self.assertIn("chapter_tasks", task_center)
        self.assertIn("章节任务", task_center)
        self.assertIn("longformLoadSequence", store)
        self.assertIn("activeProject.value?.project.id !== targetProjectId", store)
        self.assertNotIn("v-if=\"selectedStoryboardTasks.length\" class=\"toon-agent", workbench)


if __name__ == "__main__":
    unittest.main()
