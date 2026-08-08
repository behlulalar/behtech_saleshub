import { useEffect, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { MessageTemplateId } from '../../messageTemplates';
import type { AiStatusResponse } from '../../types';

interface Props {
  leadId: number;
  templateId: MessageTemplateId;
  onSuggested: (text: string) => void;
}

export default function AiSuggestMessageButton({ leadId, templateId, onSuggested }: Props) {
  const { app, locale } = useLocale();
  const t = app.ai;
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getAiStatus()
      .then((status: AiStatusResponse) => {
        if (!cancelled) setAvailable(status.suggest_message_available);
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!available) return null;

  const handleClick = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.suggestMessage({
        lead_id: leadId,
        template_id: templateId,
        locale: locale === 'en' ? 'en' : 'tr',
      });
      onSuggested(res.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.suggestFailed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex w-full flex-col gap-1.5 sm:w-auto sm:items-end">
      <button
        type="button"
        disabled={loading}
        onClick={handleClick}
        className="btn-secondary w-full justify-center gap-2 px-4 py-2.5 text-sm sm:w-auto sm:py-2"
        title={t.suggestHint}
      >
        {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
        {loading ? t.suggestLoading : t.suggestButton}
      </button>
      {error ? <p className="text-center text-xs text-rose-600 sm:max-w-[220px] sm:text-right">{error}</p> : null}
    </div>
  );
}
