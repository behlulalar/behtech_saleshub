const PERSONAL_EMAIL_DOMAINS = new Set([
  'gmail.com',
  'googlemail.com',
  'hotmail.com',
  'hotmail.com.tr',
  'outlook.com',
  'outlook.com.tr',
  'live.com',
  'msn.com',
  'yahoo.com',
  'yahoo.com.tr',
  'ymail.com',
  'icloud.com',
  'me.com',
  'mac.com',
  'proton.me',
  'protonmail.com',
  'pm.me',
  'yandex.com',
  'yandex.com.tr',
  'yandex.ru',
  'mail.ru',
  'inbox.ru',
  'gmx.com',
  'gmx.de',
  'aol.com',
  'zoho.com',
  'tutanota.com',
  'fastmail.com',
  'qq.com',
  '163.com',
  '126.com',
]);

export function getEmailDomain(email: string): string {
  return email.trim().split('@').pop()?.toLowerCase() || '';
}

export function isPersonalEmail(email: string): boolean {
  return PERSONAL_EMAIL_DOMAINS.has(getEmailDomain(email));
}

export function passwordsMatch(password: string, confirm: string): boolean {
  return password.length > 0 && password === confirm;
}

export const PASSWORD_TESTS = [
  { id: 'length', test: (p: string) => p.length >= 8 },
  { id: 'upper', test: (p: string) => /[A-Z]/.test(p) },
  { id: 'lower', test: (p: string) => /[a-z]/.test(p) },
  { id: 'digit', test: (p: string) => /[0-9]/.test(p) },
  { id: 'special', test: (p: string) => /[^A-Za-z0-9]/.test(p) },
] as const;

export function passwordIsStrong(password: string): boolean {
  return PASSWORD_TESTS.every((rule) => rule.test(password));
}
