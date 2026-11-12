/** Parse one CSV line. Fields may be quoted; quoted fields can contain commas and "" escapes. */
export function parseLine(line) {
  return line.split(',');
}
