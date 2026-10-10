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
  const MAXM = 960, PAGE_ROWS = 120;
  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const pct = (d) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
  const P3 = pct(3), P2 = pct(2);
  const el = (id) => document.getElementById(id);
  const num = (s) => { s = String(s ?? '').trim().replace(/\s|R\$/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); const n = parseFloat(s); return Number.isFinite(n) ? n : 0; };
  const st = (() => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } })() ||
    { ini: 60000, ap: 0, dm: (Math.pow(1.06, 1 / 12) - 1) * 100, da: 6, rm: (Math.pow(1.15, 1 / 12) - 1) * 100, ra: 15, ticker: '', di: '', df: '', ret: [], mes: '' };
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { } };
  let rows = [], shownRows = PAGE_ROWS, hist = null, histT = '';

  const m2a = (m) => (Math.pow(1 + m / 100, 12) - 1) * 100;
  const a2m = (a) => (Math.pow(1 + a / 100, 1 / 12) - 1) * 100;
  const fmtIn = (v, d) => (v === '' || v == null) ? '' : pct(d).format(v);

  function fill() {
    el('pvIni').value = fmtIn(st.ini, 2); el('pvAp').value = fmtIn(st.ap, 2);
    el('pvDm').value = fmtIn(st.dm, 3); el('pvDa').value = fmtIn(st.da, 2);
    el('pvRm').value = fmtIn(st.rm, 3); el('pvRa').value = fmtIn(st.ra, 2);
    el('pvTicker').value = st.ticker || '';
    renderRet();
  }
  function bind(id, f) { const i = el(id); i.addEventListener('change', () => { f(num(i.value)); save(); setTimeout(() => { fill(); compute(); }, 0); }); }
  bind('pvIni', v => st.ini = Math.max(0, v)); bind('pvAp', v => st.ap = Math.max(0, v));
  bind('pvDm', v => { st.dm = v; st.da = m2a(v); }); bind('pvDa', v => { st.da = v; st.dm = a2m(v); });
  bind('pvRm', v => { st.rm = v; st.ra = m2a(v); }); bind('pvRa', v => { st.ra = v; st.rm = a2m(v); });

  // Retiradas
  function renderRet() {
    const box = el('pvRet');
    if (!st.ret.length) { box.innerHTML = '<p class="text-xs text-slate-500">Nenhuma retirada. Toque em <b>+</b> para adicionar.</p>'; return; }
    box.innerHTML = st.ret.map((r, i) => `<div class="flex items-center gap-1.5" data-i="${i}">
      <label class="pv-mini">R$<input inputmode="decimal" class="pv-in w-24" data-f="v" value="${fmtIn(r.v, 2)}"></label>
      <label class="pv-mini">mês<input inputmode="numeric" class="pv-in w-16" data-f="m" value="${r.m || ''}"></label>
      <button type="button" class="pv-x" data-del="${i}" aria-label="Remover retirada">✕</button></div>`).join('');
  }
  el('pvRet').addEventListener('change', (e) => {
    const row = e.target.closest('[data-i]'); if (!row) return;
    const r = st.ret[+row.dataset.i]; const f = e.target.dataset.f;
    r[f] = f === 'm' ? Math.max(1, Math.min(MAXM, Math.round(num(e.target.value)))) : Math.max(0, num(e.target.value));
    st.ret.sort((a, b) => a.m - b.m); save(); setTimeout(() => { fill(); compute(); }, 0);
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
  const wAt = (m) => { let w = 0; for (const r of st.ret) if (r.m <= m) w = r.v; return w; };

  // Ação (modo histórico)
  function tickerList() {
    const rs = (typeof state !== 'undefined' && state.data && state.country === 'br') ? state.data.rows : [];
    el('pvTickers').innerHTML = rs.map(r => `<option value="${r.ticker}">`).join('');
  }
  async function loadHist() {
    const t = (st.ticker || '').toUpperCase();
    el('pvMode').textContent = t ? 'Simulação histórica com ' + t : 'Projeção futura';
    ['pvDm', 'pvDa', 'pvRm', 'pvRa'].forEach(id => el(id).disabled = !!t);
    el('pvDates').classList.toggle('hidden', !t);
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
  el('pvTicker').addEventListener('change', () => { st.ticker = el('pvTicker').value.trim().toUpperCase(); el('pvTicker').value = st.ticker; st.di = st.df = ''; loadHist(); save(); });
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
    if (st.ticker && hist) {
      const i0 = Math.max(0, hist.ym.indexOf(st.di)), i1e = hist.ym.indexOf(st.df), i1 = i1e < 0 ? hist.ym.length - 1 : i1e;
      steps = [];
      for (let i = i0 + 1; i <= i1; i++) steps.push({ r: hist.c[i] / hist.c[i - 1] - 1, d: (hist.divm[hist.ym[i]] || 0) / hist.c[i - 1], ym: hist.ym[i] });
      steps.unshift({ ym: hist.ym[i0] });
    } else if (st.ticker) { renderAll(); return; }
    const n = steps ? steps.length : MAXM;
    const r0 = st.rm / 100, d0 = st.dm / 100;
    let sem = st.ini, com = st.ini, apT = st.ini, divT = 0;
    rows.push({ m: 1, ap: st.ini, apT, rent: 0, div: 0, divT: 0, sem, com, w: 0, ym: steps?.[0].ym });
    for (let m = 2; m <= n; m++) {
      const r = steps ? steps[m - 1].r : r0, d = steps ? steps[m - 1].d : d0;
      const w = wAt(m), ap = w > 0 ? 0 : st.ap;
      const rent = sem * r, div = com * d, rentC = com * r;
      sem = Math.max(0, sem + rent + ap - w);
      com = Math.max(0, com + rentC + div + ap - w);
      apT += ap; divT += div;
      rows.push({ m, ap, apT, rent, div, divT, sem, com, w, ym: steps?.[m - 1].ym });
    }
    shownRows = PAGE_ROWS; renderAll();
  }

  const COLS = [['m', 'Mês', 'pv-c-m'], ['ap', 'Aporte mensal', 'pv-c-ap'], ['apT', 'Aporte total', 'pv-c-ap'], ['rent', 'Rentabilidade mensal', 'pv-c-r'],
    ['div', 'Dividendo mensal', 'pv-c-d'], ['divT', 'Dividendos total', 'pv-c-d'], ['sem', 'Patrimônio total', 'pv-c-r'], ['com', 'Patrimônio total com dividendos', 'pv-c-d']];
  const hasW = () => st.ret.some(r => r.v > 0);
  const cols = () => hasW() ? COLS.concat([['w', 'Retirada', 'pv-c-w']]) : COLS;
  const cell = (r, k) => k === 'm' ? (r.ym ? `${r.m}<span class="pv-ym">${r.ym.split('-').reverse().join('/')}</span>` : r.m) : (k === 'w' && !r.w ? '–' : brl.format(r[k]));
  const head = () => '<tr>' + cols().map(([k, l, c]) => `<th class="${c}">${l}</th>`).join('') + '</tr>';
  const line = (r) => '<tr>' + cols().map(([k, , c]) => `<td class="${c}">${cell(r, k)}</td>`).join('') + '</tr>';
  const startIdx = () => { const m = parseInt(st.mes, 10); return m > 1 ? Math.min(rows.length, m) - 1 : 0; };

  function renderAll() {
    if (!rows.length) { el('pvSum').innerHTML = ''; el('pvTable').innerHTML = ''; el('pvMore').classList.add('hidden'); return; }
    const s = startIdx(), r = rows[s];
    el('pvSumHead').innerHTML = head(); el('pvSumBody').innerHTML = line(r);
    const first = el('pvSumBody').querySelector('td');
    first.innerHTML = `<input id="pvMes" inputmode="numeric" class="pv-in w-14 text-center" placeholder="1" value="${st.mes || ''}" aria-label="Mês">`;
    el('pvMes').addEventListener('change', () => { st.mes = String(Math.max(0, Math.round(num(el('pvMes').value))) || ''); shownRows = PAGE_ROWS; save(); setTimeout(renderAll, 0); });
    el('pvHead').innerHTML = head();
    const end = Math.min(rows.length, s + shownRows);
    el('pvBody').innerHTML = rows.slice(s, end).map(line).join('');
    el('pvMore').classList.toggle('hidden', end >= rows.length);
    el('pvCount').textContent = `Mostrando meses ${rows[s].m}–${rows[end - 1].m} de ${rows.length}`;
  }
  el('pvMoreBtn').addEventListener('click', () => { shownRows += PAGE_ROWS * 2; renderAll(); });

  let inited = false;
  document.addEventListener('tabshow', (e) => {
    if (e.detail !== 'previsao') return;
    tickerList();
    if (!inited) { inited = true; fill(); loadHist(); }
  });
  if (!document.querySelector('[data-tabpane="previsao"]').classList.contains('hidden')) { inited = true; fill(); loadHist(); setTimeout(tickerList, 3000); }
})();
