# GraphRAG Novel Workbench

一个面向中文小说创作的工作台。

它把项目资料、长期记忆和参考文本整理进 GraphRAG 索引，再结合 MySQL、Neo4j 和真实模型接口，提供一套可操作的写作流程。

## 功能

- 用户注册、登录
- 小说项目创建与管理
- 长期记忆录入
- 参考资料录入
- GraphRAG 索引
- 基于检索结果生成正文
- 生成历史查看
- Neo4j 图谱投影

## 技术栈

- 后端：FastAPI、SQLAlchemy、PyMySQL
- 前端：Vue 3、TypeScript、Pinia、Vite
- 检索：Microsoft GraphRAG
- 数据库：MySQL 8、Neo4j 5

## 运行前准备

需要本机具备：

- Python 3.11
- Node.js 18+
- Docker Desktop

## 快速开始

1. 安装后端依赖

```powershell
python -m pip install -r requirements.txt
```

2. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

3. 准备环境变量

把 [`.env.example`](./.env.example) 复制为 `.env`，再按你的环境填写。

至少需要确认这些项：

```dotenv
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
```

4. 启动基础服务

```powershell
docker compose up -d mysql neo4j
```

5. 启动后端

```powershell
python -m app.api
```

6. 启动前端开发服务器

```powershell
cd frontend
npm run dev
```

然后打开：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- 启动检查：`http://127.0.0.1:8000/api/bootstrap`
- Neo4j Browser：`http://127.0.0.1:7474`

## 默认配置说明

项目默认更偏向开发联调，而不是大规模生产运行。

关键默认值：

- `GRAPH_MVP_GRAPHRAG_INDEX_METHOD=fast`
- `GRAPH_MVP_GRAPHRAG_RESPONSE_TYPE=Multiple Paragraphs`
- `GRAPH_MVP_LOCAL_EMBEDDINGS=true`

说明：

- `fast` 索引更适合开发时快速验证主链
- `GRAPH_MVP_LOCAL_EMBEDDINGS=true` 会为 GraphRAG CLI 启用项目内的本地 fallback embeddings
- 这样做的目的，是避免某些 OpenAI 兼容接口不提供 embeddings 时，索引过程长期卡在重试

如果你的模型服务本身支持真实 embeddings，可以把：

```dotenv
GRAPH_MVP_LOCAL_EMBEDDINGS=false
```

## 推荐使用流程

1. 注册并登录
2. 创建一个小说项目
3. 填写项目前提、世界设定、写作规则
4. 添加记忆和参考资料
5. 触发 GraphRAG 索引
6. 等待项目状态变为 `ready`
7. 发起生成请求
8. 查看生成历史与检索上下文

## 项目结构

```text
MVP/
  app/                后端服务与 GraphRAG 集成
  frontend/           Vue 工作台
  scripts/            启动脚本
  workspace/          GraphRAG workspace
  output/             运行输出
  docker-compose.yml  MySQL / Neo4j
  requirements.txt
```

## 常见问题

### 1. 点击索引后一直是 `indexing`

优先检查：

- `.env` 里的模型接口是否可用
- Docker 里的 MySQL、Neo4j 是否正常运行
- 后端日志和 `workspace/graphrag_projects/.../logs/indexing-engine.log`

### 2. OpenAI 兼容接口可以聊天，但索引失败

这通常说明：

- chat 接口可用
- embedding 接口不可用

当前项目默认已经提供本地 fallback embeddings，用于降低这类问题对联调的影响。

### 3. MySQL 端口冲突

项目默认映射：

- MySQL：`3307`

如果本机已有 MySQL，通常不需要改动；只要保证 `.env` 和 `docker-compose.yml` 一致即可。

## 说明

这个仓库当前更适合：

- 本地开发
- 产品原型验证
- GraphRAG 写作流程实验

如果要走生产环境，还需要继续加强：

- 后台任务管理
- 失败重试策略
- 更清晰的索引进度展示
- 更稳定的模型与 embedding provider
