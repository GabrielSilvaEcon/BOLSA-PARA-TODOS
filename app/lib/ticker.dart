import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'navegacao.dart';
import 'ticker_duelo.dart';
import 'ticker_online.dart';

/// Ticker Battle (como no app antigo, battle_app.py): cartas de ações com os indicadores REAIS (dividendos, ROE, P/L…).
/// Central → Meu Baralho (3 a 10 cartas) → Duelo contra o Sistema (3 rodadas) → Resultado com o Raio-X de cada rodada.
/// Quem decide tudo é o servidor (mesmas regras de battle.py): o app só manda "qual carta" e "qual indicador".
class TickerTela extends StatefulWidget {
  const TickerTela({super.key, required this.api});
  final Api api;

  @override
  State<TickerTela> createState() => _TickerTelaState();
}

const lilas = Color(0xFFD9D4F7);

/// Ícone do indicador (os mesmos nomes do app antigo).
const iconesInd = {
  'paid': Icons.paid_rounded,
  'show_chart': Icons.show_chart_rounded,
  'swap_vert': Icons.swap_vert_rounded,
  'trending_down': Icons.trending_down_rounded,
  'savings': Icons.savings_rounded,
  'percent': Icons.percent_rounded,
  'calculate': Icons.calculate_rounded,
  'balance': Icons.balance_rounded,
  'shield': Icons.shield_rounded,
};

class _TickerTelaState extends State<TickerTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  bool _comoAberto = false;
  bool _iniciando = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  String? _ativa; // duelo online ainda aberto (para voltar a ele)

  Future<void> _online() async {
    final d = _d;
    if (d == null) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => OnlineTela(api: widget.api, baralhoValido: d['valido'] == true)));
    _carregar();
  }

  Future<void> _voltarOnline() async {
    final id = _ativa;
    if (id == null) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => PartidaOnlineTela(api: widget.api, pid: id)));
    _carregar();
  }

  Future<void> _carregar() async {
    widget.api.get('/ticker/online/ativa').then((r) {
      if (mounted) setState(() => _ativa = r['id'] as String?);
    }).catchError((_) {});
    try {
      final r = await widget.api.get('/ticker/central');
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

  Future<void> _baralho() async {
    final d = _d;
    if (d == null) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => BaralhoTela(api: widget.api, central: d)));
    _carregar();
  }

  Future<void> _jogar() async {
    final d = _d;
    if (d == null || _iniciando) return;
    if (d['valido'] != true) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${d['msg'] ?? 'Monte seu baralho primeiro.'}')));
      return _baralho();
    }
    setState(() => _iniciando = true);
    try {
      final r = await widget.api.post('/ticker/duelo');
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => DueloTela(api: widget.api, inicio: r, indicadores: (d['indicadores'] as Map).cast())));
      _carregar();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _iniciando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(
        fit: StackFit.expand,
        children: [
          // mesmo fundo da tela do Trade Battle
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFF0A0A5A), Color(0xFF1C0870), Color(0xFF14054E), Color(0xFF050038)],
                stops: [0, 0.35, 0.7, 1],
              ),
            ),
          ),
          RefreshIndicator(
            onRefresh: _carregar,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(8, 6, 8, 0),
                  children: [
                    Entrada(ordem: 0, child: _cabecalho()),
                    if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(30), child: Center(child: CircularProgressIndicator())),
                    if (_erro != null && d == null) _caixa(child: Text(_erro!, style: const TextStyle(color: Colors.white))),
                    if (d != null) ...[
                      const SizedBox(height: 6),
                      Entrada(
                        ordem: 1,
                        child: Row(children: [
                          Expanded(child: Pressionavel(aoTocar: _jogar, child: Reflexo(raio: 14, child: Image.asset('assets/ticker/modo_sis.webp')))),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Pressionavel(
                              aoTocar: _online,
                              child: Reflexo(raio: 14, atraso: const Duration(milliseconds: 1900), child: Image.asset('assets/ticker/modo_on.webp')),
                            ),
                          ),
                        ]),
                      ),
                      if (_ativa != null) ...[
                        const SizedBox(height: 10),
                        Pressionavel(
                          aoTocar: _voltarOnline,
                          child: Container(
                            padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(22),
                              border: Border.all(color: const Color(0xFF26D07C), width: 2),
                              gradient: const LinearGradient(colors: [Color(0xFF0E6B52), Color(0xFF0B3A40)]),
                              boxShadow: const [BoxShadow(color: Color(0x6626D07C), blurRadius: 14)],
                            ),
                            child: const Row(children: [
                              Icon(Icons.login_rounded, size: 28, color: Colors.white),
                              SizedBox(width: 12),
                              Expanded(child: Text('Voltar para o seu duelo online', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white))),
                              Icon(Icons.chevron_right_rounded, size: 30, color: Colors.white),
                            ]),
                          ),
                        ),
                      ],
                      const SizedBox(height: 10),
                      Entrada(ordem: 2, child: _linhaBaralho(d)),
                      Entrada(ordem: 3, child: _secaoRanking()),
                      const SizedBox(height: 10),
                      Entrada(ordem: 4, child: _sobre(d)),
                      const SizedBox(height: 6),
                      Entrada(ordem: 5, child: _como(d)),
                    ],
                    const SizedBox(height: 6),
                    Image.asset('assets/jogos/tb_chao.webp'),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- topo: cartas, "Escolha seu modo de jogo" e o touro da arte (flutuando), como na tela do Trade Battle
  Widget _cabecalho() {
    return SizedBox(
      height: 112,
      child: Stack(clipBehavior: Clip.none, children: [
        Positioned(
          right: -8,
          top: 0,
          bottom: 0,
          child: ShaderMask(
            shaderCallback: (r) => const LinearGradient(colors: [Color(0x00000000), Color(0xFF000000)], stops: [0, 0.35]).createShader(r),
            blendMode: BlendMode.dstIn,
            child: ShaderMask(
              shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF000000), Color(0x00000000)], stops: [0.8, 1])
                  .createShader(r),
              blendMode: BlendMode.dstIn,
              child: Flutua(altura: 3, child: Image.asset('assets/jogos/tb_touro.webp', height: 112, fit: BoxFit.fitHeight)),
            ),
          ),
        ),
        Positioned(
          left: 0,
          top: 2,
          child: IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
        ),
        Positioned(
          left: 6,
          top: 50,
          right: 120,
          child: Row(children: [
            ClipOval(child: Image.asset('assets/ticker/pilha.webp', width: 46, height: 46, fit: BoxFit.cover)),
            const SizedBox(width: 10),
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Ticker Battle',
                    style: TextStyle(fontSize: 19, height: 1.1, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
                SizedBox(height: 3),
                Text('Escolha seu modo de jogo',
                    style: TextStyle(fontSize: 13, fontStyle: FontStyle.italic, color: lilas, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
              ]),
            ),
          ]),
        ),
      ]),
    );
  }

  // ---- Meu baralho (na barra roxa, como "Voltar para sua sala" do Trade Battle)
  Widget _linhaBaralho(Map d) {
    final deck = ((d['deck'] as List?) ?? const []).cast<String>();
    final ok = d['valido'] == true;
    return Pressionavel(
      aoTocar: _baralho,
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 10, 12, 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: ok ? const Color(0xFF6A4FE6) : const Color(0xFFF2B84B), width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF2E1CA0), Color(0xFF1C0F78)]),
          boxShadow: const [BoxShadow(color: Color(0x806A4FE6), blurRadius: 14)],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.style_rounded, size: 30, color: Color(0xFFE4DEFF)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Meu baralho · ${deck.length}/${d['max'] ?? 10}', style: const TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, color: Colors.white)),
                Text(ok ? 'Pronto para o duelo. Toque para editar.' : '${d['msg'] ?? 'Monte seu baralho'}',
                    style: TextStyle(fontSize: 12.2, color: ok ? const Color(0xFF8DF5C1) : const Color(0xFFFFD66B))),
              ]),
            ),
            const Icon(Icons.chevron_right_rounded, size: 30, color: Colors.white),
          ]),
          if (deck.isNotEmpty) ...[
            const SizedBox(height: 8),
            SizedBox(
              height: 60,
              child: ListView(scrollDirection: Axis.horizontal, children: [
                for (final t in deck) Padding(padding: const EdgeInsets.only(right: 6), child: CartaTk(tk: t, largura: 45)),
              ]),
            ),
          ],
        ]),
      ),
    );
  }

  // ---- Ranking do Ticker Battle (mesmo bloco da tela do Trade Battle)
  Widget _secaoRanking() {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(4, 16, 0, 8),
        child: Row(children: [
          const Icon(Icons.bar_chart_rounded, size: 30, color: Color(0xFFB59BFF)),
          const SizedBox(width: 6),
          const Expanded(
            child: Text('Ranking do Ticker Battle', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: Colors.white)),
          ),
          Pressionavel(
            aoTocar: () => abrirAba(3),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: const Color(0xFF7B63F0), width: 1.5),
                color: const Color(0x661C0F78),
              ),
              child: const Text('Ver ranking completo ›', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: Colors.white)),
            ),
          ),
        ]),
      ),
      Pressionavel(
        aoTocar: () => abrirAba(3),
        child: Reflexo(raio: 14, atraso: const Duration(milliseconds: 900), intervalo: const Duration(milliseconds: 4600), child: Image.asset('assets/jogos/tb_ranking.webp')),
      ),
      const Padding(
        padding: EdgeInsets.only(top: 6, left: 4),
        child: Text('Só duelos online contam para o ranking.', style: TextStyle(fontSize: 12, color: lilas)),
      ),
    ]);
  }

  // ---- Sobre o Ticker Battle (quadro com ícones, como o do Trade Battle) + seus duelos
  Widget _sobre(Map d) {
    final h = (d['historico'] as Map?) ?? const {};
    Widget col(Widget ic, String b, String t) => Expanded(
          child: Column(children: [
            SizedBox(height: 34, child: Center(child: ic)),
            const SizedBox(height: 4),
            FittedBox(fit: BoxFit.scaleDown, child: Text(b, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white))),
            Text(t, textAlign: TextAlign.center, style: const TextStyle(fontSize: 10.5, height: 1.2, color: Color(0xFFBDB5E6))),
          ]),
        );
    Widget img(String a) => ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.asset(a, height: 34));
    Widget sep() => const VerticalDivider(width: 1, thickness: 1, color: Color(0x596A4FE6));
    Widget quadro(List<Widget> filhos) => Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xFF120852), border: Border.all(color: const Color(0x406A4FE6))),
          child: IntrinsicHeight(child: Row(children: filhos)),
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 12, 10, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFF6A4FE6), width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF231388), Color(0xFF160B5E)]),
        boxShadow: const [BoxShadow(color: Color(0x666A4FE6), blurRadius: 14)],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 8),
          child: Row(children: [
            Icon(Icons.star_rounded, color: Color(0xFFFFC93C), size: 24),
            SizedBox(width: 6),
            Text('Sobre o Ticker Battle', style: TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, color: Colors.white)),
          ]),
        ),
        quadro([
          col(img('assets/ticker/pilha.webp'), '3 a 10', 'cartas no baralho'),
          sep(),
          col(img('assets/jogos/tb_ic_graf.webp'), '5', 'indicadores reais'),
          sep(),
          col(img('assets/jogos/tb_ic_xp.webp'), 'Melhor de 3', 'rodadas'),
          sep(),
          col(img('assets/jogos/tb_ic_jog.webp'), '1 × 1', 'online, vale ranking'),
        ]),
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 12, 0, 8),
          child: Text('Seus duelos', style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800, color: Colors.white)),
        ),
        quadro([
          col(const Icon(Icons.emoji_events_rounded, color: Color(0xFF26D07C), size: 28), '${h['vitoria'] ?? 0}', 'vitórias'),
          sep(),
          col(const Icon(Icons.handshake_rounded, color: Color(0xFFF2B84B), size: 28), '${h['empate'] ?? 0}', 'empates'),
          sep(),
          col(const Icon(Icons.close_rounded, color: Color(0xFFFF6B87), size: 28), '${h['derrota'] ?? 0}', 'derrotas'),
        ]),
      ]),
    );
  }

  // ---- Como funciona (mesmo bloco da tela do Trade Battle)
  Widget _como(Map d) => Container(
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x558B6CFF)), color: const Color(0xCC140E3A)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          InkWell(
            onTap: () => setState(() => _comoAberto = !_comoAberto),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(children: [
                const Icon(Icons.help_outline, size: 20, color: Colors.white),
                const SizedBox(width: 8),
                const Expanded(child: Text('Como funciona', style: TextStyle(fontWeight: FontWeight.w700, color: Colors.white))),
                Icon(_comoAberto ? Icons.expand_less : Icons.expand_more, color: Colors.white),
              ]),
            ),
          ),
          if (_comoAberto)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Text(
                'Cada carta é uma ação real da B3 com 5 indicadores de verdade: Dividendos, Rentabilidade, Volatilidade, ROE e P/L. '
                'No Duelo Clássico são ${d['rodadas'] ?? 3} rodadas: você escolhe a carta e o indicador; o sistema escolhe a carta dele por uma '
                'regra fixa e pública, sem olhar os seus valores. Cada indicador tem a sua regra (maior vence, menor vence ou menor positivo vence). '
                'Valores iguais empatam a rodada. Cada carta joga uma vez. Vence quem ganhar mais rodadas.\n\n'
                'Jogo educativo: dados reais, nenhuma recomendação de investimento. Duelos contra o sistema não pagam XP nem moedas.',
                style: const TextStyle(fontSize: 13, height: 1.45, color: Color(0xFFEDE9FF)),
              ),
            ),
        ]),
      );
}

Widget _caixa({required Widget child, Color borda = const Color(0xFF6A4FE6)}) => Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borda, width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF231388), Color(0xFF160B5E)]),
        boxShadow: [BoxShadow(color: borda.withValues(alpha: 0.35), blurRadius: 12)],
      ),
      child: child,
    );

/// Carta do Ticker Battle (arte própria de cada ação), com marcação de escolhida, trava e brilho.
class CartaTk extends StatelessWidget {
  const CartaTk({super.key, required this.tk, this.largura = 110, this.marcada = false, this.travada = false, this.brilho, this.apagada = false});
  final String tk;
  final double largura;
  final bool marcada, travada, apagada;
  final Color? brilho;

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 300),
      opacity: apagada ? 0.45 : 1,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        width: largura,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(largura * 0.08),
          boxShadow: [
            if (brilho != null) BoxShadow(color: brilho!.withValues(alpha: 0.8), blurRadius: 18, spreadRadius: 2),
            if (marcada) const BoxShadow(color: Color(0xCC26D07C), blurRadius: 12, spreadRadius: 1),
          ],
        ),
        child: Stack(children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(largura * 0.08),
            child: Image.asset(
              'assets/ticker/carta_$tk.webp',
              width: largura,
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => Container(
                width: largura,
                height: largura * 1.34,
                color: const Color(0xFF2A1E86),
                alignment: Alignment.center,
                child: Text(tk, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
              ),
            ),
          ),
          if (travada)
            Positioned.fill(
              child: Container(
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(largura * 0.08), color: const Color(0xAA0B0828)),
                child: const Icon(Icons.lock_rounded, color: Colors.white70, size: 30),
              ),
            ),
          if (marcada)
            Positioned(
              right: 4,
              top: 4,
              child: Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFF26D07C), border: Border.all(color: Colors.white, width: 2)),
                child: const Icon(Icons.check, size: 13, color: Colors.white),
              ),
            ),
        ]),
      ),
    );
  }
}

/// Meu Baralho: todas as cartas; tocar abre os detalhes (indicadores reais e a regra de cada um) com Adicionar/Remover.
class BaralhoTela extends StatefulWidget {
  const BaralhoTela({super.key, required this.api, required this.central});
  final Api api;
  final Map<String, dynamic> central;

  @override
  State<BaralhoTela> createState() => _BaralhoTelaState();
}

class _BaralhoTelaState extends State<BaralhoTela> {
  late List<String> _deck = ((widget.central['deck'] as List?) ?? const []).cast<String>().toList();
  late bool _valido = widget.central['valido'] == true;
  late String _msg = '${widget.central['msg'] ?? ''}';
  late final List<Map> _cartas = ((widget.central['cartas'] as List?) ?? const []).cast<Map>();
  late final Map _meta = (widget.central['indicadores'] as Map?) ?? const {};
  int get _max => (widget.central['max'] as num?)?.toInt() ?? 10;
  int get _min => (widget.central['min'] as num?)?.toInt() ?? 3;

  Future<void> _salvar(List<String> novo) async {
    final antes = _deck;
    setState(() => _deck = novo);
    try {
      final r = await widget.api.post('/ticker/baralho', {'deck': novo});
      if (mounted) {
        setState(() {
          _deck = ((r['deck'] as List?) ?? const []).cast<String>().toList();
          _valido = r['valido'] == true;
          _msg = '${r['msg'] ?? ''}';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _deck = antes);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  void _detalhes(Map c) {
    final tk = '${c['tk']}';
    final no = _deck.contains(tk);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF16104A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.8,
        maxChildSize: 0.95,
        builder: (ctx, sc) => ListView(
          controller: sc,
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            Center(child: CartaTk(tk: tk, largura: 150, travada: c['jogavel'] != true)),
            const SizedBox(height: 8),
            Text('${c['nome']} · ${c['categoria']}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
            Text('Dados de ${c['ref']}${'${c['fonte']}'.isEmpty ? '' : ' · ${c['fonte']}'}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: lilas)),
            const SizedBox(height: 10),
            for (final i in ((c['ind'] as List?) ?? const []).cast<Map>()) _linhaInd(i),
            for (final a in ((c['avisos'] as List?) ?? const [])) Text('⚠️ $a', style: const TextStyle(color: Color(0xFFFFD66B))),
            if (c['jogavel'] != true) Text('🔒 ${c['motivo']}', style: const TextStyle(color: Color(0xFFFF8FA3))),
            const SizedBox(height: 12),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
                backgroundColor: no ? const Color(0xFF5B4BD6) : const Color(0xFF12A83C),
                textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
              ),
              onPressed: (!no && (c['jogavel'] != true || _deck.length >= _max))
                  ? null
                  : () {
                      Navigator.of(ctx).pop();
                      _salvar(no ? (_deck.toList()..remove(tk)) : [..._deck, tk]);
                    },
              icon: Icon(no ? Icons.remove_rounded : Icons.add_rounded),
              label: Text(no ? 'Remover do baralho' : (_deck.length >= _max ? 'Baralho cheio ($_max)' : 'Adicionar ao baralho')),
            ),
            const SizedBox(height: 6),
            const Text('As barras são só visuais; quem vence segue a regra de cada indicador.', textAlign: TextAlign.center, style: TextStyle(fontSize: 11.5, color: lilas)),
          ],
        ),
      ),
    );
  }

  Widget _linhaInd(Map i) {
    final m = (_meta[i['id']] as Map?) ?? const {};
    final v = (i['v'] as num).toDouble().abs();
    final w = (m['melhor'] == 'maior' || m['melhor'] == 'menor') && '${i['txt']}'.contains('%') ? (v * 100).clamp(6, 100) : (v * 4).clamp(6, 100);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(iconesInd[m['icone']] ?? Icons.analytics_rounded, size: 18, color: const Color(0xFFB59BFF)),
          const SizedBox(width: 6),
          Expanded(child: Text('${m['nome'] ?? i['id']}', style: const TextStyle(fontWeight: FontWeight.w800, color: Colors.white))),
          Text('${i['txt']}', style: const TextStyle(fontWeight: FontWeight.w900, color: Color(0xFFFFD66B))),
        ]),
        const SizedBox(height: 4),
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: w / 100),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (ctx, f, _) => ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(value: f, minHeight: 7, backgroundColor: const Color(0x335B4BD6), color: const Color(0xFF8B6CFF)),
          ),
        ),
        Text('${m['regra'] ?? ''}', style: const TextStyle(fontSize: 11.5, color: lilas)),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B0828),
      appBar: AppBar(
        backgroundColor: const Color(0xFF110C3A),
        title: const Text('Meu baralho', style: TextStyle(fontWeight: FontWeight.w900)),
      ),
      body: Column(children: [
        Container(
          margin: const EdgeInsets.fromLTRB(12, 10, 12, 6),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            color: _valido ? const Color(0x2226D07C) : const Color(0x22F2B84B),
            border: Border.all(color: _valido ? const Color(0xFF26D07C) : const Color(0xFFF2B84B)),
          ),
          child: Row(children: [
            Text('${_deck.length}/$_max', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white)),
            const SizedBox(width: 10),
            Expanded(
              child: Text(_valido ? 'Baralho válido: pronto para jogar!' : (_msg.isEmpty ? 'Escolha de $_min a $_max cartas, sem repetir.' : _msg),
                  style: TextStyle(color: _valido ? const Color(0xFF8DF5C1) : const Color(0xFFFFD66B), fontWeight: FontWeight.w700)),
            ),
            if (_deck.isEmpty && (widget.central['sugestao'] as List?)?.isNotEmpty == true)
              TextButton(
                onPressed: () => _salvar(((widget.central['sugestao'] as List?) ?? const []).cast<String>().toList()),
                child: const Text('Sugerir'),
              ),
          ]),
        ),
        Expanded(
          child: LayoutBuilder(builder: (ctx, c) {
            final n = c.maxWidth >= 560 ? 5 : 3;
            return GridView.builder(
              padding: const EdgeInsets.fromLTRB(12, 6, 12, 90),
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: n, mainAxisSpacing: 10, crossAxisSpacing: 10, childAspectRatio: 0.74),
              itemCount: _cartas.length,
              itemBuilder: (ctx, i) {
                final carta = _cartas[i];
                final tk = '${carta['tk']}';
                return Entrada(
                  ordem: i ~/ n,
                  child: Pressionavel(
                    aoTocar: () => _detalhes(carta),
                    child: LayoutBuilder(
                      builder: (ctx, cc) => CartaTk(tk: tk, largura: cc.maxWidth, marcada: _deck.contains(tk), travada: carta['jogavel'] != true),
                    ),
                  ),
                );
              },
            );
          }),
        ),
      ]),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: SizedBox(
          width: double.infinity,
          height: 52,
          child: FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
            onPressed: _valido ? () => Navigator.of(context).pop() : null,
            icon: const Icon(Icons.check_rounded),
            label: Text(_valido ? 'Pronto' : 'Escolha pelo menos $_min cartas'),
          ),
        ),
      ),
    );
  }
}
