const PAGE = 30;
const state = { data: null, rows: [], filtered: [], shown: 0, sortKey: 'liq2m', sortDir: -1, filters: {}, fieldMap: {} };
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
function fmt(v, unit, key) {
  if (v === null || v === undefined) return '–';
  if (['liq2m', 'patrliq', 'valmerc'].includes(key)) return fmtBig(v);
  if (unit === '%') return F2.format(v) + '%';
  return F2.format(v);
}
function hint(f) {
  if (f.dir === 'high') return { sym: '≥', txt: `Maior é melhor: mostra ${f.label} ≥ valor` };
  if (f.dir === 'low') return { sym: '≤', txt: `Menor é melhor: mostra ${f.label} ≤ valor` + (f.excludeNeg ? ' (exclui negativos)' : ' (negativos incluídos: caixa líquido)') };
  return null;
}

// ---------- Filtros ----------
function buildFilters() {
  const box = $('#filters'); box.innerHTML = '';
  for (const f of state.data.fields) {
    const h = hint(f); if (!h) continue;
    const el = document.createElement('label');
    el.className = 'flex flex-col gap-1 bg-slate-950/60 border border-slate-800 rounded-lg px-2 py-1.5';
    el.title = h.txt + (f.unit === '%' ? ' — digite 8 para 8%' : '');
    el.innerHTML = `<span class="text-[11px] text-slate-400 flex justify-between gap-1"><span class="truncate">${f.label}${f.unit === '%' ? ' (%)' : ''}</span>
      <span class="font-bold ${f.dir === 'high' ? 'text-emerald-400' : 'text-sky-400'}">${h.sym}${f.excludeNeg ? '<sup class="text-[9px]">+</sup>' : ''}</span></span>
      <input data-key="${f.key}" type="number" step="any" inputmode="decimal" placeholder="${h.sym} …"
        class="w-full bg-transparent outline-none text-sm text-slate-100 placeholder:text-slate-600">`;
    box.appendChild(el);
  }
  box.querySelectorAll('input').forEach(i => i.addEventListener('input', () => {
    const v = i.value.trim().replace(',', '.');
    if (v === '' || Number.isNaN(parseFloat(v))) delete state.filters[i.dataset.key]; else state.filters[i.dataset.key] = parseFloat(v);
    i.closest('label').classList.toggle('border-emerald-600', i.dataset.key in state.filters);
    updateFiltersLabel(); apply();
  }));
}
function updateFiltersLabel() {
  const n = Object.keys(state.filters).length;
  $('#filtersLabel').textContent = n ? `Filtros (${n} ativo${n > 1 ? 's' : ''})` : 'Filtros';
  $('#btnFilters').classList.toggle('border-emerald-600', n > 0);
}
function setFiltersOpen(open) {
  $('#filtersPanel').classList.toggle('hidden', !open);
  $('#btnFilters').setAttribute('aria-expanded', String(open));
  $('#filtersChevron').textContent = open ? '▴' : '▾';
}

// ---------- Ordenação ----------
function buildSort() {
  const sel = $('#sortKey');
  const opts = [{ key: 'ticker', label: 'Ticker' }, { key: 'nome', label: 'Empresa' }, { key: 'var', label: 'Variação dia' }, ...state.data.fields];
  sel.innerHTML = opts.map(o => `<option value="${o.key}">${esc(o.label)}</option>`).join('');
  sel.value = state.sortKey;
  sel.addEventListener('change', () => {
    state.sortKey = sel.value;
    const f = state.fieldMap[sel.value];
    state.sortDir = (sel.value === 'ticker' || sel.value === 'nome') ? 1 : (f && f.dir === 'low' ? 1 : -1);
    updateSortDir(); apply();
  });
  $('#sortDir').addEventListener('click', () => { state.sortDir *= -1; updateSortDir(); apply(); });
  updateSortDir();
}
function updateSortDir() { $('#sortDir').textContent = state.sortDir > 0 ? '↑ Asc' : '↓ Desc'; }
const getVal = (r, k) => (k === 'ticker' || k === 'nome') ? r[k] : (k === 'var' ? r.var : r.v[k]);

function passes(r) {
  const q = $('#q').value.trim().toLowerCase();
  if (q && !(r.ticker.toLowerCase().includes(q) || (r.nome || '').toLowerCase().includes(q))) return false;
  if ($('#onlyLiquid').checked && !((r.v.liq2m || 0) > 0)) return false;
  for (const [k, x] of Object.entries(state.filters)) {
    const f = state.fieldMap[k]; const v = r.v[k];
    if (v === null || v === undefined) return false;
    if (f.dir === 'high' && !(v >= x)) return false;
    if (f.dir === 'low') { if (!(v <= x)) return false; if (f.excludeNeg && v < 0) return false; }
  }
  return true;
}

function apply() {
  const k = state.sortKey, d = state.sortDir;
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
function blockHtml(r) {
  const fields = state.data.fields;
  const price = r.v.preco;
  const varTxt = r.var == null ? '' : `<span class="text-sm font-semibold ${r.var >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${r.var >= 0 ? '▲' : '▼'} ${F2.format(r.var)}%</span>`;
  let cards = '';
  for (const f of fields) {
    if (f.key === 'preco') continue;
    const v = r.v[f.key], src = r.src[f.key], dv = r.div[f.key];
    const cls = ['card'];
    let tip = '';
    if (v === null || v === undefined) cls.push('na');
    else if (v < 0) cls.push('neg');
    if (src === 'si') { cls.push('si'); tip = 'Valor do Status Invest (Fundamentus sem dado)'; }
    if (src === 'calc') { cls.push('calc'); tip = 'Calculado a partir do Fundamentus (cotação ÷ múltiplo)'; }
    if (dv) { cls.push('red'); tip = `Divergência grosseira\nFundamentus: ${fmt(dv[0], f.unit, f.key)}\nStatus Invest: ${fmt(dv[1], f.unit, f.key)}\n(exibido: Fundamentus)`; }
    const badge = dv ? '<span class="badge bg-red-600 text-white">≠</span>' : (src === 'si' ? '<span class="badge bg-slate-700 text-slate-200">SI</span>' : '');
    cards += `<div class="${cls.join(' ')}"${tip ? ` data-tip="${esc(tip)}"` : ''} data-key="${f.key}">
      <div class="lbl"><span class="truncate">${esc(f.label)}</span>${badge}</div>
      <div class="val">${fmt(v, f.unit, f.key)}</div>${tip ? `<div class="detail">${esc(tip)}</div>` : ''}</div>`;
  }
  return `<article class="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden" data-ticker="${r.ticker}">
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 sm:px-4 py-2.5 bg-gradient-to-r from-slate-800/90 to-slate-900/60 border-b border-slate-800">
      <div class="text-2xl font-black tracking-tight text-emerald-300">${r.ticker}</div>
      <div class="min-w-0 flex-1 basis-full sm:basis-0 order-last sm:order-none">
        <div class="text-sm text-slate-100 font-medium truncate">${esc(r.nome || '—')}</div>
        <div class="text-[11px] text-slate-400 truncate">${esc([r.setor, r.subsetor].filter(Boolean).join(' · ') || 'Setor não informado')}</div>
      </div>
      <div class="flex items-baseline gap-2 ml-auto">
        <span class="text-xl font-bold text-white">${price == null ? '–' : 'R$ ' + F2.format(price)}</span>${varTxt}
      </div>
    </div>
    <div class="cards p-2.5 sm:p-3">${cards}</div>
  </article>`;
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
function showTip(e, text) {
  tt.textContent = text; tt.classList.remove('hidden');
  const x = Math.min(e.clientX + 12, window.innerWidth - tt.offsetWidth - 8);
  const y = Math.min(e.clientY + 12, window.innerHeight - tt.offsetHeight - 8);
  tt.style.left = Math.max(8, x) + 'px'; tt.style.top = Math.max(8, y) + 'px';
}
document.addEventListener('mousemove', (e) => {
  if (!hoverCapable) return;
  const el = e.target.closest('[data-tip],[data-tip-id]');
  if (!el || (el.classList.contains('card') && el.classList.contains('open'))) { tt.classList.add('hidden'); return; }
  showTip(e, el.dataset.tip || ruleText());
});
document.addEventListener('click', (e) => {
  const card = e.target.closest('.card[data-tip]');
  if (card) { card.classList.toggle('open'); tt.classList.add('hidden'); return; }
  const rule = e.target.closest('[data-tip-id]');
  if (rule) { showTip(e, ruleText()); setTimeout(() => tt.classList.add('hidden'), 8000); return; }
  if (!hoverCapable) tt.classList.add('hidden');
});

function ruleText() {
  const r = state.data?.rule; if (!r) return '';
  const lim = Object.entries(r.abs).map(([k, a]) => `${state.fieldMap[k].label}: ${F2.format(a)}${state.fieldMap[k].unit === '%' ? ' p.p.' : ''}`).join(' · ');
  return `Regra de divergência (indicadores presentes nas duas fontes):\n• sinais opostos (ex.: + vs −) com diferença absoluta acima do limiar; OU\n• diferença relativa > ${Math.round(r.rel * 100)}% (|a−b| ÷ max(|a|,|b|)) E diferença absoluta acima do limiar.\nO valor exibido é o do Fundamentus.\nLimiares absolutos: ${lim}\n(Liquidez 2m não é comparada: janelas diferentes.)`;
}

// ---------- CSV ----------
function exportCsv() {
  const fields = state.data.fields;
  const q = (s) => { s = s == null ? '' : String(s); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const head = ['Ticker', 'Empresa', 'Setor', 'Variação dia (%)', ...fields.map(f => f.label + (f.unit === '%' ? ' (%)' : ''))];
  const lines = [head.map(q).join(';')];
  const n = (v) => v == null ? '' : String(v).replace('.', ',');
  for (const r of state.filtered) lines.push([r.ticker, r.nome, r.setor, n(r.var), ...fields.map(f => n(r.v[f.key]))].map(q).join(';'));
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `screener_b3_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

// ---------- Carga ----------
async function load() {
  try {
    const r = await fetch('/api/data', { cache: 'no-store' });
    if (r.status === 503) { $('#updated').textContent = 'Buscando dados nas fontes…'; setTimeout(load, 3000); return; }
    const d = await r.json(); const first = !state.data;
    state.data = d; state.rows = d.rows; state.fieldMap = Object.fromEntries(d.fields.map(f => [f.key, f]));
    $('#updated').innerHTML = `<span class="hidden sm:inline">Atualizado: </span><b class="text-slate-200">${d.updated_at_sp}</b> <span class="hidden sm:inline">(Brasília)</span>` + (d.refreshing ? ' · <span class="text-amber-400">atualizando…</span>' : '');
    const st = d.status || {};
    $('#srcStatus').textContent = `Fundamentus: ${st.fundamentus || '?'} · Status Invest: ${st.statusinvest || '?'} · ${F0.format(d.counts.red)} divergências · ${F0.format(d.counts.bold)} complementos`;
    if (first) { buildFilters(); buildSort(); }
    apply();
    if (d.refreshing) setTimeout(load, 3000);
  } catch (e) { $('#updated').textContent = 'Erro ao carregar: ' + e; setTimeout(load, 5000); }
}

let qTimer;
$('#q').addEventListener('input', () => { clearTimeout(qTimer); qTimer = setTimeout(apply, 150); });
$('#onlyLiquid').addEventListener('change', apply);
$('#btnFilters').addEventListener('click', () => setFiltersOpen($('#filtersPanel').classList.contains('hidden')));
$('#btnClear').addEventListener('click', () => {
  state.filters = {}; document.querySelectorAll('#filters input').forEach(i => { i.value = ''; i.closest('label').classList.remove('border-emerald-600'); });
  $('#q').value = ''; updateFiltersLabel(); apply();
});
$('#btnCsv').addEventListener('click', exportCsv);
$('#btnRefresh').addEventListener('click', async () => {
  $('#btnRefresh').disabled = true; $('#updated').innerHTML += ' · <span class="text-amber-400">atualizando…</span>';
  await fetch('/api/refresh', { method: 'POST' }); setTimeout(async () => { await load(); $('#btnRefresh').disabled = false; }, 2500);
});
setFiltersOpen(!isMobile());
setInterval(load, 10 * 60 * 1000);
load();
