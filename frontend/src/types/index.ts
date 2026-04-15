// ==================== Auth ====================
export interface User {
  id: number;
  email: string;
  name: string;
  status: string;
  is_superuser: boolean;
  company_id?: number;
  company_name?: string;
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
  company_name?: string;
  company_cnpj?: string;
  company_phone?: string;
  company_id?: number;
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
  group?: string;
}

export interface SystemConfigGroup {
  key: string;
  label: string;
  description: string;
}

export interface SystemConfigCategory {
  category: string;
  label: string;
  icon: string;
  description: string;
  fields: SystemConfigField[];
  groups?: SystemConfigGroup[];
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
  slug?: string;
  cnpj?: string;
  email?: string;
  phone?: string;
  address?: string;
  city?: string;
  state?: string;
  website?: string;
  plan: string;
  logo_url?: string;
  is_active: boolean;
  settings_json?: Record<string, any>;
  user_count?: number;
  candidate_count?: number;
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

// ==================== Sourcing ====================
export interface SourcingProvider {
  name: string;
  type: string;
  is_configured: boolean;
  is_enabled: boolean;
  last_sync_at: string | null;
}

export interface ProviderConfig {
  id: number;
  provider_name: string;
  is_enabled: boolean;
  schedule_cron: string | null;
  rate_limit_rpm: number;
  rate_limit_daily: number;
  config_keys: string[];
  created_at: string;
  updated_at: string;
}

export interface ProviderStatus {
  provider_name: string;
  healthy: boolean;
  message: string;
  remaining_quota: number | null;
}

export interface SyncRun {
  id: number;
  provider_name: string;
  run_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  total_scanned: number;
  total_created: number;
  total_updated: number;
  total_unchanged: number;
  total_failed: number;
  error_detail: string | null;
}

export interface CandidateSource {
  id: number;
  provider_name: string;
  provider_type: string;
  external_id: string | null;
  external_url: string | null;
  sync_enabled: boolean;
  consent_status: string;
  source_priority: number;
  source_confidence: number;
  last_sync_at: string | null;
  last_status: string | null;
  created_at: string;
}

export interface SnapshotSummary {
  id: number;
  snapshot_hash: string;
  source_id: number | null;
  created_at: string;
}

export interface SnapshotDiff {
  changed_fields: Record<string, { from: any; to: any }>;
  diff_summary: string;
}

export interface MergeSuggestion {
  candidate_id_a: number;
  candidate_id_b: number;
  name_a: string;
  name_b: string;
  similarity_score: number;
  matched_fields: string[];
}

// ==================== Enriched Resume ====================
export interface EnrichedPersonalInfo {
  name?: string;
  name_confidence?: number;
  name_source?: string;
  email?: string;
  email_confidence?: number;
  phone?: string;
  phone_confidence?: number;
  location?: string;
  location_confidence?: number;
  full_address?: string;
  linkedin?: string;
  github?: string;
  portfolio?: string;
  cpf?: string;
  rg?: string;
  birth_date?: string;
}

export interface ProfessionalObjective {
  title?: string;
  summary?: string;
  confidence?: number;
}

export interface EnrichedExperience {
  company?: string;
  title?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  description?: string;
  achievements?: string[];
}

export interface EnrichedEducation {
  institution?: string;
  degree?: string;
  field?: string;
  start_year?: string;
  end_year?: string;
  status?: string;
}

export interface CategorizedSkills {
  technical?: string[];
  soft?: string[];
  tools?: string[];
  frameworks?: string[];
}

export interface EnrichedCertification {
  name?: string;
  institution?: string;
  year?: string;
  code?: string;
}

export interface ValidationAlert {
  field: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  message: string;
  suggestion?: string;
}

export interface ValidationResult {
  overall_confidence?: number;
  quality_label?: string;
  field_confidence?: Record<string, number>;
  alerts?: ValidationAlert[];
  alerts_count?: number;
  fields_extracted?: number;
  total_fields?: number;
}

export interface EnrichedResumeProfile {
  candidate_id: number;
  extraction_method: string;
  ai_enhanced: boolean;
  personal_info: EnrichedPersonalInfo;
  professional_objective: ProfessionalObjective;
  experiences: EnrichedExperience[];
  education: EnrichedEducation[];
  skills: CategorizedSkills;
  languages: { language: string; level: string }[];
  certifications: EnrichedCertification[];
  licenses: { type: string; category?: string; description?: string }[];
  additional_info: Record<string, any>;
  validation: ValidationResult;
  metadata: Record<string, any>;
}

export interface CareerAdvisoryData {
  overall_score?: number;
  score_breakdown?: Record<string, number>;
  strengths?: { point: string; impact: string }[];
  weaknesses?: { point: string; suggestion: string; priority: string }[];
  suggested_summary?: string;
  suggested_keywords?: string[];
  presentation_gaps?: { gap: string; importance: string }[];
  hr_recommendations?: { recommendation: string; context: string }[];
  candidate_tips?: { tip: string; category: string }[];
  suitable_areas?: { area: string; fit_score: number; reasoning: string }[];
  improvement_priority?: string[];
  quick_tips?: { tip: string; category: string; priority: string }[];
}

export interface CareerAdvisoryResponse {
  candidate_id: number;
  available: boolean;
  advisory?: CareerAdvisoryData;
  quick_tips?: { tip: string; category: string; priority: string }[];
  error?: string;
}
