import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'animacoes.dart';
import 'api.dart';
import 'escudo.dart';
import 'ticker.dart';

/// Ticker Battle ONLINE: encontrar um adversário na fila ou jogar com um amigo (sala com código).
/// As regras são as do app antigo (battle_online.py), aplicadas no servidor: cada um escolhe carta e indicador EM SEGREDO;
/// quando os dois confirmam, o servidor revela e compara. Duelos online contam para o ranking do Ticker Battle.
class OnlineTela extends StatefulWidget {
  const OnlineTela({super.key, required this.api, required this.baralhoValido});
  final Api api;
  final bool baralhoValido;

  @override
  State<OnlineTela> createState() => _OnlineTelaState();
}

class _OnlineTelaState extends State<OnlineTela> {
  bool _ocupado = false;

  Future<void> _abrirPartida(String id) => Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => PartidaOnlineTela(api: widget.api, pid: id)));

  Future<void> _acao(Future<void> Function() f) async {
    if (_ocupado) return;
    setState(() => _ocupado = true);
    try {
      await f();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  void _buscar() => _acao(() async {
        final r = await widget.api.post('/ticker/online/fila');
        if (!mounted) return;
        if (r['estado'] == 'partida') return _abrirPartida('${r['id']}');
        await Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => BuscaTela(api: widget.api)));
      });

  void _criarSala() => _acao(() async {
        final r = await widget.api.post('/ticker/online/sala');
        if (mounted) await _abrirPartida('${r['id']}');
      });

  void _entrarCodigo() async {
    final campo = TextEditingController();
    final cod = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF10274A),
        title: const Text('Entrar na sala do amigo', style: TextStyle(fontWeight: FontWeight.w900)),
        content: TextField(
          controller: campo,
          autofocus: true,
          maxLength: 6,
          textCapitalization: TextCapitalization.characters,
          decoration: const InputDecoration(labelText: 'Código da sala', hintText: '6 letras/números'),
          onSubmitted: (v) => Navigator.of(ctx).pop(v),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(campo.text), child: const Text('Entrar')),
        ],
      ),
    );
    campo.dispose();
    final c = (cod ?? '').trim();
    if (c.isEmpty) return;
    _acao(() async {
      final r = await widget.api.post('/ticker/online/sala/entrar', {'codigo': c});
      if (mounted) await _abrirPartida('${r['id']}');
    });
  }

  @override
  Widget build(BuildContext context) {
    return _Fundo(
      titulo: 'Duelo Online',
      child: ListView(padding: const EdgeInsets.fromLTRB(12, 0, 12, 24), children: [
        Entrada(ordem: 0, child: Image.asset('assets/ticker/modo_on.webp')),
        const SizedBox(height: 12),
        if (!widget.baralhoValido)
          _aviso('Monte um baralho válido (até 5 cartas) antes de jogar online.')
        else ...[
          Entrada(ordem: 1, child: _botao(Icons.travel_explore_rounded, 'Encontrar adversário', 'Entra na fila e joga com quem estiver procurando agora', const Color(0xFF26D07C), _buscar)),
          const SizedBox(height: 10),
          Entrada(ordem: 2, child: _botao(Icons.group_add_rounded, 'Criar sala para um amigo', 'Gera um código de 6 letras para passar ao amigo', const Color(0xFF6CA3FF), _criarSala)),
          const SizedBox(height: 10),
          Entrada(ordem: 3, child: _botao(Icons.login_rounded, 'Entrar com código', 'Digite o código que o amigo passou', const Color(0xFFF2B84B), _entrarCodigo)),
        ],
        const SizedBox(height: 14),
        _caixaTexto(
            'Como funciona online',
            'Os dois escolhem a carta e o indicador ao mesmo tempo, em segredo. Quando os dois confirmam, as cartas são reveladas. '
                'Se escolheram o mesmo indicador, vence o melhor valor. Se escolheram indicadores diferentes, cada um precisa vencer o '
                'indicador que escolheu: se só um vencer, ele leva a rodada; se os dois vencerem (ou os dois perderem), empata. '
                '3 rodadas, escolhendo entre as suas 5 cartas. Quem sai no meio perde por abandono. Duelos online contam para o ranking.'),
        if (_ocupado) const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
      ]),
    );
  }

  Widget _botao(IconData ic, String t, String s, Color cor, VoidCallback f) => Pressionavel(
        aoTocar: _ocupado ? null : f,
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: cor, width: 2),
            gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1C50A0), Color(0xFF0F3878)]),
            boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.45), blurRadius: 14)],
          ),
          child: Row(children: [
            Icon(ic, size: 32, color: cor),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t, style: const TextStyle(fontSize: 16.5, fontWeight: FontWeight.w900, color: Colors.white)),
                Text(s, style: const TextStyle(fontSize: 12.2, color: lilas)),
              ]),
            ),
            const Icon(Icons.chevron_right_rounded, size: 30, color: Colors.white),
          ]),
        ),
      );
}

/// Procurando adversário: radar girando enquanto o servidor tenta emparelhar (a cada 2 s). Cancelar tira da fila.
class BuscaTela extends StatefulWidget {
  const BuscaTela({super.key, required this.api});
  final Api api;

  @override
  State<BuscaTela> createState() => _BuscaTelaState();
}

class _BuscaTelaState extends State<BuscaTela> with SingleTickerProviderStateMixin {
  late final AnimationController _giro = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat();
  Timer? _t;
  int _seg = 0;
  bool _saiu = false;
  String _msg = 'Procurando um adversário…';

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 2), (_) => _consultar());
  }

  @override
  void dispose() {
    _t?.cancel();
    _giro.dispose();
    if (!_saiu) widget.api.post('/ticker/online/fila/sair').catchError((_) => <String, dynamic>{});
    super.dispose();
  }

  Future<void> _consultar() async {
    _seg += 2;
    try {
      final r = await widget.api.get('/ticker/online/fila');
      if (!mounted) return;
      switch (r['estado']) {
        case 'partida':
          _saiu = true;
          _t?.cancel();
          HapticFeedback.heavyImpact();
          Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => PartidaOnlineTela(api: widget.api, pid: '${r['id']}')));
        case 'expirou':
        case 'fora':
          _t?.cancel();
          setState(() => _msg = 'Ninguém apareceu agora. Tente de novo em instantes ou chame um amigo com o código da sala.');
        default:
          setState(() => _msg = r['reservado'] == true ? 'Adversário encontrado! Montando a partida…' : 'Procurando um adversário…');
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return _Fundo(
      titulo: 'Duelo Online',
      child: Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(
            width: 220,
            height: 220,
            child: AnimatedBuilder(animation: _giro, builder: (ctx, _) => CustomPaint(painter: _Radar(_giro.value))),
          ),
          const SizedBox(height: 18),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Text(_msg, textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: Colors.white)),
          ),
          const SizedBox(height: 6),
          Text('${_seg ~/ 60}:${(_seg % 60).toString().padLeft(2, '0')}', style: const TextStyle(fontSize: 14, color: lilas)),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Color(0xFF6CA3FF))),
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.close_rounded),
            label: const Text('Cancelar busca'),
          ),
        ]),
      ),
    );
  }
}

class _Radar extends CustomPainter {
  _Radar(this.v);
  final double v;

  @override
  void paint(Canvas c, Size s) {
    final o = s.center(Offset.zero), r = s.width / 2;
    for (var k = 1; k <= 3; k++) {
      c.drawCircle(
          o,
          r * k / 3,
          Paint()
            ..color = const Color(0x5526D07C)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.5);
    }
    final a = v * 2 * pi;
    c.drawArc(Rect.fromCircle(center: o, radius: r), a - 0.9, 0.9, true,
        Paint()..shader = SweepGradient(startAngle: a - 0.9, endAngle: a, colors: const [Color(0x0026D07C), Color(0x9926D07C)]).createShader(Rect.fromCircle(center: o, radius: r)));
    c.drawLine(
        o,
        o + Offset(cos(a), sin(a)) * r,
        Paint()
          ..color = const Color(0xFF5BF5A0)
          ..strokeWidth = 2.5);
    final pulso = (v * 2) % 1;
    c.drawCircle(o, 10 + 18 * pulso, Paint()..color = const Color(0xFF26D07C).withValues(alpha: 0.5 * (1 - pulso)));
    c.drawCircle(o, 9, Paint()..color = const Color(0xFF26D07C));
  }

  @override
  bool shouldRepaint(_Radar o) => o.v != v;
}

/// A partida online inteira: sala (código), espera ("Estou pronto"), rodadas (escolha secreta → espera → revelação) e resultado.
class PartidaOnlineTela extends StatefulWidget {
  const PartidaOnlineTela({super.key, required this.api, required this.pid});
  final Api api;
  final String pid;

  @override
  State<PartidaOnlineTela> createState() => _PartidaOnlineTelaState();
}

class _PartidaOnlineTelaState extends State<PartidaOnlineTela> with TickerProviderStateMixin {
  Map<String, dynamic>? _v;
  Timer? _t;
  bool _ocupado = false;
  String? _carta, _ind;
  int _vistas = 0; // quantas rodadas já foram reveladas na tela
  bool _trofMostrado = false; // a tela de troféus aparece uma vez, quando o resultado aparece
  Map<String, dynamic>? _revelando;
  late final AnimationController _rev = AnimationController(vsync: this, duration: const Duration(milliseconds: 2600));

  @override
  void initState() {
    super.initState();
    _ler();
    _t = Timer.periodic(const Duration(milliseconds: 1500), (_) => _ler());
  }

  @override
  void dispose() {
    _t?.cancel();
    _rev.dispose();
    super.dispose();
  }

  Future<void> _ler() async {
    if (_ocupado) return;
    try {
      _aplicar(await widget.api.get('/ticker/online/${widget.pid}'));
    } catch (_) {}
  }

  void _aplicar(Map<String, dynamic> v) {
    if (!mounted) return;
    final regs = ((v['reg'] as List?) ?? const []).cast<Map>();
    setState(() {
      _v = v;
      if (_v != null && _vistas == 0 && _revelando == null && regs.isNotEmpty && v['encerrada'] == true) _vistas = regs.length; // voltou numa partida já acabada
      if (regs.length > _vistas && _revelando == null) {
        _revelando = regs[_vistas].cast<String, dynamic>();
        _vistas++;
        _carta = null;
        _ind = null;
        HapticFeedback.mediumImpact();
        _rev.forward(from: 0);
      }
    });
    if (v['encerrada'] == true && _revelando == null) _t?.cancel();
  }

  Future<void> _post(String caminho, [Map<String, dynamic>? corpo]) async {
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post('/ticker/online/${widget.pid}/$caminho', corpo);
      _ocupado = false;
      _aplicar(r);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _sair() async {
    final v = _v;
    final emJogo = v != null && v['fase'] == 'em_jogo';
    if (emJogo) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF10274A),
          title: const Text('Desistir do duelo?'),
          content: const Text('Sair agora conta como derrota por abandono.'),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Continuar jogando')),
            FilledButton(style: FilledButton.styleFrom(backgroundColor: const Color(0xFFFF4D6D)), onPressed: () => Navigator.of(ctx).pop(true), child: const Text('Desistir')),
          ],
        ),
      );
      if (ok != true) return;
    }
    if (v != null && v['encerrada'] != true) {
      try {
        await widget.api.post('/ticker/online/${widget.pid}/sair');
      } catch (_) {}
    }
    if (mounted) Navigator.of(context).maybePop();
  }

  Map get _meta => (_v?['indicadores'] as Map?) ?? const {};

  @override
  Widget build(BuildContext context) {
    final v = _v;
    Widget corpo;
    if (v == null) {
      corpo = const Center(child: CircularProgressIndicator());
    } else if (_revelando != null) {
      corpo = _revelacao(_revelando!);
    } else if (v['encerrada'] == true) {
      corpo = _resultado(v);
    } else if (v['fase'] == 'aguardando') {
      corpo = _sala(v);
    } else if (v['fase'] == 'pronta') {
      corpo = _pronta(v);
    } else if ((v['eu'] as Map?)?['escolha'] != null) {
      corpo = _esperando(v);
    } else {
      corpo = _escolha(v);
    }
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _sair();
      },
      child: _Fundo(
        titulo: 'Duelo Online',
        aoVoltar: _sair,
        acima: v == null || v['fase'] == 'aguardando' ? null : _topo(v),
        child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 300), child: KeyedSubtree(key: ValueKey('${v?['fase']}${v?['rod']}$_revelando${(v?['eu'] as Map?)?['escolha'] != null}'), child: corpo)),
      ),
    );
  }

  Widget _topo(Map v) {
    final p = (v['placar'] as Map?) ?? const {};
    final op = (v['op'] as Map?) ?? const {};
    var eu = (p['eu'] as num?)?.toInt() ?? 0, ele = (p['op'] as num?)?.toInt() ?? 0;
    final r = _revelando;
    if (r != null && _rev.value < 0.7) {
      // durante a revelação o placar só muda quando a vencedora aparece
      if (r['venc'] == r['lado']) eu--;
      if (r['venc'] != 'empate' && r['venc'] != r['lado']) ele--;
    }
    final semSinal = ((op['sem_sinal'] as num?) ?? 0) > 12 && v['encerrada'] != true;
    final rod = r != null ? (r['n'] as num).toInt() : ((v['rod'] as num?)?.toInt() ?? 1);
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 6),
        child: Row(children: [
          Image.asset('assets/ticker/rodada_${rod.clamp(1, 3)}.webp', height: 30),
          const SizedBox(width: 6),
          Text('Rodada $rod de ${v['rodadas']}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xFF143362), border: Border.all(color: const Color(0xFF6CA3FF))),
            child: Text('Você $eu × $ele ${op['nick'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
          ),
        ]),
      ),
      if (semSinal)
        Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 6),
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: const Color(0x33F2B84B), border: Border.all(color: const Color(0xFFF2B84B))),
          child: Text('${op['nick']} está sem sinal. Se não voltar em instantes, você vence por abandono.', style: const TextStyle(fontSize: 12.5, color: Color(0xFFFFE3A3))),
        ),
    ]);
  }

  // ---------------------------------------------------------------- sala com código
  Widget _sala(Map v) {
    final cod = '${v['codigo'] ?? ''}';
    return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
      _cartao(
        borda: const Color(0xFFF2B84B),
        child: Column(children: [
          const Text('Código da sala', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFFFFE3A3))),
          const SizedBox(height: 4),
          Text(cod, style: const TextStyle(fontSize: 40, letterSpacing: 7, fontWeight: FontWeight.w900, color: Colors.white)),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: cod));
              if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Código copiado. Mande para o seu amigo!')));
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copiar código'),
          ),
        ]),
      ),
      const SizedBox(height: 16),
      const Center(child: SizedBox(width: 40, height: 40, child: CircularProgressIndicator())),
      const SizedBox(height: 10),
      const Text('Aguardando o amigo entrar…', textAlign: TextAlign.center, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
      const Text('A sala expira se ninguém entrar em 15 minutos.', textAlign: TextAlign.center, style: TextStyle(color: lilas)),
      const SizedBox(height: 16),
      OutlinedButton.icon(
        style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Color(0xFF6CA3FF))),
        onPressed: _sair,
        icon: const Icon(Icons.logout),
        label: const Text('Fechar sala'),
      ),
    ]);
  }

  // ---------------------------------------------------------------- sala de espera
  Widget _pronta(Map v) {
    final eu = (v['eu'] as Map?) ?? const {}, op = (v['op'] as Map?) ?? const {};
    Widget jogador(String nome, bool pronto, String sub) => Expanded(
          child: _cartao(
            borda: pronto ? const Color(0xFF26D07C) : const Color(0xFF4F88E6),
            child: Column(children: [
              Icon(Icons.person_rounded, size: 40, color: pronto ? const Color(0xFF26D07C) : const Color(0xFF9BBFFF)),
              Text(nome, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
              Text(pronto ? 'Pronto!' : sub, style: TextStyle(color: pronto ? const Color(0xFF8DF5C1) : lilas)),
            ]),
          ),
        );
    return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
      TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 800),
        curve: Curves.elasticOut,
        builder: (ctx, s, f) => Transform.scale(scale: s, child: f),
        child: Image.asset('assets/ticker/faixa_prepare.webp', height: 130),
      ),
      const SizedBox(height: 8),
      Row(children: [
        jogador('${eu['nick'] ?? 'Você'} (você)', eu['pronto'] == true, 'aguardando'),
        const SizedBox(width: 6),
        SizedBox(width: 50, child: Image.asset('assets/ticker/vs.webp')),
        const SizedBox(width: 6),
        jogador('${op['nick'] ?? 'Adversário'}', op['pronto'] == true, 'se preparando'),
      ]),
      const SizedBox(height: 16),
      SizedBox(
        height: 54,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          onPressed: eu['pronto'] == true || _ocupado ? null : () => _post('pronto'),
          icon: const Icon(Icons.check_rounded),
          label: Text(eu['pronto'] == true ? 'Aguardando o adversário…' : 'ESTOU PRONTO'),
        ),
      ),
      const SizedBox(height: 8),
      const Text('O duelo começa quando os dois estiverem prontos.', textAlign: TextAlign.center, style: TextStyle(color: lilas)),
    ]);
  }

  // ---------------------------------------------------------------- escolha secreta
  Widget _escolha(Map v) {
    final eu = (v['eu'] as Map?) ?? const {};
    final cartas = (v['cartas'] as Map?) ?? const {};
    final usadas = ((eu['usadas'] as List?) ?? const []).cast<String>();
    final mao = ((eu['deck'] as List?) ?? const []).cast<String>().where((t) => !usadas.contains(t)).toList();
    final minha = (cartas[_carta] as Map?) ?? const {};
    final inds = ((minha['ind'] as List?) ?? const []).cast<Map>();
    final op = (v['op'] as Map?) ?? const {};
    return ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 24), children: [
      Text(op['confirmou'] == true ? '${op['nick']} já confirmou a jogada!' : 'Escolha sua carta e o indicador, em segredo',
          textAlign: TextAlign.center, style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800, color: op['confirmou'] == true ? const Color(0xFFFFD66B) : Colors.white)),
      const SizedBox(height: 10),
      Wrap(alignment: WrapAlignment.center, spacing: 10, runSpacing: 10, children: [
        for (final (k, t) in mao.indexed)
          Entrada(
            ordem: k,
            child: Pressionavel(
              aoTocar: () => setState(() {
                _carta = t;
                _ind = null;
              }),
              child: AnimatedScale(
                scale: _carta == t ? 1.06 : 1,
                duration: const Duration(milliseconds: 200),
                child: CartaTk(tk: t, largura: 96, marcada: _carta == t, apagada: _carta != null && _carta != t, dados: dadosDoDuelo(cartas[t]), valores: valoresDoDuelo((cartas[t] as Map?)?['ind'])),
              ),
            ),
          ),
      ]),
      const SizedBox(height: 12),
      if (_carta != null) ...[
        const Text('Indicador desta rodada', textAlign: TextAlign.center, style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800, color: Colors.white)),
        const SizedBox(height: 8),
        LayoutBuilder(builder: (ctx, c) {
          final w = (c.maxWidth - 8) / 2;
          return Wrap(spacing: 8, runSpacing: 8, children: [
            for (final i in inds)
              SizedBox(
                width: w,
                child: Pressionavel(
                  aoTocar: () => setState(() => _ind = '${i['id']}'),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      gradient: _ind == i['id'] ? const LinearGradient(colors: [Color(0xFFF2B84B), Color(0xFFD98E1F)]) : null,
                      color: _ind == i['id'] ? null : const Color(0xFF143362),
                      border: Border.all(color: _ind == i['id'] ? const Color(0xFFFFE08A) : const Color(0xFF4F88E6), width: 1.5),
                    ),
                    child: Row(children: [
                      Icon(iconesInd[(_meta[i['id']] as Map?)?['icone']] ?? Icons.analytics_rounded, size: 20, color: _ind == i['id'] ? const Color(0xFF2A1A00) : const Color(0xFF9BBFFF)),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${(_meta[i['id']] as Map?)?['nome'] ?? i['id']}',
                              maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: FontWeight.w900, color: _ind == i['id'] ? const Color(0xFF2A1A00) : Colors.white)),
                          Text('Você: ${i['txt']}', style: TextStyle(fontSize: 11, color: _ind == i['id'] ? const Color(0xFF3B2600) : lilas)),
                        ]),
                      ),
                    ]),
                  ),
                ),
              ),
          ]);
        }),
        if (_ind != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('Regra: ${(_meta[_ind] as Map?)?['regra'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 12.5, color: lilas)),
          ),
      ],
      const SizedBox(height: 14),
      SizedBox(
        height: 54,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          onPressed: _carta == null || _ind == null || _ocupado ? null : () => _post('jogar', {'carta': _carta, 'ind': _ind}),
          icon: const Icon(Icons.lock_rounded),
          label: Text(_carta == null ? 'Escolha uma carta' : (_ind == null ? 'Escolha o indicador' : 'CONFIRMAR JOGADA')),
        ),
      ),
      const SizedBox(height: 6),
      const Text('Depois de confirmar, não dá para mudar.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: lilas)),
    ]);
  }

  // ---------------------------------------------------------------- esperando o adversário
  Widget _esperando(Map v) {
    final e = (v['eu'] as Map)['escolha'] as Map;
    final op = (v['op'] as Map?) ?? const {};
    return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
      Row(children: [
        Expanded(
            child: Column(children: [
          CartaTk(tk: '${e['tk']}', largura: 128, dados: dadosDoDuelo((v['cartas'] as Map?)?[e['tk']])),
          const SizedBox(height: 4),
          Text('${(_meta[e['ind']] as Map?)?['nome'] ?? e['ind']}', style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFFFFD66B)))
        ])),
        SizedBox(width: 62, child: Flutua(altura: 4, child: Image.asset('assets/ticker/vs.webp'))),
        Expanded(
          child: Column(children: [
            Flutua(altura: 6, periodo: const Duration(milliseconds: 1400), child: Image.asset('assets/ticker/pilha.webp', width: 128, height: CartaTk.alturaPara(128), fit: BoxFit.cover)),
            const SizedBox(height: 4),
            Text(op['confirmou'] == true ? 'Confirmou!' : 'Escolhendo…', style: TextStyle(fontWeight: FontWeight.w800, color: op['confirmou'] == true ? const Color(0xFF8DF5C1) : lilas)),
          ]),
        ),
      ]),
      const SizedBox(height: 16),
      const Center(child: SizedBox(width: 36, height: 36, child: CircularProgressIndicator())),
      const SizedBox(height: 8),
      Text('Jogada confirmada! Aguardando ${op['nick'] ?? 'o adversário'}…', textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
      const Text('Se o adversário não confirmar em 3 minutos, você vence por tempo.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, color: lilas)),
    ]);
  }

  // ---------------------------------------------------------------- revelação
  Widget _revelacao(Map r) {
    final lado = '${r['lado']}';
    final venc = '${r['venc']}';
    final ganhei = venc == lado, perdi = venc != 'empate' && venc != lado;
    final cor = ganhei ? const Color(0xFF26D07C) : (perdi ? const Color(0xFFFF4D6D) : const Color(0xFFF2B84B));
    final titulo = ganhei ? 'Você venceu a rodada!' : (perdi ? '${(_v?['op'] as Map?)?['nick'] ?? 'O adversário'} venceu a rodada.' : 'Rodada empatada.');
    final eu = (r['eu'] as Map?) ?? const {}, op = (r['op'] as Map?) ?? const {};
    final cmp = ((r['cmp'] as List?) ?? const []).cast<Map>();
    return AnimatedBuilder(
      animation: _rev,
      builder: (ctx, _) {
        final t = _rev.value;
        final vira = Curves.easeInOut.transform((t / 0.35).clamp(0.0, 1.0));
        final mostra = ((t - 0.35) / 0.3).clamp(0.0, 1.0);
        final fim = Curves.elasticOut.transform(((t - 0.7) / 0.3).clamp(0.0, 1.0));
        final ang = (1 - vira) * pi;
        return ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 24), children: [
          Row(children: [
            Expanded(
              child: Column(children: [
                Transform.scale(scale: 1 + (ganhei ? 0.06 * fim : 0), child: CartaTk(tk: '${eu['tk']}', largura: 128, brilho: fim > 0.2 && ganhei ? cor : null, apagada: fim > 0.2 && perdi)),
                const Text('Você', style: TextStyle(color: lilas)),
              ]),
            ),
            SizedBox(width: 62, child: Image.asset('assets/ticker/vs.webp')),
            Expanded(
              child: Column(children: [
                Transform(
                  alignment: Alignment.center,
                  transform: Matrix4.identity()
                    ..setEntry(3, 2, 0.0015)
                    ..rotateY(ang),
                  child: ang > pi / 2
                      ? Image.asset('assets/ticker/pilha.webp', width: 128, height: CartaTk.alturaPara(128), fit: BoxFit.cover)
                      : Transform.scale(scale: 1 + (perdi ? 0.06 * fim : 0), child: CartaTk(tk: '${op['tk']}', largura: 128, brilho: fim > 0.2 && perdi ? cor : null, apagada: fim > 0.2 && ganhei)),
                ),
                Text('${(_v?['op'] as Map?)?['nick'] ?? 'Adversário'}', style: const TextStyle(color: lilas)),
              ]),
            ),
          ]),
          const SizedBox(height: 10),
          Opacity(
            opacity: mostra,
            child: Column(children: [
              for (final x in cmp) _linhaCmp(x, lado),
              if ('${r['motivo']}'.isNotEmpty) Text('Empate: ${r['motivo']}.', textAlign: TextAlign.center, style: const TextStyle(color: lilas)),
            ]),
          ),
          const SizedBox(height: 10),
          Opacity(
            opacity: fim.clamp(0.0, 1.0),
            child: Transform.scale(
              scale: 0.6 + 0.4 * fim,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: cor.withValues(alpha: 0.18), border: Border.all(color: cor, width: 2)),
                child: Text(titulo, textAlign: TextAlign.center, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: cor)),
              ),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF4B82D6), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
              onPressed: t < 0.7
                  ? null
                  : () => setState(() {
                        _revelando = null;
                        _aplicar(_v!);
                      }),
              icon: const Icon(Icons.arrow_forward_rounded),
              label: Text(_v?['encerrada'] == true && _vistas >= ((_v?['reg'] as List?)?.length ?? 0) ? 'VER RESULTADO' : 'CONTINUAR'),
            ),
          ),
        ]);
      },
    );
  }

  /// Uma comparação: o indicador, os dois valores (o seu à esquerda) e quem venceu esse indicador.
  Widget _linhaCmp(Map x, String lado) {
    final souA = lado == 'a';
    final meu = souA ? x['txt_a'] : x['txt_b'], dele = souA ? x['txt_b'] : x['txt_a'];
    final vx = '${x['venc']}';
    final ganhei = vx == lado, perdi = vx != 'empate' && vx != lado;
    final de = '${x['de']}';
    final quem = de == 'ambos' ? 'os dois escolheram' : (de == lado ? 'você escolheu' : 'o adversário escolheu');
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0xCC143362), border: Border.all(color: const Color(0x666CA3FF))),
      child: Column(children: [
        Text('${x['nome']} · $quem', style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFFFFD66B))),
        const SizedBox(height: 4),
        Row(children: [
          Expanded(child: Text('$meu', textAlign: TextAlign.center, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: ganhei ? const Color(0xFF26D07C) : Colors.white))),
          const Text('×', style: TextStyle(color: lilas)),
          Expanded(child: Text('$dele', textAlign: TextAlign.center, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: perdi ? const Color(0xFFFF6B87) : Colors.white))),
        ]),
      ]),
    );
  }

  // ---------------------------------------------------------------- resultado
  Widget _resultado(Map v) {
    if (!_trofMostrado && v['trofeus'] is Map) {
      _trofMostrado = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) ResultadoTrofeusTela.abrir(context, v['trofeus'] as Map, api: widget.api);
      });
    }
    final f = (v['final'] as Map?) ?? const {};
    final res = '${f['resultado']}';
    final motivo = '${f['motivo']}';
    final cancelada = v['fase'] == 'cancelada' || motivo == 'cancelada';
    final faixa = cancelada ? 'faixa_empate' : ({'vitoria': 'faixa_vitoria', 'derrota': 'faixa_derrota'}[res] ?? 'faixa_empate');
    final p = (v['placar'] as Map?) ?? const {};
    final op = (v['op'] as Map?) ?? const {};
    final explica = cancelada
        ? 'A partida foi cancelada antes de começar. Ninguém ganhou nem perdeu.'
        : motivo == 'abandono'
            ? (res == 'vitoria' ? '${op['nick']} saiu do duelo: vitória por abandono.' : 'Você saiu do duelo: derrota por abandono.')
            : motivo == 'tempo'
                ? (res == 'vitoria' ? '${op['nick']} não confirmou a tempo: vitória por tempo.' : 'Você não confirmou a tempo: derrota por tempo.')
                : 'Duelo online: o resultado conta para o ranking do Ticker Battle.';
    return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
      Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 900),
          curve: Curves.elasticOut,
          builder: (ctx, s, c) => Transform.scale(scale: s, child: c),
          child: Image.asset('assets/ticker/$faixa.webp', height: 170),
        ),
        if (res == 'vitoria' && !cancelada) Positioned(right: 0, bottom: -10, child: Flutua(child: Image.asset('assets/home/mascote_principal.webp', height: 90))),
      ]),
      const SizedBox(height: 8),
      Text('Você ${p['eu'] ?? 0} × ${p['op'] ?? 0} ${op['nick'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white)),
      const SizedBox(height: 6),
      Text(explica, textAlign: TextAlign.center, style: const TextStyle(color: lilas)),
      const SizedBox(height: 14),
      for (final (k, r) in ((v['reg'] as List?) ?? const []).cast<Map>().indexed)
        Entrada(
          ordem: k,
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0xCC143362), border: Border.all(color: const Color(0x666CA3FF))),
            child: Row(children: [
              CartaTk(tk: '${(r['eu'] as Map)['tk']}', largura: 40),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                    'Rodada ${r['n']}: ${(r['cmp'] as List).map((x) => '${(x as Map)['nome']} ${r['lado'] == 'a' ? x['txt_a'] : x['txt_b']} × ${r['lado'] == 'a' ? x['txt_b'] : x['txt_a']}').join(' · ')}',
                    style: const TextStyle(fontSize: 12.5, color: Colors.white)),
              ),
              CartaTk(tk: '${(r['op'] as Map)['tk']}', largura: 40),
              const SizedBox(width: 6),
              Text(r['venc'] == r['lado'] ? 'Venceu' : (r['venc'] == 'empate' ? 'Empate' : 'Perdeu'),
                  style: TextStyle(fontWeight: FontWeight.w900, color: r['venc'] == r['lado'] ? const Color(0xFF26D07C) : (r['venc'] == 'empate' ? const Color(0xFFF2B84B) : const Color(0xFFFF6B87)))),
            ]),
          ),
        ),
      const SizedBox(height: 10),
      SizedBox(
        height: 52,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.home_rounded),
          label: const Text('Voltar ao Ticker Battle'),
        ),
      ),
    ]);
  }

  Widget _cartao({required Widget child, Color borda = const Color(0xFF4F88E6)}) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: borda, width: 2),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF134188), Color(0xFF0B2C5E)]),
          boxShadow: [BoxShadow(color: borda.withValues(alpha: 0.4), blurRadius: 12)],
        ),
        child: child,
      );
}

/// Fundo e topo das telas online (mesmo gradiente da tela do Trade Battle).
class _Fundo extends StatelessWidget {
  const _Fundo({required this.titulo, required this.child, this.aoVoltar, this.acima});
  final String titulo;
  final Widget child;
  final VoidCallback? aoVoltar;
  final Widget? acima;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(fit: StackFit.expand, children: [
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFF0A0A5A), Color(0xFF082F70), Color(0xFF05204E), Color(0xFF001738)],
              stops: [0, 0.35, 0.7, 1],
            ),
          ),
        ),
        SafeArea(
          child: Column(children: [
            Row(children: [
              IconButton(onPressed: aoVoltar ?? () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
              Text(titulo, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
            ]),
            if (acima != null) acima!,
            Expanded(child: child),
          ]),
        ),
      ]),
    );
  }
}

Widget _aviso(String t) => Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0x22F2B84B), border: Border.all(color: const Color(0xFFF2B84B))),
      child: Text(t, style: const TextStyle(color: Color(0xFFFFE3A3), fontWeight: FontWeight.w700)),
    );

Widget _caixaTexto(String t, String s) => Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x556CA3FF)), color: const Color(0xCC0E1F3A)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(t, style: const TextStyle(fontWeight: FontWeight.w800, color: Colors.white)),
        const SizedBox(height: 6),
        Text(s, style: const TextStyle(fontSize: 13, height: 1.45, color: Color(0xFFE9F1FF))),
      ]),
    );
