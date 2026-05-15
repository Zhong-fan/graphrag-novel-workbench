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
  - 为镜头生成图片、旁白、字幕素材占位。

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

## 已知限制

### 1. 任务仍是同步执行

批量正文生成、分镜生成、视频任务创建目前仍是同步接口。

设计文档建议引入 Redis + Celery / RQ，但当前尚未接入异步任务系统。

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

中途曾跑过：

- `python -m compileall app`
- `npm run build`

当时通过。

后续按要求继续写代码，没有再运行测试或构建。

数据库初始化曾因本机 MySQL `127.0.0.1` 拒绝连接未完成，不是代码层面的验证结果。

## 后续建议

### 第一优先级

1. 跑一次后端编译检查。
2. 跑一次前端构建。
3. 启动 MySQL 后执行 `init_db()`，确认新增表和迁移能落库。
4. 从前端手动走一遍主流程：
   - 生成概要
   - 提交概要反馈
   - 锁定概要
   - 批量生成 1-2 章正文
   - 重写正文版本
   - 定稿章节
   - 生成分镜
   - 创建视频任务

### 第二优先级

1. 引入后台任务系统。
2. 将批量正文生成改成可轮询进度的异步任务。
3. 将分镜生成、素材生成、视频导出改成异步任务。
4. 给 `batch_generation_jobs` 和 `video_tasks` 增加更细的进度事件表。

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

