// Teste de telas (roda no GitHub Actions em cada PR): abre o site no tamanho de celular, passa por todas as abas
// e falha se aparecer erro de JavaScript ou se uma aba não montar. Uso: node tests/ui_smoke.cjs [URL]
const { chromium } = require('playwright');
const URL = process.argv[2] || 'http://127.0.0.1:8000';

(async () => {
  const b = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const p = await b.newPage({ viewport: { width: 360, height: 780 } });
  const errs = [];
  p.on('pageerror', e => errs.push('JS: ' + e.message));
  p.on('response', r => { if (r.status() >= 500) errs.push(`HTTP ${r.status()} ${r.url()}`); });
  const ok = (cond, msg) => { if (!cond) errs.push(msg); console.log((cond ? 'ok   ' : 'FALHA ') + msg); };

  await p.goto(URL, { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#results > *', { timeout: 120000 }).catch(() => {});
  ok(await p.locator('#results > *').count() > 0, 'Ações: lista de empresas');
  const over = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  ok(over <= 1, 'Celular: sem rolagem horizontal');

  // todas as abas do menu (lidas da própria interface)
  for (const t of await p.$$eval('nav.tabs [data-tab]', a => a.map(x => x.dataset.tab))) {
    await p.click(`nav.tabs [data-tab="${t}"]`);
    const pane = p.locator(`[data-tabpane="${t}"]`);
    await p.waitForFunction(s => { const e = document.querySelector(s); return e && !e.classList.contains('hidden') && !e.querySelector('.ldr'); },
      `[data-tabpane="${t}"]`, { timeout: 60000 }).catch(() => {});
    ok(await pane.isVisible() && (await pane.innerText()).trim().length > 0, `Aba ${t}: montou`);
  }

  // chat responde sem IA
  await p.click('nav.tabs [data-tab="chat"]');
  await p.fill('#chtQ', 'maiores dividend yield');
  await p.click('#chtS');
  await p.waitForSelector('#chtL .cht-m.a', { timeout: 60000 }).catch(() => {});
  ok(await p.locator('#chtL .cht-m.a').count() > 0, 'Chat: respondeu');

  await b.close();
  if (errs.length) { console.error(errs.join('\n')); process.exit(1); }
  console.log('Telas ok');
})();
