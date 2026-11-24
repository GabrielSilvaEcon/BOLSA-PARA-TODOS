import 'package:flutter/material.dart';

import 'ajuda.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'eventos.dart';
import 'historico.dart';
import 'navegacao.dart';
import 'ticker.dart';
import 'trade.dart';

/// Central de Jogos ("Mundo dos Jogos!"), igual à do app antigo (jogos_app.pagina_central + design/kit.topo):
/// topo com a arte dos jogos e "Ver como funciona", os dois jogos (Trade Battle e Ticker Battle), Sua Evolução,
/// Desafio da Semana e os atalhos. Dados do servidor (`GET /jogos/central`).
class JogosTela extends StatefulWidget {
  const JogosTela({super.key, required this.api});
  final Api api;

  @override
  State<JogosTela> createState() => _JogosTelaState();
}

const _verde = Color(0xFF34E85E);
const _roxo = Color(0xFF6CA3FF);
const _ouro = Color(0xFFF2B84B);
const _lila = Color(0xFFD4E2F7);

class _JogosTelaState extends State<JogosTela> {
  Map<String, dynamic>? _d;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/jogos/central');
      if (mounted) setState(() => _d = r);
    } catch (_) {
      if (mounted) setState(() => _d = const {});
    }
  }

  void _emBreve(String nome) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$nome: chega na próxima etapa do app novo')));

  void _comoFunciona() {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF10274A),
        title: const Text('Como funciona', style: TextStyle(fontWeight: FontWeight.w900)),
        content: const SingleChildScrollView(
          child: Text.rich(
            TextSpan(
              style: TextStyle(fontSize: 14, height: 1.4, color: Color(0xFFE9F1FF)),
              children: [
                TextSpan(text: 'Trade Battle', style: TextStyle(fontWeight: FontWeight.w900)),
                TextSpan(
                    text: ' · Analise o gráfico, decida a operação e veja o replay. Os pontos vêm do resultado das suas operações. '
                        'Jogue sozinho ou numa sala com 2 a 4 amigos.\n\n'),
                TextSpan(text: 'Ticker Battle', style: TextStyle(fontWeight: FontWeight.w900)),
                TextSpan(text: ' · Duelo de cartas de ativos: em cada rodada vence o indicador real melhor. Contra o sistema ou online.\n\n'),
                TextSpan(text: 'XP', style: TextStyle(fontWeight: FontWeight.w900)),
                TextSpan(
                    text: ' · Você ganha XP pela colocação e pela pontuação, e ele nunca é negativo. O dinheiro do Trade Battle é só o lucro ou '
                        'prejuízo das suas operações, na sua carteira.\n\n'),
                TextSpan(text: 'Ranking', style: TextStyle(fontWeight: FontWeight.w900)),
                TextSpan(text: ' · Cada jogo tem o seu ranking. Desafie amigos pelo botão Amigos da tela inicial e acompanhe eventos e recompensas.'),
              ],
            ),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Fechar'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0C192E),
      body: Stack(
        fit: StackFit.expand,
        children: [
          const FundoCidade(),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x80090722), Color(0x9E090722), Color(0xD6090722)],
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
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 20),
                  children: [
                    _topo(),
                    _titulo('🎮 Nossos Jogos'),
                    IntrinsicHeight(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(
                            child: _jogo(
                              cor: _verde,
                              arte: 'assets/jogos/trade_hero.webp',
                              frase: 'Desafie outros jogadores em batalhas de trade!',
                              botao: const [Color(0xFF2EE86B), Color(0xFF14C98F)],
                              texto: const Color(0xFF06240F),
                              acao: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => TradeTela(api: widget.api))),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _jogo(
                              cor: _roxo,
                              arte: 'assets/jogos/ticker_hero.webp',
                              frase: 'Mostre seu conhecimento e suba no ranking!',
                              botao: const [Color(0xFF5C92F6), Color(0xFF2862D9)],
                              texto: Colors.white,
                              acao: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => TickerTela(api: widget.api))),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(2, 18, 2, 8),
                      child: Row(
                        children: [
                          const Expanded(
                            child: Text('📈 Sua Evolução', style: TextStyle(fontSize: 18.4, fontWeight: FontWeight.w900, color: Colors.white)),
                          ),
                          GestureDetector(
                            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => HistoricoTela(api: widget.api))),
                            child: const Text('Ver detalhes ›', style: TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF9CBFFF))),
                          ),
                        ],
                      ),
                    ),
                    _evolucao(),
                    if (_d?['desafio'] is Map) _desafio(_d!['desafio'] as Map),
                    const SizedBox(height: 12),
                    _atalhos(),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- topo do kit (arte à direita, título com a última palavra em verde, "Ver como funciona" dentro do cartão)
  Widget _topo() {
    return Container(
      constraints: const BoxConstraints(minHeight: 138),
      decoration: BoxDecoration(
        color: const Color(0xFF081528),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _verde.withValues(alpha: 0.6), width: 2),
        boxShadow: [BoxShadow(color: _verde.withValues(alpha: 0.22), blurRadius: 20)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: Stack(
          children: [
            Positioned.fill(
              child: Align(
                alignment: Alignment.centerRight,
                child: FractionallySizedBox(
                  widthFactor: 0.58,
                  heightFactor: 1,
                  child: ShaderMask(
                    blendMode: BlendMode.dstIn,
                    shaderCallback: (r) => const LinearGradient(
                      colors: [Colors.transparent, Colors.white],
                      stops: [0, 0.4],
                    ).createShader(r),
                    child: Image.asset('assets/jogos/topo_jogos.webp', fit: BoxFit.cover, alignment: const Alignment(0, -0.56)),
                  ),
                ),
              ),
            ),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [const Color(0xFF091F40), const Color(0xFF091F40).withValues(alpha: 0)],
                    stops: const [0.34, 0.74],
                  ),
                ),
              ),
            ),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: Alignment.bottomLeft,
                    radius: 0.9,
                    colors: [const Color(0xFFFF6B87).withValues(alpha: 0.22), const Color(0xFFFF6B87).withValues(alpha: 0)],
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
              child: FractionallySizedBox(
                widthFactor: 0.62,
                alignment: Alignment.centerLeft,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text.rich(
                      TextSpan(
                        children: [
                          const TextSpan(text: 'Mundo dos '),
                          TextSpan(
                            text: 'Jogos!',
                            style: TextStyle(color: _verde, shadows: [Shadow(color: _verde.withValues(alpha: 0.45), blurRadius: 14)]),
                          ),
                        ],
                      ),
                      style: const TextStyle(fontSize: 22.7, height: 1.12, fontWeight: FontWeight.w900, color: Colors.white),
                    ),
                    const SizedBox(height: 6),
                    const Text('Teste suas habilidades e evolua.', style: TextStyle(fontSize: 12.8, height: 1.32, color: Color(0xFFE1ECFF))),
                    const SizedBox(height: 14),
                    GestureDetector(
                      onTap: _comoFunciona,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(999),
                          gradient: const LinearGradient(colors: [Color(0xFF3B79E0), Color(0xFF2258B0)]),
                          border: Border.all(color: _roxo),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.play_arrow_rounded, size: 18, color: Colors.white),
                            SizedBox(width: 4),
                            Text('Ver como funciona', style: TextStyle(fontSize: 12.8, fontWeight: FontWeight.w700, color: Colors.white)),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _titulo(String t) => Padding(
        padding: const EdgeInsets.fromLTRB(2, 18, 2, 8),
        child: Text(t, style: const TextStyle(fontSize: 18.4, fontWeight: FontWeight.w900, color: Colors.white)),
      );

  // ---- cartão de um jogo: arte, frase e o botão "Jogar agora" encaixado embaixo
  Widget _jogo({
    required Color cor,
    required String arte,
    required String frase,
    required List<Color> botao,
    required Color texto,
    required VoidCallback acao,
  }) {
    return Column(
      children: [
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: const Color(0xFF061730),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(22)),
              border: Border(top: BorderSide(color: cor, width: 2), left: BorderSide(color: cor, width: 2), right: BorderSide(color: cor, width: 2)),
            ),
            child: ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
              child: Column(
                children: [
                  AspectRatio(aspectRatio: 2, child: Image.asset(arte, fit: BoxFit.contain)),
                  Expanded(
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.fromLTRB(8, 8, 8, 10),
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF0F2B55), Color(0xFF0B0738)]),
                      ),
                      child: Text(frase, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12.2, height: 1.3, fontWeight: FontWeight.w700, color: Color(0xFFE9F1FF))),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        GestureDetector(
          onTap: acao,
          child: Container(
            height: 46,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(22)),
              gradient: LinearGradient(colors: botao),
              border: Border(bottom: BorderSide(color: cor, width: 2), left: BorderSide(color: cor, width: 2), right: BorderSide(color: cor, width: 2)),
            ),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Row(
                children: [
                  Icon(Icons.play_arrow_rounded, color: texto, size: 22),
                  const SizedBox(width: 4),
                  Text('Jogar agora', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: texto)),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ---- Sua Evolução: vitórias, ranking, sequência e partidas
  Widget _evolucao() {
    final melhor = _d?['melhor'] as Map?;
    final ofs = (_d?['ofensiva'] as num?)?.toInt() ?? 0;
    String n(Object? v) => v is num ? '${v.toInt()}' : (_d == null ? '—' : '0');
    Widget caixa(String ic, String rot, String val, String sub, {bool fogo = false}) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: fogo ? const Color(0x80FF8C3C) : const Color(0x736CA3FF), width: 1.5),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: fogo ? const [Color(0xFF3A1A2A), Color(0xFF0F1A30)] : const [Color(0xFF143360), Color(0xFF0B1F3E)],
              ),
            ),
            child: Column(
              children: [
                Text(ic, style: const TextStyle(fontSize: 21.6, height: 1.2)),
                const SizedBox(height: 2),
                Text(rot, style: const TextStyle(fontSize: 11.2, color: _lila)),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(val, style: const TextStyle(fontSize: 16.8, fontWeight: FontWeight.w900, color: Colors.white)),
                ),
                Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 9.9, color: Color(0xFFB5C8E6))),
              ],
            ),
          ),
        );
    return Row(
      children: [
        caixa('🏆', 'Vitórias', n(_d?['vitorias']), 'nos dois jogos'),
        const SizedBox(width: 8),
        caixa('⭐', 'Ranking', melhor == null ? '—' : '#${melhor['pos']}', melhor == null ? 'jogue para entrar' : '${melhor['jogo']}'),
        const SizedBox(width: 8),
        caixa('🔥', 'Sequência', '$ofs ${ofs == 1 ? 'dia' : 'dias'}', 'de estudo', fogo: true),
        const SizedBox(width: 8),
        caixa('🎮', 'Partidas', n(_d?['partidas']), 'terminadas'),
      ],
    );
  }

  // ---- Desafio da Semana
  Widget _desafio(Map d) {
    final atual = (d['atual'] as num?) ?? 0;
    final alvo = (d['alvo'] as num?) ?? 0;
    final ok = d['ok'] == true;
    final pct = alvo == 0 ? 0.0 : (atual / alvo).clamp(0, 1).toDouble();
    return Container(
      margin: const EdgeInsets.only(top: 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _ouro, width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF182D4F), Color(0xFF0C1E3A)]),
        boxShadow: [BoxShadow(color: _ouro.withValues(alpha: 0.25), blurRadius: 16)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Stack(
          children: [
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: Alignment.centerRight,
                    radius: 1,
                    colors: [_ouro.withValues(alpha: 0.22), _ouro.withValues(alpha: 0)],
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              child: Row(
                children: [
                  const Text('📅', style: TextStyle(fontSize: 32)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Desafio da Semana', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFFFFC93C))),
                        const SizedBox(height: 2),
                        Text('${d['texto'] ?? ''}', style: const TextStyle(fontSize: 12.8, height: 1.3, color: Color(0xFFE9F1FF))),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Expanded(
                              child: Container(
                                height: 8,
                                alignment: Alignment.centerLeft,
                                decoration: BoxDecoration(color: const Color(0x1FFFFFFF), borderRadius: BorderRadius.circular(99)),
                                child: FractionallySizedBox(
                                  widthFactor: pct,
                                  child: Container(
                                    decoration: BoxDecoration(
                                      borderRadius: BorderRadius.circular(99),
                                      gradient: const LinearGradient(colors: [Color(0xFF34E85E), Color(0xFFB6F23E)]),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text('${atual.toInt()}/${alvo.toInt()}', style: const TextStyle(fontSize: 12.8, fontWeight: FontWeight.w900, color: Colors.white)),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: ok ? _verde : _ouro, width: 1.5),
                      color: const Color(0x80281800),
                    ),
                    child: Text(
                      ok ? '✓ Concluído' : '+${d['pontos'] ?? 0} pts',
                      style: TextStyle(fontSize: 12.8, fontWeight: FontWeight.w900, color: ok ? const Color(0xFF6BFF8A) : const Color(0xFFFFE08A)),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---- atalhos: Ranking, Amigos, Eventos, Ajuda
  Widget _atalhos() {
    const itens = [('👑', 'Ranking'), ('🎁', 'Eventos'), ('📖', 'Ajuda')];
    return Row(
      children: [
        for (final (i, (ic, rot)) in itens.indexed) ...[
          if (i > 0) const SizedBox(width: 8),
          Expanded(
            child: GestureDetector(
              onTap: () => switch (rot) {
                'Ranking' => abrirAba(3),
                'Eventos' => Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventosTela(api: widget.api))),
                'Ajuda' => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AjudaTela(api: widget.api))),
                _ => _emBreve(rot),
              },
              child: Container(
                padding: const EdgeInsets.fromLTRB(4, 12, 4, 10),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: const Color(0x736CA3FF), width: 1.5),
                  gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF143360), Color(0xFF0B1F3E)]),
                ),
                child: Column(
                  children: [
                    Text(ic, style: const TextStyle(fontSize: 22.4, height: 1.1)),
                    const SizedBox(height: 5),
                    Text(rot, style: const TextStyle(fontSize: 12.2, fontWeight: FontWeight.w800, color: Color(0xFFE9F1FF))),
                  ],
                ),
              ),
            ),
          ),
        ],
      ],
    );
  }
}
