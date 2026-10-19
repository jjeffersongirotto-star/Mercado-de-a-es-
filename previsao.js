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

// Sub-abas da Previsão
(function () {
  const K = 'screenerB3.pvsub.v1'; let cur = 'rent'; try { cur = localStorage.getItem(K) || 'rent'; } catch (e) { }
  const set = (id) => { cur = id; document.querySelectorAll('[data-pvsub]').forEach(b => b.classList.toggle('on', b.dataset.pvsub === id));
    document.getElementById('pvRent').classList.toggle('hidden', id !== 'rent'); document.getElementById('alugRoot').classList.toggle('hidden', id !== 'alug');
    try { localStorage.setItem(K, id); } catch (e) { } document.dispatchEvent(new CustomEvent('pvsub', { detail: id })); };
  document.querySelectorAll('[data-pvsub]').forEach(b => b.addEventListener('click', () => set(b.dataset.pvsub)));
  setTimeout(() => set(cur), 0);
})();
// ---------- Previsão ----------
(function () {
  const KEY = 'screenerB3.previsao.v1';
  const MAXM = 960, PAGE_ROWS = 240;
  const P3 = nf(3), P2 = nf(2);
  const el = (id) => document.getElementById(id);
  const st = (() => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } })() ||
    { ini: 5000, ap: 500, dm: (Math.pow(1.04, 1 / 12) - 1) * 100, da: 4, rm: (Math.pow(1.10, 1 / 12) - 1) * 100, ra: 10, ticker: '', di: '', df: '', ret: [], mes: '', proj: '', ex: [] };
  if (!Array.isArray(st.ex)) st.ex = [];
  if (!(st.tx >= 0)) st.tx = 0; st.txc = !!st.txc; // txc=false: automático (10% só em meses com dividendo > R$ 50 mil)
  if (typeof st.mod !== 'string') st.mod = ''; if (st.pvt !== 'des') st.pvt = 'tab';
  // várias empresas: '*' = Todas · 'top5' = 5 maiores de cada setor
  const MULTI = { '*': 'Todos', top5: '5 maiores de cada setor' }, multi = () => !!MULTI[st.ticker];  // modelo ('' = Sem modelo, '*' = Todos) e aba Tabela/Desempenho
  st.ret.forEach(r => { if (r.ok === undefined) r.ok = true; }); st.ex.forEach(r => { if (r.ok === undefined) r.ok = true; });
  function toast(msg) {
    let t = document.getElementById('pvToast');
    if (!t) { t = document.createElement('div'); t.id = 'pvToast'; t.className = 'pv-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('on'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 1800);
  }
  // botões salvar/editar/apagar das linhas (Retiradas e Aportes extraordinários)
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-rowact]'); if (!b) return;
    const [kind, act, i] = b.dataset.rowact.split(':'), arr = kind === 'ret' ? st.ret : st.ex, r = arr[+i]; if (!r) return;
    if (act === 'save') {
      if (r.t === 'p' && !(r.n >= 2)) { toast('Intervalo deve ser inteiro ≥ 2'); return; }
      r.ok = true; toast(kind === 'ret' ? 'Retirada salva' : 'Aporte salvo');
    } else if (act === 'edit') r.ok = false;
    else if (act === 'del') { if (!(await uiConfirm(kind === 'ret' ? 'Apagar esta retirada?' : 'Apagar este aporte?', { ok: 'Apagar', danger: true }))) return; arr.splice(+i, 1); toast(kind === 'ret' ? 'Retirada apagada' : 'Aporte apagado'); }
    if (kind === 'ret') st.ret.sort((a, b) => a.m - b.m);
    save(); renderRet(); renderEx(); applyMode(); compute();
  });
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { } };
  let rows = [], shownRows = PAGE_ROWS, hist = null, histT = '', modRows = false;

  const m2a = (m) => (Math.pow(1 + m / 100, 12) - 1) * 100;
  const a2m = (a) => (Math.pow(1 + a / 100, 1 / 12) - 1) * 100;
  const fmtIn = (v, d) => (v === '' || v == null) ? '' : nf(d).format(v);

  function fill() {
    el('pvIni').value = fmtIn(st.ini, 2); el('pvAp').value = fmtIn(st.ap, 2);
    el('pvDm').value = fmtIn(st.dm, 3); el('pvDa').value = fmtIn(st.da, 2); el('pvTx').value = st.txc ? fmtIn(st.tx, 2) : fmtIn(10, 2); el('pvTx').disabled = !st.txc; el('pvTxAuto').checked = !st.txc;
    el('pvRm').value = fmtIn(st.rm, 3); el('pvRa').value = fmtIn(st.ra, 2);
    el('pvTicker').value = MULTI[st.ticker] || st.ticker || ''; el('pvProj').value = st.proj || '';
    renderRet(); renderEx(); applyMode();
  }
  const deb = (fn, ms = 150) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };
  const liveCompute = deb(() => { compute(); save(); });
  function bind(id, f, pair, pd) {
    const i = el(id);
    i.addEventListener('input', () => { f(parseBR(i.value)); if (pair) el(pair).value = fmtIn(st[pd[0]], pd[1]); liveCompute(); });
    i.addEventListener('change', () => { f(parseBR(i.value)); save(); setTimeout(() => { fill(); compute(); }, 0); });
  }
  bind('pvIni', v => st.ini = Math.max(0, v)); bind('pvTx', v => st.tx = Math.max(0, Math.min(100, v)));
  el('pvTxAuto').addEventListener('change', () => { st.txc = !el('pvTxAuto').checked; save(); fill(); compute(); if (st.txc) el('pvTx').focus(); }); bind('pvAp', v => st.ap = Math.max(0, v));
  bind('pvDm', v => { st.dm = v; st.da = m2a(v); }, 'pvDa', ['da', 2]); bind('pvDa', v => { st.da = v; st.dm = a2m(v); }, 'pvDm', ['dm', 3]);
  bind('pvRm', v => { st.rm = v; st.ra = m2a(v); }, 'pvRa', ['ra', 2]); bind('pvRa', v => { st.ra = v; st.rm = a2m(v); }, 'pvRm', ['rm', 3]);
  // 1º toque seleciona tudo (digitar substitui); toque seguinte posiciona o cursor normalmente
  document.querySelector('[data-tabpane="previsao"]').addEventListener('focusin', (e) => {
    const t = e.target; if (!t.matches('input.pv-in:not(.ud-in)')) return;  // datas: calendário do site (ui.js)
    try { t.select(); } catch (er) { } t.dataset.fsel = '1';
    setTimeout(() => { if (t.dataset.fsel) { try { t.select(); } catch (er) { } } }, 0);
  });
  // o mouseup/toque que deu o foco não pode desfazer a seleção; os seguintes sim
  document.querySelector('[data-tabpane="previsao"]').addEventListener('mouseup', (e) => {
    const t = e.target; if (t.dataset && t.dataset.fsel) { e.preventDefault(); delete t.dataset.fsel; }
  });
  document.querySelector('[data-tabpane="previsao"]').addEventListener('keydown', (e) => { if (e.target.dataset) delete e.target.dataset.fsel; });

  // Retiradas
  // Retiradas extraordinárias: t = 'm' (mensal, vale até a próxima/0), 'u' (única), 'p' (por período, a cada n meses)
  const RTT = [['m', 'Retirada mensal'], ['u', 'Retirada única'], ['p', 'Retirada por período']];
  function renderRet() {
    const box = el('pvRet');
    if (!st.ret.length) { box.innerHTML = '<p class="text-xs text-slate-500">Nenhuma retirada extra. Toque em <b>+</b> para adicionar.</p>'; return; }
    const rTxt = (r) => (r.t || 'm') === 'm' ? (r.v > 0 ? `Retirada mensal de ${brl.format(r.v)} a partir do mês <b>${r.m}</b>` : `Encerrar retiradas mensais a partir do mês <b>${r.m}</b>`)
      : r.t === 'u' ? `Retirada única de ${brl.format(r.v)} no mês <b>${r.m}</b>` : `Retirada de ${brl.format(r.v)} a cada ${r.n} meses a partir do mês <b>${r.m}</b>`;
    box.innerHTML = st.ret.map((r, i) => r.ok ? `<div class="pv-saved" data-i="${i}"><span>${rTxt(r)}</span>
        <button type="button" class="pv-lnk" data-rowact="ret:edit:${i}">Editar</button><button type="button" class="pv-lnk dan" data-rowact="ret:del:${i}">Apagar</button></div>`
      : `<div class="pv-ex-row" data-i="${i}">
      <select data-f="t" aria-label="Tipo">${RTT.map(([k, l]) => `<option value="${k}"${(r.t || 'm') === k ? ' selected' : ''}>${l}</option>`).join('')}</select>
      <label class="pv-mini">R$<input inputmode="decimal" class="pv-in" style="width:7em" data-f="v" value="${fmtIn(r.v, 2)}"></label>
      <label class="pv-mini">mês<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="m" value="${r.m || ''}"></label>
      ${r.t === 'p' ? `<label class="pv-mini">a cada<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="n" value="${r.n || ''}">meses</label>` : ''}
      <button type="button" class="pv-x" data-del="${i}" aria-label="Remover retirada">✕</button>
      <button type="button" class="pv-ok" data-rowact="ret:save:${i}">Retirada</button>
      ${r.t === 'p' && !(r.n >= 2) ? '<span class="text-[11px] text-rose-300 basis-full">Intervalo deve ser um número inteiro de meses ≥ 2.</span>' : ''}</div>`).join('');
  }
  function setRet(e, final) {
    const row = e.target.closest('[data-i]'); if (!row) return;
    const r = st.ret[+row.dataset.i], f = e.target.dataset.f, raw = e.target.value; if (!r || !f) return;
    if (f === 't') { r.t = raw; if (r.t === 'p' && !r.n) r.n = 12; save(); renderRet(); compute(); return; }
    if (f === 'v') r.v = Math.max(0, parseBR(raw));
    if (f === 'm') r.m = Math.max(1, Math.min(MAXM, Math.round(parseBR(raw)) || 1));
    if (f === 'n') { const n = Number(String(raw).replace(',', '.')); r.n = Number.isInteger(n) && n >= 2 ? n : null; }
    save(); liveCompute(); if (final && f === 'n' && r.n >= 2) row.querySelector('.text-rose-300')?.remove();
  }
  el('pvRet').addEventListener('input', (e) => { if (e.target.tagName === 'INPUT') setRet(e, false); });
  el('pvRet').addEventListener('change', (e) => setRet(e, true));
  el('pvRet').addEventListener('click', (e) => {
    const b = e.target.closest('[data-del]'); if (!b) return;
    st.ret.splice(+b.dataset.del, 1); fill(); compute(); save();
  });
  el('pvAddRet').addEventListener('click', () => {
    const last = st.ret[st.ret.length - 1];
    st.ret.push({ t: 'm', v: 0, m: last ? Math.min(MAXM, last.m + 12) : 180, ok: false }); fill(); save();
    const ins = el('pvRet').querySelectorAll('input[data-f="v"]'); ins[ins.length - 1]?.focus();
  });
  // Aportes extraordinários: t = 'm' (mensal, substitui), 'u' (único), 'p' (por período, a cada n meses)
  const EXT = [['m', 'Aporte mensal'], ['u', 'Aporte único'], ['p', 'Aporte por período']];
  function renderEx() {
    const box = el('pvEx');
    if (!st.ex.length) { box.innerHTML = '<p class="text-xs text-slate-500">Nenhum aporte extra. Toque em <b>+</b> para adicionar.</p>'; return; }
    const exTxt = (r) => r.t === 'm' ? (r.v > 0 ? `Aporte mensal de ${brl.format(r.v)} a partir do mês <b>${r.m}</b>` : `Encerrar aportes a partir do mês <b>${r.m}</b>`)
      : r.t === 'u' ? `Aporte único de ${brl.format(r.v)} no mês <b>${r.m}</b>` : `${brl.format(r.v)} a cada ${r.n} meses a partir do mês <b>${r.m}</b>`;
    box.innerHTML = st.ex.map((r, i) => r.ok ? `<div class="pv-saved" data-x="${i}"><span>${exTxt(r)}</span>
        <button type="button" class="pv-lnk" data-rowact="ex:edit:${i}">Editar</button><button type="button" class="pv-lnk dan" data-rowact="ex:del:${i}">Apagar</button></div>` : `<div class="pv-ex-row" data-x="${i}">
      <select data-f="t" aria-label="Tipo">${EXT.map(([k, l]) => `<option value="${k}"${r.t === k ? ' selected' : ''}>${l}</option>`).join('')}</select>
      <label class="pv-mini">R$<input inputmode="decimal" class="pv-in" style="width:7em" data-f="v" value="${fmtIn(r.v, 2)}"></label>
      <label class="pv-mini">mês<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="m" value="${r.m || ''}"></label>
      ${r.t === 'p' ? `<label class="pv-mini">a cada<input inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.6em" data-f="n" value="${r.n || ''}">meses</label>` : ''}
      <button type="button" class="pv-x" data-xdel="${i}" aria-label="Remover aporte">✕</button>
      <button type="button" class="pv-ok" data-rowact="ex:save:${i}">Aporte</button>
      ${r.t === 'p' && !(r.n >= 2) ? '<span class="text-[11px] text-rose-300 basis-full">Intervalo deve ser um número inteiro de meses ≥ 2.</span>' : ''}</div>`).join('');
  }
  function setEx(e, final) {
    const row = e.target.closest('[data-x]'); if (!row) return;
    const r = st.ex[+row.dataset.x], f = e.target.dataset.f, raw = e.target.value;
    if (f === 't') { r.t = raw; if (r.t === 'p' && !r.n) r.n = 12; save(); renderEx(); compute(); return; }
    if (f === 'v') r.v = Math.max(0, parseBR(raw));
    if (f === 'm') r.m = Math.max(1, Math.min(MAXM, Math.round(parseBR(raw)) || 1));
    if (f === 'n') { const n = Number(String(raw).replace(',', '.')); r.n = Number.isInteger(n) && n >= 2 ? n : null; }
    save(); liveCompute(); if (final && f === 'n') { const row2 = e.target.closest('[data-x]'); const warn = row2.querySelector('.text-rose-300'); if (warn && r.n >= 2) warn.remove(); }
  }
  el('pvEx').addEventListener('input', (e) => { if (e.target.tagName === 'INPUT') setEx(e, false); });
  el('pvEx').addEventListener('change', (e) => setEx(e, true));
  el('pvEx').addEventListener('click', (e) => { const b = e.target.closest('[data-xdel]'); if (!b) return; st.ex.splice(+b.dataset.xdel, 1); save(); renderEx(); compute(); });
  el('pvAddEx').addEventListener('click', () => { st.ex.push({ t: 'u', v: 0, m: 12, ok: false }); save(); renderEx(); const ins = el('pvEx').querySelectorAll('input[data-f="v"]'); ins[ins.length - 1]?.focus(); });
  function apAt(m, w) {
    let reg = st.ap, extra = 0;
    for (const r of st.ex.filter(x => x.ok).sort((a, b) => a.m - b.m)) {
      if (r.t === 'm' && r.m <= m) reg = r.v;
      else if (r.t === 'u' && r.m === m) extra += r.v;
      else if (r.t === 'p' && r.n >= 2 && m >= r.m && (m - r.m) % r.n === 0) extra += r.v;
    }
    return { reg: w > 0 ? 0 : reg, extra };
  }
  // mensal: vale do mês indicado até a próxima mensal (0 encerra) e zera o aporte; única/período somam no mês
  const wAt = (m) => { let reg = 0, extra = 0;
    for (const r of st.ret.filter(x => x.ok).sort((a, b) => a.m - b.m)) { const t = r.t || 'm';
      if (t === 'm' && r.m <= m) reg = r.v; else if (t === 'u' && r.m === m) extra += r.v; else if (t === 'p' && r.n >= 2 && m >= r.m && (m - r.m) % r.n === 0) extra += r.v; }
    return { reg, extra }; };

  // Ação (modo histórico)
  function tickerList() { }
  // Combobox com busca a cada caractere (ticker, nome, setor, descrição; sem acento)
  window.pvCombo = (i, f) => combo(i, f);
  function combo(inp, onPick, all) {
    const box = document.createElement('div'); box.className = 'pv-combo hidden'; box.setAttribute('role', 'listbox');
    inp.parentNode.style.position = 'relative'; inp.parentNode.appendChild(box);
    inp.setAttribute('autocomplete', 'off'); inp.setAttribute('role', 'combobox');
    const rowsAll = () => (typeof state !== 'undefined' && state.data && state.country === 'br') ? state.data.rows : [];
    function show() {
      const q = norm(inp.value.trim());
      const list = rowsAll().filter(r => !q || r.ticker.toLowerCase().startsWith(q) || (r._s || norm(r.ticker + ' ' + r.nome)).includes(q))
        .map(r => [r, searchRank(r, q)]).sort((a, b) => a[1] - b[1]).map(x => x[0]).slice(0, 30);
      const tod = all ? [['*', 'Todos', 'todas as empresas'], ['top5', '5 maiores de cada setor', 'por valor de mercado']].filter(x => !q || norm(x[1]).includes(q))
        .map(([v, l, d]) => `<button type="button" data-t="${v}"><b>${l}</b><span class="pv-cn">${d}</span></button>`).join('') : '';
      box.innerHTML = tod + (list.length ? list.map(r => `<button type="button" data-t="${r.ticker}"><b>${r.ticker}</b><span class="pv-cn">${esc(r.nome || '')}</span><span class="pv-cs">${esc(r.macro || r.setor || '')}</span></button>`).join('')
        : '<div class="pv-cempty">Nenhuma empresa encontrada.</div>');
      box.classList.remove('hidden');
    }
    inp.addEventListener('input', show); inp.addEventListener('focus', show);
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const b = box.querySelector('[data-t]'); if (b) { e.preventDefault(); pick(b.dataset.t); } } if (e.key === 'Escape') box.classList.add('hidden'); });
    box.addEventListener('mousedown', (e) => e.preventDefault());
    box.addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (b) pick(b.dataset.t); });
    inp.addEventListener('blur', () => setTimeout(() => box.classList.add('hidden'), 150));
    function pick(t) { inp.value = MULTI[t] || t; box.classList.add('hidden'); inp.blur(); onPick(t); }
  }
  async function loadHist() {
    const t = multi() ? st.ticker : (st.ticker || '').toUpperCase();
    applyMode();
    if (!t) { hist = null; histT = ''; compute(); return; }
    if (multi()) {  // Todos / 5 maiores de cada setor: período = meses com dados dos modelos
      hist = null; histT = t; const M = await modMeta(); if (!M) { compute(); return; }
      for (const id of ['pvDi', 'pvDf']) { el(id).min = M.ini; el(id).max = M.fim; }
      if (!st.di || st.di < M.ini || st.di > M.fim) st.di = M.ini;
      if (st.df && (st.df > M.fim || st.df < st.di)) st.df = M.fim;  // vazia = Hoje (em andamento)
      el('pvDi').value = st.di; el('pvDf').value = st.df; el('pvOldest').dataset.tip = `Modelos com dados de ${dataBR(M.ini)} a ${dataBR(M.fim)}.`;
      el('pvStatus').textContent = ''; compute(); save(); return;
    }
    if (histT === t && hist) { compute(); return; }
    el('pvStatus').textContent = 'Carregando histórico de ' + t + '…';
    try {
      const r = await fetch('/api/history/' + encodeURIComponent(t) + '?kind=m');
      const d = await r.json(); if (!r.ok || !d.t || d.t.length < 2) throw new Error(d.error || 'sem histórico');
      hist = d; histT = t;
      const ym = (s) => { const x = new Date(s * 1000); return x.getUTCFullYear() + '-' + String(x.getUTCMonth() + 1).padStart(2, '0'); };
      hist.ym = d.t.map(ym); hist.divm = {}; hist.jcpm = {};  // JCP identificado pela B3 (últimos ~12 meses): 15% retido na fonte
      for (const [ts, v, lb] of d.div || []) { const k = ym(ts); hist.divm[k] = (hist.divm[k] || 0) + v; if (/JRS|JUROS|JCP/i.test(lb || '')) hist.jcpm[k] = (hist.jcpm[k] || 0) + v; }
      const lo = hist.ym[0], hi = hist.ym[hist.ym.length - 1];
      for (const id of ['pvDi', 'pvDf']) { el(id).min = lo; el(id).max = hi; }
      if (!st.di || st.di < lo || st.di > hi) st.di = lo;
      if (st.df && (st.df > hi || st.df < st.di)) st.df = hi;  // vazia = Hoje (em andamento)
      el('pvDi').value = st.di; el('pvDf').value = st.df;
      el('pvOldest').dataset.tip = `Data mais antiga disponível para ${t}: ${dataBR(lo)} (fonte: ${d.source})`;
      el('pvStatus').textContent = '';
    } catch (e) { hist = null; el('pvStatus').textContent = 'Histórico indisponível para ' + t + ': ' + e.message; }
    compute(); save();
  }
  // trocou ação ou datas: o campo Mês volta a vazio para a tabela começar no mês 1
  const resetMes = () => { st.mes = ''; const m = el('pvMes'); if (m) m.value = ''; };
  combo(el('pvTicker'), (t) => { resetMes(); st.ticker = t; st.proj = ''; projS = null; el('pvProj').value = ''; st.di = st.df = ''; loadHist(); loadProj(); save(); }, true);
  combo(el('pvProj'), (t) => { resetMes(); st.proj = t; st.ticker = ''; el('pvTicker').value = ''; loadHist(); loadProj(); save(); });
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
      el('pvProjInfo').innerHTML = `<div class="pv-pstats"><span>Rentab. <b>${P3.format(projS.rm)}% a.m.</b> · ${P2.format(m2a(projS.rm))}% a.a.</span>
        <span>Dividendos <b>${P3.format(projS.dm)}% a.m.</b> · ${P2.format(m2a(projS.dm))}% a.a.</span>
        <span class="text-slate-500">Período: ${dataBR(yms[i0])} a ${dataBR(yms[i1])} (${n} meses${n < 120 ? ', menos de 10 anos' : ''}) · ${esc(d.source)}</span></div>`;
    } catch (e) { projS = null; el('pvProjInfo').textContent = 'Histórico indisponível para ' + t + ': ' + e.message; }
    applyMode(); compute();
  }
  function applyMode() {
    const P = !!st.proj, T = !!st.ticker && !P;
    el('pvMode').textContent = P ? 'Projeção com médias de ' + st.proj : T ? 'Simulação histórica com ' + (multi() ? MULTI[st.ticker].toLowerCase() : st.ticker) : 'Projeção futura';
    ['pvDm', 'pvDa', 'pvRm', 'pvRa'].forEach(id => el(id).disabled = P || T);  // só com empresa (Projeções ou E se eu tivesse investido?) vêm do histórico; sem empresa, editáveis
    el('pvTicker').disabled = P; el('pvClearT').disabled = P; el('pvProj').disabled = T; el('pvClearP').disabled = T;
    el('pvRetBox').classList.remove('pv-off');
    el('pvRetBox').querySelectorAll('input,button,select').forEach(x => x.disabled = false);
    el('pvDates').classList.toggle('hidden', !T);
    el('pvMod').disabled = P;
  }
  el('pvClearT').addEventListener('click', () => { resetMes(); st.ticker = ''; el('pvTicker').value = ''; loadHist(); save(); });
  for (const id of ['pvDi', 'pvDf']) el(id).addEventListener('change', () => {
    let v = el(id).value; const lo = el(id).min, hi = el(id).max;
    if (v && lo && v < lo) v = lo; if (v && hi && v > hi) v = hi;
    resetMes(); if (id === 'pvDi') st.di = v; else st.df = v; st.mperC = true;  // datas novas: o chip delas fica marcado no Período
    if (st.df && st.di && st.df < st.di) st.df = st.di;
    el('pvDi').value = st.di; el('pvDf').value = st.df; compute(); save();
    if (st.ticker === '*' && st.di && !st.df && window.gSim) askSim();  // Todos + data inicial + data final vazia: oferece o Grupo simulação
  });
  // Todos + Data final já em "Hoje (em andamento)": tocar no campo pergunta antes (Sim = cria o grupo; Não = abre o seletor de data)
  el('pvDf')._udBefore = async () => {  // ui.js → uiDateField: true = abre o calendário do site
    if (!(st.ticker === '*' && st.di && !st.df && window.gSim)) return true;
    if (await uiConfirm(simTxt(), { title: 'Deseja criar grupo de simulação?', ok: 'Sim', cancel: 'Não' })) { askSim(true); return false; }
    return true;
  };
  // Grupo simulação: uma carteira por modelo desde a data inicial, com o Valor inicial; continua sozinho até hoje (aba Grupos)
  // o grupo guarda as entradas da Previsão: valor inicial, aporte mensal, aportes e retiradas extraordinários (servidor: modelos.sim_flows)
  const simRows = (L) => L.filter(x => x.ok).map(x => ({ t: x.t || 'm', m: x.m, v: x.v, n: x.n || 0 }));
  const simTxt = () => `Cada modelo começa com ${brl.format(st.ini)} em ${dataBR(st.di)}${st.ap > 0 ? ` e recebe ${brl.format(st.ap)} por mês` : ''}${simRows(st.ex).length ? ', mais os aportes extraordinários' : ''}${simRows(st.ret).length ? ', com as retiradas extraordinárias' : ''}, e segue as próprias regras até hoje, atualizando sozinho. O grupo fica na aba Grupos.`;
  async function askSim(sure) {
    if (!sure && document.querySelector('.umod')) return;  // já há um diálogo aberto
    if (!(st.ini > 0)) { uiAlert('Para criar o Grupo simulação, preencha o Valor inicial.'); return; }
    if (!sure && !(await uiConfirm(simTxt(), { title: 'Criar grupo de simulação?', ok: 'Criar', cancel: 'Agora não' }))) return;
    let name = 'Grupo simulação';
    if (gSim.has(name)) {
      const nx = gSim.next(name), c = await uiChoose(`Já existe "${name}".`, [{ label: 'Substituir', value: 'rep' }, { label: `Criar "${esc(nx)}"`, value: 'new' }]);
      if (!c) return; if (c === 'new') name = nx;
    }
    gSim.create(name, { di: st.di, v0: st.ini, ap: st.ap || 0, ex: simRows(st.ex), ret: simRows(st.ret) });
    uiToast(`"${name}" criado na aba Grupos`);
  }
  el('pvOldest').addEventListener('click', () => { const t = el('pvOldest').dataset.tip; if (t) uiAlert(t); });

  // Cálculo. Convenção (igual à planilha): mês 1 = valor inicial; no mês n,
  // rentabilidade = patrimônio_sem(n-1) × r ; dividendo = patrimônio_com(n-1) × d (reinvestido na linha "com").
  // aporte e retirada de cada mês (mês 1 = valor inicial): mesma regra da tabela e dos modelos
  function flows(n) {
    const ap = [st.ini + apAt(1, 0).extra], w = [0];
    for (let m = 2; m <= n; m++) { const W = wAt(m), W0 = W.reg + W.extra, A = apAt(m, 0); ap.push(W0 > 0 ? 0 : A.reg + A.extra); w.push(W0); }
    return { ap, w };
  }
  function compute() {
    if (peek) { peek.dirty = true; return; }  // mês a mês aberto: recalcula ao tocar em Voltar
    rows = []; modRows = false;
    if (st.mod && st.ticker && !st.proj) { runModels(); return; }
    showTabs(false);
    if (multi()) { el('pvStatus').textContent = `Escolha um modelo em Modelos para ver ${MULTI[st.ticker]}.`; renderAll(); return; }
    let steps = null; // [{r, d, label}]
    if (st.proj && !projS) { renderAll(); return; }
    if (!st.proj && st.ticker && hist) {
      const i0 = Math.max(0, hist.ym.indexOf(st.di)), i1e = hist.ym.indexOf(st.df), i1 = i1e < 0 ? hist.ym.length - 1 : i1e;
      steps = [];
      for (let i = i0 + 1; i <= i1; i++) { const dv = hist.divm[hist.ym[i]] || 0; steps.push({ r: hist.c[i] / hist.c[i - 1] - 1, d: dv / hist.c[i - 1], j: dv ? (hist.jcpm[hist.ym[i]] || 0) / dv : 0, ym: hist.ym[i] }); }
      steps.unshift({ ym: hist.ym[i0] });
    } else if (!st.proj && st.ticker) { renderAll(); return; }
    const n = steps ? steps.length : MAXM;
    const r0 = (projS && st.proj ? projS.rm : st.rm) / 100, d0 = (projS && st.proj ? projS.dm : st.dm) / 100;
    const FL = flows(n);
    let sem = FL.ap[0], com = FL.ap[0], apT = FL.ap[0], divT = 0;
    rows.push({ m: 1, ap: FL.ap[0], apT, rent: 0, div: 0, tax: 0, divT: 0, sem, com, w: 0, ym: steps?.[0].ym });
    for (let m = 2; m <= n; m++) {
      const r = steps ? steps[m - 1].r : r0, d = steps ? steps[m - 1].d : d0;
      const ap = FL.ap[m - 1], w = FL.w[m - 1]; // mês com retirada: aporte 0 (inclusive extraordinários) e sai a retirada inteira
      const jf = steps ? steps[m - 1].j || 0 : 0;  // parte JCP do provento do mês: 15% sempre (automático); dividendo: 10% só acima de R$ 50 mil
      const rent = sem * r, div = com * d, rentC = com * r, tax = st.txc ? div * (st.tx || 0) / 100 : div * jf * 0.15 + (div * (1 - jf) > 50000 ? div * (1 - jf) * 0.10 : 0); // reinveste o líquido do imposto
      sem = Math.max(0, sem + rent + ap - w);
      com = Math.max(0, com + rentC + div - tax + ap - w);
      apT += ap; divT += div - tax;
      rows.push({ m, ap, apT, rent, div, tax, divT, sem, com, w, ym: steps?.[m - 1].ym });
    }
    shownRows = PAGE_ROWS; renderAll();
  }

  const COLS = [['m', 'Mês', 'pv-c-m'], ['va', 'Valorização total', 'pv-c-va'], ['ap', 'Aporte mensal', 'pv-c-ap'], ['apT', 'Aporte total', 'pv-c-ap'], ['pa', '% Aporte', 'pv-c-ap'], ['rent', 'Rentabilidade mensal', 'pv-c-r'],
    ['div', 'Dividendo mensal', 'pv-c-d'], ['tax', 'Imposto', 'pv-c-tx'], ['divT', 'Dividendos total', 'pv-c-d'], ['sem', 'Rentabilidade total', 'pv-c-r'], ['pv', 'Rentabilidade %', 'pv-c-r'],
    ['com', 'Patrimônio total<br>com dividendos', 'pv-c-d'], ['pd', '% Dividendos', 'pv-c-d']];
  const hasW = () => st.ret.some(r => r.ok && r.v > 0);
  const cols = () => (hasW() ? COLS.concat([['w', 'Retirada', 'pv-c-w']]) : COLS).concat(modRows ? [['pos', 'Posição', 'pv-c-m'], ['cdb', `CDB ${glossBtn('CDB no mês a mês')}`, 'pv-c-t']] : []);
  const pcell = (r, k) => { const p = pvPcts(r.apT, r.sem, r.com)[k]; if (p == null) return ['—', '']; const cls = k === 'pa' ? (p > 1 ? 'neg' : 'pos') : (p < 0 ? 'neg' : p > 0 ? 'pos' : ''); return [F2.format(p * 100) + '%', cls]; };
  const cell = (r, k) => ['va', 'pa', 'pv', 'pd'].includes(k) ? pcell(r, k)[0] : k === 'm' ? (r.ym ? `${r.m}<span class="pv-ym">${dataBR(r.ym)}</span>` : r.m) : (k === 'pos' ? esc(r.pos) : k === 'cdb' ? cdbCell(r) : k === 'w' && !r.w ? '–' : brl.format(r[k]));
  // CDB no mês a mês: saldo parado no CDB no fim do mês e, embaixo, a variação no mês (dica: quanto foi rendimento do CDB)
  const cdbCell = (r) => { if (r.cdb == null) return '–'; const dv = r.dcdb || 0, s = Math.abs(dv) < 0.005 ? '' : `<span class="pv-dc ${dv < 0 ? 'neg' : 'pos'}">${dv < 0 ? '−' : '+'}${brl.format(Math.abs(dv))}</span>`;
    return `<span title="${esc(`Rendimento do CDB no mês: ${brl.format(r.cj || 0)}. O resto da variação vem de aportes, proventos, compras, vendas, retiradas e imposto.`)}">${brl.format(r.cdb)}</span>${s}`; };
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
      el('pvSumBody').querySelector('td').innerHTML = `<input id="pvMes" inputmode="numeric" maxlength="3" class="pv-in text-center" style="width:3.4em;display:block;margin:0 auto" placeholder="1" value="${st.mes || ''}" aria-label="Mês">`;
      const upd = deb(() => { st.mes = String(Math.max(0, Math.round(parseBR(el('pvMes').value))) || ''); shownRows = PAGE_ROWS; save(); renderAll(); });
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
  function syncWidths() { }

  // ---------- Modelos (regras e simulação no servidor: modelos.py; sinais semanais: snapshot modelos) ----------
  let MM = null, mmP = null, des = null, sel = null, seq = 0;
  const modMeta = () => mmP || (mmP = fetch('/api/modelos').then(r => r.json()).then(d => { if (d && d.modelos) { MM = d; fillMod(); return d; } mmP = null; return null; }).catch(() => { mmP = null; return null; }));
  const modName = (id) => ((MM && MM.modelos.find(m => m.id === id)) || {}).n || id;
  function fillMod() {
    const o = [['', 'Sem modelo']].concat(MM ? MM.modelos.map(m => [m.id, m.n]) : []).concat([['*', 'Todos']]);
    el('pvMod').innerHTML = o.map(([v, l]) => `<option value="${v}"${v === st.mod ? ' selected' : ''}>${esc(l)}</option>`).join('');
    el('pvModInfo').textContent = MM ? `Dados de ${dataBR(MM.ini)} a ${dataBR(MM.fim)}.` : '';
  }
  el('pvMod').addEventListener('change', () => { st.mod = el('pvMod').value; sel = null; peek = null; des = null; modDl(); st.pvt = multi() || st.mod === '*' ? 'des' : 'tab'; save(); applyMode(); compute(); });
  el('pvModI').addEventListener('click', () => infoSection('Modelos da Previsão'));
  // ⬇ planilha (.csv) do modelo escolhido (em Todos não aparece): o Desempenho e o mês a mês que estão na tela, nos mesmos valores
  const modDl = () => el('pvModD').classList.toggle('hidden', !st.mod || isAll() || !des);
  el('pvModD').addEventListener('click', () => {
    if (!des) return;
    const L = [[`Modelo: ${modName(st.mod)}`], [`Empresa: ${MULTI[st.ticker] || st.ticker}`, `Período: ${dataBR(des.ini)} a ${dataBR(des.fim)}`, `Aportado: ${brl.format(des.apT)}`], [],
      ['Desempenho'], ['Tipo', 'Nome', 'Empresa', 'Valor final (R$)', 'Rendimento (%)', 'TIR anual (%)', 'Imposto (R$)', 'Compras', 'Vendas']];
    for (const r of des.rows) L.push([r.k === 'g' ? 'Grupo (rodízio)' : r.k === 'r' ? 'Referência' : 'Modelo', r.k === 'g' ? `${modName(r.m)} · ${r.n}` : r.k === 'r' ? r.t : modName(r.m),
      r.k === 'g' ? (r.t || []).join(', ') : r.k === 'r' ? '' : r.t, r.v, r.pct, r.ra, r.ir, r.c, r.s]);
    if (rows.length && modRows) {
      L.push([], [`Mês a mês: ${el('pvMode').textContent}`], ['Mês', 'Aporte (R$)', 'Aporte total (R$)', 'Retirada (R$)', 'Rentabilidade no mês (R$)', 'Proventos no mês (R$)', 'Imposto no mês (R$)', 'Patrimônio sem proventos (R$)', 'Patrimônio com proventos (R$)', 'No CDB (R$)', 'Posição']);
      for (const x of rows) L.push([x.ym, x.ap, x.apT, x.w, x.rent, x.div, x.tax, x.sem, x.com, x.cdb, x.pos]);
    }
    saveCsv(L, `modelo_${st.mod}_${(MULTI[st.ticker] ? st.ticker : st.ticker || 'empresa').replace(/[^\w]/g, '')}_${new Date().toISOString().slice(0, 10)}.csv`);
  });
  // Comparar → Modelos: tocar numa empresa abre aqui a simulação mês a mês (mesmo valor inicial, aporte e período)
  // abre com os valores do Comparar sem mudar o card Modelos nem a empresa da Previsão; "‹ Voltar ao Comparar" chama o.back
  window.pvOpen = (o) => {
    const n = Math.max(2, months(o.di, o.df).length);
    peek = { t: o.t, m: o.m, body: { di: o.di, df: o.df, ap: [o.ini].concat(Array(n - 1).fill(o.ap)), w: [], tx: null }, back: { fn: o.back } };
    showTab('previsao'); document.querySelector('[data-pvsub="rent"]')?.click(); showTabs(true); loadTab(true);
  };
  // mês a mês aberto por um toque (Desempenho, Por empresa, Comparar): não muda o card Modelos nem a empresa; "‹ Voltar" restaura a tela anterior
  let peek = null;
  function openPeek(t, m) { peek = { t, m, back: { pvt: st.pvt, y: window.scrollY } }; showTabs(true); loadTab(true); }
  el('pvBack').addEventListener('click', () => {
    const p = peek; if (!p) return; peek = null;
    if (p.dirty) compute(); else { showTabs(true); applyMode(); if (!isAll()) loadTab(); }
    if (p.back.fn) { p.back.fn(); return; }
    st.pvt = p.back.pvt; showTabs(true); requestAnimationFrame(() => window.scrollTo(0, p.back.y));
  });
  const isAll = () => st.mod === '*';  // card Modelos em Todos: Tabela = comparação dos modelos (sem mês a mês)
  function showTabs(on) {
    const pk = on && !!peek;
    el('pvTabs').classList.toggle('hidden', !on || pk); el('pvBack').classList.toggle('hidden', !pk);
    el('pvPer').classList.toggle('hidden', !on || pk);
    if (pk) el('pvBack').textContent = peek.back.fn ? '‹ Voltar ao Comparar' : '‹ Voltar';
    const d = on && !pk && st.pvt === 'des', c = on && !pk && !d && isAll();
    el('pvTabs').querySelectorAll('[data-pvt]').forEach(b => b.classList.toggle('on', b.dataset.pvt === (on ? st.pvt : 'tab')));
    el('pvDes').classList.toggle('hidden', !d); el('pvCmp').classList.toggle('hidden', !c);
    ['pvSumScroll', 'pvMainScroll'].forEach(id => el(id).classList.toggle('hidden', d || c));
    el('pvCount').parentNode.classList.toggle('hidden', d || c);
    el('pvModF').classList.toggle('hidden', !(on && isAll()));
    if (!on || c || pk) el('pvTabMsg').classList.add('hidden');
  }
  el('pvTabs').addEventListener('click', (e) => { const b = e.target.closest('[data-pvt]'); if (!b) return; st.pvt = b.dataset.pvt; save(); showTabs(true); });
  const months = (a, b) => { const out = []; let [y, m] = a.split('-').map(Number); const [y2, m2] = b.split('-').map(Number);
    while (y < y2 || (y === y2 && m <= m2)) { out.push(`${y}-${String(m).padStart(2, '0')}`); if (++m > 12) { m = 1; y++; } } return out; };
  // Período dos modelos (faixa acima de Tabela/Desempenho): últimos N anos até o Fim, limitado aos dados; 0 = todo o período
  const PER = [5, 10, 15, 20, 25, 30, 0];
  if (!PER.includes(st.mper)) st.mper = 10;
  const perDi = (df) => { if (!st.mper) return MM.ini; const [y, m] = df.split('-').map(Number); const d = `${y - st.mper}-${String(m).padStart(2, '0')}`; return d > MM.ini ? d : MM.ini; };
  // chip temporário com as datas do "E se eu tivesse investido?" (ex.: 03/2025 a hoje): aparece quando a Data inicial é posterior à
  // mais antiga ou há Data final; fica marcado ao mudar as datas (st.mperC) e filtra exatamente esse intervalo; some quando as datas voltam ao padrão
  const perC = () => !!MM && (!!st.df || (!!st.di && st.di > (el('pvDi').min || MM.ini)));
  const perCOn = () => perC() && st.mperC !== false;
  function perHtml(d) {
    const info = d ? `<span class="pv-per-i">${dataBR(d.ini)} a ${dataBR(d.fim)} · aportado ${brl.format(d.apT)}${isAll() ? ' por empresa' : ''}</span>` : '';
    const c = perC() ? `<button type="button" data-mper="c" class="pv-per-c${perCOn() ? ' on' : ''}">${dataBR(st.di > MM.ini ? st.di : MM.ini)} a ${st.df ? dataBR(st.df) : 'hoje'}</button>` : '';
    el('pvPer').innerHTML = `<span class="pv-per-l">Período</span>${c}${PER.map(n => `<button type="button" data-mper="${n}" class="${n === st.mper && !perCOn() ? 'on' : ''}">${n ? n + ' anos' : 'Todo período'}</button>`).join('')}${info}`;
  }
  el('pvPer').addEventListener('click', (e) => { const b = e.target.closest('[data-mper]'); if (!b) return; if (b.dataset.mper === 'c') st.mperC = true; else { st.mper = +b.dataset.mper; st.mperC = false; } save(); perHtml(null); runModels(); });
  function modBody() {
    let df = st.df && st.df < MM.fim ? st.df : MM.fim, di = perDi(df);
    if (perCOn()) { di = st.di > MM.ini ? st.di : MM.ini; if (di > df) di = df; }  // chip das datas: exatamente o intervalo escolhido
    const f = flows(Math.max(2, months(di, df).length));
    return { di, df, ap: f.ap, w: f.w, tx: st.txc ? st.tx : null };
  }
  async function post(b, url = '/api/modelos') {
    for (let k = 0; k < 4; k++) {
      const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
      if (r.status === 202) { await new Promise(z => setTimeout(z, 3000)); continue; }
      const d = await r.json(); if (!r.ok || d.error) throw new Error(d.error || 'erro'); return d;
    }
    throw new Error('servidor carregando os dados; tente de novo');
  }
  async function runModels() {
    const my = ++seq; showTabs(true); el('pvStatus').textContent = ''; perHtml(null);
    if (!(await modMeta())) { el('pvDes').innerHTML = '<p class="pvd-note">Modelos indisponíveis agora.</p>'; return; }
    if (my !== seq) return;
    if (isAll()) { runAll(my); return; }
    el('pvDes').innerHTML = loaderHTML('Simulando os modelos…');
    const b = modBody(); const G = typeof userGroups === 'function' ? userGroups() : [];
    try {
      const d = await post(Object.assign({ ticker: st.ticker, modelo: st.mod, grupos: G, fav: [...FAVS] }, b)); if (my !== seq) return;
      des = d; perHtml(d); modDl(); const emp = d.rows.filter(r => r.k === 'a');
      if (!multi()) sel = sel && emp.some(r => r.t === sel.t && r.m === sel.m) ? sel : { t: st.ticker, m: st.mod === '*' ? emp[0]?.m : st.mod };
      else if (sel && !emp.some(r => r.t === sel.t && r.m === sel.m)) sel = null;
      el('pvDes').innerHTML = desHtml(d); loadTab();
    } catch (e) { if (my === seq) { el('pvDes').innerHTML = `<p class="pvd-note">Não foi possível simular: ${esc(e.message)}</p>`; rows = []; renderAll(); } }
  }
  // ---- card Modelos em Todos: uma simulação de todos os modelos (modelos.compare, a mesma do Comparar) ----
  let CM = null, dsk = 'pct', dsd = -1, pg = 0;
  if (!st.cv) st.cv = 'media'; if (!(st.pgs > 0)) st.pgs = 240; if (typeof st.mf !== 'string') st.mf = '';
  const CV = [['media', 'Média'], ['emp', 'Por empresa'], ['pos', 'Colocações'], ['con', 'Consistência'], ['grp', 'Grupos (rodízio)']];
  const NM = () => Object.fromEntries((MM ? MM.modelos : []).map(m => [m.id, m.n]));
  function fillModF() {
    el('pvModF').innerHTML = [['', 'Todos os modelos']].concat(MM ? MM.modelos.map(m => [m.id, m.n]) : []).map(([v, l]) => `<option value="${v}"${v === st.mf ? ' selected' : ''}>${esc(l)}</option>`).join('');
  }
  el('pvModF').addEventListener('change', () => { st.mf = el('pvModF').value; pg = 0; save(); drawCmp(); drawDes(); });
  async function runAll(my) {
    fillModF();
    el('pvCmp').innerHTML = el('pvDes').innerHTML = loaderHTML('Simulando os modelos…');
    const b = modBody(), u = st.ticker === '*' ? 'all' : st.ticker === 'top5' ? 'top5' : 'sel';
    try {
      const d = await post(Object.assign({ u, t: u === 'sel' ? [st.ticker] : [], rod: true, grupos: typeof userGroups === 'function' ? userGroups() : [], fav: [...FAVS] }, b), '/api/modelos/comparar');
      if (my !== seq) return;
      CM = d; perHtml(d); drawCmp(); drawDes();
    } catch (e) { if (my === seq) el('pvCmp').innerHTML = el('pvDes').innerHTML = `<p class="pvd-note">Não foi possível simular: ${esc(e.message)}</p>`; }
  }
  const note = (extra) => modInfo(CM, { extra });
  const isRef = (id) => !!((MM && MM.modelos.find(m => m.id === id)) || {}).ref;
  // CDB e Ouro: só o nome com ⓘ (explicação no Glossário); six = tabela com coluna Modelo (Desempenho em Todos)
  const refRows = (L, six) => L.map(r => `<tr class="tap pvd-ref" data-pvsel="|${r.m}"><td><b>${esc(r.t)}</b>${refInfo(r.m)}</td>${six ? '<td></td>' : ''}<td data-v="${r.ra ?? -1e9}">${pcl(r.ra)}</td><td data-v="${r.pct ?? -1e9}">${pcl(r.pct)}</td><td data-v="${r.v ?? -1e9}">${r.v == null ? '—' : brl.format(r.v)}</td><td data-v="0">—</td><td data-v="0">—</td><td data-v="-1">—</td></tr>`).join('');
  function drawCmp() {
    if (!CM) return;
    const nm = NM(), g = (CM.g || []).filter(x => !st.mf || x.m === st.mf);
    const grp = `<div class="pv-scroll"><table class="gtab" data-srt><thead><tr>${thSort('Grupo', 'n')}${thSort('Rendimento', 'p')}${thSort('Valor final', 'v')}${thSort('IR vendas', 'i')}${thSort('IR proventos', 'j')}${thSort('Compras / vendas', 'c')}</tr></thead><tbody>${g.map(r => `<tr class="pvd-g">
      <td data-v="${esc(r.n)}"><div class="pvd-a"><span><b>${esc(r.n)}</b><span class="pvd-m">${esc(nm[r.m] || r.m)} · rodízio</span></span><button type="button" class="pv-i" data-pvg2="${CM.g.indexOf(r)}" aria-label="Histórico de movimentação">ⓘ</button></div></td>
      <td data-v="${r.pct}">${pcl(r.pct)}</td><td data-v="${r.v}">${brl.format(r.v)}</td><td data-v="${r.irv}">${brl.format(r.irv)}</td><td data-v="${r.ir - r.irv}">${brl.format(r.ir - r.irv)}</td><td data-v="${r.c}">${r.c} / ${r.s}</td></tr>`).join('') || '<tr><td colspan="6">Nenhum grupo para este modelo.</td></tr>'}</tbody></table></div>`;
    el('pvCmp').innerHTML = `<div class="gt-tabs" role="tablist">${CV.map(([k, l]) => `<button type="button" data-cv="${k}" class="${st.cv === k ? 'on' : ''}">${l}</button>`).join('')}</div>
      ${st.cv === 'grp' ? grp : modTables(CM, st.cv, nm, st.mf)}${note(st.cv === 'emp' ? 'toque num valor para ver o mês a mês daquela empresa e modelo' : '')}`;
  }
  function drawDes() {  // Desempenho: cada empresa uma vez por modelo, ordenável, em páginas
    if (!CM) return;
    const nm = NM(), L = [];
    // CDB e Ouro: uma linha cada (não dependem da empresa), ordenadas junto com os modelos; Barsi fora do método (null) não entra
    (CM.ref || []).forEach(r => { if (r.pct != null && (!isRef(st.mf) || r.m === st.mf)) L.push({ t: r.t, m: r.m, n: '', ra: r.ra, pct: r.pct, v: r.v, irv: 0, ird: 0, c: -1, s: -1, ref: 1 }); });
    CM.m.forEach((m, i) => { if (isRef(m) || (st.mf && st.mf !== m)) return; CM.t.forEach((t, j) => { if (CM.p[i][j] != null) L.push({ t, m, n: nm[m] || m, ra: CM.ra ? CM.ra[i][j] : null, pct: CM.p[i][j], v: CM.v[i][j], irv: CM.irv[i][j], ird: CM.ir[i][j] - CM.irv[i][j], c: CM.c[i][j], s: CM.s[i][j] }); }); });
    L.sort((a, b) => (typeof a[dsk] === 'string' ? a[dsk].localeCompare(b[dsk], 'pt-BR') : (a[dsk] ?? -1e9) - (b[dsk] ?? -1e9)) * dsd);
    const np = Math.max(1, Math.ceil(L.length / st.pgs)); pg = Math.min(pg, np - 1);
    const rows = L.slice(pg * st.pgs, (pg + 1) * st.pgs);
    // paginação numa linha só, no fim da tabela
    const pager = `<div class="pv-pg"><span class="pv-pgi">Linhas por página <select class="sel" data-pgs>${[240, 500, 1000, 2000, 5000].map(n => `<option${n === st.pgs ? ' selected' : ''}>${n}</option>`).join('')}</select></span>
      <span class="pv-pgi"><button type="button" class="gbtn" data-pg="-1"${pg ? '' : ' disabled'} aria-label="Página anterior">‹</button><span>${pg + 1} de ${np}</span><button type="button" class="gbtn" data-pg="1"${pg < np - 1 ? '' : ' disabled'} aria-label="Próxima página">›</button></span></div>`;
    el('pvDes').innerHTML = `<div class="pv-scroll"><table class="gtab"><thead><tr>${[['Ativo', 't'], ['Modelo', 'n'], [`TIR anual ${glossBtn('TIR anual')}`, 'ra'], ['Rendimento', 'pct'], ['Valor final', 'v'], ['IR vendas', 'irv'], ['IR proventos', 'ird'], ['Compras / vendas', 'c']].map(([l, k]) => thSort(l, k, dsk, dsd)).join('')}</tr></thead>
      <tbody>${rows.map(r => r.ref ? refRows([r], 1) : `<tr class="tap" data-pvsel="${esc(r.t)}|${r.m}"><td><b>${esc(r.t)}</b></td><td>${esc(r.n)}</td><td>${pcl(r.ra)}</td><td>${pcl(r.pct)}</td><td>${brl.format(r.v)}</td><td>${brl.format(r.irv)}</td><td>${brl.format(r.ird)}</td><td>${r.c} / ${r.s}</td></tr>`).join('')}</tbody></table></div>${pager}${note(`${F0.format(L.length)} linhas; toque numa linha para ver o mês a mês ${glossBtn('Desempenho (melhores casos)')}`)}`;
  }
  // abre uma empresa com um modelo (mês a mês na aba Tabela)
  const openOne = (t, m) => openPeek(t, m);
  el('pvCmp').addEventListener('click', (e) => {
    if (e.target.closest('[data-gl]')) return;  // ⓘ (Glossário) não abre a linha
    const v = e.target.closest('[data-cv]'); if (v) { st.cv = v.dataset.cv; save(); drawCmp(); return; }
    const g = e.target.closest('[data-pvg2]'); if (g && CM) { const r = CM.g[+g.dataset.pvg2]; uiAlert('', { title: `${esc(r.n)} · ${esc(modName(r.m))}`, html: groupHtml(r) }); return; }
    const mo = e.target.closest('[data-mo]'); if (mo) { const [t, m] = mo.dataset.mo.split('|'); openOne(t, m); }  // células e referências (CDB, Ouro)
  });
  const pcl = (v) => v == null ? '—' : `<span class="${v < 0 ? 'dn' : 'up'}">${pc(v)}</span>`;
  function desHtml(d) {
    const tr = d.rows.map((r, i) => {
      if (r.k === 'r') return refRows([r]);
      const g = r.k === 'g', on = !g && sel && sel.t === r.t && sel.m === r.m;
      const nm = g ? `<div class="pvd-a"><span><b>${esc(r.n)}</b><span class="pvd-m">${esc(modName(r.m))} · rodízio</span></span><button type="button" class="pv-i" data-pvg="${i}" aria-label="Histórico de movimentação">ⓘ</button></div>`
        : `<b>${esc(r.t)}</b><span class="pvd-m">${esc(modName(r.m))}${r.fora ? ' · fora do método (setor não perene ou sem dividendos regulares)' : ''}</span>`;
      return `<tr class="${g ? 'pvd-g' : 'tap'}${on ? ' sel' : ''}" ${g ? '' : `data-pvsel="${esc(r.t)}|${esc(r.m)}"`}><td data-v="${esc(r.n || r.t)}">${nm}</td><td data-v="${r.ra ?? -1e9}">${pcl(r.ra)}</td><td data-v="${r.pct ?? -1e9}">${pcl(r.pct)}</td><td data-v="${r.v}">${brl.format(r.v)}</td><td data-v="${r.irv ?? 0}">${brl.format(r.irv ?? 0)}</td><td data-v="${r.ir - (r.irv ?? 0)}">${brl.format(r.ir - (r.irv ?? 0))}</td><td data-v="${r.c}">${r.c} / ${r.s}</td></tr>`;
    }).join('');
    return `<div class="pv-scroll"><table class="gtab" data-srt><thead><tr>${thSort('Ativo', 'a')}${thSort(`TIR anual ${glossBtn('TIR anual')}`, 'ra')}${thSort('Rendimento', 'p')}${thSort('Valor final', 'v')}${thSort('IR vendas', 'i')}${thSort('IR proventos', 'j')}${thSort('Compras / vendas', 'c')}</tr></thead><tbody>${tr}</tbody></table></div>
      ${modInfo(d, { extra: 'toque numa linha para ver o mês a mês' })}`;
  }
  el('pvDes').addEventListener('change', (e) => { if (e.target.matches('[data-pgs]')) { st.pgs = +e.target.value; pg = 0; save(); drawDes(); } });
  el('pvDes').addEventListener('click', (e) => {
    if (e.target.closest('[data-gl]')) return;  // ⓘ (Glossário) não abre a linha
    if (isAll() && CM) {
      const th = e.target.closest('th[data-sc]'); if (th && !th.closest('table[data-srt]')) { const k = th.dataset.sc; dsd = dsk === k ? -dsd : (k === 't' || k === 'n' ? 1 : -1); dsk = k; drawDes(); return; }
      const pb = e.target.closest('[data-pg]'); if (pb) { pg += +pb.dataset.pg; drawDes(); el('pvDes').scrollIntoView({ block: 'start' }); return; }
      const tr = e.target.closest('[data-pvsel]'); if (tr) { const [t, m] = tr.dataset.pvsel.split('|'); openOne(t, m); return; }
    }
    const gi = e.target.closest('[data-pvg]');
    if (gi && des) { const r = des.rows[+gi.dataset.pvg]; uiAlert('', { title: `${esc(r.n)} · ${esc(modName(r.m))}`, html: groupHtml(r) }); return; }
    const t = e.target.closest('[data-pvsel]'); if (!t) return;
    const [tk, m] = t.dataset.pvsel.split('|'); resetMes();
    if (tk) { sel = { t: tk, m }; el('pvDes').querySelectorAll('tr.sel').forEach(x => x.classList.remove('sel')); t.classList.add('sel'); }
    openPeek(tk, m);
  });
  // movimentações (rodízio e Grupo simulação): uma linha por evento (compra, venda, aporte, provento, aplicação/resgate do CDI,
  // retirada, imposto), mais recentes primeiro; mostra MOV_PG por vez ("Mostrar mais" acrescenta sem redesenhar o resto)
  window.pvGroupHtml = groupHtml;
  const MOV_PG = 50, movStore = {}; let movSeq = 0;
  // Tipo | Origem/destino (ticker; CDI na aplicação/resgate) | Valor ação (preço na hora; — sem ação) | Qtd. de ações | Valor
  const MOV_N = { compra: 'Compra', venda: 'Venda', aporte: 'Aporte', provento: 'Provento', cdi_ap: 'Aplicação', cdi_res: 'Resgate', retirada: 'Retirada', imposto: 'Imposto' };
  const MOV_H = '<thead><tr><th>Data</th><th>Tipo</th><th>Origem/<br>destino</th><th>Valor<br>ação</th><th>Qtd. de<br>ações</th><th>Valor</th></tr></thead>';
  const movRow = (x) => {
    const cdi = x.k === 'cdi_ap' || x.k === 'cdi_res', neg = x.k === 'compra' || x.k === 'retirada' || x.k === 'imposto';
    const org = x.t ? `<b>${esc(x.t)}</b>` : cdi ? 'CDI' : '—', det = x.x ? `<br><span class="pvd-note">${esc(x.x)}</span>` : '';
    const px = x.p != null && !cdi && x.k !== 'imposto' && x.k !== 'aporte' ? brl.format(x.p) : '—';
    return `<tr class="mv-${x.k}"><td>${dataBR(x.d).replace(/\/(\d\d)(\d\d)$/, '/$2')}</td><td>${MOV_N[x.k] || esc(x.k)}</td><td class="mv-o">${org}${det}</td><td>${px}</td>` +
      `<td>${x.q != null ? F0.format(x.q) : '—'}</td><td class="${neg || cdi ? '' : 'up'}">${brl.format(x.v)}${x.pct != null ? `<br><span class="${x.pct < 0 ? 'dn' : 'up'}">${pc(x.pct)}</span>` : ''}</td></tr>`;
  };
  // mov: as que vieram (mais antigas primeiro); nmov: total; src {di, v0, m}: o resto vem do servidor em páginas (/api/modelos/simmov)
  const movInfo = (o) => `Mostrando ${F0.format(o.n)} de ${F0.format(o.N)} movimentaç${o.N === 1 ? 'ão' : 'ões'}`;
  function movHtml(mov, nmov, src) {
    const L = (mov || []).slice().reverse(), id = 'm' + (++movSeq), N = Math.max(nmov || 0, L.length), o = { L, N, n: Math.min(MOV_PG, L.length), src };
    movStore[id] = o; for (const k of Object.keys(movStore)) if (k !== id && Object.keys(movStore).length > 8) delete movStore[k];  // só os últimos modais
    const more = o.n < N && (src || o.n < L.length) ? `<button type="button" class="btn mv-more" data-movmore="${id}">Mostrar mais ${Math.min(MOV_PG, N - o.n)}</button>` : '';
    return `<div class="mvwrap"><table class="gtab mvtab">${MOV_H}<tbody id="${id}">${L.slice(0, o.n).map(movRow).join('') || '<tr><td colspan="6">Nenhuma movimentação.</td></tr>'}</tbody></table></div>` +
      `<p class="pvd-note" id="${id}i">${movInfo(o)}${!src && N > L.length ? ` (as ${F0.format(L.length - 1)} mais recentes e o aporte inicial)` : ''}</p>${more}`;
  }
  window.pvMovHtml = movHtml; window.pvMovRow = movRow; window.pvMovHead = MOV_H;
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-movmore]'); if (!b || b.disabled) return;
    const id = b.dataset.movmore, o = movStore[id], tb = document.getElementById(id); if (!o || !tb) return;
    if (o.n + MOV_PG > o.L.length && o.src && o.L.length < o.N) {  // busca a próxima página no servidor
      b.disabled = true; b.textContent = 'Carregando…';
      try {
        const r = await fetch('/api/modelos/simmov', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ off: o.L.length, n: MOV_PG * 2 }, o.src)) });
        const d = await r.json(); if (!r.ok || !d.mov) throw new Error(d.error || 'erro');
        o.L.push(...d.mov); o.N = d.nmov;
      } catch (err) { b.disabled = false; b.textContent = 'Tentar de novo'; return; }
      b.disabled = false;
    }
    const k = Math.min(o.L.length, o.n + MOV_PG); tb.insertAdjacentHTML('beforeend', o.L.slice(o.n, k).map(movRow).join('')); o.n = k;
    const inf = document.getElementById(id + 'i'); if (inf) inf.textContent = movInfo(o);
    if (o.n >= o.N || (!o.src && o.n >= o.L.length)) b.remove(); else b.textContent = `Mostrar mais ${Math.min(MOV_PG, o.N - o.n)}`;
  });
  // blocos do resumo: [rótulo, valor, detalhe, classe] (classe: 'big up'/'big dn' para o rendimento, 'w2' ocupa a linha no celular)
  const tiles = (L) => `<div class="sumg">${L.filter(Boolean).map(([l, v, d, c = '']) => `<div class="sumt${/w2/.test(c) ? ' w2' : ''}"><span class="l">${l}</span><span class="v ${c.replace('w2', '')}">${v}</span>${d ? `<span class="s">${d}</span>` : ''}</div>`).join('')}</div>`;
  const pclr = (x) => x == null ? '' : x < 0 ? 'dn' : 'up';
  // posição: preço médio (total pago com custos ÷ ações; vendas não mudam) e resultado = preço de agora × preço médio; toque abre o histórico da empresa
  const SIM_POS = 30;
  const simPos = (x, src, i) => `<tr class="tap${i >= SIM_POS ? ' hidden' : ''}" data-simpos="${esc(x.t)}"${src ? ` data-src="${esc(JSON.stringify(src))}"` : ''}><td><b>${esc(x.t)}</b></td><td>${F0.format(x.q)}</td><td>${brl.format(x.pm != null ? x.pm : x.p)}</td><td>${brl.format(x.v)}</td><td class="${x.pct < 0 ? 'dn' : 'up'}">${x.pct == null ? '—' : pc(x.pct)}</td></tr>`;
  function simHtml(r) {
    const src = r.src, pos = r.pos.map((x, i) => simPos(x, src, i)).join('');
    return tiles([['Aportado', brl.format(r.apT != null ? r.apT : r.v0), r.apT != null && r.apT !== r.v0 ? `${brl.format(r.v0)} iniciais${r.ap > 0 ? ` + ${brl.format(r.ap)}/mês` : ''}${r.wS > 0 ? ` − ${brl.format(r.wS)} retirados` : ''}` : 'desde ' + dataBR(r.d0)], ['Hoje', brl.format(r.v), `<span class="pct ${pclr(r.pct)}">${pc(r.pct)}</span>`],
        ['Compras / vendas', `${F0.format(r.c)} <span class="s2">/</span> ${F0.format(r.s)}`], ['Imposto', brl.format(r.ir)],
        ['Posição', `${r.np} empresa${r.np === 1 ? '' : 's'}`, `+ ${brl.format(r.cash)} no CDB`, 'w2']]) + `<p class="sumd">dados até ${dataBR(r.d1)}</p>
      <p class="pvd-note">Toque numa empresa para ver as compras, vendas e proventos dela.</p>
      <table class="gtab simpos"><thead><tr><th>Ativo</th><th>Ações</th><th>Preço<br>médio</th><th>Valor</th><th>Resultado</th></tr></thead><tbody>${pos || '<tr><td colspan="5">Tudo no CDB.</td></tr>'}</tbody></table>
      ${r.pos.length > SIM_POS ? `<button type="button" class="btn mv-more" data-simall="1">Mostrar todas (${r.pos.length})</button>` : ''}
      ${movHtml(r.mov, r.nmov, src)}`;
  }
  // uma empresa dentro de um modelo do Grupo simulação (/api/modelos/simmov com tk): resumo e o histórico dela (compras, vendas, proventos)
  async function simCoLoad(src, tk) {
    const r = await fetch('/api/modelos/simmov', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ tk }, src)) });
    const d = await r.json(); if (!r.ok || !d.mov) throw new Error(d.error || 'Não foi possível carregar agora.'); return d;
  }
  function simCoHtml(d) {
    const p = d.pos;
    return tiles(p ? [['Ações', F0.format(p.q)], ['Preço médio', brl.format(p.pm), 'pago com custos ÷ ações'], ['Investido', brl.format(p.inv)], ['Valor atual', brl.format(p.v), `${brl.format(p.p)}/ação`],
        ['Resultado', `<span class="pct ${pclr(p.pct)}">${p.pct == null ? '—' : pc(p.pct)}</span>`, brl.format(p.v - p.inv)], ['Proventos recebidos', brl.format(d.dv), 'líquidos']]
      : [['Ações', '0', 'vendida (fora da carteira)'], ['Proventos recebidos', brl.format(d.dv), 'líquidos']]) + movHtml(d.mov.slice().reverse(), d.nmov);
  }
  window.pvSimCompany = async (src, tk, title) => {
    uiAlert('', { title, html: `<div id="simCo">${typeof loaderHTML === 'function' ? loaderHTML('Carregando…') : 'Carregando…'}</div>` });
    try { const d = await simCoLoad(src, tk), b = document.getElementById('simCo'); if (b) b.innerHTML = simCoHtml(d); }
    catch (e) { const b = document.getElementById('simCo'); if (b) b.textContent = e.message; }
  };
  document.addEventListener('click', async (e) => {
    const all = e.target.closest('[data-simall]');
    if (all) { const t = all.previousElementSibling && all.parentElement.querySelector('table.simpos'); if (t) t.querySelectorAll('tr.hidden').forEach(x => x.classList.remove('hidden')); all.remove(); return; }
    const tr = e.target.closest('tr[data-simpos]'); if (!tr || !tr.dataset.src) return;
    const nx = tr.nextElementSibling; if (nx && nx.classList.contains('simdet')) { nx.remove(); tr.classList.remove('sel'); return; }  // 2º toque fecha
    tr.classList.add('sel'); tr.insertAdjacentHTML('afterend', '<tr class="gdet simdet"><td colspan="5"><p class="pvd-note">Carregando…</p></td></tr>');
    const td = tr.nextElementSibling.firstElementChild;
    try { td.innerHTML = simCoHtml(await simCoLoad(JSON.parse(tr.dataset.src), tr.dataset.simpos)); } catch (err) { td.innerHTML = `<p class="pvd-note">${esc(err.message)}</p>`; }
  });
  function groupHtml(r) {
    if (r.sim) return simHtml(r);
    const h = r.hist, sem = (x) => `${F0.format(x)} sem. (~${F0.format(x / 4.35)} meses)`;
    const emp = h.emp.map(x => `<tr><td><b>${esc(x.t)}</b></td><td>${x.c}</td><td>${sem(x.sem)}</td><td class="${x.res < 0 ? 'dn' : 'up'}">${brl.format(x.res)}</td><td>${brl.format(x.ir)}</td></tr>`).join('');
    return tiles([['Rendimento', pc(r.pct), null, 'big ' + pclr(r.pct)], ['Valor final', brl.format(r.v)], ['Compras / vendas', `${F0.format(r.c)} <span class="s2">/</span> ${F0.format(r.s)}`],
        ['Trocas diretas', F0.format(h.trocas), 'entre empresas'], ['No CDB', F2.format(h.cdb) + '%', 'do tempo'], ['Maior queda', F2.format(h.dd) + '%', null, h.dd < 0 ? 'dn' : ''], ['Imposto', brl.format(r.ir), null, 'w2']]) + `
      <p class="pvd-note">Empresas do grupo: ${esc(r.t.join(', '))}. Tempo médio = semanas com a ação antes de vender; resultado inclui os proventos.</p>
      <table class="gtab"><thead><tr><th>Ativo</th><th>Compras</th><th>Tempo médio</th><th>Resultado</th><th>Imposto</th></tr></thead><tbody>${emp || '<tr><td colspan="5">Nenhuma compra no período.</td></tr>'}</tbody></table>
      ${movHtml(h.mov, h.nmov)}`;
  }
  async function loadTab(top) {
    const my = seq, S0 = peek || sel;
    if (!S0 || !S0.m) { rows = []; modRows = false; renderAll(); el('pvTabMsg').textContent = 'Toque numa empresa em Desempenho para ver o mês a mês.'; el('pvTabMsg').classList.toggle('hidden', st.pvt !== 'tab'); return; }
    el('pvTabMsg').classList.add('hidden');
    try {
      await modMeta(); const b = (peek && peek.body) || modBody(), d = await post(Object.assign({ tab: { t: S0.t, m: S0.m } }, b)); if ((!peek && my !== seq) || (peek || sel) !== S0) return;
      let apT = 0, ps = 0, pd = 0, pt = 0, pc0 = 0, pv0 = 0, pcd = 0;
      rows = d.tab.map((x, q) => {
        const ap = b.ap[q] || 0, w = b.w[q] || 0; apT += ap;
        const ops = [x.c > pc0 && 'compra', x.s > pv0 && 'venda'].filter(Boolean).join(' e ');
        const o = { m: q + 1, ym: x.ym, ap, apT, w, rent: q ? x.sem - ps - ap + w : 0, div: x.div - pd, tax: x.tax - pt, divT: x.div, sem: x.sem, com: x.com,
          pos: (S0.m !== '' ? x.pos : '') + (ops ? ' · ' + ops : ''), cdb: x.cdb, cj: x.cj, dcdb: x.cdb == null ? 0 : x.cdb - pcd };
        pcd = x.cdb || 0; ps = x.sem; pd = x.div; pt = x.tax; pc0 = x.c; pv0 = x.s; return o;
      });
      modRows = true; el('pvMode').textContent = `Simulação histórica com ${S0.t ? S0.t + ' · ' : ''}${modName(S0.m)}${peek && peek.body ? ' (valores do Comparar)' : ''}`;
    } catch (e) { rows = []; modRows = false; el('pvTabMsg').textContent = 'Tabela indisponível: ' + e.message; el('pvTabMsg').classList.remove('hidden'); }
    shownRows = PAGE_ROWS; renderAll();
    if (top && peek === S0) requestAnimationFrame(() => el('pvBack').scrollIntoView({ block: 'start' }));
  }

  el('pvMoreBtn').addEventListener('click', () => { shownRows += PAGE_ROWS; renderAll(); });

  let inited = false;
  document.addEventListener('tabshow', (e) => {
    if (e.detail !== 'previsao') return;
    if (rows.length) setTimeout(syncWidths, 0);
    tickerList();
    if (!inited) { inited = true; fill(); modMeta(); loadHist(); if (st.proj) loadProj(); }
  });
  if (!document.querySelector('[data-tabpane="previsao"]').classList.contains('hidden')) { inited = true; fill(); modMeta(); loadHist(); if (st.proj) loadProj(); }
})();

}
