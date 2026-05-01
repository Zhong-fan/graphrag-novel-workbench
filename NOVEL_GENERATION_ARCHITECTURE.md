# 晨流写作台：小说生成链路与 GraphRAG 作用说明

## 文档目的

这份文档解决四个问题：

1. 这个项目里到底有没有真正使用 `GraphRAG`
2. `GraphRAG` 在小说生成里的真实作用是什么
3. 当前“生成一篇小说正文”的完整流程到底是什么样
4. 现有设计里哪些地方会影响小说质量，尤其是为什么“长期记忆”这个词不清楚

这不是市场文案，而是后续继续重构生成链路时的技术与产品说明。

---

## 一句话结论

当前项目不是“只靠 prompt 胡乱生成小说”，也不是“GraphRAG 只是摆设”。

当前链路可以概括为：

`项目设定 / 用户输入 / 长期设定 / 参考资料 -> GraphRAG 索引 -> GraphRAG 查询 -> 写作 Prompt -> 模型生成正文`

也就是说：

- `GraphRAG` 负责提供“写什么的依据”
- `Prompt` 负责决定“怎么写出来”

当前质量问题主要不在于“没有 GraphRAG”，而在于：

1. GraphRAG 查询结果还没有被整理成适合小说创作的“场景卡”
2. 写作 prompt 现在明显把文风推向了偏重、偏文艺、偏意象先行的方向

---

## GraphRAG 在这个项目里是如何工作的

## 1. GraphRAG 不是口号，代码里真的在用

当前项目确实调用了 `GraphRAGService`：

- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py)
- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py)

后端在两个阶段使用它：

1. `索引阶段`
2. `查询阶段`

---

## 2. 索引阶段：把小说资料送进 GraphRAG

用户在“我的小说”里输入的信息，会先进入数据库：

- 项目标题
- 题材
- 故事前提
- 世界设定
- 写作规则
- 长期设定（当前界面叫“长期记忆”）
- 参考资料

当用户点击“整理资料并开始准备”时，后端会做这些事：

### 2.1 创建 GraphRAG 工作区

每个项目都有自己的 GraphRAG workspace：

- `workspace/project_{project.id}`

对应代码：

- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:24)
- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:27)

### 2.2 把项目资料重建成输入文本

系统会把数据库里的信息拆成若干文本文件，写到 GraphRAG 的 `input/` 目录里：

- `00_project_profile.txt`
- `memory_xxxx.txt`
- `source_xxxx.txt`

对应代码：

- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:38)
- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:76)

这一步的本质是：

`把结构化项目数据重新转成 GraphRAG 可索引的语料`

### 2.3 调 GraphRAG 执行 index

后端会调用：

- `graphrag index`

对应代码：

- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:95)
- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:209)

### 2.4 把索引结果同步到 Neo4j

GraphRAG 生成的 `entities.parquet` 和 `relationships.parquet` 会被读出来，再写进 Neo4j：

- 实体 -> `GraphRAGEntity`
- 关系 -> `RELATES`

对应代码：

- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:121)
- [app/graphrag_service.py](E:/Computer/Wyc_Xc/MVP/app/graphrag_service.py:134)

这里 Neo4j 目前更多是“投影展示层”和“图结果落地层”，真正生成正文时，核心仍然是 GraphRAG query 返回的文本。

---

## 3. 查询阶段：在生成正文前先查 GraphRAG

用户输入“当前写作目标”后，不会直接把这句话喂给模型。

当前流程是：

### 3.1 先查 local

根据当前 prompt 查一次局部上下文：

- `graphrag.query(..., method=payload.search_method, ...)`

### 3.2 再查 global

再查一次全局上下文：

- `graphrag.query(..., method="global", ...)`

对应代码：

- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py:815)
- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py:816)
- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py:817)

### 3.3 把 local/global 查询结果送给写作模型

写作模型最终收到：

- 项目设定
- 用户当前写作目标
- 用户长期设定
- GraphRAG Local Search 结果
- GraphRAG Global Search 结果

对应代码：

- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py:820)
- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py:828)
- [app/api.py](E:/Computer/Wyc_Xc/MVP/app/api.py:829)
- [app/story_service.py](E:/Computer/Wyc_Xc/MVP/app/story_service.py:54)

所以当前项目里，GraphRAG 的真实作用是：

`在正文生成前，把与当前写作目标相关的项目资料重新检索出来，作为模型上下文的一部分`

---

## GraphRAG 在小说生成里的价值，到底体现在哪里

如果只看功能描述，很容易误解为：

“GraphRAG 就是多喂一点资料”

但在小说创作里，它真正应该解决的是下面这些问题。

## 1. 连续性

长篇小说最怕：

- 前文设定忘掉
- 人物关系漂移
- 同一角色每章像不同人
- 某个伏笔突然消失

GraphRAG 的价值之一，就是把这些信息在生成时重新召回。

## 2. 角色与关系不乱

小说的好看程度，很大一部分来自：

- 谁对谁有什么看法
- 谁在回避谁
- 谁在误解谁
- 谁在悄悄靠近谁

GraphRAG 如果用得好，应该帮助系统稳定记住这些“关系事实”。

## 3. 世界设定不丢

例如：

- 世界是否允许超自然
- 某城市或学校的氛围
- 某组织的规则
- 某物件的来历

这些都适合被索引后，在需要时重新提供给模型。

## 4. 事件链可追踪

更好的小说不是每章独立即兴，而是前因后果越来越紧。

GraphRAG 如果继续往前做，应该承载：

- 角色做过什么关键决定
- 这个决定带来什么后果
- 谁知道了，谁不知道
- 哪些关系因此改变

---

## 当前小说生成的完整细致流程

下面是当前项目里一条完整的“生成正文”流程。

## 第 0 步：用户准备项目资料

用户在前端输入：

- 项目标题
- 题材类型
- 故事前提
- 世界设定
- 写作规则
- 长期设定（当前界面叫“长期记忆”）
- 参考资料

这些信息先进入数据库。

## 第 1 步：用户触发索引

用户点击：

- “整理资料并开始准备”

后端开始：

1. 创建 GraphRAG workspace
2. 把项目数据重建为输入文本
3. 运行 GraphRAG index
4. 同步图谱结果到 Neo4j

结果是：

- 项目进入 `ready`
- 后续允许生成正文

## 第 2 步：用户输入当前写作目标

例如：

- 写一段放学后两个人在便利店门口重逢的场景
- 让误会开始松动，但不要立刻和解

这是当前最关键的实时输入。

## 第 3 步：后端先做 GraphRAG 查询

系统先查：

- Local Search
- Global Search

得到两份文本上下文。

## 第 4 步：后端组装写作 Prompt

写作 Prompt 里目前包含：

- 项目名
- 类型
- 项目前提
- 世界设定
- 用户当前写作目标
- 用户长期设定
- GraphRAG local 结果
- GraphRAG global 结果
- 输出要求：标题 / 摘要 / 正文

对应：

- [app/story_service.py](E:/Computer/Wyc_Xc/MVP/app/story_service.py)

## 第 5 步：模型生成 JSON

写作模型返回：

- `title`
- `summary`
- `content`

如果返回不是严格 JSON，代码会做一次解析修正。

## 第 6 步：系统保存生成结果

生成结果会存进：

- `GenerationRun`

字段包括：

- 用户 prompt
- search_method
- response_type
- retrieval_context
- title
- summary
- content

## 第 7 步：用户继续做后续动作

生成结果出来后，用户现在可以：

- 继续生成下一段
- 发布到书城
- 把后续生成结果追加成新章节

---

## 当前链路的核心问题

虽然现在确实用了 GraphRAG，但“小说质量”仍然没有真正被拉起来，原因主要有下面几类。

## 1. GraphRAG 查询结果还是“资料文本”，不是“写作上下文卡”

当前 local/global 结果是直接喂给 writer 的。

这有两个问题：

1. 信息很多，但不一定是“这场戏最需要的”
2. 资料文本不等于小说场景结构

更理想的方式应该是先整理成：

- 当前场景最相关角色
- 当前关系张力
- 当前未解决冲突
- 不能违背的连续性事实
- 可用伏笔与物件

也就是：

`GraphRAG 原始结果 -> 写作场景卡 -> 正文生成`

## 2. 当前 prompt 明显把文风推向“偏重、偏文艺”

当前代码里有非常明确的倾向：

- “意象先行”
- “情绪潜流”
- “环境映射情绪”
- “情绪推进偏细微”

这些要求不等于错，但它们天然更容易把文本推成：

- 句子重
- 抒情密度高
- 环境描写多
- 人物互动偏少

这会让最终效果更像“文艺 prose”，而不是“好看的轻小说”。

## 3. 动态变化还没有真正写回状态层

目前索引资料主要来自：

- 项目设定
- 长期设定
- 参考资料

但角色在正文里发生的变化，例如：

- 某人做了一个自私决定
- 某段关系开始恶化
- 班级舆论转向

这些变化还没有被系统化地提取并写回图谱或状态层。

所以角色容易变成“静态设定上的同一个人”，而不是“会变化的人”。

---

## “长期记忆”为什么不清楚

这个词的问题不是技术问题，而是用户理解问题。

## 1. 它不符合普通用户语言

当用户看到“长期记忆”，常见反应会是：

- 这是什么？
- 是 AI 自己的记忆吗？
- 我要在这里填什么？
- 和资料、设定有什么区别？

也就是说，词本身不直观。

## 2. 它实际上承载的是“长期稳定的重要信息”

这个区块现在真正放的，通常应该是：

- 角色固定设定
- 关系背景
- 世界规则
- 长期伏笔
- 写作硬约束

也就是说，它不是“记忆”，而是：

`后续写作里必须长期保留、不能轻易丢掉的关键设定`

## 3. 更合适的替代名称

推荐按优先级考虑：

### 推荐 1：长期设定

优点：

- 最容易理解
- 和“参考资料”区分明确
- 既可以放人物，也可以放世界

### 推荐 2：关键设定

优点：

- 更简洁
- 强调“重要性”

### 推荐 3：持续约束

优点：

- 适合描述“不能违背的写作条件”

缺点：

- 偏硬，不适合普通用户第一眼理解

### 推荐 4：角色与世界设定

优点：

- 非常明确

缺点：

- 稍长

## 当前建议

如果只改一个词，我建议：

`长期记忆 -> 长期设定`

这是当前最稳的方案。

---

## 对后续优化最有价值的方向

如果目标不是“功能更多”，而是“小说更好看”，建议按下面顺序迭代。

## 第一优先级：重写写作 prompt

目标：

- 从“重文艺”改成“轻、自然、可读、像轻小说”

具体做法：

- 减少抽象抒情
- 提高对白和人物互动比例
- 强调场景推进而不是情绪解释
- 允许轻微口语感和青春空气感

## 第二优先级：把 GraphRAG 查询结果整理成写作场景卡

不要再直接把 local/global 大段文本塞给 writer。

而是先整理成：

- 当前角色状态
- 当前关系张力
- 最近三章关键变化
- 本场景必须记住的设定

## 第三优先级：建立“状态层”

把角色和世界信息拆成：

1. 核心设定层
2. 动态状态层
3. 事件层
4. 外界认知层

这样角色和世界才能随着章节演化，而不是一直静止。

## 第四优先级：加轻量改稿器

生成正文之后，再做一次小规模“减重”处理：

- 删过度抒情句
- 删重复意象
- 提高对白和动作密度
- 压缩解释性心理描写

---

## 最终建议

这个项目后续应该明确分成四个模块：

1. `GraphRAG`
   负责连续性、资料召回、角色关系和世界事实

2. `Planner`
   负责决定这一章/这一场戏到底推进什么

3. `Writer`
   负责写初稿

4. `Editor`
   负责把初稿变轻、变顺、变得更像好看的轻小说

如果只继续堆功能，不重构这四层的分工，小说质量不会真正跃升。

如果这四层理顺了，GraphRAG 的价值才会真正体现出来：

它不是“让模型知道更多资料”，而是：

`让小说的人物、关系、世界和事件真的能持续演化，同时又写得自然、轻、好读。`
