import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiActionItem, AiStatusResponse } from '../../types';
import De4ActionEditModal from './De4ActionEditModal';
import {
  actionTypeLabel,
  formatActionType,
  isDe4UpdateSupported,
  statusBadgeClass,
  statusLabel,
} from './de4ActionDisplay';
import { uniqueAiActionItems } from './de4ActionDedup';
import { groupAiActionsOperationally } from './de4ActionGrouping';

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

function paramPreview(item: AiActionItem): string {
  const p = item.parameters || {};
  const parts: string[] = [];
  for (const key of ['note', 'priority', 'target_status', 'note_text', 'title', 'activity_type']) {
    const v = p[key];
    if (typeof v === 'string' && v.trim()) {
      parts.push(`${key}: ${v.trim().slice(0, 80)}`);
    }
  }
  return parts.join(' · ');
}

export default function AiDe4ActionsInbox({ isOwner, onOpenLead, refreshToken = 0 }: Props) {
  const { app } = useLocale();
  const t = app.ai;
  const labels = t as unknown as Record<string, string>;
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<AiActionItem[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmExecuteId, setConfirmExecuteId] = useState<string | null>(null);
  const [confirmCancelId, setConfirmCancelId] = useState<string | null>(null);
  const [editItem, setEditItem] = useState<AiActionItem | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listAiActions('all');
      const filtered = res.items.filter((i) => ACTIVE_STATUSES.has(i.status));
      setItems(uniqueAiActionItems(filtered));
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

  const groups = useMemo(() => groupAiActionsOperationally(items), [items]);

  const safeError = () => setError(t.de4ActionsErrorGeneric);

  const approve = async (actionId: string) => {
    if (busyId) return;
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
    if (busyId) return;
    setConfirmExecuteId(null);
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

  const cancelAction = async (actionId: string) => {
    if (busyId) return;
    setConfirmCancelId(null);
    setBusyId(actionId);
    setError(null);
    try {
      await api.cancelAiAction(actionId);
      await load();
    } catch {
      safeError();
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

  if (!isOwner || !enabled) return null;

  if (!loading && items.length === 0 && !error) return null;

  const confirmExecuteItem = confirmExecuteId ? items.find((i) => i.action_id === confirmExecuteId) : null;
  const confirmCancelItem = confirmCancelId ? items.find((i) => i.action_id === confirmCancelId) : null;

  const renderActionRow = (item: AiActionItem) => {
    const rowBusy = busyId === item.action_id;
    const anyBusy = busyId !== null;
    const canApprove = item.status === 'proposed';
    const canEdit = item.status === 'proposed' && isDe4UpdateSupported(item.action_type);
    const canCancel = item.status === 'proposed';
    const canExecute = item.status === 'approved' && item.execute_enabled_v1 === true;
    const preview = paramPreview(item);

    return (
      <li key={item.action_id} className="rounded-lg border border-surface-100 bg-white px-3 py-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(item.status)}`}
              >
                {statusLabel(item.status, labels)}
              </span>
              <span className="text-xs text-surface-800/45">
                {t.de4ActionsSuggestedAt}: {new Date(item.created_at).toLocaleString()}
              </span>
            </div>
            {item.reason ? (
              <p className="mt-1 text-xs leading-relaxed text-surface-800/70">{item.reason}</p>
            ) : null}
            {preview ? <p className="mt-1 text-xs text-surface-800/55">{preview}</p> : null}
            {item.source_diagnosis_id ? (
              <p className="mt-1 text-xs text-surface-800/50">
                {t.de4ActionsSourceDiagnosis}: {item.source_diagnosis_id}
              </p>
            ) : null}
            {item.source_interpret_run_id ? (
              <p className="mt-0.5 text-xs text-surface-800/45">
                interpret run: {item.source_interpret_run_id}
              </p>
            ) : null}
            {item.status === 'executing' ? (
              <span className="mt-1 block text-xs text-amber-800/80">{t.de4ActionsExecuting}</span>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {canApprove ? (
              <button
                type="button"
                disabled={anyBusy}
                onClick={() => approve(item.action_id)}
                className="btn-secondary inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs"
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
                className="btn-secondary inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs"
              >
                {t.de4ActionsEdit}
              </button>
            ) : null}
            {canCancel ? (
              <button
                type="button"
                disabled={anyBusy}
                onClick={() => setConfirmCancelId(item.action_id)}
                className="btn-secondary inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs"
              >
                {t.de4ActionsCancelAction}
              </button>
            ) : null}
            {canExecute ? (
              <button
                type="button"
                disabled={anyBusy}
                onClick={() => setConfirmExecuteId(item.action_id)}
                className="btn-primary inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs"
              >
                {rowBusy ? <Loader2 size={14} className="animate-spin" /> : null}
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
  };

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
        {groups.map((group) => {
          const leadLabel =
            group.lead_name || (group.target_entity_id ? `#${group.target_entity_id}` : '—');
          const expanded = expandedKeys.has(group.key) || group.items.length === 1;
          const countLabel = t.de4ActionsGroupCount.replace('{count}', String(group.items.length));

          return (
            <li key={group.key} className="px-4 py-4 sm:px-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <button
                    type="button"
                    onClick={() => group.target_entity_id && onOpenLead(group.target_entity_id)}
                    className="text-sm font-semibold text-brand-600 hover:underline"
                  >
                    {leadLabel}
                  </button>
                  <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-violet-700/80">
                    {actionTypeLabel(group.action_type, labels)} · {countLabel}
                  </p>
                </div>
                {group.items.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => toggleGroup(group.key)}
                    className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
                  >
                    {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    {expanded ? t.de4ActionsGroupCollapse : t.de4ActionsGroupExpand}
                  </button>
                ) : null}
              </div>
              {expanded ? <ul className="mt-3 space-y-2">{group.items.map(renderActionRow)}</ul> : null}
            </li>
          );
        })}
      </ul>

      {confirmExecuteItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg">
            <h4 className="text-base font-semibold text-surface-900">{t.de4ActionsConfirmExecuteTitle}</h4>
            <p className="mt-2 text-sm text-surface-800/70">{t.de4ActionsConfirmExecuteBody}</p>
            <p className="mt-2 text-xs text-surface-800/50">
              {formatActionType(confirmExecuteItem.action_type)} ·{' '}
              {confirmExecuteItem.lead_name || confirmExecuteItem.target_entity_id}
            </p>
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
        <De4ActionEditModal item={editItem} onClose={() => setEditItem(null)} onSaved={load} />
      ) : null}
    </section>
  );
}
