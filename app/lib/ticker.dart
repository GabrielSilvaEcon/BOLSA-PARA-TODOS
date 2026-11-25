import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'cartas.dart';
import 'colecao.dart';
import 'navegacao.dart';
import 'setups.dart' show revelarSetup;
import 'ticker_duelo.dart';
import 'ticker_online.dart';

export 'cartas.dart' show CartaTk, tkBase, valoresDoDuelo, dadosDoDuelo, CatalogoCartas, revelarCartas;

/// Ticker Battle (como no app antigo, battle_app.py): cartas de ações com os indicadores REAIS (dividendos, ROE, P/L…).
/// Central → Meu Baralho (5 cartas) → Duelo contra o Sistema (3 rodadas; você escolhe quais cartas entram) → Resultado com o Raio-X.
/// Quem decide tudo é o servidor (mesmas regras de battle.py): o app só manda "qual carta" e "qual indicador".
class TickerTela extends StatefulWidget {
  const TickerTela({super.key, required this.api});
  final Api api;

  @override
  State<TickerTela> createState() => _TickerTelaState();
}

const lilas = Color(0xFFD4E2F7);

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
    CatalogoCartas.carregar(widget.api);
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
      if (!mounted) return;
      setState(() { _d = r; _erro = null; });
      if (r['tutorial_pendente'] == true && mounted) {
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => TutorialBattleTela(api: widget.api)));
        if (mounted) _carregar();
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  Future<void> _baralho() async {
    final d = _d;
    if (d == null) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ColecaoTela(api: widget.api)));
    _carregar();
  }

  Future<void> _jogar() async {
    final d = _d;
    if (d == null || _iniciando) return;
    if (d['valido'] != true) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${d['msg'] ?? 'Equipe suas cartas na Coleção primeiro.'}')));
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
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(
        fit: StackFit.expand,
        children: [
          // mesmo fundo da tela do Trade Battle
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFF0A0A5A), Color(0xFF082F70), Color(0xFF05204E), Color(0xFF001738)],
                stops: [0, 0.35, 0.7, 1],
              ),
            ),
          ),
          // fundo da arena do Ticker Battle (arte do Gabriel: touro × urso), parado atrás da página, com um véu para o texto ficar legível
          const FundoCidade(),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x33061730), Color(0x8C061730), Color(0x8C061730), Color(0x33061730)],
                stops: [0, 0.3, 0.75, 1],
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
              shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF000000), Color(0x00000000)], stops: [0.8, 1]).createShader(r),
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
                Text('Ticker Battle', style: TextStyle(fontSize: 19, height: 1.1, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
                SizedBox(height: 3),
                Text('Escolha seu modo de jogo', style: TextStyle(fontSize: 13, fontStyle: FontStyle.italic, color: lilas, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
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
          border: Border.all(color: ok ? const Color(0xFF4F88E6) : const Color(0xFFF2B84B), width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1C50A0), Color(0xFF0F3878)]),
          boxShadow: const [BoxShadow(color: Color(0x804F88E6), blurRadius: 14)],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.style_rounded, size: 30, color: Color(0xFFDEEBFF)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Coleção · ${deck.length}/4 equipadas', style: const TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, color: Colors.white)),
                Text(ok ? 'Pronto para o duelo. Toque para evoluir e trocar.' : '${d['msg'] ?? 'Equipe suas cartas'}',
                    style: TextStyle(fontSize: 12.2, color: ok ? const Color(0xFF8DF5C1) : const Color(0xFFFFD66B))),
              ]),
            ),
            const Icon(Icons.chevron_right_rounded, size: 30, color: Colors.white),
          ]),
          if (deck.isNotEmpty) ...[
            const SizedBox(height: 8),
            SizedBox(
              height: CartaTk.alturaPara(56),
              child: ListView(scrollDirection: Axis.horizontal, children: [
                for (final c in ((d['equipadas'] as List?) ?? const []).cast<Map>())
                  Padding(padding: const EdgeInsets.only(right: 6), child: CartaTk(tk: '${c['tk']}', largura: 56, dados: dadosDoDuelo(c), valores: valoresDoDuelo(c['ind']))),
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
          const Icon(Icons.bar_chart_rounded, size: 30, color: Color(0xFF9BBFFF)),
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
                border: Border.all(color: const Color(0xFF6399F0), width: 1.5),
                color: const Color(0x660F3878),
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
            Text(t, textAlign: TextAlign.center, style: const TextStyle(fontSize: 10.5, height: 1.2, color: Color(0xFFB5C8E6))),
          ]),
        );
    Widget img(String a) => ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.asset(a, height: 34));
    Widget sep() => const VerticalDivider(width: 1, thickness: 1, color: Color(0x594F88E6));
    Widget quadro(List<Widget> filhos) => Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xFF082552), border: Border.all(color: const Color(0x404F88E6))),
          child: IntrinsicHeight(child: Row(children: filhos)),
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 12, 10, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFF4F88E6), width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF134188), Color(0xFF0B2C5E)]),
        boxShadow: const [BoxShadow(color: Color(0x664F88E6), blurRadius: 14)],
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
          col(img('assets/ticker/pilha.webp'), '4', 'cartas equipadas'),
          sep(),
          col(img('assets/jogos/tb_ic_graf.webp'), '3', 'P/L, DY e ROE'),
          sep(),
          col(img('assets/jogos/tb_ic_xp.webp'), '3 rodadas', 'de 5 cartas'),
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
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x556CA3FF)), color: const Color(0xCC0E1F3A)),
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
                'Cada carta é uma ação real da B3 com 3 indicadores de verdade: P/L, DY (dividendos) e ROE. O seu baralho são as cartas '
                'equipadas na Coleção (1 de cada raridade). Ao evoluir uma carta você melhora um desses atributos só no jogo: o dado real não muda. '
                'No Duelo Clássico são ${d['rodadas'] ?? 3} rodadas: você escolhe a carta e o indicador; o sistema escolhe a carta dele por uma '
                'regra fixa e pública, sem olhar os seus valores. Cada indicador tem a sua regra (maior vence, menor vence ou menor positivo vence). '
                'Valores iguais empatam a rodada. Cada carta joga uma vez. Vence quem ganhar mais rodadas.\n\n'
                'Jogo educativo: dados reais, nenhuma recomendação de investimento. Duelos contra o sistema não pagam XP nem moedas.',
                style: const TextStyle(fontSize: 13, height: 1.45, color: Color(0xFFE9F1FF)),
              ),
            ),
        ]),
      );
}

Widget _caixa({required Widget child, Color borda = const Color(0xFF4F88E6)}) => Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borda, width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF134188), Color(0xFF0B2C5E)]),
        boxShadow: [BoxShadow(color: borda.withValues(alpha: 0.35), blurRadius: 12)],
      ),
      child: child,
    );

// ===================================================================================== Tutorial de Boas-Vindas

/// Fluxo de onboarding do Ticker Battle: aparece uma única vez quando o jogador entra pela primeira vez.
/// Passo 0 → introdução + abertura do Baú Iniciante → revelarCartas (animação existente).
/// Passo 1 → instrução para equipar cartas na Coleção.
/// Passo 2 → confirmação e botão "Batalhar!".
class TutorialBattleTela extends StatefulWidget {
  const TutorialBattleTela({super.key, required this.api});
  final Api api;

  @override
  State<TutorialBattleTela> createState() => _TutorialBattleTelaState();
}

class _TutorialBattleTelaState extends State<TutorialBattleTela> {
  int _passo = 0;
  bool _abrindo = false;

  Future<void> _abrirBau() async {
    if (_abrindo) return;
    setState(() => _abrindo = true);
    try {
      final r = await widget.api.post('/ticker/tutorial/bau');
      final cartas = (r['cartas'] as List? ?? []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList();
      if (!mounted) return;
      await revelarCartas(context, cartas, titulo: 'Baú Iniciante aberto!');
      final st = r['setup']; // brinde: a carta do setup básico
      if (mounted && st is Map) await revelarSetup(context, st.cast<String, dynamic>(), titulo: '🎁 PRESENTE DE BOAS-VINDAS!');
      if (mounted) setState(() { _passo = 1; _abrindo = false; });
    } catch (e) {
      if (mounted) {
        setState(() => _abrindo = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _irColecao() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ColecaoTela(api: widget.api)));
    if (mounted) setState(() => _passo = 2);
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: const Color(0xFF0A0A5A),
        body: Stack(fit: StackFit.expand, children: [
          const FundoCidade(),
          const DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [Color(0xCC061730), Color(0xAA061730)],
          ))),
          SafeArea(child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 400),
            child: KeyedSubtree(key: ValueKey(_passo), child: switch (_passo) {
              0 => _passoIntro(),
              1 => _passoDeck(),
              _ => _passoFinal(),
            }),
          )),
        ]),
      ),
    );
  }

  Widget _passoIntro() => _corpo(
    icone: const Icon(Icons.emoji_events_rounded, color: Color(0xFFFFB938), size: 72),
    titulo: 'Bem-vindo ao\nTicker Battle!',
    corpo: 'Colete cartas das maiores empresas do Brasil e dispute duelos com seus indicadores reais de mercado.',
    centro: Reflexo(
      raio: 24,
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Image.asset('assets/loja/bau_raro.webp', width: 150),
        const SizedBox(height: 6),
        const Text('Baú Iniciante', style: TextStyle(color: Color(0xFFFFB938), fontWeight: FontWeight.bold, fontSize: 15)),
      ]),
    ),
    botao: FilledButton.icon(
      onPressed: _abrindo ? null : _abrirBau,
      icon: _abrindo
          ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
          : const Icon(Icons.lock_open_rounded),
      label: Text(_abrindo ? 'Abrindo...' : 'Abrir meu Baú!'),
      style: FilledButton.styleFrom(
        backgroundColor: const Color(0xFFFFB938), foregroundColor: Colors.black87,
        minimumSize: const Size(double.infinity, 52),
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
  );

  Widget _passoDeck() => _corpo(
    icone: const Icon(Icons.style_rounded, color: Color(0xFF6B99FF), size: 72),
    titulo: 'Monte seu Deck!',
    corpo: 'Monte o baralho na Coleção: até 5 cartas, e o duelo usa 3 delas. Toque em cada carta e selecione "Equipar".',
    centro: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      for (var i = 0; i < 3; i++) ...[
        Container(
          width: 68, height: 96,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
                colors: [Color(0xFF1A3A6B), Color(0xFF0A1F45)]),
            border: Border.all(color: const Color(0xFF4DA3FF), width: 1.5),
            boxShadow: const [BoxShadow(color: Color(0x554DA3FF), blurRadius: 12)],
          ),
          child: const Icon(Icons.style_rounded, color: Color(0xFF4DA3FF), size: 34),
        ),
        if (i < 2) const SizedBox(width: 10),
      ],
    ]),
    botao: FilledButton.icon(
      onPressed: _irColecao,
      icon: const Icon(Icons.collections_bookmark_rounded),
      label: const Text('Ir para a Coleção'),
      style: FilledButton.styleFrom(
        backgroundColor: const Color(0xFF4DA3FF), foregroundColor: Colors.white,
        minimumSize: const Size(double.infinity, 52),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
  );

  Widget _passoFinal() => _corpo(
    icone: const Icon(Icons.sports_esports_rounded, color: Color(0xFF26D07C), size: 72),
    titulo: 'Pronto para batalhar!',
    corpo: 'Seu deck está montado. Dispute seu primeiro Ticker Battle e veja quais ações vencem na prática!',
    centro: const Icon(Icons.emoji_events_rounded, color: Color(0xFFFFB938), size: 100),
    botao: FilledButton.icon(
      onPressed: () => Navigator.of(context).pop(),
      icon: const Icon(Icons.play_arrow_rounded),
      label: const Text('Batalhar agora!'),
      style: FilledButton.styleFrom(
        backgroundColor: const Color(0xFF26D07C), foregroundColor: Colors.white,
        minimumSize: const Size(double.infinity, 52),
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
  );

  Widget _corpo({required Widget icone, required String titulo, required String corpo, required Widget centro, required Widget botao}) {
    return Column(children: [
      const SizedBox(height: 24),
      Padding(padding: const EdgeInsets.symmetric(horizontal: 8), child: Row(children: [
        const SizedBox(width: 48),
        const Spacer(),
        Row(mainAxisSize: MainAxisSize.min, children: [
          for (var i = 0; i < 3; i++) ...[
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: _passo == i ? 24 : 8, height: 8,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4),
                color: _passo == i ? const Color(0xFFFFB938) : const Color(0x44FFFFFF),
              ),
            ),
            if (i < 2) const SizedBox(width: 6),
          ],
        ]),
        const Spacer(),
        const SizedBox(width: 48),
      ])),
      const Spacer(),
      icone,
      const SizedBox(height: 16),
      Padding(padding: const EdgeInsets.symmetric(horizontal: 28), child: Text(
        titulo, textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: Colors.white, height: 1.2),
      )),
      const SizedBox(height: 10),
      Padding(padding: const EdgeInsets.symmetric(horizontal: 32), child: Text(
        corpo, textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 15, color: Color(0xFFB5C8E6), height: 1.45),
      )),
      const Spacer(),
      centro,
      const Spacer(),
      Padding(padding: const EdgeInsets.fromLTRB(24, 0, 24, 32), child: botao),
    ]);
  }
}
