import { test } from 'node:test';
import assert from 'node:assert/strict';
import { total } from '../src/cart.js';

test('applies a percentage discount', () => {
  assert.equal(total([{ price: 2000, qty: 2 }, { price: 1000, qty: 1 }], 10), 4500);
});

test('no discount', () => {
  assert.equal(total([{ price: 999, qty: 3 }]), 2997);
});
