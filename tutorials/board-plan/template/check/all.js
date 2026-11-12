// The whole plan. Run: node check/all.js
const fs = require('fs');
const { execFileSync } = require('child_process');
const rows = (f) => fs.readFileSync(f, 'utf8').trim().split('\n').slice(1).map((l) => l.split(','));
const problems = [];
try { execFileSync(process.execPath, ['check/section.js'], { stdio: 'pipe' }); } catch (e) { problems.push(String(e.stderr).trim()); }
const memo = fs.existsSync('memo.md') ? fs.readFileSync('memo.md', 'utf8') : '';
const city = (memo.match(/^Recommendation:\s*(\w+)/m) || [])[1];
const costs = Object.fromEntries(rows('data/costs.csv').map(([c, a, s]) => [c, Number(a) * 3 + Number(s)]));
const talent = Object.fromEntries(rows('data/talent.csv').map(([c, n]) => [c, Number(n)]));
if (!city || !(city in costs)) problems.push('memo.md must start with "Recommendation: <city>", a city in data/costs.csv');
else {
  if (costs[city] > 1500000) problems.push(`${city} costs ${costs[city]} over 3 years, above the 1500000 limit`);
  if (talent[city] < 40) problems.push(`${city} has ${talent[city]} senior engineers available; the plan needs 40`);
}
if (memo.split(/\s+/).length > 350) problems.push('memo.md must be 350 words or fewer');
if (!/^Risks:/m.test(memo)) problems.push('memo.md needs a "Risks:" section');
if (/\bTBD\b/.test(memo)) problems.push('memo.md still contains TBD');
if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
console.log('plan OK');
