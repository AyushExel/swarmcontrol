import { test } from 'node:test';
import assert from 'node:assert/strict';
import { invoiceTotal } from '../src/invoice.js';

test('no tax, no discount', () => assert.equal(invoiceTotal([{ qty: 2, unitPrice: 9.99 }]), 1998));
test('discount applies before tax', () => assert.equal(invoiceTotal([{ qty: 1, unitPrice: 200 }], { discount: 20, taxRate: 0.08 }), 19440));
test('tax uses banker\'s rounding (half to even)', () => assert.equal(invoiceTotal([{ qty: 1, unitPrice: 0.5 }], { taxRate: 0.05 }), 52));
test('multiple lines', () => assert.equal(invoiceTotal([{ qty: 3, unitPrice: 4.5 }, { qty: 1, unitPrice: 6 }], { taxRate: 0.1 }), 2145));
