# 长篇规划与视频化流水线实施状态

更新时间：2026-05-17

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
- 已接入项目级视觉风格锁定：
  - 分镜生成 prompt 会读取项目视觉风格配置。
  - 每个 `visual_prompt` 被要求写出画面媒介、美术方向、角色、场景、构图、光影和色彩。
  - 作者 / 工作室画风参考只作为用户配置输入，不在代码里写死任何作品或作者。

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
  - 新视频任务默认输出到按项目 / 章节 / 分镜 / 任务分层的目录：
    `output/projects/{project}/chapters/{chapter}/storyboards/{storyboard}/video_tasks/{task_id}/`
  - 写回 `media_assets.uri`、`video_tasks.output_uri`、`video_tasks.progress_json`、`task_events`
- 已接入即梦 AI 视频生成 3.0 720P 文生视频：
  - `app/jimeng_video_client.py`
  - 使用火山引擎 AK/SK 签名调用 `visual.volcengineapi.com`
  - 支持提交、轮询、下载镜头片段。
- 已接入即梦 AI 图片生成 4.0 的基础客户端：
  - `app/jimeng_image_client.py`
  - 使用 `JIMENG_IMAGE_REQ_KEY`，默认 `jimeng_t2i_v40`
  - 支持异步任务轮询。
  - 已修正图片结果返回 `binary_data_base64` 的解析路径。
- 已新增视觉资产服务：
  - `app/visual_asset_service.py`
  - 支持生成 `character_turnaround` 角色三视图资产。
  - 生成结果写入 `media_assets`，并保存到按项目 / 章节 / 角色分层的本地目录。
- 已新增统一视觉 prompt 构造：
  - `app/visual_style_prompt.py`
  - 从 `Project.visual_style_*` 字段生成项目级视觉风格块。
  - `VideoRenderService` 的即梦视频 prompt 和 fallback 图片 prompt 都会叠加视觉风格锁定。
  - 创建视频任务时，待生成镜头图的 `media_assets.prompt` 会保存最终视觉 prompt。
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
- `.env` 已新增或支持以下即梦图片配置：
  - `JIMENG_IMAGE_REQ_KEY`
  - `JIMENG_IMAGE_WIDTH`
  - `JIMENG_IMAGE_HEIGHT`

### 前端

- 已接入长篇流水线主面板：
  - 概要生成、反馈、锁定、版本恢复
  - 批量正文任务创建、状态查看、暂停、恢复、取消、重试
  - 草稿版本查看、重写、定稿
  - 分镜任务创建、状态查看、镜头 CRUD、重排
  - 视频任务创建、状态查看、事件查看
  - 素材状态查看和手动更新
  - 视觉资产区域。
  - 角色三视图生成入口。
  - 本地 `output/` 产物静态预览。
  - 图片 / 视频弹窗预览。
- 已新增 `视觉风格锁定` 区域：
  - 支持编辑画面媒介。
  - 支持填写作者 / 工作室画风参考，如“新海诚画风”“宫崎骏画风”。
  - 支持填写正向视觉关键词、禁止项和补充说明。
  - 保存后写回项目设定，用于后续分镜、图片和视频生成。
- 已弱化长篇面板里的后端工程字段展示：
  - 状态改为中文用户文案。
  - 默认不展示 worker id、原始事件类型和完整长 prompt。
  - 素材 prompt 改为摘要显示。
- 前端会轮询活跃任务：
  - 批量正文：`queued`、`retry_queued`、`running`、`pause_requested`、`cancel_requested`
  - 分镜：`queued`、`running`
  - 视频：`queued`、`running`

### 迁移

- 已有手写迁移：
  - `20260515_0005_longform_pipeline_schema`
  - `20260516_0006_longform_batch_queue_schema`
  - `20260516_0007_longform_async_metadata_schema`
  - `20260517_0008_project_visual_style_fields`
- `0007` 用于幂等补齐异步任务新增字段，避免旧环境已执行早期 `0006` 后缺列。
- `0008` 用于给 `projects` 增加视觉风格锁定字段，并从已有参考作品风格特征回填正向视觉关键词。

## 已验证

以下是本轮早前已经验证过的内容：

- `python -m compileall app` 通过。
- `npm run build` 通过。
- `init_db()` 在本机 MySQL 上通过。
- 即梦视频 3.0 AK/SK 签名、提交、轮询、下载在真实任务上通过。
- 项目 `天气之子` 的单镜头样片已按新目录整理到：
  `output/projects/0006-天气之子/chapters/chapter-001-被遗忘的鸟居/...`
- 后端 `/output` 静态挂载已接入，API 输出会在 `media_assets.meta.public_url` 和 `video_tasks.progress.public_url` 中附带可预览 URL。
- 新建项目成功。
- 进入长篇流水线成功。
- 生成 3 章长篇概要成功。
- 提交概要反馈并生成新概要版本成功。
- 锁定概要成功。
- 按锁定概要生成第 1 章正文成功。
- 前端可看到 `draft_generated` 草稿版本。

本轮视觉风格锁定改动已验证：

- `python -m compileall app` 通过。
- `npm run build` 通过。
- 代码中没有写死《天气之子》或某个作者的分支判断；“新海诚画风 / 宫崎骏画风”等只作为用户可编辑配置。

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
- 即梦图片 4.0 角色三视图接口的前端触发流程。
- `app/visual_asset_service.py` 在修正 base64 解析后的完整生成 / 保存 / 前端预览闭环。
- 新迁移 `0008` 在真实 MySQL 上执行。
- 视觉风格锁定在真实即梦视频任务中的效果。
- TTS API 调用。
- FFmpeg 合成 MP4。
- 前端对新任务事件和 worker 心跳的实际显示。
- 新迁移 `0006` / `0007` 在真实 MySQL 上执行。

注意：当前本机仍未找到 `ffmpeg`，`CHENFLOW_FFMPEG_PATH=ffmpeg` 会导致多镜头拼接失败。单镜头样片曾通过复制片段为 `final.mp4` 临时完成。

## 尚未完成

### 产品化

- 概要编辑仍是 JSON 文本框，尚未改成字段化表单。
- 章节版本对比尚未实现。
- 分镜拖拽排序尚未实现，目前是按钮上移/下移和接口重排。
- 素材预览已有最小弹窗能力，但还不是完整资产库。
- 视频预览已有最小弹窗能力，但还没有下载按钮、版本对比、历史筛选和发布流。
- 任务列表页、历史任务筛选、事件时间线尚未做成完整产品形态。

### 视觉资产

- 已有 `character_turnaround` 生成服务和前端入口。
- 已有项目级视觉风格锁定，作为所有视觉资产和镜头 prompt 的上游约束。
- 尚未完成：
  - 角色视觉设定卡 `character_profile`。
  - 表情表 `character_expression_sheet`。
  - 服装版本 `character_outfit`。
  - 场景资产 `scene_profile` / `scene_ref` / `scene_layout` / `scene_lighting`。
  - 资产锁定 / 替换 / 删除 / 版本历史。
  - 分镜镜头绑定已锁定角色资产。
  - 首帧图生成和确认。

### 视频生产

- 已有真实即梦视频生成最小闭环。
- 尚未接入 MinIO / S3 等文件存储服务。
- 新生成文件已改为项目 / 章节 / 分镜 / 任务分层目录；旧产物仍可能保留在 `output/video_tasks/{task_id}/`。
- 字幕目前生成 `.srt` 文件，但还没有烧录进视频画面。
- 即梦文生视频分支目前只生成纯视频片段，尚未把旁白、字幕、BGM、音效合成进去。
- 本地 fallback 分支可以生成静态图片 + 旁白音频 + 字幕文件 + MP4，但依赖 OpenAI-compatible 图像/TTS 配置和 FFmpeg。
- 尚未接入图生视频；当前仍以文生视频为主。

### 配音 / 音频包装

- 已有最小 TTS 函数 `_generate_voice()`，但只在本地 fallback 分支中使用。
- 即梦视频分支尚未生成旁白音频，也没有把旁白混入即梦视频片段。
- 尚未实现：
  - 旁白任务 `GenerateVoiceTask`。
  - 角色对白和旁白的 voice profile。
  - 配音试听 / 重生成。
  - 字幕与音频时长对齐。
  - FFmpeg 混音、字幕烧录、BGM ducking。
  - 音频资产前端预览。

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
-> 角色三视图 / 场景参考图
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
-> 生成并确认首帧图
-> 创建视频任务
-> worker 生成视频片段
-> 生成旁白 / 字幕 / BGM / 音效
-> FFmpeg 合成最终 MP4
```

## 下一步建议

1. 在 `长篇流水线 -> 视觉风格锁定` 中为项目 6 填好视觉配置：
   - 画面媒介：`二维动画电影`。
   - 作者 / 工作室画风参考：`新海诚画风`。
   - 正向关键词：雨天城市、天空云层、通透光线、手绘背景、青春感、城市反光。
   - 禁止项：真人、实拍、三次元、照片级写实、文字、水印、logo。
2. 安装 FFmpeg，或把 `CHENFLOW_FFMPEG_PATH` 改为 `ffmpeg.exe` 绝对路径。
3. 用前端三视图入口重新生成阳菜三视图，确认不是写实真人，并在 `media_assets.meta.locked=true` 后再进入视频。
4. 为项目 6 第 1 章补场景资产：
   - 医院病房。
   - 医院走廊 / 楼梯间。
   - 医院屋顶。
   - 被遗忘的朱红鸟居。
5. 实现 `shot_first_frame` 生成和前端确认流程。
6. 实现配音包装最小闭环：
   - `POST /api/projects/{project_id}/storyboards/{storyboard_id}/voice-tasks`
   - 每个镜头按 `StoryboardShot.narration_text` 生成 `voice` asset。
   - 前端可试听、重生成。
   - FFmpeg 把即梦视频片段和旁白音频合成。
7. 跑 API smoke 和 Playwright 前端预览检查。

## 主要改动文件

后端：

- `app/models.py`
- `app/db.py`
- `app/contracts.py`
- `app/api.py`
- `app/api_routes_longform.py`
- `app/api_support_longform.py`
- `app/api_mount.py`
- `app/batch_generation_service.py`
- `app/batch_generation_worker.py`
- `app/jimeng_image_client.py`
- `app/jimeng_video_client.py`
- `app/storyboard_job_service.py`
- `app/visual_asset_service.py`
- `app/visual_style_prompt.py`
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
