// ---------- Gráfico por ação (SVG próprio, sem biblioteca externa) ----------
(function () {
  const LINES = [
    { id: 'stock', label: 'Ação', color: '#34d399' },
    { id: 'ibov', label: 'Ibovespa', color: '#60a5fa' },
    { id: 'usd', label: 'Dólar', color: '#facc15' },
    { id: 'cdi', label: 'CDI', color: '#f472b6' },
    { id: 'ipca', label: 'Inflação (IPCA)', color: '#fb923c' },
    { id: 'poup', label: 'Poupança', color: '#a78bfa' },
  ];
  const PERIODS = [['1d', '1 dia'], ['7d', '7 dias'], ['1m', '1 mês'], ['1y', '1 ano'], ['2y', '2 anos'], ['3y', '3 anos'], ['4y', '4 anos'], ['5y', '5 anos']];
  const DAY = 864e5;
  const P2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'always' });
  const cache = {};
  const getJSON = (u) => cache[u] || (cache[u] = fetch(u).then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.error || r.status); return d; }).catch(e => { delete cache[u]; throw e; }));
  const hist = (t, k) => getJSON(`/api/history/${encodeURIComponent(t)}?kind=${k}`);
  const idx = (n) => getJSON(`/api/indices/${n}`);
  const iso = (ms) => new Date(ms).toISOString().slice(0, 10);
  const brDate = (s) => s.split('-').reverse().join('/');

  function mount(box) {
    if (box.dataset.m) return; box.dataset.m = '1';
    const t = box.dataset.gt;
    const S = Object.assign({ per: '1d', di: '', df: '', on: { stock: true } }, loadPref(t));
    const persist = () => savePref(t, S);
    box.innerHTML = `<div class="gc">
      <div class="gc-bar">${PERIODS.map(([k, l]) => `<button type="button" data-per="${k}">${l}</button>`).join('')}
        <button type="button" class="gc-ref ricon" title="Atualizar" aria-label="Atualizar gráfico"><svg class="ri" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button></div>
      <div class="gc-dates"><label>Data inicial<input type="date" data-d="di"></label><label>Data final<input type="date" data-d="df"></label></div>
      <div class="gc-chk">${LINES.map(L => `<label style="--lc:${L.color}"><input type="checkbox" data-l="${L.id}">${L.label}</label>`).join('')}</div>
      <div class="gc-wrap"><div class="gc-plot"></div><div class="gc-leg"></div></div>
      <p class="gc-note"></p></div>`;
    const q = (s) => box.querySelector(s);
    box.addEventListener('click', (e) => {
      const b = e.target.closest('[data-per]'); if (b) { S.per = b.dataset.per; S.di = S.df = ''; box.querySelectorAll('[data-d]').forEach(i => i.value = ''); persist(); draw(); }
      if (e.target.closest('.gc-ref')) draw(true);
      e.stopPropagation();
    });
    box.addEventListener('change', (e) => {
      const c = e.target.dataset.l; if (c) { S.on[c] = e.target.checked; persist(); paint(); }
      const d = e.target.dataset.d; if (d) { S[d] = e.target.value; if (S.di || S.df) S.per = 'custom'; persist(); draw(); }
    });
    box.querySelectorAll('[data-l]').forEach(i => i.checked = !!S.on[i.dataset.l]);
    box.querySelectorAll('[data-d]').forEach(i => i.value = S[i.dataset.d] || '');
    let seq = 0, cur = null;
    function range() {
      const now = Date.now(); let start, end, kind;
      if (S.per === 'custom') {
        start = S.di ? Date.parse(S.di) : now - 365 * DAY; end = S.df ? Date.parse(S.df) + DAY - 1 : now;
        kind = now - start > 5 * 365.25 * DAY ? 'm' : 'd';
      } else if (S.per === '1d') { kind = 'i'; start = 0; end = now + DAY; }
      else { kind = 'd'; const n = parseInt(S.per); start = now - (S.per.endsWith('d') ? n * DAY : S.per.endsWith('m') ? 30.5 * DAY : n * 365.25 * DAY); end = now; }
      return { start, end, kind };
    }
    function paint() {
      if (!cur) return;
      const { kind } = cur, pay = cur.pay, plot = q('.gc-plot'), note = q('.gc-note');
      let { start, end } = range();
      const sd = pay.stock;
      if (kind === 'i') { start = sd.t[0] * 1000; end = sd.t[sd.t.length - 1] * 1000 + 1; }
      const series = [], skipped = [];
      for (const L of LINES) {
        if (!S.on[L.id]) continue;
        const d = L.id === 'stock' ? sd : pay[L.id];
        if (!d || d.error) { skipped.push(L.label + (kind === 'i' ? '' : ' (indisponível)')); continue; }
        if (L.id === 'stock' || L.id === 'ibov') series.push({ ...L, label: L.id === 'stock' ? t : L.label, pts: pricePts(d, start, end) });
        else if (L.id === 'usd') series.push({ ...L, pts: pricePts({ t: d.d.map(x => Date.parse(x) / 1000), c: d.v }, start, end) });
        else series.push({ ...L, pts: ratePts(d, start, end) });
      }
      if (!series.length) { plot.innerHTML = '<div class="gc-load">Marque ao menos uma linha.</div>'; q('.gc-leg').innerHTML = ''; }
      else render(plot, q('.gc-leg'), series.filter(s => s.pts.length), start, end, kind);
      const notes = [];
      if (skipped.length) notes.push((kind === 'i' ? 'Sem dados intradiários: ' : 'Ocultos: ') + skipped.join(', ') + '.');
      if (kind === 'i') notes.push('Hoje (5 em 5 min). Toque em ⟳ para atualizar.');
      notes.push('Fonte: ' + sd.source + (kind !== 'i' ? ' · índices: Banco Central (SGS)' : '') + '.');
      note.textContent = notes.join(' ');
    }
    async function draw(force) {
      const my = ++seq, { kind } = range(), key = t + '|' + kind, ref = q('.gc-ref');
      box.querySelectorAll('[data-per]').forEach(b => b.classList.toggle('on', b.dataset.per === S.per));
      const cached = force ? null : await cget(key);
      if (my !== seq) return;
      if (cached) { cur = { kind, pay: cached.pay }; paint(); }
      else if (!cur || cur.kind !== kind) q('.gc-plot').innerHTML = '<div class="gc-load">Carregando…</div>';
      const fresh = cached && Date.now() - cached.at < (kind === 'i' ? 60e3 : 15 * 60e3);
      if (fresh && !force) return;
      ref.classList.add('spin');
      try {
        const r = await fetch(`/api/chart/${encodeURIComponent(t)}?kind=${kind}`); const pay = await r.json();
        if (!r.ok || !pay.stock) throw new Error(pay.error || r.status);
        cput(key, pay);
        if (my === seq) { cur = { kind, pay }; paint(); }
      } catch (e) {
        if (my === seq && !cached) {
          q('.gc-plot').innerHTML = '<div class="gc-empty">Sem informações no banco de dados</div>'; q('.gc-leg').innerHTML = ''; q('.gc-note').textContent = '';
          box.querySelectorAll('.gc-chk input, .gc-dates input').forEach(i => { i.disabled = true; }); box.classList.add('gc-nodata');
        }
      }
      finally { if (my === seq) ref.classList.remove('spin'); }
    }
    draw();
    setTimeout(async () => { const k = t + '|d'; if (!(await cget(k))) { try { const r = await fetch(`/api/chart/${encodeURIComponent(t)}?kind=d`); if (r.ok) cput(k, await r.json()); } catch (e) { } } }, 1200);
  }

  const PKEY = 'screenerB3.chart.v1';
  const prefsAll = () => { try { return JSON.parse(localStorage.getItem(PKEY) || '{}') || {}; } catch (e) { return {}; } };
  function loadPref(t) { const p = prefsAll()[t]; return p ? { per: p.per, di: p.di || '', df: p.df || '', on: p.on || { stock: true } } : {}; }
  function savePref(t, S) { const a = prefsAll(); a[t] = { per: S.per, di: S.di, df: S.df, on: S.on }; try { localStorage.setItem(PKEY, JSON.stringify(a)); } catch (e) { } }
  // Cache no navegador (IndexedDB): mostra na hora e atualiza depois
  const mem = {};
  let dbp = null;
  const db = () => dbp || (dbp = new Promise((res) => { try { const r = indexedDB.open('screenerB3-hist', 1); r.onupgradeneeded = () => r.result.createObjectStore('c'); r.onsuccess = () => res(r.result); r.onerror = () => res(null); } catch (e) { res(null); } }));
  async function cget(k) {
    if (mem[k]) return mem[k];
    const d = await db(); if (!d) return null;
    return new Promise(res => { try { const q = d.transaction('c').objectStore('c').get(k); q.onsuccess = () => { if (q.result) mem[k] = q.result; res(q.result || null); }; q.onerror = () => res(null); } catch (e) { res(null); } });
  }
  async function cput(k, pay) {
    const v = { at: Date.now(), pay }; mem[k] = v;
    const d = await db(); if (!d) return; try { d.transaction('c', 'readwrite').objectStore('c').put(v, k); } catch (e) { }
  }
  function pricePts(d, start, end) {
    const out = []; let base = null;
    for (let i = 0; i < d.t.length; i++) {
      const ms = d.t[i] * 1000; if (ms < start - 0 || ms > end) continue;
      if (base == null) base = d.c[i];
      out.push([ms, (d.c[i] / base - 1) * 100]);
    }
    return out;
  }
  function ratePts(d, start, end) {
    const out = []; let cum = 1, first = true;
    const s0 = iso(start), e0 = iso(end), sMonth = s0.slice(0, 7) + '-01';
    for (let i = 0; i < d.d.length; i++) {
      const x = d.d[i]; if (x < sMonth || x > e0) continue;
      const monthly = d.d.length < 1000; // IPCA/poupança são mensais
      if (!monthly && x < s0) continue;
      if (first) { out.push([Math.max(start, Date.parse(x)), 0]); first = false; }
      cum *= 1 + d.v[i] / 100;
      const ms = monthly ? Math.min(end, Date.parse(x) + 30 * DAY) : Date.parse(x);
      out.push([ms, (cum - 1) * 100]);
    }
    return out;
  }

  function render(plot, leg, series, start, end, kind) {
    const W = 600, H = 240, pad = 4;
    if (!series.length || !series[0].pts.length) { plot.innerHTML = '<div class="gc-load">Sem dados no período.</div>'; leg.innerHTML = ''; return; }
    const xs = series.flatMap(s => s.pts.map(p => p[0])), ys = series.flatMap(s => s.pts.map(p => p[1])).concat([0]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs) || x0 + 1;
    let y0 = Math.min(...ys), y1 = Math.max(...ys); if (y1 - y0 < 0.5) { y0 -= .25; y1 += .25; }
    const yr = (y1 - y0) * 0.06; y0 -= yr; y1 += yr;
    const X = (v) => pad + (v - x0) / ((x1 - x0) || 1) * (W - 2 * pad), Y = (v) => H - pad - (v - y0) / (y1 - y0) * (H - 2 * pad);
    const ticks = []; const step = niceStep((y1 - y0) / 4);
    for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step) ticks.push(Math.abs(v) < step / 1e6 ? 0 : v);
    const fmtX = (ms) => kind === 'i' ? new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : new Date(ms).toLocaleDateString('pt-BR', x1 - x0 > 400 * DAY ? { month: '2-digit', year: '2-digit' } : { day: '2-digit', month: '2-digit' });
    plot.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="gc-svg" role="img" aria-label="Variação percentual no período">
      ${ticks.map(v => `<line x1="0" x2="${W}" y1="${Y(v)}" y2="${Y(v)}" class="${Math.abs(v) < 1e-9 ? 'gc-zero' : 'gc-grid'}"/>`).join('')}
      ${series.slice().reverse().map(s => `<polyline fill="none" stroke="${s.color}" stroke-width="${s.id === 'stock' ? 2.4 : 1.6}" vector-effect="non-scaling-stroke" stroke-linejoin="round" points="${s.pts.map(p => X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join(' ')}"/>`).join('')}
    </svg>
    <div class="gc-yl">${ticks.map(v => `<span style="top:${(Y(v) / H * 100).toFixed(2)}%">${P2.format(v).replace(',00', '')}%</span>`).join('')}</div>
    <div class="gc-xl"><span>${fmtX(x0)}</span><span>${fmtX((x0 + x1) / 2)}</span><span>${fmtX(x1)}</span></div>`;
    leg.innerHTML = series.map(s => { const v = s.pts[s.pts.length - 1][1]; return `<div style="--lc:${s.color}"><b>${P2.format(v)}%</b><span>${s.label}</span></div>`; }).join('');
  }
  function niceStep(r) { const p = Math.pow(10, Math.floor(Math.log10(r || 1))), n = r / p; return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p; }

  const io = new IntersectionObserver((es) => es.forEach(e => { if (e.isIntersecting) { io.unobserve(e.target); mount(e.target); } }), { rootMargin: '200px' });
  const scan = (root) => (root.querySelectorAll ? root.querySelectorAll('.gchart:not([data-m])') : []).forEach(el => io.observe(el));
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => n.nodeType === 1 && (n.matches?.('.gchart') ? io.observe(n) : scan(n))))).observe(document.body, { childList: true, subtree: true });
  scan(document);
  window.mountChart = mount;
})();
