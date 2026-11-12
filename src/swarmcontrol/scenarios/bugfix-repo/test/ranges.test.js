import { test } from 'node:test';
import assert from 'node:assert/strict';
import { overlaps } from '../src/ranges.js';

test('overlapping ranges', () => assert.equal(overlaps({ start: 1, end: 5 }, { start: 3, end: 8 }), true));
test('disjoint ranges', () => assert.equal(overlaps({ start: 1, end: 2 }, { start: 5, end: 8 }), false));
test('touching ranges do not overlap', () => assert.equal(overlaps({ start: 1, end: 5 }, { start: 5, end: 9 }), false));
test('containment overlaps', () => assert.equal(overlaps({ start: 0, end: 10 }, { start: 2, end: 3 }), true));
