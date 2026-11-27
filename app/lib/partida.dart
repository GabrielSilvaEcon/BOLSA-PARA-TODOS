import 'som.dart';
import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'tour.dart';
import 'escudo.dart';
import 'estrategia.dart';
import 'mesa/mesa_host.dart';
import 'navegacao.dart';
import 'ordem_respostas.dart';
import 'relatorio.dart';
import 'resultado_partida.dart';
import 'estado_partida.dart';
import 'fim_partida.dart';
import 'ticker_online.dart' show BuscaTela;

/// Partida solo do Trade Battle. A mesa (gráfico, boleta, placar) é a MESMA do app antigo; aqui o app só faz a ponte com o servidor:
/// cria a partida (`POST /trade/solo`) ou entra na da sala (`/trade/salas/{id}`), consulta o andamento a cada segundo e manda as jogadas
/// (`/estrategia` e `/acao`). No fim, abre o relatório da partida (o mesmo do app antigo).
class PartidaTela extends StatefulWidget {
  const PartidaTela({super.key, required this.api, this.corrida = 'intermediaria', this.salaId, this.inicio});
  final Api api;
  final String corrida;

  /// Partida de uma sala com amigos (já criada e iniciada). Sem ela, é a partida solo.
  final String? salaId;

  /// Rota que cria a partida solo no lugar de /trade/solo (ex.: '/desafio/jogar', o gráfico do Desafio do dia).
  final String? inicio;

  @override
  State<PartidaTela> createState() => _PartidaTelaState();
}

class _PartidaTelaState extends State<PartidaTela> {
  late final MesaHost _mesa = MesaHost(aoEvento: _evento, aoPronto: () {});
  String? _pid;
  String? _erroInicio;
  Map<String, dynamic>? _ultima;
  Timer? _relogio;
  bool _ocupado = false;
  bool _fim = false;
  bool _relatorioAberto = false;
  Map<String, dynamic>? _fimDados;
  bool _resultadoAberto = false;

  /// Fase da estratégia na partida corrida: o app mostra o gráfico próprio com as ferramentas de desenho (a mesa fica por baixo).
  bool _estrategia = false;

  /// O relógio e as jogadas pedem ao servidor ao mesmo tempo: descarta a resposta que chega atrasada.
  final _ordem = OrdemRespostas();

  // o que a mesa precisa saber das jogadas já tratadas (no Streamlit vinha do "estado" da sessão)
  int _seqTratada = 0;
  int _seqOk = 0;
  String _erro = '';
  int _seqErro = 0;

  @override
  void initState() {
    super.initState();
    // tela cheia durante a partida: some o cabeçalho e a barra de baixo do app e, no celular, as barras do sistema
    WidgetsBinding.instance.addPostFrameCallback((_) => modoJogo.value++);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _iniciar();
  }

  @override
  void dispose() {
    _relogio?.cancel();
    _mesa.fechar();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (modoJogo.value > 0) modoJogo.value--;
      if (modoJogo.value == 0) SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    });
    super.dispose();
  }

  Future<void> _iniciar() async {
    try {
      final sala = widget.salaId;
      final r = sala == null ? await widget.api.post(widget.inicio ?? '/trade/solo', {'corrida': widget.corrida}) : await widget.api.get('/trade/salas/$sala');
      if (mounted) setState(() => _pid = sala ?? r['id']?.toString());
      _aplicar(r);
      _relogio = Timer.periodic(const Duration(seconds: 1), (_) => _consultar());
    } catch (e) {
      if (mounted) setState(() => _erroInicio = e.toString());
    }
  }

  /// Endereço da partida no servidor: solo ou sala.
  String get _base => widget.salaId == null ? '/trade/solo/$_pid' : '/trade/salas/$_pid';

  Future<void> _consultar() async {
    if (_ocupado || _pid == null || _fim) return;
    _ocupado = true;
    final id = _ordem.novo();
    try {
      final r = await widget.api.get(_inc.consulta(_base));
      if (_ordem.aceitar(id)) _aplicar(r);   // chegou depois de uma jogada mais nova: o retrato já está velho
    } catch (_) {
      // falha de rede passageira: tenta de novo no próximo segundo
    } finally {
      _ocupado = false;
    }
  }

  /// Manda o estado do servidor para a mesa desenhar, com o retorno das jogadas já tratadas.
  void _aplicar(Map<String, dynamic> bruta) {
    final r = _inc.aplicar(bruta); // resposta completa (junta a cauda dos candles / reaproveita o estado sem mudança)
    if (r == null) return; // não encaixou: descarta; a próxima consulta pede o estado completo
    if (r['estado'] == 'cancelada') {
      _relogio?.cancel();
      if (mounted) setState(() => _erroInicio = 'A sala foi cancelada.');
      return;
    }
    final tela = r['tela'];
    if (tela is Map) {
      final args = Map<String, dynamic>.from(tela);
      args['seq0'] = _seqTratada;
      args['ok_seq'] = _seqOk;
      args['erro'] = _erro;
      args['erro_seq'] = _seqErro;
      args['som'] = Som.ligado.value; // o botão de som de Minha conta vale também dentro da mesa
      _ultima = args;
      _mesa.desenhar(args);
      final est = r['fase'] == 'analise' && args['corrida'] == true; // pela fase da partida: no fim a tela também vem como "analise"
      if (est != _estrategia) _mesa.toques(!est);
      if (mounted && (est || est != _estrategia)) setState(() => _estrategia = est);
    }
    if (r['fim'] != null && !_fim) {
      _fim = true;
      Tour.evento('partida'); // tour guiado: partida de treino terminada
      _fimDados = (r['fim'] as Map).cast<String, dynamic>();
      _relogio?.cancel();
      if (mounted) setState(() {});
      final tr = _fimDados?['trofeus'];
      if (tr is Map && mounted && !ResultadoPartida.temAdversario(_fimDados!)) {
        // partida online: primeiro a tela de troféus (vitória/derrota e a barra da divisão), depois o relatório
        ResultadoTrofeusTela.abrir(context, tr, api: widget.api).then((_) {
          if (mounted) _abrirResultado();
        });
        return;
      }
      _abrirResultado();
    }
  }

  void _redesenhar() {
    final a = _ultima;
    if (a == null) return;
    a['seq0'] = _seqTratada;
    a['ok_seq'] = _seqOk;
    a['erro'] = _erro;
    a['erro_seq'] = _seqErro;
    _mesa.desenhar(a);
  }

  /// Jogadas que a mesa manda (mesmos eventos que ela mandava ao Streamlit).
  Future<void> _evento(Map<String, dynamic> v) async {
    final seq = (v['seq'] as num?)?.toInt() ?? 0;
    final ev = v['evento'];
    if (_pid == null) return;
    if (ev == 'voltar' || ev == 'ranking') {
      if (mounted) Navigator.of(context).maybePop();
      return;
    }
    if (ev != 'confirmar' && ev != 'acao' && ev != 'setup') {
      await _consultar(); // tempo, próxima etc.: o servidor anda sozinho pelo relógio
      return;
    }
    _ocupado = true;
    final id = _ordem.novo();
    try {
      final Map<String, dynamic> r;
      if (ev == 'confirmar') {
        final plano = (v['plano'] as Map?) ?? {'direcao': v['direcao'], 'tipo': v['tipo']};
        r = await widget.api.post('$_base/estrategia', {'direcao': plano['direcao'], 'tipo': plano['tipo']});
        _seqOk = seq;
      } else if (ev == 'setup') {
        // decisão da janela do setup (entrar/recusar): quem vale é o servidor, com o prazo dele
        r = await widget.api.post('$_base/setup', {'acao': (v['dados'] as Map?)?['acao'], 'q': (v['dados'] as Map?)?['q']});
      } else {
        r = await widget.api.post('$_base/acao', {'dados': v['dados'] ?? {}});
      }
      _erro = '';
      _seqTratada = seq;
      if (_ordem.aceitar(id)) _aplicar(r);
    } catch (e) {
      _erro = e.toString();
      _seqErro = seq;
      _seqTratada = seq;
      _redesenhar();
    } finally {
      _ocupado = false;
    }
  }

  /// Resultado da partida no app (ativo revelado, pontos, gráfico real com os desenhos ✔/✖). O relatório completo fica a um toque.
  Future<void> _abrirResultado() async {
    final f = _fimDados, tela = _ultima;
    if (f == null || tela == null || _resultadoAberto || !mounted) return;
    _resultadoAberto = true;
    final solo = widget.salaId == null;
    if (ResultadoPartida.temAdversario(f)) {
      // duelo: VITÓRIA / EMPATE / DERROTA com lucro, pontos, troféus, adversário e operações; a análise completa fica a um toque
      await Navigator.of(context).push(MaterialPageRoute(
        builder: (ctx) => ResultadoPartidaTela(
          r: ResultadoPartida.de(f, tela),
          continuar: () => Navigator.of(ctx).pop(),
          fim: f,
          tela: tela,
        ),
      ));
      _resultadoAberto = false;
      if (mounted) _mostrarFimModal();
      return;
    }
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (ctx) => RelatorioTela(
        fim: f,
        tela: tela,
        aoCompleto: _abrirRelatorio,
        rotuloAcao: solo ? 'Jogar de novo' : 'Voltar ao Trade Battle',
        acao: () {
          Navigator.of(ctx).pop();
          if (solo) {
            Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, corrida: widget.corrida)));
          } else {
            Navigator.of(context).maybePop();
          }
        },
      ),
    ));
    _resultadoAberto = false;
    if (mounted) _mostrarFimModal();
  }

  bool _modalFim = false;
  final _inc = EstadoIncremental(); // consulta incremental: só o que mudou vem do servidor

  /// Fim da partida: um pop-up que prende a tela (não fecha tocando fora nem no voltar). Só dois caminhos: jogar novamente ou voltar ao menu.
  Future<void> _mostrarFimModal() async {
    if (_modalFim || !mounted) return;
    _modalFim = true;
    final solo = widget.salaId == null;
    await mostrarFimDePartida(context, jogarNovamente: () => _jogarNovamente(solo), voltarAoMenu: () => Navigator.of(context).maybePop());
    _modalFim = false;
  }

  /// Solo: outra partida de treino. Online: volta a procurar adversário (a busca abre na hora, como no BATALHAR).
  void _jogarNovamente(bool solo) {
    if (!mounted) return;
    final corrida = solo ? widget.corrida : 'rapida'; // online: só existe a partida de 15 minutos
    if (solo) {
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, corrida: corrida)));
      return;
    }
    Route<void> partida(String id) => MaterialPageRoute<void>(builder: (_) => PartidaTela(api: widget.api, salaId: id));
    Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
        builder: (_) => BuscaTela(api: widget.api, rota: '/trade/fila', titulo: 'Trade Battle · Online', confronto: (id) => '/trade/salas/$id/confronto', abrir: partida, entrar: () => widget.api.post('/trade/fila', {'corrida': corrida}))));
  }

  Future<void> _abrirRelatorio() async {
    if (_pid == null || _relatorioAberto) return;
    String html;
    try {
      html = (await widget.api.get('$_base/relatorio'))['html']?.toString() ?? '';
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      return;
    }
    if (!mounted || html.isEmpty) return;
    _relatorioAberto = true;
    await showDialog<void>(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(10),
        child: Stack(
          children: [
            Container(
              height: MediaQuery.of(ctx).size.height * 0.86,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: const Color(0xFF5C9AFF), width: 2),
                gradient: const RadialGradient(
                  center: Alignment.topCenter,
                  radius: 1.2,
                  colors: [Color(0xFF2A579E), Color(0xFF122E58), Color(0xFF0D0A33)],
                  stops: [0, 0.45, 1],
                ),
                boxShadow: const [BoxShadow(color: Color(0x8C5C9AFF), blurRadius: 30)],
              ),
              child: ClipRRect(borderRadius: BorderRadius.circular(20), child: RelatorioView(html).widget()),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: Material(
                color: const Color(0xFF2F6FD6),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: const BorderSide(color: Color(0xFF9CBFFF), width: 2)),
                child: IconButton(
                  tooltip: 'Fechar',
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => Navigator.of(ctx).pop(),
                ),
              ),
            ),
          ],
        ),
      ),
    );
    _relatorioAberto = false;
  }

  @override
  Widget build(BuildContext context) {
    if (_erroInicio != null) {
      return Scaffold(
        backgroundColor: const Color(0xFF0C192E),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.info_outline, size: 48, color: Color(0xFFFFC93C)),
                const SizedBox(height: 12),
                Text(_erroInicio!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, color: Colors.white)),
                const SizedBox(height: 16),
                FilledButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('Voltar')),
              ],
            ),
          ),
        ),
      );
    }
    return Scaffold(
      backgroundColor: const Color(0xFF081528),
      body: Stack(
        children: [
          Positioned.fill(child: SafeArea(child: _mesa.widget())),
          if (_estrategia && _ultima != null && _pid != null)
            Positioned.fill(
              child: EstrategiaView(
                api: widget.api,
                base: _base,
                args: _ultima!,
                // a resposta da estratégia é a mais nova: qualquer consulta que estava no ar (e voltaria com a fase velha, "análise") é descartada
                aoResponder: (r) {
                  _ordem.novo();
                  _aplicar(r);
                },
                aoVoltar: () => Navigator.of(context).maybePop(),
              ),
            ),
          if (_pid == null) const Positioned.fill(child: _Carregando()),
        ],
      ),
    );
  }
}

/// Espera da partida: candles que sobem e descem em onda enquanto o servidor sorteia o gráfico.
/// Se passar de 6 s, explica que o servidor está acordando (o grátis dorme quando ninguém usa).
class _Carregando extends StatefulWidget {
  const _Carregando();

  @override
  State<_Carregando> createState() => _CarregandoState();
}

class _CarregandoState extends State<_Carregando> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat();
  Timer? _t;
  bool _demorando = false;

  @override
  void initState() {
    super.initState();
    _t = Timer(const Duration(seconds: 6), () {
      if (mounted) setState(() => _demorando = true);
    });
  }

  @override
  void dispose() {
    _c.dispose();
    _t?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const cores = [Color(0xFF26D07C), Color(0xFFFF4D6D)];
    return ColoredBox(
      color: const Color(0xF2081528),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 70,
              child: AnimatedBuilder(
                animation: _c,
                builder: (ctx, _) => Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    for (var i = 0; i < 7; i++) ...[
                      if (i > 0) const SizedBox(width: 6),
                      Builder(builder: (ctx) {
                        final f = (sin((_c.value * 2 * pi) - i * 0.8) + 1) / 2;
                        return Container(
                          width: 11,
                          height: 18 + 50 * f,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(3),
                            color: cores[i % 2],
                            boxShadow: [BoxShadow(color: cores[i % 2].withValues(alpha: 0.5), blurRadius: 8)],
                          ),
                        );
                      }),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            const Text('Preparando o gráfico…', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
            const SizedBox(height: 6),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 400),
              child: Text(
                _demorando ? 'O servidor está acordando. Na primeira partida do dia\npode levar até 1 minuto.' : 'Sorteando um gráfico real da B3.',
                key: ValueKey(_demorando),
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 13.5, height: 1.35, color: Color(0xFFC8D6EE)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
