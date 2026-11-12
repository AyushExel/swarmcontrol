import { test } from 'node:test';
import assert from 'node:assert/strict';
import { backoff } from '../src/backoff.js';

test('first retry waits the base delay', () => assert.equal(backoff(0), 100));
test('doubles each attempt', () => assert.equal(backoff(3), 800));
test('is capped', () => assert.equal(backoff(20), 5000));
test('custom base', () => assert.equal(backoff(1, 50), 100));
