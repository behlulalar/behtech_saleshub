import { useState } from 'react';
import {
  Building2,
  Calendar,
  CircleDollarSign,
  Clock,
  Edit2,
  ExternalLink,
  FileText,
  Instagram,
  Phone,
  User,
  X,
} from 'lucide-react';
import type { Lead, UserRole } from '../types';
import { formatCurrency, toInstagramUrl } from '../utils';
import LeadCommunicationPanel from './LeadCommunicationPanel';
import AiLeadSummary from './ai/AiLeadSummary';
import ActivityHistory from './ActivityHistory';
import LeadAttachments from './LeadAttachments';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';
import TagBadges from './TagBadges';

interface Props {
  lead: Lead;
  categoryLabel?: string;
  userRole: UserRole;
  senderDisplayName?: string;
  senderUsername?: string;
  onEdit: () => void;
  onClose: () => void;
  readOnly?: boolean;
}

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  const display = value?.trim();
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-surface-800/45">{label}</p>
      <p className="mt-0.5 text-sm text-surface-900">{display || '—'}</p>
    </div>
  );
}

function formatDateTime(value?: string) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function LeadDetail({
  lead,
  categoryLabel,
  userRole,
  senderDisplayName,
  senderUsername,
  onEdit,
  onClose,
  readOnly = false,
}: Props) {
  const [tab, setTab] = useState<'bilgiler' | 'aktiviteler' | 'dosyalar'>('bilgiler');
  const instagramUrl = lead.instagram ? toInstagramUrl(lead.instagram) : null;

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel-lg">
        <div className="shrink-0 border-b border-surface-200 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs text-surface-800/50">
                {categoryLabel || lead.category} · #{lead.id}
              </p>
              <h2 className="truncate text-lg font-semibold text-surface-900">{lead.isletme_adi}</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StatusBadge durum={lead.durum} size="xs" />
                <PriorityBadge oncelik={lead.oncelik || 'orta'} size="xs" />
                <TagBadges tags={lead.tags || []} />
              </div>
            </div>
            <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
              <X size={20} />
            </button>
          </div>

          <div className="mt-3 flex gap-1 border-b border-surface-100">
            <button
              type="button"
              onClick={() => setTab('bilgiler')}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${
                tab === 'bilgiler' ? 'border-brand-500 text-brand-500' : 'border-transparent text-surface-800/60'
              }`}
            >
              Detaylar
            </button>
            <button
              type="button"
              onClick={() => setTab('aktiviteler')}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${
                tab === 'aktiviteler' ? 'border-brand-500 text-brand-500' : 'border-transparent text-surface-800/60'
              }`}
            >
              Aktivite Geçmişi
            </button>
            {!readOnly && (
              <button
                type="button"
                onClick={() => setTab('dosyalar')}
                className={`border-b-2 px-3 py-2 text-sm font-medium ${
                  tab === 'dosyalar' ? 'border-brand-500 text-brand-500' : 'border-transparent text-surface-800/60'
                }`}
              >
                Dosyalar
              </button>
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {tab === 'bilgiler' ? (
            <div className="space-y-5">
              <section>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
                  <Building2 size={15} /> Temel Bilgiler
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <DetailItem label="Yetkili" value={lead.yetkili} />
                  <DetailItem label="Şehir" value={lead.sehir} />
                </div>
              </section>

              <AiLeadSummary leadId={lead.id} />

              <LeadCommunicationPanel
                leadId={lead.id}
                lead={lead}
                category={lead.category}
                role={userRole}
                senderDisplayName={senderDisplayName}
                senderUsername={senderUsername}
              />

              <section>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
                  <Phone size={15} /> İletişim Bilgileri
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wide text-surface-800/45">Instagram</p>
                    {lead.instagram ? (
                      instagramUrl ? (
                        <a
                          href={instagramUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-0.5 inline-flex items-center gap-1 text-sm text-brand-500 hover:underline"
                        >
                          <Instagram size={14} />
                          {lead.instagram}
                          <ExternalLink size={12} />
                        </a>
                      ) : (
                        <p className="mt-0.5 text-sm">{lead.instagram}</p>
                      )
                    ) : (
                      <p className="mt-0.5 text-sm text-surface-900">—</p>
                    )}
                  </div>
                  <DetailItem label="WhatsApp / Telefon" value={lead.whatsapp} />
                  <DetailItem label="E-posta" value={lead.eposta} />
                  <DetailItem label="İlk İletişim Kanalı" value={lead.ilk_iletisim_kanali} />
                  <DetailItem
                    label="İlk Mesaj"
                    value={
                      lead.ilk_mesaj_tarihi
                        ? `${lead.ilk_mesaj_tarihi}${lead.ilk_mesaj_saati ? ` ${lead.ilk_mesaj_saati}` : ''}`
                        : undefined
                    }
                  />
                </div>
              </section>

              <section>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
                  <Calendar size={15} /> Takip & Süreç
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <DetailItem label="Takip 1" value={lead.takip_1} />
                  <DetailItem label="Takip 2" value={lead.takip_2} />
                  <DetailItem
                    label="Demo"
                    value={lead.demo_gonderildi ? lead.demo_tarihi || 'Gönderildi' : undefined}
                  />
                  <DetailItem
                    label="Görüşme"
                    value={
                      lead.gorusme_tarihi
                        ? `${lead.gorusme_tarihi}${lead.gorusme_saati ? ` ${lead.gorusme_saati}` : ''}`
                        : undefined
                    }
                  />
                  {!readOnly && <DetailItem label="Teklif" value={lead.teklif} />}
                  <DetailItem label="Sonuç" value={lead.sonuc} />
                  {(lead.satis_tutari > 0 || lead.durum === 'Müşteri') && !readOnly && (
                    <>
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-wide text-surface-800/45">
                          Satış Tutarı
                        </p>
                        <p className="mt-0.5 flex items-center gap-1 text-sm font-semibold text-emerald-700">
                          <CircleDollarSign size={14} />
                          {lead.satis_tutari > 0 ? formatCurrency(lead.satis_tutari) : '—'}
                        </p>
                      </div>
                      <DetailItem label="Satış Tarihi" value={lead.satis_tarihi} />
                    </>
                  )}
                </div>
              </section>

              {lead.notlar && (
                <section>
                  <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-surface-800">
                    <FileText size={15} /> Notlar
                  </h3>
                  <p className="whitespace-pre-wrap rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-sm text-surface-800/80">
                    {lead.notlar}
                  </p>
                </section>
              )}

              <section className="grid gap-3 border-t border-surface-100 pt-4 text-xs text-surface-800/50 sm:grid-cols-2">
                <p className="flex items-center gap-1">
                  <Clock size={12} />
                  Oluşturulma: {formatDateTime(lead.created_at)}
                </p>
                <p className="flex items-center gap-1">
                  <User size={12} />
                  Son güncelleme: {formatDateTime(lead.updated_at)}
                </p>
              </section>
            </div>
          ) : tab === 'aktiviteler' ? (
            <ActivityHistory leadId={lead.id} readOnly={readOnly} />
          ) : (
            <LeadAttachments leadId={lead.id} />
          )}
        </div>

        <div className="flex shrink-0 justify-end gap-2 border-t border-surface-200 px-5 py-3">
          <button type="button" onClick={onClose} className="btn-secondary">
            Kapat
          </button>
          {!readOnly && (
            <button type="button" onClick={onEdit} className="btn-primary">
              <Edit2 size={16} />
              Düzenle
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
