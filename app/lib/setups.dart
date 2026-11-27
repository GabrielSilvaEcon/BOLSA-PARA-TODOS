import 'dart:math';

import 'package:flutter/material.dart';

import 'api.dart';
import 'carta_setup.dart';
import 'cartas.dart' show coresRaridade, rotulosRaridade;

/// Setups colecionáveis. Tudo vem do servidor (`GET /setups`): a tela só mostra o que a pessoa conquistou e deixa equipar um.
/// A arte de cada setup mora em assets/setups/<id>/ (o servidor já manda o caminho só quando o arquivo existe); sem arte, entra o
/// espaço provisório, claramente marcado, e nunca uma arte inventada.

/// Ícone provisório de cada setup (desenhado em código até a arte final).
IconData iconeDoSetup(String id) => _iconeDe(id);

IconData _iconeDe(String id) => switch (id) {
      'larry_williams' => Icons.bolt,
      'turtle_trading' => Icons.waves,
      'mark_minervini' => Icons.rocket_launch,
      'martelo' => Icons.vertical_align_bottom,
      'engolfo_alta' => Icons.stacked_bar_chart,
      'estrela_cadente' => Icons.star_border,
      _ => Icons.ssid_chart,
    };

Color _corDe(Map s) => (coresRaridade[s['raridade']] ?? coresRaridade['comum']!).$1;

/// Carta do setup: a arte enviada, ou o espaço provisório (marcado) quando ela ainda não existe ou não carrega.
class SetupCarta extends StatelessWidget {
  const SetupCarta({super.key, required this.setup, this.largura = 150});
  final Map<String, dynamic> setup;
  final double largura;

  /// A carta (frente) com a arte da raridade, o desenho do padrão e os textos do cadastro. Para virar ao toque, use [CartaGirando].
  @override
  Widget build(BuildContext context) => CartaSetup(setup: setup, largura: largura);
}

/// Aviso de setup novo vindo de um baú.
Future<void> revelarSetup(BuildContext context, Map<String, dynamic> setup, {VoidCallback? abrirMeusSetups, String titulo = 'NOVA CARTA DE SETUP!'}) {
  final cor = _corDe(setup);
  return showDialog<void>(
    context: context,
    barrierColor: const Color(0xE6030A1C),
    builder: (ctx) => Dialog(
      backgroundColor: const Color(0xFF10274A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: cor, width: 1.5)),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(titulo, style: TextStyle(color: Color(0xFFFFD76A), fontWeight: FontWeight.w900, fontSize: 16)),
            const SizedBox(height: 12),
            CartaGirando(setup: setup, largura: 230),
            const SizedBox(height: 10),
            Text('${setup['nome']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18)),
            Text(rotulosRaridade[setup['raridade']] ?? '', style: TextStyle(color: cor, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            const Text('Com esta carta você já pode usar o setup. Equipe em Meus Setups (até 2) para usar nas partidas X1 e solo.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 12.5)),
            const SizedBox(height: 14),
            Row(children: [
              Expanded(child: OutlinedButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('OK'))),
              if (abrirMeusSetups != null) ...[
                const SizedBox(width: 8),
                Expanded(
                    child: FilledButton(
                        onPressed: () {
                          Navigator.of(ctx).pop();
                          abrirMeusSetups();
                        },
                        child: const Text('Meus Setups'))),
              ],
            ]),
          ],
        ),
      ),
    ),
  );
}

/// "Meus Setups": as cartas de setup que a pessoa tem, as características de cada uma e quais estão equipadas (até 2; valem sozinhas nas partidas X1 e solo).
class SetupsTela extends StatefulWidget {
  const SetupsTela({super.key, required this.api});
  final Api api;

  @override
  State<SetupsTela> createState() => _SetupsTelaState();
}

class _SetupsTelaState extends State<SetupsTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String? _salvando;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/setups');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = 'Não foi possível carregar seus setups agora.');
    }
  }

  bool get _liberados => _d?['todos_liberados'] == true;
  int get _limite => ((_d?['limite'] as num?) ?? 2).toInt();
  int get _nEquipados => (_d?['equipados'] as List? ?? []).length;

  Future<void> _equipar(String id, {bool tirar = false}) async {
    if (_salvando != null) return;
    setState(() => _salvando = id);
    try {
      await widget.api.post(tirar ? '/setups/desequipar' : '/setups/equipar', {'id': id});
      await _carregar();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().contains('Desequipe') ? 'Você já está usando $_limite setups. Desequipe um para equipar outro.' : 'Não foi possível salvar agora. Tente de novo.')));
      }
    } finally {
      if (mounted) setState(() => _salvando = null);
    }
  }

  void _detalhe(Map<String, dynamic> s) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF10274A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, set) {
          final atual = (_d?['itens'] as List? ?? []).cast<Map>().firstWhere((x) => x['id'] == s['id'], orElse: () => s);
          final equipado = atual['equipado'] == true;
          final cheio = !equipado && _nEquipados >= _limite;
          return DraggableScrollableSheet(
            expand: false,
            initialChildSize: .9,
            maxChildSize: .95,
            builder: (_, rolagem) => ListView(
              controller: rolagem,
              padding: const EdgeInsets.fromLTRB(18, 18, 18, 28),
              children: [
                Center(child: CartaGirando(setup: {...s, 'equipado': equipado}, largura: min(340.0, MediaQuery.of(context).size.width - 56))),
                const SizedBox(height: 12),
                Text('${s['nome']}', textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 20)),
                Text(rotulosRaridade[s['raridade']] ?? '', textAlign: TextAlign.center, style: TextStyle(color: _corDe(s), fontWeight: FontWeight.w800)),
                if ('${s['resumo']}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text('${s['resumo']}', style: const TextStyle(color: Colors.white70, height: 1.35))),
                if ('${s['fonte_regra'] ?? ''}'.isNotEmpty)
                  Padding(padding: const EdgeInsets.only(top: 8), child: Text('${s['fonte_regra']}', style: const TextStyle(color: Colors.white54, fontStyle: FontStyle.italic, fontSize: 11.5, height: 1.3))),
                _bloco('Como entra', [if ('${(s['regra'] as Map)['compra']}'.isNotEmpty) 'Compra: ${(s['regra'] as Map)['compra']}', if ('${(s['regra'] as Map)['venda']}'.isNotEmpty) 'Venda: ${(s['regra'] as Map)['venda']}']),
                _bloco('Características', (s['caracteristicas'] as List).map((e) => '$e').toList()),
                _bloco('Indicadores', (s['indicadores'] as List).map((e) => '$e').toList()),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _salvando != null || cheio
                      ? null
                      : () async {
                          await _equipar('${s['id']}', tirar: equipado);
                          set(() {});
                        },
                  child: Text(equipado ? 'DESEQUIPAR' : (cheio ? 'DESEQUIPE UM SETUP PRIMEIRO' : 'USAR ESTE SETUP')),
                ),
                const SizedBox(height: 6),
                Text(_liberados
                    ? 'Você pode usar até $_limite setups ao mesmo tempo. Eles são usados automaticamente nas partidas X1 e solo, sem escolher antes de cada partida.'
                    : 'Você pode usar até $_limite setups ao mesmo tempo, só os das cartas que você tem. Eles são usados automaticamente nas partidas X1 e solo, sem escolher antes de cada partida.',
                    textAlign: TextAlign.center, style: TextStyle(color: Colors.white54, fontSize: 11.5)),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _bloco(String titulo, List<String> linhas) {
    if (linhas.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(titulo.toUpperCase(), style: const TextStyle(color: Color(0xFFFFD76A), fontWeight: FontWeight.w900, fontSize: 12, letterSpacing: .8)),
        const SizedBox(height: 4),
        for (final l in linhas) Padding(padding: const EdgeInsets.only(top: 3), child: Text('• $l', style: const TextStyle(color: Colors.white, height: 1.3))),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final itens = (d?['itens'] as List? ?? []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList();
    final total = ((d?['total'] as num?) ?? 0).toInt();
    return Scaffold(
      backgroundColor: const Color(0xFF0C192E),
      appBar: AppBar(backgroundColor: const Color(0xFF0C192E), title: const Text('Meus Setups')),
      body: _erro != null
          ? Center(child: Text(_erro!, style: const TextStyle(color: Colors.white70)))
          : d == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(_liberados ? '${itens.length} setups disponíveis · $_nEquipados/$_limite equipados' : '${itens.length} de $total cartas de setup · $_nEquipados/$_limite equipados', style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Text(
                        _liberados
                            ? 'Por enquanto todos os setups estão liberados: escolha até 2 para serem monitorados em tempo real nas suas partidas X1 e solo (menos no Desafio do dia, que é igual para todos).'
                            : 'As cartas de setup vêm dos baús. Sem a carta, não há setup para usar. Equipe até 2 para serem monitorados em tempo real nas suas partidas X1 e solo (menos no Desafio do dia, que é igual para todos).',
                        style: const TextStyle(color: Colors.white54, fontSize: 12.5)),
                    const SizedBox(height: 14),
                    if (itens.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(color: const Color(0xFF10274A), borderRadius: BorderRadius.circular(14)),
                        child: const Text('Você ainda não tem nenhuma carta de setup. Abra baús na Loja para tentar.', style: TextStyle(color: Colors.white70)),
                      )
                    else
                      Wrap(
                        spacing: 14,
                        runSpacing: 18,
                        alignment: WrapAlignment.center,
                        children: [
                          for (final s in itens)
                            GestureDetector(
                              onTap: () => _detalhe(s),
                              child: Column(children: [
                                Stack(children: [
                                  SetupCarta(setup: s, largura: 168),
                                  if (s['equipado'] == true)
                                    Positioned(
                                        top: 6,
                                        left: 6,
                                        child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                            decoration: BoxDecoration(color: const Color(0xFF2EE59D), borderRadius: BorderRadius.circular(8)),
                                            child: const Text('EQUIPADO', style: TextStyle(color: Color(0xFF04281a), fontWeight: FontWeight.w900, fontSize: 10)))),
                                ]),
                                const SizedBox(height: 6),
                                Text('${s['nome']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                              ]),
                            ),
                        ],
                      ),
                    if (!_liberados && itens.length < total) ...[
                      const SizedBox(height: 22),
                      Center(child: Text('${total - itens.length} ainda para descobrir', style: const TextStyle(color: Colors.white38, fontWeight: FontWeight.w700))),
                    ],
                  ],
                ),
    );
  }
}


/// Escolha dos setups da partida (pop-up "Escolher setup"): as cartas com filtros, o detalhe da carta (direção, região, condições, stop e alvo)
/// e o botão de confirmar. Vale até o limite de espaços (2); o que for confirmado entra sozinho nas partidas X1 e solo, sem escolher a cada partida.
/// `aoMudar` recebe a lista nova do servidor.
Future<void> escolherSetups(BuildContext context, Api api, {Map<String, dynamic>? inicial, void Function(Map<String, dynamic> novo)? aoMudar}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: const Color(0xFF081A3C),
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
    builder: (ctx) => _EscolhaSetups(api: api, inicial: inicial, aoMudar: aoMudar),
  );
}

const _filtros = [('todos', 'Todos', Icons.grid_view_rounded), ('compra', 'Compra', Icons.arrow_upward_rounded), ('venda', 'Venda', Icons.arrow_downward_rounded), ('candle', 'Padrões de candle', Icons.candlestick_chart_rounded), ('estrategia', 'Estratégias', Icons.show_chart_rounded)];

String _rotuloDirecao(String d) => switch (d) { 'venda' => 'Venda', 'ambos' => 'Compra ou venda', _ => 'Compra' };
Color _corDirecao(String d) => switch (d) { 'venda' => const Color(0xFFFF6B86), 'ambos' => const Color(0xFFC79BFF), _ => const Color(0xFF3DFFB0) };
IconData _iconeDirecao(String d) => switch (d) { 'venda' => Icons.arrow_downward_rounded, 'ambos' => Icons.swap_vert_rounded, _ => Icons.arrow_upward_rounded };

class _EscolhaSetups extends StatefulWidget {
  const _EscolhaSetups({required this.api, this.inicial, this.aoMudar});
  final Api api;
  final Map<String, dynamic>? inicial;
  final void Function(Map<String, dynamic> novo)? aoMudar;

  @override
  State<_EscolhaSetups> createState() => _EscolhaSetupsState();
}

class _EscolhaSetupsState extends State<_EscolhaSetups> {
  Map<String, dynamic>? _d;
  Set<String> _sel = {}; // o que o jogador marcou (só vale ao confirmar)
  String _filtro = 'todos';
  String? _foco; // a carta aberta no detalhe
  bool _salvando = false;

  @override
  void initState() {
    super.initState();
    _aplicar(widget.inicial);
    _recarregar();
  }

  void _aplicar(Map<String, dynamic>? d) {
    _d = d;
    if (d != null && _sel.isEmpty) {
      _sel = {for (final x in (d['itens'] as List? ?? const []).cast<Map>()) if (x['equipado'] == true) '${x['id']}'};
    }
  }

  Future<void> _recarregar() async {
    try {
      final r = await widget.api.get('/setups');
      if (mounted) setState(() => _aplicar(r));
    } catch (_) {}
  }

  int get _limite => ((_d?['limite'] as num?) ?? 2).toInt();
  List<Map<String, dynamic>> get _itens => ((_d?['itens'] as List?) ?? const []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList();

  bool _passa(Map<String, dynamic> s) => switch (_filtro) {
        'compra' => s['direcao'] == 'compra' || s['direcao'] == 'ambos',
        'venda' => s['direcao'] == 'venda' || s['direcao'] == 'ambos',
        'candle' => s['tipo'] == 'candle',
        'estrategia' => s['tipo'] != 'candle',
        _ => true,
      };

  void _tocar(Map<String, dynamic> s) {
    final id = '${s['id']}';
    setState(() {
      _foco = id;
      if (_sel.contains(id)) {
        _sel.remove(id);
      } else if (_sel.length >= _limite) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Você pode ativar até $_limite setups por partida. Toque em um ativo para tirar e escolher outro.')));
      } else {
        _sel.add(id);
      }
    });
  }

  Future<void> _confirmar() async {
    if (_salvando) return;
    setState(() => _salvando = true);
    try {
      var r = _d ?? const <String, dynamic>{};
      final atuais = {for (final x in _itens) if (x['equipado'] == true) '${x['id']}'};
      for (final id in atuais.difference(_sel)) {
        r = await widget.api.post('/setups/desequipar', {'id': id}); // primeiro tira, para sempre haver espaço
      }
      for (final id in _sel.difference(atuais)) {
        r = await widget.api.post('/setups/equipar', {'id': id});
      }
      widget.aoMudar?.call(r);
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        setState(() => _salvando = false);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Não foi possível salvar agora. Tente de novo.')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final todos = _itens;
    final lista = todos.where(_passa).toList();
    final foco = todos.where((x) => '${x['id']}' == _foco).firstOrNull ?? (lista.isNotEmpty ? lista.first : null);
    return LayoutBuilder(builder: (ctx, c) {
      final largo = c.maxWidth >= 760;
      final grade = _grade(lista, largo ? 4 : 2, c.maxWidth - (largo ? 330 : 0) - 32);
      final detalhe = foco == null ? const SizedBox.shrink() : _Detalhe(setup: foco, ativo: _sel.contains('${foco['id']}'));
      return Column(children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
            children: [
              _cabecalho(),
              const SizedBox(height: 10),
              _dica(),
              const SizedBox(height: 12),
              SizedBox(
                height: 38,
                child: ListView(scrollDirection: Axis.horizontal, children: [for (final f in _filtros) _chip(f.$1, f.$2, f.$3)]),
              ),
              const SizedBox(height: 12),
              if (_d == null)
                const Center(child: Padding(padding: EdgeInsets.all(30), child: CircularProgressIndicator()))
              else if (largo)
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: grade), const SizedBox(width: 14), SizedBox(width: 316, child: detalhe)])
              else ...[grade, const SizedBox(height: 14), detalhe],
            ],
          ),
        ),
        _rodape(),
      ]);
    });
  }

  Widget _cabecalho() => Row(children: [
        const Icon(Icons.style_rounded, size: 40, color: Color(0xFF4FC3FF)),
        const SizedBox(width: 12),
        const Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('ESCOLHER SETUP', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white, letterSpacing: .5)),
            Text('Selecione as cartas que deseja ativar para esta partida. O setup é monitorado durante o jogo e, quando as condições forem atendidas, você é avisado.',
                style: TextStyle(fontSize: 12, height: 1.3, color: Color(0xFF8FD0FF))),
          ]),
        ),
        IconButton(onPressed: () => Navigator.of(context).pop(), icon: const Icon(Icons.close_rounded, color: Colors.white)),
      ]);

  Widget _dica() => Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x554FC3FF)), color: const Color(0x66102A5A)),
        child: const Row(children: [
          Icon(Icons.gps_fixed, size: 26, color: Color(0xFF4FC3FF)),
          SizedBox(width: 10),
          Expanded(
            child: Text('Dica: os padrões de candle só ativam em regiões que VOCÊ marcar (suporte ou resistência) na estratégia, antes da batalha. Marque as suas para aumentar as chances.',
                style: TextStyle(fontSize: 12, height: 1.3, color: Color(0xFFCFE3FF))),
          ),
        ]),
      );

  Widget _chip(String id, String rotulo, IconData ic) {
    final on = _filtro == id;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: GestureDetector(
        onTap: () => setState(() => _filtro = id),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: on ? const Color(0xFF3DFFB0) : const Color(0xFF2F5FA8)),
            color: on ? const Color(0xFF16A06A) : const Color(0x990A2250),
          ),
          child: Row(children: [
            Icon(ic, size: 17, color: on ? Colors.white : const Color(0xFF8FB4F0)),
            const SizedBox(width: 6),
            Text(rotulo, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: on ? Colors.white : const Color(0xFFB9D0F5))),
          ]),
        ),
      ),
    );
  }

  Widget _grade(List<Map<String, dynamic>> lista, int colunas, double largura) {
    if (lista.isEmpty) return const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('Nenhum setup neste filtro.', style: TextStyle(color: Color(0xFFB9D0F5)))));
    const gap = 10.0;
    final w = (largura - gap * (colunas - 1)) / colunas;
    return Wrap(spacing: gap, runSpacing: gap, children: [for (final s in lista) SizedBox(width: w, child: _CartaEscolha(setup: s, marcado: _sel.contains('${s['id']}'), foco: _foco == '${s['id']}', aoTocar: () => _tocar(s)))]);
  }

  Widget _rodape() => Container(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
        decoration: const BoxDecoration(color: Color(0xFF0A2250), border: Border(top: BorderSide(color: Color(0x554FC3FF)))),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            const Icon(Icons.info_outline_rounded, size: 16, color: Color(0xFF8FB4F0)),
            const SizedBox(width: 8),
            Expanded(child: Text('Você pode ativar até $_limite setups por partida. Ativos: ${_sel.length}/$_limite.', style: const TextStyle(fontSize: 12, color: Color(0xFFB9D0F5)))),
          ]),
          const SizedBox(height: 8),
          FilledButton.icon(
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48), backgroundColor: const Color(0xFF1F6FEB)),
            onPressed: _salvando || _d == null ? null : _confirmar,
            icon: _salvando ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.check_rounded),
            label: const Text('Confirmar setup', style: TextStyle(fontWeight: FontWeight.w900)),
          ),
        ]),
      );
}

/// Uma carta da grade do "Escolher setup": a carta nova (arte da raridade e desenho do padrão) com a direção e a região embaixo.
/// Borda e brilho na cor do setup quando marcada ou aberta no detalhe; ✓ quando marcada.
class _CartaEscolha extends StatelessWidget {
  const _CartaEscolha({required this.setup, required this.marcado, required this.foco, required this.aoTocar});
  final Map<String, dynamic> setup;
  final bool marcado, foco;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final cor = _hex((setup['cores'] as Map?)?['principal']);
    final dir = '${setup['direcao']}';
    return LayoutBuilder(builder: (ctx, c) {
      final w = c.maxWidth;
      final raio = BorderRadius.circular(w * 0.06);
      return GestureDetector(
        onTap: aoTocar,
        behavior: HitTestBehavior.opaque,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Stack(children: [
            DecoratedBox(
              position: DecorationPosition.foreground,
              decoration: BoxDecoration(borderRadius: raio, border: marcado || foco ? Border.all(color: cor, width: 3) : null),
              child: DecoratedBox(
                decoration: BoxDecoration(borderRadius: raio, boxShadow: marcado ? [BoxShadow(color: cor.withValues(alpha: .6), blurRadius: 14)] : null),
                child: SetupCarta(setup: setup, largura: w),
              ),
            ),
            if (marcado)
              Positioned(
                top: w * 0.05,
                left: w * 0.05,
                child: Container(width: 24, height: 24, decoration: BoxDecoration(shape: BoxShape.circle, color: cor), child: const Icon(Icons.check_rounded, size: 17, color: Color(0xFF04281A))),
              ),
          ]),
          const SizedBox(height: 6),
          _linha(_iconeDirecao(dir), _rotuloDirecao(dir), _corDirecao(dir)),
          const SizedBox(height: 4),
          _linha(Icons.crop_free_rounded, '${setup['regiao']}', const Color(0xFFE6DCA8)),
        ]),
      );
    });
  }

  Widget _linha(IconData ic, String t, Color c) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), color: const Color(0x66000000)),
        child: Row(children: [
          Icon(ic, size: 14, color: c),
          const SizedBox(width: 5),
          Expanded(child: Text(t, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: Colors.white))),
        ]),
      );
}

Widget _selo(String t, Color cor) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), border: Border.all(color: cor), color: const Color(0x66000000)),
      child: Text(t, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: cor, letterSpacing: .4)),
    );

Color _hex(Object? v) {
  final m = RegExp(r'^#([0-9a-fA-F]{6})$').firstMatch('$v');
  return m == null ? const Color(0xFF8FB4F0) : Color(0xFF000000 | int.parse(m.group(1)!, radix: 16));
}

/// O detalhe da carta aberta: miniatura do padrão, direção, região obrigatória, condições, stop e alvo (tudo do cadastro do setup).
class _Detalhe extends StatelessWidget {
  const _Detalhe({required this.setup, required this.ativo});
  final Map<String, dynamic> setup;
  final bool ativo;

  @override
  Widget build(BuildContext context) {
    final cor = _hex((setup['cores'] as Map?)?['principal']);
    final dir = '${setup['direcao']}';
    final cond = ((setup['caracteristicas'] as List?) ?? const []).map((e) => '$e').toList();
    final exigeRegiao = setup['tipo'] == 'candle';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), border: Border.all(color: cor, width: 2), color: const Color(0xCC071634), boxShadow: [BoxShadow(color: cor.withValues(alpha: .35), blurRadius: 14)]),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(child: Text('${setup['nome']}'.toUpperCase(), style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white))),
          _selo('${rotulosRaridade[setup['raridade']] ?? ''}', cor),
        ]),
        Text('${setup['subtitulo']}', style: const TextStyle(fontSize: 12, color: Color(0xFFB9D0F5))),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox(height: 120, child: CustomPaint(painter: _MiniPadrao('${setup['id']}', cor), child: exigeRegiao ? null : Center(child: Icon(iconeDoSetup('${setup['id']}'), size: 54, color: cor.withValues(alpha: .9))))),
        ),
        const SizedBox(height: 10),
        _item(_iconeDirecao(dir), 'DIREÇÃO', _rotuloDirecao(dir), _corDirecao(dir)),
        _item(Icons.crop_free_rounded, exigeRegiao ? 'REGIÃO OBRIGATÓRIA' : 'REGIÃO', '${setup['regiao']}', const Color(0xFFE6DCA8)),
        _item(Icons.tune_rounded, 'CONDIÇÕES DO SETUP', cond.take(4).map((e) => '• $e').join('\n'), const Color(0xFF8FD0FF)),
        _item(Icons.shield_outlined, 'STOP', '${setup['stop_texto']}', const Color(0xFFFF6B86)),
        _item(Icons.gps_fixed, 'ALVO', '${setup['alvo_texto']}', const Color(0xFF3DFFB0)),
        if ('${setup['fonte_regra'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text('${setup['fonte_regra']}', style: const TextStyle(fontSize: 10.5, fontStyle: FontStyle.italic, color: Color(0xFF8F9FC4)))),
        if (ativo) const Padding(padding: EdgeInsets.only(top: 8), child: Text('✓ Marcado para esta partida', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.w900, color: Color(0xFF3DFFB0)))),
      ]),
    );
  }

  Widget _item(IconData ic, String t, String v, Color c) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(width: 34, height: 34, decoration: BoxDecoration(borderRadius: BorderRadius.circular(10), border: Border.all(color: c.withValues(alpha: .7)), color: const Color(0x66000000)), child: Icon(ic, size: 19, color: c)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: .6, color: Color(0xFF8FB4F0))),
              Text(v, style: const TextStyle(fontSize: 12.5, height: 1.3, fontWeight: FontWeight.w600, color: Colors.white)),
            ]),
          ),
        ]),
      );
}

/// Miniatura do padrão de candle (desenhada em código): candles, a região marcada em amarelo e o candle do padrão destacado.
class _MiniPadrao extends CustomPainter {
  _MiniPadrao(this.id, this.cor);
  final String id;
  final Color cor;

  // candles em coordenadas 0..1 (0 = topo): (abertura, máxima, mínima, fechamento) e o índice do candle do padrão
  static const _dados = {
    'martelo': ([(.30, .26, .46, .42), (.42, .38, .58, .55), (.55, .50, .70, .66), (.60, .56, .86, .64), (.62, .45, .66, .48), (.50, .36, .54, .40), (.42, .28, .46, .32)], 3, .84),
    'engolfo_alta': ([(.25, .20, .42, .38), (.38, .34, .56, .52), (.52, .48, .68, .64), (.60, .56, .74, .70), (.74, .50, .78, .52), (.50, .38, .54, .42), (.42, .30, .46, .34)], 4, .76),
    'estrela_cadente': ([(.70, .62, .74, .64), (.64, .54, .66, .56), (.56, .46, .58, .48), (.48, .38, .50, .40), (.42, .14, .46, .44), (.46, .40, .64, .60), (.60, .54, .78, .74)], 4, .22),
  };

  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = const Color(0xFF05122B));
    final d = _dados[id];
    if (d == null) return;
    final candles = d.$1, idx = d.$2, faixa = d.$3;
    final h = s.height, w = s.width, passo = w / (candles.length + 1);
    final y = (double v) => v * h;
    c.drawRect(Rect.fromLTWH(0, y(faixa) - 5, w, 10), Paint()..color = const Color(0x66E6C84A));
    for (var k = 0; k < candles.length; k++) {
      final (o, hi, lo, cl) = candles[k];
      final x = passo * (k + 1), alta = cl < o; // y cresce para baixo: fechamento acima da abertura = alta
      final col = alta ? const Color(0xFF26D07C) : const Color(0xFFFF4D6D);
      c.drawLine(Offset(x, y(hi)), Offset(x, y(lo)), Paint()..color = col..strokeWidth = 2);
      c.drawRect(Rect.fromLTRB(x - 6, y(o < cl ? o : cl), x + 6, y(o < cl ? cl : o) + 1), Paint()..color = col);
      if (k == idx) c.drawRect(Rect.fromLTRB(x - 11, y(hi) - 4, x + 11, y(lo) + 4), Paint()..color = cor..style = PaintingStyle.stroke..strokeWidth = 2);
    }
  }

  @override
  bool shouldRepaint(_MiniPadrao o) => o.id != id || o.cor != cor;
}
