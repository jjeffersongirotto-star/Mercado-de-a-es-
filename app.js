const state = { data: null, rows: [], filtered: [], sortKey: 'liq2m', sortDir: -1, filters: {} };
const $ = (s) => document.querySelector(s);
const nf = (d) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const F2 = nf(2), F0 = nf(0);

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
  const note = document.createElement('div');
  note.className = 'col-span-full text-[11px] text-slate-500';
  note.innerHTML = '<span class="text-emerald-400 font-bold">≥</span> maior é melhor · <span class="text-sky-400 font-bold">≤</span> menor é melhor · <sup>+</sup> ao filtrar ≤, valores negativos são excluídos (ex.: P/L negativo = prejuízo). Liquidez em R$ (ex.: 1000000 = R$ 1 mi/dia).';
  box.appendChild(note);
  box.querySelectorAll('input').forEach(i => i.addEventListener('input', () => {
    const v = i.value.trim(); if (v === '') delete state.filters[i.dataset.key]; else state.filters[i.dataset.key] = parseFloat(v.replace(',', '.'));
    apply();
  }));
}

function buildHead() {
  const cols = [{ key: 'ticker', label: 'Ticker' }, { key: 'nome', label: 'Empresa' }, ...state.data.fields];
  $('#thead').innerHTML = '<tr>' + cols.map((c, i) => {
    const arrow = state.sortKey === c.key ? (state.sortDir > 0 ? ' ▲' : ' ▼') : '';
    const h = c.dir ? hint(c) : null;
    return `<th data-key="${c.key}" class="${i === 0 ? 'sticky-col ' : ''}bg-slate-900 px-3 py-2 text-${i < 2 ? 'left' : 'right'} whitespace-nowrap cursor-pointer select-none hover:text-white border-b border-slate-700" title="${h ? h.txt : ''}">${c.label}${arrow}</th>`;
  }).join('') + '</tr>';
  $('#thead').querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.key; if (state.sortKey === k) state.sortDir *= -1; else { state.sortKey = k; state.sortDir = (k === 'ticker' || k === 'nome') ? 1 : -1; }
    buildHead(); apply();
  }));
}

function passes(r) {
  const q = $('#q').value.trim().toLowerCase();
  if (q && !(r.ticker.toLowerCase().includes(q) || (r.nome || '').toLowerCase().includes(q))) return false;
  if ($('#onlyLiquid').checked && !((r.v.liq2m || 0) > 0)) return false;
  for (const [k, x] of Object.entries(state.filters)) {
    if (Number.isNaN(x)) continue;
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
    let va = (k === 'ticker' || k === 'nome') ? a[k] : a.v[k], vb = (k === 'ticker' || k === 'nome') ? b[k] : b.v[k];
    if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1;
    return (typeof va === 'string' ? va.localeCompare(vb, 'pt-BR') : va - vb) * d;
  });
  $('#count').textContent = F0.format(state.filtered.length);
  render();
}

function render() {
  const fields = state.data.fields; const out = [];
  const rows = state.filtered;
  for (const r of rows) {
    let tds = `<td class="sticky-col bg-slate-950 px-3 py-1.5 font-semibold text-emerald-300 whitespace-nowrap">${r.ticker}</td>
      <td class="px-3 py-1.5 whitespace-nowrap max-w-[220px] truncate text-slate-300" title="${(r.nome || '') + (r.setor ? ' — ' + r.setor : '')}">${r.nome || '<span class="text-slate-600">—</span>'}</td>`;
    for (const f of fields) {
      const v = r.v[f.key]; const src = r.src[f.key]; const dv = r.div[f.key];
      let cls = 'px-3 py-1.5 text-right whitespace-nowrap'; let tip = '';
      if (src === 'si') { cls += ' cell-bold'; tip = 'Valor do Status Invest (Fundamentus sem dado)'; }
      if (src === 'calc') { cls += ' italic'; tip = 'Calculado a partir do Fundamentus'; }
      if (dv) { cls += ' cell-red tip'; tip = `Divergência grosseira\nFundamentus: ${fmt(dv[0], f.unit, f.key)}\nStatus Invest: ${fmt(dv[1], f.unit, f.key)}\n(exibido: Fundamentus)`; }
      if (v !== null && v !== undefined && v < 0 && !dv) cls += ' text-rose-400';
      tds += `<td class="${cls}"${tip ? ` data-tip="${tip.replace(/"/g, '&quot;')}"` : ''}>${fmt(v, f.unit, f.key)}</td>`;
    }
    out.push(`<tr class="hover:bg-slate-900/80">${tds}</tr>`);
  }
  $('#tbody').innerHTML = out.join('') || `<tr><td colspan="${fields.length + 2}" class="px-3 py-8 text-center text-slate-500">Nenhum resultado com esses filtros.</td></tr>`;
}

// Tooltip (funciona com mouse e toque)
const tt = $('#tooltip');
function showTip(e, text) { tt.textContent = text; tt.classList.remove('hidden');
  const x = Math.min(e.clientX + 12, window.innerWidth - tt.offsetWidth - 8); const y = Math.min(e.clientY + 12, window.innerHeight - tt.offsetHeight - 8);
  tt.style.left = x + 'px'; tt.style.top = y + 'px'; }
document.addEventListener('mouseover', (e) => {
  const el = e.target.closest('[data-tip],[data-tip-id]'); if (!el) { tt.classList.add('hidden'); return; }
  showTip(e, el.dataset.tip || ruleText());
});
document.addEventListener('mousemove', (e) => { if (!tt.classList.contains('hidden')) { const el = e.target.closest('[data-tip],[data-tip-id]'); if (el) showTip(e, el.dataset.tip || ruleText()); } });
document.addEventListener('touchstart', (e) => { const el = e.target.closest('[data-tip],[data-tip-id]'); if (el) { const t = e.touches[0]; showTip(t, el.dataset.tip || ruleText()); } else tt.classList.add('hidden'); }, { passive: true });

function ruleText() {
  const r = state.data?.rule; if (!r) return '';
  const lim = Object.entries(r.abs).map(([k, a]) => `${state.fieldMap[k].label}: ${F2.format(a)}${state.fieldMap[k].unit === '%' ? ' p.p.' : ''}`).join(' · ');
  return `Regra de divergência (indicadores presentes nas duas fontes):\n• sinais opostos (ex.: + vs −) com diferença absoluta acima do limiar; OU\n• diferença relativa > ${Math.round(r.rel * 100)}% (|a−b| ÷ max(|a|,|b|)) E diferença absoluta acima do limiar.\nO valor exibido é o do Fundamentus.\nLimiares absolutos: ${lim}\n(Liquidez 2m não é comparada: janelas diferentes.)`;
}

function exportCsv() {
  const fields = state.data.fields;
  const esc = (s) => { s = s == null ? '' : String(s); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const head = ['Ticker', 'Empresa', 'Setor', ...fields.map(f => f.label + (f.unit === '%' ? ' (%)' : ''))];
  const lines = [head.map(esc).join(';')];
  for (const r of state.filtered) lines.push([r.ticker, r.nome, r.setor, ...fields.map(f => r.v[f.key] == null ? '' : String(r.v[f.key]).replace('.', ','))].map(esc).join(';'));
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `screener_b3_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

async function load() {
  try {
    const r = await fetch('/api/data', { cache: 'no-store' });
    if (r.status === 503) { $('#updated').textContent = 'Buscando dados nas fontes…'; setTimeout(load, 3000); return; }
    const d = await r.json(); const first = !state.data;
    state.data = d; state.rows = d.rows; state.fieldMap = Object.fromEntries(d.fields.map(f => [f.key, f]));
    $('#updated').innerHTML = `Atualizado: <b class="text-slate-200">${d.updated_at_sp}</b> (horário de Brasília)` + (d.refreshing ? ' · <span class="text-amber-400">atualizando…</span>' : '');
    const st = d.status || {};
    $('#srcStatus').textContent = `Fundamentus: ${st.fundamentus || '?'} · Status Invest: ${st.statusinvest || '?'} · ${F0.format(d.counts.red)} divergências · ${F0.format(d.counts.bold)} complementos`;
    if (first) { buildFilters(); buildHead(); }
    apply();
    if (d.refreshing) setTimeout(load, 3000);
  } catch (e) { $('#updated').textContent = 'Erro ao carregar: ' + e; setTimeout(load, 5000); }
}

$('#q').addEventListener('input', apply);
$('#onlyLiquid').addEventListener('change', apply);
$('#btnClear').addEventListener('click', () => { state.filters = {}; document.querySelectorAll('#filters input').forEach(i => i.value = ''); $('#q').value = ''; apply(); });
$('#btnCsv').addEventListener('click', exportCsv);
$('#btnRefresh').addEventListener('click', async () => {
  $('#btnRefresh').disabled = true; $('#updated').innerHTML += ' · <span class="text-amber-400">atualizando…</span>';
  await fetch('/api/refresh', { method: 'POST' }); setTimeout(async () => { await load(); $('#btnRefresh').disabled = false; }, 2500);
});
setInterval(load, 10 * 60 * 1000);
load();
