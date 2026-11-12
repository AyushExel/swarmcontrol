// Cart total in cents, with an optional percentage discount code.
export function total(items, discountPct = 0) {
  const subtotal = items.reduce((s, i) => s + i.price * i.qty, 0);
  return Math.round(subtotal - discountPct); // cents
}
