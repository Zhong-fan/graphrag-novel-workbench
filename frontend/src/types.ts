export interface BootstrapResponse {
  service_name: string;
  graph_engine: string;
  auth_enabled: boolean;
  writer_model: string;
  utility_model: string;
  embedding_model: string;
  embedding_provider: string;
  embedding_base_url: string;
  punctuation_rule: string;
  query_methods: string[];
}

export interface CaptchaChallenge {
  challenge: string;
  token: string;
  expires_in: number;
}

export interface User {
  id: number;
  username: string;
  email?: string | null;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface Project {
  id: number;
  title: string;
  genre: string;
  premise: string;
  world_brief: string;
  writing_rules: string;
  punctuation_rule: string;
  indexing_status: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryItem {
  id: number;
  title: string;
  content: string;
  memory_scope: string;
  importance: number;
  created_at: string;
  updated_at: string;
}

export interface SourceItem {
  id: number;
  title: string;
  content: string;
  source_kind: string;
  created_at: string;
  updated_at: string;
}

export interface GenerationItem {
  id: number;
  title: string;
  content: string;
  summary: string;
  retrieval_context: string;
  search_method: string;
  response_type: string;
  created_at: string;
}

export interface ProjectDetailResponse {
  project: Project;
  memories: MemoryItem[];
  sources: SourceItem[];
  generations: GenerationItem[];
}

export interface IndexResponse {
  status: string;
  workspace_path: string;
  neo4j_sync_status: string;
}

export interface NovelChapter {
  id: number;
  title: string;
  summary: string;
  content: string;
  chapter_no: number;
  created_at: string;
  updated_at: string;
}

export interface NovelCard {
  id: number;
  title: string;
  author: string;
  summary: string;
  genre: string;
  tagline: string;
  cover_url?: string | null;
  status: string;
  visibility: string;
  likes_count: number;
  favorites_count: number;
  comments_count: number;
  chapters_count: number;
  latest_excerpt: string;
  is_liked: boolean;
  is_favorited: boolean;
  created_at: string;
  updated_at: string;
}

export interface NovelDetail extends NovelCard {
  chapters: NovelChapter[];
}

export interface NovelComment {
  id: number;
  user_id: number;
  username: string;
  content: string;
  created_at: string;
}

export interface FavoriteToggleResponse {
  favorited: boolean;
  novel_id: number;
  favorites_count: number;
}

export interface LikeToggleResponse {
  liked: boolean;
  novel_id: number;
  likes_count: number;
}

export interface PublishNovelPayload {
  project_id: number;
  generation_id: number;
  title: string;
  author_name: string;
  summary: string;
  tagline: string;
  visibility: "public" | "private";
}

export interface UpdateNovelPayload {
  title: string;
  author_name: string;
  summary: string;
  tagline: string;
  visibility: "public" | "private";
}

export interface AppendNovelChapterPayload {
  project_id: number;
  generation_id: number;
  title: string;
}

export interface UserProfile {
  bio: string;
  email?: string | null;
  phone?: string | null;
}
