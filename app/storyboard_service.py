from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import parse_json_object
from .llm import OpenAIResponsesLLM
from .models import NovelChapter, Project
from .visual_style_prompt import build_visual_style_block


class StoryboardService:
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

    def generate_storyboard(
        self,
        *,
        project: Project,
        chapters: list[NovelChapter],
        title: str,
    ) -> dict[str, Any]:
        chapter_text = "\n\n".join(
            f"第 {chapter.chapter_no} 章《{chapter.title}》\n摘要：{chapter.summary}\n正文节选：{chapter.content[:5000]}"
            for chapter in chapters
        )
        system_prompt = dedent(
            """
            你是小说读后短片分镜导演。请把已定稿章节转成图像驱动、轻运镜、旁白配字幕的短片分镜。
            输出必须是严格 JSON，不要输出 Markdown。
            """
        ).strip()
        prompt = f"""
项目：{project.title}
类型：{project.genre}
短片标题：{title}

{build_visual_style_block(project)}

世界设定：
{project.world_brief or "暂无"}

已定稿章节：
{chapter_text}

请输出：
{{
  "title": "...",
  "summary": "短片概述",
  "shots": [
    {{
      "shot_no": 1,
      "narration_text": "旁白/字幕文本",
      "visual_prompt": "画面提示词，包含角色、场景、构图、光线、情绪",
      "character_refs": ["角色名"],
      "scene_refs": ["场景名"],
      "duration_seconds": 4
    }}
  ]
}}

要求：
- 生成 6 到 12 个镜头。
- 每个镜头都能独立转成图片提示词。
- 每个 visual_prompt 必须明确写出画面媒介、美术方向、角色外观、场景、构图、光影和色彩。
- 必须遵守项目级视觉风格锁定；如果用户填写了作者/工作室画风参考，只借鉴可迁移的美术特征，不要复刻原作角色、剧情、专有名词或具体画面。
- 不要改写章节既定事实。
- 旁白简洁，适合短视频字幕。
""".strip()
        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        payload = parse_json_object(response.text)
        if not isinstance(payload.get("shots"), list):
            raise RuntimeError("分镜模型没有返回 shots。")
        return payload
