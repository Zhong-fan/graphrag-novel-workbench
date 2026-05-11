import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { api } from "../api";
import type {
  BootstrapResponse,
  CaptchaChallenge,
  CharacterCard,
  GenerationItem,
  GenerationProgress,
  ProjectChapterPayload,
  ProjectFolder,
  NovelCard,
  NovelComment,
  NovelDetail,
  PublishNovelPayload,
  Project,
  ProjectPayload,
  ReferenceWorkResolved,
  ProjectSuggestionResponse,
  ProjectDetailResponse,
  RestoreTrashPayload,
  TrashItem,
  CharacterCardPayload,
  UpdateNovelPayload,
  AppendNovelChapterPayload,
  UpdateProjectChapterPayload,
  UpdateNovelChapterPayload,
  User,
  UserProfile,
} from "../types";

type SelectProjectOptions = {
  showLoading?: boolean;
  silent?: boolean;
};

const tokenKey = "graph_mvp_token";
const graphPrepareMessage = "GraphRAG 输入已准备好，请先检查整理结果，再决定是否开始索引。";
const indexPendingMessage = "索引任务已提交，正在等待项目进入可写作状态。";
const indexReadyMessage = "GraphRAG 索引已完成，现在可以开始生成内容。";
const pollDelayMs = 3000;

export const useWorkbenchStore = defineStore("workbench", () => {
  const bootstrap = ref<BootstrapResponse | null>(null);
  const captcha = ref<CaptchaChallenge | null>(null);
  const token = ref<string | null>(localStorage.getItem(tokenKey));
  const currentUser = ref<User | null>(null);
  const projects = ref<Project[]>([]);
  const projectFolders = ref<ProjectFolder[]>([]);
  const trashItems = ref<TrashItem[]>([]);
  const novels = ref<NovelCard[]>([]);
  const favoriteNovels = ref<NovelCard[]>([]);
  const myNovels = ref<NovelCard[]>([]);
  const profile = ref<UserProfile | null>(null);
  const currentNovel = ref<NovelDetail | null>(null);
  const novelComments = ref<NovelComment[]>([]);
  const activeProject = ref<ProjectDetailResponse | null>(null);
  const currentGeneration = ref<GenerationItem | null>(null);
  const generationProgress = ref<GenerationProgress>({
    stage: "idle",
    message: "",
    trace: {},
    logs: [],
  });
  const loading = ref(false);
  const error = ref("");
  const success = ref("");

  let projectPollTimer: number | null = null;
  let generationProgressTimer: number | null = null;

  const isAuthenticated = computed(() => Boolean(token.value && currentUser.value));

  function stopProjectPolling() {
    if (projectPollTimer !== null) {
      window.clearTimeout(projectPollTimer);
      projectPollTimer = null;
    }
  }

  function stopGenerationProgressPolling() {
    if (generationProgressTimer !== null) {
      window.clearInterval(generationProgressTimer);
      generationProgressTimer = null;
    }
  }

  function startGenerationProgressPolling(projectId: number) {
    stopGenerationProgressPolling();
    generationProgressTimer = window.setInterval(() => {
      if (!token.value) return;
      void api
        .generationProgress(token.value, projectId)
        .then((progress) => {
          generationProgress.value = progress;
        })
        .catch(() => {
          // The main generate request owns user-facing errors.
        });
    }, 1500);
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
    generationProgress.value = { stage: "start", message: "开始生成", trace: {}, logs: [] };
    try {
      const response = await api.register(payload);
      setToken(response.token);
      currentUser.value = response.user;
      profile.value = await api.myProfile(response.token);
      await refreshWorkspace();
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      success.value = "账号已创建并自动登录。";
    } catch (err) {
      await refreshCaptcha();
      error.value = err instanceof Error ? err.message : "Registration failed.";
    } finally {
      stopGenerationProgressPolling();
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
    const workspace = await api.myWorkspace(token.value);
    projects.value = workspace.projects;
    projectFolders.value = workspace.folders;
    trashItems.value = workspace.trash;
    if (projects.value.length > 0 && !activeProject.value) {
      await selectProject(projects.value[0].id);
    }
  }

  async function refreshWorkspace() {
    if (!token.value) {
      return;
    }
    const workspace = await api.myWorkspace(token.value);
    projects.value = workspace.projects;
    projectFolders.value = workspace.folders;
    trashItems.value = workspace.trash;
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
      await refreshWorkspace();
      success.value = "项目设定已保存。";
      await selectProject(projectId, { showLoading: false, silent: true });
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存项目设定失败。";
    } finally {
      loading.value = false;
    }
  }

  async function suggestProjectBriefing(payload: {
    kind: "world_brief" | "writing_rules";
    title: string;
    genre: string;
    reference_work: string;
    seed_text: string;
  }): Promise<ProjectSuggestionResponse | null> {
    if (!token.value) {
      error.value = "请先登录。";
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      return await api.suggestProjectBriefing(token.value, payload);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成设定参考失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function resolveReferenceWork(payload: { query: string; genre: string }): Promise<ReferenceWorkResolved | null> {
    if (!token.value) {
      error.value = "请先登录。";
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      return await api.resolveReferenceWork(token.value, payload);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "识别参考作品失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createProjectChapter(payload: ProjectChapterPayload) {
    if (!token.value || !activeProject.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const chapter = await api.createProjectChapter(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = "章节已创建。";
      return chapter;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建章节失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateProjectChapter(chapterId: number, payload: UpdateProjectChapterPayload) {
    if (!token.value || !activeProject.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const chapter = await api.updateProjectChapter(token.value, activeProject.value.project.id, chapterId, payload);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = "章节设定已保存。";
      return chapter;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存章节设定失败。";
      return null;
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

  async function prepareGraphReview() {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const review = await api.prepareGraphReview(token.value, activeProject.value.project.id);
      activeProject.value.graphrag_review = review;
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = graphPrepareMessage;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "准备 GraphRAG 预览失败。";
    } finally {
      loading.value = false;
    }
  }

  async function updateGraphReviewFile(filename: string, content: string) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const review = await api.updateGraphReviewFile(token.value, activeProject.value.project.id, filename, { content });
      activeProject.value.graphrag_review = review;
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = "GraphRAG 输入文件已保存，可以继续检查后再启动索引。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存 GraphRAG 输入文件失败。";
    } finally {
      loading.value = false;
    }
  }

  async function generate(payload: {
    chapter_id: number;
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
    generationProgress.value = { stage: "start", message: "开始生成", trace: {}, logs: [] };
    startGenerationProgressPolling(activeProject.value.project.id);
    try {
      currentGeneration.value = await api.generate(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      generationProgress.value = { ...generationProgress.value, stage: "done", message: "生成流程完成" };
      success.value = "新内容已生成。";
    } catch (err) {
      try {
        if (token.value && activeProject.value) {
          generationProgress.value = await api.generationProgress(token.value, activeProject.value.project.id);
        }
      } catch {
        // Keep the original generate error visible.
      }
      error.value = err instanceof Error ? err.message : "生成失败。";
    } finally {
      stopGenerationProgressPolling();
      loading.value = false;
    }
  }

  async function refreshGenerationEvolution(generationId: number) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      currentGeneration.value = await api.refreshGenerationEvolution(token.value, activeProject.value.project.id, generationId);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = "草稿变化快照已重新抽取。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "重新抽取草稿变化失败。";
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
      await refreshWorkspace();
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
      await refreshWorkspace();
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
      await refreshWorkspace();
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
      await refreshWorkspace();
      success.value = "章节已保存。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存章节失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createFolder(name: string) {
    if (!token.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const folder = await api.createFolder(token.value, { name: name.trim() });
      await refreshWorkspace();
      success.value = "文件夹已创建。";
      return folder;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建文件夹失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function moveProjectToFolder(projectId: number, folderId?: number | null) {
    if (!token.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const project = await api.moveProjectToFolder(token.value, projectId, { folder_id: folderId ?? null });
      await refreshWorkspace();
      success.value = "项目已移动。";
      return project;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "移动项目失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function deleteProject(projectId: number) {
    if (!token.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const project = await api.deleteProject(token.value, projectId, {});
      await refreshWorkspace();
      if (activeProject.value?.project.id === projectId) {
        activeProject.value = null;
        currentGeneration.value = null;
      }
      success.value = "项目已移入回收站。";
      return project;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除项目失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function deleteNovel(novelId: number) {
    if (!token.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const novel = await api.deleteNovel(token.value, novelId, {});
      if (currentNovel.value?.id === novelId) {
        currentNovel.value = null;
        novelComments.value = [];
      }
      await loadNovels();
      await loadFavorites();
      await loadMyNovels();
      await refreshWorkspace();
      success.value = "作品已移入回收站。";
      return novel;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除作品失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function deleteCharacterCard(projectId: number, cardId: number) {
    if (!token.value) {
      return null;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const card = await api.deleteCharacterCard(token.value, projectId, cardId, {});
      await refreshWorkspace();
      if (activeProject.value?.project.id === projectId) {
        await selectProject(projectId, { showLoading: false, silent: true });
      }
      success.value = "人物卡已移入回收站。";
      return card;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除人物卡失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function restoreTrashItem(itemId: number, itemType: RestoreTrashPayload["item_type"]) {
    if (!token.value) {
      return false;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      await api.restoreTrashItem(token.value, itemId, { item_type: itemType });
      await refreshWorkspace();
      await loadMyNovels();
      success.value = "已恢复。";
      return true;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "恢复失败。";
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function trashDirtyEvolution(projectId: number) {
    if (!token.value) {
      return false;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const result = await api.trashDirtyEvolution(token.value, projectId);
      await refreshWorkspace();
      if (activeProject.value?.project.id === projectId) {
        await selectProject(projectId, { showLoading: false, silent: true });
      }
      const total = Object.values(result.stats || {}).reduce((sum, value) => sum + Number(value || 0), 0);
      success.value = total ? `已将 ${total} 条脏演化移入回收站。` : "没有检测到需要清理的脏演化。";
      return true;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "清理脏演化失败。";
      return false;
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
    generationProgress,
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
    refreshWorkspace,
    createProject,
    createFolder,
    moveProjectToFolder,
    deleteProject,
    deleteNovel,
    deleteCharacterCard,
    restoreTrashItem,
    trashDirtyEvolution,
    updateProject,
    resolveReferenceWork,
    suggestProjectBriefing,
    createProjectChapter,
    updateProjectChapter,
    clearFeedback,
    addMemory,
    addCharacterCard,
    updateCharacterCard,
    addSource,
    prepareGraphReview,
    updateGraphReviewFile,
    indexProject,
    generate,
    refreshGenerationEvolution,
    toggleFavoriteNovel,
    toggleLikeNovel,
    publishNovelFromGeneration,
    updatePublishedNovel,
    appendNovelChapter,
    updateNovelChapter,
  };
});
