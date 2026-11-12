import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isValidEmail } from '../src/email.js';

test('accepts a plain address', () => assert.equal(isValidEmail('jane@example.com'), true));
test('accepts plus addressing', () => assert.equal(isValidEmail('jane+news@example.com'), true));
test('rejects a missing domain', () => assert.equal(isValidEmail('jane@'), false));
test('rejects spaces', () => assert.equal(isValidEmail('ja ne@example.com'), false));
