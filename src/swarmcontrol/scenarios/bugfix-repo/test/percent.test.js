import { test } from 'node:test';
import assert from 'node:assert/strict';
import { percent } from '../src/percent.js';

test('half', () => assert.equal(percent(1, 2), 50));
test('rounds to one decimal', () => assert.equal(percent(1, 3), 33.3));
test('zero denominator gives 0', () => assert.equal(percent(5, 0), 0));
test('zero numerator', () => assert.equal(percent(0, 4), 0));
