// ---------- Índice de Medo e Ganância da B3 (snapshot fg; cálculo em scripts/build_fg.py) ----------
// Velocímetro no topo da aba Ações (só Brasil). fgLoad/fgBand também servem ao Comparar.
(function () {
  const box = document.getElementById('fgCard');
  const cache = {};
  window.fgLoad = (full) => cache[full ? 1 : 0] || (cache[full ? 1 : 0] = fetch('api/fg' + (full ? '?full=1' : '')).then(r => r.json()).catch(() => ({})));
  // faixa do valor: {i: 0..4, n: nome} (faixas lidas de fg.json)
  window.fgBand = (v, fx) => { const i = fx.findIndex(f => v <= f[0]); return { i: i < 0 ? fx.length - 1 : i, n: (fx[i < 0 ? fx.length - 1 : i] || [])[1] || '' }; };
  const CLS = ['fg-0', 'fg-1', 'fg-2', 'fg-3', 'fg-4'];
  window.fgCls = (i) => CLS[i] || '';
  const pt = (v, r) => { const a = Math.PI * (1 - v / 100); return [60 + r * Math.cos(a), 62 - r * Math.sin(a)]; };
  const arc = (a, b, r) => { const [x0, y0] = pt(a, r), [x1, y1] = pt(b, r); return `M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`; };
  window.fgGauge = (v, fx) => {
    let a = 0;
    const segs = fx.map((f, i) => { const s = `<path class="${CLS[i]}" d="${arc(a + (a ? 1 : 0), f[0] - (f[0] < 100 ? 1 : 0), 48)}"/>`; a = f[0]; return s; }).join('');
    const [nx, ny] = pt(v, 36);
    return `<svg class="fg-g" viewBox="0 0 120 70" aria-hidden="true">${segs}<line x1="60" y1="62" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" class="fg-n"/><circle cx="60" cy="62" r="4" class="fg-c"/></svg>`;
  };
  async function draw() {
    if (!box) return;
    if (typeof state === 'undefined' || state.country !== 'br') { box.classList.add('hidden'); return; }
    const d = await fgLoad(false);
    if (!d || !d.v || !d.v.length) { box.classList.add('hidden'); return; }
    const v = d.v, fx = d.faixas, now = v[v.length - 1], b = fgBand(now, fx);
    document.querySelectorAll('[data-fg-faixas]').forEach(e => { e.textContent = fx.map((f, i) => `${i ? fx[i - 1][0] : 0}–${f[0]} ${f[1]}`).join(' · '); });  // limites: fg.json
    const ago = (n) => v.length > n ? v[v.length - 1 - n] : null;
    const cmp = [['Ontem', ago(1)], ['1 semana', ago(5)], ['1 mês', ago(21)]].filter(x => x[1] != null)
      .map(([l, x]) => `${l} <b class="${CLS[fgBand(x, fx).i]}">${x}</b>`).join(' · ');
    box.innerHTML = `${fgGauge(now, fx)}<div class="fg-t"><div class="fg-h">Medo e Ganância (B3)${glossBtn('Medo e Ganância')}</div>
      <div class="fg-v ${CLS[b.i]}"><b>${now}</b> ${esc(b.n)}</div><div class="fg-p">${cmp}</div><div class="fg-d">${dataBR(d.d[d.d.length - 1])}</div></div>`;
    box.classList.remove('hidden');
  }
  document.addEventListener('dataload', draw);
})();
