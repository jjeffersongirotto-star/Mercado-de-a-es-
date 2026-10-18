// ---------- Utilitários compartilhados por todas as abas (fonte única: não recrie em outro arquivo) ----------
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const nf = (d) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const F0 = nf(0), F2 = nf(2);
const pc = (x) => (x > 0 ? '+' : '') + F2.format(x) + '%';  // variação com sinal: +1,23%
const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const norm = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();  // sem acento, minúsculo
// número digitado no formato brasileiro ("1.234,56", "R$ 10", "8,5%") -> 1234.56; vazio/inválido -> 0
const dataBR = (iso) => iso ? String(iso).slice(0, 10).split('-').reverse().join('/') : '—';  // 2026-10-12 -> 12/10/2026 (2026-10 -> 10/2026)
const parseBR = (s) => { s = String(s ?? '').trim().replace(/\s|R\$|%/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, ''); const n = parseFloat(s); return Number.isFinite(n) ? n : 0; };

// Setas de ordem (˄ menor → maior · ˅ maior → menor; verde = sentido atual): Ordenar da aba Mercado e títulos de colunas
window.sortIc = (dir) => `<svg class="sd-ic" viewBox="0 0 16 18" width="16" height="18" aria-hidden="true"><path class="${dir > 0 ? 'on' : ''}" d="M4 7 8 3l4 4"/><path class="${dir < 0 ? 'on' : ''}" d="M4 11l4 4 4-4"/></svg>`;
window.thSort = (label, key, cur, dir) => `<th data-sc="${key}" class="th-s"><span>${label}</span>${sortIc(cur === key ? dir : 0)}</th>`;
// Tabela ordenável no próprio navegador: <table data-srt> com títulos thSort e células com data-v (número ou texto)
if (typeof document !== 'undefined') document.addEventListener('click', (e) => {
  const th = e.target.closest('table[data-srt] th[data-sc]'); if (!th || e.target.closest('[data-gl]')) return;
  const tb = th.closest('table'), i = [...th.parentNode.children].indexOf(th), dir = th.dataset.dir === '-1' ? 1 : -1;
  tb.querySelectorAll('th[data-sc]').forEach(x => { x.dataset.dir = x === th ? dir : ''; x.querySelector('.sd-ic').outerHTML = sortIc(x === th ? dir : 0); });
  const val = (tr) => { const v = tr.children[i]?.dataset.v ?? ''; const n = parseFloat(v); return isNaN(n) ? v : n; };
  const body = tb.querySelector('tbody:not(.ref)');  // referências (tbody.ref) ficam fixas no topo
  const rows = [...body.rows].sort((a, b) => { const x = val(a), y = val(b); return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'pt-BR')) * dir; });
  body.append(...rows);
});

// Diálogos do site (substituem confirm/alert/prompt), toast e animação de carregamento
(function () {
  function modal({ title, msg, html, input, okText = 'OK', cancelText = 'Cancelar', danger = false, noCancel = false, value = '' }) {
    return new Promise((res) => {
      const w = document.createElement('div'); w.className = 'umod' + (html ? ' umod-wide' : '');
      w.innerHTML = `<div class="umod-box" role="dialog" aria-modal="true">${title ? `<h3>${title}</h3>` : ''}<p></p>
        ${input ? '<input class="umod-in" autocomplete="off" spellcheck="false" maxlength="40">' : ''}
        <div class="umod-btns">${noCancel ? '' : `<button type="button" class="umod-c">${cancelText}</button>`}<button type="button" class="umod-ok${danger ? ' dan' : ''}">${okText}</button></div></div>`;
      if (html) w.querySelector('p').outerHTML = `<div class="umod-html">${html}</div>`; else w.querySelector('p').textContent = msg || '';
      document.body.appendChild(w);
      const inp = w.querySelector('.umod-in'); if (inp) { inp.value = value; setTimeout(() => { inp.focus(); inp.select(); }, 30); } else setTimeout(() => w.querySelector('.umod-ok').focus({ preventScroll: true }), 30);
      const done = (v) => { w.remove(); document.removeEventListener('keydown', key, true); res(v); };
      const key = (e) => { if (e.key === 'Escape') { e.preventDefault(); done(input ? null : false); } else if (e.key === 'Enter') { e.preventDefault(); done(input ? inp.value : true); } };
      document.addEventListener('keydown', key, true);
      w.addEventListener('click', (e) => {
        if (e.target === w || e.target.closest('.umod-c')) done(input ? null : false);
        else if (e.target.closest('.umod-ok')) done(input ? inp.value : true);
      });
    });
  }
  window.uiConfirm = (msg, o = {}) => modal({ msg, okText: o.ok || 'Confirmar', danger: !!o.danger, title: o.title, cancelText: o.cancel || 'Cancelar' });
  window.uiAlert = (msg, o = {}) => modal({ msg, html: o.html, title: o.title, noCancel: true });  // o.html: conteúdo já escapado (tabelas)
  window.uiPrompt = (msg, value = '', o = {}) => modal({ msg, input: true, value, okText: o.ok || 'Salvar', title: o.title });
  window.uiToast = (msg) => {
    let t = document.getElementById('uiToast');
    if (!t) { t = document.createElement('div'); t.id = 'uiToast'; t.className = 'pv-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('on'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 1900);
  };
  // Senhor de boina na mesa, com computador, folheando um maço de notas
  window.loaderHTML = (txt) => `<div class="ldr" role="status" aria-label="${txt || 'Carregando'}"><svg viewBox="0 0 220 150" width="220" height="150" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <g stroke="rgb(100 116 139)" stroke-width="2">
      <path d="M10 118 H210"/><path d="M30 118 V144 M190 118 V144"/>
      <rect x="128" y="62" width="62" height="42" rx="3"/><path d="M152 104 v8 h14 v-8 M146 113 h26"/>
      <path d="M135 70 h18 M135 77 h30 M135 84 h22" stroke="rgb(16 185 129)" stroke-width="1.6"/>
      <path class="ldr-line" d="M137 96 l8 -5 l7 3 l9 -8 l9 2 l9 -7" stroke="rgb(16 185 129)"/>
    </g>
    <g stroke="rgb(203 213 225)" stroke-width="2">
      <path d="M44 44 q2 -12 18 -12 q14 0 16 10 q-16 -4 -34 2 z"/><circle cx="73" cy="31" r="2"/>
      <path d="M48 46 q-2 16 12 20 q14 -2 14 -18"/><path d="M55 53 h3 M65 53 h3"/><path d="M56 61 q4 3 9 0"/>
      <path d="M52 58 q-4 6 0 8 M70 58 q4 6 0 8" stroke="rgb(148 163 184)"/>
      <path d="M44 118 q-6 -40 16 -48 q22 6 18 48"/>
      <path d="M50 84 q14 14 34 22"/><path d="M76 82 q12 10 22 20"/>
    </g>
    <g stroke="rgb(52 211 153)" stroke-width="1.8">
      <rect x="84" y="104" width="30" height="12" rx="1.5"/><path d="M86 101 h28 M86 98 h28"/><circle cx="99" cy="110" r="2.5"/>
      <g class="ldr-note"><rect x="84" y="92" width="30" height="5" rx="1.5" fill="rgb(6 78 59)"/></g>
    </g></svg>${txt ? `<span>${txt}</span>` : ''}</div>`;
})();
// Reorganizar (arrastar pela alça ⠿, Salvar/Cancelar): items = [{id, label}] -> nova ordem de ids, ou null se cancelar. Grupos e Comparar.
window.uiReorder = (title, items) => new Promise((res) => {
  const ov = document.createElement('div'); ov.className = 'rg-ov';
  ov.innerHTML = `<div class="rg-top"><button type="button" class="gbtn" data-rg="cancel">Cancelar</button><b>${esc(title)}</b><button type="button" class="gbtn pri" data-rg="save">Salvar</button></div><div class="rg-grid"></div>`;
  document.body.appendChild(ov);
  const grid = ov.querySelector('.rg-grid');
  grid.innerHTML = items.map(x => `<div class="rg-card" data-id="${esc(x.id)}"><span class="rg-n"></span><span class="rg-t">${esc(x.label)}</span><span class="rg-h">⠿</span></div>`).join('');
  const num = () => [...grid.children].forEach((c, i) => { c.querySelector('.rg-n').textContent = i + 1; });
  const fit = () => {
    const n = items.length, H = window.innerHeight - ov.querySelector('.rg-top').offsetHeight - 24, W = Math.min(window.innerWidth - 24, 900);
    const h0 = 64, w0 = 340, gap = 8;
    let s = Math.min(1, (H - gap * (n - 1)) / (n * h0)), cols = 1;
    if (w0 * s < W / 2 && n > 1) { cols = 2; const r2 = Math.ceil(n / 2); s = Math.min(1, (H - gap * (r2 - 1)) / (r2 * h0)); }
    const rows = Math.ceil(n / cols), ch = Math.max(26, h0 * s), cw = cols === 1 ? Math.min(W, w0) : Math.min(W / 2 - gap, w0);
    grid.style.gridTemplateRows = `repeat(${rows}, ${ch}px)`; grid.style.gridTemplateColumns = `repeat(${cols}, ${cw}px)`;
    grid.style.fontSize = Math.max(10, 15 * Math.min(1, ch / h0)) + 'px';
  };
  num(); fit(); window.addEventListener('resize', fit);
  const so = window.Sortable ? Sortable.create(grid, { animation: 150, onSort: num }) : null;
  ov.addEventListener('click', (e) => {
    const b = e.target.closest('[data-rg]'); if (!b) return;
    const ids = b.dataset.rg === 'save' ? [...grid.children].map(c => c.dataset.id) : null;
    so && so.destroy(); window.removeEventListener('resize', fit); ov.remove();
    if (ids) uiToast('Ordem salva');
    res(ids);
  });
});
// Calendário do site (substitui o do navegador, igual em todo aparelho): uiCalendar abre o diálogo; uiDateField liga um campo a ele.
// kind 'date' -> AAAA-MM-DD (grade de dias) · 'month' -> AAAA-MM (grade de meses). Tocar no mês/ano do título abre a lista de anos.
const UI_MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
// empty: rótulo da opção sem data (ex.: Data final "Hoje (em andamento)"); escolhida devolve '' (null = cancelou)
window.uiCalendar = (value, { min = '', max = '', kind = 'date', title = '', empty = '' } = {}) => new Promise((res) => {
  const pad = (n) => String(n).padStart(2, '0'), iso = (y, m, d) => kind === 'month' ? `${y}-${pad(m + 1)}` : `${y}-${pad(m + 1)}-${pad(d)}`;
  const now = new Date(), clamp = (v) => (min && v < min.slice(0, v.length) ? min.slice(0, v.length) : max && v > max.slice(0, v.length) ? max.slice(0, v.length) : v);
  let sel = value || '', base = sel || clamp(iso(now.getFullYear(), now.getMonth(), now.getDate()));
  let vy = +base.slice(0, 4), vm = +base.slice(5, 7) - 1, years = false;
  const out = (v) => (min && v < min.slice(0, v.length)) || (max && v > max.slice(0, v.length));
  const w = document.createElement('div'); w.className = 'umod';
  w.innerHTML = `<div class="umod-box ucal" role="dialog" aria-modal="true" aria-label="${title || 'Calendário'}">${title ? `<h3>${title}</h3>` : ''}${empty ? `<button type="button" class="ucal-none${value ? '' : ' on'}">${empty}</button>` : ''}<div class="ucal-hd"></div><div class="ucal-g"></div>
    <div class="umod-btns"><button type="button" class="umod-c">Cancelar</button><button type="button" class="ucal-today">Hoje</button><button type="button" class="umod-ok">OK</button></div></div>`;
  const hd = w.querySelector('.ucal-hd'), g = w.querySelector('.ucal-g');
  function draw() {
    const lbl = years ? `${vy - (vy % 12)}–${vy - (vy % 12) + 11}` : kind === 'month' ? vy : `${UI_MESES[vm][0].toUpperCase() + UI_MESES[vm].slice(1)} de ${vy}`;
    hd.innerHTML = `<button type="button" data-nav="-1" aria-label="Anterior">‹</button><button type="button" class="ucal-t" data-yrs aria-label="Escolher o ano">${lbl} ▾</button><button type="button" data-nav="1" aria-label="Próximo">›</button>`;
    g.className = 'ucal-g' + (years || kind === 'month' ? ' ucal-g3' : '');
    if (years) {  // lista de anos (12 por página)
      const y0 = vy - (vy % 12);
      g.innerHTML = Array.from({ length: 12 }, (_, k) => y0 + k).map(y => `<button type="button" data-y="${y}" class="${y === +sel.slice(0, 4) ? 'on' : ''}"${out(String(y)) ? ' disabled' : ''}>${y}</button>`).join('');
    } else if (kind === 'month') {
      g.innerHTML = UI_MESES.map((n, m) => { const v = iso(vy, m); return `<button type="button" data-v="${v}" class="${v === sel ? 'on' : ''}"${out(v) ? ' disabled' : ''}>${n.slice(0, 3)}</button>`; }).join('');
    } else {
      const f = new Date(vy, vm, 1).getDay(), nd = new Date(vy, vm + 1, 0).getDate(), td = iso(now.getFullYear(), now.getMonth(), now.getDate());
      g.innerHTML = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'].map(d => `<span class="ucal-w">${d}</span>`).join('') + '<span></span>'.repeat(f) +
        Array.from({ length: nd }, (_, k) => { const v = iso(vy, vm, k + 1); return `<button type="button" data-v="${v}" class="${v === sel ? 'on' : ''}${v === td ? ' td' : ''}"${out(v) ? ' disabled' : ''}>${k + 1}</button>`; }).join('');
    }
  }
  const done = (v) => { w.remove(); document.removeEventListener('keydown', key); res(v); };
  const key = (e) => { if (e.key === 'Escape') done(null); };
  w.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (e.target === w) return done(null); if (!b || b.disabled) return;
    if (b.dataset.nav) { const k = +b.dataset.nav; if (years) vy += 12 * k; else if (kind === 'month') vy += k; else { vm += k; if (vm < 0) { vm = 11; vy--; } if (vm > 11) { vm = 0; vy++; } } }
    else if (b.hasAttribute('data-yrs')) years = !years;
    else if (b.dataset.y) { vy = +b.dataset.y; years = false; }
    else if (b.dataset.v) sel = b.dataset.v;
    else if (b.classList.contains('ucal-today')) { sel = clamp(iso(now.getFullYear(), now.getMonth(), now.getDate())); vy = +sel.slice(0, 4); vm = +sel.slice(5, 7) - 1; years = false; }
    else if (b.classList.contains('ucal-none')) return done('');
    else if (b.classList.contains('umod-c')) return done(null);
    else if (b.classList.contains('umod-ok')) return done(sel || null);
    draw();
  });
  document.addEventListener('keydown', key); document.body.appendChild(w); draw();
  setTimeout(() => w.querySelector('.umod-ok').focus({ preventScroll: true }), 30);
});
// Campo de data com o calendário do site: .value continua AAAA-MM-DD (ou AAAA-MM), min/max limitam; mostra dd/mm/aaaa e avisa com 'change'
window.uiDateField = (inp, kind = 'date') => {
  if (!inp || inp._ud) return; inp._ud = true;
  const P = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  let v = P.get.call(inp) || inp.getAttribute('value') || '';
  inp.type = 'text'; inp.readOnly = true; inp.setAttribute('inputmode', 'none'); inp.classList.add('ud-in');
  const show = () => P.set.call(inp, v ? dataBR(v) : '');
  Object.defineProperty(inp, 'value', { configurable: true, get: () => v, set: (x) => { v = x || ''; show(); } });
  show();
  const lbl = () => (inp.closest('label')?.querySelector('span')?.textContent || inp.closest('label')?.firstChild?.textContent || '').trim();
  const open = async () => {
    if (inp.disabled) return;
    const x = await uiCalendar(v, { min: inp.getAttribute('min') || '', max: inp.getAttribute('max') || '', kind, title: lbl(), empty: inp.dataset.empty || '' });
    if (x != null && x !== v) { inp.value = x; inp.dispatchEvent(new Event('change', { bubbles: true })); }
  };
  inp.addEventListener('click', open);
  inp.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
};
// todo campo de data/mês do site (Comparar, gráfico, Carteira, Previsão) usa o calendário do site, inclusive os criados depois
if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined') {
  const Q = 'input[type=date],input[type=month]', up = (n) => { if (n.matches && n.matches(Q)) uiDateField(n, n.type); else if (n.querySelectorAll) n.querySelectorAll(Q).forEach(i => uiDateField(i, i.type)); };
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => n.nodeType === 1 && up(n)))).observe(document.documentElement, { childList: true, subtree: true });
  up(document); document.addEventListener('DOMContentLoaded', () => up(document));
}
window.uiChoose = (msg, options) => new Promise((res) => {
  const w = document.createElement('div'); w.className = 'umod';
  w.innerHTML = `<div class="umod-box" role="dialog" aria-modal="true"><p></p><div class="umod-list">${options.map((o, i) => `<button type="button" data-i="${i}">${o.label}</button>`).join('')}</div><div class="umod-btns"><button type="button" class="umod-c">Cancelar</button></div></div>`;
  w.querySelector('p').textContent = msg; document.body.appendChild(w);
  w.addEventListener('click', (e) => { const b = e.target.closest('[data-i]'); if (b) { w.remove(); res(options[+b.dataset.i].value); } else if (e.target === w || e.target.closest('.umod-c')) { w.remove(); res(null); } });
});
// Média simples dos fechamentos diários dos últimos n meses (a partir do último pregão). t em segundos.
window.avgLastMonths = function (t, c, n) {
  if (!t || !t.length) return null;
  const d = new Date(t[t.length - 1] * 1000), day = d.getUTCDate();
  d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() - n);
  const dim = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(day, dim));
  const cut = d.getTime() / 1000; let s = 0, k = 0;
  for (let i = 0; i < t.length; i++) if (t[i] > cut && c[i] != null) { s += c[i]; k++; }
  return k ? s / k : null;
};
// JSON com novas tentativas: servidor recém-iniciado pode demorar; tenta até `tries` vezes (cada uma com `ms` de limite). Falhou tudo -> null.
window.getRetry = async function (u, tries = 3, ms = 15000) {
  for (let k = 0; k < tries; k++) {
    const ac = new AbortController(), h = setTimeout(() => ac.abort(), ms);
    try { const r = await fetch(u, { signal: ac.signal }); if (r.ok) return await r.json(); if (r.status < 500 && r.status !== 202) return null; } catch (e) { } finally { clearTimeout(h); }
    if (k < tries - 1) await new Promise(res => setTimeout(res, 1500));
  }
  return null;
};
// Explicação de um termo lida do Glossário do painel ⓘ (fonte única; o chat lê o mesmo texto). null se não houver.
window.glossOf = function (term) {
  const li = [...document.querySelectorAll('#infoModal details')].find(d => (d.querySelector('summary') || {}).textContent === 'Glossário');
  const it = li && [...li.querySelectorAll('li')].find(x => (x.querySelector('b') || {}).textContent === term);
  if (!it) return null;
  const c = (it.querySelector('.gl-short') || it).cloneNode(true); c.querySelectorAll('.chat-only').forEach(x => x.remove());  // .gl-short: resumo do popup (o texto completo fica no painel)  // detalhe escondido: só o chat lê
  return c.textContent.trim();
};
window.glossMore = (term) => { const li = [...document.querySelectorAll('#infoModal details li')].find(x => (x.querySelector('b') || {}).textContent === term); return !!(li && li.querySelector('.gl-short')); };
window.glossBtn = (term) => glossOf(term) ? `<button type="button" class="gl-i" data-gl="${esc(term)}" aria-label="O que é ${esc(term)}">ⓘ</button>` : '';
// Ícone de arquivo (down = exportar, senão importar) e download de .json — Exportar/Importar de Grupos e Carteira.
window.fileIc = (down) => `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>${down ? '<path d="M12 11v6m-3-3 3 3 3-3"/>' : '<path d="M12 17v-6m-3 3 3-3 3 3"/>'}</svg>`;
// Baixa um arquivo de texto (Exportar, CSV). No app Android (android/, window.JGApp) o próprio app grava em Downloads: o WebView não baixa blob:.
window.saveFile = function (text, name, type) {
  if (window.JGApp && window.JGApp.saveFile) { try { window.JGApp.saveFile(name, type, text); return; } catch (e) { } }
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
};
window.saveJSON = (obj, prefix) => saveFile(JSON.stringify(obj, null, 1), prefix + '-' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.json', 'application/json');
// Nomes de versão comparados por número em cada parte ("1.10" > "1.9"; nunca como texto). Mesma regra de UpdateLogic.cmpName (app).
window.verCmp = (a, b) => {
  const x = String(a || '').trim().split('.'), y = String(b || '').trim().split('.'), n = (s) => parseInt((String(s).match(/\d+/) || ['0'])[0], 10);
  for (let k = 0; k < Math.max(x.length, y.length); k++) { const p = k < x.length ? n(x[k]) : 0, q = k < y.length ? n(y[k]) : 0; if (p !== q) return p < q ? -1 : 1; }
  return 0;
};
if (typeof module !== 'undefined') module.exports = { avgLastMonths: window.avgLastMonths, verCmp: window.verCmp };

// Volta ao app: < 10 min fora não faz nada. >= 10 min: atualiza os dados em segundo plano mantendo aba, cards e rolagem;
// só recarrega a página se saiu versão nova, e restaura aba + rolagem depois (sessionStorage).
if (typeof document !== 'undefined') (function () {
  const mine = [...document.scripts].map(x => x.src).filter(x => x.includes('/static/')).join('|');
  const RK = 'screenerB3.restore.v1';
  try { const r = JSON.parse(sessionStorage.getItem(RK) || 'null'); sessionStorage.removeItem(RK);
    if (r && Date.now() - r.at < 120000) { let n = 0; const go = () => { window.scrollTo(0, r.y); if (Math.abs(window.scrollY - r.y) > 5 && ++n < 40) setTimeout(go, 250); }; setTimeout(go, 300); } } catch (e) { }
  let hiddenAt = 0, busy = false;
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'hidden') { hiddenAt = Date.now(); return; }
    if (busy || !hiddenAt || Date.now() - hiddenAt < 10 * 60 * 1000) return; busy = true;
    const y = window.scrollY;
    try {
      const h = await (await fetch('/', { cache: 'no-store' })).text(); const vs = [...h.matchAll(/src="(\/static\/[^"]+)"/g)].map(m => location.origin + m[1]).join('|');
      if (vs && mine && vs !== mine) { try { sessionStorage.setItem(RK, JSON.stringify({ y, at: Date.now() })); } catch (e) { } location.reload(); return; }
      if (typeof window.load === 'function') { await window.load(); requestAnimationFrame(() => window.scrollTo(0, y)); }
    } catch (e) { }
    busy = false;
  });
})();

// App instalável (manifesto + service worker): iPhone e computador instalam pelo navegador; no Android o app é o APK (/app.apk, com widget),
// então o site não deixa o Chrome oferecer a instalação dele. Dentro do app (window.JGApp) as opções de instalar somem (classe in-app).
if (typeof window !== 'undefined' && window.addEventListener) {
  if (window.JGApp) document.documentElement.classList.add('in-app');
  // App até a 1.13 (JGInvestingApp/x no user agent): a oferta nativa podia não aparecer (trava de 10 min, "Depois" de 24 h).
  // O site confere /app/version.json ao abrir e ao voltar e oferece baixar pelo navegador (dl: mesmo APK fora deste endereço).
  const av = (navigator.userAgent.match(/JGInvestingApp\/([\d.]+)/) || [])[1];
  if (av && window.verCmp(av, '1.14') < 0) {
    let asked = '';
    const check = async () => {
      try {
        const v = await (await fetch('/app/version.json?t=' + Date.now(), { cache: 'no-store' })).json();
        if (!v || !v.versionName || !v.dl || window.verCmp(v.versionName, av) <= 0 || asked === v.versionName || document.querySelector('.umod')) return;
        asked = v.versionName;
        if (await uiConfirm(`Instalada: ${av}. O navegador baixa o arquivo; depois toque nele para instalar por cima (mantém seus dados).`, { title: `Nova versão do app (${v.versionName})`, ok: 'Baixar', cancel: 'Depois' }))
          location.href = v.dl;  // outro endereço: o app abre no navegador
      } catch (e) { }
    };
    setTimeout(check, 2500); document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') setTimeout(check, 1500); });
  }
  else if (/Android/i.test(navigator.userAgent)) window.addEventListener('beforeinstallprompt', (e) => e.preventDefault());
}
if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && typeof window !== 'undefined' && window.addEventListener)
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => { }));
