import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';

/// Histórico de partidas dos dois jogos (solo e online), da mais nova para a mais antiga: resumo no topo e cada partida em um cartão.
/// Trade Battle: pontos, posição, lucro, retorno e nota de qualidade. Ticker Battle: placar e as rodadas (toque para ver).
class HistoricoTela extends StatefulWidget {
  const HistoricoTela({super.key, required this.api});
  final Api api;

  @override
  State<HistoricoTela> createState() => _HistoricoTelaState();
}

const _lilas = Color(0xFFD4E2F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);

String _n(num v, int c) => v.toStringAsFixed(c).replaceAll('.', ',');

String _data(Object? em) {
  final t = '${em ?? ''}';
  return t.length >= 16 ? '${t.substring(8, 10)}/${t.substring(5, 7)} às ${t.substring(11, 16)}' : t;
}

class _HistoricoTelaState extends State<HistoricoTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String _jogo = 'trade';
  String? _aberto;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _erro = null);
    try {
      final r = await widget.api.get('/jogos/historico');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final itens = ((d?[_jogo] as List?) ?? const []).cast<Map>();
    final res = ((d?['resumo'] as Map?)?[_jogo] as Map?) ?? const {};
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  const Expanded(child: Text('Histórico de partidas', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                _abas(),
                const SizedBox(height: 10),
                if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
                if (d == null && _erro != null)
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(children: [
                      Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
                      const SizedBox(height: 10),
                      FilledButton.icon(onPressed: _carregar, icon: const Icon(Icons.refresh_rounded), label: const Text('Tentar de novo')),
                    ]),
                  ),
                if (d != null) ...[
                  Entrada(ordem: 0, child: _resumo(res)),
                  const SizedBox(height: 10),
                  if (itens.isEmpty)
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: _caixa(const Color(0xFF4F88E6), 'arena'),
                      child: Column(children: [
                        const Icon(Icons.sports_esports_rounded, color: Colors.white, size: 40),
                        const SizedBox(height: 6),
                        Text(_jogo == 'trade' ? 'Nenhuma partida do Trade Battle ainda.' : 'Nenhum duelo do Ticker Battle ainda.',
                            textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
                        const Text('Jogue uma partida e ela aparece aqui.', style: TextStyle(color: _lilas)),
                      ]),
                    ),
                  for (final (i, h) in itens.indexed) Entrada(ordem: 1 + i.clamp(0, 12), child: _jogo == 'trade' ? _trade(h) : _ticker(h)),
                  const SizedBox(height: 10),
                  const Text('Partidas contra o sistema aparecem aqui, mas só as online contam para o ranking.', textAlign: TextAlign.center, style: TextStyle(fontSize: 11.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  BoxDecoration _caixa(Color cor, [String? arte]) => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: cor.withValues(alpha: 0.9), width: 1.6),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(cor, const Color(0xFF0B2C5E), 0.5)!, Color.lerp(cor, const Color(0xFF082450), 0.8)!]),
        image: arte == null ? null : arteCartao(arte, opacidade: 0.4),
        boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.3), blurRadius: 12)],
      );

  Widget _abas() => Container(
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xCC0B2C5E), border: Border.all(color: const Color(0xFF4F88E6))),
        child: Row(children: [
          for (final (id, rot, cor) in const [('trade', 'Trade Battle', Color(0xFF26D07C)), ('ticker', 'Ticker Battle', Color(0xFF6CA3FF))])
            Expanded(
              child: Pressionavel(
                aoTocar: () => setState(() {
                  _jogo = id;
                  _aberto = null;
                }),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: _jogo == id ? cor : Colors.transparent),
                  child: Text(rot, textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                ),
              ),
            ),
        ]),
      );

  Widget _resumo(Map r) {
    Widget item(IconData ic, Color cor, String v, String t) => Expanded(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 3),
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [cor.withValues(alpha: 0.42), cor.withValues(alpha: 0.12)]),
              border: Border.all(color: cor.withValues(alpha: 0.85), width: 1.5),
            ),
            child: Column(children: [
              Icon(ic, color: cor, size: 24),
              FittedBox(child: Text(v, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white))),
              Text(t, style: const TextStyle(fontSize: 11, color: Colors.white)),
            ]),
          ),
        );
    final melhor = r['melhor'];
    return Row(children: [
      item(Icons.sports_esports_rounded, const Color(0xFF6CA3FF), '${r['total'] ?? 0}', 'Partidas'),
      item(Icons.emoji_events_rounded, _verde, '${r['vitoria'] ?? 0}', 'Vitórias'),
      if (_jogo == 'ticker') item(Icons.handshake_rounded, _ouro, '${r['empate'] ?? 0}', 'Empates'),
      if (_jogo == 'ticker') item(Icons.close_rounded, _vermelho, '${r['derrota'] ?? 0}', 'Derrotas'),
      if (_jogo == 'trade') item(Icons.star_rounded, _ouro, melhor is num ? _n(melhor, 1) : '—', 'Melhor pontuação'),
    ]);
  }

  (String, Color) _res(Object? r) => switch (r) {
        'vitoria' => ('Vitória', _verde),
        'derrota' => ('Derrota', _vermelho),
        'empate' => ('Empate', _ouro),
        _ => ('Treino', const Color(0xFF4F9BFF)),
      };

  Widget _selo(String t, Color c) => Container(
        margin: const EdgeInsets.only(left: 4),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0x99082450), border: Border.all(color: c)),
        child: Text(t, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: c)),
      );

  Widget _trade(Map h) {
    final (rot, cor) = _res(h['resultado']);
    final online = h['modo'] == 'online';
    final pts = h['pontos'];
    Widget dado(String t, String v, [Color c = Colors.white]) => Expanded(
          child: Column(children: [
            Text(v, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: c)),
            Text(t, style: const TextStyle(fontSize: 10.5, color: _lilas)),
          ]),
        );
    final lucro = h['lucro'], ret = h['ret'], qual = h['qual'];
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: _caixa(cor, online ? 'arena' : 'velas'),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(online ? Icons.groups_rounded : Icons.smart_toy_rounded, color: Colors.white, size: 20),
          const SizedBox(width: 6),
          Expanded(child: Text(online ? 'Online${h['n'] != null ? ' · ${h['n']} jogadores' : ''}' : 'Contra o sistema', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white))),
          if (online && h['pos'] != null) _selo('${h['pos']}º lugar', cor),
          _selo(rot, cor),
        ]),
        Text(_data(h['em']), style: const TextStyle(fontSize: 11.5, color: _lilas)),
        const SizedBox(height: 8),
        Row(children: [
          dado('Pontos', pts is num ? _n(pts, 1) : '—', _ouro),
          if (lucro is num) dado('Lucro', 'T\$ ${_n(lucro, 2)}', lucro >= 0 ? _verde : _vermelho),
          if (ret is num) dado('Retorno', '${ret >= 0 ? '+' : ''}${_n(ret, 2)}%', ret >= 0 ? _verde : _vermelho),
          if (qual is num) dado('Qualidade', '${qual.round()}/100'),
        ]),
      ]),
    );
  }

  static const _ind = {'dy_12m': 'Dividendos', 'ret_12m': 'Retorno 12m', 'vol': 'Volatilidade', 'roe': 'ROE', 'pl': 'P/L'};

  Widget _ticker(Map h) {
    final (rot, cor) = _res(h['resultado']);
    final online = h['modo'] == 'online';
    final pl = (h['placar'] as Map?) ?? const {};
    final rodadas = ((h['rodadas'] as List?) ?? const []).cast<Map>();
    final aberto = _aberto == h['id'];
    return Pressionavel(
      aoTocar: rodadas.isEmpty ? () {} : () => setState(() => _aberto = aberto ? null : '${h['id']}'),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: _caixa(cor, online ? 'arena' : 'touro'),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(online ? Icons.groups_rounded : Icons.smart_toy_rounded, color: Colors.white, size: 20),
            const SizedBox(width: 6),
            Expanded(child: Text(online ? 'Duelo online' : 'Contra o sistema', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white))),
            _selo(rot, cor),
          ]),
          Text(_data(h['em']), style: const TextStyle(fontSize: 11.5, color: _lilas)),
          if (pl.isNotEmpty) ...[
            const SizedBox(height: 6),
            Row(children: [
              Text('Você ${pl['jogador'] ?? 0}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
              const Text('  ×  ', style: TextStyle(fontSize: 16, color: _lilas)),
              Text('${pl['adversario'] ?? 0} Adversário', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
              const Spacer(),
              if (rodadas.isNotEmpty) Icon(aberto ? Icons.expand_less_rounded : Icons.expand_more_rounded, color: Colors.white),
            ]),
          ],
          if (aberto)
            for (final (i, r) in rodadas.indexed)
              Container(
                margin: const EdgeInsets.only(top: 6),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: const Color(0x66082450)),
                child: Row(children: [
                  Text('${i + 1}ª', style: const TextStyle(fontWeight: FontWeight.w900, color: _ouro)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('${r['jog']} × ${r['adv']}\n${_ind['${r['ind']}'] ?? r['ind'] ?? ''}', style: const TextStyle(fontSize: 12, color: Colors.white)),
                  ),
                  Icon(
                    r['venc'] == 'jogador' ? Icons.check_circle_rounded : (r['venc'] == 'empate' ? Icons.remove_circle_rounded : Icons.cancel_rounded),
                    color: r['venc'] == 'jogador' ? _verde : (r['venc'] == 'empate' ? _ouro : _vermelho),
                  ),
                ]),
              ),
        ]),
      ),
    );
  }
}
