import { test } from 'node:test';
import assert from 'node:assert/strict';
import { nextBudget } from '../src/budget.js';

test('small underspend rolls over in full', () => assert.equal(nextBudget(1000, 900, 50), 1100));
test('rollover is capped', () => assert.equal(nextBudget(1000, 100, 50), 1500));
test('overspend is deducted in full', () => assert.equal(nextBudget(1000, 1800, 50), 200));
test('exact spend', () => assert.equal(nextBudget(1000, 1000, 50), 1000));
