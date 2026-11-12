import { test } from 'node:test';
import assert from 'node:assert/strict';
import { paginate, totalPages } from '../src/paginate.js';

const items = Array.from({ length: 25 }, (_, i) => i + 1);
test('page 1 starts at the first item', () => assert.deepEqual(paginate(items, 1, 10), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]));
test('last page is partial', () => assert.deepEqual(paginate(items, 3, 10), [21, 22, 23, 24, 25]));
test('totalPages rounds up', () => assert.equal(totalPages(25, 10), 3));
test('totalPages of empty list is 1', () => assert.equal(totalPages(0, 10), 1));
