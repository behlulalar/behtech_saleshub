import { Filter } from 'lucide-react';
import type { FunnelStage } from '../types';
import { FUNNEL_STAGE_COLORS } from '../types';
import { useLocale } from '../i18n/locale';

interface Props {
  stages: FunnelStage[];
  conversionRate: number;
}

export default function SalesFunnel({ stages, conversionRate }: Props) {
  const { app } = useLocale();
  const f = app.salesFunnel;

  if (stages.length === 0) return null;

  const maxCount = Math.max(...stages.map((stage) => stage.count), 1);

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-3">
        <Filter size={16} className="text-brand-500" />
        <h3 className="text-sm font-semibold text-surface-900">{f.title}</h3>
        <span className="ml-auto rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-500">
          %{conversionRate} {f.conversion}
        </span>
      </div>

      <div className="space-y-1 px-4 py-6">
        {stages.map((stage, index) => {
          const width = Math.max((stage.count / maxCount) * 100, stage.count > 0 ? 28 : 18);
          const barColor = FUNNEL_STAGE_COLORS[stage.key] || 'bg-brand-500';

          return (
            <div key={stage.key}>
              <div className="mx-auto transition-all" style={{ width: `${width}%` }}>
                <div className={`rounded-lg px-4 py-3 text-white shadow-sm ${barColor}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-white/80">
                        {stage.label}
                      </p>
                      <p className="text-2xl font-bold">{stage.count}</p>
                    </div>
                    {stage.conversion_rate !== null && index < stages.length - 1 ? (
                      <div className="text-right">
                        <p className="text-xs text-white/70">→</p>
                        <p className="text-sm font-semibold">%{stage.conversion_rate}</p>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
              {index < stages.length - 1 ? (
                <div className="flex justify-center py-1 text-surface-300">
                  <Filter size={14} className="rotate-180" />
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
