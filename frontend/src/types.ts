export type ViewKey =
  | "studio"
  | "trash"
  | "projectCreate"
  | "projectSettings"
  | "projectLibrary"
  | "characters"
  | "longform"
  | "workshop"
  | "generationTrace"
  | "novelEditor"
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
  visual_style_locked: boolean;
  visual_style_medium: string;
  visual_style_artists: string[];
  visual_style_positive: string[];
  visual_style_negative: string[];
  visual_style_notes: string;
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
  visual_style_locked: boolean;
  visual_style_medium: string;
  visual_style_artists: string[];
  visual_style_positive: string[];
  visual_style_negative: string[];
  visual_style_notes: string;
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
  voice_provider: string;
  voice_speaker: string;
  voice_style: string;
  voice_speed: number;
  voice_pitch: number;
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
  voice_provider: string;
  voice_speaker: string;
  voice_style: string;
  voice_speed: number;
  voice_pitch: number;
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

export interface SeriesPlanVersion {
  id: number;
  series_plan_id: number;
  version_no: number;
  summary: Record<string, unknown>;
  change_note: string;
  source_feedback_snapshot: string;
  created_by: string;
  created_at: string;
}

export interface ArcPlan {
  id: number;
  series_plan_id: number;
  version_id: number;
  arc_no: number;
  start_chapter_no: number;
  end_chapter_no: number;
  title: string;
  goal: string;
  conflict: string;
  turning_points: unknown[];
  status: string;
}

export interface ChapterOutline {
  id: number;
  project_id: number;
  series_plan_id: number;
  arc_plan_id?: number | null;
  chapter_no: number;
  title: string;
  outline: Record<string, unknown>;
  status: string;
  locked_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DraftVersion {
  id: number;
  project_id: number;
  chapter_outline_id: number;
  generation_run_id?: number | null;
  parent_version_id?: number | null;
  version_no: number;
  title: string;
  summary: string;
  content: string;
  status: string;
  revision_reason: string;
  created_at: string;
}

export interface SeriesPlan {
  id: number;
  project_id: number;
  title: string;
  target_chapter_count: number;
  theme: string;
  main_conflict: string;
  ending_direction: string;
  status: string;
  current_version_id?: number | null;
  created_at: string;
  updated_at: string;
  current_version?: SeriesPlanVersion | null;
  versions: SeriesPlanVersion[];
  arcs: ArcPlan[];
  chapters: ChapterOutline[];
}

export interface BatchGenerationJob {
  id: number;
  project_id: number;
  series_plan_id: number;
  start_chapter_no: number;
  end_chapter_no: number;
  job_status: string;
  current_chapter_no?: number | null;
  result_summary: Record<string, unknown>;
  worker_id: string;
  worker_started_at?: string | null;
  last_heartbeat_at?: string | null;
  chapter_tasks: BatchGenerationChapterTask[];
  events: TaskEvent[];
  created_at: string;
  updated_at: string;
}

export interface BatchGenerationChapterTask {
  id: number;
  job_id: number;
  chapter_outline_id: number;
  chapter_no: number;
  status: string;
  draft_version_id?: number | null;
  generation_run_id?: number | null;
  error_message: string;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskEvent {
  id: number;
  project_id: number;
  job_id?: number | null;
  storyboard_id?: number | null;
  video_task_id?: number | null;
  chapter_task_id?: number | null;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface StoryboardShot {
  id: number;
  storyboard_id: number;
  shot_no: number;
  narration_text: string;
  visual_prompt: string;
  character_refs: unknown[];
  scene_refs: unknown[];
  audio_script: Record<string, unknown>;
  duration_seconds: number;
  status: string;
}

export interface Storyboard {
  id: number;
  project_id: number;
  title: string;
  source_chapter_ids: unknown[];
  status: string;
  summary: string;
  progress: Record<string, unknown>;
  worker_id: string;
  worker_started_at?: string | null;
  last_heartbeat_at?: string | null;
  error_message: string;
  shots: StoryboardShot[];
  events: TaskEvent[];
  created_at: string;
  updated_at: string;
}

export interface VideoTask {
  id: number;
  project_id: number;
  storyboard_id: number;
  task_status: string;
  output_uri: string;
  progress: Record<string, unknown>;
  error_message: string;
  events: TaskEvent[];
  created_at: string;
  updated_at: string;
}

export interface MediaAsset {
  id: number;
  project_id: number;
  storyboard_id?: number | null;
  shot_id?: number | null;
  asset_type: string;
  uri: string;
  prompt: string;
  status: string;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LongformState {
  series_plans: SeriesPlan[];
  draft_versions: DraftVersion[];
  batch_jobs: BatchGenerationJob[];
  storyboards: Storyboard[];
  media_assets: MediaAsset[];
  video_tasks: VideoTask[];
}

export interface GenerateSeriesPlanPayload {
  target_chapter_count: number;
  user_brief: string;
}

export interface SubmitOutlineFeedbackPayload {
  target_type: "series" | "arc" | "chapter";
  target_id: number;
  feedback_text: string;
  feedback_type: string;
  priority: number;
}

export interface OutlineRevisionResponse {
  feedback: Record<string, unknown>;
  revision_plan: Record<string, unknown>;
  series_plan: SeriesPlan;
}

export interface BatchGenerationPayload {
  series_plan_id: number;
  start_chapter_no: number;
  end_chapter_no: number;
}

export interface CreateStoryboardPayload {
  novel_chapter_ids: number[];
  title: string;
}

export interface ReviseDraftPayload {
  feedback_text: string;
}

export interface CanonicalizeDraftPayload {
  novel_id?: number | null;
  author_name: string;
  visibility: "public" | "private";
  tagline: string;
}

export interface UpdateChapterOutlinePayload {
  title: string;
  outline: Record<string, unknown>;
  status: string;
}

export interface UpdateStoryboardShotPayload {
  narration_text: string;
  visual_prompt: string;
  character_refs: unknown[];
  scene_refs: unknown[];
  audio_script: Record<string, unknown>;
  duration_seconds: number;
  status: string;
}

export interface CreateStoryboardShotPayload extends UpdateStoryboardShotPayload {
  shot_no?: number | null;
}

export interface ReorderStoryboardShotsPayload {
  shot_ids: number[];
}

export interface UpdateMediaAssetPayload {
  uri: string;
  status: string;
  meta: Record<string, unknown>;
}

export interface GenerateCharacterTurnaroundPayload {
  character_card_id: number;
  chapter_no?: number | null;
  prompt_note: string;
}

export interface GenerateShotFirstFramePayload {
  shot_id: number;
}

export interface GenerateVoicePayload {
  voice_profile?: string;
  provider?: string;
  voice_role?: "narrator" | "dialogue";
  character_card_id?: number | null;
  dialogue_text?: string;
  speed?: number;
  emotion?: string;
  text_override?: string;
}

export interface GenerateAudioScriptsPayload {
  dialogue_density?: string;
  narration_policy?: string;
  music_policy?: string;
  sound_effect_policy?: string;
}

export interface VideoProductionPreflightPayload {
  generate_character_turnarounds?: boolean;
  generate_audio_scripts?: boolean;
  refresh_audio_scripts?: boolean;
  generate_dialogue_audio?: boolean;
  create_video_task?: boolean;
  fallback_voice_profile?: string;
}

export interface UpdateVideoTaskPayload {
  task_status: string;
  output_uri: string;
  progress: Record<string, unknown>;
  error_message: string;
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
