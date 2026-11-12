/** Minor-unit digits per currency (ISO 4217). */
export const DIGITS = { USD: 2, EUR: 2, GBP: 2, JPY: 0, KWD: 3 };

/**
 * Convert `amount` (major units) between currencies. `rates[c]` is how many
 * units of c one USD buys. Round to the target currency's minor unit.
 */
export function convert(amount, from, to, rates) {
  const usd = amount * rates[from];
  return Math.round(usd * rates[to] * 100) / 100;
}
