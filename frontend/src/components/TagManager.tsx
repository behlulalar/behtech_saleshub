import { useEffect, useState } from 'react';
import { Edit2, Plus, Save, Trash2, X } from 'lucide-react';
import { useConfirmDialog } from '../hooks/useConfirmDialog';
import { useLocale } from '../i18n/locale';
import type { Tag, TagFormData } from '../types';
import { EMPTY_TAG, TAG_COLOR_CLASSES, TAG_COLOR_OPTIONS } from '../types';

interface Props {
  tags: Tag[];
  onSave: (data: TagFormData, editingId?: string) => Promise<void>;
  onDelete: (tag: Tag) => Promise<void>;
  onClose: () => void;
}

export default function TagManager({ tags, onSave, onDelete, onClose }: Props) {
  const { app } = useLocale();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [editing, setEditing] = useState<Tag | null>(null);
  const [form, setForm] = useState<TagFormData>(EMPTY_TAG);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (editing) {
      setForm({ label: editing.label, color: editing.color, id: editing.id });
    } else {
      setForm(EMPTY_TAG);
    }
  }, [editing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.label.trim()) {
      setError('Etiket adı zorunludur.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await onSave(form, editing?.id);
      setEditing(null);
      setForm(EMPTY_TAG);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kayıt başarısız');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (tag: Tag) => {
    if (tag.is_system) return;
    const ok = await confirm({
      title: app.confirm.title,
      message: app.confirm.deleteTag.replace('{name}', tag.label),
      confirmLabel: app.confirm.delete,
      cancelLabel: app.confirm.cancel,
    });
    if (!ok) return;
    try {
      await onDelete(tag);
      if (editing?.id === tag.id) {
        setEditing(null);
        setForm(EMPTY_TAG);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Silme başarısız');
    }
  };

  return (
    <div className="modal-overlay-scroll">
      <div className="modal-panel-static modal-panel-lg max-h-[92dvh] overflow-y-auto lg:max-h-none">
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold">Etiket Yönetimi</h2>
            <p className="text-xs text-surface-800/50">İşletmeleri özel etiketlerle sınıflandırın</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        <div className="grid gap-6 p-6 md:grid-cols-2">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-surface-800">Mevcut Etiketler</h3>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {tags.length === 0 ? (
                <p className="text-sm text-surface-800/50">Henüz etiket yok.</p>
              ) : (
                tags.map((tag) => (
                  <div
                    key={tag.id}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2.5 ${
                      editing?.id === tag.id ? 'border-brand-500 bg-brand-50' : 'border-surface-200'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          TAG_COLOR_CLASSES[tag.color] || TAG_COLOR_CLASSES.slate
                        }`}
                      >
                        {tag.label}
                      </span>
                      <p className="text-xs text-surface-800/40">
                        {tag.lead_count ?? 0} kayıt
                        {tag.is_system ? ' · varsayılan' : ''}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => setEditing(tag)}
                        className="rounded-lg p-1.5 text-surface-800/60 hover:bg-surface-100 hover:text-brand-500"
                      >
                        <Edit2 size={14} />
                      </button>
                      {!tag.is_system && (
                        <button
                          onClick={() => handleDelete(tag)}
                          className="rounded-lg p-1.5 text-surface-800/60 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <h3 className="text-sm font-semibold text-surface-800">
              {editing ? 'Etiket Düzenle' : 'Yeni Etiket'}
            </h3>

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
            )}

            <div>
              <label className="label-field">Etiket Adı *</label>
              <input
                className="input-field"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder="Örn: Potansiyel Müşteri"
                required
              />
            </div>

            <div>
              <label className="label-field">Kimlik (isteğe bağlı)</label>
              <input
                className="input-field"
                value={form.id || ''}
                onChange={(e) => setForm({ ...form, id: e.target.value })}
                placeholder="Boş bırakılırsa otomatik oluşur"
                disabled={editing?.is_system}
              />
            </div>

            <div>
              <label className="label-field">Renk</label>
              <div className="grid grid-cols-5 gap-2">
                {TAG_COLOR_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setForm({ ...form, color: opt.id })}
                    className={`rounded-lg border p-2 text-xs transition ${
                      form.color === opt.id
                        ? 'border-brand-500 ring-2 ring-brand-200'
                        : 'border-surface-200 hover:bg-surface-50'
                    }`}
                    title={opt.label}
                  >
                    <span
                      className={`block h-5 w-full rounded ${
                        TAG_COLOR_CLASSES[opt.id]?.split(' ')[0] || 'bg-slate-100'
                      }`}
                    />
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-surface-800/50">
                Önizleme:{' '}
                <span
                  className={`rounded-full px-2 py-0.5 font-medium ${
                    TAG_COLOR_CLASSES[form.color] || TAG_COLOR_CLASSES.slate
                  }`}
                >
                  {form.label || 'Etiket'}
                </span>
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              {editing && (
                <button
                  type="button"
                  onClick={() => {
                    setEditing(null);
                    setForm(EMPTY_TAG);
                    setError('');
                  }}
                  className="btn-secondary flex-1 justify-center"
                >
                  İptal
                </button>
              )}
              <button type="submit" disabled={saving} className="btn-primary flex-1 justify-center">
                {editing ? <Save size={16} /> : <Plus size={16} />}
                {saving ? 'Kaydediliyor...' : editing ? 'Güncelle' : 'Ekle'}
              </button>
            </div>
          </form>
        </div>
      </div>
      {confirmDialog}
    </div>
  );
}
