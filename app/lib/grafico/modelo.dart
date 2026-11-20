import 'package:flutter/material.dart';

/// Um candle do gráfico (o mesmo formato que o servidor manda na mesa: t, o, h, l, c, v, d).
class Vela {
  const Vela({required this.o, required this.h, required this.l, required this.c, this.v = 0, this.t = '', this.d});
  final double o, h, l, c, v;
  final String t;
  final int? d;

  bool get alta => c >= o;

  static Vela de(Map m) {
    double n(Object? x) => x is num ? x.toDouble() : double.tryParse('$x') ?? 0;
    return Vela(o: n(m['o']), h: n(m['h']), l: n(m['l']), c: n(m['c']), v: n(m['v']), t: '${m['t'] ?? ''}', d: (m['d'] as num?)?.toInt());
  }
}

/// Ferramentas de desenho da estratégia. Cada desenho tem um PAPEL: é a aposta do jogador sobre o que o preço vai fazer ali,
/// e no fim da partida o servidor confere cada um contra o gráfico real (30% da nota).
enum Ferramenta {
  suporte('Suporte', Icons.vertical_align_bottom_rounded, Color(0xFF26D07C), 'Toque no preço onde você acha que a queda vai parar.'),
  resistencia('Resistência', Icons.vertical_align_top_rounded, Color(0xFFFF4D6D), 'Toque no preço onde você acha que a alta vai travar.'),
  rompimento('Rompimento', Icons.open_in_full_rounded, Color(0xFFF2B84B), 'Toque no preço que você acha que vai ser rompido.'),
  alvo('Alvo', Icons.flag_rounded, Color(0xFF38B6FF), 'Toque no preço que você acha que vai ser alcançado.'),
  tendencia('Tendência', Icons.show_chart_rounded, Color(0xFFB59BFF), 'Toque em dois pontos para traçar a linha de tendência.'),
  zonaAlta('Zona ↑', Icons.crop_square_rounded, Color(0xFF26D07C), 'Toque em dois cantos: o preço entra na área e reage para CIMA.'),
  zonaBaixa('Zona ↓', Icons.crop_square_rounded, Color(0xFFFF4D6D), 'Toque em dois cantos: o preço entra na área e reage para BAIXO.'),
  nota('Nota', Icons.sticky_note_2_rounded, Color(0xFFC9B8FF), 'Toque no gráfico para escrever uma anotação.'),
  apagar('Apagar', Icons.backspace_rounded, Color(0xFFFF8FA3), 'Toque num desenho para apagar.');

  const Ferramenta(this.rotulo, this.icone, this.cor, this.dica);
  final String rotulo;
  final IconData icone;
  final Color cor;
  final String dica;

  bool get nivel => this == suporte || this == resistencia || this == rompimento || this == alvo;
  bool get doisPontos => this == tendencia || this == zonaAlta || this == zonaBaixa;
}

/// Um desenho no gráfico. Os índices são de candle (o mesmo eixo do servidor); preços em reais.
class Desenho {
  Desenho.nivel(this.ferramenta, this.p1) : i1 = null, i2 = null, p2 = null, texto = null;
  Desenho.dois(this.ferramenta, int a, double pa, int b, double pb)
      : i1 = a,
        p1 = pa,
        i2 = b,
        p2 = pb,
        texto = null;
  Desenho.nota(int i, double p, this.texto) : ferramenta = Ferramenta.nota, i1 = i, p1 = p, i2 = null, p2 = null;

  final Ferramenta ferramenta;
  int? i1, i2;
  double? p1, p2;
  final String? texto;

  Color get cor => ferramenta.cor;
}

/// Converte os desenhos para o formato que o servidor guarda e avalia (`marcas`).
Map<String, dynamic> marcasDe(List<Desenho> ds) {
  const papel = {
    Ferramenta.suporte: 'suporte',
    Ferramenta.resistencia: 'resistencia',
    Ferramenta.rompimento: 'rompimento',
    Ferramenta.alvo: 'alvo',
  };
  return {
    'niveis': [
      for (final d in ds.where((d) => d.ferramenta.nivel))
        {'preco': _r2(d.p1!), 'rotulo': d.ferramenta.rotulo, 'papel': papel[d.ferramenta]},
    ],
    'tendencias': [
      for (final d in ds.where((d) => d.ferramenta == Ferramenta.tendencia)) {'i1': d.i1, 'p1': _r2(d.p1!), 'i2': d.i2, 'p2': _r2(d.p2!)},
    ],
    'zonas': [
      for (final d in ds.where((d) => d.ferramenta == Ferramenta.zonaAlta || d.ferramenta == Ferramenta.zonaBaixa))
        {'i1': d.i1, 'p1': _r2(d.p1!), 'i2': d.i2, 'p2': _r2(d.p2!), 'reacao': d.ferramenta == Ferramenta.zonaAlta ? 'alta' : 'baixa'},
    ],
    'notas': [
      for (final d in ds.where((d) => d.ferramenta == Ferramenta.nota)) {'i': d.i1, 'preco': _r2(d.p1!), 'texto': d.texto ?? ''},
    ],
  };
}

double _r2(double v) => (v * 100).roundToDouble() / 100;

/// Média móvel simples de [n] candles (null onde ainda não há candles suficientes).
List<double?> media(List<Vela> vs, int n) {
  final out = List<double?>.filled(vs.length, null);
  var s = 0.0;
  for (var i = 0; i < vs.length; i++) {
    s += vs[i].c;
    if (i >= n) s -= vs[i - n].c;
    if (i >= n - 1) out[i] = s / n;
  }
  return out;
}

String precoTxt(double p) => p.toStringAsFixed(2).replaceAll('.', ',');
