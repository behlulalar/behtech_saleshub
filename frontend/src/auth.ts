const TOKEN_KEY = 'crm_token';
const REMEMBER_PREF_KEY = 'crm_remember_pref';
const DEFAULT_IDLE_TIMEOUT_MS = 30 * 60 * 1000;

let idleTimeoutMs = DEFAULT_IDLE_TIMEOUT_MS;

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

/** User opted into remember-me (persistent session via HttpOnly cookie). */
export function isRememberMe(): boolean {
  return localStorage.getItem(REMEMBER_PREF_KEY) === '1';
}

export function getRememberPreference(): boolean {
  const pref = localStorage.getItem(REMEMBER_PREF_KEY);
  if (pref === '1') return true;
  if (pref === '0') return false;
  return false;
}

export function setRememberPreference(remember: boolean) {
  localStorage.setItem(REMEMBER_PREF_KEY, remember ? '1' : '0');
}

export function setToken(token: string, remember: boolean) {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  if (remember) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

/** Oturum bitti (401 / süre doldu) — remember preference korunur. */
export function clearSessionExpired() {
  clearToken();
}

export function clearAuth() {
  clearToken();
  localStorage.removeItem(REMEMBER_PREF_KEY);
}

export function getUsername(): string | null {
  return null;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function setIdleTimeoutMinutes(minutes: number) {
  if (minutes > 0) {
    idleTimeoutMs = minutes * 60 * 1000;
  }
}

export function getIdleTimeoutMs(): number {
  return idleTimeoutMs;
}

export function getIdleTimeoutMinutes(): number {
  return Math.round(idleTimeoutMs / 60000);
}
