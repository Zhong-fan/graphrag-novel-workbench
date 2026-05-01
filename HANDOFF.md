# Frontend Product Roadmap

## 当前状态

目前前端已经完成了第一轮产品化改版，但有一部分内容还是“展示型界面”，还没有和真实后端数据完全打通。

已经完成：

- 顶部导航改成 `首页 / 书城 / 书架 / 我的小说 / 我的`
- 登录 / 注册改成右上角独立入口
- 注册简化成 `用户名 + 密码 + 验证码`
- “我的小说”里保留了现有创作工作台
- 首页、书城、书架、我的 这些页面结构已经搭起来了

还没有完成：

- 首页推荐小说是前端写死的示例数据
- 书城小说列表是前端写死的示例数据
- 点赞 / 收藏 / 评论目前只是前端交互，没有真实持久化
- 书架数据目前来自前端临时状态，不是后端用户收藏
- “我的”里的邮箱 / 手机号 / 简介还没有真实保存
- “我的小说”生成出来的内容，还没有发布到“书城”展示

## 总目标

把当前项目从“创作后台 + 假前台”补成：

1. 有真实前台小说展示站
2. 有真实用户书架
3. 有真实互动系统
4. 有作者后台
5. 有作品发布链路

---

## 建议实施顺序

不要一起做，按下面顺序推进。

### 第 1 步：先把“书城作品”数据结构补出来

目标：

- 后端有真实的“作品”表
- 前端书城不再读假数据

建议新增实体：

- `Novel`
- `NovelChapter`
- `NovelLike`
- `NovelFavorite`
- `NovelComment`
- `UserProfile`

建议最小字段：

`Novel`

- `id`
- `author_id`
- `title`
- `summary`
- `genre`
- `tagline`
- `cover_url` 可选
- `status` 例如 `draft / published`
- `visibility` 例如 `private / public`
- `created_at`
- `updated_at`

`NovelChapter`

- `id`
- `novel_id`
- `title`
- `summary`
- `content`
- `chapter_no`
- `created_at`

`NovelLike`

- `id`
- `novel_id`
- `user_id`

`NovelFavorite`

- `id`
- `novel_id`
- `user_id`

`NovelComment`

- `id`
- `novel_id`
- `user_id`
- `content`
- `created_at`

`UserProfile`

- `id`
- `user_id`
- `bio`
- `email`
- `phone`

### 第 2 步：把“我的小说”生成结果接成可发布作品

目标：

- 用户在“我的小说”里生成的内容，能真正变成一部小说或章节

建议做法：

- 先把 `Project` 和 `GenerationRun` 保留
- 增加“发布为作品”动作
- 允许把某次生成结果写入 `Novel` + `NovelChapter`

建议新增接口：

- `POST /api/novels/from-generation`
- 入参：
  - `project_id`
  - `generation_id`
  - `title` 可覆盖
  - `summary` 可覆盖
  - `visibility`

这样可以先不改动现有生成主链，只在后面加“发布”。

### 第 3 步：把书城页面接真实 API

目标：

- 首页推荐
- 书城列表
- 小说详情

建议新增接口：

- `GET /api/novels`
- `GET /api/novels/{novel_id}`
- `GET /api/home/feed`

建议前端替换：

- 把 `App.vue` 里写死的 `novels` 移到 store
- 从 API 拉取
- 首页推荐区改成后端返回

### 第 4 步：把书架做成真实收藏

目标：

- 收藏是真收藏
- 换设备 / 刷新页面后仍然存在

建议接口：

- `POST /api/novels/{novel_id}/favorite`
- `DELETE /api/novels/{novel_id}/favorite`
- `GET /api/me/favorites`

前端改动：

- “书架”页面只展示 `GET /api/me/favorites`
- 收藏按钮直接调接口

### 第 5 步：把点赞和评论做成真实互动

目标：

- 点赞数、评论数真实可用

建议接口：

- `POST /api/novels/{novel_id}/like`
- `DELETE /api/novels/{novel_id}/like`
- `GET /api/novels/{novel_id}/comments`
- `POST /api/novels/{novel_id}/comments`

前端注意：

- 点赞要做“当前用户是否已点赞”
- 评论列表最好分页

### 第 6 步：补“我的”页面真实资料设置

目标：

- 邮箱、手机号、简介可保存

建议接口：

- `GET /api/me/profile`
- `PUT /api/me/profile`

前端改动：

- 进入“我的”时拉资料
- 点击保存时提交

### 第 7 步：再做小说详情页

当前还缺一个关键页面：

- 小说详情页

应该包含：

- 作品信息
- 章节列表
- 点赞 / 收藏 / 评论
- 作者信息
- 推荐作品

建议前端后续拆页面，而不是继续把所有内容都塞进一个 `App.vue`。

---

## 技术债

当前前端为了快速出结构，很多内容还在一个文件里。

后续建议拆分：

- `pages/HomePage.vue`
- `pages/StorePage.vue`
- `pages/ShelfPage.vue`
- `pages/StudioPage.vue`
- `pages/ProfilePage.vue`
- `components/AuthModal.vue`
- `components/NovelCard.vue`
- `components/ProjectCard.vue`

Pinia 也建议拆 store：

- `authStore`
- `novelStore`
- `shelfStore`
- `studioStore`
- `profileStore`

---

## 数据迁移注意点

因为现在用户表还是：

- `display_name` 实际充当用户名
- `email` 目前是内部占位邮箱

以后如果要做真邮箱资料：

1. 不要把现有 `email` 直接当用户真实邮箱使用
2. 最好新增 `UserProfile.email`
3. 或者单独做一次迁移，把占位邮箱与真实邮箱机制分开

---

## 推荐下一次开工顺序

你回来后，建议按这个顺序继续：

1. 先做 `Novel / NovelChapter / Favorite / Comment / Profile` 后端模型
2. 再做 `GET /api/novels` 和 `GET /api/me/favorites`
3. 把前端书城、书架从假数据切到真数据
4. 再做“从生成结果发布到书城”
5. 最后补点赞、评论、个人资料保存

---

## 一句话结论

现在前端已经有了产品外壳，但前台小说展示和社区交互还主要是假的。

后续应先补真实作品数据层，再补发布链路，再补书架 / 点赞 / 评论 / 个人资料，按顺序推进，不要一起动。
