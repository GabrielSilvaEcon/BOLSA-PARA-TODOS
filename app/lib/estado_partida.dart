/// Consulta INCREMENTAL da partida (acompanha o protocolo do servidor, ver `_enxuga` em api/main.py).
///
/// O servidor sempre sabe o estado completo; aqui o app guarda o último estado completo que recebeu e a versão dele (`e`):
///   · resposta `sem_mudanca` → reaproveita o estado guardado e só atualiza os campos que mudam a cada segundo (`vol`);
///   · resposta com `candles_cauda` → junta a cauda aos candles que já tem;
///   · resposta completa → substitui tudo.
/// Qualquer inconsistência (cauda que não encaixa, total diferente, estado sem base) devolve null: a resposta é descartada e a PRÓXIMA consulta pede o
/// estado completo. A cada [maxIncrementais] respostas incrementais seguidas o app também pede o completo (rede de segurança contra dessincronização).
class EstadoIncremental {
  static const maxIncrementais = 20;

  Map<String, dynamic>? _base;
  String? _e;
  int _seguidas = 0;

  bool get temBase => _base != null && _e != null;

  void reiniciar() {
    _base = null;
    _e = null;
    _seguidas = 0;
  }

  static double somaCandle(Map c) => double.parse(((c['o'] as num) + (c['h'] as num) + (c['l'] as num) + (c['c'] as num)).toDouble().toStringAsFixed(6));

  /// Endereço da próxima consulta: o mesmo [caminho], com `e`, `n`, `u` e `fk` quando há base confiável; sem parâmetros quando precisa do estado completo.
  String consulta(String caminho) {
    final b = _base;
    if (b == null || _e == null || _seguidas >= maxIncrementais) return caminho;
    final cs = b['candles'];
    if (cs is! List || cs.length < 2 || b['fase_key'] == null) return caminho;
    final ult = cs[cs.length - 2];
    if (ult is! Map) return caminho;
    return '$caminho?e=$_e&n=${cs.length}&u=${somaCandle(ult)}&fk=${Uri.encodeQueryComponent('${b['fase_key']}')}';
  }

  /// Transforma a resposta do servidor na resposta COMPLETA (a que o resto do app já entende). Null = descartar e pedir o completo.
  Map<String, dynamic>? aplicar(Map<String, dynamic> r) {
    final tela = r['tela'];
    if (r['sem_mudanca'] == true) {
      final b = _base;
      if (b == null || r['e'] != _e) {
        reiniciar();
        return null;
      }
      final nova = {...b, ...((r['vol'] as Map?)?.cast<String, dynamic>() ?? const {})};
      _base = nova;
      _seguidas++;
      return {...r, 'tela': nova}..remove('sem_mudanca')..remove('vol');
    }
    if (tela is! Map) {
      reiniciar();
      return r;
    }
    var t = Map<String, dynamic>.from(tela);
    if (t.containsKey('candles_cauda')) {
      final b = _base;
      final desde = (t['candles_desde'] as num?)?.toInt() ?? -1;
      final total = (t['candles_total'] as num?)?.toInt() ?? -1;
      final velhos = b == null ? null : b['candles'];
      final cauda = t['candles_cauda'];
      if (velhos is! List || cauda is! List || desde < 0 || desde > velhos.length || velhos.length < desde || desde + cauda.length != total) {
        reiniciar();
        return null;
      }
      t
        ..['candles'] = [...velhos.take(desde), ...cauda]
        ..remove('candles_cauda')
        ..remove('candles_desde')
        ..remove('candles_total');
      _seguidas++;
    } else {
      _seguidas = 0;
    }
    final completa = {...r, 'tela': t};
    if (r['e'] != null && t['candles'] is List) {
      _base = t;
      _e = '${r['e']}';
    } else {
      _base = null; // fim da partida, sala etc.: sem incremental
      _e = null;
    }
    return completa;
  }
}
