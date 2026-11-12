import { useMemo, useState } from 'react';
import type { Law, LawParams, LawScope, StructuredRule } from '../shared/types';
import { api, useExperiment, usePoll } from '../api';
import { PageHeader, useApp } from '../App';
import { Button, Empty, Field, Panel, Pill, ProofBadge, Segmented, cx, fmtPct, inputCls } from '../components/ui';

const DEMO_NL =
  'Agents must not claim a task is complete until all required checks pass. Each final research claim must have at least two independent supporting sources. Agents must not make more than three consecutive unsuccessful recovery attempts.';

const DEMO_BEND = `import Base
import ./governor.bend as G
import ./LAWS.bend as L
import ./PROOF.bend as P

# Runtime gate: block writes to the shared outline (resource 6) and
# require THREE independent domains for every claim.
def gate(c: G.Checkpoint) -> G.Decision:
  match c:
    case G.Write{r}:
      G.block_if(Nat.is_eq(r, 6n))
    case G.Claim{ds}:
      G.evidence_gate(3n, ds)
    case _:
      G.Allow{}

# The outline is protected.
law outline_frozen:
  {gate(G.Write{6n}) == G.Block{} : G.Decision}

def outline_frozen():
  {==}

# No amount of citations from a single publisher passes this gate.
law one_publisher_never_enough:
  for d: Nat
  for n: Nat
  {gate(G.Claim{List.replicate(Nat, 1n+n, d)}) == G.Block{} : G.Decision}

def one_publisher_never_enough(d, n):
  L.single_domain_insufficient(d, n, 1n)
`;

const ENFORCEMENT_LABEL: Record<Law['enforcement'], string> = {
  pre_action_block: 'pre-action block',
  post_action_gate: 'post-action gate',
  trajectory_bound: 'trajectory bound',
  contextual_unenforced: 'not enforced (contextual)',
};

export function Laws() {
  const laws = usePoll(api.laws, 0);
  const { selected, status } = useApp();
  const live = useExperiment(selected?.id ?? null);
  const stats = live.snapshot?.metrics.lawStats ?? {};
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState<'nl' | 'bend'>('nl');

  return (
    <div className="pb-10">
      <PageHeader title="Laws" sub="Behavioral laws enforced at runtime checkpoints. Formal properties are checked by the real Bend toolchain." />
      <div className="space-y-4 px-4 md:px-6">
        <CoreProofs />
        <Panel title="Configured laws" right={<span className="text-[11px] text-muted">evaluation stats: selected experiment {selected ? `(${selected.config.governor ? 'governed' : 'baseline audit'})` : ''}</span>} pad={false}>
          {!laws.data ? (
            <Empty>Loading…</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left text-[11px] text-muted">
                    <th className="px-4 py-2 font-medium">Law</th>
                    <th className="px-2 py-2 font-medium">Applies to</th>
                    <th className="px-2 py-2 font-medium">Definition</th>
                    <th className="px-2 py-2 font-medium">Validation</th>
                    <th className="px-2 py-2 font-medium">Proof</th>
                    <th className="px-2 py-2 font-medium">Enforcement</th>
                    <th className="px-2 py-2 text-right font-medium">Evals</th>
                    <th className="px-2 py-2 text-right font-medium">Violations</th>
                    <th className="px-2 py-2 text-right font-medium">Recovery</th>
                    <th className="px-4 py-2 text-right font-medium">Enabled</th>
                  </tr>
                </thead>
                <tbody>
                  {laws.data.map((l) => {
                    const s = stats[l.id];
                    return (
                      <LawRow key={l.id} law={l} open={open === l.id} onToggle={() => setOpen(open === l.id ? null : l.id)} s={s} onChange={laws.reload} />
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
        <Panel title="Add a law" right={<Segmented value={adding} onChange={setAdding} options={[{ value: 'nl', label: 'Natural language' }, { value: 'bend', label: 'Bend' }]} />}>
          {adding === 'nl' ? <NlEditor llm={Boolean(status?.llm.available)} onDone={laws.reload} /> : <BendEditor onDone={laws.reload} />}
        </Panel>
      </div>
    </div>
  );
}

function LawRow({ law, open, onToggle, s, onChange }: { law: Law; open: boolean; onToggle: () => void; s?: { evaluations: number; violations: number; recovered: number; recoveries: number }; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    setBusy(true);
    await api.updateLaw(law.id, { enabled: !law.enabled }).catch(() => null);
    setBusy(false);
    onChange();
  };
  return (
    <>
      <tr className={cx('cursor-pointer border-b border-line/60 hover:bg-raised/40', open && 'bg-raised/40')} onClick={onToggle}>
        <td className="px-4 py-2">
          <div className="font-medium text-ink">{law.name}</div>
          <div className="max-w-[420px] truncate text-[11px] text-muted">{law.description || law.originalDefinition}</div>
        </td>
        <td className="px-2 py-2"><ScopePill scope={law.appliesTo} /></td>
        <td className="px-2 py-2"><Pill>{law.sourceType === 'builtin' ? 'Bend (built-in)' : law.sourceType === 'bend' ? 'Bend' : 'Natural language'}</Pill></td>
        <td className="px-2 py-2"><Pill tone={law.validation === 'valid' ? 'good' : law.validation === 'invalid' ? 'crit' : 'warn'}>{law.validation}</Pill></td>
        <td className="px-2 py-2"><ProofBadge status={law.proofStatus} /></td>
        <td className="px-2 py-2 text-ink-2">
          {ENFORCEMENT_LABEL[law.enforcement]}
          <div className="text-[10px] text-muted">{law.installed ? 'installed in runtime' : 'not installed'}</div>
        </td>
        <td className="px-2 py-2 text-right tnum">{s?.evaluations ?? 0}</td>
        <td className="px-2 py-2 text-right tnum">{s?.violations ?? 0}</td>
        <td className="px-2 py-2 text-right tnum">{s?.recoveries ? fmtPct(s.recovered, s.recoveries) : '—'}</td>
        <td className="px-4 py-2 text-right" onClick={(e) => e.stopPropagation()}>
          <button onClick={toggle} disabled={busy} className={cx('relative inline-flex h-5 w-9 items-center rounded-full border transition-colors', law.enabled ? 'border-gov bg-gov' : 'border-line-strong bg-surface')} aria-label={law.enabled ? 'Disable' : 'Enable'}>
            <span className={cx('inline-block size-3.5 rounded-full bg-white transition-transform', law.enabled ? 'translate-x-4' : 'translate-x-0.5')} />
          </button>
        </td>
      </tr>
      {open && (
        <tr className="border-b border-line">
          <td colSpan={10} className="bg-surface px-4 py-4">
            <LawEditor law={law} onChange={onChange} />
          </td>
        </tr>
      )}
    </>
  );
}

/** Global laws govern every agent; scoped laws govern only the listed roles or agent ids. */
function ScopePill({ scope }: { scope?: LawScope | null }) {
  if (!scope || (!scope.roles?.length && !scope.agents?.length)) return <Pill>All agents</Pill>;
  return (
    <span className="flex flex-wrap gap-1">
      {scope.roles?.map((r) => <Pill key={r} tone="good">role: {r}</Pill>)}
      {scope.agents?.map((a) => <Pill key={a} tone="good">{a}</Pill>)}
    </span>
  );
}

const splitList = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

function ScopeFields({ scope, onChange }: { scope: LawScope | null; onChange: (s: LawScope | null) => void }) {
  const [roles, setRoles] = useState((scope?.roles ?? []).join(', '));
  const [agents, setAgents] = useState((scope?.agents ?? []).join(', '));
  const emit = (r: string, a: string) => {
    const next = { roles: splitList(r), agents: splitList(a) };
    onChange(next.roles.length || next.agents.length ? next : null);
  };
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <Field label="Applies to roles" hint="Comma-separated, e.g. implementer, lead, or a Claude Code subagent type (reviewer, Explore). Empty = every agent.">
        <input value={roles} onChange={(e) => { setRoles(e.target.value); emit(e.target.value, agents); }} placeholder="all roles" className={inputCls} />
      </Field>
      <Field label="…or to specific agents" hint="Agent ids, e.g. agent-003, or an attached session’s SC_AGENT name.">
        <input value={agents} onChange={(e) => { setAgents(e.target.value); emit(roles, e.target.value); }} placeholder="all agents" className={inputCls} />
      </Field>
    </div>
  );
}

function ParamsForm({ template, params, onChange }: { template: Law['template']; params: LawParams; onChange: (p: LawParams) => void }) {
  const { status } = useApp();
  if (template === 'protected_resources')
    return (
      <Field label="Protected paths (one per line; trailing / = directory)" hint={status ? `Sandbox resources: ${status.catalog.join(', ')}` : undefined}>
        <textarea rows={4} value={(params.protectedPaths ?? []).join('\n')} onChange={(e) => onChange({ ...params, protectedPaths: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} className={cx(inputCls, 'mono h-auto py-1.5')} />
      </Field>
    );
  if (template === 'conditional_obligation')
    return (
      <div className="space-y-2">
        <Field label="If the agent writes under (one path per line)" hint="Paths inside the project are /repo/..., e.g. /repo/test/ or /repo/src/.">
          <textarea rows={2} value={(params.whenWrites ?? []).join('\n')} onChange={(e) => onChange({ ...params, whenWrites: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} className={cx(inputCls, 'mono h-auto py-1.5')} />
        </Field>
        <Field label="…or uses one of these tools (one per line)">
          <textarea rows={1} value={(params.whenTools ?? []).join('\n')} onChange={(e) => onChange({ ...params, whenTools: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} className={cx(inputCls, 'mono h-auto py-1.5')} />
        </Field>
        <Field label="Then, before finishing, it must run a command containing" hint="Checked when the agent tries to stop: the command must have run after its last triggering change.">
          <input value={params.mustRun ?? ''} onChange={(e) => onChange({ ...params, mustRun: e.target.value })} className={cx(inputCls, 'mono')} />
        </Field>
      </div>
    );
  if (template === 'tool_restriction')
    return (
      <Field label="Restricted tools (one per line)" hint="Tool names as the harness reports them, e.g. Bash, Write, Edit, WebFetch, or mcp__github__* for every tool of one MCP server.">
        <textarea rows={3} value={(params.blockedTools ?? []).join('\n')} onChange={(e) => onChange({ ...params, blockedTools: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} className={cx(inputCls, 'mono h-auto py-1.5')} />
      </Field>
    );
  if (template === 'bounded_retries')
    return (
      <Field label="Retry limit (max consecutive recovery attempts)" hint="For the built-in law, the experiment's 'max recovery attempts' setting overrides this.">
        <input type="number" min={1} max={10} value={params.maxAttempts ?? ''} onChange={(e) => onChange({ ...params, maxAttempts: e.target.value === '' ? undefined : Number(e.target.value) })} className={cx(inputCls, 'w-28')} />
      </Field>
    );
  if (template === 'evidence_requirements')
    return (
      <Field label="Minimum independent sources" hint="Independence = distinct registrable domain (last two hostname labels). Ownership or syndication across domains is not detected.">
        <input type="number" min={1} max={5} value={params.minSources ?? ''} onChange={(e) => onChange({ ...params, minSources: e.target.value === '' ? undefined : Number(e.target.value) })} className={cx(inputCls, 'w-28')} />
      </Field>
    );
  if (template === 'task_completion' && status)
    return (
      <Field label="Required checks">
        <div className="space-y-1">
          {Object.entries(status.checks).map(([k, label]) => (
            <label key={k} className="flex items-center gap-2 text-[12px]">
              <input type="checkbox" checked={(params.checks ?? Object.keys(status.checks)).includes(k)} onChange={(e) => {
                const cur = params.checks ?? Object.keys(status.checks);
                onChange({ ...params, checks: e.target.checked ? [...cur, k] : cur.filter((x) => x !== k) });
              }} />
              <span className="mono text-ink-2">{k}</span>
              <span className="text-muted">{label}</span>
            </label>
          ))}
        </div>
      </Field>
    );
  return null;
}

function LawEditor({ law, onChange }: { law: Law; onChange: () => void }) {
  const [params, setParams] = useState<LawParams>(law.params);
  const [source, setSource] = useState(law.originalDefinition);
  const [scope, setScope] = useState<LawScope | null>(law.appliesTo ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.updateLaw(law.id, law.template === 'custom_bend' ? { source, appliesTo: scope } : { params, appliesTo: scope });
      onChange();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <div className="space-y-3">
        {law.template === 'custom_bend' ? (
          <Field label="Bend source">
            <textarea rows={16} value={source} onChange={(e) => setSource(e.target.value)} className={cx(inputCls, 'mono h-auto py-2 text-[12px]')} spellCheck={false} />
          </Field>
        ) : (
          <>
            {law.sourceType !== 'builtin' && (
              <div className="text-[12px]"><span className="text-muted">Original text: </span><span className="text-ink-2">“{law.originalDefinition}”</span></div>
            )}
            <ParamsForm template={law.template} params={params} onChange={setParams} />
          </>
        )}
        <ScopeFields scope={scope} onChange={setScope} />
        {law.validationErrors.length > 0 && (
          <ul className="space-y-1 text-[12px]">
            {law.validationErrors.map((e) => <li key={e} className={law.validation === 'invalid' ? 'text-crit' : 'text-warn'}>• {e}</li>)}
          </ul>
        )}
        <div className="flex gap-2">
          {law.template !== 'contextual' && <Button kind="primary" small disabled={busy} onClick={save}>Save & validate</Button>}
          <Button small disabled={busy} onClick={async () => { setBusy(true); await api.validateLaw(law.id); setBusy(false); onChange(); }}>Re-validate</Button>
          {law.sourceType !== 'builtin' && <Button small kind="danger" disabled={busy} onClick={async () => { await api.deleteLaw(law.id); onChange(); }}>Delete</Button>}
        </div>
        {err && <div className="text-[12px] text-crit">{err}</div>}
        {law.structured && (
          <Field label="Structured representation">
            <pre className="mono max-h-56 overflow-auto rounded-md border border-line bg-bg p-2 text-[11px] text-ink-2">{JSON.stringify(law.structured, null, 2)}</pre>
          </Field>
        )}
      </div>
      <div className="space-y-3">
        {law.sourceType === 'builtin' && (
          <Field label="General law (bend/LAWS.bend, proven in bend/PROOF.bend)">
            <pre className="mono max-h-56 overflow-auto rounded-md border border-line bg-bg p-2 text-[11px] text-ink-2">{law.originalDefinition}</pre>
          </Field>
        )}
        {law.bendLaw && law.template !== 'custom_bend' && (
          <Field label="Instance checked for these parameters">
            <pre className="mono max-h-64 overflow-auto rounded-md border border-line bg-bg p-2 text-[11px] text-ink-2">{law.bendLaw}</pre>
          </Field>
        )}
        <Field label="Bend checker output">
          <pre className={cx('mono max-h-48 overflow-auto rounded-md border bg-bg p-2 text-[11px]', law.proofStatus === 'proof_checked' ? 'border-[#1f4d1f] text-[#a6e6a6]' : 'border-line text-ink-2')}>{law.proofOutput ?? '(no formal property for this law)'}</pre>
        </Field>
        <ProofExplainer status={law.proofStatus} />
      </div>
    </div>
  );
}

function ProofExplainer({ status }: { status: Law['proofStatus'] }) {
  const text: Record<Law['proofStatus'], string> = {
    proof_checked: 'The Bend checker accepted a proof of this property for this exact source. This verifies the gate function’s logic. It does not verify the application code that maps paths and sources to the ids the gate sees.',
    stated: 'The law is well-formed but unproven. It can still be enforced at runtime if it installs a gate, but it is not marked as verified.',
    proof_failed: 'Bend rejected the proof. The property is not established.',
    not_applicable: 'No formal property is claimed for this rule.',
    unavailable: 'The Bend toolchain was not found, so nothing could be checked.',
  };
  return <div className="text-[11px] text-muted">{text[status]}</div>;
}

function NlEditor({ llm, onDone }: { llm: boolean; onDone: () => void }) {
  const [text, setText] = useState(DEMO_NL);
  const [useLlm, setUseLlm] = useState(llm);
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState<LawScope | null>(null);
  const [res, setRes] = useState<{ translator: string; error?: string; items: { rule: StructuredRule; draft: Law; on: boolean }[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.translate(text, useLlm);
      setRes({ translator: r.translator, error: r.error, items: r.rules.map((rule, i) => ({ rule, draft: r.drafts[i], on: r.drafts[i].validation === 'valid' && rule.enforceability === 'deterministic' })) });
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  const updateRule = async (i: number, params: LawParams) => {
    if (!res) return;
    const rule = { ...res.items[i].rule, params };
    const draft = await api.preview(rule);
    const items = res.items.slice();
    items[i] = { rule, draft, on: draft.validation === 'valid' && rule.enforceability === 'deterministic' };
    setRes({ ...res, items });
  };
  const activate = async () => {
    if (!res) return;
    setBusy(true);
    try {
      await api.activate(res.items.filter((x) => x.on).map((x) => x.rule), scope);
      setRes(null);
      onDone();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  const selectedCount = res?.items.filter((x) => x.on).length ?? 0;

  return (
    <div className="space-y-3">
      <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} className={cx(inputCls, 'h-auto py-2')} />
      <ScopeFields scope={scope} onChange={setScope} />
      <div className="flex flex-wrap items-center gap-3">
        <Button kind="primary" disabled={busy || !text.trim()} onClick={generate}>{busy ? 'Working…' : 'Generate structured rules'}</Button>
        <label className={cx('flex items-center gap-1.5 text-[12px]', !llm && 'text-muted')}>
          <input type="checkbox" checked={useLlm} disabled={!llm} onChange={(e) => setUseLlm(e.target.checked)} /> Use LLM translator {llm ? '' : '(needs ANTHROPIC_API_KEY)'}
        </label>
        <span className="text-[11px] text-muted">Only a small set of templates is supported. Anything else is flagged, never silently accepted.</span>
      </div>
      {err && <div className="text-[12px] text-crit">{err}</div>}
      {res && (
        <div className="space-y-3">
          <div className="text-[11px] text-muted">Translator: <span className="mono text-ink-2">{res.translator}</span>{res.error && <span className="text-warn"> · {res.error}</span>}</div>
          {res.items.map((it, i) => (
            <div key={i} className={cx('rounded-md border p-3', it.on ? 'border-gov/60 bg-[#0f1c2c]/40' : 'border-line bg-surface')}>
              <div className="flex flex-wrap items-center gap-2">
                <input type="checkbox" checked={it.on} disabled={it.draft.validation !== 'valid' || it.rule.enforceability !== 'deterministic'} onChange={(e) => { const items = res.items.slice(); items[i] = { ...it, on: e.target.checked }; setRes({ ...res, items }); }} />
                <span className="font-medium">{it.draft.name}</span>
                <Pill tone={it.rule.enforceability === 'deterministic' ? 'good' : it.rule.enforceability === 'contextual' ? 'warn' : 'crit'}>
                  {it.rule.enforceability === 'deterministic' ? 'deterministically enforceable' : it.rule.enforceability === 'contextual' ? 'contextual: needs LLM evaluator (not enforced)' : 'unsupported'}
                </Pill>
                <Pill tone={it.draft.validation === 'valid' ? 'good' : 'crit'}>{it.draft.validation}</Pill>
                {it.rule.enforceability === 'deterministic' && <ProofBadge status={it.draft.proofStatus} />}
              </div>
              <div className="mt-1 text-[12px] text-ink-2">“{it.rule.sourceText}”</div>
              <div className="mt-1 text-[12px] text-ink">{it.rule.explanation}</div>
              {[...new Set([...it.rule.issues, ...it.draft.validationErrors])].length > 0 && (
                <ul className="mt-1 text-[12px] text-warn">
                  {[...new Set([...it.rule.issues, ...it.draft.validationErrors])].map((x) => <li key={x}>• {x}</li>)}
                </ul>
              )}
              {it.rule.enforceability === 'deterministic' && (
                <div className="mt-2 grid gap-3 lg:grid-cols-2">
                  <div className="space-y-2">
                    <ParamsForm template={it.rule.template} params={it.rule.params} onChange={(p) => updateRule(i, p)} />
                    <pre className="mono max-h-40 overflow-auto rounded border border-line bg-bg p-2 text-[11px] text-ink-2">{JSON.stringify({ template: it.rule.template, params: it.rule.params, checkpoint: it.rule.checkpoint, evaluator: it.rule.evaluator }, null, 2)}</pre>
                  </div>
                  <div>
                    <pre className="mono max-h-56 overflow-auto rounded border border-line bg-bg p-2 text-[11px] text-ink-2">{it.draft.bendLaw ?? '(no Bend property for these parameters)'}</pre>
                    {it.draft.proofOutput && <div className="mono mt-1 text-[11px] text-muted">$ bend INSTANCE.bend → {it.draft.proofOutput.split('\n')[0]}</div>}
                  </div>
                </div>
              )}
            </div>
          ))}
          <div className="flex items-center gap-2">
            <Button kind="primary" disabled={busy || selectedCount === 0} onClick={activate}>Activate {selectedCount} validated rule{selectedCount === 1 ? '' : 's'}</Button>
            <span className="text-[11px] text-muted">A translated law is enforced by its template’s Bend gate. Translating text into Bend does not mean the text itself was proven.</span>
          </div>
        </div>
      )}
    </div>
  );
}

function BendEditor({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('Freeze outline, 3-source claims');
  const [src, setSrc] = useState(DEMO_BEND);
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState<Law | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [scope, setScope] = useState<LawScope | null>(null);
  const run = async (save: boolean) => {
    setBusy(true);
    setErr(null);
    try {
      if (save) {
        await api.createBend(name, src, '', scope);
        onDone();
        setCheck(null);
      } else setCheck(await api.checkBend(src));
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
      <div className="space-y-2">
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="Law name" />
        <ScopeFields scope={scope} onChange={setScope} />
        <textarea rows={24} value={src} onChange={(e) => { setSrc(e.target.value); setCheck(null); }} spellCheck={false} className={cx(inputCls, 'mono h-auto py-2 text-[12px] leading-5')} />
        <div className="flex gap-2">
          <Button disabled={busy} onClick={() => run(false)}>{busy ? 'Checking…' : 'Check with Bend'}</Button>
          <Button kind="primary" disabled={busy || !check || check.validation !== 'valid'} onClick={() => run(true)} title={!check ? 'Check first' : undefined}>Save & activate</Button>
        </div>
        {err && <div className="text-[12px] text-crit">{err}</div>}
      </div>
      <div className="space-y-3 text-[12px]">
        <div className="rounded-md border border-line bg-surface p-3 text-ink-2">
          <div className="mb-1 font-medium text-ink">Contract</div>
          <ul className="list-disc space-y-1 pl-4">
            <li>Optional runtime gate: <span className="mono">def gate(c: G.Checkpoint) -&gt; G.Decision</span>, called at every checkpoint. <span className="mono">Checkpoint</span> is <span className="mono">Write&#123;resource&#125; | Retry&#123;attempts&#125; | Claim&#123;domains&#125; | Complete&#123;checks&#125;</span>.</li>
            <li>Laws about it: <span className="mono">law name: …</span> proven by <span className="mono">def name(…)</span>. You may reuse the proven core laws via <span className="mono">L.*</span>.</li>
            <li>Allowed imports: Base, governor, LAWS, PROOF. Foreign code, <span className="mono">@unsafe</span> and <span className="mono">main</span> are rejected.</li>
          </ul>
        </div>
        {check && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              <Pill tone={check.validation === 'valid' ? 'good' : 'crit'}>{check.validation}</Pill>
              <ProofBadge status={check.proofStatus} />
            </div>
            {check.validationErrors.length > 0 && <ul className="text-warn">{check.validationErrors.map((e) => <li key={e}>• {e}</li>)}</ul>}
            <pre className="mono max-h-80 overflow-auto rounded-md border border-line bg-bg p-2 text-[11px] text-ink-2">{check.proofOutput ?? ''}</pre>
            <ProofExplainer status={check.proofStatus} />
          </div>
        )}
      </div>
    </div>
  );
}

function CoreProofs() {
  const { status } = useApp();
  const [show, setShow] = useState<'none' | 'governor' | 'laws' | 'proof'>('none');
  const src = usePoll(api.sources, 0);
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<string | null>(null);
  const bend = status?.bend;
  const text = useMemo(() => (show === 'none' || !src.data ? '' : src.data[show === 'laws' ? 'laws' : show]), [show, src.data]);
  return (
    <Panel
      title="Core governor proofs"
      right={
        <>
          <Segmented value={show} onChange={setShow} options={[{ value: 'none', label: 'Summary' }, { value: 'governor', label: 'governor.bend' }, { value: 'laws', label: 'LAWS.bend' }, { value: 'proof', label: 'PROOF.bend' }]} />
          <Button small disabled={busy} onClick={async () => { setBusy(true); const r = await api.recheck(); setOut(r.proofOutput); setBusy(false); }}>{busy ? 'Checking…' : 'Re-run bend PROOF.bend'}</Button>
        </>
      }
    >
      {!bend ? (
        <Empty>Loading…</Empty>
      ) : show === 'none' ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="space-y-2">
            <div className="text-[12px] text-ink-2">
              The runtime enforces the starter laws with gate functions written in Bend (<span className="mono">governor.bend</span>), compiled to a native program with <span className="mono">bend gates.bend -o gates</span>. These properties of those exact functions are proven:
            </div>
            <ul className="space-y-1">
              {bend.laws.map((l) => (
                <li key={l.name} className="flex items-center gap-2 text-[12px]">
                  <ProofBadge status={bend.proofStatus} /> <span className="mono text-ink">{l.name}</span>
                  <span className="truncate text-muted">{l.statement.split('\n').find((x) => x.startsWith('#'))?.replace(/^#\s*/, '')}</span>
                </li>
              ))}
            </ul>
            <div className="text-[11px] text-muted">
              Not covered by proofs: the Python adapter that maps paths to resource ids, hostnames to registrable domains and checklists to booleans; the simulator. Operational state (attempt counters) lives in application code and is passed to the proven gate. Kernel re-check (<span className="mono">--verdict</span>) needs a Lean toolchain and was not run.
            </div>
          </div>
          <div className="space-y-1 text-[12px]">
            <Kv k="Bend" v={`${bend.bendVersion} (${bend.binary})`} />
            <Kv k="Source hash" v={bend.sourceHash} />
            <Kv k="Gate module built from" v={bend.moduleBuiltFromHash === bend.sourceHash ? `${bend.moduleBuiltFromHash} ✓ same sources` : `${bend.moduleBuiltFromHash} ✕ stale`} />
            <Kv k="Last check" v={`${new Date(bend.checkedAt).toLocaleTimeString()} · ${bend.checkMs}ms`} />
            <pre className="mono mt-2 rounded-md border border-[#1f4d1f] bg-bg p-2 text-[11px] text-[#a6e6a6]">$ bend PROOF.bend{'\n'}{out ?? bend.proofOutput}</pre>
          </div>
        </div>
      ) : (
        <pre className="mono max-h-[520px] overflow-auto rounded-md border border-line bg-bg p-3 text-[11px] leading-5 text-ink-2">{text}</pre>
      )}
    </Panel>
  );
}

function Kv({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line/60 py-1">
      <span className="text-muted">{k}</span>
      <span className="mono truncate text-right text-ink-2">{v}</span>
    </div>
  );
}
