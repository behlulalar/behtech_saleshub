import { useCallback, useEffect, useState } from 'react';
import { Check, ClipboardList, Loader2, X } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { ActionProposalItem, AiStatusResponse } from '../../types';

interface Props {
  isOwner: boolean;
  onOpenLead: (leadId: number) => void;
  refreshToken?: number;
  onApproved?: () => void;
}

function actionLabel(proposedAction: string, t: { proposalsActionAccept: string }): string {
  if (proposedAction === 'accept_recommendation') return t.proposalsActionAccept;
  return proposedAction;
}

export default function AiActionProposals({ isOwner, onOpenLead, refreshToken = 0, onApproved }: Props) {
  const { app } = useLocale();
  const t = app.ai;
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<ActionProposalItem[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listActionProposals('pending');
      setItems(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '—');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isOwner) return;
    let cancelled = false;
    api
      .getAiStatus()
      .then((status: AiStatusResponse) => {
        if (!cancelled) setEnabled(Boolean(status.enabled));
      })
      .catch(() => {
        if (!cancelled) setEnabled(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOwner]);

  useEffect(() => {
    if (!isOwner || !enabled) return;
    load();
  }, [isOwner, enabled, load, refreshToken]);

  if (!isOwner || !enabled) return null;

  const resolve = async (id: number, approve: boolean, leadId?: number | null) => {
    setBusyId(id);
    try {
      await api.resolveActionProposal(id, approve);
      await load();
      if (approve) {
        onApproved?.();
        if (leadId) onOpenLead(leadId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '—');
    } finally {
      setBusyId(null);
    }
  };

  if (!loading && items.length === 0 && !error) return null;

  return (
    <section className="card overflow-hidden border-amber-100">
      <div className="border-b border-amber-100 bg-amber-50/50 px-4 py-3.5 sm:px-5 sm:py-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-800">
            <ClipboardList size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{t.proposalsTitle}</h3>
            <p className="mt-1 text-xs leading-relaxed text-surface-800/60 sm:text-sm">{t.proposalsHint}</p>
          </div>
          {items.length > 0 ? (
            <span className="ml-auto rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-amber-900 shadow-sm">
              {items.length}
            </span>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-surface-800/50">
          <Loader2 size={18} className="animate-spin" />
        </div>
      ) : null}

      {error ? <p className="px-4 py-3 text-sm text-rose-600 sm:px-5">{error}</p> : null}

      {!loading && items.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-surface-800/50 sm:px-5">{t.proposalsEmpty}</p>
      ) : null}

      <ul className="divide-y divide-surface-100">
        {items.map((item) => {
          const name =
            item.lead_name ||
            (typeof item.payload.isletme_adi === 'string' ? item.payload.isletme_adi : null) ||
            `#${item.lead_id ?? '?'}`;
          const score = item.payload.score;
          return (
            <li key={item.id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:px-5">
              <button
                type="button"
                onClick={() => item.lead_id && onOpenLead(item.lead_id)}
                className="min-w-0 flex-1 text-left"
              >
                <p className="text-sm font-semibold text-brand-600 hover:underline">{name}</p>
                <p className="mt-0.5 text-xs text-surface-800/60">
                  {actionLabel(item.proposed_action, t)}
                  {typeof score === 'number' ? ` · ${app.ai.scoreLabel}: ${score}` : ''}
                </p>
              </button>
              <div className="flex flex-wrap gap-2 sm:shrink-0">
                <button
                  type="button"
                  disabled={busyId === item.id}
                  onClick={() => resolve(item.id, true, item.lead_id)}
                  className="btn-primary inline-flex flex-1 items-center justify-center gap-1.5 px-3 py-2 text-sm sm:flex-none"
                >
                  {busyId === item.id ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                  {t.proposalsApprove}
                </button>
                <button
                  type="button"
                  disabled={busyId === item.id}
                  onClick={() => resolve(item.id, false)}
                  className="btn-secondary inline-flex flex-1 items-center justify-center gap-1.5 px-3 py-2 text-sm sm:flex-none"
                >
                  <X size={16} />
                  {t.proposalsReject}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
