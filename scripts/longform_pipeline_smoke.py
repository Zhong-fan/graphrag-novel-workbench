from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any


BASE_URL = "http://127.0.0.1:8000"


def _request(method: str, path: str, *, token: str | None = None, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {detail}") from exc


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _solve_captcha(challenge: str) -> str:
    match = re.match(r"^\s*(\d+)\s*([+-])\s*(\d+)\s*=\s*\?\s*$", challenge)
    if not match:
        raise RuntimeError(f"Unsupported captcha challenge: {challenge}")
    left = int(match.group(1))
    right = int(match.group(3))
    return str(left + right if match.group(2) == "+" else left - right)


def _print_step(label: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[longform-smoke] {label}{suffix}", flush=True)


def main() -> None:
    started = int(time.time())
    username = f"longform_smoke_{started}"
    password = "LongformSmoke123"

    _request("GET", "/api/health")

    captcha = _request("GET", "/api/auth/captcha")
    auth = _request(
        "POST",
        "/api/auth/register",
        payload={
            "username": username,
            "password": password,
            "captcha_answer": _solve_captcha(captcha["challenge"]),
            "captcha_token": captcha["token"],
        },
    )
    token = auth["token"]
    _print_step("registered", username)

    project = _request(
        "POST",
        "/api/projects",
        token=token,
        payload={
            "title": f"长篇流水线回归 {started}",
            "genre": "都市异能",
            "reference_work": "",
            "reference_work_creator": "",
            "reference_work_medium": "",
            "reference_work_synopsis": "",
            "reference_work_style_traits": [],
            "reference_work_world_traits": [],
            "reference_work_narrative_constraints": [],
            "reference_work_confidence_note": "",
            "world_brief": "近未来海滨城市里，普通快递员意外获得读取物品记忆的能力，并卷入城市旧案。",
            "writing_rules": "节奏清晰，人物动机明确，每章结尾保留推进下一章的悬念。",
            "style_profile": "cinematic_tense",
        },
    )
    project_id = project["id"]
    _print_step("created project", f"id={project_id}")

    plan = _request(
        "POST",
        f"/api/projects/{project_id}/series-plans/generate",
        token=token,
        payload={
            "target_chapter_count": 3,
            "user_brief": "做 3 章测试规划：发现能力、追查旧案、锁定幕后线索。",
        },
    )
    _assert(len(plan["chapters"]) == 3, "expected 3 chapter outlines")
    _print_step("generated plan", f"plan={plan['id']} chapters={len(plan['chapters'])}")

    feedback = _request(
        "POST",
        f"/api/projects/{project_id}/outline-feedback",
        token=token,
        payload={
            "target_type": "series",
            "target_id": plan["id"],
            "feedback_text": "请强化主角主动追查的动机，并让第三章结尾出现明确的幕后组织代号。",
            "feedback_type": "plot",
            "priority": 4,
        },
    )
    revised_plan = feedback["series_plan"]
    _assert(len(revised_plan["versions"]) >= 2, "expected a new plan version after feedback")
    _print_step("submitted outline feedback", f"versions={len(revised_plan['versions'])}")

    locked = _request("POST", f"/api/projects/{project_id}/series-plans/{plan['id']}/lock", token=token)
    _assert(locked["status"] == "locked", "series plan should be locked")
    _assert(all(chapter["status"] == "outline_locked" for chapter in locked["chapters"]), "all outlines should be locked")
    _print_step("locked plan")

    job = _request(
        "POST",
        f"/api/projects/{project_id}/batch-generation",
        token=token,
        payload={"series_plan_id": plan["id"], "start_chapter_no": 1, "end_chapter_no": 3},
    )
    _assert(job["job_status"] == "completed", f"batch job should complete, got {job['job_status']}")
    _print_step("batch generated drafts", f"job={job['id']}")

    state = _request("GET", f"/api/projects/{project_id}/longform", token=token)
    _assert(len(state["draft_versions"]) >= 3, "expected at least 3 draft versions")
    original_draft = sorted(state["draft_versions"], key=lambda item: item["created_at"])[0]
    _print_step("loaded drafts", f"count={len(state['draft_versions'])}")

    revised_draft = _request(
        "POST",
        f"/api/projects/{project_id}/draft-versions/{original_draft['id']}/revise",
        token=token,
        payload={"feedback_text": "增加开场压迫感，并让主角更早意识到能力代价。"},
    )
    _assert(revised_draft["status"] == "draft_revised", "revised draft should have draft_revised status")
    _print_step("revised draft", f"draft={revised_draft['id']}")

    canonical = _request(
        "POST",
        f"/api/projects/{project_id}/draft-versions/{revised_draft['id']}/canonicalize",
        token=token,
        payload={
            "novel_id": None,
            "author_name": "Smoke Test",
            "visibility": "private",
            "tagline": "长篇流水线回归产物",
        },
    )
    _assert(canonical["status"] == "chapter_canonical", "canonical draft should have chapter_canonical status")
    _print_step("canonicalized draft", f"draft={canonical['id']}")

    project_detail = _request("GET", f"/api/projects/{project_id}", token=token)
    novels = project_detail.get("managed_novels", [])
    _assert(novels, "expected canonicalization to create a managed novel")
    novel_id = novels[0]["id"]
    novel_detail = _request("GET", f"/api/novels/{novel_id}", token=token)
    chapter_ids = [chapter["id"] for chapter in novel_detail["chapters"]]
    _assert(chapter_ids, "expected at least one canonical novel chapter")
    _print_step("loaded canonical chapter", f"novel={novel_id} chapters={len(chapter_ids)}")

    storyboard = _request(
        "POST",
        f"/api/projects/{project_id}/storyboards",
        token=token,
        payload={"novel_chapter_ids": chapter_ids[:1], "title": "回归测试短片"},
    )
    _assert(storyboard["shots"], "expected storyboard shots")
    _print_step("generated storyboard", f"storyboard={storyboard['id']} shots={len(storyboard['shots'])}")

    created = _request(
        "POST",
        f"/api/projects/{project_id}/storyboards/{storyboard['id']}/shots",
        token=token,
        payload={
            "shot_no": 1,
            "narration_text": "城市雨夜里，主角第一次听见旧包裹里的求救声。",
            "visual_prompt": "近未来海滨城市雨夜，快递站冷光，主角握着旧包裹，神情紧张。",
            "character_refs": ["主角"],
            "scene_refs": ["快递站"],
            "duration_seconds": 4,
            "status": "draft",
        },
    )
    first_shot = created["shots"][0]
    updated = _request(
        "PUT",
        f"/api/projects/{project_id}/storyboards/{storyboard['id']}/shots/{first_shot['id']}",
        token=token,
        payload={
            "narration_text": first_shot["narration_text"] + " 他没有后退。",
            "visual_prompt": first_shot["visual_prompt"],
            "character_refs": first_shot["character_refs"],
            "scene_refs": first_shot["scene_refs"],
            "duration_seconds": first_shot["duration_seconds"],
            "status": "locked",
        },
    )
    reordered_ids = [shot["id"] for shot in reversed(updated["shots"])]
    reordered = _request(
        "PUT",
        f"/api/projects/{project_id}/storyboards/{storyboard['id']}/shots/reorder",
        token=token,
        payload={"shot_ids": reordered_ids},
    )
    delete_target = reordered["shots"][-1]["id"]
    after_delete = _request(
        "DELETE",
        f"/api/projects/{project_id}/storyboards/{storyboard['id']}/shots/{delete_target}",
        token=token,
    )
    _assert(len(after_delete["shots"]) == len(reordered["shots"]) - 1, "expected one shot to be deleted")
    _print_step("validated shot CRUD and reorder", f"remaining={len(after_delete['shots'])}")

    task = _request("POST", f"/api/projects/{project_id}/storyboards/{storyboard['id']}/video-tasks", token=token)
    _assert(task["task_status"] == "queued", "video task should be queued")
    _print_step("created video task", f"task={task['id']}")

    state = _request("GET", f"/api/projects/{project_id}/longform", token=token)
    assets = [asset for asset in state["media_assets"] if asset["storyboard_id"] == storyboard["id"]]
    _assert(assets, "expected media asset placeholders")
    asset = assets[0]
    updated_asset = _request(
        "PUT",
        f"/api/projects/{project_id}/media-assets/{asset['id']}",
        token=token,
        payload={
            "uri": f"local://longform-smoke/{asset['id']}",
            "status": "completed",
            "meta": {"checked_by": "longform_pipeline_smoke", "asset_type": asset["asset_type"]},
        },
    )
    _assert(updated_asset["status"] == "completed", "asset should be completed")

    updated_task = _request(
        "PUT",
        f"/api/projects/{project_id}/video-tasks/{task['id']}",
        token=token,
        payload={
            "task_status": "completed",
            "output_uri": f"local://longform-smoke/video-task-{task['id']}.mp4",
            "progress": {"steps": [{"key": "smoke", "status": "completed"}]},
            "error_message": "",
        },
    )
    _assert(updated_task["task_status"] == "completed", "video task should be completed")
    _print_step("updated asset and video task")

    print(
        json.dumps(
            {
                "project_id": project_id,
                "series_plan_id": plan["id"],
                "batch_job_id": job["id"],
                "draft_versions": len(state["draft_versions"]),
                "storyboard_id": storyboard["id"],
                "video_task_id": task["id"],
                "media_assets": len(assets),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    _print_step("passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[longform-smoke] failed: {exc}", file=sys.stderr)
        raise
