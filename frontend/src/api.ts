import type {
  AuthResponse,
  BootstrapResponse,
  CaptchaChallenge,
  CharacterCard,
  CharacterCardPayload,
  FavoriteToggleResponse,
  GraphReviewPayload,
  GenerationItem,
  GenerationProgress,
  IndexResponse,
  LikeToggleResponse,
  MemoryItem,
  NovelCard,
  NovelComment,
  NovelDetail,
  UpdateNovelPayload,
  PublishNovelPayload,
  Project,
  ProjectChapter,
  ProjectChapterPayload,
  ProjectDetailResponse,
  ProjectPayload,
  ReferenceWorkResolveRequest,
  ReferenceWorkResolved,
  ProjectSuggestionRequest,
  ProjectSuggestionResponse,
  SourceItem,
  User,
  UserProfile,
  AppendNovelChapterPayload,
  CreateFolderPayload,
  DeletePayload,
  UpdateNovelChapterPayload,
  UpdateProjectChapterPayload,
  MoveProjectFolderPayload,
  MyWorkspaceResponse,
  ProjectFolder,
  RestoreTrashPayload,
} from "./types";

type RequestOptions = RequestInit & {
  token?: string | null;
};

const fieldLabels: Record<string, string> = {
  username: "用户名",
  password: "密码",
  captcha_answer: "验证码",
  captcha_token: "验证码",
};

function localizeValidationMessage(message: string): string {
  const minLengthMatch = message.match(/at least (\d+) characters/i);
  if (minLengthMatch) {
    return `至少需要 ${minLengthMatch[1]} 个字符`;
  }
  const maxLengthMatch = message.match(/at most (\d+) characters/i);
  if (maxLengthMatch) {
    return `不能超过 ${maxLengthMatch[1]} 个字符`;
  }
  if (/field required/i.test(message)) {
    return "不能为空";
  }
  return message;
}

function formatErrorDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object") {
          const record = item as { loc?: unknown; msg?: unknown; message?: unknown };
          const message = typeof record.msg === "string" ? record.msg : typeof record.message === "string" ? record.message : "";
          if (!message) {
            return JSON.stringify(item);
          }
          const path = Array.isArray(record.loc) ? record.loc.filter((part) => part !== "body") : [];
          const field = path.length ? String(path[path.length - 1]) : "";
          const label = fieldLabels[field] ?? field;
          const readableMessage = localizeValidationMessage(message);
          return label ? `${label}: ${readableMessage}` : readableMessage;
        }
        return String(item);
      })
      .join("；");
  }

  if (detail && typeof detail === "object") {
    const record = detail as { msg?: unknown; message?: unknown; error?: unknown };
    if (typeof record.msg === "string") {
      return record.msg;
    }
    if (typeof record.message === "string") {
      return record.message;
    }
    if (typeof record.error === "string") {
      return record.error;
    }
    return JSON.stringify(detail);
  }

  return String(detail);
}

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
        message = formatErrorDetail(payload.detail);
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
  myWorkspace: (token: string) => request<MyWorkspaceResponse>("/api/me/workspace", { token }),
  createFolder: (token: string, payload: CreateFolderPayload) =>
    request<ProjectFolder>("/api/me/folders", { method: "POST", token, body: JSON.stringify(payload) }),
  createProject: (token: string, payload: ProjectPayload) =>
    request<Project>("/api/projects", { method: "POST", token, body: JSON.stringify(payload) }),
  resolveReferenceWork: (token: string, payload: ReferenceWorkResolveRequest) =>
    request<ReferenceWorkResolved>("/api/projects/reference-work/resolve", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
  suggestProjectBriefing: (token: string, payload: ProjectSuggestionRequest) =>
    request<ProjectSuggestionResponse>("/api/projects/briefing-suggestions", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
  updateProject: (token: string, projectId: number, payload: ProjectPayload) =>
    request<Project>(`/api/projects/${projectId}`, { method: "PUT", token, body: JSON.stringify(payload) }),
  moveProjectToFolder: (token: string, projectId: number, payload: MoveProjectFolderPayload) =>
    request<Project>(`/api/projects/${projectId}/folder`, { method: "PUT", token, body: JSON.stringify(payload) }),
  deleteProject: (token: string, projectId: number, payload: DeletePayload) =>
    request<Project>(`/api/projects/${projectId}`, { method: "DELETE", token, body: JSON.stringify(payload) }),
  projectDetail: (token: string, projectId: number) =>
    request<ProjectDetailResponse>(`/api/projects/${projectId}`, { token }),
  createProjectChapter: (token: string, projectId: number, payload: ProjectChapterPayload) =>
    request<ProjectChapter>(`/api/projects/${projectId}/chapters`, { method: "POST", token, body: JSON.stringify(payload) }),
  updateProjectChapter: (token: string, projectId: number, chapterId: number, payload: UpdateProjectChapterPayload) =>
    request<ProjectChapter>(`/api/projects/${projectId}/chapters/${chapterId}`, { method: "PUT", token, body: JSON.stringify(payload) }),
  addMemory: (
    token: string,
    projectId: number,
    payload: { title: string; content: string; memory_scope: string; importance: number },
  ) => request<MemoryItem>(`/api/projects/${projectId}/memories`, { method: "POST", token, body: JSON.stringify(payload) }),
  addCharacterCard: (token: string, projectId: number, payload: CharacterCardPayload) =>
    request<CharacterCard>(`/api/projects/${projectId}/character-cards`, { method: "POST", token, body: JSON.stringify(payload) }),
  updateCharacterCard: (token: string, projectId: number, cardId: number, payload: CharacterCardPayload) =>
    request<CharacterCard>(`/api/projects/${projectId}/character-cards/${cardId}`, { method: "PUT", token, body: JSON.stringify(payload) }),
  addSource: (
    token: string,
    projectId: number,
    payload: { title: string; content: string; source_kind: string },
  ) => request<SourceItem>(`/api/projects/${projectId}/sources`, { method: "POST", token, body: JSON.stringify(payload) }),
  prepareGraphReview: (token: string, projectId: number) =>
    request<GraphReviewPayload>(`/api/projects/${projectId}/graphrag/prepare-review`, { method: "POST", token }),
  updateGraphReviewFile: (token: string, projectId: number, filename: string, payload: { content: string }) =>
    request<GraphReviewPayload>(`/api/projects/${projectId}/graphrag/files/${encodeURIComponent(filename)}`, {
      method: "PUT",
      token,
      body: JSON.stringify(payload),
    }),
  indexProject: (token: string, projectId: number, payload: { force_rebuild: boolean }) =>
    request<IndexResponse>(`/api/projects/${projectId}/index`, { method: "POST", token, body: JSON.stringify(payload) }),
  generate: (
    token: string,
    projectId: number,
    payload: {
      chapter_id: number;
      prompt: string;
      search_method: string;
      response_type: string;
      use_global_search: boolean;
      use_scene_card: boolean;
      use_refiner: boolean;
      write_evolution: boolean;
    },
  ) => request<GenerationItem>(`/api/projects/${projectId}/generate`, { method: "POST", token, body: JSON.stringify(payload) }),
  generationProgress: (token: string, projectId: number) =>
    request<GenerationProgress>(
      `/api/projects/${projectId}/generate/progress`,
      { token },
    ),
  refreshGenerationEvolution: (token: string, projectId: number, generationId: number) =>
    request<GenerationItem>(`/api/projects/${projectId}/generations/${generationId}/refresh-evolution`, { method: "POST", token }),
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
  deleteNovel: (token: string, novelId: number, payload: DeletePayload) =>
    request<NovelDetail>(`/api/novels/${novelId}`, { method: "DELETE", token, body: JSON.stringify(payload) }),
  appendNovelChapterFromGeneration: (token: string, novelId: number, payload: AppendNovelChapterPayload) =>
    request<NovelDetail>(`/api/novels/${novelId}/chapters/from-generation`, {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
  updateNovelChapter: (token: string, novelId: number, chapterId: number, payload: UpdateNovelChapterPayload) =>
    request<NovelDetail>(`/api/novels/${novelId}/chapters/${chapterId}`, {
      method: "PUT",
      token,
      body: JSON.stringify(payload),
    }),
  deleteCharacterCard: (token: string, projectId: number, cardId: number, payload: DeletePayload) =>
    request<CharacterCard>(`/api/projects/${projectId}/character-cards/${cardId}`, {
      method: "DELETE",
      token,
      body: JSON.stringify(payload),
    }),
  restoreTrashItem: (token: string, itemId: number, payload: RestoreTrashPayload) =>
    request<{ status: string }>(`/api/trash/${itemId}/restore`, {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
  trashDirtyEvolution: (token: string, projectId: number) =>
    request<{ status: string; stats: Record<string, number> }>(`/api/projects/${projectId}/dirty-evolution/trash`, {
      method: "POST",
      token,
    }),
};
