import { useCallback, useEffect, useState } from 'react';
import { Activity, ChevronRight, Loader2, Stethoscope } from 'lucide-react';
import { api } from '../../api';
import type { DiagnosisItem, DiagnosisPriorityLead } from '../../types';

const severityClass: Record<string, string> = {
  low: 'bg-surface-100 text-surface-700',
  medium: 'bg-amber-50 text-amber-800',
  high: 'bg-rose-50 text-rose-800',
  critical: 'bg-rose-100 text-rose-900',
};

const priorityClass: Record<string, string> = {
  high: 'bg-rose-50 text-rose-800',
  medium: 'bg-amber-50 text-amber-800',
  low: 'bg-surface-100 text-surface-700',
};

type Props = {
  onEditLead?: (leadId: number) => void;
};

function PriorityLeadRow({
  row,
  onEditLead,
}: {
  row: DiagnosisPriorityLead;
  onEditLead?: (leadId: number) => void;
}) {
  return (
    <li className="flex items-center gap-2 rounded-lg border border-surface-100 bg-surface-50/80 px-2.5 py-2 text-xs">
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 font-medium uppercase ${priorityClass[row.priority] ?? priorityClass.medium}`}
      >
        {row.priority}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-surface-900">{row.lead_name}</p>
        <p className="text-surface-600/80">
          Skor {row.diagnosis_priority_score}
          {row.diagnosis_modifier > 0 ? ` (+${row.diagnosis_modifier} teşhis)` : ''}
          {row.idle_days != null ? ` · ${row.idle_days} gün` : ''}
          {row.offer_age_days != null ? ` · teklif ${row.offer_age_days} gün` : ''}
        </p>
      </div>
      {onEditLead ? (
        <button
          type="button"
          onClick={() => onEditLead(row.lead_id)}
          className="flex shrink-0 items-center gap-0.5 text-violet-700 hover:text-violet-900"
        >
          Aç
          <ChevronRight size={14} />
        </button>
      ) : null}
    </li>
  );
}

export default function SalesDiagnosesCard({ onEditLead }: Props) {
  const [items, setItems] = useState<DiagnosisItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listDiagnoses('monthly');
      setItems(data.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Teşhisler yüklenemedi');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="card overflow-hidden border-surface-200">
      <div className="flex items-start gap-3 border-b border-surface-100 bg-surface-50/50 px-4 py-3.5 sm:px-5 sm:py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
          <Stethoscope size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-surface-900 sm:text-base">Satış teşhisleri</h3>
          <p className="mt-1 text-xs text-surface-800/60 sm:text-sm">
            Deterministik kurallar (LLM yok). Öncelik: mevcut lead skoru + lead&apos;e özel teşhis.
          </p>
        </div>
        {loading ? <Loader2 size={18} className="animate-spin text-surface-400" /> : null}
      </div>

      {error ? <p className="px-4 py-3 text-sm text-rose-600 sm:px-5">{error}</p> : null}

      {!error && !loading && items.length === 0 ? (
        <p className="flex items-center gap-2 px-4 py-4 text-sm text-surface-800/55 sm:px-5">
          <Activity size={16} />
          Şu an tetiklenen teşhis yok — veriler normal görünüyor.
        </p>
      ) : null}

      {items.length > 0 ? (
        <ul className="divide-y divide-surface-100">
          {items.map((d) => (
            <li key={d.diagnosis_id} className="px-4 py-3 sm:px-5">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase ${severityClass[d.severity] ?? severityClass.medium}`}
                >
                  {d.severity}
                </span>
                <span className="text-xs text-surface-500">{d.type}</span>
              </div>
              <p className="mt-1 text-sm font-medium text-surface-900">{d.title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-surface-800/65">{d.description}</p>

              {d.affected_leads_available === false ? (
                <p className="mt-2 text-xs text-surface-600/70">
                  Hunu teşhisi — lead bazlı öncelik listesi yok.
                </p>
              ) : null}

              {d.impact && d.affected_leads_available !== false ? (
                <p className="mt-2 text-xs text-surface-700">
                  Öncelik dağılımı:{' '}
                  <span className="font-medium text-rose-700">{d.impact.high_priority_count} yüksek</span>
                  {', '}
                  <span className="font-medium text-amber-800">{d.impact.medium_priority_count} orta</span>
                  {', '}
                  <span>{d.impact.low_priority_count} düşük</span>
                </p>
              ) : null}

              {d.top_priority_leads && d.top_priority_leads.length > 0 ? (
                <ul className="mt-2 space-y-1.5">
                  {d.top_priority_leads.map((row) => (
                    <PriorityLeadRow key={row.lead_id} row={row} onEditLead={onEditLead} />
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
