/** Opaque pagination cursor: URL-safe base64 of JSON { id, ts }. */
export function encodeCursor(c) {
  return Buffer.from(JSON.stringify(c)).toString('base64');
}

/** Decode a cursor; return null for anything malformed or missing fields. */
export function decodeCursor(s) {
  return JSON.parse(Buffer.from(s, 'base64').toString('utf8'));
}
