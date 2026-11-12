import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LRUCache } from '../src/lru.js';

test('stores and reads', () => {
  const c = new LRUCache(2);
  c.set('a', 1);
  assert.equal(c.get('a'), 1);
});
test('evicts the least recently set key', () => {
  const c = new LRUCache(2);
  c.set('a', 1); c.set('b', 2); c.set('c', 3);
  assert.equal(c.get('a'), undefined);
});
test('a read refreshes recency', () => {
  const c = new LRUCache(2);
  c.set('a', 1); c.set('b', 2);
  c.get('a');
  c.set('c', 3);
  assert.equal(c.get('a'), 1);
  assert.equal(c.get('b'), undefined);
});
