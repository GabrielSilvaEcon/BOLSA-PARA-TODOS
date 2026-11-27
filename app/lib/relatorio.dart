import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'animacoes.dart';
import 'grafico/grafico.dart';
import 'grafico/modelo.dart';

/// Resultado da partida do Trade Battle, feito no próprio app:
///   · o ativo revelado (nome e período), que entra virando;
///   · os pontos subindo até o valor final, com o lucro, a nota da leitura e o XP;
///   · o gráfico REAL: a partida aparece andando depois da linha "início da partida" e os desenhos ganham ✔/✖ um a um;
///   · a lista "Seus desenhos" com a explicação de cada um.
/// O relatório completo (o mesmo do app antigo) continua a um toque.
class RelatorioTela extends StatefulWidget {
  const RelatorioTela({super.key, required this.fim, required this.tela, required this.aoCompleto, required this.acao, required this.rotuloAcao});
  final Map<String, dynamic> fim;
  final Map<String, dynamic> tela;
  final VoidCallback aoCompleto;
  final VoidCallback acao;
  final String rotuloAcao;

  /// Veredito de uma partida contra outro jogador (null no treino solo): compara você com o adversário pelos pontos.
  static (String, String, Color)? versus(List? placar) => _RelatorioTelaState.versus(placar);

  @override
  State<RelatorioTela> createState() => _RelatorioTelaState();
}

class _RelatorioTelaState extends State<RelatorioTela> {
  late final Map<String, dynamic> _res = (widget.fim['resultado'] as Map?)?.cast<String, dynamic>() ?? const {};
  late final Map<String, dynamic> _lt = (_res['leitura'] as Map?)?.cast<String, dynamic>() ?? const {};

  bool _comemorou = false;

  /// O número grande diz QUANTO; o veredito diz O QUÊ. Sem ele o jogador junta pontos, lucro e nota sozinho para saber como foi.
  static (String, String, Color) _veredito(double pts, double? pnl, double? nota) {
    if (pts > 0 && (pnl ?? 0) > 0 && (nota ?? 0) >= 70) {
      return ('PARTIDA CHEIA!', 'Lucro na operação e leitura confirmada.', const Color(0xFFFFC93C));
    }
    if (pts > 0) return ('VOCÊ PONTUOU!', 'Boa partida. Dá para subir ainda mais.', const Color(0xFF26D07C));
    if (pts == 0) return ('EMPATE TÉCNICO', 'Ficou no zero a zero. A próxima desempata.', const Color(0xFFB9C4FF));
    if ((nota ?? 0) >= 70) return ('LEITURA CERTA', 'Você leu o gráfico bem; faltou a operação acompanhar.', const Color(0xFFB9C4FF));
    return ('ESSA ESCAPOU', 'Faz parte. Veja no gráfico onde o preço virou.', const Color(0xFFFF8FA3));
  }

  /// Partida contra outro jogador: o veredito compara VOCÊ com o adversário (pelos pontos, que é o que decide a classificação).
  /// Sem adversário no placar (treino solo) devolve null e vale o veredito pela própria pontuação.
  static (String, String, Color)? versus(List? placar) {
    final lista = [for (final x in placar ?? const []) if (x is Map) x.cast<String, dynamic>()];
    final eu = lista.where((x) => x['voce'] == true).firstOrNull;
    final outros = lista.where((x) => x['voce'] != true).toList();
    if (eu == null || outros.isEmpty) return null;
    double pt(Map x) => (x['pontos'] as num?)?.toDouble() ?? 0;
    String f(double v) => v.toStringAsFixed(1).replaceAll('.', ',');
    final meu = pt(eu);
    final melhor = outros.reduce((a, b) => pt(a) >= pt(b) ? a : b);
    final rival = pt(melhor), nome = '${melhor['rotulo'] ?? 'o adversário'}';
    if ((meu - rival).abs() < 0.05) return ('EMPATE', 'Vocês fizeram ${f(meu)} pontos cada. A próxima desempata.', const Color(0xFFB9C4FF));
    if (meu > rival) return ('VOCÊ VENCEU!', 'Você fez ${f(meu)} pts contra ${f(rival)} de $nome.', const Color(0xFFFFC93C));
    return ('$nome VENCEU'.toUpperCase(), 'Você fez ${f(meu)} pts contra ${f(rival)}. Faltaram ${f(rival - meu)} pts: a próxima é sua.', const Color(0xFFFF8FA3));
  }

  /// Fim da contagem dos pontos: é o auge da tela, e é onde a vibração marca o resultado.
  void _comemorar(double pts) {
    if (_comemorou) return;
    _comemorou = true;
    if (pts > 0) {
      HapticFeedback.heavyImpact();
    } else if (pts < 0) {
      HapticFeedback.lightImpact();
    }
  }

  String _moeda(num v) {
    final s = v.abs().toStringAsFixed(2).split('.');
    final b = StringBuffer();
    for (var i = 0; i < s[0].length; i++) {
      if (i > 0 && (s[0].length - i) % 3 == 0) b.write('.');
      b.write(s[0][i]);
    }
    return '${v < 0 ? '−' : '+'}T\$ $b,${s[1]}';
  }

  @override
  Widget build(BuildContext context) {
    final rev = (widget.fim['revelado'] as Map?) ?? const {};
    final pts = (_res['pontos'] as num?)?.toDouble() ?? 0;
    final fin = (_res['fin'] as Map?) ?? const {};
    final xp = ((widget.fim['xp'] as Map?)?['xp'] as num?)?.toInt();
    final nota = (_lt['nota'] as num?)?.toDouble();
    return Scaffold(
      backgroundColor: const Color(0xFF081528),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
          const ColoredBox(color: Color(0xB3021026)),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(12, 6, 12, 20),
              children: [
                _topo(),
                const SizedBox(height: 6),
                Entrada(ordem: 0, child: _revelado(rev)),
                const SizedBox(height: 10),
                Entrada(ordem: 1, child: _placar(pts, fin, nota, xp)),
                const SizedBox(height: 10),
                Entrada(ordem: 2, child: AnaliseDesenhos(fim: widget.fim, tela: widget.tela)),
                const SizedBox(height: 14),
                // O relatório completo vem antes: quem sai desta tela sai pelo botão de jogar, que fica por último.
                Pressionavel(
                  aoTocar: widget.aoCompleto,
                  child: Container(
                    height: 44,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: const Color(0x996CA3FF), width: 1.5),
                    ),
                    child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Icon(Icons.bar_chart_rounded, color: Color(0xFFC8D6EE), size: 20),
                      SizedBox(width: 8),
                      Text('Relatório completo', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFFC8D6EE))),
                    ]),
                  ),
                ),
                const SizedBox(height: 12),
                Reflexo(
                  raio: 999,
                  atraso: const Duration(milliseconds: 2500),
                  child: Pressionavel(
                    aoTocar: widget.acao,
                    child: Container(
                      height: 56,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(999),
                        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF6BFF8A), Color(0xFF1FCB5A)]),
                        boxShadow: const [BoxShadow(color: Color(0xFF0F8F51), offset: Offset(0, 4)), BoxShadow(color: Color(0x8834E85E), blurRadius: 18)],
                      ),
                      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        const Icon(Icons.replay_rounded, color: Color(0xFF06361F), size: 26),
                        const SizedBox(width: 8),
                        Text(widget.rotuloAcao, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Color(0xFF06361F))),
                      ]),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Topo: logo e "Resultado da partida" com o troféu; à direita o touro comemorando, flutuando (bordas esmaecidas).
  Widget _topo() {
    Widget esmaece(Widget f, {double raio = 0.7, double ini = 0.62}) => ShaderMask(
          shaderCallback: (r) => RadialGradient(radius: raio, colors: const [Color(0xFF000000), Color(0x00000000)], stops: [ini, 1]).createShader(r),
          blendMode: BlendMode.dstIn,
          child: f,
        );
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              esmaece(Image.asset('assets/logo_th.webp', height: 60), raio: 0.85, ini: 0.78),
              const SizedBox(height: 4),
              Row(children: [
                esmaece(Image.asset('assets/jogos/trofeu.webp', height: 46), raio: 0.62, ini: 0.58),
                const SizedBox(width: 6),
                const Flexible(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text('Resultado da partida',
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 8)])),
                  ),
                ),
              ]),
            ],
          ),
        ),
        SizedBox(
          width: 118,
          height: 128,
          child: Stack(clipBehavior: Clip.none, children: [
            Positioned.fill(child: Flutua(altura: 5, child: esmaece(Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.contain), raio: 0.72, ini: 0.6))),
            Positioned(
              right: -12,
              top: -10,
              child: IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.close_rounded, color: Colors.white), tooltip: 'Fechar'),
            ),
          ]),
        ),
      ],
    );
  }

  Widget _revelado(Map rev) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeOutBack,
      builder: (ctx, v, f) => Transform(
        alignment: Alignment.center,
        transform: Matrix4.identity()
          ..setEntry(3, 2, 0.002)
          ..rotateX((1 - v) * 1.4),
        child: f,
      ),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFF2B84B), width: 2),
          gradient: const LinearGradient(colors: [Color(0xFF1E4786), Color(0xFF0E264A)]),
          boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
        ),
        child: Row(children: [
          const Icon(Icons.lock_open_rounded, color: Color(0xFFFFD66B), size: 30),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('O ativo era', style: TextStyle(fontSize: 12, color: Color(0xFFC8D6EE))),
              Text('${rev['ticker'] ?? '—'}', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B))),
              Text('${rev['nome'] ?? ''} · ${rev['de'] ?? ''} a ${rev['ate'] ?? ''} · ${rev['tf_nome'] ?? ''}',
                  style: const TextStyle(fontSize: 12, color: Color(0xFFC8D6EE))),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _placar(double pts, Map fin, double? nota, int? xp) {
    final cor = pts > 0 ? const Color(0xFF26D07C) : (pts < 0 ? const Color(0xFFFF4D6D) : Colors.white);
    final pnl = (fin['pnl'] as num?)?.toDouble();
    final pct = (fin['pct_aposta'] as num?)?.toDouble();
    Widget chip(IconData ic, String t, String v, Color c, {String? nota}) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0xFF143362), border: Border.all(color: c.withValues(alpha: 0.6))),
            child: Column(children: [
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(ic, size: 16, color: c),
                const SizedBox(width: 4),
                Text(t, style: const TextStyle(fontSize: 11.5, color: Color(0xFFD6E6FF), fontWeight: FontWeight.w700)),
              ]),
              const SizedBox(height: 2),
              FittedBox(child: Text(v, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: c))),
              if (nota != null) Text(nota, style: const TextStyle(fontSize: 10, color: Color(0xFFB5C8E6))),
            ]),
          ),
        );
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), color: const Color(0xCC0B2C5E), border: Border.all(color: cor.withValues(alpha: 0.7), width: 2)),
      child: Column(children: [
        _vereditoFaixa(pts, pnl, nota),
        const SizedBox(height: 8),
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: pts),
          duration: const Duration(milliseconds: 1600),
          curve: Curves.easeOutCubic,
          onEnd: () => _comemorar(pts),
          builder: (ctx, v, _) => Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(pts >= 0 ? Icons.trending_up_rounded : Icons.trending_down_rounded, color: cor, size: 40),
            const SizedBox(width: 8),
            Flexible(
              child: FittedBox(
                child: Text('${v > 0 ? '+' : ''}${v.toStringAsFixed(1).replaceAll('.', ',')} pts',
                    style: TextStyle(fontSize: 38, fontWeight: FontWeight.w900, color: cor, shadows: [Shadow(color: cor.withValues(alpha: 0.6), blurRadius: 16)])),
              ),
            ),
          ]),
        ),
        const Text('70% operação · 30% leitura', style: TextStyle(fontSize: 11.5, color: Color(0xFFB5C8E6))),
        const SizedBox(height: 10),
        Row(children: [
          chip(Icons.bar_chart_rounded, 'Lucro', pnl == null ? '—' : '${_moeda(pnl)}${pct == null ? '' : ' (${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(2).replaceAll('.', ',')}%)'}',
              (pnl ?? 0) >= 0 ? const Color(0xFF26D07C) : const Color(0xFFFF4D6D)),
          const SizedBox(width: 6),
          chip(Icons.track_changes_rounded, 'Desenhos', nota == null ? '—' : '${nota.toStringAsFixed(0)}/100', const Color(0xFF9BBFFF)),
          const SizedBox(width: 6),
          chip(Icons.star_rounded, 'XP', xp == null ? '—' : '+$xp', const Color(0xFFFFD66B), nota: xp == 0 ? 'limite do dia' : null),
        ]),
      ]),
    );
  }

  /// Veredito: entra crescendo, logo acima dos pontos, no mesmo estilo da tela de troféus.
  Widget _vereditoFaixa(double pts, double? pnl, double? nota) {
    final (titulo, sub, cor) = versus(widget.fim['placar'] as List?) ?? _veredito(pts, pnl, nota);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.7, end: 1),
      duration: const Duration(milliseconds: 700),
      curve: Curves.easeOutBack,
      builder: (ctx, s, f) => Transform.scale(scale: s, child: f),
      child: Column(children: [
        ShaderMask(
          shaderCallback: (r) =>
              LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color.lerp(cor, Colors.white, 0.55)!, cor]).createShader(r),
          child: Text(titulo,
              textAlign: TextAlign.center,
              style: const TextStyle(
                  fontSize: 25, fontWeight: FontWeight.w900, letterSpacing: 0.6, color: Colors.white, shadows: [Shadow(color: Color(0xCC000814), blurRadius: 10)])),
        ),
        const SizedBox(height: 2),
        Text(sub, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12.5, color: Color(0xFFC8D6EE), height: 1.25)),
      ]),
    );
  }
}

/// Gráfico REAL da partida (andando depois da linha "início", com os desenhos ganhando ✔/✖ um a um) e a lista "Seus desenhos".
/// Usada no relatório do treino solo e na última página do carrossel do resultado do duelo.
class AnaliseDesenhos extends StatefulWidget {
  const AnaliseDesenhos({super.key, required this.fim, required this.tela});
  final Map<String, dynamic> fim;
  final Map<String, dynamic> tela;

  @override
  State<AnaliseDesenhos> createState() => _AnaliseDesenhosState();
}

class _AnaliseDesenhosState extends State<AnaliseDesenhos> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 3600))..forward();
  late final List<Vela> _velas = [for (final c in (widget.tela['candles'] as List? ?? const [])) if (c is Map) Vela.de(c)];
  late final int _divisor = (_velas.length - ((widget.tela['revelados'] as num?)?.toInt() ?? 0)).clamp(0, _velas.length);
  late final Map<String, dynamic> _res = (widget.fim['resultado'] as Map?)?.cast<String, dynamic>() ?? const {};
  late final Map<String, dynamic> _lt = (_res['leitura'] as Map?)?.cast<String, dynamic>() ?? const {};
  late final List<Map> _itens = ((_lt['itens'] as List?) ?? const []).cast<Map>();
  late final List<Desenho> _desenhos = [for (final x in _itens) if (_desenho(x) case final d?) d];
  late final List<bool?> _ok = [for (final x in _itens) if (_desenho(x) != null) x['ok'] as bool?];

  static const _papel = {'suporte': Ferramenta.suporte, 'resistencia': Ferramenta.resistencia, 'rompimento': Ferramenta.rompimento, 'alvo': Ferramenta.alvo};

  Desenho? _desenho(Map x) {
    double n(Object? v) => (v as num).toDouble();
    switch (x['tipo']) {
      case 'nivel':
        final f = _papel[x['papel']];
        return f == null ? null : Desenho.nivel(f, n(x['preco']));
      case 'tendencia':
        return Desenho.dois(Ferramenta.tendencia, (x['i1'] as num).toInt(), n(x['p1']), (x['i2'] as num).toInt(), n(x['p2']));
      case 'zona':
        return Desenho.dois(x['reacao'] == 'alta' ? Ferramenta.zonaAlta : Ferramenta.zonaBaixa, (x['i1'] as num).toInt(), n(x['p1']),
            (x['i2'] as num).toInt(), n(x['p2']));
    }
    return null;
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  List<String>? get _datas => ((widget.fim['revelado'] as Map?)?['datas'] as List?)?.map((e) => '$e').toList();

  void _telaCheia(Map rev) {
    Navigator.of(context).push(MaterialPageRoute(
      fullscreenDialog: true,
      builder: (ctx) => Scaffold(
        backgroundColor: const Color(0xFF081528),
        body: SafeArea(
          child: Stack(children: [
            Positioned.fill(child: Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover)),
            const Positioned.fill(child: ColoredBox(color: Color(0xB3021026))),
            Positioned.fill(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(6, 44, 6, 6),
                child: GraficoNativo(
                  velas: _velas,
                  desenhos: _desenhos,
                  ferramenta: null,
                  somenteLeitura: true,
                  divisor: _divisor,
                  resultados: _ok,
                  datas: _datas,
                  tfNome: '${rev['tf_nome'] ?? ''}',
                  pedirTexto: () async => null,
                  aoMudar: ({bool usouFerramenta = false}) {},
                ),
              ),
            ),
            Positioned(
              left: 12,
              top: 8,
              child: Text('${rev['ticker'] ?? ''} · ${rev['tf_nome'] ?? ''}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
            ),
            Positioned(
              right: 4,
              top: 0,
              child: IconButton(onPressed: () => Navigator.of(ctx).pop(), icon: const Icon(Icons.close_rounded, color: Colors.white), tooltip: 'Fechar'),
            ),
          ]),
        ),
      ),
    ));
  }

  Widget _grafico(Map rev) {
    return Container(
      height: 360,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFF4B82D6), width: 2),
        boxShadow: const [BoxShadow(color: Color(0x664B82D6), blurRadius: 14)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: ColoredBox(
          color: const Color(0x99021026),
          child: _velas.isEmpty
              ? const SizedBox()
              : Column(children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 6, 2, 0),
                    child: Row(children: [
                      const Icon(Icons.candlestick_chart_rounded, color: Color(0xFF9BBFFF), size: 20),
                      const SizedBox(width: 6),
                      const Expanded(child: Text('O gráfico real da partida', style: TextStyle(fontWeight: FontWeight.w800, color: Colors.white))),
                      IconButton(
                        tooltip: 'Tela cheia',
                        visualDensity: VisualDensity.compact,
                        onPressed: () => _telaCheia(rev),
                        icon: const Icon(Icons.fullscreen_rounded, color: Colors.white),
                      ),
                    ]),
                  ),
                  Expanded(
                    child: AnimatedBuilder(
                  animation: _c,
                  builder: (ctx, _) => GraficoNativo(
                    datas: _datas,
                    velas: _velas,
                    desenhos: _desenhos,
                    ferramenta: null,
                    somenteLeitura: true,
                    divisor: _divisor,
                    revelacao: Curves.easeInOut.transform((_c.value / 0.6).clamp(0.0, 1.0)),
                    resultados: _ok,
                    selos: ((_c.value - 0.6) / 0.4).clamp(0.0, 1.0),
                    tfNome: '${rev['tf_nome'] ?? ''}',
                    pedirTexto: () async => null,
                    aoMudar: ({bool usouFerramenta = false}) {},
                  ),
                    ),
                  ),
                ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final rev = (widget.fim['revelado'] as Map?) ?? const {};
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _grafico(rev),
      const SizedBox(height: 12),
      _lista(),
    ]);
  }

  Widget _lista() {
    if (_itens.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xCC143362), border: Border.all(color: const Color(0x665C9AFF))),
        child: const Text('Na próxima partida, desenhe sua leitura na estratégia (suporte, resistência, zona…): cada desenho que se confirmar soma na nota.',
            style: TextStyle(color: Color(0xFFC8D6EE), height: 1.35)),
      );
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        const Icon(Icons.lightbulb_rounded, color: Color(0xFFFFD66B), size: 26),
        const SizedBox(width: 6),
        Expanded(
          child: Text('Seus desenhos · ${_lt['acertos'] ?? 0} de ${_lt['avaliados'] ?? 0} se confirmaram',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        ),
      ]),
      const SizedBox(height: 8),
      for (final (k, x) in _itens.indexed)
        Entrada(
          ordem: 4 + k,
          child: Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: const Color(0xCC143362),
              border: Border.all(color: _cor(x['ok']).withValues(alpha: 0.7)),
            ),
            child: Row(children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(shape: BoxShape.circle, color: _cor(x['ok'])),
                child: Text(x['ok'] == true ? '✔' : (x['ok'] == false ? '✖' : '!'),
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900)),
              ),
              const SizedBox(width: 10),
              Expanded(child: Text('${x['texto'] ?? ''}', style: const TextStyle(fontSize: 13.5, color: Colors.white, height: 1.3))),
            ]),
          ),
        ),
    ]);
  }

  Color _cor(Object? ok) => ok == true ? const Color(0xFF26D07C) : (ok == false ? const Color(0xFFFF4D6D) : const Color(0xFF6CA3FF));
}
