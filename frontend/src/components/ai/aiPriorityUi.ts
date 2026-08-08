/** Backend scoring v0 returns high | medium | low (English). */
export function aiPriorityLabel(priority: string, labels: Record<string, string>): string {
  const p = priority.toLowerCase();
  if (p === 'high') return labels.yuksek ?? 'Yüksek';
  if (p === 'low') return labels.dusuk ?? 'Düşük';
  return labels.orta ?? 'Orta';
}

export function aiPriorityBadgeClass(priority: string): string {
  const p = priority.toLowerCase();
  if (p === 'high') return 'bg-rose-100 text-rose-800';
  if (p === 'low') return 'bg-surface-100 text-surface-700';
  return 'bg-amber-100 text-amber-800';
}
