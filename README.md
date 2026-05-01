# 晨流写作台 · ChenFlow Workbench

一个面向中文小说创作的本地工作台。

`晨流写作台（ChenFlow Workbench）` 用来把小说项目设定、长期记忆、参考资料、生成结果和作品发布串成一条完整创作链路。

它把项目设定、长期记忆和参考资料整理起来，再围绕当前写作目标生成标题、摘要和正文。

## 运行前准备

本机需要先安装：

- Python 3.11
- Node.js 18+
- Docker Desktop
- Ollama

并提前拉取本地 embedding 模型：

```powershell
ollama pull bge-m3
```

## 一键启动

推荐直接双击项目根目录里的 [start-workbench.bat](E:\Computer\Wyc_Xc\MVP\start-workbench.bat)。

也可以在命令行运行：

```bat
cd /d E:\Computer\Wyc_Xc\MVP
start-workbench.bat
```

这个启动脚本会自动：

1. 检查 `Docker`、`Python`、`npm`、`Ollama` 是否可用
2. 检查本地 Ollama 里是否已有 `bge-m3`
3. 启动 `mysql` 和 `neo4j`
4. 如有需要自动执行前端 `npm install`
5. 构建前端
6. 启动后端服务

启动成功后直接打开：

- `http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/api/bootstrap`
- Neo4j Browser：`http://127.0.0.1:7474`

## 手动启动

如果你想分步调试，也可以手动启动。

1. 启动基础服务

```powershell
docker compose up -d mysql neo4j
```

2. 启动后端

```powershell
python -m app.api
```

3. 前端开发模式

```powershell
cd frontend
npm install
npm run dev
```

前端开发地址：

- `http://127.0.0.1:5173`

## 默认配置

默认 embedding 配置使用本地 Ollama：

```dotenv
GRAPH_MVP_EMBEDDING_MODEL=bge-m3
GRAPH_MVP_EMBEDDING_API_KEY=ollama
GRAPH_MVP_EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
GRAPH_MVP_LOCAL_EMBEDDINGS=false
```

说明：

- `OPENAI_*` 仍然用于写作模型
- `GRAPH_MVP_EMBEDDING_*` 单独用于本地 embedding
- `GRAPH_MVP_LOCAL_EMBEDDINGS=false` 表示真正调用 Ollama，而不是项目内 fallback

## 可选：Docker 里的 BGE-M3

如果你不想使用本地 Ollama，也可以切到 `docker-compose.yml` 里的 `bge-m3` 服务：

```powershell
docker compose up -d bge-m3
```

对应配置：

```dotenv
GRAPH_MVP_EMBEDDING_MODEL=BAAI/bge-m3
GRAPH_MVP_EMBEDDING_API_KEY=dummy
GRAPH_MVP_EMBEDDING_BASE_URL=http://127.0.0.1:8090/v1
GRAPH_MVP_LOCAL_EMBEDDINGS=false
```

## 用户使用流程

1. 注册并登录
2. 创建小说项目
3. 填写故事前提、世界设定、写作规则
4. 添加长期记忆和参考资料
5. 点击“整理资料并开始准备”
6. 等待项目进入可写作状态
7. 输入当前场景目标
8. 点击“生成正文”
9. 将生成结果发布到书城
10. 在详情页继续管理作品、作者名、评论与章节追加

## 目录

```text
MVP/
  app/                  后端服务
  frontend/             前端界面
  scripts/              辅助启动脚本
  workspace/            项目工作区
  output/               运行输出
  docker-compose.yml    MySQL / Neo4j / 可选 bge-m3
  start-workbench.bat   Windows 一键启动入口
```

## 常见问题

### 启动脚本提示没有 `bge-m3`

先执行：

```powershell
ollama pull bge-m3
```

### 页面打不开

优先检查：

- Docker Desktop 是否已经启动
- `ollama` 是否正在运行
- `mysql` 和 `neo4j` 容器是否正常启动
- 当前窗口里后端是否还在运行

### 想确认当前是不是走本地 Ollama

访问：

```text
GET /api/bootstrap
```

返回里会包含：

- `embedding_model`
- `embedding_provider`
- `embedding_base_url`
