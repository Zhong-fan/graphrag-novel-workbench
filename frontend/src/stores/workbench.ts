import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { api } from "../api";
import type {
  BootstrapResponse,
  CaptchaChallenge,
  GenerationItem,
  NovelCard,
  NovelComment,
  NovelDetail,
  PublishNovelPayload,
  Project,
  ProjectPayload,
  ProjectDetailResponse,
  CharacterCardPayload,
  UpdateNovelPayload,
  AppendNovelChapterPayload,
  UpdateNovelChapterPayload,
  User,
  UserProfile,
} from "../types";

type SelectProjectOptions = {
  showLoading?: boolean;
  silent?: boolean;
};

const tokenKey = "graph_mvp_token";
const indexPendingMessage = "索引任务已提交，正在等待项目进入可写作状态。";
const indexReadyMessage = "GraphRAG 索引已完成，现在可以开始生成内容。";
const pollDelayMs = 3000;

export const useWorkbenchStore = defineStore("workbench", () => {
  const bootstrap = ref<BootstrapResponse | null>(null);
  const captcha = ref<CaptchaChallenge | null>(null);
  const token = ref<string | null>(localStorage.getItem(tokenKey));
  const currentUser = ref<User | null>(null);
  const projects = ref<Project[]>([]);
  const novels = ref<NovelCard[]>([]);
  const favoriteNovels = ref<NovelCard[]>([]);
  const myNovels = ref<NovelCard[]>([]);
  const profile = ref<UserProfile | null>(null);
  const currentNovel = ref<NovelDetail | null>(null);
  const novelComments = ref<NovelComment[]>([]);
  const activeProject = ref<ProjectDetailResponse | null>(null);
  const currentGeneration = ref<GenerationItem | null>(null);
  const loading = ref(false);
  const error = ref("");
  const success = ref("");

  let projectPollTimer: number | null = null;

  const isAuthenticated = computed(() => Boolean(token.value && currentUser.value));

  function stopProjectPolling() {
    if (projectPollTimer !== null) {
      window.clearTimeout(projectPollTimer);
      projectPollTimer = null;
    }
  }

  function scheduleProjectPolling(projectId: number) {
    stopProjectPolling();
    projectPollTimer = window.setTimeout(async () => {
      projectPollTimer = null;
      if (activeProject.value?.project.id !== projectId) {
        return;
      }
      await selectProject(projectId, { showLoading: false, silent: true });
    }, pollDelayMs);
  }

  function syncProjectSummary(project: Project) {
    const index = projects.value.findIndex((item) => item.id === project.id);
    if (index >= 0) {
      projects.value[index] = project;
      return;
    }
    projects.value.unshift(project);
  }

  function setToken(next: string | null) {
    token.value = next;
    if (next) {
      localStorage.setItem(tokenKey, next);
    } else {
      localStorage.removeItem(tokenKey);
    }
  }

  function syncNovelInCollections(novelId: number, updater: (novel: NovelCard) => NovelCard) {
    novels.value = novels.value.map((item) => (item.id === novelId ? updater(item) : item));
    favoriteNovels.value = favoriteNovels.value.map((item) => (item.id === novelId ? updater(item) : item));
    myNovels.value = myNovels.value.map((item) => (item.id === novelId ? updater(item) : item));
    if (currentNovel.value?.id === novelId) {
      currentNovel.value = updater(currentNovel.value) as NovelDetail;
    }
  }

  async function initialize() {
    error.value = "";
    bootstrap.value = await api.bootstrap();
    await loadNovels();
    if (token.value) {
      try {
        currentUser.value = await api.me(token.value);
        profile.value = await api.myProfile(token.value);
        await loadProjects();
        await loadFavorites();
        await loadMyNovels();
      } catch {
        stopProjectPolling();
        setToken(null);
        currentUser.value = null;
        favoriteNovels.value = [];
      }
    } else {
      captcha.value = await api.captcha();
    }
  }

  async function refreshCaptcha() {
    captcha.value = await api.captcha();
  }

  async function register(payload: { username: string; password: string; captcha_answer: string; captcha_token: string }) {
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const response = await api.register(payload);
      setToken(response.token);
      currentUser.value = response.user;
      profile.value = await api.myProfile(response.token);
      await loadProjects();
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      success.value = "账号已创建并自动登录。";
    } catch (err) {
      await refreshCaptcha();
      error.value = err instanceof Error ? err.message : "Registration failed.";
    } finally {
      loading.value = false;
    }
  }

  async function login(payload: { username: string; password: string }) {
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const response = await api.login(payload);
      setToken(response.token);
      currentUser.value = response.user;
      profile.value = await api.myProfile(response.token);
      await loadProjects();
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      success.value = "登录成功。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Login failed.";
    } finally {
      loading.value = false;
    }
  }

  function logout() {
    stopProjectPolling();
    setToken(null);
    currentUser.value = null;
    projects.value = [];
    favoriteNovels.value = [];
    myNovels.value = [];
    profile.value = null;
    currentNovel.value = null;
    novelComments.value = [];
    activeProject.value = null;
    currentGeneration.value = null;
    void refreshCaptcha();
    void loadNovels();
    success.value = "已退出登录。";
    error.value = "";
  }

  async function loadNovels() {
    novels.value = await api.listNovels(token.value);
  }

  async function loadFavorites() {
    if (!token.value) {
      favoriteNovels.value = [];
      return;
    }
    favoriteNovels.value = await api.listFavorites(token.value);
  }

  async function loadMyNovels() {
    if (!token.value) {
      myNovels.value = [];
      return;
    }
    myNovels.value = await api.listMyNovels(token.value);
  }

  async function saveProfile(payload: UserProfile) {
    if (!token.value) {
      error.value = "请先登录。";
      return;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      profile.value = await api.updateMyProfile(token.value, payload);
      success.value = "个人资料已保存。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存个人资料失败。";
    } finally {
      loading.value = false;
    }
  }

  async function openNovel(novelId: number) {
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      currentNovel.value = await api.novelDetail(novelId, token.value);
      novelComments.value = await api.listNovelComments(novelId);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载小说详情失败。";
    } finally {
      loading.value = false;
    }
  }

  async function submitNovelComment(content: string) {
    if (!token.value) {
      error.value = "请先登录。";
      return;
    }
    if (!currentNovel.value) {
      return;
    }

    const normalized = content.trim();
    if (!normalized) {
      error.value = "评论不能为空。";
      return;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const comment = await api.createNovelComment(token.value, currentNovel.value.id, { content: normalized });
      novelComments.value = [comment, ...novelComments.value];
      syncNovelInCollections(currentNovel.value.id, (item) => ({
        ...item,
        comments_count: item.comments_count + 1,
      }));
      success.value = "评论已发布。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "评论发布失败。";
    } finally {
      loading.value = false;
    }
  }

  async function loadProjects() {
    if (!token.value) {
      return;
    }
    projects.value = await api.listProjects(token.value);
    if (projects.value.length > 0 && !activeProject.value) {
      await selectProject(projects.value[0].id);
    }
  }

  async function selectProject(projectId: number, options: SelectProjectOptions = {}) {
    if (!token.value) {
      return;
    }

    const { showLoading = true, silent = false } = options;
    if (showLoading) {
      loading.value = true;
    }
    if (!silent) {
      error.value = "";
    }

    try {
      const detail = await api.projectDetail(token.value, projectId);
      activeProject.value = detail;
      syncProjectSummary(detail.project);

      if (currentGeneration.value) {
        currentGeneration.value =
          detail.generations.find((item) => item.id === currentGeneration.value?.id) ??
          detail.generations[0] ??
          null;
      } else {
        currentGeneration.value = detail.generations[0] ?? null;
      }

      if (detail.project.indexing_status === "indexing") {
        scheduleProjectPolling(projectId);
      } else {
        stopProjectPolling();
        if (detail.project.indexing_status === "ready" && success.value === indexPendingMessage) {
          success.value = indexReadyMessage;
        }
      }
    } catch (err) {
      stopProjectPolling();
      if (!silent) {
        error.value = err instanceof Error ? err.message : "加载项目失败。";
      }
    } finally {
      if (showLoading) {
        loading.value = false;
      }
    }
  }

  async function createProject(payload: ProjectPayload) {
    if (!token.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const project = await api.createProject(token.value, payload);
      await loadProjects();
      await selectProject(project.id);
      success.value = "项目已创建。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建项目失败。";
    } finally {
      loading.value = false;
    }
  }

  async function updateProject(payload: ProjectPayload) {
    if (!token.value || !activeProject.value) {
      return;
    }
    const projectId = activeProject.value.project.id;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const project = await api.updateProject(token.value, projectId, payload);
      activeProject.value.project = project;
      syncProjectSummary(project);
      success.value = "项目设定已保存。";
      await selectProject(projectId, { showLoading: false, silent: true });
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存项目设定失败。";
    } finally {
      loading.value = false;
    }
  }

  function clearFeedback() {
    error.value = "";
    success.value = "";
  }

  async function addMemory(payload: { title: string; content: string; memory_scope: string; importance: number }) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      await api.addMemory(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id);
      success.value = "长期设定已加入项目。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存长期设定失败。";
    } finally {
      loading.value = false;
    }
  }

  async function addCharacterCard(payload: CharacterCardPayload) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      await api.addCharacterCard(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id);
      success.value = "人物卡已添加。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存人物卡失败。";
    } finally {
      loading.value = false;
    }
  }

  async function updateCharacterCard(cardId: number, payload: CharacterCardPayload) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      await api.updateCharacterCard(token.value, activeProject.value.project.id, cardId, payload);
      await selectProject(activeProject.value.project.id);
      success.value = "人物卡已保存。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存人物卡失败。";
    } finally {
      loading.value = false;
    }
  }

  async function addSource(payload: { title: string; content: string; source_kind: string }) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      await api.addSource(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id);
      success.value = "资料已加入项目。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存资料失败。";
    } finally {
      loading.value = false;
    }
  }

  async function indexProject() {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const response = await api.indexProject(token.value, activeProject.value.project.id, { force_rebuild: false });
      success.value = response.status === "ready" ? indexReadyMessage : indexPendingMessage;
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
    } catch (err) {
      error.value = err instanceof Error ? err.message : "启动索引失败。";
    } finally {
      loading.value = false;
    }
  }

  async function generate(payload: {
    prompt: string;
    search_method: string;
    response_type: string;
    use_global_search: boolean;
    use_scene_card: boolean;
    use_refiner: boolean;
    write_evolution: boolean;
  }) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      currentGeneration.value = await api.generate(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = "新内容已生成。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成失败。";
    } finally {
      loading.value = false;
    }
  }

  async function toggleFavoriteNovel(novelId: number) {
    if (!token.value) {
      error.value = "请先登录。";
      return;
    }

    const target = novels.value.find((item) => item.id === novelId) ?? favoriteNovels.value.find((item) => item.id === novelId);
    if (!target) {
      return;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      if (target.is_favorited) {
        await api.unfavoriteNovel(token.value, novelId);
        syncNovelInCollections(novelId, (item) => ({
          ...item,
          is_favorited: false,
          favorites_count: Math.max(0, item.favorites_count - 1),
        }));
        favoriteNovels.value = favoriteNovels.value.filter((item) => item.id !== novelId);
        success.value = "已移出书架。";
      } else {
        await api.favoriteNovel(token.value, novelId);
        syncNovelInCollections(novelId, (item) => ({
          ...item,
          is_favorited: true,
          favorites_count: item.favorites_count + 1,
        }));
        await loadFavorites();
        success.value = "已加入书架。";
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "收藏状态更新失败。";
    } finally {
      loading.value = false;
    }
  }

  async function toggleLikeNovel(novelId: number) {
    if (!token.value) {
      error.value = "请先登录。";
      return;
    }

    const target = novels.value.find((item) => item.id === novelId) ?? favoriteNovels.value.find((item) => item.id === novelId);
    if (!target) {
      return;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      if (target.is_liked) {
        await api.unlikeNovel(token.value, novelId);
        syncNovelInCollections(novelId, (item) => ({
          ...item,
          is_liked: false,
          likes_count: Math.max(0, item.likes_count - 1),
        }));
        success.value = "已取消点赞。";
      } else {
        await api.likeNovel(token.value, novelId);
        syncNovelInCollections(novelId, (item) => ({
          ...item,
          is_liked: true,
          likes_count: item.likes_count + 1,
        }));
        success.value = "已点赞。";
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "点赞状态更新失败。";
    } finally {
      loading.value = false;
    }
  }

  async function publishNovelFromGeneration(payload: PublishNovelPayload) {
    if (!token.value) {
      error.value = "请先登录。";
      return null;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const created = await api.publishNovelFromGeneration(token.value, payload);
      currentNovel.value = created;
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      novelComments.value = [];
      success.value = "作品已发布到书城。";
      return created;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "发布作品失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updatePublishedNovel(novelId: number, payload: UpdateNovelPayload) {
    if (!token.value) {
      error.value = "请先登录。";
      return null;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const updated = await api.updateNovel(token.value, novelId, payload);
      currentNovel.value = updated;
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      success.value = "作品信息已更新。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新作品失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function appendNovelChapter(novelId: number, payload: AppendNovelChapterPayload) {
    if (!token.value) {
      error.value = "请先登录。";
      return null;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const updated = await api.appendNovelChapterFromGeneration(token.value, novelId, payload);
      currentNovel.value = updated;
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      success.value = "新章节已追加。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "追加章节失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateNovelChapter(novelId: number, chapterId: number, payload: UpdateNovelChapterPayload) {
    if (!token.value) {
      error.value = "请先登录。";
      return null;
    }

    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const updated = await api.updateNovelChapter(token.value, novelId, chapterId, payload);
      currentNovel.value = updated;
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      success.value = "章节已保存。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存章节失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  return {
    bootstrap,
    captcha,
    token,
    currentUser,
    projects,
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
    initialize,
    refreshCaptcha,
    register,
    login,
    logout,
    loadNovels,
    loadFavorites,
    loadMyNovels,
    saveProfile,
    openNovel,
    submitNovelComment,
    selectProject,
    createProject,
    updateProject,
    clearFeedback,
    addMemory,
    addCharacterCard,
    updateCharacterCard,
    addSource,
    indexProject,
    generate,
    toggleFavoriteNovel,
    toggleLikeNovel,
    publishNovelFromGeneration,
    updatePublishedNovel,
    appendNovelChapter,
    updateNovelChapter,
  };
});
