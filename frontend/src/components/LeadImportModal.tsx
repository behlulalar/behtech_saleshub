import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, FileSpreadsheet, History, Trash2, Upload, X } from 'lucide-react';
import { api } from '../api';
import type { Category, LeadImportBatch, LeadImportResult } from '../types';
import { useLocale } from '../i18n/locale';
import { useConfirmDialog } from '../hooks/useConfirmDialog';

interface Props {
  categories: Category[];
  defaultCategoryId: string;
  onClose: () => void;
  onSuccess: () => void;
}

function formatBatchDate(value: string, locale: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-GB' : 'tr-TR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function LeadImportModal({ categories, defaultCategoryId, onClose, onSuccess }: Props) {
  const { app, locale } = useLocale();
  const t = app.leadImport;
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [categoryId, setCategoryId] = useState(defaultCategoryId || categories[0]?.id || '');
  const [file, setFile] = useState<File | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [deletingBatchId, setDeletingBatchId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [result, setResult] = useState<LeadImportResult | null>(null);
  const [batches, setBatches] = useState<LeadImportBatch[]>([]);

  const categoryLabel = useCallback(
    (id: string) => categories.find((category) => category.id === id)?.label ?? id,
    [categories],
  );

  const loadBatches = useCallback(async () => {
    setLoadingBatches(true);
    try {
      const items = await api.listLeadImportBatches();
      setBatches(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'İçe aktarma geçmişi yüklenemedi');
    } finally {
      setLoadingBatches(false);
    }
  }, []);

  useEffect(() => {
    loadBatches().catch(console.error);
  }, [loadBatches]);

  const handleDownloadTemplate = async () => {
    setError('');
    setNotice('');
    setDownloading(true);
    try {
      await api.downloadLeadImportTemplate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Şablon indirilemedi');
    } finally {
      setDownloading(false);
    }
  };

  const handleImport = async () => {
    if (!categoryId) {
      setError('Kategori seçin');
      return;
    }
    if (!file) {
      setError('Excel dosyası seçin');
      return;
    }

    setError('');
    setNotice('');
    setImporting(true);
    try {
      const importResult = await api.importLeads(categoryId, file);
      setResult(importResult);
      if (importResult.created > 0) {
        onSuccess();
        await loadBatches();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'İçe aktarma başarısız');
    } finally {
      setImporting(false);
    }
  };

  const handleDeleteBatch = async (batch: LeadImportBatch) => {
    if (batch.lead_count === 0) {
      setDeletingBatchId(batch.id);
      try {
        await api.deleteLeadImportBatch(batch.id);
        await loadBatches();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Silme başarısız');
      } finally {
        setDeletingBatchId(null);
      }
      return;
    }

    const confirmed = await confirm({
      title: app.confirm.title,
      message: t.deleteBatchConfirm.replace('{count}', String(batch.lead_count)),
      confirmLabel: app.confirm.deleteImportBatch,
      cancelLabel: app.confirm.cancel,
      variant: 'danger',
    });
    if (!confirmed) return;

    setError('');
    setNotice('');
    setDeletingBatchId(batch.id);
    try {
      const response = await api.deleteLeadImportBatch(batch.id);
      setNotice(t.deleteBatchSuccess.replace('{count}', String(response.deleted)));
      onSuccess();
      await loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Silme başarısız');
    } finally {
      setDeletingBatchId(null);
    }
  };

  const resultMessage = result
    ? result.created > 0 && result.failed === 0
      ? t.success.replace('{count}', String(result.created))
      : result.created > 0
        ? t.partial
            .replace('{created}', String(result.created))
            .replace('{failed}', String(result.failed))
        : t.failed
    : '';

  return (
    <>
      <div className="modal-overlay">
        <div className="modal-panel modal-panel-lg">
          <div className="flex shrink-0 items-start justify-between border-b border-surface-200 px-5 py-4">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-surface-900">
                <FileSpreadsheet size={18} className="text-brand-500" />
                {t.title}
              </h2>
              <p className="mt-1 text-sm text-surface-800/60">{t.subtitle}</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
              <X size={20} />
            </button>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
            {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p> : null}
            {notice ? (
              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>
            ) : null}
            {result ? (
              <p
                className={`rounded-lg px-3 py-2 text-sm ${
                  result.created > 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'
                }`}
              >
                {resultMessage}
              </p>
            ) : null}

            <div>
              <label className="label-field">{t.category}</label>
              <select
                className="input-field"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                disabled={importing}
              >
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.label}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleDownloadTemplate}
              disabled={downloading || importing}
              className="btn-secondary w-full justify-center"
            >
              <Download size={16} />
              {downloading ? app.common.loading : t.downloadTemplate}
            </button>

            <div className="rounded-xl border border-dashed border-surface-300 bg-surface-50 p-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xlsm"
                className="hidden"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setResult(null);
                  setError('');
                  setNotice('');
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={importing}
                className="btn-secondary w-full justify-center"
              >
                <Upload size={16} />
                {file ? file.name : t.selectFile}
              </button>
              <p className="mt-2 text-center text-xs text-surface-800/50">{t.fileHint}</p>
            </div>

            {result && result.errors.length > 0 ? (
              <div className="rounded-lg border border-surface-200">
                <p className="border-b border-surface-200 px-3 py-2 text-sm font-semibold text-surface-900">
                  {t.errorsTitle}
                </p>
                <div className="max-h-40 divide-y divide-surface-100 overflow-y-auto">
                  {result.errors.map((item) => (
                    <div key={`${item.row}-${item.error}`} className="px-3 py-2 text-xs text-surface-800/80">
                      <span className="font-medium">
                        {t.row} {item.row}:
                      </span>{' '}
                      {item.isletme_adi ? `${item.isletme_adi} — ` : ''}
                      {item.error}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="rounded-lg border border-surface-200">
              <p className="flex items-center gap-2 border-b border-surface-200 px-3 py-2 text-sm font-semibold text-surface-900">
                <History size={16} className="text-surface-800/50" />
                {t.historyTitle}
              </p>
              {loadingBatches ? (
                <p className="px-3 py-4 text-sm text-surface-800/60">{app.common.loading}</p>
              ) : batches.length === 0 ? (
                <p className="px-3 py-4 text-sm text-surface-800/60">{t.historyEmpty}</p>
              ) : (
                <div className="max-h-52 divide-y divide-surface-100 overflow-y-auto">
                  {batches.map((batch) => (
                    <div
                      key={batch.id}
                      className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-surface-900">
                          {batch.filename || `${t.historyFile} #${batch.id}`}
                        </p>
                        <p className="mt-0.5 text-xs text-surface-800/60">
                          {formatBatchDate(batch.created_at, locale)} · {categoryLabel(batch.category)}
                        </p>
                        <p className="mt-1 text-xs text-surface-800/70">
                          {t.historyCreated.replace('{count}', String(batch.created_count))}
                          {batch.failed_count > 0
                            ? ` · ${t.historyFailed.replace('{count}', String(batch.failed_count))}`
                            : ''}
                          {' · '}
                          {t.historyRemaining.replace('{count}', String(batch.lead_count))}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteBatch(batch)}
                        disabled={deletingBatchId === batch.id || importing}
                        className="btn-secondary shrink-0 justify-center text-red-600 hover:bg-red-50 hover:text-red-700"
                      >
                        <Trash2 size={14} />
                        {deletingBatchId === batch.id ? app.common.loading : t.deleteBatch}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex shrink-0 justify-end gap-2 border-t border-surface-200 px-5 py-3">
            <button type="button" onClick={onClose} className="btn-secondary">
              {t.close}
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={importing || !file || !categoryId}
              className="btn-primary"
            >
              <Upload size={16} />
              {importing ? t.importing : t.import}
            </button>
          </div>
        </div>
      </div>
      {confirmDialog}
    </>
  );
}
