import { test } from 'node:test';
import assert from 'node:assert/strict';
import { can } from '../src/permissions.js';

const doc = { ownerId: 'u1', locked: false };
test('viewer reads', () => assert.equal(can({ id: 'u2', role: 'viewer' }, 'read', doc), true));
test('owner may write but not delete', () => { assert.equal(can({ id: 'u1', role: 'viewer' }, 'write', doc), true); assert.equal(can({ id: 'u1', role: 'viewer' }, 'delete', doc), false); });
test('locked: owner cannot write, admin can', () => { const l = { ...doc, locked: true }; assert.equal(can({ id: 'u1', role: 'editor' }, 'write', l), false); assert.equal(can({ id: 'u9', role: 'admin' }, 'write', l), true); });
test('unknown role gets nothing', () => assert.equal(can({ id: 'u3', role: 'intern' }, 'read', doc), false));
