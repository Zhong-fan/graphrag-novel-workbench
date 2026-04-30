# Handoff

## 当前目标

把项目彻底重构为这条正式路线：

- `GraphRAG` 负责官方索引与查询
- `MySQL` 负责登录、用户、项目、记忆、资料、生成历史
- `Neo4j` 负责图谱同步与图关系投影
- `Vue 3 + TypeScript` 负责前端工作台
- 写作模型走真实接口，不走 mock

## 这次已经完成的事

### 架构方向已切换

旧的“自定义图检索 + 固定 seed 世界 + 命令行多章节生成”已经不是主路线。

现在主路线已经切到：

- 用户登录
- 项目创建
- 长期记忆管理
- 参考资料管理
- GraphRAG workspace
- GraphRAG `init / index / query`
- Neo4j 同步
- Vue 工作台

### 后端新模块

已新增或重写：

- [app/config.py](E:\Computer\Wyc_Xc\MVP\app\config.py)
- [app/db.py](E:\Computer\Wyc_Xc\MVP\app\db.py)
- [app/models.py](E:\Computer\Wyc_Xc\MVP\app\models.py)
- [app/auth.py](E:\Computer\Wyc_Xc\MVP\app\auth.py)
- [app/contracts.py](E:\Computer\Wyc_Xc\MVP\app\contracts.py)
- [app/graphrag_service.py](E:\Computer\Wyc_Xc\MVP\app\graphrag_service.py)
- [app/story_service.py](E:\Computer\Wyc_Xc\MVP\app\story_service.py)
- [app/api.py](E:\Computer\Wyc_Xc\MVP\app\api.py)
- [app/llm.py](E:\Computer\Wyc_Xc\MVP\app\llm.py)

### 前端新结构

已重写：

- [frontend/src/App.vue](E:\Computer\Wyc_Xc\MVP\frontend\src\App.vue)
- [frontend/src/api.ts](E:\Computer\Wyc_Xc\MVP\frontend\src\api.ts)
- [frontend/src/types.ts](E:\Computer\Wyc_Xc\MVP\frontend\src\types.ts)
- [frontend/src/stores/workbench.ts](E:\Computer\Wyc_Xc\MVP\frontend\src\stores\workbench.ts)
- [frontend/src/style.css](E:\Computer\Wyc_Xc\MVP\frontend\src\style.css)

前端现在围绕这些功能组织：

- 登录 / 注册
- 项目列表
- 项目创建
- 记忆录入
- 资料录入
- GraphRAG 索引
- 生成请求
- 生成历史
- 检索上下文显示

### 基础设施

已改好：

- [docker-compose.yml](E:\Computer\Wyc_Xc\MVP\docker-compose.yml)
- [.env](E:\Computer\Wyc_Xc\MVP\.env)
- [scripts/start-workbench.ps1](E:\Computer\Wyc_Xc\MVP\scripts\start-workbench.ps1)

当前容器规划：

- `mysql`
- `neo4j`

重要配置：

- 项目自己的 MySQL 端口改成了 `3307`
- Neo4j 仍是 `7687 / 7474`

## 当前确认过的事实

### GraphRAG 依赖

`graphrag==2.7.2` 已安装并可调用。

### GraphRAG workspace

`GraphRAGService.ensure_workspace()` 已验证可用：

- 能创建 workspace
- 能生成 `.env`
- 能生成 `settings.yaml`
- 我已经看过官方 `settings.yaml` 结构
- 当前补丁逻辑是按真实结构在改

### 编译/构建状态

已通过：

- `python -m compileall app`
- `cd frontend && npm run build`
- `python -m app.api` 启动后 `GET /api/bootstrap` 返回 `200`

### 没有保留测试业务数据

注意：

- 我没有保留测试项目、测试用户、测试记忆、测试正文
- 我创建过的临时 GraphRAG inspection workspace 已清理

## 写作规则记忆

这个规则要保留，后续不能丢：

- 普通对话使用 `「」`
- 嵌套引号使用 `『』`

这条规则已经进入：

- 项目说明
- 写作服务约束
- 前端说明

## 现在还没完成的关键部分

下面这些才是下一步真正要做的，不要再偏回旧 MVP 路线。

### 1. 打通真实业务主链

优先打通：

1. `register/login`
2. `create project`
3. `add memory`
4. `add source`
5. `index project`
6. `generate`

### 2. 验证 GraphRAG query 命令参数

需要做一次最小真实验证，确认当前版本 `graphrag query` 的参数组合和 `GraphRAGService.query()` 完全一致。

重点看：

- `--method`
- `--response-type`
- prompt 位置

### 3. 验证 GraphRAG index 输出与 Neo4j 映射

需要确认 `entities.parquet` 和 `relationships.parquet` 的真实字段名。

当前 `sync_to_neo4j()` 已经写了兼容式取值，但还需要实际索引结果验证：

- `id / entity_id / title / name`
- `source / src_id / source_title`
- `target / tgt_id / target_title`

### 4. 清理旧模块

这些旧模块现在已经不是主路径，后面要考虑移除或降级：

- `app/agents.py`
- `app/pipeline.py`
- `app/retriever.py`
- `app/runtime.py`
- `app/neo4j_store.py`
- `app/graph_store.py`
- `app/graph_backend.py`
- `app/schema.py`
- `app/cli.py`

但现在先不要急着删，等新主链确认跑通再清理。

### 5. 修正中文显示问题

PowerShell 里有中文乱码现象。

这是控制台编码问题，不是文件坏了，但后续仍可统一再检查：

- 终端显示
- FastAPI 返回
- Vue 页面渲染
- markdown 落盘

## 下次开机后第一步该做什么

直接按这个顺序继续：

1. 启动容器
   - `docker compose up -d mysql neo4j`
2. 启动后端
   - `python -m app.api`
3. 启动前端开发模式或直接看构建产物
   - `cd frontend`
   - `npm run dev`
4. 不创建演示小说内容
5. 只做最小真实业务验证：
   - 注册
   - 建项目
   - 加一条记忆
   - 加一条资料
   - 跑一次索引
   - 跑一次生成
6. 盯住 GraphRAG query/index 和 Neo4j sync 的真实输出

## 下一步工作重点

一句话版本：

> 先把 `MySQL + GraphRAG + Neo4j + Vue` 的真实主链跑通，再清理旧 MVP 模块，不要再把精力放在示例章节和演示数据上。
