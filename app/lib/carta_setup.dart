import 'dart:math';

import 'package:flutter/material.dart';

import 'cartas.dart' show coresRaridade, rotulosRaridade;

/// Proporção da arte das cartas de setup (altura ÷ largura): 768 x 1176.
const double proporcaoCartaSetup = 1176 / 768;

const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF4D6D);

Color _hex(Object? v, [Color padrao = const Color(0xFF8FB4F0)]) {
  final m = RegExp(r'^#([0-9a-fA-F]{6})$').firstMatch('$v');
  return m == null ? padrao : Color(0xFF000000 | int.parse(m.group(1)!, radix: 16));
}

/// Texto que escolhe sozinho o maior tamanho de letra (entre [max] e [min]) em que cabe na caixa, em até [maxLines] linhas.
class TextoAjustado extends StatelessWidget {
  const TextoAjustado(this.spans, {super.key, required this.max, required this.min, this.maxLines = 2, this.align = TextAlign.center, this.cor = Colors.white, this.peso = FontWeight.w700, this.italico = false});
  final List<InlineSpan> spans;
  final double max, min;
  final int maxLines;
  final TextAlign align;
  final Color cor;
  final FontWeight peso;
  final bool italico;

  /// Quantas vezes o laço de medição rodou de verdade (os testes conferem que reconstruir a mesma carta não mede de novo).
  static int calculos = 0;
  static final Map<String, double> _memoria = {};

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (ctx, c) {
      TextStyle estilo(double f) => TextStyle(fontSize: f, color: cor, fontWeight: peso, fontStyle: italico ? FontStyle.italic : FontStyle.normal, height: 1.12, shadows: const [Shadow(color: Color(0xCC000814), blurRadius: 3)]);
      final chave = '${TextSpan(children: spans).toPlainText()}|${c.maxWidth.round()}|${c.maxHeight.round()}|$max|$min|$maxLines|${align.index}|${peso.index}|${italico ? 1 : 0}|${spans.length}';
      var f = _memoria[chave];
      if (f == null) {
        calculos++;
        f = max;
        while (f! > min) {
          final tp = TextPainter(text: TextSpan(style: estilo(f), children: spans), textDirection: TextDirection.ltr, maxLines: maxLines, textAlign: align)..layout(maxWidth: c.maxWidth);
          if (!tp.didExceedMaxLines && tp.height <= c.maxHeight * 0.94) break;      // folga: a altura medida é um pouco menor que a desenhada
          f -= 0.5;
        }
        if (_memoria.length > 600) _memoria.clear();
        _memoria[chave] = f;
      }
      return Align(
        alignment: align == TextAlign.center ? Alignment.center : Alignment.centerLeft,
        child: Text.rich(TextSpan(style: estilo(f < min ? min : f), children: spans), maxLines: maxLines, overflow: TextOverflow.ellipsis, textAlign: align),
      );
    });
  }
}

/// Uma linha de texto que nunca é cortada: se for maior que a caixa, a letra encolhe.
class TextoUmaLinha extends StatelessWidget {
  const TextoUmaLinha(this.texto, {super.key, required this.tamanho, this.cor = Colors.white, this.peso = FontWeight.w700});
  final String texto;
  final double tamanho;
  final Color cor;
  final FontWeight peso;

  @override
  Widget build(BuildContext context) => FittedBox(
        fit: BoxFit.scaleDown,
        child: Text(texto, maxLines: 1, softWrap: false, style: TextStyle(fontSize: tamanho, color: cor, fontWeight: peso, shadows: const [Shadow(color: Color(0xCC000814), blurRadius: 3)])),
      );
}

/// Uma face da carta de setup: a arte (frente ou verso, na cor da raridade) com os textos do cadastro por cima e, na frente,
/// o desenho do padrão. Tudo é medido na arte de 768 x 1176 e escala com [largura]; em cartas pequenas só ficam o desenho e o nome.
class CartaSetup extends StatelessWidget {
  const CartaSetup({super.key, required this.setup, required this.largura, this.verso = false});
  final Map<String, dynamic> setup;
  final double largura;
  final bool verso;

  String get _rar => coresRaridade.containsKey(setup['raridade']) ? '${setup['raridade']}' : 'comum';
  Map get _c => (setup['carta'] as Map?) ?? const {};
  String _t(String k) => '${_c[k] ?? ''}';

  String get _gatilho {
    final g = _t('gatilho');
    if (g.isNotEmpty) return g;
    final r = '${setup['resumo'] ?? ''}';
    return r.length > 90 ? '${r.substring(0, 87)}…' : r;
  }

  @override
  Widget build(BuildContext context) {
    final k = largura / 768;
    final alt = largura * proporcaoCartaSetup;
    final (_, clara, _) = coresRaridade[_rar]!;
    final dpr = MediaQuery.maybeOf(context)?.devicePixelRatio ?? 2;
    Widget caixa(double x0, double y0, double x1, double y1, Widget f) => Positioned(left: x0 * k, top: y0 * k, width: (x1 - x0) * k, height: (y1 - y0) * k, child: f);
    final detalhado = largura >= 200;
    return SizedBox(
      width: largura,
      height: alt,
      child: Stack(children: [
        Positioned.fill(child: Image.asset('assets/cartas_setup/${verso ? 'verso' : 'frente'}_$_rar.webp', fit: BoxFit.fill, cacheWidth: (largura * dpr).round().clamp(200, 768), filterQuality: FilterQuality.medium)),
        ...(verso ? _verso(k, clara, caixa) : _frente(k, clara, caixa, detalhado)),
      ]),
    );
  }

  List<Widget> _frente(double k, Color clara, Widget Function(double, double, double, double, Widget) caixa, bool detalhado) {
    final dir = '${setup['direcao']}';
    final (dirTxt, dirCor) = switch (dir) { 'venda' => ('▼ Venda', _vermelho), 'ambos' => ('▲▼ Ambos', const Color(0xFFFFD76A)), _ => ('▲ Compra', _verde) };
    final tipo = '${setup['tipo']}' == 'candle' ? 'Candle' : 'Método';
    final alvo = _t('alvo_curto').isEmpty ? 'Alvo' : _t('alvo_curto');
    final cores = (setup['cores'] as Map?) ?? const {};
    Widget rotulo(double cx, String t, Color cor) => caixa(cx - 92, 936, cx + 92, 976, Center(child: TextoUmaLinha(t, tamanho: 32 * k, cor: cor, peso: FontWeight.w900)));
    return [
      caixa(58, 50, 152, 144, Center(child: Icon(Icons.diamond_rounded, size: 66 * k, color: clara))),
      if (detalhado) caixa(205, 62, 500, 138, TextoAjustado([TextSpan(text: 'SETUP · ${rotulosRaridade[_rar]}')], max: 36 * k, min: 12 * k, maxLines: 1, cor: clara, peso: FontWeight.w900)),
      caixa(92, 214, 680, 540, CustomPaint(painter: IlustracaoSetup('${setup['id']}', _hex(cores['principal']), _hex(cores['brilho'], const Color(0xFFFFD76A))))),
      caixa(125, 597, 655, 686, TextoAjustado([TextSpan(text: '${setup['nome']}'.toUpperCase())], max: 56 * k, min: 14 * k, maxLines: 2, peso: FontWeight.w900, italico: true)),
      if (detalhado) ...[
        caixa(125, 716, 650, 752, Center(child: TextoUmaLinha('${setup['subtitulo']}', tamanho: 26 * k, cor: const Color(0xFFD6E6FF)))),
        rotulo(164, tipo, Colors.white),
        rotulo(377, alvo, const Color(0xFFFFD76A)),
        rotulo(606, dirTxt, dirCor),
      ],
    ];
  }

  /// Verso: o nome e o ícone do setup, 3 textos curtos (como funciona, quando ativa, saída sugerida) e o quadro SEU DESEMPENHO com 6 espaços. A arte já traz a moldura,
  /// os títulos e os nomes dos espaços (sem nenhum texto que mude de carta): tudo que muda é escrito aqui. Coordenadas medidas na arte de 768 x 1176.
  List<Widget> _verso(double k, Color clara, Widget Function(double, double, double, double, Widget) caixa) {
    if (largura < 200) return const [];
    final est = (setup['estatisticas'] as Map?) ?? const {};
    final cores = (setup['cores'] as Map?) ?? const {};
    int n(String c) => (est[c] as num?)?.toInt() ?? 0;
    final taxa = est['taxa'] as num?, ret = est['retorno_medio'] as num?, lucro = est['lucro_total'] as num?, melhor = est['melhor_entrada'] as num?;
    String pct(num v) => '${v > 0 ? '+' : v < 0 ? '−' : ''}${v.abs().toStringAsFixed(1).replaceAll('.', ',')}%';
    String tc(num v) {
      final inteiro = v.abs().toStringAsFixed(2).split('.');
      final milhares = inteiro[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => '.');
      return '${v > 0.004 ? '+' : v < -0.004 ? '−' : ''}T\$ $milhares,${inteiro[1]}';
    }

    Color corDe(num? v) => v == null ? Colors.white : (v > 0 ? _verde : (v < 0 ? _vermelho : Colors.white));
    Widget valor(double x0, double y0, double x1, double y1, String t, Color cor) => caixa(x0, y0, x1, y1, Center(child: TextoUmaLinha(t, tamanho: 34 * k, cor: cor, peso: FontWeight.w900)));
    final tipoCandle = '${setup['tipo']}' == 'candle';
    final quando = '${tipoCandle ? 'Ao fechar o candle do padrão' : 'Ao fechar o candle'} · Região: ${_t('regiao')}';
    final alvo = _t('alvo_curto').isEmpty ? _t('alvo') : _t('alvo_curto');
    final saida = 'Stop: ${_t('stop')} | $alvo';
    return [
      caixa(74, 43, 196, 166, CustomPaint(painter: IlustracaoSetup('${setup['id']}', _hex(cores['principal']), _hex(cores['brilho'], const Color(0xFFFFD76A))))),
      caixa(244, 55, 596, 108, TextoAjustado([TextSpan(text: '${setup['nome']}'.toUpperCase())], max: 40 * k, min: 14 * k, maxLines: 1, align: TextAlign.left, peso: FontWeight.w900)),
      caixa(172, 243, 619, 305, TextoAjustado([TextSpan(text: _gatilho)], max: 24 * k, min: 10 * k, maxLines: 2, align: TextAlign.left)),
      caixa(172, 360, 497, 397, TextoAjustado([TextSpan(text: quando)], max: 24 * k, min: 10 * k, maxLines: 2, align: TextAlign.left)),
      caixa(172, 453, 619, 499, TextoAjustado([TextSpan(text: saida)], max: 24 * k, min: 10 * k, maxLines: 2, align: TextAlign.left)),
      valor(83, 653, 374, 705, '${n('ativacoes')}', Colors.white),
      valor(411, 653, 704, 705, '${n('entradas')}', Colors.white),
      valor(83, 791, 374, 853, taxa == null ? '—' : '${taxa.toInt()}%', taxa == null ? Colors.white : (taxa >= 50 ? _verde : _vermelho)),
      valor(411, 791, 704, 853, lucro == null ? '—' : tc(lucro), corDe(lucro)),
      valor(83, 927, 374, 991, ret == null ? '—' : pct(ret), corDe(ret)),
      valor(411, 927, 704, 991, melhor == null ? '—' : tc(melhor), corDe(melhor)),
    ];
  }
}

/// Carta que vira ao toque: da frente para o verso e de volta, com a rotação em 3D.
class CartaGirando extends StatefulWidget {
  const CartaGirando({super.key, required this.setup, required this.largura});
  final Map<String, dynamic> setup;
  final double largura;

  @override
  State<CartaGirando> createState() => _CartaGirandoState();
}

class _CartaGirandoState extends State<CartaGirando> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 520));
  bool _verso = false;
  // As faces não mudam durante a virada: ficam prontas e só a rotação é refeita a cada quadro (antes, cada quadro remontava a carta toda).
  late Widget _frente = CartaSetup(setup: widget.setup, largura: widget.largura);
  late Widget _versoW = Transform(alignment: Alignment.center, transform: Matrix4.identity()..rotateY(pi), child: CartaSetup(setup: widget.setup, largura: widget.largura, verso: true));

  @override
  void didUpdateWidget(CartaGirando o) {
    super.didUpdateWidget(o);
    if (o.setup != widget.setup || o.largura != widget.largura) {
      _frente = CartaSetup(setup: widget.setup, largura: widget.largura);
      _versoW = Transform(alignment: Alignment.center, transform: Matrix4.identity()..rotateY(pi), child: CartaSetup(setup: widget.setup, largura: widget.largura, verso: true));
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  void _virar() {
    _verso = !_verso;
    _verso ? _c.forward() : _c.reverse();
  }

  @override
  Widget build(BuildContext context) {
    return Column(mainAxisSize: MainAxisSize.min, children: [
      GestureDetector(
        behavior: HitTestBehavior.opaque,      // a arte e o desenho não recebem toques sozinhos: sem isto, tocar no meio da carta não virava
        onTap: _virar,
        child: RepaintBoundary(
          child: AnimatedBuilder(
            animation: _c,
            builder: (ctx, _) {
              final ang = Curves.easeInOut.transform(_c.value) * pi;
              return Transform(
                alignment: Alignment.center,
                transform: Matrix4.identity()
                  ..setEntry(3, 2, 0.0012)
                  ..rotateY(ang),
                child: ang > pi / 2 ? _versoW : _frente,
              );
            },
          ),
        ),
      ),
      const SizedBox(height: 6),
      const Text('Toque na carta para virar', style: TextStyle(color: Color(0x99FFFFFF), fontSize: 12)),
    ]);
  }
}

/// Desenho do padrão na janela da carta: velas, linhas e rótulos de cada setup, feitos em código (nada de arte por setup).
class IlustracaoSetup extends CustomPainter {
  IlustracaoSetup(this.id, this.cor, this.brilho);
  final String id;
  final Color cor, brilho;

  // vela = (abertura, máxima, mínima, fechamento) numa escala de 0 a 100
  static const _v = <String, List<List<double>>>{
    'engolfo_alta': [[72, 74, 64, 66], [66, 68, 57, 59], [59, 61, 49, 51], [51, 53, 43, 45], [46, 48, 36, 38], [40, 41, 34, 35], [33, 56, 31, 54], [54, 66, 52, 63], [63, 74, 61, 72]],
    'estrela_cadente': [[28, 36, 26, 34], [34, 44, 32, 42], [42, 52, 40, 50], [50, 60, 48, 58], [58, 68, 56, 66], [66, 76, 64, 74], [76, 98, 74, 75], [74, 76, 62, 64], [64, 66, 50, 52]],
    'martelo': [[78, 80, 70, 72], [72, 74, 63, 65], [65, 67, 56, 58], [58, 60, 49, 51], [51, 53, 42, 44], [44, 46, 36, 38], [38, 41, 14, 40], [41, 53, 39, 51], [51, 62, 49, 60]],
    'larry_williams': [[70, 72, 62, 64], [64, 66, 54, 56], [56, 58, 47, 49], [49, 51, 40, 42], [42, 47, 36, 45], [45, 55, 43, 53], [53, 66, 51, 64], [64, 76, 62, 74], [74, 84, 72, 82]],
    'mark_minervini': [[30, 46, 28, 44], [44, 76, 42, 72], [72, 74, 52, 56], [56, 78, 54, 76], [76, 78, 62, 66], [66, 79, 64, 77], [77, 78, 70, 72], [72, 79, 71, 78], [78, 98, 77, 96]],
    'setup_classico': [[30, 40, 28, 38], [38, 52, 36, 50], [50, 66, 48, 64], [64, 78, 62, 60], [60, 62, 48, 50], [50, 58, 46, 56], [56, 66, 54, 64], [64, 72, 62, 70], [70, 94, 68, 92]],
    'turtle_trading': [[50, 60, 44, 56], [56, 62, 50, 52], [52, 64, 48, 62], [62, 66, 54, 58], [58, 68, 56, 66], [66, 70, 58, 60], [60, 69, 57, 67], [67, 71, 62, 64], [64, 90, 63, 88]],
  };

  @override
  void paint(Canvas c, Size s) {
    final velas = _v[id] ?? _v['engolfo_alta']!;
    final n = velas.length;
    final comVolume = id == 'mark_minervini' || id == 'setup_classico';
    final x0 = s.width * 0.05, larg = s.width * 0.9, topo = s.height * 0.12, alt = s.height * (comVolume ? 0.56 : 0.72);
    final lo = velas.map((v) => v[2]).reduce(min) - 3, hi = velas.map((v) => v[1]).reduce(max) + 3;
    double y(double v) => topo + (hi - v) / (hi - lo) * alt;
    final passo = larg / n, corpo = passo * 0.52;
    final tp = Paint()..color = cor.withValues(alpha: .9);

    void texto(String t, double x, double yy, {Color? c0, double f = 0.085, TextAlign al = TextAlign.left}) {
      final p = TextPainter(text: TextSpan(text: t, style: TextStyle(color: c0 ?? brilho, fontSize: s.height * f, fontWeight: FontWeight.w900, shadows: const [Shadow(color: Color(0xFF000814), blurRadius: 4)])), textDirection: TextDirection.ltr)..layout();
      p.paint(c, Offset(al == TextAlign.right ? x - p.width : x, yy));
    }

    void linha(double v, String rot, {bool tracejada = true, Color? col}) {
      final yy = y(v);
      final p = Paint()
        ..color = (col ?? brilho).withValues(alpha: .9)
        ..strokeWidth = 2.4;
      if (tracejada) {
        for (var x = x0; x < x0 + larg; x += 14) {
          c.drawLine(Offset(x, yy), Offset(min(x + 8, x0 + larg), yy), p);
        }
      } else {
        c.drawLine(Offset(x0, yy), Offset(x0 + larg, yy), p);
      }
      texto(rot, x0 + larg, yy - s.height * 0.11, al: TextAlign.right, c0: col ?? brilho);
    }

    void desenhaVela(int i, {bool destaque = false}) {
      final v = velas[i];
      final alta = v[3] >= v[0];
      final col = alta ? _verde : _vermelho;
      final cx = x0 + passo * (i + .5);
      c.drawLine(Offset(cx, y(v[1])), Offset(cx, y(v[2])), Paint()..color = col..strokeWidth = 3);
      final r = Rect.fromLTRB(cx - corpo / 2, y(max(v[0], v[3])), cx + corpo / 2, max(y(min(v[0], v[3])), y(max(v[0], v[3])) + 3));
      c.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(3)), Paint()..color = col);
      if (destaque) c.drawRRect(RRect.fromRectAndRadius(r.inflate(5), const Radius.circular(5)), Paint()..style = PaintingStyle.stroke..strokeWidth = 2.4..color = brilho);
    }

    void caixaDestaque(int a, int b, {String? rot}) {
      final r = Rect.fromLTRB(x0 + passo * a + 2, topo - 4, x0 + passo * (b + 1) - 2, topo + alt + 4);
      c.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(10)), Paint()..color = brilho.withValues(alpha: .09));
      c.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(10)), Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = brilho.withValues(alpha: .8));
      if (rot != null) texto(rot, r.left + 4, r.bottom + s.height * 0.015, f: 0.075);
    }

    void seta(double xx, double v0, double v1, Color col) {
      final p = Paint()..color = col..strokeWidth = 4..strokeCap = StrokeCap.round;
      final a = Offset(xx, y(v0)), b = Offset(xx, y(v1));
      c.drawLine(a, b, p);
      final dy = v1 > v0 ? 12.0 : -12.0;      // ponta de cima: as asas descem; ponta de baixo: as asas sobem
      c.drawLine(b, Offset(b.dx - 9, b.dy + dy), p);
      c.drawLine(b, Offset(b.dx + 9, b.dy + dy), p);
    }

    // fundo de grade leve
    final g = Paint()..color = Colors.white.withValues(alpha: .05)..strokeWidth = 1;
    for (var i = 1; i < 5; i++) {
      c.drawLine(Offset(x0, topo + alt * i / 5), Offset(x0 + larg, topo + alt * i / 5), g);
    }

    switch (id) {
      case 'engolfo_alta':
        linha(34, 'Suporte');
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        caixaDestaque(5, 6, rot: 'Engolfo');
        seta(x0 + passo * 8.4, 64, 80, _verde);
      case 'estrela_cadente':
        linha(97, 'Resistência');
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        caixaDestaque(6, 6, rot: 'Estrela');
        seta(x0 + passo * 8.4, 66, 48, _vermelho);
      case 'martelo':
        linha(16, 'Suporte');
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        caixaDestaque(6, 6, rot: 'Martelo');
        seta(x0 + passo * 8.4, 52, 68, _verde);
      case 'larry_williams':
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        final m = Path();
        const med = [66, 60, 54, 48, 45, 47, 53, 62, 72];
        for (var i = 0; i < n; i++) {
          final p = Offset(x0 + passo * (i + .5), y(med[i].toDouble()));
          i == 0 ? m.moveTo(p.dx, p.dy) : m.lineTo(p.dx, p.dy);
        }
        c.drawPath(m, Paint()..style = PaintingStyle.stroke..strokeWidth = 4..color = brilho);
        texto('MME 9', x0, topo - s.height * 0.06, f: 0.075);
        desenhaVela(5, destaque: true);
        final gy = y(velas[5][1]);
        for (var x = x0 + passo * 5.5; x < x0 + larg; x += 14) {
          c.drawLine(Offset(x, gy), Offset(x + 8, gy), Paint()..color = brilho..strokeWidth = 2.4);
        }
        texto('Gatilho', x0 + larg, gy - s.height * 0.11, al: TextAlign.right);
      case 'mark_minervini':
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        linha(80, 'Pivô');
        // volume secando e o pico no rompimento
        const vol = [34, 40, 30, 28, 20, 16, 12, 10, 44];
        for (var i = 0; i < n; i++) {
          final cx = x0 + passo * (i + .5);
          final h = alt * 0.0035 * vol[i] * 30 / 10;
          c.drawRect(Rect.fromLTRB(cx - corpo / 2, topo + alt + s.height * 0.16 - h, cx + corpo / 2, topo + alt + s.height * 0.16), Paint()..color = (i == n - 1 ? brilho : cor).withValues(alpha: .55));
        }
        texto('Contrações + volume secando', x0, topo + alt + s.height * 0.17, f: 0.07);
      case 'setup_classico':
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        linha(79, 'Pivô de alta');
        const vol = [18, 16, 20, 24, 14, 12, 14, 16, 46];
        for (var i = 0; i < n; i++) {
          final cx = x0 + passo * (i + .5);
          final h = alt * 0.0035 * vol[i] * 30 / 10;
          c.drawRect(Rect.fromLTRB(cx - corpo / 2, topo + alt + s.height * 0.16 - h, cx + corpo / 2, topo + alt + s.height * 0.16), Paint()..color = (i == n - 1 ? brilho : cor).withValues(alpha: .55));
        }
        texto('Volume acima da média', x0, topo + alt + s.height * 0.17, f: 0.07);
      case 'turtle_trading':
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
        final canal = Path();
        const topos = [62, 62, 64, 66, 68, 70, 70, 71, 71];
        for (var i = 0; i < n; i++) {
          final x = x0 + passo * i, xf = x0 + passo * (i + 1);
          i == 0 ? canal.moveTo(x, y(topos[i].toDouble())) : canal.lineTo(x, y(topos[i].toDouble()));
          canal.lineTo(xf, y(topos[i].toDouble()));
        }
        c.drawPath(canal, Paint()..style = PaintingStyle.stroke..strokeWidth = 3.2..color = brilho);
        texto('Canal de máximas', x0, topo - s.height * 0.07, f: 0.07);
        seta(x0 + passo * 8.4, 66, 84, _verde);
      default:
        for (var i = 0; i < n; i++) {
          desenhaVela(i);
        }
    }
    c.drawRect(Rect.fromLTWH(x0, topo + alt + 1, larg, 0), tp);
  }

  @override
  bool shouldRepaint(IlustracaoSetup o) => o.id != id || o.cor != cor || o.brilho != brilho;
}
