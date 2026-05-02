# Bug Log

这个文件专门记录联调过程中遇到的 bug 和问题，格式固定为：

- `症状`
- `根因`
- `修复`
- `教训`

后续每次遇到新的问题，都继续往这个文件追加。

## 2026-04-30 GraphRAG query 参数不匹配

**症状**

- `generate` 链路调用 `GraphRAGService.query()` 时，GraphRAG CLI 无法正确执行查询。

**根因**

- 本地安装的 `graphrag 2.7.2` 要求查询文本通过 `--query/-q` 传入。
- 项目代码里把 prompt 当作位置参数直接拼到了命令后面。

**修复**

- 将 `app/graphrag_service.py` 中的查询命令从位置参数改为显式的 `--query prompt`。

**教训**

- 包装第三方 CLI 时，不能凭记忆拼参数。
- 必须先跑一遍 `--help`，确认当前安装版本的真实参数格式。

## 2026-04-30 GraphRAG workspace `.env` BOM 导致环境变量失效

**症状**

- `graphrag index` 直接报错，提示 `KeyError: 'GRAPHRAG_API_KEY'`。

**根因**

- workspace 下的 `.env` 文件被写成了 `utf-8-sig`。
- GraphRAG 配置加载时调用 `python-dotenv` 读取 `.env`，第一行键名前带了 BOM，导致真正注入到环境中的键名异常。

**修复**

- 将 workspace `.env`、`settings.yaml`、输入文本统一改为无 BOM 的 `utf-8`。

**教训**

- 只要文件会被别的工具解析，就优先用普通 `utf-8`。
- `utf-8-sig` 适合解决 Windows 文本显示问题，不适合做配置交换格式。

## 2026-04-30 GraphRAG 索引同步阻塞前端

**症状**

- 点击索引后，接口长时间不返回，前端一直处于等待状态。

**根因**

- GraphRAG `index` 是重操作，包含多轮 LLM/embedding 调用，不适合同步挂在 HTTP 请求里。

**修复**

- 将 `/api/projects/{project_id}/index` 改成后台任务。
- 前端 store 增加项目状态轮询，等待 `indexing -> ready/failed`。

**教训**

- 重索引、训练、导入、批处理这类任务，不应该用同步请求直接承载。
- 后台任务 + 状态轮询是更稳的产品形态。

## 2026-04-30 OpenAI 兼容接口不提供 embedding

**症状**

- 真实 HTTP 联调时，项目一直停在 `indexing`。
- GraphRAG 进程持续运行十几分钟，没有转成 `ready` 或 `failed`。

**根因**

- 查看 `workspace/graphrag_projects/project_3/logs/indexing-engine.log` 后确认：
- 当前 `OPENAI_BASE_URL=https://api.68886868.xyz/v1` 对 `text-embedding-3-large` 返回 `503 model_not_found`。
- 进一步探测 `text-embedding-3-small`、`text-embedding-ada-002` 也同样失败。
- GraphRAG 默认有指数退避重试，所以项目长时间卡在 `indexing`，而不是快速失败。

**修复**

- 先确认问题不是代码逻辑，而是 embedding provider 能力缺失。
- 计划改成项目内 fallback embeddings 或更快失败的机制，避免长时间假性“处理中”。

**教训**

- 远端 OpenAI 兼容接口“能跑 chat”不等于“能跑 embeddings”。
- 真正打通 GraphRAG 前，必须分别探测 chat 和 embeddings 两条能力链。
- 出现长时间 `indexing` 时，不要先怀疑算法慢，先查 provider 重试日志。

## 2026-04-30 `sitecustomize` fallback 未生效

**症状**

- 试图通过项目根目录的 `sitecustomize.py` 注入本地 fallback embeddings。
- 直接运行进程内 probe 时，GraphRAG 仍然走到了默认的 `LitellmEmbeddingModel`。

**根因**

- `sitecustomize.py` 依赖环境变量开关。
- 但普通 `python` 进程启动时，`sitecustomize` 的导入发生在项目代码读取 `.env` 之前。
- 也就是说，`.env` 里的值对 `sitecustomize` 来说太晚了。

**修复**

- 当前已确认这是一个启动时序问题。
- 后续需要把开关直接放到真实进程环境变量里，不能只写在项目 `.env` 后由应用层再读取。

**教训**

- `sitecustomize`、`PYTHONPATH`、解释器级 hook 这类机制，都是“应用代码之前”执行。
- 凡是依赖这类 hook 的开关，都必须在进程启动前进入 OS 环境，而不是等应用自己读配置。

## 2026-04-30 显式 GraphRAG CLI wrapper 修复 fallback 注入

**症状**

- 即使已经写了本地 fallback embeddings，GraphRAG 子进程仍然继续使用默认的 `LitellmEmbeddingModel`。

**根因**

- `sitecustomize` 方案依赖解释器启动钩子，时序和导入路径都不够稳。
- 实际上更可靠的办法不是“全局猴补丁”，而是自己控制 GraphRAG CLI 的入口点。

**修复**

- 新增 `app/graphrag_local_embeddings.py`，集中注册本地 fallback embedder。
- 新增 `app/graphrag_cli.py`，在调用官方 `graphrag.cli.main.app` 之前先执行 fallback 注册。
- `GraphRAGService._run_graphrag_command()` 改为调用 `python -m app.graphrag_cli ...`，不再直接调用 `python -m graphrag`。

**教训**

- 如果你需要稳定地改写第三方 CLI 的运行时行为，最稳的是包一层显式 wrapper。
- 启动钩子适合做轻量全局配置，不适合承载关键业务修复。

## 2026-04-30 改用 Ollama 作为 embedding provider

**症状**

- 远端 OpenAI 兼容接口可以处理 chat，但所有常见 embedding 模型都返回 `503 model_not_found`。
- GraphRAG 索引会长时间停在重试，最终无法完成。

**根因**

- 当前远端服务没有开放 embeddings 通道。
- GraphRAG 的 chat 和 embedding 之前共用同一套 `OPENAI_BASE_URL` 配置，导致 embeddings 也被错误地发往这个不支持的接口。

**修复**

- 将项目配置拆成两条链：
  - chat / writer 继续走远端 OpenAI 兼容接口
  - embeddings 单独走本机 Ollama
- 新增独立配置：
  - `GRAPH_MVP_EMBEDDING_MODEL`
  - `GRAPH_MVP_EMBEDDING_API_KEY`
  - `GRAPH_MVP_EMBEDDING_BASE_URL`
- 本机已验证：
  - `Ollama 0.20.2`
  - `nomic-embed-text`
  - `http://127.0.0.1:11434/v1/embeddings`

**教训**

- 不要假设一个 OpenAI 兼容接口“既支持 chat 也支持 embeddings”。
- chat provider 和 embedding provider 在工程上应该允许分离配置。
- 本地 Ollama 很适合拿来补 embedding 能力缺口。

## 2026-04-30 改成 Docker 里的 BGE-M3 embedding provider

**症状**

- 用户希望 embedding provider 不依赖手工本地部署，最好直接跟项目其他基础设施一起启动。

**根因**

- Ollama 方案能用，但仍然要求本机提前准备模型。
- 对项目使用者来说，`docker compose up` 一把起服务的体验更统一。

**修复**

- 在 `docker-compose.yml` 中新增 `bge-m3` 服务。
- 使用 Hugging Face Text Embeddings Inference CPU 镜像承载 `BAAI/bge-m3`。
- 默认 embedding 配置切换为：
  - `GRAPH_MVP_EMBEDDING_MODEL=BAAI/bge-m3`
  - `GRAPH_MVP_EMBEDDING_BASE_URL=http://127.0.0.1:8090/v1`
  - `GRAPH_MVP_LOCAL_EMBEDDINGS=false`

**教训**

- 面向用户的默认方案应优先选择“一条命令即可启动”的路径。
- embedding provider 和数据库一样，适合收进 `docker-compose` 统一管理。
