# ChenFlow Workbench

ChenFlow Workbench 是一个面向中文小说创作的本地优先工作台。它把项目设定、GraphRAG 检索、章节草稿生成、正式采用、已发布作品管理和读者侧阅读放在同一条链路里。

当前版本最重要的系统边界只有一条：

`草稿只是候选，采用为正式章节才更新正典资料库和 GraphRAG。`

这不是产品文案，而是后端行为约束。

## 当前工作流

系统按这条链路工作：

`项目资料 -> GraphRAG 输入预览/整理 -> GraphRAG 索引 -> 生成草稿 -> 选择草稿 -> 采用为正式章节 -> 重新执行正式演化抽取 -> 写入项目级正典演化 -> 项目标记 stale -> 再次索引 -> 下一章生成`

三个阶段必须分清：

1. `草稿阶段`
   草稿生成只产生候选正文和候选演化快照。

2. `采用阶段`
   作者把某份草稿发布为新作品，或把某份草稿追加为已发布作品的新章节。

3. `正典阶段`
   只有采用后的正式章节，才会进入项目级演化事实，并在之后进入 GraphRAG。

## 草稿、正典与 GraphRAG 的边界

### 草稿阶段会保存什么

生成草稿时会保存到 `generation_runs`：

- 草稿标题、摘要、正文
- GraphRAG 检索上下文
- `scene_card`
- `evolution_snapshot`
- `generation_trace`

这里的 `evolution_snapshot` 只是该份草稿自己的候选观察结果，用于作者查看、比对和刷新抽取结果，不是项目正典。

### 草稿阶段不会发生什么

当前实现已经收紧为：

- 草稿不会更新项目级正典演化列表
- 草稿不会参与后续 scene card 的项目状态摘要
- 草稿不会进入 GraphRAG 预览输入
- 草稿不会进入 GraphRAG 索引

### 只有采用时才会写入正典

以下两个接口代表“采用草稿为正式章节”：

- `POST /api/novels/from-generation`
- `POST /api/novels/{novel_id}/chapters/from-generation`

采用时系统会做三件事：

1. 以最终采用的章节标题、摘要、正文重新执行一次演化抽取
2. 用这次正式抽取结果替换该 generation 对应的项目级演化记录
3. 将项目标记为 `stale`，等待下一次 GraphRAG 重建索引

因此进入正典资料库和 GraphRAG 的不是“某次草稿里猜出来的变化”，而是“作者明确采用后的正式章节变化”。

## GraphRAG 约束

当前版本请按以下规则理解：

1. GraphRAG 是草稿生成前置条件
2. 项目 `indexing_status` 不是 `ready` 时，生成接口会直接拒绝
3. GraphRAG 输入来自长期资料和已采用章节形成的正典演化
4. 采用新章节后，项目会重新变成 `stale`
5. 想让新正典进入下一轮生成，必须重新索引

换句话说，GraphRAG 检索的是“确认过的世界状态”，不是“所有候选草稿的混合物”。

## DeepSeek 兼容性说明

当前代码里，写作模型与 GraphRAG 索引模型仍然共用同一组 OpenAI-compatible 配置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `GRAPH_MVP_UTILITY_MODEL`

这意味着：

- 你可以把正文写作切到 DeepSeek
- 但这不等于 GraphRAG 索引阶段也一定兼容 DeepSeek

GraphRAG 通过它自己的 `litellm` / chat completion 链路调用模型。某些 OpenAI-compatible 服务在索引阶段不支持 GraphRAG 需要的 `response_format`，这时索引会失败，项目状态会停在 `failed`，草稿生成也会继续被阻止。

如果你使用的是：

```env
OPENAI_BASE_URL=https://api.deepseek.com
```

请先确认该模型在 GraphRAG 索引链路下兼容当前请求格式。否则需要：

- 为 GraphRAG 单独切换到兼容的模型服务
- 或修改 GraphRAG 侧适配逻辑，而不是只改写作模型名

## 当前后端结构

`api.py` 已经拆成装配层，主要结构如下：

```text
app/
  api.py
  api_routes.py
  api_routes_auth.py
  api_routes_projects.py
  api_routes_novels.py
  api_routes_graphrag_generation.py
  api_support.py
  api_support_common.py
  api_support_project.py
  api_support_novel.py
  api_support_generation.py
  api_jobs.py
  api_mount.py
  seed_data.py
```

职责划分：

- `api.py`：FastAPI app 装配
- `api_routes_*.py`：按领域拆分的路由
- `api_support_*.py`：共享 helper
- `api_jobs.py`：后台索引任务
- `api_mount.py`：SPA 静态挂载
- `seed_data.py`：启动时种子数据

## 当前能力

### 作者侧

- 用户注册、登录、个人资料
- 项目创建与文件夹管理
- 项目设定编辑
- 人物卡维护
- 长期记忆维护
- 参考资料维护
- 项目章节规划
- GraphRAG 输入预览与逐文件修订
- GraphRAG 索引
- 基于 GraphRAG 的章节草稿生成
- 草稿箱查看与草稿演化快照刷新
- 将草稿发布为新作品
- 将草稿追加到已发布作品
- 已发布作品与章节编辑

### 读者侧

- 浏览公开作品
- 阅读章节
- 点赞
- 收藏
- 评论

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3, TypeScript, Pinia, Vite |
| 后端 | FastAPI, SQLAlchemy, Uvicorn |
| 关系数据库 | MySQL 8 |
| 图数据库 | Neo4j 5 |
| 检索层 | GraphRAG |
| Embedding | Ollama `bge-m3` 或兼容 OpenAI embedding 接口 |
| 模型接口 | OpenAI API / OpenAI 兼容接口 |

## 目录结构

```text
MVP/
  app/
  frontend/
  markdown/
  scripts/
  data/
  output/
  state/
  workspace/
  docker-compose.yml
  requirements.txt
  start-workbench.bat
  stop-workbench.bat
  .env.example
  README.md
```

## 环境要求

- Python 3.11+
- Node.js 18+
- Docker Desktop
- Neo4j / MySQL 对应运行环境
- 可用的 LLM 接口
- 可用的 embedding 接口

如果使用本地 Ollama embedding：

```powershell
ollama pull bge-m3
```

## 快速启动

### 1. 进入项目

```powershell
cd MVP
```

### 2. 准备环境变量

```powershell
copy .env.example .env
```

至少确认这些配置：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=graph_user
MYSQL_PASSWORD=graph_password
MYSQL_DATABASE=graphrag_novel

NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphrag-password
NEO4J_DATABASE=neo4j

AUTH_SECRET=replace-this-with-a-long-random-secret
AUTH_EXP_HOURS=168
```

### 3. 一键启动

```bat
start-workbench.bat
```

常用地址：

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:8000` | 应用入口 |
| `http://127.0.0.1:8000/api/health` | 健康检查 |
| `http://127.0.0.1:8000/api/bootstrap` | 启动配置摘要 |
| `http://127.0.0.1:7474` | Neo4j Browser |

## 手动启动

### 1. 启动基础服务

```powershell
docker compose up -d mysql neo4j
```

如需本地 embedding 服务：

```powershell
docker compose up -d bge-m3
```

### 2. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 安装前端依赖

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 4. 启动后端

```powershell
python -m app.api
```

### 5. 前端开发模式

```powershell
cd frontend
npm run dev
```

## 关键接口

### 项目与资料

- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/memories`
- `POST /api/projects/{project_id}/character-cards`
- `POST /api/projects/{project_id}/sources`
- `POST /api/projects/{project_id}/chapters`

### GraphRAG

- `POST /api/projects/{project_id}/graphrag/prepare-review`
- `PUT /api/projects/{project_id}/graphrag/files/{filename}`
- `POST /api/projects/{project_id}/index`

### 草稿生成

- `POST /api/projects/{project_id}/generate`
- `GET /api/projects/{project_id}/generate/progress`
- `POST /api/projects/{project_id}/generations/{generation_id}/refresh-evolution`

### 正式采用

- `POST /api/novels/from-generation`
- `POST /api/novels/{novel_id}/chapters/from-generation`

## 已知边界

- 普通的“已发布章节编辑”目前只改读者侧内容，不会自动重建正典演化
- 采用新章节后仍需要重新索引，GraphRAG 才会吸收新正典
- 如果数据库里已经有旧版本留下的草稿污染数据，需要单独清理
- 某些 OpenAI-compatible 服务可用于正文生成，但未必兼容 GraphRAG 索引阶段
