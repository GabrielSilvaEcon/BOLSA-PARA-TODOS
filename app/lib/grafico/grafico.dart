import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'modelo.dart';

/// Gráfico de candles feito no próprio app (Flutter), para a fase da estratégia:
///   · arrastar com um dedo anda no tempo; dois dedos dão zoom (como no app antigo, mas a 60 quadros por segundo);
///   · com uma ferramenta escolhida, tocar no gráfico desenha (níveis com um toque; tendência e zona com dois);
///   · sem ferramenta, dá para arrastar um desenho para ajustar, e segurar o dedo nele apaga;
///   · indicadores: volume e médias de 20, 50 e 200 candles.
/// Os candles entram em cascata ao abrir, e cada desenho novo acende por um instante.
class GraficoNativo extends StatefulWidget {
  const GraficoNativo({
    super.key,
    required this.velas,
    required this.desenhos,
    required this.ferramenta,
    required this.aoMudar,
    required this.pedirTexto,
    this.indicadores = const {'vol', 'mm20'},
    this.tfNome = '',
    this.limite = 12,
    this.aoAviso,
    this.somenteLeitura = false,
    this.divisor,
    this.revelacao = 1,
    this.resultados,
    this.selos = 1,
    this.datas,
  });

  /// Relatório: só olhar (arrastar e dar zoom), sem desenhar nem mexer nos desenhos.
  final bool somenteLeitura;

  /// Índice do 1º candle da partida (fim da análise): uma linha marca onde a partida começou.
  final int? divisor;

  /// 0 a 1: quanto dos candles depois do [divisor] já apareceu (animação do relatório).
  final double revelacao;

  /// Resultado de cada desenho (mesma ordem de [desenhos]): true ✔, false ✖, null • (o preço não chegou lá).
  final List<bool?>? resultados;

  /// 0 a 1: os selos ✔/✖ aparecem um a um conforme este valor cresce.
  final double selos;

  /// Datas reais de cada candle (só no resultado, quando o ativo já foi revelado); sem elas, o eixo usa os rótulos ocultos.
  final List<String>? datas;

  final List<Vela> velas;
  final List<Desenho> desenhos;
  final Ferramenta? ferramenta;

  /// Os desenhos mudaram (novo, movido ou apagado). `usouFerramenta` = um desenho novo foi colocado (a tela pode soltar a ferramenta).
  final void Function({bool usouFerramenta}) aoMudar;

  /// Pede o texto de uma anotação (null = cancelou).
  final Future<String?> Function() pedirTexto;
  final Set<String> indicadores;
  final String tfNome;

  /// Máximo de desenhos de cada grupo (níveis, tendências, zonas, notas).
  final int limite;
  final void Function(String)? aoAviso;

  @override
  State<GraficoNativo> createState() => _GraficoNativoState();
}

const _eixo = 50.0;
const _rodape = 16.0;

class _GraficoNativoState extends State<GraficoNativo> with TickerProviderStateMixin {
  double _cw = 0, _off = 0, _w = 0, _h = 0;
  bool _iniciado = false;
  (int, double)? _pendente; // 1º ponto da tendência ou zona
  Desenho? _arrastando;
  String _parte = ''; // 'p1', 'p2' (ponta da tendência/zona) ou 'tudo'
  double _cw0 = 0, _off0 = 0;
  Offset _foco0 = Offset.zero;
  (double, double)? _dominioPreso;
  Desenho? _novo;

  late final AnimationController _entrada = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..forward();
  late final AnimationController _fx = AnimationController(vsync: this, duration: const Duration(milliseconds: 700));
  late final AnimationController _pulso = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));

  /// Último índice da análise (o replay começa no [divisor]).
  int get _fimAnalise {
    final d = widget.divisor;
    return (d != null && d > 0 && d <= widget.velas.length) ? d : widget.velas.length;
  }

  /// Preço no fim da análise: a referência contra a qual o servidor confere os desenhos.
  double get _refPreco => widget.velas.isEmpty ? 0 : widget.velas[_fimAnalise - 1].c;

  /// Pode desenhar em qualquer lugar; o acerto é que vale proporcional à distância (igual ao servidor). Aqui só se avisa, sem bloquear.
  void _avisarPeso(double dist) {
    final plena = _distPlena;
    final peso = plena <= 0 ? 1.0 : (dist / plena).clamp(0.0, 1.0);
    if (peso < 0.9) widget.aoAviso?.call('Perto do preço de partida: este desenho vale ${(peso * 100).round()}% dos pontos. Quanto mais longe, mais ele vale.');
  }

  /// Distância do preço de partida a partir da qual um acerto vale 100%. Mesma conta de trader_leitura.distancia_plena: 2 ATR, com piso de 1,6%.
  double get _distPlena {
    final v = widget.velas;
    final ref = _refPreco;
    final piso = max(0.016 * ref, 0.02);
    final fim = _fimAnalise;
    if (fim < 2) return piso;
    var soma = 0.0;
    var n = 0;
    for (var i = max(1, fim - 14); i < fim; i++) {
      final ant = v[i - 1].c;
      soma += max(v[i].h - v[i].l, max((v[i].h - ant).abs(), (ant - v[i].l).abs()));
      n++;
    }
    return max(n == 0 ? 0.0 : 2.0 * soma / n, piso);     // 2 ATR, igual a trader_leitura.DIST_PLENA
  }
  late List<double?> _mm20 = media(widget.velas, 20), _mm50 = media(widget.velas, 50), _mm200 = media(widget.velas, 200);

  @override
  void didUpdateWidget(GraficoNativo old) {
    super.didUpdateWidget(old);
    if (old.velas.length != widget.velas.length || (widget.velas.isNotEmpty && old.velas.last.c != widget.velas.last.c)) {
      _mm20 = media(widget.velas, 20);
      _mm50 = media(widget.velas, 50);
      _mm200 = media(widget.velas, 200);
    }
    if (old.ferramenta != widget.ferramenta) {
      _pendente = null;
      _pulso.stop();
    }
  }

  @override
  void dispose() {
    _entrada.dispose();
    _fx.dispose();
    _pulso.dispose();
    super.dispose();
  }

  double get _pw => max(60, _w - _eixo);
  int get _n => widget.velas.length;

  void _zoomInicial() {
    final dv = widget.divisor;
    final vis = dv != null ? min(_n, max(30, _n - max(0, dv - 30))) : min(_n, max(40, (_pw / 7).floor()));
    _cw = _pw / (vis + 3);
    _off = max(-3, _n - vis.toDouble());
    _iniciado = true;
  }

  void _limita() {
    _cw = _cw.clamp(2.0, 40.0);
    _off = _off.clamp(-3.0, max(-3.0, _n - _pw / _cw + 3));
  }

  (int, int) get _visiveis => (max(0, _off.floor()), min(_n - 1, (_off + _pw / _cw).ceil()));

  (double, double) get _dominio {
    if (_dominioPreso != null) return _dominioPreso!;
    final (i0, i1) = _visiveis;
    var lo = double.infinity, hi = -double.infinity;
    for (var i = i0; i <= i1; i++) {
      lo = min(lo, widget.velas[i].l);
      hi = max(hi, widget.velas[i].h);
    }
    if (!lo.isFinite) return (0, 1);
    final pad = (hi - lo) * 0.08;
    return (lo - (pad == 0 ? hi * 0.01 : pad), hi + (pad == 0 ? hi * 0.01 : pad));
  }

  double _y(double p) {
    final (lo, hi) = _dominio;
    return 4 + (hi - p) / (hi - lo) * (_h - _rodape - 8);
  }

  double _preco(double y) {
    final (lo, hi) = _dominio;
    return hi - (y - 4) / (_h - _rodape - 8) * (hi - lo);
  }

  double _x(num i) => (i - _off) * _cw + _cw / 2;
  int _candle(double x) => ((x - _cw / 2) / _cw + _off).round().clamp(0, max(0, _n - 1));
  double _r2(double v) => (v * 100).roundToDouble() / 100;

  // ---------------------------------------------------------------- toques
  Future<void> _tocar(Offset p) async {
    final f = widget.ferramenta;
    if (widget.somenteLeitura || f == null || p.dx > _pw) return;
    final pr = _r2(_preco(p.dy));
    if (pr <= 0) return;
    if (f == Ferramenta.apagar) {
      final d = _achar(p);
      if (d == null) {
        widget.aoAviso?.call('Nada para apagar aqui.');
      } else {
        _remover(d);
      }
      return;
    }
    if (_cheio(f)) {
      widget.aoAviso?.call('Limite de ${widget.limite} desenhos deste tipo.');
      return;
    }
    if (f.nivel) {
      _adicionar(Desenho.nivel(f, pr));
      _avisarPeso((pr - _refPreco).abs());
    } else if (f.doisPontos) {
      final i = _candle(p.dx);
      if (_pendente == null) {
        setState(() => _pendente = (i, pr));
        _pulso.repeat(reverse: true);
        HapticFeedback.selectionClick();
        return;
      }
      final (ia, pa) = _pendente!;
      if (f == Ferramenta.tendencia && ia == i) {
        widget.aoAviso?.call('Escolha um candle diferente para o 2º ponto.');
        return;
      }
      _pulso.stop();
      _pendente = null;
      _adicionar(Desenho.dois(f, min(ia, i), ia <= i ? pa : pr, max(ia, i), ia <= i ? pr : pa));
      if (f != Ferramenta.tendencia) {
        final (b, t) = (min(pa, pr), max(pa, pr));                 // a distância da zona é a da borda mais próxima (zero se envolve o preço)
        _avisarPeso(b <= _refPreco && _refPreco <= t ? 0 : min((b - _refPreco).abs(), (t - _refPreco).abs()));
      }
    } else if (f == Ferramenta.nota) {
      final i = _candle(p.dx);
      final t = await widget.pedirTexto();
      if (t != null && t.trim().isNotEmpty && mounted) _adicionar(Desenho.nota(i, pr, t.trim()));
    }
  }

  bool _cheio(Ferramenta f) {
    bool grupo(Desenho d) {
      if (f.nivel) return d.ferramenta.nivel;
      if (f == Ferramenta.zonaAlta || f == Ferramenta.zonaBaixa) return d.ferramenta == Ferramenta.zonaAlta || d.ferramenta == Ferramenta.zonaBaixa;
      return d.ferramenta == f;
    }

    final lim = (f == Ferramenta.zonaAlta || f == Ferramenta.zonaBaixa) ? 3 : (f == Ferramenta.tendencia ? 4 : 6);
    return widget.desenhos.where(grupo).length >= min(lim, widget.limite);
  }

  void _adicionar(Desenho d) {
    HapticFeedback.lightImpact();
    setState(() {
      widget.desenhos.add(d);
      _novo = d;
    });
    _fx.forward(from: 0);
    widget.aoMudar(usouFerramenta: true);
  }

  void _remover(Desenho d) {
    HapticFeedback.mediumImpact();
    setState(() => widget.desenhos.remove(d));
    widget.aoMudar();
  }

  /// O desenho mais perto do dedo (linha horizontal, ponta da tendência, zona ou nota).
  Desenho? _achar(Offset p, {double raio = 22}) {
    Desenho? melhor;
    var bd = raio;
    for (final d in widget.desenhos) {
      double dist;
      if (d.ferramenta.nivel) {
        dist = (_y(d.p1!) - p.dy).abs();
      } else if (d.ferramenta == Ferramenta.tendencia) {
        final x1 = _x(d.i1!), y1 = _y(d.p1!), x2 = _x(d.i2!), y2 = _y(d.p2!);
        final k = (y2 - y1) / ((x2 - x1) == 0 ? 1 : (x2 - x1));
        dist = p.dx < x1 - 10 ? double.infinity : (y1 + k * (p.dx - x1) - p.dy).abs();
      } else if (d.ferramenta == Ferramenta.nota) {
        dist = (Offset(_x(d.i1!), _y(d.p1!)) - p).distance;
      } else {
        final r = Rect.fromLTRB(_x(d.i1!) - _cw / 2, _y(d.p2!), _pw, _y(d.p1!));
        dist = r.inflate(6).contains(p) ? 4 : double.infinity;
      }
      if (dist < bd) {
        bd = dist;
        melhor = d;
      }
    }
    return melhor;
  }

  void _inicioGesto(ScaleStartDetails e) {
    _cw0 = _cw;
    _off0 = _off;
    _foco0 = e.localFocalPoint;
    _arrastando = null;
    if (!widget.somenteLeitura && e.pointerCount == 1 && widget.ferramenta == null && e.localFocalPoint.dx <= _pw) {
      final d = _achar(e.localFocalPoint);
      if (d != null) {
        _arrastando = d;
        _dominioPreso = _dominio;
        _parte = 'tudo';
        if (d.ferramenta.doisPontos) {
          final a = (Offset(_x(d.i1!), _y(d.p1!)) - e.localFocalPoint).distance;
          final b = (Offset(_x(d.i2!), _y(d.p2!)) - e.localFocalPoint).distance;
          if (min(a, b) < 26) _parte = a < b ? 'p1' : 'p2';
        }
        HapticFeedback.selectionClick();
      }
    }
  }

  void _gesto(ScaleUpdateDetails e) {
    setState(() {
      if (e.pointerCount >= 2) {
        _arrastando = null;
        _dominioPreso = null;
        final idx = (_foco0.dx - _cw0 / 2) / _cw0 + _off0;
        _cw = (_cw0 * e.horizontalScale).clamp(2.0, 40.0);
        _off = idx - (e.localFocalPoint.dx - _cw / 2) / _cw;
        _limita();
        return;
      }
      final d = _arrastando;
      if (d != null) {
        final pr = _r2(_preco(e.localFocalPoint.dy));
        if (pr <= 0) return;
        if (d.ferramenta.nivel) {
          d.p1 = pr;
        } else if (_parte == 'p1' || _parte == 'p2') {
          final i = _candle(e.localFocalPoint.dx);
          if (_parte == 'p1') {
            d.i1 = i;
            d.p1 = pr;
          } else {
            d.i2 = i;
            d.p2 = pr;
          }
        } else {
          final dp = _preco(e.localFocalPoint.dy) - _preco(e.localFocalPoint.dy - e.focalPointDelta.dy);
          final di = (e.focalPointDelta.dx / _cw);
          d.p1 = _r2(d.p1! + dp);
          if (d.p2 != null) d.p2 = _r2(d.p2! + dp);
          if (d.i1 != null && di.abs() >= 0.5) {
            final s = di.round();
            d.i1 = (d.i1! + s).clamp(0, _n - 1);
            if (d.i2 != null) d.i2 = (d.i2! + s).clamp(0, _n - 1);
          }
        }
        return;
      }
      _off = _off0 - (e.localFocalPoint.dx - _foco0.dx) / _cw;
      _limita();
    });
  }

  void _fimGesto(ScaleEndDetails e) {
    final d = _arrastando;
    if (d != null) {
      if (d.ferramenta.doisPontos && d.i1! > d.i2!) {
        final (i, p) = (d.i1!, d.p1!);
        d.i1 = d.i2;
        d.p1 = d.p2;
        d.i2 = i;
        d.p2 = p;
      }
      widget.aoMudar();
    }
    setState(() {
      _arrastando = null;
      _dominioPreso = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (ctx, c) {
        _w = c.maxWidth;
        _h = c.maxHeight;
        if (!_iniciado && _w > 100 && _n > 0) _zoomInicial();
        _limita();
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapUp: (e) => _tocar(e.localPosition),
          onLongPressStart: (e) {
            if (widget.ferramenta != null || widget.somenteLeitura) return;
            final d = _achar(e.localPosition);
            if (d != null) {
              _remover(d);
              widget.aoAviso?.call('Desenho apagado.');
            }
          },
          onScaleStart: _inicioGesto,
          onScaleUpdate: _gesto,
          onScaleEnd: _fimGesto,
          child: AnimatedBuilder(
            animation: Listenable.merge([_entrada, _fx, _pulso]),
            builder: (ctx, _) => CustomPaint(
              size: Size(_w, _h),
              painter: _Pintor(this),
            ),
          ),
        );
      },
    );
  }
}

class _Pintor extends CustomPainter {
  _Pintor(this.g);
  final _GraficoNativoState g;

  static const _up = Color(0xFF26D07C), _dn = Color(0xFFFF4D6D);

  @override
  void paint(Canvas canvas, Size size) {
    if (g._n == 0 || g._cw <= 0) return;
    final w = g.widget;
    final pw = g._pw, h = size.height - _rodape;
    final (lo, hi) = g._dominio;
    final (i0, i1) = g._visiveis;
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, size.width, size.height));

    // marca d'água
    _texto(canvas, 'TICKER HUNTER', Offset(pw / 2, h * 0.46), max(18, min(48, pw * 0.1)), const Color(0x12AAC9FF), centro: true, peso: FontWeight.w900);
    _texto(canvas, w.tfNome, Offset(pw / 2, h * 0.46 + max(18, min(48, pw * 0.1)) * 0.8), 12, const Color(0x14AAC9FF), centro: true, peso: FontWeight.w800);

    // grade e eixo de preços
    final passo = _passo((hi - lo) / 5);
    final grade = Paint()
      ..color = const Color(0x10FFFFFF)
      ..strokeWidth = 1;
    for (var p = (lo / passo).ceil() * passo; p < hi; p += passo) {
      final y = g._y(p);
      canvas.drawLine(Offset(0, y), Offset(pw, y), grade);
      _texto(canvas, precoTxt(p), Offset(pw + 4, y), 10, const Color(0xFFC8D6EE));
    }

    final bw = max(1.0, min(g._cw * 0.7, 14.0));
    final ent = g._entrada.value;

    // volume
    if (w.indicadores.contains('vol')) {
      var mv = 0.0;
      for (var i = i0; i <= i1; i++) {
        mv = max(mv, w.velas[i].v);
      }
      if (mv > 0) {
        for (var i = i0; i <= i1; i++) {
          final v = w.velas[i];
          final hh = v.v / mv * h * 0.16 * _cascata(ent, i, i0, i1);
          canvas.drawRect(Rect.fromLTWH(g._x(i) - bw / 2, h - hh, bw, hh), Paint()..color = (v.alta ? _up : _dn).withValues(alpha: 0.3));
        }
      }
    }

    // candles (entram em cascata da esquerda para a direita ao abrir)
    final dv = w.divisor;
    final ultimoVisivel = dv == null ? w.velas.length - 1 : dv - 1 + ((w.velas.length - dv) * w.revelacao).floor();
    for (var i = i0; i <= i1; i++) {
      final v = w.velas[i];
      final e = _cascata(ent, i, i0, i1);
      if (e <= 0 || i > ultimoVisivel) continue;
      final cor = (v.alta ? _up : _dn).withValues(alpha: e);
      final x = g._x(i);
      final meio = (v.o + v.c) / 2;
      double ajusta(double p) => meio + (p - meio) * e;
      canvas.drawLine(Offset(x, g._y(ajusta(v.h))), Offset(x, g._y(ajusta(v.l))), Paint()
        ..color = cor
        ..strokeWidth = 1);
      final y1 = g._y(ajusta(max(v.o, v.c))), y2 = g._y(ajusta(min(v.o, v.c)));
      canvas.drawRect(Rect.fromLTWH(x - bw / 2, y1, bw, max(1, y2 - y1)), Paint()..color = cor);
    }

    // onde a partida começou (relatório)
    if (dv != null && dv >= i0 && dv <= i1 + 1) {
      final xd = g._x(dv) - g._cw / 2;
      _tracejadaV(canvas, xd, h, const Color(0x99FFD66B));
      _texto(canvas, 'início da partida', Offset(xd + 4, 12), 9.5, const Color(0xFFFFD66B), peso: FontWeight.w800);
    }

    // médias móveis
    void serie(List<double?> vs, Color cor) {
      final path = Path();
      var aberto = false;
      for (var i = max(0, i0 - 1); i <= i1; i++) {
        final v = vs[i];
        if (v == null) {
          aberto = false;
          continue;
        }
        final o = Offset(g._x(i), g._y(v));
        if (!aberto) {
          path.moveTo(o.dx, o.dy);
          aberto = true;
        } else {
          path.lineTo(o.dx, o.dy);
        }
      }
      canvas.drawPath(path, Paint()
        ..color = cor.withValues(alpha: ent)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6);
    }

    if (w.indicadores.contains('mm20')) serie(g._mm20, const Color(0xFFF2B84B));
    if (w.indicadores.contains('mm50')) serie(g._mm50, const Color(0xFF4DA3FF));
    if (w.indicadores.contains('mm200')) serie(g._mm200, const Color(0xFFE6E6F0));

    // último preço
    final u = w.velas.last;
    final yu = g._y(u.c);
    _tracejada(canvas, yu, pw, const Color(0x66FFFFFF), [2, 3]);
    _etiqueta(canvas, precoTxt(u.c), pw, yu, size.width, const Color(0xFFE9F1FF), const Color(0xFF0C192E));

    // desenhos
    final usados = <double>[];
    for (final d in w.desenhos) {
      final acende = identical(d, g._novo) ? (1 - g._fx.value) : 0.0;
      final arrastando = identical(d, g._arrastando);
      final lw = 2.0 + 3 * acende + (arrastando ? 1.5 : 0);
      final cor = d.cor;
      if (d.ferramenta.nivel) {
        final y = g._y(d.p1!);
        if (acende > 0) {
          canvas.drawLine(Offset(0, y), Offset(pw, y), Paint()
            ..color = cor.withValues(alpha: 0.35 * acende)
            ..strokeWidth = 12 * acende);
        }
        if (d.ferramenta == Ferramenta.rompimento) {
          _tracejada(canvas, y, pw, cor, [8, 4], largura: lw);
        } else {
          canvas.drawLine(Offset(0, y), Offset(pw, y), Paint()
            ..color = cor
            ..strokeWidth = lw);
        }
        _etiqueta(canvas, precoTxt(d.p1!), pw, y, size.width, cor, const Color(0xFF06101F));
        _rotulo(canvas, d.ferramenta.rotulo.toUpperCase(), y, cor, usados);
        if (!w.somenteLeitura) {
          // alça para arrastar
          canvas.drawCircle(Offset(pw - 14, y), 6 + 2 * acende, Paint()..color = cor);
          _texto(canvas, '↕', Offset(pw - 14, y), 9, const Color(0xFF06101F), centro: true, peso: FontWeight.w900);
        }
      } else if (d.ferramenta == Ferramenta.tendencia) {
        final a = Offset(g._x(d.i1!), g._y(d.p1!)), b = Offset(g._x(d.i2!), g._y(d.p2!));
        final k = (b.dy - a.dy) / ((b.dx - a.dx) == 0 ? 1 : (b.dx - a.dx));
        final fim = Offset(pw, a.dy + k * (pw - a.dx));
        if (acende > 0) {
          canvas.drawLine(a, fim, Paint()
            ..color = cor.withValues(alpha: 0.35 * acende)
            ..strokeWidth = 12 * acende);
        }
        canvas.drawLine(a, fim, Paint()
          ..color = cor
          ..strokeWidth = lw);
        for (final o in [a, b]) {
          canvas.drawCircle(o, 5, Paint()..color = cor);
          canvas.drawCircle(o, 5, Paint()
            ..color = Colors.white
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.5);
        }
      } else if (d.ferramenta == Ferramenta.nota) {
        final o = Offset(g._x(d.i1!), g._y(d.p1!));
        canvas.drawCircle(o, 4 + 3 * acende, Paint()..color = cor);
        final tp = _tp(d.texto ?? '', 11, Colors.white, FontWeight.w700);
        final bx = Rect.fromLTWH(min(o.dx - tp.width / 2 - 6, pw - tp.width - 12), o.dy - 26, tp.width + 12, 18);
        canvas.drawRRect(RRect.fromRectAndRadius(bx, const Radius.circular(7)), Paint()..color = const Color(0xEE2C5596));
        tp.paint(canvas, Offset(bx.left + 6, bx.top + 2));
      } else {
        final alta = d.ferramenta == Ferramenta.zonaAlta;
        final r = Rect.fromLTRB(g._x(d.i1!) - g._cw / 2, g._y(d.p2!), pw, g._y(d.p1!));
        canvas.drawRect(r, Paint()..color = cor.withValues(alpha: 0.16 + 0.2 * acende));
        canvas.drawRect(r, Paint()
          ..color = cor.withValues(alpha: 0.85)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5 + 2 * acende);
        _texto(canvas, alta ? '▲ reage para cima' : '▼ reage para baixo', Offset(r.left + 6, r.top + 9), 10, cor, peso: FontWeight.w900);
        for (final o in [Offset(g._x(d.i1!), g._y(d.p1!)), Offset(g._x(d.i2!), g._y(d.p2!))]) {
          canvas.drawCircle(o, 4.5, Paint()..color = cor);
        }
      }
    }

    // selos ✔/✖ do relatório, um a um
    final res = w.resultados;
    if (res != null) {
      for (var k = 0; k < w.desenhos.length && k < res.length; k++) {
        final t = (w.selos * w.desenhos.length - k).clamp(0.0, 1.0);
        if (t <= 0) continue;
        final d = w.desenhos[k];
        Offset o;
        if (d.ferramenta.nivel) {
          o = Offset(pw - 36, g._y(d.p1!));
        } else if (d.ferramenta == Ferramenta.tendencia) {
          o = Offset(g._x(d.i2!) + 14, g._y(d.p2!) - 14);
        } else {
          o = Offset(pw - 16, g._y(d.p2!) + 2);
        }
        final ok = res[k];
        final cor = ok == true ? const Color(0xFF26D07C) : (ok == false ? const Color(0xFFFF4D6D) : const Color(0xFF6CA3FF));
        final esc = t < 1 ? Curves.elasticOut.transform(t) : 1.0;
        canvas.save();
        canvas.translate(o.dx, o.dy);
        canvas.scale(esc);
        canvas.drawCircle(Offset.zero, 13, Paint()..color = cor.withValues(alpha: 0.35));
        canvas.drawCircle(Offset.zero, 10, Paint()..color = cor);
        canvas.drawCircle(Offset.zero, 10, Paint()
          ..color = Colors.white
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
        _texto(canvas, ok == true ? '✔' : (ok == false ? '✖' : '!'), Offset.zero, 12, Colors.white, centro: true, peso: FontWeight.w900);
        canvas.restore();
      }
    }

    // 1º ponto de tendência/zona esperando o 2º (pulsa)
    final pd = g._pendente;
    if (pd != null && w.ferramenta != null) {
      final o = Offset(g._x(pd.$1), g._y(pd.$2));
      final v = g._pulso.value;
      canvas.drawCircle(o, 8 + 8 * v, Paint()..color = w.ferramenta!.cor.withValues(alpha: 0.35 * (1 - v)));
      canvas.drawCircle(o, 6, Paint()..color = w.ferramenta!.cor);
    }

    // eixo do tempo (gráfico diário: número do pregão)
    final diario = w.tfNome == '1 dia';
    final gap = max(1, (70 / g._cw).round());
    for (var i = (g._off / gap).ceil() * gap; i <= i1; i += gap) {
      if (i < 0) continue;
      final x = g._x(i);
      if (x < 14 || x > pw - 14) continue;
      final v = w.velas[i];
      final dt = w.datas;
      final rot = dt != null && i < dt.length ? dt[i] : (diario ? 'Pregão ${v.d ?? i + 1}' : '${v.d != null ? 'D${v.d} ' : ''}${v.t}');
      _texto(canvas, rot, Offset(x, size.height - 7), 9, const Color(0xFF96ACCE), centro: true);
    }
    canvas.restore();
  }

  double _cascata(double ent, int i, int i0, int i1) {
    if (ent >= 1) return 1;
    final pos = i1 == i0 ? 1.0 : (i - i0) / (i1 - i0);
    return ((ent * 1.6 - pos * 0.6)).clamp(0.0, 1.0);
  }

  double _passo(double r) {
    final e = pow(10, (log(r) / ln10).floor()).toDouble(), f = r / e;
    return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * e;
  }

  void _tracejada(Canvas c, double y, double ate, Color cor, List<double> d, {double largura = 1}) {
    final p = Paint()
      ..color = cor
      ..strokeWidth = largura;
    var x = 0.0;
    var k = 0;
    while (x < ate) {
      final l = d[k % 2];
      if (k.isEven) c.drawLine(Offset(x, y), Offset(min(ate, x + l), y), p);
      x += l;
      k++;
    }
  }

  void _tracejadaV(Canvas c, double x, double ate, Color cor) {
    final p = Paint()
      ..color = cor
      ..strokeWidth = 1.5;
    for (var y = 0.0; y < ate; y += 9) {
      c.drawLine(Offset(x, y), Offset(x, min(ate, y + 5)), p);
    }
  }

  void _etiqueta(Canvas c, String t, double pw, double y, double w, Color fundo, Color letra) {
    final r = Rect.fromLTWH(pw + 1, y - 8, w - pw - 1, 16);
    c.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(4)), Paint()..color = fundo);
    _texto(c, t, Offset(pw + 4, y), 10, letra, peso: FontWeight.w800);
  }

  void _rotulo(Canvas c, String t, double y, Color cor, List<double> usados) {
    var yy = y;
    for (var k = 0; k < 10 && usados.any((u) => (u - yy).abs() < 17); k++) {
      yy += 17;
    }
    usados.add(yy);
    final tp = _tp(t, 9.5, const Color(0xFF06101F), FontWeight.w900);
    final r = Rect.fromLTWH(4, yy - 8, tp.width + 10, 16);
    c.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(5)), Paint()..color = cor);
    tp.paint(c, Offset(9, yy - tp.height / 2));
  }

  TextPainter _tp(String t, double s, Color cor, FontWeight peso) =>
      TextPainter(text: TextSpan(text: t, style: TextStyle(fontSize: s, color: cor, fontWeight: peso)), textDirection: TextDirection.ltr)..layout();

  void _texto(Canvas c, String t, Offset o, double s, Color cor, {bool centro = false, FontWeight peso = FontWeight.w500}) {
    final tp = _tp(t, s, cor, peso);
    tp.paint(c, Offset(centro ? o.dx - tp.width / 2 : o.dx, o.dy - tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => true;
}
