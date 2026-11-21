import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'partida.dart';

/// Sala de espera do Trade Battle com amigos (como no app antigo, trader_battle_app._frag_sala): o código para passar aos amigos,
/// quem já entrou e o botão do criador para começar. Quando a partida começa, abre a mesa (a mesma da partida solo).
/// Dados do servidor (`GET /trade/salas/{id}`, a cada 2 segundos).
class SalaTela extends StatefulWidget {
  const SalaTela({super.key, required this.api, required this.salaId});
  final Api api;
  final String salaId;

  @override
  State<SalaTela> createState() => _SalaTelaState();
}

const _rotuloCorrida = {'rapida': 'Rápida', 'intermediaria': 'Intermediária', 'longa': 'Longa'};
const _lila = Color(0xFFD4E2F7);

class _SalaTelaState extends State<SalaTela> {
  Map<String, dynamic>? _sala;
  String? _erro;
  Timer? _relogio;
  bool _ocupado = false;
  bool _saiu = false;

  @override
  void initState() {
    super.initState();
    _consultar();
    _relogio = Timer.periodic(const Duration(seconds: 2), (_) => _consultar());
  }

  @override
  void dispose() {
    _relogio?.cancel();
    super.dispose();
  }

  Future<void> _consultar() async {
    if (_ocupado || _saiu) return;
    _ocupado = true;
    try {
      _aplicar(await widget.api.get('/trade/salas/${widget.salaId}'));
    } catch (e) {
      if (mounted && _sala == null) setState(() => _erro = e.toString());
    } finally {
      _ocupado = false;
    }
  }

  void _aplicar(Map<String, dynamic> r) {
    if (!mounted || _saiu) return;
    switch (r['estado']) {
      case 'jogo':
        _saiu = true;
        _relogio?.cancel();
        Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, salaId: widget.salaId)));
        break;
      case 'cancelada':
        _relogio?.cancel();
        setState(() => _erro = 'A sala foi cancelada.');
        break;
      default:
        setState(() {
          _sala = (r['sala'] as Map?)?.cast<String, dynamic>();
          _erro = null;
        });
    }
  }

  Future<void> _iniciar() async {
    try {
      _aplicar(await widget.api.post('/trade/salas/${widget.salaId}/iniciar'));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _sair() async {
    _saiu = true;
    _relogio?.cancel();
    try {
      await widget.api.post('/trade/salas/${widget.salaId}/sair');
    } catch (_) {
      // sair é melhor esforço: a sala expira sozinha
    }
    if (mounted) Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    final s = _sala;
    return Scaffold(
      backgroundColor: const Color(0xFF0C192E),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/jogos/fundo_batalha.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x80090722), Color(0x9E090722), Color(0xD6090722)],
                stops: [0, 0.4, 1],
              ),
            ),
          ),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 20),
                children: [
                  Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0x996CA3FF), width: 2),
                      boxShadow: const [BoxShadow(color: Color(0x806CA3FF), blurRadius: 18)],
                    ),
                    child: ClipRRect(borderRadius: BorderRadius.circular(16), child: Image.asset('assets/jogos/trade_hero.webp')),
                  ),
                  const SizedBox(height: 12),
                  if (_erro != null && s == null) ...[
                    _cartao(child: Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, color: Colors.white))),
                    const SizedBox(height: 10),
                    FilledButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('Voltar')),
                  ] else if (s == null)
                    const Padding(padding: EdgeInsets.all(30), child: Center(child: CircularProgressIndicator()))
                  else ...[
                    _codigo(s),
                    const SizedBox(height: 10),
                    _jogadores(s),
                    const SizedBox(height: 12),
                    if (s['criador'] == true) ...[
                      FilledButton.icon(
                        style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF12A83C),
                          foregroundColor: Colors.white,
                          minimumSize: const Size.fromHeight(52),
                          textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
                        ),
                        onPressed: ((s['n'] as num?) ?? 0) >= ((s['min'] as num?) ?? 2) ? _iniciar : null,
                        icon: const Icon(Icons.play_arrow_rounded),
                        label: const Text('Iniciar partida'),
                      ),
                      if (((s['n'] as num?) ?? 0) < ((s['min'] as num?) ?? 2))
                        const Padding(
                          padding: EdgeInsets.only(top: 8),
                          child: Text('Aguardando pelo menos mais 1 jogador para começar.',
                              textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: _lila)),
                        ),
                    ] else
                      const Text('Aguardando o criador iniciar a partida…',
                          textAlign: TextAlign.center, style: TextStyle(fontSize: 14, color: _lila)),
                    const SizedBox(height: 14),
                    OutlinedButton.icon(
                      onPressed: _sair,
                      icon: const Icon(Icons.logout),
                      label: const Text('Sair da sala'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Código grande da sala, com o botão de copiar para mandar aos amigos.
  Widget _codigo(Map<String, dynamic> s) {
    final cod = '${s['codigo'] ?? ''}';
    final corrida = _rotuloCorrida[s['corrida']] ?? '';
    return _cartao(
      borda: const Color(0xFFF2B84B),
      child: Column(
        children: [
          const Text('Código da sala', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFFFFE3A3))),
          const SizedBox(height: 4),
          Text(cod, style: const TextStyle(fontSize: 38, letterSpacing: 6, fontWeight: FontWeight.w900, color: Colors.white)),
          if (corrida.isNotEmpty) Text('Partida $corrida', style: const TextStyle(fontSize: 12.5, color: _lila)),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: cod));
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Código copiado. Mande para os seus amigos!')));
              }
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copiar código'),
          ),
          const SizedBox(height: 4),
          const Text('Passe o código para 1 a 3 amigos. Todos veem o mesmo gráfico e o mesmo relógio.',
              textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: _lila)),
        ],
      ),
    );
  }

  Widget _jogadores(Map<String, dynamic> s) {
    final lista = ((s['jogadores'] as List?) ?? const []).cast<Map>();
    return _cartao(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Jogadores ${s['n']}/${s['max']}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
          const SizedBox(height: 6),
          for (final j in lista)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  const Icon(Icons.person, color: Color(0xFF9BBFFF)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('${j['nick'] ?? ''}${j['voce'] == true ? ' (você)' : ''}',
                        style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: Colors.white)),
                  ),
                  Text(j['criador'] == true ? 'criador' : 'jogador', style: const TextStyle(fontSize: 12, color: _lila)),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _cartao({required Widget child, Color borda = const Color(0xFF4B82D6)}) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: borda, width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1B1470), Color(0xFF081E40)]),
          boxShadow: [BoxShadow(color: borda.withValues(alpha: 0.4), blurRadius: 12)],
        ),
        child: child,
      );
}
