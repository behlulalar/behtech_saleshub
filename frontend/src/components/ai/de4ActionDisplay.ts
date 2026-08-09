/** Shared DE-4 action labels (backend `ai_actions` is source of truth). */

export function formatActionType(actionType: string): string {
  return actionType.replace(/_/g, ' ');
}

export function actionTypeLabel(
  actionType: string,
  labels: Record<string, string | undefined>,
): string {
  switch (actionType) {
    case 'propose_log_activity':
      return labels.de4ActionTypeLogActivity ?? formatActionType(actionType);
    case 'propose_note_append':
      return labels.de4ActionTypeNoteAppend ?? formatActionType(actionType);
    case 'propose_follow_up_task':
      return labels.de4ActionTypeFollowUp ?? formatActionType(actionType);
    case 'propose_status_change':
      return labels.de4ActionTypeStatusChange ?? formatActionType(actionType);
    case 'propose_priority_change':
      return labels.de4ActionTypePriorityChange ?? formatActionType(actionType);
    default:
      return formatActionType(actionType);
  }
}

export function statusLabel(status: string, t: Record<string, string>): string {
  switch (status) {
    case 'proposed':
      return t.de4ActionsStatusProposed;
    case 'approved':
      return t.de4ActionsStatusApproved;
    case 'executing':
      return t.de4ActionsExecuting;
    case 'executed':
      return t.de4ActionsExecuted;
    case 'failed':
      return t.de4ActionsFailed;
    case 'cancelled':
      return t.de4ActionsCancelled;
    case 'expired':
      return t.de4ActionsExpired;
    default:
      return status;
  }
}

export function statusBadgeClass(status: string): string {
  switch (status) {
    case 'approved':
      return 'bg-emerald-100 text-emerald-900';
    case 'executing':
      return 'bg-amber-100 text-amber-900';
    case 'executed':
      return 'bg-surface-100 text-surface-800';
    case 'failed':
      return 'bg-rose-100 text-rose-900';
    case 'cancelled':
    case 'expired':
      return 'bg-surface-100 text-surface-600';
    default:
      return 'bg-violet-100 text-violet-900';
  }
}
