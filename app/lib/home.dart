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

/// Tela inicial em formato de "arena", sem rolagem (cabe numa tela):
///   1. faixa do nome: apelido, botão Amigos (com os pedidos) e o Ticker Pass
///   2. letreiro com os indicadores do dia (IBOV, dólar, BTC, medo); toque abre o Cenário
///   3. a liga no centro: o escudo da divisão do jogo escolhido, troféus e a barra até a próxima (toque abre o Ranking)
///      laterais: Cenário, Torneio e Carteira à esquerda; Missões, Deck do Ticker e Mercado à direita
///   4. faixa de evento: o Desafio do dia com a contagem
///   5. JOGAR: o cartão da esquerda troca o jogo (Trade ou Ticker), o botão grande abre o jogo e o Duelo desafia um amigo
/// Dados: `GET /eu` (nome, passe) e `GET /home` (indicadores, missões, cenário, desafio, troféus, torneio e pedidos de amizade).
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);
const _lilas = Color(0xFFD9D4F7);

class _HomeTelaState extends State<HomeTela> {
  Map<String, dynamic>? _eu, _home;
  String? _erro;
  bool _carregando = true;
  String? _jogo; // jogo escolhido no cartão da esquerda do JOGAR (começa no que tem mais troféus)

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
          _jogo ??= '${(_home?['competicao'] as Map?)?['jogo'] ?? 'trade'}';
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

  String get _j => _jogo ?? 'trade';

  /// Abre uma tela e, na volta, relê a Home (missões, troféus e o desafio podem ter mudado).
  Future<void> _abrir(Widget t) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => t));
    if (mounted) _carregar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/home/fundo_home.png', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0, -0.15),
                radius: 0.9,
                colors: [Color(0x885B2BC8), Color(0xCC140A55), Color(0xEE0B0930)],
                stops: [0, 0.55, 1],
              ),
            ),
          ),
          SafeArea(
            child: LayoutBuilder(builder: (ctx, c) {
              // Cabe numa tela; em telas muito baixas a arena fica com altura mínima e a página rola.
              const fixo = 62 + 30 + 72 + 92 + 4 * 8 + 16.0;
              final alt = math.max(c.maxHeight, fixo + 300);
              return RefreshIndicator(
                onRefresh: _carregar,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(maxWidth: 640, minHeight: alt, maxHeight: alt),
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                        child: _carregando && _eu == null
                            ? const Center(child: CircularProgressIndicator())
                            : _erro != null && _eu == null
                                ? _erroTela()
                                : Column(children: [
                                    Entrada(ordem: 0, child: _faixaNome()),
                                    const SizedBox(height: 8),
                                    Entrada(ordem: 0, child: _letreiro()),
                                    const SizedBox(height: 8),
                                    Expanded(child: _arena()),
                                    const SizedBox(height: 8),
                                    Entrada(ordem: 2, child: _evento()),
                                    const SizedBox(height: 8),
                                    Entrada(ordem: 3, child: _batalha()),
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

  // ---- 1. faixa do nome: apelido, Amigos e Ticker Pass
  Widget _faixaNome() {
    final p = (_eu?['passe'] as Map?) ?? const {};
    final total = (p['total'] as num?)?.toInt() ?? 0, feitos = (p['feitos'] as num?)?.toInt() ?? 0;
    final pct = total == 0 ? 0.0 : (p['completo'] == true ? 1.0 : ((feitos + ((p['pct'] as num?) ?? 0).toDouble()) / total).clamp(0.0, 1.0));
    final pedidos = ((_home?['amigos'] as Map?)?['pedidos'] as num?)?.toInt() ?? 0;
    final dv = ((((_home?['competicao'] as Map?)?['jogos'] as Map?)?[_j] as Map?)?['divisao'] as Map?) ?? const {};
    return SizedBox(
      height: 62,
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
            Text(_nome,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Colors.black87, offset: Offset(0, 2), blurRadius: 3)])),
            Text('Divisão ${dv['nome'] ?? 'Bronze'} · ${_j == 'ticker' ? 'Ticker Battle' : 'Trade Battle'}',
                maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: Color.lerp(Escudo.corDe(dv['cor']), Colors.white, 0.4))),
          ]),
        ),
        _bolha(
          icone: Icons.people_alt_rounded,
          cores: const [Color(0xFF6FD3FF), Color(0xFF2A6BE0)],
          rotulo: 'Amigos',
          aviso: pedidos > 0 ? '$pedidos' : null,
          tamanho: 48,
          aoTocar: () => _abrir(SocialTela(api: widget.api)),
        ),
        const SizedBox(width: 8),
        Pressionavel(
          aoTocar: () => abrirAba(2),
          child: Container(
            width: 132,
            padding: const EdgeInsets.fromLTRB(9, 6, 9, 6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFD66B), Color(0xFFE09A1E)]),
              border: Border.all(color: const Color(0xFF8A4E00), width: 2),
              boxShadow: const [BoxShadow(color: Color(0x88F2B84B), blurRadius: 12)],
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
              const FittedBox(child: Text('TICKER PASS', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 0.5, color: Color(0xFF3B2600)))),
              const SizedBox(height: 3),
              Row(children: [
                const Icon(Icons.workspace_premium_rounded, color: Color(0xFF5A2E00), size: 16),
                const SizedBox(width: 3),
                Text(total == 0 ? '—' : '$feitos/$total', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w900, color: Color(0xFF3B2600))),
                const SizedBox(width: 5),
                Expanded(child: _barra(pct, const [Color(0xFF7C3AED), Color(0xFFB06BFF)], fundo: const Color(0x553B2600), altura: 7)),
              ]),
            ]),
          ),
        ),
      ]),
    );
  }

  // ---- 2. letreiro com os indicadores do dia
  static const _curto = {'Ibovespa': 'IBOV', 'Dólar': 'DÓLAR', 'Bitcoin': 'BTC', 'Índice do medo': 'MEDO'};

  Widget _letreiro() {
    final itens = ((_home?['hoje'] as List?) ?? const []).cast<Map>();
    final partes = <Widget>[
      for (final it in itens)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Builder(builder: (_) {
            final v = it['var'];
            final cor = v is num ? (v >= 0 ? _verde : _vermelho) : _ouro;
            return Row(mainAxisSize: MainAxisSize.min, children: [
              Text('${_curto['${it['rotulo']}'] ?? it['rotulo']} ', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: _lilas)),
              Text('${it['valor']} ', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white)),
              Text(v is num ? '${v >= 0 ? '▲' : '▼'} ${v.abs().toStringAsFixed(2).replaceAll('.', ',')}%' : '${it['nota'] ?? ''}',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: cor)),
            ]);
          }),
        ),
    ];
    return Pressionavel(
      aoTocar: () => _abrir(CenarioTela(api: widget.api)),
      child: Container(
        height: 30,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(999),
          color: const Color(0xCC0B0930),
          border: Border.all(color: const Color(0xFF26E0FF), width: 1.2),
          boxShadow: const [BoxShadow(color: Color(0x4426E0FF), blurRadius: 10)],
        ),
        child: partes.isEmpty ? const Center(child: Text('Cotações do dia voltam assim que a fonte responder', style: TextStyle(fontSize: 11.5, color: _lilas))) : _Letreiro(children: partes),
      ),
    );
  }

  // ---- 3. arena: a liga no centro e os atalhos nas laterais
  Widget _arena() {
    final comp = (_home?['competicao'] as Map?) ?? const {};
    final g = ((comp['jogos'] as Map?)?[_j] as Map?) ?? (comp['jogo'] == _j ? comp : const {});
    final dv = (g['divisao'] as Map?) ?? const {};
    final cor = Escudo.corDe(dv['cor']);
    final prox = dv['prox'] as Map?;
    final m = (_home?['missoes'] as Map?) ?? const {};
    final faltam = math.max(0, ((m['total'] as num?)?.toInt() ?? 0) - ((m['feitas'] as num?)?.toInt() ?? 0));
    final trn = (_home?['torneio'] as Map?) ?? const {};
    final cen = '${((_home?['cenario'] as Map?) ?? const {})['veredito'] ?? ''}';
    final (cenAviso, cenCor) = switch (cen) {
      'BOM' => ('▲', _verde),
      'RUIM' => ('▼', _vermelho),
      'NEUTRO' => ('≈', _ouro),
      _ => (null, _ouro),
    };
    Widget coluna(List<Widget> filhos) => SizedBox(
          width: 74,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 440),
              child: Column(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [for (final (i, f) in filhos.indexed) Entrada(ordem: 1 + i, child: f)]),
            ),
          ),
        );
    return LayoutBuilder(builder: (ctx, c) {
      final escudo = math.min(c.maxWidth - 2 * 74 - 16, c.maxHeight - 100).clamp(90.0, 270.0);
      return Row(children: [
        coluna([
          _bolha(
              icone: Icons.public_rounded,
              cores: const [Color(0xFF4FE0F0), Color(0xFF0E6E8A)],
              rotulo: 'Cenário',
              aviso: cenAviso,
              corAviso: cenCor,
              aoTocar: () => _abrir(CenarioTela(api: widget.api))),
          _bolha(
              icone: Icons.emoji_events_rounded,
              cores: const [Color(0xFFFF8A5B), Color(0xFFC0306B)],
              rotulo: 'Torneio',
              aviso: trn['aberto'] == true ? (trn['inscrito'] == true ? '✓' : '!') : null,
              corAviso: trn['inscrito'] == true ? _verde : _vermelho,
              pulsar: trn['aberto'] == true && trn['inscrito'] != true,
              aoTocar: () => _abrir(RankingTela(api: widget.api, unico: 'torneio'))),
          _bolha(icone: Icons.account_balance_wallet_rounded, cores: const [Color(0xFF6BFF8A), Color(0xFF128A4C)], rotulo: 'Carteira', aoTocar: () => _abrir(CarteiraTela(api: widget.api))),
        ]),
        Expanded(
          child: Pressionavel(
            aoTocar: () {
              rankingPedido.value = _j;
              abrirAba(3);
            },
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              SizedBox(
                width: escudo,
                height: escudo,
                child: Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
                  // halo da divisão atrás do escudo (fora do layout, não empurra o resto)
                  OverflowBox(
                    maxWidth: escudo * 1.3,
                    maxHeight: escudo * 1.3,
                    child: Container(
                      width: escudo * 1.3,
                      height: escudo * 1.3,
                      decoration: BoxDecoration(shape: BoxShape.circle, gradient: RadialGradient(colors: [cor.withValues(alpha: 0.55), cor.withValues(alpha: 0)])),
                    ),
                  ),
                  Flutua(altura: 6, child: Escudo.de(dv, tamanho: escudo)),
                ]),
              ),
              Transform.translate(
                offset: const Offset(0, -10),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE08A), Color(0xFFE09A1E)]),
                    border: Border.all(color: const Color(0xFF8A4E00), width: 2),
                    boxShadow: const [BoxShadow(color: Colors.black54, offset: Offset(0, 3), blurRadius: 4)],
                  ),
                  child: Text('${dv['nome'] ?? 'Bronze'}', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Color(0xFF3B2600))),
                ),
              ),
              Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.emoji_events_rounded, color: _ouro, size: 20),
                const SizedBox(width: 4),
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: ((g['t'] as num?) ?? 0).toDouble()),
                  duration: const Duration(milliseconds: 900),
                  builder: (ctx, v, _) => Text('${v.round()} troféus', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                ),
              ]),
              const SizedBox(height: 5),
              SizedBox(width: math.min(200, c.maxWidth - 2 * 74 - 16), child: _barra(((dv['pct'] as num?) ?? 0).toDouble(), [cor, Color.lerp(cor, Colors.white, 0.4)!])),
              const SizedBox(height: 3),
              Text(prox == null ? 'Divisão máxima!' : 'Faltam ${dv['falta'] ?? '—'} para ${prox['nome']}', style: const TextStyle(fontSize: 11.5, color: _lilas)),
            ]),
          ),
        ),
        coluna([
          _bolha(
              icone: Icons.assignment_turned_in_rounded,
              cores: const [Color(0xFFFFE08A), Color(0xFFE0861E)],
              rotulo: 'Missões',
              aviso: faltam > 0 ? '$faltam' : null,
              aoTocar: () => _abrir(MissoesTela(api: widget.api))),
          _bolha(icone: Icons.style_rounded, cores: const [Color(0xFFC08BFF), Color(0xFF6A2BD0)], rotulo: 'Deck', aoTocar: _deck),
          _bolha(icone: Icons.candlestick_chart_rounded, cores: const [Color(0xFF7FB2FF), Color(0xFF2A4BD0)], rotulo: 'Mercado', aoTocar: () => _abrir(MercadoTela(api: widget.api))),
        ]),
      ]);
    });
  }

  /// Atalho para montar o deck do Ticker Battle (a tela do baralho precisa dos dados da central do Ticker).
  Future<void> _deck() async {
    try {
      final d = await widget.api.get('/ticker/central');
      if (!mounted) return;
      await _abrir(BaralhoTela(api: widget.api, central: d));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Não consegui abrir o deck agora. Tente de novo.')));
    }
  }

  /// Botão redondo das laterais: ícone num círculo colorido com borda dourada, o nome embaixo e um aviso no canto.
  Widget _bolha({
    required IconData icone,
    required List<Color> cores,
    required String rotulo,
    required VoidCallback aoTocar,
    String? aviso,
    Color corAviso = _vermelho,
    bool pulsar = false,
    double tamanho = 56,
  }) {
    final circulo = Container(
      width: tamanho,
      height: tamanho,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: cores),
        border: Border.all(color: _ouro, width: 2.5),
        boxShadow: [BoxShadow(color: cores.last.withValues(alpha: 0.6), blurRadius: 12), const BoxShadow(color: Colors.black54, offset: Offset(0, 3), blurRadius: 3)],
      ),
      child: Icon(icone, color: Colors.white, size: tamanho * 0.52, shadows: const [Shadow(color: Colors.black54, offset: Offset(0, 2), blurRadius: 2)]),
    );
    return Semantics(
      button: true,
      label: rotulo,
      child: Pressionavel(
        aoTocar: aoTocar,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Stack(clipBehavior: Clip.none, children: [
            pulsar ? Flutua(altura: 3, periodo: const Duration(milliseconds: 1400), child: circulo) : circulo,
            if (pulsar) Positioned.fill(child: Pulso(cor: corAviso, raio: tamanho / 2)),
            if (aviso != null)
              Positioned(
                right: -4,
                top: -4,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 22),
                  height: 22,
                  padding: const EdgeInsets.symmetric(horizontal: 5),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(color: corAviso, borderRadius: BorderRadius.circular(11), border: Border.all(color: Colors.white, width: 1.5)),
                  child: Text(aviso, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: Colors.white)),
                ),
              ),
          ]),
          if (tamanho >= 56) ...[
            const SizedBox(height: 3),
            Text(rotulo, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Colors.black, offset: Offset(0, 1), blurRadius: 2)])),
          ],
        ]),
      ),
    );
  }

  Widget _barra(double v, List<Color> cores, {Color fundo = const Color(0x40FFFFFF), double altura = 9}) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: v.clamp(0.0, 1.0)),
        duration: const Duration(milliseconds: 1100),
        curve: Curves.easeOutCubic,
        builder: (ctx, x, _) => ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: Stack(children: [
            Container(height: altura, color: fundo),
            FractionallySizedBox(widthFactor: x, child: Container(height: altura, decoration: BoxDecoration(gradient: LinearGradient(colors: cores)))),
          ]),
        ),
      );

  // ---- 4. faixa de evento: Desafio do dia
  Widget _evento() {
    final d = (_home?['desafio'] as Map?) ?? const {};
    final s = (d['termina_em'] as num?)?.toInt() ?? 0;
    final (txt, cor) = d['terminou'] == true
        ? ('Feito! Nota ${d['nota'] is num ? (d['nota'] as num).toStringAsFixed(1).replaceAll('.', ',') : ''}', _verde)
        : d['jogou'] == true
            ? ('Termine sua tentativa!', _ouro)
            : ('Você ainda não jogou hoje', _ouro);
    return Pressionavel(
      aoTocar: () => _abrir(DesafioTela(api: widget.api)),
      child: Container(
        height: 72,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFFF2A50B), width: 2),
          gradient: const LinearGradient(colors: [Color(0xFF5A2BC8), Color(0xFF2A1278)]),
          boxShadow: const [BoxShadow(color: Color(0x77F2A50B), blurRadius: 14)],
        ),
        child: Stack(children: [
          Positioned(left: -4, bottom: -18, child: Image.asset('assets/ranking/urso_aponta.webp', height: 96)),
          Positioned(
            left: 86,
            right: 10,
            top: 6,
            bottom: 6,
            child: Row(children: [
              Expanded(flex: 5, child: Image.asset('assets/ranking/desafio_titulo.webp', fit: BoxFit.contain, alignment: Alignment.centerLeft)),
              const SizedBox(width: 6),
              Expanded(
                flex: 6,
                child: Column(crossAxisAlignment: CrossAxisAlignment.end, mainAxisAlignment: MainAxisAlignment.center, children: [
                  Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                    const Icon(Icons.schedule_rounded, color: _ouro, size: 16),
                    const SizedBox(width: 4),
                    Text(contagem(s), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: _ouro)),
                  ]),
                  FittedBox(child: Text(txt, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: cor))),
                ]),
              ),
            ]),
          ),
        ]),
      ),
    );
  }

  // ---- 5. JOGAR: troca de jogo, botão grande e Duelo
  Widget _batalha() {
    final ticker = _j == 'ticker';
    return SizedBox(
      height: 92,
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Pressionavel(
          aoTocar: () => setState(() => _jogo = ticker ? 'trade' : 'ticker'),
          child: Container(
            width: 84,
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFF6FD3FF), width: 2),
              color: const Color(0xFF1A3A9E),
              boxShadow: const [BoxShadow(color: Colors.black54, offset: Offset(0, 4), blurRadius: 4)],
            ),
            child: Stack(fit: StackFit.expand, children: [
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                transitionBuilder: (w, a) => ScaleTransition(scale: a, child: FadeTransition(opacity: a, child: w)),
                child: Image.asset(ticker ? 'assets/jogos/ticker_hero.webp' : 'assets/jogos/trade_hero.webp',
                    key: ValueKey(_j), fit: BoxFit.cover, alignment: ticker ? const Alignment(-0.55, 0) : Alignment.center),
              ),
              Align(
                alignment: Alignment.bottomCenter,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  color: const Color(0xCC0B0930),
                  child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.swap_horiz_rounded, color: Colors.white, size: 15),
                    SizedBox(width: 2),
                    Text('Trocar', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white)),
                  ]),
                ),
              ),
            ]),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Pressionavel(
            aoTocar: () => _abrir(ticker ? TickerTela(api: widget.api) : TradeTela(api: widget.api)),
            child: Reflexo(
              raio: 18,
              child: Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE27A), Color(0xFFF5A623), Color(0xFFE08A12)]),
                  border: Border.all(color: const Color(0xFF8A4E00), width: 2.5),
                  boxShadow: const [BoxShadow(color: Color(0xFF8A4E00), offset: Offset(0, 5)), BoxShadow(color: Color(0x88F2B84B), blurRadius: 16)],
                ),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Text('JOGAR',
                      style: TextStyle(fontSize: 32, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white, shadows: [
                        Shadow(color: Color(0xFF8A4E00), offset: Offset(0, 3)),
                        Shadow(color: Color(0xFF8A4E00), offset: Offset(0, -1), blurRadius: 2),
                      ])),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    child: Text(ticker ? 'Ticker Battle' : 'Trade Battle', key: ValueKey(_j), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Color(0xFF5A2E00))),
                  ),
                ]),
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Pressionavel(
          aoTocar: () => _abrir(SocialTela(api: widget.api)),
          child: Container(
            width: 84,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFF6B8A), Color(0xFFC0304B)]),
              border: Border.all(color: Colors.white, width: 2),
              boxShadow: const [BoxShadow(color: Colors.black54, offset: Offset(0, 4), blurRadius: 4)],
            ),
            child: const Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text('⚔️', style: TextStyle(fontSize: 34)),
              Text('Duelo', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Colors.black54, offset: Offset(0, 2))])),
              Text('desafie um amigo', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w700, color: Colors.white)),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _erroTela() => Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
          TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
        ]),
      );
}

/// Letreiro que passa da direita para a esquerda sem parar (os itens repetidos lado a lado).
class _Letreiro extends StatefulWidget {
  const _Letreiro({required this.children});
  final List<Widget> children;

  @override
  State<_Letreiro> createState() => _LetreiroState();
}

class _LetreiroState extends State<_Letreiro> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 18))..repeat();
  final _chave = GlobalKey();
  double _largura = 0;

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final w = (_chave.currentContext?.findRenderObject() as RenderBox?)?.size.width ?? 0;
      if (mounted && w != _largura) setState(() => _largura = w);
    });
    final linha = Row(key: _chave, mainAxisSize: MainAxisSize.min, children: widget.children);
    return ClipRect(
      child: OverflowBox(
        alignment: Alignment.centerLeft,
        maxWidth: double.infinity,
        child: AnimatedBuilder(
          animation: _c,
          builder: (ctx, child) => Transform.translate(offset: Offset(-_c.value * _largura, 0), child: child),
          child: Row(mainAxisSize: MainAxisSize.min, children: [linha, Row(mainAxisSize: MainAxisSize.min, children: widget.children), Row(mainAxisSize: MainAxisSize.min, children: widget.children)]),
        ),
      ),
    );
  }
}
