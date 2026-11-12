import { test } from 'node:test';
import assert from 'node:assert/strict';
import { compare } from '../src/semver.js';

test('equal versions', () => assert.equal(compare('1.2.3', '1.2.3'), 0));
test('patch ordering', () => assert.equal(compare('1.2.3', '1.2.4'), -1));
test('numeric, not lexical, minor ordering', () => assert.equal(compare('1.10.0', '1.9.0'), 1));
test('major dominates', () => assert.equal(compare('2.0.0', '10.0.0'), -1));
