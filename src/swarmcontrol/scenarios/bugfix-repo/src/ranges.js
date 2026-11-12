/** Half-open ranges [start, end): do they overlap? Touching ranges do not. */
export function overlaps(a, b) {
  return a.start <= b.end && b.start <= a.end;
}
