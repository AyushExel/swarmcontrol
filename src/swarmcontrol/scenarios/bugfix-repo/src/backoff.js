/** Delay before retry `attempt` (0-based): base * 2^attempt, capped at max. */
export function backoff(attempt, base = 100, max = 5000) {
  return base * 2 ** (attempt + 1);
}
