import { useEffect, useState } from 'react';
import {
  Building2,
  Calendar,
  Check,
  Clock,
  FileText,
  Instagram,
  Mail,
  MessageCircle,
  Phone,
  Save,
  Tag,
  User,
  X,
} from 'lucide-react';
import type { Category, LeadRequestFormData, Tag as TagType } from '../types';
import { EMPTY_LEAD_REQUEST, ILETISIM_KANALLARI, TAG_COLOR_CLASSES } from '../types';
import PrioritySelect from './PrioritySelect';
import StatusSelect from './StatusSelect';

interface Props {
  categories: Category[];
  tags: TagType[];
  defaultCategory?: string;
  onSave: (data: LeadRequestFormData) => Promise<void>;
  onClose: () => void;
}

function Field({
  label,
  icon: Icon,
  children,
}: {
  label: string;
  icon?: typeof User;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label-field mb-1 flex items-center gap-1">
        {Icon && <Icon size={12} />}
        {label}
      </label>
      {children}
    </div>
  );
}

export default function RequestForm({ categories, tags, defaultCategory, onSave, onClose }: Props) {
  const [form, setForm] = useState<LeadRequestFormData>({
    ...EMPTY_LEAD_REQUEST,
    category: defaultCategory || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (defaultCategory) {
      setForm((prev) => ({ ...prev, category: defaultCategory }));
    }
  }, [defaultCategory]);

  const update = (key: keyof LeadRequestFormData, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleTag = (tagId: string) => {
    setForm((prev) => ({
      ...prev,
      tag_ids: prev.tag_ids.includes(tagId)
        ? prev.tag_ids.filter((id) => id !== tagId)
        : [...prev.tag_ids, tagId],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.category) {
      setError('Kategori seçin');
      return;
    }
    if (!form.isletme_adi.trim()) {
      setError('İşletme adı zorunludur');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Talep gönderilemedi');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <form onSubmit={handleSubmit} className="modal-panel modal-panel-lg">
        <div className="flex shrink-0 items-center justify-between border-b border-surface-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-surface-900">Müşteri Talebi Oluştur</h2>
            <p className="text-xs text-surface-800/50">
              Pazar araştırması sonucu bilgileri girin; onay sonrası kategoriye eklenir.
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {error && (
            <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <Building2 size={16} /> Temel Bilgiler
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Kategori">
                <select
                  className="input-field"
                  value={form.category}
                  onChange={(e) => update('category', e.target.value)}
                  required
                >
                  <option value="">Seçiniz</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="İşletme Adı" icon={Building2}>
                <input
                  className="input-field"
                  value={form.isletme_adi}
                  onChange={(e) => update('isletme_adi', e.target.value)}
                  required
                />
              </Field>
              <Field label="Yetkili" icon={User}>
                <input
                  className="input-field"
                  value={form.yetkili}
                  onChange={(e) => update('yetkili', e.target.value)}
                />
              </Field>
              <Field label="Şehir">
                <input
                  className="input-field"
                  value={form.sehir}
                  onChange={(e) => update('sehir', e.target.value)}
                />
              </Field>
              <Field label="Durum">
                <StatusSelect value={form.durum} onChange={(durum) => update('durum', durum)} />
              </Field>
            </div>
            <div className="mt-4">
              <label className="label-field mb-2 block">Öncelik</label>
              <PrioritySelect value={form.oncelik} onChange={(oncelik) => update('oncelik', oncelik)} />
            </div>
          </section>

          {tags.length > 0 && (
            <section className="mb-6">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
                <Tag size={16} /> Etiketler
              </h3>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => {
                  const selected = form.tag_ids.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => toggleTag(tag.id)}
                      className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                        selected
                          ? TAG_COLOR_CLASSES[tag.color] || TAG_COLOR_CLASSES.slate
                          : 'border border-surface-200 bg-white text-surface-800/60 hover:bg-surface-50'
                      }`}
                    >
                      {tag.label}
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <Phone size={16} /> İletişim
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Instagram" icon={Instagram}>
                <input
                  className="input-field"
                  value={form.instagram}
                  onChange={(e) => update('instagram', e.target.value)}
                  placeholder="@kullaniciadi"
                />
              </Field>
              <Field label="WhatsApp / Telefon" icon={MessageCircle}>
                <input
                  className="input-field"
                  value={form.whatsapp}
                  onChange={(e) => update('whatsapp', e.target.value)}
                />
              </Field>
              <Field label="E-posta" icon={Mail}>
                <input
                  type="email"
                  className="input-field"
                  value={form.eposta}
                  onChange={(e) => update('eposta', e.target.value)}
                  placeholder="ornek@firma.com"
                />
              </Field>
              <Field label="İlk İletişim Kanalı">
                <select
                  className="input-field"
                  value={form.ilk_iletisim_kanali}
                  onChange={(e) => update('ilk_iletisim_kanali', e.target.value)}
                >
                  <option value="">Seçiniz</option>
                  {ILETISIM_KANALLARI.map((k) => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
              </Field>
              <Field label="İlk Mesaj Tarihi" icon={Calendar}>
                <input
                  type="date"
                  className="input-field"
                  value={form.ilk_mesaj_tarihi}
                  onChange={(e) => update('ilk_mesaj_tarihi', e.target.value)}
                />
              </Field>
              <Field label="İlk Mesaj Saati" icon={Clock}>
                <input
                  type="time"
                  className="input-field"
                  value={form.ilk_mesaj_saati}
                  onChange={(e) => update('ilk_mesaj_saati', e.target.value)}
                />
              </Field>
            </div>
          </section>

          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <Calendar size={16} /> Süreç Bilgileri
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Takip 1">
                <input className="input-field" value={form.takip_1} onChange={(e) => update('takip_1', e.target.value)} />
              </Field>
              <Field label="Takip 2">
                <input className="input-field" value={form.takip_2} onChange={(e) => update('takip_2', e.target.value)} />
              </Field>
              <Field label="Demo Tarihi" icon={Calendar}>
                <input type="date" className="input-field" value={form.demo_tarihi} onChange={(e) => update('demo_tarihi', e.target.value)} />
              </Field>
              <Field label="Görüşme Tarihi" icon={Calendar}>
                <input type="date" className="input-field" value={form.gorusme_tarihi} onChange={(e) => update('gorusme_tarihi', e.target.value)} />
              </Field>
              <Field label="Görüşme Saati" icon={Clock}>
                <input type="time" className="input-field" value={form.gorusme_saati} onChange={(e) => update('gorusme_saati', e.target.value)} />
              </Field>
              <Field label="Teklif">
                <input className="input-field" value={form.teklif} onChange={(e) => update('teklif', e.target.value)} />
              </Field>
              <Field label="Sonuç">
                <input className="input-field" value={form.sonuc} onChange={(e) => update('sonuc', e.target.value)} />
              </Field>
              <div className="flex items-center gap-3 sm:col-span-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.demo_gonderildi}
                    onChange={(e) => update('demo_gonderildi', e.target.checked)}
                    className="h-4 w-4 rounded border-surface-200 text-brand-500 focus:ring-brand-500"
                  />
                  <Check size={14} className="text-surface-800/50" />
                  Demo Gönderildi
                </label>
              </div>
            </div>
          </section>

          <section>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <FileText size={16} /> Notlar
            </h3>
            <textarea
              className="input-field min-h-[90px]"
              value={form.notlar}
              onChange={(e) => update('notlar', e.target.value)}
              placeholder="Pazar araştırması notları..."
            />
          </section>
        </div>

        <div className="flex shrink-0 justify-end gap-2 border-t border-surface-200 px-5 py-3">
          <button type="button" onClick={onClose} className="btn-secondary">İptal</button>
          <button type="submit" disabled={saving} className="btn-primary">
            <Save size={16} />
            {saving ? 'Gönderiliyor...' : 'Talebi Gönder'}
          </button>
        </div>
      </form>
    </div>
  );
}
