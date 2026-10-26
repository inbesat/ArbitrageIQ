/**
 * The typed `fetch` wrapper for the ArbitrageIQ API.
 *
 * `plans/TECH_STACK.md` §3 chose this over a query library. Every call resolves to one
 * of four renderable states — loading, error, empty or ready — and never throws at the
 * caller, so a failure becomes an informative panel instead of a crash
 * (`plans/ACCEPTANCE_TESTS.md` AT-10.1, AT-10.15).
 *
 * Money is carried through exactly as the backend sent it. This module never calls
 * a numeric conversion on a money value and never does arithmetic on one
 * (`plans/TECH_STACK.md` §3.1, ADR-024, `AGENTS.md` rule 7).
 */
import { useCallback, useEffect, useState } from 'react';

import type { ApiErrorBody } from './types';

export const API_BASE = '/api/v1';

/** Which of the three failure families a request hit. */
export type ApiErrorKind = 'network' | 'client' | 'server';

export type ApiState<T> =
  | { status: 'loading' }
  | { status: 'error'; kind: ApiErrorKind; detail: string; field?: string }
  | { status: 'empty' }
  | { status: 'ready'; data: T };

function kindFor(status: number): ApiErrorKind {
  return status >= 500 ? 'server' : 'client';
}

/**
 * One request, normalised. `init` carries the method, body and headers for the
 * imperative calls (import, simulate); a read needs nothing.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<ApiState<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, init);

    if (!response.ok) {
      // The backend answers every failure with {error, detail, field?} (AT-8.10),
      // so the message shown is the backend's own plain-English detail.
      let body: ApiErrorBody | null = null;
      try {
        body = (await response.json()) as ApiErrorBody;
      } catch {
        body = null;
      }
      return {
        status: 'error',
        kind: kindFor(response.status),
        detail: body?.detail ?? `The server answered with status ${response.status}.`,
        field: body?.field,
      };
    }

    return { status: 'ready', data: (await response.json()) as T };
  } catch {
    // Refused connection, DNS failure or an aborted request. No stack trace ever
    // reaches the user; the wording stays plain and actionable.
    return {
      status: 'error',
      kind: 'network',
      detail: 'The API is not reachable. Start the backend, then try again.',
    };
  }
}

/**
 * Read once on mount and expose a `reload`.
 *
 * `isEmpty` lets a view decide what "no data yet" means for its own payload — an empty
 * catalogue for `/products`, no SKUs for `/profit/reconcile`. It must be a stable
 * reference (a module-level function), because a new one re-runs the request.
 */
export function useApi<T>(
  path: string,
  isEmpty: (data: T) => boolean,
): { state: ApiState<T>; reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setState({ status: 'loading' });

    void apiFetch<T>(path).then((next) => {
      if (!live) {
        return;
      }
      setState(next.status === 'ready' && isEmpty(next.data) ? { status: 'empty' } : next);
    });

    return () => {
      live = false;
    };
  }, [path, isEmpty, attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  return { state, reload };
}
