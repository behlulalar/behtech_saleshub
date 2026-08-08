import { DURUM_STATUSES } from '../types';
import StatusBadge from './StatusBadge';

interface Props {
  compact?: boolean;
}

export default function StatusLegend({ compact = false }: Props) {
  return (
    <div className="card p-4">
      <h3 className="mb-3 text-sm font-semibold text-surface-900">Satış Aşamaları</h3>
      {compact ? (
        <div className="flex flex-wrap gap-2">
          {DURUM_STATUSES.map((status) => (
            <StatusBadge key={status.value} durum={status.value} size="xs" />
          ))}
        </div>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {DURUM_STATUSES.map((status) => (
            <div key={status.value} className="flex items-start gap-2 rounded-lg border border-surface-100 px-3 py-2">
              <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${status.barClass}`} />
              <div className="min-w-0">
                <StatusBadge durum={status.value} size="xs" />
                <p className="mt-1 text-xs text-surface-800/50">{status.description}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
