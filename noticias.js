// ---------- Notícias: matérias sobre Luiz Barsi (snapshot noticias da branch data, scripts/fetch_noticias.py) ----------
// Nada é buscado nos sites por visita: /api/noticias só repassa o arquivo. Imagem de capa da própria matéria (og:image),
// carregada só quando aparece na tela; se não abrir, a imagem some e o card fica só com o texto.
(function () {
  const root = () => document.getElementById('newsRoot');
  let loaded = false;
  const dt = (s) => !s ? '' : s.length === 7 ? `${s.slice(5, 7)}/${s.slice(0, 4)}` : `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}`;
  const card = (n) => `<a class="nw-card" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">
      ${n.img ? `<img class="nw-img" src="${esc(n.img)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      <div class="nw-tx"><p class="nw-meta">${esc(n.fonte || '')}${n.data ? ' · ' + dt(n.data) : ''}</p><h3 class="nw-t">${esc(n.titulo)}</h3>${n.resumo ? `<p class="nw-d">${esc(n.resumo)}</p>` : ''}<span class="nw-go">Abrir matéria ↗</span></div></a>`;
  async function load() {
    if (loaded) return; loaded = true;
    root().innerHTML = loaderHTML('Carregando notícias…');
    try {
      const d = await getRetry('/api/noticias'); const L = (d && d.itens) || [];
      root().innerHTML = `<section class="nw-head"><h2>Notícias · ${esc(d.tema || 'Luiz Barsi')} ${glossBtn('Notícias')}</h2></section>`
        + (L.length ? `<div class="nw-grid">${L.map(card).join('')}</div>` : '<p class="pvd-note">Nenhuma notícia por enquanto.</p>')
        + `<p class="pvd-note">Resumos curtos; o texto completo está no site de cada fonte (abre em nova aba). Para estudo, não é recomendação.</p>`;
    } catch (e) { loaded = false; root().innerHTML = `<p class="pvd-note">Não foi possível carregar as notícias: ${esc(e.message)}</p>`; }
  }
  document.addEventListener('tabshow', (e) => { if (e.detail === 'noticias') load(); });
  if (!document.querySelector('[data-tabpane="noticias"]').classList.contains('hidden')) load();
})();
