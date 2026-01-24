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
