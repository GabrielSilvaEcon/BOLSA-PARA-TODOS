// ETAPA 1 · linha de base da MESA (WebView) em Chromium headless (proxy: NÃO é um Android real; render por software).
// Uso: node medicao/mesa_chromium.js   (usa o Playwright já instalado). Só mede; não altera o jogo.
const { chromium } = require('playwright');
const path = require('path');
const URL = 'file://' + path.resolve(__dirname, '../trader_front/index.html');

const { args } = require('./mesa_args.js');

async function cenario(browser, nome, throttle, comEvento, T) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  await cdp.send('Performance.enable');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle });
  const t0 = Date.now();
  await p.goto(URL, { waitUntil: 'load' });
  const nav = await p.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; return { dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd) }; });
  const ini = await p.evaluate((a) => new Promise((res) => { const t = performance.now(); window.postMessage({ type: 'streamlit:render', args: a }, '*'); requestAnimationFrame(() => requestAnimationFrame(() => res(Math.round(performance.now() - t)))); }), args(T, comEvento));
  await p.waitForTimeout(800);
  const m0 = await cdp.send('Performance.getMetrics');
  const fps = await p.evaluate(() => new Promise((res) => { const t0 = performance.now(); let n = 0, lentos = 0, ult = t0, ft = []; function f(t) { n++; ft.push(t - ult); if (t - ult > 34) lentos++; ult = t; if (t - t0 < 5000) requestAnimationFrame(f); else { ft.sort((a, b) => a - b); res({ quadros: n, fps: +(n / ((t - t0) / 1000)).toFixed(1), quadros_lentos_gt34ms: lentos, quadro_p95_ms: +ft[Math.floor(ft.length * .95)].toFixed(1), pior_ms: +ft[ft.length - 1].toFixed(1) }); } } requestAnimationFrame(f); }));
  const m1 = await cdp.send('Performance.getMetrics');
  const g = (m, k) => m.metrics.find((x) => x.name === k).value;
  const cpu = { tarefa_s_em_5s: +(g(m1, 'TaskDuration') - g(m0, 'TaskDuration')).toFixed(2), script_s: +(g(m1, 'ScriptDuration') - g(m0, 'ScriptDuration')).toFixed(2), layout_s: +(g(m1, 'LayoutDuration') - g(m0, 'LayoutDuration')).toFixed(2), estilo_s: +(g(m1, 'RecalcStyleDuration') - g(m0, 'RecalcStyleDuration')).toFixed(2) };
  const mem = { js_heap_MB: +(g(m1, 'JSHeapUsedSize') / 1048576).toFixed(1), nos_dom: g(m1, 'Nodes') };
  await ctx.close();
  return { cenario: nome, cpu_throttle: throttle, html_dcl_ms: nav.dcl, html_load_ms: nav.load, render_ate_2_quadros_ms: ini, fps_5s: fps, cpu_5s: cpu, memoria: mem };
}

(async () => {
  const b = await chromium.launch({ args: ['--enable-precise-memory-info'] });
  const out = [];
  for (const th of [1, 4, 6]) {
    out.push(await cenario(b, 'repouso (replay sem efeito)', th, false, 0));
    out.push(await cenario(b, 'destaque do padrão (5 s de efeitos)', th, true, 4100));
  }
  console.log('BASELINE_MESA ' + JSON.stringify(out));
  await b.close();
})();
