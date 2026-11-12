import { test } from 'node:test';
import assert from 'node:assert/strict';
import { slugify } from '../src/slugify.js';

test('lowercases words', () => assert.equal(slugify('hello'), 'hello'));
test('collapses punctuation and spaces into one dash', () => assert.equal(slugify('Hello, World!'), 'hello-world'));
test('trims leading and trailing dashes', () => assert.equal(slugify('  Agents & Swarms  '), 'agents-swarms'));
test('keeps digits', () => assert.equal(slugify('v2'), 'v2'));
