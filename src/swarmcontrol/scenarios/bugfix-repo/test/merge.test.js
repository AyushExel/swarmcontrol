import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deepMerge } from '../src/merge.js';

test('merges nested objects', () => assert.deepEqual(deepMerge({ a: { x: 1 } }, { a: { y: 2 } }), { a: { x: 1, y: 2 } }));
test('later scalars win', () => assert.deepEqual(deepMerge({ a: 1 }, { a: 2 }), { a: 2 }));
test('arrays are replaced, not merged by index', () => assert.deepEqual(deepMerge({ tags: ['a', 'b', 'c'] }, { tags: ['z'] }), { tags: ['z'] }));
test('does not mutate inputs', () => {
  const a = { n: { x: 1 } };
  deepMerge(a, { n: { y: 2 } });
  assert.deepEqual(a, { n: { x: 1 } });
});
