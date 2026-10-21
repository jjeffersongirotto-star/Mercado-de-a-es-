// Indicadores criados (indicadores.js): fórmula com indicadores pelo nome, substituir/adicionar e quadro dos criados
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const store = {}, ctx = { window: {}, console, Math, Number, JSON, String, Object, Array, Set, Date, parseFloat, isNaN,
  localStorage: { getItem: (k) => store[k] || null, setItem: (k, v) => { store[k] = v; } }, document: { addEventListener() { }, getElementById: () => null },
  norm: (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(), esc: (s) => String(s ?? ''), F2: { format: (x) => String(x) },
  fmt: (v) => String(v), uiAlert() { }, uiToast() { }, state: { source: 'all', rows: [], filtered: [] } };
ctx.window = ctx; vm.createContext(ctx);
const fields = [{ key: 'pvp', label: 'P/VP', short: 'P/VP', sort: 1 }, { key: 'roe', label: 'ROE', unit: '%', sort: 2 }, { key: 'dlebitda', label: 'Dív. líq./EBITDA', sort: 3 }];
const row = { ticker: 'AAA3', v: { pvp: 2, roe: 15, dlebitda: 1.5 } };
ctx.val0 = (r, k) => r.v[k] ?? null;
store['screenerB3.indicadores.v1'] = JSON.stringify([
  { id: 'a', n: 'Meu', f: '(p/vp /2) *3', m: 'novo', d: 'high', u: '' },
  { id: 'b', n: 'ROE novo', f: '[ROE] * 2 + [Dív. líq./EBITDA]', m: 'sub', k: 'roe', d: 'high', u: '%' },
  { id: 'c', n: 'Separado', f: 'Meu ^ 2 - -1', m: 'sep', d: 'low', u: '' }]);
vm.runInContext(fs.readFileSync(__dirname + '/../indicadores.js', 'utf8'), ctx);
const CI = ctx.CI, F = CI.fields(fields);
assert.ok(F.some(f => f.key === 'ci_a' && f.sort === 4) && F.find(f => f.key === 'roe').ci === 'b');  // novo vai para Ordenar; substituto marca o original
assert.strictEqual(CI.calc(row, CI.of('ci_a')), 3);  // (2/2)*3
assert.strictEqual(CI.calc(row, CI.of('roe')), 31.5);  // usa o ROE original (15*2+1,5), não ele mesmo
assert.strictEqual(CI.calc({ ticker: 'B', v: { pvp: 4 } }, { id: 'c', f: 'Meu ^ 2 - -1' }), 37);  // usa outro criado: 6² + 1
assert.strictEqual(CI.calc({ ticker: 'C', v: { pvp: 2 } }, { id: 'z', f: 'P/VP / 0' }), null);  // divisão por zero: sem valor
const h = CI.cardHtml(row); assert.ok(/Separado/.test(h) && /criado/.test(h) && /original/.test(h) && /ROE/.test(h));
assert.throws(() => CI.parse('(P/VP'), /parêntese/); assert.throws(() => CI.parse('xyz + 1'), /Não entendi/);
console.log('test_indicadores ok');
