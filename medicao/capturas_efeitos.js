// ETAPA 3 · capturas determinísticas da sequência de ativação (relógio e sorteio controlados) para comparar ANTES × DEPOIS.
// Uso: node medicao/capturas_efeitos.js <pasta_de_saida> [padrao|classico]
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { args } = require('./mesa_args.js');
const URL = 'file://' + path.resolve(__dirname, '../trader_front/index.html');
const saida = process.argv[2] || '/tmp/capturas';
const tipo = process.argv[3] || 'padrao';
fs.mkdirSync(saida, { recursive: true });
const TEMPOS = [400, 1200, 2200, 3300, 4300, 5200, 6500, 7800, 8900, 10500, 14000];

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.addInitScript(() => {
    window.__t = 1000; performance.now = () => window.__t;
    let s = 12345; Math.random = () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; };
    window.requestAnimationFrame = () => 1;                       // quem avança o quadro é o teste
    window.setTimeout = (f, ms) => 1; window.setInterval = () => 1;
  });
  await p.goto(URL);
  const a = args(0, true);
  if (tipo === 'classico') { delete a.setup.evento.padrao; a.setup.evento.destaque_ms = 0; a.setup.evento.restante_ms = 23000; }
  await p.evaluate((a) => window.dispatchEvent(new MessageEvent('message', { data: { type: 'streamlit:render', args: a } })), a);
  let ant = 0;
  for (const T of TEMPOS) {
    await p.evaluate(([T0, T]) => { for (let t = T0; t <= T; t += 33) { window.__t = 1000 + t; window.loop && window.loop(); } window.__t = 1000 + T; window.loop && window.loop(); }, [ant, T]);
    ant = T;
    await p.screenshot({ path: path.join(saida, `t${String(T).padStart(5, '0')}.png`) });
  }
  await b.close();
})();
