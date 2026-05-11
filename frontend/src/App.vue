<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import AuthModal from "./components/auth/AuthModal.vue";
import ProfileSettingsPanel from "./components/workspace/ProfileSettingsPanel.vue";
import NovelDetailPanel from "./components/workspace/NovelDetailPanel.vue";
import NovelEditorPanel from "./components/workspace/NovelEditorPanel.vue";
import GenerationTracePanel from "./components/workspace/GenerationTracePanel.vue";
import ProjectCreateWizard from "./components/workspace/ProjectCreateWizard.vue";
import ProjectWorkshopPanel from "./components/workspace/ProjectWorkshopPanel.vue";
import ProjectSettingsPanel from "./components/workspace/ProjectSettingsPanel.vue";
import NovelReaderPanel from "./components/workspace/NovelReaderPanel.vue";
import StudioWorkspacePanel from "./components/workspace/StudioWorkspacePanel.vue";
import WorkspaceSidebar from "./components/workspace/WorkspaceSidebar.vue";
import { useAuthFlow } from "./composables/useAuthFlow";
import { useWorkbenchStore } from "./stores/workbench";
import type { CharacterCard, NovelCard, ProjectChapter, ProjectCreateDraft, ProjectPayload, ReferenceWorkResolved, TrashItem, ViewKey } from "./types";

const store = useWorkbenchStore();
const {
  captcha,
  currentUser,
  projects,
  projectFolders,
  trashItems,
  novels,
  favoriteNovels,
  myNovels,
  currentNovel,
  novelComments,
  activeProject,
  currentGeneration,
  generationProgress,
  loading,
  error,
  success,
  isAuthenticated,
} = storeToRefs(store);

const currentView = ref<ViewKey>("home");
const authError = ref("");
const favoritesTab = ref<"liked" | "favorited">("favorited");
const novelLayout = ref<"grid" | "list">("grid");
const novelSearch = ref("");
const workspaceSearch = ref("");
const showCreateFolder = ref(false);
const showPublishPanel = ref(false);
const showAppendPanel = ref(false);
const folderForm = reactive({ name: "" });
const movingProjectId = ref<number | null>(null);
const selectedWorkspaceFolderId = ref<number | null>(null);
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
  "home",
  "discover",
  "favorites",
  "studio",
  "trash",
  "projectCreate",
  "projectSettings",
  "characters",
  "workshop",
  "profile",
];

type GenreOptionCard = {
  value: string;
  label: string;
  description: string;
};

const genreOptionCards: GenreOptionCard[] = [
  { value: "现代都市轻小说", label: "现代都市轻小说", description: "现代城市日常、轻松叙事、偏角色互动，适合校园后日常和都会成长线。" },
  { value: "校园青春恋爱", label: "校园青春恋爱", description: "学生视角、关系推进明确、情绪细腻，适合青春群像和恋爱拉扯。" },
  { value: "都市情感", label: "都市情感", description: "成年角色、关系与选择驱动，重点是情绪张力和现实处境。" },
  { value: "都市异能", label: "都市异能", description: "现代背景下加入超能力或异常规则，适合爽点和悬念并行。" },
  { value: "都市悬疑", label: "都市悬疑", description: "现代都市里的谜团、失踪、反转和调查，节奏通常更紧。" },
  { value: "轻科幻", label: "轻科幻", description: "有未来技术或科幻设定，但阅读门槛不过高，偏故事可读性。" },
  { value: "奇幻冒险", label: "奇幻冒险", description: "未知世界、旅途、伙伴和成长，适合地图式推进与探索。" },
  { value: "东方玄幻", label: "东方玄幻", description: "修行体系、宗门势力、神秘传承，适合长线升级与世界层级。" },
  { value: "西幻史诗", label: "西幻史诗", description: "王国、骑士、战争、神话秩序，整体更厚重、更宏大。" },
  { value: "无限流", label: "无限流", description: "副本、规则、闯关、生存压力明确，适合强节奏结构。" },
  { value: "推理悬疑", label: "推理悬疑", description: "以解谜和因果还原为核心，强调线索、逻辑和反转。" },
  { value: "惊悚恐怖", label: "惊悚恐怖", description: "压迫感、未知感和危险感优先，适合氛围与生存危机。" },
  { value: "历史架空", label: "历史架空", description: "借用历史气质重构时代，重点在制度、风俗和人物命运。" },
  { value: "古风言情", label: "古风言情", description: "古代或类古代背景下的情感关系，适合慢热与身份冲突。" },
  { value: "治愈日常", label: "治愈日常", description: "冲突不必太重，重点是陪伴感、生活感和情绪修复。" },
  { value: "公路冒险", label: "公路冒险", description: "一路前进一路变化，空间切换频繁，适合角色关系渐进展开。" },
];

const genreOptions = genreOptionCards.map((item) => item.value);

const styleProfileOptions = [
  {
    value: "light_novel",
    label: "轻小说",
    description: "轻快、易读、偏人物互动，适合大多数网文和连载开局。",
    bullets: ["优先人物互动", "句子更轻", "每段都要推进场景或关系"],
  },
  {
    value: "lyrical_restrained",
    label: "抒情克制",
    description: "更细腻，允许少量意象和情绪潜流，但不走厚重散文。",
    bullets: ["允许细腻情绪", "意象少而准", "不能只有气氛没有动作"],
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
    description: "叙述更稳、更庄重，适合奇幻、历史和大设定冲突。",
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

  if (/(悬疑|惊悚|追逐|压迫|紧张|thriller|mystery|crime|suspense)/.test(haystack)) return "cinematic_tense";
  if (/(对话|嘴炮|群像互动|对白|conversation|dialogue)/.test(haystack)) return "dialogue_driven";
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
    { pattern: /(校园|青春|学生|社团|学园)/, genre: "校园青春恋爱" },
    { pattern: /(都市|现代|职场|都会)/, genre: "现代都市轻小说" },
    { pattern: /(异能|超能力|能力者)/, genre: "都市异能" },
    { pattern: /(悬疑|推理|案件|侦探|谜团)/, genre: "推理悬疑" },
    { pattern: /(惊悚|恐怖|怪谈|诡异)/, genre: "惊悚恐怖" },
    { pattern: /(科幻|未来|太空|机甲|赛博)/, genre: "轻科幻" },
    { pattern: /(奇幻|冒险|魔法|旅途)/, genre: "奇幻冒险" },
    { pattern: /(东方玄幻|修仙|宗门|灵气|仙侠)/, genre: "东方玄幻" },
    { pattern: /(西幻|王国|骑士|史诗|龙)/, genre: "西幻史诗" },
    { pattern: /(治愈|日常|陪伴|生活流)/, genre: "治愈日常" },
    { pattern: /(公路|旅行|旅程)/, genre: "公路冒险" },
  ];

  return mappings.find((item) => item.pattern.test(haystack))?.genre ?? "现代都市轻小说";
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
const customGenreDraft = ref("");
const customSettingsGenreDraft = ref("");
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

const memoryForm = reactive({ title: "", content: "", memory_scope: "story", importance: 3 });
const sourceForm = reactive({ title: "", content: "", source_kind: "reference" });

const generationForm = reactive({
  chapter_id: 0,
  prompt: "",
  search_method: "local",
  response_type: "Multiple Paragraphs",
  use_global_search: true,
  use_scene_card: true,
  use_refiner: true,
  write_evolution: true,
});
const profileForm = reactive({
  bio: "偏爱空气感、留白和能慢慢落下来的情绪。",
  email: "",
  phone: "",
});
const commentForm = reactive({ content: "" });

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
const chapterJumpNo = ref(1);
const selectedDraftGenerationId = ref<number | null>(null);
const selectedSettingsProjectId = ref<number | null>(null);
const selectedProjectChapterId = ref<number | null>(null);
const lastNovelSourceView = ref<ViewKey>("discover");
const workshopMode = ref<"chapters" | "drafts">("chapters");

const featuredNovel = computed(() => novels.value[0] ?? null);
const hasProject = computed(() => Boolean(activeProject.value));
const likedNovels = computed(() => novels.value.filter((novel) => novel.is_liked));
const recentProjects = computed(() =>
  [...projects.value]
    .sort((a, b) => parseServerTime(b.updated_at).getTime() - parseServerTime(a.updated_at).getTime())
    .slice(0, 3),
);
const continueProject = computed(() => recentProjects.value[0] ?? null);
const homeSpotlightNovels = computed(() =>
  [...novels.value]
    .sort((a, b) => {
      if (b.likes_count !== a.likes_count) return b.likes_count - a.likes_count;
      return parseServerTime(b.updated_at).getTime() - parseServerTime(a.updated_at).getTime();
    })
    .slice(0, 3),
);
const homeDraftCount = computed(() => activeProject.value?.generations.length ?? 0);
const homeStats = computed(() => [
  { label: "项目", value: projects.value.length },
  { label: "已发布", value: myNovels.value.length },
  { label: "收藏", value: favoriteNovels.value.length },
  { label: "草稿", value: homeDraftCount.value },
]);
const shelfDisplayNovels = computed(() => {
  const keyword = novelSearch.value.trim().toLowerCase();
  const source = favoritesTab.value === "favorited" ? favoriteNovels.value : likedNovels.value;
  return keyword ? source.filter((novel) => matchesNovelSearch(novel, keyword)) : source;
});
const searchedNovels = computed(() => {
  const keyword = novelSearch.value.trim().toLowerCase();
  return keyword ? novels.value.filter((novel) => matchesNovelSearch(novel, keyword)) : novels.value;
});
const sortedFolders = computed(() =>
  [...projectFolders.value].sort((a, b) => a.sort_order - b.sort_order || a.created_at.localeCompare(b.created_at)),
);
const selectedWorkspaceFolder = computed(() => {
  if (!sortedFolders.value.length) return null;
  return sortedFolders.value.find((item) => item.id === selectedWorkspaceFolderId.value) ?? sortedFolders.value[0] ?? null;
});
const filteredWorkspaceProjects = computed(() => {
  const folderId = selectedWorkspaceFolder.value?.id ?? null;
  const keyword = workspaceSearch.value.trim().toLowerCase();
  const source = projects.value.filter((project) => (folderId ? project.folder_id === folderId : true));
  if (!keyword) return source;
  return source.filter((project) =>
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

function matchesNovelSearch(novel: NovelCard, keyword: string) {
  return [novel.title, novel.author, novel.genre, novel.tagline, novel.summary, novel.latest_excerpt]
    .join(" ")
    .toLowerCase()
    .includes(keyword);
}

const isManagingCurrentNovel = computed(() =>
  Boolean(currentNovel.value && myNovels.value.some((item) => item.id === currentNovel.value?.id)),
);
const sortedChapters = computed(() => [...(currentNovel.value?.chapters ?? [])].sort((a, b) => a.chapter_no - b.chapter_no));
const selectedChapter = computed(() => {
  if (!sortedChapters.value.length) return null;
  return sortedChapters.value.find((chapter) => chapter.id === selectedChapterId.value) ?? sortedChapters.value[0] ?? null;
});
const selectedChapterIndex = computed(() => sortedChapters.value.findIndex((chapter) => chapter.id === selectedChapter.value?.id));
const previousChapter = computed(() => (selectedChapterIndex.value > 0 ? sortedChapters.value[selectedChapterIndex.value - 1] : null));
const nextChapter = computed(() =>
  selectedChapterIndex.value >= 0 && selectedChapterIndex.value < sortedChapters.value.length - 1
    ? sortedChapters.value[selectedChapterIndex.value + 1]
    : null,
);
const hasChapterNavigation = computed(() => sortedChapters.value.length > 1);
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
const detailReturnView = computed<ViewKey>(() => lastNovelSourceView.value);
const draftWordCount = computed(() => draftForm.content.replace(/\s+/g, "").length);

const currentStep = computed(() => {
  if (!isAuthenticated.value) return "先创建账号，再开始写自己的小说。";
  if (!hasProject.value) return "先新建项目，确定标题、题材和世界设定。";
  if (!(activeProject.value?.character_cards.length ?? 0)) return "先添加主要人物卡，再开始规划章节。";
  if (!selectedProjectChapter.value) return "先新建一个章节，写清这一章的故事前提。";
  if (activeProject.value?.project.indexing_status !== "ready") return "先准备并完成 GraphRAG 索引；未就绪时不能生成草稿。";
  return "选中章节后输入这一章想怎么写，草稿会进入当前章节的草稿箱。";
});

const publishDefaults = computed(() => ({
  title: activeProject.value?.project.title || "",
  summary: selectedDraftGeneration.value?.summary || "",
  author_name: currentUser.value?.username || "",
}));

const {
  authMode,
  authFieldErrors,
  authRequestedView,
  openAuthPanel,
  closeAuthPanel,
  clearAuthFeedback,
  requestLikeLogin,
  requestFavoriteLogin,
  requestCommentLogin,
  submitRegister,
  submitLogin,
} = useAuthFlow({
  currentView,
  authError,
  loading,
  error,
  success,
  isAuthenticated,
  captcha,
  refreshCaptcha: () => store.refreshCaptcha(),
  login: (payload) => store.login(payload),
  register: (payload) => store.register(payload),
  clearFeedback: () => store.clearFeedback(),
  afterLike: async (novelId) => {
    await store.toggleLikeNovel(novelId);
  },
  afterFavorite: async (novelId) => {
    await store.toggleFavoriteNovel(novelId);
  },
  afterComment: async (novelId, content) => {
    if (currentNovel.value?.id !== novelId) {
      await store.openNovel(novelId);
    }
    currentView.value = "detail";
    commentForm.content = content;
    await store.submitNovelComment(content);
    if (!error.value) {
      commentForm.content = "";
      return true;
    }
    return false;
  },
});

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
  if (status === "ready") return "可生成草稿";
  if (status === "indexing") return "资料准备中";
  if (status === "failed") return "准备失败";
  if (status === "stale") return "资料待更新";
  return status;
}

function goToView(view: ViewKey) {
  if (view === "projectCreate" && !isAuthenticated.value) {
    openAuthPanel("register", view);
    return;
  }
  currentView.value = view;
  mobileSidebarOpen.value = false;
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
  success.value = "这一章想怎么写已保存。";
}

async function restoreViewState() {
  if (!isAuthenticated.value) {
    currentView.value = "home";
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

function openWorkspace() {
  if (!isAuthenticated.value) {
    authError.value = "请先登录后再进入我的小说。";
    openAuthPanel("login", "studio");
    return;
  }
  currentView.value = "studio";
  mobileSidebarOpen.value = false;
}

function openFavorites() {
  if (!isAuthenticated.value) {
    authError.value = "请先登录后再查看喜欢和收藏。";
    openAuthPanel("login", "favorites");
    return;
  }
  currentView.value = "favorites";
  mobileSidebarOpen.value = false;
}

function openTrash() {
  if (!isAuthenticated.value) {
    authError.value = "请先登录后再查看回收站。";
    openAuthPanel("login", "trash");
    return;
  }
  currentView.value = "trash";
  mobileSidebarOpen.value = false;
}

function requireAuth(nextView: ViewKey) {
  if (!isAuthenticated.value) {
    openAuthPanel("register", nextView);
    return;
  }
  currentView.value = nextView;
}

function toggleMobileSidebar() {
  mobileSidebarOpen.value = !mobileSidebarOpen.value;
}

function openProjectCreate() {
  if (!isAuthenticated.value) {
    openAuthPanel("register", "projectCreate");
    return;
  }
  currentView.value = "projectCreate";
}

async function openContinueWriting(projectId?: number) {
  if (!isAuthenticated.value) {
    openAuthPanel("login", "studio");
    return;
  }
  const targetProjectId = projectId ?? continueProject.value?.id ?? null;
  if (!targetProjectId) {
    openProjectCreate();
    return;
  }
  await openWorkshop(targetProjectId);
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
  customSettingsGenreDraft.value = genreOptions.includes(project.genre) ? "" : project.genre;
}

function applyGenre(target: ProjectPayload, value: string) {
  target.genre = value;
}

function toggleCreateFolder() {
  showCreateFolder.value = !showCreateFolder.value;
  if (showCreateFolder.value) {
    folderForm.name = "";
    authError.value = "";
    store.clearFeedback();
  }
}

function closeCreateFolder() {
  showCreateFolder.value = false;
  folderForm.name = "";
}

function applyCustomGenre(target: ProjectPayload, draft: string) {
  const value = draft.trim();
  if (!value) {
    authError.value = "请输入自定义题材名称。";
    return;
  }
  target.genre = value;
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
  customGenreDraft.value = "";
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

function openReader(chapterId?: number) {
  selectedChapterId.value = chapterId ?? selectedChapterId.value ?? sortedChapters.value[0]?.id ?? null;
  currentView.value = "reader";
}

async function openNovelEditor(projectId?: number) {
  if (!isAuthenticated.value) return openAuthPanel("login");
  const targetProjectId = projectId ?? activeProject.value?.project.id ?? projects.value[0]?.id ?? null;
  if (targetProjectId && activeProject.value?.project.id !== targetProjectId) {
    await store.selectProject(targetProjectId);
  }
  if (!error.value) {
    selectedDraftGenerationId.value = currentGeneration.value?.id ?? chapterDrafts.value[0]?.id ?? null;
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

function backToWorkspace() {
  currentView.value = "studio";
}

async function openNovelDetail(novelId: number, sourceView?: ViewKey) {
  lastNovelSourceView.value = sourceView ?? currentView.value;
  await store.openNovel(novelId);
  if (!error.value) {
    selectedChapterId.value = sortedChapters.value[0]?.id ?? null;
    syncNovelManageForm();
    currentView.value = "detail";
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

function selectChapterById(value: number | string) {
  selectedChapterId.value = Number(value);
}

function jumpToChapterNo() {
  const target = sortedChapters.value.find((chapter) => chapter.chapter_no === Number(chapterJumpNo.value));
  if (target) selectedChapterId.value = target.id;
}

function openGeneration(id: number) {
  const found = chapterDrafts.value.find((item) => item.id === id) ?? null;
  currentGeneration.value = found;
  selectedDraftGenerationId.value = found?.id ?? null;
  showPublishPanel.value = false;
  showAppendPanel.value = false;
  if (found) {
    publishForm.title = activeProject.value?.project.title || "";
    publishForm.summary = found.summary || "";
    syncDraftFromGeneration(found);
  }
}

function selectDraftGenerationById(value: number | string) {
  const generationId = Number(value);
  if (!generationId) {
    selectedDraftGenerationId.value = null;
    currentGeneration.value = null;
    return;
  }
  openGeneration(generationId);
}

function selectWorkspaceFolder(folderId: number | string) {
  selectedWorkspaceFolderId.value = Number(folderId);
  workspacePage.value = 1;
}

async function submitCreateFolder() {
  const name = folderForm.name.trim();
  if (!name) {
    authError.value = "请输入文件夹名称。";
    return;
  }
  authError.value = "";
  const created = await store.createFolder(name);
  if (created) {
    folderForm.name = "";
    showCreateFolder.value = false;
    selectedWorkspaceFolderId.value = created.id;
  }
}

async function assignProjectFolder(projectId: number, folderId: number | string) {
  movingProjectId.value = projectId;
  await store.moveProjectToFolder(projectId, Number(folderId));
  movingProjectId.value = null;
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

async function likeNovel(novelId: number) {
  if (!isAuthenticated.value) {
    requestLikeLogin(novelId);
    return;
  }
  await store.toggleLikeNovel(novelId);
}

async function toggleSaveNovel(novelId: number) {
  if (!isAuthenticated.value) {
    requestFavoriteLogin(novelId);
    return;
  }
  await store.toggleFavoriteNovel(novelId);
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

async function submitComment() {
  if (!isAuthenticated.value) {
    requestCommentLogin(currentNovel.value?.id ?? null, commentForm.content);
    return;
  }
  if (!commentForm.content.trim()) {
    authError.value = "评论不能为空。";
    return;
  }
  await store.submitNovelComment(commentForm.content);
  if (!error.value) commentForm.content = "";
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
    currentView.value = "detail";
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

async function submitProfile() {
  await store.saveProfile(profileForm);
}

onMounted(() => {
  void (async () => {
    await store.initialize();
    await restoreViewState();
  })();
});

watch(publishDefaults, (next) => {
  if (!publishForm.title.trim()) publishForm.title = next.title;
  if (!publishForm.summary.trim()) publishForm.summary = next.summary;
  if (!publishForm.author_name.trim()) publishForm.author_name = next.author_name;
}, { immediate: true });

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
    openGeneration(firstDraft.id);
  }
}, { immediate: true });

watch(nextNovelChapterNo, (next) => {
  appendChapterForm.chapter_no = next;
}, { immediate: true });

watch(currentView, (next) => {
  persistView(next);
}, { immediate: true });

watch(sortedFolders, (next) => {
  if (!next.length) {
    selectedWorkspaceFolderId.value = null;
    return;
  }
  if (!selectedWorkspaceFolderId.value || !next.some((item) => item.id === selectedWorkspaceFolderId.value)) {
    selectedWorkspaceFolderId.value = next[0].id;
  }
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
  chapterJumpNo.value = next.chapter_no;
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

    <template v-else-if="['novelEditor', 'projectSettings', 'characters', 'workshop', 'generationTrace'].includes(currentView)">
      <div class="editor-shell">
        <aside class="editor-sidebar panel panel--paper">
          <div class="brand brand--sidebar">
            <p class="eyebrow">ChenFlow</p>
            <h1>小说编辑</h1>
          </div>
          <div class="editor-sidebar__actions">
            <button class="ghost-button ghost-button--small editor-sidebar__back" type="button" @click="backToWorkspace()">返回</button>
          </div>
          <nav class="sidebar-nav" aria-label="Editor">
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'novelEditor' }" @click="openNovelEditor(activeProject?.project.id)">已发布作品</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'projectSettings' }" @click="openProjectSettings()">项目设定</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'characters' }" @click="openCharacters()">人物卡</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'workshop' && workshopMode === 'chapters' }" @click="openWorkshopMode('chapters')">新增章节</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'workshop' && workshopMode === 'drafts' }" @click="openWorkshopMode('drafts')">草稿箱</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'generationTrace' }" @click="currentView = 'generationTrace'">生成过程</button>
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
              :active-project-status="activeProject?.project.indexing_status"
              :active-project-updated-at="activeProject?.project.updated_at"
              :loading="loading"
              :form="projectSettingsForm"
              :genre-options="genreOptions"
              :style-profile-options="styleProfileOptions"
              :graph-review="activeProject?.graphrag_review"
              :custom-genre-draft="customSettingsGenreDraft"
              :assistant-loading-kind="assistantLoadingKind === 'reference_work' ? null : assistantLoadingKind"
              :assistant-seed-world="assistantSeedWorld"
              :assistant-seed-writing="assistantSeedWriting"
              :world-suggestions="worldSuggestions"
              :writing-suggestions="writingSuggestions"
              @select-project="selectSettingsProject"
              @open-characters="openCharacters()"
              @prepare-graphrag="store.prepareGraphReview()"
              @save-graphrag-file="store.updateGraphReviewFile($event.filename, $event.content)"
              @start-index="store.indexProject()"
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
              @update:custom-genre-draft="customSettingsGenreDraft = $event"
              @apply-custom-genre="applyCustomGenre(projectSettingsForm, customSettingsGenreDraft)"
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
              @select-draft="openGeneration($event)"
              @create-chapter="submitCreateProjectChapter()"
              @save-chapter="submitUpdateProjectChapter()"
              @save-prompt="saveGenerationPromptDraft()"
              @generate-draft="submitAutoGenerate()"
              @continue-draft="store.refreshGenerationEvolution($event)"
              @publish-draft="submitPublishNovel()"
              @append-draft="submitAppendChapter()"
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
              :projects="projects"
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
              @open-detail="goToView('detail')"
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
              @back="goToView('detail')"
            />
          </template>
        </main>
      </div>
    </template>

    <template v-else-if="currentView === 'reader'">
      <NovelReaderPanel
        v-if="currentNovel && selectedChapter"
        :novel-title="currentNovel.title"
        :chapter="selectedChapter"
        :chapters="sortedChapters"
        :previous-chapter="previousChapter"
        :next-chapter="nextChapter"
        :has-navigation="hasChapterNavigation"
        :chapter-jump-no="chapterJumpNo"
        :can-edit="isManagingCurrentNovel"
        @back="goToView('detail')"
        @edit="openNovelEditor(activeProject?.project.id)"
        @select-chapter="selectChapterById"
        @jump="jumpToChapterNo"
        @update:chapter-jump-no="chapterJumpNo = $event"
      />
      <section v-else class="empty-panel">
        <p class="eyebrow">阅读</p>
        <h2>没有可阅读的章节</h2>
        <p>请回到作品详情，选择一本包含章节的小说。</p>
        <div class="empty-panel__actions">
          <button class="ghost-button" type="button" @click="goToView('detail')">返回作品</button>
          <button class="primary-button" type="button" @click="goToView('discover')">去发现</button>
        </div>
      </section>
    </template>

    <template v-else>
      <div class="workspace-shell">
        <button
          class="mobile-sidebar-toggle ghost-button ghost-button--small"
          type="button"
          :aria-expanded="mobileSidebarOpen ? 'true' : 'false'"
          aria-controls="primary-sidebar"
          @click="toggleMobileSidebar()"
        >
          {{ mobileSidebarOpen ? "收起菜单" : "打开菜单" }}
        </button>
        <aside id="primary-sidebar" class="sidebar panel panel--paper" :class="{ 'sidebar--mobile-open': mobileSidebarOpen }">
          <div class="brand brand--sidebar">
            <p class="eyebrow">晨流写作台</p>
            <h1>Chen Flow</h1>
          </div>
          <nav class="sidebar-nav" aria-label="Primary">
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'home' }" @click="goToView('home')">首页</button>
            <button class="sidebar-nav__item sidebar-nav__item--main" :class="{ 'sidebar-nav__item--active': currentView === 'studio' }" @click="openWorkspace()">我的小说</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'favorites' }" @click="openFavorites()">我的喜欢/收藏</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'discover' }" @click="goToView('discover')">发现</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'trash' }" @click="openTrash()">回收站</button>
          </nav>
          <div class="sidebar__footer">
            <template v-if="isAuthenticated">
              <div class="sidebar-user">
                <div class="sidebar-user__avatar">{{ (currentUser?.username?.slice(0, 1) ?? "U").toUpperCase() }}</div>
                <div class="sidebar-user__meta">
                  <strong>{{ currentUser?.username }}</strong>
                </div>
              </div>
              <button class="ghost-button ghost-button--small" @click="goToView('profile')">用户设置</button>
              <button class="ghost-button ghost-button--small" @click="store.logout()">退出</button>
            </template>
            <template v-else>
              <button class="ghost-button ghost-button--small" @click="openAuthPanel('login')">登录</button>
              <button class="primary-button primary-button--compact" @click="openAuthPanel('register')">创建账号</button>
            </template>
          </div>
        </aside>

        <main class="main-shell">
          <template v-if="currentView === 'home'">
            <section class="home-hub">
              <section class="panel panel--paper home-hub__hero">
                <div class="section-head">
                  <div>
                    <p class="panel-heading__kicker">首页</p>
                    <h2>{{ continueProject?.title ?? "先创建一个小说项目" }}</h2>
                    <p class="panel-heading__desc">
                      这里可以继续整理设定、规划章节、生成草稿，再决定哪些内容写进作品里。
                    </p>
                  </div>
                </div>
                <div class="home-hub__stats">
                  <article v-for="item in homeStats" :key="item.label" class="home-stat">
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </article>
                </div>
                <div class="hero__actions">
                  <button class="primary-button" @click="continueProject ? openContinueWriting(continueProject.id) : openProjectCreate()">
                    {{ continueProject ? "继续创作草稿" : "创建项目" }}
                  </button>
                  <button class="ghost-button" @click="openWorkspace()">打开工作区</button>
                  <button class="ghost-button" @click="goToView('discover')">去发现作品</button>
                </div>
              </section>
              <section class="home-hub__grid">
                <section class="panel panel--paper">
                  <div class="section-head">
                    <div><p class="panel-heading__kicker">最近项目</p><h2>回到你刚写过的内容</h2></div>
                    <button class="ghost-button ghost-button--small" type="button" @click="openWorkspace()">全部项目</button>
                  </div>
                  <div v-if="recentProjects.length" class="card-list">
                    <button
                      v-for="project in recentProjects"
                      :key="project.id"
                      class="project-item"
                      type="button"
                      @click="openContinueWriting(project.id)"
                    >
                      <strong>{{ project.title }}</strong>
                      <span>{{ project.genre }}</span>
                      <span class="project-item__summary">{{ project.world_brief || "回到这个项目，继续补设定、规划章节或整理草稿。" }}</span>
                      <em>{{ projectStatusLabel(project.indexing_status) }} / {{ formatDateTime(project.updated_at) }}</em>
                    </button>
                  </div>
                  <p v-else class="empty-text">还没有项目，先去创建一个。</p>
                </section>
                <section class="panel">
                  <div class="section-head">
                    <div><p class="panel-heading__kicker">热门作品</p><h2>打开就能读</h2></div>
                    <button class="ghost-button ghost-button--small" type="button" @click="goToView('discover')">全部作品</button>
                  </div>
                  <div v-if="homeSpotlightNovels.length" class="novel-grid novel-grid--list">
                    <article v-for="novel in homeSpotlightNovels" :key="novel.id" class="novel-card novel-card--clickable" @click="openNovelDetail(novel.id, 'home')">
                      <p class="novel-card__genre">{{ novel.genre }}</p>
                      <h3>{{ novel.title }}</h3>
                      <p class="novel-card__author">{{ novel.author }}</p>
                      <p class="novel-card__tagline">{{ novel.tagline }}</p>
                      <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
                    </article>
                  </div>
                  <p v-else class="empty-text">发现页暂时还没有可浏览的小说。</p>
                </section>
              </section>
            </section>
          </template>

          <template v-else-if="currentView === 'studio'">
            <StudioWorkspacePanel
              :selected-folder-name="selectedWorkspaceFolder?.name ?? '默认文件夹'"
              :workspace-search="workspaceSearch"
              :folders="sortedFolders"
              :selected-folder-id="selectedWorkspaceFolder?.id ?? null"
              :projects="pagedWorkspaceProjects"
              :moving-project-id="movingProjectId"
              :workspace-page="workspacePage"
              :workspace-page-size="workspacePageSize"
              :workspace-total-pages="workspaceTotalPages"
              :loading="loading"
              :show-create-folder="showCreateFolder"
              :folder-name="folderForm.name"
              @update:workspace-search="workspaceSearch = $event"
              @select-folder="selectWorkspaceFolder"
              @open-project-create="openProjectCreate()"
              @toggle-create-folder="toggleCreateFolder()"
              @open-project="openContinueWriting"
              @move-project-folder="assignProjectFolder"
              @delete-project="deleteProjectToTrash"
              @previous-page="previousWorkspacePage()"
              @next-page="nextWorkspacePage()"
              @update:folder-name="folderForm.name = $event"
              @submit-create-folder="submitCreateFolder()"
              @cancel-create-folder="closeCreateFolder()"
            />
          </template>

          <template v-else-if="currentView === 'favorites'">
            <section class="section-banner section-banner--catalog panel">
              <div><p class="panel-heading__kicker">我的喜欢/收藏</p><h2>{{ favoritesTab === "favorited" ? "我的收藏" : "我的喜欢" }}</h2></div>
              <div class="shelf-tools">
                <div class="mode-switch">
                  <button type="button" :class="{ 'mode-switch__item--active': favoritesTab === 'favorited' }" @click="favoritesTab = 'favorited'">收藏</button>
                  <button type="button" :class="{ 'mode-switch__item--active': favoritesTab === 'liked' }" @click="favoritesTab = 'liked'">喜欢</button>
                </div>
                <label class="field search-field"><span>搜索</span><input v-model="novelSearch" type="search" /></label>
              </div>
            </section>
            <div v-if="shelfDisplayNovels.length" class="novel-grid" :class="{ 'novel-grid--list': novelLayout === 'list' }">
              <article v-for="novel in shelfDisplayNovels" :key="novel.id" class="novel-card novel-card--saved novel-card--clickable" @click="openNovelDetail(novel.id, 'favorites')">
                <p class="novel-card__genre">{{ novel.genre }}</p>
                <h3>{{ novel.title }}</h3>
                <p class="novel-card__author">{{ novel.author }}</p>
                <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
              </article>
            </div>
            <section v-else class="empty-panel">
              <p class="eyebrow">书架</p>
              <h2>{{ novelSearch.trim() ? "没有找到匹配的作品" : "这里还没有作品" }}</h2>
              <p>{{ novelSearch.trim() ? "换个关键词试试，或者清空搜索后再看全部内容。" : "先去发现页读一读，把喜欢的作品加到这里。" }}</p>
              <div class="empty-panel__actions">
                <button v-if="novelSearch.trim()" class="ghost-button" type="button" @click="novelSearch = ''">清空搜索</button>
                <button class="primary-button" type="button" @click="goToView('discover')">去发现作品</button>
              </div>
            </section>
          </template>

          <template v-else-if="currentView === 'discover'">
            <section class="section-banner section-banner--catalog panel panel--paper">
              <div><p class="panel-heading__kicker">发现</p><h2>发现别人的小说</h2></div>
              <label class="field search-field"><span>搜索</span><input v-model="novelSearch" type="search" placeholder="标题、作者、简介或正文片段" /></label>
            </section>
            <section v-if="searchedNovels.length" class="novel-grid novel-grid--store" :class="{ 'novel-grid--list': novelLayout === 'list' }">
              <article v-for="novel in searchedNovels" :key="novel.id" class="novel-card novel-card--clickable" @click="openNovelDetail(novel.id, 'discover')">
                <p class="novel-card__genre">{{ novel.genre }}</p>
                <h3>{{ novel.title }}</h3>
                <p class="novel-card__author">{{ novel.author }}</p>
                <p class="novel-card__tagline">{{ novel.tagline }}</p>
                <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
                <div class="novel-card__meta"><span>{{ novel.likes_count }} 赞</span><span>{{ novel.favorites_count }} 收藏</span><span>{{ novel.comments_count }} 评论</span></div>
                <div class="novel-card__actions novel-card__actions--iconic">
                  <button class="novel-card__toggle novel-card__toggle--heart" :class="{ 'novel-card__toggle--active': novel.is_liked }" type="button" @click.stop="likeNovel(novel.id)">♥ {{ novel.likes_count }}</button>
                  <button class="novel-card__toggle novel-card__toggle--star" :class="{ 'novel-card__toggle--active': novel.is_favorited }" type="button" @click.stop="toggleSaveNovel(novel.id)">★ {{ novel.favorites_count }}</button>
                </div>
              </article>
            </section>
            <section v-else class="empty-panel">
              <p class="eyebrow">发现</p>
              <h2>没有找到匹配的作品</h2>
              <p>当前关键词没有命中标题、作者、简介或正文片段。可以换个词，或者先回到全部作品。</p>
              <div class="empty-panel__actions">
                <button class="ghost-button" type="button" @click="novelSearch = ''">查看全部作品</button>
              </div>
            </section>
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

          <template v-else-if="currentView === 'profile'">
            <section class="panel panel--paper">
              <div class="panel-heading">
                <div>
                  <p class="panel-heading__kicker">用户设置</p>
                  <h2>{{ currentUser?.username ?? "未登录" }}</h2>
                  <p class="panel-heading__desc">在这里维护你的简介、邮箱和联系方式。</p>
                </div>
              </div>
              <form v-if="isAuthenticated" class="form-stack" @submit.prevent="submitProfile()">
                <label class="field"><span>简介</span><textarea v-model="profileForm.bio" rows="4" /></label>
                <label class="field"><span>Email</span><input v-model="profileForm.email" type="email" /></label>
                <label class="field"><span>Phone</span><input v-model="profileForm.phone" /></label>
                <button class="primary-button" :disabled="loading">保存资料</button>
              </form>
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
                  :genre-options="genreOptions"
                  :genre-option-cards="genreOptionCards"
                  :style-profile-options="styleProfileOptions"
                  :custom-genre-draft="customGenreDraft"
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
                  @update:custom-genre-draft="customGenreDraft = $event"
                  @apply-custom-genre="applyCustomGenre(projectForm, customGenreDraft)"
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

          <template v-else-if="currentView === 'detail'">
            <NovelDetailPanel
              v-if="currentNovel"
              :novel="currentNovel"
              :sorted-chapters="sortedChapters"
              :comments="novelComments"
              :comment-content="commentForm.content"
              :loading="loading"
              :can-manage="isManagingCurrentNovel"
              @back="goToView(detailReturnView)"
              @open-reader="openReader"
              @like="likeNovel"
              @favorite="toggleSaveNovel"
              @manage="openNovelEditor(activeProject?.project.id)"
              @update:comment-content="commentForm.content = $event"
              @submit-comment="submitComment()"
            />
            <section v-else class="empty-panel">
              <p class="eyebrow">作品详情</p>
              <h2>没有打开的作品</h2>
              <p>从发现页、收藏或已发布作品列表中选择一部作品。</p>
              <div class="empty-panel__actions">
                <button class="ghost-button" type="button" @click="goToView(detailReturnView)">返回</button>
                <button class="primary-button" type="button" @click="goToView('discover')">去发现</button>
              </div>
            </section>
          </template>
        </main>
      </div>
    </template>
  </div>
</template>
