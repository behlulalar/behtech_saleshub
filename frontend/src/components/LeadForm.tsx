import { useEffect, useState } from 'react';
import {
  Building2,
  Calendar,
  Check,
  CircleDollarSign,
  Clock,
  FileText,
  Instagram,
  LucideIcon,
  Mail,
  MessageCircle,
  Phone,
  Save,
  Tag,
  User,
  X,
} from 'lucide-react';
import type { Lead, LeadFormData, Tag as TagType } from '../types';
import { EMPTY_LEAD, ILETISIM_KANALLARI, TAG_COLOR_CLASSES } from '../types';
import ActivityHistory from './ActivityHistory';
import PrioritySelect from './PrioritySelect';
import StatusSelect from './StatusSelect';

interface Props {
  lead?: Lead | null;
  tags: TagType[];
  onSave: (data: LeadFormData) => Promise<void>;
  onClose: () => void;
}

export default function LeadForm({ lead, tags, onSave, onClose }: Props) {
  const [form, setForm] = useState<LeadFormData>(EMPTY_LEAD);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'bilgiler' | 'aktiviteler'>('bilgiler');

  useEffect(() => {
    if (lead) {
      const {
        id: _,
        category: __,
        created_at: ___,
        updated_at: ____,
        tags: leadTags,
        ...rest
      } = lead;
      setForm({
        ...rest,
        oncelik: rest.oncelik || 'orta',
        satis_tutari: rest.satis_tutari || 0,
        satis_tarihi: rest.satis_tarihi || '',
        tag_ids: leadTags?.map((t) => t.id) || [],
        demo_gonderildi: rest.demo_gonderildi || rest.durum === 'Demo Gönderildi',
      });
      setTab('bilgiler');
    } else {
      setForm(EMPTY_LEAD);
      setTab('bilgiler');
    }
  }, [lead]);

  const toggleTag = (tagId: string) => {
    setForm((prev) => ({
      ...prev,
      tag_ids: prev.tag_ids.includes(tagId)
        ? prev.tag_ids.filter((id) => id !== tagId)
        : [...prev.tag_ids, tagId],
    }));
  };

  const update = (key: keyof LeadFormData, value: string | boolean | number) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleDemo = (checked: boolean) => {
    setForm((prev) => {
      const earlyStatuses = new Set(['Yeni', 'İletişime Geçildi', 'Takip Bekliyor', 'Cevap Yok']);
      return {
        ...prev,
        demo_gonderildi: checked,
        durum: checked
          ? earlyStatuses.has(prev.durum) ? 'Demo Gönderildi' : prev.durum
          : prev.durum === 'Demo Gönderildi' ? 'Takip Bekliyor' : prev.durum,
        demo_tarihi: checked ? prev.demo_tarihi || new Date().toISOString().slice(0, 10) : '',
      };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.isletme_adi.trim()) {
      setError('İşletme adı zorunludur.');
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
    <div className="modal-overlay-scroll">
      <div className="modal-panel modal-panel-xl">
        <div className="flex shrink-0 items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="text-lg font-semibold">
            {lead ? 'Kayıt Düzenle' : 'Yeni Kayıt Ekle'}
          </h2>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        {lead && (
          <div className="flex shrink-0 gap-1 border-b border-surface-200 px-6">
            <button
              type="button"
              onClick={() => setTab('bilgiler')}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                tab === 'bilgiler'
                  ? 'border-brand-500 text-brand-500'
                  : 'border-transparent text-surface-800/60 hover:text-surface-800'
              }`}
            >
              Kayıt Bilgileri
            </button>
            <button
              type="button"
              onClick={() => setTab('aktiviteler')}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                tab === 'aktiviteler'
                  ? 'border-brand-500 text-brand-500'
                  : 'border-transparent text-surface-800/60 hover:text-surface-800'
              }`}
            >
              Aktivite Geçmişi
            </button>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          {(tab === 'bilgiler' || !lead) && (
          <form id="lead-form" onSubmit={handleSubmit} className="p-6 pb-0">
            {error && (
              <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
            )}

            {/* Temel Bilgiler */}
          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <Building2 size={16} /> Temel Bilgiler
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="İşletme Adı *" icon={Building2}>
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
                <StatusSelect
                  value={form.durum}
                  onChange={(newDurum) => {
                    setForm((prev) => ({
                      ...prev,
                      durum: newDurum,
                      demo_gonderildi: newDurum === 'Demo Gönderildi'
                        ? true
                        : prev.durum === 'Demo Gönderildi'
                          ? false
                          : prev.demo_gonderildi,
                      demo_tarihi: newDurum === 'Demo Gönderildi'
                        ? prev.demo_tarihi || new Date().toISOString().slice(0, 10)
                        : prev.durum === 'Demo Gönderildi'
                          ? ''
                          : prev.demo_tarihi,
                    }));
                  }}
                />
              </Field>
            </div>

            <div className="mt-4">
              <label className="label-field mb-2 block">Öncelik Seviyesi</label>
              <PrioritySelect
                value={form.oncelik}
                onChange={(oncelik) => update('oncelik', oncelik)}
              />
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

          {/* İletişim */}
          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <Phone size={16} /> İletişim Bilgileri
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
                  placeholder="05xx xxx xx xx"
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

          {/* Takip */}
          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <Calendar size={16} /> Takip & Süreç
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Takip 1">
                <input
                  className="input-field"
                  value={form.takip_1}
                  onChange={(e) => update('takip_1', e.target.value)}
                  placeholder="Takip notu veya tarihi"
                />
              </Field>
              <Field label="Takip 2">
                <input
                  className="input-field"
                  value={form.takip_2}
                  onChange={(e) => update('takip_2', e.target.value)}
                  placeholder="Takip notu veya tarihi"
                />
              </Field>
              <Field label="Demo Tarihi" icon={Calendar}>
                <input
                  type="date"
                  className="input-field"
                  value={form.demo_tarihi}
                  onChange={(e) => update('demo_tarihi', e.target.value)}
                />
              </Field>
              <Field label="Görüşme Tarihi" icon={Calendar}>
                <input
                  type="date"
                  className="input-field"
                  value={form.gorusme_tarihi}
                  onChange={(e) => update('gorusme_tarihi', e.target.value)}
                />
              </Field>
              <Field label="Görüşme Saati" icon={Clock}>
                <input
                  type="time"
                  className="input-field"
                  value={form.gorusme_saati}
                  onChange={(e) => update('gorusme_saati', e.target.value)}
                />
              </Field>
              <Field label="Teklif">
                <input
                  className="input-field"
                  value={form.teklif}
                  onChange={(e) => update('teklif', e.target.value)}
                  placeholder="Örn. 8500 TL"
                />
              </Field>
              <Field label="Alınan miktar (TL)" icon={CircleDollarSign}>
                <input
                  type="number"
                  min="0"
                  step="1"
                  className="input-field"
                  value={form.satis_tutari || ''}
                  onChange={(e) => update('satis_tutari', Number(e.target.value) || 0)}
                  placeholder="Örn. 4500"
                />
                <p className="mt-1 text-[11px] text-surface-800/50">
                  Kasaya geçen ödeme, kaydedildiği ayda gelir istatistiklerine yazılır. Teklif tarihi kullanılmaz.
                </p>
              </Field>
              <Field label="Ödeme tarihi" icon={Calendar}>
                <input
                  type="date"
                  className="input-field"
                  value={form.satis_tarihi}
                  onChange={(e) => update('satis_tarihi', e.target.value)}
                />
                <p className="mt-1 text-[11px] text-surface-800/50">
                  İlk tahsilat tarihi. Sonraki ödemeler eklendiği günün ayında görünür.
                </p>
              </Field>
              <Field label="Sonuç">
                <input
                  className="input-field"
                  value={form.sonuc}
                  onChange={(e) => update('sonuc', e.target.value)}
                  placeholder="Sonuç"
                />
              </Field>
              <div className="flex items-center gap-3 sm:col-span-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.demo_gonderildi}
                    onChange={(e) => toggleDemo(e.target.checked)}
                    className="h-4 w-4 rounded border-surface-200 text-brand-500 focus:ring-brand-500"
                  />
                  <Check size={14} className="text-surface-800/50" />
                  Demo Gönderildi
                </label>
              </div>
            </div>
          </section>

          {/* Notlar */}
          <section className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
              <FileText size={16} /> Notlar
            </h3>
            <textarea
              className="input-field min-h-[100px] resize-y"
              value={form.notlar}
              onChange={(e) => update('notlar', e.target.value)}
              placeholder="Ek notlar..."
            />
          </section>
          </form>
          )}

          {lead && tab === 'aktiviteler' && (
            <div className="px-6 py-4">
              <ActivityHistory leadId={lead.id} />
            </div>
          )}
        </div>

        <div className="flex shrink-0 justify-end gap-3 border-t border-surface-200 bg-white px-6 py-4">
          <button type="button" onClick={onClose} className="btn-secondary">
            İptal
          </button>
          {(tab === 'bilgiler' || !lead) && (
          <button type="submit" form="lead-form" disabled={saving} className="btn-primary">
            <Save size={16} />
            {saving ? 'Kaydediliyor...' : 'Kaydet'}
          </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  icon: Icon,
  children,
}: {
  label: string;
  icon?: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label-field flex items-center gap-1">
        {Icon && <Icon size={12} className="text-surface-800/40" />}
        {label}
      </label>
      {children}
    </div>
  );
}
