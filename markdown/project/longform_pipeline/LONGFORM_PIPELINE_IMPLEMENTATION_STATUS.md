# 长篇规划与视频化流水线实施状态

更新时间：2026-05-16

## 已完成

### 1. 后端数据层

已新增长篇规划、正文版本、批量生成、分镜和视频任务相关模型：

- `series_plans`
- `series_plan_versions`
- `arc_plans`
- `chapter_outlines`
- `outline_feedback_items`
- `outline_revision_plans`
- `draft_versions`
- `batch_generation_jobs`
- `storyboards`
- `storyboard_shots`
- `media_assets`
- `video_tasks`

已在 `app/db.py` 中加入手写迁移：`20260515_0005_longform_pipeline_schema`。

### 2. 后端服务层

已新增服务：

- `series_planning_service.py`
  - 一键生成全书概要、阶段概要、章节概要。

- `outline_revision_service.py`
  - 将用户概要反馈解析为结构化修订计划。
  - 基于修订计划生成新的概要版本。

- `batch_generation_service.py`
  - 按锁定章节概要顺序生成正文。
  - 每章生成后写入 `GenerationRun`、`DraftVersion`，并抽取演化状态。

- `draft_revision_service.py`
  - 对章节草稿做基于反馈的全章重写。
  - 生成新的 `DraftVersion`。

- `storyboard_service.py`
  - 从已发布/定稿章节生成读后短片分镜。

- `media_pipeline_service.py`
  - 创建视频导出任务的任务计划。
  - 生成视频任务初始进度结构（步骤、预计时长、状态占位）。

### 3. 后端接口

已新增 `app/api_routes_longform.py` 并挂载到主路由。

已实现接口：

- 长篇状态
  - `GET /api/projects/{project_id}/longform`

- 概要生成与版本
  - `POST /api/projects/{project_id}/series-plans/generate`
  - `POST /api/projects/{project_id}/series-plans/{series_plan_id}/lock`
  - `POST /api/projects/{project_id}/series-plans/{series_plan_id}/versions/{version_id}/restore`

- 概要反馈与编辑
  - `POST /api/projects/{project_id}/outline-feedback`
  - `POST /api/projects/{project_id}/chapter-outlines/lock`
  - `PUT /api/projects/{project_id}/chapter-outlines/{outline_id}`

- 批量正文生成
  - `POST /api/projects/{project_id}/batch-generation`
  - `POST /api/projects/{project_id}/batch-generation/{job_id}/retry`

- 章节正文版本
  - `POST /api/projects/{project_id}/draft-versions/{draft_version_id}/revise`
  - `POST /api/projects/{project_id}/draft-versions/{draft_version_id}/canonicalize`

- 分镜
  - `POST /api/projects/{project_id}/storyboards`
  - `POST /api/projects/{project_id}/storyboards/{storyboard_id}/shots`
  - `PUT /api/projects/{project_id}/storyboards/{storyboard_id}/shots/{shot_id}`
  - `DELETE /api/projects/{project_id}/storyboards/{storyboard_id}/shots/{shot_id}`
  - `PUT /api/projects/{project_id}/storyboards/{storyboard_id}/shots/reorder`

- 视频任务与素材
  - `POST /api/projects/{project_id}/storyboards/{storyboard_id}/video-tasks`
  - `PUT /api/projects/{project_id}/video-tasks/{task_id}`
  - `PUT /api/projects/{project_id}/media-assets/{asset_id}`

### 4. 前端接入

已新增页面入口：

- `长篇流水线`

已新增组件：

- `frontend/src/components/workspace/LongformPipelinePanel.vue`

已接入：

- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/stores/workbench.ts`
- `frontend/src/App.vue`
- `frontend/src/styles/workspace.css`

前端已支持：

- 一键生成小说概要。
- 查看全书概要、阶段概要、章节概要。
- 按全书 / 阶段 / 章节提交概要反馈。
- 查看概要版本并恢复历史版本。
- 手动编辑章节概要 JSON。
- 锁定概要。
- 按章节范围批量生成正文。
- 批量任务失败后重试。
- 查看正文草稿版本。
- 按反馈全章重写正文。
- 将正文版本定稿为正式章节。
- 从已发布章节生成分镜。
- 新增、编辑、删除、重排分镜镜头。
- 创建视频导出任务。
- 查看并更新图片 / 旁白 / 字幕素材状态。
- 更新视频任务状态和输出 URI。

## 当前可用主流程

当前已经形成最小闭环：

```text
项目设定
-> 一键生成长篇概要
-> 用户反馈修订概要
-> 手动微调章节概要
-> 锁定概要
-> 顺序批量生成正文
-> 正文反馈重写
-> 定稿正式章节
-> 选章生成分镜
-> 编辑分镜
-> 创建视频任务
-> 更新素材与导出状态
```

## 本轮修复与验证

### 已修复

- 修复历史数据库兼容问题：
  - 本机历史库的 `projects.indexing_status` 是非空列。
  - 当前 `Project` 模型曾漏掉该字段，导致新建项目 `POST /api/projects` 返回 500。
  - 已在 `app/models.py` 补回 `Project.indexing_status`，默认值为 `stale`。
  - 已在 `app/db.py` 的手写迁移中补齐 `indexing_status` 缺列和空值回填逻辑。

- 修复长篇正文生成的 JSON 输出失败问题：
  - 之前第 1 章批量正文生成失败，接口返回 `写作模型没有返回可解析的 JSON。`
  - 已在 `app/llm.py` 增加 `json_mode` 参数。
  - Chat Completions 请求在 `json_mode=True` 时发送 `response_format: {"type": "json_object"}`。
  - Responses 请求在 `json_mode=True` 时发送对应 JSON 对象输出格式。
  - 已将所有本来就要求 JSON 的模型调用切到严格 JSON 模式：
    - 长篇概要生成。
    - 概要反馈修订。
    - 正文初稿生成。
    - 正文意图覆盖检查。
    - 正文重写。
    - 演化状态抽取。
    - 分镜生成。
    - 项目设定建议 / 参考作品识别。

### 明确保留的行为

- 没有增加兜底。
- 没有增加容错。
- 没有把非 JSON 文本强行包装成成功结果。
- 如果模型仍未返回合法 JSON，系统继续报错并中止当前步骤。
- 润色正文、参考作品写作指导等本来返回纯文本的模型调用没有切换为 JSON 模式。

### 已验证

- 新建项目成功。
- 进入长篇流水线成功。
- 生成 3 章长篇概要成功。
- 提交概要反馈并生成新概要版本成功。
- 锁定概要成功。
- 按锁定概要生成第 1 章正文成功。
- 前端长篇流水线页面可看到 `draft_generated` 草稿版本。

### 本轮新增发现

- 已新增 `scripts/longform_pipeline_smoke.py`，用于从 API 层跑长篇流水线 smoke：
  - 注册临时用户。
  - 新建项目。
  - 生成 3 章概要。
  - 提交概要反馈。
  - 锁定概要。
  - 批量生成正文。
  - 重写、定稿、分镜、分镜 CRUD、视频任务和素材状态更新。
- smoke 实际跑到批量正文生成阶段时暴露当前同步接口问题：
  - `POST /api/projects/{project_id}/batch-generation` 当前会在同一个 HTTP 请求里按章节串行生成。
  - 每章内部会调用初稿生成、润色、意图覆盖检查、演化抽取等多个模型步骤。
  - 3 章同步生成耗时过长，客户端中断后任务可能长时间停留在 `running`。
  - 原 retry 逻辑依赖 `current_chapter_no + 1`，如果第 N 章生成过程中中断，存在跳过第 N 章的风险。
- 已开始修补当前同步实现的两个明显问题：
  - retry 改为查询最早缺失 `DraftVersion` 的章节继续，而不是依赖 `current_chapter_no + 1`。
  - 每章成功后立即更新 `batch_generation_jobs.result_summary_json`，避免只在整批完成后才写入生成摘要。

## 商业化落地决策

### 批量正文生成的目标形态

用户体验上仍保留“批量生成多章”，允许用户一次选择更大的章节范围，例如 1-10、1-20。

技术执行上不再把多章塞进一个同步 HTTP 请求，也不依赖前端循环发起多次单章请求。

正式路线改为后端接管的 DB-backed 顺序任务队列：

```text
用户创建批量任务
-> 后端创建 batch_generation_job
-> 后端为章节范围创建单章任务
-> worker 固定并发 1，按章节顺序执行
-> 每章成功立即落 DraftVersion
-> 每个阶段写进度事件
-> 前端轮询任务状态
```

### 执行约束

- 同一个批量任务内固定并发为 1。
- 必须按章节顺序生成，不并发生成正文。
- 第 N 章成功后才允许进入第 N+1 章。
- 每章是最小可重试单元。
- 失败时停在失败章，已成功章节保留。
- retry 只重试失败章或缺失草稿的章节，不重跑已成功章节。
- 页面刷新、浏览器关闭、客户端断开不应影响后端任务继续执行。
- 服务重启后应能识别 stale `running` 任务，并恢复为可重试状态。

### 建议新增数据结构

保留现有 `batch_generation_jobs` 作为批量任务主表，并新增：

- `batch_generation_chapter_tasks`
  - 记录每一章的任务状态。
  - 字段建议：`job_id`、`chapter_outline_id`、`chapter_no`、`status`、`draft_version_id`、`generation_run_id`、`error_message`、`started_at`、`finished_at`。
- `task_events`
  - 记录任务进度事件。
  - 字段建议：`job_id`、`chapter_task_id`、`event_type`、`message`、`payload_json`、`created_at`。

### 建议接口形态

```text
POST /api/projects/{project_id}/batch-generation
创建任务，立即返回 job_id。

GET /api/projects/{project_id}/batch-generation/{job_id}
查询任务、章节子任务和进度事件。

POST /api/projects/{project_id}/batch-generation/{job_id}/pause
暂停任务。

POST /api/projects/{project_id}/batch-generation/{job_id}/resume
继续任务。

POST /api/projects/{project_id}/batch-generation/{job_id}/retry
从失败章或最早缺失草稿章节继续。

POST /api/projects/{project_id}/batch-generation/{job_id}/cancel
取消任务。
```

### 落地策略

第一版不必立即引入 Redis + Celery / RQ。

建议先实现本地 DB-backed worker：

- 后端启动时拉起一个本地 worker 线程。
- worker 从数据库领取 `queued` 任务。
- 单实例本地部署先固定一个 worker。
- 所有状态、错误和进度都落库。
- 后续需要云部署、多实例或更强可靠性时，再把 worker 替换为 Celery / RQ，不改前端任务接口。

## 尚未完成

### 主流程尚未完整走通

以下步骤还没有在本轮 Playwright 自动测试中跑完：

- 批量生成第 2-3 章正文在同步接口下耗时过长，需先改为后端顺序任务队列。
- 对草稿执行全章重写。
- 将草稿定稿为正式章节。
- 从已定稿章节生成分镜。
- 新增、编辑、删除、重排分镜镜头的完整回归。
- 创建视频任务。
- 更新素材状态和视频任务状态。

### 产品化和工程化尚未完成

- 批量正文生成、分镜生成、视频任务创建仍是同步接口。
- 尚未接入 Redis + Celery / RQ 等后台任务系统。
- 尚未把长耗时任务改成可轮询进度的异步任务。
- 尚未增加更细的任务进度事件表。
- 尚未将概要 JSON 文本框改成字段化编辑表单。
- 尚未实现章节版本对比。
- 尚未实现分镜拖拽排序。
- 尚未实现素材预览、视频预览、导出下载。

### 真实视频生产尚未完成

- 尚未调用图像生成模型。
- 尚未调用 TTS。
- 尚未生成真实字幕文件。
- 尚未调用 FFmpeg 合成 MP4。
- 尚未接入 MinIO / S3 等文件存储服务。

## 已知限制

### 1. 任务仍是同步执行

批量正文生成、分镜生成、视频任务创建目前仍是同步接口。

批量正文生成虽是按章节顺序执行，但当前仍运行在同一个 HTTP 请求内，不适合作为商业化落地形态。

下一步应先把批量正文生成改为 DB-backed 后端顺序任务队列，再考虑分镜生成、素材生成和视频导出的异步化。

### 2. 视频管线仍是占位

当前 `media_assets` 和 `video_tasks` 已有数据结构和状态流转，但还没有真正调用：

- 图像生成模型
- TTS
- 字幕生成器
- FFmpeg
- 文件存储服务

### 3. 正文重写仍是全章重写

当前已支持全章重写，尚未支持：

- 指定段落重写
- 对话强化
- 节奏加速 / 放缓
- 结尾单独重写

### 4. 质量评估仍未独立成闭环

当前有概要修订和正文重写，但还没有单独实现完整 Evaluator：

- 是否覆盖用户反馈
- 是否违背设定
- 是否与近期演化状态冲突
- 是否偏离概要

### 5. 概要编辑使用 JSON 文本框

目前章节概要的手动编辑以 JSON 文本框为主，功能完整但不够产品化。

后续可改成字段化表单。

### 6. 尚未补迁移降级或正式迁移框架

当前项目沿用手写迁移方式，没有引入 Alembic。

## 验证状态

已于 2026-05-16 重新验证：

- `python -m compileall app`
- `npm run build`
- `python -c "from app.db import init_db; init_db(); print('init_db ok')"`
- Playwright 自动测试：
  - 新建项目成功。
  - 进入长篇流水线成功。
  - 生成 3 章长篇概要成功。
  - 提交概要反馈并生成新概要版本成功。
  - 锁定概要成功。
  - 按锁定概要生成第 1 章正文成功。
  - 前端可看到 `draft_generated` 草稿版本。
- `python scripts/longform_pipeline_smoke.py`
  - API smoke 跑到批量正文生成阶段。
  - 验证了注册、新建项目、概要生成、概要反馈和锁定概要。
  - 暴露了同步批量正文生成请求耗时过长、任务状态不够可恢复的问题。

结果：

- 后端编译检查通过。
- 前端构建通过（在 `frontend/` 目录执行）。
- `init_db()` 执行成功，长篇流水线新增表与手写迁移可以落库。
- 长篇生成链路的 JSON 产物调用已启用模型侧严格 JSON 模式；不做兜底或容错，模型未返回合法 JSON 时仍会报错。
- 已修复历史数据库中 `projects.indexing_status` 非空列导致新建项目 500 的兼容问题。

## 后续建议

### 第一优先级

1. 将批量正文生成改成商业化最小任务队列：
   - 新增单章任务表。
   - 新增任务事件表。
   - `POST /batch-generation` 只创建任务并立即返回。
   - 本地 worker 顺序消费章节任务。
   - 前端轮询任务状态和事件。
2. 重新跑 API smoke：
   - 生成 3 章概要。
   - 提交概要反馈。
   - 锁定概要。
   - 创建 3 章或更多章批量任务。
   - 确认 worker 按顺序逐章生成，不并发。
   - 验证失败章 retry 不跳章。
3. 再继续走完下游主流程：
   - 重写正文版本。
   - 定稿章节。
   - 生成分镜。
   - 创建视频任务。

### 第二优先级

1. 将分镜生成、素材生成、视频导出也改成异步任务。
2. 给 `video_tasks` 增加更细的进度事件。
3. 增加任务暂停、恢复、取消。
4. 评估是否从本地 worker 迁移到 Redis + Celery / RQ。

### 第三优先级

1. 接入图像生成。
2. 接入 TTS。
3. 生成字幕文件。
4. 调用 FFmpeg 合成 MP4。
5. 接入 MinIO / S3 存储素材和视频。

### 第四优先级

1. 做字段化概要编辑表单。
2. 做章节版本对比。
3. 做分镜拖拽排序。
4. 做素材预览。
5. 做视频预览与导出下载。

## 主要改动文件

后端：

- `app/models.py`
- `app/db.py`
- `app/contracts.py`
- `app/api_routes.py`
- `app/api_routes_longform.py`
- `app/api_support_longform.py`
- `app/json_utils.py`
- `app/series_planning_service.py`
- `app/outline_revision_service.py`
- `app/batch_generation_service.py`
- `app/draft_revision_service.py`
- `app/storyboard_service.py`
- `app/media_pipeline_service.py`

前端：

- `frontend/src/App.vue`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/stores/workbench.ts`
- `frontend/src/components/workspace/LongformPipelinePanel.vue`
- `frontend/src/styles/workspace.css`
