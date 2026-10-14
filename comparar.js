// ---------- Aba Comparar ----------
(function () {
  const $c = (s) => document.querySelector(s);
  const KEY = 'screenerB3.comparar.v1';
  const IDX = Object.entries(window.INDICES || {}).map(([k, n]) => ['@' + k, n, k]);  // nomes: history.INDICES (servidor)
  const COLORS = ['#34d399', '#60a5fa', '#facc15', '#f472b6', '#fb923c', '#a78bfa', '#d4a373', '#22d3ee', '#f87171', '#a3e635', '#e879f9', '#94a3b8'];
  const today = new Date().toISOString().slice(0, 10), yago = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
  let S = (() => { try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; } })();
  S.items = S.items || []; S.min = !!S.min; S.all = !!S.all; S.ct = S.ct || 'br'; S.vm = S.vm || 'pct'; S.crit = S.crit || 'preco'; S.di = S.di || yago; S.df = S.df || today; S.qa = ''; S.qb = '';
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ items: S.items, crit: S.crit, di: S.di, df: S.df, min: S.min, all: S.all, ct: S.ct, vm: S.vm })); } catch (e) { } };
  // País da comparação (bandeiras): 'br' (padrão), outro país ou 'all' (🌐). Ação de fora = "us:AAPL"; índice do país = "@ix:us".
  // Linhas de cada país = mesmo /api/data das abas (carregadas uma vez); Brasil reaproveita state.data quando a aba Ações está no Brasil.
  const RC = {};
  const ctry = (c) => (state.countries || []).find(x => x.id === c) || { id: c, name: c, index: 'Índice' };
  const cOf = (id) => id.startsWith('@ix:') ? id.slice(4) : id.includes(':') ? id.split(':')[0] : 'br';
  const tOf = (id) => id.includes(':') ? id.split(':')[1] : id;
  const idOf = (c, t) => c === 'br' ? t : c + ':' + t;
  const ctList = () => S.ct === 'all' ? (state.countries || []).map(c => c.id) : [S.ct];
  async function loadRows(c) {
    if (RC[c]) return RC[c];
    if (c === 'br' && state.country === 'br' && state.data) return state.data.rows;
    try { const d = await (await fetch(`/api/data?country=${c}`)).json(); RC[c] = (d.rows || []).filter(r => !r.il).map(r => ({ ...r, cid: idOf(c, r.ticker) })); } catch (e) { RC[c] = []; }
    return RC[c];
  }
  const cached = (c) => RC[c] || (c === 'br' && state.country === 'br' && state.data ? state.data.rows : []);
  const rows = () => ctList().flatMap(c => cached(c).map(r => (r.cid ? r : { ...r, cid: idOf(c, r.ticker) })));
  const idxList = () => S.ct === 'br' ? IDX : S.ct === 'all' ? IDX.concat((state.countries || []).filter(c => c.id !== 'br').map(c => ['@ix:' + c.id, c.index + ' (' + c.name + ')', 'ibov']))
    : [['@ix:' + S.ct, ctry(S.ct).index, 'ibov']].concat(IDX.filter(x => x[0] === '@usd' || x[0] === '@gold'));
  const isIdx = (id) => id[0] === '@';
  const label = (id) => isIdx(id) ? ((idxList().concat(IDX)).find(x => x[0] === id) || [id, id])[1] : cOf(id) === 'br' || S.ct !== 'all' ? tOf(id) : `${tOf(id)} (${ctry(cOf(id)).name})`;  // país no nome só no 🌐
  const root = $c('#compRoot');
  let vals = {}, seq = 0;

  function shell() {
    const fields = (state.data?.fields || []).filter(f => f.key !== 'preco');
    root.innerHTML = `<section class="cmp-top">
      <div class="cmp-head"><label class="cmp-lbl">Principal</label><div id="cmpFlags" class="cmp-flags">${(state.countries || []).map(c => `<button type="button" data-ct="${c.id}" title="Comparar ações de ${esc(c.name)}" aria-label="${esc(c.name)}"><img class="flag" src="${c.flag}" alt=""></button>`).join('')}<button type="button" data-ct="all" title="Comparar todos os países" aria-label="Todos os países">🌐</button></div></div>
      <div id="cmpPrin" class="cmp-prin"></div>
      <div class="cmp-srch" data-w="p"><input id="cmpP" type="search" placeholder="Buscar ação ou índice principal…" autocomplete="off"><div class="pv-combo hidden"></div></div>
      <label class="cmp-lbl" id="cmpQl">Comparar com</label>
      <div class="cmp-srch" data-w="q"><input id="cmpQ" type="search" placeholder="Adicionar ação ou índice…" autocomplete="off"><div class="pv-combo hidden"></div></div>
      <div class="cmp-row frm"><label><span>Critério</span><select id="cmpCrit" class="sel"><option value="preco">Preço da ação</option><option value="fg">Medo e Ganância</option>${fields.map(f => `<option value="${f.key}">${esc(f.label)}</option>`).join('')}</select></label>
        <label><span>Início</span><input id="cmpDi" type="date" class="sel"></label><label><span>Fim</span><input id="cmpDf" type="date" class="sel"></label></div>
      <div id="cmpChips" class="cmp-chips"></div><button type="button" id="cmpGo" class="gbtn pri w-full">Pesquisar</button><button type="button" id="cmpAll" class="cmp-allb"></button><button type="button" id="cmpClr" class="gbtn w-full cmp-clr">Limpar tudo</button></section>
      <div class="cmp-bar"><div class="cmp-vm" role="group" aria-label="Mostrar no gráfico"><button type="button" data-vm="pct">%</button><button type="button" data-vm="val">Valor</button></div><button type="button" id="cmpMin" class="cmp-minb"></button></div>
      <div id="cmpChart" class="gchart cmp-chart" data-m="1"><div class="gc-body"><div class="gc-plot"></div><div class="gc-leg"></div></div></div>
      <section class="cmp-cols"><div class="cmp-col"><h3 class="dn">Renderam menos</h3><input class="cmp-f" data-q="qa" type="search" placeholder="Filtrar…" autocomplete="off"><div id="cmpLess"></div></div>
        <div class="cmp-col"><h3 class="up">Renderam mais</h3><input class="cmp-f" data-q="qb" type="search" placeholder="Filtrar…" autocomplete="off"><div id="cmpMore"></div></div></section>
      <section id="cmpFg" class="fgx-w hidden"></section>`;
    $c('#cmpCrit').value = S.crit; $c('#cmpDi').value = S.di; $c('#cmpDf').value = S.df;
  }
  function chips() {
    const fgm = S.crit === 'fg', ind = S.crit !== 'preco' && !fgm, ref = S.items[0];
    // Medo e Ganância: só a ação principal (B3) e o período
    for (const s of ['#cmpQl', '.cmp-srch[data-w="q"]', '#cmpChips', '.cmp-bar', '.cmp-cols', '#cmpChart']) root.querySelectorAll(s).forEach(e => e.classList.toggle('fgx-off', fgm));
    $c('#cmpFg').classList.toggle('hidden', !fgm);
    root.querySelectorAll('[data-ct]').forEach(b => b.classList.toggle('on', b.dataset.ct === S.ct));
    root.querySelectorAll('[data-vm]').forEach(b => b.classList.toggle('on', b.dataset.vm === S.vm));
    $c('#cmpAll').classList.toggle('hidden', S.ct !== 'br' || fgm);  // "Comparar tudo" usa o histórico da B3: só no Brasil
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
    const ind = S.crit !== 'preco', fgm = S.crit === 'fg';
    const idx = idxList().filter(x => norm(x[1]).includes(q) && !S.items.includes(x[0])).map(x => ({ id: x[0], t: x[1], s: 'índice', off: ind }));
    const st = rows().filter(r => !S.items.includes(r.cid) && (!fgm || cOf(r.cid) === 'br') && (r._s ? r._s.includes(q) : norm(r.ticker + ' ' + r.nome).includes(q))).map(r => [r, searchRank(r, q)]).sort((a, b) => a[1] - b[1]).map(x => x[0]).slice(0, 30).map(r => ({ id: r.cid, t: label(r.cid), s: r.nome || '' }));
    const L = idx.concat(st);
    d.innerHTML = L.length ? L.map(o => `<button type="button" data-add="${esc(o.id)}" data-w="${box.dataset.w}"${o.off ? ' disabled' : ''}><b>${esc(o.t)}</b><span>${esc(o.s)}${o.off ? (fgm ? ' · escolha uma ação da B3' : ' · indisponível para indicadores') : ''}</span></button>`).join('') : '<div class="px-3 py-2 text-xs text-slate-500">Nada encontrado.</div>';
    d.classList.remove('hidden');
  }
  async function compute() {
    const my = ++seq, ind = S.crit !== 'preco', chart = $c('#cmpChart');
    vals = {};
    if (S.crit === 'fg') { fgRun(my); return; }
    if (ind) {
      chart.classList.add('hidden');
      const byT = new Map(rows().map(r => [r.cid, r]));
      for (const id of S.items) if (!isIdx(id)) { const r = byT.get(id); if (r && r.v[S.crit] != null) vals[id] = r.v[S.crit]; }
      if (S.all) for (const r of rows()) if (r.v[S.crit] != null) vals[r.cid] = r.v[S.crit];
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
    // uma carga por ação; índices vêm da carga de uma ação do mesmo país (ou só do índice: "IBOV" no Brasil, "@IX" fora)
    const stocks = S.items.filter(x => !isIdx(x)), idxC = (id) => id.startsWith('@ix:') ? id.slice(4) : (id === '@usd' || id === '@gold') && S.ct !== 'br' && S.ct !== 'all' ? S.ct : 'br';
    const need = [...stocks]; for (const id of S.items.filter(isIdx)) { const c = idxC(id); if (!need.some(x => cOf(x) === c)) need.push(c === 'br' ? 'IBOV' : c + ':@IX'); }
    const pays = {}, tget = (u, ms) => getRetry(u, 3, ms);  // servidor recém-iniciado: tenta de novo antes de dizer "sem informações"
    // "comparar com tudo": retornos de todas as ações numa chamada só, em paralelo com o gráfico; nada fica carregando para sempre
    const pR = S.all ? tget(`/api/returns?di=${S.di}&df=${S.df}`, 20000) : null;
    await Promise.all(need.map(async id => { const c = cOf(id), j = await tget(`/api/chart/${encodeURIComponent(tOf(id))}?kind=${kind}${c === 'br' ? '' : '&country=' + c}`, 15000); if (j) pays[id] = j; }));
    if (my !== seq) return;
    const payC = (c) => pays[Object.keys(pays).find(x => cOf(x) === c)] || {}, anyP = payC('br');
    const series = [];
    S.items.forEach((id, i) => {
      let pts = [];
      let vfmt = null;  // modo Valor: preço da ação na moeda dela, pontos do índice, R$/US$ do dólar e do ouro; CDB/IPCA/poupança só %
      if (!isIdx(id)) { const p = pays[id], cur = (rows().find(r => r.cid === id) || {}).cur; if (p && p.stock && !p.stock.error) { pts = gcPricePts(p.stock, start, end); vfmt = (v) => fmtPrice(v, cur); } }
      else {
        const k = (idxList().concat(IDX)).find(x => x[0] === id)[2], d = payC(idxC(id))[k];
        if (d && !d.error) pts = k === 'ibov' ? gcPricePts(d, start, end) : (k === 'usd' || k === 'gold') ? gcPricePts({ t: d.d.map(x => Date.parse(x) / 1000), c: d.v }, start, end) : gcRatePts(d, start, end);
        vfmt = k === 'ibov' ? (v) => F2.format(v) + ' pts' : k === 'usd' ? (v) => fmtPrice(v, 'BRL') : k === 'gold' ? (v) => fmtPrice(v, idxC(id) === 'br' ? 'BRL' : ctry(idxC(id)).currency) : null;
      }
      if (pts.length) { vals[id] = pts[pts.length - 1][1]; series.push({ id: i === 0 ? 'stock' : id, label: label(id), color: COLORS[i % COLORS.length], pts, base: pts.base, vfmt }); }
    });
    const plot = chart.querySelector('.gc-plot'), leg = chart.querySelector('.gc-leg');
    LAST = series.length ? [plot, leg, series, start, end, kind] : null;
    if (series.length) draw();
    else { plot.innerHTML = '<div class="gc-nodata-msg">Sem informações no banco de dados</div>'; leg.innerHTML = ''; }
    if (S.all) {
      const R = (await pR) || {}; S._miss = !Object.keys(R).length || !Object.keys(pays).length;
      if (my !== seq) return;
      for (const r of rows()) { if (S.items.includes(r.cid)) continue; const v = R[r.ticker]; if (v != null) vals[r.cid] = v; }
      for (const [id, , k] of IDX) if (vals[id] == null) { const d = anyP[k]; if (d && !d.error) { const pts = k === 'ibov' ? gcPricePts(d, start, end) : (k === 'usd' || k === 'gold') ? gcPricePts({ t: d.d.map(x => Date.parse(x) / 1000), c: d.v }, start, end) : gcRatePts(d, start, end); if (pts.length) vals[id] = pts[pts.length - 1][1]; } }
    }
    if (!S.all) S._miss = false;
    cols(); chips(); window.__cmpMs = Math.round(performance.now() - t0);
  }
  function cols() {
    const ref = S.items[0], rv = vals[ref], ind = S.crit !== 'preco';
    const fmt = (v) => ind ? F2.format(v) : pc(v);
    const L = [], M = [];
    const cand = S.all ? [...new Set(S.items.slice(1).concat(IDX.map(x => x[0]), rows().map(r => r.cid)))].filter(id => id !== ref) : S.items.slice(1);
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
  // ---------- Medo e Ganância × ação (análise do servidor: /api/fgcmp, medo.py) ----------
  async function fgRun(my) {
    const box = $c('#cmpFg'), ref = S.items[0];
    if (!ref || isIdx(ref) || cOf(ref) !== 'br') { box.innerHTML = '<p class="gt-help">Escolha uma ação da B3 como Principal e toque em Pesquisar.</p>'; return; }
    box.innerHTML = loaderHTML('Analisando…');
    const d = await getRetry(`/api/fgcmp?t=${encodeURIComponent(tOf(ref))}&di=${S.di}&df=${S.df}`, 3, 20000);
    if (my !== seq) return;
    box.innerHTML = d && !d.error && d.n ? fgHtml(d) : `<p class="gt-help">${esc((d && d.error) || 'Sem dados para esta análise no período.')}</p>`;
  }
  function fgHtml(d) {
    const fx = d.faixas, T = esc(d.t), nm = (i) => esc(fx[i][1]), few = (n) => n < 5 ? ' <span class="fgx-few">(poucas ocorrências)</span>' : '';
    const bnd = (v, i) => `<span class="fgx-n ${fgCls(i)}">${v}</span> <span class="${fgCls(i)}">${nm(i)}</span>`;
    const mes = (m) => m.slice(5) + '/' + m.slice(0, 4), p = (v) => v == null ? '—' : pc(v), cl = (v) => v == null ? '' : v > 0 ? 'up' : 'dn';
    const G = [[0, 1, `${nm(0)} ou ${nm(1)}`], [2, 2, nm(2)], [3, 4, `${nm(3)} ou ${nm(4)}`]];
    const grp = (cnt) => G.map(([a, b, l]) => [cnt.slice(a, b + 1).reduce((s, x) => s + x, 0), l]).sort((x, y) => y[0] - x[0])[0];
    const cntOf = (L) => fx.map((_, i) => L.filter(x => x.b === i).length);
    const top = (L, verbo) => {
      const n5 = L.slice(0, 5), n10 = L.slice(0, 10), [k5, l5] = grp(cntOf(n5)), [k10, l10] = grp(cntOf(n10));
      return `<p><b>${k5} das ${n5.length}</b> ${verbo} com o índice em ${l5} no fim do mês anterior.${n10.length > 5 ? ` Nas ${n10.length} maiores: ${k10} em ${l10}.` : ''}${few(n5.length)}</p>
        <table class="gtab"><thead><tr><th>Mês</th><th>Variação</th><th>Índice antes</th></tr></thead><tbody>${n5.map(x => `<tr><td>${mes(x.m)}</td><td class="${cl(x.r)}">${p(x.r)}</td><td>${bnd(x.fg, x.b)}</td></tr>`).join('')}</tbody></table>`;
    };
    const h = d.hoje, sec = (t, body) => `<div class="fgx"><h3>${t}</h3>${body}</div>`;
    const out = [];
    if (h.v != null) out.push(sec('Situação de hoje', `<p>O índice está em ${bnd(h.v, h.b)} (${dataBR(h.d)}). Nas outras <b>${h.n}</b> vezes em que um mês fechou nessa faixa, a ${T} subiu em <b>${h.up}</b> e caiu em <b>${h.dn}</b> nos 3 meses seguintes (média <span class="${cl(h.r3)}">${p(h.r3)}</span>).${few(h.n)}</p>`));
    out.push(sec('Maiores quedas', top(d.quedas, 'maiores quedas mensais vieram')));
    out.push(sec('Maiores altas', top(d.altas, 'maiores altas mensais começaram')));
    out.push(sec('Retorno por faixa', `<p>O que aconteceu com quem comprou a ${T} no fim de um mês em cada faixa.</p>
      <table class="gtab"><thead><tr><th>Comprou com</th><th>Vezes</th><th>1 mês</th><th>6 meses</th><th>12 meses</th><th>Subiu em 12 m</th></tr></thead><tbody>${d.faixa.map(x => `<tr><td class="${fgCls(x.b)}">${nm(x.b)}</td><td>${x.n}</td><td class="${cl(x.r1)}">${p(x.r1)}</td><td class="${cl(x.r6)}">${p(x.r6)}</td><td class="${cl(x.r12)}">${p(x.r12)}</td><td>${x.n12 ? `${x.up12} de ${x.n12}` : '—'}${x.n12 && x.n12 < 5 ? '*' : ''}</td></tr>`).join('')}</tbody></table>${d.faixa.some(x => x.n12 && x.n12 < 5) ? '<p class="fgx-few">* poucas ocorrências</p>' : ''}`));
    const tf = (arr, o) => { const n = arr.reduce((s, x) => s + x, 0); if (!n) return `Nenhuma ${o} de 1 ano no período.`; const [k, l] = grp(arr); return `<b>${k} das ${n}</b> ${o}s de 1 ano aconteceram com o índice em ${l}.${few(n)}`; };
    out.push(sec('Topos e fundos', `<p>${tf(d.fundos, 'mínima')}</p><p>${tf(d.topos, 'máxima')}</p>`));
    const r = d.recup;
    out.push(sec('Tempo de recuperação', r.n ? `<p>Depois de o índice entrar em ${nm(0)} (<b>${r.n}</b> vezes), a ${T} levou em média <b>${r.media == null ? '—' : F2.format(r.media)} meses</b> para voltar ao preço de antes; o pior caso, <b>${r.pior ?? '—'} meses</b>.${r.aberto ? ` Em ${r.aberto} vez(es) ainda não voltou.` : ''}${few(r.n)}</p>` : `<p>O índice não entrou em ${nm(0)} no período.</p>`));
    const m = d.defe.medo, g = d.defe.gan;
    if (m.n && g.n && m.ibov != null) {
      const def = m.acao > m.ibov;
      out.push(sec('Defensiva ou de ciclo', `<p>Nos meses de medo, a ${T} variou em média <span class="${cl(m.acao)}">${p(m.acao)}</span> e o Ibovespa <span class="${cl(m.ibov)}">${p(m.ibov)}</span>; nos de ganância, <span class="${cl(g.acao)}">${p(g.acao)}</span> e <span class="${cl(g.ibov)}">${p(g.ibov)}</span>.</p><p><b>${def ? 'Defensiva' : 'De ciclo'}</b>: ${def ? 'cai menos que o mercado no medo' : 'cai mais que o mercado no medo'} e ${g.acao > g.ibov ? 'sobe mais' : 'sobe menos'} na ganância.${few(Math.min(m.n, g.n))}</p>`));
    }
    if (d.faixa.some(x => x.dy != null)) out.push(sec('Dividendos comprando em cada faixa', `<p>Proventos dos 12 meses seguintes ÷ preço de compra.</p><table class="gtab"><thead><tr><th>Comprou com</th><th>DY em 12 meses</th></tr></thead><tbody>${d.faixa.map(x => `<tr><td class="${fgCls(x.b)}">${nm(x.b)}</td><td>${x.dy == null ? '—' : F2.format(x.dy) + '%'}${x.ndy && x.ndy < 5 ? '*' : ''}</td></tr>`).join('')}</tbody></table>`));
    out.push(sec('Preço × humor do mercado', fgChart(d)));
    return `<p class="fgx-hd">${T} × Medo e Ganância · ${mes(d.per[0])} a ${mes(d.per[1])} (${d.n} meses)</p>${out.join('')}<p class="fgx-few">Comportamento passado, não é garantia nem recomendação. Cálculo mensal: fechamento do mês da ação e índice no último pregão do mês.</p>`;
  }
  function fgChart(d) {  // linha do preço (escala log) e, embaixo, uma faixa com a cor do índice em cada mês
    const s = d.serie, n = s.m.length, W = 600, H = 150, R = 16; if (n < 2) return '';
    const lg = s.c.map(Math.log), lo = Math.min(...lg), hi = Math.max(...lg), x = (i) => i / (n - 1) * W, y = (v) => H - 6 - (v - lo) / (hi - lo || 1) * (H - 12);
    const runs = [];  // meses seguidos na mesma faixa viram um bloco só
    s.fg.forEach((v, i) => { const b = fgBand(v, d.faixas).i, L = runs[runs.length - 1]; if (L && L.b === b) L.e = i; else runs.push({ b, s: i, e: i }); });
    const half = W / (n - 1) / 2;
    const bars = runs.map(r => `<rect class="${fgCls(r.b)}" x="${Math.max(0, x(r.s) - half).toFixed(1)}" y="${H + 6}" width="${(Math.min(W, x(r.e) + half) - Math.max(0, x(r.s) - half)).toFixed(1)}" height="${R}"/>`).join('');
    const line = lg.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    return `<svg class="fgx-ch" viewBox="0 0 ${W} ${H + 6 + R}" preserveAspectRatio="none" role="img" aria-label="Preço de ${esc(d.t)} e faixa do índice em cada mês">${bars}<polyline points="${line}"/></svg>
      <div class="fgx-ax"><span>${s.m[0].slice(0, 4)}</span><span>${s.m[n - 1].slice(0, 4)}</span></div><div class="fgx-lg">${d.faixas.map((f, i) => `<span class="${fgCls(i)}">■ ${esc(f[1])}</span>`).join('')}</div>`;
  }
  let LAST = null;
  const draw = () => LAST && gcRender(...LAST, undefined, { mode: S.vm, cross: true });
  function all() { chips(); compute(); save(); }
  function prep() { chips(); save(); }  // escolhas mudam só a seleção; o resultado sai ao tocar em Pesquisar
  let built = false, waiting = false;
  function build() {
    if (built) return;
    if (!state.data) { root.innerHTML = loaderHTML('Carregando dados…'); if (!waiting) { waiting = true; setTimeout(() => { waiting = false; build(); }, 1200); } return; }
    shell(); built = true;
    for (const id of ['#cmpP', '#cmpQ']) { $c(id).addEventListener('input', drop); $c(id).addEventListener('focus', drop); }
    Promise.all(ctList().map(loadRows));
    root.addEventListener('click', async (e) => {
      if (e.target.closest('#cmpMin')) { S.min = !S.min; $c('#cmpChart').classList.toggle('hidden', S.min || S.all || S.crit !== 'preco'); chips(); save(); return; }
      if (e.target.closest('#cmpAll')) { S.all = !S.all; all(); return; }
      if (e.target.closest('#cmpClr')) { S.items = []; S.all = false; $c('#cmpP').value = $c('#cmpQ').value = ''; all(); return; }  // tira todas as ações/índices e o Comparar tudo
      if (e.target.closest('#cmpGo')) { S.all = false; all(); return; }  // Pesquisar: volta do "Comparar tudo" e compara só os escolhidos
      const vm = e.target.closest('[data-vm]'); if (vm) { S.vm = vm.dataset.vm; chips(); save(); draw(); return; }
      const fl = e.target.closest('[data-ct]');
      if (fl) {  // país escolhido: só ações dele (e seus índices); 🌐 mantém tudo
        S.ct = fl.dataset.ct; if (S.ct !== 'br') S.all = false;
        if (S.ct !== 'all') S.items = S.items.filter(id => (isIdx(id) ? idxList().some(x => x[0] === id) : cOf(id) === S.ct));
        prep(); await Promise.all(ctList().map(loadRows)); return;
      }
      const a = e.target.closest('[data-add]');
      if (a) { if (a.dataset.w === 'p') S.items = [a.dataset.add].concat(S.items.filter(x => x !== a.dataset.add)); else S.items.push(a.dataset.add);
        $c('#cmpP').value = $c('#cmpQ').value = ''; root.querySelectorAll('.cmp-srch .pv-combo').forEach(x => x.classList.add('hidden')); prep(); return; }
      const rm = e.target.closest('[data-rm]'); if (rm) { S.items = S.items.filter(x => x !== rm.dataset.rm); prep(); return; }
      if (e.target.closest('#cmpSwap')) {
                const v = await uiChoose('Trocar o principal por:', S.items.slice(1).filter(id => !(S.crit !== 'preco' && isIdx(id))).map(id => ({ label: esc(label(id)), value: id })));
        if (v) { S.items = [v].concat(S.items.filter(x => x !== v)); prep(); }
      }
    });
    document.addEventListener('click', (e) => { root.querySelectorAll('.cmp-srch').forEach(b => { if (!b.contains(e.target)) b.querySelector('.pv-combo').classList.add('hidden'); }); });
    $c('#cmpCrit').addEventListener('change', () => {
      S.crit = $c('#cmpCrit').value;
      const ok = (x) => !isIdx(x) && (S.crit !== 'fg' || cOf(x) === 'br');  // Medo e Ganância: principal precisa ser ação da B3
      if (S.crit !== 'preco' && S.items[0] && !ok(S.items[0])) { const f = S.items.find(ok); if (f) S.items = [f].concat(S.items.filter(x => x !== f)); }
      prep();
    });
    $c('#cmpDi').addEventListener('change', () => { S.di = $c('#cmpDi').value || yago; prep(); });
    $c('#cmpDf').addEventListener('change', () => { S.df = $c('#cmpDf').value || today; prep(); });
    root.addEventListener('input', (e) => { const k = e.target.dataset.q; if (k) { S[k] = e.target.value; cols(); } });
    all();
  }
  document.addEventListener('tabshow', (e) => { if (e.detail === 'comparar') { if (!built) build(); else if (S.items.length) compute(); } });
  if (!document.querySelector('[data-tabpane="comparar"]').classList.contains('hidden')) build();
})();
