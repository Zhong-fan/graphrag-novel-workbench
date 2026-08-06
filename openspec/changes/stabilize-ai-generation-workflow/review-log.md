# Implementation Review Log

每轮实现的 skill 审查记录。审查 skill：`check-code-quality`（错误处理 + 注释契约），计划阶段适用时叠加 `check-simplicity`。

## Round 1 — 能力契约 + 图像适配器边界

- 日期：2026-08-06
- 范围：`app/capabilities.py`、`app/image_capability.py`、`app/visual_asset_service.py` 重构、相关测试
- 审查结果（check-code-quality）：
  - **Error Handling** — `JimengImageAdapter.generate()` 兜底 `except Exception` 会把编程 bug 也标成 `INVALID_PROVIDER_RESPONSE`，掩盖真实故障（与 OpenSpec review 第 9 条一致）。
    - 修复：收窄为 `except RuntimeError`（JimengImageClient 仅用 RuntimeError 表达业务/响应错误），其余异常原样抛出；并加注释说明该契约。
  - **Comments** — 其余模块 docstring 与边界注释合格，无 stale 注释。
- 测试：全量 `python -m unittest discover -s tests` 98 个用例通过。
- 状态：已修复并记录。


## Round 2 — 提示词质量生命周期（注册表 + 校验 + 单次修复）

- 日期：2026-08-06
- 范围：`app/prompt_builders.py`（抽取 storyboard 两个提示词构建器）、`app/prompt_registry.py`（PromptContract + 注册表 + 修复提示词）、`app/prompt_validation.py`（Pydantic 结构化校验）、`app/storyboard_service.py`（接入 builder→LLM→校验→单次修复）、新增 3 个测试文件
- 审查结果（check-code-quality）：
  - **Error Handling** — 校验失败路径明确：初次失败 → 一次定向修复 → 再失败抛出带契约 id 和错误列表的 RuntimeError，无静默吞错；注册表重复/未知 id 均立即抛错；`validate_storyboard_payload` 返回 ValidationResult，把“是否修复”的决策留在服务层，不埋在校验器里。
  - **Comments** — 发现 `_generate_with_contract` 的“每个失败阶段仅一次修复”是规格契约但未注释（contract silence）。
    - 修复：在方法入口补注释标明单次修复边界，防止后续被改成无限重试。
  - 其余 docstring（校验器“先于语义检查”契约、PromptContract、build_repair_prompt）均位于准确边界，无 stale 注释。
- 测试：新增 20 例（registry 4、validation 12、service 修复流程 4）；全量 `python -m unittest discover -s tests` 118 个用例通过。
- 状态：已修复并记录。


## Round 3 — 媒体发布服务（Docker 兼容、过期引用、脱敏记录）

- 日期：2026-08-06
- 范围：`app/media_publication_service.py`（发布/复用/校验/过期重发/checksum）、`app/api_routes_media.py`（`GET /api/media/publications/{token}`）、`app/models.py`（`media_publications` 表）、`app/config.py`（`media_public_base_url`、`media_publication_ttl_seconds`）、`app/video_render_service.py`（首帧 URL 改走发布边界并记录 publication id 作为输入来源）、`.env.example`、新增 2 个测试文件
- 审查结果（check-code-quality）：
  - **Error Handling** — 发布失败路径明确：源文件缺失时落 failed 记录并抛可操作 RuntimeError；`verify` 对 inactive/过期/源文件缺失三种情况都标记过期并抛出带原因错误；`_provider_asset_url` 先复用未过期发布，引用失效时最多重发一次，无无限重试；服务路由未知 token 返回 404，失效/过期/源缺失返回 410。已审查接受：`publish` 存在 check-then-hash 的极小竞态窗口，文件若在两次调用间被删除会以原始 OSError 冒泡到任务失败，不会静默。
  - **Comments** — 审查中发现两处契约静默：发布路由的"随机 token + 过期，不要求登录态"访问模型，以及 `_provider_asset_url` 的"最多重发一次"边界。
    - 修复：路由加 docstring 说明 token 访问契约与只存哈希；`_provider_asset_url` 加注释标明单次重发上限。
  - 服务类与 `verify` 的 docstring 准确标记了发布边界和"提交昂贵请求前校验"的契约。
- 测试：新增 14 例（服务 10、API 5 含重复计数、视频渲染接线 1）；全量 `python -m unittest discover -s tests` 132 个用例通过。
- 状态：已修复并记录。真实 provider（Seedance）合同测试留待有沙箱/真实凭据时执行。


## Round 4 — 质量/成本门禁（渲染完成与验收分离 + 预览策略 + 成本确认）

- 日期：2026-08-06
- 范围：`app/cost_estimator.py`（成本估算 + 阈值门禁）、`app/config.py`（`video_cost_confirmation_threshold_usd`、`ark_video_preview_resolution`）、`app/contracts.py`（`CreateVideoTaskRequest.budget_confirmed/preview`）、`app/api_routes_longform.py`（估算持久化 + 超阈值需确认 + 预览分辨率）、`app/video_quality_service.py`（`build_result` 拆分 render_status/status/quality_accepted）、`app/video_render_service.py`（`_video_resolution` 按任务记录提交 + 显式 quality_accepted=False）、`app/ark_seedance_video_client.py`（usage 透传）、`app/api_support_longform.py`（progress 暴露 quality_status）、`.env.example`、相关测试
- 审查结果（check-code-quality）：
  - **Error Handling** — 成本门禁关闭（阈值<=0）和超阈值两条路径都显式返回原因；API 超阈值 409 详情包含估算、镜头数、修复指引（budget_confirmed=true）；`build_result` 无静默通过：未验收的 completed 渲染记为 `requires_review`，失败记为 `failed`；`_video_resolution` 缺省回退到全局配置；Ark usage 透传做了 isinstance 守卫。无吞错点。
  - **Comments** — 新增 docstring 均标记真实契约：成本估算"只是预算提示非计费保证"、门禁阈值语义、`build_result` 的渲染/验收分离；无 stale 注释。
  - 审查发现无需修复项；语义变化（渲染完成≠质量验收）通过显式 `quality_accepted=False` 和 `requires_review` 状态自文档化。
- 测试：新增 cost estimator 5 例、成本门禁 API 4 例；更新质量验收语义 2 例、Ark usage 1 例；全量 `python -m unittest discover -s tests` 141 个用例通过。
- 状态：已记录。预览策略的"低成本静帧校验"复用既有首帧门禁，本次新增可配置预览分辨率并按任务持久化。


## Round 5 — 角色身份版本化（规范身份 + 外观状态 + 镜头绑定 + 尾帧门禁）

- 日期：2026-08-06
- 范围：`app/models.py`（`character_identity_versions`、`character_appearance_versions`）、`app/character_identity_service.py`（确认三视图→不可变身份版本、外观版本序列、镜头身份绑定、绑定读取）、`app/visual_asset_service.py`（三视图锁定时自动创建身份版本）、`app/api_routes_longform.py`（创建视频任务前自动绑定 + 延续镜头身份绑定门禁）、新增 2 个测试文件
- 审查结果（check-code-quality）：
  - **Error Handling** — `approve_turnaround` 对资产类型/完成状态/项目归属/角色匹配逐一校验并抛可操作 RuntimeError；同一三视图重复确认幂等返回既有版本；绑定按角色去重替换不重复累积；延续镜头缺身份绑定在门禁中给出明确失败原因。已审查接受：锁定未完成三视图时跳过身份创建（保持锁定 UI 不中断），缺失身份会在延续镜头门禁处以可操作信息暴露，不静默。
  - **Comments** — 模型 docstring 标记"不可变、只能追加新版本"与"外观不重写规范身份"两个核心契约；服务类与绑定方法 docstring 位于准确边界；无 stale 注释。
- 测试：新增 12 例（身份服务 10、门禁集成 3 含锁定接线与延续镜头放行）；全量 `python -m unittest discover -s tests` 153 个用例通过。
- 状态：已记录。首帧视觉校验（medium/identity-swap）与帧采样留待视觉能力轮；外观版本绑定待视觉校验轮接入。


## Round 6 — Seedream 图像适配器（参考图 content-array 合同 + provider 路由）

- 日期：2026-08-06
- 范围：`app/config.py`（`image_provider`、`ark_image_model`、`ark_image_size`，解析 `CHENFLOW_IMAGE_PROVIDER`/`ARK_IMAGE_MODEL`/`ARK_IMAGE_SIZE`）、`app/image_capability.py`（新增 `ArkSeedreamImageAdapter`：同步 `{base}/images/generations`、参考图走 content 数组 + `role:"reference"`、声明 `supports_reference_images=True` 与 `flags={"reference_contract":"content-array-url-role"}`；工厂在 `image_provider=="ark_seedream"` 时优先路由）、`.env.example`、`tests/test_image_capability.py`（新增 9 例）
- 审查结果（check-code-quality）：
  - **Error Handling** — 失败路径全部显式分类：配置缺失→`CONFIG_OR_AUTH`（缺项点名）；HTTP 4xx/5xx→`_map_http_error` 按状态与 content_policy/safety 文本归类；超时/网络→`_map_network_error`；非法 JSON、缺 data、data 首项非 dict、无 url/b64→`INVALID_PROVIDER_RESPONSE`。无静默吞错，错误经 `AdapterError` 冒泡由调用方决定重试。
  - **Comments** — 审查发现两处契约未在准确边界标注：`_build_payload` 的"顶层 prompt 必须移入 content 数组、图片 URL 用 role reference"的 wire 合同，以及"Ark 只认 size 字符串、request.width/height 仅作 trace 记录不参与 payload"的边界。
    - 修复：在 `_build_payload` 参考图分支与 `generate` 的 parameters 处补注释标明两个契约。
  - 已审查接受：`supported_input_roles=("reference_image",)` 是领域语义角色，wire 层 `role:"reference"` 由 `flags.reference_contract` 声明，两者分层不冲突。
- 测试：新增 9 例（工厂路由、from_settings、declaration 合同、无参考图 prompt payload、参考图 content 数组、403→CONFIG_OR_AUTH、缺配置、缺 data、无 url）；全量 `python -m unittest discover -s tests` 162 个用例通过。
- 状态：已修复并记录。真实 provider 合同测试（真实 ARK_API_KEY 下验证模型名与参考图响应）留待凭据可用时执行。

## Round 7 — 生成证据持久化（generation_attempts + 四处接线 + 脱敏）

- 日期：2026-08-06
- 范围：`app/models.py`（新增 `generation_attempts` 表：stage/status/provider/model/prompt 契约与版本/渲染提示/原始输出/解析输出/校验结果/参数/usage/成本估算/输入资产版本/质量结果/错误分类，只追加不修改）、`app/generation_evidence_service.py`（`GenerationEvidence` + `record_generation_evidence`，JSON 字段经 `sanitize_provider_payload` 脱敏、长文本截断 200k）、`app/storyboard_service.py`（可选 evidence_sink；成功/修复成功/双失败/非 JSON 四条路径都记录）、`app/storyboard_job_service.py`（把 db 包装为 sink 传入）、`app/visual_asset_service.py`（首帧 + 三视图成功/失败记录，`adopted_asset_id` 指向产物）、`app/video_render_service.py`（每镜头成功记录 usage+成本估算；渲染级失败记录）、`app/api_routes_longform.py`（成本门禁 blocked 记录）、新增 3 个测试文件 + 更新 1 个
- 审查结果（check-code-quality）：
  - **Error Handling** — 审查发现 3 处"证据记录可能掩盖主错误"与 1 处漏记失败路径，全部修复：
    - storyboard 非 JSON 响应（`parse_json_object` 抛 RuntimeError）原路径不落证据 → 在 `_request_payload` 捕获并记录 failed 后重抛；`project_id` 显式传入。
    - `visual_asset_service._record_attempt` 在失败路径里再次调用 `_image_capability()`，配置缺失时会二次抛错掩盖原始错误 → 改为 best-effort：declaration 取不到时降级 provider/model 为空，整段记录吞异常（带注释说明遥测不得掩盖生成错误）。
    - `video_render_service._record_video_failure` 同理改为 best-effort 吞记录异常。
    - 成本门禁记录若提交失败会把预期的 409 变成 500 → 记录+commit 包 try/except，失败回滚仍返回 409。
  - **Comments** — 关键契约均有注释：`GenerationAttempt` docstring 标注"只追加、脱敏、截断"；`_record_attempt`/`_record_video_failure`/成本门禁三处 best-effort 语义都在准确边界注释；storyboard `_generate_with_contract` 入口保留"单次修复"契约注释。无 stale 注释。
- 测试：新增 9 例（证据服务 round-trip/脱敏/失败 3、storyboard sink 成功/修复/双失败/非 JSON 4、视觉资产成功/失败 2）；成本门禁测试追加 blocked 断言 1；全量 `python -m unittest discover -s tests` 171 个用例通过。
- 状态：已修复并记录。新表沿用本 change-set 既有的 create_all 模式（同 media_publications/character_identity_versions），显式迁移条目留待验证轮与其余 schema 变更一并补齐。


## Round 8 — 异常收件箱（素材级决策点 + 推荐动作 + 预算/重复失败路由）

- 日期：2026-08-06
- 范围：`app/models.py`（新增 `exception_inbox_items`：item_type/status/severity/title/reason/recommended_action/最多三个选项/证据引用/解决记录，只追加）、`app/exception_inbox_service.py`（幂等创建：item_type+title+evidence 相同则复用 open 条目；列表；resolve/dismiss 只允许 open 迁移）、`app/api_routes_inbox.py`（GET 默认只返回 open、`status=all` 看历史；POST resolve 校验 accepted/dismissed）、`app/api_routes.py` 挂载、两处接线（成本门禁 blocked → budget_approval 高优先级条目并附 generation_attempt_id；分镜重复失败 → repeated_quality_failure 条目附最近失败证据）、新增 2 个测试文件 + 更新 1 个
- 审查结果（check-code-quality）：
  - **Error Handling** — 审查发现 1 处遥测掩盖主错误：`storyboard_job_service` 失败分支里 `create_inbox_item`/`latest_attempt` 查询若抛错，会把分镜 failed 状态挡住不落库 → 改为 best-effort（try/except 吞异常 + 注释说明收件箱路由不得掩盖分镜失败）；成本门禁接线的记录块同样已是 best-effort 并保留预期 409。API 错误路径明确：项目不存在 404、条目不存在 404、resolution 非法 422、非 open 条目 resolve 幂等返回不重复处理。
  - **Comments** — `ExceptionInboxItem` docstring 标注"只追加、不删除、解决/忽略记在行上"；`create_inbox_item` 标注幂等去重键；GET 路由注释"默认只返回待处理条目"；三处 best-effort 语义均有边界注释。无 stale 注释。
- 测试：新增 8 例（服务 4：round-trip/去重/未知条目抛错/选项上限；API 4：列表/解决/非法 resolution/404）；成本门禁测试追加收件箱断言 1；全量 `python -m unittest discover -s tests` 179 个用例通过。
- 状态：已修复并记录。creative_identity/conflicting_constraints 两类已由服务支持，待视觉身份校验轮接入；视频镜头的有界修复路由留待同轮。


## Round 9 — 引导式协调器（确定性生产状态 + 单一推荐下一步 + 默认值解析）

- 日期：2026-08-06
- 范围：`app/workflow_guidance_service.py`（`recommend_next_action`：按上下文包→分镜→门禁→预算→任务状态推导 10 种确定性状态，每种给单一推荐动作+原因+默认值；默认 provider/模型/预览分辨率/提示词契约版本集中解析，不让创作者选）、`app/video_preflight_service.py`（把 `video_quality_gate_failures` 从 api_routes_longform 迁移为独立服务层模块，消除 video_quality→visual_asset→video_render→video_quality 循环依赖；行为不变）、`app/api_routes_longform.py`（新增 `GET /api/projects/{id}/next-action`；两处调用点改用服务层函数）、新增 1 个测试文件 + 更新 2 个引用旧私有函数的测试
- 审查结果（check-code-quality）：
  - **Error Handling** — 引导服务是纯只读推导，无吞错点；项目不存在返回 404；门禁函数迁移保持原行为与可操作失败原因。审查中发现并修复 1 个实现期问题：把门禁放进 `video_quality_service` 会触发循环导入（video_quality→visual_asset→video_render→video_quality），改为独立 `video_preflight_service` 模块并在 docstring 标注该分层原因。
  - **Comments** — `recommend_next_action` docstring 标注"创作者不选 provider/模型/提示词版本，异常才进收件箱"的协调器契约；门禁 docstring 保留"延续镜头必须带 identity_bindings、尾帧不能替代规范身份"契约；状态推导的 reason 均是可操作中文。无 stale 注释。
  - 审查通过，无需额外修复。
- 测试：新增 7 例（无分镜/就绪/首帧门禁阻塞/预算确认/渲染中/待验收/端点）；全量 `python -m unittest discover -s tests` 186 个用例通过。
- 状态：已记录。progressive disclosure 的"专家控制可见性"与自动采纳可逆性依赖前端与版本链，留待后续轮次；真实 provider 合同测试仍待凭据。


## Round 10 — 验证与收尾（文档、环境示例、前端构建、可验证项全部跑通）

- 日期：2026-08-06
- 范围：`README.md`（补齐 Seedream 图片/成本门禁/媒体发布 env 说明；新增"生成证据、异常收件箱与引导"章节；API 入口列表补充 next-action 与收件箱端点）、`.env.example`（核对前几轮已追加的全部新变量：`CHENFLOW_IMAGE_PROVIDER`/`ARK_IMAGE_MODEL`/`ARK_IMAGE_SIZE`/`CHENFLOW_MEDIA_PUBLIC_BASE_URL`/`CHENFLOW_MEDIA_PUBLICATION_TTL_SECONDS`/`CHENFLOW_VIDEO_COST_CONFIRMATION_THRESHOLD_USD`/`ARK_VIDEO_PREVIEW_RESOLUTION`）
- 审查结果（check-code-quality）：
  - **Error Handling** — 本轮为文档/验证轮，无生产代码变更。验证结果如实记录：`python -m unittest discover -s tests` 186 个用例全部通过；`npm run build`（frontend）构建成功（App.vue template check passed + vite build 1.81s）；`python -m compileall app tests` 通过。
  - **Comments** — 文档无 stale 契约；`.env.example` 注释与实现一致（留空走即梦、ark_seedream 需要 ARK_API_KEY、阈值 0 表示不启用等）。
  - 未完成项如实标注（不假装完成）：真实 MySQL 未运行（`init_db` 连接被拒），Docker/数据库连通性、真实 provider 凭据合同测试、OpenSpec CLI 校验均需本机环境具备相应条件后执行。
- 状态：已记录。遗留 `output/ainami-test`（空目录）与 `output/_patch_tmp`（临时补丁脚本）未删除——删除动作依赖已损坏的审批服务，留待用户手工清理。


## Round 11 — 显式 Schema 迁移 + 历史记录可读性（Contracts And Migration 收尾）

- 日期：2026-08-06
- 范围：`app/db.py`（新增 4 个迁移条目：`20260806_0021_media_publication_schema`、`20260806_0022_character_identity_versions_schema`、`20260806_0023_generation_evidence_schema`、`20260806_0024_exception_inbox_schema`；`_create_table_if_missing` 用 ORM metadata 生成方言正确的 DDL，幂等只建缺失表）、`tests/test_schema_migrations.py`（新增 3 例）
- 审查结果（check-code-quality）：
  - **Error Handling** — `_create_table_if_missing` 先 inspect 再建表，幂等无副作用；表名拼错会抛 KeyError 在迁移事务内失败并中止 init_db（fail-fast，不静默）。迁移沿用 `_run_schema_migration` 的事务与 schema_migrations 审计记录。
  - **Comments** — `_create_table_if_missing` docstring 标注幂等契约与"用 ORM metadata 而非手写 DDL"的选型理由；迁移条目 name 描述与表用途一致。无 stale 注释。
  - 已审查接受：历史 provider/model 记录只追加不改写，字符串原样保留（round-trip 断言 provider="jimeng" 原样读回），满足"迁移期间保持历史记录可读"。
- 测试：新增 3 例（迁移创建全部 5 张新表、重复执行幂等、迁移后的 generation_attempts ORM round-trip）；全量 `python -m unittest discover -s tests` 189 个用例通过。
- 状态：已记录。真实 MySQL 上的 init_db 执行留待本机 MySQL/Docker 可用时验证。


## Round 12 — 提示词回归语料 + 防护测试（Prompt Quality 收尾）

- 日期：2026-08-06
- 范围：`app/prompt_regression_corpus.py`（紧凑回归语料：storyboard.shots.v1 与 storyboard.image_first.v1 两个强制场景，含构建输入、golden payload、提示词关键内容 marker）、`tests/test_prompt_regression_corpus.py`（防护测试 3 例）
- 审查结果（check-code-quality）：
  - **Error Handling** — 防护测试对未注册契约用 `get_prompt_contract` 的 RuntimeError 暴露，任何强制场景回归都会让测试失败；无吞错点。语料为纯数据模块，无异常路径。
  - **Comments** — 语料模块 docstring 标注"改动必须保持强制场景全绿"的守卫契约；`test_registry_has_no_unknown_contracts_beyond_corpus` 注释标明"新契约必须先入语料"的边界（防止悄悄新增无法防护的提示词）。无 stale 注释。
  - 审查通过，无需修复。
- 测试：新增 3 例（契约版本锁定、构建+校验+提示词 marker、注册表与语料一一对应）；全量 `python -m unittest discover -s tests` 192 个用例通过。
- 状态：已记录。


## Round 13 — 生成痕迹只读 API（渐进披露后端部分）

- 日期：2026-08-06
- 范围：`app/api_routes_evidence.py`（`GET /api/projects/{project_id}/generation-attempts`：默认最近 50 条、按 stage/status 过滤、limit 上限 200；返回脱敏后的 provider/model/契约版本/校验结果/参数/usage/输入资产版本/成本估算/质量结果）、`app/api_routes.py` 挂载、新增 1 个测试文件
- 审查结果（check-code-quality）：
  - **Error Handling** — limit 由 FastAPI int 校验 + 代码内 1..200 收敛；项目不存在返回 404；`json.loads` 读取的都是本系统写入的合法 JSON。路由 docstring 明确"只读、脱敏、不参与正常流程决策"的渐进披露契约。无吞错点。
  - **Comments** — 无 stale 注释。
  - 审查通过，无需修复。
- 测试：新增 3 例（列表倒序 + 字段暴露、stage/status 过滤、404）；全量 `python -m unittest discover -s tests` 195 个用例通过。
- 状态：已记录。前端把痕迹/专家控制做进工作台的渐进披露仍待接入（后端证据已就绪）。


## Round 14 — Shadow-mode 首帧视觉检查 + 6 类身份回归 fixtures

- 日期：2026-08-06
- 范围：`app/visual_check_service.py`（`VisualCheckService.check_first_frame`：未配置视觉 reporter 时按"未验证"放行不阻塞；配置后确定性判定媒介不匹配/身份漂移/双角色身份互换并产出 blocking/advisory findings；reporter 边界注释明确"图像理解归适配器，服务只翻译报告为阻断结论"）、`app/visual_identity_regression_fixtures.py`（6 类强制场景：anime→live-action 漂移、服装替换、光照变化、侧脸、遮挡、双角色特征互换）、`tests/test_visual_check_service.py`（新增 6 例）
- 审查结果（check-code-quality）：
  - **Error Handling** — `medium_mismatch` 对空媒介不误报；绑定查询有 bound_ids 空集守卫；reporter 异常原样冒泡（视觉适配器失败必须可见，不静默放行）。无吞错点。
  - **Comments** — 模块 docstring 标注 shadow-mode 语义（未验证放行）与 vision-reporter 边界契约；`check_first_frame` 注释标明影子模式行为。无 stale 注释。
  - 审查通过，无需修复。
- 测试：新增 6 例（媒介判定 3、未配置 reporter 不阻塞 1、6 类 fixtures 全量分类 1、语料完整性 1）；全量 `python -m unittest discover -s tests` 201 个用例通过。
- 状态：已记录。分类逻辑与 fixtures 就绪；接入真实视觉适配器并接线到首帧门禁（shadow→blocking）留待有凭据/模型验证时执行。



## Round 15 — Doubao 语音设计 + TTS 2.0 适配器（语音审批与合成分离）

- 日期：2026-08-06
- 范围：`app/capabilities.py`（SpeechSynthesis/VoiceDesign 请求与结果契约）、`app/voice_capability.py`（合成/设计端口 + Doubao TTS 2.0 适配器 + OpenAI 兼容合成适配器 + Doubao 预设音色设计适配器 + 工厂）、`app/voice_design_service.py`（提交/审批/拒绝/门禁）、`app/models.py`（`voice_designs` 表 + `character_cards.voice_design_id`）、`app/db.py`（迁移 0025）、`app/config.py` 与 `.env.example`（`VOLCENGINE_TTS_PRESET_SPEAKERS`）、`app/voice_service.py`（合成改走能力契约 + 审批门禁）。
- 审查结果（check-code-quality）：
  - **Error Handling** — 适配器把 HTTP/网络/空音频/提供方错误码/坏 base64 全部映射为带类别的 `AdapterError`（含脱敏 details）；审查中发现“全空 chunk 会静默返回空音频”“整段 JSON 回退路径未判空”两处静默退化，已修复为 `INVALID_PROVIDER_RESPONSE`；门禁对设计缺失/未审批/已拒绝/跨角色绑定均抛可操作 `RuntimeError`；合成失败仍标记 asset failed 后原样上抛，无吞错。
  - **Comments** — TTS 2.0 分块响应、`X-Api-Model` 注入、预设设计“不伪造克隆”（reference-audio 抛可操作错误）、绑定即门禁、`voice_design_id` 无外键约束原因、`_speech_capability` 不缓存原因均已注释；无 stale 注释。
- 测试：新增 32 例（voice_capability 21、voice_design_service 10、迁移 0025 门禁 1）；全量 `python -m unittest discover -s tests` 233 个用例通过。
- 状态：已记录。真实豆包/火山凭据验证留待环境可用；voice-design 前端接入留待后续。


## Round 16 — 自动采纳可逆性（首帧版本快照 + 身份采纳回退）

- 日期：2026-08-06
- 范围：`app/models.py`（`media_asset_versions` 快照表）、`app/db.py`（迁移 0026）、`app/adoption_revert_service.py`（覆盖前快照/列出版本/恢复资产/回退身份采纳）、`app/character_identity_service.py`（公开 `set_confirmed_version` 回退路径）、`app/visual_asset_service.py`（首帧再生成覆盖前先快照）、`app/api_routes_revert.py`（版本列表/恢复/身份回退三端点）+ `app/api_routes.py` 挂载。
- 审查结果（check-code-quality）：
  - **Error Handling** — 快照跳过未完成/无文件资产（返回 None，注释明确“可无条件调用”）；恢复时版本不存在抛 `LookupError`、快照文件缺失抛 `RuntimeError`，且恢复前先快照当前状态使恢复本身可逆；身份回退对未知/跨角色版本抛可操作 `RuntimeError` 并写 `TaskEvent` 审计；API 对 404/400/409 映射清晰。审查中简化了“空 uri 恢复”的兜底（改为明确报错）。
  - **Comments** — 模块 docstring 说明两类自动采纳（首帧覆盖、三视图锁定）及可逆契约；`restore_asset_version`/`revert_identity_adoption`/`set_confirmed_version` 均标注“不新建版本号”“恢复本身可逆”等边界；接线处注明“快照失败中止写入，避免静默丢失上一版本”。无 stale 注释。
- 测试：新增 8 例（快照+恢复可逆、跳过未完成、未知版本、快照文件缺失、身份回退全链、跨角色拒绝、未知版本拒绝、已是当前 noop）；迁移 0026 覆盖；全量 `python -m unittest discover -s tests` 241 个用例通过。
- 状态：已记录。前端接入（渐进披露里的恢复入口）留待后续。


## Round 17 — 文本传输协议化 + 文本角色集中配置（DeepSeek 兼容保留）

- 日期：2026-08-06
- 范围：`app/llm.py`（`OpenAIResponsesLLM` → `OpenAICompatibleTextLLM`，协议命名 + 中性错误文案 + 旧名别名保留）、8 个文本服务文件（导入/构造改为新类名）、`app/text_capability.py`（`text_model_for_role` 中央角色→模型映射）+ 13 处 `generate(model=...)` 接线、`tests/test_text_capability.py`。
- 审查结果（check-code-quality）：
  - **Error Handling** — `text_model_for_role` 对未知角色抛带角色值的 `AdapterError`；模型缺失时返回空串但由 `_require_first` 启动期必填保证不会进入运行期（docstring 标注该契约）；`llm.py` 仅改名与文案中性化，Responses/Chat Completions 回退、重试、base_url 候选等兼容机制原样保留。
  - **Comments** — 传输类 docstring 明确“协议是 Responses/Chat Completions，提供方是可替换部署默认（如 DeepSeek），非产品不变量”；旧名别名标注 deprecated；角色映射 docstring 说明无硬编码模型名。无 stale 注释。
- 工程判断：只替换 `generate(model=...)` 关键字参数，`"model":` 字典字面量（事件/痕迹元数据）保持直读 settings，避免无意义改动；未做全量服务重构（纯间接层），角色映射收敛为单一可测试函数，后续迁移可整体切换。
- 测试：新增 7 例（角色解析 5、别名与旧构造兼容 2）；全量 `python -m unittest discover -s tests` 248 个用例通过。
- 状态：已记录。


## Round 18 — 前端渐进披露（历史证据折叠面板）

- 日期：2026-08-06
- 范围：`frontend/src/types.ts`（`GenerationAttempt`/`GenerationAttemptList` 类型，对齐后端 `_attempt_out`）、`frontend/src/api.ts`（`listGenerationAttempts`，支持 stage/status/limit 过滤）、`frontend/src/stores/workbench.ts`（证据状态 + `loadGenerationAttempts` 懒加载，同项目只拉一次，切换项目重置，`{ force: true }` 刷新）、`frontend/src/components/workspace/ToonflowWorkbench.vue`（生产监督侧栏新增「历史证据」折叠面板：默认收起、首次展开触发加载、加载/错误/空态、每条证据含阶段/状态/提供方/模型/时间/质量判定/成本/失败原因，可展开参数与用量、校验与输入版本）、`frontend/src/App.vue`（store 接线）。
- 审查结果（check-code-quality）：
  - **Error Handling** — 面板默认收起、懒加载；加载失败显示错误与重试按钮（store 缓存守卫保证错误后重试会重新请求）。审查中发现两处问题并修复：①切换项目时在途请求会把旧项目证据写入新项目面板 → store action 在 await 后校验 `activeProject.project.id` 仍等于请求项目，否则丢弃过期响应；②「刷新」按钮被同项目缓存守卫挡住实际不刷新 → emit 增加可选 `{ force: true }`，刷新按钮强制重新拉取。项目切换时组件关闭面板，下次展开触发新项目懒加载，避免展示旧项目缓存。
  - **Comments** — 为「同项目只懒加载一次、切换重置」「过期响应丢弃」两处非显而易见契约补了边界注释；watch 关闭面板的原因已注释。无 stale 注释。
- 测试：前端无单测基建（仅 build + playwright 回归需运行中服务），以 `npm run build`（check:template + vue-tsc --noEmit 严格检查 + vite build）通过为准；后端证据 API 测试（`tests/test_generation_evidence_api.py`）已覆盖 stage/status 过滤与 404；全量 `python -m unittest discover -s tests` 248 个用例通过。
- 状态：已记录。tasks.md 勾选「渐进披露」条目；Seedance optional video revision、Jimeng/OpenAI 路径移除、真实凭据验证等条目仍留待后续。


## Round 19 — 创作上下文包 UI 接入（生成前校对面板，解除用户实际阻塞）

- 日期：2026-08-06
- 背景：用户在 hsc 账号的「城中村」项目触发 `ContextPackService.require_confirmed` 门禁（"请先完成生成前校对，并确认创作上下文包"），但后端/API/store 早已就绪，前端工作台从未暴露该功能入口 → 本轮补齐 UI，让门禁可被用户实际完成。
- 范围：`frontend/src/components/workspace/ToonflowWorkbench.vue`（编剧模块顶部新增「创作上下文包 · 生成前校对」面板：无包→参考模式+校对补充要求+「生成校对稿/生成并确认」；draft/stale→冲突清单、校对建议、需决策问题（点击选项即写回 user_decisions）、校对待办（可勾选完成/待处理）、「重建校对稿/确认创作上下文包」；confirmed→版本+参考模式+确认时间+「重建并确认」）、`frontend/src/App.vue`（传 `:context-pack` + 绑定 build/rebuild/confirm/decisions/todo 五类事件到 store 既有动作）。
- 审查结果（check-code-quality）：
  - **Error Handling** — 所有操作走 store 既有动作，失败经全局错误提示可见，无吞错；空上下文包时给出解释文案与「生成校对稿 / 生成并直接确认」两个入口，避免用户卡在"找不到入口"。审查中发现一处边界并修复：切换到无上下文包的项目时，上一项目的 user_notes 残留到新项目 → watch 在 pack 为 null 时清空补充要求。
  - **Comments** — 为"上下文包为空（未生成或切换项目）时清空补充要求"补了边界注释；面板语义与后端 `require_confirmed` 门禁一致（确认后后续生成才解锁），参考模式标签与后端枚举一一对应。无 stale 注释。
- 测试：`npm run build`（check:template + vue-tsc --noEmit + vite build）通过；上下文包门禁后端覆盖见既有 tests（series_planning/storyboard/video 系列测试均含 require_confirmed 路径）；全量 `python -m unittest discover -s tests` 248 个用例通过。
- 状态：已记录。用户现在可在编剧模块顶部完成生成前校对并确认后继续生成。


## Round 20 — Playwright 实测并修复「生成前校对」按钮点不到（布局重叠 + Vue 崩溃）

- 日期：2026-08-06
- 背景：用户实测「确认上下文包」按钮点不到，要求用 Playwright 登录实测。审批器故障无法走 Playwright MCP，经用户批准改用 node_repl 驱动本机 Chrome 实测。
- 实测发现并修复两个真实 bug：
  1. **布局重叠导致按钮被盖住**：`.toon-context-panel` 被放进 `.toon-flow`（display:flex + align-items:center）之字形流，`.toon-flow-node--source` 用 `margin-top:-80px` 上移，`elementFromPoint` 确认「01·故事源」节点整体盖住按钮行（节点 y=425.9 起 vs 按钮 y=429-471）→ 结构性修复：把面板移出 `.toon-flow`，外层包 `.toon-script-board`（grid），面板改为普通块级。复测按钮 bbox 无重叠、点击成功。
  2. **校对稿状态下 Vue 崩溃空白页**：后端 `ContextPackOut` 响应缺 `user_decisions`（as_dict 有但 Pydantic 模型没有该字段，被丢弃），而前端模板 `contextPack.user_decisions[question.question_id]` 直接访问 → TypeError → 整页空白。修复：前端防御 `(contextPack.user_decisions ?? {})[...]`；后端契约 `ContextPackOut` 补 `user_decisions: dict[str,str] = {}`（需重启后端生效）。
- 全链路实测（新账号）：注册（算术验证码自动解）→ 建「测试-城中村」项目 → 生成校对稿 → 审阅冲突清单/建议 → 点决策选项 → 勾校对待办 → 确认创作上下文包（v3 已确认）→ 均无 pageerror、按钮均实际可点。
- 环境提示（非本轮修复范围）：文本 LLM 配置为 `OPENAI_BASE_URL=https://api.deepseek.com` + 模型 `deepseek-v4-pro`（DeepSeek 无此模型名，180s 超时），且 .env 里另有 `GRAPHRAG_CHAT_BASE_URL=http://127.0.0.1:11434/v1` 但 Ollama 未运行 → 「生成长篇规划」会挂起/失败，属凭据/环境问题。
- 测试：`npm run build`（vue-tsc 严格检查）通过；全量 `python -m unittest discover -s tests` 248 个用例通过。
- 状态：已修复并记录。`ContextPackOut.user_decisions` 需重启后端后生效；临时脚本与测试账号（codex_test_638900 / 测试-城中村）留待清理。


## Round 21 — hsc 账号真实登录实测：生成前校对 / 确认创作上下文包全流程通过

- 日期：2026-08-06
- 背景：用户提供 hsc 账号真实密码（[已脱敏]），要求用 Playwright 登录 hsc 账号复测「生成前校对 / 确认创作上下文包」。此前用户反馈：创建「城中村」后被提示"请先完成生成前校对，并确认创作上下文包"，但找不到该功能入口；Round 20 确认按钮又被布局重叠盖住。
- 实测结果（node_repl 驱动本机 Chrome headless，127.0.0.1:8500，全程无 pageerror）：
  1. 真实登录：用户名 hsc + 密码 [已脱敏] →「登录成功」，进入项目库，无报错。
  2. 打开「城中村」（project 16）：编剧模块顶部「创作上下文包 · 生成前校对 · 未生成」面板可见（Round 19 入口修复生效）。
  3. 可点性验证：elementFromPoint 在「生成校对稿」「生成并确认」按钮中心命中按钮自身 → Round 20 布局修复在 hsc 项目同样生效。
  4. 全链路：生成校对稿（秒出 v1：冲突清单 3 项、校对建议 1 条、决策题、校对待办 2 项）→ 点决策「内容和风格都参考」→「标记完成」x2 →「确认创作上下文包」→「创作上下文包已确认。」（v4 · 混合参考 · 确认于 08/06 10:52）。
  5. 持久化：刷新后重新进入项目，面板保持「已确认 v4」，后端读回一致。
- 后端契约验证：GET /api/projects/16/context-pack 响应仍缺 user_decisions（运行中的后端为 18:23 启动的旧代码，contracts.py 18:41 修复未加载）→ 已停止旧进程，等待重启 `python -m app.api` 加载修复；本轮 UI 实测不受影响（前端已防御处理）。
- 测试：本轮为 UI 实测，无新增单测；前端 dist 已含布局与防御修复（npm run build 通过），后端 248 单测此前全绿。
- 状态：hsc 账号「生成前校对 → 确认创作上下文包」链路已验证可操作、可持久化，用户原始阻塞解除。遗留：后端旧进程已停止、端口 8500 当前未服务，需重启 `python -m app.api` 恢复并加载 user_decisions 契约；临时脚本（_round*、_hsc_token.py、_enc_test.txt）与测试截图留待用户清理（审批器故障无法代删）。

## Round 22 — 独立「长篇规划详情」阅读页 + 生成反馈 + 上下文包/故事源重叠修复

- 日期：2026-08-06
- 背景：用户反馈三点：① 生成的长篇规划看不到详情（此前 UI 只显示「标题 · 章数」，无详情入口）；② 点「生成长篇规划」没有反馈；③「创作上下文包 · 生成前校对」面板与「01 · 故事源」节点仍有重叠。
- 根因：
  1. 规划详情缺失：后端 /api/projects/{id}/longform 返回的 current_version.summary 已含完整主题/核心冲突/弧光/章节数据，但前端只渲染 `${title} · ${count} 章`，无任何详情视图。
  2. 无反馈：store 里 longformRequestState（"正在提交长篇概要生成请求…"）从未在 UI 展示；按钮只静默 disabled；且规划生成期间不轮询，POST 响应慢/丢失时页面一直不刷新（实测：后端规划已生成，前端仍显示"先生成或选择一个长篇规划"）。
  3. 重叠：`.toon-flow-node--source` 用 `margin-top:-80px` 上移，配合 flow `padding-top:52px` 使节点顶部超出 flow 上边缘 28px；`.toon-script-board` gap 仅 18px → 节点刺入上面面板 10px（实测 panelBottom=397 vs nodeTop=387）。
- 改动：
  1. 新增 `frontend/src/components/workspace/SeriesPlanReader.vue`：全屏独立阅读页（顶栏：返回工作台 + 项目名/规划标题/版本；正文：主题、核心冲突、结局走向、人物弧光、伏笔计划、弧光、章节全文，max-width 860px 阅读列，长文本行高 1.9）。
  2. 工作台 LONGFORM PLAN 卡新增「查看规划详情」按钮 → `go("planReader")`；阅读页以 fixed 全屏层渲染在工作台内（返回不丢 activeModule 状态）；移除此前塞在画布里的内嵌折叠面板及其 computed/CSS。
  3. 反馈：生成长篇规划/生成正文任务按钮在对应 longformRequest 期间显示「生成中…」；长文本面板顶部显示进度状态条（message 改为"正在生成长篇规划…（通常需要 1-3 分钟，请稍候）"）；`generateSeriesPlan` 开始时启动 longform 轮询，轮询停止条件加入 `!longformRequestState.active`（生成期间页面自动刷新出结果）。
  4. 重叠：`.toon-script-board` gap 18px → 40px（节点上刺 28px < gap 40px，留 12px 安全间隙，任意面板高度均不碰撞，保留之字形设计）。
- 验证：`npm run build`（check:template + vue-tsc --noEmit + vite build）通过；Playwright 实测 hsc 登录：编剧模块 0 重叠（1280/1440/1536 视口 × 0/200/500 滚动，panelBottom=397 vs nodeTop=409）；elementFromPoint 命中节点自身；查看规划详情 → 阅读页完整渲染（主题/冲突/弧光/章节）→ 返回工作台模块状态保留；点重新生成规划 → 按钮变「生成中…」+ 状态条出现；全程无 pageerror。
- 遗留：环境问题——文本 LLM（deepseek-v4-pro 不存在 + Ollama 未运行）仍会使真实生成很慢或失败，但 UI 现在有明确进行中与最终错误提示；临时脚本与测试截图留待用户清理（审批器故障无法代删）。

## Round 23 — 「创作上下文包 · 生成前校对」改为默认收起的小条，点击展开

- 日期：2026-08-06
- 背景：用户反馈：上下文包/生成前校对面板默认占用太大，希望做成小按钮，点击展开，平常保持小巧。
- 改动（`frontend/src/components/workspace/ToonflowWorkbench.vue`）：
  1. 面板由 `<section class="toon-context-panel">` 改为 `<details class="toon-context-panel">`：`<summary>` 作为常驻小条（标题「创作上下文包 · 生成前校对」+ 状态徽标（未生成/校对稿/已确认/已过期）+ 版本与参考模式 meta + 旋转箭头），原有空态/校对稿/已确认三套内容整体移入 `.toon-context-body`。
  2. CSS：收起态 `min-height:46px` 的紧凑横条（`display:flex`，隐藏原生 details 箭头，自定义 `›` 箭头展开时旋转 90°）；展开态保留原卡片样式（边框/毛玻璃/内边距）；`.toon-context-body` 接管原 `display:grid; gap:10px; padding:16px`。
  3. 状态信息（未生成/校对稿/已确认 + 版本号）在收起时也可见，无需展开即可了解上下文包状态。
- 验证：`npm run build`（check:template + vue-tsc --noEmit + vite build）通过；Playwright 实测 hsc 项目：收起态 48px 小条（summary 文案「创作上下文包 · 生成前校对 已确认 v4 · 混合参考 ›」），点击展开显示完整内容（确认于 + 重建并确认），再点收起恢复 48px；收起/展开两态与「01 · 故事源」节点均保持 12px 安全间隙（无重叠）；全程无 pageerror。
- 状态：已记录。前端 dist 已重建，刷新页面即可看到。
## Round 24 — 编剧四节点（故事源/创作约束/长篇产物/分镜出口）对齐单行 + 长篇操作面板移出流程

- 日期：2026-08-06
- 背景：用户反馈「1故事源，2创作约束，3长篇产物和4分镜出口」四个节点不在一条线上，乱掉了。
- 根因：
  1. `.toon-flow--script` 内四个节点用 `margin-top:-80px / +80px / -30px` 故意做之字形错开，视觉上不在一条线。
  2. `.toon-flow--script` 是 `flex-wrap:wrap`，4×250px 节点 + 3 个连接符超出容器（1100px）时第 4 个节点换行到第二行，更乱。
  3. LONGFORM PLAN / CHAPTER DRAFT / REVISION / CANONICAL 四个操作卡片（`.toon-longform-panel`）以 `flex:1 0 100%` 塞在 flow 内部，进一步撑破单行布局。
- 改动（`frontend/src/components/workspace/ToonflowWorkbench.vue`）：
  1. 四节点排直线：`.toon-flow--script` 改为 `align-items:stretch; flex-wrap:nowrap`；新增 `.toon-flow--script .toon-flow-node { flex:1 1 0; min-width:0; width:auto }`（等宽弹性）与 `.toon-flow--script .toon-connector { align-self:center; flex:0 0 auto }`（箭头垂直居中）。
  2. 删除之字形 margin：移除 `.toon-flow-node--source{margin-top:-80px}`、`:nth-of-type(2){+80px}`、`:nth-of-type(3){-30px}`。
  3. 长篇操作面板移出流程：`.toon-longform-panel` 移到 flow 之后、`.toon-script-board` 底部，去掉 `flex:1 0 100%`，四列 grid 不变，由 script-board 的 40px gap 与流程隔开。
- 验证：
  - `npm run build`（check:template + vue-tsc --noEmit + vite build）通过。
  - Playwright 实测 hsc/城中村（1440 与 1536 视口）：四节点 y 完全一致（317）、等高 283、等宽 215、间距均匀；`flex-wrap:nowrap`、scrollW==clientW 无换行；连接符垂直居中；面板四列卡片在流程下方 40px；横向滚动画布后 04 节点完整可见且 elementFromPoint 命中自身；全程无 pageerror。
- skill 评审：
  - check-simplicity：方案为「去之字形 + 禁换行 + 等宽弹性 + 面板移出流程」四件最小改动，无投机抽象/预留配置，范围正好落在「四节点一行」这一已确认需求。
  - check-code-quality：纯模板/CSS 声明式改动，无错误处理路径、无新增注释；`.toon-flow--script .toon-flow-node` 覆盖依赖特异性与书写顺序（晚于基类 `.toon-flow-node`），与文件既有写法一致；无 stale 注释。
- 状态：已记录。前端 dist 已重建，刷新页面即可看到四节点单行排列。
## Round 25 — 补上「锁定长篇概要」按钮（工作台 + 详情阅读页），接通前后端

- 日期：2026-08-06
- 背景：用户反馈「提示请先锁定长篇概要再批量生成正文，但没看到锁定按钮」。后端 `app/api_routes_longform.py:344` 在 `plan.status != "locked"` 时拒绝批量正文生成（409「请先锁定长篇概要再批量生成正文。」），锁定接口 `POST /series-plans/{id}/lock` 与前端 store `lockSeriesPlan` 早已存在，但 UI 从未暴露入口。
- 改动：
  1. `frontend/src/components/workspace/ToonflowWorkbench.vue`：新增 emit `lock-series-plan`；LONGFORM PLAN 卡在规划存在且未锁定时显示「锁定长篇概要」按钮（`.toon-button--lock`，点击后 toast「概要已锁定。」并刷新状态），已锁定时显示「概要已锁定」徽标；CHAPTER DRAFT 卡未锁定时显示提示「请先锁定长篇概要，再批量生成正文。」并禁用「生成正文任务」按钮，锁定后自动解除禁用。
  2. `frontend/src/components/workspace/SeriesPlanReader.vue`：新增 `lock` emit；顶栏显示「锁定长篇概要」按钮（未锁定）/「已锁定」徽标（已锁定）；`statusLabel` 补 `locked → 已锁定`（此前只映射了 outline_locked）。
  3. `frontend/src/App.vue`：`@lock-series-plan="store.lockSeriesPlan"` 接通 store。
- 验证：
  - `npm run build`（check:template + vue-tsc --noEmit + vite build）通过。
  - Playwright 实测 hsc/城中村：锁定前批量按钮 disabled=true 且显示提示；点击「锁定长篇概要」后 → 按钮变「概要已锁定」徽标、提示消失、批量按钮 disabled=false；详情阅读页顶栏显示「已锁定」；刷新重进项目后徽标与解锁状态保持（后端持久化）；全程无 pageerror。
- skill 评审：
  - check-simplicity：方案只补「按钮 + 事件 + 状态提示」三件最小改动，复用既有 store/api，未新增后端代码或配置层。
  - check-code-quality：锁定动作复用 store 既有错误处理（失败 toast 透出后端 detail）；无新增注释需求；CHAPTER DRAFT 的禁用与后端 409 门禁一致（前端先行提示，后端仍兜底）。
- 说明：实测已在真实 hsc/城中村项目上完成锁定（这是用户下一步批量生成的前置条件）；如需撤销，可通过恢复旧版本（restore 会把 status 重置为 draft）。
- 状态：已记录。前端 dist 已重建，刷新页面即可看到锁定按钮。
## Round 26 — 整体技术审计（audit skill：a11y / 性能 / 主题 / 响应式 / 反模式）

- 日期：2026-08-07
- 背景：用户反馈「问题太多，整体 review 一遍」。按 audit skill 执行 5 维代码级审计（不修复、只记录）。已按 Context Gathering Protocol 使用 `.impeccable.md` 既有设计上下文（创作工作台 / 粉彩玻璃 / 制作画布式 IA）。
- 审计限制：Docker/MySQL/后端未运行（启动 Docker Desktop 的审批被故障审批器拒绝），本轮无法做完整运行时实测；布局数据沿用 Round 24 Playwright 实测（1440 视口 canvas 可视宽 718px），对比度按令牌实际值计算。
- 评分：A11y 2/4、性能 2/4、主题 2/4、响应式 2/4、反模式 3/4 → **11/20（Acceptable，需实质整改）**。P0:0 / P1:4 / P2:6 / P3:4。
- P1 发现：
  1. **画布横向截断**：`.toon-flow/.toon-production-board { min-width:1100px }`、`.toon-script-board { min-width:1100px }` 在 1440 视口下 canvas 仅 718px 可视宽 → 编剧四节点与四个操作卡默认只露出约 1.7 个，须横向滚动且无提示（这正是「乱/看不到」观感的主要来源）。
  2. **对比度不达标（白字粉底）**：`.toon-button--dark`（`--toon-rose` #d2629c 底 + 白字）实测 3.52:1 < 4.5（WCAG 1.4.3），覆盖创建账号/新建项目/确认上下文包/查看规划详情/保存镜头等主 CTA。
  3. **对比度不达标（muted 小字）**：`--toon-ink-muted`（oklch 61% #937b88）用于 .7-.78rem 标签/footer/dt 等，实测 3.87:1 < 4.5。
  4. **分镜行键盘不可达**：`.toon-shot-row` 为 div+@click（无 role/tabindex/键盘处理），纯键盘用户无法打开「编辑镜头」（WCAG 2.1.1）。
- P2 发现：
  5. 触控目标：默认按钮 42px、多处 26-38px（`.toon-asset-card footer button` 32px、`.toon-choice-options button` 34px、`.toon-issue-list button` min-height:0），移动端 <44px。
  6. 项目卡片 `<article tabindex="0">` 可点击但缺 `role="button"`，读屏语义不准。
  7. backdrop-filter 共 87 处（canvas-toolbar sticky + 嵌套面板），滚动时合成层重绘开销。
  8. 两套令牌系统并存：全局 `--rose/--ink`（style.css + styles/*.css）vs 工作台 scoped `--toon-*`；workspace.css 12 个硬编码 hex，旧版 `linear-gradient(135deg, rose-strong…)` 渐变按钮与工作台风格不一致。
  9. AuthModal 提交按钮无显式 `type="submit"`（依赖默认行为，非 bug 但应显式化）。
  10. 焦点环用 `--rose-strong`（红橙 hue 15），与粉色主题不一致。
- P3：`styles/reader-editor.css` 无任何入口引用（死文件）；生产概览「下一步」无故事资料时仍提示"下一步生成或导入分镜"（跳级文案）；`.toon-storyboard-list small { opacity:.66 }` 降对比；无暗色模式（设计明确浅色，仅记录）。
- 正面发现：icon 按钮/搜索/画布均有 aria-label，表单控件用 label 包裹，toast aria-live；api.ts 统一抽取后端 detail + 字段中文映射，store 错误均 toast 透出，轮询有停止条件不泄漏；状态色 tone-good/warn/bad 对比度 ≥5.09 达标；图片 lazy loading；单一粉色强调色 + OKLCH 令牌方向明确。
- 建议整改顺序（按 audit skill 命令映射）：[$adapt] 画布/板面响应式 → [$harden] 对比度+键盘可达 → [$harden] 触控目标 → [$distill] 双主题令牌统一/清理渐变按钮与死 CSS → [$optimize] backdrop-filter 收敛 → [$clarify] 下一步文案 → [$polish] 收尾。
- 状态：已记录。本轮只审计不修复；需要运行时复测时请先启动 `start-workbench.bat`（Docker + 后端）。


## Round 27 — 审计修复落地（对比度 / 键盘可达 / 触控目标 / 文案）

- 日期：2026-08-07
- 范围：按 Round 26 审计的 P1/P2 逐项修复，仅改前端 3 个文件：
  - `frontend/src/components/workspace/ToonflowWorkbench.vue`：
    - 对比度：`--toon-ink-muted` 61%→53%（白底/玻璃底 ≥5.16:1）；`.toon-button--dark`、`.toon-rail button.active`、`.toon-rail__brand`、`.toon-topbar nav button.active`、`.toon-storyboard-list button.active` 背景 `--toon-rose`→`--toon-rose-deep`（白字 3.52→5.24:1）。
    - 焦点环：`--rose-strong`（红橙 hue15）→`--toon-rose-deep`，与粉色主题一致。
    - 键盘可达：项目卡片补 `role="button"`+aria-label；`.toon-shot-row` 补 `role="button" tabindex="0"`+aria-label+Enter/Space 键盘处理（WCAG 2.1.1）。
    - 触控目标：≤900px 下 `.toon-choice-options button`、`.toon-issue-list button`、`.toon-evidence-card button`、`.toon-context-panel article button`、`.toon-storyboard-list button` 补 `min-height:44px`。
    - 文案：无故事资料时「下一步」改为“先补充故事资料与改编要求，再进入后续生成”（消除跳级提示）。
  - `frontend/src/components/workspace/SeriesPlanReader.vue`：muted 令牌 61%→53%；`.plan-reader__lock` 背景 `--toon-rose`→`--toon-rose-deep`。
  - `frontend/src/components/auth/AuthModal.vue`：注册/登录提交按钮显式补 `type="submit"`。
- 评审结果（check-code-quality）：本轮为模板/Aria/CSS 改动，无新增错误处理路径；新增交互均带可访问性契约（role/tabindex/keydown），无静默失败与 stale 注释。评审通过。
- 评审结果（check-simplicity）：每个改动与 Round 26 审计项一一对应，无投机抽象；P1 横向滚动按用户确认（滑动窗口正常）跳过修复。评审通过。
- 构建：`npm run build`（check:template + vue-tsc + vite）通过。
- 状态：已记录。下一步提交并推送 dev-v3。
