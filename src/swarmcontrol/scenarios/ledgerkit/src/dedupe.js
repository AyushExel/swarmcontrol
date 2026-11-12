/**
 * Drop duplicate transactions: same merchant and amount within `windowMs` of the
 * last KEPT transaction of that kind. Input may be unsorted; keep the earliest;
 * return in time order; never mutate the input.
 */
export function dedupe(txns, windowMs) {
  txns.sort((a, b) => a.ts - b.ts);
  return txns.filter((t, i) => i === 0 || !(t.merchant === txns[i - 1].merchant && t.amount === txns[i - 1].amount && t.ts - txns[i - 1].ts <= windowMs));
}
