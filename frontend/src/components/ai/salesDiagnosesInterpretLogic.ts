import type { DiagnosisInterpretResponse } from '../../types';

export type InterpretErrorKind =
  | 'unavailable'
  | 'notFound'
  | 'quota'
  | 'invalidOutput'
  | 'generic';

export type InterpretUiState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'ready'; response: DiagnosisInterpretResponse; expanded: boolean }
  | { phase: 'error'; kind: InterpretErrorKind; expanded: boolean };

export type InterpretAvailability = 'loading' | 'available' | 'unavailable';

/** Map HTTP status to UI error kind (never expose raw backend message). */
export function mapHttpStatusToInterpretError(status: number): InterpretErrorKind {
  if (status === 404) return 'notFound';
  if (status === 429) return 'quota';
  if (status === 503) return 'unavailable';
  return 'generic';
}

/** Decide primary button action without side effects. */
export function interpretPrimaryAction(
  state: InterpretUiState,
  interpretAvailable: boolean,
): 'noop' | 'toggle' | 'fetch' | 'retry' {
  if (state.phase === 'loading') return 'noop';
  if (state.phase === 'ready') return 'toggle';
  if (state.phase === 'error') {
    return state.expanded ? 'toggle' : 'retry';
  }
  if (!interpretAvailable) return 'noop';
  return 'fetch';
}

export function isInterpretButtonDisabled(
  state: InterpretUiState,
  availability: InterpretAvailability,
): boolean {
  if (state.phase === 'loading') return true;
  if (availability === 'loading') return true;
  if (availability === 'unavailable') return true;
  return false;
}

/** Convert API JSON to UI state (200 OK). */
export function interpretResponseToUiState(
  response: DiagnosisInterpretResponse,
): Extract<InterpretUiState, { phase: 'ready' }> | Extract<InterpretUiState, { phase: 'error' }> {
  if (response.error_code === 'invalid_llm_output' || !response.interpretation) {
    return { phase: 'error', kind: 'invalidOutput', expanded: true };
  }
  return { phase: 'ready', response, expanded: true };
}

export function hasRenderableInterpretation(response: DiagnosisInterpretResponse): boolean {
  return Boolean(response.interpretation?.summary && response.interpretation?.why_it_matters);
}
