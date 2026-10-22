// ---------- Grupos (localStorage + exportar/importar .json) ----------
(function () {
  const KEY = 'screenerB3.grupos.v1';
  const $g = (s) => document.querySelector(s);
  let groups = (() => { try { const g = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(g) ? g : []; } catch (e) { return []; } })();
  window.userGroups = () => groups.filter(g => !g.sim).map(g => ({ n: g.name, t: g.tickers }));  // Previsão → Modelos (rodízio nos grupos do usuário)
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(groups)); } catch (e) { uiAlert('Não foi possível salvar no navegador.'); } if (typeof sendPins === 'function') sendPins(); pushGroups(); };
  state.selSet = new Set(); state.selMode = false; state.group = null;
  // Grupo simulação (criado na Previsão): {name, tickers: [], sim: {di, v0}}; o servidor simula todos os modelos desde di
  // (/api/modelos/simgrupo, mesma conta do Comparar). Resultado guardado no aparelho e pedido de novo só 1x por dia.
  const SKEY = 'screenerB3.simgrupo.v17';  // v17: 1º dia com ordens com preço limite, sem compra na criação; v16: 1º dia a mercado, horário das compras e vendas ao vivo; v15: aporte primeiro na carteira, Buy and Hold novo, confiança nas notícias; v14: saldo do CDB antes de cada movimentação; v13: CDB dia a dia com IR/IOF, preço atual; v12: grupo do mês atual anda até hoje; v11: ordens com fila, nada antes da data inicial, histórico por data; v10: alvos caros (Value, Barsi) e prejuízo só com empresa ruim; v9: ordens com preço limite ligadas + anti-emoção; v8: modelo Adaptativo; v7: nomes das empresas (nm); v6: caixa máximo do Barsi; v5: ações de cada balanço; v4: modelos de método; v3: preço médio, todas as posições, 50 movimentações (o resto em páginas) — o resultado antigo não vale
  try { for (let v = 1; v < +SKEY.split('.v').pop(); v++) localStorage.removeItem('screenerB3.simgrupo.v' + v); } catch (e) { }  // versões antigas
  // simRetry: depois de uma falha, só tenta de novo após SIM_RETRY (sem isso a tela pedia de novo a cada desenho, sem parar)
  const SIM = (() => { try { return JSON.parse(localStorage.getItem(SKEY) || '{}') || {}; } catch (e) { return {}; } })(), simLoad = new Set(), simRetry = {}, SIM_RETRY = 10 * 60e3;
  const simK = (g) => JSON.stringify([g.sim.di, g.sim.v0, g.sim.ap || 0, g.sim.ex || [], g.sim.ret || []]), today = hojeSP;
  const saveSim = () => { for (const k in SIM) if (!groups.some(g => g.sim && g.name === k)) delete SIM[k]; try { localStorage.setItem(SKEY, JSON.stringify(SIM)); } catch (e) { } };
  function simData(g) {
    const c = SIM[g.name], ok = c && c.k === simK(g);
    if ((!ok || c.day !== today()) && !simLoad.has(g.name) && !(Date.now() < (simRetry[g.name + simK(g)] || 0))) {
      simLoad.add(g.name);
      (async () => {
        let d = null;
        for (let i = 0; i < 6; i++) { try { const r = await fetch('/api/modelos/simgrupo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(g.sim) }); d = await r.json(); if (r.status !== 202) break; } catch (e) { d = { error: 'Sem conexão.' }; break; } await new Promise(z => setTimeout(z, 5000)); }
        simLoad.delete(g.name);
        let mud = true;
        if (d && !d.error && d.m) { delete simRetry[g.name + simK(g)]; SIM[g.name] = { k: simK(g), day: today(), d }; saveSim(); simKeep(g, d.p1, null, d.r1); }
        else {
          simRetry[g.name + simK(g)] = Date.now() + SIM_RETRY;
          const err = (d && d.error) || 'Não foi possível simular agora.', o = SIM[g.name];
          if (o && o.d && o.k === simK(g)) mud = false;  // falhou, mas há o resultado de outro dia: continua mostrando ele
          else if (o && !o.d && o.k === simK(g) && o.err === err) mud = false;
          else SIM[g.name] = { k: simK(g), day: d && d.pend ? today() : '', err };  // começo depois dos dados: tenta de novo no dia seguinte
        }
        if (mud) window.gruposRefresh && gruposRefresh();
      })();
    }
    return ok ? c : null;
  }
  // guardado no grupo (grupos.v1 → sim): cr = hora da criação no próprio dia de início, no pregão (1º dia com ordens a partir do preço
  // dessa hora); r1 = preço de referência de cada ação na criação ({ticker: [preço, mínima do dia, 'HH:MM']}); p1 = ordens do 1º dia que
  // tocaram o limite ao vivo ({ticker: [preço, 'HH:MM', 'AAAA-MM-DD']}); voltam ao servidor (server._sim_hoje, modelos._dia0);
  // hr = horário das compras e vendas vistas ao vivo ({'modelo|ticker|compra|AAAA-MM-DD': ['HH:MM', preço, ações]}; server._simw → prov)
  function simKeep(g, p1, prov, r1) {
    let mud = false; const hoje = today(), lim = new Date(Date.now() - 40 * 864e5).toISOString().slice(0, 10);
    if (g.sim.p1) for (const t in g.sim.p1) if (!Array.isArray(g.sim.p1[t]) || g.sim.p1[t].length < 3) {  // formato antigo (compra a mercado na criação): sai com os horários dela
      delete g.sim.p1[t]; mud = true; if (g.sim.hr) for (const k in g.sim.hr) if (k.split('|')[3] === g.sim.di) delete g.sim.hr[k];
    }
    for (const [k, o] of [['p1', p1], ['r1', r1]]) if (o) { g.sim[k] = g.sim[k] || {}; for (const t in o) if (!g.sim[k][t]) { g.sim[k][t] = o[t]; mud = true; } }
    for (const [m, L] of prov || []) for (const e of L || []) {
      const k = `${m}|${e.t}|${e.k}|${e.d}`; g.sim.hr = g.sim.hr || {};
      if (e.h && e.d === hoje && !g.sim.hr[k]) { g.sim.hr[k] = [e.h, e.p, e.q]; mud = true; }
    }
    if (g.sim.hr) for (const k in g.sim.hr) if (k.split('|')[3] < lim) { delete g.sim.hr[k]; mud = true; }
    if (mud) save();
  }
  const simF = (g) => { const s = g.sim; return { ap: s.ap || 0, ex: s.ex || [], ret: s.ret || [], ...(s.p1 ? { p1: s.p1 } : {}), ...(s.r1 ? { r1: s.r1 } : {}), ...(s.cr ? { cr: s.cr } : {}) }; };  // f do widget e do ao vivo
  const modN = (m) => m.n;
  // ao vivo: valor de cada modelo com o preço de agora e a variação do dia (o mesmo /api/widget/simgrupo do widget: server._simw);
  // pede de novo a cada 2 min com a aba aberta (as decisões continuam as da simulação)
  const LIVE = {};
  function simLive(g) {
    for (const n in LIVE) if (!groups.some(x => x.sim && x.name === n)) delete LIVE[n];  // grupo apagado: sai da memória
    const L = LIVE[g.name], k = simK(g);
    if (!L || L.k !== k || (Date.now() - L.at > 120000 && !L.busy)) {
      LIVE[g.name] = Object.assign(L && L.k === k ? L : { k, m: null }, { busy: true, at: Date.now() });
      const q = new URLSearchParams({ di: g.sim.di, v0: g.sim.v0, f: JSON.stringify(simF(g)) });
      fetch('/api/widget/simgrupo?' + q).then(r => r.ok ? r.json() : null).then(w => {
        const o = LIVE[g.name]; if (!o || o.k !== k) return; o.busy = false;
        if (w && w.r) { o.m = Object.fromEntries(w.r.map(x => [x.m, x])); o.u = w.u; o.nota = w.nota; simKeep(g, w.p1, w.r.map(x => [x.m, x.prov]), w.r1); window.gruposRefresh && gruposRefresh(); }
      }).catch(() => { const o = LIVE[g.name]; if (o) o.busy = false; });
    }
    return L && L.k === k ? L.m : null;
  }
  window.gSimLive = (gn, mid) => { const L = LIVE[gn]; return L && L.m ? L.m[mid] : null; };
  // resultado do grupo com Hoje/Dia ao vivo (preço de agora) — o mesmo do quadro e do chat (gSim.resumo)
  function simView(c, g) {
    const lv = simLive(g) || {}, apT = c.d.apT != null ? c.d.apT : c.d.v0;
    return [Object.assign({}, c.d, { m: c.d.m.map(x => lv[x.m] ? Object.assign({}, x, { v: lv[x.m].v, pct: apT > 0 ? (lv[x.m].v / apT - 1) * 100 : null, dp: lv[x.m].dp }) : x) }), lv];
  }
  function simBody(g, full) {
    const c = simData(g);
    if (!c) return loaderHTML('Simulando os modelos…');
    if (!c.d) return `<p class="gt-empty">${esc(c.err || '')}</p>`;
    const [d, lv] = simView(c, g);
    const L = full ? d.m : d.m.filter(x => !x.ref);
    const apx = d.apT != null && d.apT !== d.v0 ? ` · aportado até hoje ${brl.format(d.apT)}` : '';
    return `<p class="gt-help">Desde ${dataBR(d.d0)} · ${brl.format(d.v0)}${d.ap > 0 ? ` + ${brl.format(d.ap)}/mês` : ''} em cada modelo${apx} · ${d.n} empresas${full ? ` · dados até ${dataBR(d.d1)}` : ''}</p>
      <table class="gtab gsim"><thead><tr><th>Modelo</th><th>Rendimento</th><th>Hoje</th><th>Dia</th></tr></thead><tbody>${L.map(x => `<tr class="${x.ref ? '' : 'tap'}"${x.ref ? '' : ` data-simm="${esc(g.name)}|${x.m}"`}><td style="white-space:normal">${esc(modN(x))}${x.ref ? '' : `<span class="gsub">${x.np} empresa(s)</span>`}</td>
      <td class="${x.pct == null ? '' : x.pct < 0 ? 'neg' : 'pos'}">${x.pct == null ? '—' : pc(x.pct)}</td><td>${x.v == null ? '—' : brl.format(x.v)}</td><td class="${x.dp == null ? '' : x.dp < 0 ? 'neg' : 'pos'}">${x.dp == null ? '—' : pc(x.dp)}</td></tr>`).join('')}</tbody></table>
      ${c.d.nota || (LIVE[g.name] || {}).nota ? `<p class="gt-help">${esc(c.d.nota || LIVE[g.name].nota)}</p>` : ''}${Object.keys(lv).length ? `<p class="gt-help">Hoje e Dia: preço de agora (${esc((LIVE[g.name] || {}).u || '')}); as compras e vendas são as da simulação, até ${dataBR(c.d.d1)}.</p>` : ''}`;
  }
  window.gSim = {
    has: (n) => groups.some(g => g.name === n),
    // chat → Previsão e modelos → Meu Grupo simulação: cada grupo com os modelos do maior para o menor rendimento
    resumo: () => groups.filter(g => g.sim).map(g => { const c = SIM[g.name]; if (!c || !c.d) return { n: g.name, err: (c && c.err) || 'Abra a aba Grupos para simular.' };
      const [d] = simView(c, g); return { n: g.name, d0: d.d0, L: d.m.map(x => ({ n: modN(x), pct: x.pct, v: x.v, ref: x.ref })).sort((a, b) => (b.pct ?? -1e9) - (a.pct ?? -1e9)) }; }),
    next: (n) => { let i = 2; while (groups.some(g => g.name === `${n} ${i}`)) i++; return `${n} ${i}`; },
    create: (name, sim) => {
      // criado no próprio dia de início, num dia útil, antes do fim do pregão (18:30): o 1º dia começa a partir do preço da hora da criação (cr)
      const n = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' })), hm = String(n.getHours()).padStart(2, '0') + ':' + String(n.getMinutes()).padStart(2, '0');
      const cr = sim.di === today() && n.getDay() >= 1 && n.getDay() <= 5 && hm <= '18:30' ? hm : null;
      groups = groups.filter(g => g.name !== name); delete SIM[name]; groups.push({ name, tickers: [], sim: { di: sim.di, v0: sim.v0, ap: sim.ap || 0, ex: sim.ex || [], ret: sim.ret || [], ...(cr ? { cr } : {}) }, updated: new Date().toISOString() }); groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save(); saveSim(); },
  };
  let editing = null, viewing = null;

  const VKEY = 'screenerB3.ordsetor.v1';
  try { const v = JSON.parse(localStorage.getItem(VKEY) || '{}'); state.ord2 = v.ord2 || ''; state.sector = v.sector || 'Todos'; } catch (e) { state.ord2 = ''; state.sector = 'Todos'; }
  state.ord2 = '';
  $g('#gSec').innerHTML = ['Todos'].concat(SECTORS).map(x => `<option${x === state.sector ? ' selected' : ''}>${esc(x)}</option>`).join('');
  document.addEventListener('change', (e) => {
    if (e.target.id !== 'gSec') return;
    state.sector = e.target.value;
    try { localStorage.setItem(VKEY, JSON.stringify({ ord2: state.ord2, sector: state.sector })); } catch (er) { }
    if (state.data) apply();
  });
  document.addEventListener('input', (e) => {
    if (e.target.id !== 'gQ') return;
    $g('#q').value = e.target.value; if (state.data) apply();
  });
  function bar() {
    const b = $g('#gBar');
    if (state.selMode) {
      b.innerHTML = `<div class="gbar mb-2"><b class="text-emerald-300 text-sm">${state.selSet.size} selecionada(s)</b>
        <input id="gName" maxlength="40" placeholder="Nome do grupo" value="${esc(editing ? editing.name : '')}" class="flex-1 min-w-[140px] px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm">
        <button type="button" class="gbtn pri" data-g="save">Salvar</button><button type="button" class="gbtn" data-g="cancel">Cancelar</button>
        <input id="gQ" type="search" placeholder="Buscar empresa, setor ou atividade (ex.: gasol)…" value="${esc($g('#q').value)}" class="basis-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm"></div>`;
    } else if (viewing) {
      b.innerHTML = `<div class="gbar mb-2"><b class="text-emerald-300">${esc(viewing.name)}</b><span class="text-xs text-slate-400">${viewing.tickers.length} empresa(s)${viewing.rank ? ' · ordem do ranking' : ''}</span>
        ${viewing.pre ? '' : `<button type="button" class="gbtn ml-auto" data-g="edit" data-n="${esc(viewing.name)}">Editar</button>`}
        <button type="button" class="gx ${viewing.pre ? 'ml-auto' : ''}" data-g="back" aria-label="Fechar grupo">✕</button></div>`;
    } else b.innerHTML = '';
  }
  function refresh() { bar(); if (typeof apply === 'function' && state.data) apply(); }
  function startSel(g) {
    editing = g || null; state.selMode = true; state.selSet = new Set(g ? g.tickers : []);
    viewing = null; state.group = null; markTab(); showTab('acoes'); refresh();
  }
  function stopSel() { state.selMode = false; editing = null; state.selSet = new Set(); refresh(); }
  function openGroup(g) { viewing = g; state.group = new Set(g.tickers); state.groupRank = g.rank ? new Map(g.tickers.map((t, i) => [t, i])) : null; state.selMode = false; showTab('acoes'); markTab(); refresh(); window.scrollTo(0, 0); }
  function markTab() { document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('on', viewing ? b.dataset.tab === 'grupos' : b.dataset.tab === 'acoes')); }

  document.addEventListener('change', (e) => {
    const c = e.target.closest('[data-gsel]'); if (!c) return;
    if (c.checked) state.selSet.add(c.dataset.gsel); else state.selSet.delete(c.dataset.gsel);
    const b = $g('#gBar b'); if (b) b.textContent = state.selSet.size + ' selecionada(s)';
  });
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-g]'); if (!b) return;
    const a = b.dataset.g, find = (n) => groups.find(g => g.name === n);
    if (a === 'new') startSel(null);
    else if (a === 'cancel') stopSel();
    else if (a === 'save') {
      const name = ($g('#gName').value || '').trim();
      if (!name) { uiAlert('Dê um nome ao grupo.'); $g('#gName').focus(); return; }
      if (!state.selSet.size) { uiAlert('Selecione pelo menos uma empresa.'); return; }
      const other = find(name);
      if (other && other !== editing && !(await uiConfirm(`Já existe um grupo "${name}". Substituir?`, { ok: 'Substituir', danger: true }))) return;
      groups = groups.filter(g => g !== other && g !== editing);
      groups.push({ name, tickers: [...state.selSet].sort(), updated: new Date().toISOString() });
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save();
      state.selMode = false; editing = null; state.selSet = new Set(); bar(); showTab('grupos');
    }
    else if (a === 'back') { viewing = null; state.group = null; state.groupRank = null; refresh(); showTab('grupos'); }
    else if (a === 'open') openGroup(find(b.dataset.n));
    else if (a === 'edit') startSel(find(b.dataset.n));
    else if (a === 'del') { const g = find(b.dataset.n); if (g && await uiConfirm(`Excluir o grupo "${g.name}"?`, { ok: 'Excluir', danger: true })) { groups = groups.filter(x => x !== g); save(); saveSim(); list(); } }
    else if (a === 'export') exportG();
    else if (a === 'import') $g('#gFile').click();
  });

  // ---------- Grupos pré-definidos (TOP 10, recalculados com os dados atuais) ----------
  let METRICS = null;
  const loadMetrics = async () => { if (METRICS) return METRICS; try { METRICS = (await (await fetch('/api/metrics')).json()).metrics || {}; } catch (e) { METRICS = {}; } return METRICS; };
  const rowsAll = () => state.data ? state.data.rows : [];
  // grupos pré-definidos: só empresas com negociação média ≥ R$ 500 mil/dia (evita distorções de papéis sem liquidez)
  const rows1 = () => state.data ? (state.data.rowsK || state.data.rows) : []; // grupos prontos: 1 ticker por empresa
  const rowsK = () => state.country === 'br' ? rows1().filter(r => (r.v.vol30 || 0) >= 5e5) : rowsAll();
  const MX = (t) => (METRICS || {})[t] || {};
  const pctRank = (arr, key, asc) => { const s = arr.slice().sort((a, b) => asc ? key(a) - key(b) : key(b) - key(a)); const m = new Map(); s.forEach((r, i) => m.set(r, 1 - i / Math.max(1, s.length - 1))); return m; };
  // data de listagem: uma fonte por país, igual para todas as empresas — Brasil: 1º pregão na B3 (COTAHIST); exterior: IPO (TradingView)
  const listDate = (r) => (state.country === 'br' ? MX(r.ticker).ftd : r.ipo) || null;
  window.isNova = (r) => { const d = listDate(r); return !!d && (Date.now() - Date.parse(d)) < 92 * 864e5; };
  window.gTop10 = () => PRE.filter(p => preOk(p) && !p.fav).map(p => { let L = []; try { L = (p.calc(p.per ? 1 : undefined) || []).slice(0, 10); } catch (e) { } return `${p.name}${p.h ? ' [' + p.h + ']' : ''}: ` + L.map(x => Array.isArray(x) ? x[0].ticker + ' ' + (x[1] ?? '') : x.ticker).join('; '); }).join('\n');
  const PRE = [
    { id: 'valor', m: 1, name: 'Maior valorização', h: 'Valorização', per: true, calc: (n) => rowsK().filter(r => MX(r.ticker)['ret' + n] != null).map(r => [r, MX(r.ticker)['ret' + n]]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, pc(v), v]) },
    { id: 'rent', name: 'Maior rentabilidade', t: 'últimos 12 meses', h: 'Lucro/valor', calc: () => rowsK().filter(r => r.v.pl >= 2).map(r => [r, 100 / r.v.pl]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'dy', m: 1, name: 'Maiores pagadoras de dividendos', h: 'DY a.a.', per: true, calc: (n) => rowsK().map(r => [r, MX(r.ticker)['dy' + n] ?? (n === 1 ? r.v.dy : null)]).filter(x => x[1] > 0 && x[1] < 40).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'prov', m: 1, name: 'Mais proventos ao investidor', t: '12 meses', h: 'Proventos', calc: () => rowsK().map(r => [r, MX(r.ticker).prov12]).filter(x => x[1] > 0 && x[1] < 60).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%', v]) },
    { id: 'peq', m: 1, name: 'Pequenas e médias promissoras', t: 'últimos 12 meses', h: 'Nota', calc: () => {
      const c = rows1().filter(r => { const v = r.v; const liq = v.vol30; return v.valmerc >= 3e8 && v.valmerc <= 1e10 && v.lpa > 0 && v.roe >= 12 && (v.cresc5a > 0 || v.lucro5a > 0) && (v.dlebit == null || v.dlebit < 3) && liq >= 1e6; });
      const a = pctRank(c, r => r.v.roe), b = pctRank(c, r => r.v.lucro5a ?? -1e9), d = pctRank(c, r => r.v.pl > 0 ? 1 / r.v.pl : 0);
      return c.map(r => [r, (a.get(r) + b.get(r) + d.get(r)) / 3 * 100]).sort((x, y) => y[1] - x[1]).map(([r, v]) => [r, F2.format(v), v]); } },
    { id: 'magic', name: 'Magic Formula', t: 'últimos 12 meses', h: 'ROIC · EV/EBIT', calc: () => {
      const c = rowsK().filter(r => !r.fin && r.v.evebit >= 1 && r.v.roic != null && r.v.roic < 150);
      const r1 = new Map(c.slice().sort((a, b) => b.v.roic - a.v.roic).map((r, i) => [r, i])), r2 = new Map(c.slice().sort((a, b) => a.v.evebit - b.v.evebit).map((r, i) => [r, i]));
      return c.map(r => [r, r1.get(r) + r2.get(r)]).sort((a, b) => a[1] - b[1]).map(([r]) => [r, F2.format(r.v.roic) + '% · ' + F2.format(r.v.evebit)]); } },
    { id: 'graham', name: 'Baratas pelo Graham', t: 'valor justo do card', h: 'Desconto', calc: () => rowsK().map(r => [r, fairOf(r)]).filter(([, f]) => !f.why && f.pct > 0).sort((a, b) => b[1].pct - a[1].pct).map(([r, f]) => [r, F2.format(f.pct) + '%' + (f.m !== 'Graham' ? ' · ' + f.m : ''), f.pct]) },
    { id: 'consist', m: 1, name: 'Pagadoras consistentes', t: 'últimos 5 anos', h: 'DY médio · CV', calc: () => rowsK().map(r => { const an = Object.values(MX(r.ticker).anual || {}); if (an.length < 5 || an.some(x => !(x > 0))) return null; const m = an.reduce((a, b) => a + b, 0) / an.length, sd = Math.sqrt(an.reduce((a, b) => a + (b - m) ** 2, 0) / an.length); return [r, sd / m, m]; }).filter(Boolean).sort((a, b) => a[1] - b[1] || b[2] - a[2]).map(([r, cv, m]) => [r, F2.format(m) + '% · ' + F2.format(cv)]) },
    { id: 'divida', name: 'Menos endividadas', t: 'últimos 12 meses', h: 'Dív.Líq/PL', calc: () => rowsK().filter(r => r.v.lpa > 0 && r.v.dlpl != null).map(r => [r, r.v.dlpl]).sort((a, b) => a[1] - b[1]).map(([r, v]) => [r, F2.format(v)]) },
    { id: 'quedas', m: 1, name: 'Maiores quedas', h: 'Variação', per: true, calc: (n) => rowsK().filter(r => MX(r.ticker)['ret' + n] != null).map(r => [r, MX(r.ticker)['ret' + n]]).filter(x => x[1] < 0).sort((a, b) => a[1] - b[1]).map(([r, v]) => [r, pc(v), v]) },
    { id: 'negoc', name: 'Mais negociadas', t: '1 mês', h: 'Giro/dia', calc: () => rowsK().filter(r => r.v.valmerc > 0 && r.v.vol30 > 0).map(r => [r, r.v.vol30 / r.v.valmerc * 100]).sort((a, b) => b[1] - a[1]).map(([r, v]) => [r, F2.format(v) + '%']) },
    { id: 'novas', name: 'Novidades', t: 'listagens recentes', h: 'Listagem', calc: () => rows1().filter(r => listDate(r)).sort((a, b) => listDate(b).localeCompare(listDate(a))).map(r => [r, dataBR(listDate(r))]) },
  ];
  const preOk = (p) => state.country === 'br' || !p.m;
  const UKEY = 'screenerB3.gruposUI.v1';
  const ui = (() => { try { return JSON.parse(localStorage.getItem(UKEY) || '{}') || {}; } catch (e) { return {}; } })();
  ui.per = ui.per || {}; ui.order = ui.order || []; ui.gstar = ui.gstar || []; ui.fav = ui.fav || { tab: 'all', sort: 'ordem' }; ui.fav.avg = ui.fav.avg || 9;
  if (!ui.fav.ov) { ui.fav.ov = 1; if (ui.fav.sort === 'preco') ui.fav.sort = 'ordem'; }  // Minha ordem (⋮⋮) passou a ser o padrão
  // abas criadas pelo usuário nos Favoritos foram removidas: apaga as que ficaram salvas no aparelho
  if (ui.fav.tabs || ui.fav.assign) { delete ui.fav.tabs; delete ui.fav.assign; if (ui.fav.tab !== 'prov') ui.fav.tab = 'all'; try { localStorage.setItem(UKEY, JSON.stringify(ui)); } catch (e) { } }
  const saveUI = () => { try { localStorage.setItem(UKEY, JSON.stringify(ui)); } catch (e) { } };
  // quadros da aba Grupos (Favoritos e grupos; Fluxo da bolsa não): arrastar a alça do fim aumenta ou diminui a altura, guardada no
  // aparelho por quadro (ui.gh[id]); dois toques volta ao padrão
  if (!ui.gh) { ui.gh = {}; if (ui.favH) { ui.gh.fav = ui.favH; delete ui.favH; } saveUI(); }
  const ghStyle = (id) => ui.gh[id] ? ` style="height:${ui.gh[id]}px;max-height:none"` : '';
  const gripHtml = (n) => `<div class="gt-grip" data-ggrip role="separator" aria-orientation="horizontal" aria-label="Arraste para aumentar ou diminuir ${esc(n)}" title="Arraste para aumentar ou diminuir"></div>`;
  document.addEventListener('pointerdown', (e) => {
    const g = e.target.closest('[data-ggrip]'); if (!g) return;
    const box = g.closest('.gt'), id = box.dataset.id, y0 = e.clientY, h0 = box.getBoundingClientRect().height;
    e.preventDefault(); g.setPointerCapture(e.pointerId); g.classList.add('on');
    const mv = (ev) => { const h = Math.round(Math.min(window.innerHeight * .9, Math.max(140, h0 + ev.clientY - y0))); box.style.height = h + 'px'; box.style.maxHeight = 'none'; ui.gh[id] = h; };
    const up = () => { g.removeEventListener('pointermove', mv); g.removeEventListener('pointerup', up); g.removeEventListener('pointercancel', up); g.classList.remove('on'); saveUI(); };
    g.addEventListener('pointermove', mv); g.addEventListener('pointerup', up); g.addEventListener('pointercancel', up);
  });
  document.addEventListener('dblclick', (e) => { const g = e.target.closest('[data-ggrip]'); if (!g) return; const b = g.closest('.gt'); delete ui.gh[b.dataset.id]; saveUI(); b.style.height = ''; b.style.maxHeight = ''; });
  let favReord = false, favSort = null, favTmp = null, favDrag = 0;  // ⋮⋮ ligado: linhas com alça; favTmp = ordem arrastada (guardada ao desligar)
  const favList = () => { const L = rowsAll().filter(r => FAVS.has(r.ticker)), rk = favTmp ? new Map(favTmp.map((t, i) => [t, i])) : null;
    return L.sort((a, b) => rk ? (rk.get(a.ticker) ?? 1e9) - (rk.get(b.ticker) ?? 1e9) : favRank(a.ticker) - favRank(b.ticker)); };  // ordem dos Favoritos (⋮⋮)
  // Preço médio: média dos fechamentos DIÁRIOS dos últimos n meses (histórico diário atualizado do servidor)
  const DAILY = {}, pend = new Set(); let rt = null;
  const avgP = (r, n) => {
    const t = r.ticker, h = DAILY[t];
    if (h) return avgLastMonths(h.t, h.c, n);
    if (!pend.has(t)) { pend.add(t); fetch(`/api/history/${encodeURIComponent(t)}?kind=d`).then(x => x.ok ? x.json() : null).then(d => { if (d && d.t) DAILY[t] = d; clearTimeout(rt); rt = setTimeout(() => window.gruposRefresh && gruposRefresh(), 300); }).catch(() => { }); }
    return MX(t)['avg' + n] ?? null;
  };
  // ---------- Alertas de preço (Favoritos) ----------
  // Avisa uma vez quando o preço passa do limite (com o app aberto ou em segundo plano: os dados recarregam a cada 10 min);
  // volta a armar quando o preço retorna ao intervalo. Ao abrir o app, avisa de novo o que ainda está fora do intervalo.
  const AKEY = 'screenerB3.alertas.v1';
  const ALR = (() => { try { return JSON.parse(localStorage.getItem(AKEY) || '{}') || {}; } catch (e) { return {}; } })();
  const saveAlr = () => { try { localStorage.setItem(AKEY, JSON.stringify(ALR)); } catch (e) { } };
  const alrSide = (r) => { const a = ALR[r.ticker], p = r.v.preco; if (!a || p == null) return null; return a.lo != null && p <= a.lo ? 'lo' : a.hi != null && p >= a.hi ? 'hi' : null; };
  const alrPast = (r) => !!alrSide(r);
  let alrFirst = true;
  function notify(msg) {
    uiToast(msg);
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    const o = { body: msg, icon: '/static/icons/icon-192.png', tag: 'alerta-' + msg.split(' ')[0] };
    if (navigator.serviceWorker && navigator.serviceWorker.controller) navigator.serviceWorker.ready.then(r => r.showNotification('Alerta de preço', o)).catch(() => { });
    else try { new Notification('Alerta de preço', o); } catch (e) { }
  }
  function alrCheck() {
    if (!state.data) return;
    let ch = false;
    for (const t in ALR) {
      const r = state.rowMap[t], a = ALR[t]; if (!r) continue;
      const sd = alrSide(r);
      if (sd && (alrFirst || a.fired !== sd)) notify(`${t} ${sd === 'lo' ? 'abaixo' : 'acima'} de R$ ${F2.format(a[sd])}: R$ ${F2.format(r.v.preco)}`);
      if ((a.fired || null) !== sd) { if (sd) a.fired = sd; else delete a.fired; ch = true; }
    }
    alrFirst = false; if (ch) saveAlr();
  }
  function alrSet(key, txt) {
    const [t, k] = key.split(':'), v = String(txt).trim() ? parseBR(txt) : null;
    ALR[t] = ALR[t] || {};
    if (v > 0) ALR[t][k] = v; else delete ALR[t][k];
    delete ALR[t].fired;
    if (ALR[t].lo == null && ALR[t].hi == null) delete ALR[t];
    saveAlr();
    if (v > 0 && 'Notification' in window && Notification.permission === 'default') Notification.requestPermission().catch(() => { });
    const r = state.rowMap[t]; if (r) { const s = alrSide(r); if (s && ALR[t]) { ALR[t].fired = s; saveAlr(); notify(`${t} já está ${s === 'lo' ? 'abaixo' : 'acima'} de R$ ${F2.format(ALR[t][s])}: R$ ${F2.format(r.v.preco)}`); } }
    // só a linha muda (redesenhar o card durante o change perderia o foco do campo)
    $g('#gruposRoot').querySelectorAll(`tr[data-row="${CSS.escape(t)}"]`).forEach(tr => tr.classList.toggle('galr-on', !!(r && alrPast(r))));
    $g('#gruposRoot').querySelectorAll(`[data-alr="${CSS.escape(key)}"]`).forEach(i => { i.value = v > 0 ? F2.format(v) : ''; });
  }
  document.addEventListener('dataload', alrCheck);
  if (state.data) alrCheck();
  function favRows() {
    const f = ui.fav, s = favReord ? 'ordem' : (f.sort || 'ordem');
    const L = favList();
    const key = (r) => s === 'preco' ? (r.v.preco ?? -1e9) : (MX(r.ticker)['ret' + s.slice(1)] ?? -1e9);
    return (s === 'ordem' ? L : L.sort((a, b) => key(b) - key(a))).map(r => { const a = avgP(r, f.avg); return [r, a != null ? F2.format(a) : '—']; });
  }
  function tileIds() {
    const ids = ['fav'].concat(PRE.filter(preOk).map(p => 'pre:' + p.id), state.country === 'br' ? groups.map(g => 'user:' + g.name) : []);
    const ord = ui.order.filter(x => ids.includes(x) && x !== 'fav');
    const rest = ord.concat(ids.filter(x => x !== 'fav' && !ord.includes(x)));
    return ['fav'].concat(rest.filter(x => ui.gstar.includes(x)), rest.filter(x => !ui.gstar.includes(x)));
  }
  const priceCell = (r) => { const v = r.var; return `<td class="gc3">${r.v.preco != null ? F2.format(r.v.preco) : '—'}${v != null ? ` <span class="${v > 0 ? 'up' : v < 0 ? 'dn' : ''}">${v > 0 ? '+' : ''}${F2.format(v)}%</span>` : ''}</td>`; };
  // alr = colunas 🔔 Abaixo de / 🔔 Acima de (só nos Favoritos)
  const alrIn = (t, k) => { const v = (ALR[t] || {})[k]; return `<td class="galr"><input class="pv-in" inputmode="decimal" data-alr="${esc(t)}:${k}" value="${v != null ? F2.format(v) : ''}" aria-label="Avisar ${k === 'lo' ? 'abaixo' : 'acima'} de"></td>`; };
  const tbl = (rows, h, full, alr) => `<table class="gtab"><thead><tr><th>Ativo</th>${alr ? `<th class="galr">${esc(h).replace(' ', '<br>')}</th>` : `<th>${esc(h)}</th>`}${alr ? '<th class="galr galr-h">Abaixo🔔</th><th class="galr galr-h">Acima🔔</th>' : ''}<th>Preço · dia</th></tr></thead><tbody>${rows.map(([r, v]) => `<tr data-row="${esc(r.ticker)}" class="${(full || alr) && !(alr && favReord) ? 'tap' : ''}${alr && alrPast(r) ? ' galr-on' : ''}"><td>${alr && favReord ? '<span class="gdrag" aria-hidden="true">⠿</span>' : ''}<b>${esc(r.ticker)}</b>${isNova(r) ? '<span class="nova">NOVA</span>' : ''}</td><td class="gc2">${esc(v)}</td>${alr ? alrIn(r.ticker, 'lo') + alrIn(r.ticker, 'hi') : ''}${priceCell(r)}</tr>`).join('')}</tbody></table>`;
  const preTitle = (p) => p.name + ' (' + (p.per ? ((ui.per[p.id] || 1) + ' ano' + ((ui.per[p.id] || 1) > 1 ? 's' : '')) : p.t) + ')';
  const perSel = (p) => p.per ? `<select class="gper" data-per="${p.id}" aria-label="Período">${[1, 2, 3, 4, 5].map(k => `<option value="${k}"${k === (ui.per[p.id] || 1) ? ' selected' : ''}>${k} ano${k > 1 ? 's' : ''}</option>`).join('')}</select>` : '';
  function favControls() {
    const f = ui.fav, tabs = [['all', 'Todos'], ['prov', 'Proventos no ano']];
    const two = (l) => { const w = String(l).split(' '); return w.length < 2 ? esc(l) : esc(w[0]) + '<br>' + esc(w.slice(1).join(' ')); };
    const avgL = (n) => `Média ${n} ${n > 1 ? 'meses' : 'mês'}`, sortL = (v) => v === 'ordem' ? 'Minha ordem' : v === 'preco' ? 'Preço da ação' : `Maiores valorizações ${v.slice(1)} ano${+v.slice(1) > 1 ? 's' : ''}`;
    const twoS = (l) => { const m = l.match(/^(.*?) (\d.*)$/); return m ? esc(m[1]) + '<br>' + esc(m[2]) : two(l); };
    return `<div class="gt-tabs gfav-row">${tabs.map(([k, l]) => `<button type="button" class="${f.tab === k ? 'on' : ''}" data-ftab="${k}">${two(l)}</button>`).join('')}
      ${f.tab !== 'prov' ? `<label class="g2sel"><span>${twoS(avgL(f.avg || 1))}</span><select data-favg aria-label="Preço médio">${[1, 2, 3, 6, 9].map(n => `<option value="${n}"${f.avg === n ? ' selected' : ''}>${avgL(n)}</option>`).join('')}</select></label><label class="g2sel"><span>${twoS(sortL(f.sort || 'ordem'))}</span><select data-fsort aria-label="Ordenar favoritos">${['ordem', 'preco', 'v1', 'v2', 'v3', 'v4', 'v5'].map(v => `<option value="${v}"${(f.sort || 'ordem') === v ? ' selected' : ''}>${sortL(v)}</option>`).join('')}</select></label>` : ''}</div>`;
  }
  function provCols(list0, empty) {
      const parse = (s) => { const [d, m, y] = s.split('/'); return (y || '') + m + d; };
      const L = list0.map(r => { const p = r.v.preco || 0; return [r, (MX(r.ticker).ytd || []).filter(e => e[2] !== 'grupamento' && e[2] !== 'desdobramento').sort((a, b) => parse(b[0]).localeCompare(parse(a[0]))), p]; }).filter(x => x[1].length);
      if (!L.length) return `<p class="gt-empty">${empty}</p>`;
      return '<div class="pcols">' + L.map(([r, ev, p]) => `<div class="pcol"><div class="pcol-h">${esc(r.ticker)}</div>${ev.map(e => e[2] === 'bonificação' || e[2] === 'desdobramento' || e[2] === 'grupamento'
        ? `<div class="pcard bon"><span>${e[0].slice(0, 5)}</span><b>${e[2] === 'bonificação' ? 'Bonif. ' + F2.format((e[1] - 1) * 100) + '%' : e[2] + ' ' + F2.format(e[1]) + ':1'}</b></div>`
        : `<div class="pcard"><span>${e[0].slice(0, 5)}${e[3] ? ' · ' + esc(e[3]) : ''}</span><b>R$ ${e[1] < 0.1 ? e[1].toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : F2.format(e[1])}</b><em>${F2.format(p ? e[1] / p * 100 : 0)}%</em></div>`).join('')}</div>`).join('') + '</div>';
  }
  // Sub-abas Todos / Proventos no ano dos grupos de proventos
  const PTAB = ['dy', 'prov'], ptabOf = (p) => p && PTAB.includes(p.id) ? ((ui.ptab || {})[p.id] || 'all') : null;
  const ptabBar = (p) => ptabOf(p) ? `<div class="gt-tabs">${[['all', 'Todos'], ['prov', 'Proventos no ano']].map(([k, l]) => `<button type="button" class="${ptabOf(p) === k ? 'on' : ''}" data-ptab="${p.id}:${k}">${l}</button>`).join('')}</div>` : '';
  // Abas à esquerda e seletor de período à direita na mesma linha
  const ctlRow = (p) => ptabOf(p) ? ptabBar(p).replace(/<\/div>$/, perSel(p) + '</div>') : (p.per ? `<div class="gt-tabs">${perSel(p)}</div>` : '');
  const grpBody = (d, full) => ptabOf(d.p) === 'prov' ? provCols(d.rows.map(x => x[0]), 'Nenhum provento destas empresas neste ano.') : (d.rows.length ? tbl(d.rows, d.h, full) : '<p class="gt-empty">Sem dados suficientes.</p>');
  function favBody(full) {
    const f = ui.fav;
    if (f.tab === 'prov') {
      return provCols(favList(), 'Nenhum provento dos favoritos neste ano.');
    }
    const R = favRows();
    if (!R.length) return '<p class="gt-empty">Toque na ☆ de uma empresa para favoritar.</p>';
    let html = tbl(R, 'Média ' + f.avg + (f.avg > 1 ? ' meses' : ' mês'), full, true);
    return html;
  }
  function groupData(id) {
    if (id === 'fav') return { title: '★ Favoritos', n: favList().length };
    if (id.startsWith('pre:')) { const p = PRE.find(x => 'pre:' + x.id === id); return { title: preTitle(p), p, rows: p.calc(ui.per[p.id] || 1).slice(0, 10), h: p.h }; }
    const gg = groups.find(x => x.name === id.slice(5)); if (!gg) return null;
    if (gg.sim) return { title: gg.name, g: gg, sim: true };
    const byT = new Map(rowsAll().map(r => [r.ticker, r]));
    return { title: gg.name, g: gg, rows: gg.tickers.map(t => byT.get(t)).filter(Boolean).map(r => [r, r.v.valmerc ? 'R$ ' + (r.v.valmerc / 1e9).toFixed(1).replace('.', ',') + ' bi' : '—']), h: 'Valor de mercado' };
  }
  const starB = (id) => id === 'fav' ? '' : `<button type="button" class="gstar${ui.gstar.includes(id) ? ' on' : ''}" data-gstar="${esc(id)}" aria-label="Destacar grupo">${ui.gstar.includes(id) ? '★' : '☆'}</button>`;
  function tileHtml(id) {
    const d = groupData(id); if (!d) return '';
    if (id === 'fav') return `<div class="gt gt-fav${favReord ? ' reord' : ''}" data-id="fav"${ghStyle('fav')}><div class="gt-head" data-open="fav"><span class="gt-name">★ Favoritos</span><button type="button" class="gbtn gford${favReord ? ' on' : ''}" data-favord aria-pressed="${favReord}" aria-label="Reorganizar favoritos" title="Reorganizar favoritos">⋮⋮</button></div>${favControls()}<div class="gt-list">${favBody(false)}</div>${window.updTxt && updTxt() ? `<div class="upd gt-upd">${updTxt()}</div>` : ''}${gripHtml('os Favoritos')}</div>`;
    return `<div class="gt" data-id="${esc(id)}"${ghStyle(id)}><div class="gt-head" data-open="${esc(id)}">${starB(id)}<span class="gt-name">${esc(d.title)}</span></div>
      ${d.p ? ctlRow(d.p) : ''}
      <div class="gt-list">${d.sim ? simBody(d.g, false) : grpBody(d, false)}</div><div class="gt-foot">${d.sim ? `<div class="upd gt-upd">${SIM[d.g.name] && SIM[d.g.name].d ? 'Dados até ' + dataBR(SIM[d.g.name].d.d1) : ''}</div>` : window.updTxt && updTxt() ? `<div class="upd gt-upd">${updTxt()}</div>` : ''}${d.p ? '' : `${d.sim ? '' : `<button type="button" class="gt-act" data-g="edit" data-n="${esc(d.g.name)}">Editar</button>`}<button type="button" class="gt-act dan" data-g="del" data-n="${esc(d.g.name)}">Excluir</button>`}</div>${gripHtml('o quadro')}</div>`;
  }
  // Fluxo da bolsa (B3: participação dos investidores, saldo compras − vendas)
  let FLOW = null, flowLoading = false;
  const FP = [['1d', 1, '1 dia'], ['7d', 5, '7 dias'], ['1m', 21, '1 mês'], ['1a', 252, '1 ano']];
  function flowHtml() {
    if (state.country !== 'br') return '';
    if (!FLOW) { if (!flowLoading) { flowLoading = true; fetch('/api/flow').then(x => x.json()).then(d => { FLOW = d || {}; list(); }).catch(() => { FLOW = {}; }); } return `<div class="gt gt-flow"><div class="gt-head"><span class="gt-name">Fluxo da bolsa</span></div>${loaderHTML('')}</div>`; }
    const days = Object.keys(FLOW.days || {}).sort(); if (!days.length) return '';
    const pk = ui.flowP || '1d', n = (FP.find(x => x[0] === pk) || FP[0])[1], sel = days.slice(-n);
    const cats = ['Investidor Estrangeiro', 'Institucionais', 'Investidores Individuais', 'Instituições Financeiras', 'Outros'];
    const nm = { 'Investidor Estrangeiro': 'Estrangeiros', 'Institucionais': 'Institucionais', 'Investidores Individuais': 'Pessoas físicas', 'Instituições Financeiras': 'Instituições financeiras', 'Outros': 'Outros' };
    const sum = (c) => sel.reduce((a, d) => a + ((FLOW.days[d][c] || [])[2] || 0), 0);
    const bi = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + 'R$ ' + (Math.abs(v) / 1e6).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' bi';
    const fd = (d) => d.split('-').reverse().slice(0, 2).join('/');
    const fx = sel.map(d => (FLOW.days[d]['Investidor Estrangeiro'] || [])[2] || 0), mx = Math.max(1, ...fx.map(Math.abs)), W = 300, H = 64, bw = W / Math.max(fx.length, 1), w0 = Math.max(1, Math.min(6, bw * 0.6));
    const bars = fx.map((v, i) => { const h = Math.abs(v) / mx * (H / 2 - 4); return `<rect x="${(i * bw + (bw - w0) / 2).toFixed(1)}" y="${(v >= 0 ? H / 2 - h : H / 2).toFixed(1)}" width="${w0.toFixed(1)}" height="${Math.max(0.5, h).toFixed(1)}" style="fill:${v >= 0 ? 'var(--c-pos-bd)' : 'rgb(239 68 68)'}"><title>${fd(sel[i])}: ${bi(v)}</title></rect>`; }).join('');
    // 1 dia: sem gráfico (uma barra só ocupava a largura toda)
    const chart = fx.length > 1 ? `<div class="flow-ch"><span class="gt-help">Saldo diário dos estrangeiros</span><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" width="100%" height="${H}"><line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" style="stroke:var(--c-dim)" stroke-width="0.8"/>${bars}</svg>
      <div class="flow-lb"><span>${fd(sel[0])}</span><span>máx. ${bi(mx).replace(/^[+−]/, '±')}</span><span>${fd(sel[sel.length - 1])}</span></div></div>` : '';
    const short = days.length < n ? `<p class="gt-help">Histórico disponível: ${days.length} pregões (desde ${fd(days[0])}).</p>` : '';
    return `<div class="gt gt-flow"><div class="gt-head"><span class="gt-name">Fluxo da bolsa</span></div>
      <div class="gt-tabs">${FP.map(([k, , l]) => `<button type="button" class="${k === pk ? 'on' : ''}" data-flowp="${k}">${l}</button>`).join('')}</div>
      <div class="gt-list"><table class="gtab gflow"><thead><tr><th>Investidor</th><th>Saldo (${sel.length > 1 ? fd(sel[0]) + '–' : ''}${fd(sel[sel.length - 1])})</th></tr></thead><tbody>
      ${cats.map(c => { const v = sum(c); return `<tr><td>${nm[c]}</td><td class="gc2 ${v > 0 ? 'pos' : v < 0 ? 'neg' : ''}">${bi(v)}</td></tr>`; }).join('')}</tbody></table>
      ${chart}${short}${updTxt() ? `<div class="upd gt-upd">${updTxt()}</div>` : ''}</div></div>`;
  }
  let sortable = null, reorg = false, fullId = null, lastY = 0;
  function fullHtml(id) {
    const d = groupData(id); if (!d) { fullId = null; return ''; }
    const body = id === 'fav' ? favControls() + favBody(true) : (d.p ? ctlRow(d.p) : '') + (d.sim ? simBody(d.g, true) : grpBody(d, true));
    return `<section class="gfull"><div class="gfull-head"><b>${esc(d.title)}</b><button type="button" class="gx" data-gclose aria-label="Fechar grupo">✕</button></div>${body}</section>`;
  }
  function openDet(tr) {  // abre o card completo abaixo da linha (um por vez); mesmo código para todos os grupos e Favoritos
    const r = rowsAll().find(x => x.ticker === tr.dataset.row); if (!r) return;
    $g('#gruposRoot').querySelectorAll('tr.gdet').forEach(d => { const p = d.previousElementSibling; if (p) { p.classList.remove('sel'); state.expanded.delete(p.dataset.row); } d.remove(); });
    state.expanded.add(r.ticker); tr.classList.add('sel');
    tr.insertAdjacentHTML('afterend', `<tr class="gdet"><td colspan="9">${blockHtml(r)}</td></tr>`);
  }
  async function list() {
    pushGroups();  // grupos, períodos ou ordem mudaram: o widget do app acompanha
    if (favDrag) { favDrag = 2; return; }  // arrastando um favorito: redesenha ao soltar
    const r = $g('#gruposRoot');
    if (!METRICS) { r.innerHTML = loaderHTML('Carregando grupos…'); await loadMetrics(); }
    if (!state.data) { r.innerHTML = loaderHTML('Carregando dados…'); setTimeout(list, 1500); return; }
    const keep = (() => { const p = r.querySelector('tr.gdet')?.previousElementSibling, t = p && p.closest('[data-id]'); return p ? [t ? t.dataset.id : '', p.dataset.row] : null; })();
    const back = () => { if (!keep) return; const t = keep[0] ? r.querySelector(`[data-id="${CSS.escape(keep[0])}"]`) : r; const tr = t && t.querySelector(`tr.tap[data-row="${CSS.escape(keep[1])}"]`); if (tr) openDet(tr); };  // redesenho (dados novos) mantém o card aberto
    if (fullId) { r.innerHTML = fullHtml(fullId); if (fullId) { back(); return; } }
    r.innerHTML = `<section class="space-y-2">
      <div class="flex flex-wrap items-center gap-2">
        ${state.country === 'br' ? '<button type="button" class="gbtn pri" data-g="new">＋ Criar</button>' : ''}
        <button type="button" class="gbtn" data-g="reorg">⇅ Reorganizar</button>
        ${state.country === 'br' ? `<button type="button" class="gbtn fbtn" data-g="export" title="Exportar grupos" aria-label="Exportar grupos">${fileIc(1)}<span class="max-sm:hidden">Exportar</span></button>
        <button type="button" class="gbtn fbtn" data-g="import" title="Importar grupos" aria-label="Importar grupos">${fileIc(0)}<span class="max-sm:hidden">Importar</span></button>` : ''}
        <input id="gFile" type="file" accept=".json,application/json,text/plain,*/*" class="hidden"></div>
      <div id="gGrid" class="ggrid${reorg ? ' reorg' : ''}">${tileIds().map(id => tileHtml(id) + (id === 'fav' && !reorg ? flowHtml() : '')).join('')}</div></section>`;
    $g('#gFile').addEventListener('change', importG);
    if (sortable) { sortable.destroy(); sortable = null; }
    if (favSort) { favSort.destroy(); favSort = null; }
    const fb = favReord && $g('.gt-fav tbody');
    if (fb && window.Sortable) favSort = Sortable.create(fb, { handle: '.gdrag', animation: 150, forceFallback: true, fallbackTolerance: 3, touchStartThreshold: 3,
      onStart: () => { favDrag = 1; },
      onEnd: () => { favTmp = [...fb.querySelectorAll('tr[data-row]')].map(x => x.dataset.row); const again = favDrag === 2; favDrag = 0; if (again) list(); } });
    back();
    if (reorg && window.Sortable) sortable = Sortable.create($g('#gGrid'), { animation: 150, filter: '.gt-fav', preventOnFilter: false, onMove: (e) => !e.related.classList.contains('gt-fav'),
      onEnd: () => { ui.order = [...$g('#gGrid').children].map(x => x.dataset.id).filter(x => x !== 'fav'); saveUI(); } });
  }
  // Tela de reorganização: só os grupos escolhidos, numerados, ajustados para caber na tela
  async function openReorg(which) {
    const ids = tileIds().filter(x => x !== 'fav' && (which === 'star') === ui.gstar.includes(x));
    if (!ids.length) { uiAlert(which === 'star' ? 'Nenhum grupo favoritado. Toque na ☆ de um grupo.' : 'Não há outros grupos.'); return; }
    const neu = await uiReorder(which === 'star' ? 'Favoritados' : 'Demais grupos', ids.map(id => ({ id, label: groupData(id)?.title || id })));
    if (neu) { ui.order = neu.concat(tileIds().filter(x => x !== 'fav' && !neu.includes(x))); saveUI(); }
    list();
  }
  window.gruposRefresh = () => { if (!$g('[data-tabpane="grupos"]').classList.contains('hidden')) list(); };
  // Card aberto dentro do grupo: tocar no cabeçalho para fechar remove o card inteiro (fica só a linha)
  $g('#gruposRoot').addEventListener('click', (e) => {
    const head = e.target.closest('.gdet .blk-head'); if (!head || e.target.closest('.gsel')) return;
    e.stopPropagation(); const det = head.closest('.gdet'), tr = det.previousElementSibling;
    det.remove(); if (tr) { tr.classList.remove('sel'); state.expanded.delete(tr.dataset.row); }
  }, true);
  $g('#gruposRoot').addEventListener('click', async (e) => {
    const pt = e.target.closest('[data-ptab]');
    if (pt) { e.stopPropagation(); const [gid, k] = pt.dataset.ptab.split(':'); ui.ptab = Object.assign({}, ui.ptab, { [gid]: k }); saveUI(); list(); return; }
    const st = e.target.closest('[data-gstar]');
    if (st) { e.stopPropagation(); const id = st.dataset.gstar; ui.gstar = ui.gstar.includes(id) ? ui.gstar.filter(x => x !== id) : ui.gstar.concat(id); saveUI(); list(); return; }
    if (e.target.closest('[data-gclose]')) { const id = fullId, y = lastY; fullId = null; list(); requestAnimationFrame(() => { window.scrollTo(0, y); const t = document.querySelector(`.gt[data-id="${CSS.escape(id || '')}"]`); if (t) t.classList.add('hl'); }); return; }
    if (e.target.closest('[data-alr]')) return;
    if (favReord && e.target.closest('.gt-fav') && !e.target.closest('[data-favord]')) return;  // reorganizando: toque não abre card nem destaca
    const sm = e.target.closest('[data-simm]');
    if (sm) { const [gn, mid] = sm.dataset.simm.split('|'); simModal(gn, mid); return; }
    const tr = e.target.closest('tr.tap[data-row]');
    if (tr) {
      const nx = tr.nextElementSibling; if (nx && nx.classList.contains('gdet')) { nx.remove(); tr.classList.remove('sel'); return; }
      openDet(tr); return;
    }
    if (e.target.closest('[data-favord]')) {  // ⋮⋮: liga/desliga arrastar; ao desligar guarda a ordem (FAV_KEY)
      if (favReord && favTmp) setFavOrder(favTmp);
      favTmp = null; favReord = !favReord; if (favReord && ui.fav.sort !== 'ordem') { ui.fav.sort = 'ordem'; saveUI(); }
      list(); return;
    }
    const h = e.target.closest('[data-open]');
    if (h && !reorg) { const t = h.closest('.gt'); if (t.classList.contains('hl')) { lastY = window.scrollY; fullId = h.dataset.open; list(); window.scrollTo(0, 0); } else { document.querySelectorAll('.gt.hl').forEach(x => x.classList.remove('hl')); t.classList.add('hl'); } return; }
    const fp = e.target.closest('[data-flowp]'); if (fp) { ui.flowP = fp.dataset.flowp; saveUI(); list(); return; }
    const ft = e.target.closest('[data-ftab]');
    if (ft) { ui.fav.tab = ft.dataset.ftab; saveUI(); list(); return; }
    if (e.target.closest('[data-g="reorg"]')) {
      const w = await uiChoose('Reorganizar quais grupos?', [{ label: '★ Favoritados', value: 'star' }, { label: 'Demais', value: 'rest' }]);
      if (w) openReorg(w); return;
    }
  });
  $g('#gruposRoot').addEventListener('change', (e) => {
    const p = e.target.dataset.per; if (p) { ui.per[p] = +e.target.value; saveUI(); list(); return; }
    if (e.target.closest('.g2sel')) { const o = e.target.selectedOptions[0]; if (o) { const m = o.text.match(/^(.*?) (\d.*)$/); e.target.previousElementSibling.innerHTML = m ? m[1] + '<br>' + m[2] : o.text; } }
    if (e.target.hasAttribute('data-fsort')) { ui.fav.sort = e.target.value; saveUI(); list(); return; }
    if (e.target.hasAttribute('data-favg')) { ui.fav.avg = +e.target.value; saveUI(); list(); return; }
    const al = e.target.dataset.alr; if (al) { alrSet(al, e.target.value); return; }
  });
  document.addEventListener('favs', () => { if (!$g('[data-tabpane="grupos"]').classList.contains('hidden')) list(); });
  function exportG() {
    saveJSON({ app: 'screener-b3', tipo: 'grupos', versao: 1, exportado: new Date().toISOString(), grupos: groups, favoritos: [...FAVS] }, 'grupos-screener');  // favoritos: leva a ★ para outro aparelho ou para o app Android
  }
  async function importG(e) {
    const f = e.target.files[0]; if (!f) return;
    try {
      const d = JSON.parse(await f.text()); const arr = Array.isArray(d) ? d : d.grupos;
      const fv = Array.isArray(d.favoritos) ? [...new Set(d.favoritos.map(t => String(t).toUpperCase().trim()))].filter(t => t && !FAVS.has(t)) : [];
      if (!Array.isArray(arr) && !Array.isArray(d.favoritos)) throw new Error('arquivo sem grupos');
      let n = 0;
      for (const g of arr || []) {
        if (!g || typeof g.name !== 'string' || !Array.isArray(g.tickers)) continue;
        let name = g.name.trim().slice(0, 40); const tk = [...new Set(g.tickers.map(t => String(t).toUpperCase().trim()).filter(Boolean))].sort();
        const sim = g.sim && /^\d{4}-\d{2}$/.test(g.sim.di) && +g.sim.v0 > 0 ? { di: g.sim.di, v0: +g.sim.v0 } : null;  // Grupo simulação
        const ex = groups.find(x => x.name === name);
        if (ex) {
          if (ex.tickers.join() === tk.join() && JSON.stringify(ex.sim || null) === JSON.stringify(sim)) continue;
          if (await uiConfirm(`O grupo "${name}" já existe.`, { ok: 'Substituir', cancel: 'Importar como cópia', danger: true })) groups = groups.filter(x => x !== ex);
          else { let i = 2; while (groups.some(x => x.name === `${name} (${i})`)) i++; name = `${name} (${i})`; }
        }
        groups.push(Object.assign({ name, tickers: sim ? [] : tk, updated: g.updated || new Date().toISOString() }, sim ? { sim } : {})); n++;
      }
      if (fv.length) { fv.forEach(t => FAVS.add(t)); setFavOrder([...FAVS]); }  // favoritos do arquivo entram no fim da sua ordem
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save(); saveSim(); list();
      uiToast(n + ' grupo(s) importado(s)' + (fv.length ? ` e ${fv.length} favorito(s)` : ''));
    } catch (err) { uiAlert('Não foi possível importar: ' + err.message); }
    e.target.value = '';
  }

  // movimentações de um modelo do Grupo simulação (toque na linha do quadro ou "↗ Abrir" no widget Grupo simulação do app)
  // tk (widget 1.16+: toque numa empresa): janela só com essa empresa dentro do modelo (previsao.js → pvSimCompany)
  function simModal(gn, mid, tk) {
    const g = groups.find(y => y.sim && y.name === gn), c = SIM[gn], x = c && c.d && c.d.m.find(y => y.m === mid); if (!x || !g) return false;
    const src = Object.assign({}, g.sim, { m: mid });
    if (tk) { pvSimCompany(src, tk, `${esc((c.d.nm || {})[tk] || tk)} · ${esc(x.n)}`); return true; }
    const lv = window.gSimLive(gn, mid), apT = c.d.apT != null ? c.d.apT : c.d.v0;  // Hoje ao vivo (preço de agora), como no quadro
    // ordens executadas hoje ao vivo (server._simw → prov): entram no topo das movimentações, marcadas como provisórias, com a hora
    const pv = (lv && lv.prov || []).filter(p => !(x.mov || []).some(e => e.k === p.k && e.t === p.t && e.d === p.d));  // 1º dia hoje: já estão em mov
    // horário guardado no aparelho nas compras e vendas que o servidor já não tem (reinício); ordem vista ao vivo que o fechamento não confirmou
    const hr = g.sim.hr || {}, hk = (e) => `${mid}|${e.t}|${e.k}|${e.d}`, mv0 = (x.mov || []).map(e => !e.h && hr[hk(e)] ? Object.assign({}, e, { h: hr[hk(e)][0] }) : e);
    const ini = mv0.length ? mv0[0].d : '', nc = Object.keys(hr).filter(k => { const [m, t, kk, d] = k.split('|'); return m === mid && d <= c.d.d1 && d >= ini && !mv0.some(e => e.t === t && e.k === kk && e.d === d); });
    const avs = nc.map(k => { const [, t, kk, d] = k.split('|'), v = hr[k]; return `${kk === 'compra' ? 'Compra' : 'Venda'} de ${esc((c.d.nm || {})[t] || t)} vista às ${esc(v[0])} de ${dataBR(d)} (${brl.format(v[1] || 0)}) não foi confirmada pelo fechamento oficial da B3.`; });
    // posições com o mesmo preço de agora do Hoje (Preço atual, Valor e Resultado batem com ele); caixa e CDB ao vivo
    const lp = {}; (lv && lv.pos || []).forEach(y => { if (y.q > 0) lp[y.t] = y.v / y.q; });
    const pos = (x.pos || []).map(y => lp[y.t] != null ? Object.assign({}, y, { p: lp[y.t], v: y.q * lp[y.t], pct: y.inv > 0 ? (y.q * lp[y.t] / y.inv - 1) * 100 : y.pct }) : y);
    const xl = lv ? Object.assign({}, x, { v: lv.v, pct: apT > 0 ? (lv.v / apT - 1) * 100 : x.pct, pos, cash: lv.cash != null ? lv.cash : x.cash, cdb: lv.cdb || x.cdb, mov: mv0.concat(pv), nmov: (x.nmov || 0) + pv.length }) : Object.assign({}, x, { mov: mv0 });
    uiAlert('', { title: `${esc(gn)} · ${esc(x.n)}`, html: avs.map(a => `<p class="pvd-note">⚠️ ${a}</p>`).join('') + pvGroupHtml(Object.assign({ sim: true, d0: c.d.d0, d1: c.d.d1, v0: c.d.v0, apT: c.d.apT, ap: c.d.ap, wS: c.d.wS, nm: c.d.nm, cdi: c.d.cdi, src }, xl)) }); return true;
  }
  window.jgOpenSim = function (gn, mid, n, tk) {
    n = n || 0; const g = groups.find(x => x.sim && x.name === gn); if (!g) return;
    if (n === 0) { const b = document.querySelector('[data-tab="grupos"]'); if (b) b.click(); }
    if (simData(g) && simModal(gn, mid, tk)) return;
    if (n < 120) setTimeout(() => window.jgOpenSim(gn, mid, n + 1, tk), 500);  // simulação ainda carregando
  };
  { const q = new URLSearchParams(location.search), sg = q.get('sim'), tk = q.get('tk'); if (sg) { history.replaceState(null, '', location.pathname); setTimeout(() => window.jgOpenSim(sg, q.get('m') || 'hold', 0, tk && /^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(tk) ? tk : null), 300); } }
  // App 1.15+: grupos de simulação (nome, data inicial e valor inicial) para o widget Grupo simulação, que pede /api/widget/simgrupo
  function pushSims() {
    if (!window.JGApp || !window.JGApp.setSims) return;
    // widget até a 1.18 só aceita data AAAA-MM: manda o mês em di e o dia completo em f.d (o servidor usa f.d: server._simw)
    const velho = !window.APP_V || window.verCmp(window.APP_V, '1.19') < 0;
    try { window.JGApp.setSims(JSON.stringify(groups.filter(g => g.sim).map(g => { const di = String(g.sim.di || ''), cd = velho && di.length > 7;
      return { id: g.name, n: g.name, di: cd ? di.slice(0, 7) : di, v0: g.sim.v0, f: Object.assign(simF(g), cd ? { d: di } : {}) }; }))); } catch (e) { }
  }
  // App Android (window.JGApp): manda os grupos da aba Grupos (mesmas ações e ordem dos quadros: groupData) para o seletor do widget
  function pushGroups() {
    pushSims();
    if (!window.JGApp || !window.JGApp.setGroups || state.country !== 'br' || !state.data || !METRICS) return;
    try {
      const out = tileIds().filter(id => id !== 'fav').map(id => { const d = groupData(id); return d && { id, n: d.title, t: (d.rows || []).map(x => x[0].ticker) }; }).filter(x => x && x.t.length);
      window.JGApp.setGroups(JSON.stringify(out));
    } catch (e) { }
  }
  loadMetrics().then(() => { if (state.data && window.apply) apply(); pushGroups(); });
  document.addEventListener('dataload', () => { pushGroups(); if (!document.querySelector('[data-tabpane="grupos"]').classList.contains('hidden')) list(); });
  document.addEventListener('tabshow', (e) => {
    if (e.detail === 'grupos') { list(); if (viewing || state.group) { viewing = null; state.group = null; refresh(); } }
    if (e.detail === 'acoes' && !state.selMode && viewing) { /* abrindo grupo */ }
  });
  document.querySelectorAll('[data-tab="acoes"]').forEach(b => b.addEventListener('click', () => { if (viewing && !state.selMode) { viewing = null; state.group = null; refresh(); } }));
  bar(); list();
})();
