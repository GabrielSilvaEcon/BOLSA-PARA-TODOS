import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'tour.dart';
import 'navegacao.dart';
import 'partida.dart';
import 'sala.dart';
import 'ticker_online.dart' show BuscaTela;
import 'setups.dart';
import 'social.dart' show SocialTela;

/// Tela inicial do Trade Battle, montada com a arte do Gabriel: título e touro com as três durações (Rápida, Intermediária, Longa),
/// Jogar Solo / Encontrar adversário (busca online; amigos se desafiam em Meus Amigos), ranking do jogo, "Sobre o Trade Battle" e "Como funciona".
/// As partes da arte são botões de verdade e ganham vida com animações (entrada em sequência, moldura pulsando, reflexo, toque com mola).
/// Dados do servidor (`GET /trade/central`).
class TradeTela extends StatefulWidget {
  const TradeTela({super.key, required this.api, this.jogarSolo});
  final Api api;

  /// Começa a partida solo na duração escolhida (a tela da partida entra na próxima etapa).
  final void Function(String corrida)? jogarSolo;

  @override
  State<TradeTela> createState() => _TradeTelaState();
}


class _TradeTelaState extends State<TradeTela> {
  Map<String, dynamic>? _d;
  Map<String, dynamic>? _setups;
  /// Uma duração só: gráfico de 15 minutos (a mais curta). Todo mundo joga a mesma partida, então a busca por adversário junta mais gente.
  static const _corrida = 'rapida';
  bool _comoAberto = false;

  @override
  void initState() {
    super.initState();
    Tour.evento('tela_trade');
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/trade/central');
      try {
        _setups = await widget.api.get('/setups'); // falha aqui não derruba a central
      } catch (_) {}
      if (mounted) setState(() => _d = r);
    } catch (_) {
      if (mounted) setState(() => _d = const {});
    }
  }

  /// Abre a sala (espera ou partida em andamento) e, ao voltar, atualiza a tela (a sala ativa pode ter acabado).
  Future<void> _abrirSala(String id) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => SalaTela(api: widget.api, salaId: id)));
    _carregar();
  }

  /// "Encontrar adversário": entra na busca da duração escolhida. Quem estiver procurando a mesma duração ao mesmo tempo se encontra e a partida começa
  /// na hora. Não há criar sala nem código: amigos se desafiam em Meus Amigos.
  Future<void> _procurar() async {
    try {
      final r = await widget.api.post('/trade/fila', {'corrida': _corrida});
      if (!mounted) return;
      Route<void> partida(String id) => MaterialPageRoute<void>(builder: (_) => PartidaTela(api: widget.api, salaId: id));
      if (r['estado'] == 'partida') {
        await Navigator.of(context).push(partida('${r['id']}'));
      } else {
        await Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => BuscaTela(
                api: widget.api,
                rota: '/trade/fila',
                titulo: 'Trade Battle · Online',
                abrir: partida,
                avisoBot: true,
                rotuloAlternativa: 'Treinar solo enquanto isso',
                alternativa: () => MaterialPageRoute<void>(builder: (_) => PartidaTela(api: widget.api, corrida: _corrida)))));
      }
      _carregar();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    final corridas = ((_d?['corridas'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final atual = corridas.where((c) => c['id'] == _corrida).firstOrNull;
    final semGraficos = atual != null && ((atual['reais'] as num?) ?? 0) < 1;
    final ativa = _d?['ativa'] != null;
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(
        fit: StackFit.expand,
        children: [
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFF0A0A5A), Color(0xFF082F70), Color(0xFF05204E), Color(0xFF001738)],
                stops: [0, 0.35, 0.7, 1],
              ),
            ),
          ),
          RefreshIndicator(
            onRefresh: _carregar,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(8, 6, 8, 0),
                  children: [
                    Entrada(ordem: 0, child: _hero()),
                    if (semGraficos) _aviso(),
                    const SizedBox(height: 4),
                    Entrada(ordem: 1, child: _botaoBatalhar(ativa)),
                    const SizedBox(height: 10),
                    Entrada(ordem: 2, child: _secundarios(ativa)),
                    const SizedBox(height: 14),
                    Entrada(ordem: 3, child: _painelSetups()),
                    const SizedBox(height: 12),
                    Entrada(ordem: 4, child: _secaoRanking()),
                    const SizedBox(height: 6),
                    Entrada(ordem: 5, child: _comoFunciona()),
                    const SizedBox(height: 6),
                    Image.asset('assets/jogos/tb_chao.webp'),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- topo: o título, o lema e o touro da arte (flutuando)
  Widget _hero() {
    return SizedBox(
      height: 190,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            right: -10,
            top: 0,
            bottom: 0,
            child: ShaderMask(
              shaderCallback: (r) => const LinearGradient(begin: Alignment.centerLeft, end: Alignment.centerRight, colors: [Color(0x00000000), Color(0xFF000000)], stops: [0, 0.3]).createShader(r),
              blendMode: BlendMode.dstIn,
              child: ShaderMask(
                shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF000000), Color(0x00000000)], stops: [0.78, 1]).createShader(r),
                blendMode: BlendMode.dstIn,
                child: Flutua(altura: 3, child: Image.asset('assets/jogos/tb_touro.webp', height: 190, fit: BoxFit.fitHeight)),
              ),
            ),
          ),
          Positioned(
            left: 6,
            top: 26,
            right: 150,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('TRADE\nBATTLE', style: TextStyle(fontSize: 34, height: .95, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Color(0xFF4FC3FF), letterSpacing: .5)),
                const SizedBox(height: 8),
                Text('Estratégia, análise e grandes desafios!', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, fontStyle: FontStyle.italic, color: Colors.white.withValues(alpha: .85))),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// BATALHAR: procura um adversário online (1 contra 1). Se já há uma partida em andamento, volta para ela.
  Widget _botaoBatalhar(bool ativa) => Pressionavel(
        aoTocar: ativa ? () => _abrirSala('${_d!['ativa']}') : _procurar,
        child: Container(
          height: 92,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: const Color(0xFFFFD76A), width: 2.5),
            gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF8A5A0A), Color(0xFF3A2504), Color(0xFF6B4508)]),
            boxShadow: const [BoxShadow(color: Color(0x99FFB300), blurRadius: 22), BoxShadow(color: Color(0x663DA0FF), blurRadius: 30, spreadRadius: 1)],
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.bolt_rounded, size: 26, color: Color(0xFFFFD76A)),
              Text(ativa ? 'VOLTAR PARA A PARTIDA' : 'BATALHAR',
                  style: const TextStyle(fontSize: 30, height: 1.05, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Color(0xFFFFD76A), letterSpacing: .6)),
              Text(ativa ? 'Sua batalha está em andamento' : 'PRONTO PARA O DESAFIO?', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white, letterSpacing: .8)),
            ],
          ),
        ),
      );

  /// Treinar sozinho e chamar um amigo (o desafio sai de Meus Amigos: cria a batalha e começa quando o amigo aceita).
  Widget _secundarios(bool ativa) {
    Widget botao(IconData ic, String t, VoidCallback f) => Expanded(
          child: Pressionavel(
            aoTocar: f,
            child: Container(
              height: 48,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFF4F88E6), width: 1.6),
                color: const Color(0xCC0E2A58),
              ),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(ic, size: 20, color: const Color(0xFFDEEBFF)),
                const SizedBox(width: 8),
                Flexible(child: Text(t, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white))),
              ]),
            ),
          ),
        );
    return Row(children: [
      Expanded(
        child: TourAlvo(
          id: 'trade_solo',
          child: Row(children: [
            botao(
                Icons.person_rounded,
                'Treinar solo',
                () => widget.jogarSolo != null
                    ? widget.jogarSolo!(_corrida)
                    : Navigator.of(context).push(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, corrida: _corrida)))),
          ]),
        ),
      ),
      const SizedBox(width: 8),
      botao(Icons.group_add_rounded, 'Desafiar amigo', () async {
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => SocialTela(api: widget.api)));
        _carregar();
      }),
    ]);
  }

  // ---- Meus Setups: os espaços de setup da partida. Tocar em um espaço (ou no +) abre a escolha das cartas de setup.
  Widget _painelSetups() {
    final st = _setups;
    final itens = ((st?['itens'] as List?) ?? const []).cast<Map>().where((x) => x['equipado'] == true).map((x) => x.cast<String, dynamic>()).toList();
    final limite = ((st?['limite'] as num?) ?? 2).toInt();
    Widget espaco(int k) {
      final s = k < itens.length ? itens[k] : null;
      return Expanded(
        child: Pressionavel(
          aoTocar: _escolher,
          child: Container(
            height: 78,
            margin: EdgeInsets.only(right: k < limite - 1 ? 8 : 0),
            padding: const EdgeInsets.symmetric(horizontal: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: s != null ? const Color(0xFF3DFFB0) : const Color(0xFF2F5FA8), width: s != null ? 2 : 1.4),
              color: s != null ? const Color(0x331FA06C) : const Color(0x990A2250),
            ),
            child: s == null
                ? const Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.add_circle_outline_rounded, size: 26, color: Color(0xFF8FB4F0)),
                    SizedBox(height: 4),
                    Text('Escolher setup', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFFB9D0F5))),
                  ])
                : Row(children: [
                    Icon(iconeDoSetup('${s['id']}'), size: 28, color: const Color(0xFF3DFFB0)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${s['nome']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Colors.white)),
                        Container(
                          margin: const EdgeInsets.only(top: 3),
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                          decoration: BoxDecoration(color: const Color(0xFF3DFFB0), borderRadius: BorderRadius.circular(6)),
                          child: const Text('ATIVO', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w900, color: Color(0xFF04281A))),
                        ),
                      ]),
                    ),
                  ]),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0x886CA3FF)),
        color: const Color(0xCC0B1F46),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            const Icon(Icons.gps_fixed, size: 22, color: Color(0xFFFFB300)),
            const SizedBox(width: 10),
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('MEUS SETUPS', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white, letterSpacing: .4)),
                Text('Os setups que vão atuar na sua batalha.', style: TextStyle(fontSize: 11.5, color: Color(0xFFB9D0F5))),
              ]),
            ),
            Text(st == null ? '' : '${itens.length}/$limite', style: const TextStyle(color: Color(0xFFB9D0F5), fontWeight: FontWeight.w900)),
          ]),
          const SizedBox(height: 10),
          Row(children: [for (var k = 0; k < limite; k++) espaco(k)]),
        ],
      ),
    );
  }

  Future<void> _escolher() async {
    await escolherSetups(context, widget.api, inicial: _setups, aoMudar: (novo) => setState(() => _setups = novo));
    _carregar();
  }

  // ---- aviso quando a duração escolhida ainda não tem gráfico real
  // ---- aviso quando ainda não há gráfico real de 15 minutos
  Widget _aviso() {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.fromLTRB(14, 10, 6, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFF2B84B), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0x29F2B84B), Color(0xF00C1D38)]),
      ),
      child: Row(
        children: [
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ⓘ Gráficos em preparação', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFFFFC93C))),
                SizedBox(height: 4),
                Text('Os gráficos reais de 15 minutos ainda estão sendo preparados. Volte mais tarde.',
                    style: TextStyle(fontSize: 12.5, height: 1.35, color: Color(0xFFE9F1FF))),
              ],
            ),
          ),
          const SizedBox(width: 8),
          ClipRRect(borderRadius: BorderRadius.circular(14), child: Image.asset('assets/nav/mascote.webp', width: 70)),
        ],
      ),
    );
  }

  // ---- Ranking do Trade Battle: título, "Ver ranking completo", a faixa da arte e a sua posição
  Widget _secaoRanking() {
    final rk = _d?['ranking'] as Map?;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 16, 0, 8),
          child: Row(
            children: [
              const Icon(Icons.bar_chart_rounded, size: 30, color: Color(0xFF9BBFFF)),
              const SizedBox(width: 6),
              const Expanded(
                child: Text('Ranking do Trade Battle', maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: Colors.white)),
              ),
              Pressionavel(
                aoTocar: () => abrirAba(3),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: const Color(0xFF6399F0), width: 1.5),
                    color: const Color(0x660F3878),
                  ),
                  child: const Text('Ver ranking completo ›', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: Colors.white)),
                ),
              ),
            ],
          ),
        ),
        Pressionavel(
          aoTocar: () => abrirAba(3),
          child: Reflexo(raio: 14, atraso: const Duration(milliseconds: 900), intervalo: const Duration(milliseconds: 4600), child: Image.asset('assets/jogos/tb_ranking.webp')),
        ),
        if (rk != null)
          Container(
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFF4F88E6), width: 1.5),
              gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1A4586), Color(0xFF0F2B55)]),
            ),
            child: Row(
              children: [
                Text('#${rk['pos']}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFFFFC93C))),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('${rk['nome'] ?? 'Você'} · de ${rk['total']}', maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13.8, fontWeight: FontWeight.w700, color: Color(0xFFE9F1FF))),
                ),
                Text(_pts(rk['valor']), style: const TextStyle(fontWeight: FontWeight.w900, color: Color(0xFF6BFF8A))),
              ],
            ),
          ),
      ],
    );
  }

  String _pts(Object? v) {
    if (v is! num) return '';
    final s = v.abs().toStringAsFixed(1).replaceAll('.', ',');
    return '${v > 0 ? '+' : v < 0 ? '−' : ''}$s pts';
  }

  // ---- Como funciona (o mesmo texto do app antigo)
  Widget _comoFunciona() {
    final xp = _d?['xp_dia'] ?? 5;
    return Container(
      margin: const EdgeInsets.only(top: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x556CA3FF)),
        color: const Color(0xCC0E1F3A),
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
                '(eles aparecem só no fim, para ninguém pesquisar o que aconteceu depois). O gráfico é de candles de 15 minutos. Cada candle se forma na sua frente com os candles menores reais daquele dia '
                '(5 minutos, ou 1 hora no gráfico diário): dá para entrar no meio do candle, no preço que estava valendo. Você tem 120 s para '
                'analisar e montar a sua estratégia na boleta (comprar ou vender, tipo de ordem, stop, alvo e quantidade, com o risco/retorno '
                'calculado): ao confirmar, a ordem entra sozinha no 1º preço. Sozinho (treino), a partida começa assim que você confirma; contra um adversário (BATALHAR procura quem estiver online, ou você desafia um amigo '
                'em Meus Amigos), quando os dois confirmarem. Os setups que você deixar ativos em Meus Setups observam o gráfico por você. Depois o gráfico anda numa partida corrida, sem rodadas, e você opera ao vivo como num home broker: compra e '
                'vende a quantidade de ações que quiser, aumenta ou reduz a posição, usa ordem a mercado, limite ou stop de entrada, e coloca stop '
                'e alvo.\n\nCapital: a partida usa 5% do saldo disponível (caixa livre) da sua Carteira. O valor aplicado ao mesmo tempo nunca passa '
                'disso: chegou ao teto, encerre ou reduza a posição para entrar de novo. A perda máxima é esse capital.\n\nExecução honesta: a ordem '
                'a mercado executa no próximo preço real (a abertura do candle menor seguinte); stop e alvo são conferidos na ordem em que os preços '
                'aconteceram e executam no preço ou, se o preço saltar além dele, no preço do salto; cada execução paga a taxa da B3 (cerca de 0,03%). '
                'No fim, o resultado (lucro ou prejuízo) volta para a sua Carteira.\n\nVocê ganha XP pela colocação e pela pontuação positiva (até $xp '
                'partidas por dia). Jogo educativo: nenhuma ordem real, nada de recomendação de investimento.',
                style: const TextStyle(fontSize: 13, height: 1.45, color: Color(0xFFE9F1FF)),
              ),
            ),
        ],
      ),
    );
  }
}
