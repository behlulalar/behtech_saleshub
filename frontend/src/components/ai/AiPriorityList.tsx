import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Edit2, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { PriorityRecommendation } from '../../types';
import StatusBadge from '../StatusBadge';
import { aiPriorityBadgeClass, aiPriorityLabel } from './aiPriorityUi';

const CACHE_KEY = 'crm_ai_priorities_v1';

interface Props {
  isOwner: boolean;
  onOpenLead: (leadId: number) => void;
  onProposalQueued?: () => void;
}

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function readSessionCache(): PriorityRecommendation[] | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { date: string; items: PriorityRecommendation[] };
    if (parsed.date !== todayKey()) return null;
    return parsed.items;
  } catch {
    return null;
  }
}

function writeSessionCache(items: PriorityRecommendation[]) {
  sessionStorage.setItem(CACHE_KEY, JSON.stringify({ date: todayKey(), items }));
}

export default function AiPriorityList({ isOwner, onOpenLead, onProposalQueued }: Props) {
  const { app } = useLocale();
  const t = app.ai;
  const c = app.common;
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<PriorityRecommendation[]>(() => readSessionCache() ?? []);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [queueBusy, setQueueBusy] = useState<number | null>(null);
  const [queueOk, setQueueOk] = useState<number | null>(null);

  useEffect(() => {
    if (!isOwner) return;
    let cancelled = false;
    api
      .getAiStatus()
      .then((status) => {
        if (cancelled) return;
        setEnabled(Boolean(status.priorities_available));
      })
      .catch(() => {
        if (!cancelled) setEnabled(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOwner]);

  const loadPriorities = useCallback(
    async (refresh: boolean) => {
      if (!enabled) return;
      setLoading(true);
      setError(null);
      try {
        const res = await api.getPriorities(10, refresh);
        setItems(res.recommendations);
        writeSessionCache(res.recommendations);
      } catch (err) {
        setError(err instanceof Error ? err.message : t.prioritiesFailed);
      } finally {
        setLoading(false);
      }
    },
    [enabled, t.prioritiesFailed],
  );

  useEffect(() => {
    if (!isOwner || !enabled) return;
    const cached = readSessionCache();
    if (cached?.length) {
      setItems(cached);
      return;
    }
    loadPriorities(false);
  }, [isOwner, enabled, loadPriorities]);

  if (!isOwner || !enabled) return null;

  const queueProposal = async (leadId: number) => {
    setQueueBusy(leadId);
    try {
      await api.createActionProposal(leadId);
      setQueueOk(leadId);
      onProposalQueued?.();
      window.setTimeout(() => setQueueOk((c) => (c === leadId ? null : c)), 2500);
    } catch {
      /* ignore */
    } finally {
      setQueueBusy(null);
    }
  };

  return (
    <section className="card overflow-hidden border-brand-100">
      <div className="border-b border-surface-200 bg-brand-50/35 px-4 py-3.5 sm:px-5 sm:py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div className="flex min-w-0 gap-3">
            <div className="brand-icon-box flex h-10 w-10 shrink-0 items-center justify-center sm:h-11 sm:w-11">
              <Sparkles size={20} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold text-surface-900 sm:text-base">{t.prioritiesTitle}</h2>
                {items.length > 0 ? (
                  <span className="rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-surface-800/70 shadow-sm">
                    {items.length}
                  </span>
                ) : null}
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-surface-800/60 sm:text-sm sm:leading-snug">
                {t.prioritiesHint}
              </p>
            </div>
          </div>
          <button
            type="button"
            disabled={loading}
            onClick={() => loadPriorities(true)}
            className="btn-secondary w-full shrink-0 justify-center px-4 py-2.5 text-sm sm:w-auto sm:py-2"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {t.prioritiesRefresh}
          </button>
        </div>
      </div>

      {loading && items.length === 0 ? (
        <div className="flex items-center justify-center gap-2 px-4 py-10 text-sm text-surface-800/50">
          <Loader2 size={18} className="animate-spin" />
          {t.prioritiesLoading}
        </div>
      ) : null}

      {error ? (
        <p className="border-b border-surface-100 px-4 py-3 text-sm text-rose-600 sm:px-5">{error}</p>
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-surface-800/50 sm:px-5">{t.prioritiesEmpty}</p>
      ) : null}

      {items.length > 0 ? (
        <ol className="divide-y divide-surface-100">
          {items.map((item, index) => (
            <li
              key={item.lead_id}
              className="flex items-start gap-2 px-3.5 py-3.5 transition hover:bg-surface-50/80 sm:gap-3 sm:px-5 sm:py-4"
            >
              <span
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-100 text-xs font-bold tabular-nums text-surface-800/55 sm:h-8 sm:w-8 sm:text-sm"
                aria-hidden
              >
                {index + 1}
              </span>
              <button
                type="button"
                onClick={() => onOpenLead(item.lead_id)}
                className="flex min-w-0 flex-1 flex-col gap-2 text-left sm:gap-2.5"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold leading-snug text-surface-900 sm:text-base">
                      {item.isletme_adi}
                    </p>
                    <p className="mt-0.5 text-xs text-surface-800/55 sm:text-sm">
                      {item.category_label || '—'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
                    <span className="rounded-lg bg-white px-2.5 py-1 text-xs font-medium tabular-nums text-surface-800 ring-1 ring-surface-200">
                      {t.scoreLabel}: {item.score}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${aiPriorityBadgeClass(item.priority)}`}
                    >
                      {aiPriorityLabel(item.priority, app.priorities)}
                    </span>
                  </div>
                </div>

                {item.durum ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge durum={item.durum} size="xs" />
                  </div>
                ) : null}

                {item.reasons.length > 0 ? (
                  <ul className="flex flex-col gap-1.5 sm:gap-2">
                    {item.reasons.slice(0, 3).map((r) => (
                      <li
                        key={r}
                        className="rounded-lg bg-surface-50 px-3 py-2 text-xs leading-relaxed text-surface-800/75 sm:text-sm"
                      >
                        {r}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </button>
              <div className="mt-0.5 flex shrink-0 flex-col gap-1 sm:flex-row">
                <button
                  type="button"
                  disabled={queueBusy === item.lead_id}
                  onClick={() => queueProposal(item.lead_id)}
                  className="rounded-lg p-2 text-surface-800/40 transition hover:bg-amber-50 hover:text-amber-700 sm:p-2.5"
                  title={t.proposalsQueue}
                >
                  {queueBusy === item.lead_id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : queueOk === item.lead_id ? (
                    <CheckCircle2 size={16} className="text-emerald-600" />
                  ) : (
                    <CheckCircle2 size={16} />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => onOpenLead(item.lead_id)}
                  className="rounded-lg p-2 text-surface-800/40 transition hover:bg-brand-50 hover:text-brand-500 sm:p-2.5"
                  title={c.edit}
                >
                  <Edit2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
