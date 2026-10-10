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
    const S = { per: '1d', di: '', df: '', on: {} };
    box.innerHTML = `<div class="gc">
      <div class="gc-bar">${PERIODS.map(([k, l]) => `<button type="button" data-per="${k}">${l}</button>`).join('')}
        <button type="button" class="gc-ref" title="Atualizar" aria-label="Atualizar gráfico">⟳</button></div>
      <div class="gc-dates"><label>Data inicial<input type="date" data-d="di"></label><label>Data final<input type="date" data-d="df"></label></div>
      <div class="gc-chk">${LINES.slice(1).map(L => `<label style="--lc:${L.color}"><input type="checkbox" data-l="${L.id}">${L.label}</label>`).join('')}</div>
      <div class="gc-wrap"><div class="gc-plot"></div><div class="gc-leg"></div></div>
      <p class="gc-note"></p></div>`;
    const q = (s) => box.querySelector(s);
    box.addEventListener('click', (e) => {
      const b = e.target.closest('[data-per]'); if (b) { S.per = b.dataset.per; S.di = S.df = ''; box.querySelectorAll('[data-d]').forEach(i => i.value = ''); draw(); }
      if (e.target.closest('.gc-ref')) { Object.keys(cache).filter(k => k.includes('kind=i') || k.includes('/' + t + '?')).forEach(k => delete cache[k]); draw(); }
      e.stopPropagation();
    });
    box.addEventListener('change', (e) => {
      const c = e.target.dataset.l; if (c) { S.on[c] = e.target.checked; draw(); }
      const d = e.target.dataset.d; if (d) { S[d] = e.target.value; if (S.di || S.df) S.per = 'custom'; draw(); }
    });
    let seq = 0;
    async function draw() {
      const my = ++seq;
      box.querySelectorAll('[data-per]').forEach(b => b.classList.toggle('on', b.dataset.per === S.per));
      const plot = q('.gc-plot'), note = q('.gc-note');
      plot.innerHTML = '<div class="gc-load">Carregando…</div>'; note.textContent = '';
      const now = Date.now();
      let start, end, kind;
      if (S.per === 'custom') {
        start = S.di ? Date.parse(S.di) : now - 365 * DAY; end = S.df ? Date.parse(S.df) + DAY - 1 : now;
        kind = now - start > 5 * 365.25 * DAY ? 'm' : 'd';
      } else if (S.per === '1d') kind = 'i';
      else { kind = 'd'; const n = parseInt(S.per); start = now - (S.per.endsWith('d') ? n * DAY : S.per.endsWith('m') ? 30.5 * DAY : n * 365.25 * DAY); end = now; }
      try {
        const sd = await hist(t, kind);
        if (kind === 'i') { start = sd.t[0] * 1000; end = sd.t[sd.t.length - 1] * 1000 + 1; }
        const series = [{ ...LINES[0], label: t, pts: pricePts(sd, start, end) }];
        const want = LINES.slice(1).filter(L => S.on[L.id]);
        const skipped = [];
        await Promise.all(want.map(async L => {
          try {
            if (L.id === 'ibov') series.push({ ...L, pts: pricePts(await hist('IBOV', kind), start, end) });
            else if (kind === 'i') skipped.push(L.label);
            else if (L.id === 'usd') { const d = await idx('usd'); series.push({ ...L, pts: pricePts({ t: d.d.map(x => Date.parse(x) / 1000), c: d.v }, start, end) }); }
            else { const d = await idx(L.id); series.push({ ...L, pts: ratePts(d, start, end) }); }
          } catch (e) { skipped.push(L.label + ' (indisponível)'); }
        }));
        if (my !== seq) return;
        series.sort((a, b) => LINES.findIndex(L => L.id === a.id) - LINES.findIndex(L => L.id === b.id));
        render(plot, q('.gc-leg'), series.filter(s => s.pts.length), start, end, kind);
        const notes = [];
        if (skipped.length) notes.push((kind === 'i' ? 'Sem dados intradiários: ' : 'Ocultos: ') + skipped.join(', ') + '.');
        if (kind === 'i') notes.push('Hoje (5 em 5 min). Toque em ⟳ para atualizar.');
        notes.push('Fonte: ' + sd.source + (want.some(L => !['ibov'].includes(L.id)) && kind !== 'i' ? ' · Banco Central (SGS)' : '') + '. Primeiro dado: ' + brDate(iso(sd.t[0] * 1000)) + '.');
        note.textContent = notes.join(' ');
      } catch (e) { if (my === seq) plot.innerHTML = `<div class="gc-load">Histórico indisponível: ${String(e.message).slice(0, 120)}</div>`; }
    }
    draw();
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
