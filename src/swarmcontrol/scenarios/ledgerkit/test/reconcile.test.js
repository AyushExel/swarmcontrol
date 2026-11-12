import { test } from 'node:test';
import assert from 'node:assert/strict';
import { reconcile } from '../src/reconcile.js';

test('exact single match', () => assert.deepEqual(reconcile([{ id: 'b1', amount: 10 }], [{ id: 'l1', amount: 10 }], 0), [{ bank: 'b1', ledger: 'l1' }]));
test('a ledger entry is used once', () => assert.deepEqual(reconcile([{ id: 'b1', amount: 10 }, { id: 'b2', amount: 10 }], [{ id: 'l1', amount: 10 }], 0), [{ bank: 'b1', ledger: 'l1' }]));
test('prefers the exact match over an earlier near match', () => assert.deepEqual(reconcile([{ id: 'b1', amount: 10 }], [{ id: 'l1', amount: 10.5 }, { id: 'l2', amount: 10 }], 1), [{ bank: 'b1', ledger: 'l2' }]));
test('prefers the closest', () => assert.deepEqual(reconcile([{ id: 'b1', amount: 10 }], [{ id: 'l1', amount: 10.9 }, { id: 'l2', amount: 9.8 }], 1), [{ bank: 'b1', ledger: 'l2' }]));
