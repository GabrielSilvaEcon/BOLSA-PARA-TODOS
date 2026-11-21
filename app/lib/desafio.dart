import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'partida.dart';

/// Desafio do dia (como as telas de referência): o mesmo gráfico do Trade Battle para todos, uma tentativa por dia.
/// Antes de jogar: urso, título, quanto falta, a regra, o gráfico trancado, quantos já jogaram, JOGAR e o top 3 de ontem.
/// Depois: sua nota e posição, o ranking do dia (Geral ou Amigos), os prêmios e "Volte amanhã" com a contagem.
class DesafioTela extends StatefulWidget {
  const DesafioTela({super.key, required this.api});
  final Api api;

  @override
  State<DesafioTela> createState() => _DesafioTelaState();
}

const _ouro = Color(0xFFF2B84B);
const _lilas = Color(0xFFD9D4F7);

String contagem(int s) {
  final h = s ~/ 3600, m = (s % 3600) ~/ 60, x = s % 60;
  return '${h}h ${m.toString().padLeft(2, '0')}min ${x.toString().padLeft(2, '0')}s';
}

class _DesafioTelaState extends State<DesafioTela> {
  Map<String, dynamic>? _d, _rk;
  String? _erro;
  String _filtro = 'geral';
  int _resta = 0;
  Timer? _relogio;

  @override
  void initState() {
    super.initState();
    _carregar();
    _relogio = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && _resta > 0) setState(() => _resta--);
    });
  }

  @override
  void dispose() {
    _relogio?.cancel();
    super.dispose();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/desafio');
      if (!mounted) return;
      setState(() {
        _d = r;
        _erro = null;
        _resta = (r['termina_em'] as num?)?.toInt() ?? 0;
      });
      final pr = r['premio_ontem'];
      if (pr is Map && pr['novo'] == true) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Desafio de ontem: você ficou em ${pr['pos']}º e ganhou +${pr['tc']} TC!')));
      }
      if ((r['meu'] as Map?)?['terminou'] == true) _ranking();
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  Future<void> _ranking() async {
    try {
      final r = await widget.api.get('/desafio/ranking?filtro=$_filtro');
      if (mounted) setState(() => _rk = r);
    } catch (_) {}
  }

  Future<void> _jogar() async {
    await Navigator.of(context, rootNavigator: true).push(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, inicio: '/desafio/jogar')));
    _carregar();
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final meu = d?['meu'] as Map?;
    final terminou = meu?['terminou'] == true;
    return Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(fit: StackFit.expand, children: [
        Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
        Container(color: const Color(0xBF0B0930)),
        SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: RefreshIndicator(
                onRefresh: _carregar,
                child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 24), children: [
                  Row(children: [
                    IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                    const Spacer(),
                    IconButton(onPressed: _regras, icon: const Icon(Icons.info_outline_rounded, color: Colors.white)),
                  ]),
                  SizedBox(
                    height: 210,
                    child: Stack(children: [
                      Positioned(left: -8, bottom: 0, child: Flutua(child: Image.asset(terminou ? 'assets/ranking/urso_vitoria.webp' : 'assets/ranking/urso_aponta.webp', height: 200))),
                      Positioned(right: 0, top: 0, child: Image.asset('assets/ranking/desafio_titulo.webp', height: 205)),
                    ]),
                  ),
                  if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
                  if (d == null && _erro != null) Padding(padding: const EdgeInsets.all(20), child: Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white))),
                  if (d != null) ...(terminou ? _depois(d, meu!) : _antes(d, meu)),
                ]),
              ),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _faixa(Widget child, {Color borda = const Color(0xFF6A4FE6)}) => Container(
        margin: const EdgeInsets.only(top: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), color: const Color(0xE61B1462), border: Border.all(color: borda, width: 1.6)),
        child: child,
      );

  List<Widget> _antes(Map d, Map? meu) {
    final top = ((d['top_ontem'] as List?) ?? const []).cast<Map>();
    final comecou = meu != null;
    return [
      _faixa(Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        const Icon(Icons.schedule_rounded, color: _ouro, size: 26),
        const SizedBox(width: 8),
        const Text('Termina em:  ', style: TextStyle(fontSize: 15, color: Colors.white)),
        Text(contagem(_resta), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: _ouro)),
      ])),
      _faixa(const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(Icons.emoji_events_outlined, color: Colors.white),
        SizedBox(width: 8),
        Flexible(child: Text('1 tentativa, o mesmo gráfico para todos.', style: TextStyle(fontSize: 15, fontStyle: FontStyle.italic, color: Colors.white))),
      ])),
      const SizedBox(height: 12),
      ClipRRect(borderRadius: BorderRadius.circular(20), child: Image.asset('assets/ranking/grafico_trancado.webp', fit: BoxFit.cover)),
      const SizedBox(height: 12),
      Row(children: [
        Expanded(
          flex: 4,
          child: Container(
            height: 76,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), color: const Color(0xE61B1462), border: Border.all(color: const Color(0xFF8B6CFF), width: 1.6)),
            child: Row(children: [
              const Icon(Icons.groups_rounded, color: Color(0xFFB59BFF), size: 34),
              const SizedBox(width: 8),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Text('Já jogaram hoje:', style: TextStyle(fontSize: 12, color: Colors.white)),
                  FittedBox(child: Text('${d['jogaram'] ?? 0}', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: _ouro))),
                ]),
              ),
            ]),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          flex: 5,
          child: Pressionavel(
            aoTocar: _jogar,
            child: Container(
              height: 76,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFD66B), Color(0xFFF29A0B)]),
                border: Border.all(color: const Color(0xFFFFF0B8), width: 2),
                boxShadow: const [BoxShadow(color: Color(0xFF8A4E00), offset: Offset(0, 5)), BoxShadow(color: Color(0x88F2B84B), blurRadius: 18)],
              ),
              child: Text(comecou ? 'CONTINUAR ▶' : 'JOGAR ▶', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: Color(0xFF3B1E00))),
            ),
          ),
        ),
      ]),
      if (top.isNotEmpty) ...[
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 18, 4, 8),
          child: Row(children: [
            Expanded(child: Divider(color: Color(0x66F2B84B))),
            Padding(
                padding: EdgeInsets.symmetric(horizontal: 8), child: Text('🏆 TOP 3 DE ONTEM', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: _ouro))),
            Expanded(child: Divider(color: Color(0x66F2B84B))),
          ]),
        ),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          for (final i in [1, 0, 2])
            if (i < top.length) Expanded(child: _podio(top[i], destaque: i == 0)) else const Expanded(child: SizedBox()),
        ]),
      ],
    ];
  }

  Widget _podio(Map x, {bool destaque = false}) {
    final cor = switch (x['pos']) { 1 => _ouro, 2 => const Color(0xFFC0C7D4), _ => const Color(0xFFCD7F32) };
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 3),
      padding: EdgeInsets.symmetric(vertical: destaque ? 14 : 10, horizontal: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: destaque ? const Color(0xE66B3A12) : const Color(0xE61B1462),
        border: Border.all(color: cor, width: 1.6),
      ),
      child: Column(children: [
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          CircleAvatar(radius: 12, backgroundColor: cor, child: Text('${x['pos']}', style: const TextStyle(fontWeight: FontWeight.w900, color: Color(0xFF2A1A00)))),
          const SizedBox(width: 4),
          _avatar(x['avatar_img'], 44, cor),
        ]),
        const SizedBox(height: 4),
        Text('${x['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
        Text('🏆 ${_nota(x['valor'])}', style: const TextStyle(fontWeight: FontWeight.w900, color: _ouro)),
      ]),
    );
  }

  String _nota(Object? v) => v is num ? v.toStringAsFixed(1).replaceAll('.', ',') : '—';

  List<Widget> _depois(Map d, Map meu) {
    final linhas = ((_rk?['linhas'] as List?) ?? const []).cast<Map>();
    final eu = _rk?['eu'] as Map?;
    final top = linhas.take(3).toList();
    final premios = ((d['premios'] as List?) ?? const []).cast<Map>();
    return [
      Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          color: const Color(0xE6160B5E),
          border: Border.all(color: _ouro, width: 2),
          boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 18)],
        ),
        child: Row(children: [
          Expanded(
            child: Column(children: [
              const Text('Sua nota', style: TextStyle(fontSize: 16, color: Colors.white)),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: ((meu['nota'] as num?) ?? 0).toDouble()),
                duration: const Duration(milliseconds: 1100),
                builder: (ctx, v, _) => FittedBox(child: Text(_nota(v), style: const TextStyle(fontSize: 44, fontWeight: FontWeight.w900, color: _ouro))),
              ),
            ]),
          ),
          Container(width: 1.5, height: 70, color: const Color(0x99F2B84B)),
          Expanded(
            child: Column(children: [
              const Text('Você ficou em', style: TextStyle(fontSize: 16, color: Colors.white)),
              Text(meu['pos'] == null ? '—' : '${meu['pos']}º', style: const TextStyle(fontSize: 40, fontWeight: FontWeight.w900, color: _ouro)),
              Text('de ${meu['de'] ?? '—'}', style: const TextStyle(fontWeight: FontWeight.w800, color: Colors.white)),
            ]),
          ),
        ]),
      ),
      const SizedBox(height: 12),
      Row(children: [
        for (final (id, rot, ic) in const [('geral', 'Geral', Icons.emoji_events_rounded), ('amigos', 'Amigos', Icons.groups_rounded)])
          Expanded(
            child: Pressionavel(
              aoTocar: () {
                setState(() => _filtro = id);
                _ranking();
              },
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 3),
                padding: const EdgeInsets.symmetric(vertical: 9),
                decoration: BoxDecoration(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
                  color: _filtro == id ? const Color(0xFF6A3BE0) : const Color(0xE61B1462),
                  border: Border.all(color: const Color(0xFF8B6CFF)),
                ),
                child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(ic, color: _filtro == id ? _ouro : Colors.white, size: 20),
                  const SizedBox(width: 6),
                  Text(rot, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                ]),
              ),
            ),
          ),
      ]),
      Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(color: const Color(0xE6160B5E), borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)), border: Border.all(color: const Color(0xFF8B6CFF))),
        child: Column(children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(6, 2, 6, 6),
            child: Row(children: [
              SizedBox(width: 34, child: Text('#', style: TextStyle(color: _lilas))),
              Expanded(child: Text('Jogador', style: TextStyle(color: _lilas))),
              Text('Nota', style: TextStyle(color: _lilas)),
            ]),
          ),
          if (_rk == null) const Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()),
          for (final x in top) _linha(x),
          if (eu != null && ((eu['pos'] as num?) ?? 0) > 3) ...[
            const Text('• • •', style: TextStyle(color: _lilas)),
            _linha(eu),
          ],
        ]),
      ),
      const SizedBox(height: 12),
      Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), color: const Color(0xE6160B5E), border: Border.all(color: _ouro, width: 1.4)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Text('🎁', style: TextStyle(fontSize: 22)),
            SizedBox(width: 6),
            Text('Prêmios (pagos amanhã)', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: _ouro)),
          ]),
          const SizedBox(height: 6),
          Row(children: [
            for (final p in premios)
              Expanded(
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0x55120850), border: Border.all(color: const Color(0x886A4FE6))),
                  child: Column(children: [
                    Text('${p['rotulo']}', style: const TextStyle(fontWeight: FontWeight.w800, color: Colors.white)),
                    Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Image.asset('assets/home/moeda_tc.webp', height: 22, errorBuilder: (_, __, ___) => const Icon(Icons.toll_rounded, color: _ouro)),
                      const SizedBox(width: 4),
                      Text('${p['tc']}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: _ouro)),
                    ]),
                  ]),
                ),
              ),
          ]),
        ]),
      ),
      const SizedBox(height: 12),
      _faixa(Row(children: [
        const Icon(Icons.calendar_month_rounded, color: Color(0xFFB59BFF), size: 34),
        const SizedBox(width: 10),
        const Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Volte amanhã para um novo', style: TextStyle(color: Colors.white)),
            Text('Desafio do dia!', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: _ouro)),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          const Text('Disponível em:', style: TextStyle(fontSize: 12, color: Colors.white)),
          Text(contagem(_resta), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: _ouro)),
        ]),
      ])),
    ];
  }

  Widget _linha(Map x) {
    final eu = x['eu'] == true;
    final pos = (x['pos'] as num?)?.toInt() ?? 0;
    final cor = switch (pos) { 1 => _ouro, 2 => const Color(0xFFC0C7D4), 3 => const Color(0xFFCD7F32), _ => const Color(0xFF8B6CFF) };
    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
      decoration: eu
          ? BoxDecoration(borderRadius: BorderRadius.circular(12), gradient: const LinearGradient(colors: [Color(0xFFF2A50B), Color(0xFF8A4E00)]), border: Border.all(color: const Color(0xFFFFE08A)))
          : const BoxDecoration(border: Border(bottom: BorderSide(color: Color(0x22FFFFFF)))),
      child: Row(children: [
        SizedBox(width: 34, child: CircleAvatar(radius: 13, backgroundColor: cor, child: Text('$pos', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: Color(0xFF2A1A00))))),
        _avatar(x['avatar_img'], 34, cor),
        const SizedBox(width: 8),
        Expanded(child: Text(eu ? 'Você' : '${x['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: Colors.white))),
        Text(_nota(x['valor']), style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: eu ? Colors.white : _ouro)),
      ]),
    );
  }

  Widget _avatar(Object? img, double tam, Color cor) {
    final t = img is String && img.isNotEmpty ? img : null;
    final reserva = Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.cover);
    return Container(
      width: tam,
      height: tam,
      decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFF1B1545), border: Border.all(color: cor, width: 2)),
      child: ClipOval(
        child: t == null
            ? reserva
            : t.startsWith('data:')
                ? Image.memory(base64Decode(t.substring(t.indexOf(',') + 1)), fit: BoxFit.cover, errorBuilder: (_, __, ___) => reserva)
                : Image.asset('assets/$t', fit: BoxFit.cover, errorBuilder: (_, __, ___) => reserva),
      ),
    );
  }

  void _regras() => showModalBottomSheet<void>(
        context: context,
        backgroundColor: const Color(0xFF16104A),
        builder: (ctx) => const Padding(
          padding: EdgeInsets.fromLTRB(18, 18, 18, 28),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Como funciona o Desafio do dia', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
            SizedBox(height: 10),
            Text('• Todo dia sai um gráfico real do Trade Battle, o mesmo para todos os jogadores.', style: TextStyle(color: Colors.white)),
            Text('• Você tem uma tentativa: começar a partida já conta, então jogue com calma.', style: TextStyle(color: Colors.white)),
            Text('• A nota é a pontuação da partida (70% operação, 30% leitura do gráfico).', style: TextStyle(color: Colors.white)),
            Text('• À meia-noite o desafio fecha. No dia seguinte você recebe o prêmio: top 10, top 100 ou participação.', style: TextStyle(color: Colors.white)),
          ]),
        ),
      );
}
