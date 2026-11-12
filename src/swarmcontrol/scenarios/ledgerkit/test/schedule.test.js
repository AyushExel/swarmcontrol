import { test } from 'node:test';
import assert from 'node:assert/strict';
import { nextDueDates } from '../src/schedule.js';

test('mid-month dates', () => assert.deepEqual(nextDueDates('2026-01-15', 3), ['2026-02-15', '2026-03-15', '2026-04-15']));
test('clamps to the end of short months', () => assert.deepEqual(nextDueDates('2026-01-31', 2), ['2026-02-28', '2026-03-31']));
test('leap February', () => assert.deepEqual(nextDueDates('2028-01-30', 2), ['2028-02-29', '2028-03-30']));
test('crosses the year', () => assert.deepEqual(nextDueDates('2026-11-30', 3), ['2026-12-30', '2027-01-30', '2027-02-28']));
