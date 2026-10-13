export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface AuthUser {
  id: string;
  /** Employee ID recorded on every question and audit entry. Older sessions only have `id`. */
  employeeId?: string;
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
 * DEVELOPMENT-ONLY employee directory for the simulated login, so per-employee history can be
 * exercised with distinct people. These are test identities, not real staff. Replace with the
 * identity provider (SSO) before production; until then the backend trusts the identity headers.
 */
const DEV_DIRECTORY: Record<string, { employeeId: string; name: string; role: string }> = {
  'manager@feuji.com': { employeeId: 'EMP-1001', name: 'Dev Manager', role: 'manager' },
  'agent@feuji.com': { employeeId: 'EMP-1002', name: 'Dev Service Agent', role: 'csr' },
  'adjuster@feuji.com': { employeeId: 'EMP-1003', name: 'Dev Claims Adjuster', role: 'adjuster' },
  'auditor@feuji.com': { employeeId: 'EMP-1004', name: 'Dev Auditor', role: 'auditor' },
};

/** Directory entry for a dev email; any other email gets an ID derived from it and the default role. */
function devIdentity(email: string): { employeeId: string; name: string; role: string } {
  const key = email.trim().toLowerCase();
  const known = DEV_DIRECTORY[key];
  if (known) return known;
  const local = key.split('@')[0] || 'employee';
  const name = local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ');
  return { employeeId: `DEV-${local.toUpperCase()}`, name: name || 'Employee', role: 'underwriter' };
}

/** Identity of the signed-in employee, as sent to the backend with every request. */
export function currentEmployee(): { employeeId: string; name: string; role: string } | null {
  const user = getSession()?.user;
  if (!user) return null;
  return { employeeId: user.employeeId || user.id, name: user.name, role: user.role };
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
  const identity = devIdentity(credentials.email);
  return {
    success: true,
    user: {
      id: identity.employeeId,
      employeeId: identity.employeeId,
      email: credentials.email.trim(),
      name: identity.name,
      role: identity.role,
    },
    token: 'dev-session-token-placeholder',
  };
}
