// Valida o coletor do APK de diagnóstico (app/assets/diag/coletor.js) contra a mesa no Chromium: as fases aparecem, nada quebra. NÃO é medição de Android.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const { args } = require('./mesa_args.js');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 2 })).newPage();
  const erros = []; p.on('pageerror', (e) => erros.push(String(e)));
  await p.addInitScript(() => { window.__msgs = []; window.Diag = { postMessage: (s) => window.__msgs.push(JSON.parse(s)) }; });
  await p.goto('file://' + path.resolve(__dirname, '../trader_front/index.html'), { waitUntil: 'load' });
  await p.evaluate(fs.readFileSync(path.resolve(__dirname, '../app/assets/diag/coletor.js'), 'utf8'));
  await p.evaluate(() => __diag.rot('teste'));
  await p.evaluate((a) => window.postMessage({ type: 'streamlit:render', args: a }, '*'), args(0, false));
  await p.waitForTimeout(2500);
  const ev = args(0, true); ev.setup.evento.restante_ms = 28000; ev.setup.evento.sinal = 'p:1:355:1';
  await p.evaluate((a) => window.postMessage({ type: 'streamlit:render', args: a }, '*'), ev);
  await p.waitForTimeout(13500);
  await p.evaluate(() => __diag.mem('fim'));
  const snap = await p.evaluate(() => __diag.snap());
  const msgs = await p.evaluate(() => __msgs.map((m) => m.k + (m.fase ? ':' + m.fase : '')));
  console.log(JSON.stringify({ erros, msgs, fases: snap.fases.map((f) => ({ fase: f.fase, q: f.quadros, fps: f.fpsMedio, p95: f.quadroP95Ms, max: f.quadroMaxMs, draw: f.drawMedioMs, fx: f.efeitosMedioMs, cv: f.canvasCriados, minSeg: f.fpsMinSeg })), trans: snap.trans, mem: snap.mem.slice(-1), erros_js: snap.erros }, null, 1));
  await b.close();
})();
