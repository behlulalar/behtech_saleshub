import { useEffect, useState } from 'react';
import {
  CalendarDays,
  Clock,
  Filter,
  Layers,
  MapPin,
  MessageCircle,
  Percent,
} from 'lucide-react';
import { api } from '../api';
import SalesFunnel from './SalesFunnel';
import type { AnalyticsData, AnalyticsView, DailyContactAnalytics } from '../types';
import { FUNNEL_STAGE_COLORS } from '../types';
import { useLocale } from '../i18n/locale';

const viewIcons: Record<AnalyticsView, typeof Filter> = {
  'satis-hunisi': Filter,
  'analiz-donusum': Percent,
  'analiz-sehir': MapPin,
  'analiz-kategori': Layers,
  'analiz-saat': Clock,
  'analiz-gun': CalendarDays,
  'analiz-gunluk-iletisim': MessageCircle,
};

interface Props {
  view: AnalyticsView;
  data: AnalyticsData | null;
  loading: boolean;
}

function BarRow({
  label,
  value,
  max,
  suffix,
  highlight,
}: {
  label: string;
  value: number;
  max: number;
  suffix?: string;
  highlight?: string;
}) {
  const width = max > 0 ? Math.max((value / max) * 100, value > 0 ? 8 : 0) : 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="truncate font-medium text-surface-900">{label}</span>
        <span className="shrink-0 text-surface-800/70">
          {value}{suffix ? ` ${suffix}` : ''}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-100">
        <div
          className={`h-full rounded-full transition-all ${highlight || 'bg-brand-500'}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-surface-200 py-12 text-center text-sm text-surface-800/50">
      {text}
    </div>
  );
}

export default function AnalyticsPage({ view, data, loading }: Props) {
  const { app } = useLocale();
  const a = app.analyticsPage;
  const meta = app.views.analytics[view];
  const Icon = viewIcons[view];

  const [contactDate, setContactDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [dailyContact, setDailyContact] = useState<DailyContactAnalytics | null>(null);
  const [contactLoading, setContactLoading] = useState(false);
  const [contactError, setContactError] = useState('');

  useEffect(() => {
    if (view !== 'analiz-gunluk-iletisim') return;

    let cancelled = false;
    setContactLoading(true);
    setContactError('');
    api
      .getDailyContactAnalytics(contactDate)
      .then((result) => {
        if (!cancelled) setDailyContact(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setContactError(err instanceof Error ? err.message : a.loading);
          setDailyContact(null);
        }
      })
      .finally(() => {
        if (!cancelled) setContactLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [view, contactDate, a.loading]);

  if (view === 'analiz-gunluk-iletisim') {
    const maxCount = Math.max(...(dailyContact?.kategori_bazli.map((item) => item.iletisim_sayisi) ?? [0]), 1);

    return (
      <div className="mx-auto min-w-0 max-w-4xl space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="brand-icon-box h-9 w-9 lg:h-10 lg:w-10">
              <Icon size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-surface-900 lg:text-lg">{meta.title}</h2>
              <p className="text-xs text-surface-800/50 lg:text-sm">{meta.description}</p>
            </div>
          </div>
          <div>
            <label className="label-field">{a.pickDate}</label>
            <input
              type="date"
              className="input-field"
              value={contactDate}
              onChange={(e) => setContactDate(e.target.value)}
            />
          </div>
        </div>

        {contactLoading ? (
          <div className="flex items-center justify-center py-24 text-surface-800/50">{a.loading}</div>
        ) : contactError ? (
          <EmptyState text={contactError} />
        ) : dailyContact ? (
          <div className="card p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-800">
              <span>
                {a.dailyContactTitle}: <strong>{dailyContact.date_label}</strong>
              </span>
              <span>
                {a.dailyContactTotal}: <strong>{dailyContact.toplam_iletisim}</strong> {a.dailyContactPeople}
              </span>
            </div>
            <p className="mb-4 text-xs text-surface-800/55">{a.dailyContactHint}</p>
            {dailyContact.kategori_bazli.length === 0 ? (
              <EmptyState text={a.dailyContactEmpty} />
            ) : (
              <div className="space-y-4">
                {dailyContact.kategori_bazli.map((item) => (
                  <BarRow
                    key={item.category}
                    label={item.category_label}
                    value={item.iletisim_sayisi}
                    max={maxCount}
                    suffix={a.dailyContactPeople}
                    highlight="bg-teal-500"
                  />
                ))}
              </div>
            )}
          </div>
        ) : null}
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-24 text-surface-800/50">
        {a.loading}
      </div>
    );
  }

  const topCity = data.sehir_analizi[0];
  const topCategory = data.kategori_analizi[0];
  const topHour = data.saat_analizi.find((item) => item.mesaj_sayisi > 0);
  const topDay = data.gun_analizi.find((item) => item.mesaj_sayisi > 0);

  return (
    <div className="mx-auto min-w-0 max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="brand-icon-box h-9 w-9 lg:h-10 lg:w-10">
          <Icon size={18} />
        </div>
        <div>
          <h2 className="text-sm font-bold text-surface-900 lg:text-lg">{meta.title}</h2>
          <p className="text-xs text-surface-800/50 lg:text-sm">{meta.description}</p>
        </div>
      </div>

      {view === 'satis-hunisi' && (
        data.satis_hunisi.every((stage) => stage.count === 0) ? (
          <EmptyState text={a.noFunnelData} />
        ) : (
          <SalesFunnel stages={data.satis_hunisi} conversionRate={data.satis_donusum_orani} />
        )
      )}

      {view === 'analiz-donusum' && (
        <div className="card overflow-hidden">
          <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-3">
            <Percent size={16} className="text-brand-500" />
            <h3 className="text-sm font-semibold text-surface-900">{a.stageSuccessRates}</h3>
          </div>
          <div className="divide-y divide-surface-100">
            {data.donusum_oranlari.map((stage) => (
              <div key={stage.key} className="grid gap-3 px-4 py-4 sm:grid-cols-4 sm:items-center">
                <div className="flex items-center gap-2">
                  <span className={`h-3 w-3 shrink-0 rounded-full ${FUNNEL_STAGE_COLORS[stage.key] || 'bg-brand-500'}`} />
                  <div>
                    <p className="font-medium text-surface-900">{stage.label}</p>
                    <p className="text-sm text-surface-800/50">{stage.count} {a.records}</p>
                  </div>
                </div>
                <div className="text-sm">
                  <p className="text-surface-800/50">{a.fromPreviousStage}</p>
                  <p className="font-semibold text-brand-500">
                    {stage.onceki_asama_orani !== null ? `%${stage.onceki_asama_orani}` : '—'}
                  </p>
                </div>
                <div className="text-sm">
                  <p className="text-surface-800/50">{a.toNextStage}</p>
                  <p className="font-semibold text-emerald-600">
                    {stage.asama_basari_orani !== null ? `%${stage.asama_basari_orani}` : '—'}
                  </p>
                </div>
                <div className="text-sm">
                  <p className="text-surface-800/50">{a.withinTotal}</p>
                  <p className="font-semibold text-surface-900">%{stage.toplam_orani}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'analiz-sehir' && (
        <div className="card p-4">
          {topCity && (
            <div className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
              {a.topCity}: <strong>{topCity.sehir}</strong> · {topCity.satis} {a.sales} · %{topCity.satis_orani}
            </div>
          )}
          {data.sehir_analizi.length === 0 ? (
            <EmptyState text={a.noCityData} />
          ) : (
            <div className="space-y-4">
              {data.sehir_analizi.map((item) => (
                <BarRow
                  key={item.sehir}
                  label={`${item.sehir} · ${item.satis} ${a.sales}`}
                  value={item.satis_orani}
                  max={100}
                  suffix={`(%${item.satis_orani})`}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {view === 'analiz-kategori' && (
        <div className="card p-4">
          {topCategory && (
            <div className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
              {a.topCategory}: <strong>{topCategory.category_label}</strong> · {topCategory.satis} {a.sales} · %{topCategory.satis_orani}
            </div>
          )}
          {data.kategori_analizi.length === 0 ? (
            <EmptyState text={a.noCategoryData} />
          ) : (
            <div className="space-y-4">
              {data.kategori_analizi.map((item) => (
                <BarRow
                  key={item.category}
                  label={`${item.category_label} · ${item.satis}/${item.toplam} ${a.sales}`}
                  value={item.satis_orani}
                  max={100}
                  suffix={`(%${item.satis_orani})`}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {view === 'analiz-saat' && (
        <div className="card p-4">
          {topHour ? (
            <div className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
              {a.topHour}: <strong>{topHour.saat_label}</strong> · {topHour.cevap_sayisi} · %{topHour.cevap_orani}
            </div>
          ) : (
            <div className="mb-4 rounded-xl bg-surface-50 px-4 py-3 text-sm text-surface-800/60">
              Saat analizi için müşterilere ilk mesaj saati ekleyin.
            </div>
          )}
          <div className="space-y-3">
            {data.saat_analizi
              .filter((item) => item.mesaj_sayisi > 0)
              .slice(0, 12)
              .map((item) => (
                <BarRow
                  key={item.saat}
                  label={`${item.saat_label} · ${item.cevap_sayisi}/${item.mesaj_sayisi} cevap`}
                  value={item.cevap_orani}
                  max={100}
                  suffix={`(%${item.cevap_orani})`}
                  highlight="bg-indigo-500"
                />
              ))}
          </div>
        </div>
      )}

      {view === 'analiz-gun' && (
        <div className="card p-4">
          {topDay ? (
            <div className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
              {a.topDay}: <strong>{topDay.gun_label}</strong> · {topDay.cevap_sayisi} · %{topDay.cevap_orani}
            </div>
          ) : (
            <div className="mb-4 rounded-xl bg-surface-50 px-4 py-3 text-sm text-surface-800/60">
              Gün analizi için müşterilere ilk mesaj tarihi ekleyin.
            </div>
          )}
          <div className="space-y-3">
            {data.gun_analizi
              .filter((item) => item.mesaj_sayisi > 0)
              .map((item) => (
                <BarRow
                  key={item.gun}
                  label={`${item.gun_label} · ${item.cevap_sayisi}/${item.mesaj_sayisi} cevap`}
                  value={item.cevap_orani}
                  max={100}
                  suffix={`(%${item.cevap_orani})`}
                  highlight="bg-purple-500"
                />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
