# 晨流小说工作台

晨流小说工作台是一个面向中文小说创作、发布和阅读的本地优先 Web 应用。它把作者工作台、AI 写作、资料检索、人物状态演化、作品发布和读者互动放在同一个产品流程里，适合个人作者、小说设定整理、连续章节试写和小型创作原型验证。

项目当前以 MVP 形态运行：后端使用 FastAPI + MySQL 保存账号、项目、作品和互动数据；使用 Neo4j 与 GraphRAG 承载资料检索；前端使用 Vue 3 + TypeScript + Pinia 构建单页工作台。

## 核心能力

### 面向读者

- 在“发现”中浏览公开作品。
- 查看作品详情、章节目录和正文阅读页。
- 点赞、收藏和发表评论。
- 在“我的喜欢/收藏”中回到收藏过的作品。

### 面向作者

- 注册登录后进入“我的小说”工作台。
- 使用默认文件夹或自定义文件夹管理小说项目。
- 对项目进行搜索、分页、移动文件夹和删除到回收站。
- 编辑项目设定，包括标题、题材、故事前提、世界观、写作规则和文风预设。
- 维护人物卡、资料片段和长期记忆。
- 将项目资料整理为 GraphRAG 检索索引。
- 生成章节草稿，并可选择启用全局检索、场景卡、润色和演化提取。
- 将生成结果发布为新作品，或追加为已有作品的新章节。
- 在作品编辑页维护标题、简介、标语、可见性和章节内容。

### 面向项目维护

- 提供一键启动脚本 `start-workbench.bat`。
- 提供 Docker Compose 编排 MySQL、Neo4j 和可选的 TEI bge-m3 embedding 服务。
- 支持 OpenAI 兼容接口，便于切换模型服务。
- 支持 Ollama 本地 bge-m3 embedding 默认方案。
- 提供基础健康检查、启动信息接口和 SPA 静态资源托管。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Pinia、Vite |
| 后端 | Python、FastAPI、SQLAlchemy、Uvicorn |
| 关系数据库 | MySQL 8.4 |
| 图数据库 | Neo4j 5.26 |
| 检索增强 | GraphRAG |
| Embedding | Ollama `bge-m3`，或 TEI `BAAI/bge-m3` |
| 模型接口 | OpenAI API 或 OpenAI 兼容接口 |
| 本地编排 | Docker Compose、Windows batch 启动脚本 |

## 实现路线

### 1. 用户与社区基础

后端提供注册、登录、验证码、Token 鉴权和用户资料接口。作品侧提供公开作品列表、作品详情、章节、点赞、收藏和评论。前端对应首页、发现、阅读器、用户设置和收藏列表。

这一层的目标是让应用不只是“写作工具”，而是具备最小可用的创作与阅读闭环。

### 2. 作者工作台

作者登录后进入“我的小说”，可以按文件夹管理项目。每个项目保存标题、题材、故事前提、世界观、写作规则、文风预设等基础设定。

项目删除采用软删除，进入回收站后仍可恢复。回收站当前支持项目、作品和人物卡恢复。

### 3. 资料结构化

项目内部可以维护三类创作素材：

- 记忆：适合长期有效的设定、伏笔、规则和风格要求。
- 资料：适合放入检索系统的背景资料、世界观片段、章节摘要或参考文本。
- 人物卡：保存人物姓名、年龄、性别、性格、故事定位和背景。

这些资料会参与 GraphRAG 索引，并在生成章节时作为上下文来源。

### 4. GraphRAG 检索与 Neo4j 同步

点击项目索引后，后端会启动后台任务，将项目资料、人物卡和演化记录写入 GraphRAG 工作区，并同步图数据状态。项目索引状态会在 `stale`、`indexing`、`ready`、`failed` 之间变化。

生成章节时，如果索引状态为 `ready`，系统会使用所选检索方式获取上下文；如果尚未整理资料，则退化为直接根据项目设定和用户输入生成。

当前支持的查询方式包括：

- `local`
- `global`
- `drift`
- `basic`

### 5. AI 写作与状态演化

写作接口会综合项目设定、用户提示词、记忆、GraphRAG 检索结果和可选场景卡生成章节草稿。开启演化提取后，系统会从生成正文中抽取：

- 人物状态变化
- 人物关系变化
- 关键故事事件
- 世界认知变化

这些结果会回写到项目中，并可在后续章节生成时继续参与上下文组织。

### 6. 发布与阅读闭环

生成结果可以发布为公开或私有作品，也可以追加到已有作品中成为新章节。公开作品会进入“发现”，读者可以阅读、点赞、收藏和评论。

这一层让作者工作台与阅读端连接起来，形成“设定 -> 生成 -> 编辑 -> 发布 -> 阅读反馈”的完整流程。

## 目录结构

```text
MVP/
  app/                    FastAPI 后端应用
  frontend/               Vue 3 前端应用
  markdown/               项目文档与工作记录
  scripts/                辅助脚本
  docker-compose.yml      MySQL、Neo4j、TEI 服务编排
  requirements.txt        Python 依赖
  start-workbench.bat     Windows 一键启动脚本
  .env.example            环境变量模板
  README.md               项目入口文档
```

以下目录属于运行时数据或构建产物，默认不提交到 Git：

```text
data/
state/
workspace/
output/
frontend/dist/
frontend/node_modules/
```

## 环境要求

建议使用 Windows 本地运行。需要提前安装：

- Python 3.11 或更高版本
- Node.js 18 或更高版本
- Docker Desktop
- Ollama
- Git

默认 embedding 方案依赖 Ollama 的 `bge-m3`：

```powershell
ollama pull bge-m3
```

如果你希望使用 Docker 中的 TEI embedding 服务，可以启动 `bge-m3` 服务并在 `.env` 中改用 `http://127.0.0.1:8090/v1`。

## 快速启动

### 1. 克隆并进入项目

```powershell
git clone <your-repo-url>
cd MVP
```

如果你已经在当前仓库中，直接进入 `MVP` 目录即可。

### 2. 创建环境变量文件

```powershell
copy .env.example .env
```

至少需要修改：

```env
OPENAI_API_KEY=your-api-key
AUTH_SECRET=replace-this-with-a-long-random-secret
```

`AUTH_SECRET` 建议使用足够长的随机字符串。不要把真实 `.env` 提交到仓库。

### 3. 确认数据库端口

`docker-compose.yml` 将 MySQL 容器端口映射到本机 `3307`：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=graph_user
MYSQL_PASSWORD=graph_password
MYSQL_DATABASE=graphrag_novel
```

Neo4j 默认配置：

```env
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphrag-password
NEO4J_DATABASE=neo4j
```

### 4. 一键启动

Windows 下推荐直接运行：

```bat
start-workbench.bat
```

脚本会依次检查 Docker、Python、npm、Ollama 和 `bge-m3`，然后启动 MySQL / Neo4j、安装前端依赖、构建前端并启动后端服务。

启动成功后访问：

```text
http://127.0.0.1:8000
```

常用地址：

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:8000` | 应用首页 |
| `http://127.0.0.1:8000/api/health` | 健康检查 |
| `http://127.0.0.1:8000/api/bootstrap` | 启动配置摘要 |
| `http://127.0.0.1:7474` | Neo4j Browser |

## 手动启动

如果你不使用一键脚本，可以按下面步骤手动运行。

### 1. 启动基础服务

```powershell
docker compose up -d mysql neo4j
```

如果要使用 Docker TEI embedding：

```powershell
docker compose up -d bge-m3
```

### 2. 安装 Python 依赖

建议使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 安装并构建前端

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

后端默认监听：

```text
http://127.0.0.1:8000
```

### 5. 前端开发模式

开发前端时可以单独启动 Vite：

```powershell
cd frontend
npm run dev
```

默认开发地址通常是：

```text
http://127.0.0.1:5173
```

## 环境变量说明

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GRAPH_MVP_LLM_MODE` | `openai` | LLM 调用模式 |
| `GRAPH_MVP_WRITER_MODEL` | `gpt-5.5` | 正文写作模型 |
| `GRAPH_MVP_UTILITY_MODEL` | `gpt-5.4-mini` | 摘要、场景卡、演化提取等辅助模型 |
| `GRAPH_MVP_EMBEDDING_MODEL` | `bge-m3` | embedding 模型 |
| `GRAPH_MVP_EMBEDDING_API_KEY` | `ollama` | embedding 接口 Key，Ollama 可使用占位值 |
| `GRAPH_MVP_EMBEDDING_BASE_URL` | `http://127.0.0.1:11434/v1` | embedding OpenAI 兼容接口 |
| `GRAPH_MVP_GRAPHRAG_RESPONSE_TYPE` | `Multiple Paragraphs` | GraphRAG 响应格式 |
| `GRAPH_MVP_GRAPHRAG_INDEX_METHOD` | `standard` | GraphRAG 索引方法，可用 `standard`、`fast`、`standard-update`、`fast-update` |
| `GRAPH_MVP_LOCAL_EMBEDDINGS` | `false` | 是否启用本地 fallback embedding |
| `OPENAI_API_KEY` | 无 | OpenAI 或兼容服务 API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容接口地址 |
| `MYSQL_HOST` | `127.0.0.1` | MySQL 主机 |
| `MYSQL_PORT` | `3307` | 本机 MySQL 端口 |
| `MYSQL_USER` | `graph_user` | MySQL 用户 |
| `MYSQL_PASSWORD` | `graph_password` | MySQL 密码 |
| `MYSQL_DATABASE` | `graphrag_novel` | MySQL 数据库 |
| `NEO4J_URI` | `neo4j://127.0.0.1:7687` | Neo4j Bolt 地址 |
| `NEO4J_USER` | `neo4j` | Neo4j 用户 |
| `NEO4J_PASSWORD` | `graphrag-password` | Neo4j 密码 |
| `NEO4J_DATABASE` | `neo4j` | Neo4j 数据库 |
| `AUTH_SECRET` | 示例占位值 | 登录 Token 签名密钥 |
| `AUTH_EXP_HOURS` | `168` | 登录有效期，单位小时 |

## 用户使用教程

### 1. 注册和登录

打开 `http://127.0.0.1:8000`，进入注册或登录入口。注册时需要填写验证码。登录后系统会保存 Token，后续刷新页面会自动恢复会话。

### 2. 浏览作品

进入“发现”可以查看公开作品。点击作品卡片进入详情页，可以阅读章节、点赞、收藏和发表评论。

如果你收藏过作品，可以在“我的喜欢/收藏”中快速找回。

### 3. 创建小说项目

进入“我的小说”，点击新建项目，填写：

- 标题
- 题材
- 故事前提
- 世界观
- 写作规则
- 文风预设

项目创建后会出现在当前文件夹中。你可以通过左侧文件夹切换、搜索和分页管理项目。

### 4. 管理文件夹

“我的小说”支持默认文件夹和自定义文件夹。你可以：

- 新建文件夹
- 展开或收起文件夹列表
- 按文件夹查看项目
- 将项目移动到其他文件夹

### 5. 完善项目设定

打开项目后，左侧进入“项目设定”。建议先补齐：

- 故事一句话前提
- 主要冲突
- 世界运行规则
- 叙事限制
- 对话标点、称谓和风格要求

这些内容会直接参与后续生成。

### 6. 维护人物卡

进入“人物卡”，为主要角色创建人物资料。建议每张人物卡包含：

- 姓名
- 年龄
- 性别
- 性格
- 故事定位
- 背景经历

人物卡会参与索引和章节生成，也会与后续演化记录一起形成连续上下文。

### 7. 添加记忆和资料

项目中的记忆适合保存长期设定，例如“主角不能主动说谎”“城市由三层环形轨道组成”。资料适合保存较长的背景文本、章节摘要、世界观档案或参考片段。

添加资料后，项目索引状态会变为需要更新。建议在正式生成前执行一次资料整理。

### 8. 整理 GraphRAG 索引

在写作前点击索引或整理资料。系统会启动后台任务，把项目资料、人物卡和演化记录写入 GraphRAG 工作区，并同步 Neo4j 状态。

索引完成后，生成章节时可以使用 `local`、`global`、`drift` 或 `basic` 检索。资料较少时可以直接写作；资料较多、人物关系复杂时建议先整理索引。

### 9. 生成章节草稿

进入“写作”，输入本章目标，例如：

```text
写第一章。主角在雨夜回到旧城区，发现失踪三年的朋友留下了一张只写着地铁站名的纸条。
```

可按需要开启：

- 全局检索：适合跨资料查找宏观背景。
- 场景卡：适合在生成前组织冲突、目标、情绪和上下文。
- 润色：适合让生成结果更完整。
- 演化提取：适合自动记录人物状态、关系变化和关键事件。

生成完成后，草稿会保存为一次生成记录。

### 10. 发布作品或追加章节

生成草稿后可以选择：

- 发布为新作品。
- 追加到已有作品的新章节。

发布时需要填写作品标题、作者名、简介、标语和可见性。公开作品会出现在“发现”中；私有作品只在作者自己的作品列表中可见。

### 11. 编辑作品

进入“作品编辑”可以维护：

- 作品标题
- 简介
- 标语
- 题材
- 可见性
- 章节标题
- 章节摘要
- 章节正文
- 章节序号

章节序号不能重复。

### 12. 使用回收站

删除项目、作品或人物卡时，默认进入回收站。进入“回收站”后可以恢复。需要彻底删除时，应通过后端接口或后续管理能力执行硬删除。

## API 概览

主要接口包括：

| 分组 | 接口 |
| --- | --- |
| 健康与启动 | `GET /api/health`、`GET /api/bootstrap` |
| 鉴权 | `GET /api/auth/captcha`、`POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me` |
| 用户资料 | `GET /api/me/profile`、`PUT /api/me/profile` |
| 工作台 | `GET /api/me/workspace`、`POST /api/me/folders` |
| 项目 | `GET /api/projects`、`POST /api/projects`、`GET /api/projects/{project_id}`、`PUT /api/projects/{project_id}`、`DELETE /api/projects/{project_id}` |
| 项目资料 | `POST /api/projects/{project_id}/memories`、`POST /api/projects/{project_id}/sources`、`POST /api/projects/{project_id}/character-cards` |
| 检索与生成 | `POST /api/projects/{project_id}/index`、`POST /api/projects/{project_id}/generate` |
| 作品 | `GET /api/novels`、`GET /api/novels/{novel_id}`、`POST /api/novels/from-generation`、`PUT /api/novels/{novel_id}`、`DELETE /api/novels/{novel_id}` |
| 章节 | `POST /api/novels/{novel_id}/chapters/from-generation`、`PUT /api/novels/{novel_id}/chapters/{chapter_id}` |
| 互动 | `POST /api/novels/{novel_id}/like`、`DELETE /api/novels/{novel_id}/like`、`POST /api/novels/{novel_id}/favorite`、`DELETE /api/novels/{novel_id}/favorite`、`GET /api/novels/{novel_id}/comments`、`POST /api/novels/{novel_id}/comments` |
| 回收站 | `POST /api/trash/{item_id}/restore` |

启动后也可以访问 FastAPI 自动文档：

```text
http://127.0.0.1:8000/docs
```

## 开发命令

前端构建：

```powershell
cd frontend
npm run build
```

前端开发：

```powershell
cd frontend
npm run dev
```

后端启动：

```powershell
python -m app.api
```

Python 语法检查：

```powershell
python -m compileall app
```

启动数据库：

```powershell
docker compose up -d mysql neo4j
```

查看容器状态：

```powershell
docker compose ps
```

停止容器：

```powershell
docker compose down
```

## 数据与持久化

MySQL 和 Neo4j 使用 Docker volume 保存数据：

```text
mysql_data
neo4j_data
neo4j_logs
tei_data
```

GraphRAG 工作区、生成输出和其他运行时目录位于项目本地：

```text
workspace/
output/
data/
state/
```

这些目录默认不提交到 Git。迁移环境时需要单独备份数据库 volume 和运行时目录。

## 常见问题

### 提示找不到 `bge-m3`

执行：

```powershell
ollama pull bge-m3
```

然后重新运行 `start-workbench.bat`。

### 页面打不开

先检查：

- Docker Desktop 是否正在运行。
- `docker compose ps` 中 MySQL 和 Neo4j 是否为运行状态。
- `.env` 是否存在。
- `.env` 中 `MYSQL_PORT` 是否为 `3307`。
- `OPENAI_API_KEY` 是否已填写。
- 后端窗口是否仍在运行。

### 后端连不上 MySQL

确认 `docker-compose.yml` 中 MySQL 映射为 `3307:3306`，并确认 `.env` 使用：

```env
MYSQL_PORT=3307
```

如果本机已有服务占用 `3307`，需要改 `docker-compose.yml` 和 `.env` 中的端口，并重新启动容器。

### Neo4j Browser 无法登录

默认地址：

```text
http://127.0.0.1:7474
```

默认账号密码：

```text
neo4j / graphrag-password
```

### 生成章节时报模型错误

检查：

- `OPENAI_API_KEY` 是否有效。
- `OPENAI_BASE_URL` 是否为可访问的 OpenAI 兼容接口。
- `GRAPH_MVP_WRITER_MODEL` 和 `GRAPH_MVP_UTILITY_MODEL` 是否是当前接口支持的模型名。

### 一定要先整理 GraphRAG 索引吗

不一定。资料较少时可以直接生成，系统会根据项目设定和用户输入写作。资料较多、人物关系复杂或需要连续性时，建议先整理索引。

### 中文显示乱码

请确认文件以 UTF-8 保存。Windows 终端建议使用：

```powershell
chcp 65001
```

`start-workbench.bat` 已包含 UTF-8 代码页设置。

## 当前边界

- 这是 MVP，不是完整生产级多租户系统。
- 默认 CORS 放开，适合本地开发，不建议直接暴露公网。
- `.env.example` 中的数据库密码仅适合本地开发。
- 作品审核、权限分级、硬删除管理、导入导出和完整测试套件仍需继续完善。
- GraphRAG 索引耗时取决于资料规模、embedding 服务和本机性能。

## 后续规划

- 增加更细的作品权限和发布审核。
- 增加章节导出、项目备份和恢复。
- 增加资料批量导入与索引进度展示。
- 增加更完整的端到端测试。
- 增加人物关系图和事件时间线可视化。
- 增强移动端阅读体验。
- 增加硬删除确认和回收站批量操作。
