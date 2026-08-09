import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Edit2,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
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
  const [sectionOpen, setSectionOpen] = useState(true);
  const [expandedLeadId, setExpandedLeadId] = useState<number | null>(null);

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
      window.setTimeout(() => setQueueOk((cur) => (cur === leadId ? null : cur)), 2500);
    } catch {
      /* ignore */
    } finally {
      setQueueBusy(null);
    }
  };

  const toggleCard = (leadId: number) => {
    setExpandedLeadId((cur) => (cur === leadId ? null : leadId));
  };

  return (
    <section className="card overflow-hidden border-brand-100">
      <div className="border-b border-surface-200 bg-brand-50/35 px-3 py-2.5 sm:px-4 sm:py-3">
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => setSectionOpen((open) => !open)}
            className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg text-left transition hover:bg-white/50 sm:gap-3 sm:px-1 sm:py-0.5"
            aria-expanded={sectionOpen}
          >
            <div className="brand-icon-box flex h-9 w-9 shrink-0 items-center justify-center sm:h-10 sm:w-10">
              <Sparkles size={18} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold text-surface-900 sm:text-base">{t.prioritiesTitle}</h2>
                {items.length > 0 ? (
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium tabular-nums text-surface-800/70 shadow-sm">
                    {items.length}
                  </span>
                ) : null}
              </div>
              {sectionOpen ? (
                <p className="mt-1 hidden text-xs leading-relaxed text-surface-800/60 sm:block sm:text-sm sm:leading-snug">
                  {t.prioritiesHint}
                </p>
              ) : null}
            </div>
            <span className="shrink-0 text-surface-800/45" aria-hidden>
              {sectionOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </span>
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => loadPriorities(true)}
            className="btn-secondary shrink-0 px-2.5 py-2 text-sm sm:px-3"
            title={t.prioritiesRefresh}
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            <span className="hidden sm:inline">{t.prioritiesRefresh}</span>
          </button>
        </div>
        {sectionOpen ? (
          <p className="mt-2 pl-11 text-xs leading-relaxed text-surface-800/60 sm:hidden">{t.prioritiesHint}</p>
        ) : null}
      </div>

      {sectionOpen ? (
        <>
          {loading && items.length === 0 ? (
            <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-surface-800/50">
              <Loader2 size={18} className="animate-spin" />
              {t.prioritiesLoading}
            </div>
          ) : null}

          {error ? (
            <p className="border-b border-surface-100 px-4 py-2.5 text-sm text-rose-600 sm:px-5">{error}</p>
          ) : null}

          {!loading && !error && items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-surface-800/50 sm:px-5">{t.prioritiesEmpty}</p>
          ) : null}

          {items.length > 0 ? (
            <ol className="divide-y divide-surface-100">
              {items.map((item, index) => {
                const expanded = expandedLeadId === item.lead_id;
                return (
                  <li key={item.lead_id} className="px-3 py-2 sm:px-4">
                    <div className="flex items-center gap-2">
                      <span
                        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface-100 text-[11px] font-bold tabular-nums text-surface-800/50"
                        aria-hidden
                      >
                        {index + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => toggleCard(item.lead_id)}
                        className="flex min-w-0 flex-1 items-center gap-2 rounded-lg py-1 text-left transition hover:bg-surface-50 sm:gap-3"
                        aria-expanded={expanded}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-surface-900">{item.isletme_adi}</p>
                          <p className="truncate text-xs text-surface-800/50">
                            {item.category_label || '—'}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span className="hidden rounded-md bg-surface-50 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-surface-800/70 ring-1 ring-surface-200/80 sm:inline">
                            {item.score}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold sm:text-xs ${aiPriorityBadgeClass(item.priority)}`}
                          >
                            {aiPriorityLabel(item.priority, app.priorities)}
                          </span>
                          <span className="text-surface-800/35" aria-hidden>
                            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </span>
                        </div>
                      </button>
                      <div className="flex shrink-0 items-center gap-0.5">
                        <button
                          type="button"
                          disabled={queueBusy === item.lead_id}
                          onClick={() => queueProposal(item.lead_id)}
                          className="rounded-md p-1.5 text-surface-800/40 transition hover:bg-amber-50 hover:text-amber-700"
                          title={t.proposalsQueue}
                        >
                          {queueBusy === item.lead_id ? (
                            <Loader2 size={15} className="animate-spin" />
                          ) : queueOk === item.lead_id ? (
                            <CheckCircle2 size={15} className="text-emerald-600" />
                          ) : (
                            <CheckCircle2 size={15} />
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => onOpenLead(item.lead_id)}
                          className="rounded-md p-1.5 text-surface-800/40 transition hover:bg-brand-50 hover:text-brand-500"
                          title={c.edit}
                        >
                          <Edit2 size={15} />
                        </button>
                      </div>
                    </div>

                    {expanded ? (
                      <div className="mt-2 space-y-2 border-l-2 border-brand-100 pl-8 sm:pl-9">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-surface-800/65">
                          <span className="tabular-nums sm:hidden">
                            {t.scoreLabel}: {item.score}
                          </span>
                          {item.durum ? <StatusBadge durum={item.durum} size="xs" /> : null}
                        </div>
                        {item.reasons.length > 0 ? (
                          <ul className="space-y-1 text-xs leading-relaxed text-surface-800/70">
                            {item.reasons.slice(0, 3).map((r) => (
                              <li key={r} className="flex gap-2">
                                <span className="text-surface-800/30" aria-hidden>
                                  ·
                                </span>
                                <span>{r}</span>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => onOpenLead(item.lead_id)}
                          className="text-xs font-medium text-brand-600 hover:underline"
                        >
                          {t.prioritiesOpenLead}
                        </button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
