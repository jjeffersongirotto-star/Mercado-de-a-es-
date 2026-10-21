// ---------- Chat (perguntas sobre os dados do site) ----------
(function () {
  const KEY = 'screenerB3.chat.v1', root = document.getElementById('chatRoot');
  if (!root) return;
  let H = (() => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(H.slice(-60))); } catch (e) { } };
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^\s*[*•-]\s+/gm, '• ').replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener" class="text-sky-300 underline">link</a>').replace(/\n/g, '<br>');
  root.innerHTML = `<div class="cht"><div class="cht-h"><span><b>Chat</b><span class="cht-ia" id="chtIA"></span></span><button type="button" class="gbtn" id="chtClr">Limpar</button></div>
    <div class="cht-l" id="chtL"></div><div class="cht-g" id="chtG"></div>
    <form class="cht-f" id="chtF" autocomplete="off"><input id="chtQ" class="pv-in" placeholder="Pergunte sobre as ações do site…" maxlength="500" enterkeyhint="send"><button type="submit" class="gbtn pri" id="chtS">Enviar</button></form></div>`;
  const L = root.querySelector('#chtL');
  const txt = (sel, n) => { const e = document.querySelector(sel); return e ? e.innerText.replace(/[ \t]+/g, ' ').replace(/\n{2,}/g, '\n').slice(0, n) : ''; };
  const ls = (k, n) => { try { return (localStorage.getItem(k) || '').slice(0, n); } catch (e) { return ''; } };
  const favList = () => [...(typeof FAVS !== 'undefined' ? FAVS : [])];
  const cartList = () => {  // ações com posição na Carteira (screenerB3.carteira.v2: compras e vendas)
    const q = {}; try { for (const m of JSON.parse(localStorage.getItem('screenerB3.carteira.v2') || '[]') || []) if (m && m.t) q[m.t] = (q[m.t] || 0) + (m.op === 'v' ? -m.q : +m.q); } catch (e) { }
    return Object.keys(q).filter(t => q[t] > 0);
  };
  function ctxNow() { // dados do app no navegador: etiquetas, confiança, grupos, favoritos, carteira e o que o usuário preencheu
    const rows = (typeof state !== 'undefined' && state.data && state.data.rows) || [];
    let tags = '';
    try { tags = rows.map(r => r.ticker + ':' + (r.tags || []).join('/') + (typeof confTxt === 'function' && r.S ? '|' + confTxt(r) : '')).join(';'); } catch (e) { }
    let groups = ''; try { groups = window.gTop10 ? gTop10() : ''; } catch (e) { }
    return { tags: tags.slice(0, 20000), groups: groups.slice(0, 8000), fav: favList(), cart: cartList(),
      prev: ls('screenerB3.previsao.v1', 3000), prevRes: txt('[data-tabpane="previsao"] .pv-sum, [data-tabpane="previsao"] table', 2500),
      alug: ls('screenerB3.aluguel.v1', 3000), alugRes: txt('#alugRoot table', 2500),
      comp: ls('screenerB3.comparar.v1', 1500), compRes: txt('#compRoot .cmp-cols', 5000) };
  }
  const EX = ['DY do Itaú', 'Maiores DY dos bancos', 'PETR4 vs Ibovespa em 2024', 'Ações com ROE acima de 20 e P/L abaixo de 8', 'O que significam as cores?'];
  const chips = (list, lbl) => list && list.length ? `<div class="cht-s">${lbl ? `<span class="cht-sl">${esc(lbl)}</span>` : ''}${list.map(x => x.nav ? `<button type="button" class="cht-c" data-nav="${esc(x.nav)}">${esc(x.l)}</button>` : `<button type="button" class="cht-c" data-q="${esc(x.q || x)}"${x.topic ? ` data-topic="${esc(x.topic)}"` : ''}>${esc(x.l || x)}</button>`).join('')}</div>` : '';  // x = texto ou {l: rótulo, q: pergunta}
  const draw = () => {
    const last = H.length - 1;
    L.innerHTML = H.length ? H.map((m, i) => `<div class="cht-m ${m.r === 'u' ? 'u' : 'a'}">${m.r === 'u' ? esc(m.t) : md(m.t)}${i === last && m.r === 'a' ? chips(m.sug, m.sugl) : ''}</div>`).join('')
      : `<div class="cht-e">Escolha um assunto abaixo ou pergunte do seu jeito — por nome, apelido ou ticker. Exemplos:${chips(EX.slice(0, 3))}</div>`;
    L.scrollTop = L.scrollHeight;
  };
  draw();
  root.querySelector('#chtClr').onclick = async () => { if (!H.length || (window.uiConfirm ? await uiConfirm('Apagar o histórico do chat?') : true)) { H = []; save(); draw(); } };
  let topic = null, topicL = null;
  L.addEventListener('click', (e) => {  // sugestões clicáveis
    const c = e.target.closest('.cht-c'); if (!c) return;
    if (c.dataset.nav) { learn(c.dataset.nav); return goNav(c.dataset.nav); }  // “Você quis dizer:” abre o menu nesse ponto
    topic = c.dataset.topic || null; topicL = c.textContent;  // "Está falando sobre/de qual:": refaz a mesma pergunta com o tema/obra
    root.querySelector('#chtQ').value = c.dataset.q; root.querySelector('#chtF').requestSubmit();
  });
  root.querySelector('#chtF').onsubmit = async (e) => {
    e.preventDefault(); const inp = root.querySelector('#chtQ'), q = inp.value.trim(); if (!q || root.querySelector('#chtS').disabled) return;
    if (G.need === 'empresa' || G.need === 'empresa2') { const m = matches(q); if (m.length) { inp.value = ''; return pick(m[0].ticker, m[0].ticker); } }  // digitou a empresa e enviou
    const ln = NAV[norm(q)];
    if (!topic && ln && M && M.nos[ln]) { H.push({ r: 'u', t: q }); inp.value = ''; save(); draw(); return goNav(ln); }  // frase que o usuário já ensinou neste aparelho
    const hist = H.slice(-6).map(m => ({ r: m.r, t: m.t }));
    const tp = topic; topic = null;
    const first = !H.some(m => m.r === 'a');  // sem resposta anterior: boneco maior, no meio do chat
    H.push({ r: 'u', t: tp ? 'Sobre: ' + topicL : q }); inp.value = ''; draw();
    L.insertAdjacentHTML('beforeend', `<div class="cht-m a cht-w${first ? ' big' : ''}">${window.loaderHTML ? loaderHTML('Pensando…') : '…'}</div>`); L.scrollTop = L.scrollHeight;
    const slow = setTimeout(() => { const w = L.querySelector('.cht-w span'); if (w) w.textContent = 'A IA está demorando, aguarde…'; }, 10000);
    const btn = root.querySelector('#chtS'); btn.disabled = true;
    try {
      const ac = new AbortController(), to = setTimeout(() => ac.abort(), 150000);
      const r = await fetch('api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q, hist, ctx: ctxNow(), topic: tp }), signal: ac.signal });
      clearTimeout(to); const d = await r.json(); H.push({ r: 'a', t: d.a || 'Sem resposta.', mode: d.mode, sug: d.sug || null, sugl: d.sugl || null, q });
      if (d.mode && d.mode !== 'regras' && d.mode !== 'guia') iaLoad();
    } catch (err) { H.push({ r: 'a', t: 'Não foi possível responder agora. Tente de novo.', mode: '' }); }
    clearTimeout(slow); btn.disabled = false; save(); draw();
  };

  // ---------- Chat guiado (menu de intencoes.json, respostas de /api/chat/guia, sem IA) ----------
  const NKEY = 'screenerB3.chatnav.v1';  // frases que o usuário ensinou: frase normalizada → caminho do menu (só no aparelho)
  const NAV = (() => { try { return JSON.parse(localStorage.getItem(NKEY) || '{}') || {}; } catch (e) { return {}; } })();
  function learn(nid) {  // escolheu um “Você quis dizer:” depois de uma pergunta não entendida: guarda frase → caminho
    const m = H[H.length - 1]; if (!m || m.r !== 'a' || !m.q || nid === 'inicio') return;
    NAV[norm(m.q)] = nid; const k = Object.keys(NAV); if (k.length > 200) delete NAV[k[0]];
    try { localStorage.setItem(NKEY, JSON.stringify(NAV)); } catch (e) { }
  }
  const GP = root.querySelector('#chtG');
  const SL = { empresa: 'e', empresa2: 'e2', ind: 'k', periodo: 'per', setor: 'setor', secao: 'sec' };
  const ASK = { empresa: 'Qual empresa? Digite o nome ou o código.', empresa2: 'Qual a outra empresa? Digite o nome ou o código.', ind: 'Qual indicador?', setor: 'Qual setor?', secao: 'Qual parte do site?' };
  let M = null, G = { nid: 'inicio', a: {}, need: null, lb: [] }, stk = [];
  const node = (nid) => nid === 'inicio' ? M.inicio : M.nos[nid];
  const rowsBR = () => (typeof state !== 'undefined' && state.data && state.country === 'br') ? state.data.rows.filter(r => !r.etf) : [];
  const matches = (q) => { q = norm(q.trim()); if (!q) return []; return rowsBR().filter(r => r.ticker.toLowerCase().startsWith(q) || (r._s || norm(r.ticker + ' ' + r.nome)).includes(q))
    .map(r => [r, searchRank(r, q)]).sort((a, b) => a[1] - b[1]).map(x => x[0]).slice(0, 6); };  // mesma busca da Previsão/Comparar
  function needOf(g) {  // próximo dado que o caminho pede (com o que os nós de cima já pediram)
    const n = node(g.nid), a = g.a;
    for (const p of n.pede || []) {
      if (p === 'escopo') { if (!a.esc) return 'escopo'; if (a.esc === 'empresa' && !(a.e || []).length) return 'empresa'; continue; }
      if (p === 'escopo2') { if (!a.esc2) return 'escopo2'; if (a.esc2 === 'setor' && !a.setor) return 'setor'; continue; }
      if (p === 'empresa' ? !(a.e || []).length : p === 'empresa2' ? !(a.e2 || []).length : a[SL[p]] == null) return p;
    }
    return null;
  }
  const btn = (v, l, k) => `<button type="button" class="cht-c" data-g${k || ''}="${esc(v)}">${esc(l)}</button>`;
  function drawG() {
    if (!M) { GP.innerHTML = ''; return; }
    const n = node(G.nid), need = G.need = needOf(G);
    let p = '', body = '';
    if (need === 'empresa' || need === 'empresa2') {
      const fv = favList().filter(t => rowsBR().some(r => r.ticker === t)).slice(0, 6);
      p = ASK[need]; body = `<div class="cht-s" id="chtGE">${fv.map(t => btn(t, t, 'e')).join('')}</div>`;
    } else if (need === 'escopo' || need === 'escopo2' || need === 'periodo') {
      const o = M[need]; p = o.p; body = `<div class="cht-s">${o.op.map(([v, l]) => btn(v, l, 'v')).join('')}</div>`;
    } else if (need) {
      const L = (M.listas || {})[need] || []; p = ASK[need];
      body = `<div class="cht-s">${L.map(x => Array.isArray(x) ? btn(x[0], x[1], 'v') : btn(x, x, 'v')).join('')}</div>`;
    } else if (n.op) {
      p = (n.p || '').replace('{empresa}', (G.a.e || [])[0] || '').replace('{setor}', G.a.setor || '');
      body = `<div class="cht-s">${n.op.map(o => btn(o, M.nos[o].l, 'o')).join('')}</div>`;
    }
    GP.innerHTML = `<p class="cht-gp">${esc(p)}</p>${body}<div class="cht-gn">${stk.length ? '<button type="button" class="gbtn" data-gnav="back">‹ Voltar</button>' : ''}${G.nid !== 'inicio' || stk.length ? '<button type="button" class="gbtn" data-gnav="home">Início</button>' : ''}</div>`;
    const inp = root.querySelector('#chtQ'); inp.placeholder = need === 'empresa' || need === 'empresa2' ? 'Nome ou código da empresa…' : 'Pergunte sobre as ações do site…';
    if (need === 'empresa' || need === 'empresa2') { showMatches(); if (matchMedia('(pointer: fine)').matches) inp.focus(); }
  }
  function showMatches() {
    const b = GP.querySelector('#chtGE'); if (!b) return;
    const q = root.querySelector('#chtQ').value;
    const L = q.trim() ? matches(q) : rowsBR().filter(r => favList().includes(r.ticker)).slice(0, 6);
    b.innerHTML = L.map(r => btn(r.ticker, r.ticker + (r.pn || r.nome ? ' · ' + (r.pn || r.nome).split(',')[0].slice(0, 22) : ''), 'e')).join('') || (q.trim() ? '<span class="cht-sl">Nenhuma empresa com esse nome.</span>' : '');
  }
  root.querySelector('#chtQ').addEventListener('input', () => { if (G.need === 'empresa' || G.need === 'empresa2') showMatches(); });
  const push = () => stk.push(JSON.parse(JSON.stringify(G)));
  function pick(v, l) {  // respondeu o que o caminho pedia
    push(); const a = G.a, nd = G.need;
    if (nd === 'empresa') a.e = [v]; else if (nd === 'empresa2') a.e2 = [v];
    else if (nd === 'escopo') a.esc = v; else if (nd === 'escopo2') a.esc2 = v; else a[SL[nd]] = v;
    G.lb.push(l); root.querySelector('#chtQ').value = ''; step();
  }
  function step() { G.need = needOf(G); const n = node(G.nid); if (!G.need && !n.op && n.f) return run(); drawG(); }
  function goNav(nid) { if (!M || !(nid === 'inicio' || M.nos[nid])) return; push(); G = { nid, a: {}, need: null, lb: nid === 'inicio' ? [] : [M.nos[nid].l] }; step(); }
  async function run() {
    const n = node(G.nid), a = Object.assign({}, n.a || {}, G.a, { fav: favList(), cart: cartList() });
    if (n.f === 'livre') { back(); const i = root.querySelector('#chtQ'); i.placeholder = 'Escreva sua pergunta…'; i.focus(); return; }
    H.push({ r: 'u', t: G.lb.join(' → ') }); draw();
    if (n.f === 'sim') H.push({ r: 'a', t: simTxt(), mode: 'guia' });
    else {
      GP.innerHTML = ''; L.insertAdjacentHTML('beforeend', `<div class="cht-m a cht-w">${window.loaderHTML ? loaderHTML('Buscando…') : '…'}</div>`); L.scrollTop = L.scrollHeight;  // sem botões até a resposta chegar
      try { const r = await fetch('api/chat/guia', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ f: n.f, a }) }); const d = await r.json(); H.push({ r: 'a', t: d.a || 'Sem resposta.', mode: 'guia' }); }
      catch (e) { H.push({ r: 'a', t: 'Não foi possível responder agora. Tente de novo.', mode: '' }); }
    }
    save(); draw(); back(true);
  }
  function back(menu) {  // Voltar; depois de uma resposta, volta ao último menu de opções (mesma empresa/setor) para ver outra coisa
    while (stk.length) { G = stk.pop(); if (!menu || (!needOf(G) && node(G.nid).op)) break; }
    if (menu && !(node(G.nid).op && !needOf(G))) G = { nid: 'inicio', a: {}, need: null, lb: [] };
    drawG();
  }
  function simTxt() {
    const R = window.gSim && gSim.resumo ? gSim.resumo() : [];
    if (!R.length) return 'Você ainda não tem Grupo simulação. Crie na aba Previsão (Todos + Data inicial) e acompanhe na aba Grupos.';
    return R.map(g => g.err ? `**${g.n}**: ${g.err}` : `**${g.n}** (desde ${dataBR(g.d0)}):\n` + g.L.filter(x => !x.ref).map((x, i) => `${i + 1}. ${x.n}: ${x.pct == null ? '—' : pc(x.pct)}${x.v == null ? '' : ' (' + brl.format(x.v) + ')'}`).join('\n')).join('\n\n');
  }
  GP.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b || !M) return;
    const d = b.dataset;
    if (d.gnav === 'back') return back();
    if (d.gnav === 'home') return goNav('inicio');
    if (d.ge) return pick(d.ge, d.ge);
    if (d.gv) return pick(d.gv, b.textContent);
    if (d.go) { push(); G = { nid: d.go, a: G.a, need: null, lb: G.lb.concat(M.nos[d.go].l) }; step(); }
  });
  (async function menuLoad(n) {
    try { const r = await fetch('api/chat/menu'); if (r.status === 202) throw 0; M = await r.json(); drawG(); }
    catch (e) { if ((n || 0) < 6) setTimeout(() => menuLoad((n || 0) + 1), 5000); }
  })();
  // A IA (Gemini) está funcionando? Topo do chat e ⓘ → Chat
  async function iaLoad() {
    try {
      const d = await (await fetch('api/chat/ia')).json(), t = d.ok ? 'IA ligada' : 'IA fora do ar' + (d.e ? ': ' + d.e.split(':')[0] : '');
      const h = root.querySelector('#chtIA'); h.textContent = d.ok ? '● IA ligada' : '● IA fora do ar'; h.className = 'cht-ia ' + (d.ok ? 'ok' : 'no'); h.title = t;  // motivo no ⓘ → Chat
      const i = document.getElementById('iaSt'); if (i) i.textContent = t + (d.t ? ' (conferido ' + new Date(d.t * 1000).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) + ')' : '');
    } catch (e) { }
  }
  iaLoad();
})();
