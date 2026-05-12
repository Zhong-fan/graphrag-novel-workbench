# 创作工作台后端收口计划

## 背景

当前项目已经从“GraphRAG + 读者侧平台”裁成“小说创作者工作台”，但后端还有两类残留问题：

1. 运行链路已经切成创作工作台模式，但数据模型、合同层、文档、脚本里仍残留 GraphRAG 时代的字段和概念。
2. 生成链路在落库时把大体积上下文、场景卡、调试 trace 一起塞进主业务表，容易触发 MySQL 字段上限，也不利于维护。

最近一次真实报错说明了第二类问题的风险：

- 模型生成、润色、意图检查都成功
- 但在“保存草稿”附近出现 500
- 这类问题高度怀疑与 `generation_runs` 的大字段存储策略有关，而不是生成本身失败

这份计划的目标不是“先凑合跑”，而是把后端继续收口成一套可维护、可解释、可扩展的创作工作台架构。

## 核心原则

### 1. 不牺牲生成质量

- 给模型的输入上下文不裁剪
- 只优化“生成完成后如何落库”
- 不为了规避数据库限制而削弱模型实际可见信息

### 2. 主业务表不承载全部调试垃圾

- `generation_runs` 应优先保存业务必要数据
- 完整调试材料不应长期堆在主业务表的 `TEXT` 字段里
- 调试信息要么结构化摘要存储，要么转移到独立文件/独立表

### 3. 先收运行路径，再清历史兼容层

- 先保证当前创作工作台路径干净稳定
- 再逐步移除 GraphRAG 时代遗留字段、文档、脚本和数据库对象
- 避免边跑边叠兼容判断

## 当前问题拆分

### A. 生成存储策略不合理

当前 `generation_runs` 同时承担了：

- 正文内容存储
- 检索/上下文快照
- scene card
- 变化抽取快照
- 全量 trace

其中最危险的是：

- `retrieval_context`
- `scene_card`
- `generation_trace`

这几个字段目前仍是 MySQL `TEXT`，上限约 64KB。只要 trace 里继续写完整 prompt、完整上下文、完整 raw output，就非常容易在成功生成后因为落库失败而报 500。

### B. 残留 GraphRAG 语义污染

虽然主路径已经不再依赖 GraphRAG，但代码层还残留：

- `indexing_status`
- `GraphWorkspace`
- `graph_engine`
- `query_methods`
- 旧文档、旧脚本、旧说明文字

这些内容会持续误导维护者，让系统看起来仍然存在一条“图谱索引前置链路”。

### C. 业务数据和调试数据混在一起

当前 trace 既承担用户可感知的生成过程展示，又承担开发调试用途。问题在于：

- 用户界面只需要阶段、消息、少量摘要
- 开发调试才需要完整 prompt/raw output

这两类数据不应该共享同一种持久化策略。

## 目标状态

完成收口后，后端应满足：

1. 创作链路明确为：
   `项目设定 -> 章节卡 -> 生成草稿 -> 演化抽取 -> 发布/续写`
2. 模型拿到完整上下文，生成质量不因为数据库限制被动下降。
3. `generation_runs` 只保存业务必要信息和轻量调试摘要。
4. 完整原始调试材料不再硬塞主业务表。
5. GraphRAG 残余字段和概念不再参与当前业务路径。

## 具体方案

## 阶段 1：先修生成落库问题

### 1.1 拆分“运行 trace”和“持久化 trace”

生成过程中保留两个概念：

- `runtime_trace`
  用于当前请求过程中的进度展示，可以包含较详细内容
- `persisted_trace`
  用于数据库落库，只保留摘要

建议 `persisted_trace` 结构只保留：

- 请求元信息
  - project id
  - chapter id
  - response_type
  - 是否启用 refiner / evolution
- 上下文摘要
  - world_brief_length
  - writing_rules_length
  - memory_count
  - source_count
  - recent_character_update_count
  - recent_relationship_update_count
  - recent_event_count
  - recent_world_update_count
- 阶段摘要
  - draft model
  - refine model
  - intent_check model
  - 每阶段耗时
  - 是否成功
- 结果摘要
  - title
  - summary_length
  - content_length

不再落库：

- 完整 `user_prompt`
- 完整 `system_prompt`
- 完整 `direct_context`
- 完整模型 raw output

### 1.2 调整 `retrieval_context` 的定位

当前它已经不是“检索结果”，而是“给模型的直接创作上下文”。

建议改名方向：

- 后端字段未来可迁移为 `generation_context`
- 在迁移前，代码层先把它当作“上下文快照”而不是“Graph 检索结果”

短期处理：

- 仍可保存文本快照
- 但只保存适合复盘的上下文摘要版，而不是完整大对象拼接

### 1.3 `scene_card` 可以保留，但要控制职责

`scene_card` 属于创作链路的中间业务产物，保留是合理的。

但要求：

- 只存最终给 writer 的场景卡
- 不在 trace 里再次重复保存一份全文

### 1.4 如果业务确实需要大字段，升级字段类型

这是兜底方案，不是唯一方案。

建议：

- `content`: 保持可容纳长正文，必要时升为 `MEDIUMTEXT`
- `scene_card`: 升为 `MEDIUMTEXT`
- `retrieval_context`/未来的 `generation_context`: 升为 `MEDIUMTEXT`
- `generation_trace`: 即使升级，也仍然只存摘要，不再塞全量原始数据

原因：

- 字段升级能提高系统韧性
- 但不能替代存储职责拆分

## 阶段 2：清理创作工作台不再需要的旧概念

### 2.1 代码层停止使用 `indexing_status`

`indexing_status` 已不再有真实业务语义。

处理顺序：

1. 前端先移除状态显示和依赖
2. 合同层去掉 `ProjectOut.indexing_status`
3. 后端路由和 helper 不再读写该字段
4. 数据模型层保留仅作为过渡兼容，最后再迁移删除

### 2.2 停止使用 `GraphWorkspace`

`graph_workspaces` 表和 `GraphWorkspace` ORM 关系目前已无主业务入口。

处理顺序：

1. 先移除代码引用
2. 确认没有路由/脚本/管理命令再读写它
3. 最后做数据库迁移，删除表和 ORM 关系

### 2.3 精简 Bootstrap 元信息

`/api/bootstrap` 当前仍暴露：

- `graph_engine`
- `query_methods`
- embedding 相关信息

建议分两步：

- 先保留不影响运行的兼容字段
- 后续收缩成真正前端会消费的最小字段集

目标是让 bootstrap 只表达“创作工作台需要什么”，而不是历史架构痕迹。

## 阶段 3：分离调试材料与业务数据

### 3.1 为完整 trace 提供独立落点

如果仍需要完整调试能力，建议二选一：

#### 方案 A：落本地文件

- 每次生成单独写入 `output/traces/project_{id}/generation_{id}.json`
- 数据库存文件路径或 trace id

优点：

- 对现有架构侵入小
- 适合本地优先工作台

缺点：

- 文件生命周期和清理策略要明确

#### 方案 B：独立日志表

新增表，例如：

- `generation_trace_logs`

字段建议：

- id
- generation_run_id
- trace_kind
- payload_json
- created_at

优点：

- 数据结构清楚
- 可以按需要保留完整调试材料

缺点：

- 数据库继续膨胀
- 对本地单机项目不一定必要

当前更推荐方案 A。

### 3.2 前端生成过程页只展示摘要

前端“生成过程”页不需要：

- 完整 prompt
- 完整 raw output
- 全量上下文拼接全文

它只需要：

- 阶段顺序
- 每阶段耗时
- 阶段摘要
- 最终是否成功
- 错误信息

这样既更稳，也更接近用户真正需要的信息。

## 阶段 4：文档和脚本对齐

### 4.1 修正文档

需要统一修改：

- `README.md`
- `README_USER.md`
- `markdown/project/architecture/*`
- 历史 bug / changelog 中直接描述 GraphRAG 为当前主链路的文档

原则：

- 可以保留“历史说明”
- 但必须明确它们已不是当前实现

### 4.2 修正启动脚本

启动和停止脚本应只服务当前工作台：

- 启动 MySQL
- 构建前端
- 启动 FastAPI

不再出现：

- Neo4j
- GraphRAG
- 图谱索引器

## 数据库迁移建议

这部分必须单独做，不要混在普通逻辑提交里。

建议迁移顺序：

1. 升级 `generation_runs` 中需要保留的大字段到 `MEDIUMTEXT`
2. 引入新的轻量 `generation_trace` 结构
3. 部署并确认新生成链路稳定
4. 清空代码层对 `indexing_status` / `GraphWorkspace` 的依赖
5. 最后删除：
   - `projects.indexing_status`
   - `graph_workspaces` 表
   - ORM 关系

## 验收标准

### 功能验收

1. 新建项目、章节、草稿生成、发布、续写都能跑通
2. 生成完成后不再因为落库阶段报 500
3. `/api/projects/{id}`、`/api/projects/{id}/generate`、已发布作品管理接口稳定返回

### 质量验收

1. 模型输入不因数据库限制被裁剪
2. 主业务表不再存完整原始大 trace
3. 代码中不再有活跃业务路径依赖 GraphRAG/Neo4j 概念

### 可维护性验收

1. 新人阅读代码时，能直接看出这是“创作工作台”
2. 业务数据与调试数据职责分离
3. 不再存在一堆空转兼容字段驱动主流程

## 推荐执行顺序

建议按下面顺序推进：

1. 先改生成落库策略
2. 再升级需要保留的大字段
3. 再拆分完整 trace 的存储位置
4. 再清 `indexing_status` / `GraphWorkspace`
5. 最后统一修文档和脚本

## 结论

这次后续收口的关键不是“截断上下文保命”，而是：

- 模型输入保持完整
- 业务主表只存必要业务信息
- 调试材料单独处理
- 历史 GraphRAG 兼容层逐步清除

这样才能既保住生成效果，也把系统从“遗留平台裁剪态”真正收口成“可维护的创作工作台”。
