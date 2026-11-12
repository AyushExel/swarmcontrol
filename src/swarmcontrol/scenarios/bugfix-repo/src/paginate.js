/** Return page `page` (1-based) of `items`, `size` items per page. */
export function paginate(items, page, size) {
  const start = page * size;
  return items.slice(start, start + size);
}

export function totalPages(count, size) {
  return Math.max(1, Math.ceil(count / size));
}
