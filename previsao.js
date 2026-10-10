// Percentuais da tabela de Previsão (puro, testado em tests/test_previsao.js).
// va = (com − aporteT)/aporteT ; pa = aporteT/com ; pv = (sem − aporteT)/com ; pd = (com − sem)/com  → pa+pv+pd = 1
function pvPcts(apT, sem, com) {
  return { va: apT > 0 ? (com - apT) / apT : null, pa: com > 0 ? apT / com : null,
           pv: com > 0 ? (sem - apT) / com : null, pd: com > 0 ? (com - sem) / com : null };
}
if (typeof module !== 'undefined') module.exports = { pvPcts };
if (typeof document !== 'undefined') {
// ---------- Abas (Ações / Grupos / Previsão) ----------
(function () {
  const TAB_KEY = 'screenerB3.tab.v1';
  window.showTab = function (id) {
    document.querySelectorAll('[data-tabpane]').forEach(p => p.classList.toggle('hidden', p.dataset.tabpane !== id));
    document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === id));
    try { localStorage.setItem(TAB_KEY, id); } catch (e) { }
    document.dispatchEvent(new CustomEvent('tabshow', { detail: id }));
  };
  document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
  let t0 = 'acoes'; try { t0 = localStorage.getItem(TAB_KEY) || 'acoes'; } catch (e) { }
  if (!document.querySelector(`[data-tabpane="${t0}"]`)) t0 = 'acoes';
  showTab(t0);
})();

// ---------- Previsão ----------
(function () {
  const KEY = 'screenerB3.previsao.v1';
  const MAXM = 960, PAGE_ROWS = 240;
  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const pct = (d) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
  const P3 = pct(3), P2 = pct(2);
  const el = (id) => document.getElementById(id);
  const num = (s) => { s = String(s ?? '').trim().replace(/\s|R\$/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, ''); const n = parseFloat(s); return Number.isFinite(n) ? n : 0; };
  const st = (() => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } })() ||
    { ini: 5000, ap: 500, dm: (Math.pow(1.04, 1 / 12) - 1) * 100, da: 4, rm: (Math.pow(1.10, 1 / 12) - 1) * 100, ra: 10, ticker: '', di: '', df: '', ret: [], mes: '', proj: '', ex: [] };
  if (!Array.isArray(st.ex)) st.ex = [];
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { } };
  let rows = [], shownRows = PAGE_ROWS, hist = null, histT = '';

  const m2a = (m) => (Math.pow(1 + m / 100, 12) - 1) * 100;
  const a2m = (a) => (Math.pow(1 + a / 100, 1 / 12) - 1) * 100;
  const fmtIn = (v, d) => (v === '' || v == null) ? '' : pct(d).format(v);

  function fill() {
    el('pvIni').value = fmtIn(st.ini, 2); el('pvAp').value = fmtIn(st.ap, 2);
    el('pvDm').value = fmtIn(st.dm, 3); el('pvDa').value = fmtIn(st.da, 2);
    el('pvRm').value = fmtIn(st.rm, 3); el('pvRa').value = fmtIn(st.ra, 2);
    el('pvTicker').value = st.ticker || ''; el('pvProj').value = st.proj || '';
    renderRet(); renderEx(); applyMode();
  }
  const deb = (fn, ms = 150) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };
  const liveCompute = deb(() => { compute(); save(); });
  function bind(id, f, pair, pd) {
    const i = el(id);
    i.addEventListener('input', () => { f(num(i.value)); if (pair) el(pair).value = fmtIn(st[pd[0]], pd[1]); liveCompute(); });
    i.addEventListener('change', () => { f(num(i.value)); save(); setTimeout(() => { fill(); compute(); }, 0); });
  }
  bind('pvIni', v => st.ini = Math.max(0, v)); bind('pvAp', v => st.ap = Math.max(0, v));
  bind('pvDm', v => { st.dm = v; st.da = m2a(v); }, 'pvDa', ['da', 2]); bind('pvDa', v => { st.da = v; st.dm = a2m(v); }, 'pvDm', ['dm', 3]);
  bind('pvRm', v => { st.rm = v; st.ra = m2a(v); }, 'pvRa', ['ra', 2]); bind('pvRa', v => { st.ra = v; st.rm = a2m(v); }, 'pvRm', ['rm', 3]);
  // 1º toque seleciona tudo (digitar substitui); toque seguinte posiciona o cursor normalmente
  document.querySelector('[data-tabpane="previsao"]').addEventListener('focusin', (e) => {
    const t = e.target; if (!t.matches('input.pv-in:not([type=month])')) return;
    try { t.select(); } catch (er) { } t.dataset.fsel = '1';
    setTimeout(() => { if (t.dataset.fsel) { try { t.select(); } catch (er) { } } }, 0);
  });
  // o mouseup/toque que deu o foco não pode desfazer a seleção; os seguintes sim
  document.querySelector('[data-tabpane="previsao"]').addEventListener('mouseup', (e) => {
    const t = e.target; if (t.dataset && t.dataset.fsel) { e.preventDefault(); delete t.dataset.fsel; }
  });
  document.querySelector('[data-tabpane="previsao"]').addEventListener('keydown', (e) => { if (e.target.dataset) delete e.target.dataset.fsel; });

  // Retiradas
  function renderRet() {
    const box = el('pvRet');
    if (!st.ret.length) { box.innerHTML = '<p class="text-xs text-slate-500">Nenhuma retirada. Toque em <b>+</b> para adicionar.</p>'; return; }
    box.innerHTML = st.ret.map((r, i) => `<div class="flex items-center gap-1.5" data-i="${i}">
      <label class="pv-mini">R$<input inputmode="decimal" class="pv-in" style="width:7.5em" data-f="v" value="${fmtIn(r.v, 2)}"></label>
      <label class="pv-mini">mês<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="m" value="${r.m || ''}"></label>
      <button type="button" class="pv-x" data-del="${i}" aria-label="Remover retirada">✕</button></div>`).join('');
  }
  el('pvRet').addEventListener('change', (e) => {
    const row = e.target.closest('[data-i]'); if (!row) return;
    const r = st.ret[+row.dataset.i]; const f = e.target.dataset.f;
    r[f] = f === 'm' ? Math.max(1, Math.min(MAXM, Math.round(num(e.target.value)))) : Math.max(0, num(e.target.value));
    st.ret.sort((a, b) => a.m - b.m); save(); setTimeout(() => { fill(); compute(); }, 0);
  });
  el('pvRet').addEventListener('input', (e) => {
    const row = e.target.closest('[data-i]'); if (!row) return;
    const r = st.ret[+row.dataset.i]; const f = e.target.dataset.f;
    r[f] = f === 'm' ? Math.max(1, Math.min(MAXM, Math.round(num(e.target.value)) || 1)) : Math.max(0, num(e.target.value));
    liveCompute();
  });
  el('pvRet').addEventListener('click', (e) => {
    const b = e.target.closest('[data-del]'); if (!b) return;
    st.ret.splice(+b.dataset.del, 1); fill(); compute(); save();
  });
  el('pvAddRet').addEventListener('click', () => {
    const last = st.ret[st.ret.length - 1];
    st.ret.push({ v: 0, m: last ? Math.min(MAXM, last.m + 12) : 180 }); fill(); save();
    const ins = el('pvRet').querySelectorAll('input[data-f="v"]'); ins[ins.length - 1]?.focus();
  });
  // Aportes extraordinários: t = 'm' (mensal, substitui), 'u' (único), 'p' (por período, a cada n meses)
  const EXT = [['m', 'Aporte mensal'], ['u', 'Aporte único'], ['p', 'Aporte por período']];
  function renderEx() {
    const box = el('pvEx');
    if (!st.ex.length) { box.innerHTML = '<p class="text-xs text-slate-500">Nenhum aporte extra. Toque em <b>+</b> para adicionar.</p>'; return; }
    box.innerHTML = st.ex.map((r, i) => `<div class="pv-ex-row" data-x="${i}">
      <select data-f="t" aria-label="Tipo">${EXT.map(([k, l]) => `<option value="${k}"${r.t === k ? ' selected' : ''}>${l}</option>`).join('')}</select>
      <label class="pv-mini">R$<input inputmode="decimal" class="pv-in" style="width:7em" data-f="v" value="${fmtIn(r.v, 2)}"></label>
      <label class="pv-mini">mês<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="m" value="${r.m || ''}"></label>
      ${r.t === 'p' ? `<label class="pv-mini">a cada<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="n" value="${r.n || ''}">meses</label>` : ''}
      <button type="button" class="pv-x" data-xdel="${i}" aria-label="Remover aporte">✕</button>
      ${r.t === 'p' && !(r.n >= 2) ? '<span class="text-[11px] text-rose-300 basis-full">Intervalo deve ser um número inteiro de meses ≥ 2.</span>' : ''}</div>`).join('');
  }
  function setEx(e, final) {
    const row = e.target.closest('[data-x]'); if (!row) return;
    const r = st.ex[+row.dataset.x], f = e.target.dataset.f, raw = e.target.value;
    if (f === 't') { r.t = raw; if (r.t === 'p' && !r.n) r.n = 12; save(); renderEx(); compute(); return; }
    if (f === 'v') r.v = Math.max(0, num(raw));
    if (f === 'm') r.m = Math.max(1, Math.min(MAXM, Math.round(num(raw)) || 1));
    if (f === 'n') { const n = Number(String(raw).replace(',', '.')); r.n = Number.isInteger(n) && n >= 2 ? n : null; }
    if (final) { save(); setTimeout(() => { renderEx(); compute(); }, 0); } else liveCompute();
  }
  el('pvEx').addEventListener('input', (e) => { if (e.target.tagName === 'INPUT') setEx(e, false); });
  el('pvEx').addEventListener('change', (e) => setEx(e, true));
  el('pvEx').addEventListener('click', (e) => { const b = e.target.closest('[data-xdel]'); if (!b) return; st.ex.splice(+b.dataset.xdel, 1); save(); renderEx(); compute(); });
  el('pvAddEx').addEventListener('click', () => { st.ex.push({ t: 'u', v: 0, m: 12 }); save(); renderEx(); const ins = el('pvEx').querySelectorAll('input[data-f="v"]'); ins[ins.length - 1]?.focus(); });
  function apAt(m, w) {
    let reg = st.ap, extra = 0;
    for (const r of st.ex.slice().sort((a, b) => a.m - b.m)) {
      if (r.t === 'm' && r.m <= m) reg = r.v;
      else if (r.t === 'u' && r.m === m) extra += r.v;
      else if (r.t === 'p' && r.n >= 2 && m >= r.m && (m - r.m) % r.n === 0) extra += r.v;
    }
    return { reg: w > 0 ? 0 : reg, extra };
  }
  const wAt = (m) => { if (st.proj) return 0; let w = 0; for (const r of st.ret.slice().sort((a, b) => a.m - b.m)) if (r.m <= m) w = r.v; return w; };

  // Ação (modo histórico)
  function tickerList() { }
  // Combobox com busca a cada caractere (ticker, nome, setor, descrição; sem acento)
  const nrm = (x) => String(x || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const escP = (x) => String(x ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function combo(inp, onPick) {
    const box = document.createElement('div'); box.className = 'pv-combo hidden'; box.setAttribute('role', 'listbox');
    inp.parentNode.style.position = 'relative'; inp.parentNode.appendChild(box);
    inp.setAttribute('autocomplete', 'off'); inp.setAttribute('role', 'combobox');
    const rowsAll = () => (typeof state !== 'undefined' && state.data && state.country === 'br') ? state.data.rows : [];
    function show() {
      const q = nrm(inp.value.trim());
      const list = rowsAll().filter(r => !q || r.ticker.toLowerCase().startsWith(q) || (r._s || nrm(r.ticker + ' ' + r.nome)).includes(q))
        .sort((a, b) => (b.ticker.toLowerCase().startsWith(q) ? 1 : 0) - (a.ticker.toLowerCase().startsWith(q) ? 1 : 0)).slice(0, 30);
      box.innerHTML = list.length ? list.map(r => `<button type="button" data-t="${r.ticker}"><b>${r.ticker}</b><span class="pv-cn">${escP(r.nome || '')}</span><span class="pv-cs">${escP(r.macro || r.setor || '')}</span></button>`).join('')
        : '<div class="pv-cempty">Nenhuma empresa encontrada.</div>';
      box.classList.remove('hidden');
    }
    inp.addEventListener('input', show); inp.addEventListener('focus', show);
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const b = box.querySelector('[data-t]'); if (b) { e.preventDefault(); pick(b.dataset.t); } } if (e.key === 'Escape') box.classList.add('hidden'); });
    box.addEventListener('mousedown', (e) => e.preventDefault());
    box.addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (b) pick(b.dataset.t); });
    inp.addEventListener('blur', () => setTimeout(() => box.classList.add('hidden'), 150));
    function pick(t) { inp.value = t; box.classList.add('hidden'); inp.blur(); onPick(t); }
  }
  async function loadHist() {
    const t = (st.ticker || '').toUpperCase();
    applyMode();
    if (!t) { hist = null; histT = ''; compute(); return; }
    if (histT === t && hist) { compute(); return; }
    el('pvStatus').textContent = 'Carregando histórico de ' + t + '…';
    try {
      const r = await fetch('/api/history/' + encodeURIComponent(t) + '?kind=m');
      const d = await r.json(); if (!r.ok || !d.t || d.t.length < 2) throw new Error(d.error || 'sem histórico');
      hist = d; histT = t;
      const ym = (s) => { const x = new Date(s * 1000); return x.getUTCFullYear() + '-' + String(x.getUTCMonth() + 1).padStart(2, '0'); };
      hist.ym = d.t.map(ym); hist.divm = {};
      for (const [ts, v] of d.div || []) { const k = ym(ts); hist.divm[k] = (hist.divm[k] || 0) + v; }
      const lo = hist.ym[0], hi = hist.ym[hist.ym.length - 1];
      for (const id of ['pvDi', 'pvDf']) { el(id).min = lo; el(id).max = hi; }
      if (!st.di || st.di < lo || st.di > hi) st.di = lo;
      if (!st.df || st.df > hi || st.df < st.di) st.df = hi;
      el('pvDi').value = st.di; el('pvDf').value = st.df;
      el('pvOldest').dataset.tip = `Data mais antiga disponível para ${t}: ${lo.split('-').reverse().join('/')} (fonte: ${d.source})`;
      el('pvStatus').textContent = '';
    } catch (e) { hist = null; el('pvStatus').textContent = 'Histórico indisponível para ' + t + ': ' + e.message; }
    compute(); save();
  }
  combo(el('pvTicker'), (t) => { st.ticker = t; st.proj = ''; projS = null; el('pvProj').value = ''; st.di = st.df = ''; loadHist(); loadProj(); save(); });
  combo(el('pvProj'), (t) => { st.proj = t; st.ticker = ''; el('pvTicker').value = ''; loadHist(); loadProj(); save(); });
  el('pvClearP').addEventListener('click', () => { st.proj = ''; el('pvProj').value = ''; projS = null; loadProj(); save(); });
  // Projeções: médias dos últimos 10 anos (ou do que houver) do histórico mensal
  let projS = null;
  async function loadProj() {
    const t = st.proj || '';
    el('pvProjInfo').innerHTML = '';
    applyMode();
    if (!t) { projS = null; compute(); return; }
    el('pvProjInfo').textContent = 'Carregando histórico de ' + t + '…';
    try {
      const r = await fetch('/api/history/' + encodeURIComponent(t) + '?kind=m');
      const d = await r.json(); if (!r.ok || !d.t || d.t.length < 3) throw new Error(d.error || 'sem histórico');
      const ym = (x) => { const q = new Date(x * 1000); return q.getUTCFullYear() + '-' + String(q.getUTCMonth() + 1).padStart(2, '0'); };
      const yms = d.t.map(ym), divm = {};
      for (const [ts, v] of d.div || []) { const k = ym(ts); divm[k] = (divm[k] || 0) + v; }
      // último mês fechado; janela de até 120 meses
      let i1 = d.t.length - 1; const nowYm = ym(Date.now() / 1000); if (yms[i1] === nowYm && i1 > 2) i1--;
      const i0 = Math.max(0, i1 - 120), n = i1 - i0;
      const rm = Math.pow(d.c[i1] / d.c[i0], 1 / n) - 1;
      let ds = 0; for (let i = i0 + 1; i <= i1; i++) ds += (divm[yms[i]] || 0) / d.c[i - 1];
      const dm = ds / n;
      projS = { t, rm: rm * 100, dm: dm * 100, from: yms[i0], to: yms[i1], n };
      if (st.proj !== t) return;
      const br = (x) => x.split('-').reverse().join('/');
      el('pvProjInfo').innerHTML = `<div class="pv-pstats"><span>Rentab. <b>${P3.format(projS.rm)}% a.m.</b> · ${P2.format(m2a(projS.rm))}% a.a.</span>
        <span>Dividendos <b>${P3.format(projS.dm)}% a.m.</b> · ${P2.format(m2a(projS.dm))}% a.a.</span>
        <span class="text-slate-500">Período: ${br(yms[i0])} a ${br(yms[i1])} (${n} meses${n < 120 ? ', menos de 10 anos' : ''}) · ${escP(d.source)}</span></div>`;
    } catch (e) { projS = null; el('pvProjInfo').textContent = 'Histórico indisponível para ' + t + ': ' + e.message; }
    applyMode(); compute();
  }
  function applyMode() {
    const P = !!st.proj, T = !!st.ticker && !P;
    el('pvMode').textContent = P ? 'Projeção com médias de ' + st.proj : T ? 'Simulação histórica com ' + st.ticker : 'Projeção futura';
    ['pvDm', 'pvDa', 'pvRm', 'pvRa'].forEach(id => el(id).disabled = P || T);
    el('pvTicker').disabled = P; el('pvClearT').disabled = P; el('pvProj').disabled = T; el('pvClearP').disabled = T;
    el('pvRetBox').classList.toggle('pv-off', P);
    el('pvRetBox').querySelectorAll('input,button').forEach(x => x.disabled = P);
    el('pvDates').classList.toggle('hidden', !T);
  }
  el('pvClearT').addEventListener('click', () => { st.ticker = ''; el('pvTicker').value = ''; loadHist(); save(); });
  for (const id of ['pvDi', 'pvDf']) el(id).addEventListener('change', () => {
    let v = el(id).value; const lo = el(id).min, hi = el(id).max;
    if (v && lo && v < lo) v = lo; if (v && hi && v > hi) v = hi;
    if (id === 'pvDi') st.di = v; else st.df = v;
    if (st.df && st.di && st.df < st.di) st.df = st.di;
    el('pvDi').value = st.di; el('pvDf').value = st.df; compute(); save();
  });
  el('pvOldest').addEventListener('click', () => { const t = el('pvOldest').dataset.tip; if (t) alert(t); });

  // Cálculo. Convenção (igual à planilha): mês 1 = valor inicial; no mês n,
  // rentabilidade = patrimônio_sem(n-1) × r ; dividendo = patrimônio_com(n-1) × d (reinvestido na linha "com").
  function compute() {
    rows = [];
    let steps = null; // [{r, d, label}]
    if (st.proj && !projS) { renderAll(); return; }
    if (!st.proj && st.ticker && hist) {
      const i0 = Math.max(0, hist.ym.indexOf(st.di)), i1e = hist.ym.indexOf(st.df), i1 = i1e < 0 ? hist.ym.length - 1 : i1e;
      steps = [];
      for (let i = i0 + 1; i <= i1; i++) steps.push({ r: hist.c[i] / hist.c[i - 1] - 1, d: (hist.divm[hist.ym[i]] || 0) / hist.c[i - 1], ym: hist.ym[i] });
      steps.unshift({ ym: hist.ym[i0] });
    } else if (!st.proj && st.ticker) { renderAll(); return; }
    const n = steps ? steps.length : MAXM;
    const r0 = (projS && st.proj ? projS.rm : st.rm) / 100, d0 = (projS && st.proj ? projS.dm : st.dm) / 100;
    const x1 = apAt(1, 0).extra;
    let sem = st.ini + x1, com = st.ini + x1, apT = st.ini + x1, divT = 0;
    rows.push({ m: 1, ap: st.ini + x1, apT, rent: 0, div: 0, divT: 0, sem, com, w: 0, ym: steps?.[0].ym });
    for (let m = 2; m <= n; m++) {
      const r = steps ? steps[m - 1].r : r0, d = steps ? steps[m - 1].d : d0;
      const w = wAt(m), A = apAt(m, w), ap = A.reg + A.extra;
      const rent = sem * r, div = com * d, rentC = com * r;
      sem = Math.max(0, sem + rent + ap - w);
      com = Math.max(0, com + rentC + div + ap - w);
      apT += ap; divT += div;
      rows.push({ m, ap, apT, rent, div, divT, sem, com, w, ym: steps?.[m - 1].ym });
    }
    shownRows = PAGE_ROWS; renderAll();
  }

  const COLS = [['m', 'Mês', 'pv-c-m'], ['va', 'Valorização total', 'pv-c-p'], ['pa', '% Aporte', 'pv-c-p'], ['pv', '% Valorização', 'pv-c-p'], ['pd', '% Dividendos', 'pv-c-p'], ['ap', 'Aporte mensal', 'pv-c-ap'], ['apT', 'Aporte total', 'pv-c-ap'], ['rent', 'Rentabilidade mensal', 'pv-c-r'],
    ['div', 'Dividendo mensal', 'pv-c-d'], ['divT', 'Dividendos total', 'pv-c-d'], ['sem', 'Patrimônio total', 'pv-c-r'], ['com', 'Patrimônio total<br>com dividendos', 'pv-c-d']];
  const hasW = () => st.ret.some(r => r.v > 0);
  const cols = () => hasW() ? COLS.concat([['w', 'Retirada', 'pv-c-w']]) : COLS;
  const PP = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pcell = (r, k) => { const p = pvPcts(r.apT, r.sem, r.com)[k]; if (p == null) return ['—', '']; const cls = k === 'pa' ? (p > 1 ? 'neg' : 'pos') : (p < 0 ? 'neg' : p > 0 ? 'pos' : ''); return [PP.format(p * 100) + '%', cls]; };
  const cell = (r, k) => ['va', 'pa', 'pv', 'pd'].includes(k) ? pcell(r, k)[0] : k === 'm' ? (r.ym ? `${r.m}<span class="pv-ym">${r.ym.split('-').reverse().join('/')}</span>` : r.m) : (k === 'w' && !r.w ? '–' : brl.format(r[k]));
  const head = () => '<tr>' + cols().map(([k, l, c]) => `<th class="${c}">${l}</th>`).join('') + '</tr>';
  const tdc = (r, k, c) => ['va', 'pa', 'pv', 'pd'].includes(k) ? c + ' ' + pcell(r, k)[1] : c;
  const line = (r) => '<tr>' + cols().map(([k, , c]) => `<td class="${tdc(r, k, c)}">${cell(r, k)}</td>`).join('') + '</tr>';
  const startIdx = () => { const m = parseInt(st.mes, 10); return m > 1 ? Math.min(rows.length, m) - 1 : 0; };

  function renderAll() {
    if (!rows.length) { el('pvSumBody').innerHTML = ''; el('pvBody').innerHTML = ''; el('pvMore').classList.add('hidden'); return; }
    const s = startIdx(), r = rows[s];
    const hh = head();
    if (el('pvSumHead').innerHTML !== hh || !el('pvMes')) {
      el('pvSumHead').innerHTML = hh; el('pvSumBody').innerHTML = line(r);
      el('pvSumBody').querySelector('td').innerHTML = `<input id="pvMes" inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" placeholder="1" value="${st.mes || ''}" aria-label="Mês">`;
      const upd = deb(() => { st.mes = String(Math.max(0, Math.round(num(el('pvMes').value))) || ''); shownRows = PAGE_ROWS; save(); renderAll(); });
      el('pvMes').addEventListener('input', upd);
    } else {
      const tmp = document.createElement('tbody'); tmp.innerHTML = line(r);
      const src = tmp.querySelectorAll('td'), dst = el('pvSumBody').querySelectorAll('td');
      for (let i = 1; i < dst.length; i++) { dst[i].innerHTML = src[i].innerHTML; dst[i].className = src[i].className; }
    }
    el('pvHead').innerHTML = head();
    const end = Math.min(rows.length, s + shownRows);
    el('pvBody').innerHTML = rows.slice(s, end).map(line).join('');
    el('pvMore').classList.toggle('hidden', end >= rows.length);
    el('pvCount').textContent = `Mostrando meses ${rows[s].m}–${rows[end - 1].m} de ${rows.length}`;
    syncWidths();
  }
  // Larguras: a tabela principal (auto, títulos quebram) define; o resumo copia e rola junto
  function syncWidths() {
    const sumT = el('pvSumHead').closest('table');
    const ths = [...el('pvHead').querySelectorAll('th')];
    const sh = [...el('pvSumHead').querySelectorAll('th')], sb = [...el('pvSumBody').querySelectorAll('td')];
    ths.forEach(th => th.style.minWidth = '');
    const ws = ths.map(th => th.getBoundingClientRect().width);
    ws.forEach((w, i) => { if (sh[i]) sh[i].style.width = w + 'px'; if (sb[i]) sb[i].style.width = w + 'px'; });
    sumT.style.width = ws.reduce((a, b) => a + b, 0) + 'px';
    el('pvSumScroll').scrollLeft = el('pvMainScroll').scrollLeft;
  }
  let syncing = false;
  for (const [a, b] of [['pvSumScroll', 'pvMainScroll'], ['pvMainScroll', 'pvSumScroll']])
    el(a).addEventListener('scroll', () => { if (syncing) { syncing = false; return; } if (el(b).scrollLeft !== el(a).scrollLeft) { syncing = true; el(b).scrollLeft = el(a).scrollLeft; } }, { passive: true });
  window.addEventListener('resize', () => { if (rows.length) syncWidths(); });
  el('pvMoreBtn').addEventListener('click', () => { shownRows += PAGE_ROWS; renderAll(); });

  let inited = false;
  document.addEventListener('tabshow', (e) => {
    if (e.detail !== 'previsao') return;
    if (rows.length) setTimeout(syncWidths, 0);
    tickerList();
    if (!inited) { inited = true; fill(); loadHist(); if (st.proj) loadProj(); }
  });
  if (!document.querySelector('[data-tabpane="previsao"]').classList.contains('hidden')) { inited = true; fill(); loadHist(); if (st.proj) loadProj(); }
})();

}
