import 'package:flutter/material.dart';

import 'api.dart';
import 'carta_setup.dart';
import 'escudo.dart';
import 'perfil.dart' show imagemAvatar;

const _lilas = Color(0xFFD4E2F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);
const _azul = Color(0xFF4F9BFF);

/// Perfil de outro jogador (mesmo conteúdo do Streamlit: nível e XP, desempenho, jogos e rankings, conquistas e últimas partidas).
/// O servidor já filtra pela privacidade da pessoa: o que não vier, a tela não mostra.
void abrirPerfilJogador(BuildContext context, Api api, String h) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: const Color(0xFF10274A),
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
    builder: (ctx) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.8,
      minChildSize: 0.4,
      maxChildSize: 0.95,
      builder: (ctx, rolagem) => FutureBuilder<Map<String, dynamic>>(
        future: api.get('/social/perfil/$h'),
        builder: (ctx, s) {
          if (!s.hasData) {
            return SizedBox(height: 220, child: Center(child: s.hasError ? Padding(padding: const EdgeInsets.all(20), child: Text('${s.error}', style: const TextStyle(color: Colors.white))) : const CircularProgressIndicator()));
          }
          return PerfilJogadorConteudo(p: s.data!, rolagem: rolagem);
        },
      ),
    ),
  );
}

class PerfilJogadorConteudo extends StatelessWidget {
  const PerfilJogadorConteudo({super.key, required this.p, this.rolagem});
  final Map<String, dynamic> p;
  final ScrollController? rolagem;

  static String pts(Object? v) => v is num ? v.toStringAsFixed(1).replaceAll('.', ',') : '0';
  static String pos(Object? v) => v == null ? '—' : '#$v';

  Widget _titulo(String t, {String? dir}) => Padding(
        padding: const EdgeInsets.only(top: 18, bottom: 8),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Flexible(child: Text(t, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white))),
          if (dir != null) Text(dir, style: const TextStyle(fontSize: 12, color: _lilas)),
        ]),
      );

  Widget _dado(String v, String r, Color c) => Expanded(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 3),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: c.withValues(alpha: 0.2), border: Border.all(color: c)),
          child: Column(children: [
            FittedBox(child: Text(v, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
            Text(r, style: const TextStyle(fontSize: 11, color: Colors.white)),
          ]),
        ),
      );

  Widget _cartaoJogo(String nome, Color cor, String posicao, List<(String, String)> linhas) => Expanded(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 3),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: cor.withValues(alpha: 0.18), border: Border.all(color: cor)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Flexible(child: Text(nome, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white))),
              Text(posicao, style: TextStyle(fontWeight: FontWeight.w900, color: cor)),
            ]),
            const SizedBox(height: 6),
            for (final l in linhas)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  Flexible(child: Text(l.$1, style: const TextStyle(fontSize: 11.5, color: _lilas))),
                  Text(l.$2, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: Colors.white)),
                ]),
              ),
          ]),
        ),
      );

  /// A vitrine: a divisão de cada jogo (escudo e troféus) e os setups que a pessoa equipou. É o que se mostra para os outros: status e vontade de ter.
  Widget _vitrine(Map v) {
    final div = (v['divisao'] as Map?) ?? const {};
    final sets = ((v['setups'] as List?) ?? const []).whereType<Map>().map((e) => e.cast<String, dynamic>()).toList();
    Widget escudo(String jogo, String rotulo) {
      final d = (div[jogo] as Map?) ?? const {};
      if (d.isEmpty) return const Expanded(child: SizedBox.shrink());
      return Expanded(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 3),
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: Colors.white.withValues(alpha: 0.07), border: Border.all(color: Escudo.corDe(d['cor']).withValues(alpha: 0.8))),
          child: Column(children: [
            Escudo.de(d, tamanho: 50),
            const SizedBox(height: 4),
            Text(rotulo, style: const TextStyle(fontSize: 11, color: _lilas)),
            FittedBox(child: Text('${d['nome']} · ${d['trofeus']}', style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w900, color: Colors.white))),
          ]),
        ),
      );
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _titulo('🏆 Vitrine'),
      Row(children: [escudo('trade', 'Trade Battle'), escudo('ticker', 'Ticker Battle')]),
      const SizedBox(height: 10),
      if (sets.isEmpty)
        const Text('Nenhum setup equipado.', textAlign: TextAlign.center, style: TextStyle(color: _lilas))
      else
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [for (final s in sets) Padding(padding: const EdgeInsets.symmetric(horizontal: 6), child: CartaSetup(setup: s, largura: 128))]),
    ]);
  }

  Widget _partida(Map h) {
    final trade = h['jogo'] == 'trade';
    final r = '${h['r'] ?? ''}';
    final em = '${h['em'] ?? ''}';
    final data = em.length >= 10 ? '${em.substring(8, 10)}/${em.substring(5, 7)}' : '';
    final String texto;
    final Color cor;
    if (trade) {
      texto = '${pts(h['pts'])} pts${h['pos'] != null ? ' · ${h['pos']}º lugar' : ''}';
      cor = (h['pts'] is num && (h['pts'] as num) < 0) ? _vermelho : _verde;
    } else {
      texto = r == 'v' ? 'Vitória' : (r == 'd' ? 'Derrota' : (r == 'e' ? 'Empate' : '—'));
      cor = r == 'v' ? _verde : (r == 'd' ? _vermelho : _ouro);
    }
    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: Colors.white.withValues(alpha: 0.07), border: Border(left: BorderSide(color: cor, width: 4))),
      child: Row(children: [
        Icon(trade ? Icons.candlestick_chart_rounded : Icons.style_rounded, size: 18, color: cor),
        const SizedBox(width: 8),
        Expanded(child: Text(trade ? 'Trade Battle' : 'Ticker Battle', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700))),
        Flexible(child: Text(texto, overflow: TextOverflow.ellipsis, style: TextStyle(color: cor, fontWeight: FontWeight.w900))),
        if (data.isNotEmpty) Padding(padding: const EdgeInsets.only(left: 10), child: Text(data, style: const TextStyle(fontSize: 11, color: _lilas))),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final jg = (p['jogos'] as Map?) ?? const {};
    final t = (jg['trade'] as Map?) ?? const {}, k = (jg['ticker'] as Map?) ?? const {};
    final cq = p['conquistas'] as Map?;
    final es = p['estat'] as Map?;
    final medalhas = ((p['medalhas'] as List?) ?? const []).whereType<Map>().take(12).toList();
    final hist = ((p['historico'] as List?) ?? const []).whereType<Map>().toList();
    final desde = '${p['desde'] ?? ''}';
    final taxa = es?['taxa'];
    return ListView(
      controller: rolagem,
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
      children: [
        Center(
          child: Container(
            width: 86,
            height: 86,
            decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white.withValues(alpha: 0.8), width: 2), color: const Color(0xFF152845)),
            child: ClipOval(child: imagemAvatar(p['avatar_img'])),
          ),
        ),
        const SizedBox(height: 8),
        Center(child: Text('${p['nome']}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: Colors.white))),
        Center(child: Text(['@${p['usuario']}', if ('${p['titulo'] ?? ''}'.isNotEmpty) '${p['titulo']}'].join(' · '), style: const TextStyle(color: _lilas))),
        if ('${p['bio'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text('${p['bio']}', textAlign: TextAlign.center, style: const TextStyle(color: Colors.white))),
        if (desde.length >= 7) Padding(padding: const EdgeInsets.only(top: 6), child: Text('No TickerHunters desde ${desde.substring(5, 7)}/${desde.substring(0, 4)}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: _lilas))),
        if (p['xp'] != null) ...[
          const SizedBox(height: 14),
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Flexible(child: Text('⭐ ${p['xp']} XP', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white))),
            Text(p['xp_max'] == true ? 'Nível máximo' : 'Nível ${p['nivel'] ?? ''}', style: const TextStyle(color: _lilas)),
          ]),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(value: ((p['xp_pct'] as num?) ?? 0).toDouble().clamp(0.0, 1.0), minHeight: 9, backgroundColor: Colors.white12, color: _ouro),
          ),
        ],
        if (p['restrito'] == true)
          Container(
            margin: const EdgeInsets.only(top: 16),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: Colors.white.withValues(alpha: 0.07)),
            child: const Text('🔒 Este perfil é visível só para amigos. Adicione para ver as conquistas e o desempenho.', textAlign: TextAlign.center, style: TextStyle(color: _lilas)),
          )
        else ...[
          if (p['vitrine'] is Map && (p['vitrine'] as Map).isNotEmpty) _vitrine(p['vitrine'] as Map),
          if (es != null) ...[
            _titulo('📊 Desempenho'),
            Row(children: [
              _dado('${es['partidas'] ?? 0}', 'partidas', _azul),
              _dado('${es['vitorias'] ?? 0}', 'vitórias', _verde),
              _dado('${es['derrotas'] ?? 0}', 'derrotas', _vermelho),
              _dado(taxa is num ? '${taxa.toStringAsFixed(0)}%' : '—', 'taxa de vitórias', _ouro),
            ]),
          ],
          if (jg.isNotEmpty) ...[
            _titulo('🎮 Jogos e rankings'),
            IntrinsicHeight(
              child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                _cartaoJogo('Trade Battle', _verde, pos(t['posicao']), [('Pontos', pts(t['pontos'])), ('Partidas', '${t['partidas'] ?? 0}'), ('1º lugar em sala', '${t['vitorias'] ?? 0}')]),
                _cartaoJogo('Ticker Battle', const Color(0xFF8B6CFF), pos(k['posicao']), [('Vitórias', '${k['vitorias'] ?? 0}'), ('Empates', '${k['empates'] ?? 0}'), ('Derrotas', '${k['derrotas'] ?? 0}')]),
              ]),
            ),
          ],
          if (cq != null) ...[
            _titulo('🏅 Conquistas e medalhas', dir: '${cq['ok']} de ${cq['total']}'),
            if (medalhas.isEmpty)
              const Text('Nenhuma conquista ainda.', style: TextStyle(color: _lilas))
            else
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final m in medalhas)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), color: _ouro.withValues(alpha: 0.18), border: Border.all(color: _ouro)),
                    child: Text('${m['emblema'] ?? ''} ${m['nome'] ?? ''}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white)),
                  ),
              ]),
          ],
          if (hist.isNotEmpty) ...[
            _titulo('🕑 Últimas partidas'),
            for (final h in hist) _partida(h),
          ],
          if (es == null && jg.isEmpty && hist.isEmpty && cq == null) const Padding(padding: EdgeInsets.only(top: 16), child: Text('Este jogador escolheu não mostrar as estatísticas.', textAlign: TextAlign.center, style: TextStyle(color: _lilas))),
        ],
      ],
    );
  }
}
