import { useMemo, useState } from 'react';
import type { AgentState, Health } from '../shared/types';
import { useExperiment, type ExpSummary, type LiveExperiment } from '../api';
import { ExperimentPicker, PageHeader, partnerOf, useApp } from '../App';
import { HealthArea } from '../components/charts';
import { ActivityFeed, AgentDetail, AgentGrid } from '../components/swarm';
import { Empty, GovBadge, ModeBadge, Panel, Pill, Segmented, cx, fmtPct } from '../components/ui';
import { Drawer, lawsFor } from './Overview';

type Filter = 'all' | Health | 'awaiting_human' | 'violations';

function SwarmColumn({ exp, live, filter, onSelect, selected }: { exp: ExpSummary; live: LiveExperiment; filter: Filter; onSelect: (id: string) => void; selected: string | null }) {
  const agents = useMemo(() => {
    const all = live.snapshot ? [...live.snapshot.agents.values()] : [];
    if (filter === 'all') return all;
    if (filter === 'awaiting_human') return all.filter((a) => a.state === 'awaiting_human');
    if (filter === 'violations') return all.filter((a) => a.hadViolations);
    return all.filter((a) => a.health === filter && a.state !== 'queued');
  }, [live.snapshot, filter]);
  const m = live.snapshot?.metrics;
  return (
    <Panel
      title={
        <span className="inline-flex items-center gap-2">
          <GovBadge governed={exp.config.governor} /> <span>{exp.config.attachProject ? `attached: ${exp.config.attachProject} · ${live.snapshot?.agents.size ?? 0}` : exp.config.swarmSize} agents</span>
        </span>
      }
      right={<Pill tone={live.status === 'running' ? 'gov' : live.status === 'needs_attention' ? 'crit' : 'neutral'}>{live.status ?? exp.status}</Pill>}
    >
      {m && (
        <div className="mb-3 grid grid-cols-3 gap-2 text-[12px] sm:grid-cols-6">
          <Mini k="healthy" v={m.byHealth.green} c="text-good" />
          <Mini k="recovering" v={m.byHealth.yellow} c="text-warn" />
          <Mini k="intervention" v={m.byHealth.red} c="text-crit" />
          <Mini k="blocked" v={m.violationsBlocked} />
          <Mini k="took effect" v={m.violationsExecuted} c={m.violationsExecuted ? 'text-crit' : undefined} />
          <Mini k="task success" v={fmtPct(m.taskSuccess, m.total)} />
        </div>
      )}
      {agents.length ? <AgentGrid agents={agents} selected={selected} onSelect={onSelect} cell={26} /> : <Empty>No agents match this filter.</Empty>}
      {live.snapshot && (
        <div className="mt-4">
          <HealthArea points={live.snapshot.timeline} total={live.snapshot.metrics.total} height={120} real={exp.mode === 'llm'} />
        </div>
      )}
    </Panel>
  );
}

function Mini({ k, v, c }: { k: string; v: number | string; c?: string }) {
  return (
    <div className="rounded-md border border-line bg-surface px-2 py-1">
      <div className={cx('text-[15px] font-semibold tnum', c)}>{v}</div>
      <div className="text-[10px] text-muted">{k}</div>
    </div>
  );
}

export function LiveSwarm() {
  const { selected, experiments } = useApp();
  const partner = partnerOf(selected, experiments);
  const [baseline, governed] = selected && partner ? (selected.config.governor ? [partner, selected] : [selected, partner]) : [null, null];
  const a = useExperiment(baseline?.id ?? selected?.id ?? null);
  const b = useExperiment(governed?.id ?? null);
  const [filter, setFilter] = useState<Filter>('all');
  const [pick, setPick] = useState<{ exp: ExpSummary; live: LiveExperiment; agentId: string } | null>(null);

  if (!selected)
    return (
      <div>
        <PageHeader title="Live Swarm" />
        <div className="px-4 md:px-6"><Empty>No experiments yet. Start one from Experiments.</Empty></div>
      </div>
    );

  const pickedAgent = pick ? pick.live.snapshot?.agents.get(pick.agentId) : null;
  return (
    <div className="pb-8">
      <PageHeader
        title="Live Swarm"
        sub={
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <ModeBadge mode={selected.mode} scenario={selected.config.scenario} />
            {partner ? <span>Paired run: same tasks, seed {selected.seed} and fault schedule; only the governor differs.</span> : <GovBadge governed={selected.config.governor} />}
          </span>
        }
        right={<ExperimentPicker />}
      />
      <div className="space-y-4 px-4 md:px-6">
        <Segmented<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: 'All' },
            { value: 'green', label: 'Healthy' },
            { value: 'yellow', label: 'Recovering' },
            { value: 'red', label: 'Intervention' },
            { value: 'awaiting_human', label: 'Awaiting human' },
            { value: 'violations', label: 'Had violations' },
          ]}
        />
        {baseline && governed ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <SwarmColumn exp={baseline} live={a} filter={filter} selected={pick?.exp.id === baseline.id ? pick.agentId : null} onSelect={(id) => setPick({ exp: baseline, live: a, agentId: id })} />
            <SwarmColumn exp={governed} live={b} filter={filter} selected={pick?.exp.id === governed.id ? pick.agentId : null} onSelect={(id) => setPick({ exp: governed, live: b, agentId: id })} />
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
            <SwarmColumn exp={selected} live={a} filter={filter} selected={pick?.agentId ?? null} onSelect={(id) => setPick({ exp: selected, live: a, agentId: id })} />
            <Panel title="Activity" pad={false}>
              <ActivityFeed events={a.events} onSelect={(id) => setPick({ exp: selected, live: a, agentId: id })} height={620} />
            </Panel>
          </div>
        )}
        {baseline && governed && (
          <div className="flex justify-end">
            <a href={`#/results/${baseline.id}/${governed.id}`} className="text-[13px] text-gov hover:underline">Compare results →</a>
          </div>
        )}
      </div>
      {pick && pickedAgent && (
        <Drawer onClose={() => setPick(null)}>
          <div className="mb-3"><GovBadge governed={pick.exp.config.governor} /></div>
          <AgentDetail agent={pickedAgent} events={pick.live.events} experimentId={pick.exp.id} humanActions={true} laws={lawsFor(pick.exp, pick.live.events)} />
          <div className="mt-4">
            <a href={`#/trajectories/${pick.exp.id}/${pickedAgent.id}`} className="text-[12px] text-gov hover:underline">Open in Trajectories →</a>
          </div>
        </Drawer>
      )}
    </div>
  );
}

export type { AgentState };
