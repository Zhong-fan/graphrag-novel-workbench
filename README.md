# ChenFlow Workbench

ChenFlow Workbench 是一个本地优先的中文长篇小说与短剧视频创作工作台。当前主链路覆盖项目设定、生成前校对、长篇概要、正文批量生成、章节定稿、分镜、视觉资产、首帧/尾帧连续性和视频任务。

仓库里仍保留部分 GraphRAG / Neo4j 阶段的历史文档，用于追溯早期设计；它们不是当前运行前置。

## 当前能力

- 项目设定、人物卡、参考资料和视觉风格锁定
- Context Pack 生成前校对和确认
- 长篇概要生成、反馈修订和锁定
- 批量正文生成、章节修订和定稿
- 从定稿章节、图片先行、已有图片或自由简报生成分镜
- 角色三视图、镜头首帧、镜头尾帧等视觉资产管理
- 即梦文生视频、首帧图生视频和本地 FFmpeg 后处理
- 分镜镜头连续性门禁：缺少必需首帧或依赖尾帧时阻断视频任务
- 草稿和已发布作品统一阅读/管理入口

## 技术栈

| 层 | 实现 |
| --- | --- |
| 后端 | FastAPI, SQLAlchemy |
| 前端 | Vue 3, Vite, Pinia |
| 数据库 | MySQL 8 |
| 后台任务 | FastAPI startup 本地 worker thread |
| 模型调用 | OpenAI-compatible API |
| 视频生成 | 即梦 AI 视频 / 图片接口，本地 FFmpeg |

## 目录结构

```text
app/                         FastAPI 后端、领域服务、ORM、worker
frontend/                    Vue 前端
tests/                       Python 单元/源码级回归测试
scripts/                     启停脚本和 smoke 检查
docs/                        当前设计和计划文档
markdown/                    历史架构、交接、变更和问题记录
output/                      本地生成产物，通常不提交
```

## 主流程

### 小说流程

```text
项目设定
-> 生成前校对 / Context Pack 确认
-> 视觉风格锁定
-> 生成长篇概要
-> 提交概要反馈
-> 锁定概要和章节概要
-> 创建批量正文任务
-> 审阅、修订、定稿章节
-> 草稿/已发布作品阅读管理
```

### 视频流程

```text
定稿章节或图片来源
-> 生成分镜
-> 准备角色三视图、对白脚本、对白音频
-> 生成或继承镜头首帧
-> 创建视频任务
-> 即梦视频生成或本地 fallback
-> 抽取每个镜头尾帧
-> 后续连续镜头继承上一镜头尾帧
-> 拼接最终视频
```

## 首帧/尾帧连续性规则

分镜镜头的连续性语义放在 `StoryboardShot.meta_json.continuity`：

```json
{
  "shot_type": "new | continuation | camera_move",
  "first_frame_source": "generated | previous_last_frame",
  "requires_i2v": true,
  "depends_on_shot_no": 1
}
```

当前规则：

- `first_frame_source = "generated"`：镜头必须有已完成的 `shot_first_frame` 才能进入图生视频链路。
- `first_frame_source = "previous_last_frame"`：镜头复用依赖镜头的 `shot_last_frame` 作为首帧，不再调用图片生成。
- 每个镜头视频后处理完成后，后端会用 FFmpeg 抽取最后一帧并保存为 `MediaAsset(asset_type="shot_last_frame")`。
- 视频任务创建前会做门禁检查；缺少必需首帧或依赖尾帧时返回 409，并给出具体镜头原因。
- 图片先行和已有图片模式不允许回退到文生视频。

## 环境要求

- Python 3.11+
- Node.js 20+
- Docker Desktop，或本地 MySQL 8
- FFmpeg 在 `PATH` 中，或通过 `CHENFLOW_FFMPEG_PATH` 指定
- 一个 OpenAI-compatible 文本模型服务
- 可选：火山引擎 AccessKey / SecretKey，用于即梦图片和视频生成

## 环境变量

复制本地配置：

```powershell
Copy-Item .env.example .env
```

后端基础配置：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

CHENFLOW_LLM_MODE=openai
CHENFLOW_WRITER_MODEL=gpt-5.5
CHENFLOW_UTILITY_MODEL=gpt-5.4-mini

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=chenflow_user
MYSQL_PASSWORD=chenflow_password
MYSQL_DATABASE=chenflow_workbench

AUTH_SECRET=replace-this-with-a-long-random-secret
AUTH_EXP_HOURS=168
```

Ark Seedance 视频配置：

```env
ARK_API_KEY=your-volcengine-ark-api-key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_VIDEO_MODEL=doubao-seedance-2-0-mini
ARK_VIDEO_RATIO=16:9
ARK_VIDEO_DURATION_SECONDS=5
ARK_VIDEO_RESOLUTION=1080p
ARK_VIDEO_PREVIEW_RESOLUTION=720p
ARK_VIDEO_RETURN_LAST_FRAME=true
JIMENG_POLL_INTERVAL_SECONDS=10
JIMENG_POLL_TIMEOUT_SECONDS=900
CHENFLOW_FFMPEG_PATH=ffmpeg
```

成本门禁与媒体发布：

```env
# 视频生成估算成本超过该阈值（USD）时，需要预算确认才能提交；0 表示不启用。
CHENFLOW_VIDEO_COST_CONFIRMATION_THRESHOLD_USD=0.0
# 提供给视频 provider 的本地素材公开访问地址（Docker 内请填容器可达的地址）。
CHENFLOW_MEDIA_PUBLIC_BASE_URL=
CHENFLOW_MEDIA_PUBLICATION_TTL_SECONDS=1800
```

旧即梦图片配置：

```env
JIMENG_ACCESS_KEY=your-volcengine-access-key
JIMENG_SECRET_KEY=your-volcengine-secret-key
JIMENG_IMAGE_REQ_KEY=jimeng_t2i_v40
JIMENG_IMAGE_WIDTH=1024
JIMENG_IMAGE_HEIGHT=1024
```

Doubao Seedream 图片配置（可选，需要 ARK_API_KEY）：

```env
# 留空走即梦（默认）；设为 ark_seedream 使用 Doubao Seedream 图像接口。
CHENFLOW_IMAGE_PROVIDER=
ARK_IMAGE_MODEL=doubao-seedream-5-0-lite-260128
ARK_IMAGE_SIZE=1024x1024
```

本地 fallback 需要额外配置图片生成和 TTS：

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

## 生成证据、异常收件箱与引导

- 每次真实或受阻的生成（分镜、首帧、三视图、视频段、成本门禁）都会追加写入 `generation_attempts`，包含输入资产版本、提示词契约与版本、provider/model、参数、usage、成本估算与质量结果；长文本与 base64 自动脱敏截断。
- 需要创作者决策的素材级异常（预算确认、重复质量失败、身份歧义等）进入异常收件箱，每条含推荐动作、理由与最多三个选项。
- `GET /api/projects/{project_id}/next-action` 返回当前生产的确定性状态与单一推荐下一步，并解析默认 provider/模型/提示词版本，正常流程无需手动选择。

## 本地启动

推荐直接运行根目录脚本：

```powershell
.\start-workbench.ps1
```

或双击：

```text
start-workbench.bat
```

脚本会检查 Docker / Python / npm，启动 MySQL，安装依赖，构建前端并启动后端。启动后访问：

```text
http://127.0.0.1:8500
```

常用参数：

```powershell
.\start-workbench.ps1 -NoBackend -SkipBuild -SkipNpmInstall
.\start-workbench.ps1 -WithEmbedding
```

手动启动：

```powershell
docker compose up -d mysql
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m app.api
```

## 数据库

FastAPI 启动时会执行 `app.db.init_db()`：

- 创建缺失表
- 执行 `schema_migrations` 中尚未记录的手写迁移
- 保持迁移幂等，兼容已有本地数据库

手动检查：

```powershell
python -c "from app.db import init_db; init_db(); print('init_db ok')"
```

当前没有接入 Alembic；新增 schema 改动需要在 `app/models.py` 和 `app/db.py` 中同步维护。

## 后台 Worker

后端启动时会启动本地 worker thread，按顺序处理：

```text
batch_generation_jobs
-> queued storyboards
-> queued video_tasks
```

这是单机 MVP worker，不是分布式队列。当前没有跨进程抢占锁，也不会强行中断正在执行的 LLM、外部 API 或 FFmpeg 调用。

## 常用命令

后端测试：

```powershell
python -m unittest discover -s tests
```

重点回归：

```powershell
python -m unittest tests.test_image_first_reference_storyboard tests.test_image_first_video_gate tests.test_video_preflight_quality_gates
python -m unittest tests.test_frontend_image_first_video_wiring
```

编译检查：

```powershell
python -m compileall app tests
```

前端构建：

```powershell
cd frontend
npm run build
```

Playwright 浏览器回归，需先启动完整后端和 MySQL：

```powershell
.\start-workbench.ps1 -SkipBuild -SkipNpmInstall
cd frontend
npm run test:regression
```

长篇流水线 smoke，需先启动后端：

```powershell
python scripts/longform_pipeline_smoke.py
```

## API 入口

基础接口：

```text
GET  /api/health
GET  /api/bootstrap
GET  /api/me/workspace
POST /api/projects
GET  /api/projects/{project_id}
```

长篇和视频接口：

```text
GET  /api/projects/{project_id}/longform
POST /api/projects/{project_id}/series-plans/generate
POST /api/projects/{project_id}/series-plans/{series_plan_id}/lock
POST /api/projects/{project_id}/batch-generation
POST /api/projects/{project_id}/storyboards
POST /api/projects/{project_id}/storyboards/{storyboard_id}/shots/{shot_id}/first-frame
POST /api/projects/{project_id}/storyboards/{storyboard_id}/video-production/preflight
POST /api/projects/{project_id}/storyboards/{storyboard_id}/video-tasks
GET  /api/projects/{project_id}/next-action
GET  /api/projects/{project_id}/exception-inbox
POST /api/projects/{project_id}/exception-inbox/{item_id}/resolve
```

后端启动后可查看 OpenAPI：

```text
http://127.0.0.1:8500/docs
```

## 开发约定

- `.env` 只放本地，不提交真实 provider key。
- Windows 下读取中文文件使用 `Get-Content -Encoding UTF8`。
- 生成产物放在 `output/`、`workspace/` 或其他被忽略目录。
- 优先沿用现有 service 模块扩展功能，避免过早引入新框架层。
- 外部 provider 原始响应先进入 JSON metadata，等产品契约稳定后再固化字段。
- 锁定语义继续放在 `MediaAsset.meta.locked`。

## 当前限制

- worker 是本地线程，不是 Celery / RQ。
- 手写迁移没有 rollback。
- 视频预览和下载体验仍是基础形态。
- 视频供应商抽象还没有独立 provider task 表。
- 镜头级资产选择器仍是最小可用形态。
- 最终视频拼接依赖 FFmpeg。
