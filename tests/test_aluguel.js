const { aluguelSim } = require('../aluguel.js'); const assert = require('assert');
// 1000 ações × R$ 10 × 12% a.a. → R$ 100/mês bruto; corretora 10% → 10; IR 15% de 90 → 13,50
let r = aluguelSim([{ t: 'X', q: 1000, add: 0, p: 10, rate: 12, prazo: 1 }], { fee: 10, desc: true, months: 3 });
assert.strictEqual(Math.round(r.rows[0].rec * 100) / 100, 100); assert.strictEqual(Math.round(r.rows[0].dsc * 100) / 100, 23.5); assert.strictEqual(Math.round(r.rows[2].acc * 100) / 100, 229.5);
// prazo 3 meses: paga só no mês 3 o acumulado; adições mensais e retirada extraordinária
r = aluguelSim([{ t: 'X', q: 1000, add: 100, p: 10, rate: 12, prazo: 3 }], { fee: 0, desc: false, months: 3, ex: [{ m: 3, t: 'X', q: -200 }] });
assert.strictEqual(r.rows[1].rec, 0); assert.strictEqual(Math.round(r.rows[2].rec * 100) / 100, 100 + 110 + 100); assert.strictEqual(r.per[0][2].sh, 1000);
console.log('test_aluguel ok');
{ const { aluguelSim } = require('../aluguel.js'); const r = aluguelSim([{ t: 'X', q: 1000, add: 10, rate: 12, prazo: 1, p: 30, nl: 25 }], { fee: 0.5, desc: true, months: 2 });
  if (Math.abs(r.rows[0].rec - 225) > 1e-9 || r.rows[0].ql !== 750 || r.rows[1].q !== 1010) throw new Error('nl falhou'); console.log('nl ok'); }
