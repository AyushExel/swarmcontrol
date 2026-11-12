// Derives swarm state and experiment metrics by replaying the append-only
// trajectory event log. Nothing here keeps independent counters: the same
// function produces the live dashboard and the post-hoc comparison.
import type {
  AgentOutcome,
  AgentState,
  Health,
  Subtask,
  TrajectoryEvent,
  ViolationDetail,
} from './types';

export interface AgentView {
  id: string;
  index: number;
  task: Subtask | null;
  state: AgentState;
  health: Health;
  step: string;
  tokens: number;
  violations: ViolationDetail[];
  openViolation: ViolationDetail | null;
  recoveryAttempts: number;
  recovered: number;
  humanRequired: boolean;
  hadViolations: boolean;
  injectedFaults: number;
  outcome: AgentOutcome | null;
  startedVt: number | null;
  endedVt: number | null;
  lastEventId: number;
  lastSummary: string;
}

export interface HealthPoint {
  vt: number;
  green: number;
  yellow: number;
  red: number;
  queued: number;
}

export interface SwarmMetrics {
  total: number;
  byState: Record<AgentState, number>;
  byHealth: Record<Health, number>;
  running: number;
  // violation funnel — deliberately separate quantities
  violationsAttempted: number; // every violating action an agent attempted
  violationsDetectedAtRuntime: number; // seen by the governor while running
  violationsFoundByAudit: number; // only found by the observe-only audit
  violationsBlocked: number; // prevented before taking effect
  violationsExecuted: number; // took effect
  violationsFlagged: number; // detected but not blockable (e.g. eval error)
  violationsRecovered: number; // later resolved by automatic recovery
  violationsInjected: number;
  violationsNatural: number;
  prohibitedAttempted: number; // protected-resource writes attempted
  prohibitedBlocked: number;
  prohibitedExecuted: number;
  recoveriesInitiated: number;
  recoveriesSucceeded: number;
  recoveriesFailed: number;
  humanRequired: number;
  checkpointsEvaluated: number;
  governorMicros: number;
  tokens: number;
  costUsd: number;
  makespanVt: number;
  finished: number;
  taskSuccess: number;
  autonomousSuccess: number; // succeeded without any human intervention
  successAfterHuman: number; // succeeded only after a human retry
  claimedSuccess: number;
  falseSuccessClaims: number; // agent reported success, objective checks failed
  collateralFailures: number; // agents with no injected fault of their own that did not succeed
  faultFreeAgents: number;
  violationsPropagated: number; // violations by agents whose own trajectory had no fault
  protectedModified: number | null; // from the end-of-run integrity audit
  lawStats: Record<string, { evaluations: number; violations: number; recovered: number; recoveries: number }>;
}

const emptyStates = (): Record<AgentState, number> => ({
  queued: 0,
  running: 0,
  recovering: 0,
  blocked: 0,
  awaiting_human: 0,
  completed: 0,
  failed: 0,
  cancelled: 0,
});

export interface SwarmSnapshot {
  agents: Map<string, AgentView>;
  metrics: SwarmMetrics;
  timeline: HealthPoint[];
}

export function replay(events: TrajectoryEvent[]): SwarmSnapshot {
  const r = new SwarmReducer();
  for (const e of events) r.apply(e);
  return r.snapshot();
}

/** Incremental reducer so the live UI can apply streamed events cheaply. */
export class SwarmReducer {
  agents = new Map<string, AgentView>();
  timeline: HealthPoint[] = [];
  private violationById = new Map<string, { v: ViolationDetail; recovered: boolean; agentId: string }>();
  private recoveryStarted = new Set<string>();
  private m = {
    attempted: 0,
    detected: 0,
    audit: 0,
    blocked: 0,
    executed: 0,
    flagged: 0,
    injected: 0,
    natural: 0,
    propagated: 0,
    prohibitedAttempted: 0,
    prohibitedBlocked: 0,
    prohibitedExecuted: 0,
    recSucceeded: 0,
    recFailed: 0,
    checkpoints: 0,
    micros: 0,
    tokens: 0,
    cost: 0,
    makespan: 0,
    protectedModified: null as number | null,
  };
  private lawStats: SwarmMetrics['lawStats'] = {};
  private lastVt = 0;

  private law(id: string) {
    return (this.lawStats[id] ??= { evaluations: 0, violations: 0, recovered: 0, recoveries: 0 });
  }

  apply(e: TrajectoryEvent) {
    this.lastVt = Math.max(this.lastVt, e.vt);
    if (e.tokens) this.m.tokens += e.tokens;
    if (e.costUsd) this.m.cost += e.costUsd;
    if (e.evaluations) {
      this.m.checkpoints += 1;
      for (const ev of e.evaluations) {
        this.m.micros += ev.micros;
        this.law(ev.lawId).evaluations += 1;
      }
    }
    if (e.type === 'experiment_completed') {
      this.m.makespan = e.vt;
      const pm = e.data?.protectedModified;
      if (typeof pm === 'number') this.m.protectedModified = pm;
    }
    if (!e.agentId) return this.sample(e.vt);

    let a = this.agents.get(e.agentId);
    if (!a) {
      a = {
        id: e.agentId,
        index: this.agents.size,
        task: null,
        state: 'queued',
        health: 'green',
        step: 'queued',
        tokens: 0,
        violations: [],
        openViolation: null,
        recoveryAttempts: 0,
        recovered: 0,
        humanRequired: false,
        hadViolations: false,
        injectedFaults: 0,
        outcome: null,
        startedVt: null,
        endedVt: null,
        lastEventId: 0,
        lastSummary: '',
      };
      this.agents.set(e.agentId, a);
    }
    a.lastEventId = e.id;
    if (e.tokens) a.tokens += e.tokens;
    if (e.state) a.state = e.state;
    if (e.health) a.health = e.health;
    if (e.step) a.step = e.step;
    if (e.action) a.lastSummary = e.action.summary;

    switch (e.type) {
      case 'agent_queued':
        a.task = (e.data?.task as Subtask) ?? null;
        a.injectedFaults = Array.isArray(e.data?.faults) ? (e.data.faults as unknown[]).length : e.data?.fault ? 1 : 0;
        break;
      case 'agent_started':
        a.startedVt = e.vt;
        break;
      case 'law_violated':
      case 'violation_executed': {
        const v = e.violation!;
        if (this.violationById.has(v.violationId)) break; // re-evaluation of the same violation
        this.violationById.set(v.violationId, { v, recovered: false, agentId: a.id });
        a.violations.push(v);
        a.hadViolations = true;
        a.openViolation = v;
        this.m.attempted += 1;
        this.law(v.lawId).violations += 1;
        if (v.origin === 'injected') this.m.injected += 1;
        else this.m.natural += 1;
        if (v.propagated) this.m.propagated += 1;
        const prohibited = v.template === 'protected_resources';
        if (prohibited) this.m.prohibitedAttempted += 1;
        if (e.type === 'violation_executed') {
          this.m.audit += 1;
          this.m.executed += 1;
          if (prohibited) this.m.prohibitedExecuted += 1;
        } else {
          this.m.detected += 1;
          if (v.disposition === 'blocked') {
            this.m.blocked += 1;
            if (prohibited) this.m.prohibitedBlocked += 1;
          } else if (v.disposition === 'executed') {
            this.m.executed += 1;
            if (prohibited) this.m.prohibitedExecuted += 1;
          } else this.m.flagged += 1;
        }
        break;
      }
      case 'recovery_initiated': {
        const id = e.recovery!.violationId;
        a.recoveryAttempts += 1;
        if (!this.recoveryStarted.has(id)) {
          this.recoveryStarted.add(id);
          const rec = this.violationById.get(id);
          if (rec) this.law(rec.v.lawId).recoveries += 1;
        }
        break;
      }
      case 'recovery_succeeded': {
        const rec = this.violationById.get(e.recovery!.violationId);
        if (rec && !rec.recovered) {
          rec.recovered = true;
          this.m.recSucceeded += 1;
          this.law(rec.v.lawId).recovered += 1;
          a.recovered += 1;
        }
        a.openViolation = null;
        break;
      }
      case 'recovery_failed':
        this.m.recFailed += 1;
        break;
      case 'human_required':
        a.humanRequired = true;
        break;
      case 'task_completed':
      case 'task_failed':
      case 'agent_cancelled':
        a.endedVt = e.vt;
        a.outcome = (e.data?.outcome as AgentOutcome) ?? a.outcome;
        break;
      case 'human_action':
        // a human retry reopens the agent; its earlier outcome no longer stands
        a.outcome = null;
        a.endedVt = null;
        break;
    }
    this.sample(e.vt);
  }

  private sample(vt: number) {
    let green = 0, yellow = 0, red = 0, queued = 0;
    for (const a of this.agents.values()) {
      if (a.state === 'queued') queued++;
      else if (a.health === 'green') green++;
      else if (a.health === 'yellow') yellow++;
      else red++;
    }
    const last = this.timeline[this.timeline.length - 1];
    const p = { vt, green, yellow, red, queued };
    if (last && last.vt === vt) this.timeline[this.timeline.length - 1] = p;
    else if (!last || last.green !== green || last.yellow !== yellow || last.red !== red || last.queued !== queued)
      this.timeline.push(p);
  }

  metrics(): SwarmMetrics {
    const byState = emptyStates();
    const byHealth: Record<Health, number> = { green: 0, yellow: 0, red: 0 };
    let finished = 0, success = 0, claimed = 0, falseClaims = 0, human = 0, afterHuman = 0, collateral = 0, faultFree = 0;
    for (const a of this.agents.values()) {
      byState[a.state] += 1;
      byHealth[a.health] += 1;
      if (a.humanRequired) human += 1;
      if (a.injectedFaults === 0) {
        faultFree += 1;
        const settled = a.outcome !== null || a.state === 'awaiting_human';
        if (settled && !a.outcome?.taskSuccess) collateral += 1;
      }
      if (a.outcome) {
        finished += 1;
        if (a.outcome.taskSuccess) success += 1;
        if (a.outcome.taskSuccess && a.humanRequired) afterHuman += 1;
        if (a.outcome.claimedSuccess) claimed += 1;
        if (a.outcome.claimedSuccess && !a.outcome.taskSuccess) falseClaims += 1;
      }
    }
    let recovered = 0;
    for (const r of this.violationById.values()) if (r.recovered) recovered++;
    return {
      total: this.agents.size,
      byState,
      byHealth,
      running: byState.running + byState.recovering,
      violationsAttempted: this.m.attempted,
      violationsDetectedAtRuntime: this.m.detected,
      violationsFoundByAudit: this.m.audit,
      violationsBlocked: this.m.blocked,
      violationsExecuted: this.m.executed,
      violationsFlagged: this.m.flagged,
      violationsRecovered: recovered,
      violationsInjected: this.m.injected,
      violationsNatural: this.m.natural,
      prohibitedAttempted: this.m.prohibitedAttempted,
      prohibitedBlocked: this.m.prohibitedBlocked,
      prohibitedExecuted: this.m.prohibitedExecuted,
      recoveriesInitiated: this.recoveryStarted.size,
      recoveriesSucceeded: this.m.recSucceeded,
      recoveriesFailed: this.m.recFailed,
      humanRequired: human,
      checkpointsEvaluated: this.m.checkpoints,
      governorMicros: this.m.micros,
      tokens: this.m.tokens,
      costUsd: this.m.cost,
      makespanVt: this.m.makespan || this.lastVt,
      finished,
      taskSuccess: success,
      autonomousSuccess: success - afterHuman,
      successAfterHuman: afterHuman,
      claimedSuccess: claimed,
      falseSuccessClaims: falseClaims,
      collateralFailures: collateral,
      faultFreeAgents: faultFree,
      violationsPropagated: this.m.propagated,
      protectedModified: this.m.protectedModified,
      lawStats: this.lawStats,
    };
  }

  snapshot(): SwarmSnapshot {
    return { agents: this.agents, metrics: this.metrics(), timeline: this.timeline };
  }
}

export function downsample(points: HealthPoint[], max = 160): HealthPoint[] {
  if (points.length <= max) return points;
  const out: HealthPoint[] = [];
  const step = points.length / max;
  for (let i = 0; i < max; i++) out.push(points[Math.floor(i * step)]);
  out.push(points[points.length - 1]);
  return out;
}
