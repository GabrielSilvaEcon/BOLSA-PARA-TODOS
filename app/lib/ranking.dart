import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'navegacao.dart';

/// Ranking Geral, igual ao do app antigo (jogos_app.pagina_ranking): cabeçalho com o troféu, abas da Central, escolha do jogo
/// (Trade Battle ou Ticker Battle), pódio dos 3 primeiros, sua posição e a classificação com a variação do dia.
/// Dados do servidor (`GET /ranking/{jogo}/tela`).
class RankingTela extends StatefulWidget {
  const RankingTela({super.key, required this.api});
  final Api api;

  @override
  State<RankingTela> createState() => _RankingTelaState();
}

const _ouro = Color(0xFFF2B84B);
const _lila = Color(0xFFBDB5E6);

class _RankingTelaState extends State<RankingTela> {
  String _jogo = 'trade';
  Map<String, dynamic>? _d;
  bool _carregando = true;
  bool _falhou = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _falhou = false;
    });
    try {
      final r = await widget.api.get('/ranking/$_jogo/tela');
      if (mounted) setState(() => _d = r);
    } catch (_) {
      if (mounted) setState(() => _falhou = true);
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  void _trocarJogo(String j) {
    if (j == _jogo) return;
    setState(() {
      _jogo = j;
      _d = null;
    });
    _carregar();
  }

  void _emBreve(String nome) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$nome: chega na próxima etapa do app novo')));

  String _valor(Object? v) {
    if (v is! num) return '';
    if (_jogo == 'trade') {
      final s = v.abs().toStringAsFixed(1).replaceAll('.', ',');
      return '${v > 0 ? '+' : v < 0 ? '−' : ''}$s pts';
    }
    final n = v.toInt();
    return '$n vitória${n == 1 ? '' : 's'}';
  }

  @override
  Widget build(BuildContext context) {
    final linhas = ((_d?['linhas'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final total = (_d?['total'] as num?)?.toInt() ?? 0;
    final eu = _d?['eu'] as Map<String, dynamic>?;
    final resto = linhas.length > 3 ? linhas.sublist(3) : const <Map<String, dynamic>>[];
    final euFora = eu != null && (eu['pos'] as num) > 3 + resto.length;
    return Scaffold(
      backgroundColor: const Color(0xFF110C2E),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/jogos/fundo_batalha.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x99090722), Color(0xB8090722), Color(0xE0090722)],
                stops: [0, 0.4, 1],
              ),
            ),
          ),
          RefreshIndicator(
            onRefresh: _carregar,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 20),
                  children: [
                    _cab(),
                    const SizedBox(height: 8),
                    _abasCentral(),
                    const SizedBox(height: 10),
                    _seletor(),
                    const SizedBox(height: 10),
                    if (_carregando && _d == null)
                      const Padding(padding: EdgeInsets.all(30), child: Center(child: CircularProgressIndicator()))
                    else if (_falhou && _d == null)
                      _vazio('O ranking não carregou agora. Tente de novo em instantes.')
                    else if (total == 0) ...[
                      _vazio('Ainda ninguém terminou uma partida do ${_d?['nome'] ?? ''}. Seja o primeiro!'),
                      const SizedBox(height: 8),
                      FilledButton.icon(
                        onPressed: () => abrirAba(1),
                        icon: const Icon(Icons.play_arrow_rounded),
                        label: Text('Jogar ${_d?['nome'] ?? ''}'),
                      ),
                    ] else ...[
                      _card(_jogo == 'trade'
                          ? 'Classificação por pontos acumulados nas partidas terminadas. Variação ▲▼ desde o início do dia.'
                          : 'Classificação por vitórias nos duelos (contra o sistema e online). Variação ▲▼ desde o início do dia.'),
                      const SizedBox(height: 6),
                      _podio(linhas.take(3).toList()),
                      if (euFora) ...[
                        _sec('Sua posição', null),
                        _lista([eu]),
                      ],
                      if (resto.isNotEmpty) ...[
                        _sec('Classificação', '$total jogador${total == 1 ? '' : 'es'}'),
                        _lista(resto),
                      ],
                      const SizedBox(height: 10),
                      Text('Atualizado às ${_d?['hora'] ?? '--:--'}',
                          style: const TextStyle(fontSize: 12, color: _lila)),
                      const SizedBox(height: 6),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: _carregar,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Atualizar agora'),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- cabeçalho da Central: troféu, "Ranking Geral" e a frase
  Widget _cab() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0x8CF2B84B), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF241A86), Color(0xFF0E0840)]),
        boxShadow: const [BoxShadow(color: Color(0x598B6CFF), blurRadius: 18)],
      ),
      child: Row(
        children: [
          Image.asset('assets/jogos/trofeu.webp', width: 78),
          const SizedBox(width: 10),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Ranking Geral',
                    style: TextStyle(
                      fontSize: 21.6,
                      height: 1.05,
                      fontWeight: FontWeight.w900,
                      fontStyle: FontStyle.italic,
                      color: Color(0xFFFFC93C),
                      shadows: [Shadow(color: Color(0x73FFC93C), blurRadius: 12)],
                    )),
                SizedBox(height: 3),
                Text('Cada jogo com a sua classificação.', style: TextStyle(fontSize: 12.2, color: Color(0xFFD9D4F7))),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _abasCentral() {
    const abas = [
      ('Central', Icons.sports_esports),
      ('Trade', Icons.show_chart),
      ('Ticker', Icons.style),
      ('Ranking', Icons.emoji_events),
      ('Amigos', Icons.group),
      ('Eventos', Icons.redeem),
    ];
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: abas.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (_, i) {
          final (rot, ic) = abas[i];
          final on = rot == 'Ranking';
          return GestureDetector(
            onTap: () {
              if (rot == 'Central' || rot == 'Trade') {
                abrirAba(1);
              } else if (!on) {
                _emBreve(rot);
              }
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                gradient: on ? const LinearGradient(colors: [Color(0xFF7C5CFF), Color(0xFFB06BFF)]) : null,
                color: on ? null : const Color(0xFF1B1442),
                border: Border.all(color: on ? const Color(0xFFB9A8FF) : const Color(0x558B6CFF)),
                boxShadow: on ? const [BoxShadow(color: Color(0x998B6CFF), blurRadius: 12)] : null,
              ),
              child: Row(
                children: [
                  Icon(ic, size: 16, color: Colors.white),
                  const SizedBox(width: 5),
                  Text(rot, style: const TextStyle(fontSize: 12.8, fontWeight: FontWeight.w800, color: Colors.white)),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ---- escolha do jogo
  Widget _seletor() {
    Widget op(String j, String rot) {
      final on = j == _jogo;
      return Expanded(
        child: GestureDetector(
          onTap: () => _trocarJogo(j),
          child: Container(
            height: 40,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: on ? const LinearGradient(colors: [Color(0xFF7C5CFF), Color(0xFFB06BFF)]) : null,
              color: on ? null : const Color(0xFF1B1442),
              border: Border.all(color: on ? const Color(0xFFB9A8FF) : const Color(0x558B6CFF)),
            ),
            child: Text(rot, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white)),
          ),
        ),
      );
    }

    return Row(children: [op('trade', 'Trade Battle'), const SizedBox(width: 6), op('ticker', 'Ticker Battle')]);
  }

  Widget _card(String texto) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFF5B4BD6), width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1B1470), Color(0xFF0E0840)]),
          boxShadow: const [BoxShadow(color: Color(0x665B4BD6), blurRadius: 12)],
        ),
        child: Text(texto, style: const TextStyle(fontSize: 12.8, height: 1.35, color: Color(0xFFD9D4F7))),
      );

  Widget _vazio(String texto) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0x8C8B6CFF), width: 1.5),
        ),
        child: Text(texto, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13.8, color: Color(0xFFD9D4F7))),
      );

  Widget _sec(String t, String? extra) => Padding(
        padding: const EdgeInsets.fromLTRB(2, 12, 2, 4),
        child: Row(
          children: [
            Text(t, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
            const Spacer(),
            if (extra != null) Text(extra, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: _lila)),
          ],
        ),
      );

  // ---- pódio: 2º, 1º e 3º lado a lado, com as bases de alturas diferentes
  Widget _podio(List<Map<String, dynamic>> top) {
    const cores = [Color(0xFF9EA3C6), Color(0xFFE0A21A), Color(0xFFB0612A)];
    const alturas = [54.0, 74.0, 42.0];
    const tamanhos = [52.0, 64.0, 52.0];
    final ordem = [1, 0, 2];
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        for (var k = 0; k < 3; k++) ...[
          if (k > 0) const SizedBox(width: 6),
          Expanded(
            flex: k == 1 ? 115 : 100,
            child: ordem[k] < top.length
                ? Column(
                    children: [
                      _avatar(top[ordem[k]]['avatar_img'], tamanhos[k], cores[k], 3),
                      const SizedBox(height: 4),
                      Text('${top[ordem[k]]['nome'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12.2, fontWeight: FontWeight.w800, color: Colors.white)),
                      Text(_valor(top[ordem[k]]['valor']), style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: Color(0xFFFFE3A3))),
                      const SizedBox(height: 4),
                      Container(
                        height: alturas[k],
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                          gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [cores[k], const Color(0xE6140C40)]),
                          boxShadow: [BoxShadow(color: cores[k], blurRadius: 14)],
                        ),
                        child: Text('${top[ordem[k]]['pos']}',
                            style: const TextStyle(fontSize: 25.6, fontWeight: FontWeight.w900, color: Colors.white)),
                      ),
                    ],
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ],
    );
  }

  // ---- lista da classificação
  Widget _lista(List<Map<String, dynamic>> linhas) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFF5B4BD6), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF17114A), Color(0xFF0A0720)], stops: [0, 0.9]),
      ),
      child: Column(
        children: [for (final (i, x) in linhas.indexed) _linha(x, primeira: i == 0)],
      ),
    );
  }

  Widget _linha(Map<String, dynamic> x, {bool primeira = false}) {
    final eu = x['eu'] == true;
    final v = (x['valor'] as num?) ?? 0;
    final p = (x['partidas'] as num?)?.toInt() ?? 0;
    final variacao = x['var'] as num?;
    final (txtVar, corVar) = variacao == null
        ? ('—', const Color(0xFF8E87D8))
        : variacao > 0
            ? ('▲$variacao', const Color(0xFF6BFF8A))
            : variacao < 0
                ? ('▼${-variacao}', const Color(0xFFFF6B87))
                : ('=', const Color(0xFF8E87D8));
    return Container(
      margin: eu ? const EdgeInsets.symmetric(vertical: 2) : EdgeInsets.zero,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
      decoration: eu
          ? BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _ouro, width: 2),
              gradient: const LinearGradient(colors: [Color(0x47F2B84B), Color(0x0FF2B84B)]),
              boxShadow: const [BoxShadow(color: Color(0x59F2B84B), blurRadius: 12)],
            )
          : BoxDecoration(border: primeira ? null : const Border(top: BorderSide(color: Color(0x14FFFFFF)))),
      child: Row(
        children: [
          SizedBox(width: 30, child: Text('${x['pos']}', style: const TextStyle(fontWeight: FontWeight.w900, color: _lila))),
          _avatar(x['avatar_img'], 30, const Color(0xFF6C5CFF), 1.5),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${x['nome'] ?? ''}${eu ? ' (você)' : ''}', maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.white)),
                Text('$p partida${p == 1 ? '' : 's'}', style: const TextStyle(fontSize: 10.6, fontWeight: FontWeight.w600, color: _lila)),
              ],
            ),
          ),
          Text(_valor(v),
              style: TextStyle(fontWeight: FontWeight.w700, color: v < 0 ? const Color(0xFFFF6B87) : const Color(0xFF6BFF8A))),
          SizedBox(
            width: 38,
            child: Text(txtVar, textAlign: TextAlign.right, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: corVar)),
          ),
        ],
      ),
    );
  }

  Widget _avatar(Object? img, double tam, Color cor, double aro) {
    final texto = img is String && img.isNotEmpty ? img : null;
    final reserva = Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.cover);
    return Container(
      width: tam,
      height: tam,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xFF1B1545),
        boxShadow: [BoxShadow(color: cor, spreadRadius: aro), if (aro > 2) BoxShadow(color: cor, blurRadius: 14)],
      ),
      child: ClipOval(
        child: texto == null
            ? reserva
            : texto.startsWith('data:')
                ? Image.memory(base64Decode(texto.substring(texto.indexOf(',') + 1)), fit: BoxFit.cover, errorBuilder: (_, __, ___) => reserva)
                : Image.asset('assets/$texto', fit: BoxFit.cover, errorBuilder: (_, __, ___) => reserva),
      ),
    );
  }
}
