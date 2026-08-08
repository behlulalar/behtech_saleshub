import { useEffect, useState } from 'react';
import { Edit2, Plus, Save, Trash2, X } from 'lucide-react';
import { useConfirmDialog } from '../hooks/useConfirmDialog';
import { useLocale } from '../i18n/locale';
import type { Category, CategoryFormData } from '../types';
import { EMPTY_CATEGORY } from '../types';
import { CategoryIcon, ICON_OPTIONS } from '../icons';

interface Props {
  categories: Category[];
  onSave: (data: CategoryFormData, editingId?: string) => Promise<void>;
  onDelete: (category: Category) => Promise<void>;
  onClose: () => void;
}

export default function CategoryManager({ categories, onSave, onDelete, onClose }: Props) {
  const { app } = useLocale();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [editing, setEditing] = useState<Category | null>(null);
  const [form, setForm] = useState<CategoryFormData>(EMPTY_CATEGORY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (editing) {
      setForm({ label: editing.label, icon: editing.icon, id: editing.id });
    } else {
      setForm(EMPTY_CATEGORY);
    }
  }, [editing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.label.trim()) {
      setError('Kategori adı zorunludur.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await onSave(form, editing?.id);
      setEditing(null);
      setForm(EMPTY_CATEGORY);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kayıt başarısız');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (category: Category) => {
    const ok = await confirm({
      title: app.confirm.title,
      message: app.confirm.deleteCategory.replace('{name}', category.label),
      confirmLabel: app.confirm.delete,
      cancelLabel: app.confirm.cancel,
    });
    if (!ok) return;
    try {
      await onDelete(category);
      if (editing?.id === category.id) {
        setEditing(null);
        setForm(EMPTY_CATEGORY);
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
            <h2 className="text-lg font-semibold">Kategori Yönetimi</h2>
            <p className="text-xs text-surface-800/50">Kategorileri ekleyin, düzenleyin veya silin</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        <div className="grid gap-6 p-6 md:grid-cols-2">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-surface-800">Mevcut Kategoriler</h3>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {categories.length === 0 ? (
                <p className="text-sm text-surface-800/50">Henüz kategori yok.</p>
              ) : (
                categories.map((cat) => (
                  <div
                    key={cat.id}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2.5 ${
                      editing?.id === cat.id ? 'border-brand-500 bg-brand-50' : 'border-surface-200'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <CategoryIcon name={cat.icon} size={16} />
                      <div>
                        <p className="text-sm font-medium">{cat.label}</p>
                        <p className="text-xs text-surface-800/40">
                          {cat.lead_count ?? 0} kayıt
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => setEditing(cat)}
                        className="rounded-lg p-1.5 text-surface-800/60 hover:bg-surface-100 hover:text-brand-500"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(cat)}
                        className="rounded-lg p-1.5 text-surface-800/60 hover:bg-red-50 hover:text-red-600"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <h3 className="text-sm font-semibold text-surface-800">
              {editing ? 'Kategori Düzenle' : 'Yeni Kategori'}
            </h3>

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
            )}

            <div>
              <label className="label-field">Kategori Adı *</label>
              <input
                className="input-field"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder="Örn: Kuaförler"
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
              />
            </div>

            <div>
              <label className="label-field">İkon</label>
              <div className="grid grid-cols-4 gap-2">
                {ICON_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setForm({ ...form, icon: opt.id })}
                    className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-xs transition ${
                      form.icon === opt.id
                        ? 'border-brand-500 bg-brand-50 text-brand-500'
                        : 'border-surface-200 hover:bg-surface-50'
                    }`}
                  >
                    <CategoryIcon name={opt.id} size={18} />
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              {editing && (
                <button
                  type="button"
                  onClick={() => {
                    setEditing(null);
                    setForm(EMPTY_CATEGORY);
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
