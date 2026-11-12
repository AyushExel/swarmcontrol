const DAY = 86_400_000;
export const parseISO = (s) => new Date(`${s}T00:00:00Z`);
export const toISO = (d) => d.toISOString().slice(0, 10);
export const isLeap = (y) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
export const daysInYear = (y) => (isLeap(y) ? 366 : 365);
export const daysInMonth = (y, m) => new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
export const daysBetween = (a, b) => Math.round((parseISO(b) - parseISO(a)) / DAY);
