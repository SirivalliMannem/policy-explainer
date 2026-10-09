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

const SESSION_KEY = 'policy-explainer.session';

export interface Session {
  user: AuthUser;
  token: string;
}

/** Remember the signed-in employee for this browser tab. */
export function saveSession(session: Session): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // Storage can be unavailable (private mode, blocked site data); the app still works for this page view.
  }
}

export function getSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Nothing stored, nothing to clear.
  }
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
