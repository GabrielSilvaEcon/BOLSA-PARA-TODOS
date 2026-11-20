import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'api.dart';
import 'cabecalho.dart';

/// Tela de abertura (arte do Gabriel). A barra mostra o carregamento DE VERDADE, para o jogador já entrar com tudo pronto:
///   1. imagens das telas principais (Home, cabeçalho e barra de baixo) ficam na memória;
///   2. com sessão aberta: acorda o servidor e já traz nível, moedas e ranking (o cabeçalho abre preenchido, sem "Nível —");
///   3. no fim, entra com um esmaecer suave. Sem internet ou servidor lento, entra mesmo assim depois de um tempo.
class AberturaTela extends StatefulWidget {
  const AberturaTela({super.key, required this.depois});

  /// A tela que vem depois (login ou o app).
  final Widget depois;

  @override
  State<AberturaTela> createState() => _AberturaTelaState();
}

const _imagens = [
  'assets/home/fundo_home.png', 'assets/home/arena.webp', 'assets/home/btn_jogar.webp', 'assets/home/btn_carteira.webp',
  'assets/home/btn_mercado.webp', 'assets/home/mascote_principal.webp', 'assets/home/moeda_tc.webp', 'assets/home/touro.webp',
  'assets/home/trofeu.webp', 'assets/home/cofre.webp', 'assets/cabecalho/coroa.webp', 'assets/cabecalho/mais.webp',
  'assets/cabecalho/moedas.webp', 'assets/cabecalho/touro.webp', 'assets/nav/inicio.webp', 'assets/nav/jogos.webp',
  'assets/nav/aprender.webp', 'assets/nav/ranking.webp', 'assets/nav/loja.webp', 'assets/nav/mascote.webp',
  'assets/mascote.webp', 'assets/fundo_login.webp',
];

class _AberturaTelaState extends State<AberturaTela> with TickerProviderStateMixin {
  late final AnimationController _barra = AnimationController(vsync: this, duration: const Duration(milliseconds: 500));
  late final AnimationController _vida = AnimationController(vsync: this, duration: const Duration(seconds: 6))..repeat(reverse: true);
  double _alvo = 0;
  String _etapa = 'Carregando o jogo…';
  bool _pronto = false;
  bool _comecou = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_comecou) {
      _comecou = true;
      _carregar();
    }
  }

  @override
  void dispose() {
    _barra.dispose();
    _vida.dispose();
    super.dispose();
  }

  void _avancar(double v, String etapa) {
    if (!mounted) return;
    setState(() => _etapa = etapa);
    _alvo = v;
    _barra.animateTo(v, duration: const Duration(milliseconds: 600), curve: Curves.easeOutCubic);
  }

  Future<void> _carregar() async {
    final inicio = DateTime.now();
    await precacheImage(const AssetImage('assets/abertura.webp'), context);
    _avancar(0.08, 'Carregando o jogo…');

    // 1. imagens das telas principais
    var n = 0;
    await Future.wait(_imagens.map((a) async {
      try {
        await precacheImage(AssetImage(a), context);
      } catch (_) {}
      n++;
      _avancar(0.08 + 0.37 * n / _imagens.length, 'Preparando as telas…');
    }));

    // 2. servidor e perfil (só com sessão aberta)
    Session? sessao;
    try {
      sessao = Supabase.instance.client.auth.currentSession;
    } catch (_) {
      sessao = null; // Supabase não iniciado (prévia): só as imagens
    }
    if (sessao != null) {
      _avancar(0.5, 'Conectando ao servidor…');
      final api = Api(tokenAtual: () => Supabase.instance.client.auth.currentSession?.accessToken);
      final lento = Timer(const Duration(seconds: 6), () => _avancar(max(_alvo, 0.62), 'O servidor está acordando…'));
      try {
        euInicial = await api.get('/eu').timeout(const Duration(seconds: 40));
        _avancar(0.92, 'Carregando seu perfil…');
      } catch (_) {
        _avancar(0.92, 'Entrando…'); // sem servidor agora: o cabeçalho tenta de novo sozinho
      } finally {
        lento.cancel();
      }
    }

    // um mínimo de tempo para a arte aparecer (sem piscar) e o fim da barra
    final passou = DateTime.now().difference(inicio);
    if (passou < const Duration(milliseconds: 1300)) await Future.delayed(const Duration(milliseconds: 1300) - passou);
    _avancar(1, 'Pronto!');
    await Future.delayed(const Duration(milliseconds: 650));
    if (mounted) setState(() => _pronto = true);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 700),
      switchInCurve: Curves.easeOut,
      child: _pronto ? widget.depois : _tela(),
    );
  }

  Widget _tela() {
    return Scaffold(
      key: const ValueKey('abertura'),
      backgroundColor: const Color(0xFF1B0A63),
      body: Stack(
        fit: StackFit.expand,
        children: [
          // a arte "respira": um zoom bem lento, para dar vida enquanto carrega
          AnimatedBuilder(
            animation: _vida,
            builder: (ctx, f) => Transform.scale(scale: 1.0 + 0.035 * Curves.easeInOut.transform(_vida.value), child: f),
            child: Image.asset('assets/abertura.webp', fit: BoxFit.cover, alignment: Alignment.center, gaplessPlayback: true),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: MediaQuery.of(context).size.height * 0.17,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 300),
                        child: Text(
                          _etapa,
                          key: ValueKey(_etapa),
                          style: const TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.w800,
                            color: Color(0xFFF1EEFF),
                            shadows: [Shadow(color: Color(0xCC000000), blurRadius: 8)],
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      AnimatedBuilder(animation: Listenable.merge([_barra, _vida]), builder: (ctx, _) => _Barra(valor: _barra.value, brilho: _vida.value)),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Barra no estilo da arte: cápsula com borda dourada, enchimento roxo-magenta e uma faísca na ponta, com a porcentagem ao lado.
class _Barra extends StatelessWidget {
  const _Barra({required this.valor, required this.brilho});
  final double valor;
  final double brilho;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: LayoutBuilder(
            builder: (ctx, c) {
              final w = c.maxWidth;
              final cheio = max(18.0, (w - 6) * valor);
              return Container(
                height: 26,
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(999),
                  color: const Color(0xFF0C0630),
                  border: Border.all(color: const Color(0xFFE9A84B), width: 2),
                  boxShadow: [BoxShadow(color: const Color(0xFFB54BFF).withValues(alpha: 0.45 + 0.2 * brilho), blurRadius: 16)],
                ),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Container(
                      width: cheio,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(999),
                        gradient: const LinearGradient(colors: [Color(0xFF7B2FF7), Color(0xFFB54BFF), Color(0xFFFF6AD5)]),
                      ),
                    ),
                    // faísca na ponta
                    Positioned(
                      left: cheio - 14,
                      top: -6,
                      child: Container(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(colors: [
                            Colors.white.withValues(alpha: 0.95),
                            const Color(0xFFFFC56B).withValues(alpha: 0.75),
                            const Color(0x00FF8A3D),
                          ], stops: const [0, 0.35, 1]),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
        const SizedBox(width: 10),
        SizedBox(
          width: 50,
          child: Text('${(valor * 100).round()}%',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white, shadows: [Shadow(color: Color(0xCC000000), blurRadius: 6)])),
        ),
      ],
    );
  }
}
