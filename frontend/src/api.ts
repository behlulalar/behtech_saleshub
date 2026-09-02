import type { ActionProposalItem, Activity, ActivityFormData, AiActionExecuteResponse, AiActionItem, AiActionListResponse, AiChatRequest, AiChatResponse, AiRunCreateRequest, AiRunCreateResponse, AiRunDetail, AiRunListResponse, AiStatusResponse, AssistantConversation, AssistantConversationDetailResponse, AssistantConversationListResponse, CompanyProfile, AnalyticsData, Category, CategoryFormData, DashboardData, DeleteAccountData, DailyContactAnalytics, DiagnosisHistoryInterpretRequest, DiagnosisHistoryInterpretResponse, DiagnosisHistoryResponse, DiagnosisInterpretRequest, DiagnosisInterpretResponse, DiagnosisListResponse, DiagnosisSyncResponse, Employee, EmployeeFormData, FunnelData, Lead, LeadAttachment, LeadDiscoveryImportResult, LeadDiscoveryResponse, LeadFormData, LeadImportBatch, LeadImportResult, LeadRequest, LeadRequestFormData, PaginatedLeads, PlacesUsage, PrioritiesResponse, ReportData, ReportPeriod, RevenueData, Stats, SuggestMessageRequest, SuggestMessageResponse, SummarizeLeadRequest, SummarizeLeadResponse, Tag, TagFormData, UpdateProfileData, UserProfile } from './types';
import { clearSessionExpired, getToken, setIdleTimeoutMinutes, setRememberPreference, setToken } from './auth';

const API_BASE = '/api';

let refreshPromise: Promise<boolean> | null = null;

async function fetchWithCredentials(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    },
  });
}

async function tryRefreshAccessToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetchWithCredentials('/auth/refresh', { method: 'POST' });
      if (!res.ok) return false;
      const data = (await res.json()) as AuthResponse;
      setRememberPreference(true);
      setToken(data.access_token, true);
      if (data.idle_timeout_minutes) {
        setIdleTimeoutMinutes(data.idle_timeout_minutes);
      }
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

async function request<T>(path: string, options: RequestInit = {}, retried = false): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });

  if (
    res.status === 401
    && !retried
    && path !== '/auth/login'
    && path !== '/auth/refresh'
  ) {
    const refreshed = await tryRefreshAccessToken();
    if (refreshed) {
      return request<T>(path, options, true);
    }
    clearSessionExpired();
    window.location.reload();
    throw new Error('Oturum süresi doldu');
  }

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

/** Same as request but preserves HTTP status on failure (DE-3 interpret UX). */
export class ApiHttpError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiHttpError';
    this.status = status;
  }
}

async function requestWithStatus<T>(path: string, options: RequestInit = {}, retried = false): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });

  if (
    res.status === 401
    && !retried
    && path !== '/auth/login'
    && path !== '/auth/refresh'
  ) {
    const refreshed = await tryRefreshAccessToken();
    if (refreshed) {
      return requestWithStatus<T>(path, options, true);
    }
    clearSessionExpired();
    window.location.reload();
    throw new ApiHttpError(401, 'Oturum süresi doldu');
  }

  if (res.status === 401 && path !== '/auth/login') {
    clearSessionExpired();
    window.location.reload();
    throw new ApiHttpError(401, 'Oturum süresi doldu');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Bir hata oluştu' }));
    const detail = err.detail;
    const message =
      typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg : 'Bir hata oluştu';
    throw new ApiHttpError(res.status, message || 'Bir hata oluştu');
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

  login: async (username: string, password: string, remember_me: boolean) => {
    const res = await fetchWithCredentials('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password, remember_me }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Bir hata oluştu' }));
      const detail = err.detail;
      const message =
        typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg : 'Bir hata oluştu';
      throw new Error(message || 'Bir hata oluştu');
    }
    return res.json() as Promise<AuthResponse>;
  },

  refreshSession: () =>
    fetchWithCredentials('/auth/refresh', { method: 'POST' }).then(async (res) => {
      if (!res.ok) {
        throw new Error('Oturum restore edilemedi');
      }
      return res.json() as Promise<AuthResponse>;
    }),

  logout: () =>
    fetchWithCredentials('/auth/logout', { method: 'POST' }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Bir hata oluştu' }));
        throw new Error(typeof err.detail === 'string' ? err.detail : 'Çıkış başarısız');
      }
      return res.json() as Promise<{ message: string }>;
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

  getRevenue: (params?: { year?: number; month?: number }) => {
    const search = new URLSearchParams();
    if (params?.year) search.set('year', String(params.year));
    if (params?.month) search.set('month', String(params.month));
    const qs = search.toString();
    return request<RevenueData>(`/revenue${qs ? `?${qs}` : ''}`);
  },

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

  addLeadPayment: (id: number, amount: number, paidAt?: string) =>
    request<Lead>(`/leads/${id}/payments`, {
      method: 'POST',
      body: JSON.stringify({ amount, paid_at: paidAt || '' }),
    }),

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

  listAiActions: (statusFilter: 'proposed' | 'approved' | 'all' = 'all', limit = 50) =>
    request<AiActionListResponse>(
      `/ai/actions?status_filter=${encodeURIComponent(statusFilter)}&limit=${limit}`,
    ),

  getAiAction: (actionId: string) => request<AiActionItem>(`/ai/actions/${encodeURIComponent(actionId)}`),

  approveAiAction: (actionId: string) =>
    request<AiActionItem>(`/ai/actions/${encodeURIComponent(actionId)}/approve`, { method: 'POST' }),

  updateAiAction: (actionId: string, parameters: Record<string, unknown>) =>
    request<AiActionItem>(`/ai/actions/${encodeURIComponent(actionId)}/update`, {
      method: 'POST',
      body: JSON.stringify({ parameters }),
    }),

  cancelAiAction: (actionId: string) =>
    request<AiActionItem>(`/ai/actions/${encodeURIComponent(actionId)}/cancel`, { method: 'POST' }),

  executeAiAction: (actionId: string) =>
    request<AiActionExecuteResponse>(`/ai/actions/${encodeURIComponent(actionId)}/execute`, {
      method: 'POST',
    }),

  getCompanyProfile: (refresh = false) =>
    request<CompanyProfile>(`/intelligence/company-profile?refresh=${refresh ? 'true' : 'false'}`),

  listDiagnoses: (period = 'monthly') =>
    request<DiagnosisListResponse>(`/intelligence/diagnoses?period=${period}`),

  getDiagnosisHistory: (
    diagnosisId: string,
    opts?: { periodKey?: string; page?: number; limit?: number },
  ) => {
    const params = new URLSearchParams();
    if (opts?.periodKey) params.set('period_key', opts.periodKey);
    if (opts?.page != null) params.set('page', String(opts.page));
    if (opts?.limit != null) params.set('limit', String(opts.limit));
    const qs = params.toString();
    return requestWithStatus<DiagnosisHistoryResponse>(
      `/intelligence/diagnoses/${encodeURIComponent(diagnosisId)}/history${qs ? `?${qs}` : ''}`,
    );
  },

  syncDiagnoses: (body?: { period?: string; date?: string | null }) =>
    request<DiagnosisSyncResponse>('/intelligence/diagnoses/sync', {
      method: 'POST',
      body: JSON.stringify({
        period: body?.period ?? 'monthly',
        ...(body?.date ? { date: body.date } : {}),
      }),
    }),

  interpretDiagnosis: (body: DiagnosisInterpretRequest) =>
    requestWithStatus<DiagnosisInterpretResponse>('/ai/diagnosis/interpret', {
      method: 'POST',
      body: JSON.stringify({
        diagnosis_id: body.diagnosis_id,
        period: body.period,
        date: body.date ?? null,
        locale: body.locale ?? 'tr',
        refresh: body.refresh ?? false,
      }),
    }),

  interpretDiagnosisHistory: (body: DiagnosisHistoryInterpretRequest) =>
    requestWithStatus<DiagnosisHistoryInterpretResponse>('/ai/diagnosis/history/interpret', {
      method: 'POST',
      body: JSON.stringify({
        diagnosis_id: body.diagnosis_id,
        period_key: body.period_key ?? null,
        locale: body.locale ?? 'tr',
        refresh: body.refresh ?? false,
      }),
    }),

  sendAiChat: (body: AiChatRequest) =>
    request<AiChatResponse>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  listAssistantConversations: () =>
    request<AssistantConversationListResponse>('/ai/conversations'),

  createAssistantConversation: (body?: { title?: string }) =>
    request<AssistantConversation>('/ai/conversations', {
      method: 'POST',
      body: JSON.stringify(body ?? {}),
    }),

  getAssistantConversation: (conversationId: number) =>
    request<AssistantConversationDetailResponse>(
      `/ai/conversations/${encodeURIComponent(String(conversationId))}`,
    ),

  updateAssistantConversation: (conversationId: number, body: { title?: string }) =>
    request<AssistantConversation>(
      `/ai/conversations/${encodeURIComponent(String(conversationId))}`,
      {
        method: 'PATCH',
        body: JSON.stringify(body),
      },
    ),

  archiveAssistantConversation: (conversationId: number) =>
    request<AssistantConversation>(
      `/ai/conversations/${encodeURIComponent(String(conversationId))}`,
      { method: 'DELETE' },
    ),

  streamAiChat: async (
    body: AiChatRequest,
    onDelta: (chunk: string) => void,
    onToolStatus?: (status: string | null) => void,
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
    let conversation_id: number | null = body.conversation_id ?? null;

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
            conversation_id?: number;
            status?: string;
            tool?: string;
          };
          if (payload.type === 'tool_start') {
            onToolStatus?.(payload.status || payload.tool || null);
          } else if (payload.type === 'tool_done') {
            onToolStatus?.(payload.status || null);
          } else if (payload.type === 'delta' && payload.content) {
            onToolStatus?.(null);
            reply += payload.content;
            onDelta(payload.content);
          } else if (payload.type === 'done') {
            onToolStatus?.(null);
            run_id = payload.run_id ?? 0;
            disclaimer = payload.disclaimer ?? '';
            if (payload.conversation_id != null) {
              conversation_id = payload.conversation_id;
            }
          } else if (payload.type === 'error') {
            onToolStatus?.(null);
            throw new Error(payload.detail || 'Yanıt alınamadı');
          }
        }
        sep = buffer.indexOf('\n\n');
      }
    }

    return { reply, run_id, disclaimer, conversation_id };
  },
};

export function saveAuth(response: AuthResponse, remember: boolean) {
  setRememberPreference(remember);
  setToken(response.access_token, remember);
  if (response.idle_timeout_minutes) {
    setIdleTimeoutMinutes(response.idle_timeout_minutes);
  }
}
