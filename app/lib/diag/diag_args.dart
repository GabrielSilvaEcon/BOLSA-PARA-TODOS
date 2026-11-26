import 'dart:math' as math;

/// Dados sintéticos da mesa para o teste automático (mesmos de medicao/mesa_args.js: 356 candles fixos e um setup de padrão "Engolfo de Alta").
/// Com [evento] a mesa recebe a ativação (mira 4 s → destaque 5 s → decisão); [n] muda o sinal para a mesa tratar como uma nova ativação.
Map<String, dynamic> diagArgs({required bool evento, int n = 0}) {
  var px = 50.0;
  final cs = <Map<String, dynamic>>[];
  for (var i = 0; i < 356; i++) {
    final o = px, c = o + math.sin(i / 4) * 0.25 - 0.02;
    cs.add({'t': '2026-01-05T10:${(i % 60).toString().padLeft(2, '0')}', 'o': o, 'h': math.max(o, c) + 0.12, 'l': math.min(o, c) - 0.12, 'c': c, 'v': 1000});
    px = c;
  }
  final c355 = (cs[355]['c'] as double);
  final mesa = {
    'qtd': true, 'capital': 10000, 'poder': 10000, 'max_q': 884, 'exposicao': 0, 'exposicao_pct': 0, 'stake': 1000, 'pat_ini': 100000, 'posicao': null,
    'ordens': [], 'operacoes': [], 'fila': [], 'n_encerradas': 0, 'realizado_pct': 0, 'realizado_val': 0, 'aberto_pct': 0, 'aberto_val': 0,
    'aberto_txt': '0', 'acum_txt': '0', 'cor_aberto': 'zero', 'cor_acum': 'zero', 'pode_abrir': true, 'pode_encerrar': false, 'pode_cancelar': false,
    'pode_gerir': false, 'aposta_txt': 'Capital', 'preco_atual': c355, 'limite': {'bloqueado': false, 'usado_pct_cap': 0},
  };
  final ev = {
    'sinal': 'p:1:355:$n',
    'setup': {'id': 'engolfo_alta', 'nome': 'Engolfo de Alta', 'raridade': 'rara', 'cores': {'principal': '#FF4D6D', 'brilho': '#FFC2CC'}, 'assets': {'ativacao': null, 'efeitos': []}},
    'dono': 'Você', 'voce_e_dono': true, 'direcao': 'alta', 'candle': 355, 'preco': c355, 'stop': c355 - 0.3, 'alvo': c355 + 1, 'motivo': 'x',
    'anim_ms': 4000, 'destaque_ms': 5000, 'janela_ms': 19000, 'decorrido_ms': 0, 'restante_ms': 28000, 'pode_decidir': true,
    'padrao': {
      'candles': [354, 355],
      'licao': {
        'ideia': 'i', 'porque': 'p', 'partes': ['a', 'b'],
        'rotulos': [{'k': 0, 'onde': 'corpo', 'txt': '1º: baixa'}, {'k': 1, 'onde': 'corpo', 'txt': '2º: alta engole'}],
      },
    },
  };
  return {
    'modo': 'replay', 'fase_key': '1-replay', 'adversarios': [], 'propria': null, 'operacao': null, 'marcas_ant': {}, 'resultado': null, 'multi': true,
    'aposta_txt': 'Capital', 'prontos': null, 'seq0': 0, 'revelados': 56, 'total_replay': 56, 'prox_ms': 1500, 'candles': cs, 'ticker': 'TEST3',
    'tf_nome': '15 minutos', 'demo': true, 'rodada': 1, 'rodadas': 1, 'seg': 50, 'ref': c355, 'token': 'tok', 'sr': {'suportes': [], 'resistencias': []},
    'inicial': {'direcao': 'alta', 'tipo': 'continuacao', 'confianca': 3, 'marcas': {}}, 'limites': {'niveis': 6, 'tendencias': 4, 'notas': 6}, 'erro': '',
    'erro_seq': 0, 'ok_seq': 0, 'corrida': true, 'lote': 10, 'motor': 2, 'mesa': mesa, 'pausada': evento,
    'setup': {'evento': evento ? ev : null, 'marcas': [], 'avisos': []},
  };
}
