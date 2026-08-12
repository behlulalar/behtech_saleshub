import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { ApiHttpError, api } from '../../api';
import { useLocale } from '../../i18n/locale';
import { formatAppDateTime, parseApiDateTime } from '../../utils';
import type {
  DiagnosisHistoryInterpretResponse,
  DiagnosisHistoryResponse,
  DiagnosisItem,
  DiagnosisPriorityLead,
  DiagnosisTrendSummary,
} from '../../types';
import {
  activeDaysFromSeconds,
  formatSignedNumber,
  lifecycleStateClass,
  lifecycleStateLabel,
  metricLabel,
  periodKeyForDiagnosis,
  reasonCodeLabel,
  trendChangeLines,
  trendDirectionClass,
  trendDirectionLabel,
  type CaseSummary,
  type SalesDiagnosesCopy,
} from './diagnosisHistoryUi';

const severityClass: Record<string, string> = {
  low: 'bg-surface-100 text-surface-700',
  medium: 'bg-amber-50 text-amber-800',
  high: 'bg-rose-50 text-rose-800',
  critical: 'bg-rose-100 text-rose-900',
};

const priorityClass: Record<string, string> = {
  high: 'bg-rose-50 text-rose-800',
  medium: 'bg-amber-50 text-amber-800',
  low: 'bg-surface-100 text-surface-700',
};

type Props = {
  diagnosis: DiagnosisItem;
  open: boolean;
  onClose: () => void;
  onCaseSummary?: (diagnosisId: string, summary: CaseSummary) => void;
  onEditLead?: (leadId: number) => void;
};

function durationDaysLabel(
  firstSeen: string | null | undefined,
  endIso: string | null | undefined,
  copy: SalesDiagnosesCopy,
): string {
  if (!firstSeen) return copy.placeholderDash;
  const start = parseApiDateTime(firstSeen);
  const end = endIso ? parseApiDateTime(endIso) : new Date();
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return copy.placeholderDash;
  const ms = Math.max(0, end.getTime() - start.getTime());
  const days = Math.max(0, Math.floor(ms / (24 * 60 * 60 * 1000)));
  return copy.durationDays.replace('{n}', String(days));
}

function triggerLabel(trigger: string, copy: SalesDiagnosesCopy): string {
  if (trigger === 'resolve') return copy.triggerResolve;
  if (trigger === 'sync') return copy.triggerSync;
  return trigger || copy.placeholderDash;
}

function formatValue(value: number | null | undefined, copy: SalesDiagnosesCopy): string {
  if (value == null || Number.isNaN(value)) return copy.placeholderDash;
  return String(value);
}

export default function DiagnosisDetailModal({
  diagnosis,
  open,
  onClose,
  onCaseSummary,
  onEditLead,
}: Props) {
  const { app, locale } = useLocale();
  const copy = app.salesDiagnoses;
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [errorKind, setErrorKind] = useState<'none' | 'notFound' | 'failed'>('none');
  const [history, setHistory] = useState<DiagnosisHistoryResponse | null>(null);
  const [historyAiAvailability, setHistoryAiAvailability] = useState<
    'loading' | 'available' | 'unavailable'
  >('loading');
  const [historyAiLoading, setHistoryAiLoading] = useState(false);
  const [historyAiError, setHistoryAiError] = useState(false);
  const [historyAi, setHistoryAi] = useState<DiagnosisHistoryInterpretResponse | null>(null);
  const onCaseSummaryRef = useRef(onCaseSummary);
  onCaseSummaryRef.current = onCaseSummary;

  const periodKey = periodKeyForDiagnosis(diagnosis);
  const diagnosisId = diagnosis.diagnosis_id;

  const loadPage = useCallback(
    async (page: number, append: boolean) => {
      if (append) setLoadingMore(true);
      else {
        setLoading(true);
        setErrorKind('none');
        setHistory(null);
      }
      try {
        const data = await api.getDiagnosisHistory(diagnosisId, {
          periodKey,
          page,
          limit: 20,
        });
        setHistory((prev) => {
          if (!append || !prev) return data;
          const seen = new Set(prev.snapshots.map((s) => s.id));
          const merged = [
            ...prev.snapshots,
            ...data.snapshots.filter((s) => !seen.has(s.id)),
          ];
          // Keep first-page trend (full-history server calc); pagination must not recompute.
          return {
            ...data,
            snapshots: merged,
            page: data.page,
            total: data.total,
            trend: prev.trend ?? data.trend,
          };
        });
        onCaseSummaryRef.current?.(diagnosisId, {
          state: data.state,
          first_seen_at: data.first_seen_at,
          last_seen_at: data.last_seen_at,
          resolved_at: data.resolved_at,
        });
        setErrorKind('none');
      } catch (err) {
        if (!append) {
          setHistory(null);
          if (err instanceof ApiHttpError && err.status === 404) {
            setErrorKind('notFound');
          } else {
            setErrorKind('failed');
          }
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [diagnosisId, periodKey],
  );

  useEffect(() => {
    if (!open) return;
    void loadPage(1, false);
    setHistoryAi(null);
    setHistoryAiError(false);
    setHistoryAiAvailability('loading');
    void api
      .getAiStatus()
      .then((status) => {
        setHistoryAiAvailability(
          status.diagnosis_history_interpret_available ? 'available' : 'unavailable',
        );
      })
      .catch(() => setHistoryAiAvailability('unavailable'));
  }, [open, diagnosisId, periodKey, loadPage]);

  const runHistoryAi = useCallback(async () => {
    if (historyAiLoading || historyAiAvailability !== 'available') return;
    setHistoryAiLoading(true);
    setHistoryAiError(false);
    try {
      const response = await api.interpretDiagnosisHistory({
        diagnosis_id: diagnosisId,
        period_key: periodKey,
        locale,
        refresh: false,
      });
      setHistoryAi(response);
      if (response.error_code || !response.interpretation) {
        setHistoryAiError(true);
      }
    } catch {
      setHistoryAi(null);
      setHistoryAiError(true);
    } finally {
      setHistoryAiLoading(false);
    }
  }, [diagnosisId, historyAiAvailability, historyAiLoading, locale, periodKey]);

  if (!open) return null;

  const latestSnap = history?.snapshots?.[0];
  const metricSource = latestSnap?.metric || diagnosis.metric;
  const currentValue = latestSnap?.current_value ?? diagnosis.current_value;
  const previousValue = latestSnap?.engine_previous_value ?? diagnosis.previous_value;
  const changePercent = latestSnap?.change_percent ?? diagnosis.change_percent;
  const caseState = history?.state;
  const isResolved = caseState === 'resolved';
  const durationEnd = isResolved ? history?.resolved_at : undefined;
  const hasMore =
    history != null && history.snapshots.length < history.total && history.total > 0;
  const trend: DiagnosisTrendSummary | null | undefined = history?.trend;
  const changeLines = trend ? trendChangeLines(trend, copy) : [];
  const engineLeads = diagnosis.top_priority_leads ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`diagnosis-detail-title-${diagnosis.diagnosis_id}`}
        className="flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-t-xl bg-white shadow-lg sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-surface-100 px-4 py-3 sm:px-5">
          <div className="min-w-0">
            <h4
              id={`diagnosis-detail-title-${diagnosis.diagnosis_id}`}
              className="text-base font-semibold text-surface-900"
            >
              {diagnosis.title}
            </h4>
            <p className="mt-0.5 text-xs text-surface-600">{copy.history}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-surface-500 hover:bg-surface-100 hover:text-surface-800"
            aria-label={copy.closeDetails}
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-5">
          {loading ? (
            <p className="flex items-center gap-2 text-sm text-surface-700">
              <Loader2 size={16} className="animate-spin text-violet-600" aria-hidden />
              {copy.history}
            </p>
          ) : null}

          {!loading && errorKind === 'notFound' ? (
            <p className="text-sm text-surface-700">{copy.historyNotFound}</p>
          ) : null}
          {!loading && errorKind === 'failed' ? (
            <p className="text-sm text-rose-700">{copy.historyLoadFailed}</p>
          ) : null}

          {!loading && history ? (
            <>
              {/* A) Lifecycle status (Case.state — not trend.direction) */}
              <section>
                <h5 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                  {copy.diagnosisStatus}
                </h5>
                {isResolved ? (
                  <p className="mt-2 text-sm text-surface-700">{copy.noLongerActive}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${lifecycleStateClass(history.state)}`}
                  >
                    {lifecycleStateLabel(history.state, copy)}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase ${severityClass[diagnosis.severity] ?? severityClass.medium}`}
                  >
                    {diagnosis.severity}
                  </span>
                </div>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-surface-500">{copy.firstSeen}</dt>
                    <dd className="text-surface-900">
                      {history.first_seen_at
                        ? formatAppDateTime(history.first_seen_at, locale)
                        : copy.placeholderDash}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-surface-500">{copy.lastUpdated}</dt>
                    <dd className="text-surface-900">
                      {history.last_seen_at
                        ? formatAppDateTime(history.last_seen_at, locale)
                        : copy.placeholderDash}
                    </dd>
                  </div>
                  {history.resolved_at ? (
                    <div>
                      <dt className="text-xs text-surface-500">{copy.resolvedAt}</dt>
                      <dd className="text-surface-900">
                        {formatAppDateTime(history.resolved_at, locale)}
                      </dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-xs text-surface-500">{copy.durationLabel}</dt>
                    <dd className="text-surface-900">
                      {trend?.metrics?.active_duration_seconds != null
                        ? activeDaysFromSeconds(trend.metrics.active_duration_seconds, copy)
                        : durationDaysLabel(history.first_seen_at, durationEnd, copy)}
                    </dd>
                  </div>
                </dl>
              </section>

              {/* B) Deterministic trend (server-side) */}
              {trend ? (
                <section>
                  <h5 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                    {copy.trendSection}
                  </h5>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${trendDirectionClass(trend.direction)}`}
                    >
                      {trendDirectionLabel(trend.direction, copy)}
                    </span>
                    {trend.metrics.reopen_count > 0 ? (
                      <span className="text-xs text-surface-600">
                        {copy.trendReopenCount}: {trend.metrics.reopen_count}
                      </span>
                    ) : null}
                  </div>

                  {trend.metrics.last_substantive_change_at ? (
                    <p className="mt-2 text-xs text-surface-600">
                      {copy.trendLastChange}:{' '}
                      {formatAppDateTime(trend.metrics.last_substantive_change_at, locale)}
                    </p>
                  ) : null}

                  {changeLines.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-sm text-surface-800">
                      {changeLines.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  ) : trend.direction !== 'newly_detected' && trend.direction !== 'resolved' ? (
                    <p className="mt-2 text-sm text-surface-600">{copy.trendNoChanges}</p>
                  ) : null}

                  {trend.reason_codes.length > 0 ? (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-surface-500">{copy.trendReasons}</p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-surface-800">
                        {trend.reason_codes.map((code) => (
                          <li key={code}>{reasonCodeLabel(code, copy)}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {trend.metrics.worst_point ? (
                    <p className="mt-3 text-xs text-surface-600">
                      <span className="font-medium text-surface-700">{copy.trendWorstPoint}: </span>
                      {trend.metrics.worst_point.severity}
                      {' · '}
                      {copy.currentValue}:{' '}
                      {formatValue(trend.metrics.worst_point.current_value, copy)}
                      {' · '}
                      {copy.affectedLeads}: {trend.metrics.worst_point.affected_lead_count}
                      {trend.metrics.worst_point.observed_at
                        ? ` · ${formatAppDateTime(trend.metrics.worst_point.observed_at, locale)}`
                        : ''}
                    </p>
                  ) : null}
                </section>
              ) : null}

              {/* B2) Historical AI — manual only, separate from live DE-3 interpret */}
              <section className="rounded-lg border border-surface-100 bg-surface-50/60 px-3 py-3">
                <h5 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                  {copy.historyAiSection}
                </h5>
                <p className="mt-1 text-xs text-surface-600">{copy.historyAiDisclaimer}</p>
                <button
                  type="button"
                  disabled={historyAiLoading || historyAiAvailability !== 'available'}
                  onClick={() => void runHistoryAi()}
                  className="mt-3 inline-flex items-center gap-2 rounded-lg bg-surface-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-surface-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {historyAiLoading ? (
                    <Loader2 size={14} className="animate-spin" aria-hidden />
                  ) : null}
                  {historyAiLoading ? copy.historyAiLoading : copy.historyAiButton}
                </button>
                {historyAiAvailability === 'unavailable' ? (
                  <p className="mt-2 text-xs text-surface-600">{copy.historyAiUnavailable}</p>
                ) : null}
                {historyAiError && !historyAi?.interpretation ? (
                  <p className="mt-2 text-xs text-rose-700">{copy.historyAiFailed}</p>
                ) : null}
                {historyAi?.interpretation ? (
                  <div className="mt-3 space-y-2 text-sm text-surface-800">
                    {historyAi.cached ? (
                      <p className="text-xs font-medium text-sky-800">{copy.historyAiCached}</p>
                    ) : null}
                    <p>{historyAi.interpretation.summary}</p>
                    <div>
                      <p className="text-xs font-medium text-surface-500">{copy.historyAiWhatChanged}</p>
                      <p className="mt-0.5">{historyAi.interpretation.what_changed}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-surface-500">{copy.historyAiWhyMatters}</p>
                      <p className="mt-0.5">{historyAi.interpretation.why_it_matters}</p>
                    </div>
                    {historyAi.interpretation.key_points.length > 0 ? (
                      <div>
                        <p className="text-xs font-medium text-surface-500">{copy.historyAiKeyPoints}</p>
                        <ul className="mt-1 list-disc space-y-0.5 pl-4">
                          {historyAi.interpretation.key_points.map((point) => (
                            <li key={point}>{point}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {historyAi.disclaimer ? (
                      <p className="text-xs text-surface-500">{historyAi.disclaimer}</p>
                    ) : null}
                  </div>
                ) : null}
              </section>

              {/* C) Metric */}
              <section>
                <h5 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                  {copy.metricSection}
                </h5>
                <p className="mt-2 text-sm font-medium text-surface-900">
                  {metricLabel(metricSource, copy)}
                </p>
                <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-surface-500">{copy.currentValue}</dt>
                    <dd>{formatValue(currentValue, copy)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-surface-500">{copy.previousValue}</dt>
                    <dd>{formatValue(previousValue, copy)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-surface-500">{copy.change}</dt>
                    <dd>
                      {formatSignedNumber(changePercent) != null
                        ? `${formatSignedNumber(changePercent)}%`
                        : copy.placeholderDash}
                    </dd>
                  </div>
                </dl>
              </section>

              {/* D) Engine leads */}
              <section>
                <h5 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                  {copy.affectedLeads}
                </h5>
                {diagnosis.affected_leads_available === false ? (
                  <p className="mt-2 text-xs text-surface-600">{copy.noLeadPriorityList}</p>
                ) : null}
                {engineLeads.length === 0 ? (
                  <p className="mt-2 text-sm text-surface-600">{copy.placeholderDash}</p>
                ) : (
                  <ul className="mt-2 space-y-1.5">
                    {engineLeads.map((row: DiagnosisPriorityLead) => (
                      <li
                        key={row.lead_id}
                        className="flex items-center gap-2 rounded-lg border border-surface-100 bg-surface-50/80 px-2.5 py-2 text-xs"
                      >
                        <span
                          className={`shrink-0 rounded-full px-2 py-0.5 font-medium uppercase ${priorityClass[row.priority] ?? priorityClass.medium}`}
                        >
                          {row.priority}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium text-surface-900">{row.lead_name}</p>
                          <p className="text-surface-600/80">
                            {copy.scoreLabel} {row.diagnosis_priority_score}
                          </p>
                        </div>
                        {onEditLead ? (
                          <button
                            type="button"
                            onClick={() => onEditLead(row.lead_id)}
                            className="shrink-0 text-violet-700 hover:text-violet-900"
                          >
                            {copy.openLead}
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* E) Timeline — display only; no client-side trend math */}
              <section>
                <h5 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                  {copy.timeline}
                </h5>
                {history.snapshots.length === 0 ? (
                  <p className="mt-2 text-sm text-surface-700">{copy.historyEmpty}</p>
                ) : (
                  <ol className="mt-3 space-y-3">
                    {history.snapshots.map((snap) => (
                      <li
                        key={snap.id}
                        className="relative border-l-2 border-violet-100 pl-3"
                      >
                        <p className="text-xs font-medium text-surface-500">
                          {formatAppDateTime(snap.observed_at, locale)}
                          <span className="ml-2 text-surface-400">
                            {triggerLabel(snap.trigger, copy)}
                          </span>
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${lifecycleStateClass(snap.state)}`}
                          >
                            {lifecycleStateLabel(snap.state, copy)}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase ${severityClass[snap.severity] ?? severityClass.medium}`}
                          >
                            {snap.severity}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-surface-800">
                          {copy.affectedLeads}: {snap.affected_lead_count}
                          {' · '}
                          {copy.currentValue}: {formatValue(snap.current_value, copy)}
                          {snap.change_percent != null
                            ? ` · ${copy.change}: ${formatSignedNumber(snap.change_percent)}%`
                            : ''}
                        </p>
                      </li>
                    ))}
                  </ol>
                )}
                {hasMore ? (
                  <button
                    type="button"
                    disabled={loadingMore}
                    onClick={() => void loadPage((history.page ?? 1) + 1, true)}
                    className="mt-3 text-xs font-medium text-violet-700 hover:text-violet-900 disabled:opacity-50"
                  >
                    {loadingMore ? (
                      <span className="inline-flex items-center gap-1">
                        <Loader2 size={12} className="animate-spin" />
                        {copy.loadMoreHistory}
                      </span>
                    ) : (
                      copy.loadMoreHistory
                    )}
                  </button>
                ) : null}
              </section>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
