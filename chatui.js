// ---------- Chat (perguntas sobre os dados do site) ----------
(function () {
  const KEY = 'screenerB3.chat.v1', root = document.getElementById('chatRoot');
  if (!root) return;
  let H = (() => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(H.slice(-60))); } catch (e) { } };
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^\s*[*•-]\s+/gm, '• ').replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener" class="text-sky-300 underline">link</a>').replace(/\n/g, '<br>');
  root.innerHTML = `<div class="cht"><div class="cht-h"><b>Chat</b><button type="button" class="gbtn" id="chtClr">Limpar</button></div>
    <div class="cht-l" id="chtL"></div>
    <form class="cht-f" id="chtF" autocomplete="off"><input id="chtQ" class="pv-in" placeholder="Pergunte sobre as ações do site…" maxlength="500" enterkeyhint="send"><button type="submit" class="gbtn pri" id="chtS">Enviar</button></form></div>`;
  const L = root.querySelector('#chtL');
  const txt = (sel, n) => { const e = document.querySelector(sel); return e ? e.innerText.replace(/[ \t]+/g, ' ').replace(/\n{2,}/g, '\n').slice(0, n) : ''; };
  const ls = (k, n) => { try { return (localStorage.getItem(k) || '').slice(0, n); } catch (e) { return ''; } };
  function ctxNow() { // dados do app no navegador: etiquetas, confiança, grupos e o que o usuário preencheu
    const rows = (typeof state !== 'undefined' && state.data && state.data.rows) || [];
    let tags = '';
    try { tags = rows.map(r => r.ticker + ':' + (r.tags || []).join('/') + (typeof confTxt === 'function' && r.S ? '|' + confTxt(r) : '')).join(';'); } catch (e) { }
    let groups = ''; try { groups = window.gTop10 ? gTop10() : ''; } catch (e) { }
    return { tags: tags.slice(0, 20000), groups: groups.slice(0, 8000),
      prev: ls('screenerB3.previsao.v1', 3000), prevRes: txt('[data-tabpane="previsao"] .pv-sum, [data-tabpane="previsao"] table', 2500),
      alug: ls('screenerB3.aluguel.v1', 3000), alugRes: txt('#alugRoot table', 2500),
      comp: ls('screenerB3.comparar.v1', 1500), compRes: txt('#compRoot .cmp-cols', 5000) };
  }
  const EX = ['DY do Itaú', 'Maiores DY dos bancos', 'PETR4 vs Ibovespa em 2024', 'Ações com ROE acima de 20 e P/L abaixo de 8', 'O que significam as cores?'];
  const chips = (list, lbl) => list && list.length ? `<div class="cht-s">${lbl ? `<span class="cht-sl">${esc(lbl)}</span>` : ''}${list.map(x => `<button type="button" class="cht-c" data-q="${esc(x.q || x)}"${x.topic ? ` data-topic="${esc(x.topic)}"` : ''}>${esc(x.l || x)}</button>`).join('')}</div>` : '';  // x = texto ou {l: rótulo, q: pergunta}
  const draw = () => {
    const last = H.length - 1;
    L.innerHTML = H.length ? H.map((m, i) => `<div class="cht-m ${m.r === 'u' ? 'u' : 'a'}">${m.r === 'u' ? esc(m.t) : md(m.t)}${i === last && m.r === 'a' ? chips(m.sug, m.sugl) : ''}</div>`).join('')
      : `<div class="cht-e">Pergunte do seu jeito — por nome, apelido ou ticker. Exemplos:${chips(EX)}</div>`;
    L.scrollTop = L.scrollHeight;
  };
  draw();
  root.querySelector('#chtClr').onclick = async () => { if (!H.length || (window.uiConfirm ? await uiConfirm('Apagar o histórico do chat?') : true)) { H = []; save(); draw(); } };
  let topic = null;
  L.addEventListener('click', (e) => {  // sugestões clicáveis
    const c = e.target.closest('.cht-c'); if (!c) return;
    topic = c.dataset.topic || null;  // "Está falando sobre:": refaz a mesma pergunta com o tema
    root.querySelector('#chtQ').value = c.dataset.q; root.querySelector('#chtF').requestSubmit();
  });
  root.querySelector('#chtF').onsubmit = async (e) => {
    e.preventDefault(); const inp = root.querySelector('#chtQ'), q = inp.value.trim(); if (!q || root.querySelector('#chtS').disabled) return;
    const hist = H.slice(-6).map(m => ({ r: m.r, t: m.t }));
    const tp = topic; topic = null;
    H.push({ r: 'u', t: tp ? 'Sobre: ' + tp : q }); inp.value = ''; draw();
    L.insertAdjacentHTML('beforeend', `<div class="cht-m a cht-w">${window.loaderHTML ? loaderHTML('Pensando…') : '…'}</div>`); L.scrollTop = L.scrollHeight;
    const btn = root.querySelector('#chtS'); btn.disabled = true;
    try {
      const ac = new AbortController(), to = setTimeout(() => ac.abort(), 150000);
      const r = await fetch('api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q, hist, ctx: ctxNow(), topic: tp }), signal: ac.signal });
      clearTimeout(to); const d = await r.json(); H.push({ r: 'a', t: d.a || 'Sem resposta.', mode: d.mode, sug: d.sug || null, sugl: d.sugl || null });
    } catch (err) { H.push({ r: 'a', t: 'Não foi possível responder agora. Tente de novo.', mode: '' }); }
    btn.disabled = false; save(); draw();
  };
})();
