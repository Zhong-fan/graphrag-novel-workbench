import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { api } from "../api";
import type {
  BootstrapResponse,
  GenerationItem,
  Project,
  ProjectDetailResponse,
  User,
} from "../types";

type SelectProjectOptions = {
  showLoading?: boolean;
  silent?: boolean;
};

const tokenKey = "graph_mvp_token";
const indexPendingMessage = "Index job submitted. Waiting for project status to become ready.";
const indexReadyMessage = "GraphRAG index completed. You can generate content now.";
const pollDelayMs = 3000;

export const useWorkbenchStore = defineStore("workbench", () => {
  const bootstrap = ref<BootstrapResponse | null>(null);
  const token = ref<string | null>(localStorage.getItem(tokenKey));
  const currentUser = ref<User | null>(null);
  const projects = ref<Project[]>([]);
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

  async function initialize() {
    error.value = "";
    bootstrap.value = await api.bootstrap();
    if (token.value) {
      try {
        currentUser.value = await api.me(token.value);
        await loadProjects();
      } catch {
        stopProjectPolling();
        setToken(null);
        currentUser.value = null;
      }
    }
  }

  async function register(payload: { email: string; display_name: string; password: string }) {
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const response = await api.register(payload);
      setToken(response.token);
      currentUser.value = response.user;
      await loadProjects();
      success.value = "Registration complete. Logged in automatically.";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Registration failed.";
    } finally {
      loading.value = false;
    }
  }

  async function login(payload: { email: string; password: string }) {
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      const response = await api.login(payload);
      setToken(response.token);
      currentUser.value = response.user;
      await loadProjects();
      success.value = "Login successful.";
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
    activeProject.value = null;
    currentGeneration.value = null;
    success.value = "Logged out.";
    error.value = "";
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
        error.value = err instanceof Error ? err.message : "Failed to load project.";
      }
    } finally {
      if (showLoading) {
        loading.value = false;
      }
    }
  }

  async function createProject(payload: {
    title: string;
    genre: string;
    premise: string;
    world_brief: string;
    writing_rules: string;
  }) {
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
      success.value = "Project created.";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to create project.";
    } finally {
      loading.value = false;
    }
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
      success.value = "Memory added to the project.";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save memory.";
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
      success.value = "Source added to the project.";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save source.";
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
      error.value = err instanceof Error ? err.message : "Failed to start indexing.";
    } finally {
      loading.value = false;
    }
  }

  async function generate(payload: { prompt: string; search_method: string; response_type: string }) {
    if (!token.value || !activeProject.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    success.value = "";
    try {
      currentGeneration.value = await api.generate(token.value, activeProject.value.project.id, payload);
      await selectProject(activeProject.value.project.id, { showLoading: false, silent: true });
      success.value = "New content generated.";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Generation failed.";
    } finally {
      loading.value = false;
    }
  }

  return {
    bootstrap,
    token,
    currentUser,
    projects,
    activeProject,
    currentGeneration,
    loading,
    error,
    success,
    isAuthenticated,
    initialize,
    register,
    login,
    logout,
    selectProject,
    createProject,
    addMemory,
    addSource,
    indexProject,
    generate,
  };
});
