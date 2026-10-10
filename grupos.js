// ---------- Grupos (localStorage + exportar/importar .json) ----------
(function () {
  const KEY = 'screenerB3.grupos.v1';
  const $g = (s) => document.querySelector(s);
  const escH = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let groups = (() => { try { const g = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(g) ? g : []; } catch (e) { return []; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(groups)); } catch (e) { alert('Não foi possível salvar no navegador.'); } };
  state.selSet = new Set(); state.selMode = false; state.group = null;
  let editing = null, viewing = null;

  const VKEY = 'screenerB3.ordsetor.v1';
  try { const v = JSON.parse(localStorage.getItem(VKEY) || '{}'); state.ord2 = v.ord2 || ''; state.sector = v.sector || 'Todos'; } catch (e) { state.ord2 = ''; state.sector = 'Todos'; }
  const ORD = [['', 'Padrão (barra de filtros)'], ['valmerc:-1', 'Valor de mercado: maior → menor'], ['valmerc:1', 'Valor de mercado: menor → maior'],
    ['preco:-1', 'Preço da ação: maior → menor'], ['preco:1', 'Preço da ação: menor → maior'], ['var:-1', 'Alta do dia: maior → menor'], ['var:1', 'Alta do dia: menor → maior']];
  const toolsOld = () => `<div class="gtools"><label>Ordenar<select id="gOrd">${ORD.map(([v, l]) => `<option value="${v}"${v === state.ord2 ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
    <label>Setor<select id="gSec">${['Todos'].concat(SECTORS).map(x => `<option${x === state.sector ? ' selected' : ''}>${escH(x)}</option>`).join('')}</select></label></div>`;
  const tools = () => '';
  state.ord2 = '';
  $g('#gSec').innerHTML = ['Todos'].concat(SECTORS).map(x => `<option${x === state.sector ? ' selected' : ''}>${escH(x)}</option>`).join('');
  document.addEventListener('change', (e) => {
    if (e.target.id !== 'gOrd' && e.target.id !== 'gSec') return;
    if (e.target.id === 'gOrd') state.ord2 = e.target.value; else state.sector = e.target.value;
    try { localStorage.setItem(VKEY, JSON.stringify({ ord2: state.ord2, sector: state.sector })); } catch (er) { }
    if (state.data) apply();
  });
  document.addEventListener('input', (e) => {
    if (e.target.id !== 'gQ') return;
    $g('#q').value = e.target.value; if (state.data) apply();
  });
  function bar() {
    const b = $g('#gBar');
    if (state.selMode) {
      b.innerHTML = `<div class="gbar mb-2"><b class="text-emerald-300 text-sm">${state.selSet.size} selecionada(s)</b>
        <input id="gName" maxlength="40" placeholder="Nome do grupo" value="${escH(editing ? editing.name : '')}" class="flex-1 min-w-[140px] px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm">
        <button type="button" class="gbtn pri" data-g="save">Salvar</button><button type="button" class="gbtn" data-g="cancel">Cancelar</button>
        <input id="gQ" type="search" placeholder="Buscar empresa, setor ou atividade (ex.: gasol)…" value="${escH($g('#q').value)}" class="basis-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none text-sm"></div>${tools()}`;
    } else if (viewing) {
      b.innerHTML = `<div class="gbar mb-2"><button type="button" class="gbtn" data-g="back">← Grupos</button>
        <b class="text-emerald-300">${escH(viewing.name)}</b><span class="text-xs text-slate-400">${viewing.tickers.length} empresa(s)</span>
        <button type="button" class="gbtn ml-auto" data-g="edit" data-n="${escH(viewing.name)}">Editar</button></div>${tools()}`;
    } else b.innerHTML = '';
  }
  function refresh() { bar(); if (typeof apply === 'function' && state.data) apply(); }
  function startSel(g) {
    editing = g || null; state.selMode = true; state.selSet = new Set(g ? g.tickers : []);
    viewing = null; state.group = null; markTab(); showTab('acoes'); refresh();
  }
  function stopSel() { state.selMode = false; editing = null; state.selSet = new Set(); refresh(); }
  function openGroup(g) { viewing = g; state.group = new Set(g.tickers); state.selMode = false; showTab('acoes'); markTab(); refresh(); window.scrollTo(0, 0); }
  function markTab() { document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('on', viewing ? b.dataset.tab === 'grupos' : b.dataset.tab === 'acoes')); }

  document.addEventListener('change', (e) => {
    const c = e.target.closest('[data-gsel]'); if (!c) return;
    if (c.checked) state.selSet.add(c.dataset.gsel); else state.selSet.delete(c.dataset.gsel);
    const b = $g('#gBar b'); if (b) b.textContent = state.selSet.size + ' selecionada(s)';
  });
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-g]'); if (!b) return;
    const a = b.dataset.g, find = (n) => groups.find(g => g.name === n);
    if (a === 'new') startSel(null);
    else if (a === 'cancel') stopSel();
    else if (a === 'save') {
      const name = ($g('#gName').value || '').trim();
      if (!name) { alert('Dê um nome ao grupo.'); $g('#gName').focus(); return; }
      if (!state.selSet.size) { alert('Selecione pelo menos uma empresa.'); return; }
      const other = find(name);
      if (other && other !== editing && !confirm(`Já existe um grupo "${name}". Substituir?`)) return;
      groups = groups.filter(g => g !== other && g !== editing);
      groups.push({ name, tickers: [...state.selSet].sort(), updated: new Date().toISOString() });
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save();
      state.selMode = false; editing = null; state.selSet = new Set(); bar(); showTab('grupos');
    }
    else if (a === 'back') { viewing = null; state.group = null; refresh(); showTab('grupos'); }
    else if (a === 'open') openGroup(find(b.dataset.n));
    else if (a === 'edit') startSel(find(b.dataset.n));
    else if (a === 'del') { const g = find(b.dataset.n); if (g && confirm(`Excluir o grupo "${g.name}"?`)) { groups = groups.filter(x => x !== g); save(); list(); } }
    else if (a === 'export') exportG();
    else if (a === 'import') $g('#gFile').click();
  });

  function list() {
    const r = $g('#gruposRoot');
    r.innerHTML = `<section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-3 sm:p-4 space-y-3">
      <div class="flex flex-wrap items-center gap-2"><h2 class="text-base font-bold mr-auto">Meus grupos</h2>
        <button type="button" class="gbtn pri" data-g="new">＋ Criar grupo</button>
        <button type="button" class="gbtn" data-g="export">⬇ Exportar grupos</button>
        <button type="button" class="gbtn" data-g="import">⬆ Importar grupos</button>
        <input id="gFile" type="file" accept=".json,application/json,text/plain,*/*" class="hidden"></div>
      <p class="text-[11px] text-slate-500">Os grupos ficam salvos neste navegador. Para levar a outro celular ou PC, use Exportar e depois Importar o arquivo lá.</p>
      ${groups.length ? `<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">${groups.map(g => `<div class="gcard space-y-2">
          <div class="flex items-center gap-2"><b class="text-slate-100 truncate">${escH(g.name)}</b><span class="text-xs text-slate-500 ml-auto">${g.tickers.length} empresa(s)</span></div>
          <div class="flex flex-wrap gap-1">${g.tickers.slice(0, 12).map(t => `<span class="gchip">${escH(t)}</span>`).join('')}${g.tickers.length > 12 ? `<span class="text-xs text-slate-500">+${g.tickers.length - 12}</span>` : ''}</div>
          <div class="flex flex-wrap gap-2"><button type="button" class="gbtn pri" data-g="open" data-n="${escH(g.name)}">Abrir</button>
            <button type="button" class="gbtn" data-g="edit" data-n="${escH(g.name)}">Editar / renomear</button>
            <button type="button" class="gbtn dan" data-g="del" data-n="${escH(g.name)}">Excluir</button></div></div>`).join('')}</div>`
        : '<div class="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">Nenhum grupo ainda. Toque em <b>＋ Criar grupo</b>, marque as empresas, dê um nome e salve.</div>'}
    </section>`;
    $g('#gFile').addEventListener('change', importG);
  }
  function exportG() {
    const blob = new Blob([JSON.stringify({ app: 'screener-b3', tipo: 'grupos', versao: 1, exportado: new Date().toISOString(), grupos: groups }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'grupos-screener-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  async function importG(e) {
    const f = e.target.files[0]; if (!f) return;
    try {
      const d = JSON.parse(await f.text()); const arr = Array.isArray(d) ? d : d.grupos;
      if (!Array.isArray(arr)) throw new Error('arquivo sem grupos');
      let n = 0;
      for (const g of arr) {
        if (!g || typeof g.name !== 'string' || !Array.isArray(g.tickers)) continue;
        let name = g.name.trim().slice(0, 40); const tk = [...new Set(g.tickers.map(t => String(t).toUpperCase().trim()).filter(Boolean))].sort();
        const ex = groups.find(x => x.name === name);
        if (ex) {
          if (ex.tickers.join() === tk.join()) continue;
          if (confirm(`O grupo "${name}" já existe. OK = substituir; Cancelar = importar como cópia.`)) groups = groups.filter(x => x !== ex);
          else { let i = 2; while (groups.some(x => x.name === `${name} (${i})`)) i++; name = `${name} (${i})`; }
        }
        groups.push({ name, tickers: tk, updated: g.updated || new Date().toISOString() }); n++;
      }
      groups.sort((x, y) => x.name.localeCompare(y.name, 'pt-BR')); save(); list();
      alert(n + ' grupo(s) importado(s).');
    } catch (err) { alert('Não foi possível importar: ' + err.message); }
    e.target.value = '';
  }

  document.addEventListener('tabshow', (e) => {
    if (e.detail === 'grupos') { list(); if (viewing || state.group) { viewing = null; state.group = null; refresh(); } }
    if (e.detail === 'acoes' && !state.selMode && viewing) { /* abrindo grupo */ }
  });
  document.querySelectorAll('[data-tab="acoes"]').forEach(b => b.addEventListener('click', () => { if (viewing && !state.selMode) { viewing = null; state.group = null; refresh(); } }));
  bar(); list();
})();
