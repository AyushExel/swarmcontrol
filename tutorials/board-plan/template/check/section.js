// Every section that exists must be complete. Run: node check/section.js
const fs = require('fs');
const rows = (f) => fs.readFileSync(f, 'utf8').trim().split('\n').slice(1).map((l) => l.split(','));
const problems = [];
for (const [city, annual, setup] of rows('data/costs.csv')) {
  const f = `sections/${city.toLowerCase()}.md`;
  if (!fs.existsSync(f)) problems.push(`${f} is missing`);
  else if (new Set(fs.readFileSync(f, 'utf8').match(/https?:\/\/[^\s)\]]+/g) || []).size < 3) problems.push(`${f} needs at least 3 source URLs`);
  const total = String(Number(annual) * 3 + Number(setup));
  const fin = fs.existsSync('sections/finance.md') ? fs.readFileSync('sections/finance.md', 'utf8') : '';
  if (!fin) { if (!problems.includes('sections/finance.md is missing')) problems.push('sections/finance.md is missing'); }
  else if (!new RegExp(`${city}\\D[^\\n]*${total}`).test(fin.replace(/(\d),(\d)/g, '$1$2'))) problems.push(`sections/finance.md needs a row for ${city} with its 3-year total ${total} (annual x 3 + setup)`);
}
if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
console.log('sections OK');
