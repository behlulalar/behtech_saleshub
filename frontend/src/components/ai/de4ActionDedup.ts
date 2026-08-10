import type { AiActionItem } from '../../types';

/** Defensive UI dedup by action_id (backend remains authoritative). */
export function uniqueActionIds(ids: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of ids) {
    const key = (id || '').trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}

export function uniqueAiActionItems(items: AiActionItem[]): AiActionItem[] {
  const seen = new Set<string>();
  const out: AiActionItem[] = [];
  for (const item of items) {
    const key = item.action_id?.trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}
