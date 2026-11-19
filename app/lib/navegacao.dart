import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'cabecalho.dart';
import 'home.dart';

/// Itens da barra de baixo, na mesma ordem do app antigo.
const _itens = <(String, IconData)>[
  ('Início', Icons.home_rounded),
  ('Jogos', Icons.sports_esports),
  ('Aprender', Icons.menu_book),
  ('Ranking', Icons.emoji_events),
  ('Loja', Icons.shopping_cart),
];

/// Estrutura principal do app: o conteúdo de cada aba e a barra de navegação fixa embaixo.
/// Cada aba tem a sua própria pilha de telas, então a barra continua visível dentro da Carteira, da compra etc.
class Principal extends StatefulWidget {
  const Principal({super.key, required this.api});
  final Api api;

  @override
  State<Principal> createState() => _PrincipalState();
}

class _PrincipalState extends State<Principal> {
  int _aba = 0;
  final _chaves = List.generate(_itens.length, (_) => GlobalKey<NavigatorState>());

  Widget _raiz(int i) {
    if (i == 0) return HomeTela(api: widget.api);
    return EmBreveTela(api: widget.api, titulo: _itens[i].$1, icone: _itens[i].$2);
  }

  void _tocar(int i) {
    if (i == _aba) {
      _chaves[i].currentState?.popUntil((r) => r.isFirst);           // tocar na aba aberta volta para o começo dela
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

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _voltar();
      },
      child: Scaffold(
        body: IndexedStack(
          index: _aba,
          children: [
            for (var i = 0; i < _itens.length; i++)
              Navigator(
                key: _chaves[i],
                onGenerateRoute: (_) => MaterialPageRoute(builder: (_) => _raiz(i)),
              ),
          ],
        ),
        bottomNavigationBar: SafeArea(top: false, child: _barra()),
      ),
    );
  }

  Widget _barra() {
    return Container(
      margin: const EdgeInsets.fromLTRB(8, 4, 8, 8),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0xF0140E34),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0x4DBDB5E6)),
        boxShadow: const [BoxShadow(color: Color(0xB3000000), blurRadius: 24, offset: Offset(0, 10))],
      ),
      child: Row(
        children: [
          for (var i = 0; i < _itens.length; i++) Expanded(child: _botao(i)),
        ],
      ),
    );
  }

  Widget _botao(int i) {
    final ativo = i == _aba;
    final (rotulo, icone) = _itens[i];
    final cor = ativo ? Colors.white : const Color(0xFFC9C1F0);
    return Semantics(
      button: true,
      selected: ativo,
      label: rotulo,
      child: InkWell(
        borderRadius: BorderRadius.circular(15),
        onTap: () => _tocar(i),
        child: Container(
          height: 52,
          margin: const EdgeInsets.symmetric(horizontal: 2),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(15),
            gradient: ativo ? const LinearGradient(colors: [Color(0xFF6E4BFF), Color(0xFFB02FC8)]) : null,
            border: ativo ? Border.all(color: const Color(0x33FFFFFF)) : null,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icone, color: cor, size: 22),
              const SizedBox(height: 2),
              Text(
                rotulo,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: cor, fontSize: 11, fontWeight: FontWeight.w700),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Aba que ainda não foi feita no app novo: mostra o cabeçalho e avisa que está a caminho.
class EmBreveTela extends StatelessWidget {
  const EmBreveTela({super.key, required this.api, required this.titulo, required this.icone});
  final Api api;
  final String titulo;
  final IconData icone;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Cabecalho(api: api),
            const SizedBox(height: 48),
            Icon(icone, size: 64, color: const Color(0xFFB59BFF)),
            const SizedBox(height: 16),
            Text(
              '$titulo chega em breve no app novo.',
              textAlign: TextAlign.center,
              style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(
              'Por enquanto, use o app antigo para esta parte.',
              textAlign: TextAlign.center,
              style: tema.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
