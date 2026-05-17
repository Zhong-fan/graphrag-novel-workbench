<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { BatchGenerationChapterTask, ChapterOutline, CharacterCard, DraftVersion, LongformState, MediaAsset, NovelCard, NovelDetail, Project, SeriesPlan, StoryboardShot, VideoTask } from "../../types";

const props = defineProps<{
  project?: Project | null;
  projectTitle?: string;
  loading: boolean;
  state: LongformState;
  characterCards: CharacterCard[];
  managedNovels: NovelCard[];
  currentNovel?: NovelDetail | null;
  preferredSeriesPlanId?: number | null;
  preferredDraftVersionId?: number | null;
  preferredStoryboardId?: number | null;
  preferredVideoTaskId?: number | null;
}>();

const emit = defineEmits<{
  (e: "generate-plan", value: { target_chapter_count: number; user_brief: string }): void;
  (e: "submit-feedback", value: {
    target_type: "series" | "arc" | "chapter";
    target_id: number;
    feedback_text: string;
    feedback_type: string;
    priority: number;
  }): void;
  (e: "lock-plan", seriesPlanId: number): void;
  (e: "restore-plan-version", value: { seriesPlanId: number; versionId: number }): void;
  (e: "batch-generate", value: { series_plan_id: number; start_chapter_no: number; end_chapter_no: number }): void;
  (e: "retry-batch", jobId: number): void;
  (e: "pause-batch", jobId: number): void;
  (e: "resume-batch", jobId: number): void;
  (e: "cancel-batch", jobId: number): void;
  (e: "open-novel", novelId: number): void;
  (e: "create-storyboard", value: { novel_chapter_ids: number[]; title: string }): void;
  (e: "revise-draft", value: { draftVersionId: number; feedback_text: string }): void;
  (e: "canonicalize-draft", value: { draftVersionId: number; novel_id?: number | null; author_name: string; visibility: "public" | "private"; tagline: string }): void;
  (e: "create-video-task", storyboardId: number): void;
  (e: "update-outline", value: { outlineId: number; title: string; outline: Record<string, unknown>; status: string }): void;
  (e: "update-shot", value: {
    storyboardId: number;
    shotId: number;
    narration_text: string;
    visual_prompt: string;
    character_refs: unknown[];
    scene_refs: unknown[];
    audio_script: Record<string, unknown>;
    duration_seconds: number;
    status: string;
  }): void;
  (e: "update-asset", value: { assetId: number; uri: string; status: string; meta: Record<string, unknown> }): void;
  (e: "generate-character-turnaround", value: { character_card_id: number; chapter_no?: number | null; prompt_note: string }): void;
  (e: "generate-shot-first-frame", value: { storyboardId: number; shotId: number }): void;
  (e: "generate-audio-scripts", storyboardId: number): void;
  (e: "generate-storyboard-voice", storyboardId: number): void;
  (e: "prepare-video-production", storyboardId: number): void;
  (e: "generate-shot-voice", value: {
    storyboardId: number;
    shotId: number;
    voice_role?: "narrator" | "dialogue";
    character_card_id?: number | null;
    dialogue_text?: string;
    voice_profile?: string;
    emotion?: string;
  }): void;
  (e: "create-shot", value: {
    storyboardId: number;
    shot_no?: number | null;
    narration_text: string;
    visual_prompt: string;
    character_refs: unknown[];
    scene_refs: unknown[];
    audio_script: Record<string, unknown>;
    duration_seconds: number;
    status: string;
  }): void;
  (e: "delete-shot", value: { storyboardId: number; shotId: number }): void;
  (e: "reorder-shots", value: { storyboardId: number; shot_ids: number[] }): void;
  (e: "update-video-task", value: { taskId: number; task_status: string; output_uri: string; progress: Record<string, unknown>; error_message: string }): void;
  (e: "update-visual-style", value: {
    locked: boolean;
    medium: string;
    artists: string[];
    positive: string[];
    negative: string[];
    notes: string;
  }): void;
}>();

const planForm = reactive({ target_chapter_count: 12, user_brief: "" });
const feedbackForm = reactive({
  target_type: "series" as "series" | "arc" | "chapter",
  target_id: 0,
  feedback_text: "",
  feedback_type: "general",
  priority: 3,
});
const batchForm = reactive({ series_plan_id: 0, start_chapter_no: 1, end_chapter_no: 1 });
const storyboardTitle = ref("");
const selectedNovelChapterIds = ref<number[]>([]);
const selectedDraftVersionId = ref<number | null>(null);
const draftFeedback = ref("");
const canonicalForm = reactive({
  author_name: "",
  visibility: "private" as "public" | "private",
  tagline: "",
});
const outlineEdit = reactive({ id: 0, title: "", outlineText: "", status: "outline_draft" });
const shotEdit = reactive({
  id: 0,
  storyboardId: 0,
  narration_text: "",
  visual_prompt: "",
  duration_seconds: 4,
  status: "draft",
  characterCardIds: [] as number[],
  sceneRefsText: "",
});
const turnaroundForm = reactive({ character_card_id: 0, chapter_no: 1, prompt_note: "" });
const visualStyleForm = reactive({
  locked: true,
  medium: "二维动画电影",
  artistsText: "",
  positiveText: "",
  negativeText: "",
  notes: "",
});
const preview = ref<{ type: "image" | "video" | "audio"; title: string; url: string } | null>(null);
const localError = ref("");

const latestPlan = computed(
  () => props.state.series_plans.find((item) => item.id === props.preferredSeriesPlanId) ?? props.state.series_plans[0] ?? null,
);
const selectedPlan = computed<SeriesPlan | null>(
  () => props.state.series_plans.find((item) => item.id === batchForm.series_plan_id) ?? latestPlan.value,
);
const outlineCount = computed(() => selectedPlan.value?.chapters.length ?? 0);
const lockedOutlineCount = computed(() => selectedPlan.value?.chapters.filter((item) => item.status === "outline_locked").length ?? 0);
const latestBatchJob = computed(() => props.state.batch_jobs[0] ?? null);
const canPauseBatch = computed(() => {
  const status = latestBatchJob.value?.job_status ?? "";
  return ["queued", "retry_queued", "running"].includes(status);
});
const canResumeBatch = computed(() => {
  const status = latestBatchJob.value?.job_status ?? "";
  return ["paused", "pause_requested"].includes(status);
});
const canCancelBatch = computed(() => {
  const status = latestBatchJob.value?.job_status ?? "";
  return ["queued", "retry_queued", "running", "paused", "pause_requested"].includes(status);
});
const canRetryBatch = computed(() => {
  const status = latestBatchJob.value?.job_status ?? "";
  return ["failed", "canceled"].includes(status);
});
const publishedChapters = computed(() => props.currentNovel?.chapters ?? []);
const selectedDraftVersion = computed(
  () =>
    props.state.draft_versions.find((draft) => draft.id === selectedDraftVersionId.value) ??
    props.state.draft_versions.find((draft) => draft.id === props.preferredDraftVersionId) ??
    props.state.draft_versions[0] ??
    null,
);
const latestStoryboard = computed(
  () => props.state.storyboards.find((item) => item.id === props.preferredStoryboardId) ?? props.state.storyboards[0] ?? null,
);
const latestVideoTask = computed(
  () =>
    props.state.video_tasks.find((item) => item.id === props.preferredVideoTaskId) ??
    props.state.video_tasks.find((item) => latestStoryboard.value && item.storyboard_id === latestStoryboard.value.id) ??
    props.state.video_tasks[0] ??
    null,
);
const latestVideoShotProgress = computed(() => {
  const shots = latestVideoTask.value?.progress?.shots;
  return Array.isArray(shots) ? shots.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
});
const latestStoryboardAssets = computed(() => {
  const storyboardId = latestStoryboard.value?.id ?? null;
  if (!storyboardId) return [];
  return props.state.media_assets.filter((asset) => asset.storyboard_id === storyboardId).slice(0, 18);
});
const assetSummary = computed(() => {
  const counts: Record<string, number> = {};
  for (const asset of latestStoryboardAssets.value) {
    counts[asset.asset_type] = (counts[asset.asset_type] ?? 0) + 1;
  }
  return counts;
});
const visualAssets = computed(() => props.state.media_assets.filter((asset) => asset.asset_type.startsWith("character_") || asset.asset_type.startsWith("scene_") || asset.asset_type === "shot_first_frame"));
const videoOutputs = computed(() => props.state.video_tasks.filter((task) => typeof task.progress.public_url === "string" && task.progress.public_url));
const visualStyleSummary = computed(() => {
  const project = props.project;
  const reference = project?.reference_work?.trim() || "";
  const artists = project?.visual_style_artists?.filter(Boolean) ?? [];
  const positive = project?.visual_style_positive?.filter(Boolean) ?? project?.reference_work_style_traits?.filter(Boolean) ?? [];
  const negative = project?.visual_style_negative?.filter(Boolean) ?? [];
  const chips = [
    project?.visual_style_medium || "二维动画电影",
    ...artists.slice(0, 3),
    ...positive.slice(0, 4),
    ...negative.slice(0, 3).map((item) => `避开：${item}`),
  ];
  return {
    reference,
    title: project?.visual_style_locked ? "视觉风格已锁定" : "视觉风格未锁定",
    description: reference
      ? `生成图片和视频时会参考《${reference}》的可迁移视觉特征，并叠加下方作者画风、正向关键词和禁止项。`
      : "生成图片和视频时会使用下方画面媒介、作者画风、正向关键词和禁止项。",
    chips: Array.from(new Set(chips.filter(Boolean))),
  };
});
const feedbackTargets = computed(() => {
  const plan = latestPlan.value;
  if (!plan) return [];
  if (feedbackForm.target_type === "series") {
    return [{ id: plan.id, label: `全书：${plan.title}` }];
  }
  if (feedbackForm.target_type === "arc") {
    return plan.arcs.map((arc) => ({ id: arc.id, label: `阶段 ${arc.arc_no}：${arc.title}` }));
  }
  return plan.chapters.map((chapter) => ({ id: chapter.id, label: `第 ${chapter.chapter_no} 章：${chapter.title}` }));
});

watch(latestPlan, (plan) => {
  if (!plan) return;
  if (!feedbackForm.target_id) feedbackForm.target_id = plan.id;
  batchForm.series_plan_id = plan.id;
  batchForm.start_chapter_no = plan.chapters[0]?.chapter_no ?? 1;
  batchForm.end_chapter_no = plan.chapters[plan.chapters.length - 1]?.chapter_no ?? plan.target_chapter_count;
}, { immediate: true });

watch(selectedDraftVersion, (draft) => {
  selectedDraftVersionId.value = draft?.id ?? null;
}, { immediate: true });

watch(
  () => props.preferredDraftVersionId,
  (draftId) => {
    if (draftId && props.state.draft_versions.some((item) => item.id === draftId)) {
      selectedDraftVersionId.value = draftId;
    }
  },
  { immediate: true },
);

watch(() => props.characterCards, (cards) => {
  if (!cards.length) return;
  if (!turnaroundForm.character_card_id || !cards.some((card) => card.id === turnaroundForm.character_card_id)) {
    turnaroundForm.character_card_id = cards[0].id;
  }
}, { immediate: true });

watch(feedbackTargets, (targets) => {
  if (!targets.length) return;
  if (!targets.some((target) => target.id === feedbackForm.target_id)) {
    feedbackForm.target_id = targets[0].id;
  }
}, { immediate: true });

watch(() => props.project, (project) => {
  visualStyleForm.locked = project?.visual_style_locked ?? true;
  visualStyleForm.medium = project?.visual_style_medium || "二维动画电影";
  visualStyleForm.artistsText = (project?.visual_style_artists ?? []).join("，");
  visualStyleForm.positiveText = (project?.visual_style_positive ?? project?.reference_work_style_traits ?? []).join("，");
  visualStyleForm.negativeText = (project?.visual_style_negative ?? ["真人", "实拍", "三次元", "照片级写实", "文字", "水印", "logo"]).join("，");
  visualStyleForm.notes = project?.visual_style_notes || "";
}, { immediate: true });

function submitFeedback() {
  if (!feedbackForm.target_id && latestPlan.value) feedbackForm.target_id = latestPlan.value.id;
  emit("submit-feedback", { ...feedbackForm, feedback_text: feedbackForm.feedback_text.trim() });
}

function toggleChapter(chapterId: number) {
  selectedNovelChapterIds.value = selectedNovelChapterIds.value.includes(chapterId)
    ? selectedNovelChapterIds.value.filter((item) => item !== chapterId)
    : [...selectedNovelChapterIds.value, chapterId];
}

function normalizeList(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function splitTags(value: string) {
  return value
    .split(/[，,;；\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseServerTime(value: string | undefined | null) {
  if (!value) return null;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function formatRelativeTime(value: string | undefined | null) {
  const date = parseServerTime(value);
  if (!date || Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
  if (diffMinutes < 1) return "刚刚";
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} 天前`;
}

function isLikelyStale(value: string | undefined | null, thresholdMinutes = 10) {
  const date = parseServerTime(value);
  if (!date || Number.isNaN(date.getTime())) return false;
  return Date.now() - date.getTime() > thresholdMinutes * 60000;
}

function saveVisualStyle() {
  if (!props.project) return;
  emit("update-visual-style", {
    locked: visualStyleForm.locked,
    medium: visualStyleForm.medium.trim() || "二维动画电影",
    artists: splitTags(visualStyleForm.artistsText),
    positive: splitTags(visualStyleForm.positiveText),
    negative: splitTags(visualStyleForm.negativeText),
    notes: visualStyleForm.notes.trim(),
  });
}

function reviseSelectedDraft() {
  if (!selectedDraftVersion.value || !draftFeedback.value.trim()) return;
  emit("revise-draft", { draftVersionId: selectedDraftVersion.value.id, feedback_text: draftFeedback.value.trim() });
  draftFeedback.value = "";
}

function canonicalizeSelectedDraft() {
  if (!selectedDraftVersion.value) return;
  emit("canonicalize-draft", {
    draftVersionId: selectedDraftVersion.value.id,
    novel_id: props.currentNovel?.id ?? null,
    author_name: canonicalForm.author_name.trim(),
    visibility: canonicalForm.visibility,
    tagline: canonicalForm.tagline.trim(),
  });
}

function beginEditOutline(chapter: ChapterOutline) {
  outlineEdit.id = chapter.id;
  outlineEdit.title = chapter.title;
  outlineEdit.outlineText = JSON.stringify(chapter.outline, null, 2);
  outlineEdit.status = chapter.status;
}

function saveOutlineEdit() {
  if (!outlineEdit.id) return;
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(outlineEdit.outlineText) as Record<string, unknown>;
  } catch {
    localError.value = "概要 JSON 格式不正确。";
    return;
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    localError.value = "概要 JSON 必须是对象。";
    return;
  }
  localError.value = "";
  emit("update-outline", {
    outlineId: outlineEdit.id,
    title: outlineEdit.title.trim(),
    outline: parsed,
    status: outlineEdit.status,
  });
}

function beginEditShot(storyboardId: number, shot: StoryboardShot) {
  shotEdit.id = shot.id;
  shotEdit.storyboardId = storyboardId;
  shotEdit.narration_text = shot.narration_text;
  shotEdit.visual_prompt = shot.visual_prompt;
  shotEdit.duration_seconds = shot.duration_seconds;
  shotEdit.status = shot.status;
  shotEdit.characterCardIds = shot.character_refs
    .map((item) => {
      if (typeof item === "number") return item;
      if (item !== null && typeof item === "object" && typeof (item as Record<string, unknown>).character_card_id === "number") {
        return Number((item as Record<string, unknown>).character_card_id);
      }
      return null;
    })
    .filter((item): item is number => typeof item === "number" && Number.isInteger(item) && item > 0);
  shotEdit.sceneRefsText = shot.scene_refs
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const value = String((item as Record<string, unknown>).name || (item as Record<string, unknown>).scene_name || "").trim();
        return value;
      }
      return "";
    })
    .filter(Boolean)
    .join("，");
}

function saveShotEdit() {
  if (!shotEdit.id || !shotEdit.storyboardId) return;
  const currentShot = latestStoryboard.value?.shots.find((shot) => shot.id === shotEdit.id) ?? null;
  const characterRefs = shotEdit.characterCardIds
    .map((id) => props.characterCards.find((card) => card.id === id))
    .filter((card): card is CharacterCard => Boolean(card))
    .map((card) => ({
      character_card_id: card.id,
      name: card.name,
      story_role: card.story_role,
      appearance: [card.age, card.gender, card.personality].filter(Boolean).join(" / "),
    }));
  const sceneRefs = splitTags(shotEdit.sceneRefsText).map((name) => ({ scene_name: name }));
  emit("update-shot", {
    storyboardId: shotEdit.storyboardId,
    shotId: shotEdit.id,
    narration_text: shotEdit.narration_text.trim(),
    visual_prompt: shotEdit.visual_prompt.trim(),
    character_refs: characterRefs.length ? characterRefs : currentShot?.character_refs ?? [],
    scene_refs: sceneRefs.length ? sceneRefs : currentShot?.scene_refs ?? [],
    audio_script: currentShot?.audio_script ?? {},
    duration_seconds: shotEdit.duration_seconds,
    status: shotEdit.status,
  });
}

function createShotAfterLast() {
  if (!latestStoryboard.value) return;
  emit("create-shot", {
    storyboardId: latestStoryboard.value.id,
    shot_no: null,
    narration_text: "",
    visual_prompt: "",
    character_refs: [],
    scene_refs: [],
    audio_script: {},
    duration_seconds: 4,
    status: "draft",
  });
}

function deleteShot(shot: StoryboardShot) {
  if (!latestStoryboard.value) return;
  emit("delete-shot", { storyboardId: latestStoryboard.value.id, shotId: shot.id });
}

function moveShot(shot: StoryboardShot, direction: -1 | 1) {
  if (!latestStoryboard.value) return;
  const ordered = [...latestStoryboard.value.shots].sort((a, b) => a.shot_no - b.shot_no);
  const index = ordered.findIndex((item) => item.id === shot.id);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) return;
  const [item] = ordered.splice(index, 1);
  ordered.splice(nextIndex, 0, item);
  emit("reorder-shots", { storyboardId: latestStoryboard.value.id, shot_ids: ordered.map((item) => item.id) });
}

function publicUrl(item: MediaAsset | VideoTask) {
  const record = item as unknown as { progress?: Record<string, unknown>; meta?: Record<string, unknown> };
  const value = record.progress?.public_url ?? record.meta?.public_url;
  return typeof value === "string" ? value : "";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: "排队中",
    retry_queued: "等待重试",
    running: "生成中",
    pause_requested: "准备暂停",
    paused: "已暂停",
    cancel_requested: "准备取消",
    canceled: "已取消",
    completed: "已完成",
    failed: "失败",
    draft: "草稿",
    video_queued: "等待视频生成",
    video_completed: "视频完成",
    video_failed: "视频失败",
    outline_draft: "概要草稿",
    outline_locked: "已锁定",
    draft_generated: "已生成",
    draft_revised: "已重写",
    pending: "待生成",
    processing: "处理中",
    ready: "可用",
    locked: "已锁定",
    published: "已发布",
  };
  return labels[status] ?? status;
}

function eventLabel(type: string) {
  if (type.includes("retry")) return "重新处理";
  if (type.includes("pause_requested")) return "准备暂停";
  if (type.includes("paused")) return "已暂停";
  if (type.includes("cancel_requested")) return "准备取消";
  if (type.includes("canceled")) return "已取消";
  if (type.includes("failed")) return "失败";
  if (type.includes("completed")) return "完成";
  if (type.includes("queued")) return "已排队";
  if (type.includes("running")) return "进行中";
  if (type.includes("started")) return "开始";
  if (type.includes("submit")) return "已提交";
  if (type.includes("poll")) return "等待生成";
  if (type.includes("compose")) return "合成中";
  if (type.includes("image")) return "生成画面";
  if (type.includes("voice")) return "生成音频";
  return "进度";
}

function assetTypeLabel(type: string) {
  const labels: Record<string, string> = {
    image: "镜头图",
    video: "镜头视频",
    voice: "旁白",
    dialogue: "角色对白",
    subtitle: "字幕",
    character_turnaround: "角色三视图",
    shot_first_frame: "首帧",
  };
  return labels[type] ?? type;
}

function audioScript(shot: StoryboardShot) {
  return shot.audio_script || {};
}

function shotDialogues(shot: StoryboardShot) {
  const value = audioScript(shot).dialogues;
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

function shotProgressFor(shotId: number) {
  return latestVideoShotProgress.value.find((item) => Number(item.shot_id || 0) === shotId) ?? null;
}

function shotWarnings(shotId: number) {
  const warnings = shotProgressFor(shotId)?.warnings;
  return Array.isArray(warnings) ? warnings.map((item) => String(item)).filter(Boolean) : [];
}

function progressText(value: unknown) {
  const text = String(value || "").trim();
  return text ? statusLabel(text) : "未开始";
}

function stringList(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function chapterTaskSummary(task: BatchGenerationChapterTask) {
  if (task.error_message) return task.error_message;
  if (task.status === "completed") return "这一章已经生成完成，可在下方章节版本里查看。";
  if (task.status === "failed") return "这一章生成失败，请检查原因后重试。";
  if (task.status === "running") return "这一章正在生成中。";
  if (task.status === "queued" || task.status === "retry_queued") return "这一章已进入等待队列。";
  if (task.status === "canceled") return "这一章已取消。";
  return "这一章正在处理中。";
}

function draftVersionSummary(draft: DraftVersion) {
  if (draft.revision_reason?.trim()) return `重写原因：${draft.revision_reason.trim()}`;
  if (draft.parent_version_id) return "这是基于上一版重写得到的章节版本。";
  return "这是根据已锁定概要生成的章节版本。";
}

function visualAssetSummary(asset: MediaAsset) {
  const subject = String(asset.meta.character_name || asset.meta.scene_name || "").trim();
  const view = String(asset.meta.view || "").trim();
  const locked = asset.meta.locked === true;
  const pieces = [
    subject || "已生成视觉素材",
    view ? `视角：${view}` : "",
    locked ? "已锁定" : "",
  ].filter(Boolean);
  return pieces.join(" / ");
}

function storyboardAssetSummary(asset: MediaAsset) {
  const shotNo = asset.meta.shot_no ? `镜头 ${asset.meta.shot_no}` : "";
  if (asset.asset_type === "dialogue") return [shotNo, "角色对白素材"].filter(Boolean).join(" / ");
  if (asset.asset_type === "voice") return [shotNo, "旁白素材"].filter(Boolean).join(" / ");
  if (asset.asset_type === "subtitle") return [shotNo, "字幕素材"].filter(Boolean).join(" / ");
  if (asset.asset_type === "image") return [shotNo, "画面参考"].filter(Boolean).join(" / ");
  if (asset.asset_type === "video") return [shotNo, "镜头片段"].filter(Boolean).join(" / ");
  return shotNo || "已生成素材";
}

function shotCharacterNames(shot: StoryboardShot) {
  return shot.character_refs
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        return String((item as Record<string, unknown>).name || (item as Record<string, unknown>).character_name || "").trim();
      }
      return "";
    })
    .filter(Boolean);
}

function shotSceneNames(shot: StoryboardShot) {
  return shot.scene_refs
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        return String((item as Record<string, unknown>).scene_name || (item as Record<string, unknown>).name || "").trim();
      }
      return "";
    })
    .filter(Boolean);
}

function shotFirstFrameAsset(shotId: number) {
  return latestStoryboardAssets.value.find((asset) => asset.asset_type === "shot_first_frame" && Number(asset.shot_id || 0) === shotId) ?? null;
}

function videoOutputSummary(task: VideoTask) {
  if (task.error_message?.trim()) return task.error_message.trim();
  if (publicUrl(task)) return "该视频已经可以直接预览。";
  if (typeof task.progress.message === "string" && task.progress.message.trim()) return task.progress.message.trim();
  return "视频已生成，可继续查看详情。";
}

function batchJobSummary() {
  const job = latestBatchJob.value;
  if (!job) return "";
  const summary = typeof job.result_summary.summary === "object" && job.result_summary.summary ? job.result_summary.summary as Record<string, unknown> : {};
  const finished = Number(summary.completed_chapters || job.chapter_tasks.filter((task) => task.status === "completed").length || 0);
  const total = Number(summary.total_chapters || job.chapter_tasks.length || 0);
  const parts = [`最近任务：${statusLabel(job.job_status)}`];
  const currentChapterNo = Number(summary.current_chapter_no || job.current_chapter_no || 0);
  if (currentChapterNo) parts.push(`当前在处理第 ${currentChapterNo} 章`);
  if (total) parts.push(`已完成 ${finished}/${total} 章`);
  const failed = Number(summary.failed_chapters || 0);
  if (failed) parts.push(`失败 ${failed} 章`);
  const heartbeat = formatRelativeTime(String(summary.last_updated_at || "") || job.last_heartbeat_at);
  if (heartbeat && ["running", "pause_requested"].includes(job.job_status)) parts.push(`最近更新：${heartbeat}`);
  if (["running", "pause_requested"].includes(job.job_status) && isLikelyStale(String(summary.last_updated_at || "") || job.last_heartbeat_at)) {
    parts.push("长时间没有新进展，可能卡在当前章节。");
  }
  return parts.join(" / ");
}

function storyboardSummary() {
  if (!latestStoryboard.value) return "";
  const storyboard = latestStoryboard.value;
  const progress = storyboard.progress || {};
  const parts = [`状态：${statusLabel(storyboard.status)}`];
  const shotCount = Number(progress.shot_count || storyboard.shots.length || 0);
  const sourceChapterCount = Number(progress.source_chapter_count || storyboard.source_chapter_ids.length || 0);
  if (sourceChapterCount) parts.push(`来自 ${sourceChapterCount} 个章节`);
  if (shotCount) parts.push(`共 ${shotCount} 个镜头`);
  if (typeof progress.last_event_message === "string" && progress.last_event_message.trim()) {
    parts.push(progress.last_event_message.trim());
  }
  const heartbeat = formatRelativeTime(String(progress.last_updated_at || "") || storyboard.last_heartbeat_at);
  if (heartbeat && storyboard.status === "running") parts.push(`最近更新：${heartbeat}`);
  if (storyboard.status === "running" && isLikelyStale(String(progress.last_updated_at || "") || storyboard.last_heartbeat_at)) {
    parts.push("长时间没有新进展，可能卡在分镜生成。");
  }
  return parts.join(" / ");
}

function storyboardPreflightSummaryText() {
  if (!latestStoryboard.value) return "";
  const raw = latestStoryboard.value.progress?.preflight_summary;
  if (!raw || typeof raw !== "object") return "";
  const summary = raw as Record<string, unknown>;
  const generatedTurnarounds = Array.isArray(summary.generated_character_turnarounds) ? summary.generated_character_turnarounds.length : 0;
  const skippedTurnarounds = Array.isArray(summary.skipped_locked_character_turnarounds) ? summary.skipped_locked_character_turnarounds.length : 0;
  const generatedScripts = summary.generated_audio_scripts === true;
  const skippedScripts = summary.skipped_locked_audio_scripts === true;
  const generatedDialogueAudio = Number(summary.generated_dialogue_audio || 0);
  const skippedDialogueAudio = Number(summary.skipped_locked_dialogue_audio || 0);
  const parts: string[] = [];
  if (generatedTurnarounds) parts.push(`新生成了 ${generatedTurnarounds} 个角色三视图`);
  if (skippedTurnarounds) parts.push(`跳过了 ${skippedTurnarounds} 个已锁定三视图`);
  if (generatedScripts) parts.push("已生成或刷新对白脚本");
  if (skippedScripts) parts.push("已保留锁定的对白脚本");
  if (generatedDialogueAudio) parts.push(`处理了 ${generatedDialogueAudio} 条对白音频`);
  if (skippedDialogueAudio) parts.push(`跳过了 ${skippedDialogueAudio} 条已锁定对白音频`);
  return parts.join(" / ");
}

function shotStepSummary(shotId: number) {
  const progress = shotProgressFor(shotId);
  if (!progress) return "还没有开始处理这个镜头。";
  if (progress.used_first_frame === true) return "这个镜头正在复用已确认首帧继续生成视频。";
  const imageStatus = String(progress.image_status || progress.segment_status || "").trim();
  const dialogueStatus = String(progress.dialogue_status || "").trim();
  const subtitleStatus = String(progress.subtitle_status || "").trim();
  const composedStatus = String(progress.composed_status || "").trim();
  if (composedStatus === "completed") return "这个镜头已经合成完成。";
  if (composedStatus === "failed") return "这个镜头在合成阶段失败。";
  if (dialogueStatus === "failed") return "画面已准备，但对白处理失败。";
  if (dialogueStatus === "missing") return "这个镜头没有可用对白，系统将按无对白镜头继续。";
  if (subtitleStatus === "failed") return "对白已准备，但字幕生成失败。";
  if (subtitleStatus === "completed" && dialogueStatus === "completed") return "对白和字幕已准备，正在等待合成。";
  if (dialogueStatus === "completed") return "对白已生成，正在继续处理字幕或合成。";
  if (imageStatus === "completed") return "画面已生成，正在继续处理对白或字幕。";
  if (imageStatus === "running" || imageStatus === "processing") return "正在生成这个镜头的画面。";
  if (imageStatus === "queued") return "这个镜头已进入生成队列。";
  return "这个镜头正在处理中。";
}

function videoTaskSummary() {
  const task = latestVideoTask.value;
  if (!task) return "";
  const progress = task.progress || {};
  const shotCount = Number(progress.shot_count || 0);
  const audioCount = Number(progress.audio_composed_count || 0);
  const subtitleCount = Number(progress.subtitle_count || 0);
  const shots = Array.isArray(progress.shots) ? progress.shots : [];
  const firstFrameCount = shots.filter((item) => item && typeof item === "object" && (item as Record<string, unknown>).used_first_frame === true).length;
  const parts = [`最近视频任务：${statusLabel(task.task_status)}`];
  if (typeof progress.message === "string" && progress.message.trim()) parts.push(progress.message.trim());
  if (shotCount) parts.push(`共 ${shotCount} 个镜头`);
  if (firstFrameCount) parts.push(`其中 ${firstFrameCount} 个镜头复用了已确认首帧`);
  if (audioCount) parts.push(`已完成 ${audioCount} 个镜头对白混音`);
  if (subtitleCount) parts.push(`已生成 ${subtitleCount} 份字幕`);
  if (task.task_status === "running" && typeof progress.shots === "object" && isLikelyStale(task.updated_at)) {
    parts.push("最近一段时间没有新进展，建议查看下方镜头状态。");
  }
  return parts.join(" / ");
}

function eventTimeLabel(value: string) {
  const text = formatRelativeTime(value);
  return text ? ` · ${text}` : "";
}

function videoTaskActionHint() {
  const task = latestVideoTask.value;
  if (!task) return "";
  const failureStage = String(task.progress.failure_stage || "").trim();
  if (task.task_status === "failed") return "可以先查看失败原因，再重试相关镜头或重新发起任务。";
  if (task.task_status === "completed") return "可以直接预览成片；如果局部不满意，建议回到镜头层修改后再生成。";
  if (task.task_status === "running") return "系统正在持续更新镜头状态，等待完成即可。";
  if (task.task_status === "queued") return "任务已入队，后端会按顺序开始处理。";
  return "";
}

function videoFailureStageText() {
  const task = latestVideoTask.value;
  if (!task || task.task_status !== "failed") return "";
  const stage = String(task.progress.failure_stage || "").trim();
  const labels: Record<string, string> = {
    jimeng_submit: "失败发生在提交视频模型任务时。",
    jimeng_poll: "失败发生在等待视频模型结果时。",
    image_generate: "失败发生在生成镜头画面时。",
    subtitle_generate: "失败发生在生成字幕时。",
    dialogue_merge: "失败发生在整理对白音频时。",
    dialogue_compose: "失败发生在把对白混入镜头时。",
    segment_compose: "失败发生在合成镜头片段时。",
    shot_post_process: "失败发生在镜头后处理阶段。",
    final_concat: "失败发生在最终拼接成片时。",
    video_task: "失败发生在视频任务执行过程中。",
  };
  return labels[stage] || "";
}

function shotActionHint(shot: StoryboardShot) {
  const progress = shotProgressFor(shot.id);
  if (!progress) return "可以先生成这个镜头的画面或对白。";
  const imageStatus = String(progress.image_status || progress.segment_status || "").trim();
  const dialogueStatus = String(progress.dialogue_status || "").trim();
  const subtitleStatus = String(progress.subtitle_status || "").trim();
  const composedStatus = String(progress.composed_status || "").trim();
  if (composedStatus === "failed") return "建议先检查该镜头的对白和字幕，再重新发起视频任务。";
  if (dialogueStatus === "failed") return "建议先重新生成本镜头对白，再继续视频生产。";
  if (dialogueStatus === "missing") return "如果这个镜头应该有对白，建议先补对白脚本并生成本镜头对白。";
  if (subtitleStatus === "failed") return "建议先检查对白内容或字幕生成，再重新合成。";
  if (imageStatus === "failed") return "建议先检查视觉提示词或素材约束，再重新生成镜头画面。";
  if (composedStatus === "completed") return "如果对结果不满意，可以直接编辑这个镜头后重新生成。";
  return "";
}

function isAudioScriptLocked(shot: StoryboardShot) {
  return shot.audio_script?.audio_script_locked === true;
}

function toggleAudioScriptLock(shot: StoryboardShot) {
  if (!latestStoryboard.value) return;
  const nextAudioScript = {
    ...(shot.audio_script || {}),
    audio_script_locked: !isAudioScriptLocked(shot),
  };
  emit("update-shot", {
    storyboardId: latestStoryboard.value.id,
    shotId: shot.id,
    narration_text: shot.narration_text,
    visual_prompt: shot.visual_prompt,
    character_refs: shot.character_refs,
    scene_refs: shot.scene_refs,
    audio_script: nextAudioScript,
    duration_seconds: shot.duration_seconds,
    status: shot.status,
  });
}

function isAssetLocked(asset: MediaAsset) {
  return asset.meta.locked === true;
}

function toggleAssetLock(asset: MediaAsset) {
  emit("update-asset", {
    assetId: asset.id,
    uri: asset.uri,
    status: asset.status,
    meta: {
      ...asset.meta,
      locked: !isAssetLocked(asset),
    },
  });
}

function isImageAsset(asset: MediaAsset) {
  const url = publicUrl(asset).toLowerCase();
  return url.endsWith(".png") || url.endsWith(".jpg") || url.endsWith(".jpeg") || url.endsWith(".webp");
}

function isVideoAsset(asset: MediaAsset) {
  return publicUrl(asset).toLowerCase().endsWith(".mp4");
}

function isAudioAsset(asset: MediaAsset) {
  const url = publicUrl(asset).toLowerCase();
  return url.endsWith(".mp3") || url.endsWith(".wav") || url.endsWith(".m4a") || url.endsWith(".aac") || url.endsWith(".ogg");
}

function openAssetPreview(asset: MediaAsset) {
  const url = publicUrl(asset);
  if (!url) return;
  preview.value = {
    type: isVideoAsset(asset) ? "video" : isAudioAsset(asset) ? "audio" : "image",
    title: `${assetTypeLabel(asset.asset_type)} / ${statusLabel(asset.status)}`,
    url,
  };
}

function openVideoPreview(task: VideoTask) {
  const url = publicUrl(task);
  if (!url) return;
  preview.value = { type: "video", title: "视频预览", url };
}

function generateTurnaround() {
  if (!turnaroundForm.character_card_id) return;
  emit("generate-character-turnaround", {
    character_card_id: turnaroundForm.character_card_id,
    chapter_no: turnaroundForm.chapter_no || null,
    prompt_note: turnaroundForm.prompt_note.trim(),
  });
}
</script>

<template>
  <main class="workspace workspace--longform">
    <section class="panel panel--paper">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">长篇流水线</p>
          <h2>{{ projectTitle || "当前项目" }}</h2>
          <p class="panel-heading__desc">先控概要，再按锁定概要顺序生成正文；已发布章节可进入读后短片分镜。</p>
        </div>
        <div class="hero__stats">
          <span>概要 {{ state.series_plans.length }}</span>
          <span>锁定 {{ lockedOutlineCount }}/{{ outlineCount }}</span>
          <span>分镜 {{ state.storyboards.length }}</span>
        </div>
      </div>
      <form class="form-stack" @submit.prevent="emit('generate-plan', { ...planForm, user_brief: planForm.user_brief.trim() })">
        <div class="inline-row">
          <label class="field">
            <span>目标章节数</span>
            <input v-model.number="planForm.target_chapter_count" type="number" min="3" max="80" />
          </label>
          <label class="field">
            <span>补充方向</span>
            <input v-model="planForm.user_brief" maxlength="4000" placeholder="例如：慢热关系线，前十章不要和解" />
          </label>
        </div>
        <button class="primary-button" :disabled="loading">一键生成小说概要</button>
      </form>
    </section>

    <section class="panel visual-style-panel" v-if="project">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">视觉风格锁定</p>
          <h2>{{ visualStyleSummary.title }}</h2>
          <p class="panel-heading__desc">{{ visualStyleSummary.description }}</p>
        </div>
      </div>
      <div class="style-chip-row">
        <span v-for="chip in visualStyleSummary.chips" :key="chip" class="style-chip">{{ chip }}</span>
      </div>
      <form class="form-stack" @submit.prevent="saveVisualStyle()">
        <label class="field field--check">
          <input v-model="visualStyleForm.locked" type="checkbox" />
          <span>生成图片和视频时强制使用这套视觉风格</span>
        </label>
        <div class="inline-row">
          <label class="field">
            <span>画面媒介</span>
            <input v-model="visualStyleForm.medium" maxlength="80" placeholder="例如：二维动画电影、手绘漫画、水彩插画、写实电影" />
          </label>
          <label class="field">
            <span>作者 / 工作室画风</span>
            <input v-model="visualStyleForm.artistsText" maxlength="1000" placeholder="例如：新海诚画风，宫崎骏画风" />
          </label>
        </div>
        <div class="inline-row">
          <label class="field">
            <span>正向视觉关键词</span>
            <textarea v-model="visualStyleForm.positiveText" rows="3" maxlength="2000" placeholder="例如：雨天城市，天空云层，通透光线，手绘背景，青春感" />
          </label>
          <label class="field">
            <span>禁止项</span>
            <textarea v-model="visualStyleForm.negativeText" rows="3" maxlength="2000" placeholder="例如：真人，实拍，三次元，照片级写实，文字，水印，logo" />
          </label>
        </div>
        <label class="field">
          <span>补充说明</span>
          <textarea v-model="visualStyleForm.notes" rows="3" maxlength="4000" placeholder="说明这部项目的色彩、光线、构图、角色造型和场景质感。" />
        </label>
        <button class="primary-button" :disabled="loading">保存视觉风格</button>
      </form>
    </section>

    <section class="longform-grid">
      <article class="panel" v-if="latestPlan">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">全书概要</p>
            <h2>{{ latestPlan.title }}</h2>
            <p class="panel-heading__desc">{{ latestPlan.theme }}</p>
          </div>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || latestPlan.status === 'locked'" @click="emit('lock-plan', latestPlan.id)">锁定概要</button>
        </div>
        <div class="trace-grid">
          <div><strong>核心冲突</strong><span>{{ latestPlan.main_conflict }}</span></div>
          <div><strong>结局方向</strong><span>{{ latestPlan.ending_direction }}</span></div>
          <div><strong>状态</strong><span>{{ statusLabel(latestPlan.status) }}</span></div>
          <div><strong>版本</strong><span>{{ latestPlan.versions.length }}</span></div>
        </div>
        <div class="card-list longform-version-list" v-if="latestPlan.versions.length">
          <article v-for="version in [...latestPlan.versions].reverse().slice(0, 5)" :key="version.id" class="memory-card">
            <strong>版本 {{ version.version_no }}</strong>
            <span>{{ version.change_note || "无变更说明" }}</span>
            <em>{{ version.created_at }}</em>
            <button
              class="ghost-button ghost-button--small"
              type="button"
              :disabled="loading || version.id === latestPlan.current_version_id"
              @click="emit('restore-plan-version', { seriesPlanId: latestPlan.id, versionId: version.id })"
            >
              恢复此版本
            </button>
          </article>
        </div>
      </article>

      <article class="panel" v-if="latestPlan">
        <div class="panel-heading"><div><p class="panel-heading__kicker">概要修订</p><h2>反馈闭环</h2></div></div>
        <form class="form-stack" @submit.prevent="submitFeedback()">
          <div class="inline-row">
            <label class="field">
              <span>目标层级</span>
              <select v-model="feedbackForm.target_type">
                <option value="series">全书</option>
                <option value="arc">阶段</option>
                <option value="chapter">章节</option>
              </select>
            </label>
            <label class="field">
              <span>目标对象</span>
              <select v-model.number="feedbackForm.target_id">
                <option v-for="target in feedbackTargets" :key="target.id" :value="target.id">{{ target.label }}</option>
              </select>
            </label>
          </div>
          <label class="field"><span>修改意见</span><textarea v-model="feedbackForm.feedback_text" rows="4" maxlength="8000" /></label>
          <button class="primary-button" :disabled="loading || !feedbackForm.feedback_text.trim()">按反馈生成新概要版本</button>
        </form>
      </article>
    </section>

    <section class="panel" v-if="latestPlan">
      <div class="panel-heading"><div><p class="panel-heading__kicker">阶段与章节概要</p><h2>{{ latestPlan.chapters.length }} 章细纲</h2></div></div>
      <div class="longform-outline">
        <article v-for="arc in latestPlan.arcs" :key="arc.id" class="memory-card">
          <strong>阶段 {{ arc.arc_no }}：{{ arc.title }}</strong>
          <span>第 {{ arc.start_chapter_no }}-{{ arc.end_chapter_no }} 章</span>
          <em>{{ arc.goal }}</em>
        </article>
        <article v-for="chapter in latestPlan.chapters" :key="chapter.id" class="memory-card">
          <strong>#{{ chapter.chapter_no }} {{ chapter.title }}</strong>
          <span>{{ statusLabel(chapter.status) }}</span>
          <span>{{ chapter.outline.chapter_goal }}</span>
          <em>{{ normalizeList(chapter.outline.must_happen).join("；") }}</em>
          <button class="ghost-button ghost-button--small" type="button" @click="beginEditOutline(chapter)">编辑概要</button>
        </article>
      </div>
      <form class="form-stack longform-edit-box" v-if="outlineEdit.id" @submit.prevent="saveOutlineEdit()">
        <p v-if="localError" class="empty-text">{{ localError }}</p>
        <div class="inline-row">
          <label class="field"><span>概要标题</span><input v-model="outlineEdit.title" maxlength="255" /></label>
          <label class="field">
            <span>状态</span>
            <select v-model="outlineEdit.status">
              <option value="outline_draft">草稿</option>
              <option value="outline_locked">锁定</option>
            </select>
          </label>
        </div>
        <label class="field"><span>概要 JSON</span><textarea v-model="outlineEdit.outlineText" rows="8" /></label>
        <button class="primary-button" :disabled="loading">保存章节概要</button>
      </form>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">视觉资产</p>
          <h2>角色三视图与镜头参考</h2>
          <p class="panel-heading__desc">先锁定角色和场景资产，再进入首帧与视频生成。</p>
        </div>
      </div>
      <form class="form-stack" @submit.prevent="generateTurnaround()">
        <div class="inline-row">
          <label class="field">
            <span>角色</span>
            <select v-model.number="turnaroundForm.character_card_id">
              <option v-for="card in characterCards" :key="card.id" :value="card.id">{{ card.name }}</option>
            </select>
          </label>
          <label class="field">
            <span>章节</span>
            <input v-model.number="turnaroundForm.chapter_no" type="number" min="1" max="10000" />
          </label>
        </div>
        <label class="field">
          <span>造型补充</span>
          <textarea v-model="turnaroundForm.prompt_note" rows="3" maxlength="2000" placeholder="例如：第1章医院病房与屋顶场景，校服，雨中湿发，疲惫但坚定。" />
        </label>
        <button class="primary-button" :disabled="loading || !turnaroundForm.character_card_id">生成角色三视图</button>
      </form>
      <div class="longform-outline" v-if="visualAssets.length">
        <article v-for="asset in visualAssets" :key="asset.id" class="memory-card">
          <strong>{{ assetTypeLabel(asset.asset_type) }} / {{ statusLabel(asset.status) }}</strong>
          <span>{{ visualAssetSummary(asset) }}</span>
          <div class="mode-switch">
            <button v-if="publicUrl(asset)" class="ghost-button ghost-button--small" type="button" @click="openAssetPreview(asset)">预览</button>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading" @click="toggleAssetLock(asset)">
              {{ isAssetLocked(asset) ? "解锁素材" : "锁定素材" }}
            </button>
          </div>
        </article>
      </div>
      <p v-else class="empty-text">还没有视觉资产。建议先为主角生成三视图。</p>
    </section>

    <section class="longform-grid">
      <article class="panel" v-if="latestPlan">
        <div class="panel-heading"><div><p class="panel-heading__kicker">批量正文</p><h2>顺序生成</h2></div></div>
        <form class="form-stack" @submit.prevent="emit('batch-generate', { ...batchForm })">
          <div class="inline-row">
            <label class="field"><span>起始章</span><input v-model.number="batchForm.start_chapter_no" type="number" min="1" /></label>
            <label class="field"><span>结束章</span><input v-model.number="batchForm.end_chapter_no" type="number" min="1" /></label>
          </div>
          <button class="primary-button" :disabled="loading || latestPlan.status !== 'locked'">一键生成小说内容</button>
        </form>
        <p v-if="latestBatchJob" class="empty-text">{{ batchJobSummary() }}</p>
        <div v-if="latestBatchJob" class="inline-row">
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !canPauseBatch" @click="emit('pause-batch', latestBatchJob.id)">暂停</button>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !canResumeBatch" @click="emit('resume-batch', latestBatchJob.id)">恢复</button>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !canRetryBatch" @click="emit('retry-batch', latestBatchJob.id)">重试</button>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !canCancelBatch" @click="emit('cancel-batch', latestBatchJob.id)">取消</button>
        </div>
        <div v-if="latestBatchJob?.chapter_tasks.length" class="card-list">
          <div v-for="task in latestBatchJob.chapter_tasks" :key="task.id" class="memory-card">
            <strong>第 {{ task.chapter_no }} 章：{{ statusLabel(task.status) }}</strong>
            <span>{{ chapterTaskSummary(task) }}</span>
          </div>
        </div>
        <div v-if="latestBatchJob?.events.length" class="card-list">
          <div v-for="event in latestBatchJob.events.slice(-4)" :key="event.id" class="memory-card">
            <strong>{{ eventLabel(event.event_type) }}<span>{{ eventTimeLabel(event.created_at) }}</span></strong>
            <span>{{ event.message }}</span>
          </div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-heading"><div><p class="panel-heading__kicker">选章视频化</p><h2>读后短片分镜</h2></div></div>
        <div class="form-stack">
          <label class="field">
            <span>已发布作品</span>
            <select :value="currentNovel?.id || ''" @change="emit('open-novel', Number(($event.target as HTMLSelectElement).value))">
              <option value="" disabled>选择作品</option>
              <option v-for="novel in managedNovels" :key="novel.id" :value="novel.id">{{ novel.title }}</option>
            </select>
          </label>
          <label class="field"><span>短片标题</span><input v-model="storyboardTitle" maxlength="255" /></label>
          <div class="card-list" v-if="publishedChapters.length">
            <label v-for="chapter in publishedChapters" :key="chapter.id" class="memory-card memory-card--select">
              <input type="checkbox" :checked="selectedNovelChapterIds.includes(chapter.id)" @change="toggleChapter(chapter.id)" />
              <strong>#{{ chapter.chapter_no }} {{ chapter.title }}</strong>
              <span>{{ chapter.summary }}</span>
            </label>
          </div>
          <p v-else class="empty-text">只有已发布/定稿章节可生成分镜。</p>
          <button class="primary-button" :disabled="loading || !selectedNovelChapterIds.length" @click="emit('create-storyboard', { novel_chapter_ids: selectedNovelChapterIds, title: storyboardTitle.trim() })">生成分镜稿</button>
        </div>
      </article>
    </section>

    <section class="panel" v-if="state.draft_versions.length">
      <div class="panel-heading"><div><p class="panel-heading__kicker">章节版本</p><h2>批量生成草稿</h2></div></div>
      <div class="longform-grid">
        <div class="card-list">
          <button
            v-for="draft in state.draft_versions.slice(0, 12)"
            :key="draft.id"
            class="memory-card memory-card--button"
            type="button"
            @click="selectedDraftVersionId = draft.id"
          >
            <strong>v{{ draft.version_no }} {{ draft.title }}</strong>
            <span>{{ statusLabel(draft.status) }}</span>
            <span>{{ draftVersionSummary(draft) }}</span>
            <em>{{ draft.summary }}</em>
          </button>
        </div>
        <div class="form-stack" v-if="selectedDraftVersion">
          <label class="field"><span>重写反馈</span><textarea v-model="draftFeedback" rows="4" maxlength="8000" /></label>
          <button class="primary-button" :disabled="loading || !draftFeedback.trim()" @click="reviseSelectedDraft()">全章重写生成新版本</button>
          <div class="inline-row">
            <label class="field"><span>作者名</span><input v-model="canonicalForm.author_name" maxlength="100" /></label>
            <label class="field">
              <span>可见性</span>
              <select v-model="canonicalForm.visibility">
                <option value="private">私密</option>
                <option value="public">公开</option>
              </select>
            </label>
          </div>
          <label class="field"><span>作品标语</span><input v-model="canonicalForm.tagline" maxlength="255" /></label>
          <button class="ghost-button" type="button" :disabled="loading" @click="canonicalizeSelectedDraft()">定稿为正式章节</button>
        </div>
      </div>
    </section>

    <section class="panel" v-if="latestStoryboard">
      <div class="panel-heading">
        <div><p class="panel-heading__kicker">分镜稿</p><h2>{{ latestStoryboard.title }}</h2></div>
        <div class="mode-switch">
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading" @click="createShotAfterLast()">新增镜头</button>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !latestStoryboard.shots.length" @click="emit('generate-audio-scripts', latestStoryboard.id)">从正文生成对白脚本</button>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !latestStoryboard.shots.length" @click="emit('generate-storyboard-voice', latestStoryboard.id)">生成全部角色对白</button>
          <button class="primary-button primary-button--small" type="button" :disabled="loading || !latestStoryboard.shots.length" @click="emit('prepare-video-production', latestStoryboard.id)">准备并开始视频生产</button>
          <button class="ghost-button ghost-button--small" type="button" :disabled="loading || latestStoryboard.status !== 'draft' || !latestStoryboard.shots.length" @click="emit('create-video-task', latestStoryboard.id)">创建视频导出任务</button>
        </div>
      </div>
      <p class="empty-text">{{ storyboardSummary() }}</p>
      <p v-if="storyboardPreflightSummaryText()" class="empty-text">{{ storyboardPreflightSummaryText() }}</p>
      <p v-if="latestStoryboard.error_message" class="empty-text">{{ latestStoryboard.error_message }}</p>
      <div v-if="latestStoryboard.events.length" class="card-list">
        <div v-for="event in latestStoryboard.events.slice(-4)" :key="event.id" class="memory-card">
          <strong>{{ eventLabel(event.event_type) }}<span>{{ eventTimeLabel(event.created_at) }}</span></strong>
          <span>{{ event.message }}</span>
        </div>
      </div>
      <div class="longform-outline">
        <article v-for="shot in latestStoryboard.shots" :key="shot.id" class="memory-card">
          <strong>镜头 {{ shot.shot_no }} / {{ shot.duration_seconds }}s</strong>
          <span>{{ shot.narration_text }}</span>
          <em>{{ shot.visual_prompt }}</em>
          <div v-if="shotProgressFor(shot.id)" class="card-list">
            <div class="memory-card">
              <strong>画面</strong>
              <span>{{ progressText(shotProgressFor(shot.id)?.image_status) }}</span>
            </div>
            <div class="memory-card">
              <strong>对白</strong>
              <span>{{ progressText(shotProgressFor(shot.id)?.dialogue_status) }}</span>
            </div>
            <div class="memory-card">
              <strong>字幕</strong>
              <span>{{ progressText(shotProgressFor(shot.id)?.subtitle_status) }}</span>
            </div>
            <div class="memory-card">
              <strong>合成</strong>
              <span>{{ progressText(shotProgressFor(shot.id)?.composed_status) }}</span>
            </div>
          </div>
          <p v-if="shotProgressFor(shot.id)" class="empty-text">{{ shotStepSummary(shot.id) }}</p>
          <p v-for="warning in shotWarnings(shot.id)" :key="warning" class="empty-text">{{ warning }}</p>
          <p v-if="shotActionHint(shot)" class="empty-text">{{ shotActionHint(shot) }}</p>
          <span v-if="shotCharacterNames(shot).length">角色：{{ shotCharacterNames(shot).join("，") }}</span>
          <span v-if="shotSceneNames(shot).length">场景：{{ shotSceneNames(shot).join("，") }}</span>
          <p v-if="shotFirstFrameAsset(shot.id)" class="empty-text">
            首帧：{{ isAssetLocked(shotFirstFrameAsset(shot.id)!) ? "已锁定" : "未锁定" }}
          </p>
          <div class="card-list" v-if="shotDialogues(shot).length">
            <div v-for="(dialogue, index) in shotDialogues(shot)" :key="index" class="memory-card">
              <strong>{{ dialogue.character_name || "角色" }} / {{ dialogue.emotion || "novel_dialog" }}</strong>
              <span>{{ dialogue.line }}</span>
            </div>
          </div>
          <span v-if="audioScript(shot).music_cue">BGM：{{ audioScript(shot).music_cue }}</span>
          <span v-if="stringList(audioScript(shot).sound_effects).length">音效：{{ stringList(audioScript(shot).sound_effects).join("，") }}</span>
          <div class="mode-switch">
            <button class="ghost-button ghost-button--small" type="button" @click="moveShot(shot, -1)">上移</button>
            <button class="ghost-button ghost-button--small" type="button" @click="moveShot(shot, 1)">下移</button>
            <button class="ghost-button ghost-button--small" type="button" @click="beginEditShot(latestStoryboard.id, shot)">编辑</button>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading" @click="emit('generate-shot-first-frame', { storyboardId: latestStoryboard.id, shotId: shot.id })">
              生成首帧
            </button>
            <button
              v-if="shotFirstFrameAsset(shot.id) && publicUrl(shotFirstFrameAsset(shot.id)!)"
              class="ghost-button ghost-button--small"
              type="button"
              @click="openAssetPreview(shotFirstFrameAsset(shot.id)!)"
            >
              预览首帧
            </button>
            <button
              v-if="shotFirstFrameAsset(shot.id)"
              class="ghost-button ghost-button--small"
              type="button"
              :disabled="loading"
              @click="toggleAssetLock(shotFirstFrameAsset(shot.id)!)"
            >
              {{ isAssetLocked(shotFirstFrameAsset(shot.id)!) ? "解锁首帧" : "锁定首帧" }}
            </button>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading" @click="toggleAudioScriptLock(shot)">
              {{ isAudioScriptLocked(shot) ? "解锁对白脚本" : "锁定对白脚本" }}
            </button>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !shotDialogues(shot).length" @click="emit('generate-shot-voice', { storyboardId: latestStoryboard.id, shotId: shot.id, voice_role: 'dialogue' })">生成本镜头对白</button>
            <button class="ghost-button ghost-button--small" type="button" @click="deleteShot(shot)">删除</button>
          </div>
        </article>
      </div>
      <form class="form-stack longform-edit-box" v-if="shotEdit.id" @submit.prevent="saveShotEdit()">
        <label class="field"><span>旁白 / 字幕</span><textarea v-model="shotEdit.narration_text" rows="3" maxlength="8000" /></label>
        <label class="field"><span>画面提示词</span><textarea v-model="shotEdit.visual_prompt" rows="4" maxlength="8000" /></label>
        <label class="field">
          <span>关联角色</span>
          <select v-model="shotEdit.characterCardIds" multiple>
            <option v-for="card in characterCards" :key="card.id" :value="card.id">{{ card.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>场景引用</span>
          <input v-model="shotEdit.sceneRefsText" maxlength="1000" placeholder="例如：医院病房，医院屋顶，朱红鸟居" />
        </label>
        <div class="inline-row">
          <label class="field"><span>时长</span><input v-model.number="shotEdit.duration_seconds" type="number" min="0.5" max="60" step="0.5" /></label>
          <label class="field"><span>状态</span><input v-model="shotEdit.status" maxlength="40" /></label>
        </div>
        <button class="primary-button" :disabled="loading">保存镜头</button>
      </form>
      <p v-if="latestVideoTask" class="empty-text">{{ videoTaskSummary() }}</p>
      <p v-if="latestVideoTask && latestStoryboardAssets.length" class="empty-text">
        当前已准备：画面 {{ assetSummary.image || 0 }} 份，对白 {{ assetSummary.dialogue || 0 }} 份，旁白 {{ assetSummary.voice || 0 }} 份，字幕 {{ assetSummary.subtitle || 0 }} 份。
      </p>
      <p v-if="latestVideoTask && videoTaskActionHint()" class="empty-text">{{ videoTaskActionHint() }}</p>
      <p v-if="videoFailureStageText()" class="empty-text">{{ videoFailureStageText() }}</p>
      <p
        v-if="latestVideoTask?.task_status === 'running' && latestVideoTask.updated_at && isLikelyStale(latestVideoTask.updated_at)"
        class="empty-text"
      >
        这个任务已经有一段时间没有新进展了。建议先看下方最近事件和镜头状态，确认卡在哪一步。
      </p>
      <div v-if="latestVideoTask && publicUrl(latestVideoTask)" class="mode-switch">
        <button class="ghost-button ghost-button--small" type="button" @click="openVideoPreview(latestVideoTask)">预览视频</button>
      </div>
      <p v-if="latestVideoTask?.error_message" class="empty-text">{{ latestVideoTask.error_message }}</p>
      <div v-if="latestVideoTask?.events.length" class="card-list">
        <div v-for="event in latestVideoTask.events.slice(-4)" :key="event.id" class="memory-card">
          <strong>{{ eventLabel(event.event_type) }}<span>{{ eventTimeLabel(event.created_at) }}</span></strong>
          <span>{{ event.message }}</span>
        </div>
      </div>
      <div class="longform-outline" v-if="latestStoryboardAssets.length">
        <article v-for="asset in latestStoryboardAssets" :key="asset.id" class="memory-card">
          <strong>{{ assetTypeLabel(asset.asset_type) }} / {{ statusLabel(asset.status) }}</strong>
          <span>{{ storyboardAssetSummary(asset) }}</span>
          <div class="mode-switch">
            <button v-if="publicUrl(asset)" class="ghost-button ghost-button--small" type="button" @click="openAssetPreview(asset)">{{ asset.asset_type === "voice" || asset.asset_type === "dialogue" ? "试听" : "预览" }}</button>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading" @click="toggleAssetLock(asset)">
              {{ isAssetLocked(asset) ? "解锁素材" : "锁定素材" }}
            </button>
          </div>
        </article>
      </div>
    </section>
    <section class="panel" v-if="videoOutputs.length">
      <div class="panel-heading"><div><p class="panel-heading__kicker">视频产物</p><h2>已完成输出</h2></div></div>
      <div class="longform-outline">
        <article v-for="task in videoOutputs" :key="task.id" class="memory-card">
          <strong>成片 / {{ statusLabel(task.task_status) }}</strong>
          <span>{{ videoOutputSummary(task) }}</span>
          <button class="ghost-button ghost-button--small" type="button" @click="openVideoPreview(task)">预览视频</button>
        </article>
      </div>
    </section>

    <div v-if="preview" class="asset-modal" role="dialog" aria-modal="true" @click.self="preview = null">
      <div class="asset-modal__body">
        <div class="panel-heading">
          <div><p class="panel-heading__kicker">预览</p><h2>{{ preview.title }}</h2></div>
          <button class="ghost-button ghost-button--small" type="button" @click="preview = null">关闭</button>
        </div>
        <img v-if="preview.type === 'image'" class="asset-preview asset-preview--image" :src="preview.url" alt="" />
        <audio v-else-if="preview.type === 'audio'" class="asset-preview asset-preview--audio" :src="preview.url" controls />
        <video v-else class="asset-preview asset-preview--video" :src="preview.url" controls playsinline />
      </div>
    </div>
  </main>
</template>
