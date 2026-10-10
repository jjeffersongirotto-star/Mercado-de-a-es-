// ---------- Grupos (localStorage + exportar/importar .json) ----------
(function () {
  const KEY = 'screenerB3.grupos.v1';
  const $g = (s) => document.querySelector(s);
  const escH = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let groups = (() => { try { const g = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(g) ? g : []; } catch (e) { return []; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(groups)); } catch (e) { uiAlert('Não foi possível salvar no navegador.'); } };
  state.selSet = new Set(); state.selMode = false; state.group = null;
  let editing = null, viewing = null;

  const VKEY = 'screenerB3.ordsetor.v1';
  try { const v = JSON.parse(localStorage.getItem(VKEY) || '{}'); state.ord2 = v.ord2 || ''; state.sector = v.sector || 'Todos'; } catch (e) { state.ord2 = ''; state.sector = 'Todos'; }
  const ORD = [['', 'Padrão (barra de filtros)'], ['valmerc:-1', 'Valor de mercado: maior → menor'], ['valmerc:1', 'Valor de mercado: menor → maior'],
    ['preco:-1', 'Preço da ação: maior → menor'], ['preco:1', 'Preço da ação: menor → maior'], ['var:-1', 'Alta do dia: maior → menor'], ['var:1', 'Alta do dia: menor → maior']];
  const toolsOld = () => `<div class="gtools"><label>Ordenar<select id="gOrd">${ORD.map(([v, l]) => `<option value="${v}"${v === state.ord2 ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
    <label>Setor<select id="gSec">${['Todos'].concat(SECTORS).map(x => `<option${x === state.sector ? ' selected' : ''}>${escH(x)}</option>`).join('')}</select></label></div>`;
  const tools = () => '';
  state.ord2 = '';
  $g('#gSec').innerHTML = ['Todos'].concat(SECTORS).map(x => `<option${x === state.sector ? ' selected' : ''}>${escH(x)}</option>`).join('');
  document.addEventListener('change', (e) => {
    if (e.target.id !== 'gOrd' && e.target.id !== 'gSec') return;
    if (e.target.id === 'gOrd') state.ord2 = e.target.value; else state.sector = e.target.value;
    try { localStorage.setItem(VKEY, JSON.stringify({ ord2: state.ord2, sector: state.sector })); } catch (er) { }
    if (state.data) apply();
  });
  document.addEventListener('input', (e) => {
    if (e.target.id !== 'gQ') return;
    $g('#q').value = e.target.value; if (state.data) apply();
  });
  function bar() {
    const b = $g('#gBar');
    if (state.selMode) {
      b.innerHTML = `<div class="gbar mb-2"><b class="text-emerald-300 text-sm">${state.selSet.size} selecionada(s)</b>
        <input id="gName" maxlength="40" placeholder="Nome do grupo" value="${escH(editing ? editing.name : '')}" class="flex-1 min-w-[140px] px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm">
        <button type="button" class="gbtn pri" data-g="save">Salvar</button><button type="button" class="gbtn" data-g="cancel">Cancelar</button>
        <input id="gQ" type="search" placeholder="Buscar empresa, setor ou atividade (ex.: gasol)…" value="${escH($g('#q').value)}" class="basis-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm"></div>${tools()}`;
    } else if (viewing) {
      b.innerHTML = `<div class="gbar mb-2"><b class="text-emerald-300">${escH(viewing.name)}</b><span class="text-xs text-slate-400">${viewing.tickers.length} empresa(s)${viewing.rank ? ' · ordem do ranking' : ''}</span>
        ${viewing.pre ? '' : `<button type="button" class="gbtn ml-auto" data-g="edit" data-n="${escH(viewing.name)}">Editar</button>`}
        <button type="button" class="gx ${viewing.pre ? 'ml-auto' : ''}" data-g="back" aria-label="Fechar grupo">✕</button></div>`;
    } else b.innerHTML = '';
  }
  function refresh() { bar(); if (typeof apply === 'function' && state.data) apply(); }
  function startSel(g) {
    editing = g || null; state.selMode = true; state.selSet = new Set(g ? g.tickers : []);
    viewing = null; state.group = null; markTab(); showTab('acoes'); refresh();
  }
  function stopSel() { state.selMode = false; editing = null; state.selSet = new Set(); refresh(); }
  function openGroup(g) { viewing = g; state.group = new Set(g.tickers); state.groupRank = g.rank ? new Map(g.tickers.map((t, i) => [t, i])) : null; state.selMode = false; showTab('acoes'); markTab(); refresh(); window.scrollTo(0, 0); }
  function markTab() { document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('on', viewing ? b.dataset.tab === 'grupos' : b.dataset.tab === 'acoes')); }

  document.addEventListener('change', (e) => {
    const c = e.target.closest('[data-gsel]'); if (!c) return;
    if (c.checked) state.selSet.add(c.dataset.gsel); else state.selSet.delete(c.dataset.gsel);
    const b = $g('#gBar b'); if (b) b.textContent = state.selSet.size + ' selecionada(s)';
  });
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-g]'); if (!b) return;
    const a = b.dataset.g, find = (n) => groups.find(g => g.name === n);
    if (a === 'new') startSel(null);
    else if (a === 'cancel') stopSel();
    else if (a === 'save') {
      const name = ($g('#gName').value || '').trim();
      if (!name) { uiAlert('Dê um nome ao grupo.'); $g('#gName').focus(); return; }
      if (!state.selSet.size) { uiAlert('Selecione pelo menos uma empresa.'); return; }
      const other = find(name);
      if (other && other !== editing && !(await uiConfirm(`Já existe um grupo "${name}". Substituir?`, { ok: 'Substituir', danger: true }))) return;
      groups = groups.filter(g => g !== other && g !== editing);
      groups.push({ name, tickers: [...state.selSet].sort(), updated: new Date().toISOString() });
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save();
      state.selMode = false; editing = null; state.selSet = new Set(); bar(); showTab('grupos');
    }
    else if (a === 'back') { viewing = null; state.group = null; state.groupRank = null; refresh(); showTab('grupos'); }
    else if (a === 'open') openGroup(find(b.dataset.n));
    else if (a === 'edit') startSel(find(b.dataset.n));
    else if (a === 'del') { const g = find(b.dataset.n); if (g && await uiConfirm(`Excluir o grupo "${g.name}"?`, { ok: 'Excluir', danger: true })) { groups = groups.filter(x => x !== g); save(); list(); } }
    else if (a === 'export') exportG();
    else if (a === 'import') $g('#gFile').click();
  });

  // ---------- Grupos pré-definidos (TOP 10, recalculados com os dados atuais) ----------
  let METRICS = null;
  const loadMetrics = async () => { if (METRICS) return METRICS; try { METRICS = (await (await fetch('/api/metrics')).json()).metrics || {}; } catch (e) { METRICS = {}; } return METRICS; };
  const F2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pc = (x) => (x > 0 ? '+' : '') + F2.format(x) + '%';
  const rowsAll = () => state.data ? state.data.rows : [];
  // grupos pré-definidos: só empresas com negociação média ≥ R$ 500 mil/dia (evita distorções de papéis sem liquidez)
  const rowsK = () => state.country === 'br' ? rowsAll().filter(r => ((r.v.vol30 ?? r.v.liq2m) || 0) >= 5e5) : rowsAll();
  const MX = (t) => (METRICS || {})[t] || {};
  const pctRank = (arr, key, asc) => { const s = arr.slice().sort((a, b) => asc ? key(a) - key(b) : key(b) - key(a)); const m = new Map(); s.forEach((r, i) => m.set(r, 1 - i / Math.max(1, s.length - 1))); return m; };
  const listDate = (r) => r.ipo || MX(r.ticker).ftd || null;
  window.isNova = (r) => { const d = listDate(r); return !!d && (Date.now() - Date.parse(d)) < 92 * 864e5; };
  const fmtD = (d) => d ? d.slice(8, 10) + '/' + d.slice(5, 7) + '/' + d.slice(0, 4) : '—';
  const PRE = [
    { id: 'valor', m: 1, name: 'Maior valorização', h: 'Valorização', per: true, calc: (n) => rowsK().filter(r => MX(r.ticker)['ret' + n] != null).map(r => [r, MX(r.ticker)['ret' + n]]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, pc(v), v]) },
    { id: 'rent', name: 'Maior rentabilidade', t: 'atual', h: 'Lucro/valor', calc: () => rowsK().filter(r => r.v.pl >= 2).map(r => [r, 100 / r.v.pl]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'dy', m: 1, name: 'Maiores pagadoras de dividendos', h: 'DY a.a.', per: true, calc: (n) => rowsK().map(r => [r, MX(r.ticker)['dy' + n] ?? (n === 1 ? r.v.dy : null)]).filter(x => x[1] > 0 && x[1] < 40).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'prov', m: 1, name: 'Mais proventos ao investidor', t: '12 meses', h: 'Proventos', calc: () => rowsK().map(r => [r, MX(r.ticker).prov12]).filter(x => x[1] > 0 && x[1] < 60).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'peq', m: 1, name: 'Pequenas e médias promissoras', t: 'atual', h: 'Nota', calc: () => {
      const c = rowsAll().filter(r => { const v = r.v; const liq = v.vol30 ?? v.liq2m; return v.valmerc >= 3e8 && v.valmerc <= 1e10 && v.lpa > 0 && v.roe >= 12 && (v.cresc5a > 0 || v.lucro5a > 0) && (v.dlebit == null || v.dlebit < 3) && liq >= 1e6; });
      const a = pctRank(c, r => r.v.roe), b = pctRank(c, r => r.v.lucro5a ?? -1e9), d = pctRank(c, r => r.v.pl > 0 ? 1 / r.v.pl : 0);
      return c.map(r => [r, (a.get(r) + b.get(r) + d.get(r)) / 3 * 100]).sort((x, y) => y[1] - x[1]).map(([r, v]) => [r, F2.format(v), v]); } },
    { id: 'magic', name: 'Magic Formula', t: 'atual', h: 'ROIC · EV/EBIT', calc: () => {
      const c = rowsK().filter(r => r.v.evebit >= 1 && r.v.roic != null && r.v.roic < 150);
      const r1 = new Map(c.slice().sort((a, b) => b.v.roic - a.v.roic).map((r, i) => [r, i])), r2 = new Map(c.slice().sort((a, b) => a.v.evebit - b.v.evebit).map((r, i) => [r, i]));
      return c.map(r => [r, r1.get(r) + r2.get(r)]).sort((a, b) => a[1] - b[1]).map(([r]) => [r, F2.format(r.v.roic) + '% · ' + F2.format(r.v.evebit)]); } },
    { id: 'graham', name: 'Baratas pelo Graham', t: 'atual', h: 'Desconto', calc: () => rowsK().filter(r => r.v.lpa > 0 && r.v.vpa > 0 && r.v.preco > 0 && r.v.pl >= 2).map(r => [r, (Math.sqrt(22.5 * r.v.lpa * r.v.vpa) / r.v.preco - 1) * 100]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'consist', m: 1, name: 'Pagadoras consistentes', t: 'últimos 5 anos', h: 'DY médio · CV', calc: () => rowsK().map(r => { const an = Object.values(MX(r.ticker).anual || {}); if (an.length < 5 || an.some(x => !(x > 0))) return null; const m = an.reduce((a, b) => a + b, 0) / an.length, sd = Math.sqrt(an.reduce((a, b) => a + (b - m) ** 2, 0) / an.length); return [r, sd / m, m]; }).filter(Boolean).sort((a, b) => a[1] - b[1] || b[2] - a[2]).map(([r, cv, m]) => [r, F2.format(m) + '% · ' + F2.format(cv)]) },
    { id: 'divida', name: 'Menos endividadas', t: 'atual', h: 'Dív.Líq/PL', calc: () => rowsK().filter(r => r.v.lpa > 0 && r.v.dlpl != null).map(r => [r, r.v.dlpl]).sort((a, b) => a[1] - b[1]).map(([r, v]) => [r, F2.format(v)]) },
    { id: 'quedas', m: 1, name: 'Maiores quedas', h: 'Variação', per: true, calc: (n) => rowsK().filter(r => MX(r.ticker)['ret' + n] != null).map(r => [r, MX(r.ticker)['ret' + n]]).filter(x => x[1] < 0).sort((a, b) => a[1] - b[1]).map(([r, v]) => [r, pc(v), v]) },
    { id: 'negoc', name: 'Mais negociadas', t: '30 dias', h: 'Giro/dia', calc: () => rowsK().filter(r => r.v.valmerc > 0 && (r.v.vol30 ?? r.v.liq2m) > 0).map(r => [r, (r.v.vol30 ?? r.v.liq2m) / r.v.valmerc * 100]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%']) },
    { id: 'novas', name: 'Novidades', t: 'listagens recentes', h: 'Listagem', calc: () => rowsAll().filter(r => listDate(r)).sort((a, b) => listDate(b).localeCompare(listDate(a))).map(r => [r, fmtD(listDate(r))]) },
  ];
  const preOk = (p) => state.country === 'br' || !p.m;
  const UKEY = 'screenerB3.gruposUI.v1';
  const ui = (() => { try { return JSON.parse(localStorage.getItem(UKEY) || '{}') || {}; } catch (e) { return {}; } })();
  ui.per = ui.per || {}; ui.order = ui.order || []; ui.gstar = ui.gstar || []; ui.fav = ui.fav || { tabs: [], assign: {}, tab: 'all', sort: 'preco' }; ui.fav.avg = ui.fav.avg || 1;
  const saveUI = () => { try { localStorage.setItem(UKEY, JSON.stringify(ui)); } catch (e) { } };
  const favList = () => rowsAll().filter(r => FAVS.has(r.ticker));
  const avgP = (r, n) => { const m = (MX(r.ticker).m10 || []).slice(-n); return m.length ? m.reduce((a, b) => a + b, 0) / m.length : null; };
  function favRows() {
    const f = ui.fav, s = f.sort || 'preco';
    let L = favList(); if (f.tab !== 'all' && f.tab !== 'prov') L = L.filter(r => f.assign[r.ticker] === f.tab);
    const key = (r) => s === 'preco' ? (r.v.preco ?? -1e9) : (MX(r.ticker)['ret' + s.slice(1)] ?? -1e9);
    return L.sort((a, b) => key(b) - key(a)).map(r => { const a = avgP(r, f.avg); return [r, a != null ? 'R$ ' + F2.format(a) : '—']; });
  }
  function tileIds() {
    const ids = ['fav'].concat(PRE.filter(preOk).map(p => 'pre:' + p.id), state.country === 'br' ? groups.map(g => 'user:' + g.name) : []);
    const ord = ui.order.filter(x => ids.includes(x) && x !== 'fav');
    const rest = ord.concat(ids.filter(x => x !== 'fav' && !ord.includes(x)));
    return ['fav'].concat(rest.filter(x => ui.gstar.includes(x)), rest.filter(x => !ui.gstar.includes(x)));
  }
  const priceCell = (r) => { const v = r.var; return `<td class="gc3">${r.v.preco != null ? F2.format(r.v.preco) : '—'}${v != null ? ` <span class="${v > 0 ? 'up' : v < 0 ? 'dn' : ''}">${v > 0 ? '+' : ''}${F2.format(v)}%</span>` : ''}</td>`; };
  const tbl = (rows, h, full) => `<table class="gtab"><thead><tr><th>Ativo</th><th>${escH(h)}</th><th>Preço · dia</th></tr></thead><tbody>${rows.map(([r, v]) => `<tr data-row="${escH(r.ticker)}"${full ? ' class="tap"' : ''}><td><b>${escH(r.ticker)}</b>${isNova(r) ? '<span class="nova">NOVA</span>' : ''}</td><td class="gc2">${escH(v)}</td>${priceCell(r)}</tr>`).join('')}</tbody></table>`;
  const preTitle = (p) => p.name + ' (' + (p.per ? ((ui.per[p.id] || 1) + ' ano' + ((ui.per[p.id] || 1) > 1 ? 's' : '')) : p.t) + ')';
  const perSel = (p) => p.per ? `<select class="gper" data-per="${p.id}" aria-label="Período">${[1, 2, 3, 4, 5].map(k => `<option value="${k}"${k === (ui.per[p.id] || 1) ? ' selected' : ''}>${k} ano${k > 1 ? 's' : ''}</option>`).join('')}</select>` : '';
  function favControls() {
    const f = ui.fav, tabs = [['all', 'Todos']].concat(f.tabs.map(t => [t.id, t.name]), [['prov', 'Proventos no ano']]), ut = f.tabs.find(t => t.id === f.tab);
    return `<div class="gt-tabs">${tabs.map(([k, l]) => `<button type="button" class="${f.tab === k ? 'on' : ''}" data-ftab="${k}">${escH(l)}</button>`).join('')}<button type="button" data-ftab="+" aria-label="Nova aba">＋</button>
      ${ut ? `<button type="button" data-fren="${ut.id}">Renomear</button><button type="button" data-fdel="${ut.id}" class="dan">Excluir aba</button>` : ''}
      ${f.tab !== 'prov' ? `<select class="gper" data-favg aria-label="Preço médio">${[1, 2, 3, 6, 9].map(n => `<option value="${n}"${f.avg === n ? ' selected' : ''}>Média ${n} ${n > 1 ? 'meses' : 'mês'}</option>`).join('')}</select>
      <select class="gper" data-fsort aria-label="Ordenar favoritos"><option value="preco"${f.sort === 'preco' ? ' selected' : ''}>Preço da ação</option>${[1, 2, 3, 4, 5].map(n => `<option value="v${n}"${f.sort === 'v' + n ? ' selected' : ''}>Maiores valorizações ${n} ano${n > 1 ? 's' : ''}</option>`).join('')}</select>` : ''}</div>`;
  }
  function favBody(full) {
    const f = ui.fav;
    if (f.tab === 'prov') {
      const L = favList().map(r => { const ev = MX(r.ticker).ytd || [], p = r.v.preco || MX(r.ticker).p || 0; return [r, ev, p]; });
      return L.length ? '<ul class="gt-list">' + L.map(([r, ev, p]) => `<li class="gp"><b>${escH(r.ticker)}</b><span class="gv">${ev.length ? ev.map(e => e[2] === 'provento' ? `${e[0]}: R$ ${F2.format(e[1])} (${F2.format(p ? e[1] / p * 100 : 0)}%)` : (e[2] === 'bonificação' ? `${e[0]}: bonificação ${F2.format((e[1] - 1) * 100)}%` : `${e[0]}: ${e[2]} ${F2.format(e[1])}:1`)).join(' · ') + ` — total ${F2.format(p ? ev.filter(e => e[2] === 'provento').reduce((a, e) => a + e[1], 0) / p * 100 : 0)}%` : 'sem proventos no ano'}</span></li>`).join('') + '</ul>' : '<p class="gt-empty">Nenhum favorito.</p>';
    }
    const R = favRows();
    if (!R.length) return '<p class="gt-empty">Toque na ☆ de uma empresa para favoritar.</p>';
    let html = tbl(R, 'Média ' + f.avg + (f.avg > 1 ? ' meses' : ' mês'), full);
    if (f.tabs.length && full) html += `<div class="gmvbox">${R.map(([r]) => `<label>${escH(r.ticker)} → <select class="gmv" data-mv="${r.ticker}"><option value="">—</option>${f.tabs.map(x => `<option value="${x.id}"${f.assign[r.ticker] === x.id ? ' selected' : ''}>${escH(x.name)}</option>`).join('')}</select></label>`).join('')}</div>`;
    return html;
  }
  function groupData(id) {
    if (id === 'fav') return { title: '★ Favoritos', n: favList().length };
    if (id.startsWith('pre:')) { const p = PRE.find(x => 'pre:' + x.id === id); return { title: preTitle(p), p, rows: p.calc(ui.per[p.id] || 1).slice(0, 10), h: p.h }; }
    const gg = groups.find(x => x.name === id.slice(5)); if (!gg) return null;
    const byT = new Map(rowsAll().map(r => [r.ticker, r]));
    return { title: gg.name, g: gg, rows: gg.tickers.map(t => byT.get(t)).filter(Boolean).map(r => [r, r.v.valmerc ? 'R$ ' + (r.v.valmerc / 1e9).toFixed(1).replace('.', ',') + ' bi' : '—']), h: 'Valor de mercado' };
  }
  const starB = (id) => id === 'fav' ? '' : `<button type="button" class="gstar${ui.gstar.includes(id) ? ' on' : ''}" data-gstar="${escH(id)}" aria-label="Destacar grupo">${ui.gstar.includes(id) ? '★' : '☆'}</button>`;
  function tileHtml(id) {
    const d = groupData(id); if (!d) return '';
    if (id === 'fav') return `<div class="gt gt-fav" data-id="fav"><div class="gt-head" data-open="fav"><span class="gt-name">★ Favoritos</span><span class="gt-n">${d.n}</span></div>${favControls()}<div class="gt-list">${favBody(false)}</div></div>`;
    return `<div class="gt" data-id="${escH(id)}"><div class="gt-head" data-open="${escH(id)}">${starB(id)}<span class="gt-name">${escH(d.title)}</span></div>
      ${d.p ? perSel(d.p) : `<div class="gt-tabs"><button type="button" data-g="edit" data-n="${escH(d.g.name)}">Editar</button><button type="button" class="dan" data-g="del" data-n="${escH(d.g.name)}">Excluir</button></div>`}
      <div class="gt-list">${d.rows.length ? tbl(d.rows, d.h, false) : '<p class="gt-empty">Sem dados suficientes.</p>'}</div></div>`;
  }
  let sortable = null, reorg = false, fullId = null;
  function fullHtml(id) {
    const d = groupData(id); if (!d) { fullId = null; return ''; }
    const body = id === 'fav' ? favControls() + favBody(true) : (d.p ? perSel(d.p) : '') + (d.rows.length ? tbl(d.rows, d.h, true) : '<p class="gt-empty">Sem dados suficientes.</p>');
    return `<section class="gfull"><div class="gfull-head"><b>${escH(d.title)}</b><button type="button" class="gx" data-gclose aria-label="Fechar grupo">✕</button></div>${body}</section>`;
  }
  async function list() {
    const r = $g('#gruposRoot');
    if (!METRICS) { r.innerHTML = loaderHTML('Carregando grupos…'); await loadMetrics(); }
    if (!state.data) { r.innerHTML = loaderHTML('Carregando dados…'); setTimeout(list, 1500); return; }
    if (fullId) { r.innerHTML = fullHtml(fullId); if (fullId) return; }
    r.innerHTML = `<section class="space-y-2">
      <div class="flex flex-wrap items-center gap-2"><h2 class="text-base font-bold mr-auto">Grupos</h2>
        <button type="button" class="gbtn${reorg ? ' pri' : ''}" data-g="reorg">${reorg ? 'Concluir' : '⇅ Reorganizar'}</button>
        ${state.country === 'br' ? `<button type="button" class="gbtn pri" data-g="new">＋ Criar</button>
        <button type="button" class="gbtn" data-g="export" title="Exportar grupos" aria-label="Exportar grupos">↓</button>
        <button type="button" class="gbtn" data-g="import" title="Importar grupos" aria-label="Importar grupos">↑</button>` : ''}
        <input id="gFile" type="file" accept=".json,application/json,text/plain,*/*" class="hidden"></div>
      <div id="gGrid" class="ggrid${reorg ? ' reorg' : ''}">${tileIds().map(tileHtml).join('')}</div></section>`;
    $g('#gFile').addEventListener('change', importG);
    if (sortable) { sortable.destroy(); sortable = null; }
    if (reorg && window.Sortable) sortable = Sortable.create($g('#gGrid'), { animation: 150, filter: '.gt-fav', preventOnFilter: false, onMove: (e) => !e.related.classList.contains('gt-fav'),
      onEnd: () => { ui.order = [...$g('#gGrid').children].map(x => x.dataset.id).filter(x => x !== 'fav'); saveUI(); } });
  }
  window.gruposRefresh = () => { if (!$g('[data-tabpane="grupos"]').classList.contains('hidden')) list(); };
  $g('#gruposRoot').addEventListener('click', async (e) => {
    const st = e.target.closest('[data-gstar]');
    if (st) { e.stopPropagation(); const id = st.dataset.gstar; ui.gstar = ui.gstar.includes(id) ? ui.gstar.filter(x => x !== id) : ui.gstar.concat(id); saveUI(); list(); return; }
    if (e.target.closest('[data-gclose]')) { fullId = null; list(); window.scrollTo(0, 0); return; }
    const tr = e.target.closest('tr.tap[data-row]');
    if (tr) {
      const nx = tr.nextElementSibling; if (nx && nx.classList.contains('gdet')) { nx.remove(); tr.classList.remove('sel'); return; }
      const r = rowsAll().find(x => x.ticker === tr.dataset.row); if (!r) return;
      state.expanded.add(r.ticker); tr.classList.add('sel');
      tr.insertAdjacentHTML('afterend', `<tr class="gdet"><td colspan="3">${blockHtml(r)}</td></tr>`); return;
    }
    const h = e.target.closest('[data-open]');
    if (h && !reorg) { const t = h.closest('.gt'); if (t.classList.contains('hl')) { fullId = h.dataset.open; list(); window.scrollTo(0, 0); } else { document.querySelectorAll('.gt.hl').forEach(x => x.classList.remove('hl')); t.classList.add('hl'); } return; }
    const ft = e.target.closest('[data-ftab]');
    if (ft) { const k = ft.dataset.ftab; if (k === '+') { const n = ((await uiPrompt('Nome da nova aba:', '', { ok: 'Criar' })) || '').trim().slice(0, 30); if (!n) return; const id = 't' + Date.now().toString(36); ui.fav.tabs.push({ id, name: n }); ui.fav.tab = id; } else ui.fav.tab = k; saveUI(); list(); return; }
    const fr = e.target.closest('[data-fren]'); if (fr) { const t = ui.fav.tabs.find(x => x.id === fr.dataset.fren); const n = ((await uiPrompt('Novo nome da aba:', t.name)) || '').trim().slice(0, 30); if (n) { t.name = n; saveUI(); list(); } return; }
    const fd = e.target.closest('[data-fdel]'); if (fd) { const t = ui.fav.tabs.find(x => x.id === fd.dataset.fdel); if (t && await uiConfirm(`Excluir a aba "${t.name}"? As empresas continuam nos Favoritos.`, { ok: 'Excluir', danger: true })) { ui.fav.tabs = ui.fav.tabs.filter(x => x !== t); for (const k in ui.fav.assign) if (ui.fav.assign[k] === t.id) delete ui.fav.assign[k]; ui.fav.tab = 'all'; saveUI(); list(); } return; }
    if (e.target.closest('[data-g="reorg"]')) { reorg = !reorg; list(); }
  });
  $g('#gruposRoot').addEventListener('change', (e) => {
    const p = e.target.dataset.per; if (p) { ui.per[p] = +e.target.value; saveUI(); list(); return; }
    if (e.target.hasAttribute('data-fsort')) { ui.fav.sort = e.target.value; saveUI(); list(); return; }
    if (e.target.hasAttribute('data-favg')) { ui.fav.avg = +e.target.value; saveUI(); list(); return; }
    const mv = e.target.dataset.mv; if (mv) { if (e.target.value) ui.fav.assign[mv] = e.target.value; else delete ui.fav.assign[mv]; saveUI(); }
  });
  document.addEventListener('favs', () => { if (!$g('[data-tabpane="grupos"]').classList.contains('hidden')) list(); });
  function exportG() {
    const blob = new Blob([JSON.stringify({ app: 'screener-b3', tipo: 'grupos', versao: 1, exportado: new Date().toISOString(), grupos: groups }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'grupos-screener-' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.json';
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  async function importG(e) {
    const f = e.target.files[0]; if (!f) return;
    try {
      const d = JSON.parse(await f.text()); const arr = Array.isArray(d) ? d : d.grupos;
      if (!Array.isArray(arr)) throw new Error('arquivo sem grupos');
      let n = 0;
      for (const g of arr) {
        if (!g || typeof g.name !== 'string' || !Array.isArray(g.tickers)) continue;
        let name = g.name.trim().slice(0, 40); const tk = [...new Set(g.tickers.map(t => String(t).toUpperCase().trim()).filter(Boolean))].sort();
        const ex = groups.find(x => x.name === name);
        if (ex) {
          if (ex.tickers.join() === tk.join()) continue;
          if (await uiConfirm(`O grupo "${name}" já existe.`, { ok: 'Substituir', cancel: 'Importar como cópia', danger: true })) groups = groups.filter(x => x !== ex);
          else { let i = 2; while (groups.some(x => x.name === `${name} (${i})`)) i++; name = `${name} (${i})`; }
        }
        groups.push({ name, tickers: tk, updated: g.updated || new Date().toISOString() }); n++;
      }
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save(); list();
      uiToast(n + ' grupo(s) importado(s)');
    } catch (err) { uiAlert('Não foi possível importar: ' + err.message); }
    e.target.value = '';
  }

  loadMetrics().then(() => { if (state.data && window.apply) apply(); });
  document.addEventListener('tabshow', (e) => {
    if (e.detail === 'grupos') { list(); if (viewing || state.group) { viewing = null; state.group = null; refresh(); } }
    if (e.detail === 'acoes' && !state.selMode && viewing) { /* abrindo grupo */ }
  });
  document.querySelectorAll('[data-tab="acoes"]').forEach(b => b.addEventListener('click', () => { if (viewing && !state.selMode) { viewing = null; state.group = null; refresh(); } }));
  bar(); list();
})();
