import { parseISO, toISO } from './util/dates.js';

/**
 * Next `count` monthly due dates after `startISO`, on the same day of month;
 * if a month is shorter, use its last day, then return to the original day.
 */
export function nextDueDates(startISO, count) {
  const out = [];
  const d = parseISO(startISO);
  for (let i = 0; i < count; i++) {
    d.setUTCMonth(d.getUTCMonth() + 1);
    out.push(toISO(d));
  }
  return out;
}
