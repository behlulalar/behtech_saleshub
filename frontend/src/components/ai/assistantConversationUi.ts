/** DE-6.3-B / DE-6.8 — shared conversation list helpers (UI only). */

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

export type RelativeTimeLabels = {
  justNow: string;
  minutes: string;
  hours: string;
  days: string;
};

/** Compact relative label for sidebar rows (no IDs). */
export function formatRelativeConversationTime(
  iso: string,
  labels: RelativeTimeLabels,
  now = new Date(),
): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const diffMs = Math.max(0, now.getTime() - d.getTime());
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return labels.justNow;
  if (mins < 60) return labels.minutes.replace('{n}', String(mins));
  const hours = Math.floor(mins / 60);
  if (hours < 24) return labels.hours.replace('{n}', String(hours));
  const days = Math.floor(hours / 24);
  if (days < 7) return labels.days.replace('{n}', String(days));
  try {
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  } catch {
    return '';
  }
}

/** Light structure for assistant bubbles (paragraphs + simple lists). */
export function splitAssistantContentBlocks(content: string): Array<
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] }
> {
  const text = (content || '').replace(/\r\n/g, '\n').trim();
  if (!text) return [];
  const chunks = text.split(/\n{2,}/);
  const out: Array<{ type: 'paragraph'; text: string } | { type: 'list'; items: string[] }> = [];
  for (const chunk of chunks) {
    const lines = chunk.split('\n').map((l) => l.trimEnd());
    const bulletLines = lines.filter((l) => l.trim().length > 0);
    const allBullets =
      bulletLines.length > 0 &&
      bulletLines.every((l) => /^[-*•]\s+/.test(l.trim()) || /^\d+\.\s+/.test(l.trim()));
    if (allBullets) {
      out.push({
        type: 'list',
        items: bulletLines.map((l) =>
          l
            .trim()
            .replace(/^[-*•]\s+/, '')
            .replace(/^\d+\.\s+/, ''),
        ),
      });
    } else {
      out.push({ type: 'paragraph', text: chunk });
    }
  }
  return out;
}
