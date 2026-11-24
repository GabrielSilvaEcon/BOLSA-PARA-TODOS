import 'dart:async';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'grafico/grafico.dart';
import 'grafico/modelo.dart';

/// Fase da estratégia do Trade Battle, feita no próprio app: o gráfico real (sem nome nem data), as ferramentas de desenho
/// e a leitura Subir · Aguardar · Cair. Os desenhos vão junto com a estratégia e, no fim, o servidor confere cada um
/// contra o que o preço fez (30% da nota; a operação vale 70%). Desenhar é opcional.
class EstrategiaView extends StatefulWidget {
  const EstrategiaView({super.key, required this.api, required this.base, required this.args, required this.aoResponder, required this.aoVoltar});
  final Api api;

  /// Endereço da partida no servidor (solo ou sala).
  final String base;

  /// Estado da partida que o servidor mandou (o mesmo da mesa).
  final Map<String, dynamic> args;
  final void Function(Map<String, dynamic>) aoResponder;
  final VoidCallback aoVoltar;

  @override
  State<EstrategiaView> createState() => _EstrategiaViewState();
}

class _EstrategiaViewState extends State<EstrategiaView> {
  List<Vela> _velas = const [];
  final List<Desenho> _desenhos = [];
  Ferramenta? _ferramenta;
  final Set<String> _ind = {'vol', 'mm20'};
  String? _leitura; // alta · aguardar · baixa
  bool _enviando = false, _enviada = false;
  String _erro = '';
  String _aviso = '';
  Timer? _avisoT, _relogio;
  DateTime _fim = DateTime.now();

  @override
  void initState() {
    super.initState();
    _ler(primeira: true);
    _relogio = Timer.periodic(const Duration(milliseconds: 250), (_) => _tique());
  }

  @override
  void didUpdateWidget(EstrategiaView old) {
    super.didUpdateWidget(old);
    _ler();
  }

  @override
  void dispose() {
    _relogio?.cancel();
    _avisoT?.cancel();
    super.dispose();
  }

  void _ler({bool primeira = false}) {
    final cs = (widget.args['candles'] as List?) ?? const [];
    if (primeira || cs.length != _velas.length) _velas = [for (final c in cs) if (c is Map) Vela.de(c)];
    final seg = (widget.args['seg'] as num?)?.toDouble() ?? 0;
    final novo = DateTime.now().add(Duration(milliseconds: (seg * 1000).round()));
    if (primeira || (novo.difference(_fim).inMilliseconds).abs() > 1500) _fim = novo;
    if ((widget.args['confirmados'] as Map?)?['eu'] == true) _enviada = true;
  }

  int get _restante => _fim.difference(DateTime.now()).inSeconds.clamp(0, 9999);

  void _tique() {
    if (!mounted) return;
    // tempo acabando sem confirmar: manda o que já tem (a leitura escolhida ou Aguardar, com os desenhos), para não perder a estratégia
    if (!_enviada && !_enviando && _restante <= 2 && (_leitura != null || _desenhos.isNotEmpty)) _confirmar(auto: true);
    setState(() {});
  }

  void _avisar(String t) {
    _avisoT?.cancel();
    setState(() => _aviso = t);
    _avisoT = Timer(const Duration(milliseconds: 2200), () {
      if (mounted) setState(() => _aviso = '');
    });
  }

  Future<String?> _pedirTexto() async {
    final campo = TextEditingController();
    final t = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF10274A),
        title: const Text('Anotação', style: TextStyle(fontWeight: FontWeight.w900)),
        content: TextField(
          controller: campo,
          autofocus: true,
          maxLength: 40,
          decoration: const InputDecoration(hintText: 'Ex.: fundo duplo, pivô de alta…'),
          onSubmitted: (v) => Navigator.of(ctx).pop(v),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(campo.text), child: const Text('Anotar')),
        ],
      ),
    );
    campo.dispose();
    return t;
  }

  Future<void> _confirmar({bool auto = false}) async {
    if (_enviando || _enviada) return;
    final l = _leitura ?? 'aguardar';
    setState(() {
      _enviando = true;
      _erro = '';
    });
    try {
      final r = await widget.api.post('${widget.base}/estrategia', {
        'direcao': l == 'aguardar' ? null : l,
        'tipo': l == 'aguardar' ? 'aguardar' : 'continuacao',
        'marcas': marcasDe(_desenhos),
      });
      _enviada = true;
      widget.aoResponder(r);
    } catch (e) {
      if (mounted && !auto) setState(() => _erro = e.toString());
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.args;
    final cf = (a['confirmados'] as Map?) ?? const {};
    return ColoredBox(
      color: const Color(0xFF081528),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
          child: Column(
            children: [
              _topo(a),
              const SizedBox(height: 6),
              Expanded(child: _grafico(a)),
              const SizedBox(height: 6),
              _dica(),
              const SizedBox(height: 6),
              _ferramentas(),
              const SizedBox(height: 8),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 350),
                child: _enviada ? _esperando(cf) : _painel(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _topo(Map a) {
    final r = _restante;
    final urgente = r <= 20;
    return Row(
      children: [
        Material(
          color: const Color(0xFF143362),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: const BorderSide(color: Color(0xFF4B82D6))),
          child: IconButton(onPressed: widget.aoVoltar, icon: const Icon(Icons.arrow_back_rounded, color: Colors.white), tooltip: 'Voltar'),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${a['ticker'] ?? 'Ativo oculto'}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
              Text('${a['tf_nome'] ?? ''} · sua estratégia', style: const TextStyle(fontSize: 12, color: Color(0xFFB5C8E6))),
            ],
          ),
        ),
        Pulso2(
          ativo: urgente,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              color: urgente ? const Color(0x33FF4D6D) : const Color(0x2226D07C),
              border: Border.all(color: urgente ? const Color(0xFFFF4D6D) : const Color(0xFF26D07C), width: 1.5),
            ),
            child: Text('⏱ ${(r ~/ 60).toString().padLeft(2, '0')}:${(r % 60).toString().padLeft(2, '0')}',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: urgente ? const Color(0xFFFF8FA3) : const Color(0xFF7CF0C0))),
          ),
        ),
      ],
    );
  }

  Widget _grafico(Map a) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFF4B82D6), width: 2),
        boxShadow: const [BoxShadow(color: Color(0x804B82D6), blurRadius: 14)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          fit: StackFit.expand,
          children: [
            Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
            const ColoredBox(color: Color(0x99021026)),
            if (_velas.isEmpty)
              const Center(child: CircularProgressIndicator())
            else
              GraficoNativo(
                velas: _velas,
                desenhos: _desenhos,
                ferramenta: _enviada ? null : _ferramenta,
                indicadores: _ind,
                tfNome: '${a['tf_nome'] ?? ''}',
                pedirTexto: _pedirTexto,
                aoAviso: _avisar,
                aoMudar: ({bool usouFerramenta = false}) => setState(() {
                  if (usouFerramenta && _ferramenta != Ferramenta.apagar) _ferramenta = null; // desenhou: volta a poder arrastar o gráfico
                }),
              ),
          ],
        ),
      ),
    );
  }

  Widget _dica() {
    final t = _aviso.isNotEmpty
        ? _aviso
        : _ferramenta?.dica ??
            (_desenhos.isEmpty
                ? 'Desenhe sua leitura (vale 30% da nota) ou só escolha Subir, Aguardar ou Cair.'
                : '${_desenhos.length} desenho${_desenhos.length > 1 ? 's' : ''} · arraste para ajustar, segure para apagar.');
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: Text(t,
          key: ValueKey(t),
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: _aviso.isNotEmpty ? const Color(0xFFFFD66B) : const Color(0xFFC8D6EE))),
    );
  }

  Widget _ferramentas() {
    return SizedBox(
      height: 42,
      child: ListView(
        scrollDirection: Axis.horizontal,
        children: [
          for (final f in Ferramenta.values) ...[
            _chip(f),
            const SizedBox(width: 6),
          ],
          PopupMenuButton<String>(
            tooltip: 'Indicadores',
            color: const Color(0xFF143362),
            onSelected: (k) => setState(() => _ind.contains(k) ? _ind.remove(k) : _ind.add(k)),
            itemBuilder: (ctx) => [
              for (final (k, t) in const [('vol', 'Volume'), ('mm20', 'Média 20'), ('mm50', 'Média 50'), ('mm200', 'Média 200')])
                CheckedPopupMenuItem(value: k, checked: _ind.contains(k), child: Text(t)),
            ],
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: const Color(0xFF68A4FF), width: 1.5),
                color: const Color(0xFF143362),
              ),
              child: const Row(children: [
                Icon(Icons.insights_rounded, size: 18, color: Color(0xFF9BBFFF)),
                SizedBox(width: 5),
                Text('Indicadores', style: TextStyle(fontWeight: FontWeight.w800, color: Colors.white)),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(Ferramenta f) {
    final on = _ferramenta == f;
    return Pressionavel(
      aoTocar: _enviada ? null : () => setState(() => _ferramenta = on ? null : f),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 11),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          color: on ? f.cor : const Color(0xFF143362),
          border: Border.all(color: f.cor.withValues(alpha: on ? 1 : 0.6), width: 1.5),
          boxShadow: on ? [BoxShadow(color: f.cor.withValues(alpha: 0.55), blurRadius: 12)] : null,
        ),
        child: Row(
          children: [
            Icon(f.icone, size: 18, color: on ? const Color(0xFF06101F) : f.cor),
            const SizedBox(width: 5),
            Text(f.rotulo, style: TextStyle(fontWeight: FontWeight.w800, color: on ? const Color(0xFF06101F) : Colors.white)),
          ],
        ),
      ),
    );
  }

  Widget _painel() {
    Widget botao(String id, String t, IconData ic, Color cor) {
      final on = _leitura == id;
      return Expanded(
        child: Pressionavel(
          aoTocar: () => setState(() => _leitura = id),
          child: AnimatedScale(
            scale: on ? 1.04 : 1,
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutBack,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              height: 54,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                gradient: on ? LinearGradient(colors: [cor, Color.lerp(cor, Colors.black, 0.25)!]) : null,
                color: on ? null : const Color(0xFF143362),
                border: Border.all(color: cor.withValues(alpha: on ? 1 : 0.55), width: 2),
                boxShadow: on ? [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 14)] : null,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(ic, color: on ? Colors.white : cor),
                  const SizedBox(width: 4),
                  Text(t, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
                ],
              ),
            ),
          ),
        ),
      );
    }

    return Container(
      key: const ValueKey('painel'),
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF4F88E6), width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF134188), Color(0xFF0B2C5E)]),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(children: [
            botao('alta', 'Subir', Icons.trending_up_rounded, const Color(0xFF26D07C)),
            const SizedBox(width: 7),
            botao('aguardar', 'Aguardar', Icons.pause_rounded, const Color(0xFF8CB9FF)),
            const SizedBox(width: 7),
            botao('baixa', 'Cair', Icons.trending_down_rounded, const Color(0xFFFF4D6D)),
          ]),
          if (_erro.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(_erro, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFFF8FA3), fontWeight: FontWeight.w700)),
            ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            height: 50,
            child: FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFFF2B84B),
                foregroundColor: const Color(0xFF2A1A00),
                disabledBackgroundColor: const Color(0x55F2B84B),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
              ),
              onPressed: _leitura == null || _enviando ? null : () => _confirmar(),
              child: _enviando
                  ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Color(0xFF2A1A00)))
                  : Text(_leitura == null
                      ? 'Escolha Subir, Aguardar ou Cair'
                      : 'Confirmar estratégia${_desenhos.isEmpty ? '' : ' · ${_desenhos.length} desenho${_desenhos.length > 1 ? 's' : ''}'}'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _esperando(Map cf) {
    final n = (cf['n'] as num?)?.toInt(), total = (cf['total'] as num?)?.toInt();
    final t = total != null && total > 1 && (n ?? 0) < total ? 'Aguardando os outros jogadores (${n ?? 0}/$total)…' : 'A partida vai começar!';
    return Container(
      key: const ValueKey('esperando'),
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF26D07C), width: 2),
        color: const Color(0xFF0E3A2A),
      ),
      child: Column(children: [
        const Icon(Icons.check_circle_rounded, color: Color(0xFF26D07C), size: 32),
        const SizedBox(height: 4),
        const Text('Estratégia enviada!', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        Text(t, style: const TextStyle(color: Color(0xFFCFF5E0))),
      ]),
    );
  }
}

/// Pulsa (cresce e diminui) enquanto [ativo]; usado no relógio quando o tempo está acabando.
class Pulso2 extends StatefulWidget {
  const Pulso2({super.key, required this.ativo, required this.child});
  final bool ativo;
  final Widget child;

  @override
  State<Pulso2> createState() => _Pulso2State();
}

class _Pulso2State extends State<Pulso2> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 600));

  @override
  void didUpdateWidget(Pulso2 old) {
    super.didUpdateWidget(old);
    if (widget.ativo && !_c.isAnimating) _c.repeat(reverse: true);
    if (!widget.ativo && _c.isAnimating) _c.stop();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (ctx, f) => Transform.scale(scale: widget.ativo ? 1 + 0.07 * _c.value : 1, child: f),
        child: widget.child,
      );
}
