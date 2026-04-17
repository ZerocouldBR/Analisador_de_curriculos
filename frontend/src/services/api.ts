import axios, { AxiosInstance } from 'axios';
import {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
  Candidate,
  Document,
  SearchResult,
  SearchFilters,
  Role,
  ServerSettings,
  ChatConversation,
  ChatMessage,
  ChatResponse,
  LinkedInSearchCriteria,
  LinkedInSearchResult,
  Company,
  Experience,
  CandidateProfile,
  HealthCheck,
  SystemConfigResponse,
  SystemConfigUpdateResult,
  EnrichedResumeProfile,
  CareerAdvisoryResponse,
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
      timeout: 30000,
    });

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

    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // ==================== Auth ====================
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const formData = new FormData();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);

    const response = await this.api.post<LoginResponse>('/v1/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    localStorage.setItem('access_token', response.data.access_token);
    if (response.data.refresh_token) {
      localStorage.setItem('refresh_token', response.data.refresh_token);
    }

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

  async refreshToken(): Promise<LoginResponse> {
    const refreshToken = localStorage.getItem('refresh_token');
    const response = await this.api.post<LoginResponse>('/v1/auth/refresh', {
      refresh_token: refreshToken,
    });
    localStorage.setItem('access_token', response.data.access_token);
    return response.data;
  }

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
  }

  // ==================== Candidates ====================
  async getCandidates(city?: string, state?: string): Promise<Candidate[]> {
    const params: Record<string, string> = {};
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

  async getCandidateExperiences(candidateId: number): Promise<Experience[]> {
    const response = await this.api.get<Experience[]>(`/v1/candidates/${candidateId}/experiences`);
    return response.data;
  }

  async getCandidateProfiles(candidateId: number): Promise<CandidateProfile[]> {
    const response = await this.api.get<CandidateProfile[]>(`/v1/candidates/${candidateId}/profiles`);
    return response.data;
  }

  async getEnrichedProfile(candidateId: number): Promise<EnrichedResumeProfile> {
    const response = await this.api.get<EnrichedResumeProfile>(`/v1/candidates/${candidateId}/enriched-profile`);
    return response.data;
  }

  async getCareerAdvisory(candidateId: number): Promise<CareerAdvisoryResponse> {
    const response = await this.api.post<CareerAdvisoryResponse>(`/v1/candidates/${candidateId}/career-advisory`);
    return response.data;
  }

  // ==================== Documents ====================
  async uploadDocument(file: File, candidateId?: number): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);

    const params = candidateId ? { candidate_id: candidateId } : {};

    const response = await this.api.post<Document>('/v1/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
      timeout: 120000,
    });

    return response.data;
  }

  async reprocessDocument(documentId: number): Promise<void> {
    await this.api.post(`/v1/documents/${documentId}/reprocess`);
  }

  async bulkUploadDocuments(files: File[], candidateId?: number): Promise<any> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const params: Record<string, any> = {};
    if (candidateId) params.candidate_id = candidateId;

    const response = await this.api.post('/v1/documents/bulk-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
      timeout: 600000, // 10 min for bulk
    });

    return response.data;
  }

  async getDocumentStatus(documentId: number): Promise<{
    id: number;
    processing_status: string;
    processing_progress: number;
    processing_message: string | null;
    processing_error: string | null;
  }> {
    const response = await this.api.get(`/v1/documents/${documentId}/status`);
    return response.data;
  }

  async getBatchDocumentStatus(documentIds: number[]): Promise<Array<{
    id: number;
    processing_status: string;
    processing_progress: number;
    processing_message: string | null;
    processing_error: string | null;
  }>> {
    const response = await this.api.post('/v1/documents/batch-status', documentIds);
    return response.data;
  }

  async deleteDocument(documentId: number): Promise<void> {
    await this.api.delete(`/v1/candidates/documents/${documentId}`);
  }

  // ==================== Admin ====================
  async getDatabaseStats(): Promise<any> {
    const response = await this.api.get('/v1/admin/stats');
    return response.data;
  }

  async cleanupDatabase(options: {
    delete_candidates?: boolean;
    delete_documents?: boolean;
    delete_chunks?: boolean;
    delete_experiences?: boolean;
    delete_chat_history?: boolean;
    delete_audit_logs?: boolean;
    reset_sequences?: boolean;
    confirm: string;
  }): Promise<any> {
    const response = await this.api.post('/v1/admin/cleanup', options, {
      timeout: 120000,
    });
    return response.data;
  }

  async deleteCandidatesBatch(candidateIds: number[]): Promise<any> {
    const response = await this.api.post('/v1/admin/delete-candidates', {
      candidate_ids: candidateIds,
      confirm: true,
    });
    return response.data;
  }

  // ==================== Search ====================
  async semanticSearch(query: string, limit: number = 10): Promise<SearchResult[]> {
    const response = await this.api.post<SearchResult[]>('/v1/search/semantic', {
      query,
      limit,
    });
    return response.data;
  }

  async hybridSearch(query: string, filters?: SearchFilters, limit: number = 10): Promise<SearchResult[]> {
    const response = await this.api.post<SearchResult[]>('/v1/search/hybrid', {
      query,
      filters,
      limit,
    });
    return response.data;
  }

  async jobAnalysisSearch(jobDescription: string, jobTitle?: string, limit: number = 10): Promise<SearchResult[]> {
    const response = await this.api.post<SearchResult[]>('/v1/chat/quick-analyze', {
      job_description: jobDescription,
      job_title: jobTitle,
      limit,
    }, { timeout: 120000 });
    return response.data;
  }

  async getKeywords(text: string): Promise<any> {
    const response = await this.api.post('/v1/search/keywords/extract', { text });
    return response.data;
  }

  // ==================== Roles ====================
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

  // ==================== Settings ====================
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

  async getChatPrompts(): Promise<any> {
    const response = await this.api.get('/v1/settings/prompts/chat');
    return response.data;
  }

  async updateChatPrompts(prompts: any): Promise<any> {
    const response = await this.api.put('/v1/settings/prompts/chat', prompts);
    return response.data;
  }

  async resetChatPrompts(): Promise<any> {
    const response = await this.api.post('/v1/settings/prompts/chat/reset');
    return response.data;
  }

  // ==================== System Config ====================
  async getSystemConfig(): Promise<SystemConfigResponse> {
    const response = await this.api.get<SystemConfigResponse>('/v1/settings/system/config');
    return response.data;
  }

  async updateSystemConfig(values: Record<string, any>): Promise<SystemConfigUpdateResult> {
    const response = await this.api.put<SystemConfigUpdateResult>('/v1/settings/system/config', {
      values,
    });
    return response.data;
  }

  async resetSystemConfig(): Promise<any> {
    const response = await this.api.post('/v1/settings/system/config/reset');
    return response.data;
  }

  // ==================== Chat ====================
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
      { message, candidate_ids: candidateIds },
      { timeout: 120000 }
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
      { job_description: jobDescription, job_title: jobTitle, limit },
      { timeout: 120000 }
    );
    return response.data;
  }

  async quickAnalyze(
    jobDescription: string,
    jobTitle: string = '',
    limit: number = 10
  ): Promise<ChatResponse> {
    const response = await this.api.post<ChatResponse>(
      '/v1/chat/quick-analyze',
      { job_description: jobDescription, job_title: jobTitle, limit },
      { timeout: 120000 }
    );
    return response.data;
  }

  // ==================== LinkedIn ====================
  async linkedInExtract(profileUrl: string): Promise<any> {
    const response = await this.api.post('/v1/linkedin/extract', { profile_url: profileUrl });
    return response.data;
  }

  async linkedInManualEnrich(candidateId: number, data: any): Promise<any> {
    const response = await this.api.post(`/v1/linkedin/candidates/${candidateId}/manual`, data);
    return response.data;
  }

  async getLinkedInData(candidateId: number): Promise<any> {
    const response = await this.api.get(`/v1/linkedin/candidates/${candidateId}/linkedin`);
    return response.data;
  }

  async syncLinkedIn(candidateId: number): Promise<any> {
    const response = await this.api.put(`/v1/linkedin/candidates/${candidateId}/sync-from-linkedin`);
    return response.data;
  }

  async getLinkedInConfigStatus(): Promise<any> {
    const response = await this.api.get('/v1/linkedin/config-status');
    return response.data;
  }

  async getLinkedInGuide(): Promise<any> {
    const response = await this.api.get('/v1/linkedin/guide');
    return response.data;
  }

  // ==================== Companies ====================
  async getMyCompany(): Promise<Company> {
    const response = await this.api.get<Company>('/v1/companies/me');
    return response.data;
  }

  async updateMyCompany(data: Partial<Company>): Promise<Company> {
    const response = await this.api.put<Company>('/v1/companies/me', data);
    return response.data;
  }

  async getCompanies(): Promise<Company[]> {
    const response = await this.api.get<Company[]>('/v1/companies/');
    return response.data;
  }

  async createCompany(data: Partial<Company>): Promise<Company> {
    const response = await this.api.post<Company>('/v1/companies/', data);
    return response.data;
  }

  async updateCompany(id: number, data: Partial<Company>): Promise<Company> {
    const response = await this.api.put<Company>(`/v1/companies/${id}`, data);
    return response.data;
  }

  async deleteCompany(id: number): Promise<void> {
    await this.api.delete(`/v1/companies/${id}`);
  }

  async uploadCompanyLogo(companyId: number, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await this.api.post(`/v1/companies/${companyId}/logo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async deleteCompanyLogo(companyId: number): Promise<void> {
    await this.api.delete(`/v1/companies/${companyId}/logo`);
  }

  getCompanyLogoUrl(companyId: number): string {
    return `${this.api.defaults.baseURL}/v1/companies/${companyId}/logo`;
  }

  getCandidatePhotoUrl(candidateId: number): string {
    return `${this.api.defaults.baseURL}/v1/candidates/${candidateId}/photo`;
  }

  // ==================== VectorDB ====================
  async refreshEmbeddings(): Promise<any> {
    const response = await this.api.post('/v1/vectordb/initialize', {}, { timeout: 300000 });
    return response.data;
  }

  async getVectorDBStatus(): Promise<any> {
    const response = await this.api.get('/v1/vectordb/health');
    return response.data;
  }

  async testVectorDBConnection(provider: string): Promise<any> {
    const response = await this.api.post(`/v1/vectordb/test-connection/${provider}`, {}, { timeout: 15000 });
    return response.data;
  }

  async getVectorDBProviders(): Promise<any> {
    const response = await this.api.get('/v1/vectordb/providers');
    return response.data;
  }

  async setupPgvector(): Promise<any> {
    const response = await this.api.post('/v1/vectordb/setup-pgvector', {}, { timeout: 120000 });
    return response.data;
  }

  async listIndexes(tableName?: string): Promise<any> {
    const params = tableName ? { table_name: tableName } : {};
    const response = await this.api.get('/v1/vectordb/indexes', { params });
    return response.data;
  }

  async createIndex(data: {
    table_name: string;
    column_name: string;
    index_type: string;
    distance_ops?: string;
    index_name?: string;
    hnsw_m?: number;
    hnsw_ef_construction?: number;
  }): Promise<any> {
    const response = await this.api.post('/v1/vectordb/indexes', data, { timeout: 120000 });
    return response.data;
  }

  async deleteIndex(indexName: string): Promise<any> {
    const response = await this.api.delete(`/v1/vectordb/indexes/${indexName}`);
    return response.data;
  }

  // ==================== Health ====================
  async healthCheck(): Promise<HealthCheck> {
    const response = await this.api.get<HealthCheck>('/health');
    return response.data;
  }

  // ==================== Sourcing ====================
  async getSourcingProviders(): Promise<any> {
    const response = await this.api.get('/v1/sourcing/providers');
    return response.data;
  }

  async getProviderStatus(name: string): Promise<any> {
    const response = await this.api.get(`/v1/sourcing/providers/${name}/status`);
    return response.data;
  }

  async upsertProviderConfig(data: any): Promise<any> {
    const response = await this.api.post('/v1/sourcing/providers/config', data);
    return response.data;
  }

  async testProvider(name: string): Promise<any> {
    const response = await this.api.post(`/v1/sourcing/providers/${name}/test`);
    return response.data;
  }

  async triggerSync(name: string, criteria?: any): Promise<any> {
    const response = await this.api.post(`/v1/sourcing/providers/${name}/sync`, criteria ? { criteria } : {});
    return response.data;
  }

  async getSyncRuns(providerName?: string, limit?: number): Promise<any> {
    const response = await this.api.get('/v1/sourcing/runs', { params: { provider_name: providerName, limit } });
    return response.data;
  }

  async getSyncRunDetail(runId: number): Promise<any> {
    const response = await this.api.get(`/v1/sourcing/runs/${runId}`);
    return response.data;
  }

  async getCandidateSources(candidateId: number): Promise<any> {
    const response = await this.api.get(`/v1/sourcing/candidates/${candidateId}/sources`);
    return response.data;
  }

  async getCandidateSnapshots(candidateId: number): Promise<any> {
    const response = await this.api.get(`/v1/sourcing/candidates/${candidateId}/snapshots`);
    return response.data;
  }

  async getSnapshotDiff(candidateId: number, fromId: number, toId: number): Promise<any> {
    const response = await this.api.get(`/v1/sourcing/candidates/${candidateId}/snapshots/diff`, { params: { from_id: fromId, to_id: toId } });
    return response.data;
  }

  async getMergeSuggestions(limit?: number): Promise<any> {
    const response = await this.api.get('/v1/sourcing/merge-suggestions', { params: { limit } });
    return response.data;
  }

  async executeMerge(primaryId: number, secondaryId: number): Promise<any> {
    const response = await this.api.post('/v1/sourcing/merge', { primary_candidate_id: primaryId, secondary_candidate_id: secondaryId });
    return response.data;
  }

  // ==================== Diagnostics ====================
  async runFullDiagnostics(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/full', { timeout: 60000 });
    return response.data;
  }

  async testDatabaseConnection(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/test/database', { timeout: 15000 });
    return response.data;
  }

  async testRedisConnection(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/test/redis', { timeout: 15000 });
    return response.data;
  }

  async testOpenAIConnection(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/test/openai', { timeout: 30000 });
    return response.data;
  }

  async testVectorStoreConnection(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/test/vectorstore', { timeout: 15000 });
    return response.data;
  }

  async testCeleryConnection(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/test/celery', { timeout: 15000 });
    return response.data;
  }

  async testEmbeddingPipeline(): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/test/embedding', { timeout: 30000 });
    return response.data;
  }

  async getRecentLogs(lines: number = 100, level: string = 'all'): Promise<any> {
    const response = await this.api.get('/v1/diagnostics/logs', { params: { lines, level } });
    return response.data;
  }

  // ==================== Batch Import ====================
  async scanFolder(data: { folder_path: string; recursive?: boolean; extensions?: string[] }): Promise<any> {
    const response = await this.api.post('/v1/batch-import/scan', data, { timeout: 60000 });
    return response.data;
  }

  async batchImport(data: {
    folder_path: string;
    recursive?: boolean;
    extensions?: string[];
    skip_duplicates?: boolean;
    candidate_id?: number;
  }): Promise<any> {
    const response = await this.api.post('/v1/batch-import/import', data, { timeout: 300000 });
    return response.data;
  }

  async validateFolderPath(folder_path: string): Promise<any> {
    const response = await this.api.post('/v1/batch-import/validate-path', { folder_path });
    return response.data;
  }

  async getImportHistory(limit: number = 20): Promise<any> {
    const response = await this.api.get('/v1/batch-import/history', { params: { limit } });
    return response.data;
  }
}

export const apiService = new ApiService();
