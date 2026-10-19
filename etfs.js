// ---------- Aba Mercado → ETFs (só no Brasil): snapshot etfs (scripts/fetch_b3_etfs.py: lista da B3 + preços do COTAHIST) por /api/etfs ----------
// Seletor Ações | ETFs no topo da aba (#mkSeg); a escolha fica no aparelho. ETF não tem balanço: o card mostra só preço, volume, rendimento,
// proventos, tipo e índice. Ilíquido (il) = mesma regra das ações (scripts/universe.py), escondido com "Só líquidos".
(function () {
  const KEY = 'screenerB3.mercado.v1', pane = document.querySelector('[data-tabpane="acoes"]'), seg = document.getElementById('mkSeg'), root = document.getElementById('etfRoot');
  if (!pane || !seg || !root) return;
  const ORD = [['vm', 'Volume médio'], ['r1', 'Rendimento 1 ano'], ['r3', 'Rendimento 3 anos'], ['r5', 'Rendimento 5 anos'], ['dy', 'Proventos 12 meses'], ['v', 'Variação do dia'], ['t', 'Código']];
  const ls = (k, d) => { try { return JSON.parse(localStorage.getItem(KEY))[k] ?? d; } catch (e) { return d; } };
  let modo = ls('modo', 'acoes'), fil = ls('fil', 'todos'), ord = ls('ord', 'vm'), dir = ls('dir', -1), liq = ls('liq', true), q = '', D = null, loading = false;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ modo, fil, ord, dir, liq })); } catch (e) { } };
  const br = () => typeof state === 'undefined' || !state.country || state.country === 'br';
  const P = (x) => x == null ? '—' : pc(x), cor = (x) => x == null ? 'text-slate-400' : x >= 0 ? 'text-emerald-400' : 'text-rose-400';
  function apply() {
    const etf = br() && modo === 'etf';
    seg.classList.toggle('hidden', !br());
    for (const c of pane.children) if (c !== seg && c !== root) c.classList.toggle('etf-off', etf);
    root.classList.toggle('hidden', !etf);
    seg.querySelectorAll('[data-mk]').forEach(b => b.classList.toggle('on', b.dataset.mk === (etf ? 'etf' : 'acoes')));
    if (etf && !D) load();  // já desenhado: a recarga de dados das ações (dataload) não refaz a lista nem fecha os gráficos abertos
  }
  async function load() {
    if (loading) return; loading = true; root.innerHTML = loaderHTML('Carregando ETFs…');
    try { D = await getRetry('/api/etfs'); draw(); }
    catch (e) { root.innerHTML = `<p class="pvd-note">Não foi possível carregar os ETFs: ${esc(e.message)}</p>`; }
    loading = false;
  }
  const card = (t, x) => `<div class="etf-c" data-et="${esc(t)}"><div class="etf-h"><b>${esc(t)}</b><span class="gchip">${esc((D.tipos || {})[x.k] || '')}</span></div>
    <p class="etf-n">${esc(x.n || '')}</p><p class="etf-i">Índice: ${esc(x.i || '—')}</p>
    <div class="etf-p"><span class="text-lg font-bold">${x.p == null ? '—' : brl.format(x.p)}</span><span class="${cor(x.v)}">${P(x.v)}</span></div>
    <div class="etf-g"><span>Volume médio<b>${x.vm == null ? '—' : fmtMoneyBig(x.vm)}</b></span><span>Proventos 12 m<b>${x.dy == null ? '—' : F2.format(x.dy) + '%'}</b></span>
      <span>1 ano<b class="${cor(x.r1)}">${P(x.r1)}</b></span><span>3 anos<b class="${cor(x.r3)}">${P(x.r3)}</b></span><span>5 anos<b class="${cor(x.r5)}">${P(x.r5)}</b></span></div>
    <p class="etf-u">${x.u ? 'Fechamento de ' + dataBR(x.u) + ' · toque para ver o gráfico' : 'Sem negócios no COTAHIST'}</p></div>`;
  function draw() {
    const E = (D && D.e) || {}, nq = norm(q);
    let L = Object.entries(E).filter(([t, x]) => (fil === 'todos' || x.k === fil) && (!liq || !x.il) && (!nq || norm(t + ' ' + (x.n || '') + ' ' + (x.f || '')).includes(nq)));
    L.sort((a, b) => ord === 't' ? dir * -a[0].localeCompare(b[0]) : ((b[1][ord] ?? -1e18) - (a[1][ord] ?? -1e18)) * -dir);
    const tipos = [['todos', 'Todos']].concat(Object.entries(D.tipos || {}));
    root.innerHTML = `<section class="atop rounded-2xl border border-slate-800 bg-slate-900/60 p-3 space-y-2.5">
      <input id="etfQ" type="search" placeholder="Buscar ETF ou índice…" value="${esc(q)}" class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm">
      <div class="pv-per">${tipos.map(([k, l]) => `<button type="button" data-ef="${k}" class="${k === fil ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>
      <div class="flex items-center gap-2 flex-wrap"><label class="flex items-center gap-2 text-sm"><input id="etfLiq" type="checkbox" ${liq ? 'checked' : ''} class="accent-emerald-500 w-4 h-4"> Só líquidos</label>
        <label for="etfOrd" class="text-xs text-slate-400 ml-auto">Ordenar</label><select id="etfOrd" class="sel max-w-[200px]">${ORD.map(([k, l]) => `<option value="${k}"${k === ord ? ' selected' : ''}>${l}</option>`).join('')}</select>
        <button id="etfDir" type="button" class="px-2.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm" aria-label="Inverter ordem">${sortIc(dir)}</button></div></section>
      <p class="text-xs text-slate-400"><span class="text-base font-bold text-slate-100">${L.length}</span> ETFs ${glossBtn('ETF')}</p>
      ${L.length ? `<div class="etf-grid">${L.map(([t, x]) => card(t, x)).join('')}</div>` : '<p class="pvd-note">Nenhum ETF com esses filtros.</p>'}
      <p class="pvd-note">Lista oficial da B3 (fundos de índice; cripto e fundos imobiliários ficam de fora; tipo pelo índice no nome do fundo); preço e volume do COTAHIST da B3. ETF não tem balanço: sem P/L, ROE, dívida ou Barato/Caro. Para estudo, não é recomendação.</p>`;
  }
  seg.addEventListener('click', (e) => { const b = e.target.closest('[data-mk]'); if (!b) return; modo = b.dataset.mk; save(); apply(); });
  root.addEventListener('click', (e) => {
    const b = e.target.closest('[data-ef]'); if (b) { fil = b.dataset.ef; save(); draw(); return; }
    if (e.target.closest('#etfDir')) { dir = -dir; save(); draw(); return; }
    const c = e.target.closest('[data-et]');  // toque no card: gráfico do histórico (grafico.js, o mesmo das ações); 2º toque fecha
    if (c && !e.target.closest('.gchart') && D.e[c.dataset.et] && D.e[c.dataset.et].u) {
      const g = c.querySelector('.gchart'); if (g) g.remove(); else c.insertAdjacentHTML('beforeend', `<div class="gchart" data-gt="${esc(c.dataset.et)}"></div>`);
    }
  });
  root.addEventListener('change', (e) => {
    if (e.target.id === 'etfOrd') { ord = e.target.value; save(); draw(); }
    if (e.target.id === 'etfLiq') { liq = e.target.checked; save(); draw(); }
  });
  root.addEventListener('input', (e) => { if (e.target.id !== 'etfQ') return; q = e.target.value; const pos = e.target.selectionStart; draw(); const n = document.getElementById('etfQ'); n.focus(); n.setSelectionRange(pos, pos); });
  document.addEventListener('dataload', apply);
  apply();
})();
