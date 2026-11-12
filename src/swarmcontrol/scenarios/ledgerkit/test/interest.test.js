import { test } from 'node:test';
import assert from 'node:assert/strict';
import { accruedInterest } from '../src/interest.js';

test('one full non-leap year', () => assert.equal(accruedInterest(100000, 0.05, '2025-01-01', '2026-01-01'), 5000));
test('one full leap year', () => assert.equal(accruedInterest(100000, 0.05, '2028-01-01', '2029-01-01'), 5000));
test('zero days', () => assert.equal(accruedInterest(100000, 0.05, '2026-03-01', '2026-03-01'), 0));
test('spans a year boundary into a leap year', () => assert.equal(accruedInterest(3660000, 0.1, '2027-12-31', '2028-01-02'), 2003));
