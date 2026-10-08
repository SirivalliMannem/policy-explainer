import { APP_CONFIG } from '../config';
import { HealthCheckResponse } from '../types';

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...rest } = options;
  const baseUrl = (APP_CONFIG.apiBaseUrl || '').replace(/\/$/, '');
  const pathWithSlash = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullPath = `${baseUrl}${pathWithSlash}`;
  const url = fullPath.startsWith('http://') || fullPath.startsWith('https://')
    ? new URL(fullPath)
    : new URL(fullPath, typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173');

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  const response = await fetch(url.toString(), {
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    ...rest,
  });

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = await response.text();
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
  return apiClient.get<HealthCheckResponse>('/health');
}

/**
 * Fetch real dashboard metrics, activity history, evidence quality, and recent questions.
 */
export async function getDashboardStats(
  timeRange: 'today' | '7d' | '30d' = '7d'
): Promise<import('../types').DashboardResponse> {
  return apiClient.get<import('../types').DashboardResponse>('/api/dashboard/stats', {
    params: { range: timeRange },
  });
}
