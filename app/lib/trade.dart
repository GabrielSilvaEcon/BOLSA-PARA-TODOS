import 'package:flutter/material.dart';

import 'api.dart';
import 'partida.dart';

/// Tela inicial do Trade Battle, igual à do app antigo (trader_battle_app._central + jogos_app.navegacao/faixa_jogo):
/// abas da Central, arte do jogo, escolha da duração, Jogar Solo / Jogar com Amigos, Entrar em uma Sala,
/// ranking do jogo, "Sobre o Trade Battle" e "Como funciona". Dados do servidor (`GET /trade/central`).
class TradeTela extends StatefulWidget {
  const TradeTela({super.key, required this.api, this.jogarSolo});
  final Api api;

  /// Começa a partida solo na duração escolhida (a tela da partida entra na próxima etapa).
  final void Function(String corrida)? jogarSolo;

  @override
  State<TradeTela> createState() => _TradeTelaState();
}

const _verde = Color(0xFF34E85E);
const _roxo = Color(0xFF5B4BD6);
const _lila = Color(0xFFD9D4F7);
const _icones = {'rapida': Icons.bolt, 'intermediaria': Icons.timer_outlined, 'longa': Icons.emoji_events_outlined};

class _TradeTelaState extends State<TradeTela> {
  Map<String, dynamic>? _d;
  String _corrida = 'intermediaria';
  bool _comoAberto = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/trade/central');
      if (mounted) setState(() => _d = r);
    } catch (_) {
      if (mounted) setState(() => _d = const {});
    }
  }

  void _emBreve(String nome) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$nome: chega na próxima etapa do app novo')));

  @override
  Widget build(BuildContext context) {
    final corridas = ((_d?['corridas'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final atual = corridas.where((c) => c['id'] == _corrida).firstOrNull;
    final semGraficos = atual != null && ((atual['reais'] as num?) ?? 0) < 1;
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
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 20),
                  children: [
                    _abasCentral(),
                    const SizedBox(height: 10),
                    Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: const Color(0x998B6CFF), width: 2),
                        boxShadow: const [BoxShadow(color: Color(0x808B6CFF), blurRadius: 18)],
                      ),
                      child: ClipRRect(borderRadius: BorderRadius.circular(16), child: Image.asset('assets/jogos/trade_hero.webp')),
                    ),
                    _secao('🕒', 'Escolha a duração da partida'),
                    const SizedBox(height: 8),
                    if (corridas.isEmpty)
                      const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator()))
                    else
                      Row(
                        children: [
                          for (final (i, c) in corridas.indexed) ...[
                            if (i > 0) const SizedBox(width: 8),
                            Expanded(child: _duracao(c)),
                          ],
                        ],
                      ),
                    if (semGraficos) _aviso(),
                    const SizedBox(height: 10),
                    IntrinsicHeight(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(
                            child: _modo(
                              titulo: 'Jogar Solo',
                              sub: 'Desafie-se e melhore seu desempenho!',
                              icone: Icons.trending_up,
                              corIcone: _verde,
                              borda: _verde,
                              fundo: const [Color(0xBF146E50), Color(0xF50A1A28)],
                              brilho: const Color(0x7334E85E),
                              seta: _verde,
                              acao: () => widget.jogarSolo != null
                                  ? widget.jogarSolo!(_corrida)
                                  : Navigator.of(context).push(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, corrida: _corrida))),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _modo(
                              titulo: 'Jogar com Amigos',
                              sub: 'Convide seus amigos para uma batalha!',
                              icone: Icons.groups,
                              corIcone: const Color(0xFFA99BFF),
                              borda: const Color(0xFF8B6CFF),
                              fundo: const [Color(0xB36E46E6), Color(0xF5140C40)],
                              brilho: const Color(0x808B6CFF),
                              seta: const Color(0xFFB9A8FF),
                              selo: '👥 2-4',
                              acao: () => _emBreve('Salas com amigos'),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    _linhaSala(_d?['ativa'] != null),
                    _secaoRanking(),
                    _sobre(),
                    _comoFunciona(),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- abas da Central de Jogos (Trade aberta)
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
          final on = rot == 'Trade';
          return GestureDetector(
            onTap: () {
              if (rot == 'Central') {
                Navigator.of(context).maybePop();
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

  Widget _secao(String ic, String t) => Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 2),
        child: Row(
          children: [
            Text(ic, style: const TextStyle(fontSize: 18.4)),
            const SizedBox(width: 8),
            Expanded(child: Text(t, style: const TextStyle(fontSize: 16.3, fontWeight: FontWeight.w800, color: _lila))),
          ],
        ),
      );

  // ---- botão de duração (Rápida / Intermediária / Longa)
  Widget _duracao(Map<String, dynamic> c) {
    final id = c['id'] as String;
    final on = id == _corrida;
    return GestureDetector(
      onTap: () => setState(() => _corrida = id),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            constraints: const BoxConstraints(minHeight: 62),
            width: double.infinity,
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: on ? _verde : _roxo, width: 2),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: on ? const [Color(0x3834E85E), Color(0xFF150F55)] : const [Color(0xFF241A86), Color(0xFF150F55)],
                stops: on ? const [0, 0.8] : null,
              ),
              boxShadow: [BoxShadow(color: on ? const Color(0x8034E85E) : const Color(0x665B4BD6), blurRadius: on ? 16 : 10)],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(_icones[id] ?? Icons.timer, color: const Color(0xFFFFC93C), size: 25.6),
                const SizedBox(height: 2),
                Text('${c['rotulo']}', style: const TextStyle(fontSize: 15.2, height: 1.1, fontWeight: FontWeight.w900, color: Colors.white)),
                const SizedBox(height: 2),
                Text(
                  'Gráfico de ${c['grafico']}\n~${c['minutos']} min',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 10.9, height: 1.25, fontWeight: FontWeight.w600, color: on ? const Color(0xFF8DF5C1) : const Color(0xFFC9C2FF)),
                ),
              ],
            ),
          ),
          if (id == 'intermediaria')
            Positioned(
              top: -10,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
                  decoration: BoxDecoration(
                    color: _verde,
                    borderRadius: BorderRadius.circular(999),
                    boxShadow: const [BoxShadow(color: Color(0x9934E85E), blurRadius: 8)],
                  ),
                  child: const Text('Recomendado', style: TextStyle(fontSize: 9.9, fontWeight: FontWeight.w900, color: Color(0xFF06240F))),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // ---- aviso quando a duração escolhida ainda não tem gráfico real
  Widget _aviso() {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.fromLTRB(14, 10, 6, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFF2B84B), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0x29F2B84B), Color(0xF0120C38)]),
      ),
      child: Row(
        children: [
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ⓘ Gráficos em preparação', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFFFFC93C))),
                SizedBox(height: 4),
                Text('Os gráficos reais desta duração ainda estão sendo preparados. Tente outra duração ou volte mais tarde.',
                    style: TextStyle(fontSize: 12.5, height: 1.35, color: Color(0xFFEDE9FF))),
              ],
            ),
          ),
          const SizedBox(width: 8),
          ClipRRect(borderRadius: BorderRadius.circular(14), child: Image.asset('assets/nav/mascote.webp', width: 70)),
        ],
      ),
    );
  }

  // ---- Jogar Solo / Jogar com Amigos
  Widget _modo({
    required String titulo,
    required String sub,
    required IconData icone,
    required Color corIcone,
    required Color borda,
    required List<Color> fundo,
    required Color brilho,
    required Color seta,
    required VoidCallback acao,
    String? selo,
  }) {
    return GestureDetector(
      onTap: acao,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            constraints: const BoxConstraints(minHeight: 150),
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(10, 12, 10, 34),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: borda, width: 2),
              gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: fundo),
              boxShadow: [BoxShadow(color: brilho, blurRadius: 18)],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icone, size: 44.8, color: corIcone),
                const SizedBox(height: 4),
                Text(titulo, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16.8, fontWeight: FontWeight.w900, color: Colors.white)),
                const SizedBox(height: 4),
                Text(sub, textAlign: TextAlign.center, style: const TextStyle(fontSize: 11.8, height: 1.3, fontWeight: FontWeight.w500, color: _lila)),
              ],
            ),
          ),
          Positioned(
            right: 10,
            bottom: 9,
            child: Container(
              width: 26,
              height: 26,
              alignment: Alignment.center,
              decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: seta, width: 2)),
              child: const Text('→', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
            ),
          ),
          if (selo != null)
            Positioned(
              top: -1,
              right: -1,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E7A3C),
                  borderRadius: const BorderRadius.only(topRight: Radius.circular(20), bottomLeft: Radius.circular(12)),
                  border: Border.all(color: _verde, width: 1.5),
                ),
                child: Text(selo, style: const TextStyle(fontSize: 11.2, fontWeight: FontWeight.w900, color: Colors.white)),
              ),
            ),
        ],
      ),
    );
  }

  // ---- Entrar em uma Sala / Voltar para a sala
  Widget _linhaSala(bool ativa) {
    return GestureDetector(
      onTap: () => _emBreve('Salas com amigos'),
      child: Container(
        constraints: const BoxConstraints(minHeight: 58),
        padding: const EdgeInsets.fromLTRB(14, 6, 16, 6),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: _roxo, width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2A1F8E), Color(0xFF150F55)]),
          boxShadow: const [BoxShadow(color: Color(0x735B4BD6), blurRadius: 12)],
        ),
        child: Row(
          children: [
            const Icon(Icons.login, size: 30, color: Color(0xFFE4DEFF)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(ativa ? 'Voltar para sua sala/partida' : 'Entrar em uma Sala',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                  if (!ativa)
                    const Text('Digite o código de um amigo', style: TextStyle(fontSize: 12.2, fontWeight: FontWeight.w500, color: Color(0xFFC9C2FF))),
                ],
              ),
            ),
            const Text('›', style: TextStyle(fontSize: 28.8, color: Color(0xFFE4DEFF))),
          ],
        ),
      ),
    );
  }

  // ---- faixa do ranking do Trade Battle
  Widget _secaoRanking() {
    final rk = _d?['ranking'] as Map?;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(0, 14, 0, 6),
          child: Text('📊 Ranking do Trade Battle', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        ),
        if (rk == null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0x8C8B6CFF), width: 1.5),
            ),
            child: const Text('Termine uma partida para entrar no ranking do Trade Battle.',
                textAlign: TextAlign.center, style: TextStyle(fontSize: 13.8, color: _lila)),
          )
        else
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: _roxo, width: 2),
              gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF241A86), Color(0xFF150F55)]),
            ),
            child: Row(
              children: [
                Text('#${rk['pos']}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('${rk['nome'] ?? 'Você'} · de ${rk['total']}', maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13.8, fontWeight: FontWeight.w700, color: Color(0xFFEDE9FF))),
                ),
                Text(_pts(rk['valor']), style: const TextStyle(fontWeight: FontWeight.w900, color: Color(0xFF6BFF8A))),
              ],
            ),
          ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: () => _emBreve('Ranking completo'),
          icon: const Icon(Icons.emoji_events),
          label: const Text('Ver ranking completo'),
        ),
      ],
    );
  }

  String _pts(Object? v) {
    if (v is! num) return '';
    final s = v.abs().toStringAsFixed(1).replaceAll('.', ',');
    return '${v > 0 ? '+' : v < 0 ? '−' : ''}$s pts';
  }

  // ---- Sobre o Trade Battle
  Widget _sobre() {
    const itens = [('👥', '2-4', 'jogadores'), ('📊', '15m · 1h · 1D', 'gráficos reais'), ('💰', '5%', 'do saldo disponível'), ('🏆', 'XP', 'por colocação')];
    return Container(
      margin: const EdgeInsets.only(top: 10, bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _roxo, width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1B1470), Color(0xFF0E0840)]),
        boxShadow: const [BoxShadow(color: Color(0x665B4BD6), blurRadius: 12)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(left: 4, bottom: 6),
            child: Text('⭐ Sobre o Trade Battle', style: TextStyle(fontSize: 14.7, fontWeight: FontWeight.w900, color: Colors.white)),
          ),
          IntrinsicHeight(
            child: Row(
              children: [
                for (final (i, (ic, b, s)) in itens.indexed) ...[
                  if (i > 0) const VerticalDivider(width: 1, thickness: 1, color: Color(0x598B6CFF)),
                  Expanded(
                    child: Column(
                      children: [
                        Text(ic, style: const TextStyle(fontSize: 20)),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Text(b, style: const TextStyle(fontSize: 15.2, fontWeight: FontWeight.w900, color: Colors.white)),
                        ),
                        Text(s, textAlign: TextAlign.center, style: const TextStyle(fontSize: 10.6, height: 1.2, color: Color(0xFFBDB5E6))),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---- Como funciona (o mesmo texto do app antigo)
  Widget _comoFunciona() {
    final xp = _d?['xp_dia'] ?? 5;
    return Container(
      margin: const EdgeInsets.only(top: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x558B6CFF)),
        color: const Color(0xCC140E3A),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          InkWell(
            onTap: () => setState(() => _comoAberto = !_comoAberto),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.help_outline, size: 20, color: Colors.white),
                  const SizedBox(width: 8),
                  const Expanded(child: Text('Como funciona', style: TextStyle(fontWeight: FontWeight.w700, color: Colors.white))),
                  Icon(_comoAberto ? Icons.expand_less : Icons.expand_more, color: Colors.white),
                ],
              ),
            ),
          ),
          if (_comoAberto)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Text(
                'Você recebe o gráfico de uma ação real da B3, parado num ponto do passado, sem o nome do ativo nem a data '
                '(eles aparecem só no fim, para ninguém pesquisar o que aconteceu depois). Escolha a duração: Rápida usa candles de 15 minutos, '
                'Intermediária de 1 hora e Longa de 1 dia. Cada candle se forma na sua frente com os candles menores reais daquele dia '
                '(5 minutos, ou 1 hora no gráfico diário): dá para entrar no meio do candle, no preço que estava valendo. Você tem 120 s para '
                'analisar e montar a sua estratégia na boleta (comprar ou vender, tipo de ordem, stop, alvo e quantidade, com o risco/retorno '
                'calculado): ao confirmar, a ordem entra sozinha no 1º preço. Sozinho, a partida começa assim que você confirma; em sala, quando '
                'todos confirmarem. Depois o gráfico anda numa partida corrida, sem rodadas, e você opera ao vivo como num home broker: compra e '
                'vende a quantidade de ações que quiser, aumenta ou reduz a posição, usa ordem a mercado, limite ou stop de entrada, e coloca stop '
                'e alvo.\n\nCapital: a partida usa 5% do saldo disponível (caixa livre) da sua Carteira. O valor aplicado ao mesmo tempo nunca passa '
                'disso: chegou ao teto, encerre ou reduza a posição para entrar de novo. A perda máxima é esse capital.\n\nExecução honesta: a ordem '
                'a mercado executa no próximo preço real (a abertura do candle menor seguinte); stop e alvo são conferidos na ordem em que os preços '
                'aconteceram e executam no preço ou, se o preço saltar além dele, no preço do salto; cada execução paga a taxa da B3 (cerca de 0,03%). '
                'No fim, o resultado (lucro ou prejuízo) volta para a sua Carteira.\n\nVocê ganha XP pela colocação e pela pontuação positiva (até $xp '
                'partidas por dia). Jogo educativo: nenhuma ordem real, nada de recomendação de investimento.',
                style: const TextStyle(fontSize: 13, height: 1.45, color: Color(0xFFEDE9FF)),
              ),
            ),
        ],
      ),
    );
  }
}
