// ---------- Grupos (localStorage + exportar/importar .json) ----------
(function () {
  const KEY = 'screenerB3.grupos.v1';
  const $g = (s) => document.querySelector(s);
  const escH = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let groups = (() => { try { const g = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(g) ? g : []; } catch (e) { return []; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(groups)); } catch (e) { alert('Não foi possível salvar no navegador.'); } };
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
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-g]'); if (!b) return;
    const a = b.dataset.g, find = (n) => groups.find(g => g.name === n);
    if (a === 'new') startSel(null);
    else if (a === 'cancel') stopSel();
    else if (a === 'save') {
      const name = ($g('#gName').value || '').trim();
      if (!name) { alert('Dê um nome ao grupo.'); $g('#gName').focus(); return; }
      if (!state.selSet.size) { alert('Selecione pelo menos uma empresa.'); return; }
      const other = find(name);
      if (other && other !== editing && !confirm(`Já existe um grupo "${name}". Substituir?`)) return;
      groups = groups.filter(g => g !== other && g !== editing);
      groups.push({ name, tickers: [...state.selSet].sort(), updated: new Date().toISOString() });
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save();
      state.selMode = false; editing = null; state.selSet = new Set(); bar(); showTab('grupos');
    }
    else if (a === 'back') { viewing = null; state.group = null; state.groupRank = null; refresh(); showTab('grupos'); }
    else if (a === 'open') openGroup(find(b.dataset.n));
    else if (a === 'edit') startSel(find(b.dataset.n));
    else if (a === 'del') { const g = find(b.dataset.n); if (g && confirm(`Excluir o grupo "${g.name}"?`)) { groups = groups.filter(x => x !== g); save(); list(); } }
    else if (a === 'export') exportG();
    else if (a === 'import') $g('#gFile').click();
  });

  // ---------- Grupos pré-definidos (TOP 10, recalculados com os dados atuais) ----------
  let METRICS = null;
  const loadMetrics = async () => { if (METRICS) return METRICS; try { METRICS = (await (await fetch('/api/metrics')).json()).metrics || {}; } catch (e) { METRICS = {}; } return METRICS; };
  const F2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pc = (x) => (x > 0 ? '+' : '') + F2.format(x) + '%';
  const rowsAll = () => (state.data && state.country === 'br') ? state.data.rows : [];
  // grupos pré-definidos: só empresas com negociação média ≥ R$ 500 mil/dia (evita distorções de papéis sem liquidez)
  const rowsK = () => rowsAll().filter(r => ((r.v.vol30 ?? r.v.liq2m) || 0) >= 5e5);
  const MX = (t) => (METRICS || {})[t] || {};
  const pctRank = (arr, key, asc) => { const s = arr.slice().sort((a, b) => asc ? key(a) - key(b) : key(b) - key(a)); const m = new Map(); s.forEach((r, i) => m.set(r, 1 - i / Math.max(1, s.length - 1))); return m; };
  const PRE = [
    { id: 'valor', name: 'Maior valorização', per: true, calc: (n) => rowsK().filter(r => MX(r.ticker)['ret' + n] != null).map(r => [r, MX(r.ticker)['ret' + n]]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, pc(v)]) },
    { id: 'rent', name: 'Maior rentabilidade', calc: () => rowsK().filter(r => r.v.pl >= 2).map(r => [r, 100 / r.v.pl]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '% a.a.']) },
    { id: 'dy', name: 'Maiores pagadoras de dividendos', per: true, calc: (n) => rowsK().map(r => [r, MX(r.ticker)['dy' + n] ?? (n === 1 ? r.v.dy : null)]).filter(x => x[1] > 0 && x[1] < 40).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '% a.a.']) },
    { id: 'prov', name: 'Mais proventos ao investidor', calc: () => rowsK().map(r => [r, MX(r.ticker).prov12]).filter(x => x[1] > 0 && x[1] < 60).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '% 12m']) },
    { id: 'peq', name: 'Pequenas e médias promissoras', calc: () => {
      const c = rowsAll().filter(r => { const v = r.v; const liq = v.vol30 ?? v.liq2m; return v.valmerc >= 3e8 && v.valmerc <= 1e10 && v.lpa > 0 && v.roe >= 12 && (v.cresc5a > 0 || v.lucro5a > 0) && (v.dlebit == null || v.dlebit < 3) && liq >= 1e6; });
      const a = pctRank(c, r => r.v.roe), b = pctRank(c, r => r.v.lucro5a ?? -1e9), d = pctRank(c, r => r.v.pl > 0 ? 1 / r.v.pl : 0);
      return c.map(r => [r, (a.get(r) + b.get(r) + d.get(r)) / 3 * 100]).sort((x, y) => y[1] - x[1]).map(([r, v]) => [r, 'nota ' + F2.format(v)]); } },
    { id: 'magic', name: 'Magic Formula', calc: () => {
      const c = rowsK().filter(r => r.v.evebit >= 1 && r.v.roic != null && r.v.roic < 150);
      const r1 = new Map(c.slice().sort((a, b) => b.v.roic - a.v.roic).map((r, i) => [r, i])), r2 = new Map(c.slice().sort((a, b) => a.v.evebit - b.v.evebit).map((r, i) => [r, i]));
      return c.map(r => [r, r1.get(r) + r2.get(r)]).sort((a, b) => a[1] - b[1]).map(([r]) => [r, 'ROIC ' + F2.format(r.v.roic) + '% · EV/EBIT ' + F2.format(r.v.evebit)]); } },
    { id: 'graham', name: 'Baratas pelo Graham', calc: () => rowsK().filter(r => r.v.lpa > 0 && r.v.vpa > 0 && r.v.preco > 0 && r.v.pl >= 2).map(r => [r, (Math.sqrt(22.5 * r.v.lpa * r.v.vpa) / r.v.preco - 1) * 100]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, 'desconto ' + F2.format(v) + '%']) },
    { id: 'consist', name: 'Pagadoras consistentes', calc: () => rowsK().map(r => { const an = Object.values(MX(r.ticker).anual || {}); if (an.length < 5 || an.some(x => !(x > 0))) return null; const m = an.reduce((a, b) => a + b, 0) / an.length, sd = Math.sqrt(an.reduce((a, b) => a + (b - m) ** 2, 0) / an.length); return [r, sd / m, m]; }).filter(Boolean).sort((a, b) => a[1] - b[1] || b[2] - a[2]).map(([r, cv, m]) => [r, 'DY médio ' + F2.format(m) + '% · CV ' + F2.format(cv)]) },
    { id: 'divida', name: 'Menos endividadas', calc: () => rowsK().filter(r => r.v.lpa > 0 && r.v.dlpl != null && !r.bk?.length).map(r => [r, r.v.dlpl]).sort((a, b) => a[1] - b[1]).map(([r, v]) => [r, 'Dív.Líq/PL ' + F2.format(v)]) },
    { id: 'quedas', name: 'Maiores quedas', per: true, calc: (n) => rowsK().filter(r => MX(r.ticker)['ret' + n] != null).map(r => [r, MX(r.ticker)['ret' + n]]).filter(x => x[1] < 0).sort((a, b) => a[1] - b[1]).map(([r, v]) => [r, pc(v)]) },
    { id: 'negoc', name: 'Mais negociadas', calc: () => rowsK().filter(r => r.v.valmerc > 0 && (r.v.vol30 ?? r.v.liq2m) > 0).map(r => [r, (r.v.vol30 ?? r.v.liq2m) / r.v.valmerc * 100]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '% do valor/dia']) },
  ];
  const UKEY = 'screenerB3.gruposUI.v1';
  const ui = (() => { try { return JSON.parse(localStorage.getItem(UKEY) || '{}') || {}; } catch (e) { return {}; } })();
  ui.per = ui.per || {}; ui.order = ui.order || []; ui.fav = ui.fav || { tabs: [], assign: {}, tab: 'all', sort: 'preco' };
  const saveUI = () => { try { localStorage.setItem(UKEY, JSON.stringify(ui)); } catch (e) { } };
  const favList = () => rowsAll().filter(r => FAVS.has(r.ticker));
  function favRows() {
    const f = ui.fav, s = f.sort || 'preco';
    let L = favList(); if (f.tab !== 'all' && f.tab !== 'prov') L = L.filter(r => f.assign[r.ticker] === f.tab);
    const key = (r) => s === 'preco' ? (r.v.preco ?? -1e9) : (MX(r.ticker)['ret' + s.slice(1)] ?? -1e9);
    return L.sort((a, b) => key(b) - key(a)).map(r => [r, s === 'preco' ? 'R$ ' + F2.format(r.v.preco || 0) : (MX(r.ticker)['ret' + s.slice(1)] != null ? pc(MX(r.ticker)['ret' + s.slice(1)]) : '—')]);
  }
  function tileIds() {
    const ids = ['fav'].concat(PRE.map(p => 'pre:' + p.id), groups.map(g => 'user:' + g.name));
    const ord = ui.order.filter(x => ids.includes(x) && x !== 'fav');
    return ['fav'].concat(ord, ids.filter(x => x !== 'fav' && !ord.includes(x)));
  }
  const rowLine = (r, v, i, extra) => `<li><span class="gi">${i + 1}</span><b>${escH(r.ticker)}</b><span class="gv">${escH(v)}</span>${extra || ''}</li>`;
  function tileHtml(id) {
    if (id === 'fav') {
      const f = ui.fav, tabs = [['all', 'Todos']].concat(f.tabs.map(t => [t.id, t.name]), [['prov', 'Proventos no ano']]);
      let body;
      if (f.tab === 'prov') {
        const L = favList().map(r => { const ev = MX(r.ticker).ytd || [], p = r.v.preco || MX(r.ticker).p || 0; return [r, ev, p]; });
        body = L.length ? L.map(([r, ev, p]) => `<li class="gp"><b>${escH(r.ticker)}</b><span class="gv">${ev.length ? ev.map(e => e[2] === 'provento' ? `${e[0]}: R$ ${F2.format(e[1])} (${F2.format(p ? e[1] / p * 100 : 0)}%)` : (e[2] === 'bonificação' ? `${e[0]}: bonificação ${F2.format((e[1] - 1) * 100)}%` : `${e[0]}: ${e[2]} ${F2.format(e[1])}:1`)).join(' · ') + ` — total ${F2.format(p ? ev.filter(e => e[2] === 'provento').reduce((a, e) => a + e[1], 0) / p * 100 : 0)}%` : 'sem proventos no ano'}</span></li>`).join('') : '';
      } else {
        const opts = (t) => `<select class="gmv" data-mv="${t}" aria-label="Mover ${t} para aba"><option value="">—</option>${f.tabs.map(x => `<option value="${x.id}"${f.assign[t] === x.id ? ' selected' : ''}>${escH(x.name)}</option>`).join('')}</select>`;
        body = favRows().map(([r, v], i) => rowLine(r, v, i, f.tabs.length ? opts(r.ticker) : '')).join('');
      }
      const ut = f.tabs.find(t => t.id === f.tab);
      return `<div class="gt gt-fav" data-id="fav"><div class="gt-head" data-open="fav"><span class="gt-name">★ Favoritos</span><span class="gt-n">${favList().length}</span></div>
        <div class="gt-tabs">${tabs.map(([k, l]) => `<button type="button" class="${f.tab === k ? 'on' : ''}" data-ftab="${k}">${escH(l)}</button>`).join('')}<button type="button" data-ftab="+" aria-label="Nova aba">＋</button>
          ${ut ? `<button type="button" data-fren="${ut.id}">Renomear</button><button type="button" data-fdel="${ut.id}" class="dan">Excluir aba</button>` : ''}
          ${f.tab !== 'prov' ? `<select class="gper" data-fsort aria-label="Ordenar favoritos"><option value="preco"${f.sort === 'preco' ? ' selected' : ''}>Preço da ação</option>${[1, 2, 3, 4, 5].map(n => `<option value="v${n}"${f.sort === 'v' + n ? ' selected' : ''}>Maiores valorizações ${n} ano${n > 1 ? 's' : ''}</option>`).join('')}</select>` : ''}</div>
        <ul class="gt-list">${body || '<li class="gt-empty">Toque na ☆ de uma empresa para favoritar.</li>'}</ul></div>`;
    }
    if (id.startsWith('pre:')) {
      const p = PRE.find(x => 'pre:' + x.id === id), n = ui.per[p.id] || 1, L = p.calc(n).slice(0, 10);
      return `<div class="gt" data-id="${id}"><div class="gt-head" data-open="${id}"><span class="gt-name">${escH(p.name)}</span></div>
        ${p.per ? `<select class="gper" data-per="${p.id}" aria-label="Período">${[1, 2, 3, 4, 5].map(k => `<option value="${k}"${k === n ? ' selected' : ''}>${k} ano${k > 1 ? 's' : ''}</option>`).join('')}</select>` : ''}
        <ul class="gt-list">${L.map(([r, v], i) => rowLine(r, v, i)).join('') || '<li class="gt-empty">Sem dados suficientes.</li>'}</ul></div>`;
    }
    const gname = id.slice(5), gg = groups.find(x => x.name === gname); if (!gg) return '';
    return `<div class="gt gt-user" data-id="${escH(id)}"><div class="gt-head" data-open="${escH(id)}"><span class="gt-name">${escH(gg.name)}</span><span class="gt-n">${gg.tickers.length}</span></div>
      <div class="gt-tabs"><button type="button" data-g="edit" data-n="${escH(gg.name)}">Editar</button><button type="button" class="dan" data-g="del" data-n="${escH(gg.name)}">Excluir</button></div>
      <ul class="gt-list">${gg.tickers.map((t, i) => `<li><span class="gi">${i + 1}</span><b>${escH(t)}</b></li>`).join('')}</ul></div>`;
  }
  function tickersOf(id) {
    if (id === 'fav') return { name: 'Favoritos' + (ui.fav.tab !== 'all' && ui.fav.tab !== 'prov' ? ' · ' + (ui.fav.tabs.find(t => t.id === ui.fav.tab)?.name || '') : ''), tickers: (ui.fav.tab === 'prov' ? favList().map(r => [r]) : favRows()).map(x => x[0].ticker), rank: true, pre: true };
    if (id.startsWith('pre:')) { const p = PRE.find(x => 'pre:' + x.id === id); return { name: p.name + (p.per ? ` (${ui.per[p.id] || 1} ano${(ui.per[p.id] || 1) > 1 ? 's' : ''})` : ''), tickers: p.calc(ui.per[p.id] || 1).slice(0, 10).map(x => x[0].ticker), rank: true, pre: true }; }
    return groups.find(x => x.name === id.slice(5));
  }
  let sortable = null, reorg = false;
  async function list() {
    const r = $g('#gruposRoot');
    if (!METRICS) { r.innerHTML = '<div class="text-sm text-slate-400 p-4">Carregando grupos…</div>'; await loadMetrics(); }
    if (!state.data) { r.innerHTML = '<div class="text-sm text-slate-400 p-4">Carregando dados…</div>'; setTimeout(list, 1500); return; }
    r.innerHTML = `<section class="space-y-2">
      <div class="flex flex-wrap items-center gap-2"><h2 class="text-base font-bold mr-auto">Grupos</h2>
        <button type="button" class="gbtn${reorg ? ' pri' : ''}" data-g="reorg">${reorg ? 'Concluir' : '⇅ Reorganizar'}</button>
        <button type="button" class="gbtn pri" data-g="new">＋ Criar</button>
        <button type="button" class="gbtn" data-g="export" title="Exportar grupos">⬇</button>
        <button type="button" class="gbtn" data-g="import" title="Importar grupos">⬆</button>
        <input id="gFile" type="file" accept=".json,application/json,text/plain,*/*" class="hidden"></div>
      <p class="text-[11px] text-slate-500">${reorg ? 'Arraste os grupos para mudar a ordem.' : 'Toque no título para destacar; toque de novo para abrir em tela cheia.'}</p>
      <div id="gGrid" class="ggrid${reorg ? ' reorg' : ''}">${tileIds().map(tileHtml).join('')}</div></section>`;
    $g('#gFile').addEventListener('change', importG);
    if (sortable) { sortable.destroy(); sortable = null; }
    if (reorg && window.Sortable) sortable = Sortable.create($g('#gGrid'), { animation: 150, filter: '.gt-fav', preventOnFilter: false, onMove: (e) => !e.related.classList.contains('gt-fav'),
      onEnd: () => { ui.order = [...$g('#gGrid').children].map(x => x.dataset.id).filter(x => x !== 'fav'); saveUI(); } });
  }
  $g('#gruposRoot').addEventListener('click', (e) => {
    const h = e.target.closest('[data-open]');
    if (h && !reorg) { const t = h.closest('.gt'); if (t.classList.contains('hl')) { const g = tickersOf(h.dataset.open); if (g && g.tickers.length) openGroup(g); } else { document.querySelectorAll('.gt.hl').forEach(x => x.classList.remove('hl')); t.classList.add('hl'); } return; }
    const ft = e.target.closest('[data-ftab]');
    if (ft) { const k = ft.dataset.ftab; if (k === '+') { const n = (prompt('Nome da nova aba:') || '').trim().slice(0, 30); if (!n) return; const id = 't' + Date.now().toString(36); ui.fav.tabs.push({ id, name: n }); ui.fav.tab = id; } else ui.fav.tab = k; saveUI(); list(); return; }
    const fr = e.target.closest('[data-fren]'); if (fr) { const t = ui.fav.tabs.find(x => x.id === fr.dataset.fren); const n = (prompt('Novo nome da aba:', t.name) || '').trim().slice(0, 30); if (n) { t.name = n; saveUI(); list(); } return; }
    const fd = e.target.closest('[data-fdel]'); if (fd) { const t = ui.fav.tabs.find(x => x.id === fd.dataset.fdel); if (t && confirm(`Excluir a aba "${t.name}"? As empresas continuam nos Favoritos.`)) { ui.fav.tabs = ui.fav.tabs.filter(x => x !== t); for (const k in ui.fav.assign) if (ui.fav.assign[k] === t.id) delete ui.fav.assign[k]; ui.fav.tab = 'all'; saveUI(); list(); } return; }
    if (e.target.closest('[data-g="reorg"]')) { reorg = !reorg; list(); }
  });
  $g('#gruposRoot').addEventListener('change', (e) => {
    const p = e.target.dataset.per; if (p) { ui.per[p] = +e.target.value; saveUI(); list(); return; }
    if (e.target.hasAttribute('data-fsort')) { ui.fav.sort = e.target.value; saveUI(); list(); return; }
    const mv = e.target.dataset.mv; if (mv) { if (e.target.value) ui.fav.assign[mv] = e.target.value; else delete ui.fav.assign[mv]; saveUI(); }
  });
  document.addEventListener('favs', () => { if (!$g('[data-tabpane="grupos"]').classList.contains('hidden')) list(); });
  function exportG() {
    const blob = new Blob([JSON.stringify({ app: 'screener-b3', tipo: 'grupos', versao: 1, exportado: new Date().toISOString(), grupos: groups }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'grupos-screener-' + new Date().toISOString().slice(0, 10) + '.json';
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
          if (confirm(`O grupo "${name}" já existe. OK = substituir; Cancelar = importar como cópia.`)) groups = groups.filter(x => x !== ex);
          else { let i = 2; while (groups.some(x => x.name === `${name} (${i})`)) i++; name = `${name} (${i})`; }
        }
        groups.push({ name, tickers: tk, updated: g.updated || new Date().toISOString() }); n++;
      }
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save(); list();
      alert(n + ' grupo(s) importado(s).');
    } catch (err) { alert('Não foi possível importar: ' + err.message); }
    e.target.value = '';
  }

  document.addEventListener('tabshow', (e) => {
    if (e.detail === 'grupos') { list(); if (viewing || state.group) { viewing = null; state.group = null; refresh(); } }
    if (e.detail === 'acoes' && !state.selMode && viewing) { /* abrindo grupo */ }
  });
  document.querySelectorAll('[data-tab="acoes"]').forEach(b => b.addEventListener('click', () => { if (viewing && !state.selMode) { viewing = null; state.group = null; refresh(); } }));
  bar(); list();
})();
