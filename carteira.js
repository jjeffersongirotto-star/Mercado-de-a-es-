// ---------- Carteira (compras e vendas salvas no aparelho + exportar/importar .json) ----------
// Cada movimentação (compra ou venda) fica no histórico; quantidade, preço médio, lucro nas vendas e proventos são calculados dele.
// Preço atual: mesma linha de /api/data dos cards (priceOf). Proventos: /api/history (por ação, pela quantidade em cada data).
// Ibovespa e CDB: o mesmo dinheiro aplicado e retirado nas mesmas datas (/api/idxret).
(function () {
  const KEY = 'screenerB3.carteira.v2', OLD = 'screenerB3.carteira.v1';
  const $k = (s) => document.querySelector(s);
  const pane = () => $k('[data-tabpane="carteira"]');
  const valid = (m) => m && typeof m.t === 'string' && (m.op === 'c' || m.op === 'v') && m.q > 0 && m.p > 0 && /^\d{4}-\d{2}-\d{2}$/.test(m.d);
  const clean = (m) => ({ t: m.t.toUpperCase().trim(), op: m.op, q: +m.q, p: +m.p, d: m.d });
  const fromV1 = (arr) => arr.filter(x => x && typeof x.t === 'string' && x.q > 0 && x.pm > 0 && x.d).map(x => ({ t: x.t, op: 'c', q: x.q, p: x.pm, d: x.d }));
  let mov = (() => {
    try {
      const m = JSON.parse(localStorage.getItem(KEY) || 'null'); if (Array.isArray(m)) return m.filter(valid);
      const v1 = JSON.parse(localStorage.getItem(OLD) || '[]');  // v1: uma posição (preço médio) por linha -> uma compra
      return Array.isArray(v1) ? fromV1(v1).map(clean) : [];
    } catch (e) { return []; }
  })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(mov)); localStorage.removeItem(OLD); } catch (e) { uiAlert('Não foi possível salvar no navegador.'); } };
  const today = new Date().toISOString().slice(0, 10);
  const DIV = {}, IDX = {};  // cache por ticker / por data
  let editing = -1, open = new Set();

  const cls = (v) => v > 0 ? 'up' : v < 0 ? 'dn' : '';
  const money = (v) => v == null ? '—' : brl.format(v);
  const pct = (v) => v == null || !isFinite(v) ? '' : `<span class="${cls(v)}">${pc(v)}</span>`;
  const gain = (v, base) => v == null ? '—' : `<span class="${cls(v)}">${money(v)}</span> ${base ? pct(v / base * 100) : ''}`;
  // ordem cronológica; no mesmo dia, compras antes das vendas
  const chron = (L) => L.map((m, i) => [m, i]).sort((a, b) => a[0].d.localeCompare(b[0].d) || (a[0].op === 'v') - (b[0].op === 'v') || a[1] - b[1]);

  function position(L) {  // L = movimentações de uma ação; venda reduz a quantidade sem mudar o preço médio
    let q = 0, cost = 0, real = 0, bought = 0, neg = null;
    for (const [m] of chron(L)) {
      if (m.op === 'c') { q += m.q; cost += m.q * m.p; bought += m.q * m.p; }
      else { const pm = q ? cost / q : 0; if (m.q > q + 1e-9) { neg = m; break; } real += (m.p - pm) * m.q; cost -= pm * m.q; q -= m.q; }
    }
    return { q, cost, pm: q ? cost / q : null, real, bought, neg };
  }
  const provs = (t) => DIV[t] || (DIV[t] = getRetry(`/api/history/${encodeURIComponent(t)}`).then(h => (h && h.div) || []));
  const idx = (d) => IDX[d] || (IDX[d] = getRetry(`/api/idxret?di=${d}&df=${today}`).then(x => x || {}));

  async function calc(t, L) {
    const P = position(L), r = (state.rowMap || {})[t], price = r ? priceOf(r) : null;
    const C = chron(L).map(x => x[0]);
    const held = (day) => C.reduce((a, m) => m.d < day ? a + (m.op === 'c' ? m.q : -m.q) : a, 0);  // ações antes da data do provento
    const div = (await provs(t)).reduce((a, [ts, v]) => a + v * held(new Date(ts * 1000).toISOString().slice(0, 10)), 0);
    let ibov = 0, cdi = 0;  // ganho do mesmo dinheiro (compras entram, vendas saem) nos índices
    for (const m of C) {
      const ix = await idx(m.d), s = m.op === 'c' ? 1 : -1;
      ibov = ibov == null || ix['@ibov'] == null ? null : ibov + s * m.q * m.p * ix['@ibov'] / 100;
      cdi = cdi == null || ix['@cdi'] == null ? null : cdi + s * m.q * m.p * ix['@cdi'] / 100;
    }
    const cur = price != null ? P.q * price : (P.q ? null : 0);
    return { t, L, ...P, price, cur, unreal: cur != null ? cur - P.cost : null, div, ibov, cdi };
  }
  const sumK = (X, k) => X.some(x => x[k] == null) ? null : X.reduce((a, x) => a + x[k], 0);
  function total(X) {
    const o = { t: '', L: X.flatMap(x => x.L) };
    for (const k of ['cost', 'cur', 'unreal', 'real', 'div', 'bought', 'ibov', 'cdi']) o[k] = sumK(X, k);
    return o;
  }

  function cards(x) {
    const tot = x.unreal != null ? x.unreal + x.real + x.div : null;
    return `<div class="kt-sum">
      <div><span>Investido</span><b>${money(x.cost)}</b></div>
      <div><span>Valor atual</span><b>${money(x.cur)}</b></div>
      <div><span>Ganho</span><b>${gain(x.unreal, x.cost)}</b></div>
      <div><span>Lucro nas vendas</span><b>${gain(x.real)}</b></div>
      <div><span>Proventos recebidos</span><b>${money(x.div)}</b></div>
      <div><span>Total (ganho + vendas + proventos)</span><b>${gain(tot, x.bought)}</b></div>
      <div><span>Se fosse no Ibovespa</span><b>${gain(x.ibov, x.bought)}</b></div>
      <div><span>Se fosse no CDB</span><b>${gain(x.cdi, x.bought)}</b></div></div>`;
  }
  function hist(L, all) {  // all = Total da carteira (mostra a coluna Ativo)
    const rows = chron(L).reverse().map(([m]) => { const i = mov.indexOf(m); return `<tr${i === editing ? ' class="on"' : ''}>
      <td>${dataBR(m.d)}</td><td><span class="${m.op === 'c' ? 'up' : 'dn'}">${m.op === 'c' ? 'Compra' : 'Venda'}</span></td>${all ? `<td>${esc(m.t)}</td>` : ''}
      <td>${F0.format(m.q)}</td><td>${F2.format(m.p)}</td><td>${F2.format(m.q * m.p)}</td>
      <td class="kt-act"><button type="button" class="gbtn" data-k="edit" data-i="${i}" title="Editar" aria-label="Editar">✎</button><button type="button" class="gbtn dan" data-k="del" data-i="${i}" title="Excluir" aria-label="Excluir">🗑</button></td></tr>`; }).join('');
    return `<div class="kt-h"><b>Histórico de movimentações</b><div class="kt-wrap"><table class="kt-t"><thead><tr><th>Data</th><th>Tipo</th>${all ? '<th>Ativo</th>' : ''}<th>Qtd</th><th>Preço</th><th>Total R$</th><th></th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }

  function form() {
    const m = mov[editing] || { op: 'c', d: today };
    const tk = state.data ? state.data.rows.filter(r => !r.il).map(r => r.ticker).sort() : [];
    return `<form id="ktF" class="kt-f" autocomplete="off">
      <label>Ticker<input id="ktT" class="pv-in" list="ktL" required maxlength="12" value="${esc(m.t || '')}" placeholder="PETR4"></label>
      <label>Operação<select id="ktO" class="pv-in"><option value="c"${m.op === 'c' ? ' selected' : ''}>Compra</option><option value="v"${m.op === 'v' ? ' selected' : ''}>Venda</option></select></label>
      <label>Quantidade<input id="ktQ" class="pv-in" inputmode="decimal" required value="${m.q != null ? F0.format(m.q) : ''}"></label>
      <label>Preço<input id="ktP" class="pv-in" inputmode="decimal" required value="${m.p != null ? F2.format(m.p) : ''}"></label>
      <label>Data<input id="ktD" class="pv-in" type="date" required max="${today}" value="${esc(m.d)}"></label>
      <div class="kt-fb"><button type="submit" class="gbtn pri">${editing >= 0 ? 'Salvar' : '＋ Adicionar'}</button>${editing >= 0 ? '<button type="button" class="gbtn" data-k="cancel">Cancelar</button><button type="button" class="gbtn dan" data-k="del">Excluir</button>' : ''}</div>
      <datalist id="ktL">${tk.map(t => `<option value="${t}">`).join('')}</datalist></form>`;
  }

  async function render() {
    const root = $k('#carteiraRoot');
    if (state.country !== 'br') {
      root.innerHTML = `<section class="kt-box"><p>A Carteira usa as ações da B3.</p><button type="button" class="gbtn pri" data-k="br">Mudar para Brasil</button></section>`;
      return;
    }
    if (!state.data) { root.innerHTML = loaderHTML('Carregando dados…'); return; }
    const head = `<div class="flex flex-wrap items-center gap-2">
        <button type="button" class="gbtn fbtn" data-k="export" title="Exportar carteira" aria-label="Exportar carteira">${fileIc(1)}<span class="max-sm:hidden">Exportar</span></button>
        <button type="button" class="gbtn fbtn" data-k="import" title="Importar carteira" aria-label="Importar carteira">${fileIc(0)}<span class="max-sm:hidden">Importar</span></button>
        <input id="ktFile" type="file" accept=".json,application/json,text/plain,*/*" class="hidden"></div>`;
    root.innerHTML = `<section class="space-y-2">${head}<div class="kt-box">${form()}</div><div id="ktBody">${mov.length ? loaderHTML('Calculando…') : '<p class="text-slate-400 text-sm text-center">Nenhuma movimentação. Preencha ticker, operação, quantidade, preço e data e toque em ＋ Adicionar.</p>'}</div></section>`;
    $k('#ktFile').addEventListener('change', importK);
    if (mov.length) body();
  }

  async function body() {
    const by = {}; for (const m of mov) (by[m.t] = by[m.t] || []).push(m);
    const X = await Promise.all(Object.keys(by).sort().map(t => calc(t, by[t])));
    const el = $k('#ktBody'); if (!el) return;
    const T = total(X);
    const det = (k, x) => open.has(k) ? `<tr class="kt-det"><td colspan="6">${cards(x)}${hist(x.L, k === '*')}</td></tr>` : '';
    const num = (v) => v == null ? '—' : F2.format(v);  // na tabela sem "R$" (cabe no celular); nos cards com "R$"
    const gcell = (x) => x.unreal != null ? `<span class="${cls(x.unreal)}">${num(x.unreal)}</span><small>${pct(x.cost ? x.unreal / x.cost * 100 : null)}</small>` : '—';
    const row = (x) => `<tr class="kt-row${open.has(x.t) ? ' on' : ''}" data-k="open" data-t="${esc(x.t)}"><td><b>${esc(x.t)}</b></td>
        <td>${F0.format(x.q)}</td><td>${x.pm != null ? F2.format(x.pm) : '—'}</td>
        <td>${x.price != null ? F2.format(x.price) : '—'}</td>
        <td>${gcell(x)}</td><td>${num(x.div)}</td></tr>${det(x.t, x)}`;
    el.innerHTML = `<div class="kt-wrap"><table class="kt-t"><thead><tr><th>Ativo</th><th>Nº de ações</th><th>Preço médio</th><th>Cotação do dia</th><th>Ganho R$</th><th>Proventos R$</th></tr></thead><tbody>
      ${X.map(row).join('')}
      <tr class="kt-row kt-tot${open.has('*') ? ' on' : ''}" data-k="open" data-t="*"><td colspan="4"><b>Total da carteira</b></td>
        <td>${gcell(T)}</td><td>${num(T.div)}</td></tr>${det('*', T)}
      </tbody></table></div>`;
  }

  async function submit(e) {
    e.preventDefault();
    const t = $k('#ktT').value.toUpperCase().trim(), op = $k('#ktO').value, q = parseBR($k('#ktQ').value), p = parseBR($k('#ktP').value), d = $k('#ktD').value;
    if (!state.rowMap[t]) return uiAlert(`Ticker ${t} não encontrado na lista de ações.`);
    if (!(q > 0) || !(p > 0) || !d) return uiAlert('Preencha quantidade, preço e data.');
    const m = { t, op, q, p, d: d > today ? today : d };
    const next = mov.slice(); if (editing >= 0) next[editing] = m; else next.push(m);
    for (const tk of new Set([t, editing >= 0 ? mov[editing].t : t])) {
      const bad = position(next.filter(x => x.t === tk)).neg;
      if (bad) return uiAlert(`Venda de ${F0.format(bad.q)} ${tk} em ${dataBR(bad.d)} é maior que a quantidade que você tinha nessa data.`);
    }
    mov = next; editing = -1; save(); render();
  }

  async function importK(e) {
    const f = e.target.files[0]; if (!f) return;
    try {
      const d = JSON.parse(await f.text());
      const arr = Array.isArray(d.movimentacoes) ? d.movimentacoes.filter(valid).map(clean) : Array.isArray(d.carteira) ? fromV1(d.carteira).map(clean) : null;
      if (!arr) throw new Error('arquivo sem carteira');
      if (mov.length && !(await uiConfirm(`Substituir as ${mov.length} movimentações atuais pelas ${arr.length} do arquivo?`, { ok: 'Substituir', danger: true }))) { e.target.value = ''; return; }
      mov = arr; save(); render(); uiToast(arr.length + ' movimentação(ões) importada(s)');
    } catch (err) { uiAlert('Não foi possível importar: ' + err.message); }
    e.target.value = '';
  }

  pane().addEventListener('submit', (e) => { if (e.target.id === 'ktF') submit(e); });
  pane().addEventListener('click', async (e) => {
    const b = e.target.closest('[data-k]'); if (!b) return;
    const k = b.dataset.k, i = b.dataset.i != null ? +b.dataset.i : editing;
    if (k === 'export') saveJSON({ app: 'screener-b3', tipo: 'carteira', versao: 2, exportado: new Date().toISOString(), movimentacoes: mov }, 'carteira-screener');
    else if (k === 'import') $k('#ktFile').click();
    else if (k === 'open') { const t = b.dataset.t; if (open.has(t)) open.delete(t); else open.add(t); body(); }
    else if (k === 'edit') { editing = i; render(); $k('#carteiraRoot').scrollIntoView({ block: 'start', behavior: 'smooth' }); }
    else if (k === 'cancel') { editing = -1; render(); }
    else if (k === 'del') {
      const m = mov[i]; if (!m || !(await uiConfirm(`Excluir a ${m.op === 'c' ? 'compra' : 'venda'} de ${F0.format(m.q)} ${m.t} em ${dataBR(m.d)}?`, { ok: 'Excluir', danger: true }))) return;
      const next = mov.filter((_, j) => j !== i), bad = position(next.filter(x => x.t === m.t)).neg;
      if (bad) return uiAlert(`Sem essa compra, a venda de ${dataBR(bad.d)} fica maior que a quantidade que você tinha. Exclua ou ajuste a venda antes.`);
      mov = next; editing = -1; save(); render();
    }
    else if (k === 'br') { const c = document.querySelector('#countryMenu [data-country="br"]'); if (c) c.click(); }
  });
  const visible = () => !pane().classList.contains('hidden');
  document.addEventListener('tabshow', (e) => { if (e.detail === 'carteira') { open = new Set(); editing = -1; render(); } });
  document.addEventListener('dataload', () => { if (visible()) render(); });
  if (visible()) render();
})();
