// Shared schema for the runtime, the experiment analysis and the UI.
// Every dashboard number is derived from TrajectoryEvent records (see metrics.ts).

export type ExecutionMode = 'simulation' | 'llm';

export type AgentState =
  | 'queued'
  | 'running'
  | 'recovering'
  | 'blocked'
  | 'awaiting_human'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type Health = 'green' | 'yellow' | 'red';

export type LawTemplate =
  | 'protected_resources'
  | 'bounded_retries'
  | 'evidence_requirements'
  | 'task_completion'
  | 'spending_limit'
  | 'data_policy'
  | 'file_ownership'
  | 'payee_provenance'
  | 'request_scope'
  | 'tool_restriction'
  | 'conditional_obligation'
  | 'required_reading'
  | 'custom_bend'
  | 'contextual';

export type CheckpointKind = 'pre_action' | 'post_action' | 'trajectory';

export type FaultType =
  | 'protected_write'
  | 'retry_loop'
  | 'insufficient_evidence'
  | 'premature_completion'
  | 'constraint_violation'
  | 'unverifiable_source'
  | 'prompt_injection'; // real runs only: instructions planted in data the agent reads

export const FAULT_TYPES: FaultType[] = [
  'protected_write',
  'retry_loop',
  'insufficient_evidence',
  'premature_completion',
  'constraint_violation',
  'unverifiable_source',
];

export const FAULT_LABELS: Record<FaultType, string> = {
  protected_write: 'Writes to a protected resource',
  retry_loop: 'Repeats a failing tool call',
  insufficient_evidence: 'Claims with < 2 independent sources',
  premature_completion: 'Claims completion before checks pass',
  constraint_violation: 'Output breaks a task constraint',
  unverifiable_source: 'Cites a source with no domain metadata',
  prompt_injection: 'Follows instructions planted in data',
};

/** Proof / validation lifecycle of a law. Never conflate these. */
export type ProofStatus =
  | 'not_applicable' // operational rule enforced by app code, no formal claim
  | 'stated' // law parses and type-checks, proof missing or open
  | 'proof_checked' // `bend` printed ALL PROOFS CHECK for this exact source
  | 'proof_failed' // law states something, but the proof was rejected
  | 'unavailable'; // Bend toolchain not found: nothing could be checked

export type ValidationStatus = 'valid' | 'invalid' | 'pending';

export interface LawParams {
  protectedPaths?: string[]; // protected_resources: path prefixes
  maxAttempts?: number; // bounded_retries
  minSources?: number; // evidence_requirements
  checks?: string[]; // task_completion: required check ids
  capCents?: number; // spending_limit
  blockedTools?: string[]; // tool_restriction: tool names (case-insensitive; a trailing * matches a prefix, e.g. mcp__github__*)
  // conditional_obligation: IF the agent writes under one of whenWrites (or calls one of whenTools),
  // THEN before it finishes a shell command containing mustRun must have run after its last such change
  whenWrites?: string[];
  whenTools?: string[];
  mustRun?: string;
  paths?: string[]; // required_reading: files the agent must read before it changes anything
}

/**
 * Who a law governs. Absent (or empty) = every agent in the swarm (a global law).
 * A role-scoped law governs only agents with one of these roles (e.g. 'implementer', 'lead');
 * an agent-scoped law governs only the listed agent ids. Each agent is checked against its own laws only.
 */
export interface LawScope {
  roles?: string[];
  agents?: string[];
}

/**
 * True when `law` governs an agent with these ids and roles. An agent can carry several: an attached session's
 * SC_AGENT name, and a subagent's own type plus its parent's names and roles (laws inherit down to subagents).
 */
export function lawAppliesTo(law: { appliesTo?: LawScope | null }, agentId: string | string[], role: string | string[]): boolean {
  const s = law.appliesTo;
  if (!s || (!s.roles?.length && !s.agents?.length)) return true;
  const ids = Array.isArray(agentId) ? agentId : [agentId];
  const roles = Array.isArray(role) ? role : [role];
  return Boolean(roles.some((r) => s.roles?.includes(r)) || ids.some((id) => s.agents?.includes(id)));
}

export interface Law {
  id: string;
  name: string;
  description: string;
  sourceType: 'builtin' | 'natural_language' | 'bend';
  template: LawTemplate;
  originalDefinition: string; // NL text or Bend source
  structured: StructuredRule | null;
  params: LawParams;
  bendLaw: string | null; // Bend law statement (+ proof) for this rule
  validation: ValidationStatus;
  validationErrors: string[];
  proofStatus: ProofStatus;
  proofOutput: string | null;
  enforcement: EnforcementMode;
  /** which agents this law governs; null/absent = all agents */
  appliesTo?: LawScope | null;
  enabled: boolean;
  /** true only when a runtime gate exists, the law is valid, and enabled */
  installed: boolean;
  createdAt: number;
  updatedAt: number;
}

export type EnforcementMode =
  | 'pre_action_block' // evaluated before the action executes
  | 'post_action_gate' // evaluated on a result before it is accepted
  | 'trajectory_bound' // evaluated on accumulated history
  | 'contextual_unenforced'; // needs an LLM evaluator, not enforced in this build

export interface StructuredRule {
  template: LawTemplate;
  params: LawParams;
  explanation: string;
  checkpoint: CheckpointKind | null;
  evaluator: 'bend' | 'app' | 'llm' | 'none';
  enforceability: 'deterministic' | 'contextual' | 'unsupported';
  sourceText: string; // span of the NL input this rule came from
  issues: string[]; // ambiguity / validation problems shown to the user
}

export type TaskHorizon = 'short' | 'long';

export interface FailureConfig {
  /** short horizon: probability that an agent receives an injected fault */
  rate: number;
  /** long horizon: probability of a fault at each risky step (search, write, claim, complete) */
  hazard: number;
  /** relative weights per fault type; 0 disables a type */
  weights: Record<FaultType, number>;
  /** probability that an agent repeats a violation after feedback */
  persistence: number;
}

export type Scenario = 'synthetic' | 'web_research' | 'bugfix' | 'suite';
export type AgentBackend = 'api' | 'claude_code' | 'openrouter';

export interface ExperimentConfig {
  /** synthetic: simulator (or LLM-written findings over synthetic sources); others: real model + real tools */
  scenario: Scenario;
  /** real scenarios: state the laws in the system prompt in BOTH conditions */
  rulesInPrompt: boolean;
  /** real scenarios: run only the first N tasks (per family for `suite`) */
  taskLimit?: number;
  /** suite: which task families to include */
  families?: string[];
  /** claude_code backend: run the real harness (its own system prompt and built-in tools), governed through hooks */
  harness?: boolean;
  /** attached mode: the project whose live harness sessions this experiment collects */
  attachProject?: string;
  /** real scenarios: direct Messages API loop, or Claude Code headless (subscription) */
  backend?: AgentBackend;
  /** benchmark this run belongs to */
  benchmarkId?: string;
  /** openrouter: hard spend cap for this experiment, in dollars */
  budgetUsd?: number;
  swarmSize: number;
  /** short: ~8-step task, one fault max. long: ~20-step multi-phase pipeline with hand-offs. */
  horizon: TaskHorizon;
  mode: ExecutionMode;
  governor: boolean;
  lawIds: string[];
  laws: Law[]; // snapshot at launch time, so reloads and pairs are consistent
  failure: FailureConfig;
  seed: number;
  maxRecoveryAttempts: number;
  /** virtual ms advanced per wall-clock ms; Infinity = run instantly */
  speed: number;
  maxParallel: number;
  model?: string;
  pairId?: string;
  pairRole?: 'baseline' | 'governed';
  repetition?: number;
  label?: string;
}

export interface Experiment {
  id: string;
  config: ExperimentConfig;
  mode: ExecutionMode;
  seed: number;
  status: 'running' | 'completed' | 'needs_attention' | 'error';
  startedAt: number;
  endedAt: number | null;
  error?: string | null;
}

export interface Subtask {
  topic: string;
  topicId: string;
  angle: string;
  question: string;
}

export interface SourceRecord {
  id: string;
  title: string;
  url: string;
  /** hostname from source metadata; null = metadata missing */
  domain: string | null;
  publisher: string;
  topicId: string;
  snippet: string;
}

export interface Finding {
  id: string;
  text: string;
  sourceIds: string[];
  topicId: string;
  accepted: boolean | null; // null until evaluated
  /** id of a peer finding this one builds on (long-horizon hand-off) */
  dependsOn?: string;
}

export interface LawEvaluation {
  lawId: string;
  lawName: string;
  evaluator: 'bend' | 'bend_custom' | 'app' | 'llm';
  /** what was asked of the gate, for the trajectory view */
  input: string;
  result: 'pass' | 'violation' | 'error';
  decision: 'allow' | 'block' | 'escalate';
  detail: string;
  /** measured wall time of the evaluation */
  micros: number;
}

export type EventType =
  | 'experiment_started'
  | 'agent_queued'
  | 'agent_started'
  | 'action_executed'
  | 'tool_error'
  | 'checkpoint_passed'
  | 'law_violated'
  | 'action_blocked'
  | 'violation_executed' // a violating action took effect (no governor)
  | 'recovery_initiated'
  | 'recovery_succeeded'
  | 'recovery_failed'
  | 'human_required'
  | 'human_action'
  | 'task_completed'
  | 'task_failed'
  | 'agent_cancelled'
  | 'model_turn' // one model response (content recorded for export / fine-tuning)
  | 'synthesis_completed'
  | 'quality_snapshot' // long-horizon swarm: the shared artefact graded against its release suite
  | 'case_completed' // ops shift: one customer conversation ended and was graded
  | 'experiment_completed';

export interface ActionRecord {
  tool: 'search' | 'read' | 'write' | 'submit_claim' | 'complete' | 'synthesize' | 'call';
  args: Record<string, unknown>;
  summary: string;
}

export interface ViolationDetail {
  violationId: string;
  lawId: string;
  lawName: string;
  template: LawTemplate;
  severity: 'critical' | 'high' | 'medium';
  explanation: string;
  origin: 'injected' | 'natural';
  faultType?: FaultType;
  /** set when this agent had no fault of its own: the violation was caused upstream */
  propagated?: boolean;
  /** blocked = prevented before taking effect; executed = took effect */
  disposition: 'blocked' | 'executed' | 'flagged';
}

export interface RecoveryDetail {
  violationId: string;
  attempt: number;
  maxAttempts: number;
  feedback?: string;
  reason?: string;
}

export interface TrajectoryEvent {
  id: number; // per-experiment sequence number
  experimentId: string;
  agentId: string | null;
  ts: number; // wall clock ms
  vt: number; // virtual (simulated) ms since experiment start
  type: EventType;
  action?: ActionRecord;
  checkpoint?: CheckpointKind;
  lawIds?: string[];
  evaluations?: LawEvaluation[];
  violation?: ViolationDetail;
  recovery?: RecoveryDetail;
  outcome?: 'allowed' | 'blocked' | 'flagged' | 'executed' | 'escalated';
  /** state/health after this event, so the log alone reconstructs the swarm */
  state?: AgentState;
  health?: Health;
  step?: string;
  tokens?: number;
  costUsd?: number;
  data?: Record<string, unknown>;
}

export interface AgentOutcome {
  agentId: string;
  taskSuccess: boolean;
  checks: Record<string, boolean>;
  claimedSuccess: boolean;
  violations: number;
  recoveryAttempts: number;
  tokens: number;
  costUsd: number;
  durationMs: number;
  finalState: AgentState;
  finalHealth: Health;
}

export interface ReportSection {
  topicId: string;
  topic: string;
  findings: { text: string; sources: { title: string; domain: string | null }[]; agentId: string; supported: boolean }[];
}

export interface SwarmReport {
  question: string;
  sections: ReportSection[];
  trends: string[];
  opportunities: string[];
  excludedFindings: number;
  unsupportedIncluded: number;
  simulated: boolean;
}
