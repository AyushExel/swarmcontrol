import type { ReactNode } from 'react';
import type { AgentState, Health, Law } from '../shared/types';
import { withToken } from '../api';

export const cx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(' ');

export function Panel({ title, right, children, className, pad = true }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={cx('rounded-lg border border-line bg-panel', className)}>
      {(title || right) && (
        <header className="flex min-h-10 items-center justify-between gap-3 border-b border-line px-4 py-2">
          <h2 className="text-[12px] font-medium tracking-wide text-ink-2 uppercase">{title}</h2>
          <div className="flex items-center gap-2">{right}</div>
        </header>
      )}
      <div className={pad ? 'p-4' : ''}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'good' | 'warn' | 'crit' }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-panel px-4 py-3">
      <div className="flex items-center gap-1.5 text-[11px] text-muted">
        {tone && <span className={cx('inline-block size-2 rounded-full', tone === 'good' ? 'bg-good' : tone === 'warn' ? 'bg-warn' : 'bg-crit')} />}
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-1 text-[22px] leading-7 font-semibold tnum text-ink">{value}</div>
      {sub && <div className="mt-0.5 truncate text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

export function Button({ children, onClick, kind = 'default', disabled, type = 'button', small, title }: { children: ReactNode; onClick?: () => void; kind?: 'default' | 'primary' | 'danger' | 'ghost'; disabled?: boolean; type?: 'button' | 'submit'; small?: boolean; title?: string }) {
  return (
    <button
      type={type}
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        small ? 'h-7 px-2.5 text-[12px]' : 'h-8 px-3 text-[13px]',
        kind === 'primary' && 'border-gov bg-gov text-white hover:bg-[#4a93ea]',
        kind === 'default' && 'border-line-strong bg-raised text-ink hover:border-[#4a4a45]',
        kind === 'danger' && 'border-[#5a2626] bg-[#2a1717] text-[#f0a0a0] hover:border-crit',
        kind === 'ghost' && 'border-transparent text-ink-2 hover:bg-raised hover:text-ink',
      )}
    >
      {children}
    </button>
  );
}

export const HEALTH_LABEL: Record<Health, string> = { green: 'Healthy', yellow: 'Recovering', red: 'Intervention' };
export const HEALTH_GLYPH: Record<Health, string> = { green: '●', yellow: '◐', red: '■' };

export function HealthBadge({ health, compact }: { health: Health; compact?: boolean }) {
  const c = health === 'green' ? 'text-good' : health === 'yellow' ? 'text-warn' : 'text-crit';
  return (
    <span className={cx('inline-flex items-center gap-1 text-[12px] whitespace-nowrap', c)}>
      <span aria-hidden>{HEALTH_GLYPH[health]}</span>
      {!compact && <span className="text-ink-2">{HEALTH_LABEL[health]}</span>}
    </span>
  );
}

export function StateBadge({ state }: { state: AgentState }) {
  return <span className="mono rounded border border-line-strong bg-raised px-1.5 py-px text-[11px] whitespace-nowrap text-ink-2">{state}</span>;
}

export function Pill({ children, tone = 'neutral', title }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'crit' | 'gov' | 'base'; title?: string }) {
  const tones = {
    neutral: 'border-line-strong text-ink-2',
    good: 'border-[#1f4d1f] text-[#6fd66f] bg-[#0f220f]',
    warn: 'border-[#5a4410] text-[#fbcb5c] bg-[#261d08]',
    crit: 'border-[#5a2626] text-[#f08a8a] bg-[#2a1515]',
    gov: 'border-[#1f3f66] text-[#8ab9f1] bg-[#0f1c2c]',
    base: 'border-[#5c3020] text-[#f0a07e] bg-[#2a170e]',
  };
  return (
    <span title={title} className={cx('inline-flex items-center gap-1 rounded border px-1.5 py-px text-[11px] font-medium whitespace-nowrap', tones[tone])}>
      {children}
    </span>
  );
}

export const PROOF_LABEL: Record<Law['proofStatus'], string> = {
  proof_checked: 'Proof checked',
  stated: 'Stated · unproven',
  proof_failed: 'Proof rejected',
  not_applicable: 'No formal claim',
  unavailable: 'Bend unavailable',
};

export function ProofBadge({ status }: { status: Law['proofStatus'] }) {
  const tone = status === 'proof_checked' ? 'good' : status === 'stated' ? 'warn' : status === 'proof_failed' || status === 'unavailable' ? 'crit' : 'neutral';
  return (
    <Pill tone={tone} title={status === 'proof_checked' ? '`bend` printed ALL PROOFS CHECK for this exact source' : undefined}>
      {status === 'proof_checked' ? '✓' : status === 'stated' ? '○' : status === 'not_applicable' ? '–' : '✕'} {PROOF_LABEL[status]}
    </Pill>
  );
}

export function ModeBadge({ mode, scenario }: { mode: 'simulation' | 'llm'; scenario?: string }) {
  if (scenario === 'web_research') return <Pill tone="gov" title="Claude with real web search; citations are real URLs">REAL · WEB RESEARCH</Pill>;
  if (scenario === 'bugfix') return <Pill tone="gov" title="Claude fixing real bugs; success decided by running the real tests">REAL · BUG FIX</Pill>;
  return mode === 'simulation' ? (
    <Pill tone="neutral" title="Deterministic simulator: synthetic agents and injected failures">SIMULATED</Pill>
  ) : (
    <Pill tone="gov" title="Model-backed agents: findings written by a real LLM">REAL LLM</Pill>
  );
}

export function GovBadge({ governed }: { governed: boolean }) {
  return governed ? <Pill tone="gov">Governor ON</Pill> : <Pill tone="base">Governor OFF</Pill>;
}

/** Download links for the JSONL trace exports of the given experiments. */
export function ExportLinks({ ids }: { ids: string[] }) {
  const q = ids.join(',');
  const link = (format: string, label: string, title: string) => (
    <a href={withToken(`/api/export?format=${format}&experiments=${q}`)} download={`${format}.jsonl`} title={title} className="rounded px-2 py-1 text-[11px] text-ink-2 hover:bg-raised hover:text-ink">
      {label}
    </a>
  );
  return (
    <span className="inline-flex items-center gap-0.5 rounded-md border border-line-strong bg-surface px-1">
      <span className="px-1.5 text-[11px] text-muted">Export</span>
      {link('trajectories', 'trajectories.jsonl', 'Every agent: task, outcome, checks, labelled violations, recoveries; plus the conversation for real-model runs')}
      {link('sft', 'sft.jsonl', 'Real-model conversations that succeeded with no violation taking effect')}
      {link('preferences', 'preferences.jsonl', 'Governed real-model runs: blocked turn (rejected) vs corrected turn that passed the gate (chosen)')}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="flex min-h-32 items-center justify-center px-4 py-8 text-center text-[13px] text-muted">{children}</div>;
}

export function fmtPct(n: number, d: number) {
  if (!d) return '—';
  return `${((n / d) * 100).toFixed(n / d >= 0.995 || n === 0 ? 0 : 1)}%`;
}

export function fmtNum(n: number) {
  return n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : n >= 1e4 ? `${(n / 1e3).toFixed(1)}k` : n.toLocaleString();
}

export function fmtVt(ms: number) {
  const s = ms / 1000;
  return s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${s.toFixed(1)}s`;
}

export function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] font-medium text-ink-2">{label}</div>
      {children}
      {hint && <div className="mt-1 text-[11px] text-muted">{hint}</div>}
    </label>
  );
}

export const inputCls = 'h-8 w-full rounded-md border border-line-strong bg-surface px-2.5 text-[13px] text-ink placeholder:text-muted focus:border-gov focus:outline-none';

export function Segmented<T extends string | number | boolean>({ value, options, onChange }: { value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-md border border-line-strong bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          onClick={() => onChange(o.value)}
          className={cx('h-7 rounded px-3 text-[12px] font-medium', o.value === value ? 'bg-raised text-ink shadow-[inset_0_0_0_1px_#3a3a36]' : 'text-muted hover:text-ink')}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
