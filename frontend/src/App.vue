<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { useWorkbenchStore } from "./stores/workbench";
import type { CharacterCard, NovelCard, ProjectFolder, ProjectPayload, TrashItem } from "./types";

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
  | "novelEditor"
  | "reader"
  | "detail"
  | "profile"
  | "auth";

const store = useWorkbenchStore();
const {
  bootstrap,
  captcha,
  currentUser,
  projects,
  projectFolders,
  trashItems,
  novels,
  favoriteNovels,
  myNovels,
  profile,
  currentNovel,
  novelComments,
  activeProject,
  currentGeneration,
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
const writingMode = ref<"auto" | "advanced">("auto");
const favoritesTab = ref<"liked" | "favorited">("favorited");
const novelLayout = ref<"grid" | "list">("grid");
const novelSearch = ref("");
const workspaceSearch = ref("");
const folderPanelCollapsed = ref(false);
const showCreateFolder = ref(false);
const folderForm = reactive({ name: "" });
const movingProjectId = ref<number | null>(null);
const selectedWorkspaceFolderId = ref<number | null>(null);
const workspacePage = ref(1);
const workspacePageSize = ref(6);
let feedbackTimer: number | null = null;

const loginForm = reactive({ username: "", password: "" });
const registerForm = reactive({ username: "", password: "", confirmPassword: "", captcha_answer: "" });

const emptyProject = (): ProjectPayload => ({
  title: "",
  genre: "现代都市轻小说",
  premise: "",
  world_brief: "",
  writing_rules: "",
  style_profile: "light_novel",
});

const projectForm = reactive<ProjectPayload>(emptyProject());
const projectSettingsForm = reactive<ProjectPayload>(emptyProject());
const quickProjectForm = reactive({ idea: "" });

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
  prompt: "",
  search_method: "local",
  response_type: "Multiple Paragraphs",
  use_global_search: true,
  use_scene_card: true,
  use_refiner: true,
  write_evolution: true,
});
const autoGenerationForm = reactive({ idea: "" });

const profileForm = reactive({
  bio: "偏爱都市、青春与细腻情绪流动的故事。",
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
const selectedDraftProjectId = ref<number | null>(null);
const selectedDraftGenerationId = ref<number | null>(null);
const selectedSettingsProjectId = ref<number | null>(null);

const featuredNovel = computed(() => novels.value[0] ?? null);
const hasProject = computed(() => Boolean(activeProject.value));
const likedNovels = computed(() => novels.value.filter((novel) => novel.is_liked));
const shelfDisplayNovels = computed(() => {
  const keyword = novelSearch.value.trim().toLowerCase();
  const source = favoritesTab.value === "favorited" ? favoriteNovels.value : likedNovels.value;
  return keyword ? source.filter((novel) => matchesNovelSearch(novel, keyword)) : source;
});
const searchedNovels = computed(() => {
  const keyword = novelSearch.value.trim().toLowerCase();
  return keyword ? novels.value.filter((novel) => matchesNovelSearch(novel, keyword)) : novels.value;
});
const sortedFolders = computed<ProjectFolder[]>(() =>
  [...projectFolders.value].sort((a, b) => a.sort_order - b.sort_order || a.created_at.localeCompare(b.created_at)),
);
const selectedWorkspaceFolder = computed<ProjectFolder | null>(() => {
  if (!sortedFolders.value.length) return null;
  return sortedFolders.value.find((item) => item.id === selectedWorkspaceFolderId.value) ?? sortedFolders.value[0] ?? null;
});
const filteredWorkspaceProjects = computed(() => {
  const folderId = selectedWorkspaceFolder.value?.id ?? null;
  const keyword = workspaceSearch.value.trim().toLowerCase();
  const source = projects.value.filter((project) => (folderId ? project.folder_id === folderId : true));
  if (!keyword) return source;
  return source.filter((project) =>
    [project.title, project.genre, project.premise, project.world_brief, project.writing_rules].join(" ").toLowerCase().includes(keyword),
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
const nextNovelChapterNo = computed(() =>
  currentNovel.value ? Math.max(0, ...currentNovel.value.chapters.map((chapter) => chapter.chapter_no)) + 1 : 1,
);
const projectGenerations = computed(() => activeProject.value?.generations ?? []);
const selectedDraftGeneration = computed(() => {
  if (!projectGenerations.value.length) return null;
  return projectGenerations.value.find((item) => item.id === selectedDraftGenerationId.value) ?? projectGenerations.value[0] ?? null;
});

const currentStep = computed(() => {
  if (!isAuthenticated.value) return "先创建账号，再开始写自己的小说。";
  if (!hasProject.value) return "先新建项目，确定标题、题材和故事方向。";
  if (!(activeProject.value?.character_cards.length ?? 0)) return "先添加主要人物卡，再进入写作。";
  if (activeProject.value?.project.indexing_status !== "ready") return "整理资料后，项目会进入可写作状态。";
  return "输入当前场景目标，开始生成正文。";
});

const publishDefaults = computed(() => ({
  title: currentGeneration.value?.title || activeProject.value?.project.title || "",
  summary: currentGeneration.value?.summary || "",
  author_name: currentUser.value?.username || "",
}));

function formatDateTime(value: string | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function projectStatusLabel(status: string | undefined) {
  if (!status) return "未开始";
  if (status === "ready") return "可以写作";
  if (status === "indexing") return "资料准备中";
  if (status === "failed") return "准备失败";
  if (status === "stale") return "资料待更新";
  return status;
}

function goToView(view: ViewKey) {
  currentView.value = view;
}

function openWorkspace() {
  if (!isAuthenticated.value) {
    openAuthPanel("login");
    return;
  }
  currentView.value = "studio";
}

function openFavorites() {
  if (!isAuthenticated.value) {
    openAuthPanel("login");
    return;
  }
  currentView.value = "favorites";
}

function openTrash() {
  if (!isAuthenticated.value) {
    openAuthPanel("login");
    return;
  }
  currentView.value = "trash";
}

function requireAuth(nextView: ViewKey) {
  if (!isAuthenticated.value) {
    openAuthPanel("register");
    return;
  }
  currentView.value = nextView;
}

function openAuthPanel(mode: "register" | "login") {
  authMode.value = mode;
  currentView.value = "auth";
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
  projectSettingsForm.premise = project.premise;
  projectSettingsForm.world_brief = project.world_brief;
  projectSettingsForm.writing_rules = project.writing_rules;
  projectSettingsForm.style_profile = project.style_profile;
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
  draftForm.title = generation.title || "";
  draftForm.summary = generation.summary || "";
  draftForm.content = generation.content || "";
  draftForm.chapter_no = 1;
  appendChapterForm.title = generation.title || "";
  appendChapterForm.chapter_no = nextNovelChapterNo.value;
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
  const targetProjectId = projectId ?? selectedDraftProjectId.value ?? activeProject.value?.project.id ?? projects.value[0]?.id ?? null;
  if (targetProjectId && activeProject.value?.project.id !== targetProjectId) {
    await store.selectProject(targetProjectId);
  }
  if (!error.value) {
    selectedDraftProjectId.value = targetProjectId;
    selectedDraftGenerationId.value = currentGeneration.value?.id ?? activeProject.value?.generations[0]?.id ?? null;
  }
  syncNovelManageForm();
  currentView.value = "novelEditor";
}

function backToWorkspace() {
  currentView.value = "studio";
}

async function openNovelDetail(novelId: number) {
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

function selectChapterById(value: number | string) {
  selectedChapterId.value = Number(value);
}

function jumpToChapterNo() {
  const target = sortedChapters.value.find((chapter) => chapter.chapter_no === Number(chapterJumpNo.value));
  if (target) selectedChapterId.value = target.id;
}

function openGeneration(id: number) {
  const found = activeProject.value?.generations.find((item) => item.id === id) ?? null;
  currentGeneration.value = found;
  selectedDraftGenerationId.value = found?.id ?? null;
  if (found) {
    publishForm.title = found.title || activeProject.value?.project.title || "";
    publishForm.summary = found.summary || "";
    syncDraftFromGeneration(found);
  }
}

async function selectDraftProject(value: number | string) {
  const projectId = Number(value);
  if (!projectId) {
    selectedDraftProjectId.value = null;
    selectedDraftGenerationId.value = null;
    return;
  }
  await store.selectProject(projectId);
  if (!error.value) {
    selectedDraftProjectId.value = projectId;
    selectedDraftGenerationId.value = currentGeneration.value?.id ?? activeProject.value?.generations[0]?.id ?? null;
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

function toggleFolderPanel() {
  folderPanelCollapsed.value = !folderPanelCollapsed.value;
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
  if (isAuthenticated.value) currentView.value = "studio";
}

async function submitLogin() {
  authError.value = "";
  await store.login(loginForm);
  if (isAuthenticated.value) currentView.value = "studio";
}

async function submitCreateProject() {
  await store.createProject(projectForm);
  if (!error.value && activeProject.value?.project) {
    Object.assign(projectForm, emptyProject());
    syncProjectSettingsForm();
    currentView.value = "characters";
  }
}

async function submitQuickProject() {
  const idea = quickProjectForm.idea.trim();
  if (idea.length < 12) {
    authError.value = "请至少写 12 个字，让 AI 知道你想写什么。";
    return;
  }
  const firstLine = idea.split(/\r?\n/).find((line) => line.trim())?.trim() ?? idea;
  await store.createProject({
    title: firstLine.slice(0, 28),
    genre: "AI 自动创作",
    premise: idea,
    world_brief: "",
    writing_rules: "",
    style_profile: "light_novel",
  });
  if (!error.value && activeProject.value?.project) {
    autoGenerationForm.idea = idea;
    currentView.value = "characters";
  }
}

async function submitUpdateProject() {
  await store.updateProject(projectSettingsForm);
  if (!error.value) syncProjectSettingsForm();
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
  const idea = autoGenerationForm.idea.trim();
  if (!idea) {
    authError.value = "先写下你的想法，再让 AI 生成。";
    return;
  }
  await store.generate({
    prompt: `请根据下面这段想法，自动理解人物、场景、冲突和情绪走向，写成一段完整的小说正文。\n\n${idea}`,
    search_method: "local",
    response_type: "Multiple Paragraphs",
    use_global_search: false,
    use_scene_card: true,
    use_refiner: true,
    write_evolution: true,
  });
}

async function submitComment() {
  await store.submitNovelComment(commentForm.content);
  if (!error.value) commentForm.content = "";
}

async function submitPublishNovel() {
  if (!activeProject.value?.project || !currentGeneration.value) return;
  const created = await store.publishNovelFromGeneration({
    project_id: activeProject.value.project.id,
    generation_id: currentGeneration.value.id,
    title: publishForm.title.trim(),
    author_name: publishForm.author_name.trim() || currentUser.value?.username || "匿名",
    summary: publishForm.summary.trim(),
    tagline: publishForm.tagline.trim(),
    visibility: publishForm.visibility,
    chapter_title: draftForm.title.trim() || currentGeneration.value.title,
    chapter_summary: draftForm.summary.trim() || currentGeneration.value.summary,
    chapter_content: draftForm.content.trim() || currentGeneration.value.content,
    chapter_no: draftForm.chapter_no,
  });
  if (created) currentView.value = "detail";
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

async function submitAppendChapter() {
  if (!currentNovel.value || !activeProject.value?.project || !selectedDraftGeneration.value) return;
  await store.appendNovelChapter(currentNovel.value.id, {
    project_id: activeProject.value.project.id,
    generation_id: selectedDraftGeneration.value.id,
    title: appendChapterForm.title.trim() || draftForm.title.trim(),
    summary: draftForm.summary.trim(),
    content: draftForm.content.trim(),
    chapter_no: appendChapterForm.chapter_no || null,
  });
  appendChapterForm.title = "";
  appendChapterForm.chapter_no = nextNovelChapterNo.value;
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
  void store.initialize();
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

watch(nextNovelChapterNo, (next) => {
  appendChapterForm.chapter_no = next;
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
  if (activeProject.value?.project.id && !selectedSettingsProjectId.value) {
    selectedSettingsProjectId.value = activeProject.value.project.id;
  }
  if (activeProject.value?.project.id && !selectedDraftProjectId.value) {
    selectedDraftProjectId.value = activeProject.value.project.id;
  }
}, { immediate: true });

watch(profile, (next) => {
  if (!next) return;
  profileForm.bio = next.bio ?? "";
  profileForm.email = next.email ?? "";
  profileForm.phone = next.phone ?? "";
}, { immediate: true });

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
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">{{ authMode === "register" ? "创建账号" : "登录" }}</p>
              <h2>{{ authMode === "register" ? "创建你的写作空间" : "回到你的项目" }}</h2>
            </div>
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

    <template v-else-if="['novelEditor', 'projectSettings', 'characters', 'workshop'].includes(currentView)">
      <div class="editor-shell">
        <aside class="editor-sidebar panel panel--paper">
          <div class="brand brand--sidebar">
            <p class="eyebrow">ChenFlow</p>
            <h1>小说编辑</h1>
          </div>
          <div class="editor-sidebar__actions">
            <button class="ghost-button ghost-button--small" type="button" @click="backToWorkspace()">返回</button>
            <button class="ghost-button ghost-button--small" type="button" @click="goToView('profile')">我的</button>
          </div>
          <nav class="sidebar-nav" aria-label="Editor">
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'novelEditor' }" @click="openNovelEditor(activeProject?.project.id)">作品编辑</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'projectSettings' }" @click="openProjectSettings()">项目设定</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'characters' }" @click="openCharacters()">人物卡</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'workshop' }" @click="activeProject?.project.id && openWorkshop(activeProject.project.id)">写作</button>
          </nav>
        </aside>

        <main class="main-shell">
          <template v-if="currentView === 'projectSettings'">
            <main v-if="isAuthenticated && hasProject" class="workspace workspace--single">
              <section class="panel">
                <div class="panel-heading">
                  <div>
                    <p class="panel-heading__kicker">选择项目</p>
                    <h2>先选要编辑的小说项目</h2>
                    <p class="panel-heading__desc">只展示当前最重要的信息：标题、题材、状态和最近更新时间。</p>
                  </div>
                </div>
                <div class="project-list project-list--select" v-if="projects.length">
                  <button
                    v-for="project in projects"
                    :key="project.id"
                    class="project-item"
                    :class="{ 'project-item--active': activeProject?.project.id === project.id }"
                    type="button"
                    @click="selectSettingsProject(project.id)"
                  >
                    <strong>{{ project.title }}</strong>
                    <span>{{ project.genre }}</span>
                    <em>{{ projectStatusLabel(project.indexing_status) }} / {{ formatDateTime(project.updated_at) }}</em>
                  </button>
                </div>
              </section>
              <section class="panel panel--paper">
                <div class="panel-heading">
                  <div>
                    <p class="panel-heading__kicker">项目设定</p>
                    <h2>{{ activeProject?.project.title }}</h2>
                    <p class="panel-heading__desc">先确定核心前提，再补写作偏好和文风，层级会更清楚。</p>
                  </div>
                  <div class="mode-switch">
                    <button class="ghost-button ghost-button--small" type="button" @click="openCharacters()">人物卡</button>
                    <button class="primary-button primary-button--compact" :disabled="loading" @click="store.indexProject()">整理资料</button>
                  </div>
                </div>
                <div class="project-meta">
                  <div><span>题材</span><strong>{{ activeProject?.project.genre }}</strong></div>
                  <div><span>资料状态</span><strong>{{ projectStatusLabel(activeProject?.project.indexing_status) }}</strong></div>
                  <div><span>最近更新</span><strong>{{ formatDateTime(activeProject?.project.updated_at) }}</strong></div>
                </div>
                <form class="form-stack" @submit.prevent="submitUpdateProject()">
                  <label class="field"><span>小说标题</span><input v-model="projectSettingsForm.title" maxlength="255" /></label>
                  <label class="field"><span>题材类型</span><input v-model="projectSettingsForm.genre" maxlength="100" /></label>
                  <label class="field"><span>故事前提</span><textarea v-model="projectSettingsForm.premise" rows="5" maxlength="2000" /></label>
                  <label class="field"><span>世界观</span><textarea v-model="projectSettingsForm.world_brief" rows="5" maxlength="4000" /></label>
                  <label class="field"><span>写作偏好</span><textarea v-model="projectSettingsForm.writing_rules" rows="4" maxlength="2000" /></label>
                  <label class="field"><span>文风预设</span><select v-model="projectSettingsForm.style_profile"><option value="light_novel">轻小说</option><option value="lyrical_restrained">抒情克制</option></select></label>
                  <button class="primary-button" :disabled="loading">保存项目设定</button>
                </form>
              </section>
            </main>
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
            <main v-if="isAuthenticated && hasProject" class="workspace workspace--workshop">
              <section class="workspace__column workspace__column--center">
                <section class="panel panel--paper">
                  <div class="panel-heading">
                    <div><p class="panel-heading__kicker">写作</p><h2>{{ activeProject?.project.title }}</h2></div>
                    <div class="mode-switch">
                      <button type="button" :class="{ 'mode-switch__item--active': writingMode === 'auto' }" @click="writingMode = 'auto'">自动</button>
                      <button type="button" :class="{ 'mode-switch__item--active': writingMode === 'advanced' }" @click="writingMode = 'advanced'">精细</button>
                    </div>
                  </div>
                  <form v-if="writingMode === 'auto'" class="form-stack" @submit.prevent="submitAutoGenerate()">
                    <label class="field"><span>把想法写在这里</span><textarea v-model="autoGenerationForm.idea" rows="10" /></label>
                    <button class="primary-button" :disabled="loading">让 AI 写一段</button>
                  </form>
                  <form v-else class="form-stack" @submit.prevent="store.generate(generationForm)">
                    <label class="field"><span>这一段想怎么写</span><textarea v-model="generationForm.prompt" rows="6" /></label>
                    <div class="inline-row">
                      <label class="field"><span>参考范围</span><select v-model="generationForm.search_method"><option value="local">最相关内容</option><option value="global">更多全局信息</option><option value="drift">自由联想</option><option value="basic">基础参考</option></select></label>
                      <label class="field"><span>长度和形式</span><input v-model="generationForm.response_type" /></label>
                    </div>
                    <button class="primary-button" :disabled="loading">生成正文</button>
                  </form>
                </section>
              </section>
              <section class="workspace__column">
                <section class="panel panel--warm guide-card"><p class="panel-heading__kicker">下一步</p><h2>{{ currentStep }}</h2></section>
                <section class="panel">
                  <div class="panel-heading"><div><p class="panel-heading__kicker">生成记录</p><h2>草稿</h2></div></div>
                  <div class="timeline" v-if="activeProject?.generations.length">
                    <button v-for="item in activeProject.generations" :key="item.id" class="timeline-item" type="button" @click="openGeneration(item.id)"><strong>{{ item.title }}</strong><span>{{ item.summary }}</span><em>{{ formatDateTime(item.created_at) }}</em></button>
                  </div>
                </section>
              </section>
            </main>
          </template>

          <template v-else-if="currentView === 'novelEditor'">
            <section v-if="currentNovel && isManagingCurrentNovel" class="novel-editor">
              <section class="panel panel--paper">
                <div class="section-head"><div><p class="panel-heading__kicker">作品编辑</p><h2>{{ currentNovel.title }}</h2></div><button class="ghost-button ghost-button--small" type="button" @click="goToView('detail')">查看作品</button></div>
                <form class="form-stack" @submit.prevent="submitUpdateNovel()">
                  <label class="field"><span>作品标题</span><input v-model="manageNovelForm.title" /></label>
                  <label class="field"><span>作者名</span><input v-model="manageNovelForm.author_name" /></label>
                  <label class="field"><span>宣传语</span><input v-model="manageNovelForm.tagline" /></label>
                  <label class="field"><span>作品简介</span><textarea v-model="manageNovelForm.summary" rows="4" /></label>
                  <label class="field"><span>谁可以看</span><select v-model="manageNovelForm.visibility"><option value="public">公开</option><option value="private">仅自己可见</option></select></label>
                  <div class="hero__actions">
                    <button class="primary-button" :disabled="loading">保存作品信息</button>
                    <button class="ghost-button" type="button" @click="currentNovel && store.deleteNovel(currentNovel.id)">删除作品</button>
                  </div>
                </form>
              </section>
            </section>
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
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'studio' }" @click="openWorkspace()">我的小说</button>
            <div v-if="currentView === 'studio'" class="sidebar-nav__subtools">
              <button class="ghost-button ghost-button--small" type="button" @click="showCreateFolder = !showCreateFolder">+ 文件夹</button>
              <button class="ghost-button ghost-button--small" type="button" @click="toggleFolderPanel()">{{ folderPanelCollapsed ? "展开" : "收起" }}</button>
            </div>
            <div v-if="currentView === 'studio' && !folderPanelCollapsed" class="folder-list">
              <button
                v-for="folder in sortedFolders"
                :key="folder.id"
                class="folder-list__item"
                :class="{ 'folder-list__item--active': selectedWorkspaceFolder?.id === folder.id }"
                @click="selectWorkspaceFolder(folder.id)"
              >
                <span>{{ folder.name }}</span>
                <em>{{ folder.project_count }}</em>
              </button>
            </div>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'favorites' }" @click="openFavorites()">我的喜欢/收藏</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'discover' }" @click="goToView('discover')">发现</button>
            <button class="sidebar-nav__item" :class="{ 'sidebar-nav__item--active': currentView === 'trash' }" @click="openTrash()">回收站</button>
          </nav>
          <div class="sidebar__footer">
            <template v-if="isAuthenticated">
              <span class="topbar__user">{{ currentUser?.username }}</span>
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
            <section class="hero hero--showcase">
              <div class="hero__main">
                <p class="hero__label">首页推荐</p>
                <h2>{{ featuredNovel?.title ?? "正在准备推荐小说" }}</h2>
                <p class="hero__lede">{{ featuredNovel?.tagline ?? "从发现里找到作品，也从这里开始自己的小说。" }}</p>
                <p class="hero__excerpt">{{ featuredNovel?.latest_excerpt ?? "创建项目、归档到文件夹、维护人物卡，然后进入写作。" }}</p>
                <div class="hero__actions">
                  <button class="primary-button" @click="goToView('discover')">去发现</button>
                  <button class="ghost-button" @click="openWorkspace()">我的小说</button>
                </div>
              </div>
            </section>
          </template>

          <template v-else-if="currentView === 'studio'">
            <section class="section-banner panel panel--paper">
              <div><p class="panel-heading__kicker">我的小说</p><h2>{{ selectedWorkspaceFolder?.name ?? "默认文件夹" }}</h2></div>
              <div class="shelf-tools">
                <label class="field search-field"><span>搜索</span><input v-model="workspaceSearch" type="search" placeholder="搜索标题、题材或设定" /></label>
                <label class="field">
                  <span>文件夹</span>
                  <select :value="selectedWorkspaceFolder?.id ?? ''" @change="selectWorkspaceFolder(($event.target as HTMLSelectElement).value)">
                    <option v-for="folder in sortedFolders" :key="folder.id" :value="folder.id">{{ folder.name }}</option>
                  </select>
                </label>
              </div>
            </section>
            <section class="panel panel--paper">
              <div class="section-head">
                <div><p class="panel-heading__kicker">项目</p><h2>当前文件夹里的小说项目</h2></div>
                <button class="primary-button primary-button--compact" type="button" @click="goToView('projectCreate')">新建小说项目</button>
              </div>
              <div class="novel-grid" v-if="pagedWorkspaceProjects.length">
                <article v-for="project in pagedWorkspaceProjects" :key="project.id" class="novel-card novel-card--clickable" @click="openWorkshop(project.id)">
                  <p class="novel-card__genre">{{ project.genre }}</p>
                  <h3>{{ project.title }}</h3>
                  <p class="novel-card__text">{{ project.premise }}</p>
                  <p class="novel-card__author">{{ projectStatusLabel(project.indexing_status) }} / {{ formatDateTime(project.updated_at) }}</p>
                  <label class="field" @click.stop>
                    <span>移动到文件夹</span>
                    <select :disabled="movingProjectId === project.id" :value="project.folder_id ?? ''" @change="assignProjectFolder(project.id, ($event.target as HTMLSelectElement).value)">
                      <option v-for="folder in sortedFolders" :key="folder.id" :value="folder.id">{{ folder.name }}</option>
                    </select>
                  </label>
                  <div class="novel-card__actions novel-card__actions--iconic">
                    <button class="ghost-button ghost-button--small" type="button" @click.stop="openWorkshop(project.id)">打开</button>
                    <button class="ghost-button ghost-button--small" type="button" @click.stop="deleteProjectToTrash(project.id)">删除</button>
                  </div>
                </article>
              </div>
              <p v-else class="empty-text">这个文件夹里还没有项目。</p>
              <div class="pagination-bar">
                <span>共 {{ filteredWorkspaceProjects.length }} 条 / 每页 {{ workspacePageSize }} 条 / 第 {{ workspacePage }} / {{ workspaceTotalPages }} 页</span>
                <div class="hero__actions">
                  <button class="ghost-button ghost-button--small" :disabled="workspacePage <= 1" @click="previousWorkspacePage()">上一页</button>
                  <button class="ghost-button ghost-button--small" :disabled="workspacePage >= workspaceTotalPages" @click="nextWorkspacePage()">下一页</button>
                </div>
              </div>
            </section>
            <section v-if="showCreateFolder" class="panel panel--paper">
              <div class="panel-heading"><div><p class="panel-heading__kicker">新建文件夹</p><h2>为小说项目建立新分类</h2></div></div>
              <form class="form-stack" @submit.prevent="submitCreateFolder()">
                <label class="field"><span>文件夹名称</span><input v-model="folderForm.name" maxlength="120" /></label>
                <div class="hero__actions">
                  <button class="primary-button" :disabled="loading">创建文件夹</button>
                  <button class="ghost-button" type="button" @click="showCreateFolder = false">取消</button>
                </div>
              </form>
            </section>
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
              <article v-for="novel in shelfDisplayNovels" :key="novel.id" class="novel-card novel-card--saved novel-card--clickable" @click="openNovelDetail(novel.id)">
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
              <article v-for="novel in searchedNovels" :key="novel.id" class="novel-card novel-card--clickable" @click="openNovelDetail(novel.id)">
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

          <template v-else-if="currentView === 'projectCreate'">
            <main v-if="isAuthenticated" class="workspace workspace--single">
              <section class="panel panel--paper">
                <div class="panel-heading"><div><p class="panel-heading__kicker">新建项目</p><h2>先把小说的核心设定立住</h2></div></div>
                <form class="form-stack" @submit.prevent="submitCreateProject()">
                  <label class="field"><span>小说标题</span><input v-model="projectForm.title" maxlength="255" /></label>
                  <label class="field"><span>题材类型</span><input v-model="projectForm.genre" maxlength="100" /></label>
                  <label class="field"><span>故事前提</span><textarea v-model="projectForm.premise" rows="5" maxlength="2000" /></label>
                  <label class="field"><span>世界观</span><textarea v-model="projectForm.world_brief" rows="5" maxlength="4000" /></label>
                  <label class="field"><span>写作偏好</span><textarea v-model="projectForm.writing_rules" rows="4" maxlength="2000" /></label>
                  <label class="field"><span>文风预设</span><select v-model="projectForm.style_profile"><option value="light_novel">轻小说</option><option value="lyrical_restrained">抒情克制</option></select></label>
                  <button class="primary-button" :disabled="loading">创建项目</button>
                </form>
              </section>
            </main>
          </template>

          <template v-else-if="currentView === 'detail'">
            <section v-if="currentNovel" class="novel-detail">
              <section class="panel panel--paper novel-detail__hero">
                <div class="section-head">
                  <div><p class="panel-heading__kicker">作品</p><h2>{{ currentNovel.title }}</h2></div>
                  <button class="ghost-button ghost-button--small" type="button" @click="goToView('discover')">返回发现</button>
                </div>
                <div class="novel-detail__meta">
                  <div><span>作者</span><strong>{{ currentNovel.author }}</strong></div>
                  <div><span>题材</span><strong>{{ currentNovel.genre }}</strong></div>
                  <div><span>章节</span><strong>{{ currentNovel.chapters_count }}</strong></div>
                  <div><span>创建</span><strong>{{ formatDateTime(currentNovel.created_at) }}</strong></div>
                  <div><span>更新</span><strong>{{ formatDateTime(currentNovel.updated_at) }}</strong></div>
                </div>
                <p class="novel-detail__tagline">{{ currentNovel.tagline }}</p>
                <p class="project-copy">{{ currentNovel.summary }}</p>
              </section>
            </section>
          </template>
        </main>
      </div>
    </template>
  </div>
</template>
