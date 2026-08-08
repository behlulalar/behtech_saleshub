import type { Stats } from '../types';
import { DURUM_STATUSES, getDurumBarClass } from '../types';
import StatusBadge from './StatusBadge';

interface Props {
  stats: Stats | null;
}

export default function StatusBreakdown({ stats }: Props) {
  if (!stats) return null;

  const maxCount = Math.max(...Object.values(stats.by_status), 1);
  const ordered = DURUM_STATUSES.map((status) => ({
    ...status,
    count: stats.by_status[status.value] || 0,
  })).filter((item) => item.count > 0);

  if (ordered.length === 0) return null;

  return (
    <div className="card p-4">
      <h3 className="mb-4 text-sm font-semibold text-surface-900">Durum Dağılımı</h3>
      <div className="space-y-3">
        {ordered.map((item) => {
          const width = Math.max((item.count / maxCount) * 100, item.count > 0 ? 8 : 0);
          return (
            <div key={item.value} className="space-y-1.5">
              <div className="flex items-center justify-between gap-3">
                <StatusBadge durum={item.value} size="xs" />
                <span className="text-sm font-semibold text-surface-900">{item.count}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-100">
                <div
                  className={`h-full rounded-full transition-all ${getDurumBarClass(item.value)}`}
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
