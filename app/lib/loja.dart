import 'dart:math';

import 'package:flutter/material.dart';

import 'api.dart';
import 'efeitos.dart';
import 'navegacao.dart';

/// Loja Ticker, como a do app antigo (tickercoins_app.pagina_economia): título, saldo de Ticker Coins e três abas.
///   · Recompensas: baú diário e baús de progresso. O resultado de abrir aparece no PRÓPRIO cartão ("Baú Raro aberto!"), sem pop-up.
///   · Loja: vitrine com a prévia de cada item e o botão certo (Trocar, Usar, Tirar, Ativo ou Faltam N) + Minhas compras.
///   · Extrato: total recebido e usado, benefícios ativos e histórico.
/// Dados do servidor (`GET /loja`); quem sorteia, cobra e credita é sempre o servidor.
class LojaTela extends StatefulWidget {
  const LojaTela({super.key, required this.api});
  final Api api;

  @override
  State<LojaTela> createState() => _LojaTelaState();
}

const _verde = Color(0xFF2EE59D);
const _ouro = Color(0xFFFFD66B);
const _lila = Color(0xFFCFC8EE);
const _abas = [('Recompensas', Icons.star_rounded), ('Loja', Icons.storefront_rounded), ('Extrato', Icons.receipt_long_rounded)];

Color _cor(Object? hex, [Color padrao = const Color(0xFF8B6CFF)]) {
  final s = '${hex ?? ''}'.replaceFirst('#', '');
  if (s.length != 6) return padrao;
  final v = int.tryParse(s, radix: 16);
  return v == null ? padrao : Color(0xFF000000 | v);
}

String _milhar(num v) {
  final s = v.abs().toInt().toString();
  final b = StringBuffer(v < 0 ? '-' : '');
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write('.');
    b.write(s[i]);
  }
  return b.toString();
}

String _rar(Object? r) => rotRaridade.containsKey(r) ? '$r' : 'comum';

class _LojaTelaState extends State<LojaTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  int _aba = 0;
  bool _ocupado = false;

  /// Baú aberto agora há pouco (diário ou de progresso): mostrado no cartão, com a animação de abrir.
  Map<String, dynamic>? _bauNovo;
  Map<String, dynamic>? _bauProgNovo;

  /// Aviso da última ação (compra feita, erro), no topo da aba — nada de pop-up.
  (bool, String)? _aviso;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    precarregarEfeitos(context);
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/loja');
      if (mounted) {
        setState(() {
          _d = r;
          _erro = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  Future<void> _acao(Future<Map<String, dynamic>> Function() chamada, void Function(Map<String, dynamic>) depois) async {
    if (_ocupado) return;
    setState(() => _ocupado = true);
    try {
      final r = await chamada();
      depois(r);
      await _carregar();
      saldoMudou.value++;
    } catch (e) {
      if (mounted) setState(() => _aviso = (false, e.toString()));
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  void _abrirBau() => _acao(() => widget.api.post('/loja/bau'), (r) => _bauNovo = r);

  void _abrirBauProg(int indice) => _acao(() => widget.api.post('/loja/bau/$indice'), (r) => _bauProgNovo = r);

  void _usar(String? pid, String tipo) => _acao(
        () => widget.api.post('/loja/equipar', {'pid': pid, 'tipo': tipo}),
        (_) => _aviso = (true, pid == null ? 'Item guardado.' : 'Pronto! O item já está em uso.'),
      );

  Future<void> _trocar(Map<String, dynamic> it) async {
    final saldo = ((_d?['saldo'] as num?) ?? 0).toInt();
    final preco = ((it['preco'] as num?) ?? 0).toInt();
    final ok = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _ConfirmaCompra(item: it, saldo: saldo, preco: preco),
    );
    if (ok != true) return;
    final req = '${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(1 << 30)}';
    await _acao(
      () => widget.api.post('/loja/comprar', {'pid': it['id'], 'req': req}),
      (r) => _aviso =
          (true, r['duplicada'] == true ? 'Esta compra já tinha sido feita (nada foi cobrado de novo).' : 'Compra feita: ${it['nome']}! Já está na sua conta.'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    // fundo da Loja (arte do Gabriel: touro, candles e moedas), parado atrás da página; um véu escuro no meio deixa os cartões legíveis
    return Stack(
      fit: StackFit.expand,
      children: [
        const ColoredBox(color: Color(0xFF0D0A33)),
        Image.asset('assets/loja/fundo_loja.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0x330D0A33), Color(0x800D0A33), Color(0x800D0A33), Color(0x260D0A33)],
              stops: [0, 0.3, 0.75, 1],
            ),
          ),
        ),
        RefreshIndicator(
          onRefresh: _carregar,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 24),
            children: [
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 720),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _titulo(),
                      const SizedBox(height: 12),
                      if (d == null && _erro != null) ...[
                        _cartao(child: Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white))),
                        const SizedBox(height: 8),
                        FilledButton(onPressed: _carregar, child: const Text('Tentar de novo')),
                      ] else if (d == null)
                        const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
                      else ...[
                        _saldo(d),
                        const SizedBox(height: 12),
                        _seletorAbas(),
                        const SizedBox(height: 12),
                        if (_aviso != null) ...[_faixaAviso(_aviso!), const SizedBox(height: 10)],
                        ...switch (_aba) { 0 => _recompensas(d), 1 => _loja(d), _ => _extrato(d) },
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------- topo
  Widget _titulo() => Row(
        children: [
          const Icon(Icons.shopping_cart_rounded, color: _verde, size: 34),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RichText(
                  text: const TextSpan(
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Colors.white),
                    children: [TextSpan(text: 'Loja '), TextSpan(text: 'Ticker', style: TextStyle(color: _verde))],
                  ),
                ),
                const Text('Troque seus Ticker Coins por itens incríveis!', style: TextStyle(fontSize: 13, color: _lila)),
              ],
            ),
          ),
          OutlinedButton(
            style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Color(0x997A5CFF)), shape: const StadiumBorder()),
            onPressed: () => setState(() => _aba = 2),
            child: const Text('Meus itens'),
          ),
        ],
      );

  Widget _saldo(Map<String, dynamic> d) {
    final s = d['saldo'];
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 10, 16, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xCCF2B84B), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2A1E86), Color(0xFF140E4A)]),
        boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
      ),
      child: Row(
        children: [
          Image.asset('assets/loja/moedas.webp', height: 78),
          Container(width: 2, height: 60, margin: const EdgeInsets.symmetric(horizontal: 12), color: const Color(0x55FFD66B)),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Image.asset('assets/loja/tc.webp', height: 30),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(s is num ? _milhar(s) : '—',
                          style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: _ouro), overflow: TextOverflow.ellipsis),
                    ),
                  ],
                ),
                const Text('Ticker Coins disponíveis', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: _lila)),
                const SizedBox(height: 4),
                GestureDetector(
                  onTap: () => setState(() => _aba = 0),
                  child: const Text('Como ganhar?',
                      style:
                          TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: _verde, decoration: TextDecoration.underline, decorationColor: _verde)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _seletorAbas() => Row(
        children: [
          for (var i = 0; i < _abas.length; i++) ...[
            if (i > 0) const SizedBox(width: 8),
            Expanded(
              child: GestureDetector(
                onTap: () => setState(() {
                  _aba = i;
                  _aviso = null;
                }),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  height: 48,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(999),
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: _aba == i ? const [Color(0xFF5BF5A0), Color(0xFF18DB7C)] : const [Color(0xD9281E78), Color(0xF2140E46)],
                    ),
                    border: _aba == i ? null : Border.all(color: const Color(0xFF1FC99A), width: 2),
                    boxShadow: [BoxShadow(color: _aba == i ? const Color(0xFF0F8F51) : const Color(0x99080628), offset: const Offset(0, 4))],
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(_abas[i].$2, size: 18, color: _aba == i ? const Color(0xFF06361F) : const Color(0xFFB89CFF)),
                      const SizedBox(width: 5),
                      Flexible(
                        child: Text(_abas[i].$1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, color: _aba == i ? const Color(0xFF06361F) : Colors.white)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ],
      );

  Widget _faixaAviso((bool, String) a) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          color: a.$1 ? const Color(0x2618DB7C) : const Color(0x26FF5C7A),
          border: Border.all(color: a.$1 ? _verde : const Color(0xFFFF5C7A)),
        ),
        child: Row(
          children: [
            Icon(a.$1 ? Icons.check_circle : Icons.error_outline, color: a.$1 ? _verde : const Color(0xFFFF8FA3)),
            const SizedBox(width: 8),
            Expanded(child: Text(a.$2, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.white))),
            GestureDetector(onTap: () => setState(() => _aviso = null), child: const Icon(Icons.close, size: 18, color: _lila)),
          ],
        ),
      );

  // ---------------------------------------------------------------- Recompensas
  List<Widget> _recompensas(Map<String, dynamic> d) {
    final bau = (d['bau'] as Map?)?.cast<String, dynamic>() ?? const {};
    final pend = ((d['baus'] as List?) ?? const []).cast<Map>();
    return [
      if (bau['ativo'] == true) ...[
        _secao('Recompensas em destaque', Icons.star_rounded, const Color(0xFFFFD76A), pill: 'Renova à meia-noite'),
        const SizedBox(height: 8),
        if (_bauNovo != null || bau['aberto'] == true) ...[
          BauAnimado(
            key: ValueKey('bau-${_bauNovo != null}'),
            raridade: _rar((_bauNovo ?? bau)['raridade']),
            valor: (((_bauNovo ?? bau)['valor'] as num?) ?? 0).toInt(),
            animar: _bauNovo != null && _bauNovo!['novo'] != false,
          ),
          if (_bauNovo == null || _bauNovo!['novo'] == false) ...[
            const SizedBox(height: 8),
            _cartao(child: const Text('Você já abriu o baú de hoje. Volte amanhã para um novo!', style: TextStyle(fontSize: 14, color: _lila))),
          ],
        ] else
          _bauFechado(),
        const SizedBox(height: 14),
      ],
      if (_bauProgNovo != null) ...[
        BauAnimado(
          key: ValueKey(_bauProgNovo),
          raridade: _rar(_bauProgNovo!['raridade']),
          valor: ((_bauProgNovo!['valor'] as num?) ?? 0).toInt(),
          titulo: '${_bauProgNovo!['rotulo'] ?? 'Baú'} aberto!',
        ),
        const SizedBox(height: 14),
      ],
      if (pend.isNotEmpty) ...[
        _secao('Baús para abrir', Icons.card_giftcard_rounded, const Color(0xFFFFD76A)),
        const SizedBox(height: 8),
        _grade([
          for (final b in pend.take(6))
            _caixa(
              topo: Image.asset('assets/loja/bau_${_rar(b['raridade'])}.webp', height: 64),
              nome: '${b['rotulo'] ?? 'Baú'}',
              sub: b['raridade'] != null ? 'Baú ${rotRaridade[_rar(b['raridade'])]!.toLowerCase()}' : 'Prêmio surpresa',
              botao: _botaoOuro('Abrir', _ocupado ? null : () => _abrirBauProg(((b['indice'] as num?) ?? 0).toInt())),
            ),
        ]),
        if (pend.length > 6)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('Mais ${pend.length - 6} baús esperando. Abra estes para liberar os próximos.', style: const TextStyle(fontSize: 12.5, color: _lila)),
          ),
        const SizedBox(height: 14),
      ],
      _secao('Como ganhar mais', Icons.lightbulb_rounded, _verde),
      const SizedBox(height: 8),
      _cartao(
        child: const Text('Conclua lições na Jornada, jogue partidas online e abra o baú diário. Cada conquista rende Ticker Coins.',
            style: TextStyle(fontSize: 14, color: _lila, height: 1.35)),
      ),
    ];
  }

  Widget _bauFechado() => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xCCF2B84B), width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2A1E86), Color(0xFF140E4A)]),
        ),
        child: Column(
          children: [
            Row(
              children: [
                Image.asset('assets/loja/bau.webp', height: 92),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Baú diário', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
                      SizedBox(height: 2),
                      Text('Receba uma recompensa surpresa!', style: TextStyle(fontSize: 13.5, color: _lila)),
                      SizedBox(height: 6),
                      Text('Grátis hoje', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: _ouro)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0x332EE59D), border: Border.all(color: _verde)),
                  child: const Text('Disponível: 1', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: _verde)),
                ),
              ],
            ),
            const SizedBox(height: 10),
            _botaoOuro('Abrir', _ocupado ? null : _abrirBau),
          ],
        ),
      );

  // ---------------------------------------------------------------- Loja
  List<Widget> _loja(Map<String, dynamic> d) {
    final itens = ((d['itens'] as List?) ?? const []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList();
    final saldo = ((d['saldo'] as num?) ?? 0).toInt();
    final compras = ((d['compras'] as List?) ?? const []).cast<Map>();
    return [
      if (itens.isEmpty)
        _cartao(
          child: const Column(
            children: [
              Text('Nada à venda agora', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
              SizedBox(height: 4),
              Text('Volte em breve: novos itens chegam com frequência.', textAlign: TextAlign.center, style: TextStyle(color: _lila)),
            ],
          ),
        )
      else
        for (final (kind, titulo, icone) in const [('tema', 'Temas', Icons.palette_rounded), ('moldura', 'Molduras', Icons.blur_circular_rounded)])
          if (itens.any((it) => it['kind'] == kind)) ...[
            _secao(titulo, icone, const Color(0xFFFFD76A)),
            const SizedBox(height: 8),
            _grade([
              for (final (i, it) in itens.where((it) => it['kind'] == kind).indexed) _entrada(i, _itemVitrine(it, saldo)),
            ]),
            const SizedBox(height: 14),
          ],
      const SizedBox(height: 16),
      _secao('Minhas compras', Icons.shopping_bag_rounded, const Color(0xFFB89CFF)),
      const SizedBox(height: 8),
      if (compras.isEmpty)
        _cartao(child: const Text('Nenhuma compra ainda. Escolha um item na vitrine para personalizar seu perfil.', style: TextStyle(color: _lila)))
      else
        for (final c in compras) ...[
          _linha(titulo: '${c['nome']}', detalhe: '${c['quando']} · ${c['estado']}', valor: '-${c['preco']} TC', cor: const Color(0xFFFF8FA3)),
          const SizedBox(height: 6),
        ],
    ];
  }

  Widget _itemVitrine(Map<String, dynamic> it, int saldo) {
    final st = (it['status'] as Map?)?.cast<String, dynamic>() ?? const {};
    final tem = st['tem'] == true;
    final preco = ((it['preco'] as num?) ?? 0).toInt();
    final rar = (it['raridade'] as Map?)?.cast<String, dynamic>() ?? const {};
    final kind = '${it['kind'] ?? ''}';
    final Widget botao;
    if (tem && it['equipavel'] == true) {
      botao = it['em_uso'] == true
          ? _botaoRoxo('Tirar', _ocupado ? null : () => _usar(null, kind))
          : _botaoVerde('Usar', _ocupado ? null : () => _usar('${it['id']}', kind));
    } else if (tem) {
      botao = _botaoRoxo('Ativo', null);
    } else if (st['cls'] == 'fora') {
      botao = _botaoRoxo('Fora de temporada', null);
    } else if (saldo < preco) {
      botao = _botaoRoxo('Faltam ${preco - saldo}', null);
    } else {
      botao = _botaoOuro('Trocar', _ocupado ? null : () => _trocar(it));
    }
    return _caixa(
      borda: _cor(rar['cor'], const Color(0xFF5B4BD6)),
      etiqueta: '${rar['rotulo'] ?? ''}',
      topo: _Previa((it['previa'] as Map?)?.cast<String, dynamic>() ?? const {}),
      nome: '${it['nome']}',
      sub: tem ? '${st['rotulo'] ?? ''}' : '',
      preco: tem ? null : preco,
      botao: botao,
    );
  }

  // ---------------------------------------------------------------- Extrato
  List<Widget> _extrato(Map<String, dynamic> d) {
    final t = (d['totais'] as Map?)?.cast<String, dynamic>() ?? const {};
    final benef = ((d['beneficios'] as List?) ?? const []).cast<Map>();
    final hist = ((d['historico'] as List?) ?? const []).cast<Map>();
    Widget total(String rotulo, Object? v, Color cor) => Expanded(
          child: _cartao(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(rotulo, style: const TextStyle(fontSize: 13, color: _lila)),
                const SizedBox(height: 2),
                Text('${v is num ? _milhar(v) : '0'} TC', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: cor)),
              ],
            ),
          ),
        );
    return [
      Row(children: [total('Total recebido', t['recebido'], _verde), const SizedBox(width: 10), total('Total usado', t['usado'], Colors.white)]),
      if (benef.isNotEmpty) ...[
        const SizedBox(height: 16),
        _secao('Benefícios ativos', Icons.verified_rounded, _verde),
        const SizedBox(height: 8),
        for (final b in benef) ...[
          _linha(titulo: '${b['nome']}', detalhe: '${b['validade']}'),
          const SizedBox(height: 6),
        ],
      ],
      const SizedBox(height: 16),
      _secao('Histórico', Icons.history_rounded, const Color(0xFFB89CFF)),
      const SizedBox(height: 8),
      if (hist.isEmpty)
        _cartao(
            child: const Text('Nenhuma movimentação ainda. Conclua uma lição na Jornada para ganhar suas primeiras moedas.', style: TextStyle(color: _lila)))
      else
        for (final h in hist) ...[
          _linha(
            titulo: '${h['descricao']}',
            detalhe: '${h['quando']}${h['pendente'] == true ? ' · ${h['estado']}' : ''} · saldo ${h['saldo_apos']} TC',
            valor: '${((h['delta'] as num?) ?? 0) > 0 ? '+' : ''}${h['delta']} TC',
            cor: ((h['delta'] as num?) ?? 0) >= 0 ? _verde : const Color(0xFFFF8FA3),
          ),
          const SizedBox(height: 6),
        ],
    ];
  }

  // ---------------------------------------------------------------- peças
  Widget _secao(String t, IconData ic, Color cor, {String? pill}) => Row(
        children: [
          Icon(ic, color: cor, size: 24),
          const SizedBox(width: 6),
          Expanded(child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
          if (pill != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration:
                  BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0x2218DB7C), border: Border.all(color: const Color(0x992EE59D))),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.schedule, size: 14, color: _verde),
                const SizedBox(width: 4),
                Text(pill, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Colors.white)),
              ]),
            ),
        ],
      );

  /// Cartões da vitrine entram um depois do outro (sobem e aparecem).
  Widget _entrada(int i, Widget filho) => TweenAnimationBuilder<double>(
        key: ValueKey('ent-$_aba-$i'),
        tween: Tween(begin: 0, end: 1),
        duration: Duration(milliseconds: 350 + 70 * min(i, 8)),
        curve: Curves.easeOutCubic,
        builder: (ctx, v, f) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, 24 * (1 - v)), child: f)),
        child: filho,
      );

  Widget _grade(List<Widget> filhos) => LayoutBuilder(
        builder: (ctx, c) {
          final n = c.maxWidth >= 560 ? 3 : 2;
          const gap = 10.0;
          final w = (c.maxWidth - gap * (n - 1)) / n;
          return Wrap(spacing: gap, runSpacing: gap, children: [for (final f in filhos) SizedBox(width: w, child: f)]);
        },
      );

  Widget _caixa(
          {required Widget topo,
          required String nome,
          String sub = '',
          int? preco,
          required Widget botao,
          Color borda = const Color(0xFF5B4BD6),
          String etiqueta = ''}) =>
      Container(
        padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: borda.withValues(alpha: 0.85), width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF231A78), Color(0xFF120C46)]),
          boxShadow: [BoxShadow(color: borda.withValues(alpha: 0.3), blurRadius: 10)],
        ),
        child: Column(
          children: [
            if (etiqueta.isNotEmpty)
              Align(
                alignment: Alignment.topRight,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                  decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: borda.withValues(alpha: 0.22), border: Border.all(color: borda)),
                  child: Text(etiqueta, style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: borda)),
                ),
              ),
            SizedBox(height: 74, child: Center(child: topo)),
            const SizedBox(height: 6),
            Text(nome,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Colors.white, height: 1.15)),
            if (sub.isNotEmpty) Text(sub, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: _lila)),
            if (preco != null)
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Image.asset('assets/loja/tc.webp', height: 18),
                const SizedBox(width: 4),
                Text(_milhar(preco), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: _ouro)),
              ]),
            const SizedBox(height: 8),
            botao,
          ],
        ),
      );

  Widget _botaoOuro(String t, VoidCallback? f) => _botao(t, f, const [Color(0xFFF2B84B), Color(0xFFD98E1F)], const Color(0xFF7A4D0B), const Color(0xFF2A1A00));
  Widget _botaoVerde(String t, VoidCallback? f) => _botao(t, f, const [Color(0xFF5BF5A0), Color(0xFF18DB7C)], const Color(0xFF0F8F51), const Color(0xFF06361F));
  Widget _botaoRoxo(String t, VoidCallback? f) => _botao(t, f, const [Color(0x22FFFFFF), Color(0x11FFFFFF)], const Color(0x88080628), Colors.white);

  Widget _botao(String t, VoidCallback? f, List<Color> cores, Color sombra, Color texto) => Opacity(
        opacity: f == null && cores.first != const Color(0x22FFFFFF) ? 0.6 : 1,
        child: GestureDetector(
          onTap: f,
          child: Container(
            height: 44,
            width: double.infinity,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: cores),
              border: Border.all(color: cores.first == const Color(0x22FFFFFF) ? const Color(0x80C5B3FF) : const Color(0xD9FFD66B), width: 1.5),
              boxShadow: [BoxShadow(color: sombra, offset: const Offset(0, 4))],
            ),
            child: Text(t,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: f == null && texto == Colors.white ? _lila : texto)),
          ),
        ),
      );

  Widget _linha({required String titulo, required String detalhe, String? valor, Color cor = Colors.white}) => _cartao(
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(titulo, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800, color: Colors.white)),
                  Text(detalhe, style: const TextStyle(fontSize: 12, color: _lila)),
                ],
              ),
            ),
            if (valor != null) Text(valor, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: cor)),
          ],
        ),
      );

  Widget _cartao({required Widget child}) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0x667A5CFF), width: 1.5),
          color: const Color(0xFF1B1462),
        ),
        child: child,
      );
}

/// Miniatura do item (o que o servidor manda em `previa`): emoji, anel de moldura, tema, fundo, efeito ou texto.
class _Previa extends StatelessWidget {
  const _Previa(this.p);
  final Map<String, dynamic> p;

  @override
  Widget build(BuildContext context) {
    final cor = _cor(p['cor']);
    switch (p['tipo']) {
      case 'emoji':
        return Container(
          width: 62,
          height: 62,
          alignment: Alignment.center,
          decoration: BoxDecoration(shape: BoxShape.circle, color: cor.withValues(alpha: 0.18), border: Border.all(color: cor, width: 2)),
          child: Text('${p['valor'] ?? '⭐'}', style: const TextStyle(fontSize: 32)),
        );
      case 'anel':
        final cores = ((p['cores'] as List?) ?? const []).map(_cor).toList();
        return Container(
          width: 64,
          height: 64,
          padding: const EdgeInsets.all(5),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: cores.length < 2 ? cor : null,
            gradient: cores.length >= 2 ? SweepGradient(colors: [...cores, cores.first]) : null,
            boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.6), blurRadius: 10)],
          ),
          child: ClipOval(child: Image.asset('assets/mascote.webp', fit: BoxFit.cover)),
        );
      case 'tema':
        final pl = (p['paleta'] as Map?) ?? const {};
        return Container(
          width: 92,
          height: 62,
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              color: _cor(pl['fundo'], const Color(0xFF0D0A2E)),
              border: Border.all(color: _cor(pl['borda'], cor), width: 2)),
          child: Column(
            children: [
              Container(height: 14, decoration: BoxDecoration(borderRadius: BorderRadius.circular(5), color: _cor(pl['cartao'], cor))),
              const SizedBox(height: 5),
              Row(children: [
                Expanded(child: Container(height: 16, decoration: BoxDecoration(borderRadius: BorderRadius.circular(5), color: _cor(pl['elevado'], cor)))),
                const SizedBox(width: 5),
                Container(width: 24, height: 16, decoration: BoxDecoration(borderRadius: BorderRadius.circular(5), color: _cor(pl['destaque'], cor))),
              ]),
            ],
          ),
        );
      case 'fundo':
        return Container(
          width: 92,
          height: 62,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: cor, width: 2),
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [_cor(p['de']), _cor(p['para'])]),
          ),
        );
      case 'efeito':
        final cores = ((p['cores'] as List?) ?? const []).map(_cor).toList();
        final cs = cores.isEmpty ? [cor] : cores;
        return SizedBox(
          width: 80,
          height: 62,
          child: Stack(
            children: [
              for (var i = 0; i < 7; i++)
                Positioned(
                  left: (i * 23 % 64).toDouble(),
                  top: (i * 17 % 46).toDouble(),
                  child: Icon(i.isEven ? Icons.auto_awesome : Icons.circle, size: i.isEven ? 18 : 10, color: cs[i % cs.length]),
                ),
            ],
          ),
        );
      default:
        return Text('${p['valor'] ?? '★'}', style: TextStyle(fontSize: 34, fontWeight: FontWeight.w900, color: cor));
    }
  }
}

/// Confirmação da compra (folha de baixo): preço, saldo e saldo depois.
class _ConfirmaCompra extends StatelessWidget {
  const _ConfirmaCompra({required this.item, required this.saldo, required this.preco});
  final Map<String, dynamic> item;
  final int saldo;
  final int preco;

  @override
  Widget build(BuildContext context) {
    final rar = (item['raridade'] as Map?) ?? const {};
    final cor = _cor(rar['cor']);
    final falta = saldo - preco < 0;
    Widget linha(String a, String b, {bool fim = false}) => Container(
          padding: const EdgeInsets.symmetric(vertical: 6),
          decoration: BoxDecoration(border: fim ? const Border(top: BorderSide(color: Color(0x4DC5B3FF))) : null),
          child: Row(children: [
            Expanded(child: Text(a, style: const TextStyle(fontSize: 14.5, color: _lila))),
            Text(b, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: _ouro)),
          ]),
        );
    return SafeArea(
      child: Container(
        margin: const EdgeInsets.all(10),
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: cor, width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF2A1E86), Color(0xFF120C46)]),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Confirmar compra', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
            const SizedBox(height: 10),
            _Previa((item['previa'] as Map?)?.cast<String, dynamic>() ?? const {}),
            const SizedBox(height: 8),
            Text('${item['nome']}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
            if ('${item['desc'] ?? ''}'.isNotEmpty) Text('${item['desc']}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: _lila)),
            const SizedBox(height: 8),
            linha('Preço', '$preco TC'),
            linha('Seu saldo', '$saldo TC'),
            linha('Saldo depois', '${saldo - preco} TC', fim: true),
            if (falta)
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: Text('Saldo insuficiente. Ganhe mais TC na Jornada ou no baú diário.',
                    textAlign: TextAlign.center, style: TextStyle(color: Color(0xFFFF8FA3))),
              ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: FilledButton(
                style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFFF2B84B),
                    foregroundColor: const Color(0xFF2A1A00),
                    textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
                onPressed: falta ? null : () => Navigator.of(context).pop(true),
                child: const Text('Confirmar compra'),
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              height: 46,
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Color(0x80C5B3FF))),
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancelar'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
