export type ViewKey =
  | "studio"
  | "trash"
  | "projectCreate"
  | "projectSettings"
  | "characters"
  | "workshop"
  | "generationTrace"
  | "novelEditor"
  | "profile"
  | "auth";

export interface BootstrapResponse {
  service_name: string;
  auth_enabled: boolean;
  writer_model: string;
  utility_model: string;
  embedding_model: string;
  embedding_provider: string;
  embedding_base_url: string;
  punctuation_rule: string;
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
  reference_work: string;
  reference_work_creator: string;
  reference_work_medium: string;
  reference_work_synopsis: string;
  reference_work_style_traits: string[];
  reference_work_world_traits: string[];
  reference_work_narrative_constraints: string[];
  reference_work_confidence_note: string;
  world_brief: string;
  writing_rules: string;
  style_profile: string;
  punctuation_rule: string;
  folder_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectPayload {
  title: string;
  genre: string;
  reference_work: string;
  reference_work_creator: string;
  reference_work_medium: string;
  reference_work_synopsis: string;
  reference_work_style_traits: string[];
  reference_work_world_traits: string[];
  reference_work_narrative_constraints: string[];
  reference_work_confidence_note: string;
  world_brief: string;
  writing_rules: string;
  style_profile: string;
}

export interface ProjectCreateDraft extends ProjectPayload {
  reference_work_confirmed: boolean;
}

export interface ProjectSuggestionRequest {
  kind: "world_brief" | "writing_rules";
  title: string;
  genre: string;
  reference_work: string;
  seed_text: string;
}

export interface ProjectSuggestionResponse {
  kind: "world_brief" | "writing_rules";
  suggestions: string[];
}

export interface ReferenceWorkResolveRequest {
  query: string;
  genre: string;
}

export interface ReferenceWorkResolved {
  canonical_title: string;
  creator: string;
  medium: string;
  synopsis: string;
  style_traits: string[];
  world_traits: string[];
  narrative_constraints: string[];
  confidence_note: string;
}

export interface ProjectChapter {
  id: number;
  project_id: number;
  title: string;
  premise: string;
  chapter_no: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectChapterPayload {
  title: string;
  premise: string;
  chapter_no?: number | null;
}

export interface UpdateProjectChapterPayload {
  title: string;
  premise: string;
  chapter_no: number;
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
  project_chapter_id?: number | null;
  title: string;
  content: string;
  summary: string;
  retrieval_context: string;
  scene_card: string;
  evolution_snapshot: string;
  generation_trace: string;
  search_method: string;
  response_type: string;
  created_at: string;
}

export interface GenerationProgressLog {
  timestamp: string;
  stage: string;
  level: "info" | "warning" | "error" | string;
  message: string;
  details?: Record<string, unknown>;
}

export interface GenerationProgress {
  stage: string;
  message: string;
  trace?: Record<string, unknown>;
  logs?: GenerationProgressLog[];
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

export interface ProjectDetailResponse {
  project: Project;
  project_chapters: ProjectChapter[];
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
  item_type: "project" | "novel" | "character_card" | "dirty_evolution";
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
  project_id?: number | null;
  source_generation_id?: number | null;
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

export interface PublishNovelPayload {
  project_id: number;
  project_chapter_id: number;
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
  item_type: "project" | "novel" | "character_card" | "dirty_evolution";
}

export interface AppendNovelChapterPayload {
  project_id: number;
  project_chapter_id: number;
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
