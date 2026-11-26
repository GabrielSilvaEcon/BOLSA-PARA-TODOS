// Harness do front da mesa: executa o <script> de trader_front/index.html num DOM falso (sem navegador, sem rede).
// Uso: node tests_front/harness.js   (sai com código 1 se algum teste falhar)
const fs = require("fs"), vm = require("vm"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "trader_front", "index.html"), "utf8");
const code = html.match(/<script>([\s\S]*)<\/script>/)[1];
const ids = [...html.split("<script>")[0].matchAll(/id="([^"]+)"/g)].map(m => m[1]);

function carregar() {
  const posts = [], timers = [], els = {}; let agora = 1000;
  const ctx = new Proxy({}, { get: (t, k) => k === "measureText" ? () => ({ width: 10 }) : k === "createRadialGradient" ? () => ({ addColorStop() {} }) : (k in t ? t[k] : () => {}), set: (t, k, v) => { t[k] = v; return true } });
  const mk = id => { const e = { id, style: { setProperty(k, v) { this[k] = v } }, _c: new Set(), innerHTML: "", textContent: "", value: "", disabled: false, src: "", className: "", dataset: {}, L: {},
    classList: { toggle: (c, on) => { if (on === undefined) on = !e._c.has(c); on ? e._c.add(c) : e._c.delete(c) }, add: c => e._c.add(c), remove: c => e._c.delete(c), contains: c => e._c.has(c) },
    addEventListener(t, f) { (e.L[t] = e.L[t] || []).push(f) }, getBoundingClientRect: () => ({ width: 360, height: 420, top: 0, left: 0 }), querySelectorAll: () => [], closest: () => null,
    setPointerCapture() {}, getContext: () => ctx, focus() {} }; return e };
  for (const i of ids) els[i] = mk(i);
  const win = { L: {}, parent: { postMessage: (m) => posts.push(m), document: { querySelector: () => null }, innerHeight: 800, addEventListener() {} }, innerHeight: 800, frameElement: null,
    devicePixelRatio: 1, addEventListener(t, f) { (win.L[t] = win.L[t] || []).push(f) } };
  const doc = { getElementById: id => els[id], querySelectorAll: () => [], addEventListener() {}, documentElement: { clientWidth: 360, requestFullscreen() {} }, fullscreenElement: null, fullscreenEnabled: false };
  const sb = { window: win, document: doc, performance: { now: () => agora }, setTimeout: (f, ms) => { timers.push({ f, ms }); return timers.length }, clearTimeout() {}, setInterval() { return 1 },
    Image: class {}, requestAnimationFrame: () => 1, cancelAnimationFrame() {}, console, Math, JSON, Number, String, Array, Object, Set, Map, isFinite, parseFloat, Date, crypto: { randomUUID: () => "u" + Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2) } };
  sb.window.crypto = sb.crypto; sb.window.document = doc; sb.window.performance = sb.performance;
  vm.createContext(sb); vm.runInContext(code, sb);
  return { sb, els, posts, timers, win, ctx, tempo: ms => { agora += ms }, render: a => win.L.message.forEach(f => f({ data: { type: "streamlit:render", args: a } })),
           acoes: () => posts.filter(p => p.type === "streamlit:setComponentValue").map(p => p.value) };
}

function candles(n) { return Array.from({ length: n }, (_, i) => ({ t: "2026-01-05T10:" + String(i % 60).padStart(2, "0"), o: 10 + 0.01 * i, h: 10.05 + 0.01 * i, l: 9.95 + 0.01 * i, c: 10.02 + 0.01 * i, v: 1000 })) }
function args(extra) { return Object.assign({ modo: "replay", fase_key: "1-replay", adversarios: [], propria: null, operacao: null, marcas_ant: {}, resultado: null, multi: true, aposta_txt: "Aposta T$ 1.000,00",
  prontos: null, seq0: 0, revelados: 6, total_replay: 24, prox_ms: 1500, candles: candles(126), ticker: "TEST3", tf_nome: "15 minutos", demo: true, rodada: 1, rodadas: 3, seg: 50, ref: 11.3, token: "tok",
  sr: { suportes: [], resistencias: [] }, inicial: { direcao: "alta", tipo: "continuacao", confianca: 3, marcas: {} }, limites: { niveis: 6, tendencias: 4, notas: 6 }, erro: "", erro_seq: 0, ok_seq: 0 }, extra) }
const mesaSem = () => ({ preco_atual: 11.3, stake: 1000, pat_ini: 100000, posicao: null, ordens: [], operacoes: [], n_encerradas: 0, realizado_pct: 0, realizado_val: 0, aberto_pct: 0, aberto_val: 0,
  aberto_txt: "0,00%", acum_txt: "0,00%", cor_aberto: "zero", cor_acum: "zero", pode_abrir: true, pode_encerrar: false, pode_cancelar: false, pode_gerir: false, aposta_txt: "Aposta por operação" })
const mesaPos = () => Object.assign(mesaSem(), { posicao: { direcao: "alta", preco_entrada: 11.2, indice_entrada: 123, stop: 10.9, alvo: 11.8 }, ordens: [{ id: "stop", preco: 10.9 }, { id: "alvo", preco: 11.8 }],
  aberto_txt: "+0,89% (+T$ 8,90)", cor_aberto: "up", pode_abrir: false, pode_encerrar: true, pode_cancelar: true, pode_gerir: true })

let ok = 0, falhas = 0;
function t(nome, fn) { try { fn(); ok++; console.log("ok  ", nome) } catch (e) { falhas++; console.log("FAIL", nome, "->", e.message) } }
function eq(a, b, m) { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error((m || "") + " esperado " + JSON.stringify(b) + " veio " + JSON.stringify(a)) }
function yes(c, m) { if (!c) throw new Error(m || "falso") }

t("legado: replay sem motor continua com a tela antiga (sem mesa, sem erro)", () => {
  const h = carregar();
  h.render(args({ adversarios: [{ rotulo: "Jogador 2", preco: 11.0 }], operacao: { estado: "aberta", encerravel: true, cor: "up", txt: "Aberta · +1,0%", saida: null },
    inicial: { direcao: "alta", tipo: "continuacao", confianca: 3, entrada: 11.2, stop: 10.9, alvo: 11.8, marcas: {} } }));
  yes(!h.els.app._c.has("mesa"), "não pode virar mesa"); yes(h.els.sm.innerHTML.includes("Estratégia travada"), "texto antigo");
  yes(h.els.bt._c.has("enc"), "botão encerrar antigo"); yes(h.els["b-buy"].innerHTML.includes("Compra"), "rótulo antigo");
});
t("mesa: análise pede só a direção (sem entrada/stop/alvo) e rotula Alta/Baixa", () => {
  const h = carregar();
  h.render(args({ modo: "analise", fase_key: "1-analise", motor: 2, mesa: null, candles: candles(120), revelados: 0, prox_ms: null, inicial: null }));
  yes(h.els.app._c.has("mesa") && !h.els.app._c.has("replay"), "classes"); yes(h.els["b-buy"].innerHTML.includes("Alta") && h.els["b-sell"].innerHTML.includes("Baixa"));
  h.els["b-buy"].onclick(); h.sb.window.__TB.ui(); yes(h.sb.window.__TB.S.v.ok, "leitura válida só com direção"); yes(!h.els.conf.disabled, "pode confirmar");
});
t("mesa: replay mostra posição própria, botões certos e adversário sem erro de desenho", () => {
  const h = carregar();
  h.render(args({ motor: 2, mesa: mesaPos(), adversarios: [{ rotulo: "Jogador 2", ops: [{ direcao: "baixa", preco_entrada: 11.0, indice_entrada: 122, aberta: true, preco_saida: null, indice_saida: null },
    { direcao: "alta", preco_entrada: 10.8, indice_entrada: 121, aberta: false, preco_saida: 11.1, indice_saida: 124 }] }] }));
  yes(h.els.app._c.has("mesa") && h.els.app._c.has("replay")); yes(h.els.sm.innerHTML.includes("COMPRA ▲ 11,20") && h.els.sm.innerHTML.includes("STOP 10,90") && h.els.sm.innerHTML.includes("ALVO 11,80"), h.els.sm.innerHTML);
  yes(h.els["m-buy"].disabled && h.els["m-sell"].disabled && !h.els["m-enc"].disabled, "com posição: não abre outra, pode encerrar"); yes(h.els["m-can"].style.display === "block");
  yes(h.els.sm.innerHTML.includes("Aberto") && h.els.sm.innerHTML.includes("0 encerradas"));
});
t("mesa: sem posição, COMPRAR e VENDER liberados e ENCERRAR travado", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() }));
  yes(!h.els["m-buy"].disabled && !h.els["m-sell"].disabled && h.els["m-enc"].disabled && h.els["m-can"].style.display === "none"); yes(h.els.sm.innerHTML.includes("Sem posição"));
});
t("mesa: COMPRAR manda uma ação com aid e o segundo clique imediato é barrado até o servidor confirmar", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() }));
  h.els["m-buy"].onclick(); h.els["m-buy"].onclick(); h.els["m-sell"].onclick();
  let a = h.acoes(); eq(a.length, 1, "uma só ação enviada"); eq([a[0].evento, a[0].dados.tipo, a[0].dados.direcao], ["acao", "mercado", "alta"]); yes(a[0].dados.aid && a[0].dados.aid.length >= 8, "aid");
  yes(h.els["m-buy"].disabled && h.els["m-sell"].disabled, "botões travados enquanto aguarda");
  h.render(args({ motor: 2, mesa: mesaPos(), seq0: a[0].seq })); yes(!h.els["m-enc"].disabled, "confirmado: libera ENCERRAR");
  h.els["m-enc"].onclick(); a = h.acoes(); eq(a.length, 2); eq(a[1].dados.tipo, "encerrar"); yes(a[1].seq > a[0].seq && a[1].dados.aid !== a[0].dados.aid, "seq e aid novos");
});
t("mesa: se o servidor demorar mais de 5 s o envio destrava sozinho", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() })); h.els["m-buy"].onclick(); eq(h.acoes().length, 1);
  h.tempo(5200); h.render(args({ motor: 2, mesa: mesaSem(), seq0: 0 })); yes(!h.els["m-buy"].disabled, "destravou"); h.els["m-sell"].onclick(); eq(h.acoes().length, 2);
});
t("mesa: pausa técnica trava tudo e não envia nada", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaPos(), pausada: true, prox_ms: null }));
  yes(h.els["m-enc"].disabled && h.els["m-stop"].disabled && h.els["m-can"].style.display === "none"); yes(h.els.sm.innerHTML.includes("pausa técnica"));
  eq(h.sb.window.__TB.sendAcao({ tipo: "encerrar" }), false); eq(h.acoes().length, 0); yes(h.els.rod.textContent.includes("⏸"));
});
t("mesa: erro do servidor aparece para o jogador e a ordem não trava a tela", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() })); h.els["m-buy"].onclick(); const s = h.acoes()[0].seq;
  h.render(args({ motor: 2, mesa: mesaSem(), seq0: s, erro: "você já tem uma posição aberta", erro_seq: s })); yes(h.els.sm.innerHTML.includes("já tem uma posição"), "mostra o erro"); yes(!h.els["m-buy"].disabled);
});
t("mesa: painel avançado envia ordem limite com stop e alvo; vírgula decimal funciona", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() }));
  h.els["o-tipo"].value = "limite"; h.els["o-preco"].value = "11,10"; h.els["o-stop"].value = "10,90"; h.els["o-alvo"].value = "11,60"; h.els["o-buy"].onclick();
  const a = h.acoes(); eq(a.length, 1); eq([a[0].dados.tipo, a[0].dados.direcao, a[0].dados.preco, a[0].dados.stop, a[0].dados.alvo], ["limite", "alta", 11.1, 10.9, 11.6]);
});
t("mesa: ordem limite sem preço e número inválido não saem do navegador", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() })); h.els["o-tipo"].value = "limite"; h.els["o-buy"].onclick(); eq(h.acoes().length, 0);
  h.els["o-tipo"].value = "mercado"; h.els["o-stop"].value = "abc"; h.els["o-sell"].onclick(); eq(h.acoes().length, 0);
});
t("mesa: lista de ordens pendentes e cancelamento por ordem", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: Object.assign(mesaSem(), { ordens: [{ id: "entrada", tipo: "limite", direcao: "alta", preco: 11.0 }], pode_abrir: false, pode_gerir: true, pode_cancelar: true }) }));
  yes(h.els["o-lista"].innerHTML.includes("Limite") && h.els["o-lista"].innerHTML.includes("11,00")); yes(h.els["m-can"].style.display === "block");
  h.els["m-can"].onclick(); eq(h.acoes()[0].dados, Object.assign({ aid: h.acoes()[0].dados.aid }, { tipo: "cancelar", qual: "todas" }));
});
function arrastar(h, k, deltaY) {
  const { sb } = h, B = sb.window.__TB, ptr = (tp, y) => ({ pointerId: 1, pointerType: "touch", clientX: 100, clientY: y });
  B.draw(); const y0 = B.L.y(B.linhasMesa()[k]); const cv = h.els.cv.L;
  cv.pointerdown.forEach(f => f(ptr("d", y0))); cv.pointermove.forEach(f => f(ptr("m", y0 + 3))); cv.pointermove.forEach(f => f(ptr("m", y0 + deltaY))); cv.pointerup.forEach(f => f(ptr("u", y0 + deltaY)));
}
t("mesa: arrastar o STOP para longe do preço envia mover_stop com o novo preço", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaPos() })); const antes = h.sb.window.__TB.linhasMesa().stop; arrastar(h, "stop", 25);
  const a = h.acoes(); eq(a.length, 1); eq(a[0].dados.tipo, "mover_stop"); yes(a[0].dados.preco < antes && a[0].dados.preco > 0, "preço desceu: " + a[0].dados.preco);
});
t("mesa: arrastar o ALVO envia mover_alvo", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaPos() })); const antes = h.sb.window.__TB.linhasMesa().alvo; arrastar(h, "alvo", -20);
  const a = h.acoes(); eq(a.length, 1); eq(a[0].dados.tipo, "mover_alvo"); yes(a[0].dados.preco > antes, "preço subiu");
});
t("mesa: arrastar o stop para o lado errado do preço é recusado localmente", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaPos() })); arrastar(h, "stop", -200); eq(h.acoes().length, 0, "nada enviado");
});
t("mesa: ferramenta Stop + toque no gráfico define o stop (definir quando não existe)", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: Object.assign(mesaPos(), { posicao: { direcao: "alta", preco_entrada: 11.2, indice_entrada: 123, stop: null, alvo: null }, ordens: [] }) }));
  h.els["m-stop"].onclick(); yes(h.sb.window.__TB.S.tool === "mstop"); h.sb.window.__TB.draw();
  const y = h.sb.window.__TB.L.y(10.9), cv = h.els.cv.L, p = { pointerId: 1, pointerType: "touch", clientX: 100, clientY: y };
  cv.pointerdown.forEach(f => f(p)); cv.pointerup.forEach(f => f(p));
  const a = h.acoes(); eq(a.length, 1); eq(a[0].dados.tipo, "definir_stop"); yes(Math.abs(a[0].dados.preco - 10.9) < 0.05);
});
t("mesa: o jogador não arrasta o que não é dele (adversário não tem linha arrastável)", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), adversarios: [{ rotulo: "Jogador 2", ops: [{ direcao: "baixa", preco_entrada: 11.0, indice_entrada: 122, aberta: true, preco_saida: null, indice_saida: null }] }] }));
  eq(h.sb.window.__TB.linhasMesa().stop, null); h.sb.window.__TB.draw();
});
t("mesa: resultado negativo mostra sinal, nº de operações e a nota dos 1%", () => {
  const h = carregar();
  h.render(args({ motor: 2, modo: "resultado", fase_key: "1-resultado", mesa: mesaSem(), resultado: { pontos: -34.5, total: -34.5, faixa: "faixa_derrota", acertou: false, executada: true, r: null, n_ops: 3,
    fin: { cor: "down", t1: "−T$ 1.500,00 · 3 operações", t2: "Aposta de T$ 1.000,00", nota: "a perda da rodada pode passar de 1% do patrimônio." }, img: null, selo: null, linhas: [["Pontos", "x"]], ultima: false }, candles: candles(144), revelados: 24 }));
  const r = h.els.res.innerHTML; yes(r.includes("−34") || r.includes("-34"), "pontos negativos"); yes(r.includes("3 operações") && r.includes("pode passar de 1%"), r); yes(r.includes("#FF6B87"));
  yes(h.els.app._c.has("rs"), "classe de resultado esconde a mesa");
});
t("mesa: candle novo entra na fila e a tela não é reconstruída (mesmo token mantém o estado)", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() })); const S1 = h.sb.window.__TB.S; h.els["o-stop"].value = "10,5";
  h.render(args({ motor: 2, mesa: mesaSem(), candles: candles(127), revelados: 7 })); yes(h.sb.window.__TB.S === S1, "mesmo estado"); eq(h.els["o-stop"].value, "10,5", "o que o jogador digitou foi preservado");
  eq(S1.cands.length + S1.fila.length, 127);
});
t("gráfico: iframe que nasce estreito ganha o zoom certo quando chega à largura real, e mudar a largura preserva os candles visíveis", () => {
  const h = carregar(); let w = 120; h.els.cvw.getBoundingClientRect = () => ({ width: w, height: 420, top: 0, left: 0 });
  h.render(args({ modo: "analise", fase_key: "1-analise", motor: 2, mesa: null, candles: candles(120), revelados: 0, prox_ms: null, inicial: null }));
  const S = h.sb.window.__TB.S, slots = pw => pw / S.cw;
  w = 360; h.sb.window.__TB.fit(); yes(Math.abs(slots(360 - 46) - 93) < 0.01, "na largura real o zoom inicial mostra 90 candles + folga, veio " + slots(360 - 46));
  w = 300; h.sb.window.__TB.fit(); yes(Math.abs(slots(300 - 40) - 93) < 0.01, "girar/redimensionar mantém os mesmos candles na tela, veio " + slots(300 - 40));
});
t("fim da rodada: lugar, pontos e retorno, placar por pontos, Raio-X em cartões e contagem igual para todos", () => {
  const h = carregar();
  const pl = { rodada: "2/3", fechada: true, pat_txt: null, jogadores: [
    { rotulo: "Jogador 2", pct: 3.1, voce: false, pos: 1, txt: "+3,10%", cor: "up", pts: 40.2, pts_txt: "+40,2" },
    { rotulo: "Você", pct: 1.5, voce: true, pos: 2, txt: "+1,50%", cor: "up", pts: 12.0, pts_txt: "+12,0" }] };
  const res = { pontos: 12.0, total: 30.5, faixa: "faixa_vitoria", acertou: true, executada: true, r: null, n_ops: 1, limite_atingido: false, fin: null, img: null, selo: null,
    linhas: [["Sua leitura", "alta"], ["Limite de perda", "x"], ["Pontos", "y"]], ultima: false, rodada_txt: "2/3", ret_txt: "+1,50%", ret_cor: "up", ret_val: "+T$ 15,00" };
  h.render(args({ motor: 2, modo: "resultado", fase_key: "2-resultado", mesa: mesaSem(), resultado: res, placar: pl, multi: true, seg: 3, candles: candles(144), revelados: 24 }));
  const r = h.els.res.innerHTML;
  yes(r.includes("FIM DA RODADA") && r.includes("2/3"), "título e rodada"); yes(r.includes("2º lugar"), "lugar"); yes(r.includes("+12,0") && r.includes("+1,50%") && r.includes("+T$ 15,00"), "pontos e retorno");
  yes(r.indexOf("Jogador 2") < r.indexOf(">Você<") && r.includes("pr p2 eu"), "placar por pontos com você destacado");
  yes(r.includes('class="ri al"') && r.includes('class="ri pt"') && r.includes("🧭"), "Raio-X em cartões com ícone"); yes(r.includes("Próxima rodada em") && !r.includes('id="prox"'), "sala: contagem, sem botão");
  h.render(args({ motor: 2, modo: "resultado", fase_key: "2-resultado", mesa: mesaSem(), resultado: res, placar: { ...pl, jogadores: [pl.jogadores[1]] }, multi: false, seg: 0, candles: candles(144), revelados: 24 }));
  yes(h.els.res.innerHTML.includes("Acertou a direção") && h.els.res.innerHTML.includes('id="prox"'), "solo: sem placar, com botão");
});
t("placar da mesa: avatar equipado de cada assento com a cor da raridade; sem mapa, a raposa por assento", () => {
  const h = carregar();
  const pl = { rodada: "1/3", fechada: true, pat_txt: null, jogadores: [
    { rotulo: "Jogador 2", pct: 3.1, voce: false, pos: 1, txt: "+3,10%", cor: "up", pts: 40.2, pts_txt: "+40,2" },
    { rotulo: "Você", pct: 1.5, voce: true, pos: 2, txt: "+1,50%", cor: "up", pts: 12.0, pts_txt: "+12,0" }] };
  const res = { pontos: 12.0, total: 30.5, faixa: "faixa_vitoria", acertou: true, executada: true, r: null, n_ops: 1, limite_atingido: false, fin: null, img: null, selo: null,
    linhas: [], ultima: false, rodada_txt: "1/3", ret_txt: "+1,50%", ret_cor: "up", ret_val: "+T$ 15,00" };
  const avs = { "Você": { src: "/app/static/avatares/panda_p.webp", cor: "#D5DAE6" }, "Jogador 2": { src: "/app/static/avatares/dragao_p.webp", cor: "#FF4D5E" } };
  h.render(args({ motor: 2, modo: "resultado", fase_key: "1-resultado", mesa: mesaSem(), resultado: res, placar: pl, multi: true, seg: 3, candles: candles(144), revelados: 24, avatares: avs }));
  const r = h.els.res.innerHTML;
  yes(r.includes("dragao_p.webp") && r.includes("--aro:#FF4D5E") && r.includes("panda_p.webp"), "avatares e cores no placar");
  const h2 = carregar();
  h2.render(args({ motor: 2, modo: "resultado", fase_key: "1-resultado", mesa: mesaSem(), resultado: res, placar: pl, multi: true, seg: 3, candles: candles(144), revelados: 24 }));
  yes(!h2.els.res.innerHTML.includes("dragao_p.webp") && h2.els.res.innerHTML.includes("hue-rotate"), "sem mapa: raposa por assento");
});
t("boleta: abre embaixo do gráfico, troca os botões rápidos pelo Confirmar e volta recolhida na rodada seguinte", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() }));
  h.els["m-adv"].onclick();
  eq(h.els.adv.style.display, "flex", "boleta aberta"); yes(h.els.app._c.has("adv"), "app marca a boleta aberta (esconde COMPRAR/VENDER rápidos)");
  eq(h.els["m-adv"].textContent, "▴ Recolher");
  h.els["m-adv"].onclick();
  eq(h.els.adv.style.display, "none", "boleta recolhida"); yes(!h.els.app._c.has("adv")); eq(h.els["m-adv"].textContent, "⚙ Opções ▾");
  h.els["m-adv"].onclick();
  h.render(args({ motor: 2, modo: "resultado", fase_key: "1-resultado", mesa: mesaSem(), resultado: null, seg: 3 }));
  yes(!h.els.app._c.has("adv") && h.els.adv.style.display === "none", "fim da rodada: boleta recolhida e botões rápidos de volta");
});
t("boleta recolhida: COMPRAR rápido manda ordem a mercado num toque", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem() }));
  h.els["m-sell"].onclick();
  const a = h.acoes(); eq(a.length, 1); eq([a[0].dados.tipo, a[0].dados.direcao], ["mercado", "baixa"]);
});
const mesaQtd = (pos) => Object.assign(mesaSem(), { qtd: true, capital: 10000, poder: pos ? 6610 : 10000, max_q: pos ? 584 : 884, exposicao: pos ? 3390 : 0, exposicao_pct: pos ? 33.9 : 0,
  posicao: pos ? { direcao: "alta", preco_entrada: 11.2, indice_entrada: 123, stop: null, alvo: null, q: 300 } : null, fila: [], pode_reduzir: !!pos, pode_encerrar: !!pos,
  aberto_txt: "+T$ 30,00", acum_txt: "+T$ 30,00", cor_aberto: "up", cor_acum: "up", limite: { bloqueado: false, usado_pct_cap: 0 } });
t("corrida: COMPRAR manda a quantidade escolhida e o painel mostra quantidade, preço médio e poder de compra", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaQtd(true) }));
  yes(h.els.app._c.has("qtd"), "app marca a partida com quantidade");
  yes(h.els.sm.innerHTML.includes("Comprado 300") && h.els.sm.innerHTML.includes("PM 11,20") && h.els.sm.innerHTML.includes("Poder T$"), "painel da posição");
  h.els["q-val"].value = "250"; h.els["m-buy"].onclick();
  const a = h.acoes(); eq(a.length, 1); eq([a[0].dados.tipo, a[0].dados.direcao, a[0].dados.q], ["mercado", "alta", 250]);
});
t("corrida: VENDER comprado com quantidade maior que a posição vira zerar (não inverte)", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaQtd(true) }));
  h.els["q-val"].value = "999"; h.els["m-sell"].onclick();
  const a = h.acoes(); eq([a[0].dados.direcao, a[0].dados.q], ["baixa", 300]);
});
t("corrida: com o capital todo aplicado, comprar trava e vender (reduzir) continua liberado", () => {
  const h = carregar(); const m = mesaQtd(true); m.pode_abrir = false; m.max_q = 0; m.poder = 0;
  h.render(args({ motor: 2, mesa: m }));
  yes(h.els["m-buy"].disabled && !h.els["m-sell"].disabled);
});
t("corrida: sem quantidade, a ordem não sai", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaQtd(false) }));
  h.els["q-val"].value = ""; h.els["m-buy"].onclick(); eq(h.acoes().length, 0);
});
t("corrida: stop móvel manda a distância e o painel mostra STOP MÓVEL", () => {
  const h = carregar(); const m = mesaQtd(true); m.posicao.stop = 11.0; m.posicao.trail = 0.3; m.pode_gerir = true;
  h.render(args({ motor: 2, mesa: m }));
  yes(h.els.sm.innerHTML.includes("STOP MÓVEL"), "painel");
  h.els["g-trail"].value = "0,30"; h.els["g-trail-b"].onclick();
  const a = h.acoes(); eq([a[0].dados.tipo, a[0].dados.dist], ["stop_movel", 0.3]);
});
t("candle se formando: o último candle cresce no lugar (sem duplicar) e o próximo entra depois", () => {
  const h = carregar(); const c = candles(126); h.render(args({ motor: 2, mesa: mesaQtd(false), candles: c }));
  eq(vm.runInContext('S', h.sb).cands.length, 126);
  const c2 = c.map(x => ({ ...x })); c2[125] = { ...c2[125], h: 12.5, c: 12.4 };
  h.render(args({ motor: 2, mesa: mesaQtd(false), candles: c2 }));
  eq(vm.runInContext('S', h.sb).cands.length + vm.runInContext('S', h.sb).fila.length, 126, "não duplica"); eq([vm.runInContext('S', h.sb).cands[125].h, vm.runInContext('S', h.sb).cands[125].c], [12.5, 12.4]);
  const c3 = c2.concat([{ ...c2[125], t: "2026-01-05T12:00", o: 12.4, h: 12.45, l: 12.3, c: 12.35 }]);
  h.render(args({ motor: 2, mesa: mesaQtd(false), candles: c3 }));
  eq(vm.runInContext('S', h.sb).cands.length + vm.runInContext('S', h.sb).fila.length, 127, "candle novo entra");
});
t("corrida: pop-up da estratégia só tem a leitura (Subir/Cair) e depois mostra a espera", () => {
  const h = carregar();
  const base = { modo: "analise", fase_key: "1-analise", motor: 2, mesa: null, corrida: true, ref: 11.3 };
  h.render(args({ ...base, confirmados: { eu: false, n: 0, total: 2 } }));
  yes(h.els.plano._c.has("on"), "pop-up aberto na análise"); yes(h.els["pl-ok"].disabled, "sem escolher não confirma");
  h.els["pl-buy"].onclick(); h.els["pl-ok"].onclick();
  const a = h.acoes(); eq(a.length, 1); eq([a[0].evento, a[0].plano.direcao, a[0].plano.q, a[0].plano.ordem], ["confirmar", "alta", undefined, undefined]);
  h.render(args({ ...base, confirmados: { eu: true, n: 1, total: 2 } }));
  yes(h.els.plano._c.has("esp")); yes(h.els["pl-esp-t"].textContent.includes("1/2"));
});
t("corrida: Aguardar no pop-up confirma sem ordem e a aba Boleta recolhe e expande", () => {
  const h = carregar();
  h.render(args({ modo: "analise", fase_key: "1-analise", motor: 2, mesa: null, corrida: true, plano_cfg: { capital: 10000, taxa: 0.0003 }, ref: 11.3, confirmados: { eu: false, n: 0, total: 1 } }));
  h.els["pl-wait"].onclick(); yes(!h.els["pl-ok"].disabled, "aguardar libera o confirmar"); h.els["pl-ok"].onclick();
  const a = h.acoes(); eq([a[0].evento, a[0].plano.tipo, a[0].plano.direcao], ["confirmar", "aguardar", null]);
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaQtd(true), corrida: true }));
  h2.els["m-tg"].onclick(); yes(h2.els.app._c.has("bmin"), "recolheu"); h2.els["m-tg"].onclick(); yes(!h2.els.app._c.has("bmin"), "expandiu");
});
t("corrida em lotes: 3 lotes comprados, vender 2 manda 2 lotes em ações e mostra quanto fica; vender 3 zera", () => {
  const h = carregar(); const m = mesaQtd(true); m.posicao.q = 300;
  h.render(args({ motor: 2, mesa: m, corrida: true, lote: 100 }));
  eq(h.els["q-val"].value, "1", "começa com 1 lote"); yes(h.els.pbar.innerHTML.includes("Comprado 3 lotes"), "posição à vista");
  h.els["q-val"].value = "2"; h.els["m-sell"].onclick();
  let a = h.acoes(); eq([a[0].dados.direcao, a[0].dados.q], ["baixa", 200]);
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: m, corrida: true, lote: 100 }));
  h2.els["q-val"].value = "5"; h2.els["m-sell"].onclick(); a = h2.acoes(); eq(a[0].dados.q, 300, "mais lotes que a posição = zera, nunca inverte");
});
t("aviso sobre o gráfico aparece e some sozinho (também durante a partida)", () => {
  const h = carregar(); const m = mesaQtd(true); h.render(args({ motor: 2, mesa: m, corrida: true, lote: 100 }));
  eq(h.els.dica.style.display, "block", "dica da 1ª posição aparece");
  const tm = h.timers.filter(x => x.ms >= 1600).pop(); tm.f();
  eq(h.els.dica.style.display, "none", "e some");
});

// ---- Setups colecionáveis: o servidor manda o evento; a mesa só mostra e devolve a decisão ----
const evSetup = (extra) => ({ evento: Object.assign({ sinal: "p:1:130", setup: { id: "larry_williams", nome: "Larry Williams", raridade: "epica", cores: { principal: "#2EE59D", brilho: "#FFD76A" }, assets: { carta: "assets/setups/larry_williams/carta.jpg", ativacao: null, efeitos: [] }, provisorio: true },
  dono: "Você", voce_e_dono: true, direcao: "alta", candle: 120, preco: 11.3, stop: 11.0, alvo: 11.9, motivo: "x", anim_ms: 4000, janela_ms: 5000, decorrido_ms: 0, restante_ms: 9000, pode_decidir: true }, extra || {}), marcas: [] });
t("setup: durante a animação não há botões; a janela só abre depois dos 4 s e com contador de 5 s", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup() }));
  yes(h.els.stp._c.has("on"), "overlay ligado"); yes(!h.els["stp-dec"]._c.has("on"), "sem janela na animação");
  yes(h.els["stp-fx"].innerHTML.includes("Larry Williams"), "nome do setup aparece na detecção");
  h.tempo(4100); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 4100, restante_ms: 4900 }) }));
  yes(h.els["stp-dec"]._c.has("on"), "janela aberta"); eq(h.els["stp-h"].textContent, "SEU SETUP FOI ATIVADO!");
  yes(h.els["stp-p"].textContent.includes("Deseja entrar nesta operação?")); eq(h.els["stp-c"].textContent, "5s"); eq(h.els["stp-bt"].style.display, "flex");
  yes(!h.els["stp-sim"].disabled, "dono pode decidir");
});
t("setup: ENTRAR e RECUSAR mandam a decisão uma única vez (com a quantidade escolhida: 50% do que cabe no capital)", () => {
  const h = carregar(); const a = args({ motor: 2, mesa: mesaQtd(true), corrida: true, lote: 100, pausada: true, setup: evSetup({ decorrido_ms: 4500, restante_ms: 4500 }) });
  h.render(a); h.els["stp-sim"].onclick(); h.els["stp-sim"].onclick(); h.els["stp-nao"].onclick();
  const v = h.acoes().filter(x => x.evento === "setup"); eq(v.length, 1, "só um envio"); eq(v[0].dados.acao, "aceitar"); yes(v[0].dados.q > 0, "quantidade enviada");
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaQtd(true), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 4500, restante_ms: 4500 }) }));
  h2.els["stp-nao"].onclick(); eq(h2.acoes().filter(x => x.evento === "setup").map(x => x.dados), [{ acao: "recusar" }]);
});
t("setup: a janela de decisão mostra 25/50/100% do capital e o risco em T$ do stop (só para o dono)", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaQtd(true), corrida: true, lote: 100, pausada: true, setup: evSetup({ decorrido_ms: 4500, restante_ms: 4500 }) }));
  const q = h.els["stp-q"].innerHTML; yes(q.includes('data-p="25"') && q.includes('data-p="50"') && q.includes('data-p="100"'), "três opções"); yes(q.includes("Risco:"), "risco em T$");
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ voce_e_dono: false, dono: "Jogador 2", pode_decidir: false, stop: null, alvo: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h2.els["stp-q"].style.display, "none", "o adversário não vê o tamanho do outro");
});
t("setup de padrão: a lição (candles ampliados + ideia) aparece para o dono E para o adversário, sem região, stop ou alvo para o adversário", () => {
  const pad = { candles: [0, 1], licao: { ideia: "Um candle de alta cobre o corpo do de baixa.", porque: "Num suporte, sinaliza reversão.", partes: ["1º candle: baixa", "2º candle: alta engole"] } };
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaQtd(true), corrida: true, lote: 100, pausada: true, setup: evSetup({ padrao: pad, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h.els["stp-lic"].style.display, "block", "lição visível para o dono"); yes(h.els["stp-lt"].innerHTML.includes("cobre o corpo"), "ideia na tela");
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ padrao: pad, voce_e_dono: false, dono: "Jogador 2", pode_decidir: false, stop: null, alvo: null, regiao: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h2.els["stp-lic"].style.display, "block", "o adversário também aprende com o padrão"); eq(h2.els["stp-bt"].style.display, "none", "mas não opera");
  yes(!h2.els["stp-dt"].innerHTML.includes("Stop"), "sem stop do outro");
  const h3 = carregar(); h3.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h3.els["stp-lic"].style.display, "none", "setup que não é padrão de candle não mostra lição");
});
t("setup de padrão: depois da mira vem o destaque (cartão escondido, chip 'Memorize o padrão') e só então a janela de decisão", () => {
  const pad = { candles: [0, 1], licao: { ideia: "i", porque: "p", partes: ["a"], rotulos: [{ k: 0, onde: "corpo", txt: "1º: baixa" }, { k: 1, onde: "corpo", txt: "2º: alta engole" }] } };
  const ev = (d, r) => args({ motor: 2, mesa: mesaQtd(true), corrida: true, lote: 100, pausada: true, setup: evSetup({ padrao: pad, destaque_ms: 5000, decorrido_ms: d, restante_ms: r }) });
  const h = carregar(); h.render(ev(5500, 22500)); yes(!h.els["stp-dec"]._c.has("on"), "cartão escondido durante o destaque"); yes(h.els["stp-fx"].innerHTML.includes("Memorize o padrão"), "chip de memorizar");
  const h2 = carregar(); h2.render(ev(9500, 18500)); yes(h2.els["stp-dec"]._c.has("on"), "cartão volta quando o destaque termina"); yes(!h2.els["stp-fx"].innerHTML.includes("Memorize"), "chip sai");
});
t("setup: o adversário vê o evento mas não tem botões e não consegue decidir", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ voce_e_dono: false, dono: "Jogador 2", pode_decidir: false, stop: null, alvo: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  yes(h.els["stp-dec"]._c.has("on")); yes(h.els["stp-h"].textContent.includes("Jogador 2")); eq(h.els["stp-bt"].style.display, "none", "sem botões");
  h.els["stp-sim"].onclick(); eq(h.acoes().filter(x => x.evento === "setup").length, 0, "nada sai");
  yes(!h.els["stp-dt"].innerHTML.includes("Stop"), "stop e alvo do outro não aparecem");
});
t("setup: o contador acompanha o relógio do servidor e a janela fecha no fim; sem evento, tudo some", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 4000, restante_ms: 5000 }) }));
  h.tempo(2000); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 6000, restante_ms: 3000 }) }));
  eq(h.els["stp-c"].textContent, "3s"); h.tempo(3100); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 9100, restante_ms: 0 }) }));
  yes(!h.els["stp-dec"]._c.has("on"), "janela fecha em 0");
  h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, setup: { evento: null, marcas: [] } })); yes(!h.els.stp._c.has("on"), "overlay desligado sem evento");
});
t("setup: arte de ativação enviada entra pelo caminho relativo da mesa; sem ela, o aviso de arte provisória aparece", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 4500, restante_ms: 4500 }) }));
  yes(h.els["stp-prov"].textContent.includes("provisória"), "provisório sinalizado");
  const h2 = carregar(); const e = evSetup({ decorrido_ms: 4500, restante_ms: 4500 }); e.evento.setup.assets.ativacao = "assets/setups/larry_williams/ativacao.webp"; e.evento.setup.provisorio = false;
  h2.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: e })); eq(h2.els["stp-prov"].textContent, "", "sem aviso quando a arte final existe");
});
t("setup: marcas só dos sinais ativados e o desenho não quebra com marcas fora da tela", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, setup: { evento: null, marcas: [{ id: "a", candle: 120, preco: 11.3, direcao: "alta", setup: "larry_williams", estado: "aceito", meu: true }, { id: "b", candle: 9999, preco: 11, direcao: "baixa", setup: "x", estado: "recusado", meu: false }] } }));
  yes(!h.els.stp._c.has("on"), "marca sozinha não liga o overlay");
});

t("setup: o cartão de decisão traz ícone, direção, entrada, stop, alvo, risco/retorno e a saída do método", () => {
  const h = carregar(); const e = evSetup({ decorrido_ms: 4500, restante_ms: 4500 }); e.evento.setup.id = "setup_classico"; e.evento.setup.resumo = "Rompimento de pivô."; e.evento.setup.saida = "Na perda do stop ou no alvo.";
  h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: e }));
  eq(h.els["stp-nome"].textContent, "Larry Williams"); eq(h.els["stp-bd"].textContent, "COMPRA"); yes(h.els["stp-ic"].innerHTML.includes("<svg"), "ícone do setup");
  const tl = h.els["stp-dt"].innerHTML; yes(tl.includes("Entrada") && tl.includes("Stop") && tl.includes("Alvo"), "entrada, stop e alvo");
  yes(h.els["stp-rr"].innerHTML.includes("1:2") && h.els["stp-rr"].innerHTML.includes("Na perda do stop ou no alvo."), "risco/retorno calculado dos números reais e saída do setup");
  h.els["stp-x"].onclick(); eq(h.acoes().filter(x => x.evento === "setup").map(x => x.dados), [{ acao: "recusar" }]);   // o X do cartão é RECUSAR
});
t("setup: sem alvo fixo o cartão diz isso; o adversário não vê risco/retorno nem o X", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ alvo: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  yes(h.els["stp-rr"].innerHTML.includes("sem alvo fixo"), "método sem alvo");
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ voce_e_dono: false, dono: "Jogador 2", pode_decidir: false, stop: null, alvo: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h2.els["stp-rr"].style.display, "none"); eq(h2.els["stp-x"].style.display, "none");
});
t("setup: o gráfico dá zoom em volta do alvo durante a aquisição e o travamento e volta ao normal na janela de decisão", () => {
  const z = (dec) => { const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: dec, restante_ms: 9000 - dec }) })); h.sb.draw(); return h.els.cv.style.transform || ""; };
  eq(z(300), "", "detecção: ainda sem zoom");
  yes(/scale\(1\.[0-9]+\)/.test(z(1500)), "aquisição: aproximando");
  yes(/scale\(2\.[0-9]+\)/.test(z(3000)), "travamento: bem próximo");
  eq(z(4600), "", "janela de decisão: gráfico normal para ler");
});
t("setup: quando o evento acaba o zoom é desfeito", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 3000, restante_ms: 6000 }) })); h.sb.draw();
  yes(h.els.cv.style.transform, "com zoom");
  h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, setup: { evento: null, marcas: [] } })); eq(h.els.cv.style.transform || "", "");
});
t("estrutura da página: as divs fecham certo (uma a mais fecha o gráfico/aplicativo antes da hora e a boleta some) e a boleta está dentro do app", () => {
  const corpo = html.split("<script>")[0], abre = (corpo.match(/<div[\s>]/g) || []).length, fecha = (corpo.match(/<\/div>/g) || []).length;
  eq(abre, fecha, "divs abertas x fechadas");
  const i = corpo.indexOf('<div id="app">'); let prof = 0, re = /<div[\s>]|<\/div>/g, m, iMesa = corpo.indexOf('<div id="mesa">'), dentro = null;
  while ((m = re.exec(corpo))) { if (m.index < i) continue; prof += m[0] === "</div>" ? -1 : 1; if (m.index === iMesa) dentro = prof > 1; if (prof === 0) { yes(m.index > iMesa, "o app fechou antes da boleta"); break } }
  yes(dentro, "a boleta precisa estar dentro do #app");
});
t("setup: na janela de decisão o gráfico já marca entrada, stop e alvo do setup (só para o dono)", () => {
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h.sb.svNiveis().map(n => n.t + ":" + n.p), ["entrada:11.3", "stop:11", "alvo:11.9"]);
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ decorrido_ms: 1500, restante_ms: 7500 }) }));
  eq(h2.sb.svNiveis().length, 0, "durante a animação ainda não");
  const h3 = carregar(); h3.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ voce_e_dono: false, dono: "Jogador 2", pode_decidir: false, stop: null, alvo: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h3.sb.svNiveis().length, 0, "o adversário não vê níveis");
});
t("setup: depois de aceitar, enquanto a ordem está na fila, stop e alvo continuam à vista até a posição aparecer", () => {
  const marcas = [{ id: "a", candle: 120, preco: 11.3, direcao: "alta", setup: "x", estado: "aceito", meu: true, stop: 11.0, alvo: 11.9, protegido: true }];
  const m = mesaQtd(false); m.fila = [{ direcao: "alta", q: 100, reduz: false }];
  const h = carregar(); h.render(args({ motor: 2, mesa: m, corrida: true, lote: 100, setup: { evento: null, marcas } }));
  eq(h.sb.svNiveis().map(n => n.t), ["stop", "alvo"]);
  const m2 = mesaQtd(true); m2.posicao.stop = 11.0; m2.posicao.alvo = 11.9; m2.ordens = [{ id: "stop", preco: 11.0 }, { id: "alvo", preco: 11.9 }];
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: m2, corrida: true, lote: 100, setup: { evento: null, marcas } }));
  eq(h2.sb.svNiveis().length, 0, "com a posição já com stop e alvo, as linhas são as dela");
});
t("setup: entrada sem proteção (o preço já passou) avisa uma vez; a dica de arrastar não aparece quando o setup já pôs stop e alvo", () => {
  const marcas = [{ id: "a", candle: 120, preco: 11.3, direcao: "alta", setup: "x", estado: "aceito", meu: true, stop: 11.0, alvo: 11.9, protegido: false }];
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaQtd(true), corrida: true, lote: 100, setup: { evento: null, marcas } }));
  yes(h.els.dica.textContent.includes("passou do stop ou do alvo do setup"), "aviso na tela");
  h.render(args({ motor: 2, mesa: mesaQtd(true), corrida: true, lote: 100, setup: { evento: null, marcas } })); yes(h.els.dica.textContent.includes("passou do stop"), "e não é trocado pela dica genérica");
  const h2 = carregar(); const m = mesaQtd(true); m.posicao.stop = 11.0; m.posicao.alvo = 11.9;
  h2.render(args({ motor: 2, mesa: m, corrida: true, lote: 100, setup: { evento: null, marcas: [{ ...marcas[0], protegido: true }] } }));
  yes(!h2.els.dica.textContent.includes("Arraste a linha da entrada"), "sem a dica de arrastar");
});
t("setup de padrão de candle: a região marcada aparece na janela de decisão só para o dono", () => {
  const reg = { id: "r", tipo: "suporte", min: 11.0, max: 11.2 };
  const h = carregar(); h.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ regiao: reg, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h.sb.svRegiao(), reg); h.sb.draw();
  const h2 = carregar(); h2.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ regiao: reg, decorrido_ms: 1500, restante_ms: 7500 }) }));
  eq(h2.sb.svRegiao(), null, "durante a animação ainda não");
  const h3 = carregar(); h3.render(args({ motor: 2, mesa: mesaSem(), corrida: true, pausada: true, setup: evSetup({ voce_e_dono: false, dono: "Jogador 2", pode_decidir: false, stop: null, alvo: null, regiao: null, decorrido_ms: 4500, restante_ms: 4500 }) }));
  eq(h3.sb.svRegiao(), null, "o adversário não vê a região");
});
console.log(`\n${ok} passaram, ${falhas} falharam`); process.exit(falhas ? 1 : 0);
