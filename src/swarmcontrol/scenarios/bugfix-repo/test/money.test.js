import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatCents } from '../src/money.js';

test('formats thousands', () => assert.equal(formatCents(123456), '$1,234.56'));
test('formats zero', () => assert.equal(formatCents(0), '$0.00'));
test('puts the minus sign before the dollar sign', () => assert.equal(formatCents(-500), '-$5.00'));
test('negative thousands', () => assert.equal(formatCents(-123456), '-$1,234.56'));
