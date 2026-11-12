/**
 * Next month's budget. Unspent money rolls over, capped at capPct% of this
 * month's budget. Overspending is deducted in full from next month.
 */
export function nextBudget(base, spent, capPct) {
  const left = base - spent;
  const cap = (base * capPct) / 100;
  return base + Math.min(Math.abs(left), cap);
}
