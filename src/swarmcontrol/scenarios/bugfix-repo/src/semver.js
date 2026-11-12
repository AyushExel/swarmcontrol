/** Compare "major.minor.patch" versions: -1, 0 or 1. */
export function compare(a, b) {
  if (a === b) return 0;
  return a < b ? -1 : 1;
}
