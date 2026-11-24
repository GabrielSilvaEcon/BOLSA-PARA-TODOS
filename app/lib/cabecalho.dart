import 'dart:convert';

import 'package:flutter/material.dart';

import 'alertas.dart';
import 'api.dart';
import 'navegacao.dart';
import 'tour.dart';

/// Cabeçalho fixo do app, no visual da arte do jogo: barra roxa com moldura dourada e cantos recortados.
///   · avatar no aro dourado com a coroa + "Nível N" + barra de XP
///   · pilha de moedas + saldo de TC + botão "+" (abre a Loja)
///   · touro + posição no ranking + botão "+" (abre o Ranking)
///   · sino com o número de alertas não lidos
/// Fica no topo de todas as telas. Dados do servidor (`GET /eu`).
class Cabecalho extends StatefulWidget {
  const Cabecalho({super.key, required this.api, this.abrirAlertas, this.abrirPerfil});
  final Api api;

  /// Abre o Meu Perfil (toque no avatar/nível).
  final Future<void> Function()? abrirPerfil;

  /// Abre a tela de alertas na aba aberta (quem monta o app passa isto; sem ele, o sino abre por cima).
  final Future<void> Function()? abrirAlertas;

  @override
  State<Cabecalho> createState() => CabecalhoState();
}

/// Nível, moedas e ranking já trazidos pela tela de abertura: o cabeçalho abre preenchido (depois se atualiza sozinho).
Map<String, dynamic>? euInicial;

const _ouro = Color(0xFFFFC93C);

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
    final trofeus = _eu?['trofeus'];
    final alertas = _eu?['alertas'];
    final nAlertas = alertas is num ? alertas.toInt() : 0;
    final noNivel = nivel?['xp_no_nivel'], faixa = nivel?['xp_faixa'];
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 18, 8, 8),
      decoration: const BoxDecoration(
        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF0A1A45), Color(0xFF0E2560)]),
        border: Border(bottom: BorderSide(color: Color(0x553A6FD8))),
      ),
      child: SizedBox(
        height: 52,
        child: Row(
          children: [
            // nível: avatar no aro dourado com a coroa, "Nível N", barra de XP e "xp / próximo"
            Expanded(
              flex: 150,
              child: GestureDetector(
                onTap: _falhou ? atualizar : widget.abrirPerfil,
                child: Stack(
                  clipBehavior: Clip.none,
                  alignment: Alignment.centerLeft,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(left: 22),
                      padding: const EdgeInsets.fromLTRB(32, 4, 10, 4),
                      decoration: _pilula(),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            nivel == null ? (_falhou ? 'Toque p/ atualizar' : 'Nível —') : 'Nível ${nivel['nivel']}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 14, height: 1, fontWeight: FontWeight.w900, color: Colors.white),
                          ),
                          const SizedBox(height: 5),
                          Row(children: [
                            Expanded(
                              child: Container(
                                height: 8,
                                alignment: Alignment.centerLeft,
                                decoration: BoxDecoration(color: const Color(0xFF061131), borderRadius: BorderRadius.circular(99), border: Border.all(color: const Color(0xFF2B4F9E))),
                                child: FractionallySizedBox(
                                  widthFactor: pct,
                                  child: Container(
                                    decoration: BoxDecoration(
                                      borderRadius: BorderRadius.circular(99),
                                      gradient: const LinearGradient(colors: [Color(0xFF2F7BFF), Color(0xFF5BC8FF)]),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            if (noNivel is num && faixa is num && faixa > 0) ...[
                              const SizedBox(width: 5),
                              Text('${_inteiro(noNivel)}/${_inteiro(faixa)}', style: const TextStyle(fontSize: 9.5, fontWeight: FontWeight.w800, color: Color(0xFFD6E2FF))),
                            ],
                          ]),
                        ],
                      ),
                    ),
                    _avatar(_eu?['avatar_img']),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 5),
            // moedas
            Expanded(
              flex: 96,
              child: TourAlvo(id: 'cab_moedas', child: _caixa(
                icone: 'assets/home/ic_moeda.webp',
                texto: Text.rich(
                  TextSpan(children: [
                    TextSpan(text: moedas is num ? _inteiro(moedas) : '—', style: const TextStyle(fontSize: 17, color: Colors.white)),
                    const TextSpan(text: ' tc', style: TextStyle(fontSize: 13, color: Colors.white)),
                  ]),
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                mais: () => abrirAba(4),
              )),
            ),
            const SizedBox(width: 5),
            // troféus (do jogo em que está melhor)
            Expanded(
              flex: 92,
              child: _caixa(
                icone: 'assets/home/ic_trofeu.webp',
                texto: Text(trofeus is num ? _inteiro(trofeus) : '—', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: _ouro)),
                mais: () => abrirAba(3),
              ),
            ),
            const SizedBox(width: 2),
            // sino
            SizedBox(
              width: 38,
              child: Stack(
                clipBehavior: Clip.none,
                alignment: Alignment.center,
                children: [
                  GestureDetector(
                    onTap: () async {
                      if (widget.abrirAlertas != null) {
                        await widget.abrirAlertas!();
                      } else {
                        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => AlertasTela(api: widget.api)));
                      }
                      atualizar();
                    },
                    child: Semantics(
                      button: true,
                      label: 'Alertas',
                      child: ShaderMask(
                        blendMode: BlendMode.srcIn,
                        shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Colors.white, Color(0xFF9CC4FF)]).createShader(r),
                        child: const Icon(Icons.notifications_rounded, size: 36, shadows: [Shadow(color: Color(0xAA000000), offset: Offset(0, 2), blurRadius: 3)]),
                      ),
                    ),
                  ),
                  if (nAlertas > 0)
                    Positioned(
                      top: 2,
                      right: -2,
                      child: IgnorePointer(
                        child: Container(
                          constraints: const BoxConstraints(minWidth: 18),
                          height: 18,
                          padding: const EdgeInsets.symmetric(horizontal: 4),
                          alignment: Alignment.center,
                          decoration: BoxDecoration(color: const Color(0xFFE5243B), borderRadius: BorderRadius.circular(9), border: Border.all(color: Colors.white, width: 1.5)),
                          child: Text(nAlertas > 9 ? '9+' : '$nAlertas', style: const TextStyle(color: Colors.white, fontSize: 10.5, fontWeight: FontWeight.w900)),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            // engrenagem: perfil e configurações
            GestureDetector(
              onTap: widget.abrirPerfil,
              child: Semantics(button: true, label: 'Perfil e configurações', child: Image.asset('assets/home/ic_engrenagem.webp', width: 36, height: 36)),
            ),
          ],
        ),
      ),
    );
  }

  /// Cápsula azul-marinho das informações do topo (nível, moedas, troféus).
  BoxDecoration _pilula() => BoxDecoration(
        borderRadius: BorderRadius.circular(99),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF15306E), Color(0xFF0A1A45)]),
        border: Border.all(color: const Color(0xFF2E5AB0), width: 1.4),
        boxShadow: const [BoxShadow(color: Color(0x66000000), offset: Offset(0, 2), blurRadius: 4)],
      );

  /// Cápsula das moedas e dos troféus: ícone, valor e o botão verde "+".
  Widget _caixa({required String icone, required Widget texto, required VoidCallback mais}) {
    return Container(
      height: 40,
      padding: const EdgeInsets.fromLTRB(3, 2, 3, 2),
      decoration: _pilula(),
      child: Row(children: [
        Image.asset(icone, width: 30, height: 30),
        const SizedBox(width: 3),
        Expanded(child: FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: texto)),
        _mais(mais),
      ]),
    );
  }

  /// Botão verde "+" da arte (abre a Loja ou o Ranking).
  Widget _mais(VoidCallback acao) => GestureDetector(
        onTap: acao,
        child: Image.asset('assets/cabecalho/mais.webp', width: 28, height: 28),
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
                        ? Image.memory(base64Decode(texto.substring(texto.indexOf(',') + 1)), fit: BoxFit.cover, errorBuilder: (_, __, ___) => mascote)
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
