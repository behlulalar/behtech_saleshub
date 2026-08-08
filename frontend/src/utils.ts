export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('tr-TR', {
    style: 'currency',
    currency: 'TRY',
    maximumFractionDigits: 0,
  }).format(value);
}

export function toInstagramUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }

  const domainMatch = trimmed.match(/(?:www\.)?instagram\.com\/([^/?#]+)/i);
  if (domainMatch?.[1]) {
    return `https://www.instagram.com/${domainMatch[1]}/`;
  }

  const handle = trimmed.replace(/^@/, '').replace(/\/$/, '');
  if (!handle || /\s/.test(handle)) return null;

  return `https://www.instagram.com/${handle}/`;
}

/** Telefon numarasını rakamlara indirger; Türkiye için wa.me / tel uyumlu hale getirir. */
export function normalizePhone(value: string): string | null {
  let digits = value.replace(/\D/g, '');
  if (!digits) return null;

  if (digits.startsWith('90') && digits.length === 12) {
    return digits;
  }
  if (digits.startsWith('0') && digits.length === 11) {
    return `90${digits.slice(1)}`;
  }
  if (digits.length === 10 && digits.startsWith('5')) {
    return `90${digits}`;
  }
  if (digits.length >= 10) {
    return digits;
  }
  return null;
}

export function toWhatsAppUrl(phone: string, message?: string): string | null {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;
  const base = `https://wa.me/${normalized}`;
  if (!message?.trim()) return base;
  return `${base}?text=${encodeURIComponent(message.trim())}`;
}

export function toTelUrl(phone: string): string | null {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;
  return `tel:+${normalized}`;
}

export function toMailtoUrl(options: {
  email?: string;
  subject?: string;
  body?: string;
}): string {
  const params = new URLSearchParams();
  if (options.subject?.trim()) params.set('subject', options.subject.trim());
  if (options.body?.trim()) params.set('body', options.body.trim());
  const query = params.toString();
  const to = options.email?.trim() || '';
  return query ? `mailto:${to}?${query}` : `mailto:${to}`;
}

export function fillMessageTemplate(
  template: string,
  vars: Record<string, string | undefined | null>,
): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = vars[key];
    return value?.trim() ? value.trim() : '';
  });
}

/** Backend naive UTC ISO → Europe/Istanbul for display. */
export function parseApiDateTime(iso: string): Date {
  const trimmed = iso.trim();
  if (!trimmed) return new Date(NaN);
  const hasTz = /[Zz]$|[+-]\d{2}:\d{2}$/.test(trimmed);
  return new Date(hasTz ? trimmed : `${trimmed}Z`);
}

export function formatAppDateTime(iso: string, locale: 'tr' | 'en' = 'tr'): string {
  const date = parseApiDateTime(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const loc = locale === 'en' ? 'en-GB' : 'tr-TR';
  return date.toLocaleString(loc, {
    timeZone: 'Europe/Istanbul',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}
