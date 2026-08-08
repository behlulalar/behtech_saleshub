import { useCallback, useEffect, useState } from 'react';
import { Activity, Loader2, Stethoscope } from 'lucide-react';
import { api } from '../../api';
import type { DiagnosisItem } from '../../types';

const severityClass: Record<string, string> = {
  low: 'bg-surface-100 text-surface-700',
  medium: 'bg-amber-50 text-amber-800',
  high: 'bg-rose-50 text-rose-800',
  critical: 'bg-rose-100 text-rose-900',
};

export default function SalesDiagnosesCard() {
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
            Deterministik kurallar (LLM yok). Aylık dönem karşılaştırması.
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
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
