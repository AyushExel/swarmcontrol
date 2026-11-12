import { useMemo, useState } from 'react';
import type { SwarmSnapshot } from '../shared/metrics';
import type { TrajectoryEvent } from '../shared/types';
import { authToken, useExperiment, type ExpSummary } from '../api';
import { ExperimentPicker, PageHeader, partnerOf, useApp } from '../App';
import { HealthArea } from '../components/charts';
import { ActivityFeed, AgentDetail, AgentGrid } from '../components/swarm';
import { Button, Empty, GovBadge, ModeBadge, Panel, Pill, Stat, fmtPct } from '../components/ui';

export function lawsFor(exp: ExpSummary | null, events: TrajectoryEvent[]) {
  if (!exp?.config.governor) return [];
  const start = events.find((e) => e.type === 'experiment_started');
  const laws = ((start?.data?.config as { laws?: { id: string; name: string; template: string; installed: boolean }[] })?.laws ?? []).filter((l) => l.installed && l.template !== 'contextual');
  return laws;
}

export function MetricTiles({ snap }: { snap: SwarmSnapshot }) {
  const m = snap.metrics;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 2xl:grid-cols-9">
      <Stat label="Total agents" value={m.total} sub={`${m.byState.queued} queued`} />
      <Stat label="Running" value={m.running} sub={`${m.byState.recovering} recovering`} />
      <Stat label="Healthy" value={m.byHealth.green} tone="good" sub={fmtPct(m.byHealth.green, m.total)} />
      <Stat label="Recovering" value={m.byHealth.yellow} tone="warn" sub="open violation, budget left" />
      <Stat label="Intervention" value={m.byHealth.red} tone="crit" sub={`${m.byState.awaiting_human} awaiting human`} />
      <Stat label="Law violations" value={m.violationsAttempted} sub={`${m.violationsBlocked} blocked · ${m.violationsExecuted} executed`} />
      <Stat label="Recoveries" value={m.recoveriesSucceeded} sub={m.recoveriesInitiated ? `of ${m.recoveriesInitiated} initiated` : 'none initiated'} />
      <Stat label="Collateral failures" value={m.collateralFailures} tone={m.collateralFailures ? 'crit' : undefined} sub={`of ${m.faultFreeAgents} agents with no fault`} />
      <Stat label="Task completion" value={fmtPct(m.taskSuccess, m.total)} sub={`${m.taskSuccess}/${m.total} pass all checks`} />
    </div>
  );
}

export function Drawer({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <div className="h-full w-full max-w-[640px] overflow-y-auto border-l border-line-strong bg-panel p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex justify-end">
          <Button kind="ghost" small onClick={onClose}>Close ✕</Button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Overview() {
  const { selected, experiments, status } = useApp();
  const live = useExperiment(selected?.id ?? null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const agents = useMemo(() => (live.snapshot ? [...live.snapshot.agents.values()] : []), [live.snapshot]);
  const agent = agentId ? live.snapshot?.agents.get(agentId) : null;
  const partner = partnerOf(selected, experiments);

  if (!experiments.length)
    return (
      <div>
        <PageHeader title="Overview" sub="Runtime governance and observability for agent swarms" />
        <div className="px-4 md:px-6">
          <Panel title="Three-minute walkthrough">
            <ol className="grid gap-3 text-[13px] md:grid-cols-5">
              {[
                ['1 · Define laws', 'Write a requirement in plain English or Bend; inspect the structured rule and its Bend proof status.', '#/laws'],
                ['2 · Uncontrolled swarm', '50 agents, governor off. Injected faults execute; an observe-only audit records what took effect.', '#/experiments'],
                ['3 · Governed swarm', 'Same seed, same faults. Prohibited actions are blocked before they run; agents get corrective feedback.', '#/experiments'],
                ['4 · Compare', 'Side-by-side metrics computed from the recorded event logs.', '#/experiments'],
                ['5 · Inspect a trajectory', 'Original action → violated law → runtime decision → feedback → next action → result.', '#/trajectories'],
              ].map(([t, d, h]) => (
                <a key={t} href={h} className="rounded-md border border-line bg-surface p-3 hover:border-line-strong">
                  <div className="font-medium text-ink">{t}</div>
                  <div className="mt-1 text-[12px] text-muted">{d}</div>
                </a>
              ))}
            </ol>
            <div className="mt-4">
              <a href="#/experiments"><Button kind="primary">Configure an experiment →</Button></a>
            </div>
          </Panel>
          <div className="mt-4"><ConnectPanel /></div>
          {status && <div className="mt-3 text-[12px] text-muted">Bend {status.bend.bendVersion ?? 'not found'} · core laws {status.bend.proofStatus === 'proof_checked' ? 'proof-checked' : status.bend.proofStatus}</div>}
        </div>
      </div>
    );

  return (
    <div className="pb-8">
      <PageHeader
        title="Overview"
        sub={
          selected && (
            <span className="inline-flex flex-wrap items-center gap-1.5">
              <ModeBadge mode={selected.mode} scenario={selected.config.scenario} /> <GovBadge governed={selected.config.governor} />
              <Pill>{selected.config.attachProject ? `attached: ${selected.config.attachProject}` : `${selected.config.swarmSize} agents · seed ${selected.seed}`}</Pill>
              <Pill tone={live.status === 'running' ? 'gov' : live.status === 'needs_attention' ? 'crit' : 'neutral'}>{live.status ?? selected.status}</Pill>
              {partner && (
                <a href="#/swarm" className="text-gov hover:underline">paired with {partner.config.governor ? 'governed' : 'baseline'} run →</a>
              )}
            </span>
          )
        }
        right={<ExperimentPicker />}
      />
      <div className="space-y-4 px-4 md:px-6">
        {selected?.config.scenario && selected.config.scenario !== 'synthetic' && (
          <div className="text-[11px] text-muted">{selected.config.attachProject ? <>Your own Claude Code sessions in <b className="text-ink-2">{selected.config.attachProject}</b>, governed through hooks. Every tool call was checked before it ran.</> : <>Real run: every agent is <b className="text-ink-2">{selected.config.model}</b> working with real tools. Tokens, cost and duration are measured. Injected instructions are labelled.</>}</div>
        )}
        {selected?.mode === 'simulation' && (
          <div className="text-[11px] text-muted">All figures on this page come from a <b className="text-ink-2">simulated</b> swarm with deliberately injected failures. They are derived from the recorded event log.</div>
        )}
        {live.snapshot ? <MetricTiles snap={live.snapshot} /> : <Empty>Loading event stream…</Empty>}
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-4">
            <Panel title="Swarm" right={<span className="text-[11px] text-muted">click an agent to inspect</span>}>
              {agents.length ? <AgentGrid agents={agents} selected={agentId} onSelect={setAgentId} cell={agents.length > 60 ? 22 : 30} /> : <Empty>No agents.</Empty>}
            </Panel>
            <Panel title="Swarm health over time">
              {live.snapshot && <HealthArea points={live.snapshot.timeline} total={live.snapshot.metrics.total} real={selected?.mode === 'llm'} />}
            </Panel>
          </div>
          <Panel title="Activity" pad={false}>
            <ActivityFeed events={live.events} onSelect={setAgentId} height={560} />
          </Panel>
        </div>
      </div>
      <div className="mt-4 px-4 md:px-6"><ConnectPanel /></div>
      {agent && selected && (
        <Drawer onClose={() => setAgentId(null)}>
          <AgentDetail agent={agent} events={live.events} experimentId={selected.id} humanActions={true} laws={lawsFor(selected, live.events)} />
          <div className="mt-4">
            <a href={`#/trajectories/${selected.id}/${agent.id}`} className="text-[12px] text-gov hover:underline">Open in Trajectories →</a>
          </div>
        </Drawer>
      )}
    </div>
  );
}

/** The one command a developer runs to connect their Claude Code to this governor. */
function ConnectPanel() {
  const origin = window.location.origin;
  const token = authToken();
  const cmd = `curl -fsSL ${origin}/connect.py | python3 - connect --server ${origin}${token ? ' --token <your token>' : ''}`;
  const [copied, setCopied] = useState(false);
  return (
    <Panel title="Connect your Claude Code" right={<span className="text-[11px] text-muted">run in the project folder · add --global for every project · --team to commit for the whole repo</span>}>
      <div className="flex flex-wrap items-center gap-2">
        <code className="mono min-w-0 flex-1 overflow-x-auto rounded border border-line bg-bg px-2 py-1.5 text-[12px] whitespace-nowrap text-ink-2">{cmd}</code>
        <Button small onClick={() => { navigator.clipboard?.writeText(cmd).then(() => setCopied(true), () => null); }}>{copied ? 'Copied' : 'Copy'}</Button>
      </div>
      <div className="mt-2 text-[11px] text-muted">Then use <span className="mono">claude</span> as usual. Sessions appear in Live Swarm as “attached: &lt;project&gt;”. Options: <span className="mono">--role</span>, <span className="mono">--agent</span>, <span className="mono">--done-check "npm test"</span>, <span className="mono">--observe</span>. Guide: tutorials/claude-code.md.</div>
    </Panel>
  );
}
