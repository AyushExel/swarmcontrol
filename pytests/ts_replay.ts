// Parity helper: replays events (JSON on stdin) through the dashboard's TypeScript reducer.
import { replay } from '../web/src/shared/metrics';
let raw = '';
process.stdin.on('data', (c) => (raw += c));
process.stdin.on('end', () => {
  const runs: Record<string, unknown[]> = JSON.parse(raw);
  const out: Record<string, unknown> = {};
  for (const [id, evs] of Object.entries(runs)) {
    const s = replay(evs as never);
    out[id] = { metrics: s.metrics, timeline: s.timeline, agents: [...s.agents.values()].map((a) => ({ id: a.id, state: a.state, health: a.health, recovered: a.recovered, outcome: a.outcome })) };
  }
  process.stdout.write(JSON.stringify(out));
});
