import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isLeapYear } from '../src/leap.js';

test('2024 is a leap year', () => assert.equal(isLeapYear(2024), true));
test('2023 is not', () => assert.equal(isLeapYear(2023), false));
test('1900 is not (century rule)', () => assert.equal(isLeapYear(1900), false));
test('2000 is (400 rule)', () => assert.equal(isLeapYear(2000), true));
