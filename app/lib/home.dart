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
import 'tour.dart';
import 'trade.dart';

/// Tela inicial (a "capa" do jogo), igual à arte de referência, sem rolagem:
///   1. placa do jogador (escudo, nome e divisão) e quadro com IBOV e Dólar do dia
///   2. o urso do joinha e a placa do Desafio do dia (contagem e se você já jogou)
///   3. os botões grandes do Trade Battle e do Ticker Battle
///   4. lista (Cenário, Torneio, Carteira, Missões, Loja), a liga no centro (escudo com louros, faixa da divisão, troféus e barra)
///      e, à direita, Mercado em Alta/Baixa e a melhor nota do Desafio
///   5. faixa de convite que alterna: Bora jogar Trade Battle? / Ticker Battle? / Bora duelar? (amigos)
/// Dados: `GET /eu` e `GET /home` (indicadores, missões, cenário, desafio, troféus, torneio e pedidos de amizade).
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

const _verde = Color(0xFF2EE88A);
const _vermelho = Color(0xFFFF4D5E);
const _ouro = Color(0xFFF7C84A);
const _ouroEscuro = Color(0xFF8A4E00);
const _azulBorda = Color(0xFF2E5AB0);
const _texto2 = Color(0xFFC9D8FF);

/// Painel azul-marinho (o "vidro" dos blocos).
BoxDecoration _painel({Color borda = _azulBorda, double raio = 18, List<Color>? cores}) => BoxDecoration(
      borderRadius: BorderRadius.circular(raio),
      gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: cores ?? const [Color(0xF0173372), Color(0xF50B1A47)]),
      border: Border.all(color: borda, width: 1.6),
      boxShadow: const [BoxShadow(color: Color(0x99000814), offset: Offset(0, 4), blurRadius: 8)],
    );

/// Título de jogo: letras grossas em itálico com degradê, contorno escuro e sombra.
Widget _tituloJogo(String t, double tam, {List<Color> cores = const [Color(0xFFFFF3B0), Color(0xFFFFD34A), Color(0xFFF5A623)]}) {
  final estilo = TextStyle(fontSize: tam, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, height: 1.02, letterSpacing: 0.3);
  return Stack(children: [
    Text(t,
        style: estilo.copyWith(
            shadows: const [Shadow(color: Color(0xCC000000), offset: Offset(0, 3), blurRadius: 2)],
            foreground: Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = tam / 5.5
              ..strokeJoin = StrokeJoin.round
              ..color = const Color(0xFF14102E))),
    ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (r) => LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: cores).createShader(r),
      child: Text(t, style: estilo.copyWith(color: Colors.white)),
    ),
  ]);
}

const _branco = [Colors.white, Color(0xFFE4EEFF), Color(0xFFB8CFFF)];

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
      // as cotações vêm à parte, sem segurar a tela: dependem de fonte externa que pode demorar ou cair
      widget.api.get('/home/cotacoes').then((c) {
        if (mounted) setState(() => _cot = ((c['hoje'] as List?) ?? const []).cast<Map>());
      }).catchError((_) {});
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
  List<Map> _cot = const [];
  List<Map> get _hoje => _cot;

  /// Marca um elemento para o tour guiado (sem id, devolve o próprio elemento).
  Widget _alvo(String? id, Widget w) => id == null ? w : TourAlvo(id: id, child: w);

  /// Abre uma tela e, na volta, relê a Home (missões, troféus e o desafio podem ter mudado).
  Future<void> _abrir(Widget t) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => t));
    if (mounted) _carregar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1A47),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/home/cidade_dia.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x220B1A47), Color(0x000B1A47), Color(0x660B1A47), Color(0xAA0B1A47)],
                stops: [0, 0.3, 0.6, 1],
              ),
            ),
          ),
          SafeArea(
            child: LayoutBuilder(builder: (ctx, c) {
              // Telas grandes (tablet) mostram a mesma composição do celular, ampliada: monta numa largura de celular e escala.
              const fixo = 60 + 72 + 232 + 70 + 3 * 8 + 12.0;
              final k = math.max(1.0, math.min(c.maxWidth / 400, c.maxHeight / 700));
              final wl = math.min(c.maxWidth / k, 520.0);
              final hl = math.max(c.maxHeight / k, fixo + 170);
              final conteudo = SizedBox(
                width: wl,
                height: hl,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(10, 6, 10, 6),
                  child: _carregando && _eu == null
                      ? _esqueleto()
                      : _erro != null && _eu == null
                          ? _erroTela()
                          : Column(children: [
                              Entrada(ordem: 0, child: _topo()),
                              Expanded(child: _heroi()),
                              Entrada(ordem: 1, child: _jogos()),
                              const SizedBox(height: 8),
                              Entrada(ordem: 2, child: _meio()),
                              const SizedBox(height: 8),
                              Entrada(ordem: 3, child: _Convite(abrir: _abrir, api: widget.api, pedidos: ((_home?['amigos'] as Map?)?['pedidos'] as num?)?.toInt() ?? 0)),
                            ]),
                ),
              );
              return RefreshIndicator(
                onRefresh: _carregar,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  child: Center(
                    child: SizedBox(width: wl * k, height: hl * k, child: k == 1 ? conteudo : FittedBox(fit: BoxFit.fill, child: conteudo)),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }

  // ---- 1. placa do jogador e IBOV/Dólar
  Widget _topo() {
    Widget linha(Map it, String rot) {
      final v = it['var'];
      final cor = v is num ? (v >= 0 ? _verde : _vermelho) : _ouro;
      return FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Row(children: [
          Text('$rot ', style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w900, color: Colors.white)),
          Text('${it['valor']} ', style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: Colors.white)),
          Text(v is num ? '${v >= 0 ? '▲ +' : '▼ '}${v.toStringAsFixed(2).replaceAll('.', ',')}%' : '', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w900, color: cor)),
        ]),
      );
    }

    final ibov = _hoje.where((x) => x['rotulo'] == 'Ibovespa').firstOrNull;
    final dolar = _hoje.where((x) => x['rotulo'] == 'Dólar').firstOrNull;
    return SizedBox(
      height: 60,
      child: Row(children: [
        Expanded(
          flex: 10,
          child: Pressionavel(
            aoTocar: () {
              rankingPedido.value = _jogo;
              abrirAba(3);
            },
            child: Stack(clipBehavior: Clip.none, alignment: Alignment.centerLeft, children: [
              Container(
                margin: const EdgeInsets.only(left: 24, top: 4, bottom: 4),
                padding: const EdgeInsets.fromLTRB(36, 2, 12, 2),
                decoration: _painel(raio: 30),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                  Text(_nome, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
                  Row(children: [
                    const Text('👑 ', style: TextStyle(fontSize: 12)),
                    Flexible(child: Text('${_div['nome'] ?? 'Bronze'}', maxLines: 1, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: _ouro))),
                  ]),
                ]),
              ),
              Escudo.de(_div, tamanho: 58),
            ]),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          flex: 10,
          child: Pressionavel(
            aoTocar: () => _abrir(CenarioTela(api: widget.api)),
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 2),
              padding: const EdgeInsets.fromLTRB(8, 4, 8, 4),
              decoration: _painel(raio: 18),
              child: Row(children: [
                Image.asset('assets/home/ic_grafico.webp', width: 34),
                const SizedBox(width: 6),
                Expanded(
                  child: ibov == null && dolar == null
                      ? const Text('Cotações já voltam', style: TextStyle(fontSize: 11, color: _texto2))
                      : Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                          if (ibov != null) linha(ibov, 'IBOV'),
                          if (dolar != null) linha(dolar, 'Dólar'),
                        ]),
                ),
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
        ? ('Você já jogou hoje!', Icons.check_circle_rounded, const Color(0xFF22C55E))
        : d['jogou'] == true
            ? ('Termine sua tentativa!', Icons.play_circle_fill_rounded, _ouro)
            : ('Valendo TC! Jogue agora', Icons.bolt_rounded, _ouro);
    return LayoutBuilder(builder: (ctx, c) {
      final h = c.maxHeight;
      final placaL = math.min(c.maxWidth * 0.58, 360.0);
      return Stack(clipBehavior: Clip.none, children: [
        Positioned(
          left: -8,
          bottom: -8,
          height: math.min(h + 8, c.maxWidth * 0.8),
          child: Flutua(altura: 5, periodo: const Duration(milliseconds: 3200), child: Image.asset('assets/home/urso_joinha.webp', fit: BoxFit.contain)),
        ),
        Positioned(
          right: -2,
          top: math.max(2, (h - placaL * 0.62) * 0.3),
          width: placaL,
          child: Pressionavel(
            aoTocar: () => _abrir(DesafioTela(api: widget.api)),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Stack(alignment: Alignment.center, children: [
                TourAlvo(id: 'home_desafio', child: Image.asset('assets/home/placa_desafio.webp', width: placaL, fit: BoxFit.contain)),
                Padding(
                  padding: EdgeInsets.only(top: placaL * 0.09),
                  child: FittedBox(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      _tituloJogo('DESAFIO', placaL * 0.13, cores: _branco),
                      _tituloJogo('DO DIA', placaL * 0.15),
                    ]),
                  ),
                ),
              ]),
              Transform.translate(
                offset: const Offset(0, -4),
                child: Container(
                  width: placaL * 0.84,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF7A4316), Color(0xFF4A2408)]),
                    border: Border.all(color: _ouro, width: 2),
                    boxShadow: const [BoxShadow(color: Color(0x99000000), offset: Offset(0, 3), blurRadius: 4)],
                  ),
                  child: FittedBox(
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      const Icon(Icons.schedule_rounded, color: _ouro, size: 24),
                      const SizedBox(width: 8),
                      Text(contagem(s), style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: Color(0xFFFFE9A8))),
                    ]),
                  ),
                ),
              ),
              Container(
                width: placaL * 0.84,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: _painel(raio: 16),
                child: FittedBox(
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Container(
                      decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.white),
                      child: Icon(ic, color: cor, size: 20),
                    ),
                    const SizedBox(width: 6),
                    Text(txt, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white)),
                  ]),
                ),
              ),
            ]),
          ),
        ),
      ]);
    });
  }

  // ---- 3. botões grandes dos dois jogos
  Widget _jogos() => SizedBox(
        height: 72,
        child: Row(children: [
          Expanded(child: TourAlvo(id: 'home_trade', child: _botaoJogo('assets/home/btn_trade.webp', 'TRADE', 'BATTLE', () => _abrir(TradeTela(api: widget.api)), 0))),
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
                      _tituloJogo(l1, 22, cores: _branco),
                      _tituloJogo(l2, 22),
                    ]),
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, color: Colors.white, size: 32, shadows: [Shadow(color: Colors.black54, offset: Offset(0, 2))]),
              ]),
            ),
          ]),
        ),
      );

  // ---- 4. lista, liga e cartões da direita
  Widget _meio() {
    final m = (_home?['missoes'] as Map?) ?? const {};
    final faltam = math.max(0, ((m['total'] as num?)?.toInt() ?? 0) - ((m['feitas'] as num?)?.toInt() ?? 0));
    final trn = (_home?['torneio'] as Map?) ?? const {};
    // Quem ainda não ganhou troféu (não jogou online) vê só o essencial: Cenário e Torneio aparecem depois da primeira conquista.
    final jogosComp = (((_home?['competicao'] as Map?)?['jogos']) as Map?) ?? const {};
    final veterano = jogosComp.values.any((j) => j is Map && (((j['max'] ?? j['t']) as num?) ?? 0) > 0);
    final itens = <(String, String, String?, VoidCallback)>[
      if (veterano) ('assets/home/ic_cenario.webp', 'Cenário', null, () => _abrir(CenarioTela(api: widget.api))),
      if (veterano) ('assets/home/ic_torneio.webp', 'Torneio', trn['aberto'] == true ? (trn['inscrito'] == true ? '✓' : '1') : null, () => _abrir(RankingTela(api: widget.api, unico: 'torneio'))),
      ('assets/home/ic_carteira.webp', 'Carteira', null, () => _abrir(CarteiraTela(api: widget.api))),
      ('assets/home/ic_missoes.webp', 'Missões', faltam > 0 ? '$faltam' : null, () => _abrir(MissoesTela(api: widget.api))),
      ('assets/home/ic_loja.webp', 'Loja', null, () => abrirAba(4)),
    ];
    return SizedBox(
      height: 232,
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Expanded(
          flex: 29,
          child: Container(
            padding: const EdgeInsets.all(4),
            decoration: _painel(raio: 16),
            child: Column(children: [
              for (final (i, (arte, rot, aviso, f)) in itens.indexed) ...[
                if (i > 0) const SizedBox(height: 4),
                Expanded(
                  child: _alvo(rot == 'Carteira' ? 'home_carteira' : null, Pressionavel(
                    aoTocar: f,
                    child: Stack(clipBehavior: Clip.none, children: [
                      Container(
                        padding: const EdgeInsets.only(left: 5, right: 4),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(11),
                          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1C3B80), Color(0xFF12295E)]),
                          border: Border.all(color: const Color(0x663A6FD8)),
                        ),
                        child: Row(children: [
                          Image.asset(arte, width: 30, height: 30),
                          const SizedBox(width: 6),
                          Expanded(
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerLeft,
                              child: Text(rot, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white)),
                            ),
                          ),
                        ]),
                      ),
                      if (aviso != null)
                        Positioned(
                          right: -3,
                          top: -3,
                          child: Container(
                            width: 18,
                            height: 18,
                            alignment: Alignment.center,
                            decoration:
                                BoxDecoration(color: aviso == '✓' ? const Color(0xFF16A34A) : const Color(0xFFE5243B), shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 1.2)),
                            child: Text(aviso, style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w900, color: Colors.white)),
                          ),
                        ),
                    ]),
                  )),
                ),
              ],
            ]),
          ),
        ),
        const SizedBox(width: 6),
        Expanded(flex: 38, child: TourAlvo(id: 'home_liga', child: _liga())),
        const SizedBox(width: 6),
        Expanded(
          flex: 33,
          child: Column(children: [
            Expanded(flex: 13, child: TourAlvo(id: 'home_mercado', child: _mercado())),
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
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
        decoration: _painel(),
        child: Column(children: [
          Expanded(
            child: LayoutBuilder(builder: (ctx, c) {
              final e = math.min(c.maxHeight * 0.98, c.maxWidth * 0.62);
              return Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
                // brilho da divisão atrás do escudo
                Container(width: e * 1.5, height: e * 1.5, decoration: BoxDecoration(shape: BoxShape.circle, gradient: RadialGradient(colors: [cor.withValues(alpha: 0.6), cor.withValues(alpha: 0)]))),
                // louros dos dois lados
                Positioned(left: c.maxWidth / 2 - e * 0.78, top: c.maxHeight / 2 - e * 0.38, height: e * 0.92, child: Image.asset('assets/home/louro.webp')),
                Positioned(
                  right: c.maxWidth / 2 - e * 0.78,
                  top: c.maxHeight / 2 - e * 0.38,
                  height: e * 0.92,
                  child: Transform.flip(flipX: true, child: Image.asset('assets/home/louro.webp')),
                ),
                Flutua(altura: 3, child: Escudo.de(dv, tamanho: e)),
              ]);
            }),
          ),
          SizedBox(
            height: 30,
            width: double.infinity,
            child: CustomPaint(
              painter: _Faixa(),
              child: Center(
                child: FittedBox(
                  child: Text('${dv['nome'] ?? 'Bronze'}',
                      style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Color(0xFFFFF1C9), shadows: [Shadow(color: Color(0xFF5A2A00), offset: Offset(0, 2), blurRadius: 1)])),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          FittedBox(
            child: Row(children: [
              Image.asset('assets/home/ic_trofeu.webp', width: 24),
              const SizedBox(width: 5),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: ((_comp['t'] as num?) ?? 0).toDouble()),
                duration: const Duration(milliseconds: 900),
                builder: (ctx, v, _) => Text('${v.round()} troféus', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
              ),
            ]),
          ),
          const SizedBox(height: 6),
          _barra(((dv['pct'] as num?) ?? 0).toDouble()),
          const SizedBox(height: 4),
          FittedBox(child: Text(prox == null ? 'Divisão máxima!' : 'Faltam ${dv['falta'] ?? '—'} para ${prox['nome']}', style: const TextStyle(fontSize: 12, color: _texto2))),
        ]),
      ),
    );
  }

  Widget _mercado() {
    final ibov = _hoje.where((x) => x['rotulo'] == 'Ibovespa').firstOrNull;
    final v = ibov?['var'];
    final alta = v is! num || v >= 0;
    final cor = v is! num ? _texto2 : (alta ? _verde : _vermelho);   // sem cotação ainda: não afirma direção nenhuma
    return Pressionavel(
      aoTocar: () => _abrir(MercadoTela(api: widget.api)),
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: _painel(borda: alta ? const Color(0xFF2FB874) : const Color(0xFFD8475A), cores: alta ? const [Color(0xFF0D3B44), Color(0xFF082A30)] : const [Color(0xFF451421), Color(0xFF2A0A14)]),
        child: Stack(fit: StackFit.expand, children: [
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            top: 62,
            child: ColorFiltered(
              colorFilter: alta ? const ColorFilter.mode(Colors.transparent, BlendMode.dst) : const ColorFilter.matrix([1.1, 0, 0, 0, 0, 0, 0.45, 0, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0, 1, 0]),
              child: Image.asset('assets/home/touro_mercado.webp', fit: BoxFit.cover, alignment: Alignment.bottomRight),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(9, 6, 8, 6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              FittedBox(child: Text(v is! num ? 'Mercado' : (alta ? 'Mercado em Alta' : 'Mercado em Baixa'), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: Colors.white))),
              FittedBox(
                child: Row(children: [
                  Icon(v is! num ? Icons.show_chart_rounded : (alta ? Icons.trending_up_rounded : Icons.trending_down_rounded), color: cor, size: 30),
                  const SizedBox(width: 4),
                  Text(v is num ? '${alta ? '+' : ''}${v.toStringAsFixed(2).replaceAll('.', ',')}%' : '—',
                      style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: cor, shadows: const [Shadow(color: Colors.black, offset: Offset(0, 2), blurRadius: 3)])),
                ]),
              ),
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
        padding: const EdgeInsets.fromLTRB(8, 6, 6, 6),
        decoration: _painel(),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const FittedBox(child: Text('Sua Melhor Pontuação', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white))),
          Expanded(
            child: Row(children: [
              Image.asset('assets/home/ic_trofeu_grande.webp', height: 40),
              const SizedBox(width: 4),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                  FittedBox(
                    child: Text(n is num ? n.toStringAsFixed(1).replaceAll('.', ',') : '—',
                        style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: _ouro, shadows: [Shadow(color: Color(0xFF5A2A00), offset: Offset(0, 2))])),
                  ),
                  const FittedBox(child: Text('no Desafio do Dia', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Colors.white))),
                ]),
              ),
              Align(alignment: Alignment.bottomRight, child: Image.asset('assets/home/ic_barras.webp', height: 22)),
            ]),
          ),
        ]),
      ),
    );
  }

  /// Barra dourada grossa até a próxima divisão (sempre mostra um pedacinho, como na arte).
  Widget _barra(double v) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: math.max(0.1, v.clamp(0.0, 1.0))),
        duration: const Duration(milliseconds: 1100),
        curve: Curves.easeOutCubic,
        builder: (ctx, x, _) => Container(
          height: 14,
          padding: const EdgeInsets.all(2),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xFF07112E), border: Border.all(color: const Color(0xFF2B4F9E))),
          child: Align(
            alignment: Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: x,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(999),
                  gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE27A), Color(0xFFF5A623), Color(0xFFD9861A)]),
                ),
              ),
            ),
          ),
        ),
      );

  /// Home ainda chegando: os mesmos blocos em cinza, no lugar de um giro no vazio.
  Widget _esqueleto() => const Column(children: [
        Esqueleto(altura: 58, raio: 18),
        SizedBox(height: 8),
        Expanded(child: Esqueleto(raio: 18)),
        SizedBox(height: 8),
        Row(children: [
          Expanded(child: Esqueleto(altura: 74, raio: 18)),
          SizedBox(width: 8),
          Expanded(child: Esqueleto(altura: 74, raio: 18)),
        ]),
        SizedBox(height: 8),
        Esqueleto(altura: 96, raio: 18),
        SizedBox(height: 8),
        Esqueleto(altura: 40, raio: 18),
      ]);

  Widget _erroTela() => Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
          TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
        ]),
      );
}

/// Faixa dourada da divisão: pontas recortadas (hexágono alongado), degradê de cobre e brilhos nos cantos.
class _Faixa extends CustomPainter {
  @override
  void paint(Canvas canvas, Size s) {
    final p = s.height * 0.5;
    final caminho = Path()
      ..moveTo(0, s.height / 2)
      ..lineTo(p, 0)
      ..lineTo(s.width - p, 0)
      ..lineTo(s.width, s.height / 2)
      ..lineTo(s.width - p, s.height)
      ..lineTo(p, s.height)
      ..close();
    final r = Offset.zero & s;
    canvas.drawShadow(caminho, Colors.black, 3, false);
    canvas.drawPath(
        caminho, Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFF2A54A), Color(0xFFC26A1E), Color(0xFF9A4F12)]).createShader(r));
    canvas.drawPath(
        caminho,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = const Color(0xFFFFD27A));
    final brilho = Paint()..color = const Color(0xFFFFF1C9);
    for (final x in [p + 6, s.width - p - 6]) {
      canvas.drawCircle(Offset(x, s.height / 2), 1.6, brilho);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Faixa de convite no pé da tela, com o urso do celular: alterna sozinha entre jogar Trade Battle, Ticker Battle e duelar com um amigo.
class _Convite extends StatefulWidget {
  const _Convite({required this.abrir, required this.api, required this.pedidos});
  final Future<void> Function(Widget) abrir;
  final Api api;
  final int pedidos;

  @override
  State<_Convite> createState() => _ConviteState();
}

class _ConviteState extends State<_Convite> {
  int _i = 0;
  Timer? _t;

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 6), (_) {
      if (mounted) setState(() => _i = (_i + 1) % 3);
    });
  }

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final (l1, l2, sub, tela) = switch (_i) {
      0 => ('BORA JOGAR', 'TRADE BATTLE?', 'Teste suas estratégias contra outros jogadores!', TradeTela(api: widget.api) as Widget),
      1 => ('BORA JOGAR', 'TICKER BATTLE?', 'Monte seu deck e vença o duelo de indicadores!', TickerTela(api: widget.api) as Widget),
      _ => ('BORA', 'DUELAR?', widget.pedidos > 0 ? 'Você tem ${widget.pedidos} pedido(s) de amizade!' : 'Desafie um amigo e ganhe troféus!', SocialTela(api: widget.api) as Widget),
    };
    return Pressionavel(
      aoTocar: () => widget.abrir(tela),
      child: Container(
        height: 70,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: const LinearGradient(colors: [Color(0xFF6A2FD0), Color(0xFF2A2A8A), Color(0xFF14286A)], stops: [0, 0.4, 1]),
          border: Border.all(color: const Color(0xFF5B7BE0), width: 1.8),
          boxShadow: const [BoxShadow(color: Color(0x99000814), offset: Offset(0, 4), blurRadius: 8)],
        ),
        child: Row(children: [
          Image.asset('assets/home/banner_urso.webp', fit: BoxFit.cover, height: 70, width: 128, alignment: Alignment.centerLeft),
          Expanded(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 400),
              transitionBuilder: (w, a) => FadeTransition(opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0.15, 0), end: Offset.zero).animate(a), child: w)),
              child: Column(
                key: ValueKey(_i),
                crossAxisAlignment: CrossAxisAlignment.center,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  FittedBox(child: _tituloJogo(l1, 18, cores: _branco)),
                  FittedBox(child: _tituloJogo(l2, 18)),
                  const SizedBox(height: 1),
                  FittedBox(child: Text(sub, style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: Colors.white))),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Reflexo(
              raio: 14,
              intervalo: const Duration(milliseconds: 3000),
              child: Container(
                padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(14),
                  gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE27A), Color(0xFFF5A623)]),
                  border: Border.all(color: _ouroEscuro, width: 2),
                  boxShadow: const [BoxShadow(color: _ouroEscuro, offset: Offset(0, 3))],
                ),
                child: const Row(mainAxisSize: MainAxisSize.min, children: [
                  Text('Entrar', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFF4A2800))),
                  Icon(Icons.chevron_right_rounded, color: Color(0xFF4A2800), size: 26),
                ]),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}
