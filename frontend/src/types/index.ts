// API Types
export interface User {
  id: number;
  email: string;
  name: string;
  status: string;
  is_superuser: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

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
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: number;
  candidate_id: number;
  original_filename: string;
  mime_type: string;
  source_path: string;
  sha256_hash: string;
  uploaded_at: string;
}

export interface SearchResult {
  candidate_id: number;
  candidate_name: string;
  score: number;
  matched_chunks: Array<{
    section: string;
    content: string;
    similarity: number;
  }>;
}

export interface WebSocketMessage {
  type: string;
  document_id?: number;
  status?: string;
  progress?: number;
  message?: string;
}

export interface Role {
  id: number;
  name: string;
  description?: string;
  permissions: Record<string, boolean>;
}

export interface ServerSettings {
  id: number;
  key: string;
  value_json: any;
  description?: string;
  version: number;
  updated_at: string;
}

// Chat types
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
  candidates_found: Array<{
    id: number;
    name: string;
    email?: string;
    city?: string;
    state?: string;
    relevance: number;
  }>;
  sources: Array<{
    chunk_id: number;
    candidate_id: number;
    candidate_name: string;
    section: string;
    relevance: number;
  }>;
  suggestions: string[];
  tokens_used: number;
  confidence: number;
}

// LinkedIn search types
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
  results: Array<{
    candidate_id: number;
    name: string;
    score: number;
    match_details: string[];
    source: string;
  }>;
  total_found: number;
}
