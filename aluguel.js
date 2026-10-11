// Previsão aluguel (empréstimo de ações, BTB): renda de aluguel mês a mês de várias ações.
// Cálculo puro (testado em tests/test_aluguel.js): aluguelSim(items, opts) → {rows: total por mês, per: por ação e mês}
function aluguelSim(items, o) {
  const N = o.months || 360, fee = (o.fee || 0) / 100, desc = o.desc !== false;
  const per = items.map(() => []), rows = [];
  let acc = 0;
  for (let m = 1; m <= N; m++) {
    let q = 0, rec = 0, dsc = 0, dv = 0;
    items.forEach((it, k) => {
      const ex = (o.ex || []).filter(e => e.t === it.t && e.m <= m).reduce((a, e) => a + e.q, 0);
      const sh = Math.max(0, it.q + (it.add || 0) * (m - 1) + ex);
      const P = Math.max(1, Math.round(it.prazo || 1));
      // renda bruta do mês = ações × preço × taxa a.a./12; paga ao fim de cada contrato (a cada P meses)
      const acr = sh * it.p * (it.rate / 100) / 12; it._acr = (m === 1 ? 0 : it._acr || 0) + acr;
      let g = 0; if (m % P === 0) { g = it._acr; it._acr = 0; }
      const fe = desc ? g * fee : 0, ir = desc ? (g - fe) * 0.15 : 0;
      const d = o.div ? sh * it.p * (it.dy || 0) / 100 / 12 : 0;
      per[k].push({ m, t: it.t, sh, rec: g, dsc: fe + ir, div: d });
      q += sh; rec += g; dsc += fe + ir; dv += d;
    });
    acc += rec - dsc + dv;
    rows.push({ m, q, rec, dsc, liq: rec - dsc, div: dv, acc });
  }
  return { rows, per };
}
if (typeof module !== 'undefined') module.exports = { aluguelSim };
if (typeof document !== 'undefined') (function () {
  const KEY = 'screenerB3.aluguel.v1', root = document.getElementById('alugRoot'); if (!root) return;
  const st = (() => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } })() || { items: [], fee: 0, desc: true, div: false, ex: [], mes: '' };
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { } };
  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }), N0 = new Intl.NumberFormat('pt-BR');
  const num = (s) => { s = String(s ?? '').trim().replace(/\s|R\$|%/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, ''); const n = parseFloat(s); return Number.isFinite(n) ? n : 0; };
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let BTB = null, MET = null;
  const row = (t) => (typeof state !== 'undefined' && state.data ? state.data.rows : []).find(r => r.ticker === t);
  const b3 = (t) => BTB && BTB.t ? BTB.t[t] : null;
  const rateOf = (t) => { const x = b3(t); return x && x[1] != null ? +(x[1] * 100).toFixed(2) : null; };
  const lowDemand = (t) => { const x = b3(t); return !x || (x[0] || 0) < 500000 || (x[3] || 0) < 20; };
  async function load() {
    try { BTB = await (await fetch('/api/btb')).json(); } catch (e) { BTB = {}; }
    try { MET = (await (await fetch('/api/metrics')).json()).metrics || {}; } catch (e) { MET = {}; }
    render();
  }
  function items() { return st.items.filter(i => i.ok && row(i.t)).map(i => ({ ...i, p: row(i.t).v.preco || 0, dy: (MET[i.t] || {}).dy1 || 0 })); }
  function inputsHtml() {
    return st.items.map((it, k) => `<div class="al-it${it.ok ? ' ok' : ''}" data-k="${k}">
      <label class="pv-f"><span>Ação</span><input class="pv-in al-t" value="${esc(it.t)}" placeholder="Buscar…" autocomplete="off"></label>
      <label class="pv-f"><span>Quantidade</span><input class="pv-in" data-f="q" inputmode="numeric" value="${it.q ? N0.format(it.q) : ''}"></label>
      <label class="pv-f"><span>Adições mensais</span><input class="pv-in" data-f="add" inputmode="numeric" value="${it.add ? N0.format(it.add) : ''}"></label>
      <label class="pv-f"><span>Taxa (% a.a.)</span><input class="pv-in" data-f="rate" inputmode="decimal" value="${it.rate != null ? String(it.rate).replace('.', ',') : ''}"></label>
      <label class="pv-f"><span>Prazo (meses)</span><input class="pv-in" data-f="prazo" inputmode="numeric" value="${it.prazo || 1}"></label>
      <div class="al-btns"><button type="button" class="gbtn pri" data-a="ok" aria-label="Confirmar">✓</button><button type="button" class="gx" data-a="del" aria-label="Remover">✕</button></div>
      ${it.t && b3(it.t) ? `<p class="gt-help al-info">B3 (${(BTB.date || '').split('-').reverse().join('/')}): ${N0.format(b3(it.t)[0])} ações alugadas · taxa média doador ${rateOf(it.t) != null ? String(rateOf(it.t)).replace('.', ',') + '% a.a.' : '—'} · ${N0.format(b3(it.t)[3])} contratos no dia</p>` : ''}
      ${it.t && lowDemand(it.t) ? '<p class="al-warn">⚠ Pouca demanda de aluguel para esta ação na B3: o empréstimo pode não acontecer ou demorar.</p>' : ''}</div>`).join('');
  }
  function exHtml() {
    return st.ex.map((e, k) => `<div class="pv-ex-row al-ex" data-x="${k}"><label class="pv-f"><span>Mês</span><input class="pv-in" data-xf="m" inputmode="numeric" value="${e.m || ''}"></label>
      <label class="pv-f"><span>Ação</span><select class="pv-in" data-xf="t">${st.items.filter(i => i.t).map(i => `<option${i.t === e.t ? ' selected' : ''}>${esc(i.t)}</option>`).join('')}</select></label>
      <label class="pv-f"><span>Ações (+ adiciona, − retira)</span><input class="pv-in" data-xf="q" inputmode="numeric" value="${e.q ? N0.format(e.q) : ''}"></label><button type="button" class="gx" data-xdel="${k}" aria-label="Remover">✕</button></div>`).join('');
  }
  function render() {
    if (!BTB) { root.innerHTML = loaderHTML('Carregando dados de aluguel da B3…'); load(); return; }
    const I = items(), R = aluguelSim(I, { fee: st.fee, desc: st.desc, div: st.div, ex: st.ex.filter(e => e.t && e.m > 0) });
    const m0 = Math.max(1, Math.min(360, parseInt(st.mes, 10) || 1)), dv = st.div;
    root.innerHTML = `<section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-3 sm:p-4 space-y-2">
      <div class="flex items-baseline justify-between gap-2"><h2 class="text-base font-bold">Ações para alugar</h2><button type="button" class="gbtn pri" data-a="new">＋ Ação</button></div>
      <div id="alItems" class="space-y-2">${inputsHtml() || '<p class="gt-empty">Adicione uma ação para simular o aluguel.</p>'}</div>
      <div class="al-opts"><label class="pv-f"><span>Taxa da corretora (% do aluguel)</span><input id="alFee" class="pv-in" inputmode="decimal" value="${String(st.fee).replace('.', ',')}"></label>
        <label class="al-ck"><input id="alDesc" type="checkbox" class="accent-emerald-500 w-4 h-4"${st.desc ? ' checked' : ''}> Descontar automaticamente taxa da corretora + IR 15%</label>
        <label class="al-ck"><input id="alDiv" type="checkbox" class="accent-emerald-500 w-4 h-4"${dv ? ' checked' : ''}> Incluir dividendos (DY dos últimos 12 meses)</label></div>
      <div><div class="flex items-center justify-between"><h3 class="text-sm font-bold">Adições e retiradas extraordinárias</h3><button type="button" class="gbtn" data-a="exnew">＋</button></div>
        <div class="flex flex-col gap-1.5 mt-1">${exHtml()}</div></div>
      <p class="gt-help">Renda bruta = ações × preço atual × taxa a.a. ÷ 12, paga ao fim de cada contrato (prazo). Descontos = taxa da corretora + IR de 15% sobre o restante. Taxa sugerida = média ponderada do doador na B3 (editável).</p></section>
    <section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-2 sm:p-3 space-y-3">
      <div class="pv-scroll"><table class="pv-t pv-sum"><thead><tr><th class="pv-c-m">Mês</th><th>Ação</th><th>Ações totais alugadas</th><th>Valor recebido</th><th>Descontos</th>${dv ? '<th>Dividendos</th>' : ''}</tr></thead>
        <tbody>${I.length ? R.per.map((p, k) => { const x = p[m0 - 1]; return `<tr><td class="pv-c-m">${k ? m0 : '<input id="alMes" class="pv-in" inputmode="numeric" maxlength="3" style="width:3.6em;text-align:center" value="' + esc(st.mes) + '" placeholder="1">'}</td><td><b>${esc(x.t)}</b></td><td>${N0.format(Math.round(x.sh))}</td><td class="pos">${brl.format(x.rec)}</td><td class="neg">${brl.format(x.dsc)}</td>${dv ? `<td class="pos">${brl.format(x.div)}</td>` : ''}</tr>`; }).join('') : `<tr><td colspan="${dv ? 6 : 5}" class="gt-empty">Nenhuma ação confirmada.</td></tr>`}</tbody></table></div>
      <p class="gt-help px-1">Digite um mês na primeira célula: mostra a contribuição de cada ação nesse mês e a tabela total a partir dele.</p>
      <div class="pv-scroll pv-main"><table class="pv-t"><thead><tr><th class="pv-c-m">Mês</th><th>Ações alugadas</th><th>Valor recebido</th><th>Descontos</th><th>Líquido</th>${dv ? '<th>Dividendos</th>' : ''}<th>Total acumulado</th></tr></thead>
        <tbody>${I.length ? R.rows.slice(m0 - 1).map(r => `<tr><td class="pv-c-m">${r.m}</td><td>${N0.format(Math.round(r.q))}</td><td>${brl.format(r.rec)}</td><td class="neg">${brl.format(r.dsc)}</td><td class="pos">${brl.format(r.liq)}</td>${dv ? `<td>${brl.format(r.div)}</td>` : ''}<td><b>${brl.format(r.acc)}</b></td></tr>`).join('') : ''}</tbody></table></div></section>`;
    root.querySelectorAll('.al-t').forEach(inp => window.pvCombo && pvCombo(inp, (t) => { const k = +inp.closest('[data-k]').dataset.k; st.items[k].t = t; const r = rateOf(t); if (r != null) st.items[k].rate = r; save(); render(); }));
  }
  let tm = null; const later = () => { clearTimeout(tm); tm = setTimeout(() => { save(); renderKeep(); }, 250); };
  function renderKeep() { const a = document.activeElement, id = a && a.id, f = a && a.dataset && (a.dataset.f || a.dataset.xf), k = a && a.closest && (a.closest('[data-k]') || a.closest('[data-x]')); const kk = k && (k.dataset.k || k.dataset.x); render();
    let n = id ? document.getElementById(id) : f && kk != null ? root.querySelector(`[data-${a.dataset.f ? 'k' : 'x'}="${kk}"] [data-${a.dataset.f ? 'f' : 'xf'}="${f}"]`) : null; if (n) { n.focus(); try { const L = n.value.length; n.setSelectionRange(L, L); } catch (e) { } } }
  root.addEventListener('input', (e) => {
    const t = e.target, k = t.closest('[data-k]'), x = t.closest('[data-x]');
    if (t.id === 'alMes') { st.mes = t.value.replace(/\D/g, '').slice(0, 3); later(); return; }
    if (t.id === 'alFee') { st.fee = num(t.value); later(); return; }
    if (k && t.dataset.f) { const it = st.items[+k.dataset.k]; it[t.dataset.f] = t.dataset.f === 'rate' ? num(t.value) : Math.round(num(t.value)); it.ok = false; later(); return; }
    if (x && t.dataset.xf === 'q') { st.ex[+x.dataset.x].q = Math.round(num(t.value.replace(/^−/, '-'))); later(); }
    if (x && t.dataset.xf === 'm') { st.ex[+x.dataset.x].m = Math.min(360, Math.round(num(t.value))); later(); }
  });
  root.addEventListener('change', (e) => {
    const t = e.target, x = t.closest('[data-x]');
    if (t.id === 'alDesc') { st.desc = t.checked; save(); render(); }
    if (t.id === 'alDiv') { st.div = t.checked; save(); render(); }
    if (x && t.dataset.xf === 't') { st.ex[+x.dataset.x].t = t.value; save(); render(); }
  });
  root.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-a],[data-xdel]'); if (!b) return;
    const k = b.closest('[data-k]'), a = b.dataset.a;
    if (a === 'new') st.items.push({ t: '', q: 100, add: 0, rate: null, prazo: 1, ok: false });
    else if (a === 'exnew') { const t = (st.items.find(i => i.t) || {}).t; if (!t) { uiToast('Adicione uma ação primeiro'); return; } st.ex.push({ m: 12, t, q: 100 }); }
    else if (a === 'ok') { const it = st.items[+k.dataset.k]; if (!row(it.t)) { uiAlert('Escolha uma ação da lista.'); return; } if (!(it.q > 0)) { uiAlert('Informe a quantidade de ações.'); return; } if (it.rate == null || !(it.rate > 0)) { uiAlert('Informe a taxa de aluguel (% a.a.).'); return; } it.ok = true; uiToast(it.t + ' confirmada'); }
    else if (a === 'del') { if (!(await uiConfirm('Remover esta ação da simulação?', { ok: 'Remover', danger: true }))) return; const t = st.items[+k.dataset.k].t; st.items.splice(+k.dataset.k, 1); st.ex = st.ex.filter(x => x.t !== t); }
    else if (b.dataset.xdel != null) st.ex.splice(+b.dataset.xdel, 1);
    save(); render();
  });
  document.addEventListener('pvsub', (e) => { if (e.detail === 'alug') render(); });
  window.aluguelRender = render;
})();
