// node tests/test_previsao.js — % Aporte + % Valorização + % Dividendos = 100%
const assert = require('assert');
const { pvPcts } = require('../previsao.js');
const cases = [[60000, 126436.67, 171901.09], [100, 80, 95], [1000, 1000, 1000], [5000, 4000, 3000], [0, 10, 12]];
for (const [a, s, c] of cases) { const p = pvPcts(a, s, c); assert(Math.abs(p.pa + p.pv + p.pd - 1) < 1e-12, JSON.stringify([a, s, c, p])); }
assert.deepStrictEqual(pvPcts(100, 0, 0), { va: -1, pa: null, pv: null, pd: null });
assert(Math.abs(pvPcts(60000, 126436.67, 171901.09).va - (171901.09 - 60000) / 60000) < 1e-12);
console.log('ok: test_previsao');
