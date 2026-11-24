import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'api.dart';
import 'navegacao.dart';

/// Tour guiado do primeiro acesso (onboarding interativo).
///
/// O urso leva o jogador por um primeiro dia completo de "caçador": conhece a tela inicial, faz a primeira lição (aprender),
/// abre uma empresa no Mercado (analisar), faz a primeira compra na Carteira (comprar) e joga uma partida de treino (jogar).
/// Cada passo escurece a tela e deixa aceso só o que é para tocar (o resto não responde). Nos passos de fazer de verdade
/// (lição, compra, partida) a camada some e o tour espera o aviso da tela (`Tour.evento`). O servidor (`/tour`) guarda onde o
/// jogador parou e paga, uma vez cada, os Ticker Coins dos marcos.
///
/// Como ligar uma tela: envolva o elemento em `TourAlvo(id: '...', child: ...)` e chame `Tour.evento('...')` quando algo
/// acontecer. A camada (`TourCamada`) fica por cima de tudo, no `builder` do MaterialApp.
class PassoTour {
  const PassoTour({required this.titulo, required this.texto, this.alvo, this.evento, this.marco, this.espera, this.botao = 'Próximo', this.secao = false});

  final String titulo, texto;

  /// Elemento aceso (id de um `TourAlvo`). Sem alvo: cartão no meio da tela.
  final String? alvo;

  /// Passo de toque: o passo acaba quando a tela avisa este evento (ex.: 'aba_2', 'tela_mercado', 'compra').
  final String? evento;

  /// Marco do servidor cumprido ao terminar o passo (paga TC uma vez).
  final String? marco;

  /// Depois do toque, o jogador faz algo longo (lição, compra, partida): a camada some e fica só este lembrete.
  final String? espera;

  final String botao;

  /// Começo de uma parte do tour: ao voltar ao app no meio, o tour recomeça da última parte (não do meio de um passo de toque).
  final bool secao;
}

const passosTour = <PassoTour>[
  PassoTour(
    secao: true,
    titulo: 'Bem-vindo, caçador!',
    texto: 'Eu sou o Hunter. Aqui você aprende a investir jogando, com dinheiro virtual: sem risco nenhum.\n\n'
        'Vamos fazer o seu primeiro dia juntos: aprender, analisar, comprar e jogar. Leva uns 5 minutos e vale até 100 Ticker Coins!',
    botao: 'Bora!',
  ),
  PassoTour(alvo: 'cab_moedas', titulo: 'Ticker Coins (TC)', texto: 'As moedas do jogo. Você ganha TC com lições, missões e partidas, e troca por itens na Loja.'),
  PassoTour(alvo: 'home_liga', titulo: 'Sua liga', texto: 'Partidas online valem troféus. Com troféus você sobe de divisão: Bronze, Prata, Ouro... até Lenda!'),
  PassoTour(alvo: 'home_desafio', titulo: 'Desafio do dia', texto: 'Todo dia, o mesmo gráfico para todos e uma tentativa só. Os melhores do dia ganham TC.'),
  PassoTour(
    secao: true,
    alvo: 'nav_2',
    evento: 'aba_2',
    titulo: '1 · Aprender',
    texto: 'Todo bom investidor começa estudando. Toque em Aprender.',
  ),
  PassoTour(
    alvo: 'area_financas',
    evento: 'tela_area_financas',
    titulo: 'Escolha um caminho',
    texto: 'O Aprender é dividido em áreas: finanças, cartões, investimentos, trading, cripto, certificações... Vamos começar pela base: toque em Educação financeira.',
  ),
  PassoTour(
    alvo: 'aprender_proxima',
    evento: 'licao',
    marco: 'aprender',
    espera: 'Conclua a lição para continuar o tour',
    titulo: 'Sua primeira lição',
    texto: 'Lições curtas, de 2 minutos. Toque nela e depois em Começar. Eu espero você terminar!',
  ),
  PassoTour(titulo: 'Mandou bem!', texto: 'Primeira lição feita! Agora vamos usar o que você aprendeu para analisar uma empresa de verdade.'),
  PassoTour(secao: true, alvo: 'nav_0', evento: 'aba_0', titulo: '2 · Analisar', texto: 'Volte ao Início.'),
  PassoTour(alvo: 'home_mercado', evento: 'tela_mercado', titulo: 'O Mercado', texto: 'Aqui ficam as ações da bolsa e as criptomoedas, com dados reais. Toque para abrir.'),
  PassoTour(alvo: 'mercado_acao', evento: 'tela_acao', titulo: 'Escolha uma empresa', texto: 'Toque nesta empresa para ver a análise completa dela.'),
  PassoTour(
    alvo: 'acao_preco',
    titulo: 'O preço está bom?',
    texto: 'Compara o preço de hoje com quanto a empresa parece valer pelos lucros e dividendos. Mais barata que o valor estimado pode ser uma oportunidade!',
  ),
  PassoTour(
    alvo: 'acao_saude',
    marco: 'analisar',
    titulo: 'A empresa é saudável?',
    texto: 'Lucro, dívidas e dividendos explicados em palavras simples. Mais abaixo ficam o preço justo e os indicadores (P/L, ROE...) para quem quer ir fundo.',
  ),
  PassoTour(titulo: 'Analisou? Hora de comprar!', texto: 'Você tem um capital virtual na Carteira para montar a sua carteira de investimentos.'),
  PassoTour(secao: true, alvo: 'nav_0', evento: 'aba_0', titulo: '3 · Comprar', texto: 'Volte ao Início.'),
  PassoTour(alvo: 'home_carteira', evento: 'tela_carteira', titulo: 'Sua Carteira', texto: 'Aqui fica o seu dinheiro virtual e os seus investimentos. Toque para abrir.'),
  PassoTour(
    alvo: 'cart_comprar',
    evento: 'compra',
    marco: 'comprar',
    espera: 'Faça a sua primeira compra para continuar o tour',
    titulo: 'Sua primeira compra',
    texto:
        'Se a carteira ainda não estiver ativa, escolha um apelido e toque em Participar. Depois toque em Comprar, digite o código da ação (por exemplo PETR4) e a quantidade. É dinheiro virtual: pode testar sem medo!',
  ),
  PassoTour(titulo: 'Você é investidor!', texto: 'A sua carteira segue o mercado de verdade, dia após dia. Agora, a parte mais divertida: jogar.'),
  PassoTour(secao: true, alvo: 'nav_0', evento: 'aba_0', titulo: '4 · Jogar', texto: 'Volte ao Início.'),
  PassoTour(
    alvo: 'home_trade',
    evento: 'tela_trade',
    titulo: 'Trade Battle',
    texto: 'Você opera um gráfico real, comprando e vendendo no tempo certo, e disputa com outros jogadores. Toque para entrar.',
  ),
  PassoTour(
    alvo: 'trade_solo',
    evento: 'partida',
    marco: 'jogar',
    espera: 'Termine a partida de treino para concluir o tour',
    titulo: 'Partida de treino',
    texto: 'Já deixei a duração Rápida escolhida. Toque em Jogar Solo: compre quando achar que vai subir e venda antes de cair!',
  ),
  PassoTour(
    secao: true,
    marco: 'fim',
    titulo: 'Primeiro dia concluído!',
    texto: 'Você aprendeu, analisou, comprou e jogou: já é um caçador de verdade! Aqui vão +50 TC de presente.\n\n'
        'Volte todo dia: Desafio do dia, missões e o torneio de fim de semana. Boa caçada!',
    botao: 'Concluir',
  ),
];

/// Controle do tour (um só no app).
class Tour {
  static Api? _api;
  static final passo = ValueNotifier<int?>(null); // null = sem tour
  static final esperando = ValueNotifier<bool>(false); // passo de "fazer de verdade" em andamento: a camada some
  static final ganho = ValueNotifier<int>(0); // TC ganhos no último marco (mostra no cartão seguinte)
  static final _alvos = <String, GlobalKey>{};

  /// Lê o tour no servidor; se ainda não foi feito nem pulado, começa (ou continua da última parte).
  static Future<void> iniciar(Api api) async {
    _api = api;
    try {
      final r = await api.get('/tour');
      if (r['ativo'] != true) return;
      var p = ((r['passo'] as num?) ?? 0).toInt().clamp(0, passosTour.length - 1);
      while (p > 0 && !passosTour[p].secao) {
        p--;
      }
      esperando.value = false;
      passo.value = p;
    } catch (_) {}
  }

  /// Rever o tour (pela Ajuda): volta ao começo; os prêmios já recebidos não se repetem.
  static Future<void> rever() async {
    try {
      await _api?.post('/tour', {'reiniciar': true});
    } catch (_) {}
    abrirAba(0);
    esperando.value = false;
    passo.value = 0;
  }

  static Future<void> pular() async {
    passo.value = null;
    esperando.value = false;
    try {
      await _api?.post('/tour', {'pular': true});
    } catch (_) {}
  }

  /// Uma tela avisa algo (troca de aba, tela aberta, lição concluída, compra feita, partida terminada).
  static void evento(String e) {
    // as telas avisam no initState (no meio da montagem): o passo troca logo depois, fora da montagem
    scheduleMicrotask(() {
      final i = passo.value;
      if (i == null || passosTour[i].evento != e) return;
      _concluir(i);
    });
  }

  /// Próximo (passos de informação) ou fim de um passo de toque.
  static Future<void> _concluir(int i) async {
    final p = passosTour[i];
    final prox = i + 1;
    esperando.value = false;
    ganho.value = 0;
    passo.value = prox < passosTour.length ? prox : null;
    try {
      final r = await _api?.post('/tour', {'passo': prox < passosTour.length ? prox : i, if (p.marco != null) 'marco': p.marco});
      final tc = (r?['tc'] as num?)?.toInt() ?? 0;
      if (tc > 0) {
        ganho.value = tc;
        saldoMudou.value++; // moedas novas no cabeçalho
      }
    } catch (_) {}
  }

  static void proximo() {
    final i = passo.value;
    if (i != null) _concluir(i);
  }

  static void _registrar(String id, GlobalKey k) => _alvos[id] = k;
  static void _remover(String id, GlobalKey k) {
    if (_alvos[id] == k) _alvos.remove(id);
  }

  /// Rola a tela até o alvo, se ele estiver cortado na borda (uma vez por passo).
  static int? _rolado;
  static void _rolarAte(String id, Size tela, Rect r) {
    final i = passo.value;
    if (i == null || _rolado == i) return;
    if (r.top >= 90 && r.bottom <= tela.height - 130) return;
    final c = _alvos[id]?.currentContext;
    if (c == null || Scrollable.maybeOf(c) == null) return;
    _rolado = i;
    Scrollable.ensureVisible(c, alignment: 0.35, duration: const Duration(milliseconds: 450), curve: Curves.easeOutCubic);
  }

  /// Retângulo do alvo na tela, só se ele estiver à mostra (aba aberta e tela do topo).
  static Rect? retangulo(String id) {
    final c = _alvos[id]?.currentContext;
    if (c == null || !c.mounted) return null;
    if (!TickerMode.valuesOf(c).enabled) return null;
    if (ModalRoute.of(c)?.isCurrent == false) return null;
    final ro = c.findRenderObject();
    if (ro is! RenderBox || !ro.attached || !ro.hasSize) return null;
    // posição E tamanho já com a escala da tela (no tablet a tela inicial é montada em tamanho de celular e ampliada)
    return MatrixUtils.transformRect(ro.getTransformTo(null), Offset.zero & ro.size);
  }
}

/// Marca um elemento que o tour pode acender.
class TourAlvo extends StatefulWidget {
  const TourAlvo({super.key, required this.id, required this.child});
  final String id;
  final Widget child;

  @override
  State<TourAlvo> createState() => _TourAlvoState();
}

class _TourAlvoState extends State<TourAlvo> {
  final _k = GlobalKey();

  @override
  void initState() {
    super.initState();
    Tour._registrar(widget.id, _k);
  }

  @override
  void dispose() {
    Tour._remover(widget.id, _k);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => KeyedSubtree(key: _k, child: widget.child);
}

/// A camada do tour, por cima de todo o app.
class TourCamada extends StatefulWidget {
  const TourCamada({super.key});

  @override
  State<TourCamada> createState() => _TourCamadaState();
}

class _TourCamadaState extends State<TourCamada> with SingleTickerProviderStateMixin {
  late final AnimationController _pulso = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);
  Timer? _relogio;
  Rect? _r;

  @override
  void initState() {
    super.initState();
    Tour.passo.addListener(_mudou);
    Tour.esperando.addListener(_mudou);
    modoJogo.addListener(_mudou);
    // o alvo pode mexer (rolagem, telas abrindo): confere a posição algumas vezes por segundo enquanto o tour está ativo
    _relogio = Timer.periodic(const Duration(milliseconds: 200), (_) => _medir());
  }

  @override
  void dispose() {
    _relogio?.cancel();
    _pulso.dispose();
    Tour.passo.removeListener(_mudou);
    Tour.esperando.removeListener(_mudou);
    modoJogo.removeListener(_mudou);
    super.dispose();
  }

  void _mudou() {
    if (mounted) setState(() {});
    _medir();
  }

  void _medir() {
    final i = Tour.passo.value;
    final alvo = i == null ? null : passosTour[i].alvo;
    final r = alvo == null ? null : Tour.retangulo(alvo);
    if (r != null && mounted) Tour._rolarAte(alvo!, MediaQuery.sizeOf(context), r);
    if (r != _r && mounted) setState(() => _r = r);
  }

  @override
  Widget build(BuildContext context) {
    final i = Tour.passo.value;
    if (i == null || Tour.esperando.value || modoJogo.value > 0) return const SizedBox.shrink();
    final p = passosTour[i];
    final tela = MediaQuery.sizeOf(context);
    // passo com alvo que ainda não está à mostra (tela carregando, outra aba): não trava o jogador, mostra só um lembrete
    if (p.alvo != null && _r == null) return _lembrete(p, tela);
    final buraco = _r?.inflate(6);
    return Stack(children: [
      // fundo escuro com o buraco no alvo
      Positioned.fill(
        child: IgnorePointer(
          child: AnimatedBuilder(
            animation: _pulso,
            builder: (ctx, _) => CustomPaint(painter: _Escuro(buraco, _pulso.value)),
          ),
        ),
      ),
      // o escuro não deixa tocar no resto; no buraco o toque passa para o app
      ..._bloqueios(buraco, tela),
      if (buraco != null && p.evento != null)
        Positioned.fromRect(
          rect: buraco,
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerUp: (_) {
              // tocou no alvo: se o passo é longo (lição, compra, partida), a camada some até a tela avisar que acabou
              if (p.espera != null) Future.delayed(const Duration(milliseconds: 250), () => Tour.esperando.value = true);
            },
          ),
        ),
      if (buraco != null && p.evento != null) _mao(buraco),
      _balao(p, buraco, tela),
    ]);
  }

  List<Widget> _bloqueios(Rect? b, Size t) {
    Widget bloco(Rect r) => Positioned.fromRect(rect: r, child: const AbsorbPointer(child: SizedBox.expand()));
    if (b == null) return [bloco(Offset.zero & t)];
    final passa = passosTour[Tour.passo.value!].evento != null;
    if (!passa) return [bloco(Offset.zero & t)]; // passo de informação: nada no app responde, só o balão
    return [
      bloco(Rect.fromLTRB(0, 0, t.width, math.max(0, b.top))),
      bloco(Rect.fromLTRB(0, b.bottom, t.width, t.height)),
      bloco(Rect.fromLTRB(0, b.top, math.max(0, b.left), b.bottom)),
      bloco(Rect.fromLTRB(b.right, b.top, t.width, b.bottom)),
    ];
  }

  /// Mãozinha apontando o alvo, subindo e descendo.
  Widget _mao(Rect b) => AnimatedBuilder(
        animation: _pulso,
        builder: (ctx, _) => Positioned(
          left: b.center.dx - 4,
          top: b.center.dy + 6 + _pulso.value * 10,
          child: const IgnorePointer(child: Text('👆', style: TextStyle(fontSize: 38, shadows: [Shadow(color: Colors.black87, blurRadius: 6)]))),
        ),
      );

  Widget _balao(PassoTour p, Rect? b, Size t) {
    final largura = math.min(t.width - 24, 420.0);
    final cartao = _Cartao(p: p, largura: largura);
    final pad = MediaQuery.paddingOf(context);
    if (b == null) return Center(child: cartao);
    // abaixo do alvo se ele está na metade de cima; senão, acima
    final emCima = b.center.dy < t.height / 2;
    return Positioned(
      left: (t.width - largura) / 2,
      top: emCima ? math.min(b.bottom + 58, t.height - 260) : null,
      bottom: emCima ? null : math.max(pad.bottom + 12, t.height - b.top + 14),
      width: largura,
      child: cartao,
    );
  }

  /// Lembrete discreto (não bloqueia nada) quando o alvo do passo não está na tela.
  Widget _lembrete(PassoTour p, Size t) => Positioned(
        left: 12,
        right: 12,
        bottom: MediaQuery.paddingOf(context).bottom + 96,
        child: Center(
          child: Material(
            color: Colors.transparent,
            child: Container(
              constraints: const BoxConstraints(maxWidth: 420),
              padding: const EdgeInsets.fromLTRB(8, 6, 6, 6),
              decoration: _decoracaoBalao(),
              child: Row(children: [
                Image.asset('assets/home/urso_joinha.webp', height: 40),
                const SizedBox(width: 6),
                Expanded(
                  child: Text('${p.titulo}: ${p.texto}', maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: Colors.white)),
                ),
                TextButton(onPressed: Tour.pular, child: const Text('Pular', style: TextStyle(color: Color(0xFFBFD3FF)))),
              ]),
            ),
          ),
        ),
      );
}

BoxDecoration _decoracaoBalao() => BoxDecoration(
      borderRadius: BorderRadius.circular(20),
      gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1A3A80), Color(0xFF0B1A47)]),
      border: Border.all(color: const Color(0xFFF7C84A), width: 2),
      boxShadow: const [BoxShadow(color: Color(0xAA000000), blurRadius: 18, offset: Offset(0, 6))],
    );

/// Balão do urso: título dourado, texto, prêmio ganho, botões Próximo e Pular.
class _Cartao extends StatelessWidget {
  const _Cartao({required this.p, required this.largura});
  final PassoTour p;
  final double largura;

  @override
  Widget build(BuildContext context) {
    final i = Tour.passo.value ?? 0;
    final info = p.evento == null;
    return Material(
      color: Colors.transparent,
      child: TweenAnimationBuilder<double>(
        key: ValueKey(i),
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 380),
        curve: Curves.easeOutBack,
        builder: (ctx, v, child) => Opacity(opacity: v.clamp(0.0, 1.0), child: Transform.scale(scale: 0.85 + 0.15 * v, child: child)),
        child: Container(
          width: largura,
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
          decoration: _decoracaoBalao(),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Image.asset('assets/home/urso_joinha.webp', height: p.alvo == null ? 86 : 58),
              const SizedBox(width: 8),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(p.titulo, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFFF7C84A))),
                  const SizedBox(height: 4),
                  Text(p.texto, style: const TextStyle(fontSize: 14, height: 1.3, color: Colors.white)),
                ]),
              ),
            ]),
            ValueListenableBuilder<int>(
              valueListenable: Tour.ganho,
              builder: (ctx, tc, _) => tc <= 0
                  ? const SizedBox.shrink()
                  : Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Row(children: [
                        Image.asset('assets/home/ic_moeda.webp', height: 22),
                        const SizedBox(width: 6),
                        Text('+$tc TC', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFF2EE88A))),
                      ]),
                    ),
            ),
            const SizedBox(height: 6),
            Row(children: [
              // progresso: bolinhas das 4 partes
              for (final (k, s) in const ['Aprender', 'Analisar', 'Comprar', 'Jogar'].indexed)
                Padding(
                  padding: const EdgeInsets.only(right: 4),
                  child: Semantics(
                    label: s,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(shape: BoxShape.circle, color: i >= [4, 8, 14, 18][k] ? const Color(0xFFF7C84A) : const Color(0x553A6FD8)),
                    ),
                  ),
                ),
              const Spacer(),
              if (i < passosTour.length - 1) TextButton(onPressed: Tour.pular, child: const Text('Pular tour', style: TextStyle(color: Color(0xFFBFD3FF)))),
              if (info)
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: const Color(0xFFF5A623), foregroundColor: const Color(0xFF3B2600)),
                  onPressed: Tour.proximo,
                  child: Text(p.botao, style: const TextStyle(fontWeight: FontWeight.w900)),
                ),
            ]),
          ]),
        ),
      ),
    );
  }
}

/// Fundo escuro com um buraco arredondado no alvo e uma borda dourada pulsando em volta.
class _Escuro extends CustomPainter {
  _Escuro(this.b, this.t);
  final Rect? b;
  final double t;

  @override
  void paint(Canvas canvas, Size s) {
    final fundo = Path()..addRect(Offset.zero & s);
    if (b == null) {
      canvas.drawPath(fundo, Paint()..color = const Color(0xC8030A20));
      return;
    }
    final rr = RRect.fromRectAndRadius(b!, const Radius.circular(16));
    canvas.drawPath(Path.combine(PathOperation.difference, fundo, Path()..addRRect(rr)), Paint()..color = const Color(0xC8030A20));
    canvas.drawRRect(
        rr.inflate(2 + t * 4),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = Color.lerp(const Color(0xFFF7C84A), const Color(0x00F7C84A), t * 0.7)!);
  }

  @override
  bool shouldRepaint(covariant _Escuro o) => o.b != b || o.t != t;
}
