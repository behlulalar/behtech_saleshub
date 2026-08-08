import { BarChart3, CheckCircle, Send, Users } from 'lucide-react';
import type { Stats } from '../types';
import { ONCELIK_OPTIONS } from '../types';
import { useLocale } from '../i18n/locale';
import PriorityBadge from './PriorityBadge';

interface Props {
  stats: Stats | null;
}

export default function StatsCards({ stats }: Props) {
  const { app } = useLocale();
  const s = app.stats;

  if (!stats) return null;

  const activeCount = Object.entries(stats.by_status)
    .filter(([status]) => !['Olumsuz', 'Cevap Yok'].includes(status))
    .reduce((sum, [, count]) => sum + count, 0);

  const items = [
    { label: s.total, value: stats.total, icon: Users, color: 'text-brand-500' },
    { label: s.active, value: activeCount, icon: BarChart3, color: 'text-amber-600' },
    { label: s.demo, value: stats.demo_gonderildi, icon: Send, color: 'text-indigo-600' },
    { label: s.customer, value: stats.by_status['Müşteri'] || 0, icon: CheckCircle, color: 'text-emerald-600' },
  ];

  return (
    <div className="card min-w-0 shrink-0 px-3 py-2.5 text-sm max-lg:hidden">
      <div className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4 lg:flex lg:flex-wrap lg:items-center lg:gap-x-4 lg:gap-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <item.icon size={14} className={item.color} />
            <span className="text-surface-800/50">{item.label}</span>
            <span className="font-bold text-surface-900">{item.value}</span>
          </div>
        ))}
        {stats.by_priority && (
          <>
            <span className="col-span-2 hidden h-4 w-px bg-surface-200 sm:col-auto lg:block" />
            <div className="col-span-2 flex flex-wrap items-center gap-x-3 gap-y-1 sm:col-span-4 lg:col-auto lg:contents">
              {ONCELIK_OPTIONS.map((option) => (
                <div key={option.value} className="flex items-center gap-1">
                  <PriorityBadge oncelik={option.value} size="xs" showIcon={false} />
                  <span className="font-semibold text-surface-900">
                    {stats.by_priority[option.value] || 0}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
