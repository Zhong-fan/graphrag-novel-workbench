# GraphRAG 中文小说工作台

这是一个按 `GraphRAG + MySQL + Neo4j + Vue` 路线重构中的中文小说项目。

当前目标不是“命令行多生成几章示例”，而是把下面这套完整应用做出来：

- `Vue 3 + TypeScript` 前端工作台
- `FastAPI` 应用服务层
- `MySQL` 用户、项目、记忆、资料、生成历史
- 官方 `GraphRAG` 索引与查询
- `Neo4j` 图谱同步与图关系承载
- 真实模型写作，不走本地 mock

## 当前实现路线

系统现在按下面这条主链工作：

1. 用户注册并登录
2. 创建自己的小说项目
3. 录入世界设定、写作规则、长期记忆、参考资料
4. 后端把这些内容写入 `GraphRAG workspace`
5. 官方 `GraphRAG` 执行 `init / index / query`
6. 索引结果同步一份到 `Neo4j`
7. 写作请求先走 `GraphRAG local/global` 查询
8. 查询结果再交给写作模型生成正文
9. 生成历史、记忆、项目归属保存在 `MySQL`

这和之前的自定义图检索路线不同。现在的方向是“应用层自建，GraphRAG 官方链路接入”。

## 技术栈

后端：

- Python 3.11
- FastAPI
- SQLAlchemy 2
- PyMySQL
- Neo4j Python Driver
- 官方 GraphRAG

前端：

- Vue 3
- TypeScript
- Vite
- Pinia

基础设施：

- Docker Compose
- MySQL 8.4
- Neo4j 5

## 目录结构

```text
MVP/
  app/
    api.py
    auth.py
    config.py
    contracts.py
    db.py
    graphrag_service.py
    llm.py
    models.py
    story_service.py
  frontend/
    src/
    package.json
    vite.config.ts
  scripts/
    start-workbench.ps1
  workspace/
    graphrag_projects/
  docker-compose.yml
  requirements.txt
  .env
```

## 环境配置

项目默认从根目录 `.env` 读取配置。当前关键项：

```dotenv
GRAPH_MVP_LLM_MODE=openai
GRAPH_MVP_WRITER_MODEL=gpt-5.5
GRAPH_MVP_UTILITY_MODEL=gpt-5.4-mini
GRAPH_MVP_EMBEDDING_MODEL=text-embedding-3-large
GRAPH_MVP_GRAPHRAG_RESPONSE_TYPE=Multiple Paragraphs
GRAPH_MVP_GRAPHRAG_INDEX_METHOD=fast

OPENAI_API_KEY=...
OPENAI_BASE_URL=.../v1

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

注意：项目自己的 MySQL 容器当前映射到宿主机 `3307`，避免和本机已有 MySQL 冲突。

## 启动基础设施

```powershell
docker compose up -d mysql neo4j
```

服务端口：

- MySQL: `127.0.0.1:3307`
- Neo4j Bolt: `127.0.0.1:7687`
- Neo4j Browser: `http://127.0.0.1:7474`

## 安装依赖

后端：

```powershell
python -m pip install -r requirements.txt
```

前端：

```powershell
cd frontend
npm install
cd ..
```

## 启动后端

```powershell
python -m app.api
```

后端启动后访问：

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/api/bootstrap`

## 启动前端开发模式

```powershell
cd frontend
npm run dev
```

然后打开：

- `http://127.0.0.1:5173`

Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 构建前端成品

```powershell
cd frontend
npm run build
cd ..
```

构建结果在 `frontend/dist/`，之后由 FastAPI 直接托管。

## 一键启动脚本

```powershell
.\scripts\start-workbench.ps1
```

这个脚本会：

1. 启动 `MySQL + Neo4j`
2. 构建前端
3. 启动 FastAPI

## 写作规范

正文标点规则固定为：

- 普通对话使用 `「」`
- 嵌套引号使用 `『』`

这条规则会作为项目写作约束进入生成流程。

## 当前状态

开发联调建议：
- 默认把 `GRAPH_MVP_GRAPHRAG_INDEX_METHOD` 设为 `fast`，先把主链跑通
- 只有在需要更完整图谱质量时，再切回 `standard`
- `GraphRAG index` 天然比 `query` 慢，适合做后台任务，不适合阻塞式前台等待

当前已经完成或落地的部分：

- 新的认证与项目模型
- `MySQL` 数据层
- `GraphRAG workspace` 生成与配置补丁
- `Neo4j` 同步服务骨架
- 新版 Vue 工作台结构
- 新版 API 主路径

当前还在继续收口的部分：

- 用真实项目数据打通 GraphRAG `index/query`
- 完整验证 Neo4j 同步字段映射
- 清理旧的 MVP 遗留模块
- 更完整的前端交互与错误反馈

## 说明

当前项目没有用 `LangChain`。

这是有意选择。你这个项目的关键是：

- 应用层状态必须自己掌控
- GraphRAG 必须接官方链路
- 登录、记忆、项目归属必须是业务系统的一部分

所以正确分层是：

- `MySQL` 管应用状态
- `GraphRAG` 管索引和查询
- `Neo4j` 管图关系投影
- `Vue + FastAPI` 管产品形态
