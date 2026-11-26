// Argumentos de teste da mesa (candles sintéticos + evento de setup).
function args(T, comEvento) {
  let px = 50, cs = [];
  for (let i = 0; i < 356; i++) { const o = px, c = o + Math.sin(i / 4) * 0.25 - 0.02; cs.push({ t: '2026-01-05T10:' + String(i % 60).padStart(2, '0'), o, h: Math.max(o, c) + 0.12, l: Math.min(o, c) - 0.12, c, v: 1000 }); px = c; }
  const mesa = { qtd: true, capital: 10000, poder: 10000, max_q: 884, exposicao: 0, exposicao_pct: 0, stake: 1000, pat_ini: 100000, posicao: null, ordens: [], operacoes: [], fila: [], n_encerradas: 0, realizado_pct: 0, realizado_val: 0, aberto_pct: 0, aberto_val: 0, aberto_txt: '0', acum_txt: '0', cor_aberto: 'zero', cor_acum: 'zero', pode_abrir: true, pode_encerrar: false, pode_cancelar: false, pode_gerir: false, aposta_txt: 'Capital', preco_atual: cs[355].c, limite: { bloqueado: false, usado_pct_cap: 0 } };
  const ev = { sinal: 'p:1:355', setup: { id: 'engolfo_alta', nome: 'Engolfo de Alta', raridade: 'rara', cores: { principal: '#FF4D6D', brilho: '#FFC2CC' }, assets: { ativacao: null, efeitos: [] } }, dono: 'Você', voce_e_dono: true, direcao: 'alta', candle: 355, preco: cs[355].c, stop: cs[355].c - 0.3, alvo: cs[355].c + 1, motivo: 'x', anim_ms: 4000, destaque_ms: 5000, janela_ms: 19000, decorrido_ms: T, restante_ms: 60000, pode_decidir: true,
    padrao: { candles: [354, 355], licao: { ideia: 'i', porque: 'p', partes: ['a', 'b'], rotulos: [{ k: 0, onde: 'corpo', txt: '1º: baixa' }, { k: 1, onde: 'corpo', txt: '2º: alta engole' }] } } };
  return { modo: 'replay', fase_key: '1-replay', adversarios: [], propria: null, operacao: null, marcas_ant: {}, resultado: null, multi: true, aposta_txt: 'Capital', prontos: null, seq0: 0, revelados: 56, total_replay: 56, prox_ms: 1500, candles: cs, ticker: 'TEST3', tf_nome: '15 minutos', demo: true, rodada: 1, rodadas: 1, seg: 50, ref: cs[355].c, token: 'tok', sr: { suportes: [], resistencias: [] }, inicial: { direcao: 'alta', tipo: 'continuacao', confianca: 3, marcas: {} }, limites: { niveis: 6, tendencias: 4, notas: 6 }, erro: '', erro_seq: 0, ok_seq: 0, corrida: true, lote: 10, motor: 2, mesa, pausada: !!comEvento, setup: { evento: comEvento ? ev : null, marcas: [], avisos: [] } };
}


module.exports = { args };
