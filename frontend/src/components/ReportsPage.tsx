import { useState } from 'react';
import {
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  FileText,
  Percent,
  TrendingUp,
  UserPlus,
  Users,
} from 'lucide-react';
import { api } from '../api';
import { useLocale } from '../i18n/locale';
import type { AccountType, ReportData, ReportPeriod } from '../types';
import { formatCurrency } from '../utils';
import SalesFunnel from './SalesFunnel';

interface Props {
  accountType: AccountType;
  loading: boolean;
  data: ReportData | null;
  period: ReportPeriod;
  canGoNext: boolean;
  onPeriodChange: (period: ReportPeriod) => void;
  onPrevPeriod: () => void;
  onNextPeriod: () => void;
  onCurrentPeriod: () => void;
  onReload: () => void;
}

function SummaryCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: typeof TrendingUp;
  color: string;
}) {
  return (
    <div className="card flex min-w-0 flex-1 basis-[calc(50%-0.375rem)] items-start gap-3 p-4 max-lg:min-w-0 lg:min-w-[150px]">
      <div className={`rounded-lg bg-surface-50 p-2 ${color}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-surface-800/50">{label}</p>
        <p className="text-sm font-bold text-surface-900 lg:text-lg">{value}</p>
        {sub ? <p className="mt-0.5 text-[11px] text-surface-800/45">{sub}</p> : null}
      </div>
    </div>
  );
}

export default function ReportsPage({
  accountType,
  loading,
  data,
  period,
  canGoNext,
  onPeriodChange,
  onPrevPeriod,
  onNextPeriod,
  onCurrentPeriod,
  onReload,
}: Props) {
  const { app } = useLocale();
  const r = app.reports;
  const [exporting, setExporting] = useState<'csv' | 'xlsx' | 'pdf' | null>(null);
  const showRevenue = accountType === 'company';

  const handleExport = async (format: 'csv' | 'xlsx' | 'pdf') => {
    setExporting(format);
    try {
      const month = period === 'monthly' && data ? data.period_start.slice(0, 7) : undefined;
      const date = period === 'weekly' && data ? data.period_start : undefined;
      await api.exportReport(period, format, { month, date });
    } catch (err) {
      alert(err instanceof Error ? err.message : r.exportFailed);
    } finally {
      setExporting(null);
    }
  };

  if (loading && !data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-800/50">
        {r.loading}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-surface-800/50">
        <p>{r.loadFailed}</p>
        <button type="button" onClick={onReload} className="btn-secondary">
          {r.retry}
        </button>
      </div>
    );
  }

  const prev = data.onceki_donem;
  const leadDelta = data.yeni_kayit - prev.yeni_kayit;
  const customerDelta = data.yeni_musteri - prev.yeni_musteri;

  return (
    <div className="h-full min-w-0 space-y-4 overflow-y-auto overflow-x-hidden pb-4 max-lg:overscroll-contain">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex rounded-lg border border-surface-200 bg-white p-0.5 text-sm font-medium">
            <button
              type="button"
              onClick={() => onPeriodChange('weekly')}
              className={`rounded-md px-4 py-2 transition ${period === 'weekly' ? 'bg-brand-500 text-white shadow-sm' : 'text-surface-800/60 hover:text-surface-900'}`}
            >
              {r.weekly}
            </button>
            <button
              type="button"
              onClick={() => onPeriodChange('monthly')}
              className={`rounded-md px-4 py-2 transition ${period === 'monthly' ? 'bg-brand-500 text-white shadow-sm' : 'text-surface-800/60 hover:text-surface-900'}`}
            >
              {r.monthly}
            </button>
          </div>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-surface-800/55">
            <span className="inline-flex items-center gap-2">
              <CalendarRange size={14} />
              {data.period_label}
            </span>
            <span className="inline-flex items-center gap-1 rounded-lg border border-surface-200 bg-white p-0.5">
              <button
                type="button"
                disabled={loading}
                onClick={onPrevPeriod}
                className="rounded-md p-1.5 text-surface-800/60 transition hover:bg-surface-50 hover:text-surface-900 disabled:opacity-40"
                title={r.prevPeriod}
                aria-label={r.prevPeriod}
              >
                <ChevronLeft size={18} />
              </button>
              <button
                type="button"
                disabled={loading || !canGoNext}
                onClick={onNextPeriod}
                className="rounded-md p-1.5 text-surface-800/60 transition hover:bg-surface-50 hover:text-surface-900 disabled:opacity-40"
                title={r.nextPeriod}
                aria-label={r.nextPeriod}
              >
                <ChevronRight size={18} />
              </button>
            </span>
            {!canGoNext ? null : (
              <button
                type="button"
                disabled={loading}
                onClick={onCurrentPeriod}
                className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-40"
              >
                {r.currentPeriod}
              </button>
            )}
            {loading && data ? (
              <span className="text-xs text-surface-800/40">{r.loading}</span>
            ) : null}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!!exporting}
            onClick={() => handleExport('csv')}
            className="btn-secondary py-2 text-xs"
          >
            <Download size={14} />
            {exporting === 'csv' ? r.downloading : r.csv}
          </button>
          <button
            type="button"
            disabled={!!exporting}
            onClick={() => handleExport('xlsx')}
            className="btn-secondary py-2 text-xs"
          >
            <FileSpreadsheet size={14} />
            {exporting === 'xlsx' ? r.downloading : r.excel}
          </button>
          <button
            type="button"
            disabled={!!exporting}
            onClick={() => handleExport('pdf')}
            className="btn-primary py-2 text-xs"
          >
            <FileText size={14} />
            {exporting === 'pdf' ? r.creating : r.pdf}
          </button>
        </div>
      </div>

      <p className="text-sm text-surface-800/60">
        {period === 'weekly' ? r.weeklyDesc : r.monthlyDesc}
      </p>

      <div className="flex flex-wrap gap-3">
        <SummaryCard
          label={r.newLeads}
          value={String(data.yeni_kayit)}
          sub={`${r.previousPeriod}: ${prev.yeni_kayit} (${leadDelta >= 0 ? '+' : ''}${leadDelta})`}
          icon={UserPlus}
          color="text-brand-500"
        />
        <SummaryCard
          label={r.newCustomers}
          value={String(data.yeni_musteri)}
          sub={`${r.previousPeriod}: ${prev.yeni_musteri} (${customerDelta >= 0 ? '+' : ''}${customerDelta})`}
          icon={Users}
          color="text-emerald-600"
        />
        <SummaryCard
          label={r.conversionRate}
          value={data.donusum_orani != null ? `%${data.donusum_orani}` : '—'}
          sub={`${r.funnelEndRate}: %${data.satis_donusum_orani}`}
          icon={Percent}
          color="text-violet-600"
        />
        {showRevenue && data.satis_sayisi != null ? (
          <>
            <SummaryCard
              label={r.periodRevenue}
              value={formatCurrency(data.toplam_gelir || 0)}
              sub={`${data.satis_sayisi} ${r.salesCount} · ${r.avgSale} ${formatCurrency(data.ortalama_satis || 0)}`}
              icon={TrendingUp}
              color="text-amber-600"
            />
          </>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SalesFunnel stages={data.satis_hunisi} conversionRate={data.satis_donusum_orani} />

        <div className="card p-4">
          <h3 className="mb-4 text-sm font-semibold text-surface-900">{r.statusBreakdown}</h3>
          {data.durum_dagilimi.length === 0 ? (
            <p className="text-sm text-surface-800/50">{r.noLeadsThisPeriod}</p>
          ) : (
            <ul className="space-y-2">
              {data.durum_dagilimi.map((item) => (
                <li key={item.durum} className="flex items-center justify-between rounded-lg bg-surface-50 px-3 py-2 text-sm">
                  <span className="font-medium text-surface-900">{item.durum}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-brand-600">{item.count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="card min-w-0 p-4">
        <h3 className="mb-4 text-sm font-semibold text-surface-900">{r.categorySummary}</h3>
        {data.kategori_ozet.length === 0 ? (
          <p className="text-sm text-surface-800/50">{r.noCategoryData}</p>
        ) : (
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200 text-xs uppercase tracking-wide text-surface-800/45">
                  <th className="pb-2 pr-4 font-semibold">{r.category}</th>
                  <th className="pb-2 pr-4 font-semibold">{r.newLeads}</th>
                  <th className="pb-2 font-semibold">{r.customer}</th>
                </tr>
              </thead>
              <tbody>
                {data.kategori_ozet.map((item) => (
                  <tr key={item.category} className="border-b border-surface-100 last:border-0">
                    <td className="py-2.5 pr-4 font-medium text-surface-900">{item.category_label}</td>
                    <td className="py-2.5 pr-4 text-surface-800/70">{item.yeni_kayit}</td>
                    <td className="py-2.5 text-surface-800/70">{item.musteri}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showRevenue && data.donem_satislar.length > 0 ? (
        <div className="card min-w-0 p-4">
          <h3 className="mb-4 text-sm font-semibold text-surface-900">{r.periodSales}</h3>
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200 text-xs uppercase tracking-wide text-surface-800/45">
                  <th className="pb-2 pr-4 font-semibold">{r.business}</th>
                  <th className="pb-2 pr-4 font-semibold">{r.category}</th>
                  <th className="pb-2 pr-4 font-semibold">{r.city}</th>
                  <th className="pb-2 pr-4 font-semibold">{r.amount}</th>
                  <th className="pb-2 font-semibold">{r.date}</th>
                </tr>
              </thead>
              <tbody>
                {data.donem_satislar.map((sale, index) => (
                  <tr key={`${sale.isletme_adi}-${index}`} className="border-b border-surface-100 last:border-0">
                    <td className="py-2.5 pr-4 font-medium text-surface-900">{sale.isletme_adi}</td>
                    <td className="py-2.5 pr-4 text-surface-800/70">{sale.category_label}</td>
                    <td className="py-2.5 pr-4 text-surface-800/70">{sale.sehir || '—'}</td>
                    <td className="py-2.5 pr-4 font-medium text-emerald-700">{formatCurrency(sale.satis_tutari)}</td>
                    <td className="py-2.5 text-surface-800/70">{sale.satis_tarihi || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
