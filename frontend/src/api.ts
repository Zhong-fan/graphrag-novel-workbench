import type {
  AuthResponse,
  BootstrapResponse,
  CaptchaChallenge,
  FavoriteToggleResponse,
  GenerationItem,
  IndexResponse,
  LikeToggleResponse,
  MemoryItem,
  NovelCard,
  NovelComment,
  NovelDetail,
  UpdateNovelPayload,
  PublishNovelPayload,
  Project,
  ProjectDetailResponse,
  SourceItem,
  User,
  UserProfile,
  AppendNovelChapterPayload,
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
  captcha: () => request<CaptchaChallenge>("/api/auth/captcha"),
  register: (payload: { username: string; password: string; captcha_answer: string; captcha_token: string }) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { username: string; password: string }) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: (token: string) => request<User>("/api/auth/me", { token }),
  myProfile: (token: string) => request<UserProfile>("/api/me/profile", { token }),
  updateMyProfile: (token: string, payload: UserProfile) =>
    request<UserProfile>("/api/me/profile", { method: "PUT", token, body: JSON.stringify(payload) }),
  listProjects: (token: string) => request<Project[]>("/api/projects", { token }),
  createProject: (
    token: string,
    payload: { title: string; genre: string; premise: string; world_brief: string; writing_rules: string; style_profile: string },
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
    payload: {
      prompt: string;
      search_method: string;
      response_type: string;
      use_global_search: boolean;
      use_scene_card: boolean;
      use_refiner: boolean;
      write_evolution: boolean;
    },
  ) => request<GenerationItem>(`/api/projects/${projectId}/generate`, { method: "POST", token, body: JSON.stringify(payload) }),
  listNovels: (token?: string | null) => request<NovelCard[]>("/api/novels", { token }),
  novelDetail: (novelId: number, token?: string | null) => request<NovelDetail>(`/api/novels/${novelId}`, { token }),
  listFavorites: (token: string) => request<NovelCard[]>("/api/me/favorites", { token }),
  listMyNovels: (token: string) => request<NovelCard[]>("/api/me/novels", { token }),
  favoriteNovel: (token: string, novelId: number) =>
    request<FavoriteToggleResponse>(`/api/novels/${novelId}/favorite`, { method: "POST", token }),
  unfavoriteNovel: (token: string, novelId: number) =>
    request<FavoriteToggleResponse>(`/api/novels/${novelId}/favorite`, { method: "DELETE", token }),
  likeNovel: (token: string, novelId: number) =>
    request<LikeToggleResponse>(`/api/novels/${novelId}/like`, { method: "POST", token }),
  unlikeNovel: (token: string, novelId: number) =>
    request<LikeToggleResponse>(`/api/novels/${novelId}/like`, { method: "DELETE", token }),
  listNovelComments: (novelId: number) => request<NovelComment[]>(`/api/novels/${novelId}/comments`),
  createNovelComment: (token: string, novelId: number, payload: { content: string }) =>
    request<NovelComment>(`/api/novels/${novelId}/comments`, { method: "POST", token, body: JSON.stringify(payload) }),
  publishNovelFromGeneration: (token: string, payload: PublishNovelPayload) =>
    request<NovelDetail>("/api/novels/from-generation", { method: "POST", token, body: JSON.stringify(payload) }),
  updateNovel: (token: string, novelId: number, payload: UpdateNovelPayload) =>
    request<NovelDetail>(`/api/novels/${novelId}`, { method: "PUT", token, body: JSON.stringify(payload) }),
  appendNovelChapterFromGeneration: (token: string, novelId: number, payload: AppendNovelChapterPayload) =>
    request<NovelDetail>(`/api/novels/${novelId}/chapters/from-generation`, {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
};
