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

// Diálogos do site (substituem confirm/alert/prompt), toast e animação de carregamento
(function () {
  function modal({ title, msg, input, okText = 'OK', cancelText = 'Cancelar', danger = false, noCancel = false, value = '' }) {
    return new Promise((res) => {
      const w = document.createElement('div'); w.className = 'umod';
      w.innerHTML = `<div class="umod-box" role="dialog" aria-modal="true">${title ? `<h3>${title}</h3>` : ''}<p></p>
        ${input ? '<input class="umod-in" autocomplete="off" spellcheck="false" maxlength="40">' : ''}
        <div class="umod-btns">${noCancel ? '' : `<button type="button" class="umod-c">${cancelText}</button>`}<button type="button" class="umod-ok${danger ? ' dan' : ''}">${okText}</button></div></div>`;
      w.querySelector('p').textContent = msg || '';
      document.body.appendChild(w);
      const inp = w.querySelector('.umod-in'); if (inp) { inp.value = value; setTimeout(() => { inp.focus(); inp.select(); }, 30); } else setTimeout(() => w.querySelector('.umod-ok').focus(), 30);
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
  window.uiAlert = (msg, o = {}) => modal({ msg, title: o.title, noCancel: true });
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
  return it ? it.textContent.trim() : null;
};
window.glossBtn = (term) => glossOf(term) ? `<button type="button" class="gl-i" data-gl="${esc(term)}" aria-label="O que é ${esc(term)}">ⓘ</button>` : '';
// Ícone de arquivo (down = exportar, senão importar) e download de .json — Exportar/Importar de Grupos e Carteira.
window.fileIc = (down) => `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>${down ? '<path d="M12 11v6m-3-3 3 3 3-3"/>' : '<path d="M12 17v-6m-3 3 3-3 3 3"/>'}</svg>`;
window.saveJSON = function (obj, prefix) {
  const blob = new Blob([JSON.stringify(obj, null, 1)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = prefix + '-' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.json';
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
};
if (typeof module !== 'undefined') module.exports = { avgLastMonths: window.avgLastMonths };

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

// App instalável (manifesto + service worker): no celular, "Instalar app" / "Adicionar à tela inicial" (passo a passo no painel ⓘ)
if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && typeof window !== 'undefined' && window.addEventListener)
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => { }));
