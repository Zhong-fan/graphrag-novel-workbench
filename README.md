# ChenFlow Workbench

ChenFlow Workbench 是一个面向中文小说创作的本地优先工作台。当前实现聚焦在创作者主链路，不再依赖 GraphRAG 或 Neo4j 作为运行前置。

当前主流程是：

`项目设定 -> 人物卡 / 长期资料 -> 章节卡 -> 生成草稿 -> 变化抽取 -> 发布作品 / 追加章节`

## 当前架构

后端现在围绕三类数据运转：

- 项目层长期设定：题材、世界观、写作规则、参考作品理解、人物卡、长期资料
- 章节层创作输入：章节标题、章节前提、用户本次写作意图
- 生成层结果：草稿标题、摘要、正文、场景卡、轻量 trace、变化抽取快照

关键约束：

- 生成时给模型的上下文保持完整
- `generation_runs` 只保留业务必要信息和轻量调试摘要
- 正式正典变化在发布作品或采用章节时写回，不再通过 GraphRAG 索引链路驱动

## 技术栈

| 层 | 实现 |
| --- | --- |
| 后端 | FastAPI |
| 前端 | Vue 3 + Vite + Pinia |
| 数据库 | MySQL |
| 模型调用 | OpenAI-compatible API |
| 写作模型 | `CHENFLOW_WRITER_MODEL` |
| 工具模型 | `CHENFLOW_UTILITY_MODEL` |

## 目录概览

```text
MVP/
  app/          FastAPI 后端
  frontend/     Vue 工作台前端
  scripts/      启动辅助脚本
  tests/        测试
  markdown/     架构、变更、问题记录
```

## 启动

### 1. 准备环境

- Python 3.11+
- Node.js 20+
- Docker Desktop 或本地 MySQL

### 2. 配置 `.env`

复制 `.env.example` 为 `.env`，至少确认这些变量：

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1

CHENFLOW_LLM_MODE=openai
CHENFLOW_WRITER_MODEL=gpt-4.1
CHENFLOW_UTILITY_MODEL=gpt-4.1-mini
CHENFLOW_EMBEDDING_BASE_URL=https://api.openai.com/v1
CHENFLOW_EMBEDDING_MODEL=text-embedding-3-small

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=chenflow_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=chenflow_workbench

AUTH_SECRET=change_me
AUTH_EXP_HOURS=168

CHENFLOW_IMAGE_API_KEY=
CHENFLOW_IMAGE_BASE_URL=
CHENFLOW_IMAGE_MODEL=
CHENFLOW_IMAGE_SIZE=1024x1024
CHENFLOW_TTS_API_KEY=
CHENFLOW_TTS_BASE_URL=
CHENFLOW_TTS_MODEL=
CHENFLOW_TTS_VOICE=
CHENFLOW_FFMPEG_PATH=ffmpeg
```

说明：

- embedding 配置目前仍保留，是为了兼容现有配置结构；当前主流程不再依赖 GraphRAG 索引。
- 配置加载优先读取 `CHENFLOW_*`，同时兼容旧的 `GRAPH_MVP_*` 变量名。
- 视频生产需要图像生成、TTS 和本机 FFmpeg。图像接口按 OpenAI-compatible `POST {CHENFLOW_IMAGE_BASE_URL}/images/generations` 调用；TTS 按 `POST {CHENFLOW_TTS_BASE_URL}/audio/speech` 调用。以上 key/model 可先留空，创建视频任务后会失败并提示缺失配置。

### 3. 启动 MySQL

如果使用仓库内 docker compose：

```bash
docker compose up -d mysql
```

### 4. 安装依赖

后端：

```bash
pip install -r requirements.txt
```

前端：

```bash
cd frontend
npm install
```

### 5. 构建前端并启动后端

前端构建：

```bash
cd frontend
npm run build
```

后端启动：

```bash
python -m app.api
```

也可以直接使用：

- `start-workbench.bat`
- `scripts/start-workbench.ps1`

## 当前功能

- 用户注册、登录、个人资料
- 项目创建、修改、分组、回收站恢复
- 参考作品识别与项目设定建议
- 人物卡、长期资料、参考资料管理
- 章节创建与编辑
- 草稿生成、生成过程查看、变化抽取刷新
- 已发布作品创建、章节追加、作品编辑

## 生成链路说明

当前生成链路不再做 GraphRAG 检索，而是直接使用这些输入构造创作上下文：

- 项目世界设定
- 写作规则
- 章节前提
- 用户本次提示词
- 长期资料摘要
- 参考资料标题摘要
- 最近变化记录
- 场景卡

持久化时：

- `retrieval_context` 存上下文摘要快照
- `scene_card` 存最终写作场景卡
- `generation_trace` 存轻量步骤摘要，不再存完整 prompt/raw output

## 常用接口

- `GET /api/bootstrap`
- `GET /api/me/workspace`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/generate`
- `GET /api/projects/{project_id}/generate/progress`
- `POST /api/projects/{project_id}/generations/{generation_id}/refresh-evolution`
- `POST /api/novels/from-generation`
- `POST /api/novels/{novel_id}/chapters/from-generation`

## 开发校验

后端导入校验：

```bash
python -c "import app.api; print('app import ok')"
```

后端编译校验：

```bash
python -m compileall app
```

前端构建校验：

```bash
cd frontend
npm run build
```

## 历史说明

仓库里仍保留了一部分 GraphRAG 时代的架构文档、bug 记录和清理计划，用于追溯历史决策。它们不是当前运行架构说明。

当前后端收口计划见：

- `markdown/project/architecture/CREATOR_WORKBENCH_BACKEND_CLEANUP_PLAN.md`
