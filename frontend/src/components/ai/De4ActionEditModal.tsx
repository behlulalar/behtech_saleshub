import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiActionItem } from '../../types';
import { ACTIVITY_TYPE_OPTIONS, DURUM_STATUSES, ONCELIK_OPTIONS } from '../../types';
import { actionTypeLabel, isDe4UpdateSupported } from './de4ActionDisplay';

type Props = {
  item: AiActionItem;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

function strParam(params: Record<string, unknown>, key: string, fallback = ''): string {
  const v = params[key];
  return typeof v === 'string' ? v : v == null ? fallback : String(v);
}

export default function De4ActionEditModal({ item, onClose, onSaved }: Props) {
  const { app } = useLocale();
  const t = app.ai;
  const labels = t as unknown as Record<string, string>;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [note, setNote] = useState('');
  const [priority, setPriority] = useState('orta');
  const [targetStatus, setTargetStatus] = useState('Yeni');
  const [noteText, setNoteText] = useState('');
  const [separator, setSeparator] = useState('\n\n');
  const [activityType, setActivityType] = useState('takip_yapildi');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    const p = item.parameters || {};
    setNote(strParam(p, 'note'));
    setPriority(strParam(p, 'priority', 'orta'));
    setTargetStatus(strParam(p, 'target_status', DURUM_STATUSES[0]?.value ?? 'Yeni'));
    setNoteText(strParam(p, 'note_text'));
    setSeparator(strParam(p, 'separator', '\n\n'));
    setActivityType(strParam(p, 'activity_type', 'takip_yapildi'));
    setTitle(strParam(p, 'title'));
    setDescription(strParam(p, 'description'));
    setError(null);
  }, [item.action_id, item.parameters]);

  if (!isDe4UpdateSupported(item.action_type) || item.status !== 'proposed') {
    return null;
  }

  const buildParameters = (): Record<string, unknown> => {
    switch (item.action_type) {
      case 'propose_follow_up_task':
        return { note };
      case 'propose_priority_change':
        return { priority };
      case 'propose_status_change':
        return { target_status: targetStatus };
      case 'propose_note_append':
        return { note_text: noteText, separator };
      case 'propose_log_activity':
        return { activity_type: activityType, title, description };
      default:
        return {};
    }
  };

  const save = async () => {
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateAiAction(item.action_id, buildParameters());
      await onSaved();
      onClose();
    } catch {
      setError(t.de4ActionsErrorGeneric);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg">
        <h4 className="text-base font-semibold text-surface-900">{t.de4ActionsEditTitle}</h4>
        <p className="mt-1 text-xs text-surface-800/60">
          {actionTypeLabel(item.action_type, labels)} · {item.lead_name || item.target_entity_id}
        </p>

        <div className="mt-4 space-y-3">
          {item.action_type === 'propose_follow_up_task' ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldNote}</span>
              <textarea
                className="input-field min-h-[88px] w-full resize-y"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={400}
                disabled={saving}
              />
            </label>
          ) : null}

          {item.action_type === 'propose_priority_change' ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldPriority}</span>
              <select
                className="input-field w-full"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                disabled={saving}
              >
                {ONCELIK_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {app.priorities[o.value] ?? o.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {item.action_type === 'propose_status_change' ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldStatus}</span>
              <select
                className="input-field w-full"
                value={targetStatus}
                onChange={(e) => setTargetStatus(e.target.value)}
                disabled={saving}
              >
                {DURUM_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {item.action_type === 'propose_note_append' ? (
            <>
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldNoteText}</span>
                <textarea
                  className="input-field min-h-[100px] w-full resize-y"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  maxLength={4000}
                  disabled={saving}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldSeparator}</span>
                <input
                  className="input-field w-full font-mono text-xs"
                  value={separator}
                  onChange={(e) => setSeparator(e.target.value)}
                  maxLength={8}
                  disabled={saving}
                />
              </label>
            </>
          ) : null}

          {item.action_type === 'propose_log_activity' ? (
            <>
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldActivityType}</span>
                <select
                  className="input-field w-full"
                  value={activityType}
                  onChange={(e) => setActivityType(e.target.value)}
                  disabled={saving}
                >
                  {ACTIVITY_TYPE_OPTIONS.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldTitle}</span>
                <input
                  className="input-field w-full"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={255}
                  disabled={saving}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-surface-800/70">{t.de4ActionsFieldDescription}</span>
                <textarea
                  className="input-field min-h-[88px] w-full resize-y"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={2000}
                  disabled={saving}
                />
              </label>
            </>
          ) : null}
        </div>

        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}

        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-secondary px-4 py-2 text-sm" disabled={saving} onClick={onClose}>
            {t.de4ActionsConfirmCancel}
          </button>
          <button
            type="button"
            className="btn-primary inline-flex items-center gap-1.5 px-4 py-2 text-sm"
            disabled={saving}
            onClick={() => void save()}
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : null}
            {t.de4ActionsSave}
          </button>
        </div>
      </div>
    </div>
  );
}
