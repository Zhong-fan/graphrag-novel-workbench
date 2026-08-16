<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import AuthModal from "./components/auth/AuthModal.vue";
import ToonflowWorkbench from "./components/workspace/ToonflowWorkbench.vue";
import { useAuthFlow } from "./composables/useAuthFlow";
import { useWorkbenchStore } from "./stores/workbench";
import type { ProjectAIBriefDraftPayload, ProjectCreateDraft, ProjectImportDraftPayload, ProjectPayload, TrashItem, UpdateMediaAssetPayload, ViewKey } from "./types";

const store = useWorkbenchStore();
const {
  captcha,
  currentUser,
  projects,
  trashItems,
  activeProject,
  longformState,
  contextPack,
  generationAttempts,
  generationAttemptsLoading,
  generationAttemptsError,
  loading,
  longformRequestState,
  error,
  success,
  isAuthenticated,
} = storeToRefs(store);

const currentView = ref<ViewKey>("studio");
const authError = ref("");
const workspaceSearch = ref("");
const projectCreationMode = ref<"upload" | "ai" | "manual">("manual");
const hasRestoredViewState = ref(false);
let feedbackTimer: number | null = null;

const persistedViewKey = "chenflow_current_view";
const persistedProjectIdKey = "chenflow_active_project_id";
const legacyPersistedViewKey = "graph_mvp_current_view";
const legacyPersistedProjectIdKey = "graph_mvp_active_project_id";
const restorableViews: ViewKey[] = ["studio", "assetLibrary", "trash"];

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
  reference_inheritance_mode: "style_only",
  reference_rewrite_start: "",
  reference_authorized_changes: "",
  story_boundary_text: "",
  visual_style_locked: true,
  visual_style_medium: "",
  visual_style_artists: [],
  visual_style_positive: [],
  visual_style_negative: [],
  visual_style_notes: "",
  world_brief: "",
  writing_rules: "",
  style_profile: "lyrical_restrained",
});

const emptyProjectDraft = (): ProjectCreateDraft => ({
  ...emptyProject(),
  reference_work_confirmed: false,
});

const projectForm = reactive<ProjectCreateDraft>(emptyProjectDraft());

const trashSummary = computed<Record<TrashItem["item_type"], number>>(() => ({
  project: trashItems.value.filter((item) => item.item_type === "project").length,
  novel: trashItems.value.filter((item) => item.item_type === "novel").length,
  character_card: trashItems.value.filter((item) => item.item_type === "character_card").length,
  dirty_evolution: trashItems.value.filter((item) => item.item_type === "dirty_evolution").length,
  media_asset: trashItems.value.filter((item) => item.item_type === "media_asset").length,
}));

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
  if (view !== "auth" && !isAuthenticated.value && ["studio", "assetLibrary", "trash", "projectCreate"].includes(view)) {
    openAuthPanel(view === "projectCreate" ? "register" : "login", view);
    return;
  }
  currentView.value = view;
}

function openSidebarProjectCreate(mode: "upload" | "ai" | "manual" = "manual") {
  projectCreationMode.value = mode;
  goToView("projectCreate");
}

async function loadImportedProjectDraft(payload: ProjectImportDraftPayload) {
  const draft = await store.loadImportedProjectDraft(payload);
  if (draft) Object.assign(projectForm, draft.project, { reference_work_confirmed: false });
}

async function loadAiProjectDraft(payload: ProjectAIBriefDraftPayload) {
  const draft = await store.loadAiProjectDraft(payload);
  if (draft) Object.assign(projectForm, draft.project, { reference_work_confirmed: false });
}

function readPersistedNumber(key: string, legacyKey?: string) {
  const raw = localStorage.getItem(key) ?? (legacyKey ? localStorage.getItem(legacyKey) : null);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function readPersistedView() {
  const raw = localStorage.getItem(persistedViewKey) ?? localStorage.getItem(legacyPersistedViewKey);
  return restorableViews.includes(raw as ViewKey) ? (raw as ViewKey) : "studio";
}

function persistView(view: ViewKey) {
  if (view === "auth" || !hasRestoredViewState.value || !restorableViews.includes(view)) return;
  localStorage.setItem(persistedViewKey, view);
}

async function restoreViewState() {
  if (!isAuthenticated.value) {
    currentView.value = "studio";
    hasRestoredViewState.value = true;
    return;
  }

  const persistedProjectId = readPersistedNumber(persistedProjectIdKey, legacyPersistedProjectIdKey);
  if (persistedProjectId && projects.value.some((project) => project.id === persistedProjectId)) {
    await store.selectProject(persistedProjectId, { showLoading: false, silent: true });
  }

  currentView.value = readPersistedView();
  hasRestoredViewState.value = true;
}

function clearToasts() {
  authError.value = "";
  clearAuthFeedback();
}

async function openWorkspaceProject(projectId: number) {
  await store.selectProject(projectId);
  if (activeProject.value?.project.id === projectId) {
    localStorage.setItem(persistedProjectIdKey, String(projectId));
  }
  currentView.value = "studio";
}

async function deleteProjectToTrash(projectId: number) {
  await store.deleteProject(projectId);
}

async function restoreTrash(item: TrashItem) {
  await store.restoreTrashItem(item.item_id, item.item_type);
}

async function updateMediaAsset(assetId: number, meta: Record<string, unknown>) {
  const asset = longformState.value.media_assets.find((item) => item.id === assetId);
  if (!asset) return;
  const payload: UpdateMediaAssetPayload = {
    uri: asset.uri,
    status: asset.status,
    meta: {
      ...asset.meta,
      ...meta,
    },
  };
  await store.updateMediaAsset(assetId, payload);
}

async function submitCreateProject() {
  const title = projectForm.title.trim();
  if (!title) {
    authError.value = "项目标题不能为空。";
    return;
  }

  await store.createProject({
    title,
    genre: projectForm.genre.trim() || "现代都市",
    reference_work: "",
    reference_work_creator: "",
    reference_work_medium: "",
    reference_work_synopsis: "",
    reference_work_style_traits: [],
    reference_work_world_traits: [],
    reference_work_narrative_constraints: [],
    reference_work_confidence_note: "",
    reference_inheritance_mode: projectForm.reference_inheritance_mode,
    reference_rewrite_start: projectForm.reference_rewrite_start.trim(),
    reference_authorized_changes: projectForm.reference_authorized_changes.trim(),
    story_boundary_text: projectForm.story_boundary_text.trim(),
    visual_style_locked: projectForm.visual_style_locked,
    visual_style_medium: projectForm.visual_style_medium.trim(),
    visual_style_artists: [...projectForm.visual_style_artists],
    visual_style_positive: [...projectForm.visual_style_positive],
    visual_style_negative: [...projectForm.visual_style_negative],
    visual_style_notes: projectForm.visual_style_notes.trim(),
    world_brief: projectForm.world_brief.trim(),
    writing_rules: projectForm.writing_rules.trim(),
    style_profile: projectForm.style_profile,
  });

  if (!error.value && activeProject.value?.project) {
    Object.assign(projectForm, emptyProjectDraft());
    localStorage.setItem(persistedProjectIdKey, String(activeProject.value.project.id));
    currentView.value = "studio";
  }
}

onMounted(() => {
  void (async () => {
    await store.initialize();
    await restoreViewState();
  })();
});

watch(currentView, (next) => {
  persistView(next);
  void nextTick(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  });
}, { immediate: true });

watch(() => activeProject.value?.project.id, (projectId) => {
  if (projectId) localStorage.setItem(persistedProjectIdKey, String(projectId));
  else localStorage.removeItem(persistedProjectIdKey);
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

    <template v-else>
      <ToonflowWorkbench
        v-model:workspace-search="workspaceSearch"
        :current-view="currentView"
        :creation-mode="projectCreationMode"
        :is-authenticated="isAuthenticated"
        :username="currentUser?.username"
        :projects="projects"
        :active-project="activeProject"
        :longform-state="longformState"
        :context-pack="contextPack"
        :generation-attempts="generationAttempts"
        :generation-attempts-loading="generationAttemptsLoading"
        :generation-attempts-error="generationAttemptsError"
        :trash-items="trashItems"
        :trash-summary="trashSummary"
        :loading="loading"
        :longform-request="longformRequestState"
        :longform-last-refreshed-at="store.longformLastRefreshedAt"
        :longform-refresh-error="store.longformRefreshError"
        :longform-polling-failures="store.longformPollingFailures"
        :form="projectForm"
        @go="goToView"
        @login="openAuthPanel('login', 'studio')"
        @register="openAuthPanel('register', 'studio')"
        @logout="store.logout()"
        @open-project-create="openSidebarProjectCreate"
        @load-imported-project-draft="loadImportedProjectDraft"
        @load-ai-project-draft="loadAiProjectDraft"
        @open-project="openWorkspaceProject"
        @delete-project="deleteProjectToTrash"
        @restore-trash="restoreTrash"
        @update-media-asset="updateMediaAsset"
        @delete-media-asset="store.deleteMediaAsset"
        @create-video-task="store.createVideoTask"
        @create-storyboard="store.createBriefStoryboard"
        @import-storyboard="store.importStoryboard"
        @refresh-tasks="store.loadLongformState(activeProject?.project.id)"
        @delete-video-task="store.deleteVideoTask"
        @delete-storyboard="store.deleteStoryboard"
        @generate-character-turnaround="store.generateCharacterTurnaround"
        @generate-shot-first-frame="store.generateShotFirstFrame"
        @generate-storyboard-voice="store.generateStoryboardVoice"
        @prepare-video-production="store.prepareVideoProduction"
        @load-generation-attempts="store.loadGenerationAttempts"
        @build-context-pack="store.buildContextPack"
        @rebuild-context-pack="store.rebuildContextPack"
        @confirm-context-pack="store.confirmContextPack"
        @update-context-pack-decisions="store.updateContextPackDecisions"
        @update-context-pack-todo="store.updateContextPackTodo"
        @generate-series-plan="store.generateSeriesPlan"
        @run-batch-generation="store.runBatchGeneration"
        @retry-chapter-task="store.retryChapterTask"
        @revise-draft-version="store.reviseDraftVersion"
        @canonicalize-draft-version="store.canonicalizeDraftVersion"
        @confirm-series-plan="store.lockSeriesPlan"
        @update-storyboard-shot="store.updateStoryboardShot"
        @create-storyboard-shot="store.createStoryboardShot"
        @delete-storyboard-shot="store.deleteStoryboardShot"
        @reorder-storyboard-shots="store.reorderStoryboardShots"
        @save-project-settings="store.updateProject"
        @update:title="projectForm.title = $event"
        @update:genre="projectForm.genre = $event"
        @update:world-brief="projectForm.world_brief = $event"
        @update:writing-rules="projectForm.writing_rules = $event"
        @submit-create="submitCreateProject()"
      />
    </template>
  </div>
</template>
