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

  Future<Map<String, dynamic>> get(String caminho) async {
    final r = await http.get(Uri.parse('$apiBase$caminho'), headers: _cabecalhos).timeout(const Duration(seconds: 60));
    return _ler(r);
  }

  Future<Map<String, dynamic>> post(String caminho, [Map<String, dynamic>? corpo]) async {
    final r = await http
        .post(Uri.parse('$apiBase$caminho'), headers: _cabecalhos, body: jsonEncode(corpo ?? {}))
        .timeout(const Duration(seconds: 60));
    return _ler(r);
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
