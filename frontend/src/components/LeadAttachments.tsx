import { useEffect, useRef, useState } from 'react';
import { Archive, Download, FileText, Pencil, RefreshCw, Trash2, Upload, X } from 'lucide-react';
import { api } from '../api';
import type { LeadAttachment } from '../types';

interface Props {
  leadId: number;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

function AttachmentRow({
  attachment,
  onDownload,
  onArchive,
  onReplace,
  onDelete,
  onSaveLabel,
  showArchiveActions,
}: {
  attachment: LeadAttachment;
  onDownload: (attachment: LeadAttachment) => void;
  onArchive?: (attachment: LeadAttachment) => void;
  onReplace?: (attachment: LeadAttachment) => void;
  onDelete: (attachment: LeadAttachment) => void;
  onSaveLabel?: (attachmentId: number, label: string) => Promise<void>;
  showArchiveActions?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [editingLabel, setEditingLabel] = useState(attachment.label);

  const saveLabel = async () => {
    if (!onSaveLabel) return;
    await onSaveLabel(attachment.id, editingLabel);
    setEditing(false);
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-surface-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          <div
            className={`mt-0.5 rounded-lg p-2 ${
              attachment.is_archived ? 'bg-surface-100 text-surface-500' : 'bg-brand-50 text-brand-500'
            }`}
          >
            <FileText size={16} />
          </div>
          <div className="min-w-0 flex-1">
            {editing ? (
              <div className="flex items-center gap-2">
                <input
                  className="input-field py-1.5 text-sm"
                  value={editingLabel}
                  onChange={(e) => setEditingLabel(e.target.value)}
                  maxLength={255}
                />
                <button type="button" onClick={saveLabel} className="btn-primary px-3 py-1.5 text-xs">
                  Kaydet
                </button>
                <button type="button" onClick={() => setEditing(false)} className="rounded-lg p-1.5 hover:bg-surface-100">
                  <X size={16} />
                </button>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-sm font-semibold text-surface-900">{attachment.label}</p>
                  <span className="rounded-full bg-surface-100 px-2 py-0.5 text-[10px] font-medium text-surface-600">
                    v{attachment.version_number}
                  </span>
                  {attachment.is_archived && (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                      Arşiv
                    </span>
                  )}
                </div>
                <p className="truncate text-xs text-surface-800/50">{attachment.original_filename}</p>
              </>
            )}
            <p className="mt-1 text-xs text-surface-800/45">
              {formatFileSize(attachment.size_bytes)} · Yüklendi: {formatDate(attachment.created_at)}
              {attachment.uploaded_by_username ? ` · ${attachment.uploaded_by_username}` : ''}
            </p>
            {attachment.is_archived && attachment.archived_at && (
              <p className="text-xs text-surface-800/45">
                Arşivlendi: {formatDate(attachment.archived_at)}
                {attachment.archived_by_username ? ` · ${attachment.archived_by_username}` : ''}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 flex-wrap gap-2">
        <button type="button" onClick={() => onDownload(attachment)} className="btn-secondary px-3 py-1.5 text-xs">
          <Download size={14} />
          İndir
        </button>
        {showArchiveActions && onSaveLabel && !attachment.is_archived && (
          <button type="button" onClick={() => setEditing(true)} className="btn-secondary px-3 py-1.5 text-xs">
            <Pencil size={14} />
            Adlandır
          </button>
        )}
        {showArchiveActions && onReplace && !attachment.is_archived && (
          <button type="button" onClick={() => onReplace(attachment)} className="btn-secondary px-3 py-1.5 text-xs">
            <RefreshCw size={14} />
            Yeni sürüm
          </button>
        )}
        {showArchiveActions && onArchive && !attachment.is_archived && (
          <button type="button" onClick={() => onArchive(attachment)} className="btn-secondary px-3 py-1.5 text-xs">
            <Archive size={14} />
            Arşivle
          </button>
        )}
        {showArchiveActions && (
          <button type="button" onClick={() => onDelete(attachment)} className="btn-danger px-3 py-1.5 text-xs">
            <Trash2 size={14} />
            {attachment.is_archived ? 'Kalıcı sil' : 'Sil'}
          </button>
        )}
      </div>
    </div>
  );
}

export default function LeadAttachments({ leadId }: Props) {
  const [view, setView] = useState<'active' | 'archived'>('active');
  const [activeFiles, setActiveFiles] = useState<LeadAttachment[]>([]);
  const [archivedFiles, setArchivedFiles] = useState<LeadAttachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [label, setLabel] = useState('');
  const [replaceAttachmentId, setReplaceAttachmentId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  const loadAttachments = async () => {
    setLoading(true);
    setError('');
    try {
      const [active, archived] = await Promise.all([
        api.getLeadAttachments(leadId, 'active'),
        api.getLeadAttachments(leadId, 'archived'),
      ]);
      setActiveFiles(active);
      setArchivedFiles(archived);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dosyalar yüklenemedi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAttachments();
  }, [leadId]);

  const handleUploadClick = () => {
    setReplaceAttachmentId(null);
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>, replaceId?: number | null) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    setUploading(true);
    setError('');
    try {
      const created = await api.uploadLeadAttachment(leadId, file, {
        label,
        replaceAttachmentId: replaceId ?? replaceAttachmentId ?? undefined,
      });
      const archivedId = replaceId ?? replaceAttachmentId;
      setActiveFiles((prev) => {
        const withoutReplaced = archivedId ? prev.filter((item) => item.id !== archivedId) : prev;
        return [created, ...withoutReplaced];
      });
      if (archivedId) {
        const archived = await api.getLeadAttachments(leadId, 'archived');
        setArchivedFiles(archived);
      }
      setLabel('');
      setReplaceAttachmentId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dosya yüklenemedi');
    } finally {
      setUploading(false);
    }
  };

  const handleReplaceClick = (attachment: LeadAttachment) => {
    setReplaceAttachmentId(attachment.id);
    setLabel(`${attachment.label} (yenileme)`);
    replaceInputRef.current?.click();
  };

  const handleDownload = async (attachment: LeadAttachment) => {
    setError('');
    try {
      await api.downloadLeadAttachment(leadId, attachment.id, attachment.original_filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'İndirme başarısız');
    }
  };

  const handleArchive = async (attachment: LeadAttachment) => {
    const confirmed = window.confirm(
      `"${attachment.label}" dosyasını arşive taşımak istiyor musunuz? Dosya silinmez, geçmiş sürümler bölümünde kalır.`,
    );
    if (!confirmed) return;

    setError('');
    try {
      const archived = await api.archiveLeadAttachment(leadId, attachment.id);
      setActiveFiles((prev) => prev.filter((item) => item.id !== attachment.id));
      setArchivedFiles((prev) => [archived, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Arşivleme başarısız');
    }
  };

  const handleDelete = async (attachment: LeadAttachment) => {
    const confirmed = window.confirm(
      attachment.is_archived
        ? `"${attachment.label}" arşiv kaydını ve dosyayı kalıcı olarak silmek istediğinize emin misiniz?`
        : `"${attachment.label}" dosyasını kalıcı olarak silmek istediğinize emin misiniz?`,
    );
    if (!confirmed) return;

    setError('');
    try {
      await api.deleteLeadAttachment(leadId, attachment.id);
      if (attachment.is_archived) {
        setArchivedFiles((prev) => prev.filter((item) => item.id !== attachment.id));
      } else {
        setActiveFiles((prev) => prev.filter((item) => item.id !== attachment.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dosya silinemedi');
    }
  };

  const handleSaveLabel = async (attachmentId: number, nextLabel: string) => {
    const trimmed = nextLabel.trim();
    if (!trimmed) {
      setError('Dosya adı boş olamaz');
      return;
    }
    setError('');
    const updated = await api.updateLeadAttachmentLabel(leadId, attachmentId, trimmed);
    setActiveFiles((prev) => prev.map((item) => (item.id === attachmentId ? updated : item)));
  };

  const currentFiles = view === 'active' ? activeFiles : archivedFiles;

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-surface-200 bg-surface-50 p-4">
        <h3 className="text-sm font-semibold text-surface-800">Dosya Yükle</h3>
        <p className="mt-1 text-xs text-surface-800/55">
          Sözleşme yenilendiğinde mevcut dosyada <strong>Yeni sürüm</strong> ile eskisini arşivleyip
          yenisini yükleyebilirsiniz. Eski sözleşmeler arşivde saklanır.
        </p>

        <div className="mt-3 space-y-3">
          <div>
            <label className="label-field">Dosya adı / açıklama (isteğe bağlı)</label>
            <input
              className="input-field"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Örn: 2025 Sözleşmesi"
              maxLength={255}
            />
          </div>

          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,application/pdf,image/png,image/jpeg"
            onChange={(e) => handleFileChange(e)}
          />
          <input
            ref={replaceInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,application/pdf,image/png,image/jpeg"
            onChange={(e) => handleFileChange(e, replaceAttachmentId)}
          />

          <button
            type="button"
            onClick={handleUploadClick}
            disabled={uploading}
            className="btn-primary w-full justify-center"
          >
            <Upload size={16} />
            {uploading ? 'Yükleniyor...' : 'Dosya Seç ve Yükle'}
          </button>

          <p className="text-xs text-surface-800/45">
            PDF, JPG, PNG, DOC, DOCX · En fazla 15 MB · Yalnızca hesap sahibi erişebilir
          </p>
        </div>
      </section>

      <div className="flex gap-1 rounded-lg border border-surface-200 bg-surface-50 p-1">
        <button
          type="button"
          onClick={() => setView('active')}
          className={`flex-1 rounded-md px-3 py-2 text-sm font-medium ${
            view === 'active' ? 'bg-white text-brand-500 shadow-sm' : 'text-surface-800/60'
          }`}
        >
          Güncel Dosyalar ({activeFiles.length})
        </button>
        <button
          type="button"
          onClick={() => setView('archived')}
          className={`flex-1 rounded-md px-3 py-2 text-sm font-medium ${
            view === 'archived' ? 'bg-white text-brand-500 shadow-sm' : 'text-surface-800/60'
          }`}
        >
          Arşiv / Geçmiş ({archivedFiles.length})
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-surface-800/60">Dosyalar yükleniyor...</p>
      ) : currentFiles.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-200 px-4 py-8 text-center">
          <FileText size={28} className="mx-auto text-surface-800/25" />
          <p className="mt-2 text-sm text-surface-800/60">
            {view === 'active' ? 'Henüz güncel dosya yok.' : 'Arşivlenmiş dosya yok.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {currentFiles.map((attachment) => (
            <AttachmentRow
              key={attachment.id}
              attachment={attachment}
              onDownload={handleDownload}
              onArchive={view === 'active' ? handleArchive : undefined}
              onReplace={view === 'active' ? handleReplaceClick : undefined}
              onDelete={handleDelete}
              onSaveLabel={view === 'active' ? handleSaveLabel : undefined}
              showArchiveActions
            />
          ))}
        </div>
      )}
    </div>
  );
}
