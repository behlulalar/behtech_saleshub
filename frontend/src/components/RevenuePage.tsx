import {
  Banknote,
  CalendarRange,
  CircleDollarSign,
  Layers,
  ShoppingBag,
  TrendingUp,
} from 'lucide-react';
import type { RevenueData } from '../types';
import { useLocale } from '../i18n/locale';
import { formatCurrency } from '../utils';

interface Props {
  data: RevenueData | null;
  loading: boolean;
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: typeof Banknote;
  color: string;
}) {
  return (
    <div className="card flex min-w-0 flex-1 basis-[calc(50%-0.375rem)] items-center gap-3 px-4 py-3 max-lg:min-w-0 lg:min-w-[140px]">
      <div className={`rounded-lg bg-surface-50 p-2 ${color}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-surface-800/50">{label}</p>
        <p className="truncate text-sm font-bold text-surface-900 lg:text-base">{value}</p>
      </div>
    </div>
  );
}

function BarRow({
  label,
  value,
  max,
  countLabel,
}: {
  label: string;
  value: number;
  max: number;
  countLabel?: string;
}) {
  const width = max > 0 ? Math.max((value / max) * 100, value > 0 ? 6 : 0) : 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="truncate font-medium text-surface-900">{label}</span>
        <span className="shrink-0 text-surface-800/70">
          {formatCurrency(value)}
          {countLabel ? ` · ${countLabel}` : ''}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-100">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all"
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function formatSaleDate(value: string, locale: string) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(locale === 'en' ? 'en-US' : 'tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

export default function RevenuePage({ data, loading }: Props) {
  const { locale, app } = useLocale();
  const r = app.revenue;

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-800/50">
        {r.loading}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-800/50">
        {r.notFound}
      </div>
    );
  }

  const maxMonth = Math.max(...data.aylik_gelir.map((item) => item.gelir), 1);
  const maxCategory = Math.max(...data.kategori_dagilimi.map((item) => item.gelir), 1);

  return (
    <div className="h-full min-w-0 space-y-4 overflow-y-auto overflow-x-hidden pb-2 max-lg:overscroll-contain">
      <div className="flex flex-wrap gap-3">
        <SummaryCard
          label={r.totalRevenue}
          value={formatCurrency(data.toplam_gelir)}
          icon={CircleDollarSign}
          color="text-emerald-600"
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
          icon={TrendingUp}
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
          icon={ShoppingBag}
          color="text-purple-600"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-surface-900">
            <TrendingUp size={16} className="text-brand-500" />
            {r.monthlyRevenue}
          </h3>
          {data.aylik_gelir.every((item) => item.gelir === 0) ? (
            <p className="text-sm text-surface-800/50">{r.noSalesYet}</p>
          ) : (
            <div className="space-y-3">
              {data.aylik_gelir.map((item) => (
                <BarRow
                  key={item.ay}
                  label={item.ay_label}
                  value={item.gelir}
                  max={maxMonth}
                />
              ))}
            </div>
          )}
        </section>

        <section className="card p-4">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-surface-900">
            <Layers size={16} className="text-brand-500" />
            {r.categoryRevenue}
          </h3>
          {data.kategori_dagilimi.length === 0 ? (
            <p className="text-sm text-surface-800/50">{r.noCategorySales}</p>
          ) : (
            <div className="space-y-3">
              {data.kategori_dagilimi.map((item) => (
                <BarRow
                  key={item.category}
                  label={item.category_label}
                  value={item.gelir}
                  max={maxCategory}
                  countLabel={`${item.satis_sayisi} ${r.sales}`}
                />
              ))}
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
          <p className="px-4 py-6 text-sm text-surface-800/50">
            {r.noRecentSales}
          </p>
        ) : (
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-surface-100 bg-surface-50/80 text-xs uppercase tracking-wide text-surface-800/50">
                  <th className="px-4 py-2.5 font-medium">{r.business}</th>
                  <th className="px-4 py-2.5 font-medium">{r.category}</th>
                  <th className="px-4 py-2.5 font-medium">{r.city}</th>
                  <th className="px-4 py-2.5 font-medium">{r.date}</th>
                  <th className="px-4 py-2.5 text-right font-medium">{r.amount}</th>
                </tr>
              </thead>
              <tbody>
                {data.son_satislar.map((sale) => (
                  <tr key={sale.id} className="border-b border-surface-100 last:border-0">
                    <td className="px-4 py-2.5 font-medium text-surface-900">{sale.isletme_adi}</td>
                    <td className="px-4 py-2.5 text-surface-800/70">{sale.category_label}</td>
                    <td className="px-4 py-2.5 text-surface-800/70">{sale.sehir || '—'}</td>
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
    </div>
  );
}
