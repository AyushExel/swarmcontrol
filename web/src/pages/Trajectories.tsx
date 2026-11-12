import { useEffect, useMemo, useState } from 'react';
import { useExperiment } from '../api';
import { PageHeader, expLabel, useApp } from '../App';
import { AgentDetail } from '../components/swarm';
import { Empty, ExportLinks, GovBadge, HealthBadge, ModeBadge, Panel, Segmented, StateBadge, cx } from '../components/ui';
import { lawsFor } from './Overview';

type F = 'violations' | 'escalated' | 'all';

export function Trajectories({ expId, agentId }: { expId: string | null; agentId: string | null }) {
  const { experiments, selected } = useApp();
  const exp = experiments.find((e) => e.id === expId) ?? selected;
  const live = useExperiment(exp?.id ?? null);
  const [filter, setFilter] = useState<F>('violations');
  const [pick, setPick] = useState<string | null>(agentId);
  useEffect(() => setPick(agentId), [agentId]);

  const agents = useMemo(() => {
    const all = live.snapshot ? [...live.snapshot.agents.values()] : [];
    const f = filter === 'all' ? all : filter === 'escalated' ? all.filter((a) => a.humanRequired) : all.filter((a) => a.hadViolations);
    return f.sort((a, b) => b.violations.length - a.violations.length || a.index - b.index);
  }, [live.snapshot, filter]);
  const agent = pick ? live.snapshot?.agents.get(pick) : agents[0];

  if (!exp) return <div><PageHeader title="Trajectories" /><div className="px-6"><Empty>No experiments yet.</Empty></div></div>;
  return (
    <div className="pb-8">
      <PageHeader
        title="Trajectories"
        sub={<span className="inline-flex items-center gap-1.5"><ModeBadge mode={exp.mode} scenario={exp.config.scenario} /><GovBadge governed={exp.config.governor} /> Each action, the gate that judged it, the decision, the feedback and what the agent did next.</span>}
        right={
          <>
          <ExportLinks ids={[exp.id]} />
          <select value={exp.id} onChange={(e) => (window.location.hash = `/trajectories/${e.target.value}`)} className="h-8 max-w-[360px] rounded-md border border-line-strong bg-surface px-2 text-[12px]">
            {experiments.map((e) => <option key={e.id} value={e.id}>{expLabel(e)}</option>)}
          </select>
          </>
        }
      />
      <div className="grid gap-4 px-4 md:px-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Panel title="Agents" pad={false} right={<span className="text-[11px] text-muted">{agents.length}</span>}>
          <div className="border-b border-line p-2">
            <Segmented value={filter} onChange={setFilter} options={[{ value: 'violations', label: 'Had violations' }, { value: 'escalated', label: 'Escalated' }, { value: 'all', label: 'All' }]} />
          </div>
          <div className="max-h-[70vh] overflow-y-auto">
            {agents.length === 0 && <Empty>No agents match.</Empty>}
            {agents.map((a) => (
              <button key={a.id} onClick={() => (window.location.hash = `/trajectories/${exp.id}/${a.id}`)} className={cx('flex w-full items-center gap-2 border-b border-line/60 px-3 py-2 text-left hover:bg-raised/60', agent?.id === a.id && 'bg-raised')}>
                <HealthBadge health={a.health} compact />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="mono text-[12px]">{a.id}</span>
                    <StateBadge state={a.state} />
                  </div>
                  <div className="truncate text-[11px] text-muted">{a.violations.length ? [...new Set(a.violations.map((v) => v.lawName.replace(' (audit)', '')))].join(', ') : a.task?.topic}</div>
                </div>
                {a.violations.length > 0 && <span className="text-[11px] text-ink-2 tnum">{a.violations.length}</span>}
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Trajectory">
          {agent ? <AgentDetail agent={agent} events={live.events} experimentId={exp.id} humanActions={true} laws={lawsFor(exp, live.events)} /> : <Empty>Select an agent.</Empty>}
        </Panel>
      </div>
    </div>
  );
}
