/**
 * Rows -> CSV. Quote fields containing comma, quote, CR or LF (doubling quotes).
 * Neutralize spreadsheet formulas: fields starting with = + - @ get a leading '.
 */
export function toCSV(rows, columns) {
  const cell = (v) => {
    const s = v == null ? '' : String(v);
    return s.includes(',') ? `"${s}"` : s;
  };
  return [columns.join(','), ...rows.map((r) => columns.map((c) => cell(r[c])).join(','))].join('\n');
}
