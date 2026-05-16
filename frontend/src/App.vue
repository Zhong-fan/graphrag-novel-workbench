<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import AuthModal from "./components/auth/AuthModal.vue";
import LongformPipelinePanel from "./components/workspace/LongformPipelinePanel.vue";
import NovelEditorPanel from "./components/workspace/NovelEditorPanel.vue";
import GenerationTracePanel from "./components/workspace/GenerationTracePanel.vue";
import ProjectCreateWizard from "./components/workspace/ProjectCreateWizard.vue";
import ProjectWorkshopPanel from "./components/workspace/ProjectWorkshopPanel.vue";
import ProjectSettingsPanel from "./components/workspace/ProjectSettingsPanel.vue";
import StudioWorkspacePanel from "./components/workspace/StudioWorkspacePanel.vue";
import { useAuthFlow } from "./composables/useAuthFlow";
import { useWorkbenchStore } from "./stores/workbench";
import type { CharacterCard, ProjectChapter, ProjectCreateDraft, ProjectPayload, ReferenceWorkResolved, TrashItem, ViewKey } from "./types";

const store = useWorkbenchStore();
const {
  captcha,
  currentUser,
  projects,
  trashItems,
  myNovels,
  currentNovel,
  activeProject,
  currentGeneration,
  longformState,
  generationProgress,
  loading,
  error,
  success,
  isAuthenticated,
} = storeToRefs(store);

const currentView = ref<ViewKey>("studio");
const authError = ref("");
const workspaceSearch = ref("");
const showPublishPanel = ref(false);
const showAppendPanel = ref(false);
const workspacePage = ref(1);
const workspacePageSize = ref(6);
const hasRestoredViewState = ref(false);
const mobileSidebarOpen = ref(false);
let feedbackTimer: number | null = null;
const persistedViewKey = "graph_mvp_current_view";
const persistedProjectIdKey = "graph_mvp_active_project_id";
const persistedProjectChapterIdKey = "graph_mvp_selected_project_chapter_id";
const persistedNovelChapterIdKey = "graph_mvp_selected_novel_chapter_id";
const generationPromptDraftPrefix = "graph_mvp_generation_prompt_";
const restorableViews: ViewKey[] = [
  "studio",
  "trash",
  "projectCreate",
  "projectSettings",
  "characters",
  "longform",
  "workshop",
];

type GenreOptionCard = {
  value: string;
  label: string;
  description: string;
};

const genreOptionCards: GenreOptionCard[] = [
  { value: "现代都市", label: "现代都市", description: "适合现实背景、职场、情感和城市成长线。" },
  { value: "校园青春", label: "校园青春", description: "适合学生视角、关系推进和轻微成长痛感。" },
  { value: "都市异能", label: "都市异能", description: "现实都市里加入超能力、怪异规则或隐秘秩序。" },
  { value: "悬疑推理", label: "悬疑推理", description: "适合线索、反转、调查和因果还原。" },
  { value: "幻想冒险", label: "幻想冒险", description: "适合地图推进、世界探索、伙伴关系和成长线。" },
  { value: "东方幻想", label: "东方幻想", description: "适合修行体系、宗门势力和世界层级扩展。" },
  { value: "治愈日常", label: "治愈日常", description: "适合陪伴感、生活流、修复关系和缓慢推进。" },
];

const genreOptions = genreOptionCards.map((item) => item.value);

const styleProfileOptions = [
  {
    value: "light_novel",
    label: "轻小说",
    description: "轻快、易读、偏人物互动，适合多数网络连载起步。",
    bullets: ["优先人物互动", "句子更轻", "每段都要推进场景或关系"],
  },
  {
    value: "lyrical_restrained",
    label: "抒情克制",
    description: "更细腻，允许少量意象和情绪潜流，但不走厚重散文。",
    bullets: ["允许细腻情绪", "意象少而准", "不能只有氛围没有动作"],
  },
  {
    value: "dialogue_driven",
    label: "对白驱动",
    description: "靠人物说话和来回拉扯推进，节奏更明快。",
    bullets: ["优先对话推进", "减少解释型旁白", "每段带来关系或信息变化"],
  },
  {
    value: "cinematic_tense",
    label: "影视化紧张",
    description: "画面感强，段落更短，适合悬疑、冲突和追逐场景。",
    bullets: ["写清动作顺序", "空间位置明确", "保持压力和推进"],
  },
  {
    value: "warm_healing",
    label: "温柔治愈",
    description: "语气柔和，生活感更强，适合日常、陪伴和情感修复。",
    bullets: ["强化日常细节", "语言柔和自然", "优先可信的陪伴感"],
  },
  {
    value: "epic_serious",
    label: "厚重史诗",
    description: "叙述更稳、更庄重，适合幻想、历史和大设定冲突。",
    bullets: ["先交代局势和代价", "庄重但不堆辞藻", "服务更大的冲突与秩序"],
  },
];

function inferStyleProfileFromReference(payload: ReferenceWorkResolved): ProjectPayload["style_profile"] {
  const haystack = [
    payload.medium,
    payload.synopsis,
    payload.confidence_note,
    ...payload.style_traits,
    ...payload.world_traits,
    ...payload.narrative_constraints,
  ]
    .join(" ")
    .toLowerCase();

  if (/(悬疑|惊悚|紧张|thriller|mystery|crime|suspense)/.test(haystack)) return "cinematic_tense";
  if (/(对白|对话|conversation|dialogue)/.test(haystack)) return "dialogue_driven";
  if (/(治愈|温柔|日常|陪伴|healing|slice of life|comfort)/.test(haystack)) return "warm_healing";
  if (/(史诗|战争|历史|秩序|文明|王朝|epic|historical)/.test(haystack)) return "epic_serious";
  if (/(轻小说|校园|青春|恋爱|anime|轻快|少年)/.test(haystack)) return "light_novel";
  return "lyrical_restrained";
}

function inferGenreFromReference(payload: ReferenceWorkResolved): string {
  const haystack = [
    payload.medium,
    payload.synopsis,
    payload.confidence_note,
    ...payload.style_traits,
    ...payload.world_traits,
    ...payload.narrative_constraints,
  ].join(" ");

  const mappings: Array<{ pattern: RegExp; genre: string }> = [
    { pattern: /(校园|青春|学生|社团|学园)/, genre: "校园青春" },
    { pattern: /(都市|现代|职场|都会)/, genre: "现代都市" },
    { pattern: /(异能|超能力)/, genre: "都市异能" },
    { pattern: /(悬疑|推理|案件|侦探|谜团)/, genre: "悬疑推理" },
    { pattern: /(幻想|冒险|魔法|旅途)/, genre: "幻想冒险" },
    { pattern: /(东方幻想|修行|宗门|灵气|仙侠)/, genre: "东方幻想" },
    { pattern: /(治愈|日常|陪伴|生活流)/, genre: "治愈日常" },
  ];

  return mappings.find((item) => item.pattern.test(haystack))?.genre ?? "现代都市";
}

function buildReferenceWorldBrief(payload: ReferenceWorkResolved): string {
  const worldTraits = payload.world_traits.slice(0, 4);
  const constraints = payload.narrative_constraints.slice(0, 2);
  const parts = [
    payload.synopsis ? `整体项目世界气质参考《${payload.canonical_title}》：${payload.synopsis}` : "",
    worldTraits.length ? `优先保留这些可迁移的世界特征：${worldTraits.join("；")}。` : "",
    constraints.length ? `创作时只借鉴方法，不直接照搬原作设定：${constraints.join("；")}。` : "",
  ].filter(Boolean);
  return parts.join("\n\n");
}

function buildReferenceWritingRules(payload: ReferenceWorkResolved): string {
  const styleTraits = payload.style_traits.slice(0, 4);
  const constraints = payload.narrative_constraints.slice(0, 3);
  const parts = [
    styleTraits.length ? `文风默认参考这些方向：${styleTraits.join("；")}。` : "",
    "保留参考作品的节奏、情绪组织和人物互动方法，但不要直接复用角色名、剧情节点或专有设定名词。",
    constraints.length ? `写作边界：${constraints.join("；")}。` : "",
  ].filter(Boolean);
  return parts.join("\n\n");
}

const emptyProject = (): ProjectPayload => ({
  title: "",
  genre: "现代都市",
  reference_work: "",
  reference_work_creator: "",
  reference_work_medium: "",
  reference_work_synopsis: "",
  reference_work_style_traits: [],
  reference_work_world_traits: [],
  reference_work_narrative_constraints: [],
  reference_work_confidence_note: "",
  world_brief: "",
  writing_rules: "",
  style_profile: "lyrical_restrained",
});

const emptyProjectDraft = (): ProjectCreateDraft => ({
  ...emptyProject(),
  reference_work_confirmed: false,
});

const projectForm = reactive<ProjectCreateDraft>(emptyProjectDraft());
const projectSettingsForm = reactive<ProjectPayload>(emptyProject());
const projectCreateStep = ref<1 | 2 | 3>(1);
const referenceWorkInput = ref("");
const referenceWorkResolved = ref<ReferenceWorkResolved | null>(null);
const assistantLoadingKind = ref<"world_brief" | "writing_rules" | "reference_work" | null>(null);
const assistantSeedWorld = ref("");
const assistantSeedWriting = ref("");
const worldSuggestions = ref<string[]>([]);
const writingSuggestions = ref<string[]>([]);
const projectChapterForm = reactive({ title: "", premise: "", chapter_no: 1 });
const projectChapterEditForm = reactive({ title: "", premise: "", chapter_no: 1 });

const characterForm = reactive({
  name: "",
  age: "",
  gender: "",
  personality: "",
  story_role: "",
  background: "",
});
const editingCharacterId = ref<number | null>(null);

const generationForm = reactive({
  chapter_id: 0,
  prompt: "",
  search_method: "direct",
  response_type: "Multiple Paragraphs",
  use_global_search: false,
  use_scene_card: true,
  use_refiner: true,
  write_evolution: true,
});

const publishForm = reactive({
  title: "",
  author_name: "",
  summary: "",
  tagline: "",
  visibility: "public" as "public" | "private",
});
const manageNovelForm = reactive({
  title: "",
  author_name: "",
  summary: "",
  tagline: "",
  visibility: "public" as "public" | "private",
});
const appendChapterForm = reactive({ title: "", chapter_no: 1 });
const draftForm = reactive({ title: "", summary: "", content: "", chapter_no: 1 });
const chapterEditForm = reactive({ title: "", summary: "", content: "", chapter_no: 1 });

const selectedChapterId = ref<number | null>(null);
const selectedDraftGenerationId = ref<number | null>(null);
const selectedSettingsProjectId = ref<number | null>(null);
const selectedProjectChapterId = ref<number | null>(null);
const workshopMode = ref<"chapters" | "drafts">("chapters");

const hasProject = computed(() => Boolean(activeProject.value));
const filteredWorkspaceProjects = computed(() => {
  const keyword = workspaceSearch.value.trim().toLowerCase();
  if (!keyword) return projects.value;
  return projects.value.filter((project) =>
    [project.title, project.genre, project.world_brief, project.writing_rules].join(" ").toLowerCase().includes(keyword),
  );
});
const workspaceTotalPages = computed(() => Math.max(1, Math.ceil(filteredWorkspaceProjects.value.length / workspacePageSize.value)));
const pagedWorkspaceProjects = computed(() => {
  const start = (workspacePage.value - 1) * workspacePageSize.value;
  return filteredWorkspaceProjects.value.slice(start, start + workspacePageSize.value);
});
const trashSummary = computed<Record<TrashItem["item_type"], number>>(() => ({
  project: trashItems.value.filter((item) => item.item_type === "project").length,
  novel: trashItems.value.filter((item) => item.item_type === "novel").length,
  character_card: trashItems.value.filter((item) => item.item_type === "character_card").length,
  dirty_evolution: trashItems.value.filter((item) => item.item_type === "dirty_evolution").length,
}));
const managedNovels = computed(() => {
  const activeProjectId = activeProject.value?.project.id ?? null;
  const source = activeProjectId
    ? myNovels.value.filter((novel) => novel.project_id === activeProjectId)
    : myNovels.value;
  return [...source].sort((a, b) => parseServerTime(b.updated_at).getTime() - parseServerTime(a.updated_at).getTime());
});
const activeProjectNovel = computed(() => managedNovels.value[0] ?? null);
const hasPublishedNovelForProject = computed(() => Boolean(activeProjectNovel.value));
const isManagingCurrentNovel = computed(() =>
  Boolean(currentNovel.value && myNovels.value.some((item) => item.id === currentNovel.value?.id)),
);
const sortedChapters = computed(() => [...(currentNovel.value?.chapters ?? [])].sort((a, b) => a.chapter_no - b.chapter_no));
const selectedChapter = computed(() => {
  if (!sortedChapters.value.length) return null;
  return sortedChapters.value.find((chapter) => chapter.id === selectedChapterId.value) ?? sortedChapters.value[0] ?? null;
});
const projectChapters = computed(() =>
  [...(activeProject.value?.project_chapters ?? [])].sort((a, b) => a.chapter_no - b.chapter_no),
);
const selectedProjectChapter = computed(() => {
  if (!projectChapters.value.length) return null;
  return projectChapters.value.find((chapter) => chapter.id === selectedProjectChapterId.value) ?? projectChapters.value[0] ?? null;
});
const nextNovelChapterNo = computed(() =>
  currentNovel.value ? Math.max(0, ...currentNovel.value.chapters.map((chapter) => chapter.chapter_no)) + 1 : 1,
);
const chapterDrafts = computed(() => {
  const chapterId = selectedProjectChapter.value?.id ?? null;
  if (!chapterId) return [];
  return (activeProject.value?.generations ?? []).filter((item) => item.project_chapter_id === chapterId);
});
const selectedDraftGeneration = computed(() => {
  if (!chapterDrafts.value.length) return null;
  return chapterDrafts.value.find((item) => item.id === selectedDraftGenerationId.value) ?? chapterDrafts.value[0] ?? null;
});
const draftWordCount = computed(() => draftForm.content.replace(/\s+/g, "").length);
const currentStep = computed(() => {
  if (!isAuthenticated.value) return "先创建账号，再开始搭建你的创作工作台。";
  if (!hasProject.value) return "先新建项目，确定标题、题材和世界设定。";
  if (!(activeProject.value?.character_cards.length ?? 0)) return "先补充主要人物卡，再开始规划章节。";
  if (!selectedProjectChapter.value) return "先新建一个章节，写清这一章的故事前提。";
  return "选中章节后输入这一章想怎么写，草稿会进入当前章节的草稿箱。";
});

const {
  authMode,
  authFieldErrors,
  openAuthPanel,
  closeAuthPanel,
  clearAuthFeedback,
  submitRegister,
  submitLogin,
} = useAuthFlow({
  currentView,
  authError,
  error,
  isAuthenticated,
  captcha,
  refreshCaptcha: () => store.refreshCaptcha(),
  login: (payload) => store.login(payload),
  register: (payload) => store.register(payload),
  clearFeedback: () => store.clearFeedback(),
});

function goToView(view: ViewKey) {
  if (view === "projectCreate" && !isAuthenticated.value) {
    openAuthPanel("register", view);
    return;
  }
  if (view !== "auth" && !isAuthenticated.value && ["studio", "trash", "projectSettings", "characters", "longform", "workshop", "generationTrace", "novelEditor"].includes(view)) {
    openAuthPanel("login", view);
    return;
  }
  currentView.value = view;
  mobileSidebarOpen.value = false;
}

function formatDateTime(value: string | undefined) {
  if (!value) return "-";
  return parseServerTime(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function projectStatusLabel(status: string | undefined) {
  if (!status) return "未开始";
  if (status === "ready") return "可继续创作";
  if (status === "stale") return "待同步最新设定";
  return status;
}

function readPersistedNumber(key: string) {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function persistView(view: ViewKey) {
  if (view === "auth" || !hasRestoredViewState.value) return;
  localStorage.setItem(persistedViewKey, view);
}

function generationPromptDraftKey(chapterId: number) {
  return `${generationPromptDraftPrefix}${chapterId}`;
}

function loadGenerationPromptDraft(chapterId: number | null | undefined) {
  if (!chapterId) return "";
  return localStorage.getItem(generationPromptDraftKey(chapterId)) ?? "";
}

function saveGenerationPromptDraft() {
  const chapterId = selectedProjectChapter.value?.id ?? null;
  if (!chapterId) return;
  localStorage.setItem(generationPromptDraftKey(chapterId), generationForm.prompt);
  success.value = "这一章的写法提示已保存。";
}

async function restoreViewState() {
  if (!isAuthenticated.value) {
    currentView.value = "studio";
    hasRestoredViewState.value = true;
    return;
  }

  const persistedProjectId = readPersistedNumber(persistedProjectIdKey);
  if (persistedProjectId && projects.value.some((project) => project.id === persistedProjectId)) {
    await store.selectProject(persistedProjectId, { showLoading: false, silent: true });
  }

  const persistedProjectChapterId = readPersistedNumber(persistedProjectChapterIdKey);
  if (persistedProjectChapterId && projectChapters.value.some((chapter) => chapter.id === persistedProjectChapterId)) {
    selectedProjectChapterId.value = persistedProjectChapterId;
  }

  const persistedNovelChapterId = readPersistedNumber(persistedNovelChapterIdKey);
  if (persistedNovelChapterId) {
    selectedChapterId.value = persistedNovelChapterId;
  }

  const persistedView = localStorage.getItem(persistedViewKey) as ViewKey | null;
  if (persistedView && restorableViews.includes(persistedView)) {
    currentView.value = persistedView;
  }
  hasRestoredViewState.value = true;
}

function clearToasts() {
  authError.value = "";
  clearAuthFeedback();
}

function syncProjectSettingsForm() {
  const project = activeProject.value?.project;
  if (!project) return;
  projectSettingsForm.title = project.title;
  projectSettingsForm.genre = project.genre;
  projectSettingsForm.reference_work = project.reference_work;
  projectSettingsForm.reference_work_creator = project.reference_work_creator;
  projectSettingsForm.reference_work_medium = project.reference_work_medium;
  projectSettingsForm.reference_work_synopsis = project.reference_work_synopsis;
  projectSettingsForm.reference_work_style_traits = [...project.reference_work_style_traits];
  projectSettingsForm.reference_work_world_traits = [...project.reference_work_world_traits];
  projectSettingsForm.reference_work_narrative_constraints = [...project.reference_work_narrative_constraints];
  projectSettingsForm.reference_work_confidence_note = project.reference_work_confidence_note;
  projectSettingsForm.world_brief = project.world_brief;
  projectSettingsForm.writing_rules = project.writing_rules;
  projectSettingsForm.style_profile = project.style_profile;
}

function appendOrReplaceField(target: ProjectPayload, key: "world_brief" | "writing_rules", text: string, mode: "replace" | "append") {
  if (mode === "replace") {
    target[key] = text;
    return;
  }
  const current = target[key].trim();
  target[key] = current ? `${current}\n\n${text}` : text;
}

async function generateProjectSuggestion(kind: "world_brief" | "writing_rules", target: ProjectPayload) {
  const seedText = (kind === "world_brief" ? assistantSeedWorld.value : assistantSeedWriting.value).trim();
  if (seedText.length < 4) {
    authError.value = "至少先写 4 个字，再让 AI 扩写。";
    return;
  }
  assistantLoadingKind.value = kind;
  authError.value = "";
  store.clearFeedback();
  const result = await store.suggestProjectBriefing({
    kind,
    title: target.title.trim(),
    genre: target.genre.trim(),
    reference_work: target.reference_work.trim(),
    seed_text: seedText,
  });
  assistantLoadingKind.value = null;
  if (!result) return;
  if (kind === "world_brief") {
    worldSuggestions.value = result.suggestions;
    return;
  }
  writingSuggestions.value = result.suggestions;
}

function resetProjectAssistantState() {
  projectCreateStep.value = 1;
  referenceWorkInput.value = "";
  referenceWorkResolved.value = null;
  projectForm.reference_work_confirmed = false;
  assistantSeedWorld.value = "";
  assistantSeedWriting.value = "";
  worldSuggestions.value = [];
  writingSuggestions.value = [];
}

function applyResolvedReferenceDefaults(payload: ReferenceWorkResolved) {
  if (!projectForm.genre.trim() || genreOptions.includes(projectForm.genre)) {
    projectForm.genre = inferGenreFromReference(payload);
  }
  if (!projectForm.world_brief.trim()) {
    projectForm.world_brief = buildReferenceWorldBrief(payload);
  }
  if (!projectForm.writing_rules.trim()) {
    projectForm.writing_rules = buildReferenceWritingRules(payload);
  }
  projectForm.style_profile = inferStyleProfileFromReference(payload);
}

async function resolveReferenceWork() {
  const query = referenceWorkInput.value.trim();
  if (!query) {
    authError.value = "请先输入参考作品。";
    return;
  }
  assistantLoadingKind.value = "reference_work";
  authError.value = "";
  store.clearFeedback();
  const result = await store.resolveReferenceWork({ query, genre: projectForm.genre.trim() });
  assistantLoadingKind.value = null;
  if (!result) return;
  referenceWorkResolved.value = result;
  projectForm.reference_work = result.canonical_title;
  projectForm.reference_work_creator = result.creator;
  projectForm.reference_work_medium = result.medium;
  projectForm.reference_work_synopsis = result.synopsis;
  projectForm.reference_work_style_traits = [...result.style_traits];
  projectForm.reference_work_world_traits = [...result.world_traits];
  projectForm.reference_work_narrative_constraints = [...result.narrative_constraints];
  projectForm.reference_work_confidence_note = result.confidence_note;
  projectForm.reference_work_confirmed = false;
}

async function reResolveProjectSettingsReferenceWork() {
  const query = projectSettingsForm.reference_work.trim();
  if (!query) {
    authError.value = "请先填写参考作品。";
    return;
  }
  assistantLoadingKind.value = "reference_work";
  authError.value = "";
  store.clearFeedback();
  const result = await store.resolveReferenceWork({ query, genre: projectSettingsForm.genre.trim() });
  assistantLoadingKind.value = null;
  if (!result) return;
  projectSettingsForm.reference_work = result.canonical_title;
  projectSettingsForm.reference_work_creator = result.creator;
  projectSettingsForm.reference_work_medium = result.medium;
  projectSettingsForm.reference_work_synopsis = result.synopsis;
  projectSettingsForm.reference_work_style_traits = [...result.style_traits];
  projectSettingsForm.reference_work_world_traits = [...result.world_traits];
  projectSettingsForm.reference_work_narrative_constraints = [...result.narrative_constraints];
  projectSettingsForm.reference_work_confidence_note = result.confidence_note;
}

function confirmReferenceWork() {
  if (!referenceWorkResolved.value) return;
  projectForm.reference_work = referenceWorkResolved.value.canonical_title;
  referenceWorkInput.value = referenceWorkResolved.value.canonical_title;
  projectForm.reference_work_confirmed = true;
  applyResolvedReferenceDefaults(referenceWorkResolved.value);
}

function clearReferenceWorkResolution() {
  referenceWorkResolved.value = null;
  projectForm.reference_work = "";
  projectForm.reference_work_creator = "";
  projectForm.reference_work_medium = "";
  projectForm.reference_work_synopsis = "";
  projectForm.reference_work_style_traits = [];
  projectForm.reference_work_world_traits = [];
  projectForm.reference_work_narrative_constraints = [];
  projectForm.reference_work_confidence_note = "";
  projectForm.reference_work_confirmed = false;
}

function syncNovelManageForm() {
  if (!currentNovel.value) return;
  manageNovelForm.title = currentNovel.value.title;
  manageNovelForm.author_name = currentNovel.value.author;
  manageNovelForm.summary = currentNovel.value.summary;
  manageNovelForm.tagline = currentNovel.value.tagline;
  manageNovelForm.visibility = currentNovel.value.visibility as "public" | "private";
}

function syncDraftFromGeneration(generation: typeof currentGeneration.value) {
  if (!generation) {
    draftForm.title = "";
    draftForm.summary = "";
    draftForm.content = "";
    draftForm.chapter_no = 1;
    return;
  }
  draftForm.title = selectedProjectChapter.value?.title || generation.title || "";
  draftForm.summary = generation.summary || "";
  draftForm.content = generation.content || "";
  draftForm.chapter_no = selectedProjectChapter.value?.chapter_no ?? 1;
  appendChapterForm.title = generation.title || "";
  appendChapterForm.chapter_no = nextNovelChapterNo.value;
}

function syncProjectChapterForm(chapter: ProjectChapter | null) {
  if (!chapter) {
    projectChapterEditForm.title = "";
    projectChapterEditForm.premise = "";
    projectChapterEditForm.chapter_no = 1;
    return;
  }
  projectChapterEditForm.title = chapter.title;
  projectChapterEditForm.premise = chapter.premise;
  projectChapterEditForm.chapter_no = chapter.chapter_no;
}

function resetCharacterForm() {
  editingCharacterId.value = null;
  characterForm.name = "";
  characterForm.age = "";
  characterForm.gender = "";
  characterForm.personality = "";
  characterForm.story_role = "";
  characterForm.background = "";
}

function editCharacterCard(card: CharacterCard) {
  editingCharacterId.value = card.id;
  characterForm.name = card.name;
  characterForm.age = card.age;
  characterForm.gender = card.gender;
  characterForm.personality = card.personality;
  characterForm.story_role = card.story_role;
  characterForm.background = card.background;
}

function openProjectCreate() {
  if (!isAuthenticated.value) {
    openAuthPanel("register", "projectCreate");
    return;
  }
  currentView.value = "projectCreate";
}

function openProjectSettings() {
  if (!isAuthenticated.value) return openAuthPanel("login");
  currentView.value = "projectSettings";
}

async function selectSettingsProject(value: number | string) {
  const projectId = Number(value);
  if (!projectId) {
    selectedSettingsProjectId.value = null;
    return;
  }
  await store.selectProject(projectId);
  if (!error.value) {
    selectedSettingsProjectId.value = projectId;
    syncProjectSettingsForm();
  }
}

function openCharacters() {
  if (!isAuthenticated.value) return openAuthPanel("login");
  currentView.value = "characters";
}

async function openLongform() {
  if (!isAuthenticated.value) return openAuthPanel("login");
  if (activeProject.value?.project.id) {
    await store.loadLongformState(activeProject.value.project.id);
  }
  currentView.value = "longform";
}

async function openNovelEditor(projectId?: number) {
  if (!isAuthenticated.value) return openAuthPanel("login");
  const targetProjectId = projectId ?? activeProject.value?.project.id ?? projects.value[0]?.id ?? null;
  if (targetProjectId && activeProject.value?.project.id !== targetProjectId) {
    await store.selectProject(targetProjectId);
  }
  if ((!currentNovel.value || !isManagingCurrentNovel.value || currentNovel.value.project_id !== targetProjectId) && managedNovels.value.length === 1) {
    await store.openNovel(managedNovels.value[0].id);
  }
  syncNovelManageForm();
  currentView.value = "novelEditor";
}

async function openManagedNovelEditor(novelId: number) {
  await store.openNovel(novelId);
  if (!error.value) {
    syncNovelManageForm();
    currentView.value = "novelEditor";
  }
}

async function openWorkshop(projectId: number) {
  await store.selectProject(projectId);
  if (!error.value) currentView.value = "workshop";
}

async function openWorkshopMode(mode: "chapters" | "drafts") {
  workshopMode.value = mode;
  if (activeProject.value?.project.id) {
    await openWorkshop(activeProject.value.project.id);
    return;
  }
  currentView.value = "workshop";
}

function previousWorkspacePage() {
  workspacePage.value = Math.max(1, workspacePage.value - 1);
}

function nextWorkspacePage() {
  workspacePage.value = Math.min(workspaceTotalPages.value, workspacePage.value + 1);
}

async function deleteProjectToTrash(projectId: number) {
  await store.deleteProject(projectId);
}

async function restoreTrash(item: TrashItem) {
  await store.restoreTrashItem(item.item_id, item.item_type);
}

async function submitCreateProject() {
  await store.createProject({
    title: projectForm.title,
    genre: projectForm.genre,
    reference_work: projectForm.reference_work_confirmed ? projectForm.reference_work : "",
    reference_work_creator: projectForm.reference_work_confirmed ? projectForm.reference_work_creator : "",
    reference_work_medium: projectForm.reference_work_confirmed ? projectForm.reference_work_medium : "",
    reference_work_synopsis: projectForm.reference_work_confirmed ? projectForm.reference_work_synopsis : "",
    reference_work_style_traits: projectForm.reference_work_confirmed ? [...projectForm.reference_work_style_traits] : [],
    reference_work_world_traits: projectForm.reference_work_confirmed ? [...projectForm.reference_work_world_traits] : [],
    reference_work_narrative_constraints: projectForm.reference_work_confirmed ? [...projectForm.reference_work_narrative_constraints] : [],
    reference_work_confidence_note: projectForm.reference_work_confirmed ? projectForm.reference_work_confidence_note : "",
    world_brief: projectForm.world_brief,
    writing_rules: projectForm.writing_rules,
    style_profile: projectForm.style_profile,
  });
  if (!error.value && activeProject.value?.project) {
    Object.assign(projectForm, emptyProjectDraft());
    resetProjectAssistantState();
    syncProjectSettingsForm();
    currentView.value = "characters";
  }
}

async function submitUpdateProject() {
  await store.updateProject(projectSettingsForm);
  if (!error.value) syncProjectSettingsForm();
}

async function submitCreateProjectChapter() {
  const title = projectChapterForm.title.trim();
  const premise = projectChapterForm.premise.trim();
  if (!title) {
    authError.value = "章节标题不能为空。";
    return;
  }
  if (premise.length < 12) {
    authError.value = "这一章的故事前提至少写 12 个字。";
    return;
  }
  const created = await store.createProjectChapter({
    title,
    premise,
    chapter_no: projectChapterForm.chapter_no || null,
  });
  if (created) {
    selectedProjectChapterId.value = created.id;
    workshopMode.value = "drafts";
    projectChapterForm.title = "";
    projectChapterForm.premise = "";
    projectChapterForm.chapter_no = (created.chapter_no ?? 0) + 1;
  }
}

async function submitUpdateProjectChapter() {
  if (!selectedProjectChapter.value) return;
  await store.updateProjectChapter(selectedProjectChapter.value.id, {
    title: projectChapterEditForm.title.trim(),
    premise: projectChapterEditForm.premise.trim(),
    chapter_no: projectChapterEditForm.chapter_no,
  });
}

function parseServerTime(value: string) {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

async function submitCharacterCard() {
  const payload = {
    name: characterForm.name.trim(),
    age: characterForm.age.trim(),
    gender: characterForm.gender.trim(),
    personality: characterForm.personality.trim(),
    story_role: characterForm.story_role.trim(),
    background: characterForm.background.trim(),
  };
  if (!payload.name) {
    authError.value = "人物姓名不能为空。";
    return;
  }
  if (editingCharacterId.value) await store.updateCharacterCard(editingCharacterId.value, payload);
  else await store.addCharacterCard(payload);
  if (!error.value) resetCharacterForm();
}

async function submitAutoGenerate() {
  const chapterId = selectedProjectChapter.value?.id ?? null;
  const idea = generationForm.prompt.trim();
  if (!chapterId) {
    authError.value = "先新建并选中一个章节。";
    return;
  }
  if (!idea) {
    authError.value = "先写下这一章想怎么推进，再让 AI 生成。";
    return;
  }
  currentView.value = "generationTrace";
  await store.generate({
    chapter_id: chapterId,
    prompt: idea,
    search_method: generationForm.search_method,
    response_type: generationForm.response_type,
    use_global_search: generationForm.use_global_search,
    use_scene_card: generationForm.use_scene_card,
    use_refiner: generationForm.use_refiner,
    write_evolution: generationForm.write_evolution,
  });
  if (!error.value) workshopMode.value = "drafts";
}

async function submitGenerateSeriesPlan(payload: { target_chapter_count: number; user_brief: string }) {
  await store.generateSeriesPlan(payload);
}

async function submitOutlineFeedback(payload: {
  target_type: "series" | "arc" | "chapter";
  target_id: number;
  feedback_text: string;
  feedback_type: string;
  priority: number;
}) {
  if (!payload.feedback_text.trim()) {
    authError.value = "请先写下概要修改意见。";
    return;
  }
  await store.submitOutlineFeedback(payload);
}

async function submitBatchGeneration(payload: { series_plan_id: number; start_chapter_no: number; end_chapter_no: number }) {
  await store.runBatchGeneration(payload);
  if (!error.value) workshopMode.value = "drafts";
}

async function submitRestorePlanVersion(payload: { seriesPlanId: number; versionId: number }) {
  await store.restoreSeriesPlanVersion(payload.seriesPlanId, payload.versionId);
}

async function submitRetryBatch(jobId: number) {
  await store.retryBatchGeneration(jobId);
  if (!error.value) workshopMode.value = "drafts";
}

async function submitPauseBatch(jobId: number) {
  await store.pauseBatchGeneration(jobId);
}

async function submitResumeBatch(jobId: number) {
  await store.resumeBatchGeneration(jobId);
}

async function submitCancelBatch(jobId: number) {
  await store.cancelBatchGeneration(jobId);
}

async function submitCreateStoryboard(payload: { novel_chapter_ids: number[]; title: string }) {
  await store.createStoryboard(payload);
}

async function openNovelForLongform(novelId: number) {
  if (!novelId) return;
  await store.openNovel(novelId);
}

async function submitReviseDraft(payload: { draftVersionId: number; feedback_text: string }) {
  await store.reviseDraftVersion(payload.draftVersionId, { feedback_text: payload.feedback_text });
}

async function submitCanonicalizeDraft(payload: {
  draftVersionId: number;
  novel_id?: number | null;
  author_name: string;
  visibility: "public" | "private";
  tagline: string;
}) {
  await store.canonicalizeDraftVersion(payload.draftVersionId, {
    novel_id: payload.novel_id ?? null,
    author_name: payload.author_name || currentUser.value?.username || "匿名",
    visibility: payload.visibility,
    tagline: payload.tagline,
  });
}

async function submitUpdateOutline(payload: { outlineId: number; title: string; outline: Record<string, unknown>; status: string }) {
  await store.updateChapterOutline(payload.outlineId, {
    title: payload.title,
    outline: payload.outline,
    status: payload.status,
  });
}

async function submitUpdateShot(payload: {
  storyboardId: number;
  shotId: number;
  narration_text: string;
  visual_prompt: string;
  character_refs: unknown[];
  scene_refs: unknown[];
  duration_seconds: number;
  status: string;
}) {
  await store.updateStoryboardShot(payload.storyboardId, payload.shotId, {
    narration_text: payload.narration_text,
    visual_prompt: payload.visual_prompt,
    character_refs: payload.character_refs,
    scene_refs: payload.scene_refs,
    duration_seconds: payload.duration_seconds,
    status: payload.status,
  });
}

async function submitUpdateAsset(payload: { assetId: number; uri: string; status: string; meta: Record<string, unknown> }) {
  await store.updateMediaAsset(payload.assetId, {
    uri: payload.uri,
    status: payload.status,
    meta: payload.meta,
  });
}

async function submitCreateShot(payload: {
  storyboardId: number;
  shot_no?: number | null;
  narration_text: string;
  visual_prompt: string;
  character_refs: unknown[];
  scene_refs: unknown[];
  duration_seconds: number;
  status: string;
}) {
  await store.createStoryboardShot(payload.storyboardId, {
    shot_no: payload.shot_no ?? null,
    narration_text: payload.narration_text,
    visual_prompt: payload.visual_prompt,
    character_refs: payload.character_refs,
    scene_refs: payload.scene_refs,
    duration_seconds: payload.duration_seconds,
    status: payload.status,
  });
}

async function submitDeleteShot(payload: { storyboardId: number; shotId: number }) {
  await store.deleteStoryboardShot(payload.storyboardId, payload.shotId);
}

async function submitReorderShots(payload: { storyboardId: number; shot_ids: number[] }) {
  await store.reorderStoryboardShots(payload.storyboardId, { shot_ids: payload.shot_ids });
}

async function submitUpdateVideoTask(payload: {
  taskId: number;
  task_status: string;
  output_uri: string;
  progress: Record<string, unknown>;
  error_message: string;
}) {
  await store.updateVideoTask(payload.taskId, {
    task_status: payload.task_status,
    output_uri: payload.output_uri,
    progress: payload.progress,
    error_message: payload.error_message,
  });
}

async function submitPublishNovel() {
  if (!activeProject.value?.project || !selectedProjectChapter.value || !selectedDraftGeneration.value) return;
  if (hasPublishedNovelForProject.value) {
    authError.value = "这部小说已经发布过。更新章节请使用“更新小说章节”。";
    return;
  }
  const created = await store.publishNovelFromGeneration({
    project_id: activeProject.value.project.id,
    project_chapter_id: selectedProjectChapter.value.id,
    generation_id: selectedDraftGeneration.value.id,
    title: activeProject.value.project.title,
    author_name: publishForm.author_name.trim() || currentUser.value?.username || "匿名",
    summary: publishForm.summary.trim(),
    tagline: publishForm.tagline.trim(),
    visibility: publishForm.visibility,
    chapter_title: draftForm.title.trim() || selectedProjectChapter.value.title || selectedDraftGeneration.value.title,
    chapter_summary: draftForm.summary.trim() || selectedDraftGeneration.value.summary,
    chapter_content: draftForm.content.trim() || selectedDraftGeneration.value.content,
    chapter_no: draftForm.chapter_no,
  });
  if (created) {
    showPublishPanel.value = false;
    currentView.value = "novelEditor";
  }
}

async function submitUpdateNovel() {
  if (!currentNovel.value) return;
  await store.updatePublishedNovel(currentNovel.value.id, {
    title: manageNovelForm.title.trim(),
    author_name: manageNovelForm.author_name.trim() || "匿名",
    summary: manageNovelForm.summary.trim(),
    tagline: manageNovelForm.tagline.trim(),
    visibility: manageNovelForm.visibility,
  });
  syncNovelManageForm();
}

async function deleteCurrentNovel() {
  if (!currentNovel.value) return;
  await store.deleteNovel(currentNovel.value.id);
}

async function submitAppendChapter() {
  if (!activeProject.value?.project || !selectedProjectChapter.value || !selectedDraftGeneration.value) return;
  const targetNovel = activeProjectNovel.value;
  if (!targetNovel) {
    authError.value = "这部小说还没有发布。请先发布小说，再更新章节。";
    return;
  }
  if (currentNovel.value?.id !== targetNovel.id) {
    await store.openNovel(targetNovel.id);
  }
  await store.appendNovelChapter(targetNovel.id, {
    project_id: activeProject.value.project.id,
    project_chapter_id: selectedProjectChapter.value.id,
    generation_id: selectedDraftGeneration.value.id,
    title: appendChapterForm.title.trim() || draftForm.title.trim(),
    summary: draftForm.summary.trim(),
    content: draftForm.content.trim(),
    chapter_no: appendChapterForm.chapter_no || null,
  });
  appendChapterForm.title = "";
  appendChapterForm.chapter_no = nextNovelChapterNo.value;
  showAppendPanel.value = false;
}

async function submitUpdateChapter() {
  if (!currentNovel.value || !selectedChapter.value) return;
  const chapterId = selectedChapter.value.id;
  await store.updateNovelChapter(currentNovel.value.id, chapterId, {
    title: chapterEditForm.title.trim(),
    summary: chapterEditForm.summary.trim(),
    content: chapterEditForm.content.trim(),
    chapter_no: chapterEditForm.chapter_no,
  });
  selectedChapterId.value = chapterId;
}

onMounted(() => {
  void (async () => {
    await store.initialize();
    await restoreViewState();
  })();
});

watch(currentGeneration, (next) => {
  selectedDraftGenerationId.value = next?.id ?? null;
  syncDraftFromGeneration(next);
}, { immediate: true });

watch(selectedProjectChapter, (next) => {
  generationForm.chapter_id = next?.id ?? 0;
  generationForm.prompt = loadGenerationPromptDraft(next?.id);
  syncProjectChapterForm(next);
  if (!next) {
    selectedDraftGenerationId.value = null;
    return;
  }
  const firstDraft = chapterDrafts.value[0] ?? null;
  if (!firstDraft) {
    selectedDraftGenerationId.value = null;
    currentGeneration.value = null;
    return;
  }
  if (!chapterDrafts.value.some((item) => item.id === selectedDraftGenerationId.value)) {
    currentGeneration.value = firstDraft;
    selectedDraftGenerationId.value = firstDraft.id;
  }
}, { immediate: true });

watch(nextNovelChapterNo, (next) => {
  appendChapterForm.chapter_no = next;
}, { immediate: true });

watch(currentView, (next) => {
  persistView(next);
}, { immediate: true });

watch(filteredWorkspaceProjects, () => {
  if (workspacePage.value > workspaceTotalPages.value) {
    workspacePage.value = workspaceTotalPages.value;
  }
}, { immediate: true });

watch(selectedChapter, (next) => {
  if (!next) {
    chapterEditForm.title = "";
    chapterEditForm.summary = "";
    chapterEditForm.content = "";
    chapterEditForm.chapter_no = 1;
    return;
  }
  chapterEditForm.title = next.title;
  chapterEditForm.summary = next.summary;
  chapterEditForm.content = next.content;
  chapterEditForm.chapter_no = next.chapter_no;
}, { immediate: true });

watch(() => activeProject.value?.project.id, () => {
  syncProjectSettingsForm();
  resetCharacterForm();
  selectedProjectChapterId.value = activeProject.value?.project_chapters?.[0]?.id ?? null;
  if (activeProject.value?.project.id) {
    localStorage.setItem(persistedProjectIdKey, String(activeProject.value.project.id));
  } else {
    localStorage.removeItem(persistedProjectIdKey);
  }
  if (activeProject.value?.project.id && !selectedSettingsProjectId.value) {
    selectedSettingsProjectId.value = activeProject.value.project.id;
  }
}, { immediate: true });

watch(selectedProjectChapterId, (next) => {
  if (next) localStorage.setItem(persistedProjectChapterIdKey, String(next));
  else localStorage.removeItem(persistedProjectChapterIdKey);
});

watch(selectedChapterId, (next) => {
  if (next) localStorage.setItem(persistedNovelChapterIdKey, String(next));
  else localStorage.removeItem(persistedNovelChapterIdKey);
});

watch(() => [authError.value, error.value, success.value], ([nextAuthError, nextError, nextSuccess]) => {
  if (feedbackTimer !== null) window.clearTimeout(feedbackTimer);
  if (nextAuthError || nextError || nextSuccess) {
    feedbackTimer = window.setTimeout(() => {
      clearToasts();
      feedbackTimer = null;
    }, 4200);
  }
});
</script>

<template>
  <div class="app-scene" aria-hidden="true">
    <div class="app-scene__color app-scene__color--one"></div>
    <div class="app-scene__color app-scene__color--two"></div>
    <div class="app-scene__color app-scene__color--three"></div>
    <div class="app-scene__glass app-scene__glass--one"></div>
    <div class="app-scene__glass app-scene__glass--two"></div>
    <div class="app-scene__glass app-scene__glass--three"></div>
    <div class="app-scene__glass app-scene__glass--four"></div>
    <div class="app-scene__glass app-scene__glass--five"></div>
    <div class="app-scene__glass app-scene__glass--six"></div>
    <div class="app-scene__glass app-scene__glass--seven"></div>
  </div>

  <div class="shell shell--workspace">
    <div class="toast-stack" v-if="authError || error || success" aria-live="polite">
      <div class="toast toast--error" v-if="authError || error">
        <span>{{ authError || error }}</span>
        <button type="button" aria-label="关闭提示" @click="clearToasts()">x</button>
      </div>
      <div class="toast toast--success" v-else-if="success">
        <span>{{ success }}</span>
        <button type="button" aria-label="关闭提示" @click="clearToasts()">x</button>
      </div>
    </div>

    <template v-if="currentView === 'auth'">
      <AuthModal
        v-model:mode="authMode"
        :loading="loading"
        :captcha="captcha"
        :register-field-errors="authFieldErrors.register"
        :login-field-errors="authFieldErrors.login"
        @close="closeAuthPanel()"
        @refresh-captcha="store.refreshCaptcha()"
        @register="submitRegister"
        @login="submitLogin"
      />
    </template>

    <template v-else-if="['novelEditor', 'projectSettings', 'characters', 'longform', 'workshop', 'generationTrace'].includes(currentView)">
      <div class="editor-shell">
        <aside class="editor-sidebar panel panel--paper">
          <div class="brand brand--sidebar">
            <p class="eyebrow">ChenFlow</p>
            <h1>创作台</h1>
          </div>
          <div class="editor-sidebar__actions">
            <button class="ghost-button ghost-button--small editor-sidebar__back" type="button" @click="goToView('studio')">返回工作区</button>
          </div>
          <nav class="sidebar-nav" aria-label="Editor">
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'projectSettings' }" @click="openProjectSettings()">项目设定</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'characters' }" @click="openCharacters()">人物卡</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'longform' }" @click="openLongform()">长篇流水线</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'workshop' && workshopMode === 'chapters' }" @click="openWorkshopMode('chapters')">新增章节</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'workshop' && workshopMode === 'drafts' }" @click="openWorkshopMode('drafts')">草稿箱</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'generationTrace' }" @click="currentView = 'generationTrace'">生成过程</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'novelEditor' }" @click="openNovelEditor(activeProject?.project.id)">已发布作品</button>
          </nav>
        </aside>

        <main class="main-shell">
          <template v-if="currentView === 'projectSettings'">
            <ProjectSettingsPanel
              v-if="isAuthenticated && hasProject"
              :projects="projects"
              :active-project-id="activeProject?.project.id"
              :active-project-title="activeProject?.project.title"
              :active-project-genre="activeProject?.project.genre"
              :active-project-updated-at="activeProject?.project.updated_at"
              :loading="loading"
              :form="projectSettingsForm"
              :genre-options="genreOptions"
              :style-profile-options="styleProfileOptions"
              :assistant-loading-kind="assistantLoadingKind === 'reference_work' ? null : assistantLoadingKind"
              :assistant-seed-world="assistantSeedWorld"
              :assistant-seed-writing="assistantSeedWriting"
              :world-suggestions="worldSuggestions"
              :writing-suggestions="writingSuggestions"
              @select-project="selectSettingsProject"
              @open-characters="openCharacters()"
              @submit="submitUpdateProject()"
              @re-resolve-reference-work="reResolveProjectSettingsReferenceWork()"
              @update:title="projectSettingsForm.title = $event"
              @update:genre="projectSettingsForm.genre = $event"
              @update:reference-work="projectSettingsForm.reference_work = $event"
              @update:reference-work-creator="projectSettingsForm.reference_work_creator = $event"
              @update:reference-work-medium="projectSettingsForm.reference_work_medium = $event"
              @update:reference-work-synopsis="projectSettingsForm.reference_work_synopsis = $event"
              @update:reference-work-style-traits="projectSettingsForm.reference_work_style_traits = $event"
              @update:reference-work-world-traits="projectSettingsForm.reference_work_world_traits = $event"
              @update:reference-work-narrative-constraints="projectSettingsForm.reference_work_narrative_constraints = $event"
              @update:reference-work-confidence-note="projectSettingsForm.reference_work_confidence_note = $event"
              @update:world-brief="projectSettingsForm.world_brief = $event"
              @update:writing-rules="projectSettingsForm.writing_rules = $event"
              @update:style-profile="projectSettingsForm.style_profile = $event"
              @update:assistant-seed-world="assistantSeedWorld = $event"
              @update:assistant-seed-writing="assistantSeedWriting = $event"
              @generate-suggestion="generateProjectSuggestion($event, projectSettingsForm)"
              @use-suggestion="appendOrReplaceField(projectSettingsForm, $event.kind, $event.text, $event.mode)"
            />
          </template>

          <template v-else-if="currentView === 'characters'">
            <main v-if="isAuthenticated && hasProject" class="workspace workspace--single">
              <section class="panel panel--paper">
                <div class="panel-heading">
                  <div>
                    <p class="panel-heading__kicker">人物卡</p>
                    <h2>{{ editingCharacterId ? "编辑人物" : "添加人物" }}</h2>
                    <p class="panel-heading__desc">一张卡只放一类信息，让角色的姓名、职责、性格和背景分层展示。</p>
                  </div>
                  <div class="mode-switch">
                    <button class="ghost-button ghost-button--small" type="button" @click="openProjectSettings()">项目设定</button>
                    <button v-if="editingCharacterId" class="ghost-button ghost-button--small" type="button" @click="resetCharacterForm()">取消</button>
                  </div>
                </div>
                <form class="form-stack" @submit.prevent="submitCharacterCard()">
                  <div class="inline-row">
                    <label class="field"><span>姓名</span><input v-model="characterForm.name" maxlength="120" /></label>
                    <label class="field"><span>年龄</span><input v-model="characterForm.age" maxlength="60" /></label>
                    <label class="field"><span>性别</span><input v-model="characterForm.gender" maxlength="60" /></label>
                  </div>
                  <label class="field"><span>在小说里的角色</span><input v-model="characterForm.story_role" maxlength="120" /></label>
                  <label class="field"><span>性格</span><textarea v-model="characterForm.personality" rows="4" maxlength="2000" /></label>
                  <label class="field"><span>人物背景</span><textarea v-model="characterForm.background" rows="5" maxlength="4000" /></label>
                  <button class="primary-button" :disabled="loading">{{ editingCharacterId ? "保存人物卡" : "添加人物卡" }}</button>
                </form>
              </section>
              <section class="panel">
                <div class="panel-heading"><div><p class="panel-heading__kicker">已有人物</p><h2>{{ activeProject?.character_cards.length ?? 0 }} 张人物卡</h2></div></div>
                <div class="card-list" v-if="activeProject?.character_cards.length">
                  <article v-for="card in activeProject.character_cards" :key="card.id" class="memory-card">
                    <strong>{{ card.name }}</strong>
                    <span>{{ card.story_role }} / {{ card.age }} {{ card.gender }}</span>
                    <span>{{ card.personality }}</span>
                    <em>{{ card.background }}</em>
                    <div class="hero__actions">
                      <button class="ghost-button ghost-button--small" type="button" @click="editCharacterCard(card)">编辑</button>
                      <button class="ghost-button ghost-button--small" type="button" @click="activeProject?.project.id && store.deleteCharacterCard(activeProject.project.id, card.id)">删除</button>
                    </div>
                  </article>
                </div>
              </section>
            </main>
          </template>

          <template v-else-if="currentView === 'workshop'">
            <ProjectWorkshopPanel
              v-if="isAuthenticated && hasProject"
              :mode="workshopMode"
              :project-title="activeProject?.project.title"
              :loading="loading"
              :generation-progress="generationProgress"
              :current-step="currentStep"
              :chapters="projectChapters"
              :selected-chapter-id="selectedProjectChapterId"
              :selected-chapter="selectedProjectChapter"
              :chapter-drafts="chapterDrafts"
              :selected-draft-generation="selectedDraftGeneration"
              :draft-word-count="draftWordCount"
              :chapter-form="projectChapterForm"
              :chapter-edit-form="projectChapterEditForm"
              :generation-form="generationForm"
              :draft-form="draftForm"
              :publish-form="publishForm"
              :append-chapter-form="appendChapterForm"
              :show-publish-panel="showPublishPanel"
              :show-append-panel="showAppendPanel"
              :current-novel="currentNovel"
              :has-published-novel="hasPublishedNovelForProject"
              :published-novel-title="activeProjectNovel?.title"
              @update:chapter-form="Object.assign(projectChapterForm, $event)"
              @update:chapter-edit-form="Object.assign(projectChapterEditForm, $event)"
              @update:generation-form="Object.assign(generationForm, $event)"
              @update:draft-form="Object.assign(draftForm, $event)"
              @update:publish-form="Object.assign(publishForm, $event)"
              @update:append-chapter-form="Object.assign(appendChapterForm, $event)"
              @update:show-publish-panel="showPublishPanel = $event"
              @update:show-append-panel="showAppendPanel = $event"
              @select-chapter="selectedProjectChapterId = $event"
              @select-draft="selectedDraftGenerationId = $event"
              @create-chapter="submitCreateProjectChapter()"
              @save-chapter="submitUpdateProjectChapter()"
              @save-prompt="saveGenerationPromptDraft()"
              @generate-draft="submitAutoGenerate()"
              @continue-draft="store.refreshGenerationEvolution($event)"
              @publish-draft="submitPublishNovel()"
              @append-draft="submitAppendChapter()"
            />
          </template>

          <template v-else-if="currentView === 'longform'">
            <LongformPipelinePanel
              v-if="isAuthenticated && hasProject"
              :project-title="activeProject?.project.title"
              :loading="loading"
              :state="longformState"
              :managed-novels="managedNovels"
              :current-novel="currentNovel"
              @generate-plan="submitGenerateSeriesPlan"
              @submit-feedback="submitOutlineFeedback"
              @lock-plan="store.lockSeriesPlan"
              @restore-plan-version="submitRestorePlanVersion"
              @batch-generate="submitBatchGeneration"
              @retry-batch="submitRetryBatch"
              @pause-batch="submitPauseBatch"
              @resume-batch="submitResumeBatch"
              @cancel-batch="submitCancelBatch"
              @open-novel="openNovelForLongform"
              @create-storyboard="submitCreateStoryboard"
              @revise-draft="submitReviseDraft"
              @canonicalize-draft="submitCanonicalizeDraft"
              @create-video-task="store.createVideoTask"
              @update-outline="submitUpdateOutline"
              @update-shot="submitUpdateShot"
              @update-asset="submitUpdateAsset"
              @create-shot="submitCreateShot"
              @delete-shot="submitDeleteShot"
              @reorder-shots="submitReorderShots"
              @update-video-task="submitUpdateVideoTask"
            />
          </template>

          <template v-else-if="currentView === 'generationTrace'">
            <GenerationTracePanel
              :project-title="activeProject?.project.title"
              :chapter-title="selectedProjectChapter?.title"
              :loading="loading"
              :progress="generationProgress"
            />
          </template>

          <template v-else-if="currentView === 'novelEditor'">
            <NovelEditorPanel
              :managed-novels="managedNovels"
              :novel="currentNovel && isManagingCurrentNovel ? currentNovel : null"
              :selected-chapter="selectedChapter"
              :sorted-chapters="sortedChapters"
              :manage-title="manageNovelForm.title"
              :manage-author-name="manageNovelForm.author_name"
              :manage-summary="manageNovelForm.summary"
              :manage-tagline="manageNovelForm.tagline"
              :manage-visibility="manageNovelForm.visibility"
              :chapter-title="chapterEditForm.title"
              :chapter-summary="chapterEditForm.summary"
              :chapter-content="chapterEditForm.content"
              :chapter-no="chapterEditForm.chapter_no"
              :append-title="appendChapterForm.title"
              :append-summary="draftForm.summary"
              :append-content="draftForm.content"
              :append-chapter-no="appendChapterForm.chapter_no"
              :selected-project-chapter="selectedProjectChapter"
              :selected-draft-generation="selectedDraftGeneration"
              :loading="loading"
              @open-novel="openManagedNovelEditor"
              @open-detail="goToView('workshop')"
              @open-workshop="activeProject?.project.id && openWorkshop(activeProject.project.id)"
              @update:manage-title="manageNovelForm.title = $event"
              @update:manage-author-name="manageNovelForm.author_name = $event"
              @update:manage-summary="manageNovelForm.summary = $event"
              @update:manage-tagline="manageNovelForm.tagline = $event"
              @update:manage-visibility="manageNovelForm.visibility = $event"
              @update:chapter-title="chapterEditForm.title = $event"
              @update:chapter-summary="chapterEditForm.summary = $event"
              @update:chapter-content="chapterEditForm.content = $event"
              @update:chapter-no="chapterEditForm.chapter_no = $event"
              @update:append-title="appendChapterForm.title = $event"
              @update:append-summary="draftForm.summary = $event"
              @update:append-content="draftForm.content = $event"
              @update:append-chapter-no="appendChapterForm.chapter_no = $event"
              @select-chapter="selectedChapterId = Number($event)"
              @save-novel="submitUpdateNovel()"
              @delete-novel="deleteCurrentNovel()"
              @save-chapter="submitUpdateChapter()"
              @append-chapter="submitAppendChapter()"
              @back="goToView('workshop')"
            />
          </template>
        </main>
      </div>
    </template>

    <template v-else>
      <div class="workspace-shell">
        <button
          class="mobile-sidebar-toggle ghost-button ghost-button--small"
          type="button"
          :aria-expanded="mobileSidebarOpen ? 'true' : 'false'"
          aria-controls="primary-sidebar"
          @click="mobileSidebarOpen = !mobileSidebarOpen"
        >
          {{ mobileSidebarOpen ? "收起菜单" : "打开菜单" }}
        </button>
        <aside id="primary-sidebar" class="sidebar panel panel--paper" :class="{ 'sidebar--mobile-open': mobileSidebarOpen }">
          <div class="brand brand--sidebar">
            <p class="eyebrow">晨流写作台</p>
            <h1>Chen Flow</h1>
          </div>
          <nav class="sidebar-nav" aria-label="Primary">
            <button class="sidebar-nav__item sidebar-nav__item--main" :class="{ 'sidebar-nav__item--active': currentView === 'studio' }" @click="goToView('studio')">我的项目</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'projectCreate' }" @click="openProjectCreate()">新建项目</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'trash' }" @click="goToView('trash')">回收站</button>
          </nav>
          <div class="sidebar__footer">
            <template v-if="isAuthenticated">
              <div class="sidebar-user">
                <div class="sidebar-user__avatar">{{ (currentUser?.username?.slice(0, 1) ?? "U").toUpperCase() }}</div>
                <div class="sidebar-user__meta">
                  <strong>{{ currentUser?.username }}</strong>
                </div>
              </div>
              <button class="ghost-button ghost-button--small" @click="store.logout()">退出</button>
            </template>
            <template v-else>
              <button class="ghost-button ghost-button--small" @click="openAuthPanel('login', 'studio')">登录</button>
              <button class="primary-button primary-button--compact" @click="openAuthPanel('register', 'studio')">创建账号</button>
            </template>
          </div>
        </aside>

        <main class="main-shell">
          <template v-if="currentView === 'studio'">
            <StudioWorkspacePanel
              :workspace-search="workspaceSearch"
              :projects="pagedWorkspaceProjects"
              :workspace-page="workspacePage"
              :workspace-page-size="workspacePageSize"
              :workspace-total-pages="workspaceTotalPages"
              :loading="loading"
              @update:workspace-search="workspaceSearch = $event"
              @open-project-create="openProjectCreate()"
              @open-project="openWorkshop"
              @delete-project="deleteProjectToTrash"
              @previous-page="previousWorkspacePage()"
              @next-page="nextWorkspacePage()"
            />
          </template>

          <template v-else-if="currentView === 'trash'">
            <section class="section-banner panel panel--paper">
              <div><p class="panel-heading__kicker">回收站</p><h2>已删除内容</h2></div>
              <div class="hero__stats">
                <span>项目 {{ trashSummary.project }}</span>
                <span>作品 {{ trashSummary.novel }}</span>
                <span>人物卡 {{ trashSummary.character_card }}</span>
                <span>脏演化 {{ trashSummary.dirty_evolution }}</span>
              </div>
            </section>
            <section class="panel">
              <div class="card-list" v-if="trashItems.length">
                <article v-for="item in trashItems" :key="`${item.item_type}-${item.item_id}`" class="memory-card">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.subtitle || item.item_type }}</span>
                  <em>{{ formatDateTime(item.deleted_at) }}</em>
                  <button class="ghost-button ghost-button--small" type="button" @click="restoreTrash(item)">恢复</button>
                </article>
              </div>
              <p v-else class="empty-text">回收站目前是空的。</p>
            </section>
          </template>

          <template v-else-if="currentView === 'projectCreate'">
            <main v-if="isAuthenticated" class="workspace workspace--single">
              <section class="panel panel--paper">
                <div class="panel-heading">
                  <div>
                    <p class="panel-heading__kicker">新建项目</p>
                    <h2>先把小说的核心设定立住</h2>
                    <p class="panel-heading__desc">项目层只放长期有效的信息：题材、世界设定、写作偏好和文风。具体剧情前提留到章节里写。</p>
                  </div>
                </div>
                <ProjectCreateWizard
                  :loading="loading"
                  :step="projectCreateStep"
                  :form="projectForm"
                  :genre-option-cards="genreOptionCards"
                  :style-profile-options="styleProfileOptions"
                  :reference-work-input="referenceWorkInput"
                  :reference-work-resolved="referenceWorkResolved"
                  :reference-work-confirmed="projectForm.reference_work_confirmed"
                  :assistant-loading-kind="assistantLoadingKind"
                  :assistant-seed-world="assistantSeedWorld"
                  :assistant-seed-writing="assistantSeedWriting"
                  :world-suggestions="worldSuggestions"
                  :writing-suggestions="writingSuggestions"
                  @update:step="projectCreateStep = $event"
                  @submit="submitCreateProject()"
                  @submit-quick="submitCreateProject()"
                  @update:title="projectForm.title = $event"
                  @update:genre="projectForm.genre = $event"
                  @update:reference-work-input="referenceWorkInput = $event"
                  @resolve-reference-work="resolveReferenceWork()"
                  @confirm-reference-work="confirmReferenceWork()"
                  @clear-reference-work="clearReferenceWorkResolution()"
                  @update:world-brief="projectForm.world_brief = $event"
                  @update:writing-rules="projectForm.writing_rules = $event"
                  @update:style-profile="projectForm.style_profile = $event"
                  @update:assistant-seed-world="assistantSeedWorld = $event"
                  @update:assistant-seed-writing="assistantSeedWriting = $event"
                  @generate-suggestion="generateProjectSuggestion($event, projectForm)"
                  @use-suggestion="appendOrReplaceField(projectForm, $event.kind, $event.text, $event.mode)"
                />
              </section>
            </main>
          </template>
        </main>
      </div>
    </template>
  </div>
</template>
