// ---------- Aba Comparar ----------
(function () {
  const $c = (s) => document.querySelector(s);
  const KEY = 'screenerB3.comparar.v1';
  const IDX = Object.entries(window.INDICES || {}).map(([k, n]) => ['@' + k, n, k]);  // nomes: history.INDICES (servidor)
  const COLORS = ['#34d399', '#60a5fa', '#facc15', '#f472b6', '#fb923c', '#a78bfa', '#d4a373', '#22d3ee', '#f87171', '#a3e635', '#e879f9', '#94a3b8'];
  const today = new Date().toISOString().slice(0, 10), yago = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
  let S = (() => { try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; } })();
  S.items = S.items || []; S.min = !!S.min; S.all = !!S.all; S.ct = S.ct || 'br'; S.vm = S.vm || 'pct'; S.crit = S.crit || 'preco'; S.di = S.di || yago; S.df = S.df || today; S.qa = ''; S.qb = '';
  S.ini = S.ini >= 0 ? S.ini : 20000; S.ap = S.ap >= 0 ? S.ap : 500; S.mu = S.mu || 'sel'; S.mv = S.mv || 'media'; S.mg = S.mg === 'grp' ? 'grp' : 'ind';  // Modelos: valores, empresas e tabela
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ items: S.items, crit: S.crit, di: S.di, df: S.df, min: S.min, all: S.all, ct: S.ct, vm: S.vm, fgOrd: S.fgOrd, ini: S.ini, ap: S.ap, mu: S.mu, mv: S.mv, mg: S.mg })); } catch (e) { } };
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
      <div class="cmp-row frm"><label><span>Critério</span><select id="cmpCrit" class="sel"><option value="preco">Preço da ação</option><option value="fg">Medo e Ganância</option><option value="mod">Modelos</option>${fields.map(f => `<option value="${f.key}">${esc(f.label)}</option>`).join('')}</select></label>
        <label><span>Início</span><input id="cmpDi" type="date" class="sel"></label><label><span>Fim</span><input id="cmpDf" type="date" class="sel"></label>
        <label class="cmp-mod"><span>Valor inicial</span><input id="cmpIni" inputmode="decimal" class="sel"></label><label class="cmp-mod"><span>Aporte mensal</span><input id="cmpAp" inputmode="decimal" class="sel"></label>
        <label class="cmp-mod"><span>Empresas</span><select id="cmpMu" class="sel"></select></label><div class="cmp-mod gt-tabs cmp-mg" role="group" aria-label="Individual ou Grupo"><button type="button" data-mg="ind">Individual</button><button type="button" data-mg="grp">Grupo</button>${glossBtn('Modo Grupo')}</div></div>
      <div id="cmpChips" class="cmp-chips"></div><button type="button" id="cmpGo" class="gbtn pri w-full">Pesquisar</button><button type="button" id="cmpAll" class="cmp-allb"></button><button type="button" id="cmpClr" class="gbtn w-full cmp-clr">Limpar tudo</button></section>
      <div class="cmp-bar"><div class="cmp-vm" role="group" aria-label="Mostrar no gráfico"><button type="button" data-vm="pct">%</button><button type="button" data-vm="val">Valor</button></div><button type="button" id="cmpMin" class="cmp-minb"></button></div>
      <div id="cmpChart" class="gchart cmp-chart" data-m="1"><div class="gc-body"><div class="gc-plot"></div><div class="gc-leg"></div></div></div>
      <section class="cmp-cols"><div class="cmp-col"><h3 class="dn">Renderam menos</h3><input class="cmp-f" data-q="qa" type="search" placeholder="Filtrar…" autocomplete="off"><div id="cmpLess"></div></div>
        <div class="cmp-col"><h3 class="up">Renderam mais</h3><input class="cmp-f" data-q="qb" type="search" placeholder="Filtrar…" autocomplete="off"><div id="cmpMore"></div></div></section>
      <section id="cmpFg" class="fgx-w hidden"></section><section id="cmpMod" class="fgx-w hidden"></section>`;
    $c('#cmpCrit').value = S.crit; $c('#cmpDi').value = S.di; $c('#cmpDf').value = S.df;
    $c('#cmpIni').value = F2.format(S.ini); $c('#cmpAp').value = F2.format(S.ap); muFill(); mgOn();
  }
  function chips() {
    const mod = S.crit === 'mod', fgm = S.crit === 'fg', ind = S.crit !== 'preco' && !fgm && !mod, ref = S.items[0];
    // Medo e Ganância: só a ação principal (B3) e o período · Modelos: empresas escolhidas (ou Todas / 5 maiores de cada setor), período e valores
    for (const s of ['#cmpQl', '.cmp-srch[data-w="q"]', '#cmpChips']) root.querySelectorAll(s).forEach(e => e.classList.toggle('fgx-off', fgm || (mod && S.mu !== 'sel')));
    for (const s of ['.cmp-bar', '.cmp-cols', '#cmpChart']) root.querySelectorAll(s).forEach(e => e.classList.toggle('fgx-off', fgm || mod));
    root.querySelectorAll('#cmpPrin, .cmp-srch[data-w="p"], .cmp-head').forEach(e => e.classList.toggle('fgx-off', mod && S.mu !== 'sel'));
    root.querySelectorAll('.cmp-mod').forEach(e => e.classList.toggle('fgx-off', !mod));
    $c('#cmpFg').classList.toggle('hidden', !fgm); $c('#cmpMod').classList.toggle('hidden', !mod);
    root.querySelectorAll('[data-ct]').forEach(b => b.classList.toggle('on', b.dataset.ct === S.ct));
    root.querySelectorAll('[data-vm]').forEach(b => b.classList.toggle('on', b.dataset.vm === S.vm));
    $c('#cmpAll').classList.toggle('hidden', S.ct !== 'br' || fgm);  // "Comparar tudo" usa o histórico da B3: só no Brasil (em Modelos = Empresas Todas)
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
    const ind = S.crit !== 'preco', fgm = S.crit === 'fg' || S.crit === 'mod';  // Medo e Ganância e Modelos: só ações da B3
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
    if (S.crit === 'mod') { modRun(my); return; }
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
    const sorter = (a, b) => (fav(b.id) - fav(a.id)) || (fav(a.id) ? favRank(a.id) - favRank(b.id) : 0) || Math.abs(b.d) - Math.abs(a.d);  // favoritos primeiro, na ordem dos Favoritos
    const html = (arr, q, cls) => arr.filter(x => !q || norm(label(x.id)).includes(norm(q))).sort(sorter).map(x => `<div class="cmp-it"><b>${fav(x.id) ? '★ ' : ''}${esc(label(x.id))}</b><span class="${cls}">${fmt(x.v)}</span><small>${rv != null ? (x.d > 0 ? '+' : '') + F2.format(x.d) + (ind ? '' : ' p.p.') + ' vs ref.' : ''}</small></div>`).join('') || '<p class="text-xs text-slate-500 py-2">—</p>';
    $c('#cmpLess').innerHTML = (rv != null ? `<p class="cmp-ref">Principal ${esc(label(ref))}: ${fmt(rv)}</p>` : '') + html(L, S.qa, 'dn');
    if (S._miss) $c('#cmpLess').insertAdjacentHTML('afterbegin', '<p class="gt-help">Alguns dados não carregaram agora; mostrando o que veio.</p>');
    $c('#cmpMore').innerHTML = (rv != null ? `<p class="cmp-ref">Principal ${esc(label(ref))}: ${fmt(rv)}</p>` : '') + html(M, S.qb, 'up');
  }
  // ---------- Medo e Ganância × ação (análise do servidor: /api/fgcmp, medo.py) ----------
  const yrsBack = (iso, n) => { const x = new Date(iso + 'T12:00:00Z'); x.setUTCFullYear(x.getUTCFullYear() - n); return x.toISOString().slice(0, 10); };
  let FGD = null, FGS = {};  // última análise (gráficos interativos) e suas seções
  const FG_IDS = ['hoje', 'faixa', 'quedas', 'altas', 'topos', 'recup', 'defe', 'graf'];  // ordem padrão das análises
  const fgOrder = () => (S.fgOrd || []).filter(id => FGS[id]).concat(FG_IDS.filter(id => FGS[id] && !(S.fgOrd || []).includes(id)));
  async function fgRun(my) {
    const box = $c('#cmpFg'), ref = S.items[0];
    if (!ref || isIdx(ref) || cOf(ref) !== 'br') { box.innerHTML = '<p class="gt-help">Escolha uma ação da B3 como Principal e toque em Pesquisar.</p>'; return; }
    let aviso = '';
    if (S.di > yrsBack(S.df, 5)) { S.di = yrsBack(S.df, 5); $c('#cmpDi').value = S.di; save(); aviso = `<p class="gt-help">Período mínimo de 5 anos: Início ajustado para ${dataBR(S.di)}.</p>`; }
    box.innerHTML = aviso + loaderHTML('Analisando…');
    const d = await getRetry(`/api/fgcmp?t=${encodeURIComponent(tOf(ref))}&di=${S.di}&df=${S.df}`, 3, 30000);
    if (my !== seq) return;
    FGD = d && !d.error && d.n ? d : null;
    box.innerHTML = aviso + (FGD ? fgHtml(d) : `<p class="gt-help">${esc((d && d.error) || 'Sem dados para esta análise no período.')}</p>`);
  }
  function fgHtml(d) {
    const fx = d.faixas, T = esc(d.t), nm = (i) => esc(fx[i][1]), few = (n) => n < 5 ? ' <span class="fgx-few">(poucas ocorrências)</span>' : '';
    const bnd = (v, i) => `<span class="fgx-n ${fgCls(i)}">${v}</span> <span class="${fgCls(i)}">${nm(i)}</span>`;
    const mes = (m) => m.slice(5) + '/' + m.slice(0, 4), p = (v) => v == null ? '—' : pc(v), cl = (v) => v == null ? '' : v > 0 ? 'up' : 'dn';
    const G = [[0, 1, `${nm(0)} ou ${nm(1)}`], [2, 2, nm(2)], [3, 4, `${nm(3)} ou ${nm(4)}`]];
    const grp = (cnt) => G.map(([a, b, l]) => [cnt.slice(a, b + 1).reduce((s, x) => s + x, 0), l]).sort((x, y) => y[0] - x[0])[0];
    const cntOf = (L) => fx.map((_, i) => L.filter(x => x.b === i).length);
    const S2 = {};  // seções por id (a ordem é escolhida em ⇅ Reorganizar)
    const sec = (id, t, body) => { S2[id] = { t, html: `<div class="fgx" data-fgs="${id}"><h3>${t}</h3>${body}</div>` }; };
    // velocímetros: ação e mercado (hoje, ontem, 1 semana, 1 mês)
    const gauge = (titulo, L) => {
      if (!L || L[0] == null) return `<div class="fgx-g"><div class="fg-h">${titulo}</div><p class="fgx-few">Sem dados suficientes para o índice.</p></div>`;
      const b = fgBand(L[0], fx), ago = [['Ontem', L[1]], ['1 sem.', L[2]], ['1 mês', L[3]]].filter(x => x[1] != null).map(([l, x]) => `${l} <b class="${fgCls(fgBand(x, fx).i)}">${x}</b>`).join(' · ');
      return `<div class="fgx-g">${fgGauge(L[0], fx)}<div class="fg-h">${titulo}</div><div class="fg-v ${fgCls(b.i)}"><b>${L[0]}</b> ${esc(b.n)}</div><div class="fg-p">${ago}</div></div>`;
    };
    const out = [`<div class="fgx fgx-gs">${gauge(T, d.acao)}${gauge('Mercado (B3)', d.mercado)}</div>`];  // velocímetros e conclusão: sempre no topo
    // conclusão: comprar no medo × na ganância (12 meses)
    const fa = d.faixa, pick = (ids) => ids.map(i => fa[i]).find(x => x && x.n12 >= 3);
    const fm = pick([0, 1]), fgn = pick([4, 3]);
    if (fm && fgn) out.push(`<p class="fgx-cc">Historicamente, comprar ${T} com o índice dela em <span class="${fgCls(fm.b)}">${nm(fm.b)}</span> rendeu em média <span class="${cl(fm.r12)}">${p(fm.r12)}</span> em 12 meses; em <span class="${fgCls(fgn.b)}">${nm(fgn.b)}</span>, <span class="${cl(fgn.r12)}">${p(fgn.r12)}</span>.</p>`);
    const h = d.hoje;
    if (h.v != null) sec('hoje', 'Situação de hoje', `<p>Hoje (${dataBR(h.d)}) o índice da ${T} está em ${bnd(h.v, h.b)}. No período escolhido, das <b>${h.n}</b> vezes em que um mês fechou com a ${T} nessa faixa, ela subiu em <b>${h.up}</b> e caiu em <b>${h.dn}</b> nos 3 meses seguintes (média <span class="${cl(h.r3)}">${p(h.r3)}</span>).${few(h.n)}</p>`);
    sec('faixa', 'Retorno por faixa', `<p>O que aconteceu com quem comprou a ${T} no fim de um mês em cada faixa do índice dela.</p>
      <table class="gtab"><thead><tr><th>Comprou com</th><th>Vezes</th><th>1 mês</th><th>6 meses</th><th>12 meses</th><th>Subiu em 12 m</th></tr></thead><tbody>${fa.map(x => `<tr><td class="${fgCls(x.b)}">${nm(x.b)}</td><td>${x.n}</td><td class="${cl(x.r1)}">${p(x.r1)}</td><td class="${cl(x.r6)}">${p(x.r6)}</td><td class="${cl(x.r12)}">${p(x.r12)}</td><td>${x.n12 ? `${x.up12} de ${x.n12}` : '—'}${x.n12 && x.n12 < 5 ? '*' : ''}</td></tr>`).join('')}</tbody></table>${fa.some(x => x.n12 && x.n12 < 5) ? '<p class="fgx-few">* poucas ocorrências</p>' : ''}`);
    const top = (L, verbo) => {
      if (!L.length) return '<p>Nenhuma no período.</p>';
      const [k, l] = grp(cntOf(L));
      return `<p><b>${k} das ${L.length}</b> ${verbo} com o índice da ${T} em ${l} no dia em que a semana começou.${few(L.length)}</p>
        <table class="gtab"><thead><tr><th>Semana de</th><th>Variação</th><th>Índice da ação no dia</th></tr></thead><tbody>${L.map(x => `<tr><td>${dataBR(x.d)}</td><td class="${cl(x.r)}">${p(x.r)}</td><td>${bnd(x.fg, x.b)}</td></tr>`).join('')}</tbody></table>`;
    };
    sec('quedas', 'Maiores quedas semanais', top(d.quedas, 'maiores quedas semanais começaram'));
    sec('altas', 'Maiores altas semanais', top(d.altas, 'maiores altas semanais começaram'));
    const tf = (arr, o) => { const n = arr.reduce((s, x) => s + x, 0); if (!n) return `Nenhuma ${o} de 1 ano no período.`; const [k, l] = grp(arr); return `<b>${k} das ${n}</b> ${o}s de 1 ano da ${T} aconteceram com o índice do mercado em ${l}.${few(n)}`; };
    sec('topos', 'Topos e fundos × humor do mercado', `<p>${tf(d.fundos, 'mínima')}</p><p>${tf(d.topos, 'máxima')}</p>`);
    const r = d.recup;
    sec('recup', 'Tempo de recuperação', r.n ? `<p>Depois de o índice da ${T} entrar em ${nm(0)} (<b>${r.n}</b> vezes), a ${T} levou em média <b>${r.media == null ? '—' : F2.format(r.media)} meses</b> para voltar ao preço de antes; o pior caso, <b>${r.pior ?? '—'} meses</b>.${r.aberto ? ` Em ${r.aberto} vez(es) ainda não voltou.` : ''}${few(r.n)}</p>` : `<p>O índice da ${T} não entrou em ${nm(0)} no período.</p>`);
    const m = d.defe.medo, g = d.defe.gan;
    if (m.n && g.n && m.ibov != null) {
      const def = m.acao > m.ibov;
      sec('defe', 'Defensiva ou de ciclo (× mercado)', `<p>Nos meses de medo do mercado, a ${T} variou em média <span class="${cl(m.acao)}">${p(m.acao)}</span> e o Ibovespa <span class="${cl(m.ibov)}">${p(m.ibov)}</span>; nos de ganância, <span class="${cl(g.acao)}">${p(g.acao)}</span> e <span class="${cl(g.ibov)}">${p(g.ibov)}</span>.</p><p><b>${def ? 'Defensiva' : 'De ciclo'}</b>: ${def ? 'cai menos que o mercado no medo' : 'cai mais que o mercado no medo'} e ${g.acao > g.ibov ? 'sobe mais' : 'sobe menos'} na ganância.${few(Math.min(m.n, g.n))}</p>`);
    }
    sec('graf', `Preço × humor da ${T}`, fgChart(d));
    FGS = S2;
    return `<div class="fgx-hdr"><p class="fgx-hd">${T} × Medo e Ganância · ${mes(d.per[0])} a ${mes(d.per[1])} (${d.n} meses)</p><button type="button" class="gbtn" data-fgreorg>⇅ Reorganizar</button></div>${out.join('')}${fgOrder().map(id => S2[id].html).join('')}<p class="fgx-few">Comportamento passado, não é garantia nem recomendação. Altas e quedas: 5 pregões; demais análises: mensais (fechamento do mês e índice no último pregão do mês).</p>`;
  }
  // dois gráficos com as mesmas datas: preço (em cima) e índice (embaixo, com as faixas no fundo); tocar em um marca os dois
  function fgChart(d) {
    const s = d.serie, n = s.d.length, W = 600, H1 = 150, H2 = 90; if (n < 2) return '';
    const lg = s.c.map(Math.log), lo = Math.min(...lg), hi = Math.max(...lg), x = (i) => (i / (n - 1) * W).toFixed(1);
    const y1 = (i) => H1 - 6 - (lg[i] - lo) / (hi - lo || 1) * (H1 - 12), y2 = (v) => H2 - v / 100 * H2;
    d._y1 = (i) => y1(i) / H1 * 100; d._y2 = (i) => y2(s.fg[i]) / H2 * 100;
    let a = 0;
    const zones = d.faixas.map((f, i) => { const z = `<rect class="${fgCls(i)}" x="0" y="${y2(f[0]).toFixed(1)}" width="${W}" height="${(y2(a) - y2(f[0])).toFixed(1)}"/>`; a = f[0]; return z; }).join('');
    const line = (fy) => s.d.map((_, i) => `${x(i)},${fy(i).toFixed(1)}`).join(' ');
    const panel = (cls, h, body) => `<div class="fgc-p ${cls}"><svg viewBox="0 0 ${W} ${h}" preserveAspectRatio="none">${body}</svg><i class="fgc-vl hidden"></i><b class="fgc-dot hidden"></b><span class="fgc-lb hidden"></span></div>`;
    return `<div class="fgc" role="img" aria-label="Preço de ${esc(d.t)} e índice de Medo e Ganância da ação por data">
      ${panel('fgc-pr', H1, `<polyline points="${line(y1)}"/>`)}${panel('fgc-ix', H2, `${zones}<polyline points="${line(i => y2(s.fg[i]))}"/>`)}
      <div class="fgx-ax"><span>${dataBR(s.d[0])}</span><span>${dataBR(s.d[n - 1])}</span></div></div>
      <p class="fgx-few">Toque ou arraste no gráfico: em cima, o preço; embaixo, o índice da ação e a faixa naquele dia.</p>`;
  }
  function fgPoint(e) {
    const box = e.target.closest && e.target.closest('.fgc'); if (!box || !FGD) return;
    const s = FGD.serie, n = s.d.length, r = box.querySelector('.fgc-pr').getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), i = Math.round(f * (n - 1)), xp = (i / (n - 1) * 100) + '%';
    const b = fgBand(s.fg[i], FGD.faixas), side = f > .55 ? 'translateX(calc(-100% - 6px))' : 'translateX(6px)';
    const put = (p, yp, txt, cls) => {
      const [vl, dot, lb] = [p.querySelector('.fgc-vl'), p.querySelector('.fgc-dot'), p.querySelector('.fgc-lb')];
      [vl, dot, lb].forEach(el => el.classList.remove('hidden'));
      vl.style.left = dot.style.left = lb.style.left = xp; dot.style.top = yp + '%'; lb.style.transform = side; lb.className = 'fgc-lb ' + cls; lb.textContent = txt;
    };
    put(box.querySelector('.fgc-pr'), FGD._y1(i), `${fmtPrice(s.c[i], 'BRL')} · ${dataBR(s.d[i])}`, '');
    put(box.querySelector('.fgc-ix'), FGD._y2(i), `${s.fg[i]} · ${FGD.faixas[b.i][1]}`, fgCls(b.i));
  }
  // colocação: medalhas 🥇🥈🥉 até o 3º; depois selo arredondado "4º", "5º"… na cor da colocação (seção Cores do painel ⓘ)
  const MED = ['🥇', '🥈', '🥉'];
  const RK = (p) => p < 0 || p == null ? '' : p < 3 ? `<span class="rkm" role="img" aria-label="${p + 1}º">${MED[p]}</span>` : `<i class="rkb rk-${p}">${p + 1}º</i>`;
  const RKN = (p) => p < 3 ? RK(p) + `${p + 1}º` : RK(p);  // com o número (cabeçalhos e pior colocação)
  // Tabelas dos modelos a partir de modelos.compare (Comparar → Modelos e Previsão com o card Modelos em Todos).
  // mv: media | emp | pos | con; nm: nomes dos modelos (/api/modelos); only: id de um modelo (filtro da Previsão)
  window.modTables = (d, mv, nm, only) => {
    const NV = (i) => esc(nm[d.m[i]] || d.m[i]), N = (i) => NV(i) + (R[i].ref ? refInfo(d.m[i]) : ''), R = d.res, cl = (v) => v == null ? '' : v < 0 ? 'dn' : 'up', pp = (v) => v == null ? '—' : pc(v);
    const posOf = (ord) => { const o = {}; ord.forEach((i, p) => { o[i] = p; }); return o; };
    // CDB e Ouro (modelos.REF) entram como linhas, pelo rendimento; nos Pontos ficam sempre com as últimas colocações
    const TR = (i) => R[i].ref ? `<tr class="pvd-ref tap" data-mo="|${d.m[i]}">` : '<tr>';
    const tab = (h, body) => `<div class="pv-scroll"><table class="gtab cmp-mt" data-srt><thead><tr>${h.map(([l, k]) => thSort(l, k)).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
    const td = (v, html, cls = '') => `<td data-v="${v ?? ''}" class="${cls}">${html}</td>`;
    const rp = (r) => `<span class="${cl(r.pct)}">${pp(r.pct)}</span>`, rv = (r) => r.v == null ? '—' : brl.format(r.v);
    if (mv === 'media') {
      const ps = posOf(d.ord_media);
      const CT = Object.fromEntries((d.cart || []).map(c => [c.m, c.pct]));  // Média da carteira: modo Grupo (uma carteira por modelo)
      return tab([['Modelo', 'm'], ['Média por empresa', 'l'], ['Média da carteira', 'k'], ['Valor final médio', 'v']], d.ord_media.map(i => `${TR(i)}${td(NV(i), RK(ps[i]) + N(i))}${td(R[i].media, pp(R[i].media), cl(R[i].media))}${td(CT[d.m[i]], pp(CT[d.m[i]]), cl(CT[d.m[i]]))}${td(R[i].vmedio, R[i].vmedio == null ? '—' : brl.format(R[i].vmedio))}</tr>`).join(''));
    }
    if (mv === 'emp') {
      const cols = d.ord_pos.filter(i => !R[i].ref && (!only || d.m[i] === only));
      const rl = (d.ref || []).map(r => `<button type="button" class="pv-lnk" data-mo="|${r.m}">${esc(r.t)}</button>${refInfo(r.m)} ${rp(r)}`).join(' · ');
      return (rl ? `<p class="pvd-note">${rl}</p>` : '') + tab([['Ativo', 't']].concat(cols.map(i => [N(i), d.m[i]])), d.t.map((tk, j) => `<tr>${td(tk, `<b>${esc(tk)}</b>`)}${cols.map(i => d.p[i][j] == null ? '<td data-v="" title="fora do método">—</td>' : `<td class="tap" data-v="${d.p[i][j]}" data-mo="${esc(tk)}|${d.m[i]}">${RK(d.rk[i][j])}<span class="${cl(d.p[i][j])}">${pp(d.p[i][j])}</span></td>`).join('')}</tr>`).join(''));
    }
    if (mv === 'pos') {  // pontos por colocação (modelos.PONTOS: 21, 18, 15…); ordem pela média de pontos (modelos.ranking)
      const ps = posOf(d.ord_pts);
      return tab([['Modelo', 'm']].concat(d.m.map((_, p) => [RKN(p), 'p' + p])).concat([['Pontos', 'pt'], ['Média de pontos', 'pm'], ['Lucro mediano', 'md']]),
        d.ord_pts.map(i => `${TR(i)}${td(NV(i), RK(ps[i]) + N(i))}${R[i].pos.map(c => td(c, c || '—')).join('')}${td(R[i].pts, `<b>${R[i].pts}</b>`)}${td(R[i].ptsm, F2.format(R[i].ptsm))}${td(R[i].mediana, pp(R[i].mediana), cl(R[i].mediana))}</tr>`).join(''));
    }
    const ord = R.map((_, i) => i).sort((a, b) => (R[b].mediana ?? -1e9) - (R[a].mediana ?? -1e9)), ps = posOf(ord);
    return tab([['Modelo', 'm'], ['Lucro mediano', 'md'], ['Ganha de Comprar e segurar', 'g'], ['Pior colocação', 'w']], ord.map(i => `${TR(i)}${td(NV(i), RK(ps[i]) + N(i))}${td(R[i].mediana, pp(R[i].mediana), cl(R[i].mediana))}${td(R[i].ganha ?? -1, R[i].ganha == null ? '—' : F0.format(R[i].ganha) + '% das empresas')}${td(R[i].pior ?? 99, R[i].pior == null ? '—' : RKN(R[i].pior - 1))}</tr>`).join(''));
  };
  // CDB e Ouro: ⓘ com a explicação curta (Glossário); a nota só aparece quando o ouro começa depois do início do período
  window.refInfo = (m) => glossBtn(m === 'cdb' ? 'CDB nos modelos' : 'Ouro nos modelos');
  window.modRefNote = (d) => (d.ref || []).filter(r => /cotação do ouro só desde/.test(r.nota || '')).map(r => `Ouro: ${esc(r.nota.split('; ').slice(1).join('; '))}.`).join(' ') + (d.fora ? ` Método Barsi: ${d.fora} de ${d.t.length} empresas fora do método (setor não perene ou sem dividendos regulares) aparecem como — e não entram nas colocações dele.` : '');
  window.modRK = (p) => RK(p);
  // modo Grupo: cada modelo cuida de UMA carteira com as empresas escolhidas (modelos.grupo); CDB e Ouro com o mesmo dinheiro
  window.modGrupo = (d, nm) => {
    const L = (d.cart || []).slice().sort((a, b) => (b.pct ?? -1e9) - (a.pct ?? -1e9)), cl = (v) => v == null ? '' : v < 0 ? 'dn' : 'up';
    const td = (v, h, c = '') => `<td data-v="${v ?? ''}" class="${c}">${h}</td>`;
    return `<div class="pv-scroll"><table class="gtab cmp-mt" data-srt><thead><tr>${[['Modelo', 'm'], ['Rendimento da carteira', 'p'], ['Valor final', 'v'], ['Imposto pago', 'i'], ['Compras / vendas', 'c']].map(([l, k]) => thSort(l, k)).join('')}</tr></thead><tbody>${L.map((c, p) => `<tr${c.ref ? ' class="pvd-ref"' : ''}>${td(esc(nm[c.m] || c.m), RK(p) + esc(nm[c.m] || c.m) + (c.ref ? refInfo(c.m) : ''))}${td(c.pct, c.pct == null ? '—' : pc(c.pct), cl(c.pct))}${td(c.v, c.v == null ? '—' : brl.format(c.v))}${td(c.ir, c.ref ? '—' : brl.format(c.ir))}${td(c.c ?? -1, c.ref ? '—' : `${c.c} / ${c.s}`)}</tr>`).join('')}</tbody></table></div>`;
  };
  // rodapé dos resultados dos modelos: tópicos curtos em colunas (Período · Empresas · Aportado · Rendimento · Observações)
  window.modInfo = (d, o = {}) => {
    const it = [['Período', `${dataBR(d.ini)} a ${dataBR(d.fim)} (${d.meses} meses)`],
      d.t ? ['Empresas', `${d.t.length} de ${d.pedidas} (com preço no início)`] : null,
      ['Aportado', `${brl.format(d.apT)}${d.t ? ' por empresa' : ''}`],
      ['Rendimento', '(valor final − aportado) ÷ aportado'],
      o.extra ? ['Dica', o.extra] : null, modRefNote(d) ? ['Obs.', modRefNote(d)] : null].filter(Boolean);
    return `<dl class="pv-info">${it.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>`;
  };
  // ---------- Modelos: todos os modelos da Previsão nas empresas escolhidas (simulação do servidor: modelos.compare) ----------
  let MD = null, MN = {};
  const MV = [['media', 'Média'], ['emp', 'Por empresa'], ['pos', 'Colocações'], ['con', 'Consistência']];
  // Empresas (Modelos): as escolhidas acima, 5 maiores de cada setor ou uma empresa da aba Ações (todas: botão Comparar tudo)
  const mgOn = () => root.querySelectorAll('[data-mg]').forEach(b => b.classList.toggle('on', b.dataset.mg === S.mg));
  function muFill() {
    const rows = ((state.data && state.data.rows) || []).filter(r => /\d$/.test(r.ticker)).map(r => r.ticker).sort();
    if (S.mu === 'all') S.mu = 'sel';
    $c('#cmpMu').innerHTML = `<option value="sel">Escolhidas acima</option><option value="top5">5 maiores de cada setor</option><optgroup label="Empresas da aba Ações">${rows.map(t => `<option value="t:${t}">${t}</option>`).join('')}</optgroup>`;
    $c('#cmpMu').value = S.mu; if ($c('#cmpMu').value !== S.mu) { S.mu = 'sel'; $c('#cmpMu').value = 'sel'; }
  }
  async function modRun(my) {
    const one = S.mu.startsWith('t:') ? [S.mu.slice(2)] : null, box = $c('#cmpMod'), t = one || S.items.filter(x => !isIdx(x) && cOf(x) === 'br').map(tOf);
    const u = S.all ? 'all' : one ? 'sel' : S.mu;  // Comparar tudo: todas as empresas; Voltar: volta às Empresas escolhidas
    if (u === 'sel' && !t.length) { box.innerHTML = '<p class="gt-help">Escolha uma ou mais ações da B3 (ou uma empresa / 5 maiores de cada setor em Empresas; todas: Comparar tudo) e toque em Pesquisar.</p>'; return; }
    box.innerHTML = loaderHTML('Simulando os modelos…');
    if (!Object.keys(MN).length) { try { const m = await (await fetch('/api/modelos')).json(); (m.modelos || []).forEach(x => { MN[x.id] = x.n; }); } catch (e) { } }
    let d = null;
    for (let k = 0; k < 20 && my === seq; k++) {
      try {
        const r = await fetch('/api/modelos/comparar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ u, t, di: S.di, df: S.df, ini: S.ini, ap: S.ap, fav: [...FAVS] }) });
        if (r.status === 202) { await new Promise(z => setTimeout(z, 3000)); continue; }
        d = await r.json(); break;
      } catch (e) { await new Promise(z => setTimeout(z, 3000)); }
    }
    if (my !== seq) return;
    MD = d && !d.error && d.t ? d : null;
    box.innerHTML = MD ? modHtml() : `<p class="gt-help">${esc((d && d.error) || 'Não foi possível comparar agora.')}</p>`;
  }
  function modHtml() {
    const d = MD, emp = S.mv === 'emp' && S.mg !== 'grp';
    if (S.mg === 'grp') return `${modGrupo(d, MN)}${modInfo(d, { extra: `Grupo: uma carteira por modelo com as ${d.t.length} empresas, mesmo aporte de uma empresa ${glossBtn('Modo Grupo')}` })}`;
    return `<div class="gt-tabs" role="tablist">${MV.map(([k, l]) => `<button type="button" data-mv="${k}" class="${S.mv === k ? 'on' : ''}">${l}</button>`).join('')}</div>${modTables(d, S.mv, MN)}
      ${modInfo(d, { extra: emp ? 'toque num valor para ver o mês a mês na Previsão' : '' })}`;
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
      if (e.target.closest('[data-fgreorg]')) {  // ⇅ Reorganizar as análises do Medo e Ganância
        const ids = await uiReorder('Análises', fgOrder().map(id => ({ id, label: FGS[id].t })));
        if (ids) { S.fgOrd = ids; save(); if (FGD) $c('#cmpFg').innerHTML = fgHtml(FGD); }
        return;
      }
      if (e.target.closest('#cmpGo')) { S.all = false; all(); return; }
      const mg = e.target.closest('[data-mg]'); if (mg) { S.mg = mg.dataset.mg; mgOn(); save(); if (MD) $c('#cmpMod').innerHTML = modHtml(); return; }
      const mv = e.target.closest('[data-mv]'); if (mv && MD) { S.mv = mv.dataset.mv; save(); $c('#cmpMod').innerHTML = modHtml(); return; }
      const mo = !e.target.closest('[data-gl]') && e.target.closest('[data-mo]');
      if (mo && MD) {  // mês a mês na Previsão; "‹ Voltar ao Comparar" volta para esta mesma tela, sem pesquisar de novo
        const [t, m] = mo.dataset.mo.split('|'), y = window.scrollY;
        if (window.pvOpen) pvOpen({ t, m, di: MD.ini, df: MD.fim, ini: S.ini, ap: S.ap, back: () => { keep = true; showTab('comparar'); requestAnimationFrame(() => window.scrollTo(0, y)); } });
        return;
      }  // Pesquisar: volta do "Comparar tudo" e compara só os escolhidos
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
    root.addEventListener('pointerdown', fgPoint); root.addEventListener('pointermove', (e) => { if (e.buttons || e.pointerType === 'mouse') fgPoint(e); });
    $c('#cmpCrit').addEventListener('change', () => {
      S.crit = $c('#cmpCrit').value;
      if (S.crit === 'fg') { S.di = yrsBack(S.df, 10); $c('#cmpDi').value = S.di; }  // Medo e Ganância: começa com 10 anos
      if (S.crit === 'mod') { S.ct = 'br'; S.di = yrsBack(S.df, 10); $c('#cmpDi').value = S.di; }  // Modelos: ações da B3, começa com 10 anos
      const ok = (x) => !isIdx(x) && ((S.crit !== 'fg' && S.crit !== 'mod') || cOf(x) === 'br');  // Medo e Ganância e Modelos: principal precisa ser ação da B3
      if (S.crit !== 'preco' && S.items[0] && !ok(S.items[0])) { const f = S.items.find(ok); if (f) S.items = [f].concat(S.items.filter(x => x !== f)); }
      prep();
    });
    $c('#cmpDi').addEventListener('change', () => { S.di = $c('#cmpDi').value || yago; prep(); });
    $c('#cmpDf').addEventListener('change', () => { S.df = $c('#cmpDf').value || today; prep(); });
    for (const [id, k] of [['#cmpIni', 'ini'], ['#cmpAp', 'ap']]) $c(id).addEventListener('change', () => { S[k] = Math.max(0, parseBR($c(id).value)); $c(id).value = F2.format(S[k]); prep(); });
    $c('#cmpMu').addEventListener('change', () => { S.mu = $c('#cmpMu').value; prep(); });
    root.addEventListener('input', (e) => { const k = e.target.dataset.q; if (k) { S[k] = e.target.value; cols(); } });
    all();
  }
  let keep = false;  // volta da Previsão (‹ Voltar ao Comparar): mantém o resultado na tela
  document.addEventListener('tabshow', (e) => { if (e.detail === 'comparar') { if (!built) build(); else if (keep) keep = false; else if (S.items.length) compute(); } });
  if (!document.querySelector('[data-tabpane="comparar"]').classList.contains('hidden')) build();
})();
