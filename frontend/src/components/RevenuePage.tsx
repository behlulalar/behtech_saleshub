import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Banknote,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Layers,
  RefreshCw,
  ShoppingBag,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { api } from '../api';
import type { RevenueData, RevenueMonthItem } from '../types';
import { useLocale } from '../i18n/locale';
import { formatCurrency } from '../utils';

const MONTHS = {
  tr: ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
} as const;

function currentYear() {
  return new Date().getFullYear();
}

function currentMonth() {
  return new Date().getMonth() + 1;
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
  icon: typeof Banknote;
  color: string;
}) {
  return (
    <div className="card flex min-w-0 flex-1 basis-[calc(50%-0.375rem)] items-start gap-3 p-4 max-lg:min-w-0 lg:min-w-[150px]">
      <div className={`rounded-lg bg-surface-50 p-2 ${color}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-surface-800/50">{label}</p>
        <p className="truncate text-lg font-bold text-surface-900">{value}</p>
        {sub ? <p className="mt-0.5 text-[11px] text-surface-800/45">{sub}</p> : null}
      </div>
    </div>
  );
}

function BarChart({
  items,
  emptyLabel,
}: {
  items: { key: string; label: string; value: number }[];
  emptyLabel: string;
}) {
  const max = Math.max(...items.map((item) => item.value), 0);
  if (items.length === 0 || max <= 0) {
    return <p className="py-10 text-center text-sm text-surface-800/50">{emptyLabel}</p>;
  }

  return (
    <div className="flex h-52 items-end gap-1.5 sm:gap-2">
      {items.map((item) => {
        const height = Math.max((item.value / max) * 100, item.value > 0 ? 6 : 0);
        return (
          <div key={item.key} className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <span className="truncate text-[10px] font-medium text-surface-800/70">
              {item.value > 0 ? formatCurrency(item.value) : ''}
            </span>
            <div className="flex h-36 w-full items-end rounded-t-md bg-surface-100">
              <div
                className="w-full rounded-t-md bg-emerald-500 transition-all"
                style={{ height: `${height}%` }}
                title={`${item.label}: ${formatCurrency(item.value)}`}
              />
            </div>
            <span className="w-full truncate text-center text-[10px] text-surface-800/55">{item.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function formatSaleDate(value: string, locale: string) {
  if (!value) return '—';
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(locale === 'en' ? 'en-US' : 'tr-TR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function shortMonthLabel(item: RevenueMonthItem, locale: string) {
  const month = Number(item.ay.split('-')[1]);
  const names = locale === 'en' ? MONTHS.en : MONTHS.tr;
  return names[month - 1]?.slice(0, 3) || item.ay;
}

export default function RevenuePage() {
  const { locale, app } = useLocale();
  const r = app.revenue;
  const months = locale === 'en' ? MONTHS.en : MONTHS.tr;
  const nowYear = currentYear();
  const nowMonth = currentMonth();

  const [year, setYear] = useState<number | 'all'>(nowYear);
  const [month, setMonth] = useState<number | 'all'>('all');
  const [data, setData] = useState<RevenueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await api.getRevenue({
        year: year === 'all' ? undefined : year,
        month: month === 'all' ? undefined : month,
      });
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : r.loadFailed);
    } finally {
      setLoading(false);
    }
  }, [year, month, r.loadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const years = useMemo(() => {
    const fromApi = data?.available_years || [];
    const set = new Set<number>([nowYear, ...fromApi]);
    if (typeof year === 'number') set.add(year);
    return [...set].sort((a, b) => b - a);
  }, [data?.available_years, nowYear, year]);

  const canGoNext =
    year === 'all'
      ? false
      : month === 'all'
        ? year < nowYear
        : year < nowYear || (year === nowYear && month < nowMonth);

  function goPrev() {
    if (year === 'all') return;
    if (month === 'all') {
      setYear(year - 1);
      return;
    }
    if (month === 1) {
      setYear(year - 1);
      setMonth(12);
    } else {
      setMonth(month - 1);
    }
  }

  function goNext() {
    if (!canGoNext || year === 'all') return;
    if (month === 'all') {
      setYear(year + 1);
      return;
    }
    if (month === 12) {
      setYear(year + 1);
      setMonth(1);
    } else {
      setMonth(month + 1);
    }
  }

  const chartItems =
    data?.gunluk_gelir && data.gunluk_gelir.length > 0
      ? data.gunluk_gelir.map((item) => ({ key: item.gun, label: item.gun_label, value: item.gelir }))
      : (data?.aylik_gelir || []).map((item) => ({
          key: item.ay,
          label: shortMonthLabel(item, locale),
          value: item.gelir,
        }));

  const maxCategory = Math.max(...(data?.kategori_dagilimi || []).map((item) => item.gelir), 1);
  const change = data?.degisim_yuzde;
  const changeLabel =
    change == null
      ? undefined
      : `${change > 0 ? '+' : ''}${change}% ${r.vsPrevious}`;

  return (
    <div className="h-full min-w-0 space-y-4 overflow-y-auto overflow-x-hidden pb-4 max-lg:overscroll-contain">
      <div className="card flex flex-col gap-3 p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${year === nowYear && month === nowMonth ? 'bg-brand-500 text-white' : 'bg-surface-100 text-surface-800'}`}
            onClick={() => {
              setYear(nowYear);
              setMonth(nowMonth);
            }}
          >
            {r.thisMonth}
          </button>
          <button
            type="button"
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${year === nowYear && month === 'all' ? 'bg-brand-500 text-white' : 'bg-surface-100 text-surface-800'}`}
            onClick={() => {
              setYear(nowYear);
              setMonth('all');
            }}
          >
            {r.thisYear}
          </button>
          <button
            type="button"
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${year === 'all' ? 'bg-brand-500 text-white' : 'bg-surface-100 text-surface-800'}`}
            onClick={() => {
              setYear('all');
              setMonth('all');
            }}
          >
            {r.allTime}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary px-2 py-1.5" onClick={goPrev} disabled={year === 'all'} title={r.previous}>
            <ChevronLeft size={16} />
          </button>
          <label className="sr-only" htmlFor="revenue-year">{r.year}</label>
          <select
            id="revenue-year"
            className="input-field w-auto min-w-[96px]"
            value={year === 'all' ? 'all' : String(year)}
            onChange={(e) => {
              const value = e.target.value;
              setYear(value === 'all' ? 'all' : Number(value));
              if (value === 'all') setMonth('all');
            }}
          >
            <option value="all">{r.allTime}</option>
            {years.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <label className="sr-only" htmlFor="revenue-month">{r.month}</label>
          <select
            id="revenue-month"
            className="input-field w-auto min-w-[120px]"
            value={month === 'all' ? 'all' : String(month)}
            disabled={year === 'all'}
            onChange={(e) => setMonth(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          >
            <option value="all">{r.allMonths}</option>
            {months.map((label, index) => (
              <option key={label} value={index + 1}>{label}</option>
            ))}
          </select>
          <button type="button" className="btn-secondary px-2 py-1.5" onClick={goNext} disabled={!canGoNext} title={r.next}>
            <ChevronRight size={16} />
          </button>
          <button type="button" className="btn-secondary px-2 py-1.5" onClick={() => void load()} title={r.retry}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : undefined} />
          </button>
        </div>
      </div>

      {error ? (
        <div className="card flex flex-col items-center gap-3 p-8 text-sm text-surface-800/70">
          <p>{error || r.loadFailed}</p>
          <button type="button" className="btn-secondary" onClick={() => void load()}>
            {r.retry}
          </button>
        </div>
      ) : loading && !data ? (
        <div className="flex h-40 items-center justify-center text-sm text-surface-800/50">{r.loading}</div>
      ) : data ? (
        <>
          <p className="text-sm font-medium text-surface-800/70">{data.period_label}</p>

          <div className="flex flex-wrap gap-3">
            <SummaryCard
              label={r.totalRevenue}
              value={formatCurrency(data.toplam_gelir)}
              sub={changeLabel}
              icon={CircleDollarSign}
              color={change != null && change < 0 ? 'text-rose-600' : 'text-emerald-600'}
            />
            <SummaryCard
              label={r.offered}
              value={formatCurrency(data.teklif_toplami)}
              sub={data.kalan_toplam > 0 ? `${r.remaining}: ${formatCurrency(data.kalan_toplam)}` : undefined}
              icon={Wallet}
              color="text-indigo-600"
            />
            <SummaryCard
              label={r.avgSale}
              value={formatCurrency(data.ortalama_satis)}
              icon={Banknote}
              color="text-amber-600"
            />
            <SummaryCard
              label={r.salesCount}
              value={String(data.satis_sayisi)}
              sub={`${data.satis_sayisi} ${r.payments}`}
              icon={ShoppingBag}
              color="text-purple-600"
            />
            <SummaryCard
              label={r.thisMonth}
              value={formatCurrency(data.bu_ay_gelir)}
              icon={CalendarRange}
              color="text-brand-500"
            />
            <SummaryCard
              label={r.thisYear}
              value={formatCurrency(data.bu_yil_gelir)}
              icon={change != null && change < 0 ? TrendingDown : TrendingUp}
              color="text-emerald-700"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-5">
            <section className="card p-4 lg:col-span-3">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-surface-900">
                <TrendingUp size={16} className="text-brand-500" />
                {data.gunluk_gelir?.length ? r.dailyRevenue : r.monthlyRevenue}
              </h3>
              <BarChart items={chartItems} emptyLabel={r.noSalesYet} />
            </section>

            <section className="card p-4 lg:col-span-2">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-surface-900">
                <Layers size={16} className="text-brand-500" />
                {r.categoryRevenue}
              </h3>
              {data.kategori_dagilimi.length === 0 ? (
                <p className="py-8 text-sm text-surface-800/50">{r.noCategorySales}</p>
              ) : (
                <div className="space-y-3">
                  {data.kategori_dagilimi.map((item) => {
                    const width = Math.max((item.gelir / maxCategory) * 100, item.gelir > 0 ? 6 : 0);
                    return (
                      <div key={item.category} className="space-y-1">
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <span className="truncate font-medium text-surface-900">{item.category_label}</span>
                          <span className="shrink-0 text-surface-800/70">
                            {formatCurrency(item.gelir)} · {item.satis_sayisi} {r.sales}
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-surface-100">
                          <div className="h-full rounded-full bg-emerald-500" style={{ width: `${width}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          <section className="card min-w-0 overflow-hidden">
            <div className="border-b border-surface-200 px-4 py-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-surface-900">
                <ShoppingBag size={16} className="text-brand-500" />
                {r.recentSales}
              </h3>
            </div>
            {data.son_satislar.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-surface-800/50">
                {r.noRecentSales}
                <span className="mt-1 block text-xs">{r.emptyHint}</span>
              </p>
            ) : (
              <div className="min-w-0 overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-surface-100 bg-surface-50/80 text-xs uppercase tracking-wide text-surface-800/50">
                      <th className="px-4 py-2.5 font-medium">{r.business}</th>
                      <th className="px-4 py-2.5 font-medium">{r.category}</th>
                      <th className="px-4 py-2.5 font-medium">{r.city}</th>
                      <th className="px-4 py-2.5 font-medium">{r.offer}</th>
                      <th className="px-4 py-2.5 font-medium">{r.date}</th>
                      <th className="px-4 py-2.5 text-right font-medium">{r.received}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.son_satislar.map((sale) => (
                      <tr key={sale.id} className="border-b border-surface-100 last:border-0">
                        <td className="px-4 py-2.5 font-medium text-surface-900">{sale.isletme_adi}</td>
                        <td className="px-4 py-2.5 text-surface-800/70">{sale.category_label}</td>
                        <td className="px-4 py-2.5 text-surface-800/70">{sale.sehir || '—'}</td>
                        <td className="px-4 py-2.5 text-surface-800/70">{sale.teklif || '—'}</td>
                        <td className="px-4 py-2.5 text-surface-800/70">{formatSaleDate(sale.satis_tarihi, locale)}</td>
                        <td className="px-4 py-2.5 text-right font-semibold text-emerald-700">
                          {formatCurrency(sale.satis_tutari)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
