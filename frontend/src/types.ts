export interface BootstrapResponse {
  service_name: string;
  graph_engine: string;
  auth_enabled: boolean;
  writer_model: string;
  utility_model: string;
  punctuation_rule: string;
  query_methods: string[];
}

export interface User {
  id: number;
  email: string;
  display_name: string;
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
