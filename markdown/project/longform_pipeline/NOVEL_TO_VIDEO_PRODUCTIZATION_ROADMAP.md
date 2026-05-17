# 小说视频化产品化路线

更新时间：2026-05-17

## 目标定位

当前系统已经具备“小说 -> 定稿章节 -> 分镜 -> 视频任务 -> 即梦逐镜头生成 -> FFmpeg 拼接”的 MVP 闭环。下一阶段目标不是继续堆单点能力，而是把它产品化为一条可控、可预览、可重试、可迭代的小说视频化生产链路。

产品化后的目标形态：

```text
小说内容是源头
角色和场景资产是视觉约束
分镜是创作控制层
视频模型是渲染执行层
音频字幕是成片包装层
任务系统和前端预览是生产管理层
```

## 当前状态判断

当前链路属于“工程骨架完整，产品控制力不足”：

- 已有长篇概要、正文、定稿章节、分镜、视频任务。
- 已有本地 worker 和任务事件。
- 已接入即梦 3.0 720P 文生视频。
- 已能按镜头生成片段，并用 FFmpeg 拼接最终视频。

但还缺少产品化必须具备的能力：

- 角色视觉一致性。
- 场景和服装资产管理。
- 结构化镜头控制。
- 镜头首帧图和图生视频。
- 单镜头重生成和版本对比。
- 旁白、字幕、音效、BGM 的最终合成。
- 前端预览、下载、成本估算和任务管理。
- 更可靠的后台任务系统和文件存储。

## 产品化主链路

推荐目标链路：

```text
项目设定
-> 角色视觉资产
-> 场景视觉资产
-> 长篇概要
-> 章节正文
-> 定稿章节
-> 分镜生成
-> 分镜镜头结构化编辑
-> 镜头首帧生成
-> 图生视频 / 文生视频
-> 单镜头预览与重生成
-> 旁白 / 字幕 / BGM / 音效
-> 最终合成
-> 视频预览 / 下载 / 发布
```

## 一、视觉资产层

### 0. 项目级视觉风格锁定

这是视觉资产层的前置能力。用户在项目层明确“这部作品的视频应该长什么样”，后续角色三视图、场景图、首帧图、镜头图和视频 prompt 都从这里继承约束。

短期已采用 `projects` 表字段承载：

```text
visual_style_locked
visual_style_medium
visual_style_artists_json
visual_style_positive_json
visual_style_negative_json
visual_style_notes
```

前端入口：

```text
长篇流水线 -> 视觉风格锁定
```

用户可编辑：

- 画面媒介：例如 `二维动画电影`、`手绘漫画`、`水彩插画`、`写实电影`。
- 作者 / 工作室画风参考：例如 `新海诚画风`、`宫崎骏画风`。
- 正向视觉关键词：色彩、光线、场景质感、角色造型、构图语言。
- 禁止项：例如真人、实拍、三次元、照片级写实、文字、水印、logo。
- 补充说明：这部项目独有的视觉要求。

实现原则：

- 不能在代码里写死某一部参考作品或某个作者。
- 作者画风只作为用户可编辑的项目配置参与 prompt。
- 后端统一从项目配置构造视觉风格块，而不是让每个服务各写一套 prompt。
- 如果用户没有填写正向关键词，短期回退到参考作品识别出的 `reference_work_style_traits` 和 `reference_work_world_traits`。

已接入位置：

- `StoryboardService`：生成分镜时要求 `visual_prompt` 遵守项目级视觉风格。
- `VideoRenderService`：即梦文生视频和 fallback 图片生成都使用最终视觉 prompt。
- `VisualAssetService`：角色三视图 prompt 使用同一套视觉风格。

后续应扩展：

- 把视觉风格锁定也接入场景资产、首帧图和图生视频。
- 增加“风格测试图”按钮，先生成低成本 sample，再进入批量视频。
- 增加项目级风格版本历史，避免改风格后旧素材失去上下文。

### 1. 角色资产

目标：让同一角色在不同镜头中尽量保持外观、服装、年龄、气质一致。

需要支持的资产类型：

- `character_profile`：角色视觉设定卡。
- `character_turnaround`：三视图，正面 / 侧面 / 背面。
- `character_expression_sheet`：表情表。
- `character_outfit`：服装版本。
- `character_pose_ref`：动作姿态参考。

建议数据落点：

```text
media_assets.asset_type:
  character_profile
  character_turnaround
  character_expression_sheet
  character_outfit
  character_pose_ref
```

建议新增字段或 metadata：

```json
{
  "character_name": "角色名",
  "version": 1,
  "locked": true,
  "view": "front|side|back",
  "outfit": "default",
  "style": "cinematic_realistic"
}
```

前端能力：

- 角色资产库。
- 上传 / 生成 / 替换三视图。
- 锁定视觉版本。
- 在分镜镜头中选择角色引用。

### 2. 场景资产

目标：让关键地点在多镜头中保持空间关系和视觉风格。

需要支持的资产类型：

- `scene_profile`：场景视觉设定卡。
- `scene_ref`：场景参考图。
- `scene_layout`：空间布局。
- `scene_lighting`：光照风格参考。

建议数据落点：

```text
media_assets.asset_type:
  scene_profile
  scene_ref
  scene_layout
  scene_lighting
```

前端能力：

- 场景资产库。
- 分镜镜头绑定场景。
- 场景内统一光照、天气、时代感和道具。

## 二、分镜控制层

当前 `StoryboardShot.visual_prompt` 仍是自由文本。产品化需要把镜头信息结构化。

### 1. 推荐镜头字段

建议在 `storyboard_shots` 新增字段，或先存入 `meta_json`：

```json
{
  "shot_size": "wide|medium|close_up|extreme_close_up",
  "camera_angle": "eye_level|low_angle|high_angle|over_shoulder",
  "camera_motion": "static|push_in|pull_out|pan|tilt|tracking|handheld|orbit",
  "composition": "center|rule_of_thirds|foreground_layered|symmetrical",
  "subject_action": "角色动作",
  "emotion_tone": "紧张、压抑、温柔、爆发",
  "lighting": "cold_neon|warm_sunset|backlight|low_key",
  "pace": "slow|normal|fast",
  "negative_prompt": "不要文字、水印、logo、变脸、畸形手指"
}
```

### 2. Prompt 生成策略

不要直接把小说段落塞给视频模型。推荐由后端统一生成视频 prompt：

```text
视觉主体
+ 角色引用
+ 场景引用
+ 镜头景别
+ 机位角度
+ 运镜
+ 动作
+ 情绪
+ 光照
+ 禁止项
```

示例：

```text
近未来海滨城市雨夜，快递站冷光环境。
主角握着旧包裹，神情紧张，听见包裹里传出微弱求救声。
中近景，平视机位，缓慢推镜，主体位于画面右侧三分线。
冷色霓虹反光，雨水打在玻璃门上，电影感，动作自然。
避免文字、水印、logo、角色变脸、手部畸形。
```

## 三、镜头首帧和图生视频

当前即梦接入的是 720P 文生视频。产品化后建议升级为：

```text
角色/场景资产
-> 生成镜头首帧
-> 用户确认首帧
-> 图生视频生成镜头片段
```

原因：

- 文生视频角色一致性不稳定。
- 首帧可作为镜头构图和角色外观锚点。
- 用户可以先低成本确认画面，再消耗视频生成成本。

建议新增资产类型：

```text
media_assets.asset_type:
  shot_first_frame
  shot_video_segment
```

建议流程：

```text
生成 shot_first_frame
-> 前端预览首帧
-> 用户锁定或重生成
-> 提交图生视频
-> 下载 shot_video_segment
```

## 四、视频模型 Provider 层

不要把即梦逻辑长期写死在 `VideoRenderService` 中。后续需要 provider 抽象。

建议接口：

```python
class VideoProvider:
    def submit(self, request: VideoGenerationRequest) -> ProviderTask
    def poll(self, provider_task_id: str) -> ProviderTaskResult
    def download(self, result: ProviderTaskResult, output_path: Path) -> Path
```

推荐 provider：

- `JimengTextToVideoProvider`
- `JimengImageToVideoProvider`
- `WanxVideoProvider`
- `KlingVideoProvider`
- `ViduVideoProvider`
- `HailuoVideoProvider`

调度策略：

```text
draft    -> 低成本模型
standard -> 即梦 720P / 通义万相 / Vidu
premium  -> 即梦 Pro / 可灵高质量模型
```

分镜级别可以支持：

```json
{
  "quality_mode": "draft|standard|premium",
  "provider": "jimeng",
  "cost_limit_cny": 3.0
}
```

## 五、音频、字幕和最终合成

视频模型不应该承担完整成片包装。旁白、字幕、BGM、音效建议由本地合成层处理。

目标链路：

```text
每个镜头视频片段
-> TTS 生成旁白
-> 生成字幕 srt/ass
-> 匹配音效
-> 匹配 BGM
-> FFmpeg 合成最终视频
```

需要补齐：

- 旁白 TTS provider。
- 字幕样式配置。
- 字幕烧录。
- BGM 音量 ducking。
- 音效素材库。
- 片头 / 片尾 / 水印策略。

建议新增资产类型：

```text
voice
subtitle
bgm
sound_effect
final_video
```

### 配音功能实现方案

配音优先做“旁白 TTS”，再扩展到角色对白。原因是当前 `StoryboardShot.narration_text` 已经稳定存在，能直接作为每个镜头的旁白脚本。

#### 1. 数据落点

短期继续复用 `media_assets`：

```text
media_assets.asset_type:
  voice
  subtitle
  bgm
  sound_effect
  final_video
```

`voice` asset 的 `meta_json` 建议写入：

```json
{
  "video_task_id": 1,
  "storyboard_id": 1,
  "shot_id": 1,
  "shot_no": 1,
  "voice_role": "narrator",
  "voice_profile": "female_soft|male_young|custom",
  "provider": "openai_compatible|volcengine|edge_tts",
  "model": "tts-model-name",
  "duration_seconds": 4.8,
  "sample_rate": 24000,
  "mime_type": "audio/mpeg",
  "locked": false,
  "version": 1
}
```

中期可新增表：

```text
voice_profiles
voice_tasks
voice_segments
audio_compositions
```

但在 MVP 阶段不必立刻加表，先保证 `media_assets` 中的音频资产可生成、可试听、可替换。

#### 2. 后端服务

建议新增：

```text
app/voice_service.py
```

核心方法：

```python
class VoiceService:
    def generate_shot_voice(db, shot, voice_profile, output_dir) -> MediaAsset
    def generate_storyboard_voice(db, storyboard, voice_profile) -> list[MediaAsset]
```

短期可以复用 `VideoRenderService._generate_voice()` 的 OpenAI-compatible TTS 调用，但应抽出来，不再藏在本地 fallback 视频分支里。

#### 3. API

建议新增接口：

```text
POST /api/projects/{project_id}/storyboards/{storyboard_id}/voice-tasks
POST /api/projects/{project_id}/storyboards/{storyboard_id}/shots/{shot_id}/voice
POST /api/projects/{project_id}/media-assets/{asset_id}/regenerate-voice
```

请求体：

```json
{
  "voice_profile": "female_soft",
  "provider": "openai_compatible",
  "speed": 1.0,
  "emotion": "calm|sad|tense|hopeful",
  "text_override": ""
}
```

返回 `MediaAssetOut` 或 voice task 状态。

#### 4. Worker 拆分

配音不应该和视频模型任务绑定死。推荐拆成独立步骤：

```text
GenerateVoiceTask
GenerateSubtitleTask
ComposeShotAudioTask
ComposeFinalVideoTask
```

最小实现可以先同步执行：

```text
点击“生成旁白”
-> 遍历 shots
-> 每个 shot 调 TTS
-> 保存 shot-001.mp3
-> 写入 media_assets voice
-> 前端可试听
```

后续再改为队列任务。

#### 5. 字幕与音频对齐

短期：

- 每个镜头一条字幕，时间轴为 `0 -> shot.duration_seconds`。
- 文件格式先用 `.srt`。
- `media_assets.asset_type=subtitle`。

中期：

- 根据 TTS 返回时长或 `ffprobe` 读取音频时长。
- 如果音频长于镜头，提示用户缩短旁白或自动延长镜头时长。
- 支持 `.ass` 样式字幕。

#### 6. 最终合成

FFmpeg 最小合成：

```text
输入：shot_video_segment.mp4 + shot_voice.mp3
输出：shot_composed.mp4
```

示例命令逻辑：

```text
ffmpeg -i segment.mp4 -i voice.mp3 \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac -shortest shot-composed.mp4
```

最终合成：

```text
shot-composed-001.mp4
shot-composed-002.mp4
...
-> concat
-> 加 BGM ducking
-> 烧录字幕
-> final.mp4
```

BGM ducking 可后置，先实现旁白混入和字幕文件生成。

#### 7. 前端体验

前端需要在长篇流水线或独立视频任务页中支持：

- 镜头旁白文本查看和编辑。
- 选择 voice profile。
- 单镜头生成 / 重生成配音。
- 整个分镜批量生成配音。
- 音频试听。
- 显示音频时长。
- 显示“音频比镜头长”的警告。
- 选择是否烧录字幕。
- 最终视频预览。

小内容用弹框处理：

- 配音参数。
- 试听。
- 重生成确认。
- 字幕样式。

主页面保持单列生产链路，不做左右结构。

## 六、前端产品化体验

当前前端已有长篇流水线入口，但视频生产体验还不够完整。

### 1. 资产库页面

需要支持：

- 角色资产列表。
- 场景资产列表。
- 三视图预览。
- 首帧图预览。
- 视频片段预览。
- 锁定 / 替换 / 删除 / 版本历史。

### 2. 分镜编辑器

需要支持：

- 镜头列表。
- 拖拽排序。
- 镜头结构化表单。
- 角色引用选择。
- 场景引用选择。
- 首帧预览。
- 片段预览。
- 单镜头重生成。
- 成本预估。

### 3. 视频任务页

需要支持：

- 任务列表。
- 状态筛选。
- 事件时间线。
- 每个镜头的生成状态。
- 失败原因展示。
- 重试单镜头。
- 继续未完成任务。
- 最终视频预览和下载。

## 七、后台任务系统

当前 worker 是本地线程，适合单机 MVP。产品化建议逐步演进。

### 阶段 1：增强本地 worker

- 给 video task 增加 worker 心跳。
- 记录 provider task id。
- 支持服务重启后恢复轮询。
- 支持单镜头失败后从失败镜头继续。
- 支持任务取消标记。

### 阶段 2：引入队列

推荐：

```text
Redis + RQ
或
Redis + Celery
```

任务拆分：

```text
GenerateFirstFrameTask
GenerateVideoSegmentTask
GenerateVoiceTask
ComposeFinalVideoTask
```

### 阶段 3：分布式和限流

- provider 并发限流。
- 每用户每日预算。
- 每任务成本上限。
- 失败重试策略。
- 幂等任务 key。
- 死信队列。

## 八、文件存储

当前生成文件落本地：

```text
output/video_tasks/{task_id}/
```

产品化建议接入对象存储：

- MinIO：本地和私有部署。
- S3：云部署。
- 火山 TOS：如果主要用火山生态。

建议新增统一 storage service：

```python
class StorageService:
    def put_file(local_path: Path, key: str) -> str
    def get_signed_url(uri: str, expires_seconds: int) -> str
    def delete(uri: str) -> None
```

`media_assets.uri` 不应该长期依赖本地绝对路径。

## 九、质量评估

产品化必须有 Evaluator，否则生成失败只能靠用户肉眼发现。

建议评估维度：

- 角色是否一致。
- 服装是否一致。
- 场景是否符合设定。
- 镜头是否符合分镜字段。
- 是否有文字、水印、logo。
- 是否有明显畸形。
- 旁白和字幕是否匹配。
- 视频时长是否符合预期。

评估结果写入：

```text
media_assets.meta_json.evaluation
video_tasks.progress_json.evaluation_summary
```

## 十、数据模型建议

短期可以继续复用 `media_assets.meta_json`。中期建议新增更明确的表。

建议新增表：

```text
visual_characters
visual_character_versions
visual_scenes
visual_scene_versions
video_provider_tasks
video_segments
video_compositions
asset_versions
```

其中 `video_provider_tasks` 用于记录外部模型任务：

```text
id
project_id
video_task_id
storyboard_id
shot_id
provider
provider_task_id
req_key
status
request_json
response_json
output_url
error_message
created_at
updated_at
```

## 十一、推荐实施顺序

### P0：把当前即梦链路稳定下来

- 更新实施状态文档，记录即梦 720P 已接入。
- 真实填 key 跑 1 个镜头。
- 验证签名、提交、轮询、下载、FFmpeg 拼接。
- 前端能看到任务事件和 output uri。

### P1：单镜头产品化

- 每个镜头生成独立片段。
- 前端支持片段预览。
- 支持单镜头重试。
- 支持单镜头替换。
- 支持失败后继续生成剩余镜头。

### P2：视觉资产层

- 角色资产库。
- 场景资产库。
- 三视图 / 场景参考图上传和生成。
- 分镜镜头绑定角色和场景资产。

### P3：首帧图和图生视频

- 生成 `shot_first_frame`。
- 前端确认首帧。
- 接入即梦图生视频或其他图生视频 provider。
- 保留文生视频作为低成本 fallback。

### P4：成片包装

- TTS 旁白。
- 字幕烧录。
- BGM 和音效。
- 片头片尾。
- 下载最终视频。

### P5：任务和存储升级

- 引入 Redis 队列。
- 接入 MinIO / S3 / TOS。
- 增加 provider task 表。
- 增加成本统计和限流。

## 十二、判断标准

达到产品化可用，至少要满足：

- 用户能从定稿章节一键生成分镜。
- 用户能编辑每个镜头的角色、场景、机位、动作。
- 用户能先预览首帧，再决定是否生成视频。
- 用户能单独重生成失败或不满意的镜头。
- 用户能预览最终视频。
- 用户能下载最终视频。
- 系统能展示每一步成本、状态和失败原因。
- 服务重启后任务不会丢失。

当以上能力完成后，这条链路才算从“可跑通的工程 MVP”升级为“可持续使用的小说视频化产品”。
