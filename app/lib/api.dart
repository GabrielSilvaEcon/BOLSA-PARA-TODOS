import 'dart:convert';

import 'package:http/http.dart' as http;


/// Servidor do jogo (api/main.py, já no ar no Render). Mesmo motor do app atual.
const String apiBase = 'https://tickerhunters-api.onrender.com';

class ApiErro implements Exception {
  ApiErro(this.mensagem);
  final String mensagem;
  @override
  String toString() => mensagem;
}

/// Chamadas ao servidor. O token é lido a cada chamada (o Supabase renova o token sozinho).
class Api {
  Api({this.tokenAtual});
  final String? Function()? tokenAtual;

  Map<String, String> get _cabecalhos {
    final t = tokenAtual?.call();
    return {
      'Content-Type': 'application/json',
      if (t != null && t.isNotEmpty) 'Authorization': 'Bearer $t',
    };
  }

  /// Chamadas com nova tentativa: o servidor grátis "dorme" e leva alguns segundos para acordar.
  /// Tenta até 4 vezes (esperas de 2, 4 e 8 s) quando não há resposta ou o servidor responde 5xx.
  Future<Map<String, dynamic>> get(String caminho) => _com_tentativas(() => http.get(Uri.parse('$apiBase$caminho'), headers: _cabecalhos));

  Future<Map<String, dynamic>> post(String caminho, [Map<String, dynamic>? corpo]) => _com_tentativas(
        () => http.post(Uri.parse('$apiBase$caminho'), headers: _cabecalhos, body: jsonEncode(corpo ?? {})),
      );

  Future<Map<String, dynamic>> _com_tentativas(Future<http.Response> Function() chamada) async {
    const esperas = [Duration(seconds: 2), Duration(seconds: 4), Duration(seconds: 8)];
    for (var i = 0; ; i++) {
      try {
        final r = await chamada().timeout(const Duration(seconds: 45));
        if (r.statusCode >= 500 && i < esperas.length) {
          await Future.delayed(esperas[i]);
          continue;
        }
        return _ler(r);
      } catch (e) {
        if (e is ApiErro || i >= esperas.length) rethrow;
        await Future.delayed(esperas[i]);
      }
    }
  }

  Map<String, dynamic> _ler(http.Response r) {
    final dados = r.body.isEmpty ? <String, dynamic>{} : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 400) {
      final msg = dados is Map && dados['detail'] != null ? dados['detail'].toString() : 'Erro ${r.statusCode}';
      throw ApiErro(msg);
    }
    return dados as Map<String, dynamic>;
  }
}
