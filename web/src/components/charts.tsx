import { useMemo, useRef, useState } from 'react';
import { downsample, type HealthPoint } from '../shared/metrics';
import { fmtVt } from './ui';

const C = { good: '#0ca30c', warn: '#fab219', crit: '#d03b3b', queued: '#3a3a36', grid: '#2c2c29', axis: '#8f8e85', surface: '#161615' };

/** Stacked area: agents by health over (simulated) time, with a crosshair tooltip. */
export function HealthArea({ points, total, height = 180, real = false }: { points: HealthPoint[]; total: number; height?: number; real?: boolean }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 640;
  const H = height;
  const pad = { l: 32, r: 8, t: 8, b: 22 };
  const data = useMemo(() => downsample(points, 200), [points]);
  const maxT = Math.max(1, data[data.length - 1]?.vt ?? 1);
  const maxY = Math.max(1, total);
  const x = (t: number) => pad.l + (t / maxT) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / maxY) * (H - pad.t - pad.b);

  const layers = useMemo(() => {
    // stacking order bottom->top: green, yellow, red, queued
    const keys = ['green', 'yellow', 'red', 'queued'] as const;
    const color = { green: C.good, yellow: C.warn, red: C.crit, queued: C.queued };
    return keys.map((k, i) => {
      const lo = (p: HealthPoint) => keys.slice(0, i).reduce((s, kk) => s + p[kk], 0);
      const hi = (p: HealthPoint) => lo(p) + p[k];
      if (!data.length) return { k, d: '', color: color[k] };
      // step-after curve: counts change at events
      let top = `M${x(data[0].vt)},${y(hi(data[0]))}`;
      for (let j = 1; j < data.length; j++) top += `H${x(data[j].vt)}V${y(hi(data[j]))}`;
      top += `H${x(maxT)}`;
      let bot = `V${y(lo(data[data.length - 1]))}`;
      for (let j = data.length - 1; j >= 1; j--) bot += `H${x(data[j].vt)}V${y(lo(data[j - 1]))}`;
      bot += `H${x(data[0].vt)}Z`;
      return { k, d: top + bot, color: color[k] };
    });
  }, [data, maxT, maxY]);

  const ticks = [0, Math.round(maxY / 2), maxY];
  const hp = hover !== null ? data[hover] : null;

  function onMove(e: React.MouseEvent) {
    const svg = ref.current;
    if (!svg || !data.length) return;
    const r = svg.getBoundingClientRect();
    const t = ((e.clientX - r.left) / r.width) * W;
    const vt = ((t - pad.l) / (W - pad.l - pad.r)) * maxT;
    let idx = 0;
    for (let j = 0; j < data.length; j++) if (data[j].vt <= vt) idx = j;
    setHover(idx);
  }

  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="block w-full" style={{ height }} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="Agents by health over time">
        {ticks.map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke={C.grid} strokeWidth={1} />
            <text x={pad.l - 6} y={y(v) + 3} textAnchor="end" fontSize={10} fill={C.axis} className="tnum">
              {v}
            </text>
          </g>
        ))}
        {layers.map((l) => (
          <path key={l.k} d={l.d} fill={l.color} fillOpacity={l.k === 'queued' ? 0.5 : 0.85} stroke={C.surface} strokeWidth={1} />
        ))}
        <text x={pad.l} y={H - 6} fontSize={10} fill={C.axis}>0s</text>
        <text x={W - pad.r} y={H - 6} fontSize={10} fill={C.axis} textAnchor="end">{fmtVt(maxT)} {real ? 'elapsed' : 'simulated'}</text>
        {hp && <line x1={x(hp.vt)} x2={x(hp.vt)} y1={pad.t} y2={H - pad.b} stroke="#f0efec" strokeOpacity={0.6} strokeWidth={1} />}
      </svg>
      {hp && (
        <div className="pointer-events-none absolute top-1 right-2 rounded-md border border-line-strong bg-raised px-2.5 py-1.5 text-[11px] shadow-lg">
          <div className="mb-0.5 text-muted">t = {fmtVt(hp.vt)}</div>
          <div className="grid grid-cols-[auto_auto] gap-x-3 tnum">
            <span className="text-ink-2"><span className="text-good">●</span> Healthy</span><span className="text-right">{hp.green}</span>
            <span className="text-ink-2"><span className="text-warn">◐</span> Recovering</span><span className="text-right">{hp.yellow}</span>
            <span className="text-ink-2"><span className="text-crit">■</span> Intervention</span><span className="text-right">{hp.red}</span>
            <span className="text-ink-2"><span className="text-muted">○</span> Queued</span><span className="text-right">{hp.queued}</span>
          </div>
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-4 text-[11px] text-ink-2">
        <span><span className="text-good">●</span> Healthy</span>
        <span><span className="text-warn">◐</span> Recovering</span>
        <span><span className="text-crit">■</span> Intervention required</span>
        <span><span className="text-muted">○</span> Queued</span>
      </div>
    </div>
  );
}

export interface CompareRow {
  label: string;
  baseline: number;
  governed: number;
  denom?: string;
  fmt?: (n: number) => string;
  better?: 'higher' | 'lower' | 'neutral';
}

/** Paired horizontal bars, baseline vs governed, each row on its own scale. */
export function CompareBars({ rows }: { rows: CompareRow[] }) {
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex gap-4 text-[11px] text-ink-2">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2 w-3 rounded-sm bg-base" /> Baseline (no governor)</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2 w-3 rounded-sm bg-gov" /> Governed</span>
      </div>
      {rows.map((r) => {
        const max = Math.max(r.baseline, r.governed, 1e-9);
        const f = r.fmt ?? ((n: number) => n.toLocaleString());
        return (
          <div key={r.label} onMouseEnter={() => setHover(r.label)} onMouseLeave={() => setHover(null)} className="rounded px-1 py-0.5 hover:bg-raised/60">
            <div className="mb-1 flex items-baseline justify-between gap-2 text-[12px]">
              <span className="text-ink-2">{r.label}</span>
              {r.denom && <span className="text-[10px] text-muted">{hover === r.label ? r.denom : ''}</span>}
            </div>
            {(['baseline', 'governed'] as const).map((k) => (
              <div key={k} className="flex items-center gap-2">
                <div className="h-[10px] flex-1">
                  <div className={k === 'baseline' ? 'h-full rounded-r-[4px] bg-base' : 'h-full rounded-r-[4px] bg-gov'} style={{ width: `${(r[k] / max) * 100}%`, minWidth: r[k] > 0 ? 2 : 0 }} />
                </div>
                <span className="w-16 text-right text-[12px] tnum text-ink">{f(r[k])}</span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
