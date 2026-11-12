import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toCSV } from '../src/csvexport.js';

test('plain values', () => assert.equal(toCSV([{ a: 1, b: 'x' }], ['a', 'b']), 'a,b\n1,x'));
test('quotes commas and doubles quotes', () => assert.equal(toCSV([{ a: 'say "hi", ok' }], ['a']), 'a\n"say ""hi"", ok"'));
test('quotes newlines', () => assert.equal(toCSV([{ a: 'l1\nl2' }], ['a']), 'a\n"l1\nl2"'));
test('neutralizes formulas', () => assert.equal(toCSV([{ a: '=SUM(A1)' }, { a: '-5' }], ['a']), "a\n'=SUM(A1)\n'-5"));
