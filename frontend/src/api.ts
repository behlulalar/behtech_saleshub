import type { ActionProposalItem, Activity, ActivityFormData, AiChatRequest, AiChatResponse, AiRunCreateRequest, AiRunCreateResponse, AiRunDetail, AiRunListResponse, AiStatusResponse, CompanyProfile, AnalyticsData, Category, CategoryFormData, DashboardData, DeleteAccountData, DailyContactAnalytics, DiagnosisListResponse, Employee, EmployeeFormData, FunnelData, Lead, LeadAttachment, LeadDiscoveryImportResult, LeadDiscoveryResponse, LeadFormData, LeadImportBatch, LeadImportResult, LeadRequest, LeadRequestFormData, PaginatedLeads, PlacesUsage, PrioritiesResponse, ReportData, ReportPeriod, RevenueData, Stats, SuggestMessageRequest, SuggestMessageResponse, SummarizeLeadRequest, SummarizeLeadResponse, Tag, TagFormData, UpdateProfileData, UserProfile } from './types';
import { clearSessionExpired, getToken, setToken, setUsername, clearRememberCredentials, setSavedPassword, setIdleTimeoutMinutes, setRememberPreference } from './auth';

const API_BASE = '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && path !== '/auth/login') {
    clearSessionExpired();
    window.location.reload();
    throw new Error('Oturum süresi doldu');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Bir hata oluştu' }));
    const detail = err.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg : 'Bir hata oluştu';
    throw new Error(message || 'Bir hata oluştu');
  }

  if (res.status === 204) return {} as T;
  return res.json();
}

export interface AuthResponse {
  access_token: string;
  username: string;
  role: 'owner' | 'employee';
  account_type: 'individual' | 'company';
  expires_in: number;
  idle_timeout_minutes?: number;
}

export interface PublicConfig {
  idle_timeout_minutes: number;
}

export interface RegisterResponse {
  message: string;
  requires_verification: boolean;
  email?: string;
  access_token?: string;
  username?: string;
  role?: 'owner' | 'employee';
  account_type?: 'individual' | 'company';
  expires_in?: number;
}

export const api = {
  getPublicConfig: () => request<PublicConfig>('/public/config'),

  login: (username: string, password: string, remember_me: boolean) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password, remember_me }),
    }),

  register: (
    username: string,
    email: string,
    password: string,
    password_confirm: string,
    account_type: 'individual' | 'company',
    company_name?: string,
  ) =>
    request<RegisterResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username,
        email,
        password,
        password_confirm,
        account_type,
        company_name,
      }),
    }),

  verifyEmail: (token: string) =>
    request<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),

  resendVerification: (email: string) =>
    request<{ message: string }>('/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  forgotPassword: (identifier: string) =>
    request<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ identifier }),
    }),

  resetPassword: (token: string, password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, password }),
    }),

  getMe: () => request<UserProfile>('/auth/me'),

  updateProfile: (data: UpdateProfileData) =>
    request<UserProfile>('/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteAccount: (data: DeleteAccountData) =>
    request<{ message: string }>('/auth/me', {
      method: 'DELETE',
      body: JSON.stringify(data),
    }),

  getEmployees: () => request<Employee[]>('/employees'),

  createEmployee: (data: EmployeeFormData) =>
    request<Employee>('/employees', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateEmployee: (id: number, data: { display_name: string }) =>
    request<Employee>(`/employees/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteEmployee: (id: number) =>
    request<{ message: string }>(`/employees/${id}`, { method: 'DELETE' }),

  getPendingRequestCount: () => request<{ count: number }>('/lead-requests/pending-count'),

  getLeadRequests: (status?: string) => {
    const params = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<LeadRequest[]>(`/lead-requests${params}`);
  },

  createLeadRequest: (data: LeadRequestFormData) =>
    request<LeadRequest>('/lead-requests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  approveLeadRequest: (id: number) =>
    request<Lead>(`/lead-requests/${id}/approve`, { method: 'POST' }),

  rejectLeadRequest: (id: number, rejection_note: string) =>
    request<LeadRequest>(`/lead-requests/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejection_note }),
    }),

  getDashboard: () => request<DashboardData>('/dashboard'),

  getFunnel: () => request<FunnelData>('/funnel'),

  getAnalytics: () => request<AnalyticsData>('/analytics'),

  getDailyContactAnalytics: (date?: string) => {
    const params = date ? `?date=${encodeURIComponent(date)}` : '';
    return request<DailyContactAnalytics>(`/analytics/daily-contact${params}`);
  },

  getRevenue: () => request<RevenueData>('/revenue'),

  getWeeklyReport: (date?: string) =>
    request<ReportData>(`/reports/weekly${date ? `?date=${encodeURIComponent(date)}` : ''}`),

  getMonthlyReport: (month?: string) =>
    request<ReportData>(`/reports/monthly${month ? `?month=${encodeURIComponent(month)}` : ''}`),

  exportReport: async (period: ReportPeriod, format: 'csv' | 'xlsx' | 'pdf', params?: { date?: string; month?: string }) => {
    const search = new URLSearchParams({ period, format });
    if (params?.date) search.set('date', params.date);
    if (params?.month) search.set('month', params.month);

    const token = getToken();
    const res = await fetch(`${API_BASE}/reports/export?${search}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Dışa aktarma başarısız' }));
      throw new Error(typeof err.detail === 'string' ? err.detail : 'Dışa aktarma başarısız');
    }

    const blob = await res.blob();
    const ext = format === 'xlsx' ? 'xlsx' : format;
    const filename = `behtech-${period}-rapor.${ext}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  getCategories: () => request<Category[]>('/categories'),

  createCategory: (data: CategoryFormData) =>
    request<Category>('/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateCategory: (id: string, data: Partial<CategoryFormData>) =>
    request<Category>(`/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteCategory: (id: string) =>
    request<{ message: string }>(`/categories/${id}`, { method: 'DELETE' }),

  getTags: () => request<Tag[]>('/tags'),

  createTag: (data: TagFormData) =>
    request<Tag>('/tags', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateTag: (id: string, data: Partial<TagFormData>) =>
    request<Tag>(`/tags/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteTag: (id: string) =>
    request<{ message: string }>(`/tags/${id}`, { method: 'DELETE' }),

  getLeads: (
    category: string,
    search?: string,
    durum?: string,
    tag?: string,
    oncelik?: string,
    sehir?: string,
    page = 1,
    pageSize = 50,
  ) => {
    const params = new URLSearchParams({ category, page: String(page), page_size: String(pageSize) });
    if (search) params.set('search', search);
    if (durum) params.set('durum', durum);
    if (tag) params.set('tag', tag);
    if (oncelik) params.set('oncelik', oncelik);
    if (sehir) params.set('sehir', sehir);
    return request<PaginatedLeads>(`/leads?${params}`);
  },

  getLead: (id: number) => request<Lead>(`/leads/${id}`),

  createLead: (category: string, data: LeadFormData) =>
    request<Lead>('/leads', {
      method: 'POST',
      body: JSON.stringify({ ...data, category }),
    }),

  downloadLeadImportTemplate: async () => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/leads/import/template`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }
    if (!res.ok) {
      throw new Error('Şablon indirilemedi');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'behtech-musteri-sablonu.xlsx';
    link.click();
    URL.revokeObjectURL(url);
  },

  importLeads: async (category: string, file: File) => {
    const token = getToken();
    const form = new FormData();
    form.append('category', category);
    form.append('file', file);
    const res = await fetch(`${API_BASE}/leads/import`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'İçe aktarma başarısız' }));
      const detail = err.detail;
      throw new Error(typeof detail === 'string' ? detail : 'İçe aktarma başarısız');
    }
    return res.json() as Promise<LeadImportResult>;
  },

  listLeadImportBatches: () => request<LeadImportBatch[]>('/leads/import/batches'),

  deleteLeadImportBatch: (batchId: number) =>
    request<{ deleted: number; message: string }>(`/leads/import/batches/${batchId}`, {
      method: 'DELETE',
    }),

  getLeadDiscoveryUsage: () => request<PlacesUsage>('/leads/discover/usage'),

  discoverLeads: async (payload: {
    city: string;
    district?: string;
    sector_keyword: string;
    category?: string;
    radius_meters?: number;
    confirm_over_quota?: boolean;
  }) => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/leads/discover`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    });
    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }
    if (res.status === 402) {
      const err = await res.json().catch(() => ({ detail: { message: 'Kota aşıldı' } }));
      const detail = err.detail;
      throw new Error(`QUOTA:${JSON.stringify(detail)}`);
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Tarama başarısız' }));
      const detail = err.detail;
      throw new Error(typeof detail === 'string' ? detail : detail?.message || 'Tarama başarısız');
    }
    return res.json() as Promise<LeadDiscoveryResponse>;
  },

  importDiscoveredLeads: (payload: {
    category: string;
    city: string;
    places: Array<{
      google_place_id: string;
      business_name: string;
      phone_number?: string;
      address?: string;
      rating?: number | null;
      rating_count?: number | null;
      latitude?: number | null;
      longitude?: number | null;
      low_digital_presence?: boolean;
    }>;
  }) =>
    request<LeadDiscoveryImportResult>('/leads/discover/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateLead: (id: number, data: LeadFormData) =>
    request<Lead>(`/leads/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteLead: (id: number) =>
    request<{ message: string }>(`/leads/${id}`, { method: 'DELETE' }),

  getStats: (category: string) => request<Stats>(`/stats/${category}`),

  getActivities: (leadId: number) => request<Activity[]>(`/leads/${leadId}/activities`),

  createActivity: (leadId: number, data: ActivityFormData) =>
    request<Activity>(`/leads/${leadId}/activities`, {
      method: 'POST',
      body: JSON.stringify({
        activity_type: data.activity_type,
        description: data.description,
        activity_date: data.activity_date ? new Date(data.activity_date).toISOString() : undefined,
      }),
    }),

  updateActivity: (leadId: number, activityId: number, data: ActivityFormData) =>
    request<Activity>(`/leads/${leadId}/activities/${activityId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        activity_type: data.activity_type,
        description: data.description,
        activity_date: data.activity_date ? new Date(data.activity_date).toISOString() : undefined,
      }),
    }),

  getLeadAttachments: (leadId: number, status: 'active' | 'archived' | 'all' = 'active') =>
    request<LeadAttachment[]>(`/leads/${leadId}/attachments?status=${status}`),

  uploadLeadAttachment: async (
    leadId: number,
    file: File,
    options?: { label?: string; replaceAttachmentId?: number },
  ) => {
    const token = getToken();
    const formData = new FormData();
    formData.append('file', file);
    if (options?.label?.trim()) {
      formData.append('label', options.label.trim());
    }
    if (options?.replaceAttachmentId) {
      formData.append('replace_attachment_id', String(options.replaceAttachmentId));
    }

    const res = await fetch(`${API_BASE}/leads/${leadId}/attachments`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Dosya yüklenemedi' }));
      const detail = err.detail;
      const message = typeof detail === 'string' ? detail : 'Dosya yüklenemedi';
      throw new Error(message);
    }

    return res.json() as Promise<LeadAttachment>;
  },

  archiveLeadAttachment: (leadId: number, attachmentId: number) =>
    request<LeadAttachment>(`/leads/${leadId}/attachments/${attachmentId}/archive`, {
      method: 'POST',
    }),

  downloadLeadAttachment: async (leadId: number, attachmentId: number, filename: string) => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/leads/${leadId}/attachments/${attachmentId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'İndirme başarısız' }));
      throw new Error(typeof err.detail === 'string' ? err.detail : 'İndirme başarısız');
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  updateLeadAttachmentLabel: (leadId: number, attachmentId: number, label: string) =>
    request<LeadAttachment>(`/leads/${leadId}/attachments/${attachmentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ label }),
    }),

  deleteLeadAttachment: (leadId: number, attachmentId: number) =>
    request<{ message: string }>(`/leads/${leadId}/attachments/${attachmentId}`, {
      method: 'DELETE',
    }),

  getAiStatus: () => request<AiStatusResponse>('/ai/status'),

  suggestMessage: (body: SuggestMessageRequest) =>
    request<SuggestMessageResponse>('/ai/suggest-message', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  summarizeLead: (body: SummarizeLeadRequest) =>
    request<SummarizeLeadResponse>('/ai/summarize-lead', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getPriorities: (limit = 10, refresh = false) =>
    request<PrioritiesResponse>('/ai/priorities', {
      method: 'POST',
      body: JSON.stringify({ limit, refresh }),
    }),

  createAiRun: (body: AiRunCreateRequest) =>
    request<AiRunCreateResponse>('/ai/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getAiRun: (runId: number) => request<AiRunDetail>(`/ai/runs/${runId}`),

  listAiRuns: (limit = 10) => request<AiRunListResponse>(`/ai/runs?limit=${limit}`),

  listActionProposals: (status: 'pending' | 'approved' | 'rejected' | 'all' = 'pending') =>
    request<{ items: ActionProposalItem[] }>(
      `/intelligence/action-proposals?status=${status}&limit=30`,
    ),

  createActionProposal: (leadId: number) =>
    request<ActionProposalItem>('/intelligence/action-proposals', {
      method: 'POST',
      body: JSON.stringify({ lead_id: leadId }),
    }),

  resolveActionProposal: (proposalId: number, approve: boolean) =>
    request<ActionProposalItem>(`/intelligence/action-proposals/${proposalId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ approve }),
    }),

  getCompanyProfile: (refresh = false) =>
    request<CompanyProfile>(`/intelligence/company-profile?refresh=${refresh ? 'true' : 'false'}`),

  listDiagnoses: (period = 'monthly') =>
    request<DiagnosisListResponse>(`/intelligence/diagnoses?period=${period}`),

  sendAiChat: (body: AiChatRequest) =>
    request<AiChatResponse>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  streamAiChat: async (
    body: AiChatRequest,
    onDelta: (chunk: string) => void,
  ): Promise<AiChatResponse> => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/ai/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });

    if (res.status === 401) {
      clearSessionExpired();
      window.location.reload();
      throw new Error('Oturum süresi doldu');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Bir hata oluştu' }));
      const detail = err.detail;
      const message =
        typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg : 'Bir hata oluştu';
      throw new Error(message || 'Bir hata oluştu');
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error('Akış desteklenmiyor');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let reply = '';
    let run_id = 0;
    let disclaimer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep = buffer.indexOf('\n\n');
      while (sep >= 0) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of block.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const payload = JSON.parse(line.slice(6)) as {
            type: string;
            content?: string;
            run_id?: number;
            disclaimer?: string;
            detail?: string;
          };
          if (payload.type === 'delta' && payload.content) {
            reply += payload.content;
            onDelta(payload.content);
          } else if (payload.type === 'done') {
            run_id = payload.run_id ?? 0;
            disclaimer = payload.disclaimer ?? '';
          } else if (payload.type === 'error') {
            throw new Error(payload.detail || 'Yanıt alınamadı');
          }
        }
        sep = buffer.indexOf('\n\n');
      }
    }

    return { reply, run_id, disclaimer };
  },
};

export function saveAuth(response: AuthResponse, remember: boolean, password?: string) {
  setRememberPreference(remember);
  setToken(response.access_token, remember);
  if (response.idle_timeout_minutes) {
    setIdleTimeoutMinutes(response.idle_timeout_minutes);
  }
  if (remember) {
    setUsername(response.username);
    if (password) setSavedPassword(password);
  } else {
    clearRememberCredentials();
  }
}
