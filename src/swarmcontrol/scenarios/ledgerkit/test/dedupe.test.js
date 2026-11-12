import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dedupe } from '../src/dedupe.js';

const t = (merchant, amount, ts) => ({ merchant, amount, ts });
test('drops an immediate duplicate', () => assert.deepEqual(dedupe([t('a', 5, 0), t('a', 5, 1000)], 60000), [t('a', 5, 0)]));
test('handles interleaved merchants', () => assert.deepEqual(dedupe([t('a', 5, 0), t('b', 7, 500), t('a', 5, 1000)], 60000), [t('a', 5, 0), t('b', 7, 500)]));
test('does not mutate the input', () => { const x = [t('a', 5, 9), t('a', 5, 1)]; dedupe(x, 10); assert.deepEqual(x, [t('a', 5, 9), t('a', 5, 1)]); });
test('window is measured from the kept transaction', () => assert.deepEqual(dedupe([t('a', 5, 0), t('a', 5, 40), t('a', 5, 80)], 50), [t('a', 5, 0), t('a', 5, 80)]));
