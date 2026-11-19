import 'dart:convert';

import 'package:flutter/material.dart';

import 'alertas.dart';
import 'api.dart';

/// Cabeçalho fixo do app, igual ao do app antigo (uma linha só):
/// avatar com anel verde + "Nível N" + barra de XP · moeda + saldo de Ticker Coins · touro + posição no ranking · sino com alertas.
/// Fica no topo de todas as telas, com a linha verde embaixo. Dados do servidor (`GET /eu`).
class Cabecalho extends StatefulWidget {
  const Cabecalho({super.key, required this.api, this.abrirAlertas});
  final Api api;

  /// Abre a tela de alertas na aba aberta (quem monta o app passa isto; sem ele, o sino abre por cima).
  final Future<void> Function()? abrirAlertas;

  @override
  State<Cabecalho> createState() => CabecalhoState();
}

class CabecalhoState extends State<Cabecalho> {
  Map<String, dynamic>? _eu;
  bool _falhou = false;

  @override
  void initState() {
    super.initState();
    atualizar();
  }

  /// Relê nível, moedas, ranking e alertas (chamado ao abrir o app, ao voltar dos alertas e quando outra tela pede).
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

  static const _lila = Color(0xFFCFC8F5);
  static const _ouro = Color(0xFFFFD76A);

  @override
  Widget build(BuildContext context) {
    final nivel = _eu?['nivel'] as Map?;
    final pct = ((nivel?['pct'] as num?) ?? 0).toDouble().clamp(0.0, 1.0);
    final moedas = _eu?['moedas'];
    final pos = ((_eu?['ranking'] as Map?) ?? const {})['pos'];
    final alertas = _eu?['alertas'];
    final nAlertas = alertas is num ? alertas.toInt() : 0;
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 6, 4, 6),
      decoration: const BoxDecoration(
        color: Color(0xFF0E0B26),
        border: Border(bottom: BorderSide(color: Color(0xFF3DDC6A), width: 3)),
      ),
      child: Row(
        children: [
          // nível: avatar com anel, "Nível N" e a barra de XP
          Expanded(
            flex: 145,
            child: GestureDetector(
              onTap: _falhou ? atualizar : null,
              child: _pilula(
                padding: const EdgeInsets.fromLTRB(3, 3, 8, 3),
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
                            style: const TextStyle(fontSize: 13, height: 1, fontWeight: FontWeight.w900, color: Color(0xFFDDEBFF)),
                          ),
                          const SizedBox(height: 4),
                          Container(
                            height: 7,
                            decoration: BoxDecoration(color: const Color(0x73000000), borderRadius: BorderRadius.circular(99)),
                            alignment: Alignment.centerLeft,
                            child: FractionallySizedBox(
                              widthFactor: pct,
                              child: Container(
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(99),
                                  gradient: const LinearGradient(colors: [Color(0xFF16E0FF), Color(0xFF7CF7FF)]),
                                  boxShadow: const [BoxShadow(color: Color(0xFF16E0FF), blurRadius: 8)],
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
          ),
          const SizedBox(width: 4),
          // Ticker Coins: moeda + saldo + "TC"
          Expanded(
            flex: 100,
            child: _pilula(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Image.asset('assets/home/moeda_tc.webp', width: 22, height: 22),
                    const SizedBox(width: 5),
                    Text(
                      moedas is num ? _inteiro(moedas) : '—',
                      style: const TextStyle(fontSize: 16, height: 1, fontWeight: FontWeight.w900, color: _ouro),
                    ),
                    const SizedBox(width: 3),
                    const Text('TC', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: Color(0xFFFFE8A8))),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 4),
          // ranking: touro + posição
          Expanded(
            flex: 80,
            child: _pilula(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Row(
                  children: [
                    ClipOval(child: Image.asset('assets/home/touro.webp', width: 26, height: 26, fit: BoxFit.contain)),
                    const SizedBox(width: 5),
                    Text(
                      pos == null ? '—' : '#$pos',
                      style: const TextStyle(fontSize: 16, height: 1, fontWeight: FontWeight.w900, color: _ouro),
                    ),
                  ],
                ),
              ),
            ),
          ),
          // sino com o número de alertas não lidos
          SizedBox(
            width: 46,
            height: 44,
            child: Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                IconButton(
                  tooltip: 'Alertas',
                  padding: EdgeInsets.zero,
                  icon: const Icon(Icons.notifications_none_rounded, size: 32, color: Colors.white),
                  onPressed: () async {
                    if (widget.abrirAlertas != null) {
                      await widget.abrirAlertas!();
                    } else {
                      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => AlertasTela(api: widget.api)));
                    }
                    atualizar();
                  },
                ),
                if (nAlertas > 0)
                  Positioned(
                    top: -2,
                    right: 0,
                    child: IgnorePointer(
                      child: Container(
                        constraints: const BoxConstraints(minWidth: 20),
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFE53950),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: const Color(0xFF0E0B26), width: 1.5),
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
    );
  }

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

  /// Pílula do cabeçalho: 40 de altura, degradê roxo escuro e borda azul clara (mesmo estilo do app antigo).
  Widget _pilula({required Widget child, EdgeInsets padding = const EdgeInsets.symmetric(horizontal: 8, vertical: 3)}) {
    return Container(
      height: 40,
      padding: padding,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xEB28245C), Color(0xEB100E30)],
        ),
        border: Border.all(color: const Color(0x7378AAFF), width: 1.5),
        boxShadow: const [BoxShadow(color: Color(0x5550A0FF), blurRadius: 14, spreadRadius: -6)],
      ),
      child: DefaultTextStyle.merge(style: const TextStyle(color: _lila), child: child),
    );
  }

  /// Avatar equipado (arquivo do app ou imagem enviada pelo servidor), com o anel verde. Sem ele, mostra o mascote.
  Widget _avatar(Object? img) {
    final texto = img is String && img.isNotEmpty ? img : null;
    final mascote = Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.cover);
    return Container(
      width: 32,
      height: 32,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        color: Color(0xFF1B1545),
        boxShadow: [
          BoxShadow(color: Color(0xFF34E85E), spreadRadius: 2),
          BoxShadow(color: Color(0xFF34E85E), blurRadius: 8),
        ],
      ),
      child: ClipOval(
        child: texto == null
            ? mascote
            : texto.startsWith('data:')
                ? Image.memory(
                    base64Decode(texto.substring(texto.indexOf(',') + 1)),
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => mascote,
                  )
                : Image.asset('assets/$texto', fit: BoxFit.cover, errorBuilder: (_, __, ___) => mascote),
      ),
    );
  }
}
