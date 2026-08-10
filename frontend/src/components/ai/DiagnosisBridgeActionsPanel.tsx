import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiActionItem } from '../../types';
import De4ActionEditModal from './De4ActionEditModal';
import {
  actionTypeLabel,
  isDe4UpdateSupported,
  statusBadgeClass,
  statusLabel,
} from './de4ActionDisplay';
import { uniqueActionIds, uniqueAiActionItems } from './de4ActionDedup';
import { groupAiActionsOperationally } from './de4ActionGrouping';

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
  const [confirmExecuteId, setConfirmExecuteId] = useState<string | null>(null);
  const [confirmCancelId, setConfirmCancelId] = useState<string | null>(null);
  const [editItem, setEditItem] = useState<AiActionItem | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  const idsKey = uniqueActionIds(actionIds).join(',');

  const load = useCallback(async () => {
    const ids = uniqueActionIds(actionIds);
    if (ids.length === 0) {
      setItems([]);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const rows = await Promise.all(ids.map((id) => api.getAiAction(id)));
      setItems(uniqueAiActionItems(rows));
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

  const groups = useMemo(() => groupAiActionsOperationally(items), [items]);

  const afterMutation = async () => {
    await load();
    onLifecycleChange?.();
  };

  const approve = async (actionId: string) => {
    if (busyId) return;
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
    if (busyId) return;
    setConfirmExecuteId(null);
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

  const cancelAction = async (actionId: string) => {
    if (busyId) return;
    setConfirmCancelId(null);
    setBusyId(actionId);
    try {
      await api.cancelAiAction(actionId);
      await afterMutation();
    } catch {
      setError(true);
    } finally {
      setBusyId(null);
    }
  };

  const toggleGroup = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (actionIds.length === 0) return null;

  const confirmExecuteItem = confirmExecuteId ? items.find((i) => i.action_id === confirmExecuteId) : null;
  const confirmCancelItem = confirmCancelId ? items.find((i) => i.action_id === confirmCancelId) : null;

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

      {!loading && groups.length > 0 ? (
        <ul className="mt-3 space-y-3">
          {groups.map((group) => {
            const leadLabel =
              group.lead_name || (group.target_entity_id ? `#${group.target_entity_id}` : '—');
            const expanded = expandedKeys.has(group.key) || group.items.length === 1;
            const countLabel = t.de4ActionsGroupCount.replace('{count}', String(group.items.length));

            return (
              <li
                key={group.key}
                className="rounded-lg border border-surface-100 bg-violet-50/30 px-3 py-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-surface-900">
                      {actionTypeLabel(group.action_type, labels)} · {countLabel}
                    </p>
                    <button
                      type="button"
                      onClick={() => group.target_entity_id && onOpenLead?.(group.target_entity_id)}
                      className="mt-0.5 text-sm font-semibold text-brand-600 hover:underline"
                    >
                      {leadLabel}
                    </button>
                  </div>
                  {group.items.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => toggleGroup(group.key)}
                      className="btn-secondary inline-flex items-center gap-1 px-2 py-1 text-xs"
                    >
                      {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      {expanded ? t.de4ActionsGroupCollapse : t.de4ActionsGroupExpand}
                    </button>
                  ) : null}
                </div>

                {expanded ? (
                  <ul className="mt-2 space-y-2">
                    {group.items.map((item) => {
                      const rowBusy = busyId === item.action_id;
                      const anyBusy = busyId !== null;
                      const canApprove = item.status === 'proposed';
                      const canEdit = item.status === 'proposed' && isDe4UpdateSupported(item.action_type);
                      const canCancel = item.status === 'proposed';
                      const canExecute = item.status === 'approved' && item.execute_enabled_v1 === true;

                      return (
                        <li
                          key={item.action_id}
                          className="rounded-md border border-white/80 bg-white px-2.5 py-2"
                        >
                          {item.reason ? (
                            <p className="text-xs leading-relaxed text-surface-700">
                              <span className="font-medium text-surface-800">
                                {t.diagnosisInterpretBridgeReason}:{' '}
                              </span>
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
                            {canEdit ? (
                              <button
                                type="button"
                                disabled={anyBusy}
                                onClick={() => setEditItem(item)}
                                className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
                              >
                                {t.de4ActionsEdit}
                              </button>
                            ) : null}
                            {canCancel ? (
                              <button
                                type="button"
                                disabled={anyBusy}
                                onClick={() => setConfirmCancelId(item.action_id)}
                                className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
                              >
                                {t.de4ActionsCancelAction}
                              </button>
                            ) : null}
                            {canExecute ? (
                              <button
                                type="button"
                                disabled={anyBusy}
                                onClick={() => setConfirmExecuteId(item.action_id)}
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
              </li>
            );
          })}
        </ul>
      ) : null}

      {confirmExecuteItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg">
            <h4 className="text-base font-semibold text-surface-900">{t.de4ActionsConfirmExecuteTitle}</h4>
            <p className="mt-2 text-sm text-surface-800/70">{t.de4ActionsConfirmExecuteBody}</p>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-secondary px-4 py-2 text-sm"
                onClick={() => setConfirmExecuteId(null)}
              >
                {t.de4ActionsConfirmCancel}
              </button>
              <button
                type="button"
                className="btn-primary px-4 py-2 text-sm"
                disabled={busyId === confirmExecuteItem.action_id}
                onClick={() => execute(confirmExecuteItem.action_id)}
              >
                {t.de4ActionsConfirmOk}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {confirmCancelItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg">
            <h4 className="text-base font-semibold text-surface-900">{t.de4ActionsConfirmCancelTitle}</h4>
            <p className="mt-2 text-sm text-surface-800/70">{t.de4ActionsConfirmCancelBody}</p>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-secondary px-4 py-2 text-sm"
                onClick={() => setConfirmCancelId(null)}
              >
                {t.de4ActionsConfirmCancel}
              </button>
              <button
                type="button"
                className="btn-primary px-4 py-2 text-sm"
                disabled={busyId === confirmCancelItem.action_id}
                onClick={() => cancelAction(confirmCancelItem.action_id)}
              >
                {t.de4ActionsConfirmCancelOk}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {editItem ? (
        <De4ActionEditModal
          item={editItem}
          onClose={() => setEditItem(null)}
          onSaved={afterMutation}
        />
      ) : null}
    </div>
  );
}
