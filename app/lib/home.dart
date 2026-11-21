import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'animacoes.dart';
import 'api.dart';
import 'carteira.dart';
import 'cenario.dart';
import 'desafio.dart';
import 'escudo.dart';
import 'mercado.dart';
import 'missoes.dart';
import 'navegacao.dart';
import 'ranking.dart' show RankingTela, rankingPedido;
import 'social.dart';
import 'ticker.dart';
import 'trade.dart';

/// Tela inicial no estilo de jogo mobile (fundo da cidade de dia, painéis azul-marinho e dourado), sem rolagem:
///   1. placa do jogador (divisão, nome e Ticker Pass) e o quadro dos indicadores do dia (passam de dois em dois)
///   2. o urso do joinha e a placa do Desafio do dia (contagem e se você já jogou)
///   3. os botões grandes do Trade Battle e do Ticker Battle
///   4. atalhos (Cenário, Torneio, Carteira, Missões, Amigos), a liga no centro e, à direita, o Mercado e a melhor nota do Desafio
///   5. faixa do Duelo: desafie um amigo
/// Dados: `GET /eu` (nome, passe) e `GET /home` (indicadores, missões, cenário, desafio, troféus, torneio e pedidos de amizade).
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

const _verde = Color(0xFF2EE88A);
const _vermelho = Color(0xFFFF5A6E);
const _ouro = Color(0xFFF7C84A);
const _ouroEscuro = Color(0xFF8A4E00);
const _azulBorda = Color(0xFF3A6FD8);
const _texto2 = Color(0xFFBFD3FF);

/// Painel azul-marinho translúcido, o "vidro" de todos os blocos da tela.
BoxDecoration _painel({Color borda = _azulBorda, double raio = 18}) => BoxDecoration(
      borderRadius: BorderRadius.circular(raio),
      gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xEB16306A), Color(0xF00B1A44)]),
      border: Border.all(color: borda, width: 1.6),
      boxShadow: const [BoxShadow(color: Color(0x88000814), offset: Offset(0, 4), blurRadius: 8)],
    );

/// Título de jogo: letras grossas em itálico com degradê (branco→dourado), contorno escuro e sombra.
Widget _tituloJogo(String t, double tam, {List<Color> cores = const [Colors.white, Color(0xFFFFE27A), Color(0xFFF5A623)]}) {
  final estilo = TextStyle(fontSize: tam, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, height: 1.0, letterSpacing: 0.5);
  return Stack(children: [
    Text(t,
        style: estilo.copyWith(
            foreground: Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = tam / 6
              ..color = const Color(0xFF1A1030))),
    ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (r) => LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: cores).createShader(r),
      child: Text(t, style: estilo.copyWith(color: Colors.white)),
    ),
  ]);
}

class _HomeTelaState extends State<HomeTela> {
  Map<String, dynamic>? _eu, _home;
  String? _erro;
  bool _carregando = true;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final r = await Future.wait([widget.api.get('/eu'), widget.api.get('/home').catchError((_) => <String, dynamic>{})]);
      if (mounted) {
        setState(() {
          _eu = r[0];
          _home = r[1];
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = 'Não consegui carregar a sua Home agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  String get _nome {
    final perfil = (_eu?['perfil'] as Map?) ?? {};
    final conta = (_eu?['conta'] as Map?) ?? {};
    for (final n in [perfil['nome'], perfil['usuario'], conta['nome']]) {
      if (n is String && n.trim().isNotEmpty) return n.contains('@') ? n.split('@').first : n.trim();
    }
    final e = '${conta['email'] ?? ''}';
    return e.contains('@') ? e.split('@').first : 'Jogador';
  }

  Map get _comp => (_home?['competicao'] as Map?) ?? const {};
  String get _jogo => '${_comp['jogo'] ?? 'trade'}';
  Map get _div => (_comp['divisao'] as Map?) ?? const {};

  /// Abre uma tela e, na volta, relê a Home (missões, troféus e o desafio podem ter mudado).
  Future<void> _abrir(Widget t) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => t));
    if (mounted) _carregar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1638),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/home/cidade_dia.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x330B1638), Color(0x000B1638), Color(0xB00B1638), Color(0xF00B1638)],
                stops: [0, 0.25, 0.5, 0.72],
              ),
            ),
          ),
          SafeArea(
            child: LayoutBuilder(builder: (ctx, c) {
              const fixo = 56 + 74 + 236 + 70 + 4 * 8 + 12.0;
              final alt = math.max(c.maxHeight, fixo + 170);
              return RefreshIndicator(
                onRefresh: _carregar,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(maxWidth: 640, minHeight: alt, maxHeight: alt),
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(10, 6, 10, 6),
                        child: _carregando && _eu == null
                            ? const Center(child: CircularProgressIndicator())
                            : _erro != null && _eu == null
                                ? _erroTela()
                                : Column(children: [
                                    Entrada(ordem: 0, child: _topo()),
                                    Expanded(child: _heroi()),
                                    Entrada(ordem: 1, child: _jogos()),
                                    const SizedBox(height: 8),
                                    Entrada(ordem: 2, child: _meio()),
                                    const SizedBox(height: 8),
                                    Entrada(ordem: 3, child: _duelo()),
                                  ]),
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }

  // ---- 1. placa do jogador e indicadores do dia
  Widget _topo() {
    final p = (_eu?['passe'] as Map?) ?? const {};
    final total = (p['total'] as num?)?.toInt() ?? 0, feitos = (p['feitos'] as num?)?.toInt() ?? 0;
    final pct = total == 0 ? 0.0 : (p['completo'] == true ? 1.0 : ((feitos + ((p['pct'] as num?) ?? 0).toDouble()) / total).clamp(0.0, 1.0));
    final itens = ((_home?['hoje'] as List?) ?? const []).cast<Map>();
    return SizedBox(
      height: 56,
      child: Row(children: [
        Expanded(
          flex: 11,
          child: Pressionavel(
            aoTocar: () => abrirAba(2),
            child: Container(
              padding: const EdgeInsets.fromLTRB(4, 4, 12, 4),
              decoration: _painel(raio: 28),
              child: Row(children: [
                Escudo.de(_div, tamanho: 46),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                    Text(_nome, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                    Row(children: [
                      const Text('👑 ', style: TextStyle(fontSize: 11)),
                      Text('${_div['nome'] ?? 'Bronze'}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: _ouro)),
                      const SizedBox(width: 6),
                      Expanded(child: _barra(pct, const [Color(0xFFFFE27A), Color(0xFFF5A623)], altura: 6)),
                      Text(' $feitos/$total', style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: _texto2)),
                    ]),
                  ]),
                ),
              ]),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          flex: 10,
          child: Pressionavel(
            aoTocar: () => _abrir(CenarioTela(api: widget.api)),
            child: Container(
              padding: const EdgeInsets.fromLTRB(8, 4, 8, 4),
              decoration: _painel(raio: 16),
              child: Row(children: [
                const Icon(Icons.insights_rounded, color: _verde, size: 26),
                const SizedBox(width: 6),
                Expanded(child: itens.isEmpty ? const Text('Cotações já voltam', style: TextStyle(fontSize: 11, color: _texto2)) : _Indicadores(itens: itens)),
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  // ---- 2. o urso e a placa do Desafio do dia
  Widget _heroi() {
    final d = (_home?['desafio'] as Map?) ?? const {};
    final s = (d['termina_em'] as num?)?.toInt() ?? 0;
    final (txt, ic, cor) = d['terminou'] == true
        ? ('Você já jogou hoje!', Icons.check_circle_rounded, _verde)
        : d['jogou'] == true
            ? ('Termine sua tentativa!', Icons.play_circle_fill_rounded, _ouro)
            : ('Valendo TC! Jogue agora', Icons.bolt_rounded, _ouro);
    return LayoutBuilder(builder: (ctx, c) {
      final h = c.maxHeight;
      final placaL = math.min(c.maxWidth * 0.56, 330.0);
      return Stack(clipBehavior: Clip.none, children: [
        Positioned(
          left: -6,
          bottom: -6,
          height: math.min(h + 6, c.maxWidth * 0.78),
          child: Flutua(altura: 5, periodo: const Duration(milliseconds: 3200), child: Image.asset('assets/home/urso_joinha.webp', fit: BoxFit.contain)),
        ),
        Positioned(
          right: 0,
          top: math.max(4, h * 0.08),
          width: placaL,
          child: Pressionavel(
            aoTocar: () => _abrir(DesafioTela(api: widget.api)),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Stack(alignment: Alignment.center, children: [
                Image.asset('assets/home/placa_desafio.webp', width: placaL, fit: BoxFit.contain),
                Padding(
                  padding: EdgeInsets.only(top: placaL * 0.08),
                  child: FittedBox(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      _tituloJogo('DESAFIO', placaL * 0.12, cores: const [Colors.white, Color(0xFFD6E6FF)]),
                      _tituloJogo('DO DIA', placaL * 0.12),
                    ]),
                  ),
                ),
              ]),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(14),
                  gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF6B3A12), Color(0xFF3E1F08)]),
                  border: Border.all(color: _ouro, width: 1.6),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.schedule_rounded, color: _ouro, size: 20),
                  const SizedBox(width: 6),
                  Text(contagem(s), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFFFFE27A))),
                ]),
              ),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: _painel(raio: 14),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(ic, color: cor, size: 18),
                  const SizedBox(width: 6),
                  Flexible(child: Text(txt, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: Colors.white))),
                ]),
              ),
            ]),
          ),
        ),
      ]);
    });
  }

  // ---- 3. botões grandes dos dois jogos
  Widget _jogos() => SizedBox(
        height: 74,
        child: Row(children: [
          Expanded(child: _botaoJogo('assets/home/btn_trade.webp', 'TRADE', 'BATTLE', () => _abrir(TradeTela(api: widget.api)), 0)),
          const SizedBox(width: 8),
          Expanded(child: _botaoJogo('assets/home/btn_ticker.webp', 'TICKER', 'BATTLE', () => _abrir(TickerTela(api: widget.api)), 1)),
        ]),
      );

  Widget _botaoJogo(String arte, String l1, String l2, VoidCallback f, int i) => Pressionavel(
        aoTocar: f,
        child: Reflexo(
          raio: 14,
          atraso: Duration(milliseconds: 900 * i),
          child: Stack(fit: StackFit.expand, children: [
            Image.asset(arte, fit: BoxFit.fill),
            Positioned(
              left: 0,
              right: 6,
              top: 0,
              bottom: 0,
              child: Row(children: [
                const Spacer(flex: 9),
                Expanded(
                  flex: 11,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                      _tituloJogo(l1, 22, cores: const [Colors.white, Color(0xFFDDE8FF)]),
                      _tituloJogo(l2, 22),
                    ]),
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, color: Colors.white, size: 30, shadows: [Shadow(color: Colors.black54, offset: Offset(0, 2))]),
              ]),
            ),
          ]),
        ),
      );

  // ---- 4. atalhos, liga e cartões da direita
  Widget _meio() {
    final m = (_home?['missoes'] as Map?) ?? const {};
    final faltam = math.max(0, ((m['total'] as num?)?.toInt() ?? 0) - ((m['feitas'] as num?)?.toInt() ?? 0));
    final trn = (_home?['torneio'] as Map?) ?? const {};
    final pedidos = ((_home?['amigos'] as Map?)?['pedidos'] as num?)?.toInt() ?? 0;
    Widget arte(String a) => Image.asset(a, width: 30, height: 30, fit: BoxFit.contain);
    Widget emoji(String e) => SizedBox(width: 30, child: Text(e, textAlign: TextAlign.center, style: const TextStyle(fontSize: 22)));
    final atalhos = <(Widget, String, String?, VoidCallback)>[
      (arte('assets/home/ic_cenario.webp'), 'Cenário', null, () => _abrir(CenarioTela(api: widget.api))),
      (arte('assets/home/ic_torneio.webp'), 'Torneio', trn['aberto'] == true ? (trn['inscrito'] == true ? '✓' : '!') : null, () => _abrir(RankingTela(api: widget.api, unico: 'torneio'))),
      (emoji('💰'), 'Carteira', null, () => _abrir(CarteiraTela(api: widget.api))),
      (arte('assets/home/ic_missoes.webp'), 'Missões', faltam > 0 ? '$faltam' : null, () => _abrir(MissoesTela(api: widget.api))),
      (emoji('👥'), 'Amigos', pedidos > 0 ? '$pedidos' : null, () => _abrir(SocialTela(api: widget.api))),
    ];
    return SizedBox(
      height: 236,
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Expanded(
          flex: 30,
          child: Column(children: [
            for (final (i, (ic, rot, aviso, f)) in atalhos.indexed) ...[
              if (i > 0) const SizedBox(height: 4),
              Expanded(
                child: Pressionavel(
                  aoTocar: f,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6),
                    decoration: _painel(raio: 12),
                    child: Row(children: [
                      ic,
                      const SizedBox(width: 6),
                      Expanded(
                          child: FittedBox(
                              fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(rot, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, color: Colors.white)))),
                      if (aviso != null)
                        Container(
                          constraints: const BoxConstraints(minWidth: 20),
                          height: 20,
                          alignment: Alignment.center,
                          padding: const EdgeInsets.symmetric(horizontal: 4),
                          decoration:
                              BoxDecoration(color: aviso == '✓' ? const Color(0xFF12A85A) : const Color(0xFFE5243B), shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 1.4)),
                          child: Text(aviso, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white)),
                        ),
                    ]),
                  ),
                ),
              ),
            ],
          ]),
        ),
        const SizedBox(width: 6),
        Expanded(flex: 38, child: _liga()),
        const SizedBox(width: 6),
        Expanded(
          flex: 32,
          child: Column(children: [
            Expanded(flex: 13, child: _mercado()),
            const SizedBox(height: 6),
            Expanded(flex: 10, child: _melhorNota()),
          ]),
        ),
      ]),
    );
  }

  Widget _liga() {
    final dv = _div;
    final cor = Escudo.corDe(dv['cor']);
    final prox = dv['prox'] as Map?;
    return Pressionavel(
      aoTocar: () {
        rankingPedido.value = _jogo;
        abrirAba(3);
      },
      child: Container(
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
        decoration: _painel(),
        child: Column(children: [
          Expanded(
            child: Stack(alignment: Alignment.center, children: [
              Container(decoration: BoxDecoration(shape: BoxShape.circle, gradient: RadialGradient(colors: [cor.withValues(alpha: 0.5), cor.withValues(alpha: 0)]))),
              Flutua(altura: 4, child: LayoutBuilder(builder: (ctx, c) => Escudo.de(dv, tamanho: math.min(c.maxHeight, c.maxWidth) * 0.95))),
            ]),
          ),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 3),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFD66B), Color(0xFFD9861A)]),
              border: Border.all(color: _ouroEscuro, width: 1.6),
            ),
            child: FittedBox(fit: BoxFit.scaleDown, child: Text('${dv['nome'] ?? 'Bronze'}', style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Color(0xFF4A2800)))),
          ),
          const SizedBox(height: 5),
          FittedBox(
            child: Row(children: [
              const Icon(Icons.emoji_events_rounded, color: _ouro, size: 18),
              const SizedBox(width: 3),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: ((_comp['t'] as num?) ?? 0).toDouble()),
                duration: const Duration(milliseconds: 900),
                builder: (ctx, v, _) => Text('${v.round()} troféus', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
              ),
            ]),
          ),
          const SizedBox(height: 4),
          _barra(((dv['pct'] as num?) ?? 0).toDouble(), const [Color(0xFFFFE27A), Color(0xFFF5A623)], altura: 9, minimo: 0.06),
          const SizedBox(height: 3),
          FittedBox(child: Text(prox == null ? 'Divisão máxima!' : 'Faltam ${dv['falta'] ?? '—'} para ${prox['nome']}', style: const TextStyle(fontSize: 11, color: _texto2))),
          Text(_jogo == 'ticker' ? 'Ticker Battle' : 'Trade Battle', style: const TextStyle(fontSize: 10, color: _texto2)),
        ]),
      ),
    );
  }

  Widget _mercado() {
    final itens = ((_home?['hoje'] as List?) ?? const []).cast<Map>();
    final ibov = itens.where((x) => x['rotulo'] == 'Ibovespa').firstOrNull;
    final v = ibov?['var'];
    final alta = v is! num || v >= 0;
    final cor = alta ? _verde : _vermelho;
    return Pressionavel(
      aoTocar: () => _abrir(MercadoTela(api: widget.api)),
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: _painel(borda: alta ? const Color(0xFF2FB874) : const Color(0xFFD8475A)),
        child: Stack(fit: StackFit.expand, children: [
          Positioned.fill(
            child: ColorFiltered(
              colorFilter: alta ? const ColorFilter.mode(Colors.transparent, BlendMode.dst) : const ColorFilter.matrix([1, 0, 0, 0, 0, 0, 0.55, 0, 0, 0, 0, 0, 0.6, 0, 0, 0, 0, 0, 1, 0]),
              child: Image.asset('assets/home/touro_mercado.webp', fit: BoxFit.cover, alignment: Alignment.bottomRight),
            ),
          ),
          const DecoratedBox(
              decoration: BoxDecoration(
                  gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xF20B1A44), Color(0xCC0B1A44), Color(0x000B1A44)], stops: [0, 0.45, 0.8]))),
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              FittedBox(child: Text(v is num ? (alta ? 'Mercado em Alta' : 'Mercado em Baixa') : 'Mercado', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Colors.white))),
              if (v is num)
                FittedBox(
                  child: Row(children: [
                    Icon(alta ? Icons.trending_up_rounded : Icons.trending_down_rounded, color: cor, size: 24),
                    const SizedBox(width: 3),
                    Text('${alta ? '+' : ''}${v.toStringAsFixed(2).replaceAll('.', ',')}%',
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: cor, shadows: const [Shadow(color: Colors.black87, offset: Offset(0, 2), blurRadius: 3)])),
                  ]),
                ),
              const Text('Ibovespa hoje', style: TextStyle(fontSize: 10, color: _texto2)),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _melhorNota() {
    final n = _comp['desafio_max'];
    return Pressionavel(
      aoTocar: () => _abrir(DesafioTela(api: widget.api)),
      child: Container(
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
        decoration: _painel(),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const FittedBox(child: Text('Sua Melhor Pontuação', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: Colors.white))),
          Expanded(
            child: Row(children: [
              Image.asset('assets/home/ic_torneio.webp', height: 32),
              const SizedBox(width: 4),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                  FittedBox(child: Text(n is num ? n.toStringAsFixed(1).replaceAll('.', ',') : '—', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: _ouro))),
                  const FittedBox(child: Text('no Desafio do Dia', style: TextStyle(fontSize: 10, color: _texto2))),
                ]),
              ),
            ]),
          ),
        ]),
      ),
    );
  }

  // ---- 5. faixa do Duelo
  Widget _duelo() => Pressionavel(
        aoTocar: () => _abrir(SocialTela(api: widget.api)),
        child: Container(
          height: 70,
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            gradient: const LinearGradient(colors: [Color(0xFF1C4FB8), Color(0xFF12307A), Color(0xFF0E2257)]),
            border: Border.all(color: _ouro, width: 1.8),
            boxShadow: const [BoxShadow(color: Color(0x66F7C84A), blurRadius: 12)],
          ),
          child: Stack(children: [
            Positioned(left: -4, bottom: -22, child: Image.asset('assets/ranking/urso_aponta.webp', height: 100)),
            Positioned(
              left: 92,
              right: 8,
              top: 0,
              bottom: 0,
              child: Row(children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                    FittedBox(child: _tituloJogo('BORA DUELAR?', 20)),
                    const SizedBox(height: 2),
                    const FittedBox(child: Text('Desafie um amigo e vale troféus!', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Colors.white))),
                  ]),
                ),
                const SizedBox(width: 6),
                Reflexo(
                  raio: 14,
                  intervalo: const Duration(milliseconds: 3000),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE27A), Color(0xFFF5A623)]),
                      border: Border.all(color: _ouroEscuro, width: 2),
                      boxShadow: const [BoxShadow(color: _ouroEscuro, offset: Offset(0, 3))],
                    ),
                    child: const Row(mainAxisSize: MainAxisSize.min, children: [
                      Text('Duelo', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Color(0xFF4A2800))),
                      Icon(Icons.chevron_right_rounded, color: Color(0xFF4A2800)),
                    ]),
                  ),
                ),
              ]),
            ),
          ]),
        ),
      );

  Widget _barra(double v, List<Color> cores, {double altura = 9, double minimo = 0}) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: math.max(minimo, v.clamp(0.0, 1.0))),
        duration: const Duration(milliseconds: 1100),
        curve: Curves.easeOutCubic,
        builder: (ctx, x, _) => Container(
          height: altura,
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xFF07112E), border: Border.all(color: const Color(0x553A6FD8))),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: Align(
              alignment: Alignment.centerLeft,
              child: FractionallySizedBox(widthFactor: x, child: Container(decoration: BoxDecoration(gradient: LinearGradient(colors: cores)))),
            ),
          ),
        ),
      );

  Widget _erroTela() => Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
          TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
        ]),
      );
}

/// Quadro dos indicadores: mostra dois por vez (IBOV e Dólar, depois BTC e Medo) e troca a cada 4 segundos, deslizando.
class _Indicadores extends StatefulWidget {
  const _Indicadores({required this.itens});
  final List<Map> itens;

  @override
  State<_Indicadores> createState() => _IndicadoresState();
}

class _IndicadoresState extends State<_Indicadores> {
  static const _curto = {'Ibovespa': 'IBOV', 'Dólar': 'Dólar', 'Bitcoin': 'BTC', 'Índice do medo': 'Medo'};
  int _pag = 0;
  Timer? _t;

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 4), (_) {
      if (mounted && widget.itens.length > 2) setState(() => _pag = (_pag + 1) % ((widget.itens.length + 1) ~/ 2));
    });
  }

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  Widget _linha(Map it) {
    final v = it['var'];
    final cor = v is num ? (v >= 0 ? _verde : _vermelho) : _ouro;
    return FittedBox(
      fit: BoxFit.scaleDown,
      alignment: Alignment.centerLeft,
      child: Row(children: [
        Text('${_curto['${it['rotulo']}'] ?? it['rotulo']} ', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w900, color: Colors.white)),
        Text('${it['valor']} ', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: _texto2)),
        Text(v is num ? '${v >= 0 ? '▲ +' : '▼ '}${v.toStringAsFixed(2).replaceAll('.', ',')}%' : '${it['nota'] ?? ''}', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w900, color: cor)),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final par = widget.itens.skip(_pag * 2).take(2).toList();
    return ClipRect(
        child: AnimatedSwitcher(
      duration: const Duration(milliseconds: 450),
      transitionBuilder: (w, a) => SlideTransition(
        position: Tween(begin: const Offset(0, 0.6), end: Offset.zero).animate(a),
        child: FadeTransition(opacity: a, child: w),
      ),
      child: Column(
        key: ValueKey(_pag),
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [for (final it in par) _linha(it)],
      ),
    ));
  }
}
