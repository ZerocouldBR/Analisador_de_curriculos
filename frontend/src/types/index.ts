// ==================== Auth ====================
export interface User {
  id: number;
  email: string;
  name: string;
  status: string;
  is_superuser: boolean;
  company_id?: number;
  roles?: string[];
  created_at: string;
  last_login?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

// ==================== Candidates ====================
export interface Candidate {
  id: number;
  full_name: string;
  email?: string;
  phone?: string;
  doc_id?: string;
  birth_date?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  company_id?: number;
  created_at: string;
  updated_at: string;
}

export interface CandidateProfile {
  id: number;
  candidate_id: number;
  snapshot_data: Record<string, any>;
  version: number;
  created_at: string;
}

export interface Experience {
  id: number;
  candidate_id: number;
  company_name: string;
  role_title: string;
  start_date?: string;
  end_date?: string;
  description?: string;
  location?: string;
  is_current: boolean;
}

// ==================== Documents ====================
export interface Document {
  id: number;
  candidate_id: number;
  original_filename: string;
  mime_type: string;
  source_path: string;
  sha256_hash: string;
  file_size?: number;
  status?: string;
  uploaded_at: string;
}

// ==================== Search ====================
export interface SearchResult {
  candidate_id: number;
  candidate_name: string;
  score: number;
  email?: string;
  city?: string;
  state?: string;
  matched_chunks: MatchedChunk[];
}

export interface MatchedChunk {
  section: string;
  content: string;
  similarity: number;
}

export interface SearchFilters {
  city?: string;
  state?: string;
  skills?: string[];
  min_experience?: number;
}

// ==================== WebSocket ====================
export interface WebSocketMessage {
  type: string;
  document_id?: number;
  status?: string;
  progress?: number;
  message?: string;
  data?: Record<string, any>;
}

// ==================== Roles & Permissions ====================
export interface Role {
  id: number;
  name: string;
  description?: string;
  permissions: Record<string, boolean>;
}

// ==================== Settings ====================
export interface ServerSettings {
  id: number;
  key: string;
  value_json: any;
  description?: string;
  version: number;
  updated_at: string;
}

// System Config - Configuracoes completas do sistema
export interface SystemConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'password' | 'textarea' | 'list_int' | 'list_str';
  description: string;
  restart_required: boolean;
  sensitive: boolean;
  value: any;
  options?: string[];
  min_value?: number;
  max_value?: number;
  step?: number;
  placeholder?: string;
}

export interface SystemConfigCategory {
  category: string;
  label: string;
  icon: string;
  description: string;
  fields: SystemConfigField[];
}

export interface SystemConfigResponse {
  categories: SystemConfigCategory[];
  has_overrides: boolean;
  override_keys: string[];
}

export interface SystemConfigUpdateResult {
  updated_keys: string[];
  total_overrides: number;
  restart_required: boolean;
}

// ==================== Chat ====================
export interface ChatConversation {
  id: number;
  title: string;
  job_title?: string;
  domain: string;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tokens_used: number;
  created_at: string;
  metadata?: {
    candidates_found?: number[];
    chunks_used?: number;
    confidence?: number;
  };
}

export interface ChatResponse {
  message: string;
  conversation_id: number;
  message_id: number;
  candidates_found: ChatCandidate[];
  sources: ChatSource[];
  suggestions: string[];
  tokens_used: number;
  confidence: number;
}

export interface ChatCandidate {
  id: number;
  name: string;
  email?: string;
  city?: string;
  state?: string;
  relevance: number;
}

export interface ChatSource {
  chunk_id: number;
  candidate_id: number;
  candidate_name: string;
  section: string;
  relevance: number;
}

// ==================== LinkedIn ====================
export interface LinkedInSearchCriteria {
  title?: string;
  skills?: string[];
  location?: string;
  experience_years?: number;
  keywords?: string[];
  industry?: string;
}

export interface LinkedInSearchResult {
  search_id: number;
  criteria: LinkedInSearchCriteria;
  results: LinkedInMatch[];
  total_found: number;
}

export interface LinkedInMatch {
  candidate_id: number;
  name: string;
  score: number;
  match_details: string[];
  source: string;
}

// ==================== Companies ====================
export interface Company {
  id: number;
  name: string;
  cnpj?: string;
  plan: string;
  logo_url?: string;
  is_active: boolean;
  max_candidates?: number;
  max_monthly_ai_cost?: number;
  created_at: string;
  updated_at: string;
}

// ==================== Dashboard ====================
export interface DashboardStats {
  total_candidates: number;
  total_documents: number;
  recent_uploads: number;
  processed_today: number;
  candidates_by_state: { name: string; value: number }[];
  uploads_by_month: { month: string; count: number }[];
  top_skills: { skill: string; count: number }[];
}

// ==================== AI Usage ====================
export interface AIUsageLog {
  id: number;
  operation: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  user_id: number;
  company_id?: number;
  created_at: string;
}

// ==================== Audit ====================
export interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number;
  user_id: number;
  details?: Record<string, any>;
  ip_address?: string;
  created_at: string;
}

// ==================== Pagination ====================
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ==================== Health ====================
export interface HealthCheck {
  status: string;
  version: string;
  database: string;
  redis: string;
  celery: string;
  vector_db: string;
}
