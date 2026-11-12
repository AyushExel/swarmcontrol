import { useMemo, useState } from 'react';
import type { AgentView } from '../shared/metrics';
import type { EventType, Health, TrajectoryEvent } from '../shared/types';
import { api } from '../api';
import { Button, Empty, HEALTH_GLYPH, HEALTH_LABEL, HealthBadge, Pill, StateBadge, cx, fmtNum, fmtTime, fmtVt, inputCls } from './ui';

const HEALTH_BG: Record<Health, string> = { green: 'bg-good', yellow: 'bg-warn', red: 'bg-crit' };

/** One cell per agent. Health is color + glyph (never color alone); state shows on hover. */
export function AgentGrid({ agents, selected, onSelect, cell = 22 }: { agents: AgentView[]; selected?: string | null; onSelect: (id: string) => void; cell?: number }) {
  const [hover, setHover] = useState<{ a: AgentView; x: number; y: number } | null>(null);
  return (
    <div className="relative" onMouseLeave={() => setHover(null)}>
      <div className="grid gap-[3px]" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${cell}px, 1fr))` }}>
        {agents.map((a) => {
          const queued = a.state === 'queued';
          const done = a.state === 'completed' || a.state === 'cancelled' || a.state === 'failed';
          return (
            <button
              key={a.id}
              aria-label={`${a.id}: ${HEALTH_LABEL[a.health]}, ${a.state}`}
              onClick={() => onSelect(a.id)}
              onMouseEnter={(e) => {
                const r = (e.currentTarget.offsetParent as HTMLElement).getBoundingClientRect();
                const b = e.currentTarget.getBoundingClientRect();
                setHover({ a, x: b.left - r.left + b.width / 2, y: b.bottom - r.top + 6 });
              }}
              className={cx(
                'relative flex aspect-square items-center justify-center rounded-[4px] text-[10px] leading-none font-semibold transition-[outline] outline-offset-1',
                queued ? 'border border-dashed border-line-strong bg-transparent text-muted' : HEALTH_BG[a.health],
                !queued && (a.health === 'green' ? 'text-[#062606]' : 'text-[#1a1208]'),
                !queued && a.health === 'red' && 'text-white',
                done && !queued && 'opacity-75',
                selected === a.id && 'outline-2 outline-ink',
              )}
            >
              {queued ? '' : a.health === 'green' ? (a.hadViolations ? '↺' : done ? '✓' : '') : HEALTH_GLYPH[a.health] === '◐' ? '…' : '!'}
            </button>
          );
        })}
      </div>
      {hover && (
        <div className="pointer-events-none absolute z-20 w-64 -translate-x-1/2 rounded-md border border-line-strong bg-raised p-2.5 text-[12px] shadow-xl" style={{ left: Math.max(130, hover.x), top: hover.y }}>
          <div className="flex items-center justify-between gap-2">
            <span className="mono font-medium text-ink">{hover.a.id}</span>
            <HealthBadge health={hover.a.health} />
          </div>
          <div className="mt-1 text-ink-2">{hover.a.task?.topic} · {hover.a.task?.angle}</div>
          <div className="mt-1.5 flex items-center gap-1.5">
            <StateBadge state={hover.a.state} />
            <span className="truncate text-muted">{hover.a.step}</span>
          </div>
          {hover.a.violations.length > 0 && (
            <div className="mt-1.5 text-[11px] text-ink-2">
              {hover.a.violations.length} violation{hover.a.violations.length > 1 ? 's' : ''}: {[...new Set(hover.a.violations.map((v) => v.lawName))].join(', ')}
            </div>
          )}
          {hover.a.lastSummary && <div className="mono mt-1 truncate text-[11px] text-muted">{hover.a.lastSummary}</div>}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-2">
        <span><span className="text-good">■</span> healthy</span>
        <span><span className="text-good">↺</span> recovered (had violations)</span>
        <span><span className="text-warn">■ …</span> recovering</span>
        <span><span className="text-crit">■ !</span> intervention required</span>
        <span className="text-muted">⬚ queued · faded = finished</span>
      </div>
    </div>
  );
}

export const EVENT_META: Record<EventType, { label: string; tone: 'neutral' | 'good' | 'warn' | 'crit' | 'gov' }> = {
  experiment_started: { label: 'Experiment started', tone: 'neutral' },
  agent_queued: { label: 'Agent queued', tone: 'neutral' },
  agent_started: { label: 'Agent started', tone: 'neutral' },
  action_executed: { label: 'Action executed', tone: 'neutral' },
  tool_error: { label: 'Tool error', tone: 'warn' },
  checkpoint_passed: { label: 'Checkpoint passed', tone: 'good' },
  law_violated: { label: 'Law violated', tone: 'crit' },
  action_blocked: { label: 'Action blocked', tone: 'gov' },
  violation_executed: { label: 'Violation took effect', tone: 'crit' },
  recovery_initiated: { label: 'Recovery initiated', tone: 'warn' },
  recovery_succeeded: { label: 'Recovery succeeded', tone: 'good' },
  recovery_failed: { label: 'Recovery failed', tone: 'crit' },
  human_required: { label: 'Human intervention required', tone: 'crit' },
  human_action: { label: 'Human action', tone: 'gov' },
  task_completed: { label: 'Task completed', tone: 'good' },
  task_failed: { label: 'Task failed', tone: 'crit' },
  agent_cancelled: { label: 'Agent cancelled', tone: 'neutral' },
  model_turn: { label: 'Model turn', tone: 'neutral' },
  synthesis_completed: { label: 'Report synthesized', tone: 'gov' },
  quality_snapshot: { label: 'Release suite graded', tone: 'neutral' },
  case_completed: { label: 'Case graded', tone: 'neutral' },
  experiment_completed: { label: 'Experiment completed', tone: 'neutral' },
};

const FEED_TYPES: EventType[] = [
  'agent_started', 'checkpoint_passed', 'law_violated', 'action_blocked', 'violation_executed', 'recovery_initiated', 'recovery_succeeded',
  'recovery_failed', 'human_required', 'human_action', 'task_completed', 'task_failed', 'tool_error', 'synthesis_completed', 'experiment_completed',
];

function eventDetail(e: TrajectoryEvent): string {
  if (e.violation) return `${e.violation.lawName}: ${e.violation.explanation}`;
  if (e.type === 'recovery_initiated') return e.recovery?.feedback ?? `attempt ${e.recovery?.attempt}`;
  if (e.type === 'recovery_succeeded') return `recovered after ${e.recovery?.attempt} attempt${e.recovery?.attempt === 1 ? '' : 's'}`;
  if (e.type === 'recovery_failed') return e.recovery?.reason ?? '';
  if (e.type === 'human_required') return String(e.data?.reason ?? '');
  if (e.type === 'task_completed' || e.type === 'task_failed') {
    const o = e.data?.outcome as { taskSuccess: boolean; checks: Record<string, boolean> } | undefined;
    if (!o) return '';
    const failed = Object.entries(o.checks).filter(([, v]) => !v).map(([k]) => k);
    return o.taskSuccess ? 'all checks pass' : `checks failing: ${failed.join(', ') || 'incomplete'}`;
  }
  if (e.type === 'tool_error') return String(e.data?.error ?? '');
  if (e.data?.sharedStateCorrupted) return String(e.data.sharedStateCorrupted);
  if (e.type === 'experiment_completed') return `${e.data?.protectedModified ?? 0} protected resources modified · ${e.data?.awaitingHuman ?? 0} awaiting human`;
  if (e.type === 'action_blocked') return String(e.data?.prevented ?? '');
  if (e.type === 'human_action') return `${e.data?.action}${e.data?.note ? `: ${e.data.note}` : ''}`;
  return e.action?.summary ?? '';
}

export function ActivityFeed({ events, onSelect, max = 120, height = 420 }: { events: TrajectoryEvent[]; onSelect?: (agentId: string) => void; max?: number; height?: number }) {
  const [filter, setFilter] = useState<'all' | 'issues'>('all');
  const rows = useMemo(() => {
    const out: TrajectoryEvent[] = [];
    for (let i = events.length - 1; i >= 0 && out.length < max; i--) {
      const e = events[i];
      const corruption = e.type === 'action_executed' && Boolean(e.data?.sharedStateCorrupted);
      if (!FEED_TYPES.includes(e.type) && !corruption) continue;
      if (filter === 'issues' && !['law_violated', 'action_blocked', 'violation_executed', 'recovery_failed', 'human_required', 'task_failed'].includes(e.type)) continue;
      out.push(e);
    }
    return out;
  }, [events, filter, max]);
  return (
    <div>
      <div className="flex gap-1 border-b border-line px-3 py-2">
        {(['all', 'issues'] as const).map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={cx('rounded px-2 py-0.5 text-[11px]', filter === f ? 'bg-raised text-ink' : 'text-muted hover:text-ink')}>
            {f === 'all' ? 'All events' : 'Violations & escalations'}
          </button>
        ))}
      </div>
      <div className="overflow-y-auto" style={{ height }}>
        {rows.length === 0 && <Empty>No events yet.</Empty>}
        {rows.map((e) => {
          const m = EVENT_META[e.type];
          return (
            <button key={e.id} onClick={() => e.agentId && onSelect?.(e.agentId)} className="block w-full border-b border-line/60 px-3 py-1.5 text-left hover:bg-raised/60">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="tnum text-muted">{fmtTime(e.ts)}</span>
                <Pill tone={m.tone}>{m.label}</Pill>
                {e.agentId && <span className="mono text-ink-2">{e.agentId}</span>}
                {e.violation && <Pill tone={e.violation.origin === 'injected' ? 'neutral' : 'warn'}>{e.violation.propagated ? 'propagated' : e.violation.origin}</Pill>}
                {e.type === 'action_executed' && Boolean(e.data?.sharedStateCorrupted) && <Pill tone="crit">Shared state corrupted</Pill>}
              </div>
              <div className="mt-0.5 truncate text-[12px] text-ink-2">{eventDetail(e)}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Why is this agent yellow or red? One sentence, from the log. */
export function healthReason(a: AgentView, events: TrajectoryEvent[]): string | null {
  const mine = events.filter((e) => e.agentId === a.id);
  if (a.health === 'red') {
    const h = [...mine].reverse().find((e) => e.type === 'human_required');
    if (a.state === 'awaiting_human' && h) return `Escalated: ${h.data?.reason}. The violating action did not execute; a human decision is required.`;
    const ex = mine.find((e) => e.type === 'violation_executed');
    if (ex) return `A violating action took effect with no runtime to stop it (${ex.violation!.lawName}: ${ex.violation!.explanation}).`;
    if (a.state === 'failed') return `Agent failed: ${a.step}.`;
    if (a.state === 'cancelled') return 'Cancelled by a human after escalation.';
  }
  if (a.health === 'yellow' && a.openViolation) return `Recovering from a blocked action (${a.openViolation.lawName}: ${a.openViolation.explanation}). The action did not take effect.`;
  if (a.health === 'green' && a.hadViolations) return `Recovered: ${a.recovered} violation${a.recovered === 1 ? '' : 's'} resolved automatically by the runtime.`;
  return null;
}

export function AgentDetail({ agent, events, experimentId, humanActions, laws }: { agent: AgentView; events: TrajectoryEvent[]; experimentId: string; humanActions: boolean; laws: { id: string; name: string; template: string }[] }) {
  // tool results are already shown on the action events; keep only the model's own turns
  const mine = useMemo(() => events.filter((e) => e.agentId === agent.id && e.type !== 'agent_queued' && !(e.type === 'model_turn' && e.data?.role === 'user')), [events, agent.id]);
  const reason = healthReason(agent, events);
  const queuedEv = events.find((e) => e.agentId === agent.id && e.type === 'agent_queued');
  const injection = queuedEv?.data?.injection as string | null | undefined;
  const faults = (queuedEv?.data?.faults as string[] | undefined) ?? (queuedEv?.data?.fault ? [String(queuedEv.data.fault)] : []);
  const attached = events.some((e) => e.agentId === agent.id && e.type === 'agent_started' && e.data?.backend === 'attached');
  // an attached session that was approved stays idle until someone prompts it: hooks only run when the agent acts
  const lastHuman = mine.map((e) => e.type === 'human_action' && e.data?.action === 'retry_with_guidance').lastIndexOf(true);
  const quietSinceApproval = attached && lastHuman >= 0 && mine.slice(lastHuman + 1).every((e) => e.type === 'recovery_initiated');
  const resuming = quietSinceApproval && Boolean(mine[lastHuman].data?.resumes);
  const awaitingPrompt = quietSinceApproval && !resuming;
  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="mono text-[15px] font-semibold">{agent.id}</span>
          <HealthBadge health={agent.health} />
          <StateBadge state={agent.state} />
          {agent.hadViolations && agent.health === 'green' && <Pill tone="warn">had violations</Pill>}
        </div>
        <div className="mt-1 text-[13px] text-ink-2">{agent.task?.question}</div>
        {injection && (
          <div className="mt-2 rounded-md border border-[#5c3020] bg-[#2a170e] px-2.5 py-1.5 text-[12px] text-[#f0b89e]">
            <span className="text-[10px] font-semibold tracking-wide uppercase">Injected instruction in the task brief</span>
            <div>{injection}</div>
          </div>
        )}
        {!attached && <div className="mt-1 text-[11px] text-muted">
          Injected faults: <span className="mono text-ink-2">{faults.length ? faults.join(', ') : 'none'}</span>
          {Boolean(queuedEv?.data?.steps) && <> · {String(queuedEv?.data?.steps)} planned actions</>}
          {faults.length === 0 && agent.violations.length > 0 && <span className="text-warn"> · every violation here was caused upstream by another agent</span>}
          {Boolean(queuedEv?.data?.persistent) && ' (persistent: tends to repeat after feedback)'}
        </div>}
      </div>
      {reason && (
        <div className={cx('rounded-md border px-3 py-2 text-[12px]', agent.health === 'red' ? 'border-[#5a2626] bg-[#2a1515] text-[#f5b5b5]' : agent.health === 'yellow' ? 'border-[#5a4410] bg-[#261d08] text-[#fbd98a]' : 'border-[#1f4d1f] bg-[#0f220f] text-[#a6e6a6]')}>
          {reason}
        </div>
      )}
      {resuming && <div className="rounded-md border border-[#1f3f66] bg-[#0f1c2c] px-3 py-2 text-[12px] font-semibold text-[#8ab9f1]">Approved. The session is resuming with your note.</div>}
      {awaitingPrompt && (
        <div className="rounded-md border border-[#1f3f66] bg-[#0f1c2c] px-3 py-2 text-[12px] text-[#8ab9f1]">
          <div className="font-semibold">Approved. Now tell the agent to continue in its terminal.</div>
          <div className="mt-1 text-ink-2">A stopped session doesn't resume by itself. Type something like “A human reviewed this. Please continue.” Your note is delivered with its next tool call, so repeat anything important there.</div>
        </div>
      )}
      {agent.state === 'awaiting_human' && <HumanPanel agent={agent} events={mine} experimentId={experimentId} available={humanActions} attached={attached} />}
      <div className="grid grid-cols-2 gap-2 text-[12px] sm:grid-cols-4">
        <Kv k="Current step" v={awaitingPrompt ? 'waiting for you in the terminal' : resuming ? 'resuming with your note' : agent.step} />
        <Kv k="Violations" v={String(agent.violations.length)} />
        <Kv k="Recovery attempts" v={String(agent.recoveryAttempts)} />
        <Kv k="Tokens" v={fmtNum(agent.tokens)} />
      </div>
      {agent.outcome && (
        <div>
          <div className="mb-1 text-[11px] font-medium text-ink-2 uppercase">Final outcome (objective checks)</div>
          <div className="flex flex-wrap gap-1.5">
            <Pill tone={agent.outcome.taskSuccess ? 'good' : 'crit'}>{agent.outcome.taskSuccess ? 'Task succeeded' : 'Task not successful'}</Pill>
            {agent.outcome.claimedSuccess && !agent.outcome.taskSuccess && <Pill tone="crit">false success claim</Pill>}
            {Object.entries(agent.outcome.checks).map(([k, v]) => (
              <Pill key={k} tone={v ? 'neutral' : 'crit'}>{v ? '✓' : '✕'} {k}</Pill>
            ))}
          </div>
        </div>
      )}
      <div>
        <div className="mb-1 text-[11px] font-medium text-ink-2 uppercase">Applicable laws</div>
        <div className="flex flex-wrap gap-1.5">{laws.length ? laws.map((l) => <Pill key={l.id}>{l.name}</Pill>) : <span className="text-[12px] text-muted">none — governor off (observe-only audit)</span>}</div>
      </div>
      <Timeline events={mine} />
    </div>
  );
}

function Kv({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5">
      <div className="text-[10px] text-muted">{k}</div>
      <div className="truncate text-ink">{v}</div>
    </div>
  );
}

function HumanPanel({ agent, events, experimentId, available, attached }: { agent: AgentView; events: TrajectoryEvent[]; experimentId: string; available: boolean; attached: boolean }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const h = [...events].reverse().find((e) => e.type === 'human_required');
  const attempts = events.filter((e) => e.type === 'recovery_initiated');
  const act = async (action: 'retry_with_guidance' | 'cancel') => {
    setBusy(true);
    setErr(null);
    try {
      await api.human(experimentId, agent.id, action, note || undefined);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rounded-md border border-[#5a2626] bg-[#1e1212] p-3">
      <div className="text-[12px] font-semibold text-[#f5b5b5]">Human intervention required</div>
      <dl className="mt-2 grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-[12px]">
        <dt className="text-muted">What went wrong</dt>
        <dd className="text-ink-2">{String(h?.data?.reason ?? '')}</dd>
        <dt className="text-muted">Law</dt>
        <dd className="text-ink-2">{agent.violations.at(-1)?.lawName ?? '—'}</dd>
        <dt className="text-muted">Recovery attempts</dt>
        <dd className="text-ink-2">{attempts.length ? attempts.map((a) => `#${a.recovery?.attempt}`).join(', ') : 'none (escalated immediately)'}</dd>
        <dt className="text-muted">Why it stopped</dt>
        <dd className="text-ink-2">
          {String(h?.data?.reason ?? '').includes('evaluated')
            ? 'The runtime could not evaluate a required law, so it refused to proceed (fail closed).'
            : 'The agent kept repeating the violation after corrective feedback until the retry budget ran out.'}
        </dd>
        <dt className="text-muted">Last feedback</dt>
        <dd className="text-ink-2">{String(h?.data?.lastFeedback ?? '—')}</dd>
      </dl>
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Guidance for the agent (optional)" className={cx(inputCls, 'mt-3')} />
      <div className="mt-2 flex items-center gap-2">
        <Button kind="primary" small disabled={busy || !available} onClick={() => act('retry_with_guidance')}>Approve retry with guidance</Button>
        <Button kind="danger" small disabled={busy || !available} onClick={() => act('cancel')}>Cancel agent</Button>
        <span className="text-[11px] text-muted">{available ? `Retried actions are still gated by every law.${attached ? ' A session waiting here resumes by itself; if it has already stopped, tell it to continue in its terminal.' : ''}` : 'Unavailable: this run was recorded before a server restart.'}</span>
      </div>
      {err && <div className="mt-2 text-[12px] text-crit">{err}</div>}
    </div>
  );
}

/** Full trajectory: each action, the gate evaluations, decisions and feedback. */
export function Timeline({ events }: { events: TrajectoryEvent[] }) {
  const [open, setOpen] = useState<Set<number>>(() => new Set(events.filter((e) => e.violation || e.type === 'recovery_initiated').map((e) => e.id)));
  if (!events.length) return <Empty>No events for this agent yet.</Empty>;
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium text-ink-2 uppercase">Trajectory ({events.length} events)</div>
      <ol className="relative border-l border-line pl-4">
        {events.map((e) => {
          const m = EVENT_META[e.type];
          const isOpen = open.has(e.id);
          const hasMore = Boolean(e.evaluations?.length || e.recovery?.feedback || e.violation || e.type === 'model_turn');
          const dot = m.tone === 'crit' ? 'bg-crit' : m.tone === 'warn' ? 'bg-warn' : m.tone === 'good' ? 'bg-good' : m.tone === 'gov' ? 'bg-gov' : 'bg-line-strong';
          return (
            <li key={e.id} className="relative pb-2.5">
              <span className={cx('absolute top-1.5 -left-[21px] size-2.5 rounded-full ring-2 ring-panel', dot)} />
              <button
                className="w-full text-left"
                onClick={() => hasMore && setOpen((s) => { const n = new Set(s); n.has(e.id) ? n.delete(e.id) : n.add(e.id); return n; })}
              >
                <div className="flex flex-wrap items-center gap-2 text-[12px]">
                  <span className="w-12 tnum text-[11px] text-muted">{fmtVt(e.vt)}</span>
                  <span className={cx('font-medium', m.tone === 'crit' ? 'text-[#f08a8a]' : m.tone === 'good' ? 'text-[#6fd66f]' : m.tone === 'warn' ? 'text-[#fbcb5c]' : m.tone === 'gov' ? 'text-[#8ab9f1]' : 'text-ink')}>{m.label}</span>
                  {e.checkpoint && <span className="mono text-[10px] text-muted">{e.checkpoint}</span>}
                  {e.action && <span className="mono min-w-0 max-w-full truncate text-[11px] text-ink-2">{e.action.summary}</span>}
                  {e.tokens ? <span className="ml-auto text-[10px] text-muted tnum">{e.tokens} tok</span> : null}
                </div>
              </button>
              {isOpen && (
                <div className="mt-1.5 ml-14 space-y-1.5 text-[12px]">
                  {e.violation && (
                    <div className="rounded border border-[#5a2626] bg-[#1e1212] px-2 py-1.5 text-[#f5b5b5]">
                      <b>{e.violation.lawName}</b> · {e.violation.severity} · {e.violation.disposition === 'blocked' ? 'blocked before taking effect' : e.violation.disposition === 'executed' ? 'took effect' : 'flagged'} · {e.violation.propagated ? 'propagated from another agent' : e.violation.origin}
                      <div className="text-ink-2">{e.violation.explanation}</div>
                    </div>
                  )}
                  {e.evaluations?.map((ev, i) => (
                    <div key={i} className="rounded border border-line bg-surface px-2 py-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <Pill tone={ev.decision === 'allow' ? 'good' : 'crit'}>{ev.decision}</Pill>
                        <span className="text-ink-2">{ev.lawName}</span>
                        <span className="text-[10px] text-muted">{ev.evaluator === 'bend' ? 'Bend gate (compiled)' : ev.evaluator === 'bend_custom' ? 'custom Bend gate' : ev.evaluator === 'app' ? 'runtime code' : ev.evaluator} · {ev.micros}µs</span>
                      </div>
                      <div className="mono mt-1 text-[11px] break-all text-ink-2">{ev.input}</div>
                      <div className="text-[11px] text-muted">{ev.detail}</div>
                    </div>
                  ))}
                  {e.recovery?.feedback && (
                    <div className="rounded border border-[#1f3f66] bg-[#0f1c2c] px-2 py-1.5 text-[#b9d6f7]">
                      <span className="text-[10px] font-semibold tracking-wide uppercase">Corrective feedback → agent (attempt {e.recovery.attempt}/{e.recovery.maxAttempts})</span>
                      <div>{e.recovery.feedback}</div>
                    </div>
                  )}
                  {e.type === 'model_turn' && Array.isArray(e.data?.content) && (
                    <div className="space-y-1 rounded border border-line bg-surface px-2 py-1.5 text-[11px] text-ink-2">
                      {(e.data!.content as { type: string; text?: string; name?: string; input?: unknown; results?: { title: string; url: string }[] }[]).map((c, i) =>
                        c.type === 'text' && c.text ? <div key={i} className="whitespace-pre-wrap">{c.text}</div>
                        : c.type === 'tool_use' ? <div key={i} className="mono break-all">→ {c.name}({JSON.stringify(c.input).slice(0, 400)})</div>
                        : c.type === 'server_tool_use' ? <div key={i} className="mono">→ {c.name}({JSON.stringify(c.input)})</div>
                        : c.type === 'web_search_tool_result' ? <div key={i} className="text-muted">{c.results?.length ?? 0} search results: {c.results?.slice(0, 4).map((r) => new URL(r.url).hostname).join(', ')}{(c.results?.length ?? 0) > 4 ? ', …' : ''}</div>
                        : null,
                      )}
                    </div>
                  )}
                  {e.type === 'tool_error' && e.data?.feedback ? (
                    <div className="rounded border border-[#1f3f66] bg-[#0f1c2c] px-2 py-1.5 text-[#b9d6f7]">{String(e.data.feedback)}</div>
                  ) : null}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
