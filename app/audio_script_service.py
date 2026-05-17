from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import ensure_list, json_dumps, json_loads_object, parse_json_object
from .llm import OpenAIResponsesLLM
from .models import NovelChapter, Project, Storyboard, StoryboardShot


class AudioScriptService:
    def __init__(self, settings: Settings) -> None:
        if settings.llm_mode != "openai" or not settings.openai_api_key:
            raise RuntimeError("当前项目只支持真实模型模式。")
        self.settings = settings
        self.llm = OpenAIResponsesLLM(
            settings.openai_api_key,
            settings.openai_base_url,
            use_system_proxy=settings.openai_use_system_proxy,
            use_responses=settings.llm_use_responses,
            stream_responses=settings.llm_stream_responses,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            retry_max_sleep_seconds=settings.llm_retry_max_sleep_seconds,
        )

    def generate_storyboard_audio_scripts(
        self,
        *,
        project: Project,
        storyboard: Storyboard,
        chapters: list[NovelChapter],
        dialogue_density: str = "normal",
        narration_policy: str = "minimal",
        music_policy: str = "cue_only",
        sound_effect_policy: str = "cue_only",
    ) -> Storyboard:
        shots = sorted(storyboard.shots, key=lambda item: item.shot_no)
        if not shots:
            raise RuntimeError("分镜稿没有镜头，无法生成对白脚本。")
        payload = self._generate_payload(
            project=project,
            storyboard=storyboard,
            chapters=chapters,
            shots=shots,
            dialogue_density=dialogue_density,
            narration_policy=narration_policy,
            music_policy=music_policy,
            sound_effect_policy=sound_effect_policy,
        )
        scripts_by_no = {
            int(item.get("shot_no") or 0): self._normalize_audio_script(project=project, value=item.get("audio_script"))
            for item in ensure_list(payload.get("shots"))
            if isinstance(item, dict)
        }
        for shot in shots:
            existing_meta = json_loads_object(shot.meta_json)
            script_meta = existing_meta.get("audio_script") if isinstance(existing_meta.get("audio_script"), dict) else {}
            if existing_meta.get("audio_script_locked") is True or script_meta.get("audio_script_locked") is True:
                continue
            script = scripts_by_no.get(shot.shot_no)
            if script is None:
                continue
            meta = existing_meta
            meta["audio_script"] = script
            shot.meta_json = json_dumps(meta)
        return storyboard

    def _generate_payload(
        self,
        *,
        project: Project,
        storyboard: Storyboard,
        chapters: list[NovelChapter],
        shots: list[StoryboardShot],
        dialogue_density: str,
        narration_policy: str,
        music_policy: str,
        sound_effect_policy: str,
    ) -> dict[str, Any]:
        chapter_text = "\n\n".join(
            f"第 {chapter.chapter_no} 章《{chapter.title}》\n摘要：{chapter.summary}\n正文：{chapter.content[:7000]}"
            for chapter in chapters
        )
        shot_text = "\n".join(
            f"镜头 {shot.shot_no}：\n画面：{shot.visual_prompt}\n现有字幕/旁白：{shot.narration_text}\n角色：{shot.character_refs_json}\n场景：{shot.scene_refs_json}"
            for shot in shots
        )
        system_prompt = dedent(
            """
            你是小说视频化音频编剧。请基于定稿小说正文和已生成分镜，为每个镜头生成结构化音频脚本。
            输出必须是严格 JSON，不要输出 Markdown。
            """
        ).strip()
        prompt = f"""
项目：{project.title}
类型：{project.genre}
分镜标题：{storyboard.title}

世界设定：
{project.world_brief or "暂无"}

定稿小说正文：
{chapter_text}

现有分镜：
{shot_text}

参数：
- dialogue_density: {dialogue_density}
- narration_policy: {narration_policy}
- music_policy: {music_policy}
- sound_effect_policy: {sound_effect_policy}

请输出：
{{
  "shots": [
    {{
      "shot_no": 1,
      "audio_script": {{
        "dialogues": [
          {{
            "character_name": "角色名",
            "line": "角色会自然说出口的一句对白",
            "emotion": "novel_dialog|soft|sad|angry|hopeful|hesitant",
            "voice_profile": "",
            "start_hint": 0.0,
            "duration_hint": 2.0
          }}
        ],
        "narration": "可选旁白，能不用就留空",
        "subtitle_text": "字幕压缩文本",
        "music_cue": "音乐氛围提示",
        "sound_effects": ["音效提示"]
      }}
    }}
  ]
}}

要求：
- 必须覆盖输入中的每个镜头 shot_no。
- 对白必须由小说正文、人物关系和镜头动作推导，不能让用户手动补齐。
- 不要把大段叙述硬改成台词；没有合适对白时 dialogues 可以为空。
- narration_policy=none 时 narration 必须留空；minimal 时只保留必要信息；cinematic 时可保留电影感旁白。
- music_cue 只描述情绪、配器、节奏和氛围，不要写具体受版权保护的曲名或旋律。
- sound_effects 只写镜头中可听见的环境音、动作音和空间音。
""".strip()
        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        payload = parse_json_object(response.text)
        if not isinstance(payload.get("shots"), list):
            raise RuntimeError("音频脚本模型没有返回 shots。")
        return payload

    def _normalize_audio_script(self, *, project: Project, value: Any) -> dict[str, Any]:
        payload = value if isinstance(value, dict) else {}
        character_name_to_id = {
            character.name.strip().lower(): character.id
            for character in project.character_cards
            if character.deleted_at is None and character.name.strip()
        }
        dialogues = []
        for item in ensure_list(payload.get("dialogues")):
            if not isinstance(item, dict):
                continue
            line = str(item.get("line") or "").strip()
            if not line:
                continue
            character_name = str(item.get("character_name") or "").strip()
            character_card_id = item.get("character_card_id") if isinstance(item.get("character_card_id"), int) else None
            if character_card_id is None and character_name:
                character_card_id = character_name_to_id.get(character_name.lower())
            dialogues.append(
                {
                    "character_name": character_name,
                    "character_card_id": character_card_id,
                    "line": line,
                    "emotion": str(item.get("emotion") or "novel_dialog").strip(),
                    "voice_profile": str(item.get("voice_profile") or "").strip(),
                    "start_hint": item.get("start_hint"),
                    "duration_hint": item.get("duration_hint"),
                }
            )
        return {
            "dialogues": dialogues,
            "narration": str(payload.get("narration") or "").strip(),
            "subtitle_text": str(payload.get("subtitle_text") or "").strip(),
            "music_cue": str(payload.get("music_cue") or "").strip(),
            "sound_effects": [str(item).strip() for item in ensure_list(payload.get("sound_effects")) if str(item).strip()],
        }
