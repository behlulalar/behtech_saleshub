const TOKEN_KEY = 'crm_token';
const REMEMBER_KEY = 'crm_remember';
const REMEMBER_PREF_KEY = 'crm_remember_pref';
const USERNAME_KEY = 'crm_username';
const PASSWORD_KEY = 'crm_password';
const DEFAULT_IDLE_TIMEOUT_MS = 30 * 60 * 1000;

let idleTimeoutMs = DEFAULT_IDLE_TIMEOUT_MS;

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

export function isRememberMe(): boolean {
  return localStorage.getItem(REMEMBER_KEY) === '1';
}

/** Login form checkbox — survives logout / expired session when user opted in before. */
export function getRememberPreference(): boolean {
  const pref = localStorage.getItem(REMEMBER_PREF_KEY);
  if (pref === '1') return true;
  if (pref === '0') return false;
  return isRememberMe();
}

export function setRememberPreference(remember: boolean) {
  localStorage.setItem(REMEMBER_PREF_KEY, remember ? '1' : '0');
}

export function setToken(token: string, remember: boolean) {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  if (remember) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(REMEMBER_KEY, '1');
  } else {
    sessionStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(REMEMBER_KEY);
  }
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

/** Oturum bitti (401 / süre doldu) — “beni hatırla” kullanıcı adını korur. */
export function clearSessionExpired() {
  clearToken();
}

export function clearAuth() {
  clearToken();
  localStorage.removeItem(REMEMBER_KEY);
  localStorage.removeItem(REMEMBER_PREF_KEY);
  clearSavedUsername();
  clearSavedPassword();
}

export function setSavedPassword(password: string) {
  localStorage.setItem(PASSWORD_KEY, password);
}

export function clearSavedPassword() {
  localStorage.removeItem(PASSWORD_KEY);
}

export function getSavedPassword(): string | null {
  if (!getRememberPreference()) return null;
  return localStorage.getItem(PASSWORD_KEY);
}

export function persistRememberCredentials(username: string, password: string) {
  setRememberPreference(true);
  if (username.trim()) setUsername(username.trim());
  if (password) setSavedPassword(password);
}

export function clearRememberCredentials() {
  clearSavedUsername();
  clearSavedPassword();
}

export function setUsername(username: string) {
  localStorage.setItem(USERNAME_KEY, username);
}

export function clearSavedUsername() {
  localStorage.removeItem(USERNAME_KEY);
}

export function getUsername(): string | null {
  return localStorage.getItem(USERNAME_KEY);
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
