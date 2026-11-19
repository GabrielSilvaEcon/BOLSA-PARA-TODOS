import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'alertas.dart';
import 'api.dart';
import 'cabecalho.dart';
import 'home.dart';
import 'jogos.dart';

/// Itens da barra de baixo, na mesma ordem do app antigo.
const _itens = <(String, IconData)>[
  ('Início', Icons.home_outlined),
  ('Jogos', Icons.sports_esports_outlined),
  ('Aprender', Icons.menu_book_outlined),
  ('Ranking', Icons.emoji_events_outlined),
  ('Loja', Icons.shopping_cart_outlined),
];

/// Pedido de troca de aba vindo de dentro de uma tela (ex.: "Jogar agora" da Home abre a aba Jogos).
final abaPedida = ValueNotifier<int?>(null);

/// Abre a aba [i] da barra de baixo (0 Início, 1 Jogos, 2 Aprender, 3 Ranking, 4 Loja).
void abrirAba(int i) => abaPedida.value = i;

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
  }

  @override
  void dispose() {
    abaPedida.removeListener(_trocarPedida);
    super.dispose();
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
    return EmBreveTela(titulo: _itens[i].$1, icone: _itens[i].$2);
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
            SafeArea(bottom: false, child: Cabecalho(api: widget.api, abrirAlertas: _abrirAlertas)),
            Expanded(
              child: MediaQuery.removePadding(
                context: context,
                removeTop: true,
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
        bottomNavigationBar: _barra(),
      ),
    );
  }

  /// Barra de baixo: faixa escura de ponta a ponta, cantos de cima arredondados, ícone ao lado do nome.
  Widget _barra() {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF141236),
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        border: Border(top: BorderSide(color: Color(0x33BDB5E6))),
        boxShadow: [BoxShadow(color: Color(0x99000000), blurRadius: 24, offset: Offset(0, -8))],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(6, 6, 6, 6),
          child: Row(
            children: [for (var i = 0; i < _itens.length; i++) Expanded(child: _botao(i))],
          ),
        ),
      ),
    );
  }

  Widget _botao(int i) {
    final ativo = i == _aba;
    final (rotulo, icone) = _itens[i];
    final cor = ativo ? const Color(0xFFB59BFF) : const Color(0xFFE4E0FA);
    return Semantics(
      button: true,
      selected: ativo,
      label: rotulo,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _tocar(i),
        child: Container(
          height: 48,
          margin: const EdgeInsets.symmetric(horizontal: 2),
          padding: const EdgeInsets.symmetric(horizontal: 4),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            color: ativo ? const Color(0x338B6CFF) : null,
          ),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Row(
              children: [
                Icon(icone, color: cor, size: 26),
                const SizedBox(width: 6),
                Text(rotulo, style: TextStyle(color: cor, fontSize: 17, fontWeight: FontWeight.w700)),
              ],
            ),
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
