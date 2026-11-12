import { useEffect, useMemo, useState } from 'react';
import { replay, type SwarmSnapshot } from '../shared/metrics';
import type { SwarmReport, TrajectoryEvent } from '../shared/types';
import { api, type ExpSummary } from '../api';
import { PageHeader, useApp } from '../App';
import { CompareBars, HealthArea } from '../components/charts';
import { Empty, ExportLinks, GovBadge, ModeBadge, Panel, Pill, Segmented, cx, fmtNum, fmtVt } from '../components/ui';

interface Loaded {
  exp: ExpSummary;
  events: TrajectoryEvent[];
  snap: SwarmSnapshot;
}

async function load(id: string): Promise<Loaded> {
  const [exp, events] = await Promise.all([api.experiment(id), api.events(id)]);
  return { exp, events, snap: replay(events) };
}

function useRuns(ids: string[]) {
  const [runs, setRuns] = useState<Loaded[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const key = ids.join(',');
  useEffect(() => {
    let alive = true;
    const go = () =>
      Promise.all(ids.map(load))
        .then((r) => {
          if (!alive) return;
          setRuns(r);
          if (r.some((x) => x.exp.live)) setTimeout(go, 1500);
        })
        .catch((e) => alive && setErr(String(e.message)));
    go();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { runs, err };
}

export function Results({ ids }: { ids: string[] }) {
  if (ids[0] === 'group') return <GroupResults label={ids[1]} />;
  return <PairResults ids={ids.slice(0, 2)} />;
}

/** Derived per-run quantities, each with its denominator spelled out. */
function derive(r: Loaded) {
  const m = r.snap.metrics;
  const agents = [...r.snap.agents.values()];
  const withExecuted = agents.filter((a) => a.violations.some((v) => v.disposition === 'executed')).length;
  const report = r.events.find((e) => e.type === 'synthesis_completed')?.data?.report as SwarmReport | undefined;
  return { m, withExecuted, report, N: m.total };
}

function delta(b: number, g: number, fmt: (n: number) => string, unit = '') {
  if (Number.isNaN(b) || Number.isNaN(g)) return { abs: 'n/a', rel: 'n/a' };
  const d = g - b;
  if (unit === '%') unit = ' pp'; // differences of rates are percentage points
  const rel = b !== 0 ? (d / Math.abs(b)) * 100 : null;
  return { abs: `${d > 0 ? '+' : ''}${fmt(d)}${unit}`, rel: rel === null ? (d === 0 ? '0%' : 'n/a') : `${rel > 0 ? '+' : ''}${rel.toFixed(rel !== 0 && Math.abs(rel) < 10 ? 1 : 0)}%` };
}

const pctv = (n: number, d: number) => (d ? (n / d) * 100 : NaN);
const f1 = (n: number) => (Number.isNaN(n) ? '—' : (Math.round(n * 10) / 10).toString());

function PairResults({ ids }: { ids: string[] }) {
  const { runs, err } = useRuns(ids);
  const [tab, setTab] = useState<'metrics' | 'report'>('metrics');
  if (err) return <div className="p-6 text-crit">{err}</div>;
  if (!runs) return <div className="p-6"><Empty>Loading recorded events…</Empty></div>;
  const [B, G] = runs[0].exp.config.governor ? [runs[1], runs[0]] : [runs[0], runs[1]];
  if (!B || !G || B.exp.config.governor === G.exp.config.governor)
    return <div className="p-6"><Empty>Select one baseline run and one governed run to compare.</Empty></div>;
  const b = derive(B);
  const g = derive(G);
  const live = runs.some((r) => r.exp.live);
  const sim = B.exp.mode === 'simulation' || G.exp.mode === 'simulation';
  const diffs = comparability(B.exp, G.exp);

  type Row = { label: string; b: number; g: number; fmt: (n: number) => string; unit?: string; denom: string; better: 'higher' | 'lower' | 'neutral'; group: string };
  const rows: Row[] = [
    { group: 'Outcome', label: 'Task success rate', b: pctv(b.m.taskSuccess, b.N), g: pctv(g.m.taskSuccess, g.N), fmt: f1, unit: '%', denom: `agents passing all objective checks / ${b.N} agents`, better: 'higher' },
    { group: 'Outcome', label: '…without human help', b: pctv(b.m.autonomousSuccess, b.N), g: pctv(g.m.autonomousSuccess, g.N), fmt: f1, unit: '%', denom: 'succeeded with no escalation / all agents', better: 'higher' },
    { group: 'Outcome', label: 'Collateral failures', b: b.m.collateralFailures, g: g.m.collateralFailures, fmt: String, denom: `agents with no injected fault that still did not succeed (of ${b.m.faultFreeAgents} fault-free)`, better: 'lower' },
    { group: 'Outcome', label: 'False success claims', b: b.m.falseSuccessClaims, g: g.m.falseSuccessClaims, fmt: String, denom: 'agents that reported success while checks failed', better: 'lower' },
    { group: 'Outcome', label: 'Constraint violation rate', b: pctv(b.withExecuted, b.N), g: pctv(g.withExecuted, g.N), fmt: f1, unit: '%', denom: 'agents with ≥1 violation that took effect / all agents', better: 'lower' },
    { group: 'Prohibited actions', label: 'Prohibited actions attempted', b: b.m.prohibitedAttempted, g: g.m.prohibitedAttempted, fmt: String, denom: 'writes to protected resources, each attempt counted', better: 'neutral' },
    { group: 'Prohibited actions', label: 'Prohibited actions blocked', b: b.m.prohibitedBlocked, g: g.m.prohibitedBlocked, fmt: String, denom: 'prevented before execution', better: 'higher' },
    { group: 'Prohibited actions', label: 'Prohibited actions executed', b: b.m.prohibitedExecuted, g: g.m.prohibitedExecuted, fmt: String, denom: 'took effect', better: 'lower' },
    { group: 'Prohibited actions', label: 'Protected resources modified', b: b.m.protectedModified ?? 0, g: g.m.protectedModified ?? 0, fmt: String, denom: 'distinct files changed, from the sandbox integrity audit', better: 'lower' },
    { group: 'Violations', label: 'Violations attempted', b: b.m.violationsAttempted, g: g.m.violationsAttempted, fmt: String, denom: 'every violating action, including repeats', better: 'neutral' },
    { group: 'Violations', label: 'Detected at runtime', b: b.m.violationsDetectedAtRuntime, g: g.m.violationsDetectedAtRuntime, fmt: String, denom: 'seen by the governor while the agent ran', better: 'neutral' },
    { group: 'Violations', label: 'Found only by post-hoc audit', b: b.m.violationsFoundByAudit, g: g.m.violationsFoundByAudit, fmt: String, denom: 'observe-only audit, no enforcement', better: 'neutral' },
    { group: 'Violations', label: 'Blocked before execution', b: b.m.violationsBlocked, g: g.m.violationsBlocked, fmt: String, denom: 'violating actions prevented', better: 'higher' },
    { group: 'Violations', label: 'Took effect', b: b.m.violationsExecuted, g: g.m.violationsExecuted, fmt: String, denom: 'violating actions that executed', better: 'lower' },
    { group: 'Violations', label: 'Propagated from other agents', b: b.m.violationsPropagated, g: g.m.violationsPropagated, fmt: String, denom: 'violations by agents with no fault of their own', better: 'lower' },
    { group: 'Violations', label: 'Recovered automatically', b: b.m.violationsRecovered, g: g.m.violationsRecovered, fmt: String, denom: 'incidents resolved at the next checkpoint', better: 'higher' },
    { group: 'Recovery', label: 'Recovery success rate', b: pctv(b.m.recoveriesSucceeded, b.m.recoveriesInitiated), g: pctv(g.m.recoveriesSucceeded, g.m.recoveriesInitiated), fmt: f1, unit: '%', denom: `recovered / incidents with recovery initiated (${b.m.recoveriesInitiated} vs ${g.m.recoveriesInitiated})`, better: 'higher' },
    { group: 'Recovery', label: 'Agents requiring a human', b: b.m.humanRequired, g: g.m.humanRequired, fmt: String, denom: 'agents escalated to awaiting_human', better: 'lower' },
    { group: 'Cost', label: 'Total model tokens', b: b.m.tokens, g: g.m.tokens, fmt: fmtNum, denom: sim ? 'simulated token counts, including recovery prompts' : 'measured from API usage', better: 'lower' },
    { group: 'Cost', label: 'Tokens per successful task', b: b.m.taskSuccess ? b.m.tokens / b.m.taskSuccess : NaN, g: g.m.taskSuccess ? g.m.tokens / g.m.taskSuccess : NaN, fmt: (n) => (Number.isNaN(n) ? '—' : fmtNum(Math.round(n))), denom: 'all tokens spent / agents that succeeded: failed work still costs', better: 'lower' },
    { group: 'Cost', label: 'Estimated model cost', b: b.m.costUsd, g: g.m.costUsd, fmt: (n) => `$${n.toFixed(3)}`, denom: sim ? 'simulated tokens × assumed price' : 'API usage × list price', better: 'lower' },
    { group: 'Cost', label: 'Execution duration', b: b.m.makespanVt / 1000, g: g.m.makespanVt / 1000, fmt: f1, unit: 's', denom: sim ? 'simulated makespan, first start to synthesis' : 'measured', better: 'lower' },
    { group: 'Cost', label: 'Governor evaluation time', b: b.m.governorMicros / 1000, g: g.m.governorMicros / 1000, fmt: (n) => n.toFixed(2), unit: 'ms', denom: `measured wall time of all gate evaluations (${b.m.checkpointsEvaluated} vs ${g.m.checkpointsEvaluated} checkpoints)`, better: 'lower' },
  ];

  const verdict = [
    `Prohibited actions that executed: ${b.m.prohibitedExecuted} → ${g.m.prohibitedExecuted}. Protected resources modified: ${b.m.protectedModified ?? 0} → ${g.m.protectedModified ?? 0}.`,
    `Task success: ${b.m.taskSuccess}/${b.N} → ${g.m.taskSuccess}/${g.N} (${g.m.autonomousSuccess} without human help). Collateral failures (agents with no fault of their own): ${b.m.collateralFailures} → ${g.m.collateralFailures}.`,
    `Cost: ${fmtNum(b.m.tokens)} → ${fmtNum(g.m.tokens)} tokens (${delta(b.m.tokens, g.m.tokens, fmtNum).rel}); duration ${fmtVt(b.m.makespanVt)} → ${fmtVt(g.m.makespanVt)}.`,
    `Human intervention: ${b.m.humanRequired} → ${g.m.humanRequired} agents.${b.m.humanRequired === 0 && g.m.humanRequired > 0 ? ' The baseline had no escalation path, so its failures went unflagged.' : ''}`,
  ];

  return (
    <div className="pb-10">
      <PageHeader
        title="Results: baseline vs governed"
        sub={
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <ModeBadge mode={G.exp.mode} scenario={G.exp.config.scenario} />
            <Pill>{G.exp.config.swarmSize} agents · {G.exp.config.horizon === 'long' ? 'long-horizon pipeline' : 'short task'} · seed {G.exp.seed}</Pill>
            {live && <Pill tone="gov">runs in progress, updating</Pill>}
            {sim ? <span>Simulated findings. Every number is computed from the two recorded event logs.</span> : <span>Real model runs ({G.exp.config.model}{G.exp.config.rulesInPrompt === false ? ', rules NOT in prompt' : ', rules stated in the prompt in both conditions'}). Tokens and cost are measured from API usage.</span>}
          </span>
        }
        right={<><ExportLinks ids={[B.exp.id, G.exp.id]} /><Segmented value={tab} onChange={setTab} options={[{ value: 'metrics', label: 'Metrics' }, { value: 'report', label: 'Synthesized reports' }]} /></>}
      />
      <div className="space-y-4 px-4 md:px-6">
        <div className={cx('rounded-md border px-3 py-2 text-[12px]', diffs.length === 1 ? 'border-[#1f4d1f] bg-[#0f220f] text-[#a6e6a6]' : 'border-[#5a4410] bg-[#261d08] text-[#fbd98a]')}>
          {diffs.length === 1 ? 'Comparable: identical tasks, seed, failure schedule, recovery budget and model. Only difference: ' : 'Differences between these runs: '}
          {diffs.join('; ')}.
          {G.exp.mode === 'llm' && ' Model outputs vary between calls, and the runtime changes later execution, so a shared seed does not make LLM behavior identical.'}
        </div>

        {tab === 'metrics' ? (
          <>
            <Panel title="Does the runtime reduce executed prohibited actions and improve completion, without excessive cost, latency or human intervention?">
              <ul className="space-y-1 text-[13px] text-ink-2">
                {verdict.map((v) => <li key={v}>• {v}</li>)}
              </ul>
              <div className="mt-2 text-[11px] text-muted">One pair of runs is an illustration, not evidence. Use “Run repeated pairs” to see variation across seeds. No statistical significance is claimed.</div>
            </Panel>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
              <Panel title="Side by side" pad={false}>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-line text-left text-[11px] text-muted">
                        <th className="px-4 py-2 font-medium">Metric</th>
                        <th className="px-2 py-2 text-right font-medium"><span className="text-base">■</span> Baseline</th>
                        <th className="px-2 py-2 text-right font-medium"><span className="text-gov">■</span> Governed</th>
                        <th className="px-2 py-2 text-right font-medium">Δ abs</th>
                        <th className="px-2 py-2 text-right font-medium">Δ rel</th>
                        <th className="px-4 py-2 font-medium">Denominator / definition</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => {
                        const d = delta(r.b, r.g, r.fmt, r.unit);
                        const good = r.better === 'neutral' || r.g === r.b ? null : (r.better === 'higher') === r.g > r.b;
                        return (
                          <tr key={r.label} className={cx('border-b border-line/60', i > 0 && rows[i - 1].group !== r.group && 'border-t-2 border-t-line')}>
                            <td className="px-4 py-1.5 text-ink">
                              {(i === 0 || rows[i - 1].group !== r.group) && <div className="pt-1 text-[10px] tracking-wide text-muted uppercase">{r.group}</div>}
                              {r.label}
                            </td>
                            <td className="px-2 py-1.5 text-right tnum">{r.fmt(r.b)}{Number.isNaN(r.b) ? '' : r.unit}</td>
                            <td className="px-2 py-1.5 text-right tnum">{r.fmt(r.g)}{Number.isNaN(r.g) ? '' : r.unit}</td>
                            <td className={cx('px-2 py-1.5 text-right tnum', good === true && 'text-[#6fd66f]', good === false && 'text-[#f08a8a]')}>{d.abs}</td>
                            <td className="px-2 py-1.5 text-right tnum text-ink-2">{d.rel}</td>
                            <td className="px-4 py-1.5 text-[11px] text-muted">{r.denom}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="px-4 py-2 text-[11px] text-muted">pp = percentage points; — = no denominator (nothing to rate). Δ coloring: green = moved in the desirable direction, red = undesirable (e.g. more tokens). Neutral rows (attempts) are inputs and are not scored.</div>
              </Panel>
              <div className="space-y-4">
                <Panel title="Violation funnel">
                  <CompareBars
                    rows={[
                      { label: 'Attempted', baseline: b.m.violationsAttempted, governed: g.m.violationsAttempted, denom: 'violating actions' },
                      { label: 'Detected at runtime', baseline: b.m.violationsDetectedAtRuntime, governed: g.m.violationsDetectedAtRuntime },
                      { label: 'Blocked before execution', baseline: b.m.violationsBlocked, governed: g.m.violationsBlocked },
                      { label: 'Took effect', baseline: b.m.violationsExecuted, governed: g.m.violationsExecuted },
                      { label: 'Recovered', baseline: b.m.violationsRecovered, governed: g.m.violationsRecovered },
                    ]}
                  />
                </Panel>
                <Panel title="Outcome & cost">
                  <CompareBars
                    rows={[
                      { label: 'Task success (agents)', baseline: b.m.taskSuccess, governed: g.m.taskSuccess },
                      { label: 'Needed a human (agents)', baseline: b.m.humanRequired, governed: g.m.humanRequired },
                      { label: 'Tokens', baseline: b.m.tokens, governed: g.m.tokens, fmt: fmtNum },
                      { label: sim ? 'Duration (s, simulated)' : 'Duration (s, wall clock)', baseline: b.m.makespanVt / 1000, governed: g.m.makespanVt / 1000, fmt: f1 },
                    ]}
                  />
                </Panel>
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {[B, G].map((r) => (
                <Panel key={r.exp.id} title={<span className="inline-flex items-center gap-2">Health over time <GovBadge governed={r.exp.config.governor} /></span>}>
                  <HealthArea points={r.snap.timeline} total={r.snap.metrics.total} height={150} real={!sim} />
                </Panel>
              ))}
            </div>
            <LawBreakdown b={B} g={G} />
          </>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {[B, G].map((r) => (
              <ReportView key={r.exp.id} run={r} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function comparability(a: ExpSummary, b: ExpSummary): string[] {
  const out = ['governor off vs on'];
  if (a.config.swarmSize !== b.config.swarmSize) out.push(`swarm size ${a.config.swarmSize} vs ${b.config.swarmSize}`);
  if (a.seed !== b.seed) out.push(`seed ${a.seed} vs ${b.seed}`);
  if (a.config.horizon !== b.config.horizon) out.push(`horizon ${a.config.horizon} vs ${b.config.horizon}`);
  if (a.mode !== b.mode) out.push(`mode ${a.mode} vs ${b.mode}`);
  if (JSON.stringify(a.config.failure) !== JSON.stringify(b.config.failure)) out.push('failure-injection settings differ');
  if (a.config.maxRecoveryAttempts !== b.config.maxRecoveryAttempts) out.push('recovery budget differs');
  if (a.config.model !== b.config.model) out.push(`model ${a.config.model} vs ${b.config.model}`);
  if ((a.config.scenario ?? 'synthetic') !== (b.config.scenario ?? 'synthetic')) out.push('different scenarios');
  if (a.config.rulesInPrompt !== b.config.rulesInPrompt) out.push('rules-in-prompt setting differs');
  if (!a.config.pairId || a.config.pairId !== b.config.pairId) out.push('not launched as a pair');
  return out;
}

function LawBreakdown({ b, g }: { b: Loaded; g: Loaded }) {
  const ids = [...new Set([...Object.keys(b.snap.metrics.lawStats), ...Object.keys(g.snap.metrics.lawStats)])];
  const name = (id: string) =>
    [...b.events, ...g.events].find((e) => e.violation?.lawId === id)?.violation?.lawName.replace(' (audit)', '') ??
    [...b.events, ...g.events].flatMap((e) => e.evaluations ?? []).find((e) => e.lawId === id)?.lawName ?? id;
  return (
    <Panel title="Per law" pad={false}>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-line text-left text-[11px] text-muted">
            <th className="px-4 py-2 font-medium">Law</th>
            <th className="px-2 py-2 text-right font-medium">Evaluations (base / gov)</th>
            <th className="px-2 py-2 text-right font-medium">Violations (base / gov)</th>
            <th className="px-4 py-2 text-right font-medium">Recovered / recoveries (gov)</th>
          </tr>
        </thead>
        <tbody>
          {ids.map((id) => {
            const x = b.snap.metrics.lawStats[id];
            const y = g.snap.metrics.lawStats[id];
            return (
              <tr key={id} className="border-b border-line/60">
                <td className="px-4 py-1.5">{name(id)}</td>
                <td className="px-2 py-1.5 text-right tnum">{x?.evaluations ?? 0} / {y?.evaluations ?? 0}</td>
                <td className="px-2 py-1.5 text-right tnum">{x?.violations ?? 0} / {y?.violations ?? 0}</td>
                <td className="px-4 py-1.5 text-right tnum">{y?.recovered ?? 0} / {y?.recoveries ?? 0}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="px-4 py-2 text-[11px] text-muted">Baseline evaluations come from the observe-only audit, which uses the same Bend gates with default parameters and does not enforce anything.</div>
    </Panel>
  );
}

function ReportView({ run }: { run: Loaded }) {
  const report = run.events.find((e) => e.type === 'synthesis_completed')?.data?.report as SwarmReport | undefined;
  return (
    <Panel title={<span className="inline-flex items-center gap-2">Synthesized report <GovBadge governed={run.exp.config.governor} /></span>}>
      {!report ? (
        <Empty>Synthesis runs when all agents finish or wait for a human.</Empty>
      ) : (
        <div className="space-y-3 text-[12px]">
          <div className="text-ink-2">{report.question}</div>
          <div className="flex flex-wrap gap-1.5">
            {report.simulated && <Pill>SIMULATED CONTENT</Pill>}
            <Pill tone={report.unsupportedIncluded ? 'crit' : 'good'}>{report.unsupportedIncluded} unsupported findings included</Pill>
            <Pill>{report.excludedFindings} findings from unfinished agents excluded</Pill>
          </div>
          {report.sections.map((s) => (
            <div key={s.topicId}>
              <div className="font-medium text-ink">{s.topic}</div>
              <ul className="mt-1 space-y-1">
                {s.findings.slice(0, 4).map((f) => (
                  <li key={f.text} className={cx('rounded border px-2 py-1', f.supported ? 'border-line bg-surface text-ink-2' : 'border-[#5a2626] bg-[#1e1212] text-[#f5b5b5]')}>
                    {!f.supported && <b>[unsupported] </b>}
                    {f.text.length > 220 ? `${f.text.slice(0, 220)}…` : f.text}
                    <div className="mt-0.5 text-[10px] text-muted">{f.sources.map((x) => x.domain ?? 'no domain metadata').join(' · ')} · {f.agentId}</div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {report.opportunities.length > 0 && (
            <div>
              <div className="font-medium text-ink">Opportunities (topics with supported evidence)</div>
              <ul className="mt-1 list-disc pl-4 text-ink-2">{report.opportunities.map((o) => <li key={o}>{o}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function GroupResults({ label }: { label: string }) {
  const { experiments } = useApp();
  const ids = useMemo(() => experiments.filter((e) => e.config.label === label).map((e) => e.id), [experiments, label]);
  const { runs } = useRuns(ids);
  if (!runs) return <div className="p-6"><Empty>Loading…</Empty></div>;
  const pairs = new Map<string, { b?: Loaded; g?: Loaded }>();
  for (const r of runs) {
    const p = pairs.get(r.exp.config.pairId!) ?? {};
    if (r.exp.config.governor) p.g = r;
    else p.b = r;
    pairs.set(r.exp.config.pairId!, p);
  }
  const done = [...pairs.values()].filter((p) => p.b && p.g && !p.b.exp.live && !p.g.exp.live).sort((x, y) => x.b!.exp.seed - y.b!.exp.seed);
  const metric = (name: string, get: (l: Loaded) => number, fmt: (n: number) => string = (n) => n.toFixed(1)) => {
    const bs = done.map((p) => get(p.b!));
    const gs = done.map((p) => get(p.g!));
    const stat = (xs: number[]) => (xs.length ? { mean: xs.reduce((s, x) => s + x, 0) / xs.length, min: Math.min(...xs), max: Math.max(...xs) } : null);
    return { name, b: stat(bs), g: stat(gs), fmt };
  };
  const N = done[0]?.b!.snap.metrics.total ?? 0;
  const rows = [
    metric('Task success rate (%)', (l) => pctv(l.snap.metrics.taskSuccess, l.snap.metrics.total)),
    metric('Prohibited actions executed', (l) => l.snap.metrics.prohibitedExecuted),
    metric('Protected resources modified', (l) => l.snap.metrics.protectedModified ?? 0),
    metric('Violations that took effect', (l) => l.snap.metrics.violationsExecuted),
    metric('Agents requiring a human', (l) => l.snap.metrics.humanRequired),
    metric('False success claims', (l) => l.snap.metrics.falseSuccessClaims),
    metric('Collateral failures', (l) => l.snap.metrics.collateralFailures),
    metric('Tokens per successful task (k)', (l) => (l.snap.metrics.taskSuccess ? l.snap.metrics.tokens / l.snap.metrics.taskSuccess / 1000 : NaN)),
    metric('Tokens (k)', (l) => l.snap.metrics.tokens / 1000),
    metric('Duration (s, simulated)', (l) => l.snap.metrics.makespanVt / 1000),
  ];
  return (
    <div className="pb-10">
      <PageHeader title="Repeated pairs" sub={<span>{label} · {done.length} of {pairs.size} pairs complete · {N} agents each · simulated</span>} />
      <div className="space-y-4 px-4 md:px-6">
        <Panel title="Across seeds (mean, min–max)" pad={false}>
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-line text-left text-[11px] text-muted">
                <th className="px-4 py-2 font-medium">Metric</th>
                <th className="px-2 py-2 text-right font-medium"><span className="text-base">■</span> Baseline</th>
                <th className="px-4 py-2 text-right font-medium"><span className="text-gov">■</span> Governed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name} className="border-b border-line/60">
                  <td className="px-4 py-1.5">{r.name}</td>
                  <td className="px-2 py-1.5 text-right tnum">{r.b ? `${r.fmt(r.b.mean)} (${r.fmt(r.b.min)}–${r.fmt(r.b.max)})` : '—'}</td>
                  <td className="px-4 py-1.5 text-right tnum">{r.g ? `${r.fmt(r.g.mean)} (${r.fmt(r.g.min)}–${r.fmt(r.g.max)})` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 text-[11px] text-muted">n = {done.length} pairs. Ranges show seed-to-seed variation in the simulator. This is not a significance test.</div>
        </Panel>
        <Panel title="Pairs" pad={false}>
          <div className="divide-y divide-line">
            {done.map((p) => (
              <div key={p.b!.exp.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-[12px]">
                <span className="tnum">seed {p.b!.exp.seed}</span>
                <span className="text-ink-2 tnum">success {p.b!.snap.metrics.taskSuccess} → {p.g!.snap.metrics.taskSuccess} · executed violations {p.b!.snap.metrics.violationsExecuted} → {p.g!.snap.metrics.violationsExecuted} · human {p.b!.snap.metrics.humanRequired} → {p.g!.snap.metrics.humanRequired}</span>
                <a className="text-gov hover:underline" href={`#/results/${p.b!.exp.id}/${p.g!.exp.id}`}>details →</a>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
