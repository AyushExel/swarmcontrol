import { test } from 'node:test';
import assert from 'node:assert/strict';
import { encodeCursor, decodeCursor } from '../src/cursor.js';

test('round trip', () => assert.deepEqual(decodeCursor(encodeCursor({ id: 7, ts: 1 })), { id: 7, ts: 1 }));
test('is URL safe', () => assert.match(encodeCursor({ id: '>>>???', ts: 1 }), /^[A-Za-z0-9_-]+$/));
test('garbage decodes to null', () => assert.equal(decodeCursor('%%%not-a-cursor'), null));
test('missing fields decode to null', () => assert.equal(decodeCursor(Buffer.from('{"id":1}').toString('base64url')), null));
