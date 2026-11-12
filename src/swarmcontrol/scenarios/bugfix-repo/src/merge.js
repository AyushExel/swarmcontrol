/** Deep-merge plain objects. Arrays in `b` replace arrays in `a`. */
export function deepMerge(a, b) {
  const out = { ...a };
  for (const [k, v] of Object.entries(b)) {
    if (v && typeof v === 'object' && a[k] && typeof a[k] === 'object') out[k] = deepMerge(a[k], v);
    else out[k] = v;
  }
  return out;
}
