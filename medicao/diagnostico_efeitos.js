// ETAPA 3 · diagnóstico do custo dos efeitos do destaque do padrão (Chromium headless, desktop, render por SOFTWARE: proxy, não é Android).
// Desliga UMA peça por vez (só dentro da página de teste, sem alterar o jogo) e mede o FPS com CPU 4×. Quanto mais o FPS sobe, mais cara era a peça.
const { chromium } = require('playwright');
const path = require('path');
const URL = 'file://' + path.resolve(__dirname, '../trader_front/index.html');
const { args } = require('./mesa_args.js');

const VARIANTES = {
  'A) como está': '',
  'B) sem redesenho do gráfico principal nem efeitos (draw vazio)': 'window.__draw = window.draw; window.draw = function(){ if(!window.__primeiro){window.__primeiro=1; return window.__draw();} };',
  'C) sem shadowBlur': "Object.defineProperty(CanvasRenderingContext2D.prototype,'shadowBlur',{set(v){},get(){return 0}});",
  'D) sem a camada de efeitos (desenhaMira)': 'window.desenhaMira = function(){};',
  'E) sem zoom CSS da câmera (svZoom)': 'window.svZoom = function(){};',
  'F) sem atualizar o cartão HTML (svUI)': 'window.svUI = function(){};',
  'H) a camada de efeitos só toca 1 pixel por quadro': 'window.desenhaMira = function(){ fxx.clearRect(0,0,W,H); fxx.fillRect(0,0,1,1); };',
  'I) camada de efeitos isolada (will-change + contain)': "document.getElementById('cvfx').style.willChange='transform'; document.getElementById('cvfx').style.contain='strict';",
  'K) sem svJuice (partículas/ondas/gatilhos)': 'window.svJuice = function(){};',
  'L) sem a mira/corpo (_desenhaMira vazio, mas svJuice roda)': 'window._desenhaMira = function(){ fxx.clearRect(0,0,W,H); };',
  'M) sem vinheta': 'window.svVinheta = function(){};',
  'N) sem o corpo da mira (svSombraUnica vazio)': 'window.svSombraUnica = function(){};',
  'O) sem a etiqueta (svEtiqueta)': 'window.svEtiqueta = function(){};',
  'P) sem desenho do corpo (svMiraCorpo vazio)': 'window.svMiraCorpo = function(){};',
  'Q) sem limpar a camada de efeitos (mede o custo do clearRect total)': 'fxx.clearRect = function(){};',
  'R) limpa só uma faixa pequena da camada de efeitos': 'const o=fxx.clearRect.bind(fxx); fxx.clearRect = function(){ o(0,0,60,60); };',
  'J) só efeitos, sem redesenhar o gráfico principal': 'window.draw = function(){ window.desenhaMira(); };',
};

async function rodar(browser, nome, js, throttle, T = 4100) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  await cdp.send('Performance.enable');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle });
  await p.goto(URL, { waitUntil: 'load' });
  await p.evaluate((a) => window.postMessage({ type: 'streamlit:render', args: a }, '*'), args(T, true));
  await p.waitForTimeout(300);
  await p.evaluate((T) => { SVs.t0 = performance.now(); SVs.off = T; }, T);   // fixa a fase da sequência em T ms (o relógio da animação é local)
  await p.waitForTimeout(200);
  if (js) await p.evaluate(js);
  await p.waitForTimeout(300);
  const m0 = await cdp.send('Performance.getMetrics');
  const fps = await p.evaluate(() => new Promise((res) => { const t0 = performance.now(); let n = 0, ult = t0, ft = []; function f(t) { n++; ft.push(t - ult); ult = t; if (t - t0 < 3500) requestAnimationFrame(f); else { ft.sort((a, b) => a - b); res({ fps: +(n / ((t - t0) / 1000)).toFixed(1), p95: +ft[Math.floor(ft.length * .95)].toFixed(0), pior: +ft[ft.length - 1].toFixed(0) }); } } requestAnimationFrame(f); }));
  const m1 = await cdp.send('Performance.getMetrics');
  const g = (m, k) => m.metrics.find((x) => x.name === k).value;
  await ctx.close();
  return { variante: nome, T, cpu: throttle, ...fps, tarefa_s: +(g(m1, 'TaskDuration') - g(m0, 'TaskDuration')).toFixed(2), script_s: +(g(m1, 'ScriptDuration') - g(m0, 'ScriptDuration')).toFixed(2) };
}

(async () => {
  const b = await chromium.launch();
  const out = [];
  const fases = process.argv[2] ? process.argv[2].split(',').map(Number) : [4100];
  for (const T of fases) for (const [nome, js] of Object.entries(VARIANTES)) out.push(await rodar(b, nome, js, 4, T));
  console.log('DIAG_EFEITOS ' + JSON.stringify(out));
  await b.close();
})();
