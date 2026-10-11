// Previsão aluguel (empréstimo de ações, BTB): renda de aluguel mês a mês de várias ações.
// Cálculo puro (testado em tests/test_aluguel.js): aluguelSim(items, opts) → {rows: total por mês, per: por ação e mês}
function aluguelSim(items, o) {
  const N = o.months || 960, fee = (o.fee || 0) / 100, desc = o.desc !== false;
  const per = items.map(() => []), rows = [];
  let acc = 0;
  for (let m = 1; m <= N; m++) {
    let q = 0, ql = 0, val = 0, rec = 0, dsc = 0;
    items.forEach((it, k) => {
      const ex = (o.ex || []).filter(e => e.t === it.t && e.m <= m).reduce((a, e) => a + e.q, 0);
      const sh = Math.max(0, it.q + (it.add || 0) * (m - 1) + ex);
      const lent = sh * (1 - Math.max(0, Math.min(100, it.nl || 0)) / 100); // só a parte alugada rende
      const P = Math.max(1, Math.round(it.prazo || 1));
      // renda bruta do mês = ações × preço × taxa a.a./12; paga ao fim de cada contrato (a cada P meses)
      const acr = lent * it.p * (it.rate / 100) / 12; it._acr = (m === 1 ? 0 : it._acr || 0) + acr;
      let g = 0; if (m % P === 0) { g = it._acr; it._acr = 0; }
      const fe = desc ? g * fee : 0, ir = desc ? (g - fe) * 0.15 : 0;
      per[k].push({ m, t: it.t, sh, val: sh * it.p, lent, rec: g, dsc: fe + ir });
      q += sh; val += sh * it.p; ql += lent; rec += g; dsc += fe + ir;
    });
    acc += rec - dsc;
    rows.push({ m, q, ql, val, rec, dsc, liq: rec - dsc, acc });
  }
  return { rows, per };
}
if (typeof module !== 'undefined') module.exports = { aluguelSim };
if (typeof document !== 'undefined') (function () {
  const KEY = 'screenerB3.aluguel.v1', root = document.getElementById('alugRoot'); if (!root) return;
  const st = (() => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } })() || { items: [], fee: 0, desc: true, div: false, ex: [], mes: '' };
  st.items = (st.items || []).filter(i => i.t && i.ok !== false).map(({ ok, ...i }) => i); delete st.div; if (st.draft === undefined) st.draft = null;
  // Prazos usuais de contrato BTC na B3 (dias): 30, 60, 90, 180, 360 -> meses de contrato
  const PRZ = [1, 2, 3, 6, 12], nearP = (m) => PRZ.reduce((a, b) => Math.abs(b - (m || 1)) < Math.abs(a - (m || 1)) ? b : a, 1);
  st.items.forEach(i => i.prazo = nearP(i.prazo)); if (st.draft) st.draft.prazo = nearP(st.draft.prazo);
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { } };
  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }), N0 = new Intl.NumberFormat('pt-BR');
  const num = (s) => { s = String(s ?? '').trim().replace(/\s|R\$|%/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, ''); const n = parseFloat(s); return Number.isFinite(n) ? n : 0; };
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let BTB = null, loading = false;
  const row = (t) => (typeof state !== 'undefined' && state.data ? state.data.rows : []).find(r => r.ticker === t);
  const b3 = (t) => BTB && BTB.t ? BTB.t[t] : null;
  const rateOf = (t) => { const x = b3(t); return x && x[1] != null ? +(x[1] * 100).toFixed(2) : null; };
  const lowDemand = (t) => { const x = b3(t); return !x || (x[0] || 0) < 500000 || (x[3] || 0) < 20; };
  async function load() {
    const get = async (u) => { const c = new AbortController(), h = setTimeout(() => c.abort(), 8000); try { const r = await fetch(u, { signal: c.signal }); return r.ok ? await r.json() : null; } catch (e) { return null; } finally { clearTimeout(h); } };
    const j = await get('/api/btb'); BTB = j && j.t ? j : { t: {}, err: true };
    render();
  }
  function items() { return st.items.filter(i => row(i.t)).map(i => ({ ...i, p: row(i.t).v.preco || 0 })); }
  const pct = (v) => v == null ? '—' : String(v).replace('.', ',') + '% a.a.';
  // Ações confirmadas: lista compacta (editar/excluir). Formulário só aparece com "+ Ação" ou "editar".
  function inputsHtml() {
    const list = st.items.map((it, k) => `<div class="al-row" data-k="${k}"><div class="min-w-0"><b>${esc(it.t)}</b> <span class="al-sub">${N0.format(it.q)} ações${it.add ? ' · +' + N0.format(it.add) + '/mês' : ''} · ${pct(it.rate)} · ${(it.prazo || 1) * 30} dias${it.nl ? ' · ' + String(it.nl).replace('.', ',') + '% não alugado' : ''}</span>${lowDemand(it.t) ? '<span class="al-warn"> ⚠ pouca demanda</span>' : ''}</div>
      <div class="al-btns"><button type="button" class="gbtn" data-a="edit" aria-label="Editar ${esc(it.t)}">Editar</button><button type="button" class="gx" data-a="del" aria-label="Excluir ${esc(it.t)}">✕</button></div></div>`).join('');
    const d = st.draft;
    const form = d ? `<div class="al-it" id="alForm">
      <label class="pv-f"><span>Ação</span><input class="pv-in al-t" value="${esc(d.t)}" placeholder="Buscar…" autocomplete="off"></label>
      <label class="pv-f"><span>Quantidade</span><input class="pv-in" data-f="q" inputmode="numeric" value="${d.q ? N0.format(d.q) : ''}"></label>
      <label class="pv-f"><span>Adições mensais</span><input class="pv-in" data-f="add" inputmode="numeric" value="${d.add ? N0.format(d.add) : ''}"></label>
      <label class="pv-f"><span>Taxa (% a.a.)</span><input class="pv-in" data-f="rate" inputmode="decimal" value="${d.rate != null ? String(d.rate).replace('.', ',') : ''}"></label>
      <label class="pv-f"><span>Prazo</span><select class="pv-in" data-f="prazo">${PRZ.map(m => `<option value="${m}"${(d.prazo || 1) === m ? ' selected' : ''}>${m * 30} dias</option>`).join('')}</select></label>
      <label class="pv-f"><span>% não alugado</span><input class="pv-in" data-f="nl" inputmode="decimal" value="${d.nl ? String(d.nl).replace('.', ',') : '0'}"></label>
      <div class="al-btns"><button type="button" class="gbtn pri" data-a="ok" aria-label="Confirmar">✓</button><button type="button" class="gx" data-a="cancel" aria-label="Cancelar">✕</button></div>
      ${d.t && b3(d.t) ? `<div class="upd">${(window.updTxt && updTxt()) || 'Atualizado em ' + (BTB.date || '').split('-').reverse().join('/')}</div>` : ''}
      ${d.t && lowDemand(d.t) ? '<p class="al-warn">⚠ Pouca demanda de aluguel para esta ação na B3: o empréstimo pode não acontecer ou demorar.</p>' : ''}</div>` : '';
    return list + form;
  }
  function exHtml() {
    return st.ex.map((e, k) => `<div class="pv-ex-row al-ex" data-x="${k}"><label class="pv-f"><span>Mês</span><input class="pv-in" data-xf="m" inputmode="numeric" value="${e.m || ''}"></label>
      <label class="pv-f"><span>Ação</span><select class="pv-in" data-xf="t">${[...new Set(st.items.map(i => i.t))].map(t => ({ t })).map(i => `<option${i.t === e.t ? ' selected' : ''}>${esc(i.t)}</option>`).join('')}</select></label>
      <label class="pv-f"><span>Ações (+ adiciona, − retira)</span><input class="pv-in" data-xf="q" inputmode="numeric" value="${e.q ? N0.format(e.q) : ''}"></label><button type="button" class="gx" data-xdel="${k}" aria-label="Remover">✕</button></div>`).join('');
  }
  const perB = (I, R, m0) => I.length ? R.per.map(p => { const x = p[m0 - 1]; return `<tr><td class="pv-c-m">${m0}</td><td><b>${esc(x.t)}</b></td><td>${N0.format(Math.round(x.sh))}</td><td>${brl.format(x.val)}</td><td>${N0.format(Math.round(x.lent))}</td><td class="pos">${brl.format(x.rec)}</td><td class="neg">${brl.format(x.dsc)}</td></tr>`; }).join('') : '';
  let shown = 240;
  const moreB = (I, R, m0) => I.length && m0 - 1 + shown < R.rows.length ? '<button type="button" class="gbtn" data-a="more">Mostrar mais meses</button>' : '';
  const mainB = (I, R, m0) => I.length ? R.rows.slice(m0 - 1, m0 - 1 + shown).map(r => `<tr><td class="pv-c-m">${r.m}</td><td>${N0.format(Math.round(r.q))}</td><td>${brl.format(r.val)}</td><td>${N0.format(Math.round(r.ql))}</td><td>${brl.format(r.rec)}</td><td class="neg">${brl.format(r.dsc)}</td><td class="pos">${brl.format(r.liq)}</td><td><b>${brl.format(r.acc)}</b></td></tr>`).join('') : '';
  // Só as tabelas são refeitas enquanto digita: o campo ativo não é recriado (mantém foco, cursor e seleção)
  function tables() {
    const pb = document.getElementById('alPerB'); if (!pb) return render();
    const I = items(), R = aluguelSim(I, { fee: st.fee, desc: st.desc, ex: st.ex.filter(e => e.t && e.m > 0) }), m0 = Math.max(1, Math.min(960, parseInt(st.mes, 10) || 1));
    pb.innerHTML = perB(I, R, m0); document.getElementById('alMainB').innerHTML = mainB(I, R, m0); document.getElementById('alMore').innerHTML = moreB(I, R, m0);
  }
  function render() {
    if (!BTB || typeof state === 'undefined' || !state.data) { root.innerHTML = loaderHTML('Carregando…'); if (!BTB) { if (!loading) { loading = true; load(); } } else setTimeout(render, 600); return; }
    const I = items(), R = aluguelSim(I, { fee: st.fee, desc: st.desc, ex: st.ex.filter(e => e.t && e.m > 0) });
    const m0 = Math.max(1, Math.min(960, parseInt(st.mes, 10) || 1)), dv = false;
    root.innerHTML = `<section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-3 sm:p-4 space-y-2">
      <div class="flex items-baseline justify-between gap-2"><h2 class="text-base font-bold">Ações para alugar</h2><button type="button" class="gbtn pri" data-a="new">＋ Ação</button></div>
      ${BTB.err ? '<p class="gt-help">Dados de aluguel da B3 indisponíveis agora: informe a taxa manualmente.</p>' : ''}<div id="alItems" class="space-y-2">${inputsHtml()}</div>
      <div class="al-opts"><label class="pv-f"><span>Taxa da corretora (% do aluguel)</span><input id="alFee" class="pv-in" inputmode="decimal" value="${String(st.fee).replace('.', ',')}"></label>
        <label class="al-ck"><input id="alDesc" type="checkbox" class="accent-emerald-500 w-4 h-4"${st.desc ? ' checked' : ''}> Descontar automaticamente taxa da corretora + IR 15%</label></div>
      <div><div class="flex items-center justify-between"><h3 class="text-sm font-bold">Adições e retiradas extraordinárias</h3><button type="button" class="gbtn" data-a="exnew">＋</button></div>
        <div class="flex flex-col gap-1.5 mt-1">${exHtml()}</div></div></section>
    <section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-2 sm:p-3 space-y-3">
      <div class="pv-scroll"><table class="pv-t pv-sum"><thead><tr><th class="pv-c-m">Mês<br><input id="alMes" class="pv-in" inputmode="numeric" maxlength="3" style="width:3.6em;text-align:center" value="${esc(st.mes)}" placeholder="1" aria-label="Mês"></th><th>Ação</th><th>Nº de ações</th><th>Valor das ações</th><th>Ações totais alugadas</th><th>Valor recebido</th><th>Descontos</th>${dv ? '<th>Dividendos</th>' : ''}</tr></thead>
        <tbody id="alPerB">${perB(I, R, m0)}</tbody></table></div>
      <div class="pv-scroll pv-main"><table class="pv-t"><thead><tr><th class="pv-c-m">Mês</th><th>Nº de ações</th><th>Valor das ações</th><th>Ações alugadas</th><th>Valor recebido</th><th>Descontos</th><th>Líquido</th>${dv ? '<th>Dividendos</th>' : ''}<th>Total acumulado</th></tr></thead>
        <tbody id="alMainB">${mainB(I, R, m0)}</tbody></table></div><div id="alMore" class="text-center mt-2">${moreB(I, R, m0)}</div></section>`;
    root.querySelectorAll('.al-t').forEach(inp => window.pvCombo && pvCombo(inp, (t) => { st.draft.t = t; const r = rateOf(t); if (r != null) st.draft.rate = r; save(); render(); }));
  }
  let tm = null; const later = () => { clearTimeout(tm); tm = setTimeout(() => { save(); tables(); }, 200); };
  function renderKeep() { const a = document.activeElement, id = a && a.id, f = a && a.dataset && (a.dataset.f || a.dataset.xf), k = a && a.closest && (a.closest('[data-k]') || a.closest('[data-x]')); const kk = k && (k.dataset.k || k.dataset.x); render();
    let n = id ? document.getElementById(id) : f && kk != null ? root.querySelector(`[data-${a.dataset.f ? 'k' : 'x'}="${kk}"] [data-${a.dataset.f ? 'f' : 'xf'}="${f}"]`) : null; if (n) { n.focus(); try { const L = n.value.length; n.setSelectionRange(L, L); } catch (e) { } } }
  root.addEventListener('input', (e) => {
    const t = e.target, k = t.closest('[data-k]'), x = t.closest('[data-x]');
    if (t.id === 'alMes') { st.mes = t.value.replace(/\D/g, '').slice(0, 3); later(); return; }
    if (t.id === 'alFee') { st.fee = num(t.value); later(); return; }
    if (t.dataset.f && st.draft) { st.draft[t.dataset.f] = t.dataset.f === 'rate' ? num(t.value) : t.dataset.f === 'nl' ? Math.max(0, Math.min(100, num(t.value))) : Math.round(num(t.value)); save(); return; }
    if (x && t.dataset.xf === 'q') { st.ex[+x.dataset.x].q = Math.round(num(t.value.replace(/^−/, '-'))); later(); }
    if (x && t.dataset.xf === 'm') { st.ex[+x.dataset.x].m = Math.min(960, Math.round(num(t.value))); later(); }
  });
  root.addEventListener('change', (e) => {
    const t = e.target, x = t.closest('[data-x]');
    if (t.id === 'alDesc') { st.desc = t.checked; save(); render(); }
    if (x && t.dataset.xf === 't') { st.ex[+x.dataset.x].t = t.value; save(); render(); }
  });
  root.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-a],[data-xdel]'); if (!b) return;
    const k = b.closest('[data-k]'), a = b.dataset.a;
    if (a === 'more') { shown += 240; tables(); return; }
    if (a === 'new') st.draft = { t: '', q: 100, add: 0, rate: null, prazo: 1, nl: 0, idx: -1 };
    else if (a === 'cancel') st.draft = null;
    else if (a === 'edit') { const i = +k.dataset.k; st.draft = { ...st.items[i], idx: i }; }
    else if (a === 'exnew') { const t = (st.items[0] || {}).t; if (!t) { uiToast('Confirme uma ação primeiro'); return; } st.ex.push({ m: 12, t, q: 100 }); }
    else if (a === 'ok') { const d = st.draft; if (!row(d.t)) { uiAlert('Escolha uma ação da lista.'); return; } if (!(d.q > 0)) { uiAlert('Informe a quantidade de ações.'); return; } if (d.rate == null || !(d.rate > 0)) { uiAlert('Informe a taxa de aluguel (% a.a.).'); return; }
      const it = { t: d.t, q: d.q, add: d.add || 0, rate: d.rate, prazo: Math.max(1, d.prazo || 1), nl: Math.max(0, Math.min(100, d.nl || 0)) };
      if (d.idx >= 0 && st.items[d.idx]) st.items[d.idx] = it; else st.items.push(it);
      st.draft = null; uiToast(it.t + ' adicionada'); }
    else if (a === 'del') { if (!(await uiConfirm('Remover esta ação da simulação?', { ok: 'Remover', danger: true }))) return; const t = st.items[+k.dataset.k].t; st.items.splice(+k.dataset.k, 1); if (!st.items.some(i => i.t === t)) st.ex = st.ex.filter(x => x.t !== t); }
    else if (b.dataset.xdel != null) st.ex.splice(+b.dataset.xdel, 1);
    save(); render();
  });
  document.addEventListener('pvsub', (e) => { if (e.detail === 'alug') render(); });
  window.aluguelRender = render;
  // o evento da sub-aba pode ter disparado antes deste script carregar
  if (!root.classList.contains('hidden')) render();
})();
