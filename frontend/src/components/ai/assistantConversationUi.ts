/** DE-6.3-B — shared conversation list helpers (UI only). */

export type ConversationDateGroup = 'today' | 'yesterday' | 'last7' | 'older';

export function conversationDateGroup(iso: string, now = new Date()): ConversationDateGroup {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'older';
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOf7 = new Date(startOfToday);
  startOf7.setDate(startOf7.getDate() - 6);
  if (d >= startOfToday) return 'today';
  if (d >= startOfYesterday) return 'yesterday';
  if (d >= startOf7) return 'last7';
  return 'older';
}

export function titlePreview(title: string | null | undefined, fallback: string, max = 48): string {
  const t = (title || '').trim();
  if (!t) return fallback;
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1).trimEnd()}…`;
}

/** Hide tool dumps / internal-looking payloads from chat bubbles. */
export function sanitizeAssistantDisplayText(content: string): string {
  const text = (content || '').trim();
  if (!text) return '';
  if (/^\s*\{[\s\S]*"ok"\s*:/.test(text) && text.length > 80) {
    return '';
  }
  if (/\borganization_id\b|\bfingerprint\b/i.test(text) && text.startsWith('{')) {
    return '';
  }
  return text;
}

export function isSnakeToolName(value: string | null | undefined): boolean {
  if (!value) return false;
  return /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/.test(value.trim());
}
