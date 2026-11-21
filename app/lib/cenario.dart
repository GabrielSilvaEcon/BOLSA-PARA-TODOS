import 'dart:math';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';

/// Cenário econômico do Brasil (botão da tela inicial): o veredito geral, os números principais (juros, inflação, juro real,
/// dólar, desemprego e a Selic esperada), os fatores da economia em barras e quem tende a ganhar ou perder.
/// O cálculo é o da página Economia do app antigo (macro_cenario.py), feito no servidor. Educativo: descreve o ambiente.
class CenarioTela extends StatefulWidget {
  const CenarioTela({super.key, required this.api});
  final Api api;

  @override
  State<CenarioTela> createState() => _CenarioTelaState();
}

const _lilas = Color(0xFFD4E2F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);

String _num(num v, int casas) {
  final s = v.abs().toStringAsFixed(casas);
  final p = s.split('.');
  final b = StringBuffer();
  for (var i = 0; i < p[0].length; i++) {
    if (i > 0 && (p[0].length - i) % 3 == 0) b.write('.');
    b.write(p[0][i]);
  }
  return '${v < 0 ? '-' : ''}$b${casas > 0 ? ',${p[1]}' : ''}';
}

class _CenarioTelaState extends State<CenarioTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String? _aberto;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _erro = null);
    try {
      final r = await widget.api.get('/cenario');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  const Expanded(child: Text('Cenário econômico', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                if (d == null && _erro == null)
                  const Padding(
                    padding: EdgeInsets.all(40),
                    child: Column(children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 12),
                      Text('Lendo os indicadores da economia…', style: TextStyle(color: _lilas)),
                    ]),
                  ),
                if (d == null && _erro != null)
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(children: [
                      Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
                      const SizedBox(height: 10),
                      FilledButton.icon(onPressed: _carregar, icon: const Icon(Icons.refresh_rounded), label: const Text('Tentar de novo')),
                    ]),
                  ),
                if (d != null) ...[
                  Entrada(ordem: 0, child: _veredito((d['geral'] as Map?) ?? const {}, '${d['dados_ate'] ?? ''}')),
                  _titulo('Os números de hoje', Icons.speed_rounded),
                  Entrada(ordem: 1, child: _principais(((d['principais'] as List?) ?? const []).cast<Map>())),
                  if (((d['fatores'] as List?) ?? const []).isNotEmpty) ...[
                    _titulo('O que está pesando na economia', Icons.tune_rounded),
                    Entrada(ordem: 2, child: _fatores(((d['fatores'] as List?) ?? const []).cast<Map>())),
                  ],
                  _titulo('Quem tende a ganhar ou perder', Icons.swap_vert_rounded),
                  Entrada(ordem: 3, child: _setores('Tende a ganhar', ((d['beneficiados'] as List?) ?? const []).cast<Map>(), _verde, Icons.trending_up_rounded, 'seta')),
                  const SizedBox(height: 8),
                  Entrada(ordem: 4, child: _setores('Tende a sofrer', ((d['pressionados'] as List?) ?? const []).cast<Map>(), _vermelho, Icons.trending_down_rounded, 'touro')),
                  const SizedBox(height: 14),
                  Text('${d['aviso'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 11.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _titulo(String t, IconData ic) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
        child: Row(children: [
          Icon(ic, color: const Color(0xFF7FE6F5), size: 20),
          const SizedBox(width: 6),
          Expanded(child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
        ]),
      );

  BoxDecoration _caixa(Color cor, [String? arte]) => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: cor.withValues(alpha: 0.9), width: 1.6),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(cor, const Color(0xFF0B2C5E), 0.5)!, Color.lerp(cor, const Color(0xFF082450), 0.8)!]),
        image: arte == null ? null : arteCartao(arte, opacidade: 0.42),
        boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.3), blurRadius: 12)],
      );

  Widget _veredito(Map g, String ate) {
    final v = '${g['veredito'] ?? 'NEUTRO'}';
    final (rot, cor, ic) = switch (v) {
      'BOM' => ('Favorável', _verde, Icons.sentiment_satisfied_alt_rounded),
      'RUIM' => ('Desfavorável', _vermelho, Icons.sentiment_dissatisfied_rounded),
      _ => ('Sinais mistos', _ouro, Icons.sentiment_neutral_rounded),
    };
    String data(String t) => t.length >= 10 ? '${t.substring(8, 10)}/${t.substring(5, 7)}/${t.substring(0, 4)}' : '';
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _caixa(cor, 'cidade'),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
                shape: BoxShape.circle, color: cor.withValues(alpha: 0.25), border: Border.all(color: cor, width: 2), boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 14)]),
            child: Icon(ic, color: Colors.white, size: 32),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Economia do Brasil', style: TextStyle(fontSize: 13, color: _lilas)),
              Text(rot, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: cor)),
              if (g['confianca'] != null) Text('Confiança da leitura: ${'${g['confianca']}'.toLowerCase()}', style: const TextStyle(fontSize: 12, color: Colors.white)),
            ]),
          ),
        ]),
        const SizedBox(height: 10),
        Text('${g['texto'] ?? ''}', style: const TextStyle(fontSize: 13.5, height: 1.35, color: Colors.white)),
        if (data(ate).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text('Dados até ${data(ate)}', style: const TextStyle(fontSize: 11, color: _lilas))),
      ]),
    );
  }

  static const _visual = {
    'selic_meta': (Icons.account_balance_rounded, Color(0xFF6CA3FF), 'cofre'),
    'ipca_12m': (Icons.shopping_cart_rounded, Color(0xFFFF8A3D), 'moedas'),
    'juro_real': (Icons.trending_up_rounded, Color(0xFF26D07C), 'seta'),
    'dolar': (Icons.attach_money_rounded, Color(0xFF2BC4A0), 'moedas'),
    'desemprego': (Icons.work_rounded, Color(0xFFFF6B8A), 'cidade'),
    'focus_selic': (Icons.query_stats_rounded, Color(0xFF4F9BFF), 'velas'),
  };

  String _fmt(Map p) {
    final v = p['valor'];
    if (v is! num) return '—';
    if (p['id'] == 'dolar') return 'R\$ ${_num(v, 2)}';
    return '${_num(v, p['id'] == 'desemprego' || p['id'] == 'juro_real' ? 1 : 2)}%';
  }

  Widget _principais(List<Map> ps) => LayoutBuilder(builder: (ctx, c) {
        final w = (c.maxWidth - 8) / 2;
        return Wrap(spacing: 8, runSpacing: 8, children: [
          for (final p in ps)
            Builder(builder: (ctx) {
              final (ic, cor, arte) = _visual['${p['id']}'] ?? (Icons.insights_rounded, const Color(0xFF6CA3FF), 'cidade');
              final aberto = _aberto == p['id'];
              final serie = [for (final x in (p['serie'] as List? ?? const [])) (x as num).toDouble()];
              return SizedBox(
                width: aberto ? c.maxWidth : w,
                child: Pressionavel(
                  aoTocar: () => setState(() => _aberto = aberto ? null : '${p['id']}'),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 250),
                    padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                    decoration: _caixa(cor, arte),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Container(
                          width: 30,
                          height: 30,
                          decoration: BoxDecoration(shape: BoxShape.circle, color: cor.withValues(alpha: 0.35), border: Border.all(color: Colors.white.withValues(alpha: 0.6))),
                          child: Icon(ic, color: Colors.white, size: 17),
                        ),
                        const SizedBox(width: 6),
                        Expanded(child: Text('${p['rotulo']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: Colors.white))),
                      ]),
                      const SizedBox(height: 4),
                      FittedBox(child: Text(_fmt(p), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Colors.white))),
                      if (serie.length >= 2) SizedBox(height: 26, width: double.infinity, child: CustomPaint(painter: _Mini(serie, Color.lerp(cor, Colors.white, 0.3)!))),
                      if (p['ref'] != null) Text('${p['ref']}', style: const TextStyle(fontSize: 10.5, color: _lilas)),
                      if (aberto) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${p['explica']}', style: const TextStyle(fontSize: 12.5, color: Colors.white))),
                    ]),
                  ),
                ),
              );
            }),
        ]);
      });

  Widget _fatores(List<Map> fs) => Container(
        padding: const EdgeInsets.all(12),
        decoration: _caixa(const Color(0xFF26C6DA)),
        child: Column(children: [
          for (final f in fs) _fator(f),
          const Padding(
            padding: EdgeInsets.only(top: 4),
            child: Text('Cada barra vai de "mais baixo" (esquerda) a "mais alto" (direita). Alto não é bom nem ruim por si só: depende do setor. Toque para ler.',
                style: TextStyle(fontSize: 11, color: _lilas)),
          ),
        ]),
      );

  Widget _fator(Map f) {
    final v = ((f['valor'] as num?) ?? 0).toDouble().clamp(-1.0, 1.0);
    final aberto = _aberto == 'f_${f['id']}';
    final cor = Color.lerp(const Color(0xFF4F9BFF), const Color(0xFFFF8A3D), (v + 1) / 2)!;
    return Pressionavel(
      aoTocar: () => setState(() => _aberto = aberto ? null : 'f_${f['id']}'),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text('${f['nome']}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white))),
            Text(v > 0.15 ? 'alto' : (v < -0.15 ? 'baixo' : 'normal'), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: cor)),
          ]),
          const SizedBox(height: 4),
          LayoutBuilder(builder: (ctx, c) {
            final w = c.maxWidth;
            return SizedBox(
              height: 12,
              child: Stack(children: [
                Container(decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), gradient: const LinearGradient(colors: [Color(0x554F9BFF), Color(0x33FFFFFF), Color(0x55FF8A3D)]))),
                Positioned(left: w / 2 - 1, top: 0, bottom: 0, child: Container(width: 2, color: Colors.white54)),
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: v),
                  duration: const Duration(milliseconds: 1000),
                  curve: Curves.easeOutCubic,
                  builder: (ctx, x, _) => Positioned(
                    left: x >= 0 ? w / 2 : w / 2 + x * w / 2,
                    width: max(2, x.abs() * w / 2),
                    top: 0,
                    bottom: 0,
                    child: Container(decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: cor, boxShadow: [BoxShadow(color: cor, blurRadius: 6)])),
                  ),
                ),
              ]),
            );
          }),
          if (aberto && '${f['texto'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${f['texto']}', style: const TextStyle(fontSize: 12, color: Colors.white))),
        ]),
      ),
    );
  }

  Widget _setores(String titulo, List<Map> itens, Color cor, IconData ic, String arte) => Container(
        padding: const EdgeInsets.all(12),
        decoration: _caixa(cor, arte),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(ic, color: cor),
            const SizedBox(width: 6),
            Text(titulo, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: cor)),
          ]),
          const SizedBox(height: 6),
          if (itens.isEmpty) const Text('Nenhum setor com sinal forte agora.', style: TextStyle(color: _lilas)),
          for (final s in itens)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Container(margin: const EdgeInsets.only(top: 5), width: 8, height: 8, decoration: BoxDecoration(shape: BoxShape.circle, color: cor)),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${s['nome']}', style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w900, color: Colors.white)),
                    if ('${s['motivo'] ?? ''}'.isNotEmpty) Text('${s['motivo']}', style: const TextStyle(fontSize: 11.5, color: Color(0xFFE1ECFF))),
                  ]),
                ),
              ]),
            ),
        ]),
      );
}

/// Linha pequena do histórico de cada número (últimos 24 pontos).
class _Mini extends CustomPainter {
  _Mini(this.v, this.cor);
  final List<double> v;
  final Color cor;

  @override
  void paint(Canvas c, Size s) {
    final lo = v.reduce(min), hi = v.reduce(max);
    final f = hi - lo == 0 ? 1.0 : hi - lo;
    final p = Path();
    for (var i = 0; i < v.length; i++) {
      final o = Offset(s.width * i / (v.length - 1), s.height - 2 - (v[i] - lo) / f * (s.height - 4));
      i == 0 ? p.moveTo(o.dx, o.dy) : p.lineTo(o.dx, o.dy);
    }
    c.drawPath(
        p,
        Paint()
          ..color = cor
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2);
  }

  @override
  bool shouldRepaint(_Mini o) => o.v != v;
}
