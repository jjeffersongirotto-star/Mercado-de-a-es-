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
