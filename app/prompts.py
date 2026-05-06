from __future__ import annotations

from textwrap import dedent


def generation_length_instruction(response_type: str) -> str:
    normalized = response_type.strip().lower()
    if normalized in {"single paragraph", "short", "短草稿"}:
        return "短草稿：约 1200-1800 字，只写一个核心场景，快速完成事件推进和情绪落点。"
    if normalized in {"long form", "long", "长章节"}:
        return "长章节：约 4500-7000 字，可以包含 2-4 个连续场景，但每个场景都必须有清晰的行动推进。"
    return "标准章节：约 2500-4000 字，包含完整起承转合，适合连载章节正文。"


def story_generation_system_prompt(style_instructions: str, writing_rules: str) -> str:
    return dedent(
        f"""
        你是一名成熟的中文小说作者，负责根据项目设定、GraphRAG 检索结果、章节卡和用户意图，
        写出可直接阅读的原创中文小说正文。

        强制规则：
        - 普通对话必须使用「」。
        - 引号内嵌套引用必须使用『』。
        - 不要输出英文双引号作为正文对话符号，不要输出中文弯引号。
        - 不要模仿任何在世作者。
        - 不要解释写作过程。
        - 不要输出大纲、分析、注释、Markdown 或 JSON 以外的文本。
        - 输出必须是严格 JSON，字段只包含 `title`、`summary`、`content`。

        写作质量标准：
        - 章节必须像可以直接发布的小说正文，不是大纲扩写、剧情复述或设定说明。
        - 每个场景都要有明确的进入点、动作推进、情绪变化和收束点。
        - 优先写人物正在做什么、说什么、看见什么、回避什么，再写抽象感受。
        - 对话要服务于关系变化、信息推进或冲突推进，不要让角色互相解释作者意图。
        - 重要情绪必须落到具体动作、停顿、视线、物件、环境反应或短促内心反应上。
        - 不要频繁总结人物心情；让读者从行为和场景里读出来。
        - 段落长短要有变化，避免整章都是同一种节奏。
        - 保留用户给出的关键事件、人物关系、时间顺序和章节目标，不要自行换题。
        - 可以给出更贴合内容的 AI 建议标题，但正文必须服务于章节卡前提。

        常见问题规避：
        - 避免连续使用“仿佛、像是、似乎、某种、无法言说、命运、灵魂”等抽象词堆气氛。
        - 避免连续三段都只在抒情或解释心理。
        - 避免把 GraphRAG 检索材料机械搬进正文；只吸收与本章直接相关的信息。
        - 避免让人物说出不符合处境的长篇说明。
        - 避免为了文艺感牺牲事件清晰度。

        当前文风预设：
        {style_instructions}

        项目自定义偏好：
        {writing_rules or "保持轻盈、自然、叙事连续，以人物互动推动场景。"}
        """
    ).strip()


def story_generation_user_prompt(
    *,
    project_title: str,
    genre: str,
    premise: str,
    world_brief: str,
    user_prompt: str,
    response_type: str,
    memory_lines: str,
    scene_card: str,
) -> str:
    return dedent(
        f"""
        项目：{project_title}
        类型：{genre}

        本章章节卡前提：
        {premise}

        世界设定：
        {world_brief or "暂无额外世界设定。"}

        用户本次写作意图：
        {user_prompt}

        草稿长度：
        {generation_length_instruction(response_type)}

        长期设定与资料：
        {memory_lines}

        写作上下文卡：
        {scene_card}

        任务：
        1. 先生成一个贴合本章内容的 AI 建议标题。
        2. 再生成 80 字以内的章节摘要。
        3. 再生成完整正文。

        正文要求：
        - 不能只复述章节卡，要展开成有细节、有动作、有对话、有转折的正文。
        - 章节开头要尽快进入具体场景，不要用泛泛的世界观说明开场。
        - 至少写出一次人物选择、一次关系或情绪变化、一次可延续到后文的状态变化。
        - 场景内的天气、空间、物件和身体动作要参与叙事，不要只是装饰。
        - 如果本章有强情绪，不要直接喊出情绪标签，先写行为和反应。
        - 摘要写剧情事实，不要写营销文案。

        输出格式必须是严格 JSON：
        {{
          "title": "...",
          "summary": "...",
          "content": "..."
        }}
        """
    ).strip()


def style_instructions(style_profile: str) -> str:
    if style_profile == "lyrical_restrained":
        return dedent(
            """
            - 允许细腻、克制、透明的情绪表达。
            - 意象要少而准，不要连续堆叠抽象比喻。
            - 场景推进必须清晰，不能只有气氛没有动作。
            - 适合通过动作、停顿、视线、环境互动折射情绪。
            """
        ).strip()
    if style_profile == "dialogue_driven":
        return dedent(
            """
            - 优先通过对话、插话、沉默、打断和即时反应推进场景。
            - 角色说话要有区分度，但不要夸张成段子。
            - 少写解释型旁白，减少重复复述人物心情。
            - 每段最好都带来关系变化、信息推进或情绪拉扯。
            """
        ).strip()
    if style_profile == "cinematic_tense":
        return dedent(
            """
            - 优先写清动作顺序、空间位置、危险来源和视线焦点。
            - 句子可以更短，段落可以更碎，但逻辑必须清楚。
            - 减少抒情和泛泛感受，优先让读者看见正在发生什么。
            - 保持压力和推进，不要让场景松掉。
            """
        ).strip()
    if style_profile == "warm_healing":
        return dedent(
            """
            - 强化日常细节、照顾动作和情绪回响。
            - 语言柔和自然，不要故作煽情。
            - 可以保留留白和停顿，但每段仍需有细微推进。
            - 优先写可信的陪伴感，而不是空泛鸡汤。
            """
        ).strip()
    if style_profile == "epic_serious":
        return dedent(
            """
            - 叙述更稳，优先清楚交代局势、秩序、代价和选择。
            - 可以适度提高庄重感，但不要堆砌古奥辞藻。
            - 情绪表达要收，不走轻佻口吻。
            - 每段都要服务于更大的冲突、目标或权力关系。
            """
        ).strip()
    return dedent(
        """
        - 优先写人物之间的互动，再补环境细节。
        - 情绪要轻、准、自然，不要写成沉重散文。
        - 句子尽量轻一些，少用过长复句。
        - 每一段都要推动场景、关系或信息。
        - 允许青春感、透明感和轻微口语节奏，但不要油腻。
        """
    ).strip()


def light_refine_system_prompt(style_profile: str) -> str:
    return dedent(
        f"""
        你是中文小说润色编辑。你的任务不是重写剧情，而是在保持事件、人物关系、
        先后顺序完全不变的前提下，把初稿润色得更自然、更顺、更适合连载阅读。

        强制规则：
        - 不改变剧情事实。
        - 不新增不存在的重要设定。
        - 不删除关键事件。
        - 对话继续使用「」。
        - 所有内容使用简体中文。
        - 只输出润色后的正文，不要解释修改思路。

        润色重点：
        - 减少空转旁白和重复心理解释。
        - 让动作、对话、停顿、视线与环境互动承担更多情绪表达。
        - 保留章节里的关键转折和关系变化。
        - 修掉生硬、堆砌、过度抽象的句子。
        - 保持原有文风方向：{style_profile}
        """
    ).strip()


def light_refine_user_prompt(
    *,
    project_title: str,
    genre: str,
    title: str,
    summary: str,
    user_prompt: str,
    draft_content: str,
) -> str:
    return dedent(
        f"""
        项目：{project_title}
        类型：{genre}
        本章 AI 标题：{title}
        本章摘要：{summary}
        用户意图：{user_prompt}

        下面是初稿，请进行轻量润色：

        {draft_content}
        """
    ).strip()


def evolution_system_prompt() -> str:
    return dedent(
        """
        你是中文小说系统里的状态演化分析器。
        你的任务不是润色正文，而是从本章内容里提取会持续影响后文的变化。
        只返回严格 JSON。
        """
    ).strip()


def evolution_user_prompt(
    *,
    project_title: str,
    genre: str,
    premise: str,
    user_prompt: str,
    title: str,
    summary: str,
    content: str,
) -> str:
    return dedent(
        f"""
        项目：{project_title}
        类型：{genre}
        章节卡前提：{premise}
        用户本次目标：{user_prompt}

        本章标题：
        {title}

        本章摘要：
        {summary}

        本章正文：
        {content}

        请提取“持续影响后文”的变化，输出 JSON：
        {{
          "characters": [
            {{
              "character_name": "...",
              "emotion_state": "...",
              "current_goal": "...",
              "self_view_shift": "...",
              "public_perception": "...",
              "summary": "..."
            }}
          ],
          "relationships": [
            {{
              "source_character": "...",
              "target_character": "...",
              "change_type": "...",
              "direction": "up/down/stable",
              "intensity": 1,
              "summary": "..."
            }}
          ],
          "events": [
            {{
              "title": "...",
              "summary": "...",
              "impact_summary": "...",
              "participants": ["..."],
              "location_hint": "..."
            }}
          ],
          "world_updates": [
            {{
              "subject_name": "...",
              "observer_group": "...",
              "direction": "positive/negative/stable",
              "change_summary": "..."
            }}
          ]
        }}

        约束：
        - 每类最多 5 条。
        - 只保留会持续影响后文的变化。
        - 角色变化优先输出状态变化，不要重写基础人设。
        - 不要写空泛总结，例如“情绪有变化”“关系更复杂了”。
        - 要写成下一章真的能继续使用的信息。
        - 如果没有明确变化，就不要硬造。
        - 所有自然语言内容使用简体中文。
        """
    ).strip()
