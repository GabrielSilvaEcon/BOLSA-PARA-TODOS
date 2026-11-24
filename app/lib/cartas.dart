import 'dart:math';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';

/// Cartas colecionáveis do TickerHunters: a carta desenhada em código (modelo aprovado: selo de raridade com estrela, ticker, ilustração,
/// nome, setor, atividade principal, P/L · DY · ROE e uma curiosidade), o catálogo (textos vindos do servidor) e a revelação animada.
/// A cor da moldura segue a raridade: Comum prata · Rara azul · Épica roxa · Lendária dourada.

/// Cores de cada raridade: (principal, clara, escura).
const coresRaridade = {
  'comum': (Color(0xFFB9C4D4), Color(0xFFF1F5FB), Color(0xFF5E6B80)),
  'rara': (Color(0xFF3FA2FF), Color(0xFFA9DBFF), Color(0xFF1546A8)),
  'epica': (Color(0xFFB062FF), Color(0xFFE3C2FF), Color(0xFF5A1FA8)),
  'lendaria': (Color(0xFFFFC93C), Color(0xFFFFF0B0), Color(0xFFB5720A)),
};
const rotulosRaridade = {'comum': 'COMUM', 'rara': 'RARA', 'epica': 'ÉPICA', 'lendaria': 'LENDÁRIA'};
const nomesRaridade = {'comum': 'Comum', 'rara': 'Rara', 'epica': 'Épica', 'lendaria': 'Lendária'};
const ordemRaridade = ['comum', 'rara', 'epica', 'lendaria'];

/// Ilustração provisória por setor (ícones do app) enquanto a empresa não tem arte própria.
const _artesSetor = {
  'Petróleo e gás': 'petroleo',
  'Mineração': 'mineracao',
  'Bancos': 'bancos',
  'Bebidas': 'alimentos',
  'Bens industriais': 'industria',
  'Serviços financeiros': 'bancos',
  'Papel e celulose': 'agro',
  'Aeronáutica': 'aereo',
  'Telecomunicações': 'telecom',
  'Combustíveis': 'combustiveis',
  'Varejo': 'varejo',
  'Energia elétrica': 'energia',
  'Petroquímica': 'industria',
  'Turismo': 'aereo',
  'Transporte': 'logistica',
  'Tecnologia': 'tecnologia',
  'Locação de veículos': 'automotivo',
};

/// Ticker da empresa a partir do id da carta no duelo ("PETR4-ab12cd" → "PETR4").
String tkBase(Object? id) => '${id ?? ''}'.split('-').first;

/// Catálogo de textos das cartas (nome, setor, atividade, fato, arte, raridade), carregado uma vez do servidor.
class CatalogoCartas {
  static final Map<String, Map<String, dynamic>> empresas = {};
  static final ValueNotifier<int> versao = ValueNotifier(0);
  static Future<void>? _carregando;

  static Future<void> carregar(Api api, {bool forcar = false}) {
    if (!forcar && empresas.isNotEmpty) return Future.value();
    return _carregando ??= api
        .get('/cartas/catalogo')
        .then((r) {
          final e = (r['empresas'] as Map?) ?? const {};
          empresas
            ..clear()
            ..addAll({for (final k in e.keys) '$k': (e[k] as Map).cast<String, dynamic>()});
          versao.value++;
        })
        .catchError((_) {})
        .whenComplete(() => _carregando = null);
  }

  /// Junta os textos do catálogo com o que veio junto (da coleção ou do duelo).
  static Map<String, dynamic> info(String tk, [Map? extra]) => {...?empresas[tk], ...?extra?.cast<String, dynamic>()};
}

/// A carta. [tk] pode ser o ticker ou o id da carta no duelo. [valores]: {pl, dy_12m, roe} → texto (sem valores mostra "?").
/// [dados] (opcional) sobrepõe o catálogo: nome, setor, raridade, nível, atividade, fato, arte…
class CartaTk extends StatelessWidget {
  const CartaTk({
    super.key,
    required this.tk,
    this.largura = 110,
    this.marcada = false,
    this.travada = false,
    this.brilho,
    this.apagada = false,
    this.valores,
    this.dados,
    this.silhueta = false,
  });
  final String tk;
  final double largura;
  final bool marcada, travada, apagada, silhueta;
  final Color? brilho;
  final Map<String, String>? valores;
  final Map? dados;

  static const double lw = 300, lh = 492; // tamanho de desenho (a carta escala para [largura])
  static double alturaPara(double largura) => largura * lh / lw;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int>(
      valueListenable: CatalogoCartas.versao,
      builder: (ctx, _, __) {
        final t = tkBase(tk);
        final info = CatalogoCartas.info(t, dados);
        final rar = coresRaridade.containsKey(info['raridade']) ? '${info['raridade']}' : 'comum';
        final raio = largura * 0.07;
        return AnimatedOpacity(
          duration: const Duration(milliseconds: 300),
          opacity: apagada ? 0.45 : 1,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: largura,
            height: alturaPara(largura),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(raio),
              boxShadow: [
                if (brilho != null) BoxShadow(color: brilho!.withValues(alpha: 0.8), blurRadius: 18, spreadRadius: 2),
                if (marcada) const BoxShadow(color: Color(0xCC26D07C), blurRadius: 12, spreadRadius: 1),
              ],
            ),
            child: Stack(children: [
              Positioned.fill(
                child: _brilhoLendaria(
                  !silhueta && rar == 'lendaria',
                  raio,
                  FittedBox(
                    fit: BoxFit.fill,
                    child: SizedBox(width: lw, height: lh, child: silhueta ? _Silhueta(rar: rar, setor: '${info['setor'] ?? ''}') : _Face(tk: t, info: info, rar: rar, valores: valores)),
                  ),
                ),
              ),
              if (travada)
                Positioned.fill(
                  child: Container(
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(raio), color: const Color(0xAA081528)),
                    child: Icon(Icons.lock_rounded, color: Colors.white70, size: largura * 0.25),
                  ),
                ),
              if (marcada)
                Positioned(
                  right: 4,
                  top: largura * 0.2,
                  child: Container(
                    width: 22,
                    height: 22,
                    decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFF26D07C), border: Border.all(color: Colors.white, width: 2)),
                    child: const Icon(Icons.check, size: 13, color: Colors.white),
                  ),
                ),
            ]),
          ),
        );
      },
    );
  }
}

/// Lendária: um reflexo dourado atravessa a carta de tempos em tempos (mais impacto visual).
Widget _brilhoLendaria(bool sim, double raio, Widget child) => sim ? Reflexo(raio: raio, intervalo: const Duration(milliseconds: 3200), child: child) : child;

/// Moldura neon na cor da raridade (o mesmo desenho para frente e silhueta).
class _Moldura extends StatelessWidget {
  const _Moldura({required this.rar, required this.child});
  final String rar;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final (cor, clara, escura) = coresRaridade[rar]!;
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [clara, cor, escura, cor, clara], stops: const [0, .25, .5, .75, 1]),
        boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.55), blurRadius: 14)],
      ),
      padding: const EdgeInsets.all(4),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF0B1E45), Color(0xFF06122E)]),
          border: Border.all(color: cor.withValues(alpha: 0.6), width: 1.5),
        ),
        clipBehavior: Clip.antiAlias,
        child: child,
      ),
    );
  }
}

/// Painel interno com borda na cor da raridade (blocos da carta).
Widget _painel(String rar, Widget child, {EdgeInsets pad = const EdgeInsets.fromLTRB(10, 6, 10, 6)}) {
  final cor = coresRaridade[rar]!.$1;
  return Container(
    padding: pad,
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(12),
      color: const Color(0xFF081A3D),
      border: Border.all(color: cor.withValues(alpha: 0.75), width: 1.6),
      boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.25), blurRadius: 6)],
    ),
    child: child,
  );
}

class _Face extends StatelessWidget {
  const _Face({required this.tk, required this.info, required this.rar, this.valores});
  final String tk, rar;
  final Map<String, dynamic> info;
  final Map<String, String>? valores;

  @override
  Widget build(BuildContext context) {
    final (cor, clara, _) = coresRaridade[rar]!;
    final nivel = (info['nivel'] as num?)?.toInt();
    final nome = '${info['nome'] ?? tk}';
    final setor = '${info['setor'] ?? '—'}';
    return _Moldura(
      rar: rar,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
        child: Column(children: [
          // topo: raridade (com estrela) e ticker
          SizedBox(
            height: 40,
            child: Row(children: [
              Expanded(
                flex: 11,
                child: _selo(
                  rar,
                  Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.star_rounded, size: 24, color: clara, shadows: [Shadow(color: cor, blurRadius: 8)]),
                    const SizedBox(width: 3),
                    Flexible(child: FittedBox(child: Text(rotulosRaridade[rar]!, style: _txt(17, clara, italico: true)))),
                  ]),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(flex: 9, child: _selo(rar, FittedBox(child: Text(tk, style: _txt(19, Colors.white, italico: true))))),
            ]),
          ),
          const SizedBox(height: 6),
          // ilustração
          SizedBox(
            height: 138,
            child: Stack(fit: StackFit.expand, children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: DecoratedBox(
                  decoration: BoxDecoration(border: Border.all(color: cor.withValues(alpha: 0.7), width: 1.5), borderRadius: BorderRadius.circular(10)),
                  child: _arte(info, rar),
                ),
              ),
              if (nivel != null)
                Positioned(
                  left: 6,
                  bottom: 6,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xE6081A3D), border: Border.all(color: cor, width: 1.5)),
                    child: Text('Nv $nivel', style: _txt(14, Colors.white)),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 6),
          // nome e setor
          _painel(
            rar,
            SizedBox(
              height: 52,
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                SizedBox(height: 28, child: FittedBox(child: Text(nome, style: _txt(26, Colors.white)))),
                Container(height: 1, margin: const EdgeInsets.symmetric(vertical: 2, horizontal: 10), color: cor.withValues(alpha: 0.7)),
                SizedBox(
                  height: 18,
                  child: FittedBox(
                    child: Text.rich(TextSpan(children: [
                      TextSpan(text: 'Setor:  ', style: _txt(14, Colors.white)),
                      TextSpan(text: setor, style: _txt(14, const Color(0xFFFFE94A), italico: true)),
                    ])),
                  ),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 6),
          // atividade principal
          _painel(
            rar,
            SizedBox(
              height: 66,
              child: Row(children: [
                SizedBox(
                  width: 46,
                  child: Text('${info['icone'] ?? '🏢'}', textAlign: TextAlign.center, style: TextStyle(fontSize: 32, shadows: [Shadow(color: cor, blurRadius: 10)])),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                    Text('Atividade Principal:', style: _txt(13.5, const Color(0xFF34E0FF), italico: true)),
                    const SizedBox(height: 1),
                    Text('${info['atividade'] ?? ''}', maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, height: 1.15, color: Colors.white)),
                  ]),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 6),
          // P/L · DY · ROE
          _painel(
            rar,
            SizedBox(
              height: 46,
              child: Row(children: [
                Expanded(child: _ind(Icons.trending_up_rounded, const Color(0xFF2EE59D), 'P/L', valores?['pl'])),
                Container(width: 1, height: 34, color: cor.withValues(alpha: 0.5)),
                Expanded(child: _ind(Icons.monetization_on_rounded, const Color(0xFFFFC93C), 'DY', valores?['dy_12m'])),
                Container(width: 1, height: 34, color: cor.withValues(alpha: 0.5)),
                Expanded(child: _ind(Icons.insights_rounded, const Color(0xFFC07BFF), 'ROE', valores?['roe'])),
              ]),
            ),
            pad: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          ),
          const SizedBox(height: 6),
          // curiosidade
          Expanded(
            child: _painel(
              rar,
              Row(children: [
                Icon(Icons.lightbulb_rounded, size: 30, color: const Color(0xFFFFC93C), shadows: [Shadow(color: const Color(0xFFFF9D00).withValues(alpha: 0.8), blurRadius: 10)]),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('${info['fato'] ?? ''}', maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, height: 1.15, color: Colors.white)),
                ),
              ]),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _ind(IconData ic, Color c, String nome, String? v) => Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(ic, size: 26, color: c, shadows: [Shadow(color: c.withValues(alpha: 0.7), blurRadius: 8)]),
        const SizedBox(width: 3),
        Flexible(
          child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(nome, style: _txt(12, c == const Color(0xFFC07BFF) ? c : const Color(0xFF9CC7FF))),
            FittedBox(child: Text(v ?? '?', style: _txt(14, Colors.white))),
          ]),
        ),
      ]);
}

Widget _selo(String rar, Widget child) {
  final (cor, _, escura) = coresRaridade[rar]!;
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(12),
      gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [const Color(0xFF13306A), escura.withValues(alpha: 0.9)]),
      border: Border.all(color: cor, width: 2),
      boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.45), blurRadius: 8)],
    ),
    alignment: Alignment.center,
    child: child,
  );
}

TextStyle _txt(double t, Color c, {bool italico = false}) => TextStyle(
      fontSize: t,
      fontWeight: FontWeight.w900,
      fontStyle: italico ? FontStyle.italic : FontStyle.normal,
      color: c,
      height: 1.05,
      shadows: const [Shadow(color: Color(0xCC000000), blurRadius: 4, offset: Offset(0, 1))],
    );

Widget _arte(Map info, String rar) {
  final arte = info['arte'];
  if (arte is String && arte.isNotEmpty) {
    return Image.asset('assets/cartas/$arte', fit: BoxFit.cover, errorBuilder: (_, __, ___) => _arteSetor(info, rar));
  }
  return _arteSetor(info, rar);
}

/// Sem arte própria: fundo na cor da raridade com o ícone do setor (sem logotipos de empresas).
Widget _arteSetor(Map info, String rar) {
  final (cor, clara, escura) = coresRaridade[rar]!;
  final ic = _artesSetor['${info['setor']}'] ?? 'industria';
  return DecoratedBox(
    decoration: BoxDecoration(
      gradient: RadialGradient(center: const Alignment(0, -0.2), radius: 1.0, colors: [cor.withValues(alpha: 0.55), escura.withValues(alpha: 0.6), const Color(0xFF071634)]),
    ),
    child: Stack(fit: StackFit.expand, children: [
      CustomPaint(painter: _Grade(clara.withValues(alpha: 0.12))),
      Center(
        child: Container(
          decoration: BoxDecoration(shape: BoxShape.circle, boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.6), blurRadius: 30, spreadRadius: 4)]),
          child: ClipRRect(borderRadius: BorderRadius.circular(22), child: Image.asset('assets/logos/setores/$ic.webp', height: 96)),
        ),
      ),
    ]),
  );
}

class _Grade extends CustomPainter {
  _Grade(this.cor);
  final Color cor;

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = cor
      ..strokeWidth = 1;
    for (var x = 0.0; x < size.width; x += 18) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), p);
    }
    for (var y = 0.0; y < size.height; y += 18) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), p);
    }
  }

  @override
  bool shouldRepaint(_Grade o) => o.cor != cor;
}

/// Carta ainda não descoberta: só a moldura da raridade, um "?" e o setor.
class _Silhueta extends StatelessWidget {
  const _Silhueta({required this.rar, required this.setor});
  final String rar, setor;

  @override
  Widget build(BuildContext context) {
    final (cor, clara, _) = coresRaridade[rar]!;
    return Opacity(
      opacity: 0.85,
      child: _Moldura(
        rar: rar,
        child: Stack(fit: StackFit.expand, children: [
          CustomPaint(painter: _Grade(cor.withValues(alpha: 0.10))),
          Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(Icons.help_rounded, size: 120, color: cor.withValues(alpha: 0.55), shadows: [Shadow(color: cor, blurRadius: 24)]),
            const SizedBox(height: 14),
            Text(rotulosRaridade[rar]!, style: _txt(40, clara, italico: true)),
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: FittedBox(child: Text(setor, style: _txt(28, const Color(0xFFFFE94A)))),
            ),
            const SizedBox(height: 18),
            const Icon(Icons.lock_rounded, size: 40, color: Colors.white54),
          ]),
        ]),
      ),
    );
  }
}

/// Nível e raridade de uma carta do duelo (o resto vem do catálogo).
Map<String, dynamic> dadosDoDuelo(Object? c) {
  final m = (c as Map?) ?? const {};
  return {if (m['nivel'] != null) 'nivel': m['nivel'], if (m['rar'] != null) 'raridade': m['rar']};
}

/// Valores {pl, dy_12m, roe} → texto, a partir da lista de indicadores do duelo ([{id, txt}]).
Map<String, String> valoresDoDuelo(Object? ind) => {
      for (final i in ((ind as List?) ?? const []).cast<Map>()) '${i['id']}': '${i['txt']}',
    };

// ===================================================================================== revelação (baú, pacote inicial)

/// Mostra as cartas recebidas, uma a uma: carta virada → gira e revela (nova = "NOVA!", repetida = "+1 cópia").
/// Lendária tem raios dourados girando e mais brilho.
Future<void> revelarCartas(BuildContext context, List itens, {String titulo = 'Cartas recebidas'}) {
  final lista = itens.cast<Map>().map((m) => m.cast<String, dynamic>()).toList();
  if (lista.isEmpty) return Future.value();
  return showGeneralDialog(
    context: context,
    barrierDismissible: false,
    barrierColor: const Color(0xE6030A1C),
    transitionDuration: const Duration(milliseconds: 250),
    pageBuilder: (ctx, _, __) => _Revelacao(itens: lista, titulo: titulo),
  );
}

class _Revelacao extends StatefulWidget {
  const _Revelacao({required this.itens, required this.titulo});
  final List<Map<String, dynamic>> itens;
  final String titulo;

  @override
  State<_Revelacao> createState() => _RevelacaoState();
}

class _RevelacaoState extends State<_Revelacao> with TickerProviderStateMixin {
  int _i = 0;
  late final AnimationController _vira = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..forward();
  late final AnimationController _giro = AnimationController(vsync: this, duration: const Duration(seconds: 9))..repeat();

  @override
  void dispose() {
    _vira.dispose();
    _giro.dispose();
    super.dispose();
  }

  void _proxima() {
    if (_vira.isAnimating) return;
    if (_i >= widget.itens.length - 1) {
      Navigator.of(context).pop();
      return;
    }
    setState(() => _i++);
    _vira.forward(from: 0);
  }

  @override
  Widget build(BuildContext context) {
    final it = widget.itens[_i];
    final rar = coresRaridade.containsKey(it['raridade']) ? '${it['raridade']}' : 'comum';
    final (cor, clara, _) = coresRaridade[rar]!;
    final lend = rar == 'lendaria';
    final larg = min(MediaQuery.of(context).size.width * 0.62, 260.0);
    return Material(
      type: MaterialType.transparency,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _proxima,
        child: SafeArea(
          child: Column(children: [
            const SizedBox(height: 14),
            Text(widget.titulo, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white)),
            Text('${_i + 1} de ${widget.itens.length}', style: const TextStyle(fontSize: 13, color: Color(0xFFB5C8E6))),
            Expanded(
              child: Center(
                child: AnimatedBuilder(
                  animation: Listenable.merge([_vira, _giro]),
                  builder: (ctx, _) {
                    final t = Curves.easeInOutCubic.transform((_vira.value / 0.7).clamp(0.0, 1.0));
                    final pos = Curves.elasticOut.transform(((_vira.value - 0.55) / 0.45).clamp(0.0, 1.0));
                    final ang = pi * (1 - t);
                    final frente = ang < pi / 2;
                    return Stack(alignment: Alignment.center, children: [
                      if (frente)
                        Transform.rotate(
                          angle: _giro.value * 2 * pi,
                          child: CustomPaint(size: Size.square(larg * (lend ? 2.3 : 1.8)), painter: _RaiosCarta(cor.withValues(alpha: lend ? 0.55 : 0.3), lend ? 18 : 12)),
                        ),
                      Container(
                        width: larg * 0.9,
                        height: larg * 0.9,
                        decoration: BoxDecoration(shape: BoxShape.circle, boxShadow: [BoxShadow(color: cor.withValues(alpha: frente ? (lend ? 0.7 : 0.45) : 0.1), blurRadius: 80, spreadRadius: 10)]),
                      ),
                      Transform(
                        alignment: Alignment.center,
                        transform: Matrix4.identity()
                          ..setEntry(3, 2, 0.0012)
                          ..rotateY(ang),
                        child: Transform.scale(
                            scale: 0.7 + 0.3 * t,
                            child: frente
                                ? CartaTk(tk: '${it['tk']}', largura: larg, dados: it)
                                : Transform(alignment: Alignment.center, transform: Matrix4.rotationY(pi), child: _Verso(largura: larg, cor: cor))),
                      ),
                      if (frente)
                        Positioned(
                          top: 0,
                          child: Transform.scale(
                            scale: 0.4 + 0.6 * pos,
                            child: Opacity(
                              opacity: pos.clamp(0.0, 1.0),
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(999),
                                  color: it['nova'] == true ? const Color(0xFF26D07C) : const Color(0xFF1C50A0),
                                  border: Border.all(color: Colors.white, width: 2),
                                  boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.8), blurRadius: 16)],
                                ),
                                child: Text(it['nova'] == true ? 'NOVA CARTA!' : '+1 cópia · ${it['copias'] ?? ''} guardada(s)',
                                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
                              ),
                            ),
                          ),
                        ),
                    ]);
                  },
                ),
              ),
            ),
            Text(lend ? '✨ ${nomesRaridade[rar]}! ✨' : nomesRaridade[rar]!, style: TextStyle(fontSize: lend ? 22 : 17, fontWeight: FontWeight.w900, color: clara)),
            const SizedBox(height: 6),
            Text(_i < widget.itens.length - 1 ? 'Toque para a próxima carta' : 'Toque para fechar', style: const TextStyle(fontSize: 13, color: Color(0xFFB5C8E6))),
            const SizedBox(height: 18),
          ]),
        ),
      ),
    );
  }
}

class _Verso extends StatelessWidget {
  const _Verso({required this.largura, required this.cor});
  final double largura;
  final Color cor;

  @override
  Widget build(BuildContext context) => Container(
        width: largura,
        height: CartaTk.alturaPara(largura),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(largura * 0.07),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1C50A0), Color(0xFF081A3D), Color(0xFF1C50A0)]),
          border: Border.all(color: const Color(0xFFFFC93C), width: 4),
          boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.6), blurRadius: 20)],
        ),
        alignment: Alignment.center,
        child: Image.asset('assets/logo_th.webp', width: largura * 0.6, errorBuilder: (_, __, ___) => const Icon(Icons.style_rounded, size: 80, color: Color(0xFFFFC93C))),
      );
}

class _RaiosCarta extends CustomPainter {
  _RaiosCarta(this.cor, this.n);
  final Color cor;
  final int n;

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 2;
    final p = Paint()..shader = RadialGradient(colors: [cor, cor.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: r));
    for (var i = 0; i < n; i++) {
      final a = 2 * pi * i / n;
      final path = Path()
        ..moveTo(c.dx, c.dy)
        ..lineTo(c.dx + r * cos(a - 0.09), c.dy + r * sin(a - 0.09))
        ..lineTo(c.dx + r * cos(a + 0.09), c.dy + r * sin(a + 0.09))
        ..close();
      canvas.drawPath(path, p);
    }
  }

  @override
  bool shouldRepaint(_RaiosCarta o) => o.cor != cor || o.n != n;
}
