import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api, navigate, usePoll, useHashRoute, type ExpSummary, type Status } from './api';
import { Pill, cx } from './components/ui';
import { Overview } from './pages/Overview';
import { LiveSwarm } from './pages/LiveSwarm';
import { Laws } from './pages/Laws';
import { Experiments } from './pages/Experiments';
import { Results } from './pages/Results';
import { Trajectories } from './pages/Trajectories';

interface Ctx {
  status: Status | null;
  experiments: ExpSummary[];
  selected: ExpSummary | null;
  select: (id: string) => void;
  reloadExperiments: () => void;
}
const AppCtx = createContext<Ctx>(null!);
export const useApp = () => useContext(AppCtx);

export function partnerOf(e: ExpSummary | null, all: ExpSummary[]) {
  if (!e?.config.pairId) return null;
  return all.find((x) => x.id !== e.id && x.config.pairId === e.config.pairId) ?? null;
}

const NAV = [
  { id: 'overview', label: 'Overview', icon: 'M3 3h7v7H3zM14 3h7v4h-7zM14 11h7v10h-7zM3 14h7v7H3z' },
  { id: 'swarm', label: 'Live Swarm', icon: 'M5 5h3v3H5zM10.5 5h3v3h-3zM16 5h3v3h-3zM5 10.5h3v3H5zM10.5 10.5h3v3h-3zM16 10.5h3v3h-3zM5 16h3v3H5zM10.5 16h3v3h-3zM16 16h3v3h-3z' },
  { id: 'laws', label: 'Laws', icon: 'M12 3v18M5 7h14M7 7l-3 7h6zM17 7l-3 7h6zM8 21h8' },
  { id: 'experiments', label: 'Experiments', icon: 'M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3' },
  { id: 'trajectories', label: 'Trajectories', icon: 'M4 6h10M4 12h16M4 18h7M17 4l3 2-3 2M14 16l3 2-3 2' },
];

export function App() {
  const route = useHashRoute();
  const page = route[0] ?? 'overview';
  const status = usePoll(api.status, 15000);
  const exps = usePoll(api.experiments, 2000);
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    try {
      return localStorage.getItem('gov.selected');
    } catch {
      return null;
    }
  });
  const experiments = exps.data ?? [];
  const selected = experiments.find((e) => e.id === selectedId) ?? experiments[0] ?? null;
  const select = (id: string) => {
    setSelectedId(id);
    try {
      localStorage.setItem('gov.selected', id);
    } catch {
      /* storage unavailable */
    }
  };
  useEffect(() => {
    if (!route.length) navigate('/overview');
  }, [route.length]);

  const ctx = useMemo<Ctx>(() => ({ status: status.data, experiments, selected, select, reloadExperiments: exps.reload }), [status.data, experiments, selected]);
  const bend = status.data?.bend;

  return (
    <AppCtx.Provider value={ctx}>
      <div className="flex h-full">
        <aside className="hidden w-52 shrink-0 flex-col border-r border-line bg-panel md:flex">
          <div className="flex h-14 items-center gap-2 border-b border-line px-4">
            <svg viewBox="0 0 16 16" className="size-5" aria-hidden>
              <circle cx="4" cy="4" r="2" fill="#0ca30c" /><circle cx="12" cy="4" r="2" fill="#0ca30c" /><circle cx="4" cy="12" r="2" fill="#fab219" /><rect x="10" y="10" width="4" height="4" rx="1" fill="#d03b3b" />
            </svg>
            <div>
              <div className="text-[13px] leading-4 font-semibold">SwarmControl</div>
              <div className="text-[10px] text-muted">runtime control plane</div>
            </div>
          </div>
          <nav className="flex-1 space-y-0.5 p-2">
            {NAV.map((n) => (
              <a key={n.id} href={`#/${n.id}`} className={cx('flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px]', page === n.id || (page === 'results' && n.id === 'experiments') ? 'bg-raised text-ink' : 'text-ink-2 hover:bg-raised/60 hover:text-ink')}>
                <svg viewBox="0 0 24 24" className="size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d={n.icon} />
                </svg>
                {n.label}
              </a>
            ))}
          </nav>
          <div className="space-y-2 border-t border-line p-3 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="text-muted">Bend</span>
              <span className="mono text-ink-2">{bend?.bendVersion?.replace('bend ', '') ?? '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted">Core proofs</span>
              {bend ? (
                <Pill tone={bend.proofStatus === 'proof_checked' ? 'good' : 'crit'}>{bend.proofStatus === 'proof_checked' ? `✓ ${bend.laws.length} checked` : bend.proofStatus}</Pill>
              ) : (
                <span className="text-muted">…</span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted">Gates</span>
              <span className={status.data?.gatesLoaded ? 'text-good' : 'text-crit'}>{status.data ? (status.data.gatesLoaded ? 'loaded' : 'unavailable (fail closed)') : '…'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted">LLM</span>
              <span className="text-ink-2">{status.data?.llm.available ? status.data.llm.model : 'not configured'}</span>
            </div>
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <MobileNav page={page} />
          {status.error && <div className="border-b border-[#5a2626] bg-[#2a1515] px-4 py-2 text-[12px] text-[#f5b5b5]">Cannot reach the governor API ({status.error}). Is the server running? <span className="mono">swctl serve</span></div>}
          <main className="min-w-0 flex-1 overflow-y-auto">
            {page === 'overview' && <Overview />}
            {page === 'swarm' && <LiveSwarm />}
            {page === 'laws' && <Laws />}
            {page === 'experiments' && <Experiments />}
            {page === 'results' && <Results ids={route.slice(1)} />}
            {page === 'trajectories' && <Trajectories expId={route[1] ?? null} agentId={route[2] ?? null} />}
          </main>
        </div>
      </div>
    </AppCtx.Provider>
  );
}

function MobileNav({ page }: { page: string }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-line bg-panel px-2 py-2 md:hidden">
      {NAV.map((n) => (
        <a key={n.id} href={`#/${n.id}`} className={cx('rounded px-2.5 py-1 text-[12px] whitespace-nowrap', page === n.id ? 'bg-raised text-ink' : 'text-ink-2')}>
          {n.label}
        </a>
      ))}
    </div>
  );
}

export function PageHeader({ title, sub, right }: { title: string; sub?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 px-4 pt-5 pb-4 md:px-6">
      <div className="min-w-0">
        <h1 className="text-[18px] font-semibold">{title}</h1>
        {sub && <div className="mt-0.5 text-[12px] text-muted">{sub}</div>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

export function ExperimentPicker() {
  const { experiments, selected, select } = useApp();
  if (!experiments.length) return null;
  return (
    <select value={selected?.id ?? ''} onChange={(e) => select(e.target.value)} className="h-8 max-w-[360px] rounded-md border border-line-strong bg-surface px-2 text-[12px] text-ink">
      {experiments.map((e) => (
        <option key={e.id} value={e.id}>
          {expLabel(e)}
        </option>
      ))}
    </select>
  );
}

export function expLabel(e: ExpSummary) {
  const t = new Date(e.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  if (e.config.attachProject) return `${t} · attached: ${e.config.attachProject} · ${e.config.governor ? 'enforcing' : 'observe only'}${e.live ? ' · LIVE' : ''}`;
  const kind = e.config.scenario === 'web_research' ? 'web research' : e.config.scenario === 'bugfix' ? 'bug fix' : e.mode === 'simulation' ? 'sim' : 'LLM';
  return `${t} · ${kind} · ${e.config.swarmSize} agents · ${e.config.governor ? 'governed' : 'baseline'}${e.config.scenario && e.config.scenario !== 'synthetic' && !e.config.rulesInPrompt ? ' · rules not in prompt' : ''} · seed ${e.seed}${e.config.pairId ? ' · paired' : ''}${e.live ? ' · LIVE' : ''}`;
}
