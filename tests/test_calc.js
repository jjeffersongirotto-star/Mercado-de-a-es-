global.window = {}; global.document = undefined;
const { avgLastMonths } = require('../ui.js');
const assert = require('assert');
const day = (s) => Date.parse(s + 'T13:00:00Z') / 1000;
// 10/09 → 1 mês = pregões após 10/08
const t = [day('2026-08-09'), day('2026-08-10'), day('2026-08-11'), day('2026-09-01'), day('2026-09-10')];
const c = [100, 1, 2, 3, 4];
assert.strictEqual(avgLastMonths(t, c, 1), (2 + 3 + 4) / 3);
assert.strictEqual(avgLastMonths(t, c, 2), (100 + 1 + 2 + 3 + 4) / 5);
// fim de mês: 31/03 menos 1 mês → 28/02
const t2 = [day('2026-02-27'), day('2026-02-28'), day('2026-03-02'), day('2026-03-31')];
assert.strictEqual(avgLastMonths(t2, [9, 9, 1, 3], 1), 2);
console.log('test_calc ok');
