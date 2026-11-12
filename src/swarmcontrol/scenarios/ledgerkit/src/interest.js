import { daysBetween } from './util/dates.js';

/**
 * Simple daily interest (cents) on `principalCents` from fromISO (inclusive) to
 * toISO (exclusive), actual/actual: each day accrues annualRate / days-in-that-
 * year. Round half up at the end.
 */
export function accruedInterest(principalCents, annualRate, fromISO, toISO) {
  const days = daysBetween(fromISO, toISO) + 1;
  return Math.round((principalCents * annualRate * days) / 365);
}
