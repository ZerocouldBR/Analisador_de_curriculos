import axios, { AxiosInstance } from 'axios';
import {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
  Candidate,
  Document,
  SearchResult,
  Role,
  ServerSettings,
  ChatConversation,
  ChatMessage,
  ChatResponse,
  LinkedInSearchCriteria,
  LinkedInSearchResult,
} from '../types';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: `${API_URL}/api`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const formData = new FormData();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);

    const response = await this.api.post<LoginResponse>('/v1/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Save token
    localStorage.setItem('access_token', response.data.access_token);

    return response.data;
  }

  async register(data: RegisterRequest): Promise<User> {
    const response = await this.api.post<User>('/v1/auth/register', data);
    return response.data;
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.api.get<User>('/v1/auth/me');
    return response.data;
  }

  async changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await this.api.post('/v1/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  }

  logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  }

  // Candidate endpoints
  async getCandidates(city?: string, state?: string): Promise<Candidate[]> {
    const params: any = {};
    if (city) params.city = city;
    if (state) params.state = state;

    const response = await this.api.get<Candidate[]>('/v1/candidates/', { params });
    return response.data;
  }

  async getCandidate(id: number): Promise<Candidate> {
    const response = await this.api.get<Candidate>(`/v1/candidates/${id}`);
    return response.data;
  }

  async createCandidate(data: Partial<Candidate>): Promise<Candidate> {
    const response = await this.api.post<Candidate>('/v1/candidates/', data);
    return response.data;
  }

  async updateCandidate(id: number, data: Partial<Candidate>): Promise<Candidate> {
    const response = await this.api.put<Candidate>(`/v1/candidates/${id}`, data);
    return response.data;
  }

  async deleteCandidate(id: number): Promise<void> {
    await this.api.delete(`/v1/candidates/${id}`);
  }

  async getCandidateDocuments(candidateId: number): Promise<Document[]> {
    const response = await this.api.get<Document[]>(`/v1/candidates/${candidateId}/documents`);
    return response.data;
  }

  // Document endpoints
  async uploadDocument(file: File, candidateId?: number): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);

    const params = candidateId ? { candidate_id: candidateId } : {};

    const response = await this.api.post<Document>('/v1/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      params,
    });

    return response.data;
  }

  async reprocessDocument(documentId: number): Promise<void> {
    await this.api.post(`/v1/documents/${documentId}/reprocess`);
  }

  async deleteDocument(documentId: number): Promise<void> {
    await this.api.delete(`/v1/candidates/documents/${documentId}`);
  }

  // Search endpoints
  async semanticSearch(query: string, topK: number = 10): Promise<SearchResult[]> {
    const response = await this.api.post<SearchResult[]>('/v1/search/semantic', {
      query,
      top_k: topK,
    });
    return response.data;
  }

  async hybridSearch(query: string, filters?: any, topK: number = 10): Promise<SearchResult[]> {
    const response = await this.api.post<SearchResult[]>('/v1/search/hybrid', {
      query,
      filters,
      top_k: topK,
    });
    return response.data;
  }

  async searchBySkill(skill: string): Promise<Candidate[]> {
    const response = await this.api.get<Candidate[]>('/v1/search/candidates/by-skill', {
      params: { skill },
    });
    return response.data;
  }

  // Role endpoints
  async getRoles(): Promise<Role[]> {
    const response = await this.api.get<Role[]>('/v1/auth/roles');
    return response.data;
  }

  async createRole(data: Partial<Role>): Promise<Role> {
    const response = await this.api.post<Role>('/v1/auth/roles', data);
    return response.data;
  }

  async updateRole(id: number, data: Partial<Role>): Promise<Role> {
    const response = await this.api.put<Role>(`/v1/auth/roles/${id}`, data);
    return response.data;
  }

  async assignRole(userId: number, roleName: string): Promise<void> {
    await this.api.post(`/v1/auth/users/${userId}/roles/${roleName}`);
  }

  async removeRole(userId: number, roleName: string): Promise<void> {
    await this.api.delete(`/v1/auth/users/${userId}/roles/${roleName}`);
  }

  // Settings endpoints
  async getSettings(): Promise<ServerSettings[]> {
    const response = await this.api.get<ServerSettings[]>('/v1/settings/');
    return response.data;
  }

  async getSetting(key: string): Promise<ServerSettings> {
    const response = await this.api.get<ServerSettings>(`/v1/settings/${key}`);
    return response.data;
  }

  async updateSetting(key: string, value: any): Promise<ServerSettings> {
    const response = await this.api.put<ServerSettings>(`/v1/settings/${key}`, {
      value_json: value,
    });
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<any> {
    const response = await this.api.get('/health');
    return response.data;
  }

  // Chat endpoints
  async createConversation(data: {
    title?: string;
    job_description?: string;
    job_title?: string;
    domain?: string;
  }): Promise<ChatConversation> {
    const response = await this.api.post<ChatConversation>('/v1/chat/conversations', data);
    return response.data;
  }

  async getConversations(status: string = 'active'): Promise<ChatConversation[]> {
    const response = await this.api.get<ChatConversation[]>('/v1/chat/conversations', {
      params: { status_filter: status },
    });
    return response.data;
  }

  async getConversation(id: number): Promise<ChatConversation> {
    const response = await this.api.get<ChatConversation>(`/v1/chat/conversations/${id}`);
    return response.data;
  }

  async archiveConversation(id: number): Promise<void> {
    await this.api.delete(`/v1/chat/conversations/${id}`);
  }

  async getMessages(conversationId: number): Promise<ChatMessage[]> {
    const response = await this.api.get<ChatMessage[]>(
      `/v1/chat/conversations/${conversationId}/messages`
    );
    return response.data;
  }

  async sendMessage(
    conversationId: number,
    message: string,
    candidateIds?: number[]
  ): Promise<ChatResponse> {
    const response = await this.api.post<ChatResponse>(
      `/v1/chat/conversations/${conversationId}/messages`,
      { message, candidate_ids: candidateIds }
    );
    return response.data;
  }

  async analyzeJob(
    conversationId: number,
    jobDescription: string,
    jobTitle: string = '',
    limit: number = 10
  ): Promise<ChatResponse> {
    const response = await this.api.post<ChatResponse>(
      `/v1/chat/conversations/${conversationId}/analyze-job`,
      { job_description: jobDescription, job_title: jobTitle, limit }
    );
    return response.data;
  }

  async quickAnalyze(
    jobDescription: string,
    jobTitle: string = '',
    limit: number = 10
  ): Promise<ChatResponse> {
    const response = await this.api.post<ChatResponse>('/v1/chat/quick-analyze', {
      job_description: jobDescription,
      job_title: jobTitle,
      limit,
    });
    return response.data;
  }

  // LinkedIn search endpoints
  async searchProfessionals(criteria: LinkedInSearchCriteria): Promise<LinkedInSearchResult> {
    const response = await this.api.post<LinkedInSearchResult>('/v1/linkedin/search', criteria);
    return response.data;
  }

  async getSearchHistory(limit: number = 20): Promise<any[]> {
    const response = await this.api.get('/v1/linkedin/search/history', {
      params: { limit },
    });
    return response.data;
  }
}

export const apiService = new ApiService();
