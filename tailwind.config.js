// Configuração única do Tailwind: usada pelo build (scripts/build_css.sh) e, sem o CSS gerado, pelo CDN no navegador.
const twConfig = {
  darkMode: 'class',
  content: ['./index.html', './*.js'],
};
if (typeof module !== 'undefined') module.exports = twConfig; else tailwind.config = twConfig;
