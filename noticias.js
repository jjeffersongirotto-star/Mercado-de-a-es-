// ---------- Notícias: mercado e Luiz Barsi (snapshot noticias da branch data, scripts/fetch_noticias.py) ----------
// Filtros: Todas · Mercado · Exterior (mercado de fora) · Minhas empresas (as do Barsi entram junto, sem filtro próprio; destaque no topo) (citam um Favorito: raiz do ticker da B3 ou ticker de fora); a escolha fica no aparelho.
// Nada é buscado nos sites por visita: /api/noticias só repassa o arquivo. Imagem de capa da própria matéria (og:image),
// carregada só quando aparece na tela; se não abrir, a imagem some e o card fica só com o texto.
(function () {
  const root = () => document.getElementById('newsRoot');
  let loaded = false, D = null;
  const KEY = 'screenerB3.noticias.v1', FIL = [['todas', 'Todas'], ['mercado', 'Mercado'], ['ext', 'Exterior'], ['fav', 'Minhas empresas']];
  // mercado da notícia (m: "br" e/ou países de fora); nome do país = o do seletor de país (state.countries)
  const pais = (c) => (((typeof state !== 'undefined' && state.countries) || []).find(x => x.id === c) || {}).name || c.toUpperCase();
  let fil = (() => { try { const v = localStorage.getItem(KEY) || 'todas'; return FIL.some(f => f[0] === v) ? v : 'todas'; } catch (e) { return 'todas'; } })();
  const favR = () => new Set([...(typeof FAVS !== 'undefined' ? FAVS : [])].map(t => t.slice(0, 4)));
  const favs = () => new Set([...(typeof FAVS !== 'undefined' ? FAVS : [])]);
  const pass = (n) => fil === 'todas' || (fil === 'ext' ? (n.m || []).some(c => c !== 'br')
    : fil === 'fav' ? (n.t || []).some(t => favR().has(t.slice(0, 4))) || (n.tf || []).some(x => favs().has(x.split(':')[1]))
    : fil === 'mercado' && (n.m || ['br']).includes('br'));
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
    const dest = ((D && D.itens) || []).filter(n => n.destaque || (!('destaque' in n) && /^Preço-teto:/i.test(n.titulo || '')));
    const L = ((D && D.itens) || []).filter(n => !dest.includes(n)).filter(pass).sort((a, b) => (b.data || '0000').localeCompare(a.data || '0000'));
    root().innerHTML = `<section class="nw-head"><h2>Notícias ${glossBtn('Notícias')}</h2><div class="pv-per nw-fil">${FIL.map(([k, l]) => `<button type="button" data-nwf="${k}" class="${k === fil ? 'on' : ''}">${l}</button>`).join('')}</div></section>` + metHtml()
      // Destaque é o 1º card da mesma grade: as fileiras começam cheias e só a última pode ficar incompleta
      + (dest.length || L.length ? `<div class="nw-grid">${dest.map(n => card(n, true)).join('')}${L.map(n => card(n)).join('')}</div>` : '')
      + (L.length ? '' : `<p class="pvd-note">${fil === 'fav' ? 'Nenhuma notícia cita seus Favoritos por enquanto.' : 'Nenhuma notícia por enquanto.'}</p>`)
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
