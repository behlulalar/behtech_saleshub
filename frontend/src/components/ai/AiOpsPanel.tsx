import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Cpu, History, Loader2, MessageSquareText } from 'lucide-react';
import { api } from '../../api';
import { useLocale } from '../../i18n/locale';
import type { AiRunDetail, AiStatusResponse } from '../../types';
import { formatAppDateTime } from '../../utils';

interface Props {
  isOwner: boolean;
}

export default function AiOpsPanel({ isOwner }: Props) {
  const { app, locale } = useLocale();
  const t = app.ai;
  const [enabled, setEnabled] = useState(false);
  const [batchAvailable, setBatchAvailable] = useState(false);
  const [agentAvailable, setAgentAvailable] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchMessage, setBatchMessage] = useState<string | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentAnswer, setAgentAnswer] = useState<string | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [runs, setRuns] = useState<AiRunDetail[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsOpen, setRunsOpen] = useState(false);

  const loadRuns = useCallback(async () => {
    setRunsLoading(true);
    try {
      const res = await api.listAiRuns(8);
      setRuns(res.items);
    } catch {
      setRuns([]);
    } finally {
      setRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isOwner) return;
    let cancelled = false;
    api
      .getAiStatus()
      .then((status: AiStatusResponse) => {
        if (cancelled) return;
        setEnabled(Boolean(status.enabled));
        setBatchAvailable(Boolean(status.batch_runs_available));
        setAgentAvailable(Boolean(status.agent_runs_available));
      })
      .catch(() => {
        if (!cancelled) {
          setEnabled(false);
          setBatchAvailable(false);
          setAgentAvailable(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isOwner]);

  useEffect(() => {
    if (!isOwner || !enabled) return;
    loadRuns();
  }, [isOwner, enabled, loadRuns]);

  if (!isOwner || !enabled || (!batchAvailable && !agentAvailable)) return null;

  const runBatch = async () => {
    setBatchLoading(true);
    setBatchError(null);
    setBatchMessage(null);
    try {
      const created = await api.createAiRun({ run_type: 'batch_score', locale: locale === 'en' ? 'en' : 'tr' });
      const detail = await api.getAiRun(created.run_id);
      if (detail.status === 'failed') {
        setBatchError(t.batchScoreFailed);
        return;
      }
      const count = (detail.output?.leads_scored as number | undefined) ?? 0;
      setBatchMessage(t.batchScoreDone.replace('{count}', String(count)));
      loadRuns();
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : t.batchScoreFailed);
    } finally {
      setBatchLoading(false);
    }
  };

  const runAgent = async () => {
    const q = question.trim();
    if (!q) return;
    setAgentLoading(true);
    setAgentError(null);
    setAgentAnswer(null);
    try {
      const created = await api.createAiRun({
        run_type: 'agent',
        question: q,
        locale: locale === 'en' ? 'en' : 'tr',
      });
      const detail = await api.getAiRun(created.run_id);
      if (detail.status === 'failed') {
        setAgentError(t.agentFailed);
        return;
      }
      const answer = (detail.output?.answer as string | undefined) ?? '';
      setAgentAnswer(answer || '—');
      loadRuns();
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : t.agentFailed);
    } finally {
      setAgentLoading(false);
    }
  };

  return (
    <section className="card overflow-hidden border-surface-200">
      <div className="grid gap-0 lg:grid-cols-2 lg:divide-x lg:divide-surface-100">
        {batchAvailable ? (
          <div className="p-4 sm:p-5">
            <div className="mb-3 flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-100 text-surface-700">
                <Cpu size={20} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{t.batchScoreTitle}</h3>
                <p className="mt-1 text-xs leading-relaxed text-surface-800/60 sm:text-sm">{t.batchScoreHint}</p>
              </div>
            </div>
            <button
              type="button"
              disabled={batchLoading}
              onClick={runBatch}
              className="btn-secondary w-full justify-center gap-2 py-2.5 text-sm sm:w-auto"
            >
              {batchLoading ? <Loader2 size={16} className="animate-spin" /> : null}
              {batchLoading ? t.batchScoreRunning : t.batchScoreButton}
            </button>
            {batchMessage ? <p className="mt-3 text-sm text-emerald-700">{batchMessage}</p> : null}
            {batchError ? <p className="mt-3 text-sm text-rose-600">{batchError}</p> : null}
          </div>
        ) : null}

        {agentAvailable ? (
          <div className="border-t border-surface-100 p-4 sm:p-5 lg:border-t-0">
            <div className="mb-3 flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-600">
                <MessageSquareText size={20} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{t.agentTitle}</h3>
              </div>
            </div>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder={t.agentPlaceholder}
              className="input-field min-h-[88px] resize-y text-sm"
            />
            <button
              type="button"
              disabled={agentLoading || !question.trim()}
              onClick={runAgent}
              className="btn-primary mt-3 w-full justify-center gap-2 py-2.5 text-sm sm:w-auto"
            >
              {agentLoading ? <Loader2 size={16} className="animate-spin" /> : null}
              {agentLoading ? t.agentRunning : t.agentAsk}
            </button>
            {agentAnswer ? (
              <p className="mt-3 whitespace-pre-wrap rounded-xl bg-surface-50 p-3 text-sm leading-relaxed text-surface-800/85">
                {agentAnswer}
              </p>
            ) : null}
            {agentError ? <p className="mt-3 text-sm text-rose-600">{agentError}</p> : null}
          </div>
        ) : null}
      </div>

      <div className="border-t border-surface-100 bg-surface-50/40 px-4 py-3 sm:px-5 sm:py-3">
        <button
          type="button"
          onClick={() => setRunsOpen((v) => !v)}
          className="flex w-full items-center gap-2 rounded-lg py-1 text-left transition hover:bg-white/60"
        >
          <History size={16} className="shrink-0 text-surface-800/45" />
          <span className="text-xs font-semibold uppercase tracking-wide text-surface-800/50">
            {t.runHistoryTitle}
          </span>
          {runs.length > 0 ? (
            <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-surface-800/60 ring-1 ring-surface-200">
              {runs.length}
            </span>
          ) : null}
          <span className="ml-auto text-xs font-medium text-brand-600">
            {runsOpen ? t.runHistoryHide : t.runHistoryShow}
          </span>
          {runsOpen ? (
            <ChevronUp size={16} className="shrink-0 text-surface-800/40" />
          ) : (
            <ChevronDown size={16} className="shrink-0 text-surface-800/40" />
          )}
        </button>

        {runsOpen ? (
          <div className="mt-3 border-t border-surface-100/80 pt-3">
            {runsLoading ? (
              <div className="flex items-center gap-2 text-xs text-surface-800/45">
                <Loader2 size={14} className="animate-spin" />
              </div>
            ) : runs.length === 0 ? (
              <p className="text-xs text-surface-800/45">{t.runHistoryEmpty}</p>
            ) : (
              <ul className="max-h-48 space-y-1.5 overflow-y-auto pr-1">
                {runs.map((run) => (
                  <li
                    key={run.id}
                    className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-lg bg-white px-3 py-2 text-xs ring-1 ring-surface-200"
                  >
                    <span className="font-medium text-surface-900">
                      {run.run_type === 'batch_score' ? t.runTypeBatch : t.runTypeAgent}
                    </span>
                    <span className="tabular-nums text-surface-800/55">
                      {formatAppDateTime(run.created_at, locale === 'en' ? 'en' : 'tr')}
                    </span>
                    <span
                      className={
                        run.status === 'failed'
                          ? 'font-medium text-rose-600'
                          : run.status === 'done' || run.status === 'success'
                            ? 'font-medium text-emerald-700'
                            : 'text-surface-800/60'
                      }
                    >
                      {run.status === 'failed'
                        ? t.runStatusFailed
                        : run.status === 'done'
                          ? t.runStatusDone
                          : run.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
