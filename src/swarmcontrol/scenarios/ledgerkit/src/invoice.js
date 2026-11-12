import { toCents } from './util/money.js';

/**
 * Invoice total in cents. Accounting policy: the coupon `discount` (dollars) is
 * subtracted from the subtotal BEFORE tax, and tax is rounded to the cent with
 * banker's rounding (half to even).
 */
export function invoiceTotal(lines, { discount = 0, taxRate = 0 } = {}) {
  const subtotal = lines.reduce((s, l) => s + l.qty * l.unitPrice, 0);
  const tax = toCents(subtotal * taxRate) / 100;
  return toCents(subtotal + tax - discount);
}
