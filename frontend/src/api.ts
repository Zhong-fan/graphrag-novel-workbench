import type {
  AuthResponse,
  BootstrapResponse,
  GenerationItem,
  IndexResponse,
  MemoryItem,
  Project,
  ProjectDetailResponse,
  SourceItem,
  User,
} from "./types";

type RequestOptions = RequestInit & {
  token?: string | null;
};

async function request<T>(input: RequestInfo, init: RequestOptions = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  headers.set("Content-Type", "application/json");
  if (init.token) {
    headers.set("Authorization", `Bearer ${init.token}`);
  }

  const response = await fetch(input, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = String(payload.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export const api = {
  bootstrap: () => request<BootstrapResponse>("/api/bootstrap"),
  register: (payload: { email: string; display_name: string; password: string }) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: (token: string) => request<User>("/api/auth/me", { token }),
  listProjects: (token: string) => request<Project[]>("/api/projects", { token }),
  createProject: (
    token: string,
    payload: { title: string; genre: string; premise: string; world_brief: string; writing_rules: string },
  ) => request<Project>("/api/projects", { method: "POST", token, body: JSON.stringify(payload) }),
  projectDetail: (token: string, projectId: number) =>
    request<ProjectDetailResponse>(`/api/projects/${projectId}`, { token }),
  addMemory: (
    token: string,
    projectId: number,
    payload: { title: string; content: string; memory_scope: string; importance: number },
  ) => request<MemoryItem>(`/api/projects/${projectId}/memories`, { method: "POST", token, body: JSON.stringify(payload) }),
  addSource: (
    token: string,
    projectId: number,
    payload: { title: string; content: string; source_kind: string },
  ) => request<SourceItem>(`/api/projects/${projectId}/sources`, { method: "POST", token, body: JSON.stringify(payload) }),
  indexProject: (token: string, projectId: number, payload: { force_rebuild: boolean }) =>
    request<IndexResponse>(`/api/projects/${projectId}/index`, { method: "POST", token, body: JSON.stringify(payload) }),
  generate: (
    token: string,
    projectId: number,
    payload: { prompt: string; search_method: string; response_type: string },
  ) => request<GenerationItem>(`/api/projects/${projectId}/generate`, { method: "POST", token, body: JSON.stringify(payload) }),
};
