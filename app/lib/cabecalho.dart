import 'dart:convert';

import 'package:flutter/material.dart';

import 'alertas.dart';
import 'api.dart';
import 'navegacao.dart';

/// Cabeçalho fixo do app, no visual da arte do jogo: barra roxa com moldura dourada e cantos recortados.
///   · avatar no aro dourado com a coroa + "Nível N" + barra de XP
///   · pilha de moedas + saldo de TC + botão "+" (abre a Loja)
///   · touro + posição no ranking + botão "+" (abre o Ranking)
///   · sino com o número de alertas não lidos
/// Fica no topo de todas as telas. Dados do servidor (`GET /eu`).
class Cabecalho extends StatefulWidget {
  const Cabecalho({super.key, required this.api, this.abrirAlertas});
  final Api api;

  /// Abre a tela de alertas na aba aberta (quem monta o app passa isto; sem ele, o sino abre por cima).
  final Future<void> Function()? abrirAlertas;

  @override
  State<Cabecalho> createState() => CabecalhoState();
}

/// Nível, moedas e ranking já trazidos pela tela de abertura: o cabeçalho abre preenchido (depois se atualiza sozinho).
Map<String, dynamic>? euInicial;

const _ouro = Color(0xFFFFC93C);
const _ouroEscuro = Color(0xFFE9A80C);

class CabecalhoState extends State<Cabecalho> {
  Map<String, dynamic>? _eu = euInicial;
  bool _falhou = false;

  @override
  void initState() {
    super.initState();
    atualizar();
    saldoMudou.addListener(atualizar);
  }

  @override
  void dispose() {
    saldoMudou.removeListener(atualizar);
    super.dispose();
  }

  /// Relê nível, moedas, ranking e alertas (ao abrir o app, ao voltar dos alertas e quando outra tela pede).
  Future<void> atualizar() async {
    try {
      final r = await widget.api.get('/eu');
      if (mounted) {
        setState(() {
          _eu = r;
          _falhou = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _falhou = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final nivel = _eu?['nivel'] as Map?;
    final pct = ((nivel?['pct'] as num?) ?? 0).toDouble().clamp(0.0, 1.0);
    final moedas = _eu?['moedas'];
    final pos = ((_eu?['ranking'] as Map?) ?? const {})['pos'];
    final alertas = _eu?['alertas'];
    final nAlertas = alertas is num ? alertas.toInt() : 0;
    return Container(
      padding: const EdgeInsets.fromLTRB(6, 16, 6, 8),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF1C0E55), Color(0xFF0E0B2E)],
        ),
      ),
      child: Container(
        height: 58,
        padding: const EdgeInsets.fromLTRB(4, 4, 4, 4),
        decoration: ShapeDecoration(
          shape: const BeveledRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            side: BorderSide(color: _ouroEscuro, width: 2),
          ),
          gradient: const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF4B2AB8), Color(0xFF2A1680)],
          ),
          shadows: const [BoxShadow(color: Color(0x88FFB020), blurRadius: 14, spreadRadius: -4)],
        ),
        child: Row(
          children: [
            // nível: avatar no aro dourado com a coroa, "Nível N" e a barra de XP
            Expanded(
              flex: 150,
              child: GestureDetector(
                onTap: _falhou ? atualizar : null,
                child: Row(
                  children: [
                    _avatar(_eu?['avatar_img']),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            nivel == null ? (_falhou ? 'Toque p/ atualizar' : 'Nível —') : 'Nível ${nivel['nivel']}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 15, height: 1, fontWeight: FontWeight.w900, color: Colors.white),
                          ),
                          const SizedBox(height: 5),
                          Container(
                            height: 9,
                            alignment: Alignment.centerLeft,
                            decoration: BoxDecoration(
                              color: const Color(0xFF120A3A),
                              borderRadius: BorderRadius.circular(99),
                              border: Border.all(color: const Color(0xFF6B4BE0)),
                            ),
                            child: FractionallySizedBox(
                              widthFactor: pct,
                              child: Container(
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(99),
                                  gradient: const LinearGradient(colors: [Color(0xFF16E0FF), Color(0xFF7CF7FF)]),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 4),
            // moedas
            Expanded(
              flex: 112,
              child: _caixa(
                child: Row(
                  children: [
                    Image.asset('assets/cabecalho/moedas.webp', width: 28, height: 28),
                    const SizedBox(width: 3),
                    Expanded(
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: Text.rich(
                          TextSpan(
                            children: [
                              TextSpan(
                                text: moedas is num ? _inteiro(moedas) : '—',
                                style: const TextStyle(fontSize: 19, color: _ouro),
                              ),
                              const TextSpan(text: ' TC', style: TextStyle(fontSize: 13, color: Colors.white)),
                            ],
                          ),
                          style: const TextStyle(fontWeight: FontWeight.w900),
                        ),
                      ),
                    ),
                    _mais(() => abrirAba(4)),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 4),
            // ranking
            Expanded(
              flex: 100,
              child: _caixa(
                child: Row(
                  children: [
                    Image.asset('assets/cabecalho/touro.webp', width: 28, height: 28),
                    const SizedBox(width: 3),
                    Expanded(
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: Text(
                          pos == null ? '—' : '#$pos',
                          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: _ouro),
                        ),
                      ),
                    ),
                    _mais(() => abrirAba(3)),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 4),
            // sino
            SizedBox(
              width: 46,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned.fill(
                    child: Container(
                      decoration: ShapeDecoration(
                        shape: const BeveledRectangleBorder(
                          borderRadius: BorderRadius.all(Radius.circular(8)),
                          side: BorderSide(color: Color(0xFF8B6CFF), width: 1.5),
                        ),
                        color: const Color(0xFF2E1890),
                      ),
                      child: IconButton(
                        tooltip: 'Alertas',
                        padding: EdgeInsets.zero,
                        icon: const Icon(Icons.notifications_none_rounded, size: 30, color: Colors.white),
                        onPressed: () async {
                          if (widget.abrirAlertas != null) {
                            await widget.abrirAlertas!();
                          } else {
                            await Navigator.of(context).push(MaterialPageRoute(builder: (_) => AlertasTela(api: widget.api)));
                          }
                          atualizar();
                        },
                      ),
                    ),
                  ),
                  if (nAlertas > 0)
                    Positioned(
                      top: -8,
                      right: -4,
                      child: IgnorePointer(
                        child: Container(
                          constraints: const BoxConstraints(minWidth: 20),
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFE53950),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: Colors.white, width: 1.5),
                          ),
                          child: Text(
                            nAlertas > 99 ? '99+' : '$nAlertas',
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w900),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Caixa das moedas e do ranking: cantos recortados, fundo roxo e borda dourada.
  Widget _caixa({required Widget child}) {
    return Container(
      height: double.infinity,
      padding: const EdgeInsets.fromLTRB(5, 2, 3, 2),
      decoration: ShapeDecoration(
        shape: const BeveledRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          side: BorderSide(color: Color(0xCCFFB23C), width: 1.5),
        ),
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF3A209A), Color(0xFF241270)],
        ),
      ),
      child: child,
    );
  }

  /// Botão verde "+" da arte (abre a Loja ou o Ranking).
  Widget _mais(VoidCallback acao) => GestureDetector(
        onTap: acao,
        child: Image.asset('assets/cabecalho/mais.webp', width: 24, height: 24),
      );

  /// 1234 vira "1.234".
  String _inteiro(num v) {
    final s = v.round().toString();
    final buf = StringBuffer();
    for (var i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) buf.write('.');
      buf.write(s[i]);
    }
    return buf.toString();
  }

  /// Avatar equipado no aro dourado, com a coroa em cima. Sem avatar, mostra o mascote.
  Widget _avatar(Object? img) {
    final texto = img is String && img.isNotEmpty ? img : null;
    final mascote = Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.cover);
    return SizedBox(
      width: 46,
      height: 46,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [
          Container(
            width: 46,
            height: 46,
            padding: const EdgeInsets.all(3),
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFFFFE27A), Color(0xFFB07A10)]),
              boxShadow: [BoxShadow(color: Color(0x99FFC93C), blurRadius: 8)],
            ),
            child: ClipOval(
              child: ColoredBox(
                color: const Color(0xFF1B1545),
                child: texto == null
                    ? mascote
                    : texto.startsWith('data:')
                        ? Image.memory(base64Decode(texto.substring(texto.indexOf(',') + 1)), fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => mascote)
                        : Image.asset('assets/$texto', fit: BoxFit.cover, errorBuilder: (_, __, ___) => mascote),
              ),
            ),
          ),
          Positioned(top: -15, child: Image.asset('assets/cabecalho/coroa.webp', width: 30)),
        ],
      ),
    );
  }
}
