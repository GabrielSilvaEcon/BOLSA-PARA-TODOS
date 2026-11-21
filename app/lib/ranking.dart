import 'dart:convert';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'escudo.dart';
import 'navegacao.dart';

/// Central de rankings (aba Ranking): no topo, a sua divisão no jogo escolhido (troféus, barra até a próxima e a temporada);
/// abaixo, Trade Battle e Ticker Battle por troféus da temporada e a Carteira pelo retorno (geral, mês, semana ou risco),
/// cada um com Geral ou Amigos, pódio, sua posição e a classificação. Troféus só mudam em partidas online.
class RankingTela extends StatefulWidget {
  const RankingTela({super.key, required this.api});
  final Api api;

  @override
  State<RankingTela> createState() => _RankingTelaState();
}

/// Outras telas pedem um ranking específico (ex.: "Ver classificação" da Carteira abre a aba Ranking já na Carteira).
final rankingPedido = ValueNotifier<String?>(null);

const _ouro = Color(0xFFF2B84B);
const _lila = Color(0xFFBDB5E6);

class _RankingTelaState extends State<RankingTela> {
  String _jogo = 'trade';
  String _filtro = 'geral';
  String _periodo = 'geral';
  Map<String, dynamic>? _d, _t;
  bool _carregando = true;
  bool _falhou = false;

  @override
  void initState() {
    super.initState();
    final p = rankingPedido.value;
    if (p != null) {
      _jogo = p;
      rankingPedido.value = null;
    }
    rankingPedido.addListener(_pedido);
    _carregar();
  }

  @override
  void dispose() {
    rankingPedido.removeListener(_pedido);
    super.dispose();
  }

  void _pedido() {
    final p = rankingPedido.value;
    if (p == null) return;
    rankingPedido.value = null;
    _trocar(jogo: p);
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _falhou = false;
    });
    try {
      final rs = await Future.wait([
        widget.api.get('/ranking/$_jogo/tela?filtro=$_filtro&periodo=$_periodo'),
        if (_t == null) widget.api.get('/trofeus'),
      ]);
      if (!mounted) return;
      setState(() {
        _d = rs[0];
        if (rs.length > 1) _t = rs[1];
      });
      final fim = _t?['fim_temporada'];
      if (fim is Map) {
        _t!['fim_temporada'] = null;
        WidgetsBinding.instance.addPostFrameCallback((_) => _mostrarFimTemporada(fim));
      }
    } catch (_) {
      if (mounted) setState(() => _falhou = true);
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  void _trocar({String? jogo, String? filtro, String? periodo}) {
    setState(() {
      _jogo = jogo ?? _jogo;
      _filtro = filtro ?? _filtro;
      _periodo = periodo ?? _periodo;
      _d = null;
    });
    _carregar();
  }

  String _valor(Object? v) {
    if (v is! num) return '—';
    if (_jogo == 'carteira') {
      if (_periodo == 'risco') return v.toStringAsFixed(2).replaceAll('.', ',');
      return '${v >= 0 ? '+' : ''}${v.toStringAsFixed(2).replaceAll('.', ',')}%';
    }
    return '${v.toInt()}';
  }

  @override
  Widget build(BuildContext context) {
    final linhas = ((_d?['linhas'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final total = (_d?['total'] as num?)?.toInt() ?? 0;
    final eu = _d?['eu'] as Map<String, dynamic>?;
    final resto = linhas.length > 3 ? linhas.sublist(3) : const <Map<String, dynamic>>[];
    final euFora = eu != null && (eu['pos'] == null || (eu['pos'] as num) > 3 + resto.length);
    return Scaffold(
      backgroundColor: const Color(0xFF110C2E),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/jogos/fundo_batalha.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x99090722), Color(0xB8090722), Color(0xE0090722)],
                stops: [0, 0.4, 1],
              ),
            ),
          ),
          RefreshIndicator(
            onRefresh: _carregar,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 20),
                  children: [
                    if (_jogo != 'carteira' && _t != null) Entrada(ordem: 0, child: _minhaDivisao()),
                    if (_jogo == 'carteira') ClipRRect(borderRadius: BorderRadius.circular(16), child: Image.asset('assets/jogos/banner_ranking.webp', fit: BoxFit.cover)),
                    const SizedBox(height: 10),
                    _abas(),
                    const SizedBox(height: 8),
                    _filtros(),
                    const SizedBox(height: 10),
                    if (_carregando && _d == null)
                      const Padding(padding: EdgeInsets.all(30), child: Center(child: CircularProgressIndicator()))
                    else if (_falhou && _d == null)
                      _vazio('O ranking não carregou agora. Tente de novo em instantes.')
                    else if (total == 0) ...[
                      _vazio(_jogo == 'carteira'
                          ? 'Ainda não há participantes neste ranking. Ele mostra quem tem a carteira ativa há alguns pregões.'
                          : _filtro == 'amigos'
                              ? 'Nenhum amigo seu jogou online nesta temporada ainda. Desafie alguém!'
                              : 'Ninguém jogou online nesta temporada ainda. Seja o primeiro a ganhar troféus!'),
                      const SizedBox(height: 8),
                      if (_jogo != 'carteira') FilledButton.icon(onPressed: () => abrirAba(1), icon: const Icon(Icons.play_arrow_rounded), label: Text('Jogar ${_d?['nome'] ?? ''} online')),
                    ] else ...[
                      _card(switch (_jogo) {
                        'carteira' => switch (_periodo) {
                            'risco' => 'Retorno por unidade de risco (Sharpe) desde o início: premia quem ganha sem apostar tudo num papel.',
                            'mes' => 'Retorno da carteira virtual neste mês.',
                            'semana' => 'Retorno da carteira virtual nesta semana.',
                            _ => 'Retorno da carteira virtual desde o início.',
                          },
                        _ => 'Troféus da temporada: vencer partidas online dá troféus e perder tira. Vencer quem tem mais troféus vale mais.',
                      }),
                      const SizedBox(height: 6),
                      _podio(linhas.take(3).toList()),
                      if (euFora) ...[
                        _sec('Sua posição', null),
                        _lista([eu]),
                      ],
                      if (resto.isNotEmpty) ...[
                        _sec('Classificação', '$total jogador${total == 1 ? '' : 'es'}'),
                        _lista(resto),
                      ],
                      const SizedBox(height: 10),
                      Text('${_d?['rotulo'] ?? 'Atualizado'} às ${_d?['hora'] ?? '--:--'}', style: const TextStyle(fontSize: 12, color: _lila)),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- topo: a sua divisão no jogo escolhido
  Widget _minhaDivisao() {
    final g = ((_t?['jogos'] as Map?)?[_jogo] as Map?) ?? const {};
    final dv = (g['divisao'] as Map?) ?? const {};
    final cor = Escudo.corDe(dv['cor']);
    final tp = (_t?['temporada'] as Map?) ?? const {};
    final prox = dv['prox'] as Map?;
    return Pressionavel(
      aoTocar: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DivisoesTela(t: _t!, jogo: _jogo))),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: cor, width: 2),
          gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(cor, const Color(0xFF2A1A6E), 0.55)!, const Color(0xFF120850)]),
          boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 18)],
        ),
        child: Row(children: [
          Flutua(child: Escudo.de(dv, tamanho: 84)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${dv['nome'] ?? 'Bronze'}', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Color.lerp(cor, Colors.white, 0.35))),
              Row(children: [
                const Icon(Icons.emoji_events_rounded, color: _ouro, size: 20),
                const SizedBox(width: 4),
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: ((g['t'] as num?) ?? 0).toDouble()),
                  duration: const Duration(milliseconds: 900),
                  builder: (ctx, v, _) => Text('${v.round()} troféus', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                ),
              ]),
              const SizedBox(height: 6),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: ((dv['pct'] as num?) ?? 0).toDouble()),
                duration: const Duration(milliseconds: 1100),
                curve: Curves.easeOutCubic,
                builder: (ctx, v, _) => ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(value: v, minHeight: 9, backgroundColor: const Color(0x55120850), color: cor),
                ),
              ),
              const SizedBox(height: 4),
              Text(prox == null ? 'Divisão máxima!' : 'Faltam ${dv['falta']} para ${prox['nome']}', style: const TextStyle(fontSize: 12, color: _lila)),
              Text('Temporada ${tp['rotulo'] ?? ''} · acaba em ${tp['dias_restantes'] ?? '—'} dias', style: const TextStyle(fontSize: 11.5, color: _lila)),
            ]),
          ),
          const Icon(Icons.chevron_right_rounded, color: Colors.white),
        ]),
      ),
    );
  }

  void _mostrarFimTemporada(Map fim) {
    final jogos = (fim['jogos'] as Map?) ?? const {};
    showDialog<void>(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: const Color(0xFF1B1462),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24), side: const BorderSide(color: _ouro, width: 2)),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Fim da temporada!', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: _ouro)),
            const SizedBox(height: 10),
            for (final e in jogos.entries)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(children: [
                  Escudo(id: '${(e.value as Map)['id']}', cor: Colors.amber, tamanho: 40),
                  const SizedBox(width: 10),
                  Expanded(
                      child: Text('${e.key == 'trade' ? 'Trade Battle' : 'Ticker Battle'}: ${(e.value as Map)['divisao']} (${(e.value as Map)['max']} troféus)',
                          style: const TextStyle(color: Colors.white))),
                ]),
              ),
            const SizedBox(height: 8),
            Text('Você ganhou +${fim['premio']} TC pela maior divisão alcançada.', textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
            const SizedBox(height: 4),
            const Text('Quem passou do Ouro volta metade do caminho até ele. Boa temporada!', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: _lila)),
            const SizedBox(height: 12),
            FilledButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Continuar')),
          ]),
        ),
      ),
    );
  }

  // ---- abas e filtros
  Widget _chip(String rot, bool on, VoidCallback f, {double altura = 40}) => Expanded(
        child: GestureDetector(
          onTap: f,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            height: altura,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: on ? const LinearGradient(colors: [Color(0xFF7C5CFF), Color(0xFFB06BFF)]) : null,
              color: on ? null : const Color(0xFF1B1442),
              border: Border.all(color: on ? const Color(0xFFB9A8FF) : const Color(0x558B6CFF)),
            ),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Padding(padding: const EdgeInsets.symmetric(horizontal: 6), child: Text(rot, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white))),
            ),
          ),
        ),
      );

  Widget _abas() => Row(children: [
        for (final (i, (id, rot)) in const [('trade', 'Trade Battle'), ('ticker', 'Ticker Battle'), ('carteira', 'Carteira')].indexed) ...[
          if (i > 0) const SizedBox(width: 6),
          _chip(rot, _jogo == id, () => _trocar(jogo: id)),
        ],
      ]);

  Widget _filtros() => Row(children: [
        _chip('Geral', _filtro == 'geral', () => _trocar(filtro: 'geral'), altura: 32),
        const SizedBox(width: 6),
        _chip('Amigos', _filtro == 'amigos', () => _trocar(filtro: 'amigos'), altura: 32),
        if (_jogo == 'carteira') ...[
          const SizedBox(width: 12),
          for (final (id, rot) in const [('geral', 'Tudo'), ('mes', 'Mês'), ('semana', 'Semana'), ('risco', 'Risco')]) ...[
            const SizedBox(width: 4),
            _chip(rot, _periodo == id, () => _trocar(periodo: id), altura: 32),
          ],
        ],
      ]);

  Widget _card(String texto) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFF5B4BD6), width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1B1470), Color(0xFF0E0840)]),
          boxShadow: const [BoxShadow(color: Color(0x665B4BD6), blurRadius: 12)],
        ),
        child: Text(texto, style: const TextStyle(fontSize: 12.8, height: 1.35, color: Color(0xFFD9D4F7))),
      );

  Widget _vazio(String texto) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0x8C8B6CFF), width: 1.5)),
        child: Text(texto, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13.8, color: Color(0xFFD9D4F7))),
      );

  Widget _sec(String t, String? extra) => Padding(
        padding: const EdgeInsets.fromLTRB(2, 12, 2, 4),
        child: Row(children: [
          Text(t, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
          const Spacer(),
          if (extra != null) Text(extra, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: _lila)),
        ]),
      );

  Widget _icone({double t = 15}) => _jogo == 'carteira'
      ? Icon(_periodo == 'risco' ? Icons.shield_rounded : Icons.trending_up_rounded, size: t, color: const Color(0xFF6BFF8A))
      : Icon(Icons.emoji_events_rounded, size: t, color: _ouro);

  // ---- pódio: 2º, 1º e 3º lado a lado
  Widget _podio(List<Map<String, dynamic>> top) {
    const cores = [Color(0xFF9EA3C6), Color(0xFFE0A21A), Color(0xFFB0612A)];
    const alturas = [54.0, 74.0, 42.0];
    const tamanhos = [52.0, 64.0, 52.0];
    final ordem = [1, 0, 2];
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        for (var k = 0; k < 3; k++) ...[
          if (k > 0) const SizedBox(width: 6),
          Expanded(
            flex: k == 1 ? 115 : 100,
            child: ordem[k] < top.length
                ? Column(children: [
                    Stack(clipBehavior: Clip.none, children: [
                      _avatar(top[ordem[k]]['avatar_img'], tamanhos[k], cores[k], 3),
                      if (top[ordem[k]]['divisao'] is Map) Positioned(right: -8, bottom: -6, child: Escudo.de(top[ordem[k]]['divisao'] as Map, tamanho: 26)),
                    ]),
                    const SizedBox(height: 4),
                    Text('${top[ordem[k]]['nome'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.2, fontWeight: FontWeight.w800, color: Colors.white)),
                    Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      _icone(t: 13),
                      const SizedBox(width: 2),
                      Text(_valor(top[ordem[k]]['valor']), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: Color(0xFFFFE3A3))),
                    ]),
                    const SizedBox(height: 4),
                    Container(
                      height: alturas[k],
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [cores[k], const Color(0xE6140C40)]),
                        boxShadow: [BoxShadow(color: cores[k], blurRadius: 14)],
                      ),
                      child: Text('${top[ordem[k]]['pos']}', style: const TextStyle(fontSize: 25.6, fontWeight: FontWeight.w900, color: Colors.white)),
                    ),
                  ])
                : const SizedBox.shrink(),
          ),
        ],
      ],
    );
  }

  // ---- lista da classificação
  Widget _lista(List<Map<String, dynamic>> linhas) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFF5B4BD6), width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF17114A), Color(0xFF0A0720)], stops: [0, 0.9]),
        ),
        child: Column(children: [for (final (i, x) in linhas.indexed) _linha(x, primeira: i == 0)]),
      );

  Widget _linha(Map<String, dynamic> x, {bool primeira = false}) {
    final eu = x['eu'] == true;
    final v = x['valor'];
    final dv = x['divisao'] as Map?;
    final sub = _jogo == 'carteira'
        ? [if (x['dd'] is num) 'queda máx. ${(x['dd'] as num).toStringAsFixed(1).replaceAll('.', ',')}%', if (x['dias'] != null) '${x['dias']} pregões'].join(' · ')
        : [if (dv != null) '${dv['nome']}', if ('${x['usuario'] ?? ''}'.isNotEmpty) '@${x['usuario']}'].join(' · ');
    return Container(
      margin: eu ? const EdgeInsets.symmetric(vertical: 2) : EdgeInsets.zero,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
      decoration: eu
          ? BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _ouro, width: 2),
              gradient: const LinearGradient(colors: [Color(0x47F2B84B), Color(0x0FF2B84B)]),
              boxShadow: const [BoxShadow(color: Color(0x59F2B84B), blurRadius: 12)],
            )
          : BoxDecoration(border: primeira ? null : const Border(top: BorderSide(color: Color(0x14FFFFFF)))),
      child: Row(children: [
        SizedBox(width: 30, child: Text(x['pos'] == null ? '—' : '${x['pos']}', style: const TextStyle(fontWeight: FontWeight.w900, color: _lila))),
        _avatar(x['avatar_img'], 32, const Color(0xFF6C5CFF), 1.5),
        const SizedBox(width: 8),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${x['nome'] ?? ''}${eu ? ' (você)' : ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.white)),
            if (sub.isNotEmpty) Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 10.6, fontWeight: FontWeight.w600, color: _lila)),
          ]),
        ),
        if (dv != null) Padding(padding: const EdgeInsets.only(right: 6), child: Escudo.de(dv, tamanho: 28)),
        Container(
          padding: const EdgeInsets.fromLTRB(6, 3, 8, 3),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(10), color: const Color(0x55120850)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            _icone(),
            const SizedBox(width: 3),
            Text(_valor(v), style: TextStyle(fontWeight: FontWeight.w900, color: _jogo == 'carteira' && v is num && v < 0 ? const Color(0xFFFF6B87) : Colors.white)),
          ]),
        ),
      ]),
    );
  }

  Widget _avatar(Object? img, double tam, Color cor, double aro) {
    final texto = img is String && img.isNotEmpty ? img : null;
    final reserva = Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.cover);
    return Container(
      width: tam,
      height: tam,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xFF1B1545),
        boxShadow: [BoxShadow(color: cor, spreadRadius: aro), if (aro > 2) BoxShadow(color: cor, blurRadius: 14)],
      ),
      child: ClipOval(
        child: texto == null
            ? reserva
            : texto.startsWith('data:')
                ? Image.memory(base64Decode(texto.substring(texto.indexOf(',') + 1)), fit: BoxFit.cover, errorBuilder: (_, __, ___) => reserva)
                : Image.asset('assets/$texto', fit: BoxFit.cover, errorBuilder: (_, __, ___) => reserva),
      ),
    );
  }
}

/// Caminho das divisões (como a arte de referência): o urso no topo, a trilha Lenda → Bronze com o escudo, os troféus de cada
/// divisão e o prêmio de fim de temporada, a seta "Você está aqui" e o botão para ir jogar.
class DivisoesTela extends StatelessWidget {
  const DivisoesTela({super.key, required this.t, required this.jogo});
  final Map<String, dynamic> t;
  final String jogo;

  @override
  Widget build(BuildContext context) {
    final divs = ((t['divisoes'] as List?) ?? const []).cast<Map>();
    final meus = (((t['jogos'] as Map?)?[jogo] as Map?)?['t'] as num?)?.toInt() ?? 0;
    final atual = divs.lastIndexWhere((d) => meus >= ((d['min'] as num?) ?? 0));
    final dias = ((t['temporada'] as Map?)?['dias_restantes']) ?? '—';
    return Scaffold(
      backgroundColor: const Color(0xFF110C2E),
      body: Stack(fit: StackFit.expand, children: [
        Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
        Container(color: const Color(0xB30B0930)),
        SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: ListView(padding: const EdgeInsets.fromLTRB(14, 6, 14, 24), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  const Spacer(),
                  Text(jogo == 'trade' ? 'Trade Battle' : 'Ticker Battle', style: const TextStyle(fontWeight: FontWeight.w800, color: _lila)),
                ]),
                SizedBox(
                  height: 190,
                  child: Stack(children: [
                    Positioned(left: -6, bottom: 0, child: Flutua(child: Image.asset('assets/ranking/urso_bracos.webp', height: 185))),
                    Positioned(
                      left: 150,
                      right: 0,
                      top: 0,
                      child: Column(children: [
                        const Text('CAMINHO DAS', style: TextStyle(fontSize: 18, letterSpacing: 1, fontWeight: FontWeight.w900, color: Colors.white)),
                        ShaderMask(
                          shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFE9A0), Color(0xFFF2A50B)]).createShader(r),
                          child: const FittedBox(child: Text('DIVISÕES', style: TextStyle(fontSize: 40, fontWeight: FontWeight.w900, color: Colors.white))),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(16),
                            color: const Color(0xE61B1462),
                            border: Border.all(color: const Color(0xFF6A4FE6), width: 1.5),
                          ),
                          child: Row(children: [
                            const Icon(Icons.emoji_events_rounded, color: _ouro, size: 30),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text('Você tem $meus troféus. Vença partidas online para subir e mostre que é um TickerHunter!', style: const TextStyle(fontSize: 12.5, color: Colors.white)),
                            ),
                          ]),
                        ),
                      ]),
                    ),
                  ]),
                ),
                const SizedBox(height: 10),
                for (final (i, d) in divs.reversed.indexed)
                  Builder(builder: (ctx) {
                    final idx = divs.length - 1 - i;
                    final cor = Escudo.corDe(d['cor']);
                    final aqui = idx == atual;
                    return Entrada(
                      ordem: i,
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: SizedBox(
                          height: 96,
                          child: Stack(clipBehavior: Clip.none, children: [
                            Positioned(
                              left: 46,
                              right: 0,
                              top: 10,
                              bottom: 10,
                              child: Container(
                                padding: const EdgeInsets.only(left: 62, right: 12),
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(color: aqui ? Colors.white : cor.withValues(alpha: 0.85), width: aqui ? 2.5 : 1.6),
                                  gradient: LinearGradient(colors: [Color.lerp(cor, const Color(0xFF160B5E), 0.55)!, const Color(0xF0120850)]),
                                  boxShadow: [BoxShadow(color: cor.withValues(alpha: aqui ? 0.8 : 0.35), blurRadius: aqui ? 20 : 10)],
                                ),
                                child: Row(children: [
                                  Expanded(
                                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                                      FittedBox(
                                        child: Text('${d['nome']}'.toUpperCase(),
                                            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Color.lerp(cor, Colors.white, 0.25))),
                                      ),
                                      Row(children: [
                                        const Icon(Icons.emoji_events_rounded, color: _ouro, size: 16),
                                        const SizedBox(width: 4),
                                        Text('${d['min']} troféus', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white)),
                                      ]),
                                    ]),
                                  ),
                                  Container(width: 1.5, height: 46, color: Colors.white24),
                                  const SizedBox(width: 10),
                                  Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    const Text('Prêmio da temporada', style: TextStyle(fontSize: 10.5, color: _lila)),
                                    Row(children: [
                                      Image.asset('assets/home/moeda_tc.webp', height: 24, errorBuilder: (_, __, ___) => const Icon(Icons.toll_rounded, color: _ouro)),
                                      const SizedBox(width: 4),
                                      Text('${d['premio']} TC', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: _ouro)),
                                    ]),
                                  ]),
                                ]),
                              ),
                            ),
                            Positioned(left: 4, top: 0, bottom: 0, child: Opacity(opacity: idx > atual ? 0.55 : 1, child: Escudo(id: '${d['id']}', cor: cor, nivel: idx, tamanho: 96))),
                            if (aqui)
                              Positioned(
                                left: -6,
                                bottom: -2,
                                child: Pulso2(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(6), color: _ouro, border: Border.all(color: const Color(0xFF8A4E00))),
                                    child: const Text('VOCÊ ESTÁ AQUI', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w900, color: Color(0xFF3B2600))),
                                  ),
                                ),
                              ),
                          ]),
                        ),
                      ),
                    );
                  }),
                const SizedBox(height: 6),
                Row(children: [
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xE61B1462), border: Border.all(color: const Color(0xFF6A4FE6))),
                      child: Row(children: [
                        const Icon(Icons.calendar_month_rounded, color: Color(0xFFB59BFF)),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            const Text('A temporada termina em:', style: TextStyle(fontSize: 11, color: Colors.white)),
                            Text('$dias dias', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: _ouro)),
                          ]),
                        ),
                      ]),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Pressionavel(
                      aoTocar: () {
                        Navigator.of(context).popUntil((r) => r.isFirst);
                        abrirAba(1);
                      },
                      child: Container(
                        height: 62,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          gradient: const LinearGradient(colors: [Color(0xFF9B6BFF), Color(0xFF6A3BE0)]),
                          border: Border.all(color: Colors.white70, width: 1.5),
                          boxShadow: const [BoxShadow(color: Color(0xFF3A1E8A), offset: Offset(0, 4))],
                        ),
                        child: const Text('BORA SUBIR\nDE DIVISÃO?', textAlign: TextAlign.center, style: TextStyle(fontSize: 14, height: 1.1, fontWeight: FontWeight.w900, color: Colors.white)),
                      ),
                    ),
                  ),
                ]),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

/// Pulsar leve (a etiqueta "Você está aqui").
class Pulso2 extends StatefulWidget {
  const Pulso2({super.key, required this.child});
  final Widget child;

  @override
  State<Pulso2> createState() => _Pulso2State();
}

class _Pulso2State extends State<Pulso2> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(animation: _c, builder: (ctx, f) => Transform.scale(scale: 1 + 0.08 * _c.value, child: f), child: widget.child);
}
