/** Dollars -> integer cents, rounding half up (company default). */
export function toCents(dollars) {
  return Math.round(dollars * 100 + 1e-9);
}

/** Round to cents using banker's rounding (half to even). */
export function toCentsHalfEven(dollars) {
  const x = dollars * 100;
  const f = Math.floor(x);
  const d = x - f;
  if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
  return Math.round(x);
}
