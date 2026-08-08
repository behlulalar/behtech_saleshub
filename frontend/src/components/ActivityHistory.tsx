import { useEffect, useState } from 'react';
import {
  Calendar,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  Clock,
  Edit2,
  FileText,
  MessageSquare,
  Phone,
  Plus,
  Save,
  Send,
  UserCheck,
  X,
} from 'lucide-react';
import { api } from '../api';
import type { Activity, ActivityFormData } from '../types';
import { ACTIVITY_TYPE_OPTIONS } from '../types';

const activityIcons: Record<string, typeof MessageSquare> = {
  mesaj_gonderildi: MessageSquare,
  demo_gonderildi: Send,
  teklif_verildi: FileText,
  telefon_gorusmesi: Phone,
  gorusme_planlandi: CalendarClock,
  gorusme_yapildi: UserCheck,
  takip_yapildi: Clock,
  durum_degisti: CheckCircle2,
  satis_kaydedildi: CircleDollarSign,
  kayit_olusturuldu: Plus,
  diger: FileText,
};

const activityColors: Record<string, string> = {
  mesaj_gonderildi: 'bg-blue-100 text-blue-700',
  demo_gonderildi: 'bg-indigo-100 text-indigo-700',
  teklif_verildi: 'bg-cyan-100 text-cyan-700',
  telefon_gorusmesi: 'bg-emerald-100 text-emerald-700',
  gorusme_planlandi: 'bg-violet-100 text-violet-700',
  gorusme_yapildi: 'bg-purple-100 text-purple-700',
  takip_yapildi: 'bg-amber-100 text-amber-700',
  durum_degisti: 'bg-slate-100 text-slate-700',
  satis_kaydedildi: 'bg-emerald-100 text-emerald-700',
  kayit_olusturuldu: 'bg-brand-50 text-brand-500',
  diger: 'bg-gray-100 text-gray-600',
};

const EMPTY_ACTIVITY: ActivityFormData = {
  activity_type: 'mesaj_gonderildi',
  description: '',
  activity_date: new Date().toISOString().slice(0, 10),
};

interface Props {
  leadId: number;
  readOnly?: boolean;
}

function formatDate(value: string) {
  const date = new Date(value);
  return date.toLocaleDateString('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function toDateInput(value: string) {
  return value.slice(0, 10);
}

function activityToForm(activity: Activity): ActivityFormData {
  return {
    activity_type: activity.activity_type,
    description: activity.description,
    activity_date: toDateInput(activity.activity_date),
  };
}

function activityTypeOptions(currentType?: string) {
  if (!currentType || ACTIVITY_TYPE_OPTIONS.some((option) => option.id === currentType)) {
    return ACTIVITY_TYPE_OPTIONS;
  }
  return [{ id: currentType, label: currentType }, ...ACTIVITY_TYPE_OPTIONS];
}

export default function ActivityHistory({ leadId, readOnly = false }: Props) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState<ActivityFormData>(EMPTY_ACTIVITY);
  const [editForm, setEditForm] = useState<ActivityFormData>(EMPTY_ACTIVITY);

  const loadActivities = async () => {
    setLoading(true);
    try {
      setActivities(await api.getActivities(leadId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Aktiviteler yüklenemedi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivities().catch(console.error);
  }, [leadId]);

  const handleAddActivity = async () => {
    setSaving(true);
    setError('');
    try {
      const created = await api.createActivity(leadId, form);
      setActivities((prev) => [...prev, created]);
      setForm({ ...EMPTY_ACTIVITY, activity_date: new Date().toISOString().slice(0, 10) });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Aktivite eklenemedi');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (activity: Activity) => {
    setEditingId(activity.id);
    setEditForm(activityToForm(activity));
    setError('');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(EMPTY_ACTIVITY);
  };

  const handleUpdateActivity = async (activityId: number) => {
    setSaving(true);
    setError('');
    try {
      const updated = await api.updateActivity(leadId, activityId, editForm);
      setActivities((prev) => prev.map((item) => (item.id === activityId ? updated : item)));
      setEditingId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Aktivite güncellenemedi');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="mb-6">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
        <Clock size={16} /> Aktivite Geçmişi
      </h3>

      {!readOnly && (
      <div className="mb-4 rounded-xl border border-surface-200 bg-surface-50 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="label-field">Aktivite Türü</label>
            <select
              className="input-field"
              value={form.activity_type}
              onChange={(e) => setForm((prev) => ({ ...prev, activity_type: e.target.value }))}
            >
              {ACTIVITY_TYPE_OPTIONS.map((type) => (
                <option key={type.id} value={type.id}>{type.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label-field flex items-center gap-1">
              <Calendar size={12} /> Tarih
            </label>
            <input
              type="date"
              className="input-field"
              value={form.activity_date}
              onChange={(e) => setForm((prev) => ({ ...prev, activity_date: e.target.value }))}
            />
          </div>
          <div className="sm:col-span-1">
            <label className="label-field">Açıklama</label>
            <input
              className="input-field"
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Kısa not ekleyin..."
            />
          </div>
        </div>
        <div className="mt-3 flex justify-end">
          <button type="button" onClick={handleAddActivity} disabled={saving} className="btn-primary">
            <Plus size={16} />
            {saving && editingId === null ? 'Ekleniyor...' : 'Aktivite Ekle'}
          </button>
        </div>
      </div>
      )}

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-surface-800/50">Aktiviteler yükleniyor...</p>
      ) : activities.length === 0 ? (
        <p className="rounded-xl border border-dashed border-surface-200 py-8 text-center text-sm text-surface-800/50">
          Henüz aktivite kaydı yok. Yukarıdan manuel ekleyebilir veya kayıt güncelledikçe otomatik oluşur.
        </p>
      ) : (
        <div className="relative space-y-0">
          {activities.map((activity, index) => {
            const Icon = activityIcons[activity.activity_type] || FileText;
            const color = activityColors[activity.activity_type] || activityColors.diger;
            const isEditing = editingId === activity.id;

            return (
              <div key={activity.id} className="relative flex gap-4 pb-6">
                {index < activities.length - 1 && (
                  <span className="absolute left-[15px] top-8 h-full w-px bg-surface-200" />
                )}
                <div className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${color}`}>
                  <Icon size={14} />
                </div>
                <div className="min-w-0 flex-1 rounded-xl border border-surface-200 bg-white px-4 py-3">
                  {isEditing ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div>
                          <label className="label-field">Aktivite Türü</label>
                          <select
                            className="input-field"
                            value={editForm.activity_type}
                            onChange={(e) => setEditForm((prev) => ({ ...prev, activity_type: e.target.value }))}
                          >
                            {activityTypeOptions(activity.activity_type).map((type) => (
                              <option key={type.id} value={type.id}>{type.label}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="label-field flex items-center gap-1">
                            <Calendar size={12} /> Tarih
                          </label>
                          <input
                            type="date"
                            className="input-field"
                            value={editForm.activity_date}
                            onChange={(e) => setEditForm((prev) => ({ ...prev, activity_date: e.target.value }))}
                          />
                        </div>
                      </div>
                      <div>
                        <label className="label-field">Açıklama</label>
                        <input
                          className="input-field"
                          value={editForm.description}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                          placeholder="Kısa not..."
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={cancelEdit} className="btn-secondary px-3 py-1.5 text-xs">
                          <X size={14} />
                          İptal
                        </button>
                        <button
                          type="button"
                          onClick={() => handleUpdateActivity(activity.id)}
                          disabled={saving}
                          className="btn-primary px-3 py-1.5 text-xs"
                        >
                          <Save size={14} />
                          {saving ? 'Kaydediliyor...' : 'Kaydet'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <p className="font-medium text-surface-900">{activity.title}</p>
                        <div className="flex items-center gap-1">
                          <time className="text-xs text-surface-800/50">
                            {formatDate(activity.activity_date)}
                          </time>
                          {!readOnly && (
                            <button
                              type="button"
                              onClick={() => startEdit(activity)}
                              className="rounded-lg p-1.5 text-surface-800/40 transition hover:bg-brand-50 hover:text-brand-500"
                              title="Düzenle"
                            >
                              <Edit2 size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                      {activity.description && (
                        <p className="mt-1 text-sm text-surface-800/70">{activity.description}</p>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
