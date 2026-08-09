import { useEffect, useMemo, useState } from 'react';
import { Calendar, Clock, Save, X } from 'lucide-react';
import { api } from '../api';
import type { Category, Lead, LeadFormData } from '../types';
import { EMPTY_LEAD } from '../types';
import StatusSelect from './StatusSelect';

export type TaskType = 'gorusme' | 'demo' | 'takip';

export interface QuickTaskData {
  category: string;
  lead_id?: number;
  isletme_adi: string;
  gorev_tipi: TaskType;
  tarih: string;
  saat: string;
  durum: string;
  notlar: string;
}

const TASK_DEFAULTS: Record<TaskType, { durum: string; label: string }> = {
  gorusme: { durum: 'Görüşme Planlandı', label: 'Görüşme' },
  demo: { durum: 'Demo Gönderildi', label: 'Demo' },
  takip: { durum: 'Takip Bekliyor', label: 'Takip' },
};

interface Props {
  categories: Category[];
  onSave: (data: QuickTaskData) => Promise<void>;
  onClose: () => void;
  initialType?: TaskType;
  initialDate?: string;
  /** Pre-select category (e.g. current sidebar category). */
  defaultCategoryId?: string;
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

async function fetchLeadsForCategory(category: string): Promise<Lead[]> {
  const pageSize = 100;
  const first = await api.getLeads(category, undefined, undefined, undefined, undefined, undefined, 1, pageSize);
  const items = [...first.items];
  for (let page = 2; page <= first.total_pages; page += 1) {
    const next = await api.getLeads(
      category,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      page,
      pageSize,
    );
    items.push(...next.items);
  }
  return items.sort((a, b) => a.isletme_adi.localeCompare(b.isletme_adi, 'tr'));
}

export default function QuickTaskForm({
  categories,
  onSave,
  onClose,
  initialType = 'gorusme',
  initialDate,
  defaultCategoryId,
}: Props) {
  const initialCategory =
    defaultCategoryId && categories.some((c) => c.id === defaultCategoryId)
      ? defaultCategoryId
      : categories[0]?.id || '';

  const [form, setForm] = useState<QuickTaskData>({
    category: initialCategory,
    isletme_adi: '',
    gorev_tipi: initialType,
    tarih: initialDate || todayStr(),
    saat: '',
    durum: TASK_DEFAULTS[initialType].durum,
    notlar: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [categoryLeads, setCategoryLeads] = useState<Lead[]>([]);
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [leadsLoadError, setLeadsLoadError] = useState('');
  const [selectedLeadId, setSelectedLeadId] = useState<number | ''>('');

  useEffect(() => {
    if (categories.length && !form.category) {
      setForm((f) => ({ ...f, category: categories[0].id }));
    }
  }, [categories, form.category]);

  useEffect(() => {
    if (!form.category) {
      setCategoryLeads([]);
      setSelectedLeadId('');
      return;
    }

    let cancelled = false;
    setLeadsLoading(true);
    setLeadsLoadError('');
    setSelectedLeadId('');
    setForm((f) => ({ ...f, isletme_adi: '', lead_id: undefined }));

    fetchLeadsForCategory(form.category)
      .then((leads) => {
        if (cancelled) return;
        setCategoryLeads(leads);
      })
      .catch((err) => {
        if (!cancelled) {
          setCategoryLeads([]);
          setLeadsLoadError(err instanceof Error ? err.message : 'İşletmeler yüklenemedi');
        }
      })
      .finally(() => {
        if (!cancelled) setLeadsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [form.category]);

  const hasRegisteredLeads = categoryLeads.length > 0;

  const leadOptions = useMemo(
    () => categoryLeads.map((l) => ({ id: l.id, name: l.isletme_adi })),
    [categoryLeads],
  );

  const handleCategoryChange = (category: string) => {
    setForm((f) => ({ ...f, category, isletme_adi: '', lead_id: undefined }));
    setSelectedLeadId('');
  };

  const handleLeadSelect = (value: string) => {
    if (value === '') {
      setSelectedLeadId('');
      setForm((f) => ({ ...f, isletme_adi: '', lead_id: undefined }));
      return;
    }
    const id = Number(value);
    const lead = categoryLeads.find((l) => l.id === id);
    if (!lead) return;
    setSelectedLeadId(id);
    setForm((f) => ({ ...f, isletme_adi: lead.isletme_adi, lead_id: lead.id }));
  };

  const handleTypeChange = (type: TaskType) => {
    setForm((f) => ({ ...f, gorev_tipi: type, durum: TASK_DEFAULTS[type].durum }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.isletme_adi.trim()) {
      setError(hasRegisteredLeads ? 'Kayıtlı bir işletme seçin.' : 'İşletme adı zorunludur.');
      return;
    }
    if (hasRegisteredLeads && !form.lead_id) {
      setError('Kayıtlı bir işletme seçin.');
      return;
    }
    if (!form.category) {
      setError('Kategori seçin.');
      return;
    }
    if (!form.tarih) {
      setError('Tarih seçin.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kayıt başarısız');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-panel-static modal-panel-md max-h-[92dvh] overflow-y-auto lg:max-h-none">
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="text-lg font-semibold">Görev Ekle</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          <div>
            <label className="label-field">Kategori</label>
            <select
              className="input-field"
              value={form.category}
              onChange={(e) => handleCategoryChange(e.target.value)}
              required
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label-field">İşletme Adı *</label>
            {leadsLoading ? (
              <p className="text-sm text-surface-800/50">İşletmeler yükleniyor…</p>
            ) : leadsLoadError ? (
              <>
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{leadsLoadError}</p>
                <input
                  className="input-field mt-2"
                  value={form.isletme_adi}
                  onChange={(e) => setForm({ ...form, isletme_adi: e.target.value, lead_id: undefined })}
                  placeholder="Salon veya işletme adı"
                  required
                />
              </>
            ) : hasRegisteredLeads ? (
              <select
                className="input-field"
                value={selectedLeadId === '' ? '' : String(selectedLeadId)}
                onChange={(e) => handleLeadSelect(e.target.value)}
                required
              >
                <option value="">İşletme seçin</option>
                {leadOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
            ) : (
              <>
                <input
                  className="input-field"
                  value={form.isletme_adi}
                  onChange={(e) => setForm({ ...form, isletme_adi: e.target.value, lead_id: undefined })}
                  placeholder="Salon veya işletme adı"
                  required
                />
                <p className="mt-1 text-xs text-surface-800/50">
                  Bu kategoride kayıtlı işletme yok; yeni kayıt oluşturulur.
                </p>
              </>
            )}
          </div>

          <div>
            <label className="label-field">Görev Tipi</label>
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(TASK_DEFAULTS) as TaskType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleTypeChange(type)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                    form.gorev_tipi === type
                      ? 'border-brand-500 bg-brand-50 text-brand-500'
                      : 'border-surface-200 hover:bg-surface-50'
                  }`}
                >
                  {TASK_DEFAULTS[type].label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="label-field flex items-center gap-1">
              <Calendar size={12} /> Tarih *
            </label>
            <input
              type="date"
              className="input-field"
              value={form.tarih}
              onChange={(e) => setForm({ ...form, tarih: e.target.value })}
              required
            />
          </div>

          {form.gorev_tipi === 'gorusme' && (
            <div>
              <label className="label-field flex items-center gap-1">
                <Clock size={12} /> Görüşme Saati
              </label>
              <input
                type="time"
                className="input-field"
                value={form.saat}
                onChange={(e) => setForm({ ...form, saat: e.target.value })}
              />
            </div>
          )}

          <div>
            <label className="label-field">Durum</label>
            <StatusSelect
              value={form.durum}
              onChange={(durum) => setForm({ ...form, durum })}
            />
          </div>

          <div>
            <label className="label-field">Not (isteğe bağlı)</label>
            <textarea
              className="input-field min-h-[60px] resize-y"
              value={form.notlar}
              onChange={(e) => setForm({ ...form, notlar: e.target.value })}
              placeholder="Görev notu..."
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">
              İptal
            </button>
            <button type="submit" disabled={saving} className="btn-primary flex-1 justify-center">
              <Save size={16} />
              {saving ? 'Kaydediliyor...' : 'Görev Ekle'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function quickTaskToLeadData(task: QuickTaskData) {
  const base = { ...EMPTY_LEAD, isletme_adi: task.isletme_adi, durum: task.durum, notlar: task.notlar };

  if (task.gorev_tipi === 'gorusme') {
    return { ...base, gorusme_tarihi: task.tarih, gorusme_saati: task.saat };
  }
  if (task.gorev_tipi === 'demo') {
    return { ...base, demo_gonderildi: true, demo_tarihi: task.tarih };
  }
  return { ...base, takip_1: task.tarih + (task.notlar ? ` - ${task.notlar}` : '') };
}

export function applyQuickTaskToExistingLead(lead: Lead, task: QuickTaskData): LeadFormData {
  const {
    id: _id,
    category: _cat,
    created_at: _ca,
    updated_at: _ua,
    tags,
    ...rest
  } = lead;

  const base = {
    ...rest,
    oncelik: rest.oncelik || 'orta',
    satis_tutari: rest.satis_tutari || 0,
    satis_tarihi: rest.satis_tarihi || '',
    tag_ids: tags?.map((t) => t.id) || [],
    demo_gonderildi: rest.demo_gonderildi || rest.durum === 'Demo Gönderildi',
    isletme_adi: task.isletme_adi.trim(),
    durum: task.durum,
    notlar: task.notlar.trim() ? task.notlar.trim() : rest.notlar,
  };

  if (task.gorev_tipi === 'gorusme') {
    return { ...base, gorusme_tarihi: task.tarih, gorusme_saati: task.saat };
  }
  if (task.gorev_tipi === 'demo') {
    return {
      ...base,
      demo_gonderildi: true,
      demo_tarihi: task.tarih,
    };
  }
  const takipNote = task.notlar ? ` - ${task.notlar}` : '';
  return { ...base, takip_1: task.tarih + takipNote };
}
