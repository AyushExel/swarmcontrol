/** n as a percentage of d, rounded to one decimal; 0 when d is 0. */
export function percent(n, d) {
  return Math.round((n / d) * 1000) / 10;
}
