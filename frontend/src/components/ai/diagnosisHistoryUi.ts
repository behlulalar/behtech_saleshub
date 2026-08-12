/** Shared DE-5 diagnosis history UI helpers (frontend-only). */

import type {
  DiagnosisItem,
  DiagnosisLifecycleState,
  DiagnosisTrendChanges,
  DiagnosisTrendDirection,
  DiagnosisTrendSummary,
} from '../../types';

export type SalesDiagnosesCopy = (typeof import('../../i18n/app').appCopy)['tr']['salesDiagnoses'];

export function periodKeyForDiagnosis(diagnosis: Pick<DiagnosisItem, 'diagnosis_id' | 'type'>): string {
  const type = (diagnosis.type || '').trim();
  if (type === 'follow_up' || type === 'offer') return 'current';
  if (type === 'funnel_drop') return 'monthly';
  const id = diagnosis.diagnosis_id || '';
  if (id.startsWith('follow_up') || id.startsWith('offer_')) return 'current';
  if (id.startsWith('funnel_')) return 'monthly';
  return 'monthly';
}

export function lifecycleStateLabel(state: string, copy: SalesDiagnosesCopy): string {
  switch (state) {
    case 'new':
      return copy.stateNew;
    case 'active':
      return copy.stateActive;
    case 'improving':
      return copy.stateImproving;
    case 'worsening':
      return copy.stateWorsening;
    case 'resolved':
      return copy.stateResolved;
    default:
      return state;
  }
}

export function lifecycleStateClass(state: string): string {
  switch (state as DiagnosisLifecycleState) {
    case 'improving':
      return 'bg-emerald-50 text-emerald-800';
    case 'worsening':
      return 'bg-rose-50 text-rose-800';
    case 'resolved':
      return 'bg-surface-100 text-surface-700';
    case 'new':
      return 'bg-violet-50 text-violet-800';
    case 'active':
    default:
      return 'bg-amber-50 text-amber-900';
  }
}

export function trendDirectionLabel(direction: string, copy: SalesDiagnosesCopy): string {
  switch (direction as DiagnosisTrendDirection) {
    case 'newly_detected':
      return copy.trendDirectionNewlyDetected;
    case 'worsening':
      return copy.trendDirectionWorsening;
    case 'improving':
      return copy.trendDirectionImproving;
    case 'stable':
      return copy.trendDirectionStable;
    case 'resolved':
      return copy.trendDirectionResolved;
    case 'reopened':
      return copy.trendDirectionReopened;
    default:
      return direction;
  }
}

export function trendDirectionClass(direction: string): string {
  switch (direction as DiagnosisTrendDirection) {
    case 'worsening':
      return 'bg-rose-50 text-rose-800';
    case 'improving':
      return 'bg-emerald-50 text-emerald-800';
    case 'newly_detected':
      return 'bg-violet-50 text-violet-800';
    case 'reopened':
      return 'bg-amber-50 text-amber-900';
    case 'resolved':
      return 'bg-surface-100 text-surface-700';
    case 'stable':
    default:
      return 'bg-sky-50 text-sky-900';
  }
}

export function reasonCodeLabel(code: string, copy: SalesDiagnosesCopy): string {
  switch (code) {
    case 'severity_increased':
      return copy.reasonSeverityIncreased;
    case 'severity_decreased':
      return copy.reasonSeverityDecreased;
    case 'metric_worsened':
      return copy.reasonMetricWorsened;
    case 'metric_improved':
      return copy.reasonMetricImproved;
    case 'affected_lead_count_increased':
      return copy.reasonAffectedIncreased;
    case 'affected_lead_count_decreased':
      return copy.reasonAffectedDecreased;
    case 'high_priority_count_increased':
      return copy.reasonHighPriorityIncreased;
    case 'high_priority_count_decreased':
      return copy.reasonHighPriorityDecreased;
    case 'lead_set_increased':
      return copy.reasonLeadSetIncreased;
    case 'lead_set_decreased':
      return copy.reasonLeadSetDecreased;
    default:
      return code;
  }
}

export function metricLabel(metric: string, copy: SalesDiagnosesCopy): string {
  switch (metric) {
    case 'days_since_last_contact':
      return copy.metricDaysSinceLastContact;
    case 'pending_offer_age_days':
      return copy.metricPendingOfferAge;
    case 'demo_to_offer_conversion':
      return copy.metricDemoToOffer;
    case 'offer_to_won_conversion':
      return copy.metricOfferToWon;
    default:
      return metric
        ? metric
            .split('_')
            .filter(Boolean)
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(' ')
        : copy.placeholderDash;
  }
}

export function formatSignedNumber(value: number | null | undefined, digits = 1): string | null {
  if (value == null || Number.isNaN(value)) return null;
  const fixed = Number(value).toFixed(digits);
  const n = Number(fixed);
  if (n > 0) return `+${fixed}`;
  return fixed;
}

function fmtVal(value: number | null | undefined, copy: SalesDiagnosesCopy): string {
  if (value == null || Number.isNaN(value)) return copy.placeholderDash;
  return String(value);
}

/** Build human-readable change lines from API trend.changes (no client math). */
export function trendChangeLines(
  trend: DiagnosisTrendSummary,
  copy: SalesDiagnosesCopy,
): string[] {
  const ch: DiagnosisTrendChanges = trend.changes;
  const lines: string[] = [];
  if (ch.severity_delta !== 0 && (ch.severity_from || ch.severity_to)) {
    lines.push(
      copy.trendChangeSeverity
        .replace('{from}', ch.severity_from || copy.placeholderDash)
        .replace('{to}', ch.severity_to || copy.placeholderDash),
    );
  }
  if (
    ch.metric_direction !== 0
    || (ch.current_value_from != null && ch.current_value_to != null
      && ch.current_value_from !== ch.current_value_to)
  ) {
    const metricName = metricLabel(
      trend.current_snapshot?.metric || trend.previous_snapshot?.metric || '',
      copy,
    );
    lines.push(
      copy.trendChangeMetric
        .replace('{metric}', metricName)
        .replace('{from}', fmtVal(ch.current_value_from, copy))
        .replace('{to}', fmtVal(ch.current_value_to, copy)),
    );
  }
  if (ch.affected_lead_count_delta !== 0) {
    lines.push(
      copy.trendChangeAffected
        .replace('{from}', String(ch.affected_lead_count_from))
        .replace('{to}', String(ch.affected_lead_count_to)),
    );
  }
  if (ch.high_priority_count_delta !== 0) {
    lines.push(
      copy.trendChangeHighPriority
        .replace('{from}', String(ch.high_priority_count_from))
        .replace('{to}', String(ch.high_priority_count_to)),
    );
  }
  return lines;
}

export function activeDaysFromSeconds(
  seconds: number | null | undefined,
  copy: SalesDiagnosesCopy,
): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return copy.placeholderDash;
  const days = Math.max(0, Math.floor(seconds / (24 * 60 * 60)));
  return copy.durationDays.replace('{n}', String(days));
}

export type CaseSummary = {
  state: string;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  resolved_at?: string | null;
};
