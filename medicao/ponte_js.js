// ETAPA 3 · custo de entregar o estado da partida ao WebView: literal de objeto JS × JSON.parse de uma string (mesmo dado, ~27 KB). Chromium, CPU 4×.
const { chromium } = require('playwright');
const { args } = require('./mesa_args.js');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext(); const p = await ctx.newPage(); const cdp = await ctx.newCDPSession(p);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 }); await p.goto('about:blank');
  const r = await p.evaluate((a) => {
    const js = JSON.stringify(a), lit = 'window.__x1=' + js + ';', par = 'window.__x2=JSON.parse(' + JSON.stringify(js) + ');';
    const med = (src) => { const ts = []; for (let i = 0; i < 200; i++) { const t = performance.now(); (0, eval)(src + '//' + i + Math.random()); ts.push(performance.now() - t); } ts.sort((x, y) => x - y); return { p50: +ts[100].toFixed(3), p95: +ts[190].toFixed(3) }; };
    return { bytes: js.length, literal_de_objeto: med(lit), json_parse_de_string: med(par) };
  }, args(0, false));
  console.log('PONTE_JS ' + JSON.stringify(r)); await b.close();
})();
