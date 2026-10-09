import { APP_CONFIG } from '../config';
import type {
  AttentionResponse,
  BillingItem,
  ClaimItem,
  ConversationMessageRecord,
  ConversationResponse,
  CoverageItem,
  DashboardResponse,
  FormItem,
  HealthCheckResponse,
  LedgerDetail,
  LedgerFilters,
  LedgerPage,
  LedgerQuery,
  LedgerSummary,
  PolicyContextCandidate,
  PolicyDetail,
  QuestionAnswerResponse,
  QuestionResolution,
  RecentQuestionItem,
  SourceDocument,
} from '../types';

/** status 0 = the backend could not be reached; 408 = the browser gave up waiting. */
export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }

  /** The FastAPI `detail` string, when the backend sent one. */
  get detail(): string | undefined {
    const data = this.data as { detail?: unknown } | undefined;
    return typeof data?.detail === 'string' ? data.detail : undefined;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 15_000;
// The backend allows the AI service 45s; leave headroom for the backend's own work.
const QUESTION_TIMEOUT_MS = 60_000;

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = options;
  const baseUrl = (APP_CONFIG.apiBaseUrl || '').replace(/\/$/, '');
  const pathWithSlash = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullPath = `${baseUrl}${pathWithSlash}`;
  const url = fullPath.startsWith('http://') || fullPath.startsWith('https://')
    ? new URL(fullPath)
    : new URL(fullPath, typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173');

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.append(key, String(value));
      }
    });
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      ...rest,
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new ApiError(408, `Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw new ApiError(0, `Could not reach the backend at ${baseUrl || window.location.origin}`, err);
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = await response.text().catch(() => undefined);
    }
    throw new ApiError(
      response.status,
      `API request failed with status ${response.status}`,
      errorData
    );
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: 'GET', ...options }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: 'DELETE', ...options }),
};

/**
 * Health check helper querying the backend health endpoint.
 */
export async function checkHealth(): Promise<HealthCheckResponse> {
  return apiClient.get<HealthCheckResponse>('/health', { timeoutMs: 5_000 });
}

/**
 * Fetch real dashboard metrics, activity history, evidence quality, and recent questions.
 */
export async function getDashboardStats(
  timeRange: 'today' | '7d' | '30d' = '7d'
): Promise<DashboardResponse> {
  return apiClient.get<DashboardResponse>('/api/dashboard/stats', {
    params: { range: timeRange },
  });
}

/** Flagged and unanswered questions in the range, grouped by question, with their causes. */
export async function getNeedsAttention(
  timeRange: 'today' | '7d' | '30d' = '7d'
): Promise<AttentionResponse> {
  return apiClient.get<AttentionResponse>('/api/dashboard/attention', {
    params: { range: timeRange },
  });
}

// ==========================================
// Policy Features API Endpoints
// ==========================================

export async function getPolicy(policyId: string): Promise<PolicyDetail> {
  return apiClient.get<PolicyDetail>(`/api/policies/${encodeURIComponent(policyId)}`);
}

export async function getPolicyCoverages(policyId: string): Promise<CoverageItem[]> {
  return apiClient.get<CoverageItem[]>(`/api/policies/${encodeURIComponent(policyId)}/coverages`);
}

export async function getPolicyForms(policyId: string): Promise<FormItem[]> {
  return apiClient.get<FormItem[]>(`/api/policies/${encodeURIComponent(policyId)}/forms`);
}

export async function getPolicyClaims(policyId: string): Promise<ClaimItem[]> {
  return apiClient.get<ClaimItem[]>(`/api/policies/${encodeURIComponent(policyId)}/claims`);
}

export async function getPolicyBilling(policyId: string): Promise<BillingItem[]> {
  return apiClient.get<BillingItem[]>(`/api/policies/${encodeURIComponent(policyId)}/billing`);
}

// ==========================================
// Policy Resolution API Endpoints
// ==========================================

export async function searchPolicyContext(query: string): Promise<PolicyContextCandidate[]> {
  return apiClient.get<PolicyContextCandidate[]>('/api/policy-resolution/search', {
    params: { q: query },
  });
}

export async function resolvePolicyContext(policyId: string): Promise<PolicyContextCandidate> {
  return apiClient.post<PolicyContextCandidate>('/api/policy-resolution/resolve', {
    policy_id: policyId,
  });
}

/** Ask the backend which policy, if any, a free-text question refers to. */
export async function resolvePolicyFromQuestion(
  question: string,
  conversationId?: string | null
): Promise<QuestionResolution> {
  return apiClient.post<QuestionResolution>(
    '/api/policy-resolution/from-question',
    { question, conversation_id: conversationId ?? undefined },
    // Includes one language-model call to understand the question.
    { timeoutMs: 30_000 }
  );
}

// ==========================================
// Conversation & Question Endpoints
// ==========================================

export async function createConversation(policyId?: string): Promise<ConversationResponse> {
  return apiClient.post<ConversationResponse>('/api/conversations', {
    policy_id: policyId || undefined,
  });
}

export async function getConversation(conversationId: string): Promise<ConversationResponse> {
  return apiClient.get<ConversationResponse>(`/api/conversations/${encodeURIComponent(conversationId)}`);
}

export async function setConversationContext(
  conversationId: string,
  policyId: string
): Promise<ConversationResponse> {
  return apiClient.post<ConversationResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}/context`,
    { policy_id: policyId }
  );
}

export async function clearConversationContext(
  conversationId: string
): Promise<ConversationResponse> {
  return apiClient.delete<ConversationResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}/context`
  );
}

export async function submitQuestion(
  conversationId: string,
  question: string
): Promise<QuestionAnswerResponse> {
  return apiClient.post<QuestionAnswerResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}/questions`,
    { question },
    { timeoutMs: QUESTION_TIMEOUT_MS }
  );
}

/** Most recently asked questions across conversations, newest first. */
export async function getRecentQuestions(limit = 30): Promise<RecentQuestionItem[]> {
  return apiClient.get<RecentQuestionItem[]>('/api/conversations/recent', { params: { limit } });
}

export async function getConversationMessages(conversationId: string): Promise<ConversationMessageRecord[]> {
  return apiClient.get<ConversationMessageRecord[]>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`
  );
}

// ==========================================
// Sources & Evidence Ledger
// ==========================================

export async function getSource(sourceType: string, sourceId: string): Promise<SourceDocument> {
  return apiClient.get<SourceDocument>(
    `/api/sources/${encodeURIComponent(sourceType)}/${encodeURIComponent(sourceId)}`
  );
}

export async function getLedgerSummary(): Promise<LedgerSummary> {
  return apiClient.get<LedgerSummary>('/api/ledger/summary');
}

export async function getLedgerFilters(): Promise<LedgerFilters> {
  return apiClient.get<LedgerFilters>('/api/ledger/filters');
}

export async function getLedger(query: LedgerQuery): Promise<LedgerPage> {
  return apiClient.get<LedgerPage>('/api/ledger', {
    params: query as Record<string, string | number | undefined>,
  });
}

export async function getLedgerEntry(entryId: string): Promise<LedgerDetail> {
  return apiClient.get<LedgerDetail>(`/api/ledger/${encodeURIComponent(entryId)}`);
}
