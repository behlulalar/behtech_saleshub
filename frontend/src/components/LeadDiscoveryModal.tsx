import { useCallback, useEffect, useMemo, useState } from 'react';
import { Compass, Loader2, MapPin, Search, X } from 'lucide-react';
import { api } from '../api';
import type { Category, LeadDiscoveryResult, PlacesUsage } from '../types';
import { useLocale } from '../i18n/locale';
import { useConfirmDialog } from '../hooks/useConfirmDialog';

interface Props {
  categories: Category[];
  defaultCategoryId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function LeadDiscoveryModal({ categories, defaultCategoryId, onClose, onSuccess }: Props) {
  const { app } = useLocale();
  const t = app.leadDiscovery;
  const { confirm, dialog: confirmDialog } = useConfirmDialog();

  const [city, setCity] = useState('');
  const [district, setDistrict] = useState('');
  const [sectorKeyword, setSectorKeyword] = useState('');
  const [categoryId, setCategoryId] = useState(defaultCategoryId || categories[0]?.id || '');
  const [radiusMeters, setRadiusMeters] = useState(5000);
  const [usage, setUsage] = useState<PlacesUsage | null>(null);
  const [results, setResults] = useState<LeadDiscoveryResult[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [warningMessage, setWarningMessage] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [mappedCategory, setMappedCategory] = useState('');

  const loadUsage = useCallback(async () => {
    try {
      const data = await api.getLeadDiscoveryUsage();
      setUsage(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.usageLoadFailed);
    }
  }, [t.usageLoadFailed]);

  useEffect(() => {
    loadUsage().catch(console.error);
  }, [loadUsage]);

  const importableResults = useMemo(
    () => results.filter((item) => !item.already_in_crm),
    [results],
  );

  const toggleSelect = (placeId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(placeId)) next.delete(placeId);
      else next.add(placeId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === importableResults.length) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(importableResults.map((item) => item.google_place_id)));
  };

  const runDiscover = async (confirmOverQuota = false) => {
    if (!city.trim() || !sectorKeyword.trim()) {
      setError(t.requiredFields);
      return;
    }
    if (!categoryId) {
      setError(t.categoryRequired);
      return;
    }

    setError('');
    setNotice('');
    setWarningMessage('');
    setScanning(true);
    try {
      const response = await api.discoverLeads({
        city: city.trim(),
        district: district.trim(),
        sector_keyword: sectorKeyword.trim(),
        category: categoryId,
        radius_meters: radiusMeters,
        confirm_over_quota: confirmOverQuota,
      });
      setResults(response.results);
      setMappedCategory(response.mapped_category);
      setUsage(response.usage);
      setSelectedIds(
        new Set(response.results.filter((item) => !item.already_in_crm).map((item) => item.google_place_id)),
      );
      if (response.warning_message) setWarningMessage(response.warning_message);
    } catch (err) {
      if (err instanceof Error && err.message.startsWith('QUOTA:')) {
        const payload = JSON.parse(err.message.slice(6)) as { message: string; usage: PlacesUsage };
        const approved = await confirm({
          title: t.quotaTitle,
          message: payload.message,
          confirmLabel: t.quotaConfirm,
          cancelLabel: app.confirm.cancel,
          variant: 'danger',
        });
        if (approved) {
          await runDiscover(true);
        }
        return;
      }
      setError(err instanceof Error ? err.message : t.scanFailed);
    } finally {
      setScanning(false);
    }
  };

  const handleImport = async () => {
    const selected = results.filter((item) => selectedIds.has(item.google_place_id) && !item.already_in_crm);
    if (selected.length === 0) {
      setError(t.noSelection);
      return;
    }

    setError('');
    setNotice('');
    setImporting(true);
    try {
      const response = await api.importDiscoveredLeads({
        category: mappedCategory || categoryId,
        city: city.trim(),
        places: selected.map((item) => ({
          google_place_id: item.google_place_id,
          business_name: item.business_name,
          phone_number: item.phone_number,
          address: item.address,
          rating: item.rating,
          rating_count: item.rating_count,
          latitude: item.latitude,
          longitude: item.longitude,
          low_digital_presence: item.low_digital_presence,
        })),
      });
      setNotice(
        t.importSuccess
          .replace('{created}', String(response.created))
          .replace('{updated}', String(response.updated)),
      );
      onSuccess();
      setResults((prev) =>
        prev.map((item) =>
          selectedIds.has(item.google_place_id)
            ? { ...item, already_in_crm: true }
            : item,
        ),
      );
      setSelectedIds(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : t.importFailed);
    } finally {
      setImporting(false);
    }
  };

  const usageLabel = usage
    ? t.usageRemaining
        .replace('{remaining}', String(usage.remaining))
        .replace('{quota}', String(usage.free_quota))
    : '';

  return (
    <>
      <div className="modal-overlay">
        <div className="modal-panel modal-panel-lg">
          <div className="flex shrink-0 items-start justify-between border-b border-surface-200 px-5 py-4">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-surface-900">
                <Compass size={18} className="text-brand-500" />
                {t.title}
              </h2>
              <p className="mt-1 text-sm text-surface-800/60">{t.subtitle}</p>
              {usage ? (
                <p className="mt-2 inline-flex rounded-full bg-surface-100 px-2.5 py-1 text-xs font-medium text-surface-800/70">
                  {usageLabel}
                  {usage.warning ? ` · ${t.usageWarning}` : ''}
                </p>
              ) : null}
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
              <X size={20} />
            </button>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
            {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p> : null}
            {notice ? <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p> : null}
            {warningMessage ? (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{warningMessage}</p>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="label-field">{t.city}</label>
                <input className="input-field" value={city} onChange={(e) => setCity(e.target.value)} disabled={scanning} />
                <p className="mt-1 text-xs text-surface-800/50">{t.cityHint}</p>
              </div>
              <div>
                <label className="label-field">{t.district}</label>
                <input
                  className="input-field"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  disabled={scanning}
                  placeholder={t.districtOptional}
                />
              </div>
              <div>
                <label className="label-field">{t.sectorKeyword}</label>
                <input
                  className="input-field"
                  value={sectorKeyword}
                  onChange={(e) => setSectorKeyword(e.target.value)}
                  disabled={scanning}
                  placeholder={t.sectorPlaceholder}
                />
              </div>
              <div>
                <label className="label-field">{t.category}</label>
                <select
                  className="input-field"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  disabled={scanning}
                >
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="label-field">{t.radius}</label>
                <input
                  type="number"
                  min={1000}
                  max={20000}
                  step={500}
                  className="input-field"
                  value={radiusMeters}
                  onChange={(e) => setRadiusMeters(Number(e.target.value) || 5000)}
                  disabled={scanning}
                />
              </div>
            </div>

            <button
              type="button"
              onClick={() => runDiscover(false)}
              disabled={scanning || importing}
              className="btn-primary w-full justify-center"
            >
              {scanning ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              {scanning ? t.scanning : t.scan}
            </button>

            {results.length > 0 ? (
              <div className="rounded-lg border border-surface-200">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-200 px-3 py-2">
                  <p className="text-sm font-semibold text-surface-900">
                    {t.resultsTitle.replace('{count}', String(results.length))}
                  </p>
                  {importableResults.length > 0 ? (
                    <button type="button" onClick={toggleSelectAll} className="text-xs font-medium text-brand-600">
                      {selectedIds.size === importableResults.length ? t.deselectAll : t.selectAll}
                    </button>
                  ) : null}
                </div>
                <div className="max-h-72 divide-y divide-surface-100 overflow-y-auto">
                  {results.map((item) => (
                    <label
                      key={item.google_place_id}
                      className="flex cursor-pointer gap-3 px-3 py-3 hover:bg-surface-50"
                    >
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={selectedIds.has(item.google_place_id)}
                        disabled={item.already_in_crm || importing}
                        onChange={() => toggleSelect(item.google_place_id)}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-medium text-surface-900">{item.business_name}</p>
                          {item.already_in_crm ? (
                            <span className="rounded-full bg-surface-100 px-2 py-0.5 text-[10px] font-semibold text-surface-700">
                              {t.alreadyAdded}
                            </span>
                          ) : null}
                          {item.low_digital_presence ? (
                            <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">
                              {t.lowDigital}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-0.5 flex items-start gap-1 text-xs text-surface-800/70">
                          <MapPin size={12} className="mt-0.5 shrink-0" />
                          <span>{item.address || t.noAddress}</span>
                        </p>
                        <p className="mt-1 text-xs text-surface-800/70">
                          {item.phone_number || t.noPhone}
                          {item.rating != null
                            ? ` · ${t.rating}: ${item.rating} (${item.rating_count ?? 0})`
                            : ''}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <div className="flex shrink-0 justify-end gap-2 border-t border-surface-200 px-5 py-3">
            <button type="button" onClick={onClose} className="btn-secondary">
              {t.close}
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={importing || scanning || selectedIds.size === 0}
              className="btn-primary"
            >
              {importing ? t.importing : t.importSelected.replace('{count}', String(selectedIds.size))}
            </button>
          </div>
        </div>
      </div>
      {confirmDialog}
    </>
  );
}
