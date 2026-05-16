import json
import json
from textwrap import dedent

from .config import Settings
from .llm import APIHTTPError, APINetworkError, OpenAIResponsesLLM


class ProjectBriefingService:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings
        self.llm = OpenAIResponsesLLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            use_system_proxy=settings.openai_use_system_proxy,
            use_responses=settings.llm_use_responses,
            stream_responses=False,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            retry_max_sleep_seconds=settings.llm_retry_max_sleep_seconds,
        )

    def resolve_reference_work(self, *, query: str, genre: str = "") -> dict:
        system_prompt = dedent(
            """
            你是中文小说创作系统里的参考作品识别助手。
            用户会输入一部作品名，可能不完整、可能有歧义。
            你的任务是基于常识识别用户最可能指向的作品，并提取后续创作可迁移的特征。

            规则：
            - 只返回 JSON。
            - 不要说自己不确定，但要在 `confidence_note` 里说明是否可能存在歧义。
            - 不要输出无关分析。
            - 风格特征、世界特征、叙事约束都要写成短句数组，每组 3 到 5 条。
            - 叙事约束强调“可以借鉴什么”和“不要直接照搬什么”。

            JSON 结构必须是：
            {
              "canonical_title": "...",
              "creator": "...",
              "medium": "...",
              "synopsis": "...",
              "style_traits": ["...", "...", "..."],
              "world_traits": ["...", "...", "..."],
              "narrative_constraints": ["...", "...", "..."],
              "confidence_note": "..."
            }
            """
        ).strip()
        user_prompt = dedent(
            f"""
            识别以下参考作品，并抽取可迁移的创作特征。

            用户输入：{query}
            当前项目题材：{genre or "未指定"}
            """
        ).strip()
        payload = self._generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        return {
            "canonical_title": str(payload.get("canonical_title", query)).strip() or query,
            "creator": str(payload.get("creator", "")).strip(),
            "medium": str(payload.get("medium", "")).strip(),
            "synopsis": str(payload.get("synopsis", "")).strip(),
            "style_traits": self._normalize_list(payload.get("style_traits")),
            "world_traits": self._normalize_list(payload.get("world_traits")),
            "narrative_constraints": self._normalize_list(payload.get("narrative_constraints")),
            "confidence_note": str(payload.get("confidence_note", "")).strip(),
        }

    def suggest(self, *, kind: str, title: str, genre: str, reference_work: str, seed_text: str) -> list[str]:
        reference_payload = self.resolve_reference_work(query=reference_work, genre=genre) if reference_work.strip() else None

        system_prompt = dedent(
            """
            你是中文小说项目设定助手。
            你的任务不是替用户定稿，而是基于用户写下的短句，生成几份“可迁移、可修改、可选择”的参考草案。

            输出要求：
            - 只返回 JSON。
            - JSON 结构必须是 {"suggestions": ["...", "...", "..."]}。
            - 固定返回 3 条建议。
            - 每条建议都必须是完整中文段落。
            - 不要写成大纲或列表，不要加序号，不要加标题。
            - 必须保留用户原意，但要补足规则、边界、冲突点或写法约束。
            - 不要替用户锁死剧情，不要写成不可修改的最终设定。
            """
        ).strip()
        focus_label = "世界观" if kind == "world_brief" else "写作偏好"
        reference_block = self._reference_block(reference_payload)
        user_prompt = dedent(
            f"""
            请为小说项目生成 {focus_label} 参考草案。

            项目信息：
            - 标题：{title or "未命名项目"}
            - 题材：{genre or "未指定"}
            - 参考作品：{reference_work or "无"}
            - 用户原始输入：{seed_text}

            参考作品识别结果：
            {reference_block}

            额外约束：
            - 如果是世界观，要补充长期有效的规则、秩序、资源、禁忌或环境差异。
            - 如果是写作偏好，要补充叙述视角、节奏、篇幅感、禁写项、情绪表达方式或关系推进偏好。
            - 如果提供了参考作品，要尽量借鉴其可迁移特征，但不要照搬角色名、剧情节点或原作设定名词。
            - 每条都要彼此有区分，不要只是同一句话换词。
            """
        ).strip()
        payload = self._generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        suggestions = payload.get("suggestions", []) if isinstance(payload, dict) else []
        normalized = [str(item).strip() for item in suggestions if str(item).strip()]
        if len(normalized) < 3:
            raise RuntimeError("AI 返回的设定参考不足 3 条，请重试。")
        return normalized[:3]

    def _generate_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        try:
            response = self.llm.generate(
                model=self.settings.utility_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
            )
            payload = json.loads(response.text)
        except (RuntimeError, ValueError, TypeError, APIHTTPError, APINetworkError) as exc:
            raise RuntimeError(f"AI 服务暂时不可用：{exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("AI 返回的数据格式不正确。")
        return payload

    def _normalize_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:5]

    def _reference_block(self, payload: dict | None) -> str:
        if not payload:
            return "无"
        parts = [
            f"- 标准作品名：{payload.get('canonical_title', '')}",
            f"- 创作者：{payload.get('creator', '')}",
            f"- 载体：{payload.get('medium', '')}",
            f"- 剧情概况：{payload.get('synopsis', '')}",
            f"- 风格特征：{'；'.join(self._normalize_list(payload.get('style_traits')))}",
            f"- 世界特征：{'；'.join(self._normalize_list(payload.get('world_traits')))}",
            f"- 叙事约束：{'；'.join(self._normalize_list(payload.get('narrative_constraints')))}",
        ]
        note = str(payload.get("confidence_note", "")).strip()
        if note:
            parts.append(f"- 识别说明：{note}")
        return "\n".join(parts)
