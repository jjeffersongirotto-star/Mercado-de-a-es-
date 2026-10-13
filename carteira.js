// ---------- Carteira (posições salvas no aparelho + exportar/importar .json) ----------
// Preço atual: mesma linha de /api/data dos cards (priceOf). Proventos: /api/history (por ação, desde a data).
// Comparação: quanto o mesmo valor renderia no Ibovespa e no CDB desde a data de cada posição (/api/idxret).
(function () {
  const KEY = 'screenerB3.carteira.v1';
  const $k = (s) => document.querySelector(s);
  const pane = () => $k('[data-tabpane="carteira"]');
  let pos = (() => { try { const p = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(p) ? p : []; } catch (e) { return []; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(pos)); } catch (e) { uiAlert('Não foi possível salvar no navegador.'); } };
  const today = new Date().toISOString().slice(0, 10);
  const DIV = {}, IDX = {};  // cache por ticker / por data
  let editing = -1;

  const cls = (v) => v > 0 ? 'up' : v < 0 ? 'dn' : '';
  const money = (v) => v == null ? '—' : brl.format(v);
  const pct = (v) => v == null ? '' : `<span class="${cls(v)}">${pc(v)}</span>`;

  async function provs(t) {  // proventos por ação [[epoch, valor]]
    if (!DIV[t]) DIV[t] = getRetry(`/api/history/${encodeURIComponent(t)}`).then(h => (h && h.div) || []);
    return DIV[t];
  }
  async function idx(d) {
    if (!IDX[d]) IDX[d] = getRetry(`/api/idxret?di=${d}&df=${today}`).then(x => x || {});
    return IDX[d];
  }

  function form() {
    const p = pos[editing] || {};
    const tk = state.country === 'br' && state.data ? state.data.rows.filter(r => !r.il).map(r => r.ticker).sort() : [];
    return `<form id="ktF" class="kt-f" autocomplete="off">
      <label>Ticker<input id="ktT" class="pv-in" list="ktL" required maxlength="12" value="${esc(p.t || '')}" placeholder="PETR4"></label>
      <label>Quantidade<input id="ktQ" class="pv-in" inputmode="decimal" required value="${p.q != null ? F0.format(p.q) : ''}"></label>
      <label>Preço médio<input id="ktP" class="pv-in" inputmode="decimal" required value="${p.pm != null ? F2.format(p.pm) : ''}"></label>
      <label>Data<input id="ktD" class="pv-in" type="date" required max="${today}" value="${esc(p.d || today)}"></label>
      <div class="kt-fb"><button type="submit" class="gbtn pri">${editing >= 0 ? 'Salvar' : '＋ Adicionar'}</button>${editing >= 0 ? '<button type="button" class="gbtn" data-k="cancel">Cancelar</button><button type="button" class="gbtn dan" data-k="del">Excluir</button>' : ''}</div>
      <datalist id="ktL">${tk.map(t => `<option value="${t}">`).join('')}</datalist></form>`;
  }

  async function render() {
    const root = $k('#carteiraRoot');
    if (state.country !== 'br') {
      root.innerHTML = `<section class="kt-box"><p>A Carteira usa as ações da B3.</p><button type="button" class="gbtn pri" data-k="br">Mudar para Brasil</button></section>`;
      return;
    }
    if (!state.data) { root.innerHTML = loaderHTML('Carregando dados…'); return; }
    const head = `<div class="flex flex-wrap items-center gap-2">
        <button type="button" class="gbtn" data-k="export" title="Exportar carteira" aria-label="Exportar carteira">${fileIc(1)}<span class="max-sm:hidden">Exportar</span></button>
        <button type="button" class="gbtn" data-k="import" title="Importar carteira" aria-label="Importar carteira">${fileIc(0)}<span class="max-sm:hidden">Importar</span></button>
        <input id="ktFile" type="file" accept=".json,application/json,text/plain,*/*" class="hidden"></div>`;
    root.innerHTML = `<section class="space-y-2">${head}<div class="kt-box">${form()}</div><div id="ktBody">${pos.length ? loaderHTML('Calculando…') : '<p class="text-slate-400 text-sm">Nenhuma posição. Preencha ticker, quantidade, preço médio e data e toque em ＋ Adicionar.</p>'}</div></section>`;
    $k('#ktFile').addEventListener('change', importK);
    if (pos.length) body();
  }

  async function body() {
    const rm = state.rowMap || {};
    const L = await Promise.all(pos.map(async (p) => {
      const r = rm[p.t], price = r ? priceOf(r) : null;
      const ts = Date.parse(p.d + 'T00:00:00Z') / 1000;
      const div = (await provs(p.t)).filter(x => x[0] >= ts).reduce((a, x) => a + x[1], 0) * p.q;
      const ix = await idx(p.d);
      const inv = p.q * p.pm, cur = price != null ? p.q * price : null;
      return { p, r, price, inv, cur, div, ibov: ix['@ibov'] != null ? inv * (1 + ix['@ibov'] / 100) : null, cdi: ix['@cdi'] != null ? inv * (1 + ix['@cdi'] / 100) : null };
    }));
    const el = $k('#ktBody'); if (!el) return;
    const sum = (k) => L.some(x => x[k] == null) ? null : L.reduce((a, x) => a + x[k], 0);
    const inv = sum('inv'), cur = sum('cur'), div = sum('div'), tot = cur != null ? cur + div : null;
    const g = (v, b) => v == null ? '—' : `${money(v - b)} ${pct((v / b - 1) * 100)}`;
    el.innerHTML = `<div class="kt-sum">
        <div><span>Investido</span><b>${money(inv)}</b></div>
        <div><span>Valor atual</span><b>${money(cur)}</b></div>
        <div><span>Ganho</span><b>${g(cur, inv)}</b></div>
        <div><span>Proventos recebidos</span><b>${money(div)}</b></div>
        <div><span>Total (ganho + proventos)</span><b>${g(tot, inv)}</b></div>
        <div><span>Se fosse no Ibovespa</span><b>${g(sum('ibov'), inv)}</b></div>
        <div><span>Se fosse no CDB</span><b>${g(sum('cdi'), inv)}</b></div></div>
      <div class="kt-wrap"><table class="kt-t"><thead><tr><th>Ativo</th><th>Qtd / PM</th><th>Atual</th><th>Ganho</th><th>Proventos</th></tr></thead><tbody>
      ${L.map((x, i) => `<tr data-k="edit" data-i="${i}"${i === editing ? ' class="on"' : ''}><td><b>${esc(x.p.t)}</b><small>${dataBR(x.p.d)}</small></td>
        <td>${F0.format(x.p.q)}<small>${F2.format(x.p.pm)}</small></td>
        <td>${x.price != null ? F2.format(x.price) : '—'}<small>${money(x.cur)}</small></td>
        <td>${x.cur != null ? `<span class="${cls(x.cur - x.inv)}">${money(x.cur - x.inv)}</span><small>${pct((x.cur / x.inv - 1) * 100)}</small>` : '—'}</td>
        <td>${money(x.div)}</td></tr>`).join('')}
      </tbody></table></div>
      <p class="text-slate-500 text-xs">Preço atual da aba Ações (fonte escolhida no topo). Proventos desde a data da posição. Ibovespa e CDB: o mesmo valor investido na mesma data. Toque numa posição para editar ou excluir.</p>`;
  }

  async function submit(e) {
    e.preventDefault();
    const t = $k('#ktT').value.toUpperCase().trim(), q = parseBR($k('#ktQ').value), pm = parseBR($k('#ktP').value), d = $k('#ktD').value;
    if (!state.rowMap[t]) return uiAlert(`Ticker ${t} não encontrado na lista de ações.`);
    if (!(q > 0) || !(pm > 0) || !d) return uiAlert('Preencha quantidade, preço médio e data.');
    const p = { t, q, pm, d: d > today ? today : d };
    if (editing >= 0) pos[editing] = p; else pos.push(p);
    editing = -1; pos.sort((a, b) => a.t.localeCompare(b.t) || a.d.localeCompare(b.d)); save(); render();
  }

  async function importK(e) {
    const f = e.target.files[0]; if (!f) return;
    try {
      const d = JSON.parse(await f.text()); const arr = Array.isArray(d) ? d : d.carteira;
      if (!Array.isArray(arr)) throw new Error('arquivo sem carteira');
      const ok = arr.filter(p => p && typeof p.t === 'string' && p.q > 0 && p.pm > 0 && /^\d{4}-\d{2}-\d{2}$/.test(p.d)).map(p => ({ t: p.t.toUpperCase().trim(), q: +p.q, pm: +p.pm, d: p.d }));
      if (pos.length && !(await uiConfirm(`Substituir as ${pos.length} posições atuais pelas ${ok.length} do arquivo?`, { ok: 'Substituir', danger: true }))) { e.target.value = ''; return; }
      pos = ok; save(); render(); uiToast(ok.length + ' posição(ões) importada(s)');
    } catch (err) { uiAlert('Não foi possível importar: ' + err.message); }
    e.target.value = '';
  }

  pane().addEventListener('submit', (e) => { if (e.target.id === 'ktF') submit(e); });
  pane().addEventListener('click', async (e) => {
    const b = e.target.closest('[data-k]'); if (!b) return;
    const k = b.dataset.k, i = b.dataset.i != null ? +b.dataset.i : editing;
    if (k === 'export') saveJSON({ app: 'screener-b3', tipo: 'carteira', versao: 1, exportado: new Date().toISOString(), carteira: pos }, 'carteira-screener');
    else if (k === 'import') $k('#ktFile').click();
    else if (k === 'edit') { editing = i; render(); $k('#carteiraRoot').scrollIntoView({ block: 'start', behavior: 'smooth' }); }
    else if (k === 'cancel') { editing = -1; render(); }
    else if (k === 'del' && await uiConfirm(`Excluir ${pos[i].t} da carteira?`, { ok: 'Excluir', danger: true })) { pos.splice(i, 1); editing = -1; save(); render(); }
    else if (k === 'br') { const c = document.querySelector('#countryMenu [data-country="br"]'); if (c) c.click(); }
  });
  const visible = () => !pane().classList.contains('hidden');
  document.addEventListener('tabshow', (e) => { if (e.detail === 'carteira') render(); });
  document.addEventListener('dataload', () => { if (visible()) render(); });
  if (visible()) render();
})();
