import { useCallback, useEffect, useState } from 'react';
import { Bot, Loader2 } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiActionItem, AiStatusResponse } from '../../types';

interface Props {
  isOwner: boolean;
  onOpenLead: (leadId: number) => void;
  refreshToken?: number;
}

const ACTIVE_STATUSES = new Set([
  'proposed',
  'approved',
  'executing',
  'executed',
  'failed',
  'cancelled',
  'expired',
]);

function formatActionType(actionType: string): string {
  return actionType.replace(/_/g, ' ');
}

function statusLabel(status: string, t: Record<string, string>): string {
  switch (status) {
    case 'proposed':
      return t.de4ActionsStatusProposed;
    case 'approved':
      return t.de4ActionsStatusApproved;
    case 'executing':
      return t.de4ActionsExecuting;
    case 'executed':
      return t.de4ActionsExecuted;
    case 'failed':
      return t.de4ActionsFailed;
    case 'cancelled':
      return t.de4ActionsCancelled;
    case 'expired':
      return t.de4ActionsExpired;
    default:
      return status;
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'approved':
      return 'bg-emerald-100 text-emerald-900';
    case 'executing':
      return 'bg-amber-100 text-amber-900';
    case 'executed':
      return 'bg-surface-100 text-surface-800';
    case 'failed':
      return 'bg-rose-100 text-rose-900';
    case 'cancelled':
    case 'expired':
      return 'bg-surface-100 text-surface-600';
    default:
      return 'bg-violet-100 text-violet-900';
  }
}

export default function AiDe4ActionsInbox({ isOwner, onOpenLead, refreshToken = 0 }: Props) {
  const { app } = useLocale();
  const t = app.ai;
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<AiActionItem[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmActionId, setConfirmActionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listAiActions('all');
      const filtered = res.items.filter((i) => ACTIVE_STATUSES.has(i.status));
      setItems(filtered);
    } catch {
      setError(t.de4ActionsErrorGeneric);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [t.de4ActionsErrorGeneric]);

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

  const safeError = () => setError(t.de4ActionsErrorGeneric);

  const approve = async (actionId: string) => {
    setBusyId(actionId);
    setError(null);
    try {
      await api.approveAiAction(actionId);
      await load();
    } catch {
      safeError();
    } finally {
      setBusyId(null);
    }
  };

  const execute = async (actionId: string) => {
    setConfirmActionId(null);
    setBusyId(actionId);
    setError(null);
    try {
      await api.executeAiAction(actionId);
      await load();
    } catch {
      safeError();
    } finally {
      setBusyId(null);
    }
  };

  if (!isOwner || !enabled) return null;

  if (!loading && items.length === 0 && !error) return null;

  const confirmItem = confirmActionId ? items.find((i) => i.action_id === confirmActionId) : null;

  return (
    <section className="card overflow-hidden border-violet-100">
      <div className="border-b border-violet-100 bg-violet-50/50 px-4 py-3.5 sm:px-5 sm:py-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-800">
            <Bot size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{t.de4ActionsTitle}</h3>
            <p className="mt-1 text-xs leading-relaxed text-surface-800/60 sm:text-sm">{t.de4ActionsHint}</p>
          </div>
          {items.length > 0 ? (
            <span className="ml-auto rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-violet-900 shadow-sm">
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
        <p className="px-4 py-6 text-center text-sm text-surface-800/50 sm:px-5">{t.de4ActionsEmpty}</p>
      ) : null}

      <ul className="divide-y divide-surface-100">
        {items.map((item) => {
          const leadLabel = item.lead_name || (item.target_entity_id ? `#${item.target_entity_id}` : '—');
          const rowBusy = busyId === item.action_id;
          const anyBusy = busyId !== null;
          const canApprove = item.status === 'proposed';
          const canExecute =
            item.status === 'approved' && item.execute_enabled_v1 === true;

          return (
            <li key={item.action_id} className="px-4 py-4 sm:px-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-violet-700/80">
                    {formatActionType(item.action_type)}
                  </p>
                  <button
                    type="button"
                    onClick={() => item.target_entity_id && onOpenLead(item.target_entity_id)}
                    className="mt-0.5 text-sm font-semibold text-brand-600 hover:underline"
                  >
                    {leadLabel}
                  </button>
                  {item.reason ? (
                    <p className="mt-1 text-xs leading-relaxed text-surface-800/70">{item.reason}</p>
                  ) : null}
                  {item.source_diagnosis_id ? (
                    <p className="mt-1 text-xs text-surface-800/50">
                      {t.de4ActionsSourceDiagnosis}: {item.source_diagnosis_id}
                    </p>
                  ) : null}
                  <p className="mt-1 text-xs text-surface-800/45">
                    {t.de4ActionsSuggestedAt}: {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
                  <span
                    className={`self-start rounded-full px-2 py-0.5 text-xs font-medium sm:self-end ${statusBadgeClass(item.status)}`}
                  >
                    {statusLabel(item.status, t as unknown as Record<string, string>)}
                  </span>
                  {item.status === 'executing' ? (
                    <span className="text-xs text-amber-800/80">{t.de4ActionsExecuting}</span>
                  ) : null}
                  {canApprove ? (
                    <button
                      type="button"
                      disabled={anyBusy}
                      onClick={() => approve(item.action_id)}
                      className="btn-secondary inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm"
                    >
                      {rowBusy ? <Loader2 size={16} className="animate-spin" /> : null}
                      {t.de4ActionsApprove}
                    </button>
                  ) : null}
                  {canExecute ? (
                    <button
                      type="button"
                      disabled={anyBusy}
                      onClick={() => setConfirmActionId(item.action_id)}
                      className="btn-primary inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm"
                    >
                      {rowBusy ? <Loader2 size={16} className="animate-spin" /> : null}
                      {t.de4ActionsExecute}
                    </button>
                  ) : null}
                  {item.status === 'proposed' && !item.execute_enabled_v1 ? (
                    <span className="text-xs text-surface-800/40">{t.de4ActionsExecuteSoon}</span>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {confirmItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg">
            <h4 className="text-base font-semibold text-surface-900">{t.de4ActionsConfirmExecuteTitle}</h4>
            <p className="mt-2 text-sm text-surface-800/70">{t.de4ActionsConfirmExecuteBody}</p>
            <p className="mt-2 text-xs text-surface-800/50">
              {formatActionType(confirmItem.action_type)} · {confirmItem.lead_name || confirmItem.target_entity_id}
            </p>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-secondary px-4 py-2 text-sm"
                onClick={() => setConfirmActionId(null)}
              >
                {t.de4ActionsConfirmCancel}
              </button>
              <button
                type="button"
                className="btn-primary px-4 py-2 text-sm"
                disabled={busyId === confirmItem.action_id}
                onClick={() => execute(confirmItem.action_id)}
              >
                {t.de4ActionsConfirmOk}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
