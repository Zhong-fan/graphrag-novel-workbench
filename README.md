# 晨流写作台 · ChenFlow Workbench

面向中文小说创作的本地 AI 工作台。它既支持“只给一段想法，让 AI 自动写”的轻量流程，也保留了面向重度创作者的项目设定、资料管理、GraphRAG 检索和章节连续性能力。

## 核心能力

- 账号注册、登录、验证码和个人资料管理
- 我的小说：管理制作项目和已发布作品
- 创作工坊：进入具体小说项目后继续写作
- AI 自动创作：输入一大段想法，AI 自动理解并生成正文
- 精细控制：补充角色信息、故事资料、参考范围和输出形式
- GraphRAG + Neo4j：整理项目资料并用于上下文检索
- 连续性记录：提取角色、关系、事件和外界认知变化
- 书城、书架、点赞、收藏、评论和章节追加
- 右上角 toast 成功/失败提示，不打断当前操作

## 两种写作方式

### AI 自动创作

适合普通用户。你只需要写一段自然语言想法，例如：

```text
我想写一个雨夜便利店的故事。男主是夜班店员，女主每周三凌晨都会来买同一种饮料。
她每次都像第一次见到他。希望这一段写他们第一次真正聊起来，气氛有点暧昧，也有一点不安。
```

系统会自动把这段话理解成场景、人物、冲突和氛围，并生成小说正文。

### 精细控制

适合想法比较完整的用户。你可以继续补充：

- 角色和故事信息
- 外部资料或片段
- 参考范围
- 正文长度和形式
- 是否自动润色
- 是否记录本章发生的变化

## 推荐使用流程

1. 注册并登录。
2. 进入“我的小说”。
3. 在“快速开始”里写一段小说想法。
4. 系统创建项目后进入“创作工坊”。
5. 默认使用“AI 自动创作”生成正文。
6. 如果需要更多控制，再切到“精细控制”。
7. 满意后发布到书城，后续可以继续追加章节。

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL
- 前端：Vue 3、Pinia、Vite、TypeScript
- 图谱与检索：GraphRAG、Neo4j
- Embedding：Ollama `bge-m3`
- LLM：OpenAI Responses API 兼容接口

## 运行前准备

本机需要安装：

- Python 3.11+
- Node.js 18+
- Docker Desktop
- Ollama

拉取本地 embedding 模型：

```powershell
ollama pull bge-m3
```

复制环境变量：

```powershell
copy .env.example .env
```

然后编辑 `.env`，至少填写：

```env
OPENAI_API_KEY=your-api-key
AUTH_SECRET=replace-this-with-a-long-random-secret
```

## 一键启动

Windows 下推荐直接运行：

```bat
start-workbench.bat
```

启动脚本会自动：

1. 检查 Docker、Python、npm、Ollama
2. 检查本地 `bge-m3`
3. 启动 MySQL 和 Neo4j
4. 安装前端依赖（如需要）
5. 构建前端
6. 启动后端服务

打开：

- 应用首页：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/api/bootstrap`
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

开发前端：

```powershell
cd frontend
npm run dev
```

开发地址通常是：

```text
http://127.0.0.1:5173
```

## 常用验证

前端构建：

```powershell
cd frontend
npm run build
```

后端语法检查：

```powershell
python -m compileall app
```

查看后端配置摘要：

```text
GET /api/bootstrap
```

## 目录结构

```text
MVP/
  app/                    FastAPI 后端
  frontend/               Vue 前端
  scripts/                辅助启动脚本
  docker-compose.yml      MySQL / Neo4j
  requirements.txt        Python 依赖
  start-workbench.bat     Windows 一键启动
  .env.example            环境变量模板
```

运行时目录会被 `.gitignore` 排除：

```text
data/
state/
workspace/
output/
frontend/dist/
frontend/node_modules/
```

## 常见问题

### 提示找不到 bge-m3

执行：

```powershell
ollama pull bge-m3
```

### 页面打不开

检查：

- Docker Desktop 是否运行
- MySQL / Neo4j 容器是否启动
- `.env` 是否配置了 `OPENAI_API_KEY`
- 后端窗口是否还在运行

### 普通用户需要先整理资料吗

不需要。AI 自动创作模式可以直接根据项目设定和你的输入生成。GraphRAG 资料整理主要服务于精细控制和长篇连续写作。
