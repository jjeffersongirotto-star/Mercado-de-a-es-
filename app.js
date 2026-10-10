const PAGE = 50;
const VIEW_KEY = 'screenerB3.view.v1';
const view = (() => { try { return JSON.parse(localStorage.getItem(VIEW_KEY) || '{}') || {}; } catch (e) { return {}; } })();
const saveView = () => { try { localStorage.setItem(VIEW_KEY, JSON.stringify({ country: state.country, source: state.source })); } catch (e) { } };
const state = { country: view.country || 'br', source: view.source || 'all', countries: [], expanded: new Set(), rowMap: {}, data: null, rows: [], filtered: [], shown: 0, sortKey: 'liq2m', sortDir: -1, filters: {}, fieldMap: {} };
const $ = (s) => document.querySelector(s);
const nf = (d) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const F2 = nf(2), F0 = nf(0);
const isMobile = () => window.matchMedia('(max-width: 767px)').matches;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function fmtBig(v) {
  const a = Math.abs(v);
  if (a >= 1e9) return F2.format(v / 1e9) + ' bi';
  if (a >= 1e6) return F2.format(v / 1e6) + ' mi';
  if (a >= 1e3) return F2.format(v / 1e3) + ' mil';
  return F2.format(v);
}
const F1 = nf(1);
function fmtMoneyBig(v, cur) {
  const c = cur || state.data?.currency || 'BRL', sym = CUR[c] || c, a = Math.abs(v);
  const t = a >= 1e9 ? F1.format(v / 1e9) + ' bi' : a >= 1e6 ? F1.format(v / 1e6) + ' mi' : a >= 1e3 ? F1.format(v / 1e3) + ' mil' : F0.format(v);
  return sym + ' ' + t;
}
const fmtQty = (q) => q >= 1e9 ? F1.format(q / 1e9) + ' bi' : q >= 1e6 ? F1.format(q / 1e6) + ' mi' : q >= 1e3 ? F1.format(q / 1e3) + ' mil' : F0.format(q);
const curSym = () => CUR[state.data?.currency] || state.data?.currency || 'R$';
const qOf = (r, k) => ((r.q || (r.S && r.S.tv) || {})['q_' + k]);
function fmt(v, unit, key, cur) {
  if (v === null || v === undefined) return '–';
  if (unit === '$') return fmtMoneyBig(v, cur);
  if (['liq2m', 'patrliq', 'valmerc'].includes(key)) return fmtBig(v);
  if (unit === '%') return F2.format(v) + '%';
  return F2.format(v);
}
const CUR = { BRL: 'R$', USD: 'US$', EUR: '€', GBP: '£', JPY: '¥' };
function fmtPrice(v, cur) {
  if (v === null || v === undefined) return '—';
  const c = cur || state.data?.currency || 'BRL';
  return (CUR[c] || c) + ' ' + (c === 'JPY' ? F0.format(v) : F2.format(v));
}
const srcInfo = (id) => (state.data?.sources || []).find(s => s.id === id) || { id, name: id, logo: '' };
const logoImg = (id, cls = 'srclogo') => { const s = srcInfo(id); return s.logo ? `<img class="${cls}" src="${s.logo}" alt="" loading="lazy">` : ''; };
// valor exibido/filtrado: consenso ('Todos') ou só a fonte escolhida
function val(r, k) {
  if (state.source === 'all') return r.v[k];
  const S = r.S ? r.S[state.source] : (state.data.single_source === state.source ? r.v : null);
  const x = S ? S[k] : null;
  return x === undefined ? null : x;
}
function hint(f) {
  if (f.scale) return { sym: '≥', txt: `Mostra ${f.label} ≥ valor, digitado em milhões de ${curSym()} (ex.: 10 = ${curSym()} 10 mi/dia). Fonte: TradingView` };
  if (f.dir === 'high') return { sym: '≥', txt: `Maior é melhor: mostra ${f.label} ≥ valor` };
  if (f.dir === 'low') return { sym: '≤', txt: `Menor é melhor: mostra ${f.label} ≤ valor` + (f.excludeNeg ? ' (exclui negativos)' : ' (negativos incluídos: caixa líquido)') };
  return null;
}

// ---------- Filtros (favoritos, ordem, ocultos e valores persistidos no localStorage) ----------
const LS_KEY = 'screenerB3.filtros.v1';
const prefs = (() => {
  let p = {};
  try { p = JSON.parse(localStorage.getItem(LS_KEY) || '{}') || {}; } catch (e) { p = {}; }
  return { order: p.order || [], fav: p.fav || {}, hidden: p.hidden || {}, values: p.values || {},
           minimized: p.minimized !== false, folderOpen: !!p.folderOpen };
})();
const savePrefs = () => { try { localStorage.setItem(LS_KEY, JSON.stringify(prefs)); } catch (e) { /* modo privado */ } };

const filterFields = () => state.data.fields.filter(f => hint(f));
function orderedKeys() {
  const keys = filterFields().map(f => f.key);
  const base = keys.slice();
  const pos = (k) => { const i = prefs.order.indexOf(k); return i < 0 ? 1e6 + base.indexOf(k) : i; };
  return keys.sort((a, b) => (prefs.fav[b] ? 1 : 0) - (prefs.fav[a] ? 1 : 0) || pos(a) - pos(b));
}
const parseVal = (s) => { s = String(s ?? '').trim().replace(',', '.'); if (s === '') return null; const n = parseFloat(s); return Number.isNaN(n) ? null : n; };
// aplicados = com valor e não ocultos
function computeFilters() {
  state.filters = {};
  for (const f of filterFields()) {
    const v = parseVal(prefs.values[f.key]);
    if (v !== null && !prefs.hidden[f.key]) state.filters[f.key] = v * (f.scale || 1);  // só campos existentes no país atual
  }
}

function itemHtml(f, inFolder) {
  const h = hint(f), k = f.key, val = prefs.values[k] ?? '';
  const sym = `<span class="font-bold ${f.dir === 'high' ? 'text-emerald-400' : 'text-sky-400'}">${h.sym}${f.excludeNeg ? '<sup class="text-[9px]">+</sup>' : ''}</span>`;
  if (inFolder) {
    return `<div class="fitem flex items-center gap-2 bg-slate-950/70 border border-slate-800 rounded-lg px-2 py-1.5" data-key="${k}">
      <span class="drag-handle cursor-grab select-none text-slate-500 px-1" title="Arraste de volta para o painel">⠿</span>
      <span class="text-xs text-slate-300 flex-1 truncate">${esc(f.label)} ${sym}${val !== '' ? ` <span class="text-slate-500">(${esc(val)} – ignorado)</span>` : ''}</span>
      <button type="button" class="restore text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700" data-key="${k}">restaurar</button>
    </div>`;
  }
  const active = parseVal(val) !== null;
  return `<div class="fitem flex flex-col gap-1 bg-slate-950/60 border ${active ? 'border-emerald-600' : 'border-slate-800'} rounded-lg px-2 py-1.5" data-key="${k}" title="${esc(h.txt + (f.unit === '%' ? ' — digite 8 para 8%' : ''))}">
    <div class="flex items-center gap-1 text-[11px] text-slate-400">
      <span class="drag-handle cursor-grab select-none text-slate-500 text-sm leading-none px-0.5" title="Arraste para reordenar ou para 'Filtros ocultos'">⠿</span>
      <span class="truncate flex-1">${esc(f.label)}${f.unit === '%' ? ' (%)' : f.scale ? ` (${curSym()} mi)` : ''}</span>
      ${sym}
      <button type="button" class="fav text-base leading-none ${prefs.fav[k] ? 'text-amber-400' : 'text-slate-600 hover:text-slate-300'}" data-key="${k}" title="${prefs.fav[k] ? 'Remover dos favoritos' : 'Favoritar (vai para o topo)'}">${prefs.fav[k] ? '★' : '☆'}</button>
    </div>
    <input data-key="${k}" type="number" step="any" inputmode="decimal" placeholder="${h.sym} …${f.scale ? ' mi' : ''}" value="${esc(val)}"
      class="fval w-full bg-transparent outline-none text-sm text-slate-100 placeholder:text-slate-600">
  </div>`;
}

function renderFilterUI() {
  const keys = orderedKeys();
  const visible = keys.filter(k => !prefs.hidden[k]), hidden = keys.filter(k => prefs.hidden[k]);
  $('#filters').innerHTML = visible.map(k => itemHtml(state.fieldMap[k], false)).join('');
  $('#filtersEmpty').classList.toggle('hidden', visible.length > 0);
  $('#hiddenList').innerHTML = hidden.map(k => itemHtml(state.fieldMap[k], true)).join('');
  $('#hiddenCount').textContent = hidden.length;
  $('#hiddenFolder').classList.toggle('open', prefs.folderOpen);
  $('#folderChevron').textContent = prefs.folderOpen ? '▴' : '▾';
  $('#hiddenEmpty').classList.toggle('hidden', hidden.length > 0 || !prefs.folderOpen);
  updateFiltersLabel();
}
function updateFiltersLabel() {
  const n = Object.keys(state.filters).length;
  $('#activeCount').textContent = n ? `${n} filtro${n > 1 ? 's' : ''} ativo${n > 1 ? 's' : ''}` : 'nenhum filtro ativo';
  $('#activeCount').classList.toggle('text-emerald-400', n > 0);
}
function setMinimized(min) {
  prefs.minimized = min; savePrefs();
  $('#minimize').checked = min;
  $('#filtersPanel').classList.toggle('hidden', min);
}
function changed() { computeFilters(); savePrefs(); updateFiltersLabel(); apply(); }
function syncOrderFromDom() {
  const vis = [...$('#filters').querySelectorAll('.fitem')].map(e => e.dataset.key);
  const hid = [...$('#hiddenList').querySelectorAll('.fitem')].map(e => e.dataset.key);
  prefs.order = [...vis, ...hid];
}
function restoreFilter(k) {
  delete prefs.hidden[k];
  prefs.order = [...prefs.order.filter(x => x !== k), k];  // volta ao fim do painel (favoritos seguem no topo)
  changed(); renderFilterUI();
}

function buildFilters() {
  const panel = $('#filters'), folder = $('#hiddenList');
  panel.addEventListener('input', (e) => {
    const i = e.target.closest('.fval'); if (!i) return;
    prefs.values[i.dataset.key] = i.value.trim();
    const item = i.closest('.fitem'), on = parseVal(i.value) !== null;
    item.classList.toggle('border-emerald-600', on); item.classList.toggle('border-slate-800', !on);
    changed();
  });
  panel.addEventListener('click', (e) => {
    const s = e.target.closest('.fav'); if (!s) return;
    const k = s.dataset.key;
    syncOrderFromDom();
    if (prefs.fav[k]) delete prefs.fav[k];
    else { prefs.fav[k] = true; prefs.order = [k, ...prefs.order.filter(x => x !== k)]; }
    savePrefs(); renderFilterUI();
  });
  folder.addEventListener('click', (e) => { const r = e.target.closest('.restore'); if (r) { e.stopPropagation(); restoreFilter(r.dataset.key); } });
  $('#folderHead').addEventListener('click', () => { prefs.folderOpen = !prefs.folderOpen; savePrefs(); renderFilterUI(); });
  $('#minimize').addEventListener('change', (e) => setMinimized(e.target.checked));
  // Arrastar e soltar (mouse e toque) só pela alça ⠿ — digitação e rolagem no celular continuam normais
  if (window.Sortable) {
    const common = { group: 'filtros', handle: '.drag-handle', animation: 150, forceFallback: true, fallbackOnBody: true,
      fallbackTolerance: 3, ghostClass: 'opacity-40', emptyInsertThreshold: 30, scroll: true, bubbleScroll: true };
    Sortable.create(panel, { ...common, onEnd: (evt) => { if (evt.to === panel) { syncOrderFromDom(); savePrefs(); renderFilterUI(); } } });
    Sortable.create(folder, { ...common,
      onAdd: (evt) => { prefs.hidden[evt.item.dataset.key] = true; syncOrderFromDom(); changed(); renderFilterUI(); },
      onRemove: (evt) => { delete prefs.hidden[evt.item.dataset.key]; syncOrderFromDom(); changed(); renderFilterUI(); } });
  }
  setMinimized(prefs.minimized);
  computeFilters(); renderFilterUI();
}
function clearFilters() { prefs.values = {}; changed(); renderFilterUI(); }

// ---------- Ordenação ----------
function buildSortOptions() {
  const sel = $('#sortKey');
  const opts = [{ key: 'ticker', label: 'Ticker' }, { key: 'nome', label: 'Empresa' }, { key: 'var', label: 'Variação dia' }, ...state.data.fields];
  sel.innerHTML = opts.map(o => `<option value="${o.key}">${esc(o.label)}</option>`).join('');
  if (!opts.some(o => o.key === state.sortKey)) { state.sortKey = state.data.fields.some(f => f.key === 'liq2m') ? 'liq2m' : 'ticker'; updateSortDir(); }
  sel.value = state.sortKey;
}
function buildSort() {
  const sel = $('#sortKey');
  buildSortOptions();
  sel.addEventListener('change', () => {
    state.sortKey = sel.value;
    const f = state.fieldMap[sel.value];
    state.sortDir = (sel.value === 'ticker' || sel.value === 'nome') ? 1 : (f && f.dir === 'low' ? 1 : -1);
    updateSortDir(); apply();
  });
  $('#sortDir').addEventListener('click', () => { state.sortDir *= -1; updateSortDir(); apply(); });
  updateSortDir();
}
function updateSortDir() { $('#sortDir').innerHTML = state.sortDir > 0 ? '<span class="sd-ic">1→9</span> Menor → maior' : '<span class="sd-ic">9→1</span> Maior → menor'; }
const getVal = (r, k) => (k === 'ticker' || k === 'nome') ? r[k] : (k === 'var' ? r.var : val(r, k));

function passes(r) {
  const q = norm($('#q').value.trim());
  if (q && !(r._s || norm(r.ticker + ' ' + r.nome)).includes(q)) return false;
  if (state.sector && state.sector !== 'Todos' && r.macro !== state.sector) return false;
  if (state.group && !state.selMode && !state.group.has(r.ticker)) return false;
  if ((!state.group || state.selMode) && $('#onlyLiquid').checked && !((r.v.liq2m || 0) > 0)) return false;
  for (const [k, x] of Object.entries(state.filters)) {
    const f = state.fieldMap[k]; if (!f) continue; const v = val(r, k);
    if (v === null || v === undefined) return false;
    if (f.dir === 'high' && !(v >= x)) return false;
    if (f.dir === 'low') { if (!(v <= x)) return false; if (f.excludeNeg && v < 0) return false; }
  }
  return true;
}

function apply() {
  const o2 = state.ord2 ? state.ord2.split(':') : null;
  const k = o2 ? o2[0] : state.sortKey, d = o2 ? +o2[1] : state.sortDir;
  state.filtered = state.rows.filter(passes).sort((a, b) => {
    const va = getVal(a, k), vb = getVal(b, k);
    if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1;
    return (typeof va === 'string' ? va.localeCompare(vb, 'pt-BR') : va - vb) * d;
  });
  $('#count').textContent = F0.format(state.filtered.length);
  $('#results').innerHTML = ''; state.shown = 0;
  renderMore();
}

// ---------- Blocos ----------
function cardsHtml(r) {
  const fields = state.data.fields, all = state.source === 'all';
  let cards = '';
  for (const f of fields) {
    if (f.key === 'preco') continue;
    const v = val(r, f.key), st = all ? (r.st || {})[f.key] : null, src = all ? (r.src || {})[f.key] : null;
    const nSrc = r.S ? Object.values(r.S).filter(d => d[f.key] != null).length : 0;
    const ag = (r.ag || {})[f.key] || [];
    const cls = ['card'];
    if (v === null || v === undefined) cls.push('na');
    else if (v < 0) cls.push('neg');
    let badge = '';
    const cmo = all ? ((r.cm || {})[f.key] || {}) : {}, cmt = cmo.t;
    if (cmo.aj) cls.push('aj');
    const isBank = all && (r.bk || []).includes(f.key);
    if (isBank) { cls.push('bank'); badge = '<span class="badge bg-blue-900 text-blue-100 font-bold border border-blue-700" title="Banco/seguradora — indicador não comparável entre fontes">banco</span>'; }
    else if (st === 'red') { cls.push('red'); if (cmt === 'avg') cls.push('avg'); badge = `<span class="badge bg-red-600 text-white">${cmt === 'avg' ? 'média' : cmt === 'w' ? 'pond.' : cmt === 'pri' ? '2 f.' : '≠'}</span>`; }
    else if (st === 'amb') { cls.push('res'); badge = `<span class="badge bg-amber-500 text-slate-900 font-bold">${((r.ex || {})[f.key] || []).length ? '±' : ag.length + '/' + (nSrc - (((r.xv || {})[f.key]) || []).length)}</span>`; }
    else if (cmt === 'pri') { cls.push('two'); badge = '<span class="badge bg-slate-600 text-slate-100" title="apenas 2 fontes, divergentes — exibida a de maior prioridade">2 fontes</span>'; }
    else if (src && src !== 'multi' && v != null) { badge = logoImg(src, 'srclogo opacity-80'); if (src === 'si') cls.push('si'); }
    if (all && nSrc >= 1 && v != null || st) cls.push('tip');
    cards += `<div class="${cls.join(' ')}" data-key="${f.key}">
      <div class="lbl"><span class="truncate" title="${esc(f.label)}">${esc(f.short || f.label)}</span>${cmo.aj ? '<span class="badge bg-sky-600 text-white font-bold ml-auto mr-0.5" title="concordância via EBIT ajustado">aj</span>' : ''}${badge}</div>
      <div class="val">${v == null ? '—' : fmt(v, f.unit, f.key, r.cur)}</div><div class="detail"></div></div>`;
  }
  return `<div class="cards p-2.5 sm:p-3">${cards}</div>`;
}

function tipHtml(r, f) {
  const k = f.key, st = (r.st || {})[k], ag = (r.ag || {})[k] || [], F = (x) => fmt(x, f.unit, k, r.cur);
  const S = r.S || { [state.data.single_source || 'tv']: r.v };
  const ids = (state.data.sources || []).map(s => s.id).filter(id => S[id] && S[id][k] != null);
  const exl = ((r.ex || {})[k]) || [];
  const cm = (r.cm || {})[k] || {};
  const P0 = nf(0);
  const xv = ((r.xv || {})[k]) || [];
  const isBank = (r.bk || []).includes(k);
  const idsV = ids.filter(id => !xv.includes(id));
  const head = isBank ? '<b class="text-blue-300">Banco/seguradora</b> — indicador baseado em EBIT/receita não é comparável entre fontes'
    : cm.t === 'pri' ? `<b class="text-slate-200">Apenas 2 fontes</b> — exibido: ${esc(srcInfo(cm.src).name)} (maior prioridade)`
    : st === 'red' && cm.t === 'avg' ? '<b class="text-red-300">Sem maioria — todas as fontes diferem</b><br>Exibido: <b class="text-yellow-300">média de todas as fontes</b>'
    : st === 'red' && cm.t === 'w' ? '<b class="text-red-300">Sem maioria — média ponderada pelos grupos</b><br>' + cm.w.map(([w, x, ids]) => `${P0.format(w * 100)}% × ${F(x)} <span class="text-slate-400">(${ids.map(id => esc(srcInfo(id).name)).join(', ')})</span>`).join('<br>+ ')
    : st === 'red' ? '<b class="text-red-300">Sem maioria entre as fontes</b>'
    : cm.t === 'half' ? `<b class="text-amber-300">Grupo com metade das fontes (${ag.length}/${idsV.length})</b> — tratado como maioria`
    : exl.length ? `<b class="text-amber-300">Sinal conferido pela Dív.Líq/PL</b> — usado: ${ag.map(id => esc(srcInfo(id).name)).join(', ')}`
    : st === 'amb' ? `<b class="text-amber-300">Maioria ${ag.length}/${idsV.length}</b> — valor de consenso`
    : idsV.length > 1 ? `<b class="text-emerald-300">Fontes concordam (${idsV.length}/${idsV.length})</b>` : '<b>Fonte única</b>';
  const ok = (id) => xv.includes(id) ? '' : cm.t === 'pri' ? (id === cm.src ? '✓' : '') : st === 'red' ? '' : (st ? (ag.includes(id) ? '✓' : '✗') : '✓');
  const aj = cm.aj || [], A0 = r.A || {};
  const ajm = (id) => aj.includes(id) ? ` <span class="badge bg-sky-600 text-white font-bold" title="concorda com o Fundamentus via EBIT ajustado">aj</span> <span class="text-sky-200">${F(A0[id][k + '_adj'])}</span>` : '';
  const rows = ids.map(id => `<tr class="${xv.includes(id) || st && st !== 'red' && !ag.includes(id) ? 'no' : ''}"><td>${logoImg(id)} ${esc(srcInfo(id).name)}${xv.includes(id) ? ' <span class="text-slate-400 text-[10px]">fora da votação neste indicador</span>' : ''}</td><td class="text-right font-semibold">${F(S[id][k])}${ajm(id)}</td><td>${ok(id)}</td></tr>`).join('');
  let extra = exl.length ? `<div class="mt-1 text-amber-200">Fora da votação (sinal oposto ao da Dív.Líq/PL de consenso — caixa líquido vs dívida líquida): ${exl.map(id => esc(srcInfo(id).name)).join(', ')}</div>` : '';
  const A = r.A || {};
  const adj = Object.entries(A).filter(([, d]) => d[k + '_adj'] != null);
  if (aj.length) extra += `<div class="mt-1 text-sky-200"><span class="badge bg-sky-600 text-white font-bold">aj</span> ${aj.map(id => esc(srcInfo(id).name)).join(', ')} concorda${aj.length > 1 ? 'm' : ''} com o Fundamentus via EBIT ajustado (lucro bruto − desp. vendas − desp. G&amp;A)</div>`;
  else if (adj.length) extra += '<div class="mt-1 text-sky-200">EBIT ajustado: ' + adj.map(([id, d]) => `${logoImg(id)} ${esc(srcInfo(id).name)} ${F(d[k + '_adj'])}`).join(' · ') + '</div>';
  const q = f.unit === '$' ? qOf(r, k) : null;
  if (q != null) extra += `<div class="mt-1 text-slate-300">≈ ${fmtQty(q)} ações${k === 'voldia' ? ' negociadas no dia' : '/dia (média)'}${k !== 'voldia' ? ' · financeiro = média de ações × cotação atual' : ''}</div>`;
  return `${head}<table class="tipt">${rows}</table>${extra}<div class="mt-1 text-slate-400">Exibido e usado nos filtros: <b class="text-slate-200">${F(r.v[k])}</b></div>`;
}

const chartSlot = (r) => state.country === 'br' ? `<div class="gchart" data-gt="${r.ticker}"></div>` : '';
function blockHtml(r) {
  const price = val(r, 'preco') ?? (state.source === 'all' ? null : r.v.preco);
  const open = state.expanded.has(r.ticker);
  const varTxt = r.var == null ? '' : `<span class="text-sm font-semibold ${r.var >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${r.var >= 0 ? '▲' : '▼'} ${F2.format(r.var)}%</span>`;
  const stv = state.source === 'all' ? Object.values(r.st || {}) : [];
  const bks = new Set(state.source === 'all' ? r.bk || [] : []), stE = state.source === 'all' ? Object.entries(r.st || {}).filter(([kk]) => !bks.has(kk)).map(([, x]) => x) : [];
  const nRed = stE.filter(x => x === 'red').length, nRes = stE.filter(x => x === 'amb').length, nBank = bks.size, nAdj = state.source === 'all' ? Object.values(r.cm || {}).filter(m => m.aj).length : 0;
  const badges = (nRed ? `<span class="hb hb-red" title="${nRed} indicador(es) sem maioria entre as fontes">≠ ${nRed}</span>` : '') +
                 (nRes ? `<span class="hb hb-res" title="${nRes} indicador(es) com maioria, mas alguma fonte discorda">maioria ${nRes}</span>` : '') +
                 (nBank ? `<span class="hb hb-bank" title="${nBank} indicador(es) baseados em EBIT/receita não comparáveis (banco/seguradora)">banco ${nBank}</span>` : '') +
                 (nAdj ? `<span class="hb hb-adj" title="${nAdj} indicador(es) em que CVM/Dados de Mercado concordam com o Fundamentus via EBIT ajustado">aj ${nAdj}</span>` : '');
  const tags = (r.tags || []).map(t => `<span class="ctag">${t}</span>`).join('');
  return `<article class="blk rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden${open ? ' open' : ''}" data-ticker="${r.ticker}">
    <div class="blk-head px-3 sm:px-4 py-2.5 bg-gradient-to-r from-slate-800/90 to-slate-900/60 cursor-pointer select-none">
      <div class="flex items-center gap-2">
        ${state.selMode ? `<label class="gsel" title="Selecionar ${r.ticker}"><input type="checkbox" data-gsel="${r.ticker}"${state.selSet.has(r.ticker) ? ' checked' : ''}></label>` : ''}<div class="text-2xl font-black tracking-tight text-emerald-300">${r.ticker}</div>
        <div class="ml-auto flex items-baseline gap-2 whitespace-nowrap"><span class="text-xl font-bold text-white">${fmtPrice(price, r.cur)}</span>${varTxt}</div>
      </div>
      ${tags || r.macro ? `<div class="flex flex-wrap items-center gap-1 mt-1">${tags}${r.macro && r.macro !== 'Outros' ? `<span class="ctag ctag-sec">${esc(r.macro)}</span>` : ''}</div>` : ''}
      <div class="flex items-center gap-3 mt-1">
        <div class="min-w-0 flex-1">
          <div class="text-sm text-slate-100 font-medium truncate">${esc(r.nome || '—')}</div>
          <div class="text-[11px] text-slate-400 truncate">${esc([r.setor, r.subsetor].filter(Boolean).join(' · ') || 'Setor não informado')}</div>
        </div>
        <button type="button" class="tgl" aria-expanded="${open}" aria-label="${open ? 'Recolher' : 'Expandir'} indicadores de ${r.ticker}"><span>${open ? '−' : '+'}</span></button>
      </div>
    </div>
    <div class="collapse-wrap"><div class="collapse-inner">${open ? chartSlot(r) + cardsHtml(r) : ''}</div></div>
  </article>`;
}

function setBlockOpen(art, open) {
  const t = art.dataset.ticker, inner = art.querySelector('.collapse-inner'), btn = art.querySelector('.tgl');
  if (open) {
    state.expanded.add(t);
    if (!inner.firstElementChild) { const r = state.rowMap[t]; if (r) inner.innerHTML = chartSlot(r) + cardsHtml(r); }
    requestAnimationFrame(() => art.classList.add('open'));
  } else { state.expanded.delete(t); art.classList.remove('open'); }
  btn.setAttribute('aria-expanded', String(open));
  btn.setAttribute('aria-label', `${open ? 'Recolher' : 'Expandir'} indicadores de ${t}`);
  btn.firstElementChild.textContent = open ? '−' : '+';
}
document.addEventListener('click', (e) => {
  const head = e.target.closest('.blk-head'); if (!head || e.target.closest('.gsel')) return;
  if (window.getSelection && String(window.getSelection()).length) return;
  const art = head.closest('.blk'); setBlockOpen(art, !art.classList.contains('open'));
});
function expandAll(open) {
  if (open) state.filtered.forEach(r => state.expanded.add(r.ticker)); else state.expanded.clear();
  document.querySelectorAll('#results .blk').forEach(a => setBlockOpen(a, open));
}

function renderMore() {
  const next = state.filtered.slice(state.shown, state.shown + PAGE);
  if (state.shown === 0 && !next.length) {
    $('#results').innerHTML = '<div class="rounded-2xl border border-slate-800 p-8 text-center text-slate-500">Nenhum resultado com esses filtros.</div>';
  } else {
    $('#results').insertAdjacentHTML('beforeend', next.map(blockHtml).join(''));
  }
  state.shown += next.length;
  const total = state.filtered.length;
  $('#shown').textContent = total ? `Mostrando ${F0.format(state.shown)} de ${F0.format(total)}` : '';
  $('#btnMore').classList.toggle('hidden', state.shown >= total);
}
// rolagem infinita + botão de fallback
new IntersectionObserver((ents) => {
  if (ents.some(e => e.isIntersecting) && state.data && state.shown < state.filtered.length) renderMore();
}, { rootMargin: '600px' }).observe($('#more'));
$('#btnMore').addEventListener('click', renderMore);

// ---------- Tooltip (desktop) e toque (mobile) ----------
const tt = $('#tooltip');
const hoverCapable = window.matchMedia('(hover: hover)').matches;
function showTip(e, html) {
  tt.innerHTML = html; tt.classList.remove('hidden');
  const x = Math.min(e.clientX + 12, window.innerWidth - tt.offsetWidth - 8);
  const y = Math.min(e.clientY + 12, window.innerHeight - tt.offsetHeight - 8);
  tt.style.left = Math.max(8, x) + 'px'; tt.style.top = Math.max(8, y) + 'px';
}
const nl2br = (t) => esc(t).replace(/\n/g, '<br>');
function cardTip(card) {
  const art = card.closest('.blk'); const r = art && state.rowMap[art.dataset.ticker]; const f = state.fieldMap[card.dataset.key];
  return r && f ? tipHtml(r, f) : '';
}
document.addEventListener('mousemove', (e) => {
  if (!hoverCapable) return;
  const card = e.target.closest('.card.tip');
  if (card && !card.classList.contains('open')) { showTip(e, cardTip(card)); return; }
  const el = e.target.closest('[data-tip-id]');
  if (!el) { tt.classList.add('hidden'); return; }
  showTip(e, nl2br(ruleText()));
});
document.addEventListener('click', (e) => {
  const card = e.target.closest('.card.tip');
  if (card) {
    const open = card.classList.toggle('open');
    if (open) card.querySelector('.detail').innerHTML = cardTip(card);
    tt.classList.add('hidden'); return;
  }
  const rule = e.target.closest('[data-tip-id]');
  if (rule) { showTip(e, nl2br(ruleText())); setTimeout(() => tt.classList.add('hidden'), 8000); return; }
  if (!hoverCapable) tt.classList.add('hidden');
});

function ruleText() {
  const r = state.data?.rule; if (!r) return '';
  const lim = Object.entries(r.abs).map(([k, a]) => `${state.fieldMap[k].label}: ${F2.format(a)}${state.fieldMap[k].unit === '%' ? ' p.p.' : ''}`).join(' · ');
  return `Consenso entre fontes: para cada indicador, procura o maior grupo de fontes que concordam entre si (todos os pares dentro da regra abaixo). Maioria = mais da metade das fontes com valor (um grupo único com exatamente metade, de 2+ fontes, também vale). Exibido: Fundamentus se estiver no grupo, senão a mediana do grupo. Sem maioria = vermelho: se todas diferem, média simples (número amarelo); senão média ponderada — cada grupo repetido pesa tamanho/n e as fontes isoladas entram juntas pela média delas.\nRegra de concordância entre dois valores:\n• sinais opostos (ex.: + vs −) com diferença absoluta acima do limiar; OU\n• diferença relativa > ${Math.round(r.rel * 100)}% (|a−b| ÷ max(|a|,|b|)) E diferença absoluta acima do limiar.\nLimiares absolutos: ${lim}\n(Liquidez 2m não é comparada: janelas diferentes.)`;
}

// ---------- CSV ----------
function exportCsv() {
  const fields = state.data.fields;
  const q = (s) => { s = s == null ? '' : String(s); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const head = ['Ticker', 'Empresa', 'Setor', 'Variação dia (%)', ...fields.map(f => f.label + (f.unit === '%' ? ' (%)' : f.unit === '$' ? ` (${state.data.currency})` : ''))];
  const lines = [head.map(q).join(';')];
  const n = (v) => v == null ? '' : String(v).replace('.', ',');
  for (const r of state.filtered) lines.push([r.ticker, r.nome, r.setor, n(r.var), ...fields.map(f => n(val(r, f.key)))].map(q).join(';'));
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `screener_${state.country}_${state.source}_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

// ---------- País e fonte ----------
function closeMenus(except) {
  document.querySelectorAll('.dd').forEach(dd => { if (dd !== except) { dd.classList.remove('open'); dd.querySelector('.dd-menu').classList.add('hidden'); } });
}
function toggleMenu(dd) {
  const open = !dd.classList.contains('open'); closeMenus(dd);
  dd.classList.toggle('open', open); dd.querySelector('.dd-menu').classList.toggle('hidden', !open);
}
document.addEventListener('click', (e) => { if (!e.target.closest('.dd')) closeMenus(); });
$('#btnCountry').addEventListener('click', () => toggleMenu($('#ddCountry')));
$('#btnSource').addEventListener('click', () => toggleMenu($('#ddSource')));
function renderCountry() {
  const c = state.countries.find(x => x.id === state.country) || { id: 'br', name: 'Brasil', flag: '/static/flags/br.png' };
  $('#countryFlag').src = c.flag; $('#countryFlag').alt = c.name; $('#btnCountry').title = `País: ${c.name}`;
  $('#countryTitle').textContent = c.id === 'br' ? 'B3' : c.name;
  $('#countryMenu').innerHTML = state.countries.map(x => `<button type="button" role="option" data-country="${x.id}" class="${x.id === state.country ? 'sel' : ''}"><img class="flag" src="${x.flag}" alt=""> ${esc(x.name)}<span class="cnt">${x.sources.length > 1 ? x.sources.length + ' fontes' : 'TradingView'}</span></button>`).join('');
}
$('#countryMenu').addEventListener('click', (e) => {
  const b = e.target.closest('[data-country]'); if (!b) return;
  closeMenus();
  if (b.dataset.country === state.country) return;
  state.country = b.dataset.country; state.expanded.clear(); saveView(); renderCountry();
  state.data = null; $('#results').innerHTML = '<div class="rounded-2xl border border-slate-800 p-8 text-center text-slate-500">Carregando…</div>';
  load();
});
function renderSource() {
  const srcs = state.data?.sources || [];
  if (state.source !== 'all' && !srcs.some(s => s.id === state.source)) state.source = 'all';
  const cur = srcs.find(s => s.id === state.source);
  $('#sourceLabel').innerHTML = cur ? `${logoImg(cur.id)} ${esc(cur.name)}` : 'Todos';
  $('#btnSource').classList.toggle('border-emerald-600', !!cur);
  $('#sourceMenu').innerHTML = `<button type="button" role="option" data-src="all" class="${state.source === 'all' ? 'sel' : ''}"><span class="srclogo grid place-items-center text-[10px]">∑</span> Todos <span class="cnt">consenso</span></button>` +
    srcs.map(s => `<button type="button" role="option" data-src="${s.id}" class="${s.id === state.source ? 'sel' : ''}">${logoImg(s.id)} ${esc(s.name)}<span class="cnt">${F0.format(s.count)}</span></button>`).join('');
}
$('#sourceMenu').addEventListener('click', (e) => {
  const b = e.target.closest('[data-src]'); if (!b) return;
  closeMenus(); state.source = b.dataset.src; saveView(); renderSource(); apply();
});

// ---------- Universo: 1 ticker por empresa; remove ilíquidas sem bons resultados (igual a scripts/universe.py) ----------
const isIlliq = (r) => { const v = r.v || {}, liq = v.vol30 != null ? v.vol30 : v.liq2m; return !(v.liq2m > 0) || liq == null || liq < 50000; };
const isPromising = (r) => { const v = r.v || {}; return v.lpa > 0 && v.roe >= 10 && !(v.lucro5a < 0); };
const clsRank = (t) => { const m = /^[A-Z]{4}(\d+)/.exec(t); return ({ '3': 0, '4': 1, '11': 2 })[m ? m[1] : ''] ?? 3; };
function universe(rows) {
  const best = {};
  for (const r of rows) {
    if (isIlliq(r) && !isPromising(r)) continue;
    const k = r.ticker.slice(0, 4), key = [clsRank(r.ticker), -((r.v || {}).liq2m || 0)], b = best[k];
    if (!b || key[0] < b[0][0] || (key[0] === b[0][0] && key[1] < b[0][1])) best[k] = [key, r];
  }
  const keep = new Set(Object.values(best).map(b => b[1]));
  return rows.filter(r => keep.has(r));
}
let PROFILES = null;
async function loadProfiles(rows) {
  if (!PROFILES) { try { const j = await (await fetch('/api/profiles')).json(); PROFILES = j.profiles || {}; } catch (e) { PROFILES = {}; } }
  for (const r of rows) { const p = PROFILES[r.ticker]; if (p) { r.desc = p.d; r.psetor = p.s; r.pind = p.i; } }
}
const norm = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
// ---------- Setor (macro) e classificação ----------
const SECTORS = ['Financeiro', 'Utilidade Pública', 'Materiais Básicos & Commodities', 'Petróleo, Gás e Biocombustíveis', 'Consumo Cíclico', 'Consumo Não Cíclico', 'Agronegócio', 'Saúde', 'Tecnologia & Comunicações', 'Outros'];
const SEC_RULES = [
  [3, /petrol|refino|combustiv|biocomb|acucar e alcool|etanol|oleo e gas/], [1, /energia eletrica|saneamento|\bagua\b|^gas$|\bgas\b(?! integrado)|utilidade|eletric/],
  [0, /banco|segur|ressegur|financ|bolsa|previd|credito|corretora|holding/], [7, /medic|hospit|saude|diagnost|farmac|odontol/],
  [8, /telecom|programas|tecnolog|computador|software|comunica|internet|fidelizac/], [6, /agric|agropec|fertiliz|defensiv|sement|graos/],
  [5, /alimento|bebida|cerveja|carnes|supermerc|uso pessoal|limpeza|frigor/],
  [4, /varejo|tecido|vestuar|calcad|incorpora|construc|eletrodom|automove|viage|educac|hotel|restaurante|aluguel de carro|comercio|e-commerce|esport|eventos|imobili|acessorio/],
  [2, /siderur|minera|minerais|papel|celulose|quimic|embalag|metal|cobre|madeira|aco\b/]];
const TV_SEC = { 'Finance': 0, 'Utilities': 1, 'Energy Minerals': 3, 'Non-Energy Minerals': 2, 'Process Industries': 2, 'Retail Trade': 4, 'Consumer Durables': 4, 'Consumer Services': 4,
  'Consumer Non-Durables': 5, 'Health Services': 7, 'Health Technology': 7, 'Technology Services': 8, 'Communications': 8, 'Electronic Technology': 8 };
function macroSector(r) {
  for (const txt of [norm(r.subsetor), norm(r.pind), norm(r.psetor)]) { if (!txt) continue; for (const [i, re] of SEC_RULES) if (re.test(txt)) return SECTORS[i]; }
  return SECTORS[TV_SEC[r.setor] ?? 9];
}
// Classificação (máx. 2, por prioridade). Regras explicadas no painel ⓘ.
function classify(r) {
  const v = r.v || {}, sec = r.macro, out = [];
  const defSec = ['Utilidade Pública', 'Financeiro', 'Saúde', 'Consumo Não Cíclico'].includes(sec);
  const perene = (sec === 'Utilidade Pública' || /banco|segur/.test(norm(r.subsetor + ' ' + (r.pind || '')))) && v.dy > 5 && v.roe > 10 && !(v.lucro5a < 0) && v.lpa > 0;
  if (perene) out.push('Perenes');
  if (Math.max(v.cresc5a ?? -1e9, v.lucro5a ?? -1e9) > 15 && v.lpa > 0) out.push('Growth');
  if (v.lpa > 0 && v.lucro5a != null && v.lucro5a <= 0 && v.roe > 0) out.push('Turnaround');
  if (v.pl > 0 && v.pl <= 10 && v.pvp > 0 && v.pvp < 1.5) out.push('Valor');
  if (!perene) out.push(defSec ? 'Defensivas' : ['Materiais Básicos & Commodities', 'Petróleo, Gás e Biocombustíveis', 'Consumo Cíclico', 'Agronegócio'].includes(sec) ? 'Cíclicas' : null);
  return out.filter(Boolean).slice(0, 2);
}
function prepRow(r) {
  r.macro = macroSector(r); r.tags = classify(r);
  r._s = norm([r.ticker, r.nome, r.setor, r.subsetor, r.psetor, r.pind, r.macro, r.desc].filter(Boolean).join(' | '));
}

function friendlyStatus(s, upd) {
  s = String(s || '');
  const m = /(\d{2})\/(\d{2})\/\d{4} (\d{2}:\d{2})/.exec(s);
  if (/ao vivo/i.test(s) && !/bloque|falh|erro/i.test(s.split('ao vivo')[0])) return 'ao vivo' + (upd ? ' · atualizado em ' + String(upd).slice(0, 5) + ' ' + String(upd).slice(11, 16) : '');
  if (m) return `atualizado em ${m[1]}/${m[2]} ${m[3]}`;
  if (/indispon|falh|erro|bloque|sem snapshot/i.test(s)) return 'indisponível no momento';
  return upd ? 'atualizado em ' + String(upd).slice(0, 5) + ' ' + String(upd).slice(11, 16) : 'atualizado';
}
// Sem sugestões/autopreenchimento do Chrome em nenhum campo
(function noAutofill() {
  const fix = (root) => (root.querySelectorAll ? root.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=file])') : []).forEach(i => {
    if (i.dataset.naf) return; i.dataset.naf = '1';
    i.setAttribute('autocomplete', 'off'); i.setAttribute('autocorrect', 'off'); i.setAttribute('spellcheck', 'false');
    if (!i.name) i.name = 'f_' + Math.random().toString(36).slice(2, 8);
  });
  fix(document);
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => n.nodeType === 1 && fix(n.parentNode || n)))).observe(document.body, { childList: true, subtree: true });
})();

// ---------- Carga ----------
let loadSeq = 0, built = false;
async function load() {
  const seq = ++loadSeq, country = state.country;
  try {
    const r = await fetch(`/api/data?country=${country}`, { cache: 'no-store' });
    if (seq !== loadSeq) return;
    if (r.status === 503) { $('#updated').textContent = 'Buscando dados nas fontes…'; setTimeout(load, 3000); return; }
    if (!r.ok) { const j = await r.json().catch(() => ({})); $('#updated').textContent = 'Fonte indisponível: ' + (j.error || r.status); setTimeout(load, 15000); return; }
    const d = await r.json();
    if (country === 'br') { d.rows = universe(d.rows); await loadProfiles(d.rows); }
    d.rows.forEach(prepRow);
    state.data = d; state.rows = d.rows; state.rowMap = Object.fromEntries(d.rows.map(x => [x.ticker, x])); state.fieldMap = Object.fromEntries(d.fields.map(f => [f.key, f]));
    $('#updated').innerHTML = `<span class="hidden sm:inline">Atualizado: </span><b class="text-slate-200">${d.updated_at_sp}</b> <span class="hidden sm:inline">(Brasília)</span>` + (d.refreshing ? ' · <span class="text-amber-400">atualizando…</span>' : '');
    const st = d.status || {}, c = d.counts || {};
    const L = { fundamentus: 'Fundamentus', statusinvest: 'Status Invest', cvm: 'CVM', investidor10: 'Investidor10', tradingview: 'TradingView', dadosdemercado: 'Dados de Mercado', yfinance: 'Yahoo' };
    $('#srcStatus').innerHTML = Object.entries(L).filter(([k]) => st[k]).map(([k, n]) => `<div><b class="text-slate-300">${n}</b>: ${friendlyStatus(st[k], d.updated_at_sp)}</div>`).join('');
    $('#consSummary').innerHTML = country === 'br' ? '' : `${F0.format(c.tickers || d.rows.length)} ações (maiores por valor de mercado) · fonte única: TradingView`;
    $('#consSummary').style.display = country === 'br' ? 'none' : '';
    $('#subtitle').textContent = country === 'br' ? 'Consenso entre ' + (d.sources || []).length + ' fontes' : 'Fonte: TradingView (scanner)';
    if (!built) { buildFilters(); buildSort(); built = true; } else { renderFilterUI(); buildSortOptions(); }
    renderSource();
    computeFilters(); apply();
    if (d.refreshing) setTimeout(load, 3000);
  } catch (e) { if (seq === loadSeq) { $('#updated').textContent = 'Erro ao carregar: ' + e; setTimeout(load, 5000); } }
}
async function init() {
  try { state.countries = await (await fetch('/api/countries')).json(); } catch (e) { state.countries = []; }
  if (!state.countries.some(c => c.id === state.country)) state.country = 'br';
  renderCountry(); load();
}

let qTimer;
$('#q').addEventListener('input', () => { clearTimeout(qTimer); qTimer = setTimeout(apply, 60); });
$('#onlyLiquid').addEventListener('change', apply);
$('#btnClear').addEventListener('click', () => { $('#q').value = ''; clearFilters(); });
$('#btnCsv').addEventListener('click', exportCsv);
const infoOpen = (o) => { $('#infoModal').classList.toggle('hidden', !o); document.body.style.overflow = o ? 'hidden' : ''; };
$('#btnInfo').addEventListener('click', () => infoOpen(true));
$('#infoModal').addEventListener('click', (e) => { if (e.target.id === 'infoModal' || e.target.closest('[data-close]')) infoOpen(false); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#infoModal').classList.contains('hidden')) infoOpen(false); });
$('#btnExpandAll').addEventListener('click', () => expandAll(true));
$('#btnCollapseAll').addEventListener('click', () => expandAll(false));
$('#btnRefresh').addEventListener('click', async () => {
  $('#btnRefresh').disabled = true; $('#btnRefresh').classList.add('spin'); if (!$('#updated').textContent.includes('atualizando')) $('#updated').innerHTML += ' · <span class="text-amber-400">atualizando…</span>';
  await fetch('/api/refresh', { method: 'POST' }); setTimeout(async () => { await load(); $('#btnRefresh').disabled = false; $('#btnRefresh').classList.remove('spin'); }, 2500);
});
setInterval(load, 10 * 60 * 1000);
init();
