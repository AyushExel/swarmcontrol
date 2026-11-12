/**
 * Token bucket. Starts full; refills continuously at refillPerSec (fractional
 * tokens allowed), never above capacity. now() returns milliseconds.
 */
export class TokenBucket {
  constructor(capacity, refillPerSec, now = Date.now) {
    this.capacity = capacity;
    this.rate = refillPerSec;
    this.now = now;
    this.tokens = capacity;
    this.last = now();
  }
  take(n = 1) {
    const t = this.now();
    this.tokens += Math.floor((t - this.last) / 1000) * this.rate;
    this.last = t;
    if (this.tokens < n) return false;
    this.tokens -= n;
    return true;
  }
}
