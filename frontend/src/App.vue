<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import ProfileSettingsPanel from "./components/workspace/ProfileSettingsPanel.vue";
import NovelDetailPanel from "./components/workspace/NovelDetailPanel.vue";
import NovelEditorPanel from "./components/workspace/NovelEditorPanel.vue";
import GenerationTracePanel from "./components/workspace/GenerationTracePanel.vue";
import ProjectWorkshopPanel from "./components/workspace/ProjectWorkshopPanel.vue";
import ProjectSettingsPanel from "./components/workspace/ProjectSettingsPanel.vue";
import NovelReaderPanel from "./components/workspace/NovelReaderPanel.vue";
import StudioWorkspacePanel from "./components/workspace/StudioWorkspacePanel.vue";
import WorkspaceSidebar from "./components/workspace/WorkspaceSidebar.vue";
import { useWorkbenchStore } from "./stores/workbench";
import type { CharacterCard, NovelCard, ProjectChapter, ProjectPayload, TrashItem } from "./types";

type ViewKey =
  | "home"
  | "discover"
  | "favorites"
  | "studio"
  | "trash"
  | "projectCreate"
  | "projectSettings"
  | "characters"
  | "workshop"
  | "generationTrace"
  | "novelEditor"
  | "reader"
  | "detail"
  | "profile"
  | "auth";

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
const authMode = ref<"register" | "login">("register");
const authError = ref("");
const showRegisterPassword = ref(false);
const showLoginPassword = ref(false);
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
const authReturnView = ref<ViewKey>("home");
const authRequestedView = ref<ViewKey | null>(null);
const hasRestoredViewState = ref(false);
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

const loginForm = reactive({ username: "", password: "" });
const registerForm = reactive({ username: "", password: "", confirmPassword: "", captcha_answer: "" });

const genreOptions = [
  "现代都市轻小说",
  "校园青春恋爱",
  "都市情感",
  "都市异能",
  "都市悬疑",
  "轻科幻",
  "奇幻冒险",
  "东方玄幻",
  "西幻史诗",
  "无限流",
  "推理悬疑",
  "惊悚恐怖",
  "历史架空",
  "古风言情",
  "治愈日常",
  "公路冒险",
];

const styleProfileOptions = [
  {
    value: "light_novel",
    label: "轻小说",
    description: "轻快、易读、偏人物互动，适合大多数网文和连载开局。",
  },
  {
    value: "lyrical_restrained",
    label: "抒情克制",
    description: "更细腻，允许少量意象和情绪潜流，但不走厚重散文。",
  },
  {
    value: "dialogue_driven",
    label: "对白驱动",
    description: "靠人物说话和来回拉扯推进，节奏更明快。",
  },
  {
    value: "cinematic_tense",
    label: "影视化紧张",
    description: "画面感强，段落更短，适合悬疑、冲突和追逐场景。",
  },
  {
    value: "warm_healing",
    label: "温柔治愈",
    description: "语气柔和，生活感更强，适合日常、陪伴和情感修复。",
  },
  {
    value: "epic_serious",
    label: "厚重史诗",
    description: "叙述更稳、更庄重，适合奇幻、历史和大设定冲突。",
  },
];

const emptyProject = (): ProjectPayload => ({
  title: "",
  genre: "现代都市",
  world_brief: "",
  writing_rules: "",
  style_profile: "lyrical_restrained",
});

const projectForm = reactive<ProjectPayload>(emptyProject());
const projectSettingsForm = reactive<ProjectPayload>(emptyProject());
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
}));
const managedNovels = computed(() => {
  const activeProjectId = activeProject.value?.project.id ?? null;
  const source = activeProjectId
    ? myNovels.value.filter((novel) => novel.project_id === activeProjectId)
    : myNovels.value;
  return [...source].sort((a, b) => parseServerTime(b.updated_at).getTime() - parseServerTime(a.updated_at).getTime());
});

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
  if (activeProject.value?.project.indexing_status !== "ready") return "整理资料后，项目会进入可生成章节草稿状态。";
  return "选中章节后输入这一章想怎么写，草稿会进入当前章节的草稿箱。";
});

const publishDefaults = computed(() => ({
  title: activeProject.value?.project.title || selectedDraftGeneration.value?.title || "",
  summary: selectedDraftGeneration.value?.summary || "",
  author_name: currentUser.value?.username || "",
}));

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
  if (status === "ready") return "可创作草稿";
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
    openAuthPanel("login", "studio");
    return;
  }
  currentView.value = "studio";
}

function openFavorites() {
  if (!isAuthenticated.value) {
    openAuthPanel("login", "favorites");
    return;
  }
  currentView.value = "favorites";
}

function openTrash() {
  if (!isAuthenticated.value) {
    openAuthPanel("login", "trash");
    return;
  }
  currentView.value = "trash";
}

function requireAuth(nextView: ViewKey) {
  if (!isAuthenticated.value) {
    openAuthPanel("register", nextView);
    return;
  }
  currentView.value = nextView;
}

function openAuthPanel(mode: "register" | "login", nextView?: ViewKey) {
  if (currentView.value !== "auth") authReturnView.value = currentView.value;
  authRequestedView.value = nextView ?? null;
  authMode.value = mode;
  currentView.value = "auth";
}

function closeAuthPanel() {
  authError.value = "";
  currentView.value = authReturnView.value;
  authRequestedView.value = null;
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
  store.clearFeedback();
}

function syncProjectSettingsForm() {
  const project = activeProject.value?.project;
  if (!project) return;
  projectSettingsForm.title = project.title;
  projectSettingsForm.genre = project.genre;
  projectSettingsForm.world_brief = project.world_brief;
  projectSettingsForm.writing_rules = project.writing_rules;
  projectSettingsForm.style_profile = project.style_profile;
}

function applyGenre(target: ProjectPayload, value: string) {
  target.genre = value;
}

function styleProfileLabel(value: string) {
  return styleProfileOptions.find((item) => item.value === value)?.label ?? "轻小说";
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
    publishForm.title = activeProject.value?.project.title || found.title || "";
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
  await store.toggleLikeNovel(novelId);
}

async function toggleSaveNovel(novelId: number) {
  await store.toggleFavoriteNovel(novelId);
}

async function submitRegister() {
  authError.value = "";
  if (registerForm.password !== registerForm.confirmPassword) {
    authError.value = "两次输入的密码不一致。";
    return;
  }
  if (!captcha.value) {
    await store.refreshCaptcha();
    return;
  }
  await store.register({
    username: registerForm.username,
    password: registerForm.password,
    captcha_answer: registerForm.captcha_answer,
    captcha_token: captcha.value.token,
  });
  if (isAuthenticated.value) {
    currentView.value = authRequestedView.value ?? "studio";
    authRequestedView.value = null;
  }
}

async function submitLogin() {
  authError.value = "";
  await store.login(loginForm);
  if (isAuthenticated.value) {
    currentView.value = authRequestedView.value ?? "studio";
    authRequestedView.value = null;
  }
}

async function submitCreateProject() {
  await store.createProject(projectForm);
  if (!error.value && activeProject.value?.project) {
    Object.assign(projectForm, emptyProject());
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
  await store.submitNovelComment(commentForm.content);
  if (!error.value) commentForm.content = "";
}

async function submitPublishNovel() {
  if (!activeProject.value?.project || !selectedProjectChapter.value || !selectedDraftGeneration.value) return;
  const created = await store.publishNovelFromGeneration({
    project_id: activeProject.value.project.id,
    project_chapter_id: selectedProjectChapter.value.id,
    generation_id: selectedDraftGeneration.value.id,
    title: publishForm.title.trim() || activeProject.value.project.title,
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
  if (!currentNovel.value || !activeProject.value?.project || !selectedProjectChapter.value || !selectedDraftGeneration.value) return;
  await store.appendNovelChapter(currentNovel.value.id, {
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
      <section class="auth-page">
        <section class="auth-modal auth-modal--page panel">
          <div class="panel-heading auth-modal__head">
            <div>
              <p class="panel-heading__kicker">{{ authMode === "register" ? "创建账号" : "登录" }}</p>
              <h2>{{ authMode === "register" ? "创建你的写作空间" : "回到你的项目" }}</h2>
            </div>
            <button class="ghost-button ghost-button--small" type="button" @click="closeAuthPanel()">稍后再说</button>
          </div>
          <div class="auth-tabs">
            <button class="auth-tab" :class="{ 'auth-tab--active': authMode === 'register' }" type="button" @click="authMode = 'register'">注册</button>
            <button class="auth-tab" :class="{ 'auth-tab--active': authMode === 'login' }" type="button" @click="authMode = 'login'">登录</button>
          </div>
          <form v-if="authMode === 'register'" class="form-stack" @submit.prevent="submitRegister()">
            <label class="field"><span>用户名</span><input v-model.trim="registerForm.username" autocomplete="username" /></label>
            <label class="field">
              <span>密码</span>
              <div class="password-field">
                <input v-model="registerForm.password" :type="showRegisterPassword ? 'text' : 'password'" autocomplete="new-password" />
                <button class="password-toggle" type="button" @click="showRegisterPassword = !showRegisterPassword">{{ showRegisterPassword ? "隐藏" : "显示" }}</button>
              </div>
            </label>
            <label class="field"><span>确认密码</span><input v-model="registerForm.confirmPassword" :type="showRegisterPassword ? 'text' : 'password'" /></label>
            <label class="field">
              <span>验证码</span>
              <div class="captcha-row">
                <div class="captcha-box">{{ captcha?.challenge ?? "正在生成..." }}</div>
                <button class="ghost-button ghost-button--small" type="button" @click="store.refreshCaptcha()">换一个</button>
              </div>
              <input v-model.trim="registerForm.captcha_answer" inputmode="numeric" />
            </label>
            <button class="primary-button" :disabled="loading">{{ loading ? "正在注册..." : "注册并登录" }}</button>
          </form>
          <form v-else class="form-stack" @submit.prevent="submitLogin()">
            <label class="field"><span>用户名</span><input v-model.trim="loginForm.username" autocomplete="username" /></label>
            <label class="field">
              <span>密码</span>
              <div class="password-field">
                <input v-model="loginForm.password" :type="showLoginPassword ? 'text' : 'password'" autocomplete="current-password" />
                <button class="password-toggle" type="button" @click="showLoginPassword = !showLoginPassword">{{ showLoginPassword ? "隐藏" : "显示" }}</button>
              </div>
            </label>
            <button class="primary-button" :disabled="loading">{{ loading ? "正在登录..." : "登录" }}</button>
          </form>
        </section>
      </section>
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
              @select-project="selectSettingsProject"
              @open-characters="openCharacters()"
              @prepare-graphrag="store.prepareGraphReview()"
              @save-graphrag-file="store.updateGraphReviewFile($event.filename, $event.content)"
              @start-index="store.indexProject()"
              @submit="submitUpdateProject()"
              @update:title="projectSettingsForm.title = $event"
              @update:genre="projectSettingsForm.genre = $event"
              @update:world-brief="projectSettingsForm.world_brief = $event"
              @update:writing-rules="projectSettingsForm.writing_rules = $event"
              @update:style-profile="projectSettingsForm.style_profile = $event"
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
              :can-append-to-novel="Boolean(currentNovel && isManagingCurrentNovel)"
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
              @continue-draft="store.continueGeneration($event)"
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

    <template v-else>
      <div class="workspace-shell">
        <aside class="sidebar panel panel--paper">
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
              @toggle-create-folder="showCreateFolder = !showCreateFolder"
              @open-project="openContinueWriting"
              @move-project-folder="assignProjectFolder"
              @delete-project="deleteProjectToTrash"
              @previous-page="previousWorkspacePage()"
              @next-page="nextWorkspacePage()"
              @update:folder-name="folderForm.name = $event"
              @submit-create-folder="submitCreateFolder()"
              @cancel-create-folder="showCreateFolder = false"
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
          </template>

          <template v-else-if="currentView === 'discover'">
            <section class="section-banner section-banner--catalog panel panel--paper">
              <div><p class="panel-heading__kicker">发现</p><h2>发现别人的小说</h2></div>
              <label class="field search-field"><span>搜索</span><input v-model="novelSearch" type="search" placeholder="标题、作者、简介或正文片段" /></label>
            </section>
            <section class="novel-grid novel-grid--store" :class="{ 'novel-grid--list': novelLayout === 'list' }">
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
          </template>

          <template v-else-if="currentView === 'trash'">
            <section class="section-banner panel panel--paper">
              <div><p class="panel-heading__kicker">回收站</p><h2>已删除内容</h2></div>
              <div class="hero__stats">
                <span>项目 {{ trashSummary.project }}</span>
                <span>作品 {{ trashSummary.novel }}</span>
                <span>人物卡 {{ trashSummary.character_card }}</span>
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
                <form class="form-stack" @submit.prevent="submitCreateProject()">
                  <label class="field">
                    <span>小说标题</span>
                    <input v-model="projectForm.title" maxlength="255" placeholder="例如：在晚一点下雨的城市" />
                    <small class="field-hint">建议 6 到 20 字。工作标题也可以，后面还能改。</small>
                  </label>
                  <label class="field">
                    <span>题材类型</span>
                    <select v-model="projectForm.genre">
                      <option v-for="option in genreOptions" :key="option" :value="option">{{ option }}</option>
                    </select>
                    <small class="field-hint">这里只选一个最接近的大类就行，比如“都市悬疑”或“轻科幻”。别的元素后面写进世界观或章节前提。</small>
                    <div class="choice-chips">
                      <button
                        v-for="option in genreOptions"
                        :key="`create-genre-${option}`"
                        class="choice-chip"
                        :class="{ 'choice-chip--active': projectForm.genre === option }"
                        type="button"
                        @click="applyGenre(projectForm, option)"
                      >
                        {{ option }}
                      </button>
                    </div>
                    <input v-model="projectForm.genre" maxlength="100" placeholder="也可以自定义，例如：沿海城市成长 / 校园悬疑 / 通勤科幻日常" />
                  </label>
                  <label class="field">
                    <span>世界观</span>
                    <textarea
                      v-model="projectForm.world_brief"
                      rows="5"
                      maxlength="4000"
                      placeholder="例如：故事发生在一座被旧电车、海雾和潮汐包围的沿海城市。这里的人习惯按照天气预报和末班车时刻安排生活，城市表面平静，很多关系却会在季节更替里悄悄松动。"
                    />
                    <small class="field-hint">写“规则”和“差异”最有用：时代背景、能力体系、势力结构、资源稀缺、公开禁忌。纯风景描写帮助不大。</small>
                  </label>
                  <label class="field">
                    <span>写作偏好</span>
                    <textarea
                      v-model="projectForm.writing_rules"
                      rows="4"
                      maxlength="2000"
                      placeholder="例如：第三人称近距离；语气清澈克制；多写天气、光线、空间和动作；情绪通过停顿与细节显现；避免悬浮告白、过度煽情和密集玩梗。"
                    />
                    <small class="field-hint">这里适合写人称、节奏、篇幅、禁写项、关系推进方式。不要重复世界观，也不用把剧情梗概再写一遍。</small>
                  </label>
                  <label class="field">
                    <span>文风预设</span>
                    <select v-model="projectForm.style_profile">
                      <option v-for="option in styleProfileOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                    <small class="field-hint">推荐先从一个稳定预设开始。当前选择：{{ styleProfileLabel(projectForm.style_profile) }}。</small>
                    <div class="choice-cards">
                      <button
                        v-for="option in styleProfileOptions"
                        :key="`create-style-${option.value}`"
                        class="choice-card"
                        :class="{ 'choice-card--active': projectForm.style_profile === option.value }"
                        type="button"
                        @click="projectForm.style_profile = option.value"
                      >
                        <strong>{{ option.label }}</strong>
                        <span>{{ option.description }}</span>
                      </button>
                    </div>
                  </label>
                  <button class="primary-button" :disabled="loading">创建项目</button>
                </form>
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
            <NovelEditorPanel
              v-else
              :managed-novels="managedNovels"
              :novel="null"
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
  </div>
</template>
