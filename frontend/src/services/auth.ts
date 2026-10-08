export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

export interface AuthResult {
  success: boolean;
  user?: AuthUser;
  token?: string;
  error?: string;
}

/**
 * Authentication service boundary.
 * Currently provides an isolated development simulation.
 * Will connect to backend authentication API when endpoints are deployed.
 */
export async function authenticateEmployee(credentials: LoginCredentials): Promise<AuthResult> {
  // Realistic API latency simulation
  await new Promise((resolve) => setTimeout(resolve, 800));

  // Placeholder boundary: will be replaced with:
  // return apiClient.post<AuthResult>('/api/auth/login', credentials);
  return {
    success: true,
    user: {
      id: 'emp-dev-01',
      email: credentials.email,
      name: 'Insurance Specialist',
      role: 'underwriter',
    },
    token: 'dev-session-token-placeholder',
  };
}
