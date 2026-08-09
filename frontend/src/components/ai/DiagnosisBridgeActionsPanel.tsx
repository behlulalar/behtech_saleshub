import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiActionItem } from '../../types';
import {
  actionTypeLabel,
  statusBadgeClass,
  statusLabel,
} from './de4ActionDisplay';

type Props = {
  actionIds: string[];
  onOpenLead?: (leadId: number) => void;
  onLifecycleChange?: () => void;
};

export default function DiagnosisBridgeActionsPanel({
  actionIds,
  onOpenLead,
  onLifecycleChange,
}: Props) {
  const { app } = useLocale();
  const t = app.ai;
  const labels = t as unknown as Record<string, string>;

  const [items, setItems] = useState<AiActionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmActionId, setConfirmActionId] = useState<string | null>(null);

  const idsKey = actionIds.join(',');

  const load = useCallback(async () => {
    if (actionIds.length === 0) {
      setItems([]);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const rows = await Promise.all(actionIds.map((id) => api.getAiAction(id)));
      setItems(rows);
    } catch {
      setError(true);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [idsKey, actionIds]);

  useEffect(() => {
    void load();
  }, [load]);

  const afterMutation = async () => {
    await load();
    onLifecycleChange?.();
  };

  const approve = async (actionId: string) => {
    setBusyId(actionId);
    try {
      await api.approveAiAction(actionId);
      await afterMutation();
    } catch {
      setError(true);
    } finally {
      setBusyId(null);
    }
  };

  const execute = async (actionId: string) => {
    setConfirmActionId(null);
    setBusyId(actionId);
    try {
      await api.executeAiAction(actionId);
      await afterMutation();
    } catch {
      setError(true);
    } finally {
      setBusyId(null);
    }
  };

  if (actionIds.length === 0) return null;

  const confirmItem = confirmActionId ? items.find((i) => i.action_id === confirmActionId) : null;

  return (
    <div className="mt-4 rounded-lg border border-violet-200 bg-white p-3 shadow-sm">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-violet-800">
        {t.diagnosisInterpretBridgeTitle}
      </h4>
      <p className="mt-1 text-xs text-surface-700/80">{t.diagnosisInterpretBridgeHint}</p>

      {loading ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-surface-700">
          <Loader2 size={16} className="animate-spin text-violet-600" aria-hidden />
          {t.diagnosisInterpretBridgeLoading}
        </p>
      ) : null}

      {error ? (
        <p className="mt-2 text-xs text-rose-700">{t.de4ActionsErrorGeneric}</p>
      ) : null}

      {!loading && items.length > 0 ? (
        <ul className="mt-3 space-y-3">
          {items.map((item) => {
            const leadLabel =
              item.lead_name || (item.target_entity_id ? `#${item.target_entity_id}` : '—');
            const rowBusy = busyId === item.action_id;
            const anyBusy = busyId !== null;
            const canApprove = item.status === 'proposed';
            const canExecute = item.status === 'approved' && item.execute_enabled_v1 === true;

            return (
              <li
                key={item.action_id}
                className="rounded-lg border border-surface-100 bg-violet-50/30 px-3 py-3"
              >
                <p className="text-sm font-medium text-surface-900">
                  {actionTypeLabel(item.action_type, labels)}
                </p>
                <button
                  type="button"
                  onClick={() => item.target_entity_id && onOpenLead?.(item.target_entity_id)}
                  className="mt-0.5 text-sm font-semibold text-brand-600 hover:underline"
                >
                  {leadLabel}
                </button>
                {item.reason ? (
                  <p className="mt-1 text-xs leading-relaxed text-surface-700">
                    <span className="font-medium text-surface-800">{t.diagnosisInterpretBridgeReason}: </span>
                    {item.reason}
                  </p>
                ) : null}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(item.status)}`}
                  >
                    {statusLabel(item.status, labels)}
                  </span>
                  {canApprove ? (
                    <button
                      type="button"
                      disabled={anyBusy}
                      onClick={() => approve(item.action_id)}
                      className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
                    >
                      {rowBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                      {t.de4ActionsApprove}
                    </button>
                  ) : null}
                  {canExecute ? (
                    <button
                      type="button"
                      disabled={anyBusy}
                      onClick={() => setConfirmActionId(item.action_id)}
                      className="btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
                    >
                      {rowBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                      {t.de4ActionsExecute}
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {confirmItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg">
            <h4 className="text-base font-semibold text-surface-900">{t.de4ActionsConfirmExecuteTitle}</h4>
            <p className="mt-2 text-sm text-surface-800/70">{t.de4ActionsConfirmExecuteBody}</p>
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
    </div>
  );
}
