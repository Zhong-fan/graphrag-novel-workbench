# ChenFlow Workbench 开发者说明

ChenFlow Workbench 是一个本地优先的中文小说创作工作台。当前代码聚焦在项目设定、章节创作、长篇规划、正文修订、分镜生成和短片生成。

仓库里仍保留部分 GraphRAG / Neo4j 阶段的文件和文档，用于追溯历史设计；它们已经不是当前主链路的运行前置。

## 技术栈

| 层 | 实现 |
| --- | --- |
| 后端 | FastAPI, SQLAlchemy |
| 前端 | Vue 3, Vite, Pinia |
| 数据库 | MySQL 8 |
| 模型调用 | OpenAI-compatible API |
| 视频生成 | 即梦 AI 3.0 720P 文生视频 + 本地 FFmpeg 拼接 |

## 目录结构

```text
MVP/
  app/                         FastAPI 后端和领域服务
    api.py                     ASGI app、启动钩子、worker 启动
    api_routes*.py             按业务拆分的路由注册
    *_service.py               写作、规划、分镜、视频等领域服务
    batch_generation_worker.py 本地后台 worker
    db.py                      SQLAlchemy engine/session 和手写迁移
    models.py                  ORM 模型
    contracts.py               Pydantic API 契约
    jimeng_video_client.py     火山引擎/即梦签名和异步视频客户端
  frontend/                    Vue 前端
  scripts/                     开发脚本和 smoke 检查
  tests/                       Python 测试
  markdown/                    架构、交接、变更和问题记录
  output/                      本地生成产物，通常不提交
```

## 核心链路

单章创作链路：

```text
项目设定
-> 人物卡 / 长期资料 / 参考资料
-> 章节卡
-> 生成草稿
-> 抽取演化变化
-> 发布作品或追加章节
```

长篇创作链路：

```text
项目设定
-> 视觉风格锁定
-> 生成长篇概要
-> 提交概要反馈
-> 锁定概要 / 章节概要
-> 创建批量正文任务
-> 审阅 / 修订 / 定稿正文
-> 从定稿章节生成分镜
-> 编辑分镜镜头
-> 创建视频任务
```

视频生成链路：

```text
VideoTask queued
-> 本地 worker 消费任务
-> 每个 StoryboardShot 提交到即梦
-> worker 轮询即梦结果
-> 下载每个镜头片段
-> FFmpeg 拼接为 output/video_tasks/{task_id}/final.mp4
-> VideoTask completed
```

如果没有配置即梦 key，后端会回退到旧的本地合成链路：图片生成 + TTS + 字幕文件 + FFmpeg。

## 视觉风格锁定

项目层现在有独立的视觉风格配置，用于约束分镜、角色三视图、镜头图片和视频 prompt。它不是写死某一部作品，而是由用户在项目中填写：

- 画面媒介：例如 `二维动画电影`、`手绘漫画`、`水彩插画`、`写实电影`。
- 作者 / 工作室画风参考：例如 `新海诚画风`、`宫崎骏画风`。
- 正向视觉关键词：例如雨天城市、天空云层、通透光线、手绘背景。
- 禁止项：例如真人、实拍、三次元、照片级写实、文字、水印、logo。
- 补充说明：色彩、光线、构图、角色造型和场景质感。

相关字段保存在 `projects` 表：

```text
visual_style_locked
visual_style_medium
visual_style_artists_json
visual_style_positive_json
visual_style_negative_json
visual_style_notes
```

后端统一通过 `app/visual_style_prompt.py` 生成视觉风格块，再接入：

- `app/storyboard_service.py`：要求分镜 `visual_prompt` 遵守项目级视觉风格。
- `app/video_render_service.py`：即梦文生视频和 fallback 图片生成都使用最终视觉 prompt。
- `app/visual_asset_service.py`：角色三视图使用同一套项目级视觉风格。

前端入口在 `长篇流水线 -> 视觉风格锁定`。如果当前项目参考《天气之子》，应在这里填写类似 `二维动画电影`、`新海诚画风`、雨天城市、天空、通透光线、禁止真人/实拍等约束；其他项目可以填写自己的作者画风和媒介方向。

## 环境要求

- Python 3.11+
- Node.js 20+
- Docker Desktop，或本地 MySQL 8
- FFmpeg 在 `PATH` 中，或通过 `CHENFLOW_FFMPEG_PATH` 指定绝对路径
- 一个 OpenAI-compatible 的文本模型服务
- 可选：火山引擎 AccessKey / SecretKey，用于即梦视频生成

## 环境变量

复制示例配置：

```powershell
Copy-Item .env.example .env
```

后端最小必填配置：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

CHENFLOW_LLM_MODE=openai
CHENFLOW_WRITER_MODEL=gpt-5.5
CHENFLOW_UTILITY_MODEL=gpt-5.4-mini

CHENFLOW_EMBEDDING_MODEL=text-embedding-3-small
CHENFLOW_EMBEDDING_API_KEY=your-api-key
CHENFLOW_EMBEDDING_BASE_URL=https://api.openai.com/v1

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=chenflow_user
MYSQL_PASSWORD=chenflow_password
MYSQL_DATABASE=chenflow_workbench

AUTH_SECRET=replace-this-with-a-long-random-secret
AUTH_EXP_HOURS=168
```

即梦 3.0 720P 视频配置：

```env
JIMENG_ACCESS_KEY=your-volcengine-access-key
JIMENG_SECRET_KEY=your-volcengine-secret-key
JIMENG_VIDEO_REQ_KEY=jimeng_t2v_v30
JIMENG_VIDEO_ASPECT_RATIO=16:9
JIMENG_VIDEO_FRAMES=121
JIMENG_POLL_INTERVAL_SECONDS=10
JIMENG_POLL_TIMEOUT_SECONDS=900
CHENFLOW_FFMPEG_PATH=ffmpeg
```

`JIMENG_VIDEO_FRAMES=121` 表示 5 秒，`241` 表示 10 秒。默认 `jimeng_t2v_v30` 对应即梦 AI 视频生成 3.0 720P 文生视频。

即梦图片 4.0 配置，用于角色三视图、场景参考图、镜头首帧等视觉资产：

```env
JIMENG_IMAGE_REQ_KEY=jimeng_t2i_v40
JIMENG_IMAGE_WIDTH=1024
JIMENG_IMAGE_HEIGHT=1024
```

图片 4.0 使用同一组 `JIMENG_ACCESS_KEY` / `JIMENG_SECRET_KEY` 火山引擎 AK/SK 签名，不走 `CHENFLOW_IMAGE_API_KEY` 的 OpenAI-compatible 调用。

旧本地合成 fallback 配置：

```env
CHENFLOW_IMAGE_API_KEY=
CHENFLOW_IMAGE_BASE_URL=
CHENFLOW_IMAGE_MODEL=
CHENFLOW_IMAGE_SIZE=1024x1024
CHENFLOW_TTS_API_KEY=
CHENFLOW_TTS_BASE_URL=
CHENFLOW_TTS_MODEL=
CHENFLOW_TTS_VOICE=
```

## 本地启动

启动 MySQL：

```powershell
docker compose up -d mysql
```

安装后端依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

安装前端依赖：

```powershell
cd frontend
npm install
cd ..
```

构建前端并启动后端：

```powershell
cd frontend
npm run build
cd ..
python -m app.api
```

后端会把 `frontend/dist` 里的 SPA 挂在 `http://127.0.0.1:8000`。

也可以使用封装脚本：

```text
start-workbench.bat
scripts/start-workbench.ps1
```

## 数据库和迁移

FastAPI 启动时会执行 `app.db.init_db()`，它会创建缺失表，并执行记录在 `schema_migrations` 表里的手写迁移。

当前迁移体系有几个约束：

- ORM 模型在 `app/models.py`。
- 手写迁移函数在 `app/db.py`。
- 还没有接入 Alembic。
- 新增 schema 改动必须保持幂等，因为本地数据库可能已经跑过早期迁移。

手动验证数据库初始化：

```powershell
python -c "from app.db import init_db; init_db(); print('init_db ok')"
```

## 后台 Worker

`app.batch_generation_worker.start_batch_generation_worker()` 会在 FastAPI startup 时启动。它是本地 daemon thread，按顺序消费：

```text
batch_generation_jobs
-> queued storyboards
-> queued video_tasks
```

这是单机 MVP worker，不是分布式队列。当前没有跨进程抢占锁，也不会强行中断正在执行的 LLM、外部 API 或 FFmpeg 调用。

## 视频生成实现

即梦接入相关文件：

- `app/jimeng_video_client.py`
- `app/jimeng_image_client.py`
- `app/video_render_service.py`
- `app/visual_asset_service.py`

客户端调用火山引擎视觉 API：

```text
POST https://visual.volcengineapi.com?Action=CVSync2AsyncSubmitTask&Version=2022-08-31
POST https://visual.volcengineapi.com?Action=CVSync2AsyncGetResult&Version=2022-08-31
```

当前不新增即梦任务表，而是把进度和 provider 元数据写进现有字段：

- `video_tasks.progress_json`
- `task_events.payload_json`
- `media_assets.meta_json`

如果后续接入更多视频供应商，优先抽象 provider 层，再考虑是否增加独立任务表或 provider task 表。

## 常用命令

后端编译检查：

```powershell
python -m compileall app
```

前端生产构建：

```powershell
cd frontend
npm run build
```

前端回归脚本：

```powershell
cd frontend
npm run test:regression
```

长篇流水线 API smoke，需先启动后端：

```powershell
python scripts/longform_pipeline_smoke.py
```

## API 入口

核心接口：

```text
GET  /api/health
GET  /api/bootstrap
GET  /api/me/workspace
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/generate
```

长篇接口：

```text
GET  /api/projects/{project_id}/longform
POST /api/projects/{project_id}/series-plans/generate
POST /api/projects/{project_id}/series-plans/{series_plan_id}/lock
POST /api/projects/{project_id}/batch-generation
POST /api/projects/{project_id}/storyboards
POST /api/projects/{project_id}/storyboards/{storyboard_id}/video-tasks
```

后端启动后可以查看 OpenAPI：

```text
http://127.0.0.1:8000/docs
```

## 开发注意事项

- `.env` 只保留在本地，不要提交真实 provider key。
- Windows 下读取中文文件建议使用 `Get-Content -Encoding UTF8`。
- 生成产物应放在 `output/`、`workspace/` 或其他被忽略的本地目录。
- 优先沿用现有 service 模块扩展功能，避免过早引入新的框架层。
- 外部 provider 的原始响应先放 JSON metadata，等产品契约稳定后再固化字段。

## 当前限制

- worker 是本地线程，不是 Celery / RQ。
- 手写迁移没有 rollback。
- 视频预览和下载体验还比较基础。
- 即梦 720P 目前是逐镜头文生视频；人物三视图、首帧图生视频、角色一致性约束属于下一阶段 provider 层扩展。
- 最终视频拼接仍依赖 FFmpeg。
