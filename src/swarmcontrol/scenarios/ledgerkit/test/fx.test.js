import { test } from 'node:test';
import assert from 'node:assert/strict';
import { convert } from '../src/fx.js';

const R = { USD: 1, EUR: 0.8, JPY: 150, KWD: 0.3, GBP: 0.75 };
test('same currency', () => assert.equal(convert(10, 'USD', 'USD', R), 10));
test('EUR to USD', () => assert.equal(convert(8, 'EUR', 'USD', R), 10));
test('USD to JPY rounds to whole yen', () => assert.equal(convert(1.234, 'USD', 'JPY', R), 185));
test('GBP to KWD rounds to 3 decimals', () => assert.equal(convert(1, 'GBP', 'KWD', R), 0.4));
