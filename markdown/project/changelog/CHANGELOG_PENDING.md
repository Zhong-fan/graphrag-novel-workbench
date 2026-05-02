# 临时变更记录

说明：

- 用户要求把每次修改都记录到 `E:\Computer\Wyc_Xc\日志`
- 当前仓库内无法直接用 `apply_patch` 写到工作区外目录
- 先在仓库内维护这份同步记录，后续如获得对目标日志目录的稳定写入方式，再同步过去

## 2026-05-01 当前轮次

### 已完成

- 建立小说生成链路与 GraphRAG 作用文档
- 建立演化机制设计文档
- 实现演化数据层：
  - `CharacterStateUpdate`
  - `RelationshipStateUpdate`
  - `StoryEvent`
  - `WorldPerceptionUpdate`
- 实现章节生成后的演化提取与写回
- 实现演化数据进入 GraphRAG 输入重建
- 实现写作上下文卡
- 把“长期记忆”统一为“长期设定”
- 前端增加演化状态、写作上下文卡、演化快照展示
- 新增可选文风预设：
  - `light_novel`
  - `lyrical_restrained`
- 实现两段式生成：
  - 初稿生成
  - 轻量润色

### 当前正在做

- 强化 scene card 结构化程度
- 强化演化提取 prompt 的具体性
- 建立日志记录机制
