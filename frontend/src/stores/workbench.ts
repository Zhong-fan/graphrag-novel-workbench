import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { api } from "../api";
import type {
  BootstrapResponse,
  CaptchaChallenge,
  CharacterCard,
  GenerationItem,
  GenerationProgress,
  NovelCard,
  ProjectChapterPayload,
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
  BatchGenerationPayload,
  CreateStoryboardPayload,
  GenerateSeriesPlanPayload,
  LongformState,
  SubmitOutlineFeedbackPayload,
  CanonicalizeDraftPayload,
  ReviseDraftPayload,
  UpdateChapterOutlinePayload,
  UpdateMediaAssetPayload,
  GenerateCharacterTurnaroundPayload,
  GenerateShotFirstFramePayload,
  GenerateVoicePayload,
  GenerateAudioScriptsPayload,
  VideoProductionPreflightPayload,
  UpdateStoryboardShotPayload,
  CreateStoryboardShotPayload,
  ReorderStoryboardShotsPayload,
  UpdateVideoTaskPayload,
} from "../types";

type SelectProjectOptions = {
  showLoading?: boolean;
  silent?: boolean;
};

const tokenKey = "graph_mvp_token";

export const useWorkbenchStore = defineStore("workbench", () => {
  const bootstrap = ref<BootstrapResponse | null>(null);
  const captcha = ref<CaptchaChallenge | null>(null);
  const token = ref<string | null>(localStorage.getItem(tokenKey));
  const currentUser = ref<User | null>(null);
  const projects = ref<Project[]>([]);
  const trashItems = ref<TrashItem[]>([]);
  const myNovels = ref<NovelCard[]>([]);
  const currentNovel = ref<NovelDetail | null>(null);
  const activeProject = ref<ProjectDetailResponse | null>(null);
  const currentGeneration = ref<GenerationItem | null>(null);
  const longformState = ref<LongformState>({
    series_plans: [],
    draft_versions: [],
    batch_jobs: [],
    storyboards: [],
    media_assets: [],
    video_tasks: [],
  });
  const generationProgress = ref<GenerationProgress>({
    stage: "idle",
    message: "",
    trace: {},
    logs: [],
  });
  const loading = ref(false);
  const error = ref("");
  const success = ref("");

  let generationProgressTimer: number | null = null;
  let longformPollingTimer: number | null = null;
  let longformPollingProjectId: number | null = null;

  const isAuthenticated = computed(() => Boolean(token.value && currentUser.value));

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

  function hasActiveLongformJobs() {
    const hasActiveBatchJob = longformState.value.batch_jobs.some((job) =>
      ["queued", "retry_queued", "running", "pause_requested", "cancel_requested"].includes(job.job_status),
    );
    const hasActiveStoryboardJob = longformState.value.storyboards.some((storyboard) => ["queued", "running"].includes(storyboard.status));
    const hasActiveVideoTask = longformState.value.video_tasks.some((task) => ["queued", "running"].includes(task.task_status));
    return hasActiveBatchJob || hasActiveStoryboardJob || hasActiveVideoTask;
  }

  function stopLongformPolling() {
    if (longformPollingTimer !== null) {
      window.clearInterval(longformPollingTimer);
      longformPollingTimer = null;
    }
    longformPollingProjectId = null;
  }

  function startLongformPolling(projectId: number) {
    if (longformPollingTimer !== null && longformPollingProjectId === projectId) return;
    stopLongformPolling();
    longformPollingProjectId = projectId;
    longformPollingTimer = window.setInterval(() => {
      if (!token.value) return;
      void loadLongformState(projectId, { silent: true }).then(() => {
        if (!hasActiveLongformJobs()) {
          stopLongformPolling();
        }
      });
    }, 2500);
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

  async function initialize() {
    error.value = "";
    bootstrap.value = await api.bootstrap();
    if (token.value) {
      try {
        currentUser.value = await api.me(token.value);
        await loadProjects();
        await loadMyNovels();
      } catch {
        setToken(null);
        currentUser.value = null;
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
      await refreshWorkspace();
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
      await loadProjects();
      await loadMyNovels();
      success.value = "登录成功。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Login failed.";
    } finally {
      loading.value = false;
    }
  }

  function logout() {
    setToken(null);
    currentUser.value = null;
    projects.value = [];
    myNovels.value = [];
    currentNovel.value = null;
    activeProject.value = null;
    currentGeneration.value = null;
    void refreshCaptcha();
    stopLongformPolling();
    success.value = "已退出登录。";
    error.value = "";
  }

  async function loadMyNovels() {
    if (!token.value) {
      myNovels.value = [];
      return;
    }
    myNovels.value = await api.listMyNovels(token.value);
  }

  async function openNovel(novelId: number) {
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      currentNovel.value = await api.novelDetail(novelId, token.value);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载作品详情失败。";
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
      await loadLongformState(projectId, { silent: true });
    } catch (err) {
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
      await loadMyNovels();
      await refreshWorkspace();
      success.value = "作品已发布。";
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
      }
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

  async function loadLongformState(projectId?: number, options: { silent?: boolean } = {}) {
    if (!token.value) return;
    const targetProjectId = projectId ?? activeProject.value?.project.id;
    if (!targetProjectId) return;
    try {
      longformState.value = await api.longformState(token.value, targetProjectId);
      if (hasActiveLongformJobs()) {
        startLongformPolling(targetProjectId);
      } else {
        stopLongformPolling();
      }
    } catch (err) {
      if (!options.silent) {
        error.value = err instanceof Error ? err.message : "加载长篇流水线失败。";
      }
    }
  }

  async function generateSeriesPlan(payload: GenerateSeriesPlanPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const plan = await api.generateSeriesPlan(token.value, activeProject.value.project.id, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "长篇概要已生成。";
      return plan;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成长篇概要失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function submitOutlineFeedback(payload: SubmitOutlineFeedbackPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const result = await api.submitOutlineFeedback(token.value, activeProject.value.project.id, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "概要已按反馈生成新版本。";
      return result;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "修订概要失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function lockSeriesPlan(seriesPlanId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const plan = await api.lockSeriesPlan(token.value, activeProject.value.project.id, seriesPlanId);
      await loadLongformState(activeProject.value.project.id);
      success.value = "概要已锁定。";
      return plan;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "锁定概要失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function restoreSeriesPlanVersion(seriesPlanId: number, versionId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const plan = await api.restoreSeriesPlanVersion(token.value, activeProject.value.project.id, seriesPlanId, versionId);
      await loadLongformState(activeProject.value.project.id);
      success.value = "概要版本已恢复为新版本。";
      return plan;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "恢复概要版本失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function runBatchGeneration(payload: BatchGenerationPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const job = await api.runBatchGeneration(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      await loadLongformState(activeProject.value.project.id);
      startLongformPolling(activeProject.value.project.id);
      success.value = "批量正文生成任务已创建。";
      return job;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "批量正文生成失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function retryBatchGeneration(jobId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const job = await api.retryBatchGeneration(token.value, activeProject.value.project.id, jobId);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      await loadLongformState(activeProject.value.project.id);
      startLongformPolling(activeProject.value.project.id);
      success.value = "批量任务已重试。";
      return job;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "重试批量任务失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function pauseBatchGeneration(jobId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const job = await api.pauseBatchGeneration(token.value, activeProject.value.project.id, jobId);
      await loadLongformState(activeProject.value.project.id);
      success.value = "批量任务已请求暂停。";
      return job;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "暂停批量任务失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function resumeBatchGeneration(jobId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const job = await api.resumeBatchGeneration(token.value, activeProject.value.project.id, jobId);
      await loadLongformState(activeProject.value.project.id);
      startLongformPolling(activeProject.value.project.id);
      success.value = "批量任务已恢复。";
      return job;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "恢复批量任务失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function cancelBatchGeneration(jobId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const job = await api.cancelBatchGeneration(token.value, activeProject.value.project.id, jobId);
      await loadLongformState(activeProject.value.project.id);
      success.value = "批量任务已请求取消。";
      return job;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "取消批量任务失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createStoryboard(payload: CreateStoryboardPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const storyboard = await api.createStoryboard(token.value, activeProject.value.project.id, payload);
      await loadLongformState(activeProject.value.project.id);
      startLongformPolling(activeProject.value.project.id);
      success.value = "分镜生成任务已创建。";
      return storyboard;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成分镜失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function reviseDraftVersion(draftVersionId: number, payload: ReviseDraftPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const draft = await api.reviseDraftVersion(token.value, activeProject.value.project.id, draftVersionId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "章节已生成新版本。";
      return draft;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "章节重写失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function canonicalizeDraftVersion(draftVersionId: number, payload: CanonicalizeDraftPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const draft = await api.canonicalizeDraftVersion(token.value, activeProject.value.project.id, draftVersionId, payload);
      await loadLongformState(activeProject.value.project.id);
      await loadMyNovels();
      success.value = "章节已定稿。";
      return draft;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "章节定稿失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createVideoTask(storyboardId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const task = await api.createVideoTask(token.value, activeProject.value.project.id, storyboardId);
      await loadLongformState(activeProject.value.project.id);
      startLongformPolling(activeProject.value.project.id);
      success.value = "视频生产任务已创建。";
      return task;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建视频任务失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateChapterOutline(outlineId: number, payload: UpdateChapterOutlinePayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const outline = await api.updateChapterOutline(token.value, activeProject.value.project.id, outlineId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "章节概要已保存。";
      return outline;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存章节概要失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateStoryboardShot(storyboardId: number, shotId: number, payload: UpdateStoryboardShotPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const storyboard = await api.updateStoryboardShot(token.value, activeProject.value.project.id, storyboardId, shotId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "镜头已保存。";
      return storyboard;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存镜头失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createStoryboardShot(storyboardId: number, payload: CreateStoryboardShotPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const storyboard = await api.createStoryboardShot(token.value, activeProject.value.project.id, storyboardId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "镜头已新增。";
      return storyboard;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增镜头失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function deleteStoryboardShot(storyboardId: number, shotId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const storyboard = await api.deleteStoryboardShot(token.value, activeProject.value.project.id, storyboardId, shotId);
      await loadLongformState(activeProject.value.project.id);
      success.value = "镜头已删除。";
      return storyboard;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除镜头失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function reorderStoryboardShots(storyboardId: number, payload: ReorderStoryboardShotsPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const storyboard = await api.reorderStoryboardShots(token.value, activeProject.value.project.id, storyboardId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "镜头顺序已更新。";
      return storyboard;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新镜头顺序失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateMediaAsset(assetId: number, payload: UpdateMediaAssetPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const asset = await api.updateMediaAsset(token.value, activeProject.value.project.id, assetId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "素材状态已保存。";
      return asset;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存素材状态失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function generateCharacterTurnaround(payload: GenerateCharacterTurnaroundPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const asset = await api.generateCharacterTurnaround(token.value, activeProject.value.project.id, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "角色三视图已生成。";
      return asset;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成角色三视图失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function generateShotFirstFrame(storyboardId: number, shotId: number) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const asset = await api.generateShotFirstFrame(token.value, activeProject.value.project.id, storyboardId, shotId);
      await loadLongformState(activeProject.value.project.id);
      success.value = "镜头首帧已生成。";
      return asset;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成镜头首帧失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function generateStoryboardVoice(storyboardId: number, payload: GenerateVoicePayload = {}) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const assets = await api.generateStoryboardVoice(token.value, activeProject.value.project.id, storyboardId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "分镜旁白已生成。";
      return assets;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成分镜旁白失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function generateStoryboardAudioScripts(storyboardId: number, payload: GenerateAudioScriptsPayload = {}) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const storyboard = await api.generateStoryboardAudioScripts(token.value, activeProject.value.project.id, storyboardId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "自动对白脚本已生成。";
      return storyboard;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成自动对白脚本失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function generateShotVoice(storyboardId: number, shotId: number, payload: GenerateVoicePayload = {}) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const asset = await api.generateShotVoice(token.value, activeProject.value.project.id, storyboardId, shotId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "镜头旁白已生成。";
      return asset;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成镜头旁白失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function prepareVideoProduction(storyboardId: number, payload: VideoProductionPreflightPayload = {}) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const state = await api.prepareVideoProduction(token.value, activeProject.value.project.id, storyboardId, payload);
      longformState.value = state;
      startLongformPolling(activeProject.value.project.id);
      success.value = "视频生产前置内容已准备，视频任务已进入队列。";
      return state;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "准备视频生产失败。";
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateVideoTask(taskId: number, payload: UpdateVideoTaskPayload) {
    if (!token.value || !activeProject.value) return null;
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const task = await api.updateVideoTask(token.value, activeProject.value.project.id, taskId, payload);
      await loadLongformState(activeProject.value.project.id);
      success.value = "视频任务已更新。";
      return task;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新视频任务失败。";
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
    initialize,
    refreshCaptcha,
    register,
    login,
    logout,
    loadMyNovels,
    openNovel,
    selectProject,
    refreshWorkspace,
    createProject,
    deleteProject,
    deleteNovel,
    deleteCharacterCard,
    restoreTrashItem,
    trashDirtyEvolution,
    loadLongformState,
    generateSeriesPlan,
    submitOutlineFeedback,
    lockSeriesPlan,
    restoreSeriesPlanVersion,
    runBatchGeneration,
    retryBatchGeneration,
    pauseBatchGeneration,
    resumeBatchGeneration,
    cancelBatchGeneration,
    createStoryboard,
    reviseDraftVersion,
    canonicalizeDraftVersion,
    createVideoTask,
    updateChapterOutline,
    updateStoryboardShot,
    createStoryboardShot,
    deleteStoryboardShot,
    reorderStoryboardShots,
    updateMediaAsset,
    generateCharacterTurnaround,
    generateShotFirstFrame,
    generateStoryboardAudioScripts,
    generateStoryboardVoice,
    generateShotVoice,
    prepareVideoProduction,
    updateVideoTask,
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
    generate,
    refreshGenerationEvolution,
    publishNovelFromGeneration,
    updatePublishedNovel,
    appendNovelChapter,
    updateNovelChapter,
  };
});

