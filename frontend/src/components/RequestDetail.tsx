import { useState } from 'react';
import {
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Instagram,
  Phone,
  User,
  X,
  XCircle,
} from 'lucide-react';
import type { LeadRequest, Tag, UserRole } from '../types';
import { toInstagramUrl } from '../utils';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';
import TagBadges from './TagBadges';

interface Props {
  request: LeadRequest;
  tags: Tag[];
  role: UserRole;
  onClose: () => void;
  onApprove?: (request: LeadRequest) => Promise<void>;
  onReject?: (request: LeadRequest, note: string) => Promise<void>;
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

function formatDateTime(value?: string | null) {
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

function requestStatusBadge(status: string) {
  if (status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
        <Clock size={12} /> Bekliyor
      </span>
    );
  }
  if (status === 'approved') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
        <CheckCircle2 size={12} /> Onaylandı
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800">
      <XCircle size={12} /> Reddedildi
    </span>
  );
}

export default function RequestDetail({
  request,
  tags,
  role,
  onClose,
  onApprove,
  onReject,
}: Props) {
  const [processing, setProcessing] = useState(false);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectNote, setRejectNote] = useState('');

  const instagramUrl = request.instagram ? toInstagramUrl(request.instagram) : null;
  const requestTags = tags.filter((tag) => request.tag_ids.includes(tag.id));
  const isOwner = role === 'owner';
  const isPending = request.status === 'pending';

  const handleApprove = async () => {
    if (!onApprove) return;
    setProcessing(true);
    try {
      await onApprove(request);
      onClose();
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!onReject) return;
    setProcessing(true);
    try {
      await onReject(request, rejectNote);
      onClose();
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel-lg">
        <div className="shrink-0 border-b border-surface-200 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs text-surface-800/50">
                {request.category_label} · Talep #{request.id}
              </p>
              <h2 className="truncate text-lg font-semibold text-surface-900">{request.isletme_adi}</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {requestStatusBadge(request.status)}
                <StatusBadge durum={request.durum} size="xs" />
                <PriorityBadge oncelik={request.oncelik || 'orta'} size="xs" />
                <TagBadges tags={requestTags} />
              </div>
              <p className="mt-2 text-xs text-surface-800/50">
                {request.requested_by_username} tarafından gönderildi · {formatDateTime(request.created_at)}
              </p>
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="space-y-5">
            <section>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
                <Building2 size={15} /> Temel Bilgiler
              </h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <DetailItem label="Yetkili" value={request.yetkili} />
                <DetailItem label="Şehir" value={request.sehir} />
                <DetailItem label="Kategori" value={request.category_label} />
                <DetailItem label="Gönderen" value={request.requested_by_username} />
              </div>
            </section>

            <section>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-surface-800">
                <Phone size={15} /> İletişim
              </h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-surface-800/45">Instagram</p>
                  {request.instagram ? (
                    instagramUrl ? (
                      <a
                        href={instagramUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-0.5 inline-flex items-center gap-1 text-sm text-brand-500 hover:underline"
                      >
                        <Instagram size={14} />
                        {request.instagram}
                        <ExternalLink size={12} />
                      </a>
                    ) : (
                      <p className="mt-0.5 text-sm">{request.instagram}</p>
                    )
                  ) : (
                    <p className="mt-0.5 text-sm text-surface-900">—</p>
                  )}
                </div>
                <DetailItem label="WhatsApp" value={request.whatsapp} />
                <DetailItem label="İlk İletişim Kanalı" value={request.ilk_iletisim_kanali} />
                <DetailItem
                  label="İlk Mesaj"
                  value={
                    request.ilk_mesaj_tarihi
                      ? `${request.ilk_mesaj_tarihi}${request.ilk_mesaj_saati ? ` ${request.ilk_mesaj_saati}` : ''}`
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
                <DetailItem label="Takip 1" value={request.takip_1} />
                <DetailItem label="Takip 2" value={request.takip_2} />
                <DetailItem
                  label="Demo"
                  value={request.demo_gonderildi ? request.demo_tarihi || 'Gönderildi' : undefined}
                />
                <DetailItem
                  label="Görüşme"
                  value={
                    request.gorusme_tarihi
                      ? `${request.gorusme_tarihi}${request.gorusme_saati ? ` ${request.gorusme_saati}` : ''}`
                      : undefined
                  }
                />
                {isOwner && <DetailItem label="Teklif" value={request.teklif} />}
                <DetailItem label="Sonuç" value={request.sonuc} />
              </div>
            </section>

            {request.notlar && (
              <section>
                <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-surface-800">
                  <FileText size={15} /> Notlar
                </h3>
                <p className="whitespace-pre-wrap rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-sm text-surface-800/80">
                  {request.notlar}
                </p>
              </section>
            )}

            {(request.status === 'rejected' || request.status === 'approved') && (
              <section className="rounded-lg border border-surface-200 bg-surface-50 px-4 py-3">
                <h3 className="mb-2 text-sm font-semibold text-surface-800">Talep Sonucu</h3>
                {request.status === 'rejected' && request.rejection_note && (
                  <p className="text-sm text-red-700">Red nedeni: {request.rejection_note}</p>
                )}
                {request.status === 'rejected' && !request.rejection_note && (
                  <p className="text-sm text-surface-800/60">Talep reddedildi.</p>
                )}
                {request.status === 'approved' && (
                  <p className="text-sm text-emerald-700">
                    Talep onaylandı
                    {request.reviewed_by_username ? ` · ${request.reviewed_by_username}` : ''}
                    {request.approved_lead_id ? ` · Müşteri #${request.approved_lead_id}` : ''}
                  </p>
                )}
                {request.reviewed_at && (
                  <p className="mt-1 text-xs text-surface-800/50">
                    İşlem tarihi: {formatDateTime(request.reviewed_at)}
                  </p>
                )}
              </section>
            )}

            <section className="grid gap-3 border-t border-surface-100 pt-4 text-xs text-surface-800/50 sm:grid-cols-2">
              <p className="flex items-center gap-1">
                <Clock size={12} />
                Gönderilme: {formatDateTime(request.created_at)}
              </p>
              <p className="flex items-center gap-1">
                <User size={12} />
                Son güncelleme: {formatDateTime(request.updated_at)}
              </p>
            </section>
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-2 border-t border-surface-200 px-5 py-3 sm:flex-row sm:justify-end">
          {isOwner && isPending && showRejectForm ? (
            <div className="flex w-full flex-col gap-2 sm:max-w-md sm:ml-auto">
              <input
                className="input-field py-1.5 text-sm"
                placeholder="Red nedeni (opsiyonel)"
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowRejectForm(false);
                    setRejectNote('');
                  }}
                  className="btn-secondary"
                >
                  Vazgeç
                </button>
                <button type="button" onClick={handleReject} disabled={processing} className="btn-secondary">
                  Reddet
                </button>
              </div>
            </div>
          ) : (
            <>
              <button type="button" onClick={onClose} className="btn-secondary">
                Kapat
              </button>
              {isOwner && isPending && onApprove && onReject && (
                <>
                  <button
                    type="button"
                    onClick={() => setShowRejectForm(true)}
                    disabled={processing}
                    className="btn-secondary"
                  >
                    Reddet
                  </button>
                  <button type="button" onClick={handleApprove} disabled={processing} className="btn-primary">
                    {processing ? 'İşleniyor...' : 'Onayla'}
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
