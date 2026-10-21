// ---------- Indicadores criados pelo usuário (aba Mercado → + Indicadores → Criar indicador) ----------
// Fórmula como no Excel, com indicadores no lugar das células: "(P/VP / 2) * 3", "[ROE] * [Payout] / 100". O indicador entra pelo nome
// (rótulo, sigla ou chave de /api/data → fields; entre colchetes ou não) ou tocando no card dele na janela. Guardado no aparelho
// (screenerB3.indicadores.v1): {id, n nome, f fórmula, m 'sub' substitui k | 'novo' indicador novo | 'sep' só no quadro dos criados, d direção, u unidade}.
// app.js lê daqui: val() (CI.of/CI.calc), campos de filtro/Ordenar/cards (CI.fields), quadro "Indicadores criados" do card (CI.cardHtml).
(function () {
  const KEY = 'screenerB3.indicadores.v1';
  let L = (() => { try { const x = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(x) ? x : []; } catch (e) { return []; } })();
  let ver = 1, base = null;  // ver: muda a cada alteração (cache dos valores); base: fields originais de /api/data
  const nkey = (c) => 'ci_' + c.id;

  // --- fórmula: números (2 / 2,5 / 2.5), + − * / ^, parênteses e indicadores -> árvore {n} | {r: chave} | {o, a, b} | {neg}
  function nomes() {  // nomes aceitos de cada indicador (sem acento, minúsculos), os mais compridos primeiro
    const out = [];
    for (const f of base || []) for (const x of [f.label, f.short, f.key]) if (x) out.push([norm(x), f.key]);
    for (const c of L) if (c.m === 'novo') out.push([norm(c.n), nkey(c)]);
    return out.sort((a, b) => b[0].length - a[0].length);
  }
  function parse(txt) {
    const s = norm(txt), N = nomes(); let i = 0;
    const sp = () => { while (s[i] === ' ' || s[i] === '\n' || s[i] === '\t') i++; };
    const ref = () => {
      if (s[i] === '[') { const j = s.indexOf(']', i); if (j < 0) throw 'Falta fechar o colchete ]'; const t = s.slice(i + 1, j).trim(), m = N.find(x => x[0] === t); if (!m) throw `Indicador não encontrado: ${t}`; i = j + 1; return { r: m[1] }; }
      const m = N.find(x => x[0] && s.startsWith(x[0], i) && !/[a-z0-9]/.test(s[i + x[0].length] || ' ')); if (m) { i += m[0].length; return { r: m[1] }; }
      return null;
    };
    function prim() {
      sp();
      if (s[i] === '(') { i++; const e = expr(); sp(); if (s[i] !== ')') throw 'Falta fechar o parêntese )'; i++; return e; }
      if (s[i] === '-' || s[i] === '+') { const g = s[i++] === '-'; const e = pot(); return g ? { neg: e } : e; }
      const m = /^\d+(?:[.,]\d+)?/.exec(s.slice(i)); if (m) { i += m[0].length; return { n: parseFloat(m[0].replace(',', '.')) }; }
      const r = ref(); if (r) return r;
      throw i >= s.length ? 'A fórmula terminou antes da hora' : `Não entendi a partir de "${txt.slice(i, i + 12)}"`;
    }
    function pot() { const a = prim(); sp(); if (s[i] === '^') { i++; return { o: '^', a, b: pot() }; } return a; }
    function termo() { let a = pot(); for (;;) { sp(); const o = s[i]; if (o !== '*' && o !== '/' && o !== 'x') return a; if (o === 'x' && /[a-z]/.test(s[i + 1] || '')) return a; i++; a = { o: o === 'x' ? '*' : o, a, b: pot() }; } }
    function expr() { let a = termo(); for (;;) { sp(); const o = s[i]; if (o !== '+' && o !== '-') return a; i++; a = { o, a, b: termo() }; } }
    if (!s.trim()) throw 'Escreva a fórmula';
    const e = expr(); sp(); if (i < s.length) throw `Não entendi a partir de "${txt.slice(i, i + 12)}"`;
    return e;
  }
  const refs = (e, o = new Set()) => { if (e.r) o.add(e.r); for (const k of ['a', 'b', 'neg']) if (e[k]) refs(e[k], o); return o; };
  function ev(e, r, d) {
    if (e.n != null) return e.n;
    if (e.r) { const c = e.r.startsWith('ci_') && L.find(x => nkey(x) === e.r); return c ? calc(r, c, d + 1) : window.val0(r, e.r); }  // indicador substituído entra com o valor original
    if (e.neg) { const x = ev(e.neg, r, d); return x == null ? null : -x; }
    const a = ev(e.a, r, d), b = ev(e.b, r, d); if (a == null || b == null) return null;
    const v = e.o === '+' ? a + b : e.o === '-' ? a - b : e.o === '*' ? a * b : e.o === '/' ? (b === 0 ? null : a / b) : Math.pow(a, b);
    return v == null || !Number.isFinite(v) ? null : v;
  }
  const tree = {};  // id -> árvore da fórmula (refeita quando muda)
  function calc(r, c, d = 0) {
    if (d > 8) return null;
    const ck = ver + '|' + state.source; if (!r._ci || r._ci.k !== ck) r._ci = { k: ck, v: {} };
    if (c.id in r._ci.v) return r._ci.v[c.id];
    let v = null; try { const t = tree[c.id] || (tree[c.id] = parse(c.f)); v = ev(t, r, d); } catch (e) { v = null; }
    return (r._ci.v[c.id] = v);
  }
  // indicador que responde por uma chave: substituto (m 'sub') ou indicador novo ('ci_…')
  const of = (k) => L.find(c => (c.m === 'sub' && c.k === k) || (c.m === 'novo' && nkey(c) === k)) || null;
  // campos de /api/data com os criados: substituto fica com a chave e o lugar do original (marcado como criado); novo entra no fim e em Ordenar
  function fields(f0) {
    base = f0; const mx = Math.max(0, ...f0.map(f => f.sort || 0));
    const out = f0.map(f => { const c = L.find(x => x.m === 'sub' && x.k === f.key); return c ? Object.assign({}, f, { ci: c.id, label: f.label + ' (criado)', short: (f.short || f.label) + ' ✎', dir: c.d || f.dir, unit: c.u ?? f.unit, grp: null }) : f; });
    L.filter(c => c.m === 'novo').forEach((c, j) => out.push({ key: nkey(c), label: c.n + ' (criado)', short: c.n + ' ✎', unit: c.u || '', dir: c.d || 'high', sort: mx + 1 + j, ci: c.id }));
    return out;
  }
  // quadro "Indicadores criados" no card da empresa: os que não substituem nem acrescentam e o valor original dos substituídos
  function cardHtml(r) {
    const it = L.filter(c => c.m === 'sep').map(c => [c.n, calc(r, c), c.u, 'criado']).concat(
      L.filter(c => c.m === 'sub').map(c => { const f = (base || []).find(x => x.key === c.k); return f && [f.label, window.val0(r, c.k), f.unit, 'original', f.key]; }).filter(Boolean));
    if (!it.length) return '';
    return `<div class="ci-box"><div class="ci-h">Indicadores criados</div><div class="cards">${it.map(([n, v, u, t, k]) => `<div class="card${v == null ? ' na' : v < 0 ? ' neg' : ''}"><div class="lbl"><span class="truncate" title="${esc(n)}">${esc(n)}</span><span class="badge ci-${t === 'criado' ? 'c' : 'o'}">${t}</span></div><div class="val">${v == null ? '—' : fmt(v, u, k, r.cur)}</div></div>`).join('')}</div></div>`;
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(L)); } catch (e) { uiAlert('Não foi possível salvar no aparelho.'); } ver++; for (const k in tree) delete tree[k]; listHtml(); window.refreshFields && window.refreshFields(); };

  // --- janela Criar/Editar indicador
  const MODO = [['novo', 'Adicionar como indicador novo (todas as empresas, filtros e Ordenar)'], ['sub', 'Substituir um indicador'], ['sep', 'Só no quadro "Indicadores criados"']];
  async function editar(c0) {
    if (!base) return;
    const c = Object.assign({ n: '', f: '', m: 'novo', k: '', d: 'high', u: '' }, c0 || {}), fs = base;
    const L1 = (t, h, x = '') => `<div class="ci-l"${x}><span>${t}</span>${h}</div>`;  // campo com o nome em cima
    const html = `<div class="ci-f${c.m === 'sub' ? '' : ' ci-nosub'}">
      ${L1('Nome', `<input class="pv-in" id="ciN" maxlength="40" value="${esc(c.n)}" placeholder="Ex.: Meu ROE">`)}
      ${L1('Fórmula', `<textarea class="pv-in" id="ciF" rows="3" placeholder="Ex.: (P/VP / 2) * 3">${esc(c.f)}</textarea>`)}
      <p class="pvd-note">Use + − * / ^ e parênteses. Toque num indicador para pôr na fórmula ou escreva o nome (entre colchetes quando tiver espaço: [Dív. líq./EBITDA]).</p>
      <div class="ci-chips">${fs.map(f => `<button type="button" class="gbtn" data-ciins="${esc(f.short || f.label)}">${esc(f.short || f.label)}</button>`).join('')}${L.filter(x => x.m === 'novo' && x.id !== c.id).map(x => `<button type="button" class="gbtn" data-ciins="${esc(x.n)}">${esc(x.n)} ✎</button>`).join('')}</div>
      <p class="pvd-note" id="ciP"></p>
      ${L1('Uso', `<select class="pv-in" id="ciM">${MODO.map(([k, l]) => `<option value="${k}"${c.m === k ? ' selected' : ''}>${l}</option>`).join('')}</select>`)}
      ${L1('Substitui', `<select class="pv-in" id="ciK">${fs.map(f => `<option value="${f.key}"${c.k === f.key ? ' selected' : ''}>${esc(f.label)}</option>`).join('')}</select>`, ' data-cisub')}
      <div class="ci-2">${L1('Melhor', `<select class="pv-in" id="ciD"><option value="high"${c.d === 'high' ? ' selected' : ''}>Maior é melhor</option><option value="low"${c.d === 'low' ? ' selected' : ''}>Menor é melhor</option></select>`)}
      ${L1('Unidade', `<select class="pv-in" id="ciU"><option value=""${!c.u ? ' selected' : ''}>Número</option><option value="%"${c.u === '%' ? ' selected' : ''}>% (8 = 8%)</option></select>`)}</div>
      <p class="umod-err"></p></div>`;
    const ok = await uiForm(c0 ? 'Editar indicador' : 'Criar indicador', html, (w) => {
      const g = (id) => w.querySelector('#' + id).value, n = g('ciN').trim(), f = g('ciF').trim(), m = g('ciM'), k = g('ciK');
      if (!n) return { erro: 'Dê um nome ao indicador.' };
      try { const t = parse(f); if (m === 'sub' && refs(t).has(k)) { /* usa o original: permitido */ } } catch (e) { return { erro: 'Fórmula: ' + e }; }
      if (m === 'sub' && L.some(x => x.m === 'sub' && x.k === k && x.id !== c.id)) return { erro: 'Esse indicador já foi substituído por outro criado.' };
      if (L.some(x => norm(x.n) === norm(n) && x.id !== c.id)) return { erro: 'Já existe um indicador criado com esse nome.' };
      return { n, f, m, k: m === 'sub' ? k : '', d: g('ciD'), u: g('ciU') };
    });
    if (!ok) return;
    if (c0) Object.assign(L.find(x => x.id === c0.id), ok); else L.push(Object.assign({ id: Date.now().toString(36) }, ok));
    save(); uiToast(c0 ? 'Indicador atualizado' : 'Indicador criado');
  }
  // prévia da fórmula com 3 empresas da lista, enquanto digita
  function preview(w) {
    const p = w.querySelector('#ciP'), f = w.querySelector('#ciF').value; if (!p) return;
    w.querySelector('#ciK').closest('.ci-f').classList.toggle('ci-nosub', w.querySelector('#ciM').value !== 'sub');
    if (!f.trim()) { p.textContent = ''; return; }
    try { const t = parse(f), rs = (state.filtered.length ? state.filtered : state.rows).slice(0, 3); p.textContent = 'Exemplo: ' + rs.map(r => `${r.ticker} = ${(v => v == null ? '—' : F2.format(v))(ev(t, r, 0))}`).join(' · '); }
    catch (e) { p.textContent = 'Fórmula: ' + e; }
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-ciins]');
    if (b) { const ta = b.closest('.umod-box').querySelector('#ciF'), t = b.dataset.ciins, x = /[\s]/.test(t) ? `[${t}]` : t, p = ta.selectionStart ?? ta.value.length;
      ta.value = ta.value.slice(0, p) + x + ta.value.slice(ta.selectionEnd ?? p); ta.focus(); ta.selectionStart = ta.selectionEnd = p + x.length; preview(b.closest('.umod-box')); return; }
    const a = e.target.closest('[data-ci]'); if (!a) return;
    const c = L.find(x => x.id === a.dataset.id);
    if (a.dataset.ci === 'novo') editar(null);
    else if (a.dataset.ci === 'edit' && c) editar(c);
    else if (a.dataset.ci === 'del' && c) uiConfirm(`Excluir o indicador "${c.n}"?`, { ok: 'Excluir', danger: true }).then(y => { if (y) { L = L.filter(x => x !== c); save(); } });
  });
  document.addEventListener('input', (e) => { if (e.target.id === 'ciF') preview(e.target.closest('.umod-box')); });
  document.addEventListener('change', (e) => { if (e.target.id === 'ciM') preview(e.target.closest('.umod-box')); });
  // lista em + Indicadores: botão Criar indicador e os criados (Editar/Excluir)
  const USO = { novo: 'indicador novo', sub: 'substitui', sep: 'só no quadro dos criados' };
  function listHtml() {
    const el = document.getElementById('ciList'); if (!el) return;
    el.innerHTML = `<button type="button" class="gbtn pri" data-ci="novo">Criar indicador</button>` + L.map(c => {
      const f = c.m === 'sub' && (base || []).find(x => x.key === c.k);
      return `<div class="ci-it"><b>${esc(c.n)}</b> <span class="badge ci-c">criado</span><span class="gsub">${esc(c.f)} · ${USO[c.m]}${f ? ' ' + esc(f.label) : ''}</span>
        <button type="button" class="gbtn" data-ci="edit" data-id="${c.id}">Editar</button><button type="button" class="gbtn dan" data-ci="del" data-id="${c.id}">Excluir</button></div>`;
    }).join('');
  }
  window.CI = { of, calc: (r, c) => calc(r, c), fields, cardHtml, listHtml, parse };
})();
