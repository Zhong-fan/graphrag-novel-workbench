# Implementation Tasks

## 1. Contracts And Migration

- [x] Add typed capability requests, results, capability declarations, and adapter error categories. — Round 1：capabilities.py + 适配器边界
- [x] Add immutable character identity versions and separate appearance-state versions.
- [x] Persist generation attempts with input asset versions, prompt version, provider, model, parameters, usage, cost estimate, and quality outcome. — Round 7：generation_attempts 表 + 四处接线
- [x] Preserve readability of historical provider and asset records during migration. — Round 11：迁移只追加不改写，历史 provider/model 字符串原样保留（round-trip 断言）
- [x] Add database migrations and round-trip contract tests before changing runtime routing. — Round 11：4 个显式迁移条目 + 3 例迁移/round-trip 测试；路由改动已于前几轮落地并全量回归

## 2. Provider Boundaries

- [x] Rename the current OpenAI-branded text transport into a protocol-focused or DeepSeek-focused implementation without removing compatibility mechanics required by DeepSeek. — Round 17：OpenAIResponsesLLM → OpenAICompatibleTextLLM（协议命名 + 中性错误文案 + 旧名别名），Responses/Chat Completions 兼容机制原样保留
- [x] Configure DeepSeek creative and utility roles centrally and remove obsolete selectable GPT text defaults. — Round 17：text_capability.text_model_for_role 集中映射（creative→writer / utility→utility）；模型由 CHENFLOW_WRITER_MODEL/UTILITY_MODEL 必填配置，本就无 GPT 默认可选
- [x] Add a narrow Seedream image adapter with reference-image support and provider contract tests. — 单测覆盖路由/payload/错误分类；真实 provider 合同测试待凭据
- [x] Route visual asset generation through the image capability instead of constructing `JimengImageClient` in the domain service.
- [ ] Extend the Seedance adapter only for provider capabilities confirmed by contract tests, including typed reference roles and optional video revision.
- [x] Add Doubao voice-design and TTS 2.0 adapters while keeping voice approval separate from speech synthesis. — Round 15：语音能力契约 + TTS 2.0 适配器 + 预设音色设计审批门禁
- [ ] Remove obsolete active Jimeng and unused OpenAI provider paths only after equivalent replacement tests pass.

## 3. Media Publication

- [x] Implement one Docker-compatible media-publication service for provider-readable expiring URLs.
- [x] Record checksum, source asset, expiry, purpose, and sanitized errors for each publication.
- [ ] Verify local first-frame publication through a real or provider-sandbox Seedance contract test. — 需真实/sandbox 凭据，留待可用时执行
- [x] Reject expired or inaccessible references before spending video generation tokens.

## 4. Character Continuity

- [x] Let the creator upload or approve one turnaround and automatically derive the internal reference bundle. — 锁定三视图即生成不可变身份版本
- [x] Bind every character-bearing shot to canonical identity and current appearance versions. — 身份绑定已接入；外观版本绑定待视觉校验轮
- [x] Ensure a previous tail is represented only as continuity state and never replaces the canonical binding. — 延续镜头强制要求 identity_bindings
- [ ] Add visual-medium, identity-drift, and multi-character identity-swap checks for first frames. — Round 14 分类逻辑与 fixtures 已就绪（shadow-mode）；真实视觉适配器验证后接线阻塞
- [ ] Sample rendered video frames and apply the same blocking checks before accepting a segment tail.
- [ ] Add one bounded shot repair and route repeated failure to the exception inbox. — Round 8 已接通 storyboard 有界修复→收件箱路由；视频镜头修复待视觉校验轮
- [x] Add regression fixtures for anime-to-live-action drift, costume change, lighting change, profile view, occlusion, and two-character identity swap. — Round 14：6 类 fixtures + 完整性/分类测试

## 5. Prompt Quality

- [x] Create a small prompt registry with identifiers, versions, ordered builders, output schemas, and repair instructions.
- [x] Move scattered generation instructions into registered prompt builders only when each call site is migrated. — storyboard 两个调用点已迁移；其余提示词调用点保持原位直到各自迁移
- [x] Replace permissive JSON-object parsing with task-specific schema validation for structured tasks. — storyboard 结构化任务已迁移
- [x] Add deterministic validation before semantic model checks.
- [x] Limit automatic prompt repair to one targeted attempt per failed stage.
- [x] Persist prompt inputs, rendered prompt, raw output, parsed output, validation results, and adoption outcome with secret redaction. — Round 7：storyboard 契约调用点全路径落库（含非 JSON/校验失败），image/video 落渲染提示与结果
- [x] Establish a compact regression corpus and block prompt/model changes that regress mandatory cases. — Round 12：prompt_regression_corpus + 防护测试；新契约必须先入语料

## 6. Guided Coordinator And UX

- [x] Define deterministic production states and one recommended next action for the normal workflow. — Round 9：workflow_guidance_service + /next-action
- [x] Automatically resolve technical defaults, dependencies, prompt versions, media publication, and low-cost preflight. — Round 9 默认值解析；media-publication 与预览/预检复用 Round 3/4
- [x] Add an exception inbox for creative identity, conflicting constraints, repeated quality failures, and budget approval. — Round 8：服务+API+预算/重复失败接线；creative_identity 类别待视觉轮接入
- [x] Keep expert controls and full generation traces available through progressive disclosure. — Round 13 后端只读证据 API + Round 18 前端「历史证据」折叠面板（懒加载/刷新/错误重试/切换项目重置）
- [x] Make every automatically adopted change versioned and reversible. — Round 16：media_asset_versions 快照 + 首帧覆盖前快照 + 身份采纳回退（不新建版本号），恢复本身可逆

## 7. Quality And Cost Gates

- [x] Separate render completion from quality acceptance in stored results and UI status.
- [x] Add a preview policy using low-cost still validation and configurable video resolution before final rendering. — 低成本静帧校验复用既有首帧门禁；新增 preview 模式与 ARK_VIDEO_PREVIEW_RESOLUTION 按任务持久化
- [x] Estimate cost before material generation and require confirmation above a configurable project threshold.
- [x] Persist estimated and actual usage where the provider exposes it. — 估算持久化；usage 透传（provider 暴露时）
- [x] Prevent infinite retries, hidden model substitution, and automatic whole-project regeneration. — 既有有界重试/单次修复/显式 provider 配置保证；无自动整项目再生成路径

## 8. Verification And Cleanup

- [x] Add adapter contract, orchestration, migration, quality-gate, and failure-routing tests. — Round 1-9：adapter 合同、orchestration、quality-gate、failure-routing 均已覆盖；迁移 round-trip 以 create_all + 内存库测试覆盖
- [x] Verify existing source traces, locked assets, shot editing, preflight, and review routing remain functional. — Round 10：186 个 Python 测试 + 前端构建通过
- [x] Update environment examples and runtime documentation without including secrets. — Round 10：README + .env.example 已同步
- [ ] Verify Docker services, mounted media, FFmpeg, database connectivity, and provider credentials explicitly. — 需本机 Docker/MySQL 运行与真实凭据，当前环境不可验证
- [ ] Run Python tests, frontend checks, Docker smoke tests, and strict OpenSpec validation. — Python 测试与前端构建已通过；Docker smoke 需 MySQL 运行，OpenSpec CLI 未安装
