import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ChevronRight, Loader2, RefreshCw, Sparkles, Stethoscope } from 'lucide-react';
import { ApiHttpError, api } from '../../api';
import { useLocale } from '../../i18n/locale';
import { formatAppDateTime } from '../../utils';
import type { DiagnosisItem, DiagnosisInterpretResponse, DiagnosisPriorityLead } from '../../types';
import DiagnosisBridgeActionsPanel from './DiagnosisBridgeActionsPanel';
import DiagnosisDetailModal from './DiagnosisDetailModal';
import {
  type CaseSummary,
  lifecycleStateClass,
  lifecycleStateLabel,
} from './diagnosisHistoryUi';
import { uniqueActionIds } from './de4ActionDedup';
import { aiPriorityBadgeClass, aiPriorityLabel } from './aiPriorityUi';
import {
  type InterpretAvailability,
  type InterpretUiState,
  hasRenderableInterpretation,
  interpretPrimaryAction,
  interpretResponseToUiState,
  isInterpretButtonDisabled,
  mapHttpStatusToInterpretError,
} from './salesDiagnosesInterpretLogic';

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
  onEditLead?: (leadId: number) => void;
  onDe4ActionChanged?: () => void;
};

function PriorityLeadRow({
  row,
  onEditLead,
  copy,
}: {
  row: DiagnosisPriorityLead;
  onEditLead?: (leadId: number) => void;
  copy: (typeof import('../../i18n/app').appCopy)['tr']['salesDiagnoses'];
}) {
  return (
    <li className="flex items-center gap-2 rounded-lg border border-surface-100 bg-surface-50/80 px-2.5 py-2 text-xs">
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 font-medium uppercase ${priorityClass[row.priority] ?? priorityClass.medium}`}
      >
        {row.priority}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-surface-900">{row.lead_name}</p>
        <p className="text-surface-600/80">
          {copy.scoreLabel} {row.diagnosis_priority_score}
          {row.diagnosis_modifier > 0
            ? ` (+${row.diagnosis_modifier} ${copy.diagnosisModifierSuffix})`
            : ''}
          {row.idle_days != null ? ` · ${row.idle_days} ${copy.daysSuffix}` : ''}
          {row.offer_age_days != null ? ` · ${copy.offerAgeSuffix} ${row.offer_age_days} ${copy.daysSuffix}` : ''}
        </p>
      </div>
      {onEditLead ? (
        <button
          type="button"
          onClick={() => onEditLead(row.lead_id)}
          className="flex shrink-0 items-center gap-0.5 text-violet-700 hover:text-violet-900"
        >
          {copy.openLead}
          <ChevronRight size={14} />
        </button>
      ) : null}
    </li>
  );
}

function InterpretationBody({
  response,
  labels,
  priorityLabels,
  onOpenLead,
  onDe4ActionChanged,
}: {
  response: DiagnosisInterpretResponse;
  labels: (typeof import('../../i18n/app').appCopy)['tr']['ai'];
  priorityLabels: Record<string, string>;
  onOpenLead?: (leadId: number) => void;
  onDe4ActionChanged?: () => void;
}) {
  const interp = response.interpretation;
  if (!interp || !hasRenderableInterpretation(response)) return null;

  const findings = (interp.key_findings ?? []).filter((line) => line?.trim());
  const actions = interp.recommended_actions ?? [];
  const bridgeActionIds = uniqueActionIds(response.proposal_bridge?.action_ids?.filter(Boolean) ?? []);

  return (
    <div className="space-y-3 text-sm text-surface-800">
      {response.cached ? (
        <p className="text-xs font-medium text-violet-700/90">{labels.diagnosisInterpretCachedBadge}</p>
      ) : null}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
          {labels.diagnosisInterpretSummary}
        </h4>
        <p className="mt-1 leading-relaxed">{interp.summary}</p>
      </div>
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
          {labels.diagnosisInterpretWhy}
        </h4>
        <p className="mt-1 leading-relaxed">{interp.why_it_matters}</p>
      </div>
      {findings.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
            {labels.diagnosisInterpretFindings}
          </h4>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-sm">
            {findings.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {actions.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-surface-500">
            {labels.diagnosisInterpretActions}
          </h4>
          <ol className="mt-2 space-y-2">
            {actions.map((action, idx) => (
              <li
                key={`${action.title}-${idx}`}
                className="rounded-lg border border-surface-100 bg-white px-3 py-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-surface-900">
                    {idx + 1}. {action.title}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${aiPriorityBadgeClass(action.priority)}`}
                  >
                    {aiPriorityLabel(action.priority, priorityLabels)}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-surface-700">{action.reason}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      <DiagnosisBridgeActionsPanel
        actionIds={bridgeActionIds}
        onOpenLead={onOpenLead}
        onLifecycleChange={onDe4ActionChanged}
      />
      <p className="text-xs text-surface-600">
        <span className="font-medium text-surface-700">{labels.diagnosisInterpretConfidence}: </span>
        {aiPriorityLabel(interp.confidence, priorityLabels)}
      </p>
      {response.disclaimer?.trim() ? (
        <p className="border-t border-surface-100 pt-2 text-xs text-surface-500">{response.disclaimer}</p>
      ) : null}
    </div>
  );
}

function DiagnosisInterpretSection({
  diagnosisId,
  availability,
  state,
  onRequest,
  onToggleExpand,
  labels,
  priorityLabels,
  onOpenLead,
  onDe4ActionChanged,
}: {
  diagnosisId: string;
  availability: InterpretAvailability;
  state: InterpretUiState;
  onRequest: (diagnosisId: string) => void;
  onToggleExpand: (diagnosisId: string) => void;
  labels: (typeof import('../../i18n/app').appCopy)['tr']['ai'];
  priorityLabels: Record<string, string>;
  onOpenLead?: (leadId: number) => void;
  onDe4ActionChanged?: () => void;
}) {
  const errorMessage =
    state.phase === 'error'
      ? state.kind === 'unavailable'
        ? labels.diagnosisInterpretUnavailable
        : state.kind === 'notFound'
          ? labels.diagnosisInterpretNotFound
          : state.kind === 'quota'
            ? labels.diagnosisInterpretQuota
            : state.kind === 'invalidOutput'
              ? labels.diagnosisInterpretInvalidOutput
              : labels.diagnosisInterpretGenericError
      : null;

  const showPanel =
    state.phase === 'loading' ||
    (state.phase === 'ready' && state.expanded) ||
    (state.phase === 'error' && state.expanded);

  const buttonDisabled = isInterpretButtonDisabled(state, availability);
  const interpretAvailable = availability === 'available';

  const buttonLabel =
    state.phase === 'loading'
      ? labels.diagnosisInterpretLoading
      : availability === 'loading'
        ? labels.diagnosisInterpretStatusLoading
        : labels.diagnosisInterpretButton;

  const buttonTitle =
    availability === 'unavailable' ? labels.diagnosisInterpretDisabledTitle : undefined;

  const panelId = `diagnosis-interpret-panel-${diagnosisId}`;

  const handlePrimaryClick = () => {
    const action = interpretPrimaryAction(state, interpretAvailable);
    if (action === 'noop') return;
    if (action === 'toggle') {
      onToggleExpand(diagnosisId);
      return;
    }
    if (action === 'retry' || action === 'fetch') {
      onRequest(diagnosisId);
    }
  };

  return (
    <div className="mt-3 border-t border-surface-100 pt-3">
      {availability === 'unavailable' ? (
        <p className="mb-2 text-xs text-surface-600/80">{labels.diagnosisInterpretUnavailable}</p>
      ) : null}
      <button
        type="button"
        onClick={handlePrimaryClick}
        disabled={buttonDisabled}
        title={buttonTitle}
        aria-expanded={showPanel}
        aria-controls={showPanel ? panelId : undefined}
        aria-busy={state.phase === 'loading'}
        aria-label={labels.diagnosisInterpretButton}
        className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 transition hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {state.phase === 'loading' || availability === 'loading' ? (
          <Loader2 size={14} className="animate-spin" aria-hidden />
        ) : (
          <Sparkles size={14} aria-hidden />
        )}
        {buttonLabel}
      </button>

      {showPanel ? (
        <div
          id={panelId}
          role="region"
          aria-live="polite"
          className="mt-2 rounded-lg border border-violet-100 bg-violet-50/40 p-3 sm:p-4"
        >
          {state.phase === 'loading' ? (
            <p className="flex items-center gap-2 text-sm text-surface-700">
              <Loader2 size={16} className="animate-spin text-violet-600" aria-hidden />
              {labels.diagnosisInterpretLoading}
            </p>
          ) : null}
          {state.phase === 'ready' && state.response && hasRenderableInterpretation(state.response) ? (
            <>
              <InterpretationBody
                response={state.response}
                labels={labels}
                priorityLabels={priorityLabels}
                onOpenLead={onOpenLead}
                onDe4ActionChanged={onDe4ActionChanged}
              />
              <button
                type="button"
                onClick={() => onToggleExpand(diagnosisId)}
                className="mt-3 text-xs font-medium text-violet-700 hover:text-violet-900"
              >
                {labels.diagnosisInterpretHide}
              </button>
            </>
          ) : null}
          {state.phase === 'ready' && state.response && !hasRenderableInterpretation(state.response) ? (
            <p className="text-sm text-amber-900/90">{labels.diagnosisInterpretInvalidOutput}</p>
          ) : null}
          {state.phase === 'error' && errorMessage ? (
            <p className="text-sm text-amber-900/90">{errorMessage}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function SalesDiagnosesCard({ onEditLead, onDe4ActionChanged }: Props) {
  const { app, locale } = useLocale();
  const t = app.ai;
  const cardCopy = app.salesDiagnoses;
  const priorityLabels = app.common;

  const [items, setItems] = useState<DiagnosisItem[]>([]);
  const [periodType, setPeriodType] = useState('monthly');
  const [anchor, setAnchor] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [interpretAvailability, setInterpretAvailability] = useState<InterpretAvailability>('loading');
  const [interpretById, setInterpretById] = useState<Record<string, InterpretUiState>>({});
  const inFlightRef = useRef<Set<string>>(new Set());
  const [detailDiagnosis, setDetailDiagnosis] = useState<DiagnosisItem | null>(null);
  const [caseSummaryById, setCaseSummaryById] = useState<Record<string, CaseSummary>>({});
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listDiagnoses('monthly');
      setItems(data.items ?? []);
      setPeriodType(data.period_type || 'monthly');
      setAnchor(data.anchor || '');
    } catch {
      setError(cardCopy.loadFailed);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [cardCopy.loadFailed]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSync = useCallback(async () => {
    if (syncing) return;
    setSyncing(true);
    setSyncMessage(null);
    setSyncError(null);
    try {
      await api.syncDiagnoses({ period: 'monthly' });
      setCaseSummaryById({});
      await load();
      setSyncMessage(cardCopy.syncSuccess);
    } catch {
      setSyncError(cardCopy.syncFailed);
    } finally {
      setSyncing(false);
    }
  }, [cardCopy.syncFailed, cardCopy.syncSuccess, load, syncing]);

  const handleCaseSummary = useCallback((diagnosisId: string, summary: CaseSummary) => {
    setCaseSummaryById((prev) => ({ ...prev, [diagnosisId]: summary }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .getAiStatus()
      .then((status) => {
        if (cancelled) return;
        setInterpretAvailability(status.diagnosis_interpret_available ? 'available' : 'unavailable');
      })
      .catch(() => {
        if (!cancelled) setInterpretAvailability('unavailable');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const requestInterpret = useCallback(
    async (diagnosisId: string) => {
      if (interpretAvailability !== 'available') {
        setInterpretById((prev) => ({
          ...prev,
          [diagnosisId]: { phase: 'error', kind: 'unavailable', expanded: true },
        }));
        return;
      }

      if (inFlightRef.current.has(diagnosisId)) {
        return;
      }

      let skipFetch = false;
      setInterpretById((prev) => {
        const cur = prev[diagnosisId];
        if (cur?.phase === 'loading') {
          skipFetch = true;
          return prev;
        }
        if (cur?.phase === 'ready') {
          skipFetch = true;
          return { ...prev, [diagnosisId]: { ...cur, expanded: true } };
        }
        return { ...prev, [diagnosisId]: { phase: 'loading' } };
      });

      if (skipFetch) {
        return;
      }

      inFlightRef.current.add(diagnosisId);

      try {
        const response = await api.interpretDiagnosis({
          diagnosis_id: diagnosisId,
          period: periodType,
          date: anchor || null,
          locale,
          refresh: false,
        });

        setInterpretById((prev) => ({
          ...prev,
          [diagnosisId]: interpretResponseToUiState(response),
        }));
      } catch (err) {
        const kind =
          err instanceof ApiHttpError
            ? mapHttpStatusToInterpretError(err.status)
            : 'generic';
        setInterpretById((prev) => ({
          ...prev,
          [diagnosisId]: { phase: 'error', kind, expanded: true },
        }));
      } finally {
        inFlightRef.current.delete(diagnosisId);
      }
    },
    [anchor, interpretAvailability, locale, periodType],
  );

  const toggleExpand = useCallback((diagnosisId: string) => {
    setInterpretById((prev) => {
      const cur = prev[diagnosisId];
      if (cur?.phase === 'ready') {
        return { ...prev, [diagnosisId]: { ...cur, expanded: !cur.expanded } };
      }
      if (cur?.phase === 'error') {
        return { ...prev, [diagnosisId]: { ...cur, expanded: !cur.expanded } };
      }
      return prev;
    });
  }, []);

  return (
    <section className="card overflow-hidden border-surface-200">
      <div className="flex flex-col gap-3 border-b border-surface-100 bg-surface-50/50 px-4 py-3.5 sm:flex-row sm:items-start sm:justify-between sm:px-5 sm:py-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
            <Stethoscope size={20} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-surface-900 sm:text-base">{cardCopy.title}</h3>
            <p className="mt-1 text-xs text-surface-800/60 sm:text-sm">{cardCopy.subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 self-stretch sm:self-start">
          {loading ? <Loader2 size={18} className="animate-spin text-surface-400" aria-hidden /> : null}
          <button
            type="button"
            disabled={syncing || loading}
            onClick={() => void handleSync()}
            className="btn-secondary inline-flex w-full items-center justify-center gap-2 py-2 text-sm sm:w-auto"
          >
            {syncing ? (
              <Loader2 size={16} className="animate-spin" aria-hidden />
            ) : (
              <RefreshCw size={16} aria-hidden />
            )}
            {syncing ? cardCopy.syncing : cardCopy.syncButton}
          </button>
        </div>
      </div>

      {error ? <p className="px-4 py-3 text-sm text-rose-600 sm:px-5">{error}</p> : null}
      {syncError ? <p className="px-4 py-2 text-sm text-rose-600 sm:px-5">{syncError}</p> : null}
      {syncMessage ? (
        <p className="px-4 py-2 text-sm text-emerald-700 sm:px-5">{syncMessage}</p>
      ) : null}

      {!error && !loading && items.length === 0 ? (
        <p className="flex items-center gap-2 px-4 py-4 text-sm text-surface-800/55 sm:px-5">
          <Activity size={16} aria-hidden />
          {cardCopy.empty}
        </p>
      ) : null}

      {items.length > 0 ? (
        <ul className="divide-y divide-surface-100">
          {items.map((d) => {
            const summary = caseSummaryById[d.diagnosis_id];
            return (
              <li key={d.diagnosis_id} className="px-4 py-3 sm:px-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase ${severityClass[d.severity] ?? severityClass.medium}`}
                  >
                    {d.severity}
                  </span>
                  <span className="text-xs text-surface-500">{d.type}</span>
                  {summary ? (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${lifecycleStateClass(summary.state)}`}
                    >
                      {lifecycleStateLabel(summary.state, cardCopy)}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm font-medium text-surface-900">{d.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-surface-800/65">{d.description}</p>

                {summary ? (
                  <p className="mt-1.5 text-xs text-surface-600">
                    {cardCopy.firstSeen}:{' '}
                    {summary.first_seen_at
                      ? formatAppDateTime(summary.first_seen_at, locale)
                      : cardCopy.placeholderDash}
                    {' · '}
                    {cardCopy.lastUpdated}:{' '}
                    {summary.last_seen_at
                      ? formatAppDateTime(summary.last_seen_at, locale)
                      : cardCopy.placeholderDash}
                  </p>
                ) : null}

                <button
                  type="button"
                  onClick={() => setDetailDiagnosis(d)}
                  className="mt-2 text-xs font-medium text-violet-700 hover:text-violet-900"
                >
                  {cardCopy.viewDetails}
                </button>

                {d.affected_leads_available === false ? (
                  <p className="mt-2 text-xs text-surface-600/70">{cardCopy.noLeadPriorityList}</p>
                ) : null}

                {d.impact && d.affected_leads_available !== false ? (
                  <p className="mt-2 text-xs text-surface-700">
                    {cardCopy.impactDistribution}{' '}
                    <span className="font-medium text-rose-700">
                      {d.impact.high_priority_count} {cardCopy.impactHigh}
                    </span>
                    {', '}
                    <span className="font-medium text-amber-800">
                      {d.impact.medium_priority_count} {cardCopy.impactMedium}
                    </span>
                    {', '}
                    <span>
                      {d.impact.low_priority_count} {cardCopy.impactLow}
                    </span>
                  </p>
                ) : null}

                {d.top_priority_leads && d.top_priority_leads.length > 0 ? (
                  <ul className="mt-2 space-y-1.5">
                    {d.top_priority_leads.map((row) => (
                      <PriorityLeadRow
                        key={row.lead_id}
                        row={row}
                        onEditLead={onEditLead}
                        copy={cardCopy}
                      />
                    ))}
                  </ul>
                ) : null}

                <DiagnosisInterpretSection
                  diagnosisId={d.diagnosis_id}
                  availability={interpretAvailability}
                  state={interpretById[d.diagnosis_id] ?? { phase: 'idle' }}
                  onRequest={requestInterpret}
                  onToggleExpand={toggleExpand}
                  labels={t}
                  priorityLabels={priorityLabels}
                  onOpenLead={onEditLead}
                  onDe4ActionChanged={onDe4ActionChanged}
                />
              </li>
            );
          })}
        </ul>
      ) : null}

      {detailDiagnosis ? (
        <DiagnosisDetailModal
          diagnosis={detailDiagnosis}
          open
          onClose={() => setDetailDiagnosis(null)}
          onCaseSummary={handleCaseSummary}
          onEditLead={onEditLead}
        />
      ) : null}
    </section>
  );
}
