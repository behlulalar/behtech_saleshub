import type { AiActionItem } from '../../types';

/** UI-only operational grouping (does not mutate / merge API rows). */
export type De4ActionGroup = {
  key: string;
  action_type: string;
  target_entity: string;
  target_entity_id: number | null;
  lead_name: string | null;
  items: AiActionItem[];
};

export function operationalGroupKey(item: AiActionItem): string {
  const entity = (item.target_entity || 'lead').trim().toLowerCase();
  const tid = item.target_entity_id ?? 'none';
  return `${item.action_type}|${entity}|${tid}`;
}

export function groupAiActionsOperationally(items: AiActionItem[]): De4ActionGroup[] {
  const map = new Map<string, De4ActionGroup>();
  for (const item of items) {
    const key = operationalGroupKey(item);
    let group = map.get(key);
    if (!group) {
      group = {
        key,
        action_type: item.action_type,
        target_entity: item.target_entity || 'lead',
        target_entity_id: item.target_entity_id ?? null,
        lead_name: item.lead_name ?? null,
        items: [],
      };
      map.set(key, group);
    }
    group.items.push(item);
    if (!group.lead_name && item.lead_name) {
      group.lead_name = item.lead_name;
    }
  }

  const groups = Array.from(map.values());
  for (const g of groups) {
    g.items.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  }
  groups.sort((a, b) => {
    const leadA = (a.lead_name || `#${a.target_entity_id ?? ''}`).toLocaleLowerCase();
    const leadB = (b.lead_name || `#${b.target_entity_id ?? ''}`).toLocaleLowerCase();
    if (leadA !== leadB) return leadA.localeCompare(leadB, 'tr');
    return a.action_type.localeCompare(b.action_type);
  });
  return groups;
}
