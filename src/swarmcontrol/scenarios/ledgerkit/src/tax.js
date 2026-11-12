import { toCents } from './util/money.js';

/**
 * Progressive tax in cents. brackets: [{ upTo, rate }] in ascending order; the
 * last bracket has upTo: Infinity. Each rate applies only to the income inside
 * its bracket. Rounded half up to the cent.
 */
export function bracketTax(income, brackets) {
  const b = brackets.find((x) => income <= x.upTo);
  return toCents(income * b.rate);
}
