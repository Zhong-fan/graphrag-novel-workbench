# 晨流小说工作台（ChenFlow Novel Workbench）

晨流小说工作台是一个面向中文小说创作和阅读的本地优先 Web 应用。它不是后台管理面板，而是一个读者和作者都能直接使用的产品：读者可以逛书城、收藏、点赞、评论和阅读章节；作者可以创建小说项目、维护项目设定、添加人物卡、生成正文、编辑草稿，并把作品发布到书城。

## 核心功能

- 书城、书架、作品概览页、独立阅读页。
- 小说卡片整体点击进入作品页，不再额外放“详情”按钮。
- 作品概览和阅读分离：概览页展示简介、数据、章节目录和评论；阅读页专注正文阅读。
- 独立作者页面：
  - 新建项目
  - 项目设定
  - 人物卡
  - 写作
  - 作品编辑
- 项目设定可随时修改：小说标题、题材类型、故事前提、世界观、写作偏好、文风预设。
- 人物卡可新增和编辑：姓名、年龄、性别、性格、在小说里的角色、人物背景。
- 人物卡会写入 GraphRAG 项目资料，AI 写作时可以作为上下文参考。
- 两种写作方式：
  - 自动模式：只写一段想法，让 AI 自动补足场景、人物和冲突。
  - 精细模式：控制参考范围、输出形式，并补充设定和资料。
- 发布后仍可编辑作品信息、修改章节、把当前草稿追加成新章节。
- 支持账号、个人资料、收藏、点赞、评论、浮动 toast 成功/错误提示。

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL
- 前端：Vue 3、TypeScript、Pinia、Vite
- 图谱和检索：GraphRAG、Neo4j
- Embedding：Ollama `bge-m3`
- 大模型：OpenAI 兼容接口配置

## 运行环境

需要本机安装：

- Python 3.11+
- Node.js 18+
- Docker Desktop
- Ollama

先拉取本地 embedding 模型：

```powershell
ollama pull bge-m3
```

复制环境变量模板：

```powershell
copy .env.example .env
```

至少需要在 `.env` 中配置：

```env
OPENAI_API_KEY=your-api-key
AUTH_SECRET=replace-with-a-long-random-secret
```

## 一键启动

Windows 下推荐直接运行：

```bat
start-workbench.bat
```

脚本会检查本地依赖，启动 MySQL 和 Neo4j，按需安装/构建前端，并启动后端服务。

打开：

- 应用首页：`http://127.0.0.1:8000`
- 后端健康检查：`http://127.0.0.1:8000/api/bootstrap`
- Neo4j Browser：`http://127.0.0.1:7474`

## 手动启动

启动数据库和图数据库：

```powershell
docker compose up -d mysql neo4j
```

安装前端依赖并构建：

```powershell
cd frontend
npm install
npm run build
cd ..
```

启动后端：

```powershell
python -m app.api
```

前端开发模式：

```powershell
cd frontend
npm run dev
```

Vite 默认地址通常是：

```text
http://127.0.0.1:5173
```

## 推荐使用流程

1. 注册或登录。
2. 进入“新建项目”，填写小说标题、题材、故事前提和世界观。
3. 进入“人物卡”，添加主角和重要配角。
4. 需要调整时，进入“项目设定”随时修改项目信息。
5. 需要 GraphRAG 上下文时，点击“整理资料”。
6. 进入“写作”，选择自动模式或精细模式生成正文。
7. 先编辑草稿，再发布为作品。
8. 发布后可以进入“作品编辑”修改作品信息、章节内容，或追加新章节。

## 验证命令

前端构建：

```powershell
cd frontend
npm run build
```

后端语法检查：

```powershell
python -m compileall app
```

## 目录结构

```text
MVP/
  app/                    FastAPI 后端
  frontend/               Vue 前端
  scripts/                辅助脚本
  docker-compose.yml      MySQL / Neo4j 服务
  requirements.txt        Python 依赖
  start-workbench.bat     Windows 一键启动脚本
  .env.example            环境变量模板
```

运行时或生成目录通常不会提交：

```text
data/
state/
workspace/
output/
frontend/dist/
frontend/node_modules/
```

## 数据和上下文说明

- 项目设定是小说的基础信息，可以随时编辑。
- 人物卡是作者手动维护的核心设定，和 AI 生成后的角色状态更新分开存储。
- 修改项目设定、添加或编辑人物卡后，项目资料会标记为需要更新；需要最新 GraphRAG 上下文时，再重新整理资料。
- 阅读页比普通页面更宽，方便连续阅读正文。

## 常见问题

### 找不到 `bge-m3`

执行：

```powershell
ollama pull bge-m3
```

### 页面打不开

检查：

- Docker Desktop 是否正在运行。
- MySQL / Neo4j 容器是否已启动。
- `.env` 是否配置了 `OPENAI_API_KEY`。
- 后端进程是否仍在运行。

### 普通用户一定要先整理资料吗？

不一定。自动写作模式可以直接根据项目设定和输入想法生成正文。整理资料主要用于人物卡、世界观、资料片段较多时，让 GraphRAG 检索提供更稳定的上下文。
