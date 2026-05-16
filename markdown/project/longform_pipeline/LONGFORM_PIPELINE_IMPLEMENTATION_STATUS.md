# 长篇规划与视频化流水线实施状态

更新时间：2026-05-16

## 已完成

### 长篇规划

- 已实现长篇概要数据模型：
  - `series_plans`
  - `series_plan_versions`
  - `arc_plans`
  - `chapter_outlines`
  - `outline_feedback_items`
  - `outline_revision_plans`
- 已实现概要生成、反馈修订、版本恢复、锁定、章节概要编辑。
- 前端已有 `长篇流水线` 页面入口，可查看全书概要、阶段概要、章节概要和历史版本。

### 正文生成

- 已实现章节正文版本模型 `draft_versions`。
- 已实现正文初稿生成、全章重写、定稿为正式章节。
- 已将批量正文生成改为 DB-backed 本地 worker 队列：
  - `POST /api/projects/{project_id}/batch-generation` 只创建任务并立即返回。
  - `batch_generation_jobs` 作为主任务表。
  - `batch_generation_chapter_tasks` 记录每章子任务。
  - `task_events` 记录进度事件。
  - worker 固定按章节顺序执行，不并发写正文。
  - 每章成功后立即落 `GenerationRun` 和 `DraftVersion`。
  - 失败章会停在 `failed`，不伪造成功。
  - 支持查询、暂停、恢复、取消、重试。
  - retry 不重跑已有草稿章节。
- 已加 worker 可观测字段：
  - `worker_id`
  - `worker_started_at`
  - `last_heartbeat_at`

### 分镜生成

- 已实现分镜数据模型：
  - `storyboards`
  - `storyboard_shots`
- 已将分镜生成改为 DB-backed 本地 worker 队列：
  - `POST /api/projects/{project_id}/storyboards` 创建 `queued` 分镜任务并立即返回。
  - worker 后台调用分镜模型生成 shots。
  - 分镜任务事件通过 `task_events.storyboard_id` 关联。
  - 分镜模型失败、章节引用失效、没有有效镜头时，任务标记为 `failed`。
  - 不生成空分镜稿。
- 已实现分镜镜头新增、编辑、删除、重排接口和前端操作。

### 视频生产

- 已实现视频任务和素材模型：
  - `media_assets`
  - `video_tasks`
- 已接入视频任务事件：
  - `task_events.video_task_id`
  - 创建视频任务写入 `video_task_queued`
  - 更新视频任务写入 `video_task_{status}`
- 已实现真实视频生产最小闭环：
  - `app/video_render_service.py`
  - 图像生成：OpenAI-compatible `POST {CHENFLOW_IMAGE_BASE_URL}/images/generations`
  - TTS：OpenAI-compatible `POST {CHENFLOW_TTS_BASE_URL}/audio/speech`
  - 本地生成 `.srt` 字幕
  - 调用 FFmpeg 合成镜头片段和最终 `final.mp4`
  - 输出到 `output/video_tasks/{task_id}/`
  - 写回 `media_assets.uri`、`video_tasks.output_uri`、`video_tasks.progress_json`、`task_events`
- 视频任务已进入本地 worker 消费：
  - `queued` -> `running` -> `completed`
  - 配置缺失、API 失败、TTS 失败、FFmpeg 失败时直接 `failed`
  - 不做假成功。
- `.env` 已留空白配置，后续填入即可：
  - `CHENFLOW_IMAGE_API_KEY`
  - `CHENFLOW_IMAGE_BASE_URL`
  - `CHENFLOW_IMAGE_MODEL`
  - `CHENFLOW_IMAGE_SIZE`
  - `CHENFLOW_TTS_API_KEY`
  - `CHENFLOW_TTS_BASE_URL`
  - `CHENFLOW_TTS_MODEL`
  - `CHENFLOW_TTS_VOICE`
  - `CHENFLOW_FFMPEG_PATH`

### 前端

- 已接入长篇流水线主面板：
  - 概要生成、反馈、锁定、版本恢复
  - 批量正文任务创建、状态查看、暂停、恢复、取消、重试
  - 草稿版本查看、重写、定稿
  - 分镜任务创建、状态查看、镜头 CRUD、重排
  - 视频任务创建、状态查看、事件查看
  - 素材状态查看和手动更新
- 前端会轮询活跃任务：
  - 批量正文：`queued`、`retry_queued`、`running`、`pause_requested`、`cancel_requested`
  - 分镜：`queued`、`running`
  - 视频：`queued`、`running`

### 迁移

- 已有手写迁移：
  - `20260515_0005_longform_pipeline_schema`
  - `20260516_0006_longform_batch_queue_schema`
  - `20260516_0007_longform_async_metadata_schema`
- `0007` 用于幂等补齐异步任务新增字段，避免旧环境已执行早期 `0006` 后缺列。

## 已验证

以下是本轮早前已经验证过的内容：

- `python -m compileall app` 通过。
- `npm run build` 通过。
- 新建项目成功。
- 进入长篇流水线成功。
- 生成 3 章长篇概要成功。
- 提交概要反馈并生成新概要版本成功。
- 锁定概要成功。
- 按锁定概要生成第 1 章正文成功。
- 前端可看到 `draft_generated` 草稿版本。

## 尚未验证

以下改动是在“先别测试”的要求之后继续写的，尚未跑 smoke / Playwright / 构建验证：

- 新的 DB-backed 批量正文 worker 完整流程。
- 批量正文第 2-3 章及更多章节的顺序生成。
- 批量正文 pause / resume / cancel / retry。
- 服务重启后 stale `running` 任务恢复。
- 分镜异步 worker 完整流程。
- 分镜失败路径：
  - 章节引用失效
  - 模型失败
  - 无有效镜头
- 视频任务 worker 完整流程。
- 图像生成 API 调用。
- TTS API 调用。
- FFmpeg 合成 MP4。
- 前端对新任务事件和 worker 心跳的实际显示。
- 新迁移 `0006` / `0007` 在真实 MySQL 上执行。

注意：最近一次尝试 `init_db()` 时，本机 MySQL `127.0.0.1` 拒绝连接，因此没有完成数据库迁移验证。

## 尚未完成

### 产品化

- 概要编辑仍是 JSON 文本框，尚未改成字段化表单。
- 章节版本对比尚未实现。
- 分镜拖拽排序尚未实现，目前是按钮上移/下移和接口重排。
- 素材预览尚未实现。
- 视频预览和导出下载尚未实现。
- 任务列表页、历史任务筛选、事件时间线尚未做成完整产品形态。

### 视频生产

- 已有真实视频生成最小闭环，但尚未接入具体图像/TTS 服务的真实配置并跑通。
- 尚未接入 MinIO / S3 等文件存储服务。
- 生成文件目前落本地 `output/video_tasks/{task_id}/`。
- 字幕目前生成 `.srt` 文件，但还没有烧录进视频画面。
- 镜头视频目前是静态图片 + 旁白音频，尚未做真实运镜、转场、背景音乐、字幕样式。

### 后台任务系统

- 当前 worker 是本地线程，适合单机 MVP。
- 尚未接入 Redis + Celery / RQ。
- 尚未做多实例锁、任务抢占锁、分布式心跳。
- 暂停/取消在章节或视频步骤边界生效，不会硬中断正在执行的模型/API/FFmpeg 调用。

### 质量评估

- 尚未实现独立 Evaluator：
  - 是否覆盖用户反馈
  - 是否违背设定
  - 是否与近期演化状态冲突
  - 是否偏离概要

### 正文局部编辑

- 当前正文重写仍是全章重写。
- 尚未支持：
  - 指定段落重写
  - 对话强化
  - 节奏加速 / 放缓
  - 结尾单独重写

### 迁移体系

- 当前仍是手写迁移。
- 尚未接入 Alembic。
- 尚未实现迁移降级。

## 当前主流程目标

```text
项目设定
-> 一键生成长篇概要
-> 用户反馈修订概要
-> 手动微调章节概要
-> 锁定概要
-> 创建批量正文任务
-> worker 顺序生成章节草稿
-> 正文反馈重写
-> 定稿正式章节
-> 创建分镜任务
-> worker 生成分镜
-> 编辑分镜
-> 创建视频任务
-> worker 生成图片、旁白、字幕和 MP4
```

## 下一步建议

1. 启动 MySQL，执行 `init_db()`，确认 `0006` / `0007` 迁移落库。
2. 跑 `python -m compileall app`。
3. 跑 `npm run build`。
4. 跑 API smoke：
   - 生成概要
   - 锁定概要
   - 创建 3 章批量正文任务
   - 等 worker 逐章完成
   - 重写并定稿章节
   - 创建分镜任务
   - 等 worker 完成分镜
5. 填入 `.env` 的图像/TTS/FFmpeg 配置，跑真实视频 smoke。

## 主要改动文件

后端：

- `app/models.py`
- `app/db.py`
- `app/contracts.py`
- `app/api.py`
- `app/api_routes_longform.py`
- `app/api_support_longform.py`
- `app/batch_generation_service.py`
- `app/batch_generation_worker.py`
- `app/storyboard_job_service.py`
- `app/video_render_service.py`
- `app/series_planning_service.py`
- `app/outline_revision_service.py`
- `app/draft_revision_service.py`
- `app/storyboard_service.py`
- `app/media_pipeline_service.py`
- `app/config.py`

前端：

- `frontend/src/App.vue`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/stores/workbench.ts`
- `frontend/src/components/workspace/LongformPipelinePanel.vue`

文档 / 配置：

- `.env`
- `README.md`
- `markdown/project/longform_pipeline/LONGFORM_PIPELINE_IMPLEMENTATION_STATUS.md`
