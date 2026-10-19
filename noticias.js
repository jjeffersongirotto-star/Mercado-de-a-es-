// ---------- Notícias: mercado e Luiz Barsi (snapshot noticias da branch data, scripts/fetch_noticias.py) ----------
// Filtros: Todas · Mercado · Exterior (mercado de fora) · Barsi · Minhas empresas (citam um Favorito: raiz do ticker da B3 ou ticker de fora); a escolha fica no aparelho.
// Nada é buscado nos sites por visita: /api/noticias só repassa o arquivo. Imagem de capa da própria matéria (og:image),
// carregada só quando aparece na tela; se não abrir, a imagem some e o card fica só com o texto.
(function () {
  const root = () => document.getElementById('newsRoot');
  let loaded = false, D = null;
  const KEY = 'screenerB3.noticias.v1', FIL = [['todas', 'Todas'], ['mercado', 'Mercado'], ['ext', 'Exterior'], ['barsi', 'Barsi'], ['fav', 'Minhas empresas']];
  // mercado da notícia (m: "br" e/ou países de fora); nome do país = o do seletor de país (state.countries)
  const pais = (c) => (((typeof state !== 'undefined' && state.countries) || []).find(x => x.id === c) || {}).name || c.toUpperCase();
  let fil = (() => { try { return localStorage.getItem(KEY) || 'todas'; } catch (e) { return 'todas'; } })();
  const favR = () => new Set([...(typeof FAVS !== 'undefined' ? FAVS : [])].map(t => t.slice(0, 4)));
  const favs = () => new Set([...(typeof FAVS !== 'undefined' ? FAVS : [])]);
  const pass = (n) => fil === 'todas' || (fil === 'ext' ? (n.m || []).some(c => c !== 'br')
    : fil === 'fav' ? (n.t || []).some(t => favR().has(t.slice(0, 4))) || (n.tf || []).some(x => favs().has(x.split(':')[1]))
    : (n.tema || 'barsi') === fil);
  const dt = (s) => !s ? '' : s.length === 7 ? `${s.slice(5, 7)}/${s.slice(0, 4)}` : `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}`;
  const card = (n) => `<a class="nw-card" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">
      ${n.img ? `<img class="nw-img" src="${esc(n.img)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      <div class="nw-tx"><p class="nw-meta">${esc(n.fonte || '')}${n.data ? ' · ' + dt(n.data) : ''}${(n.m || []).length ? ' · ' + n.m.map(c => esc(pais(c))).join(', ') : ''}</p><h3 class="nw-t">${esc(n.titulo)}</h3>${(n.t || []).length + (n.tf || []).length ? `<p class="nw-tk">${(n.t || []).concat((n.tf || []).map(x => x.split(':')[1])).map(t => `<span class="gchip">${esc(t)}</span>`).join('')}</p>` : ''}${n.resumo ? `<p class="nw-d">${esc(n.resumo)}</p>` : ''}<span class="nw-go">Abrir matéria ↗</span></div></a>`;
  async function load() {
    if (loaded) return; loaded = true;
    root().innerHTML = loaderHTML('Carregando notícias…');
    try {
      D = await getRetry('/api/noticias'); draw();
    } catch (e) { loaded = false; root().innerHTML = `<p class="pvd-note">Não foi possível carregar as notícias: ${esc(e.message)}</p>`; }
  }
  function draw() {
    const L = ((D && D.itens) || []).filter(pass);
    root().innerHTML = `<section class="nw-head"><h2>Notícias ${glossBtn('Notícias')}</h2><div class="pv-per nw-fil">${FIL.map(([k, l]) => `<button type="button" data-nwf="${k}" class="${k === fil ? 'on' : ''}">${l}</button>`).join('')}</div></section>`
      + (L.length ? `<div class="nw-grid">${L.map(card).join('')}</div>` : `<p class="pvd-note">${fil === 'fav' ? 'Nenhuma notícia cita seus Favoritos por enquanto.' : 'Nenhuma notícia por enquanto.'}</p>`)
      + `<p class="pvd-note">Resumos curtos; o texto completo está no site de cada fonte (abre em nova aba). Para estudo, não é recomendação.</p>`;
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-nwf]'); if (!b) return;
    fil = b.dataset.nwf; try { localStorage.setItem(KEY, fil); } catch (x) { } draw();
  });
  document.addEventListener('favs', () => { if (D && fil === 'fav') draw(); });
  document.addEventListener('tabshow', (e) => { if (e.detail === 'noticias') load(); });
  if (!document.querySelector('[data-tabpane="noticias"]').classList.contains('hidden')) load();
})();
