import { useEffect, useRef, useState } from 'react';
import { SwarmReducer, type SwarmSnapshot } from './shared/metrics';
import type { Experiment, ExperimentConfig, Law, LawScope, StructuredRule, TrajectoryEvent } from './shared/types';

/** Access token for a self-hosted governor (SWARMCONTROL_TOKEN); asked for once, kept in this browser. */
export function authToken(): string {
  try {
    return localStorage.getItem('gov.token') ?? '';
  } catch {
    return '';
  }
}
/** `?token=` / `&token=` for URLs the browser fetches itself (event streams, downloads). */
export const withToken = (url: string) => (authToken() ? `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(authToken())}` : url);
let asking: Promise<void> | null = null;

async function req<T>(method: string, url: string, body?: unknown, retried = false): Promise<T> {
  const headers: Record<string, string> = body ? { 'Content-Type': 'application/json' } : {};
  if (authToken()) headers.Authorization = `Bearer ${authToken()}`;
  const r = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 401 && !retried) {
    asking ??= Promise.resolve().then(() => {
      const t = window.prompt('This governor requires an access token (SWARMCONTROL_TOKEN):') ?? '';
      try {
        localStorage.setItem('gov.token', t.trim());
      } catch {
        /* storage unavailable */
      }
      asking = null;
    });
    await asking;
    return req<T>(method, url, body, true);
  }
  const j = await r.json();
  if (!r.ok) throw new Error(j.error ?? `HTTP ${r.status}`);
  return j as T;
}

export interface Status {
  bend: {
    bendVersion: string | null;
    binary: string | null;
    sourceHash: string;
    proofStatus: Law['proofStatus'];
    proofOutput: string;
    checkedAt: number;
    checkMs: number;
    moduleBuiltFromHash: string | null;
    laws: { name: string; statement: string }[];
  };
  gatesLoaded: boolean;
  gatesError: string | null;
  llm: { available: boolean; model: string };
  claudeCode?: { ok: boolean; version: string | null };
  openRouter?: boolean;
  defaults: { failure: ExperimentConfig['failure']; maxRecoveryAttempts: number; protectedPaths: string[] };
  assumptions: {
    complianceModel: { cooperative: { withFeedback: number; withoutFeedback: number }; persistent: { withFeedback: number; withoutFeedback: number } };
    baselineLoopCap: number;
    safetyRecoveryCap: number;
    simulatedPricePerMTok: number;
  };
  checks: Record<string, string>;
  catalog: string[];
}

export type ExpSummary = Experiment & { live: boolean };

export const api = {
  status: () => req<Status>('GET', '/api/status'),
  sources: () => req<{ governor: string; laws: string; proof: string }>('GET', '/api/bend/sources'),
  recheck: () => req<Status['bend']>('POST', '/api/bend/recheck'),
  laws: () => req<Law[]>('GET', '/api/laws'),
  translate: (text: string, useLlm: boolean) => req<{ rules: StructuredRule[]; drafts: Law[]; translator: string; error?: string }>('POST', '/api/laws/translate', { text, useLlm }),
  preview: (rule: StructuredRule) => req<Law>('POST', '/api/laws/preview', { rule }),
  activate: (rules: StructuredRule[], appliesTo?: LawScope | null) => req<Law[]>('POST', '/api/laws/activate', { rules, appliesTo }),
  checkBend: (source: string) => req<Law>('POST', '/api/laws/bend/check', { source }),
  createBend: (name: string, source: string, description: string, appliesTo?: LawScope | null) => req<Law>('POST', '/api/laws/bend', { name, source, description, appliesTo }),
  updateLaw: (id: string, patch: Record<string, unknown>) => req<Law>('PATCH', `/api/laws/${id}`, patch),
  validateLaw: (id: string) => req<Law>('POST', `/api/laws/${id}/validate`),
  deleteLaw: (id: string) => req<{ ok: true }>('DELETE', `/api/laws/${id}`),
  experiments: () => req<ExpSummary[]>('GET', '/api/experiments'),
  experiment: (id: string) => req<ExpSummary & { humanActionsAvailable: boolean }>('GET', `/api/experiments/${id}`),
  events: (id: string) => req<TrajectoryEvent[]>('GET', `/api/experiments/${id}/events`),
  start: (config: Partial<ExperimentConfig>) => req<Experiment>('POST', '/api/experiments', config),
  startPaired: (config: Partial<ExperimentConfig>, repetitions = 1) =>
    req<{ pairId?: string; baseline?: Experiment; governed?: Experiment; group?: string; repetitions?: number }>('POST', '/api/experiments/paired', { config, repetitions }),
  human: (id: string, agentId: string, action: 'retry_with_guidance' | 'cancel', note?: string) =>
    req<{ ok: true }>('POST', `/api/experiments/${id}/agents/${agentId}/human`, { action, note }),
};

export function usePoll<T>(fn: () => Promise<T>, ms: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    const run = () =>
      fn()
        .then((d) => alive && (setData(d), setError(null)))
        .catch((e) => alive && setError(String(e.message ?? e)));
    run();
    const t = ms > 0 ? setInterval(run, ms) : null;
    return () => {
      alive = false;
      if (t) clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, reload: () => setTick((x) => x + 1) };
}

export interface LiveExperiment {
  snapshot: SwarmSnapshot | null;
  events: TrajectoryEvent[];
  status: Experiment['status'] | null;
  version: number;
}

/**
 * Streams an experiment's events over SSE and folds them through the shared
 * reducer: the dashboard shows exactly what replaying the stored log shows.
 */
export function useExperiment(id: string | null): LiveExperiment {
  const [state, setState] = useState<LiveExperiment>({ snapshot: null, events: [], status: null, version: 0 });
  const ref = useRef<{ reducer: SwarmReducer; events: TrajectoryEvent[]; dirty: boolean; status: Experiment['status'] | null } | null>(null);

  useEffect(() => {
    if (!id) {
      setState({ snapshot: null, events: [], status: null, version: 0 });
      return;
    }
    const cur = { reducer: new SwarmReducer(), events: [] as TrajectoryEvent[], dirty: true, status: null as Experiment['status'] | null };
    ref.current = cur;
    const es = new EventSource(withToken(`/api/experiments/${id}/stream`));
    es.onmessage = (m) => {
      const evs = JSON.parse(m.data) as TrajectoryEvent[];
      for (const e of evs) {
        cur.reducer.apply(e);
        cur.events.push(e);
      }
      cur.dirty = true;
    };
    es.addEventListener('status', (m) => {
      const s = JSON.parse((m as MessageEvent).data).status;
      if (s !== cur.status) {
        cur.status = s;
        cur.dirty = true;
      }
    });
    let version = 0;
    const t = setInterval(() => {
      if (!cur.dirty) return;
      cur.dirty = false;
      setState({ snapshot: cur.reducer.snapshot(), events: cur.events.slice(), status: cur.status, version: ++version });
    }, 150);
    return () => {
      es.close();
      clearInterval(t);
    };
  }, [id]);
  return state;
}

export function navigate(hash: string) {
  window.location.hash = hash;
}

export function useHashRoute(): string[] {
  const get = () => window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const [r, setR] = useState(get);
  useEffect(() => {
    const on = () => setR(get());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return r;
}
