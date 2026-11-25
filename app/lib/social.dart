import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';
import 'perfil.dart' show imagemAvatar;
import 'sala.dart';
import 'ticker.dart';
import 'ticker_online.dart';
import 'trade.dart';

/// Ticker Battle precisa de baralho, e quem nunca abriu o Baú Iniciante não tem carta nenhuma (INICIAL = ()).
/// Só a aba do jogo abria o tutorial, então desafiar daqui morria num "Escolha pelo menos 3 cartas" sem saída:
/// as cartas vêm justamente do baú. Abre o tutorial antes, como a aba do jogo faz.
Future<void> _garantirBaralho(NavigatorState nav, Api api, String jogo) async {
  if (jogo != 'ticker') return;
  try {
    final c = await api.get('/ticker/central');
    if (c['tutorial_pendente'] == true && nav.mounted) {
      await nav.push(MaterialPageRoute(builder: (_) => TutorialBattleTela(api: api)));
    }
  } catch (_) {
    // servidor sem resposta: segue e deixa o desafio falhar com a mensagem dele
  }
}

/// Desafio PvP direto a um amigo, de qualquer tela (ex.: Revanche no fim da partida): abre a espera "VS" e, se ele aceitar,
/// a partida (Trade Battle na sala, Ticker Battle no duelo online).
Future<void> desafiarAmigo(BuildContext context, Api api, Map amigo, String jogo, {Object? euImg}) async {
  final nav = Navigator.of(context, rootNavigator: true);
  final msg = ScaffoldMessenger.maybeOf(context);
  await _garantirBaralho(nav, api, jogo);
  if (!nav.mounted) return;
  final r = await nav.push<Map>(MaterialPageRoute(builder: (_) => _Desafiando(api: api, amigo: amigo, jogo: jogo, euImg: euImg)));
  if (r != null && r['estado'] == 'aceito' && r['id'] != null) {
    await nav.push(MaterialPageRoute(builder: (_) => r['jogo'] == 'trade' ? SalaTela(api: api, salaId: '${r['id']}') : PartidaOnlineTela(api: api, pid: '${r['id']}')));
  } else if (r != null && r['msg'] != null) {
    msg?.showSnackBar(SnackBar(content: Text('${r['msg']}')));
  }
}

/// Social (atalho Amigos da aba Jogos): convites para jogar e pedidos de amizade no topo; a lista dos amigos em "On-line" (ativos hoje)
/// e "Classificação" (pontos do Trade Battle ou vitórias do Ticker Battle, com você no meio); tocar num amigo abre um balão com
/// Ver perfil e Batalha amistosa (cria a sala privada e manda o convite). Embaixo: Jogo rápido e Adicionar amigos.
/// As regras são as do app antigo (amigos.py): pedido, aceite, bloqueio e denúncia passam todos pelo servidor.
class SocialTela extends StatefulWidget {
  const SocialTela({super.key, required this.api});
  final Api api;

  @override
  State<SocialTela> createState() => _SocialTelaState();
}

const _lilas = Color(0xFFD4E2F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);
const _azul = Color(0xFF4F9BFF);

class _SocialTelaState extends State<SocialTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String _jogo = 'trade';
  bool _ocupado = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _erro = null);
    try {
      final r = await widget.api.get('/social');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  void _aviso(String t, {bool erro = false}) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t), backgroundColor: erro ? const Color(0xFF8A1F3A) : null));

  Future<Map<String, dynamic>?> _post(String caminho, Map<String, dynamic> corpo, {String? ok}) async {
    if (_ocupado) return null;
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post(caminho, corpo);
      if (ok != null || r['msg'] != null) _aviso('${r['msg'] ?? ok}');
      await _carregar();
      return r;
    } catch (e) {
      _aviso(e.toString(), erro: true);
      return null;
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  void _abrirSala(String jogo, Object? id) {
    if (id == null) return;
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => jogo == 'trade' ? SalaTela(api: widget.api, salaId: '$id') : PartidaOnlineTela(api: widget.api, pid: '$id')));
  }

  // ---- métrica da classificação
  num _valor(Map x) => _jogo == 'trade' ? (((x['trade'] as Map?)?['pts'] as num?) ?? -1e9) : (((x['ticker'] as Map?)?['v'] as num?) ?? -1e9);

  String _valorTxt(Map x) {
    if (_jogo == 'trade') {
      final p = (x['trade'] as Map?)?['pts'];
      return p is num ? (p.abs() < 0.05 ? 0.0 : p).toStringAsFixed(1).replaceAll('.', ',') : '—';
    }
    final v = (x['ticker'] as Map?)?['v'];
    return v is num ? '$v' : '—';
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final amigos = ((d?['amigos'] as List?) ?? const []).cast<Map>();
    final eu = d?['eu'] as Map?;
    final online = amigos.where((a) => a['atividade'] == 'hoje').toList();
    final classe = [
      ...amigos,
      if (eu != null) {...eu, '_eu': true}
    ]..sort((a, b) => _valor(b).compareTo(_valor(a)));
    final convites = ((d?['convites'] as List?) ?? const []).cast<Map>();
    final recebidos = ((d?['recebidos'] as List?) ?? const []).cast<Map>();
    final enviados = ((d?['enviados'] as List?) ?? const []).cast<Map>();
    var ordem = 0;
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        SafeArea(
          top: false,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: Column(children: [
                Expanded(
                  child: RefreshIndicator(
                    onRefresh: _carregar,
                    child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 16), children: [
                      Row(children: [
                        IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                        const Expanded(child: Text('Amigos', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                      ]),
                      Entrada(ordem: ordem++, child: _placa(convites.length, recebidos.length)),
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
                        for (final c in convites) Entrada(ordem: ordem++, child: _convite(c)),
                        for (final r in recebidos) Entrada(ordem: ordem++, child: _pedido(r)),
                        const SizedBox(height: 10),
                        Entrada(ordem: ordem++, child: _painel(online, classe, amigos.isEmpty)),
                        if (enviados.isNotEmpty) ...[
                          const Padding(
                            padding: EdgeInsets.fromLTRB(4, 14, 4, 6),
                            child: Text('Pedidos enviados', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
                          ),
                          for (final e in enviados) _linha(e, fim: TextButton(onPressed: () => _post('/social/remover', {'h': e['h']}, ok: 'Pedido cancelado.'), child: const Text('Cancelar'))),
                        ],
                      ],
                    ]),
                  ),
                ),
                _rodape(),
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  // ---- placa do topo: convites, pedidos e adicionar
  Widget _placa(int nConv, int nPed) {
    Widget botao(IconData ic, String t, Color cor, int n, VoidCallback f) => Expanded(
          child: Pressionavel(
            aoTocar: f,
            child: Stack(clipBehavior: Clip.none, children: [
              Container(
                height: 92,
                width: double.infinity,
                margin: const EdgeInsets.symmetric(horizontal: 4),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color.lerp(cor, Colors.white, 0.15)!, Color.lerp(cor, Colors.black, 0.35)!]),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.5), width: 1.5),
                  boxShadow: [BoxShadow(color: Color.lerp(cor, Colors.black, 0.6)!, offset: const Offset(0, 4)), BoxShadow(color: cor.withValues(alpha: 0.4), blurRadius: 12)],
                ),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(ic, color: Colors.white, size: 34),
                  const SizedBox(height: 4),
                  Text(t, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Colors.white)),
                ]),
              ),
              if (n > 0)
                Positioned(
                  right: 0,
                  top: -6,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), color: const Color(0xFFE5243B), border: Border.all(color: Colors.white, width: 1.5)),
                    child: Text('$n', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                  ),
                ),
            ]),
          ),
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 12, 8, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF8A4F1E), Color(0xFF5A3010)]),
        border: Border.all(color: _ouro, width: 2),
        image: arteCartao('moedas', opacidade: 0.25),
        boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 14)],
      ),
      child: Row(children: [
        botao(Icons.sports_esports_rounded, 'Convites', const Color(0xFF2F71F7), nConv,
            () => _aviso(nConv == 0 ? 'Nenhum convite agora. Quando um amigo te desafiar, aparece aqui.' : 'Os convites estão logo abaixo.')),
        botao(Icons.person_add_alt_1_rounded, 'Pedidos', const Color(0xFF2BA7C9), nPed, () => _aviso(nPed == 0 ? 'Nenhum pedido de amizade novo.' : 'Os pedidos estão logo abaixo.')),
        botao(Icons.search_rounded, 'Procurar', const Color(0xFF12A83C), 0, _adicionar),
      ]),
    );
  }

  Widget _avatar(Map x, {double tam = 46, bool online = false}) => Stack(clipBehavior: Clip.none, children: [
        Container(
          width: tam,
          height: tam,
          decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white.withValues(alpha: 0.8), width: 2), color: const Color(0xFF152845)),
          child: ClipOval(child: imagemAvatar(x['avatar_img'])),
        ),
        if (online)
          Positioned(
            right: -1,
            bottom: -1,
            child: Container(width: 14, height: 14, decoration: BoxDecoration(shape: BoxShape.circle, color: _verde, border: Border.all(color: Colors.white, width: 2))),
          ),
      ]);

  Widget _caixa(Color cor, Widget child, {String? arte}) => Container(
        margin: const EdgeInsets.only(top: 8),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: cor, width: 1.6),
          gradient: LinearGradient(colors: [Color.lerp(cor, const Color(0xFF0B2C5E), 0.45)!, Color.lerp(cor, const Color(0xFF082450), 0.8)!]),
          image: arte == null ? null : arteCartao(arte, opacidade: 0.35),
          boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.35), blurRadius: 12)],
        ),
        child: child,
      );

  Widget _convite(Map c) => _caixa(
        const Color(0xFF2F71F7),
        Row(children: [
          _avatar(c),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${c['nome']} te desafiou!', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
              Text('Desafio de ${c['jogo_nome']} · aceite para começar', style: const TextStyle(fontSize: 12, color: _lilas)),
            ]),
          ),
          IconButton(onPressed: () => _post('/social/convite/recusar', {'h': c['h']}), icon: const Icon(Icons.close_rounded, color: Colors.white70)),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C)),
            onPressed: () async {
              final r = await _post('/social/convite/entrar', {'h': c['h']});
              if (r != null) _abrirSala('${r['jogo']}', r['id']);
            },
            child: const Text('Aceitar'),
          ),
        ]),
        arte: 'arena',
      );

  Widget _pedido(Map r) => _caixa(
        const Color(0xFF2BA7C9),
        Row(children: [
          _avatar(r),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${r['nome']}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
              Text('@${r['usuario']} quer ser seu amigo', style: const TextStyle(fontSize: 12, color: _lilas)),
            ]),
          ),
          IconButton(onPressed: () => _post('/social/responder', {'h': r['h'], 'aceitar': false}), icon: const Icon(Icons.close_rounded, color: Colors.white70)),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C)),
            onPressed: () => _post('/social/responder', {'h': r['h'], 'aceitar': true}, ok: 'Agora vocês são amigos!'),
            child: const Text('Aceitar'),
          ),
        ]),
      );

  // ---- painel principal
  Widget _painel(List<Map> online, List<Map> classe, bool semAmigos) {
    Widget divisor(String t) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Row(children: [
            const Expanded(child: Divider(color: Color(0x669BBFFF), thickness: 2)),
            Padding(padding: const EdgeInsets.symmetric(horizontal: 10), child: Text(t, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Color(0xFFDEEAFF)))),
            const Expanded(child: Divider(color: Color(0x669BBFFF), thickness: 2)),
          ]),
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF3B75D6), Color(0xFF204F9A)]),
        border: Border.all(color: const Color(0xFF6CA3FF), width: 2),
        boxShadow: const [BoxShadow(color: Color(0x666CA3FF), blurRadius: 16)],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Text('Social', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white)),
          const Spacer(),
          for (final (id, rot) in const [('trade', 'Trade'), ('ticker', 'Ticker')])
            Padding(
              padding: const EdgeInsets.only(left: 6),
              child: Pressionavel(
                aoTocar: () => setState(() => _jogo = id),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    color: _jogo == id ? (id == 'trade' ? _verde : const Color(0xFF4B7DFF)) : const Color(0x55082450),
                    border: Border.all(color: Colors.white.withValues(alpha: 0.6)),
                  ),
                  child: Text(rot, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                ),
              ),
            ),
        ]),
        if (semAmigos)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Column(children: [
              const Icon(Icons.group_add_rounded, color: Colors.white, size: 46),
              const SizedBox(height: 6),
              const Text('Você ainda não tem amigos aqui.', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
              const Text('Procure pelo @usuario e desafie quem você conhece.', textAlign: TextAlign.center, style: TextStyle(color: _lilas)),
              const SizedBox(height: 10),
              FilledButton.icon(
                  onPressed: _adicionar, style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C)), icon: const Icon(Icons.add_rounded), label: const Text('Adicionar amigos')),
            ]),
          )
        else ...[
          divisor('On-line hoje'),
          if (online.isEmpty) const Center(child: Text('Nenhum amigo entrou hoje.', style: TextStyle(color: _lilas))),
          for (final a in online) _linha(a, online: true, toque: true),
          divisor('Classificação · ${_jogo == 'trade' ? 'pontos do Trade Battle' : 'vitórias no Ticker Battle'}'),
          for (final (i, a) in classe.indexed) _linha(a, pos: i + 1, toque: a['_eu'] != true, online: a['atividade'] == 'hoje'),
        ],
      ]),
    );
  }

  Widget _linha(Map a, {int? pos, bool online = false, bool toque = false, Widget? fim}) {
    final eu = a['_eu'] == true;
    final corPos = switch (pos) { 1 => _ouro, 2 => const Color(0xFFC0C7D4), 3 => const Color(0xFFCD7F32), _ => const Color(0xFF6CA3FF) };
    final cartao = Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.fromLTRB(8, 8, 10, 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: eu ? const [Color(0xFFFFE9B0), Color(0xFFE6C068)] : const [Color(0xFFE6F0FF), Color(0xFFC2D4F0)]),
        border: Border.all(color: eu ? _ouro : Colors.white, width: 1.5),
        boxShadow: const [BoxShadow(color: Color(0x66082450), offset: Offset(0, 3))],
      ),
      child: Row(children: [
        if (pos != null)
          Container(
            width: 28,
            margin: const EdgeInsets.only(right: 6),
            child: Text('$pos', textAlign: TextAlign.center, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color.lerp(corPos, Colors.black, 0.25))),
          ),
        _avatar(a, online: online),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${a['coroa'] == true ? '👑 ' : ''}${eu ? '${a['nome']} (você)' : '${a['nome']}'}',
                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Color(0xFF1A3A6E))),
            if (a['rival'] == true || a['h2h'] is Map)
              Row(children: [
                if (a['rival'] == true)
                  Container(
                    margin: const EdgeInsets.only(right: 6),
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(6), color: const Color(0xFFE5243B)),
                    child: const Text('RIVAL', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: Colors.white)),
                  ),
                if (a['h2h'] is Map)
                  Text('Você ${(a['h2h'] as Map)['v'] ?? 0} × ${(a['h2h'] as Map)['d'] ?? 0}', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: Color(0xFF3B75E0))),
              ]),
            Text(['@${a['usuario']}', if (a['nivel'] != null) 'Nível ${a['nivel']}'].join(' · '),
                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF9A6A10))),
          ]),
        ),
        fim ??
            Container(
              padding: const EdgeInsets.fromLTRB(6, 3, 10, 3),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(10), color: const Color(0xFF617595)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(_jogo == 'trade' ? Icons.emoji_events_rounded : Icons.military_tech_rounded, color: _ouro, size: 22),
                const SizedBox(width: 4),
                Text(_valorTxt(a), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
              ]),
            ),
      ]),
    );
    if (!toque) return cartao;
    return Builder(builder: (ctx) => Pressionavel(aoTocar: () => _menu(ctx, a), child: cartao));
  }

  // ---- balão do amigo
  void _menu(BuildContext ctx, Map a) {
    showDialog<void>(
      context: context,
      barrierColor: const Color(0x99000000),
      builder: (dctx) {
        Widget botao(String t, IconData ic, Color cor, VoidCallback f) => Padding(
              padding: const EdgeInsets.only(top: 8),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(backgroundColor: cor, minimumSize: const Size.fromHeight(46), textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900)),
                  onPressed: () {
                    Navigator.of(dctx).pop();
                    f();
                  },
                  icon: Icon(ic),
                  label: Text(t),
                ),
              ),
            );
        return Dialog(
          backgroundColor: Colors.white,
          insetPadding: const EdgeInsets.symmetric(horizontal: 50),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              _avatar(a, tam: 60),
              const SizedBox(height: 6),
              Text('${a['nome']}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Color(0xFF1A3A6E))),
              Text('@${a['usuario']}', style: const TextStyle(color: Color(0xFF5A77A8))),
              botao('Ver perfil', Icons.person_rounded, _azul, () => _verPerfil(a)),
              botao('Desafiar no Trade Battle', Icons.candlestick_chart_rounded, const Color(0xFF12A83C), () => _desafiar(a, 'trade')),
              botao('Desafiar no Ticker Battle', Icons.style_rounded, const Color(0xFF2F71F7), () => _desafiar(a, 'ticker')),
              TextButton(
                onPressed: () {
                  Navigator.of(dctx).pop();
                  _mais(a);
                },
                child: const Text('Mais opções', style: TextStyle(color: Color(0xFF5A77A8))),
              ),
            ]),
          ),
        );
      },
    );
  }

  Future<void> _desafiar(Map a, String jogo) async {
    final nav = Navigator.of(context);
    await _garantirBaralho(nav, widget.api, jogo);
    if (!mounted) return;
    final r = await nav.push<Map>(MaterialPageRoute(builder: (_) => _Desafiando(api: widget.api, amigo: a, jogo: jogo, euImg: (_d?['eu'] as Map?)?['avatar_img'])));
    if (!mounted) return;
    if (r != null && r['estado'] == 'aceito') {
      _abrirSala('${r['jogo']}', r['id']);
    } else if (r != null && r['msg'] != null) {
      _aviso('${r['msg']}');
    }
    _carregar();
  }

  void _mais(Map a) => showModalBottomSheet<void>(
        context: context,
        backgroundColor: const Color(0xFF10274A),
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
        builder: (ctx) => SafeArea(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            ListTile(
              leading: const Icon(Icons.person_remove_rounded, color: Colors.white),
              title: Text('Desfazer amizade com ${a['nome']}', style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                _post('/social/remover', {'h': a['h']}, ok: 'Amizade desfeita.');
              },
            ),
            ListTile(
              leading: const Icon(Icons.block_rounded, color: _vermelho),
              title: const Text('Bloquear', style: TextStyle(color: _vermelho)),
              subtitle: const Text('Vocês deixam de ver um ao outro.', style: TextStyle(color: _lilas)),
              onTap: () {
                Navigator.of(ctx).pop();
                _post('/social/bloquear', {'h': a['h']}, ok: 'Jogador bloqueado.');
              },
            ),
            ListTile(
              leading: const Icon(Icons.flag_rounded, color: _ouro),
              title: const Text('Denunciar perfil', style: TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                _denunciar(a);
              },
            ),
          ]),
        ),
      );

  void _denunciar(Map a) {
    const motivos = {'nome': 'Nome ou foto ofensivos', 'bio': 'Biografia ofensiva', 'golpe': 'Golpe, spam ou divulgação', 'trapaca': 'Trapaça nos jogos', 'outro': 'Outro motivo'};
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF10274A),
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Padding(padding: EdgeInsets.all(14), child: Text('Por que você quer denunciar?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white))),
          for (final m in motivos.entries)
            ListTile(
              title: Text(m.value, style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                _post('/social/denunciar', {'h': a['h'], 'motivo': m.key});
              },
            ),
        ]),
      ),
    );
  }

  Future<void> _verPerfil(Map a) async {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF10274A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
      builder: (ctx) => FutureBuilder<Map<String, dynamic>>(
        future: widget.api.get('/social/perfil/${a['h']}'),
        builder: (ctx, s) {
          if (!s.hasData) {
            return SizedBox(height: 220, child: Center(child: s.hasError ? Text('${s.error}', style: const TextStyle(color: Colors.white)) : const CircularProgressIndicator()));
          }
          final p = s.data!;
          final jg = (p['jogos'] as Map?) ?? const {};
          final t = (jg['trade'] as Map?) ?? const {}, k = (jg['ticker'] as Map?) ?? const {};
          final cq = p['conquistas'] as Map?;
          Widget dado(String v, String r, Color c) => Expanded(
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
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 26),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              _avatar(p, tam: 86),
              const SizedBox(height: 8),
              Text('${p['nome']}', style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: Colors.white)),
              Text(['@${p['usuario']}', if (p['nivel'] != null) 'Nível ${p['nivel']}', if ('${p['titulo'] ?? ''}'.isNotEmpty) '${p['titulo']}'].join(' · '), style: const TextStyle(color: _lilas)),
              if ('${p['bio'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text('${p['bio']}', textAlign: TextAlign.center, style: const TextStyle(color: Colors.white))),
              if (p['restrito'] == true) const Padding(padding: EdgeInsets.only(top: 10), child: Text('Este perfil mostra mais coisas só para amigos.', style: TextStyle(color: _lilas))),
              if (jg.isNotEmpty) ...[
                const SizedBox(height: 14),
                Row(children: [
                  dado(t['pontos'] is num ? (t['pontos'] as num).toStringAsFixed(1).replaceAll('.', ',') : '0', 'pts Trade', _verde),
                  dado('${k['vitorias'] ?? 0}', 'vitórias Ticker', const Color(0xFF4B7DFF)),
                  if (cq != null) dado('${cq['ok']}/${cq['total']}', 'conquistas', _ouro),
                ]),
              ],
            ]),
          );
        },
      ),
    );
  }

  // ---- rodapé: Jogo rápido e Adicionar amigos
  Widget _rodape() => Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
        decoration: const BoxDecoration(
          color: Color(0xEE1A407E),
          border: Border(top: BorderSide(color: Color(0xFF6CA3FF), width: 1.5)),
        ),
        child: Row(children: [
          Expanded(
            child: _botaoGrande('Jogo rápido', Icons.bolt_rounded, const Color(0xFF2E8BFF), () {
              showModalBottomSheet<void>(
                context: context,
                backgroundColor: const Color(0xFF10274A),
                builder: (ctx) => SafeArea(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Padding(padding: EdgeInsets.all(14), child: Text('Qual jogo?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white))),
                    ListTile(
                      leading: const Icon(Icons.candlestick_chart_rounded, color: _verde),
                      title: const Text('Trade Battle', style: TextStyle(color: Colors.white)),
                      onTap: () {
                        Navigator.of(ctx).pop();
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => TradeTela(api: widget.api)));
                      },
                    ),
                    ListTile(
                      leading: const Icon(Icons.style_rounded, color: Color(0xFF4B7DFF)),
                      title: const Text('Ticker Battle', style: TextStyle(color: Colors.white)),
                      onTap: () {
                        Navigator.of(ctx).pop();
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => TickerTela(api: widget.api)));
                      },
                    ),
                  ]),
                ),
              );
            }),
          ),
          const SizedBox(width: 10),
          Expanded(child: _botaoGrande('Adicionar amigos', Icons.person_add_alt_1_rounded, const Color(0xFF12A83C), _adicionar)),
        ]),
      );

  Widget _botaoGrande(String t, IconData ic, Color cor, VoidCallback f) => Pressionavel(
        aoTocar: f,
        child: Container(
          height: 54,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color.lerp(cor, Colors.white, 0.2)!, cor]),
            border: Border.all(color: Colors.white.withValues(alpha: 0.6), width: 1.5),
            boxShadow: [BoxShadow(color: Color.lerp(cor, Colors.black, 0.55)!, offset: const Offset(0, 4))],
          ),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(ic, color: Colors.white),
            const SizedBox(width: 6),
            Flexible(child: FittedBox(child: Text(t, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)))),
          ]),
        ),
      );

  // ---- adicionar amigos: busca por nome ou @usuario
  void _adicionar() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF10274A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
      builder: (ctx) => _Busca(
          api: widget.api,
          aoPedir: (u) async {
            final r = await _post('/social/pedir', {'usuario': u});
            return r != null;
          }),
    );
  }
}

class _Busca extends StatefulWidget {
  const _Busca({required this.api, required this.aoPedir});
  final Api api;
  final Future<bool> Function(String usuario) aoPedir;

  @override
  State<_Busca> createState() => _BuscaState();
}

class _BuscaState extends State<_Busca> {
  List<Map> _itens = const [];
  bool _buscando = false;
  String _ultimo = '';
  final Set<String> _pedidos = {};

  Future<void> _buscar(String t) async {
    _ultimo = t;
    if (t.trim().length < 2) {
      setState(() => _itens = const []);
      return;
    }
    setState(() => _buscando = true);
    try {
      final r = await widget.api.get('/social/buscar?texto=${Uri.encodeQueryComponent(t.trim())}');
      if (mounted && t == _ultimo) setState(() => _itens = ((r['itens'] as List?) ?? const []).cast<Map>());
    } catch (_) {
    } finally {
      if (mounted) setState(() => _buscando = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(16, 18, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('Adicionar amigos', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
          const SizedBox(height: 10),
          TextField(
            autofocus: true,
            onChanged: _buscar,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xFF1A3B6E),
              prefixIcon: const Icon(Icons.alternate_email_rounded, color: Color(0xFF9BBFFF)),
              hintText: 'Nome ou @usuario',
              hintStyle: const TextStyle(color: Color(0xFF93ADD6)),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
            ),
          ),
          const SizedBox(height: 8),
          if (_buscando) const LinearProgressIndicator(minHeight: 2),
          ConstrainedBox(
            constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.45),
            child: ListView(shrinkWrap: true, children: [
              for (final x in _itens)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(backgroundColor: const Color(0xFF152845), child: ClipOval(child: imagemAvatar(x['avatar_img']))),
                  title: Text('${x['nome']}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                  subtitle: Text('@${x['usuario']}', style: const TextStyle(color: _lilas)),
                  trailing: switch (_pedidos.contains('${x['usuario']}') ? 'enviada' : x['estado']) {
                    'amigos' => const Text('Amigo', style: TextStyle(color: _verde, fontWeight: FontWeight.w900)),
                    'enviada' => const Text('Pedido enviado', style: TextStyle(color: _lilas)),
                    _ => FilledButton(
                        style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C)),
                        onPressed: () async {
                          if (await widget.aoPedir('${x['usuario']}') && mounted) setState(() => _pedidos.add('${x['usuario']}'));
                        },
                        child: Text(x['estado'] == 'recebida' ? 'Aceitar' : 'Adicionar'),
                      ),
                  },
                ),
              if (!_buscando && _ultimo.trim().length >= 2 && _itens.isEmpty)
                const Padding(padding: EdgeInsets.all(12), child: Text('Ninguém encontrado com esse nome.', style: TextStyle(color: _lilas))),
            ]),
          ),
        ]),
      );
}

/// Quem desafia espera aqui: os dois avatares frente a frente, o relógio de 3 minutos e o botão Cancelar. Quando o amigo aceita, a tela
/// fecha e a partida abre direto; se ele recusar ou o tempo acabar, volta com o aviso.
class _Desafiando extends StatefulWidget {
  const _Desafiando({required this.api, required this.amigo, required this.jogo, this.euImg});
  final Api api;
  final Object? euImg;
  final Map amigo;
  final String jogo;

  @override
  State<_Desafiando> createState() => _DesafiandoState();
}

class _DesafiandoState extends State<_Desafiando> with SingleTickerProviderStateMixin {
  late final AnimationController _pulso = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat(reverse: true);
  bool _ativo = true;
  int _resta = 180;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _comecar();
  }

  @override
  void dispose() {
    _ativo = false;
    _pulso.dispose();
    super.dispose();
  }

  Future<void> _comecar() async {
    try {
      await widget.api.post('/social/desafiar', {'h': widget.amigo['h'], 'jogo': widget.jogo});
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
      return;
    }
    while (_ativo && mounted) {
      await Future<void>.delayed(const Duration(seconds: 2));
      if (!_ativo || !mounted) return;
      try {
        final r = await widget.api.get('/social/desafio?h=${widget.amigo['h']}');
        final e = '${r['estado']}';
        if (e == 'aceito') {
          _ativo = false;
          if (mounted) Navigator.of(context).pop(r);
          return;
        }
        if (e == 'recusado' || e == 'expirado') {
          _ativo = false;
          await _cancelar(msg: e == 'recusado' ? '${widget.amigo['nome']} recusou o desafio.' : 'O desafio expirou: ${widget.amigo['nome']} não respondeu a tempo.');
          return;
        }
        if (mounted && r['resta'] is num) setState(() => _resta = (r['resta'] as num).toInt());
      } catch (_) {}
    }
  }

  Future<void> _cancelar({String? msg}) async {
    _ativo = false;
    try {
      await widget.api.post('/social/desafio/cancelar', {'h': widget.amigo['h']});
    } catch (_) {}
    if (mounted) Navigator.of(context).pop({'estado': 'cancelado', 'msg': msg ?? 'Desafio cancelado.'});
  }

  @override
  Widget build(BuildContext context) {
    final nomeJogo = widget.jogo == 'trade' ? 'Trade Battle' : 'Ticker Battle';
    final cor = widget.jogo == 'trade' ? _verde : const Color(0xFF4B7DFF);
    Widget lado(Object? img, String nome) => Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 104,
            height: 104,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 3),
              boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.7), blurRadius: 22)],
              color: const Color(0xFF152845),
            ),
            child: ClipOval(child: imagemAvatar(img)),
          ),
          const SizedBox(height: 8),
          SizedBox(
              width: 120,
              child: Text(nome, textAlign: TextAlign.center, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white))),
        ]);
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (feito, _) {
        if (!feito) _cancelar();
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF0A2755),
        body: Stack(fit: StackFit.expand, children: [
          Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
          Container(color: const Color(0xAA0B0930)),
          SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: _erro != null
                    ? Column(mainAxisSize: MainAxisSize.min, children: [
                        Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, color: Colors.white)),
                        const SizedBox(height: 14),
                        FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Voltar')),
                      ])
                    : Column(mainAxisSize: MainAxisSize.min, children: [
                        Text('DESAFIO · ${nomeJogo.toUpperCase()}', style: TextStyle(fontSize: 15, letterSpacing: 2, fontWeight: FontWeight.w900, color: cor)),
                        const SizedBox(height: 26),
                        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                          lado(widget.euImg, 'Você'),
                          AnimatedBuilder(
                            animation: _pulso,
                            builder: (ctx, _) => Transform.scale(
                              scale: 1 + 0.15 * _pulso.value,
                              child: const Padding(
                                padding: EdgeInsets.symmetric(horizontal: 10),
                                child: Text('VS', style: TextStyle(fontSize: 38, fontWeight: FontWeight.w900, color: _ouro, shadows: [Shadow(color: Color(0xAAF2B84B), blurRadius: 16)])),
                              ),
                            ),
                          ),
                          lado(widget.amigo['avatar_img'], '${widget.amigo['nome']}'),
                        ]),
                        const SizedBox(height: 30),
                        Text('Aguardando ${widget.amigo['nome']} aceitar…', textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
                        const SizedBox(height: 6),
                        Text('A partida começa assim que o desafio for aceito · ${_resta ~/ 60}:${(_resta % 60).toString().padLeft(2, '0')}',
                            textAlign: TextAlign.center, style: const TextStyle(color: _lilas)),
                        const SizedBox(height: 18),
                        SizedBox(width: 220, child: LinearProgressIndicator(value: _resta / 180, minHeight: 6, color: cor, backgroundColor: const Color(0x55082450))),
                        const SizedBox(height: 26),
                        OutlinedButton.icon(
                          onPressed: () => _cancelar(),
                          style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Colors.white70), minimumSize: const Size(200, 48)),
                          icon: const Icon(Icons.close_rounded),
                          label: const Text('Cancelar desafio'),
                        ),
                      ]),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}
