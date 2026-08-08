import { useCallback, useEffect, useState } from 'react';
import { Building2, Loader2, RefreshCw } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import { formatAppDateTime } from '../../utils';
import type { CompanyProfile } from '../../types';

interface Props {
  isOwner: boolean;
}

export default function CompanyIntelligenceCard({ isOwner }: Props) {
  const { app, locale } = useLocale();
  const t = app.companyIntel;
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getCompanyProfile(refresh);
        setProfile(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : t.loadFailed);
      } finally {
        setLoading(false);
      }
    },
    [t.loadFailed],
  );

  useEffect(() => {
    if (!isOwner) return;
    load(false);
  }, [isOwner, load]);

  if (!isOwner) return null;

  return (
    <section className="card overflow-hidden border-surface-200">
      <div className="flex flex-col gap-3 border-b border-surface-100 bg-surface-50/50 px-4 py-3.5 sm:flex-row sm:items-start sm:justify-between sm:px-5 sm:py-4">
        <div className="flex gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-600">
            <Building2 size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{t.title}</h3>
            <p className="mt-1 text-xs leading-relaxed text-surface-800/60 sm:text-sm">{t.subtitle}</p>
          </div>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => load(true)}
          className="btn-secondary w-full justify-center gap-2 py-2 text-sm sm:w-auto"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          {t.refresh}
        </button>
      </div>

      {error ? <p className="px-4 py-3 text-sm text-rose-600 sm:px-5">{error}</p> : null}

      {profile && !error ? (
        <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
          <Stat label={t.period} value={profile.period_label ?? '—'} />
          <Stat label={t.newLeads} value={String(profile.yeni_kayit ?? 0)} />
          <Stat label={t.newCustomers} value={String(profile.yeni_musteri ?? 0)} />
          <Stat
            label={t.conversion}
            value={
              profile.satis_donusum_orani != null ? `%${profile.satis_donusum_orani}` : '—'
            }
          />
          <Stat label={t.awaitingReply} value={String(profile.cevap_bekleyen_sayisi ?? 0)} />
          <Stat label={t.todayTasks} value={String(profile.bugunku_gorevler ?? 0)} />
          <Stat label={t.totalLeads} value={String(profile.total_leads ?? 0)} />
          <Stat label={t.lostStalled} value={String(profile.lost_or_stalled_leads ?? 0)} />
        </div>
      ) : null}

      {profile?.best_lead_source ? (
        <div className="border-t border-surface-100 px-4 py-3 text-sm text-surface-800/80 sm:px-5">
          {t.bestSource
            .replace('{label}', profile.best_lead_source.label ?? '')
            .replace('{rate}', String(profile.best_lead_source.win_rate_pct ?? 0))
            .replace('{n}', String(profile.best_lead_source.sample_size ?? 0))}
        </div>
      ) : null}

      {profile?.top_insights && profile.top_insights.length > 0 ? (
        <ul className="border-t border-surface-100 px-4 py-3 sm:px-5">
          {profile.top_insights.map((item) => (
            <li key={item.title} className="text-xs text-surface-800/70 sm:text-sm">
              · {item.title}
            </li>
          ))}
        </ul>
      ) : null}

      {profile?.computed_at ? (
        <p className="border-t border-surface-100 px-4 py-2 text-[11px] text-surface-800/45 sm:px-5">
          {t.updatedAt}: {formatAppDateTime(profile.computed_at, locale === 'en' ? 'en' : 'tr')}
        </p>
      ) : null}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-50 px-3 py-2.5 ring-1 ring-surface-100">
      <p className="text-[11px] text-surface-800/50">{label}</p>
      <p className="mt-0.5 text-base font-semibold tabular-nums text-surface-900">{value}</p>
    </div>
  );
}
