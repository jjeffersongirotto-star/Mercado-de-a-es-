// ---------- Notícias: mercado e Luiz Barsi (snapshot noticias da branch data, scripts/fetch_noticias.py) ----------
// Filtros (a escolha fica no aparelho): assunto (Todas, Dividendos, Resultados, Economia, Negócios, Alertas: n.a do servidor, server.noticia_assuntos),
// onde (Brasil, Exterior, Minhas empresas = citam um Favorito: raiz do ticker da B3 ou ticker de fora; toque de novo desmarca) e setor das empresas
// citadas (macro de app.js → SECTORS). O Destaque (Preço-teto) entra em Todas e Dividendos; Métodos de investimento aparecem sempre.
// Nada é buscado nos sites por visita: /api/noticias só repassa o arquivo. Imagem de capa da própria matéria (og:image),
// carregada só quando aparece na tela; se não abrir, a imagem some e o card fica só com o texto.
(function () {
  const root = () => document.getElementById('newsRoot');
  let loaded = false, D = null;
  const KEY = 'screenerB3.noticias.v2', ASS = [['todas', 'Todas'], ['div', 'Dividendos'], ['res', 'Resultados'], ['eco', 'Economia'], ['neg', 'Negócios'], ['al', 'Alertas']],
    ONDE = [['br', 'Brasil'], ['ext', 'Exterior'], ['fav', 'Minhas empresas']];
  // mercado da notícia (m: "br" e/ou países de fora); nome do país = o do seletor de país (state.countries)
  const pais = (c) => (((typeof state !== 'undefined' && state.countries) || []).find(x => x.id === c) || {}).name || c.toUpperCase();
  const F = (() => { try { const v = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; return { a: ASS.some(x => x[0] === v.a) ? v.a : 'todas', o: ONDE.some(x => x[0] === v.o) ? v.o : '', s: v.s || '' }; } catch (e) { return { a: 'todas', o: '', s: '' }; } })();
  try { localStorage.removeItem('screenerB3.noticias.v1'); } catch (e) { }
  const saveF = () => { try { localStorage.setItem(KEY, JSON.stringify(F)); } catch (e) { } };
  // raízes e tickers dos Favoritos: montados uma vez por filtragem (não a cada notícia) e refeitos na próxima
  let FS = null;
  const favSets = () => {
    if (!FS) { const L = [...(typeof FAVS !== 'undefined' ? FAVS : [])]; FS = { r: new Set(L.map(t => t.slice(0, 4))), t: new Set(L) }; queueMicrotask(() => { FS = null; }); }
    return FS;
  };
  const setores = (n) => { const R = (typeof state !== 'undefined' && state.rowMap) || {}; return new Set((n.t || []).map(t => (R[t] || {}).macro).filter(Boolean)); };
  const onde = (n) => !F.o || (F.o === 'ext' ? (n.m || []).some(c => c !== 'br')
    : F.o === 'fav' ? (n.t || []).some(t => favSets().r.has(t.slice(0, 4))) || (n.tf || []).some(x => favSets().t.has(x.split(':')[1]))
    : (n.m || ['br']).includes('br'));
  const pass = (n) => (F.a === 'todas' || (n.a || []).includes(F.a)) && onde(n) && (!F.s || setores(n).has(F.s));
  const dt = (s) => !s ? '' : s.length === 7 ? `${s.slice(5, 7)}/${s.slice(0, 4)}` : `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}`;
  const card = (n, dst) => `<a class="nw-card${dst ? ' nw-dest' : ''}" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">
      ${n.img ? `<img class="nw-img" src="${esc(n.img)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      <div class="nw-tx"><p class="nw-meta">${dst ? '<span class="nw-dst">Destaque</span> ' : ''}${esc(n.fonte || '')}${n.data ? ' · ' + dt(n.data) : ''}${(n.m || []).length ? ' · ' + n.m.map(c => esc(pais(c))).join(', ') : ''}</p><h3 class="nw-t">${esc(n.titulo)}</h3>${(n.t || []).length + (n.tf || []).length ? `<p class="nw-tk">${(n.t || []).concat((n.tf || []).map(x => x.split(':')[1])).map(t => `<span class="gchip">${esc(t)}</span>`).join('')}</p>` : ''}${n.resumo ? `<p class="nw-d">${esc(n.resumo)}</p>` : ''}<span class="nw-go">Abrir matéria ↗</span></div></a>`;
  // Métodos de investimento: matérias do ⓘ → Métodos de investimento (.met-links, fonte única), em pasta: 1º toque destaca, 2º abre
  const metHtml = () => {
    const L = [...document.querySelectorAll('#infoModal .met-links li')];
    if (!L.length) return '';
    return `<h3 class="nw-sub">Métodos de investimento</h3><div class="mf">${L.map((li, i) => {
      const d = li.dataset, x = li.cloneNode(true); x.querySelectorAll('b, a').forEach(n => n.remove()); const tx = x.textContent.replace(/^:\s*/, '').trim();
      return `<a class="mf-c" style="--i:${i * 8 / Math.max(1, L.length - 1)};--h:${(i * 40) % 360};z-index:${i + 1}" href="${esc(d.url)}" target="_blank" rel="noopener noreferrer"><span class="mf-tab">${esc(d.met)}</span><span class="mf-b"><b>${esc(d.met)}</b><small>${esc(d.src)}</small><p>${esc(tx)}</p><em>Toque de novo para abrir ↗</em></span></a>`;
    }).join('')}</div>`;
  };
  document.addEventListener('click', (e) => {
    const c = e.target.closest('.mf-c'), f = document.querySelector('.mf.sel');
    if (c && !c.classList.contains('on')) {
      e.preventDefault();
      document.querySelectorAll('.mf-c.on').forEach(x => x.classList.remove('on'));
      c.classList.add('on'); c.closest('.mf').classList.add('sel'); return;
    }
    if (!c && f) { f.classList.remove('sel'); f.querySelectorAll('.mf-c.on').forEach(x => x.classList.remove('on')); }
  });
  async function load() {
    if (loaded) return; loaded = true;
    root().innerHTML = loaderHTML('Carregando notícias…');
    try {
      D = await getRetry('/api/noticias'); draw();
    } catch (e) { loaded = false; root().innerHTML = `<p class="pvd-note">Não foi possível carregar as notícias: ${esc(e.message)}</p>`; }
  }
  function draw() {
    const dest = ((D && D.itens) || []).filter(n => n.destaque || (!('destaque' in n) && /^Preço-teto:/i.test(n.titulo || ''))).filter(n => (F.a === 'todas' || F.a === 'div') && onde(n) && !F.s);
    const L = ((D && D.itens) || []).filter(n => !dest.includes(n)).filter(pass).sort((a, b) => (b.data || '0000').localeCompare(a.data || '0000'));
    const SEC = typeof SECTORS !== 'undefined' ? SECTORS : [];
    root().innerHTML = `<section class="nw-head"><h2>Notícias ${glossBtn('Notícias')}</h2><div class="pv-per nw-fil">${ASS.map(([k, l]) => `<button type="button" data-nwa="${k}" class="${k === F.a ? 'on' : ''}">${l}</button>`).join('')}</div>
      <div class="nw-fil2"><div class="pv-per nw-fil">${ONDE.map(([k, l]) => `<button type="button" data-nwo="${k}" class="${k === F.o ? 'on' : ''}">${l}</button>`).join('')}</div>
      <select id="nwSec" class="sel" aria-label="Setor"><option value="">Todos os setores</option>${SEC.map(x => `<option${x === F.s ? ' selected' : ''}>${esc(x)}</option>`).join('')}</select></div></section>` + metHtml()
      // Destaque é o 1º card da mesma grade: as fileiras começam cheias e só a última pode ficar incompleta
      + (dest.length || L.length ? `<div class="nw-grid">${dest.map(n => card(n, true)).join('')}${L.map(n => card(n)).join('')}</div>` : '')
      + (L.length || dest.length ? '' : `<p class="pvd-note">${F.o === 'fav' ? 'Nenhuma notícia com esses filtros cita seus Favoritos por enquanto.' : 'Nenhuma notícia com esses filtros por enquanto.'}</p>`)
      + `<p class="pvd-note">Resumos curtos; o texto completo está no site de cada fonte (abre em nova aba). Para estudo, não é recomendação.</p>`;
  }
  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-nwa]'), o = e.target.closest('[data-nwo]'); if (!a && !o) return;
    if (a) F.a = a.dataset.nwa; else F.o = F.o === o.dataset.nwo ? '' : o.dataset.nwo;  // onde: toque de novo desmarca
    saveF(); draw();
  });
  document.addEventListener('change', (e) => { if (e.target.id === 'nwSec') { F.s = e.target.value; saveF(); draw(); } });
  document.addEventListener('favs', () => { if (D && F.o === 'fav') draw(); });
  document.addEventListener('dataload', () => { if (D && F.s) draw(); });  // setor das empresas citadas vem de /api/data
  document.addEventListener('tabshow', (e) => { if (e.detail === 'noticias') load(); });
  if (!document.querySelector('[data-tabpane="noticias"]').classList.contains('hidden')) load();
})();
