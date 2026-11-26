import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'tour.dart';
import 'navegacao.dart';
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
  String _corrida = 'intermediaria';
  bool _comoAberto = false;

  @override
  void initState() {
    super.initState();
    Tour.evento('tela_trade');
    if (Tour.passo.value != null) _corrida = 'rapida'; // tour guiado: a partida de treino é a mais curta
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
            builder: (_) => BuscaTela(api: widget.api, rota: '/trade/fila', titulo: 'Trade Battle · Online', abrir: partida)));
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
                    Entrada(ordem: 0, child: _cabecalho()),
                    Entrada(ordem: 0, child: _duracoes(corridas)),
                    if (semGraficos) _aviso(),
                    const SizedBox(height: 8),
                    Entrada(
                      ordem: 1,
                      child: Row(
                        children: [
                          Expanded(
                            child: TourAlvo(id: 'trade_solo', child: _cartaoModo(
                              'tb_solo',
                              Duration.zero,
                              () => widget.jogarSolo != null
                                  ? widget.jogarSolo!(_corrida)
                                  : Navigator.of(context).push(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, corrida: _corrida))),
                            )),
                          ),
                          const SizedBox(width: 6),
                          Expanded(child: _cartaoAdversario(ativa)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    Entrada(ordem: 2, child: _linhaSala(ativa)),
                    Entrada(ordem: 3, child: _secaoRanking()),
                    const SizedBox(height: 10),
                    Entrada(ordem: 3, child: _secaoSetups()),
                    const SizedBox(height: 10),
                    Entrada(ordem: 4, child: _sobre()),
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

  // ---- topo: relógio, "Escolha a duração da partida" e o touro da arte (flutuando)
  Widget _cabecalho() {
    return SizedBox(
      height: 112,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            right: -8,
            top: 0,
            bottom: 0,
            child: ShaderMask(
              shaderCallback: (r) => const LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [Color(0x00000000), Color(0xFF000000)],
                stops: [0, 0.35],
              ).createShader(r),
              blendMode: BlendMode.dstIn,
              child: ShaderMask(
                shaderCallback: (r) => const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFF000000), Color(0x00000000)],
                  stops: [0.8, 1],
                ).createShader(r),
                blendMode: BlendMode.dstIn,
                child: Flutua(altura: 3, child: Image.asset('assets/jogos/tb_touro.webp', height: 112, fit: BoxFit.fitHeight)),
              ),
            ),
          ),
          Positioned(
            left: 2,
            top: 20,
            right: 120,
            child: Row(
              children: [
                ClipOval(child: Image.asset('assets/jogos/tb_ic_relogio.webp', width: 46, height: 46, fit: BoxFit.cover)),
                const SizedBox(width: 10),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Escolha a duração da partida',
                          style: TextStyle(fontSize: 17, height: 1.1, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
                      SizedBox(height: 3),
                      Text('Defina o tempo da sua batalha!',
                          style: TextStyle(fontSize: 13, fontStyle: FontStyle.italic, color: Color(0xFFD4E2F7), shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---- as três durações, no visual da arte (azul, dourado e roxo). A escolhida cresce, pulsa e ganha o ✓; as outras ficam mais apagadas.
  static const _estilos = {
    'rapida': ('tb_ic_rapida', Color(0xFF3FA2FF), [Color(0xFF2050D8), Color(0xFF141C78)]),
    'intermediaria': ('tb_ic_inter', Color(0xFFFFC93C), [Color(0xFF5B3A16), Color(0xFF162340)]),
    'longa': ('tb_ic_longa', Color(0xFF83ACFF), [Color(0xFF2B5FB8), Color(0xFF12356E)]),
  };

  Widget _duracoes(List<Map<String, dynamic>> corridas) {
    if (corridas.isEmpty) return const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator()));
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (final (i, c) in corridas.indexed) ...[
            if (i > 0) const SizedBox(width: 7),
            Expanded(child: _duracao(c)),
          ],
        ],
      ),
    );
  }

  Widget _duracao(Map<String, dynamic> c) {
    final id = '${c['id']}';
    final on = id == _corrida;
    final (arte, cor, fundo) = _estilos[id] ?? _estilos['intermediaria']!;
    return Pressionavel(
      aoTocar: () => setState(() => _corrida = id),
      child: AnimatedScale(
        scale: on ? 1.04 : 0.97,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutBack,
        child: AnimatedOpacity(
          opacity: on ? 1 : 0.72,
          duration: const Duration(milliseconds: 250),
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                height: 128,
                padding: const EdgeInsets.fromLTRB(6, 12, 6, 8),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: cor.withValues(alpha: on ? 1 : 0.6), width: 2),
                  gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: fundo),
                  boxShadow: [BoxShadow(color: cor.withValues(alpha: on ? 0.55 : 0.25), blurRadius: on ? 16 : 8)],
                ),
                child: Column(
                  children: [
                    ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.asset('assets/jogos/$arte.webp', height: 46)),
                    const SizedBox(height: 5),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Text('${c['rotulo']}', style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w900, color: Colors.white)),
                    ),
                    const SizedBox(height: 1),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Text('Gráfico de ${c['grafico']}', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: Color(0xFFDEEBFF))),
                    ),
                    Text('~${c['minutos']} min', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Color(0xFFDEEBFF))),
                  ],
                ),
              ),
              if (on) Positioned.fill(child: IgnorePointer(child: Pulso(cor: cor, raio: 18, largura: 2.5))),
              if (id == 'intermediaria')
                Positioned(
                  top: -11,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(999),
                        gradient: const LinearGradient(colors: [Color(0xFFFFE08A), Color(0xFFF2B84B)]),
                        border: Border.all(color: const Color(0xFFFFF1B8), width: 1.2),
                        boxShadow: const [BoxShadow(color: Color(0x99F2B84B), blurRadius: 8)],
                      ),
                      child: const Text('Recomendado ★', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: Color(0xFF3B2600))),
                    ),
                  ),
                ),
              if (on)
                Positioned(
                  right: -5,
                  top: -7,
                  child: TweenAnimationBuilder<double>(
                    key: ValueKey(id),
                    tween: Tween(begin: 0, end: 1),
                    duration: const Duration(milliseconds: 500),
                    curve: Curves.elasticOut,
                    builder: (ctx, v, f) => Transform.scale(scale: v, child: f),
                    child: Container(
                      width: 22,
                      height: 22,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: const Color(0xFF26D07C),
                        border: Border.all(color: Colors.white, width: 2),
                        boxShadow: const [BoxShadow(color: Color(0x9926D07C), blurRadius: 8)],
                      ),
                      child: const Icon(Icons.check, size: 13, color: Colors.white),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  // ---- Sobre o Trade Battle (ícones da arte)
  Widget _sobre() {
    const itens = [('tb_ic_jog', '2-4', 'jogadores'), ('tb_ic_graf', '15m · 1h · 1D', 'gráficos reais'), ('tb_ic_saldo', '5%', 'do saldo disponível'), ('tb_ic_xp', 'XP', 'por colocação')];
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 12, 10, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFF4F88E6), width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF134188), Color(0xFF0B2C5E)]),
        boxShadow: const [BoxShadow(color: Color(0x664F88E6), blurRadius: 14)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(left: 4, bottom: 8),
            child: Row(children: [
              Icon(Icons.star_rounded, color: Color(0xFFFFC93C), size: 24),
              SizedBox(width: 6),
              Text('Sobre o Trade Battle', style: TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, color: Colors.white)),
            ]),
          ),
          Container(
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xFF082552), border: Border.all(color: const Color(0x404F88E6))),
            child: IntrinsicHeight(
              child: Row(
                children: [
                  for (final (i, (ic, b, t)) in itens.indexed) ...[
                    if (i > 0) const VerticalDivider(width: 1, thickness: 1, color: Color(0x594F88E6)),
                    Expanded(
                      child: Column(
                        children: [
                          ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.asset('assets/jogos/$ic.webp', height: 34)),
                          const SizedBox(height: 4),
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(b, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white)),
                          ),
                          Text(t, textAlign: TextAlign.center, style: const TextStyle(fontSize: 10.5, height: 1.2, color: Color(0xFFB5C8E6))),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- Jogar Solo / Jogar com Amigos: a arte inteira é o botão (afunda ao tocar) e um reflexo de luz passa de tempos em tempos
  Widget _cartaoModo(String arte, Duration atraso, VoidCallback acao) => Pressionavel(
        aoTocar: acao,
        child: Reflexo(raio: 14, atraso: atraso, child: Image.asset('assets/jogos/$arte.webp')),
      );

  // ---- aviso quando a duração escolhida ainda não tem gráfico real
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
                Text('Os gráficos reais desta duração ainda estão sendo preparados. Tente outra duração ou volte mais tarde.',
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

  // ---- Entrar em uma Sala / Voltar para a sala (no visual da arte)
  Widget _linhaSala(bool ativa) {
    return Pressionavel(
      aoTocar: ativa ? () => _abrirSala('${_d!['ativa']}') : null,
      child: Container(
        constraints: const BoxConstraints(minHeight: 58),
        padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: const Color(0xFF4F88E6), width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1C50A0), Color(0xFF0F3878)]),
          boxShadow: const [BoxShadow(color: Color(0x804F88E6), blurRadius: 14)],
        ),
        child: Row(
          children: [
            Icon(ativa ? Icons.login_rounded : Icons.group_rounded, size: 30, color: const Color(0xFFDEEBFF)),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(ativa ? 'Voltar para sua partida' : 'Jogar com um amigo',
                      style: const TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, color: Colors.white)),
                  if (!ativa)
                    const Text('Em Meus Amigos, toque em "Desafiar no Trade Battle"', style: TextStyle(fontSize: 12.2, fontWeight: FontWeight.w500, color: Color(0xFFC2DAFF))),
                ],
              ),
            ),
            if (ativa) const Icon(Icons.chevron_right_rounded, size: 30, color: Colors.white),
          ],
        ),
      ),
    );
  }

  /// Encontrar adversário (no lugar do antigo "Jogar com Amigos"): desenhado em código, do mesmo tamanho das artes dos outros modos.
  Widget _cartaoAdversario(bool ativa) => Pressionavel(
        aoTocar: ativa ? () => _abrirSala('${_d!['ativa']}') : _procurar,
        child: AspectRatio(
          aspectRatio: 676 / 430,
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0xFF26D07C), width: 2),
              gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF14563E), Color(0xFF0B2A44)]),
              boxShadow: const [BoxShadow(color: Color(0x6626D07C), blurRadius: 14)],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.travel_explore_rounded, size: 40, color: Color(0xFF5BF5A0)),
                const SizedBox(height: 6),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(ativa ? 'VOLTAR PARA A PARTIDA' : 'ENCONTRAR ADVERSÁRIO',
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white, letterSpacing: .4)),
                ),
                const SizedBox(height: 2),
                const Text('Online · 1 contra 1', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: Color(0xFFBFE9D3))),
              ],
            ),
          ),
        ),
      );

  // ---- Meus Setups: atalho com o setup equipado e quantos já foram conquistados
  Widget _secaoSetups() {
    final st = _setups;
    final itens = (st?['itens'] as List? ?? []).cast<Map>();
    final eq = itens.where((x) => x['equipado'] == true).map((x) => '${x['nome']}').join(' · ');
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () async {
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => SetupsTela(api: widget.api)));
        _carregar();
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: const Color(0xCC10274A), borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x55FFD76A))),
        child: Row(children: [
          const Icon(Icons.gps_fixed, color: Color(0xFFFFD76A)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Meus Setups', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
              Text(eq.isNotEmpty ? 'Equipados: $eq' : (itens.isEmpty ? 'Ganhe cartas de setup nos baús' : 'Nenhum equipado'), style: const TextStyle(fontSize: 12.5, color: Colors.white70)),
            ]),
          ),
          Text(st == null ? '' : '${itens.length}/${st['total']}', style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w800)),
          const SizedBox(width: 6),
          const Icon(Icons.chevron_right, color: Colors.white70),
        ]),
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
                style: const TextStyle(fontSize: 13, height: 1.45, color: Color(0xFFE9F1FF)),
              ),
            ),
        ],
      ),
    );
  }
}
