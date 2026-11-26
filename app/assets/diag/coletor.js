/* Coletor de diagnóstico da mesa (SÓ no APK de testes). Injetado pelo app depois que a página carrega; não altera o desenho.
   Mede: intervalo entre quadros (requestAnimationFrame) por fase, tempo de JS do draw/efeitos, canvases criados, memória de JS e canvases vivos.
   Não mostra nada na tela. Fases: classico | mira | destaque | decisao (lidas do próprio estado da mesa). */
(function () {
  if (window.__diag) return;
  var T0 = performance.now(), EP0 = Date.now() - T0;
  var D = { rot: 'partida', fase: 'classico', last: 0, F: {}, trans: [], jank: [], mem: [], cvTot: 0, cvVivos: [], pronto: 0, pausas: 0, erros: [], janT: 0, janN: 0 };
  var HF = 201, HD = 201;   // histograma de quadros: 1 ms por balde (0..200); de JS: 0,5 ms por balde (0..100)
  function F(rot, f) {
    var k = rot + '|' + f;
    return D.F[k] || (D.F[k] = { rot: rot, fase: f, n: 0, soma: 0, max: 0, h: new Int32Array(HF), l25: 0, l34: 0, l50: 0, l100: 0, sec: [], dn: 0, ds: 0, dmax: 0, dh: new Int32Array(HD), fn: 0, fs: 0, fmax: 0, fh: new Int32Array(HD), cv: 0, ms: 0 });
  }
  function fase() {
    try {
      var ev = SVs.ev;
      if (!ev || svRest() <= 0) return 'classico';
      var t = svT(), A = ev.anim_ms, Dd = ev.destaque_ms || 0, bx = svPadraoBox(ev);
      if (t < A) return 'mira';
      if (bx && Dd > 0 && t < A + Dd) return 'destaque';
      return 'decisao';
    } catch (e) { return 'classico'; }
  }
  function envia(o) { try { if (window.Diag) Diag.postMessage(JSON.stringify(o)); } catch (e) {} }
  function reg(f, dt, t) {
    var s = F(D.rot, f);
    s.n++; s.soma += dt; if (dt > s.max) s.max = dt;
    s.h[Math.min(HF - 1, Math.round(dt))]++;
    if (dt > 25) s.l25++; if (dt > 34) s.l34++; if (dt > 50) s.l50++; if (dt > 100) s.l100++;
    if (dt > 34 && D.jank.length < 400) D.jank.push({ t: Math.round(t - T0), dt: Math.round(dt), fase: f, rot: D.rot });
    // janela de 1 s (descartada quando a fase muda): FPS de cada segundo
    if (!D.janT) { D.janT = t; D.janN = 0; }
    D.janN++;
    if (t - D.janT >= 1000) { if (s.sec.length < 4000) s.sec.push(+(D.janN * 1000 / (t - D.janT)).toFixed(1)); D.janT = t; D.janN = 0; }
  }
  function reg2(nome, ms) {
    var s = F(D.rot, D.fase);
    if (nome === 'draw') { s.dn++; s.ds += ms; if (ms > s.dmax) s.dmax = ms; s.dh[Math.min(HD - 1, Math.round(ms * 2))]++; }
    else { s.fn++; s.fs += ms; if (ms > s.fmax) s.fmax = ms; s.fh[Math.min(HD - 1, Math.round(ms * 2))]++; }
  }
  function loop(t) {
    var f = fase();
    if (f !== D.fase) {
      D.trans.push({ t: Math.round(t - T0), de: D.fase, para: f, rot: D.rot });
      D.fase = f; D.janT = 0;
      envia({ k: 'fase', fase: f, ep: Math.round(EP0 + t) });
    }
    if (D.last) { var dt = t - D.last; if (dt < 2000) reg(f, dt, t); else D.pausas++; }
    D.last = t;
    requestAnimationFrame(loop);
  }
  function envolve(nome, chave) {
    try {
      var o = window[nome];
      if (typeof o !== 'function' || o.__d) return;
      var w = function () {
        var a = performance.now();
        try { return o.apply(this, arguments); }
        finally {
          reg2(chave, performance.now() - a);
          if (!D.pronto && chave === 'draw' && typeof S !== 'undefined' && S && typeof W !== 'undefined' && W) {
            D.pronto = 1; envia({ k: 'pronto', ep: Math.round(EP0 + performance.now()) });
          }
        }
      };
      w.__d = 1; window[nome] = w;
    } catch (e) { D.erros.push('envolve ' + nome + ': ' + e); }
  }
  // canvases criados (churn de alocação) e vivos (memória estimada do backing store)
  try {
    var ce = document.createElement;
    document.createElement = function (n) {
      var e = ce.apply(document, arguments);
      try {
        if (String(n).toLowerCase() === 'canvas') {
          D.cvTot++; F(D.rot, D.fase).cv++;
          if (D.cvVivos.length < 6000 && typeof WeakRef !== 'undefined') D.cvVivos.push(new WeakRef(e));
        }
      } catch (x) {}
      return e;
    };
  } catch (e) { D.erros.push('createElement: ' + e); }
  function memoria() {
    var m = {}, vivos = 0, px = 0, dom = 0, i, c;
    try { var pm = performance.memory; if (pm) { m.jsUsado = pm.usedJSHeapSize; m.jsTotal = pm.totalJSHeapSize; m.jsLimite = pm.jsHeapSizeLimit; } } catch (e) {}
    try {
      var vv = [];
      for (i = 0; i < D.cvVivos.length; i++) { c = D.cvVivos[i].deref(); if (c) { vv.push(D.cvVivos[i]); vivos++; px += (c.width || 0) * (c.height || 0); } }
      D.cvVivos = vv;
      var cs = document.getElementsByTagName('canvas');
      for (i = 0; i < cs.length; i++) { dom++; px += (cs[i].width || 0) * (cs[i].height || 0); }
      m.canvasVivosCriados = vivos; m.canvasNoDom = dom; m.canvasPx = px; m.canvasMB = +(px * 4 / 1048576).toFixed(2);
      m.nos = document.getElementsByTagName('*').length;
    } catch (e) {}
    m.t = Math.round(performance.now() - T0); m.ep = Math.round(EP0 + performance.now()); m.rot = D.rot; m.fase = D.fase;
    return m;
  }
  function pct(h, q, passo) {
    var tot = 0, i; for (i = 0; i < h.length; i++) tot += h[i];
    if (!tot) return 0;
    var alvo = Math.ceil(tot * q), acc = 0;
    for (i = 0; i < h.length; i++) { acc += h[i]; if (acc >= alvo) return i * passo; }
    return (h.length - 1) * passo;
  }
  function snap() {
    var out = [], k, s;
    for (k in D.F) {
      s = D.F[k]; if (!s.n && !s.dn && !s.fn) continue;
      var sec = s.sec.slice().sort(function (a, b) { return a - b; });
      out.push({
        rot: s.rot, fase: s.fase, quadros: s.n, segundos: +(s.soma / 1000).toFixed(2),
        fpsMedio: s.soma ? +(s.n * 1000 / s.soma).toFixed(1) : 0,
        fpsMinSeg: sec.length ? sec[0] : null, fpsP5Seg: sec.length ? sec[Math.floor(sec.length * 0.05)] : null, janelas1s: sec.length,
        quadroMedioMs: s.n ? +(s.soma / s.n).toFixed(2) : 0, quadroP50Ms: pct(s.h, 0.5, 1), quadroP95Ms: pct(s.h, 0.95, 1), quadroP99Ms: pct(s.h, 0.99, 1), quadroMaxMs: +s.max.toFixed(1),
        quadrosAcima25ms: s.l25, quadrosAcima34ms: s.l34, quadrosAcima50ms: s.l50, quadrosAcima100ms: s.l100,
        drawN: s.dn, drawMedioMs: s.dn ? +(s.ds / s.dn).toFixed(2) : 0, drawP95Ms: pct(s.dh, 0.95, 0.5), drawMaxMs: +s.dmax.toFixed(1),
        efeitosN: s.fn, efeitosMedioMs: s.fn ? +(s.fs / s.fn).toFixed(2) : 0, efeitosP95Ms: pct(s.fh, 0.95, 0.5), efeitosMaxMs: +s.fmax.toFixed(1),
        canvasCriados: s.cv
      });
    }
    return { rot: D.rot, fases: out, trans: D.trans.slice(-200), jank: D.jank.slice(), mem: D.mem.slice(-400), canvasCriadosTotal: D.cvTot, pausas: D.pausas, erros: D.erros.slice(), dprPagina: window.devicePixelRatio, tela: [window.innerWidth, window.innerHeight] };
  }
  function enviar() { envia({ k: 'snap', d: snap() }); }
  window.__diag = {
    rot: function (r) { D.rot = r; D.janT = 0; },
    mem: function (rot) { var m = memoria(); m.marco = rot || ''; D.mem.push(m); envia({ k: 'mem', d: m }); },
    enviar: enviar, snap: snap
  };
  var tent = 0;
  (function acha() {
    if (typeof draw === 'function' && typeof desenhaMira === 'function') { envolve('draw', 'draw'); envolve('desenhaMira', 'efeitos'); }
    else if (tent++ < 50) setTimeout(acha, 100);
  })();
  requestAnimationFrame(loop);
  setInterval(function () { var m = memoria(); D.mem.push(m); if (D.mem.length > 600) D.mem.shift(); }, 5000);
  setInterval(enviar, 10000);
  document.addEventListener('visibilitychange', function () { if (document.hidden) enviar(); });
  window.addEventListener('pagehide', enviar);
  window.addEventListener('error', function (e) { if (D.erros.length < 30) D.erros.push(String(e.message) + ' @' + (e.lineno || '')); });
  window.addEventListener('unhandledrejection', function (e) { if (D.erros.length < 30) D.erros.push('rejeição: ' + e.reason); });
  envia({ k: 'ok', ep: Date.now() });
})();
