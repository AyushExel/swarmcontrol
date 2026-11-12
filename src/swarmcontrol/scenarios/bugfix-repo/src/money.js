/** Format integer cents as US dollars, e.g. 123456 -> "$1,234.56", -500 -> "-$5.00". */
export function formatCents(cents) {
  const dollars = (cents / 100).toFixed(2);
  const [whole, frac] = dollars.split('.');
  return '$' + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + frac;
}
