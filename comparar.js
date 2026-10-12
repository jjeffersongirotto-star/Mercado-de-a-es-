// ---------- Aba Comparar ----------
(function () {
  const $c = (s) => document.querySelector(s);
  const KEY = 'screenerB3.comparar.v1';
  const IDX = [['@ibov', 'Ibovespa', 'ibov'], ['@usd', 'Dólar', 'usd'], ['@cdi', 'CDB 100% do CDI', 'cdi'], ['@ipca', 'Inflação (IPCA)', 'ipca'], ['@poup', 'Poupança', 'poup'], ['@gold', 'Ouro', 'gold']];
  const COLORS = ['#34d399', '#60a5fa', '#facc15', '#f472b6', '#fb923c', '#a78bfa', '#d4a373', '#22d3ee', '#f87171', '#a3e635', '#e879f9', '#94a3b8'];
  const today = new Date().toISOString().slice(0, 10), yago = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
  let S = (() => { try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; } })();
  S.items = S.items || []; S.min = !!S.min; S.all = !!S.all; S.crit = S.crit || 'preco'; S.di = S.di || yago; S.df = S.df || today; S.qa = ''; S.qb = '';
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ items: S.items, crit: S.crit, di: S.di, df: S.df, min: S.min, all: S.all })); } catch (e) { } };
  const rows = () => state.data ? state.data.rows : [];
  const isIdx = (id) => id[0] === '@';
  const label = (id) => isIdx(id) ? IDX.find(x => x[0] === id)[1] : id;
  const root = $c('#compRoot');
  let vals = {}, seq = 0;

  function shell() {
    const fields = (state.data?.fields || []).filter(f => f.key !== 'preco');
    root.innerHTML = `<section class="cmp-top">
      <label class="cmp-lbl">Principal</label>
      <div id="cmpPrin" class="cmp-prin"></div>
      <div class="cmp-srch" data-w="p"><input id="cmpP" type="search" placeholder="Buscar ação ou índice principal…" autocomplete="off"><div class="pv-combo hidden"></div></div>
      <label class="cmp-lbl">Comparar com</label>
      <div class="cmp-srch" data-w="q"><input id="cmpQ" type="search" placeholder="Adicionar ação ou índice…" autocomplete="off"><div class="pv-combo hidden"></div></div>
      <div class="cmp-row"><label>Critério<select id="cmpCrit" class="sel"><option value="preco">Preço da ação</option>${fields.map(f => `<option value="${f.key}">${esc(f.label)}</option>`).join('')}</select></label>
        <label>Início<input id="cmpDi" type="date" class="sel"></label><label>Fim<input id="cmpDf" type="date" class="sel"></label></div>
      <div id="cmpChips" class="cmp-chips"></div><button type="button" id="cmpAll" class="cmp-allb"></button></section>
      <div class="cmp-bar"><button type="button" id="cmpMin" class="cmp-minb"></button></div>
      <div id="cmpChart" class="gchart cmp-chart" data-m="1"><div class="gc-body"><div class="gc-plot"></div><div class="gc-leg"></div></div></div>
      <section class="cmp-cols"><div class="cmp-col"><h3 class="dn">Renderam menos</h3><input class="cmp-f" data-q="qa" type="search" placeholder="Filtrar…" autocomplete="off"><div id="cmpLess"></div></div>
        <div class="cmp-col"><h3 class="up">Renderam mais</h3><input class="cmp-f" data-q="qb" type="search" placeholder="Filtrar…" autocomplete="off"><div id="cmpMore"></div></div></section>`;
    $c('#cmpCrit').value = S.crit; $c('#cmpDi').value = S.di; $c('#cmpDf').value = S.df;
  }
  function chips() {
    const ind = S.crit !== 'preco', ref = S.items[0];
    $c('#cmpPrin').innerHTML = ref ? `<span class="cmp-chip ref" style="--cc:${COLORS[0]}">${esc(label(ref))}<b class="cmp-pv ${vals[ref] > 0 ? 'up' : vals[ref] < 0 ? 'dn' : ''}">${vals[ref] != null ? (ind ? F2.format(vals[ref]) : pc(vals[ref])) : ''}</b><button type="button" data-rm="${esc(ref)}" aria-label="Remover principal">✕</button></span>${S.items.length > 1 ? '<button type="button" id="cmpSwap" class="cmp-swap" title="Trocar principal" aria-label="Trocar principal">⇅</button>' : ''}` : '';
    $c('#cmpP').closest('.cmp-srch').classList.toggle('hidden', !!ref);
    $c('#cmpChips').innerHTML = S.items.slice(1).map((id, j) => `<span class="cmp-chip${ind && isIdx(id) ? ' off' : ''}" style="--cc:${COLORS[(j + 1) % COLORS.length]}">${esc(label(id))}<button type="button" data-rm="${esc(id)}" aria-label="Remover ${esc(label(id))}">✕</button></span>`).join('');
    $c('#cmpDi').disabled = $c('#cmpDf').disabled = ind;
    $c('#cmpAll').textContent = S.all ? 'Voltar' : 'Comparar tudo';
    $c('#cmpAll').classList.toggle('on', S.all);
    $c('#cmpMin').classList.toggle('hidden', S.all);
    $c('#cmpMin').textContent = S.min ? '▸ Expandir gráfico' : '▾ Minimizar gráfico';
    $c('#cmpMin').setAttribute('aria-expanded', String(!S.min));
  }
  let MET = null;
  const metrics = async () => MET || (MET = fetch('/api/metrics').then(r => r.json()).then(d => d.metrics || {}).catch(() => { MET = null; return {}; }));
  function monthRet(m, di, df) {
    if (!m || !m.mc || !m.mc0) return null;
    const [y0, m0] = m.mc0.split('-').map(Number), ix = (s) => (+s.slice(0, 4) - y0) * 12 + (+s.slice(5, 7) - m0);
    const a = ix(di) - 1, b = Math.min(ix(df), m.mc.length - 1);
    if (a < 0 || b <= a || !m.mc[a]) return null;
    return (m.mc[b] / m.mc[a] - 1) * 100;
  }
  function drop(e) {
    const box = e.target.closest('.cmp-srch'), q = norm(e.target.value).trim(), d = box.querySelector('.pv-combo');
    if (!q) { d.classList.add('hidden'); return; }
    const ind = S.crit !== 'preco';
    const idx = IDX.filter(x => norm(x[1]).includes(q) && !S.items.includes(x[0])).map(x => ({ id: x[0], t: x[1], s: 'índice', off: ind }));
    const st = rows().filter(r => !S.items.includes(r.ticker) && (r._s ? r._s.includes(q) : norm(r.ticker + ' ' + r.nome).includes(q))).map(r => [r, searchRank(r, q)]).sort((a, b) => a[1] - b[1]).map(x => x[0]).slice(0, 30).map(r => ({ id: r.ticker, t: r.ticker, s: r.nome || '' }));
    const L = idx.concat(st);
    d.innerHTML = L.length ? L.map(o => `<button type="button" data-add="${esc(o.id)}" data-w="${box.dataset.w}"${o.off ? ' disabled' : ''}><b>${esc(o.t)}</b><span>${esc(o.s)}${o.off ? ' · indisponível para indicadores' : ''}</span></button>`).join('') : '<div class="px-3 py-2 text-xs text-slate-500">Nada encontrado.</div>';
    d.classList.remove('hidden');
  }
  async function compute() {
    const my = ++seq, ind = S.crit !== 'preco', chart = $c('#cmpChart');
    vals = {};
    if (ind) {
      chart.classList.add('hidden');
      const byT = new Map(rows().map(r => [r.ticker, r]));
      for (const id of S.items) if (!isIdx(id)) { const r = byT.get(id); if (r && r.v[S.crit] != null) vals[id] = r.v[S.crit]; }
      if (S.all) for (const r of rows()) if (r.v[S.crit] != null) vals[r.ticker] = r.v[S.crit];
      cols(); return;
    }
    chart.classList.toggle('hidden', S.min || S.all);
    if (S.all) { $c('#cmpLess').innerHTML = loaderHTML('Comparando…'); $c('#cmpMore').innerHTML = loaderHTML('Comparando…'); requestAnimationFrame(() => ['#cmpLess', '#cmpMore'].forEach(k => { const el = $c(k); if (el && el.getAnimations) el.getAnimations({ subtree: true }).forEach(a => { try { a.startTime = 0; } catch (e) {} }); })); }
    const t0 = performance.now();
    if (!S.items.length) { chart.querySelector('.gc-plot').innerHTML = ''; chart.querySelector('.gc-leg').innerHTML = ''; cols(); return; }
    if (S.all) {
      // Comparar tudo: uma chamada traz ações + índices (sem gráfico). Servidor aquecendo (202): mantém a animação e tenta de novo.
      let R = null;
      for (let k = 0; k < 60 && my === seq; k++) {
        try { const r = await fetch(`/api/returns?di=${S.di}&df=${S.df}`, { cache: 'no-store' }); if (r.status === 200) { R = await r.json(); break; } } catch (e) { }
        await new Promise(res => setTimeout(res, 3000));
      }
      if (my !== seq) return;
      S._miss = !R; R = R || {};
      for (const [id, v] of Object.entries(R)) vals[id] = v;
      cols(); chips(); window.__cmpMs = Math.round(performance.now() - t0); return;
    }
    const start = Date.parse(S.di), end = Date.parse(S.df) + 864e5 - 1;
    const kind = (Date.now() - start) > 5 * 365 * 864e5 ? 'm' : 'd';
    chart.querySelector('.gc-plot').innerHTML = loaderHTML('');
    const stocks = S.items.filter(x => !isIdx(x)), need = stocks.length ? stocks : ['IBOV'];
    const pays = {}, tget = async (u, ms) => { const ac = new AbortController(), h = setTimeout(() => ac.abort(), ms); try { const r = await fetch(u, { signal: ac.signal }); return r.ok ? await r.json() : null; } catch (e) { return null; } finally { clearTimeout(h); } };
    // "comparar com tudo": retornos de todas as ações numa chamada só, em paralelo com o gráfico; nada fica carregando para sempre
    const pR = S.all ? tget(`/api/returns?di=${S.di}&df=${S.df}`, 20000) : null;
    await Promise.all(need.map(async t => { const j = await tget(`/api/chart/${encodeURIComponent(t)}?kind=${kind}`, 15000); if (j) pays[t] = j; }));
    if (my !== seq) return;
    const anyP = Object.values(pays)[0] || {};
    const series = [];
    S.items.forEach((id, i) => {
      let pts = [];
      if (!isIdx(id)) { const p = pays[id]; if (p && p.stock && !p.stock.error) pts = gcPricePts(p.stock, start, end); }
      else {
        const k = IDX.find(x => x[0] === id)[2], d = anyP[k];
        if (d && !d.error) pts = k === 'ibov' ? gcPricePts(d, start, end) : (k === 'usd' || k === 'gold') ? gcPricePts({ t: d.d.map(x => Date.parse(x) / 1000), c: d.v }, start, end) : gcRatePts(d, start, end);
      }
      if (pts.length) { vals[id] = pts[pts.length - 1][1]; series.push({ id: i === 0 ? 'stock' : id, label: label(id), color: COLORS[i % COLORS.length], pts }); }
    });
    const plot = chart.querySelector('.gc-plot'), leg = chart.querySelector('.gc-leg');
    if (series.length) gcRender(plot, leg, series, start, end, kind);
    else { plot.innerHTML = '<div class="gc-nodata-msg">Sem informações no banco de dados</div>'; leg.innerHTML = ''; }
    if (S.all) {
      const R = (await pR) || {}; S._miss = !Object.keys(R).length || !Object.keys(pays).length;
      if (my !== seq) return;
      for (const r of rows()) { if (S.items.includes(r.ticker)) continue; const v = R[r.ticker]; if (v != null) vals[r.ticker] = v; }
      for (const [id, , k] of IDX) if (vals[id] == null) { const d = anyP[k]; if (d && !d.error) { const pts = k === 'ibov' ? gcPricePts(d, start, end) : (k === 'usd' || k === 'gold') ? gcPricePts({ t: d.d.map(x => Date.parse(x) / 1000), c: d.v }, start, end) : gcRatePts(d, start, end); if (pts.length) vals[id] = pts[pts.length - 1][1]; } }
    }
    if (!S.all) S._miss = false;
    cols(); chips(); window.__cmpMs = Math.round(performance.now() - t0);
  }
  function cols() {
    const ref = S.items[0], rv = vals[ref], ind = S.crit !== 'preco';
    const fmt = (v) => ind ? F2.format(v) : pc(v);
    const L = [], M = [];
    const cand = S.all ? [...new Set(S.items.slice(1).concat(IDX.map(x => x[0]), rows().map(r => r.ticker)))].filter(id => id !== ref) : S.items.slice(1);
    for (const id of cand) {
      if (vals[id] == null) continue;
      const it = { id, v: vals[id], d: rv == null ? 0 : vals[id] - rv };
      (rv != null && it.d < 0 ? L : M).push(it);
    }
    const fav = (id) => typeof FAVS !== 'undefined' && FAVS.has(id);
    const sorter = (a, b) => (fav(b.id) - fav(a.id)) || Math.abs(b.d) - Math.abs(a.d);
    const html = (arr, q, cls) => arr.filter(x => !q || norm(label(x.id)).includes(norm(q))).sort(sorter).map(x => `<div class="cmp-it"><b>${fav(x.id) ? '★ ' : ''}${esc(label(x.id))}</b><span class="${cls}">${fmt(x.v)}</span><small>${rv != null ? (x.d > 0 ? '+' : '') + F2.format(x.d) + (ind ? '' : ' p.p.') + ' vs ref.' : ''}</small></div>`).join('') || '<p class="text-xs text-slate-500 py-2">—</p>';
    $c('#cmpLess').innerHTML = (rv != null ? `<p class="cmp-ref">Principal ${esc(label(ref))}: ${fmt(rv)}</p>` : '') + html(L, S.qa, 'dn');
    if (S._miss) $c('#cmpLess').insertAdjacentHTML('afterbegin', '<p class="gt-help">Alguns dados não carregaram agora; mostrando o que veio.</p>');
    $c('#cmpMore').innerHTML = (rv != null ? `<p class="cmp-ref">Principal ${esc(label(ref))}: ${fmt(rv)}</p>` : '') + html(M, S.qb, 'up');
  }
  function all() { chips(); compute(); save(); }
  let built = false, waiting = false;
  function build() {
    if (built) return;
    if (!state.data) { root.innerHTML = loaderHTML('Carregando dados…'); if (!waiting) { waiting = true; setTimeout(() => { waiting = false; build(); }, 1200); } return; }
    shell(); built = true;
    for (const id of ['#cmpP', '#cmpQ']) { $c(id).addEventListener('input', drop); $c(id).addEventListener('focus', drop); }
    root.addEventListener('click', async (e) => {
      if (e.target.closest('#cmpMin')) { S.min = !S.min; $c('#cmpChart').classList.toggle('hidden', S.min || S.all || S.crit !== 'preco'); chips(); save(); return; }
      if (e.target.closest('#cmpAll')) { S.all = !S.all; all(); return; }
      const a = e.target.closest('[data-add]');
      if (a) { if (a.dataset.w === 'p') S.items = [a.dataset.add].concat(S.items.filter(x => x !== a.dataset.add)); else S.items.push(a.dataset.add);
        $c('#cmpP').value = $c('#cmpQ').value = ''; root.querySelectorAll('.cmp-srch .pv-combo').forEach(x => x.classList.add('hidden')); all(); return; }
      const rm = e.target.closest('[data-rm]'); if (rm) { S.items = S.items.filter(x => x !== rm.dataset.rm); all(); return; }
      if (e.target.closest('#cmpSwap')) {
                const v = await uiChoose('Trocar o principal por:', S.items.slice(1).filter(id => !(S.crit !== 'preco' && isIdx(id))).map(id => ({ label: esc(label(id)), value: id })));
        if (v) { S.items = [v].concat(S.items.filter(x => x !== v)); all(); }
      }
    });
    document.addEventListener('click', (e) => { root.querySelectorAll('.cmp-srch').forEach(b => { if (!b.contains(e.target)) b.querySelector('.pv-combo').classList.add('hidden'); }); });
    $c('#cmpCrit').addEventListener('change', () => { S.crit = $c('#cmpCrit').value; if (S.crit !== 'preco' && S.items[0] && isIdx(S.items[0])) { const f = S.items.find(x => !isIdx(x)); if (f) S.items = [f].concat(S.items.filter(x => x !== f)); } all(); });
    $c('#cmpDi').addEventListener('change', () => { S.di = $c('#cmpDi').value || yago; all(); });
    $c('#cmpDf').addEventListener('change', () => { S.df = $c('#cmpDf').value || today; all(); });
    root.addEventListener('input', (e) => { const k = e.target.dataset.q; if (k) { S[k] = e.target.value; cols(); } });
    all();
  }
  document.addEventListener('tabshow', (e) => { if (e.detail === 'comparar') { if (!built) build(); else if (S.items.length) compute(); } });
  if (!document.querySelector('[data-tabpane="comparar"]').classList.contains('hidden')) build();
})();
