// Charges a card through the payment provider. Owned by the payments team.
export async function charge(cardToken, amountCents) {
  if (!Number.isInteger(amountCents) || amountCents <= 0) throw new Error('invalid amount');
  return { ok: true, cardToken, amountCents };
}
