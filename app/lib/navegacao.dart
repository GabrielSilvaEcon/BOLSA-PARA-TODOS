import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'alertas.dart';
import 'api.dart';
import 'cabecalho.dart';
import 'home.dart';
import 'loja.dart';
import 'jogos.dart';
import 'ranking.dart';

/// Itens da barra de baixo, na mesma ordem do app antigo: (nome, ícone 3D da arte da barra, ícone simples para a tela "em breve").
const _itens = <(String, String, IconData)>[
  ('Início', 'assets/nav/inicio.webp', Icons.home_outlined),
  ('Jogos', 'assets/nav/jogos.webp', Icons.sports_esports_outlined),
  ('Aprender', 'assets/nav/aprender.webp', Icons.menu_book_outlined),
  ('Ranking', 'assets/nav/ranking.webp', Icons.emoji_events_outlined),
  ('Loja', 'assets/nav/loja.webp', Icons.shopping_cart_outlined),
];

/// Pedido de troca de aba vindo de dentro de uma tela (ex.: "Jogar agora" da Home abre a aba Jogos).
final abaPedida = ValueNotifier<int?>(null);

/// Abre a aba [i] da barra de baixo (0 Início, 1 Jogos, 2 Aprender, 3 Ranking, 4 Loja).
void abrirAba(int i) => abaPedida.value = i;

/// Partida aberta: o cabeçalho e a barra de baixo somem para o gráfico usar a tela inteira (a mesa tem o próprio botão de voltar).
/// Conta as partidas abertas (trocar "Jogar de novo" abre uma e fecha a outra), para não piscar o cabeçalho no meio.
final modoJogo = ValueNotifier<int>(0);

/// Uma tela mudou moedas ou nível (baú aberto, compra na Loja): o cabeçalho relê `/eu`.
final saldoMudou = ValueNotifier<int>(0);

/// Estrutura do app, igual à do app antigo: cabeçalho fixo no topo, a tela no meio e a barra de navegação fixa embaixo.
/// Cada aba tem a sua própria pilha de telas, então o cabeçalho e a barra continuam visíveis dentro da Carteira, da compra etc.
class Principal extends StatefulWidget {
  const Principal({super.key, required this.api});
  final Api api;

  @override
  State<Principal> createState() => _PrincipalState();
}

class _PrincipalState extends State<Principal> {
  int _aba = 0;
  final _chaves = List.generate(_itens.length, (_) => GlobalKey<NavigatorState>());

  @override
  void initState() {
    super.initState();
    abaPedida.addListener(_trocarPedida);
    modoJogo.addListener(_redesenhar);
  }

  @override
  void dispose() {
    abaPedida.removeListener(_trocarPedida);
    modoJogo.removeListener(_redesenhar);
    super.dispose();
  }

  void _redesenhar() {
    if (mounted) setState(() {});
  }

  void _trocarPedida() {
    final i = abaPedida.value;
    if (i == null) return;
    abaPedida.value = null;
    if (mounted && i != _aba) setState(() => _aba = i);
  }

  Widget _raiz(int i) {
    if (i == 0) return HomeTela(api: widget.api);
    if (i == 1) return JogosTela(api: widget.api);
    if (i == 3) return RankingTela(api: widget.api);
    if (i == 4) return LojaTela(api: widget.api);
    return EmBreveTela(titulo: _itens[i].$1, icone: _itens[i].$3);
  }

  void _tocar(int i) {
    if (i == _aba) {
      _chaves[i].currentState?.popUntil((r) => r.isFirst); // tocar na aba aberta volta para o começo dela
      return;
    }
    setState(() => _aba = i);
  }

  /// Botão "voltar" do celular: volta dentro da aba; no começo de uma aba, vai para o Início; no Início, sai do app.
  void _voltar() {
    final nav = _chaves[_aba].currentState;
    if (nav != null && nav.canPop()) {
      nav.pop();
    } else if (_aba != 0) {
      setState(() => _aba = 0);
    } else {
      SystemNavigator.pop();
    }
  }

  Future<void> _abrirAlertas() async {
    await _chaves[_aba].currentState?.push(MaterialPageRoute(builder: (_) => AlertasTela(api: widget.api)));
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _voltar();
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF0E0B26),
        body: Column(
          children: [
            if (modoJogo.value == 0) SafeArea(bottom: false, child: Cabecalho(api: widget.api, abrirAlertas: _abrirAlertas)),
            Expanded(
              child: MediaQuery.removePadding(
                context: context,
                removeTop: modoJogo.value == 0,
                child: IndexedStack(
                  index: _aba,
                  children: [
                    for (var i = 0; i < _itens.length; i++)
                      Navigator(
                        key: _chaves[i],
                        onGenerateRoute: (_) => MaterialPageRoute(builder: (_) => _raiz(i)),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
        bottomNavigationBar: modoJogo.value > 0 ? null : _barra(),
      ),
    );
  }

  /// Barra de baixo no estilo da arte do jogo: moldura dourada, casas roxas com os ícones 3D, a aba aberta com moldura dourada
  /// e brilho, e o mascote espiando por cima do canto esquerdo.
  Widget _barra() {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(6, 0, 6, 6),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              padding: const EdgeInsets.all(2.5),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(26),
                gradient: const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFFFFE27A), Color(0xFFE9A80C), Color(0xFFB07A10)],
                ),
                boxShadow: const [
                  BoxShadow(color: Color(0x99FFC93C), blurRadius: 14, spreadRadius: -4),
                  BoxShadow(color: Color(0xCC000000), blurRadius: 18, offset: Offset(0, 8)),
                ],
              ),
              child: Container(
                padding: const EdgeInsets.fromLTRB(5, 6, 5, 6),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(23.5),
                  gradient: const LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Color(0xFF3B2690), Color(0xFF21125A)],
                  ),
                ),
                child: Row(
                  children: [
                    for (var i = 0; i < _itens.length; i++) ...[
                      if (i > 0) const SizedBox(width: 4),
                      Expanded(child: _botao(i)),
                    ],
                  ],
                ),
              ),
            ),
            // mascote espiando por cima da barra, no canto esquerdo (não pega toque)
            Positioned(
              left: 0,
              top: -52,
              child: IgnorePointer(
                child: SizedBox(
                  height: 60,
                  child: ClipRect(
                    child: Align(
                      alignment: Alignment.topCenter,
                      heightFactor: 0.6,
                      child: Image.asset('assets/nav/mascote.webp', height: 100),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _botao(int i) {
    final ativo = i == _aba;
    final (rotulo, arte, _) = _itens[i];
    return Semantics(
      button: true,
      selected: ativo,
      label: rotulo,
      child: GestureDetector(
        onTap: () => _tocar(i),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          height: 62,
          padding: const EdgeInsets.fromLTRB(2, 4, 2, 3),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: ativo ? const [Color(0xFF6A45E0), Color(0xFF3A1F9E)] : const [Color(0xFF2E1C78), Color(0xFF1E1150)],
            ),
            border: Border.all(color: ativo ? const Color(0xFFFFC93C) : const Color(0x33B59BFF), width: ativo ? 2.5 : 1),
            boxShadow: ativo ? const [BoxShadow(color: Color(0xAAFFC93C), blurRadius: 12, spreadRadius: -2)] : null,
          ),
          child: Column(
            children: [
              Expanded(
                child: AnimatedScale(
                  duration: const Duration(milliseconds: 150),
                  scale: ativo ? 1.12 : 1,
                  child: Image.asset(arte, fit: BoxFit.contain),
                ),
              ),
              const SizedBox(height: 1),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  rotulo,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                    shadows: [Shadow(color: Color(0xCC000000), blurRadius: 3, offset: Offset(0, 1))],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Aba que ainda não foi feita no app novo: avisa que está a caminho.
class EmBreveTela extends StatelessWidget {
  const EmBreveTela({super.key, required this.titulo, required this.icone});
  final String titulo;
  final IconData icone;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SizedBox(height: 48),
          Icon(icone, size: 64, color: const Color(0xFFB59BFF)),
          const SizedBox(height: 16),
          Text(
            '$titulo chega em breve no app novo.',
            textAlign: TextAlign.center,
            style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          Text('Por enquanto, use o app antigo para esta parte.', textAlign: TextAlign.center, style: tema.textTheme.bodyMedium),
        ],
      ),
    );
  }
}
