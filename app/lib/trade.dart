import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'tour.dart';
import 'partida.dart';
import 'sala.dart';
import 'ticker_online.dart' show BuscaTela;
import 'setups.dart';

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
    Route<void> partida(String id) => MaterialPageRoute<void>(builder: (_) => PartidaTela(api: widget.api, salaId: id));
    // a tela de busca abre NA HORA; a entrada na fila acontece dentro dela (antes o toque esperava o servidor e parecia travado)
    await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => BuscaTela(
            api: widget.api,
            rota: '/trade/fila',
            titulo: 'Trade Battle · Online', confronto: (id) => '/trade/salas/$id/confronto',
            abrir: partida,
            entrar: () => widget.api.post('/trade/fila', {'corrida': _corrida}))));
    if (mounted) _carregar();
  }

  @override
  Widget build(BuildContext context) {
    final corridas = ((_d?['corridas'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final atual = corridas.where((c) => c['id'] == _corrida).firstOrNull;
    final semGraficos = atual != null && ((atual['reais'] as num?) ?? 0) < 1;
    final ativa = _d?['ativa'] != null;
    return Scaffold(
      backgroundColor: _fundo,
      body: RefreshIndicator(
        onRefresh: _carregar,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            Entrada(ordem: 0, child: _capa(ativa)),
            if (semGraficos) Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 720), child: Padding(padding: const EdgeInsets.symmetric(horizontal: 14), child: _aviso()))),
            const SizedBox(height: 10),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  child: Column(children: [
                    Entrada(ordem: 2, child: _painelSetups()),
                    const SizedBox(height: 10),
                    Entrada(ordem: 4, child: _comoFunciona()),
                    const SizedBox(height: 24),
                  ]),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static const _fundo = Color(0xFF050E2C);

  // ---- capa: a arte do Trade Battle (logo, touro e arena) com o botão BATALHAR hexagonal dourado sobre a base da arena
  Widget _capa(bool ativa) {
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      final tela = MediaQuery.of(context).size.height;
      final h = (w * 788 / 1024).clamp(0.0, tela * 0.62);          // em telas largas a arte é cortada nas laterais em vez de ficar pequena
      final bw = (w * 0.86).clamp(0.0, 560.0);
      final bh = (bw * 0.24).clamp(96.0, 132.0);
      return SizedBox(
        height: h + bh * 0.4,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned(
              left: 0,
              right: 0,
              top: 0,
              height: h,
              child: ShaderMask(
                shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF000000), Color(0xFF000000), Color(0x00000000)], stops: [0, 0.78, 1]).createShader(r),
                blendMode: BlendMode.dstIn,
                child: Image.asset('assets/jogos/tb_capa.webp', width: w, height: h, fit: BoxFit.cover, alignment: Alignment.topCenter),
              ),
            ),
            Positioned(left: (w - bw) / 2, width: bw, bottom: 0, height: bh, child: _botaoBatalhar(ativa)),
          ],
        ),
      );
    });
  }

  /// BATALHAR: procura um adversário online (1 contra 1). Se já há uma partida em andamento, volta para ela.
  Widget _botaoBatalhar(bool ativa) => Pressionavel(
        aoTocar: ativa ? () => _abrirSala('${_d!['ativa']}') : _procurar,
        child: CustomPaint(
          painter: _HexDourado(),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.flash_on_rounded, size: 24, color: Color(0xFFFFE08A)),
                Text(ativa ? 'VOLTAR PARA A PARTIDA' : 'BATALHAR',
                    style: TextStyle(fontSize: ativa ? 20 : 34, height: 1.0, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: const Color(0xFFFFD04A), letterSpacing: .6, shadows: const [Shadow(color: Color(0xFF7A4A00), blurRadius: 6, offset: Offset(0, 2))])),
                const SizedBox(height: 2),
                Text(ativa ? 'SUA BATALHA ESTÁ EM ANDAMENTO' : 'PRONTO PARA O DESAFIO?', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: Colors.white, letterSpacing: .8)),
              ],
            ),
          ),
        ),
      );

  // ---- Meus Setups: os espaços de setup da partida. Tocar em um espaço (ou no +) abre a escolha das cartas de setup.
  Widget _painelSetups() {
    final st = _setups;
    final itens = ((st?['itens'] as List?) ?? const []).cast<Map>().where((x) => x['equipado'] == true).map((x) => x.cast<String, dynamic>()).toList();
    final limite = ((st?['limite'] as num?) ?? 2).toInt();
    Widget espaco(int k) {
      final s = k < itens.length ? itens[k] : null;
      return Expanded(
        child: SizedBox(height: 78, child: Stack(clipBehavior: Clip.none, children: [
          Positioned.fill(child: Pressionavel(
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
                      ]),
                    ),
                  ]),
          ),
        )),
          if (s != null)
            Positioned(
              right: k < limite - 1 ? 14 : 6,
              top: -8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                decoration: BoxDecoration(color: const Color(0xFF1FA85A), borderRadius: BorderRadius.circular(8), border: Border.all(color: const Color(0xFF7DFFB8))),
                child: const Text('ATIVO', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: Colors.white)),
              ),
            ),
        ])),
      );
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0x886CA3FF)),
        color: const Color(0xE60A1A40),
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
                Text('Seus setups ativos e evolução.', style: TextStyle(fontSize: 11.5, color: Color(0xFFB9D0F5))),
              ]),
            ),
            Text(st == null ? '' : '${itens.length}/$limite', style: const TextStyle(color: Color(0xFFB9D0F5), fontWeight: FontWeight.w900)),
          ]),
          const SizedBox(height: 14),
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


/// Moldura hexagonal dourada do botão BATALHAR (como na arte de referência): corpo escuro com brilho, borda dourada dupla e luz azul em volta.
class _HexDourado extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height, o = h * 0.42;
    Path hex(double d) => Path()
      ..moveTo(o + d, d)
      ..lineTo(w - o - d, d)
      ..lineTo(w - d, h / 2)
      ..lineTo(w - o - d, h - d)
      ..lineTo(o + d, h - d)
      ..lineTo(d, h / 2)
      ..close();
    final ext = hex(2);
    canvas.drawPath(ext, Paint()..color = const Color(0x883DA0FF)..maskFilter = const MaskFilter.blur(BlurStyle.outer, 14));
    canvas.drawPath(ext, Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE08A), Color(0xFFB8741A), Color(0xFFFFC94A)]).createShader(Offset.zero & size));
    final int = hex(7);
    canvas.drawPath(int, Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF7A4B08), Color(0xFF2F1B02), Color(0xFF5B3806)]).createShader(Offset.zero & size));
    canvas.drawPath(hex(11), Paint()..style = PaintingStyle.stroke..strokeWidth = 1.6..color = const Color(0xFFFFD76A));
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}
