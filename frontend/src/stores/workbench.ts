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


const tokenKey = "graph_mvp_token";


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

  const isAuthenticated = computed(() => Boolean(token.value && currentUser.value));

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
      success.value = "注册完成，已自动登录。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "注册失败。";
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
      success.value = "登录成功。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "登录失败。";
    } finally {
      loading.value = false;
    }
  }

  function logout() {
    setToken(null);
    currentUser.value = null;
    projects.value = [];
    activeProject.value = null;
    currentGeneration.value = null;
    success.value = "已退出登录。";
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

  async function selectProject(projectId: number) {
    if (!token.value) {
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      activeProject.value = await api.projectDetail(token.value, projectId);
      currentGeneration.value = activeProject.value.generations[0] ?? null;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "读取项目失败。";
    } finally {
      loading.value = false;
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
      success.value = "项目已创建。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建项目失败。";
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
      success.value = "记忆已加入项目。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "写入记忆失败。";
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
      error.value = err instanceof Error ? err.message : "写入资料失败。";
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
      await api.indexProject(token.value, activeProject.value.project.id, { force_rebuild: true });
      await selectProject(activeProject.value.project.id);
      success.value = "GraphRAG 索引和 Neo4j 同步已完成。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "索引失败。";
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
      await selectProject(activeProject.value.project.id);
      success.value = "新的小说内容已经生成。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "生成失败。";
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
