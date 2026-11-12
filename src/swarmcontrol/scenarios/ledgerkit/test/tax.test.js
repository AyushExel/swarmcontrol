import { test } from 'node:test';
import assert from 'node:assert/strict';
import { bracketTax } from '../src/tax.js';

const B = [{ upTo: 10000, rate: 0.1 }, { upTo: 40000, rate: 0.2 }, { upTo: Infinity, rate: 0.3 }];
test('inside the first bracket', () => assert.equal(bracketTax(5000, B), 50000));
test('spans two brackets', () => assert.equal(bracketTax(25000, B), 400000));
test('spans three brackets', () => assert.equal(bracketTax(50000, B), 1000000));
test('rounds half up at the cent', () => assert.equal(bracketTax(0.25, [{ upTo: Infinity, rate: 0.1 }]), 3));
