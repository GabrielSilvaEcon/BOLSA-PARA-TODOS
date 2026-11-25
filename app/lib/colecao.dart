import 'dart:math';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'cartas.dart';

/// COLEÇÃO: cartas descobertas e silhuetas das que faltam, filtros por raridade e setor, nível, cópias e progresso,
/// evoluir (escolhendo P/L, DY ou ROE) e equipar (1 por raridade, 4 espaços). Tudo é validado no servidor.
class ColecaoTela extends StatefulWidget {
  const ColecaoTela({super.key, required this.api});
  final Api api;

  @override
  State<ColecaoTela> createState() => _ColecaoTelaState();
}

class _ColecaoTelaState extends State<ColecaoTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String? _rar; // filtro de raridade (null = todas)
  String? _setor; // filtro de setor (null = todos)
  String? _acabouDeEquipar;

  @override
  void initState() {
    super.initState();
    CatalogoCartas.carregar(widget.api);
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/cartas/colecao');
      if (!mounted) return;
      setState(() {
        _d = r;
        _erro = null;
      });
      final ini = r['inicial'];
      if (ini is List && ini.isNotEmpty) {
        await Future.delayed(const Duration(milliseconds: 350));
        if (mounted) await revelarCartas(context, ini, titulo: 'Seu pacote inicial!');
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  List<Map<String, dynamic>> get _cartas => ((_d?['cartas'] as List?) ?? const []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList();

  Map<String, dynamic>? _carta(String? tk) => tk == null ? null : _cartas.where((c) => c['tk'] == tk).firstOrNull;

  Future<void> _abrir(Map<String, dynamic> c) async {
    final r = await Navigator.of(context).push<Map<String, dynamic>>(PageRouteBuilder(
      transitionDuration: const Duration(milliseconds: 380),
      pageBuilder: (_, __, ___) => DetalheCartaTela(api: widget.api, carta: c, colecao: _d!),
      transitionsBuilder: (_, a, __, f) =>
          FadeTransition(opacity: a, child: ScaleTransition(scale: Tween(begin: 0.92, end: 1.0).animate(CurvedAnimation(parent: a, curve: Curves.easeOutBack)), child: f)),
    ));
    if (r != null && mounted) {
      setState(() {
        _d = r;
        _acabouDeEquipar = (r['equipar'] as Map?)?['tk'] as String?;
      });
    } else {
      _carregar();
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        SafeArea(
          child: d == null
              ? Center(
                  child: _erro == null
                      ? const Padding(
                          padding: EdgeInsets.all(14),
                          child: Column(children: [
                            Esqueleto(altura: 52, raio: 16),
                            SizedBox(height: 12),
                            Expanded(child: Esqueleto(raio: 16)),
                          ]),
                        )
                      : Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(mainAxisSize: MainAxisSize.min, children: [
                            Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
                            const SizedBox(height: 12),
                            FilledButton(onPressed: _carregar, child: const Text('Tentar de novo')),
                          ]),
                        ),
                )
              : RefreshIndicator(
                  onRefresh: _carregar,
                  child: CustomScrollView(slivers: [
                    SliverToBoxAdapter(child: _topo(d)),
                    SliverToBoxAdapter(child: _equipadas(d)),
                    SliverToBoxAdapter(child: _filtros(d)),
                    _grade(),
                    const SliverToBoxAdapter(child: SizedBox(height: 30)),
                  ]),
                ),
        ),
      ]),
    );
  }

  Widget _topo(Map d) => Padding(
        padding: const EdgeInsets.fromLTRB(6, 6, 14, 4),
        child: Row(children: [
          IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
          const Expanded(
            child: Text('COLEÇÃO',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xCC0B2C5E), border: Border.all(color: const Color(0xFFFFC93C), width: 1.5)),
            child: Text('${d['descobertas']}/${d['total']} descobertas', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: Color(0xFFFFE08A))),
          ),
        ]),
      );

  // ---- Baralho: lista de até equip_max cartas, com teto só para épica e lendária
  Widget _equipadas(Map d) {
    final eq = ((d['equip'] as List?) ?? const []).map((e) => '$e').toList();
    final nMax = (d['equip_max'] as num?)?.toInt() ?? 5;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 4),
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 10, 10, 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFF4F88E6), width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xE6134188), Color(0xE60B2C5E)]),
          boxShadow: const [BoxShadow(color: Color(0x664F88E6), blurRadius: 14)],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.shield_rounded, color: Color(0xFFFFC93C), size: 22),
            SizedBox(width: 6),
            Text('Equipadas', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
            Spacer(),
            Text('máx 1 Épica e 1 Lendária · vão para o Ticker Battle', style: TextStyle(fontSize: 11, color: Color(0xFFB5C8E6))),
          ]),
          const SizedBox(height: 10),
          LayoutBuilder(builder: (ctx, cc) {
            final w = (cc.maxWidth - (nMax - 1) * 6) / nMax;
            return Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              for (var i = 0; i < nMax; i++) _slot(i < eq.length ? eq[i] : null, w),
            ]);
          }),
        ]),
      ),
    );
  }

  Widget _slot(String? tk, double w) {
    final c = _carta(tk);
    final rar = c == null ? 'comum' : '${c['raridade']}';
    final (cor, clara, _) = coresRaridade[rar] ?? coresRaridade['comum']!;
    final novo = tk != null && tk == _acabouDeEquipar;
    Widget conteudo = c == null
        ? Container(
            width: w,
            height: CartaTk.alturaPara(w),
            decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(w * 0.08), color: const Color(0x55081A3D), border: Border.all(color: const Color(0x884F88E6), width: 2)),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.add_rounded, color: const Color(0xFF8FB4F0), size: w * 0.35),
              const Text('Vazio', style: TextStyle(fontSize: 10, color: Color(0xFFB5C8E6))),
            ]),
          )
        : CartaTk(tk: tk!, largura: w, dados: c, valores: _vals(c['jogo']));
    if (novo) {
      conteudo = TweenAnimationBuilder<double>(
        key: ValueKey('eq-$tk'),
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 900),
        builder: (ctx, v, f) => Transform.scale(
          scale: 1 + 0.18 * sin(v * pi) * (1 - v),
          child: DecoratedBox(
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(w * 0.08), boxShadow: [BoxShadow(color: cor.withValues(alpha: (1 - v) * 0.9), blurRadius: 24, spreadRadius: 4)]),
            child: f,
          ),
        ),
        child: conteudo,
      );
    }
    return Column(children: [
      Pressionavel(aoTocar: c == null ? () => setState(() => _rar = null) : () => _abrir(c), child: conteudo),
      const SizedBox(height: 4),
      Text(c == null ? '—' : nomesRaridade[rar]!, style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: c == null ? const Color(0xFF8FB4F0) : clara)),
    ]);
  }

  // ---- filtros por raridade e setor
  Widget _filtros(Map d) {
    final setores = ((d['setores'] as List?) ?? const []).cast<String>();
    Widget chip(String? r, String txt) {
      final sel = _rar == r;
      final cor = r == null ? const Color(0xFF6399F0) : coresRaridade[r]!.$1;
      return Padding(
        padding: const EdgeInsets.only(right: 6),
        child: Pressionavel(
          aoTocar: () => setState(() => _rar = r),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              color: sel ? cor.withValues(alpha: 0.35) : const Color(0xAA0B2C5E),
              border: Border.all(color: cor, width: sel ? 2 : 1.2),
              boxShadow: sel ? [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 10)] : null,
            ),
            child: Text(txt, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: sel ? Colors.white : const Color(0xFFD4E2F7))),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 6),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(children: [chip(null, 'Todas'), for (final r in ordemRaridade) chip(r, nomesRaridade[r]!)]),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0xCC0B2C5E), border: Border.all(color: const Color(0x806399F0))),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String?>(
              value: _setor,
              isExpanded: true,
              dropdownColor: const Color(0xFF0E2A5C),
              iconEnabledColor: Colors.white,
              style: const TextStyle(fontSize: 14, color: Colors.white, fontWeight: FontWeight.w700),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('Todos os setores')),
                for (final s in setores) DropdownMenuItem<String?>(value: s, child: Text(s)),
              ],
              onChanged: (v) => setState(() => _setor = v),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _grade() {
    final lista = _cartas.where((c) => (_rar == null || c['raridade'] == _rar) && (_setor == null || c['setor'] == _setor)).toList();
    if (lista.isEmpty) {
      return const SliverToBoxAdapter(
        child: Padding(padding: EdgeInsets.all(30), child: Text('Nenhuma carta com esses filtros.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white))),
      );
    }
    return SliverPadding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      sliver: SliverLayoutBuilder(builder: (ctx, cs) {
        final cols = cs.crossAxisExtent > 700 ? 5 : (cs.crossAxisExtent > 480 ? 4 : 3);
        final w = (cs.crossAxisExtent - (cols - 1) * 10) / cols;
        return SliverGrid(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: cols, mainAxisSpacing: 12, crossAxisSpacing: 10, childAspectRatio: w / (CartaTk.alturaPara(w) + 30)),
          delegate: SliverChildBuilderDelegate((ctx, i) => Entrada(ordem: i % 9, child: _item(lista[i], w)), childCount: lista.length),
        );
      }),
    );
  }

  Widget _item(Map<String, dynamic> c, double w) {
    final tem = c['possui'] == true;
    if (!tem) {
      return Column(children: [
        CartaTk(tk: '${c['tk']}', largura: w, silhueta: true, dados: c),
        const SizedBox(height: 4),
        const Text('Não descoberta', style: TextStyle(fontSize: 11, color: Color(0xFF8FA6C8))),
      ]);
    }
    final (cor, _, _) = coresRaridade[c['raridade']] ?? coresRaridade['comum']!;
    final precisa = (c['precisa'] as num?)?.toInt();
    final copias = ((c['copias'] as num?) ?? 0).toInt();
    final pode = c['pode'] == true;
    return Pressionavel(
      aoTocar: () => _abrir(c),
      child: Column(children: [
        Stack(clipBehavior: Clip.none, children: [
          pode
              ? Reflexo(raio: w * 0.07, child: CartaTk(tk: '${c['tk']}', largura: w, dados: c, valores: _vals(c['jogo'])))
              : CartaTk(tk: '${c['tk']}', largura: w, dados: c, valores: _vals(c['jogo'])),
          if (c['equipada'] == true)
            Positioned(
              bottom: 4,
              right: 4,
              child: Container(
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFFFFC93C), border: Border.all(color: Colors.white, width: 1.5)),
                child: const Icon(Icons.shield_rounded, size: 13, color: Color(0xFF0B2C5E)),
              ),
            ),
        ]),
        const SizedBox(height: 5),
        _Barra(
            valor: precisa == null ? 1 : (copias / max(precisa, 1)).clamp(0.0, 1.0),
            cor: pode ? const Color(0xFF26D07C) : cor,
            texto: precisa == null ? 'MÁX' : (pode ? 'EVOLUIR!  $copias/$precisa' : '$copias/$precisa')),
      ]),
    );
  }
}

Map<String, String> _vals(Object? m) => ((m as Map?) ?? const {}).map((k, v) => MapEntry('$k', '$v'));

class _Barra extends StatelessWidget {
  const _Barra({required this.valor, required this.cor, required this.texto});
  final double valor;
  final Color cor;
  final String texto;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 18,
        child: Stack(children: [
          Container(decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xCC081A3D), border: Border.all(color: cor.withValues(alpha: 0.6)))),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: valor),
            duration: const Duration(milliseconds: 700),
            curve: Curves.easeOutCubic,
            builder: (ctx, v, _) => FractionallySizedBox(
              widthFactor: v,
              child: Container(
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), gradient: LinearGradient(colors: [cor.withValues(alpha: 0.7), cor])),
              ),
            ),
          ),
          Center(child: Text(texto, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(blurRadius: 3)]))),
        ]),
      );
}

// ===================================================================================== detalhe

/// Detalhe da carta: carta grande, valores reais × atributos de jogo, progresso, histórico de melhorias, Evoluir e Equipar.
/// Devolve (pop) a coleção atualizada quando algo mudou.
class DetalheCartaTela extends StatefulWidget {
  const DetalheCartaTela({super.key, required this.api, required this.carta, required this.colecao});
  final Api api;
  final Map<String, dynamic> carta;
  final Map<String, dynamic> colecao;

  @override
  State<DetalheCartaTela> createState() => _DetalheCartaTelaState();
}

class _DetalheCartaTelaState extends State<DetalheCartaTela> with TickerProviderStateMixin {
  late Map<String, dynamic> _c = widget.carta;
  late Map<String, dynamic> _col = widget.colecao;
  Map<String, dynamic>? _mudou;
  bool _ocupado = false;
  late final AnimationController _evo = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800));
  late final AnimationController _giro = AnimationController(vsync: this, duration: const Duration(seconds: 12))..repeat();

  @override
  void dispose() {
    _evo.dispose();
    _giro.dispose();
    super.dispose();
  }

  String get _rar => coresRaridade.containsKey(_c['raridade']) ? '${_c['raridade']}' : 'comum';

  void _atualizar(Map<String, dynamic> r) {
    _mudou = r;
    _col = r;
    final novo = ((r['cartas'] as List?) ?? const []).cast<Map>().where((x) => x['tk'] == _c['tk']).firstOrNull;
    if (novo != null) _c = novo.cast<String, dynamic>();
  }

  void _aviso(String t, {bool ok = true}) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        backgroundColor: ok ? const Color(0xFF138A55) : const Color(0xFFB3263E),
        content: Text(t, style: const TextStyle(fontWeight: FontWeight.w700)),
      ));

  Future<void> _evoluir() async {
    final ind = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _EscolhaAtributo(carta: _c, bonus: ((_col['bonus'] as Map?) ?? const {}).cast<String, dynamic>()),
    );
    if (ind == null || !mounted) return;
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post('/cartas/evoluir', {'tk': _c['tk'], 'ind': ind});
      if (!mounted) return;
      setState(() => _atualizar(r));
      _evo.forward(from: 0);
    } catch (e) {
      if (mounted) _aviso(e.toString(), ok: false);
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  // Não há mais substituição: a carta entra se couber, e o servidor recusa com o motivo (baralho cheio ou teto da raridade).
  Future<void> _equipar() async {
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post('/cartas/equipar', {'tk': _c['tk']});
      if (!mounted) return;
      setState(() => _atualizar(r));
      _aviso('${_c['tk']} entrou no baralho!');
      await Future.delayed(const Duration(milliseconds: 450));
      if (mounted) Navigator.of(context).pop(_mudou);
    } catch (e) {
      if (mounted) _aviso(e.toString(), ok: false);
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _desequipar() async {
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post('/cartas/desequipar', {'tk': _c['tk']});
      if (mounted) setState(() => _atualizar(r));
    } catch (e) {
      if (mounted) _aviso(e.toString(), ok: false);
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final (cor, clara, _) = coresRaridade[_rar]!;
    final lend = _rar == 'lendaria';
    final larg = min(MediaQuery.of(context).size.width * 0.6, 280.0);
    final precisa = (_c['precisa'] as num?)?.toInt();
    final copias = ((_c['copias'] as num?) ?? 0).toInt();
    final pode = _c['pode'] == true;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.of(context).pop(_mudou);
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF0A2755),
        body: Stack(fit: StackFit.expand, children: [
          const FundoCidade(),
          SafeArea(
            child: ListView(padding: const EdgeInsets.fromLTRB(14, 4, 14, 24), children: [
              Row(children: [
                IconButton(onPressed: () => Navigator.of(context).pop(_mudou), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                Expanded(child: Text('${_c['nome']}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
              ]),
              const SizedBox(height: 6),
              // carta grande com raios (lendária: dourados e mais fortes) e explosão de evolução
              SizedBox(
                height: CartaTk.alturaPara(larg) + 20,
                child: AnimatedBuilder(
                  animation: Listenable.merge([_evo, _giro]),
                  builder: (ctx, _) {
                    final e = _evo.value;
                    final pico = e == 0 ? 0.0 : sin(min(e / 0.5, 1) * pi);
                    return Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
                      Transform.rotate(
                        angle: _giro.value * 2 * pi,
                        child: CustomPaint(size: Size.square(larg * (lend ? 2.0 : 1.6)), painter: _Raios(cor.withValues(alpha: (lend ? 0.4 : 0.18) + 0.4 * pico), lend ? 18 : 10)),
                      ),
                      Transform.scale(
                        scale: 1 + 0.08 * pico,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(larg * 0.07),
                            boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.35 + 0.6 * pico), blurRadius: 30 + 40 * pico, spreadRadius: 2 + 8 * pico)],
                          ),
                          child: CartaTk(tk: '${_c['tk']}', largura: larg, dados: _c, valores: _vals(_c['jogo'])),
                        ),
                      ),
                      if (e > 0 && e < 1)
                        Opacity(
                          opacity: (1 - max(0.0, (e - 0.6) / 0.4)).clamp(0.0, 1.0).toDouble(),
                          child: Transform.scale(
                            scale: Curves.elasticOut.transform(min(e / 0.6, 1.0)),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(999),
                                color: const Color(0xFF26D07C),
                                border: Border.all(color: Colors.white, width: 2.5),
                                boxShadow: [BoxShadow(color: cor, blurRadius: 24)],
                              ),
                              child: Text('NÍVEL ${_c['nivel']}!', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white)),
                            ),
                          ),
                        ),
                    ]);
                  },
                ),
              ),
              const SizedBox(height: 10),
              Center(
                child: Text('${nomesRaridade[_rar]} · Nível ${_c['nivel']} de ${_c['nivel_max']}', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: clara)),
              ),
              const SizedBox(height: 8),
              _Barra(
                  valor: precisa == null ? 1 : (copias / max(precisa, 1)).clamp(0.0, 1.0),
                  cor: pode ? const Color(0xFF26D07C) : cor,
                  texto: precisa == null ? 'Nível máximo' : 'Cópias: $copias/$precisa para o nível ${((_c['nivel'] as num?) ?? 1).toInt() + 1}'),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child:
                      _botao(pode ? 'EVOLUIR' : (precisa == null ? 'NÍVEL MÁXIMO' : 'FALTAM ${precisa - copias}'), Icons.upgrade_rounded, pode && !_ocupado ? _evoluir : null, const Color(0xFF26D07C)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _c['equipada'] == true
                      ? _botao('DESEQUIPAR', Icons.shield_outlined, _ocupado ? null : _desequipar, const Color(0xFF6399F0))
                      : _botao('EQUIPAR', Icons.shield_rounded, _ocupado ? null : _equipar, const Color(0xFFFFC93C)),
                ),
              ]),
              const SizedBox(height: 14),
              _valores(cor),
              const SizedBox(height: 12),
              _historico(cor),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _botao(String t, IconData ic, VoidCallback? f, Color cor) => Pressionavel(
        aoTocar: f,
        child: Opacity(
          opacity: f == null ? 0.5 : 1,
          child: Container(
            height: 50,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color.lerp(cor, Colors.white, 0.25)!, cor, Color.lerp(cor, Colors.black, 0.25)!]),
              border: Border.all(color: Colors.white.withValues(alpha: 0.8), width: 2),
              boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 12)],
            ),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(ic, color: Colors.white),
              const SizedBox(width: 6),
              Flexible(child: FittedBox(child: Text(t, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(blurRadius: 4)])))),
            ]),
          ),
        ),
      );

  Widget _quadro(Color cor, Widget child) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: cor.withValues(alpha: 0.8), width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xE6134188), Color(0xE60B2C5E)]),
        ),
        child: child,
      );

  Widget _valores(Color cor) {
    final real = ((_c['real'] as Map?) ?? const {}).cast<String, dynamic>();
    final jogo = ((_c['jogo'] as Map?) ?? const {}).cast<String, dynamic>();
    final mel = ((_c['melhorias'] as Map?) ?? const {}).cast<String, dynamic>();
    const nomes = {'pl': 'P/L', 'dy_12m': 'DY', 'roe': 'ROE'};
    TextStyle s(Color c, {bool b = false}) => TextStyle(fontSize: 13.5, color: c, fontWeight: b ? FontWeight.w900 : FontWeight.w600);
    return _quadro(
      cor,
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Dados reais × atributos de jogo', style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w900, color: Colors.white)),
        const SizedBox(height: 2),
        Text('Dados reais de ${_c['ref'] ?? '—'}. As melhorias valem só no jogo: o dado real nunca muda.', style: const TextStyle(fontSize: 11.5, color: Color(0xFFB5C8E6))),
        const SizedBox(height: 8),
        Table(columnWidths: const {
          0: FlexColumnWidth(1.1),
          1: FlexColumnWidth(1.2),
          2: FlexColumnWidth(1.2),
          3: FlexColumnWidth(1)
        }, children: [
          TableRow(children: [
            Text('', style: s(Colors.white)),
            Text('Real', style: s(const Color(0xFFB5C8E6), b: true)),
            Text('No jogo', style: s(const Color(0xFF8DF5C1), b: true)),
            Text('Melhorias', style: s(const Color(0xFFFFE08A), b: true)),
          ]),
          for (final k in nomes.keys)
            TableRow(children: [
              Padding(padding: const EdgeInsets.only(top: 6), child: Text(nomes[k]!, style: s(Colors.white, b: true))),
              Padding(padding: const EdgeInsets.only(top: 6), child: Text('${real[k] ?? '—'}', style: s(Colors.white))),
              Padding(padding: const EdgeInsets.only(top: 6), child: Text('${jogo[k] ?? '—'}', style: s(const Color(0xFF8DF5C1), b: true))),
              Padding(padding: const EdgeInsets.only(top: 6), child: Text('×${mel[k] ?? 0}', style: s(const Color(0xFFFFE08A)))),
            ]),
        ]),
      ]),
    );
  }

  Widget _historico(Color cor) {
    final esc = ((_c['escolhas'] as List?) ?? const []).cast<String>();
    const nomes = {'pl': 'P/L', 'dy_12m': 'DY', 'roe': 'ROE'};
    return _quadro(
      cor,
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Histórico de melhorias', style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w900, color: Colors.white)),
        const SizedBox(height: 6),
        if (esc.isEmpty)
          const Text('Nenhuma ainda. Junte cópias desta carta nos baús para evoluir e escolher o que melhorar.', style: TextStyle(fontSize: 13, color: Color(0xFFD4E2F7)))
        else
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (var i = 0; i < esc.length; i++)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xFF081A3D), border: Border.all(color: cor)),
                child: Text('Nv ${i + 2}: ${nomes[esc[i]] ?? esc[i]}', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: Colors.white)),
              ),
          ]),
        const SizedBox(height: 8),
        Text('Cópias já obtidas: ${_c['total'] ?? 1}', style: const TextStyle(fontSize: 12, color: Color(0xFFB5C8E6))),
      ]),
    );
  }
}

/// Escolha do atributo na evolução: 3 opções grandes; a escolhida pulsa e confirma.
class _EscolhaAtributo extends StatefulWidget {
  const _EscolhaAtributo({required this.carta, required this.bonus});
  final Map<String, dynamic> carta;
  final Map<String, dynamic> bonus;

  @override
  State<_EscolhaAtributo> createState() => _EscolhaAtributoState();
}

class _EscolhaAtributoState extends State<_EscolhaAtributo> {
  String? _sel;

  @override
  Widget build(BuildContext context) {
    final jogo = ((widget.carta['jogo'] as Map?) ?? const {}).cast<String, dynamic>();
    const ops = [
      ('pl', 'P/L', Icons.trending_up_rounded, Color(0xFF2EE59D), 'Preço/Lucro menor: a ação fica "mais barata" no jogo.'),
      ('dy_12m', 'DY', Icons.monetization_on_rounded, Color(0xFFFFC93C), 'Dividendos maiores no jogo.'),
      ('roe', 'ROE', Icons.insights_rounded, Color(0xFFC07BFF), 'Rentabilidade maior no jogo.'),
    ];
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 22),
      decoration: const BoxDecoration(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF134188), Color(0xFF081A3D)]),
        border: Border(top: BorderSide(color: Color(0xFFFFC93C), width: 2)),
      ),
      child: SafeArea(
        top: false,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('O que melhorar?', textAlign: TextAlign.center, style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: Colors.white)),
          const SizedBox(height: 4),
          const Text('A escolha é permanente e soma com as próximas evoluções.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, color: Color(0xFFB5C8E6))),
          const SizedBox(height: 12),
          for (final (id, nome, ic, cor, txt) in ops)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Pressionavel(
                aoTocar: () => setState(() => _sel = id),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    color: _sel == id ? cor.withValues(alpha: 0.22) : const Color(0xCC0B2C5E),
                    border: Border.all(color: cor, width: _sel == id ? 3 : 1.5),
                    boxShadow: _sel == id ? [BoxShadow(color: cor.withValues(alpha: 0.6), blurRadius: 18)] : null,
                  ),
                  child: Row(children: [
                    AnimatedScale(scale: _sel == id ? 1.2 : 1, duration: const Duration(milliseconds: 300), curve: Curves.elasticOut, child: Icon(ic, size: 36, color: cor)),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('$nome  ·  ${widget.bonus[id] ?? ''}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                        Text('Agora no jogo: ${jogo[id] ?? '—'}. $txt', style: const TextStyle(fontSize: 12.5, color: Color(0xFFD4E2F7))),
                      ]),
                    ),
                    if (_sel == id) const Icon(Icons.check_circle_rounded, color: Colors.white),
                  ]),
                ),
              ),
            ),
          const SizedBox(height: 4),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF26D07C), minimumSize: const Size.fromHeight(50), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
            onPressed: _sel == null ? null : () => Navigator.pop(context, _sel),
            child: const Text('CONFIRMAR EVOLUÇÃO', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
          ),
        ]),
      ),
    );
  }
}

class _Raios extends CustomPainter {
  _Raios(this.cor, this.n);
  final Color cor;
  final int n;

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 2;
    final p = Paint()..shader = RadialGradient(colors: [cor, cor.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: r));
    for (var i = 0; i < n; i++) {
      final a = 2 * pi * i / n;
      canvas.drawPath(
        Path()
          ..moveTo(c.dx, c.dy)
          ..lineTo(c.dx + r * cos(a - 0.08), c.dy + r * sin(a - 0.08))
          ..lineTo(c.dx + r * cos(a + 0.08), c.dy + r * sin(a + 0.08))
          ..close(),
        p,
      );
    }
  }

  @override
  bool shouldRepaint(_Raios o) => o.cor != cor || o.n != n;
}
