import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Loader2, Sparkles } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiStatusResponse } from '../../types';

interface Props {
  leadId: number;
}

export default function AiLeadSummary({ leadId }: Props) {
  const { app, locale } = useLocale();
  const t = app.ai;
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const key = `crm_ai_summary_${leadId}_${new Date().toISOString().slice(0, 10)}`;
    const cached = sessionStorage.getItem(key);
    if (cached) {
      setSummary(cached);
    }
  }, [leadId]);

  useEffect(() => {
    let cancelled = false;
    api
      .getAiStatus()
      .then((status: AiStatusResponse) => {
        if (!cancelled) setAvailable(Boolean(status.summarize_lead_available));
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!available) return null;

  const loadSummary = async (force = false) => {
    const key = `crm_ai_summary_${leadId}_${new Date().toISOString().slice(0, 10)}`;
    if (summary && !force) {
      setOpen((v) => !v);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.summarizeLead({
        lead_id: leadId,
        locale: locale === 'en' ? 'en' : 'tr',
      });
      setSummary(res.summary);
      sessionStorage.setItem(key, res.summary);
      setOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.summarizeFailed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="overflow-hidden rounded-xl border border-brand-100 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-brand-50 bg-brand-50/30 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5 sm:py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-600">
            <Sparkles size={18} />
          </div>
          <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{t.summarizeTitle}</h3>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => loadSummary(false)}
          className="btn-secondary w-full justify-center gap-2 px-4 py-2.5 text-sm sm:w-auto sm:py-2"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : null}
          {!loading && !summary ? t.summarizeButton : null}
          {!loading && summary ? (open ? t.summarizeHide : t.summarizeShow) : null}
          {!loading && summary ? (open ? <ChevronUp size={16} /> : <ChevronDown size={16} />) : null}
        </button>
      </div>
      {error ? <p className="px-4 py-2.5 text-sm text-rose-600 sm:px-5">{error}</p> : null}
      {open && summary ? (
        <p className="whitespace-pre-wrap px-4 py-4 text-sm leading-relaxed text-surface-800/85 sm:px-5 sm:py-5 sm:text-[15px] sm:leading-7">
          {summary}
        </p>
      ) : null}
    </section>
  );
}
