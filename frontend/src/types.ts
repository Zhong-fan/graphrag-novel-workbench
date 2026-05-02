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
  style_profile: string;
  punctuation_rule: string;
  indexing_status: string;
  folder_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectPayload {
  title: string;
  genre: string;
  premise: string;
  world_brief: string;
  writing_rules: string;
  style_profile: string;
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

export interface CharacterCard {
  id: number;
  name: string;
  age: string;
  gender: string;
  personality: string;
  story_role: string;
  background: string;
  created_at: string;
  updated_at: string;
}

export interface CharacterCardPayload {
  name: string;
  age: string;
  gender: string;
  personality: string;
  story_role: string;
  background: string;
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
  scene_card: string;
  evolution_snapshot: string;
  search_method: string;
  response_type: string;
  created_at: string;
}

export interface ProjectDetailResponse {
  project: Project;
  memories: MemoryItem[];
  character_cards: CharacterCard[];
  sources: SourceItem[];
  generations: GenerationItem[];
  character_state_updates: CharacterStateUpdate[];
  relationship_state_updates: RelationshipStateUpdate[];
  story_events: StoryEventItem[];
  world_perception_updates: WorldPerceptionUpdate[];
}

export interface ProjectFolder {
  id: number;
  name: string;
  sort_order: number;
  is_default: boolean;
  project_count: number;
  created_at: string;
  updated_at: string;
}

export interface TrashItem {
  item_type: "project" | "novel" | "character_card";
  item_id: number;
  title: string;
  subtitle: string;
  deleted_at: string;
  project_id?: number | null;
}

export interface MyWorkspaceResponse {
  folders: ProjectFolder[];
  projects: Project[];
  trash: TrashItem[];
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
  chapter_title: string;
  chapter_summary: string;
  chapter_content: string;
  chapter_no: number;
}

export interface UpdateNovelPayload {
  title: string;
  author_name: string;
  summary: string;
  tagline: string;
  visibility: "public" | "private";
}

export interface CreateFolderPayload {
  name: string;
}

export interface MoveProjectFolderPayload {
  folder_id?: number | null;
}

export interface DeletePayload {
  hard_delete?: boolean;
}

export interface RestoreTrashPayload {
  item_type: "project" | "novel" | "character_card";
}

export interface AppendNovelChapterPayload {
  project_id: number;
  generation_id: number;
  title: string;
  summary: string;
  content: string;
  chapter_no?: number | null;
}

export interface UpdateNovelChapterPayload {
  title: string;
  summary: string;
  content: string;
  chapter_no: number;
}

export interface UserProfile {
  bio: string;
  email?: string | null;
  phone?: string | null;
}

export interface CharacterStateUpdate {
  id: number;
  character_name: string;
  emotion_state: string;
  current_goal: string;
  self_view_shift: string;
  public_perception: string;
  summary: string;
  created_at: string;
}

export interface RelationshipStateUpdate {
  id: number;
  source_character: string;
  target_character: string;
  change_type: string;
  direction: string;
  intensity: number;
  summary: string;
  created_at: string;
}

export interface StoryEventItem {
  id: number;
  title: string;
  summary: string;
  impact_summary: string;
  participants: string[];
  location_hint: string;
  created_at: string;
}

export interface WorldPerceptionUpdate {
  id: number;
  subject_name: string;
  observer_group: string;
  direction: string;
  change_summary: string;
  created_at: string;
}
