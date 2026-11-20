import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'api.dart';
import 'carteira.dart';
import 'mercado.dart';
import 'navegacao.dart';

/// Home no estilo de jogo: cabeçalho (nível, Ticker Coins e ranking), banner do Hunter Pass e os três acessos.
/// Os dados vêm do servidor (`GET /eu`). Ranking e telas de destino entram nas próximas partes.
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

class _HomeTelaState extends State<HomeTela> {
  Map<String, dynamic>? _eu;
  String? _erro;
  bool _carregando = true;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final r = await widget.api.get('/eu');
      setState(() => _eu = r);
    } catch (e) {
      setState(() => _erro = 'Não consegui carregar a sua Home agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  String get _nome {
    final perfil = (_eu?['perfil'] as Map?) ?? {};
    final conta = (_eu?['conta'] as Map?) ?? {};
    final n = (perfil['nome'] as String?)?.trim();
    if (n != null && n.isNotEmpty) return n;
    return (conta['nome'] as String?) ?? (conta['email'] as String?) ?? 'Jogador';
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/home/fundo_home.png', fit: BoxFit.cover, alignment: Alignment.topCenter),
          Container(color: const Color(0xD90B0930)),
          SafeArea(
            child: RefreshIndicator(
              onRefresh: _carregar,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _arena(),
                  const SizedBox(height: 14),
                  if (_carregando && _eu == null)
                    const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
                  else if (_erro != null && _eu == null)
                    _erroTela(tema)
                  else ...[
                    _bannerPasse(tema),
                    const SizedBox(height: 14),
                    _acessos(tema),
                  ],
                  const SizedBox(height: 24),
                  Text(
                    'Jogo educativo. Sem recomendação de compra ou venda.',
                    style: tema.textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Banner: nome do jogador e o Hunter Pass da temporada com a barra de progresso.
  Widget _bannerPasse(ThemeData tema) {
    return _cartao(
      tema,
      destaque: true,
      child: Row(
        children: [
          Image.asset('assets/home/mascote_principal.webp', width: 72, height: 72, fit: BoxFit.contain),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Olá, $_nome', style: tema.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                Text('TICKER HUNTERS', style: tema.textTheme.labelMedium?.copyWith(color: const Color(0xFFCFC8F5), letterSpacing: 1.2)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Imagem central da Home (arena do pregão). As bordas somem num degradê, sem linha nem caixa.
  Widget _arena() {
    const cores = [Colors.transparent, Colors.white, Colors.white, Colors.transparent];
    const paradas = [0.0, 0.22, 0.78, 1.0];
    return AspectRatio(
      aspectRatio: 768 / 490,
      child: ShaderMask(
        blendMode: BlendMode.dstIn,
        shaderCallback: (r) => const LinearGradient(colors: cores, stops: paradas).createShader(r),
        child: ShaderMask(
          blendMode: BlendMode.dstIn,
          shaderCallback: (r) => const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: cores,
            stops: paradas,
          ).createShader(r),
          child: Image.asset('assets/home/arena.webp', fit: BoxFit.cover),
        ),
      ),
    );
  }

  /// Os três acessos da Home com a arte dos botões. Os destinos chegam nas próximas partes.
  Widget _acessos(ThemeData tema) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: _botao(
            'assets/home/btn_carteira.webp',
            'Carteira',
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CarteiraTela(api: widget.api))),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
            flex: 2,
            child: _botao(
              'assets/home/btn_jogar.webp',
              'Jogar agora',
              onTap: () => abrirAba(1),
            )),
        const SizedBox(width: 8),
        Expanded(
            child: _botao(
          'assets/home/btn_mercado.webp',
          'Mercado',
          onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MercadoTela(api: widget.api))),
        )),
      ],
    );
  }

  Widget _botao(String arquivo, String rotulo, {VoidCallback? onTap}) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap ?? () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$rotulo: em breve'))),
      child: Semantics(
        button: true,
        label: rotulo,
        child: Image.asset(arquivo, fit: BoxFit.contain),
      ),
    );
  }

  Widget _erroTela(ThemeData tema) {
    return Column(
      children: [
        Text(_erro!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
        TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
      ],
    );
  }

  Widget _cartao(ThemeData tema, {required Widget child, bool destaque = false}) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: destaque ? const [Color(0xFF3B2A9E), Color(0xFF1A1258)] : const [Color(0xFF28245C), Color(0xFF16134A)],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF7A5CFF), width: 1.5),
      ),
      child: child,
    );
  }
}
