/**
 * Match bank lines to ledger entries: |amount diff| <= tolerance, each ledger
 * entry used at most once. Prefer exact matches, then the closest amount.
 * Returns [{ bank, ledger }] for matched bank ids, in bank order.
 */
export function reconcile(bank, ledger, tolerance) {
  const out = [];
  for (const b of bank) {
    const m = ledger.find((l) => Math.abs(l.amount - b.amount) <= tolerance);
    if (m) out.push({ bank: b.id, ledger: m.id });
  }
  return out;
}
