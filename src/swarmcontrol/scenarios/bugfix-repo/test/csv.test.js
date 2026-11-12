import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseLine } from '../src/csv.js';

test('splits plain fields', () => assert.deepEqual(parseLine('a,b,c'), ['a', 'b', 'c']));
test('keeps commas inside quotes', () => assert.deepEqual(parseLine('1,"Smith, Jane",NYC'), ['1', 'Smith, Jane', 'NYC']));
test('unescapes doubled quotes', () => assert.deepEqual(parseLine('"say ""hi""",x'), ['say "hi"', 'x']));
test('keeps empty fields', () => assert.deepEqual(parseLine('a,,c'), ['a', '', 'c']));
