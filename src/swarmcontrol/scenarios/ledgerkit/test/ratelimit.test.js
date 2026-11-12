import { test } from 'node:test';
import assert from 'node:assert/strict';
import { TokenBucket } from '../src/ratelimit.js';

const clock = () => { let t = 0; const f = () => t; f.adv = (ms) => (t += ms); return f; };
test('starts full', () => { const c = clock(); const b = new TokenBucket(2, 1, c); assert.equal(b.take(), true); assert.equal(b.take(), true); assert.equal(b.take(), false); });
test('refills fractionally', () => { const c = clock(); const b = new TokenBucket(1, 2, c); b.take(); c.adv(500); assert.equal(b.take(), true); });
test('never exceeds capacity', () => { const c = clock(); const b = new TokenBucket(2, 1, c); c.adv(60000); assert.equal(b.take(2), true); assert.equal(b.take(), false); });
test('partial refill is kept between calls', () => { const c = clock(); const b = new TokenBucket(1, 1, c); b.take(); c.adv(600); assert.equal(b.take(), false); c.adv(600); assert.equal(b.take(), true); });
