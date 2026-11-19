import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'api.dart';
import 'cabecalho.dart';
import 'compra.dart';

/// Tela da Carteira no visual do jogo: topo com a ficha do jogador, patrimônio, Comprar/Vender, abas por classe e os ativos em cartões.
/// Dados do servidor (`GET /carteira`).
class CarteiraTela extends StatefulWidget {
  const CarteiraTela({super.key, required this.api});
  final Api api;

  @override
  State<CarteiraTela> createState() => _CarteiraTelaState();
}

/// Abas: (chave da classe no servidor, rótulo, ícone). `null` = todos os ativos.
const _abas = <(String?, String, String)>[
  (null, 'Todos', 'assets/carteira/valor.webp'),
  ('acao', 'Ações', 'assets/carteira/acoes.webp'),
  ('fii', 'FIIs', ''),
  ('cripto', 'Cripto', 'assets/carteira/cripto.webp'),
];

const _ordens = ['Maior valor', 'Maior alta', 'Maior queda'];

class _CarteiraTelaState extends State<CarteiraTela> {
  Map<String, dynamic>? _cart;
  String? _erro;
  bool _carregando = true;
  String? _aba;
  String _ordem = _ordens.first;
  final _apelido = TextEditingController();
  bool _aceito = false;
  bool _enviando = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  @override
  void dispose() {
    _apelido.dispose();
    super.dispose();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final r = await widget.api.get('/carteira');
      setState(() => _cart = r);
    } catch (e) {
      setState(() => _erro = 'Não consegui carregar a sua carteira agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  Future<void> _comecar() async {
    setState(() => _enviando = true);
    try {
      await widget.api.post('/carteira/comecar', {'apelido': _apelido.text.trim(), 'aceito': _aceito});
      await _carregar();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _abrirCompra(String lado) async {
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => CompraTela(api: widget.api, ladoInicial: lado)),
    );
    if (ok == true) _carregar();
  }

  List<double> get _serie => ((_cart?['serie'] as List?) ?? const [])
      .whereType<Map>()
      .map((x) => ((x['v'] as num?) ?? 0).toDouble())
      .toList();

  Color get _corSerie {
    final s = _serie;
    return s.length < 2 || s.last >= s.first ? const Color(0xFF6BE58A) : const Color(0xFFFF6B7A);
  }

  Widget _missao(ThemeData tema) {
    final m = _cart?['missao'] as Map?;
    return _cartao(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Image.asset('assets/carteira/trofeu.webp', width: 28, height: 28),
              const SizedBox(width: 8),
              Text('Minhas Missões', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
            ],
          ),
          const SizedBox(height: 10),
          if (m == null)
            Text('Tudo em dia! Nenhuma missão pendente agora.', style: tema.textTheme.bodyMedium)
          else ...[
            Text('${m['nome'] ?? ''}', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text(
              '${_inteiro(m['progresso'])} / ${_inteiro(m['meta'])}',
              style: tema.textTheme.bodySmall,
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (((m['progresso'] as num?) ?? 0) / (((m['meta'] as num?) ?? 1) == 0 ? 1 : ((m['meta'] as num?) ?? 1))).clamp(0, 1).toDouble(),
                minHeight: 8,
                color: const Color(0xFFFFD76A),
                backgroundColor: Colors.white12,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Recompensa: ${_recompensa((m['recompensa'] as Map?) ?? {})}',
              style: const TextStyle(color: Color(0xFFFFD76A), fontWeight: FontWeight.w800),
            ),
          ],
        ],
      ),
    );
  }

  String _inteiro(Object? v) => v is num ? '${v.round()}' : '—';

  String _recompensa(Map r) {
    if (r['tc'] is num) return '+${(r['tc'] as num).round()} TC';
    if (r['xp'] is num) return '+${(r['xp'] as num).round()} XP';
    if (r['capital'] is num) return '+${_moeda(r['capital'])}';
    return '—';
  }

  /// Atalhos do fim da tela. As telas de destino ainda não existem no app novo: por enquanto avisam que estão em breve.
  Widget _atalhos(ThemeData tema) {
    const itens = [
      ('Conquistas', Icons.workspace_premium),
      ('Histórico', Icons.history),
      ('Gestão', Icons.shield_outlined),
      ('Simulador', Icons.rocket_launch),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Mais da sua carteira', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
        const SizedBox(height: 8),
        for (final (rotulo, icone) in itens) ...[
          InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$rotulo: em breve'))),
            child: _cartao(
              child: Row(
                children: [
                  Icon(icone, color: const Color(0xFF9AD8FF)),
                  const SizedBox(width: 12),
                  Expanded(child: Text(rotulo, style: tema.textTheme.titleSmall)),
                  const Icon(Icons.chevron_right),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ],
    );
  }

  List<Map<String, dynamic>> get _todas => ((_cart?['posicoes'] as List?) ?? const []).cast<Map<String, dynamic>>();

  int _contar(String? classe) => classe == null ? _todas.length : _todas.where((p) => p['classe'] == classe).length;

  List<Map<String, dynamic>> get _posicoes {
    final lista = _aba == null ? [..._todas] : _todas.where((p) => p['classe'] == _aba).toList();
    num valor(Map<String, dynamic> p) => (p['valor'] as num?) ?? 0;
    num pct(Map<String, dynamic> p) => (p['pct'] as num?) ?? 0;
    switch (_ordem) {
      case 'Maior alta':
        lista.sort((a, b) => pct(b).compareTo(pct(a)));
        break;
      case 'Maior queda':
        lista.sort((a, b) => pct(a).compareTo(pct(b)));
        break;
      default:
        lista.sort((a, b) => valor(b).compareTo(valor(a)));
    }
    return lista;
  }

  /// 1234.5 vira "T$ 1.234,50" (dinheiro virtual do jogo). Sem valor, mostra um traço.
  String _moeda(Object? v) {
    if (v is! num) return '—';
    final neg = v < 0;
    final cents = (v.abs() * 100).round();
    final inteiro = (cents ~/ 100).toString();
    final centavos = (cents % 100).toString().padLeft(2, '0');
    final buf = StringBuffer();
    for (var i = 0; i < inteiro.length; i++) {
      if (i > 0 && (inteiro.length - i) % 3 == 0) buf.write('.');
      buf.write(inteiro[i]);
    }
    return '${neg ? '-' : ''}T\$ $buf,$centavos';
  }

  /// 0.1234 vira "+12,34%".
  String _percentual(Object? v) {
    if (v is! num) return '—';
    final p = v * 100;
    final sinal = p > 0 ? '+' : '';
    return '$sinal${p.toStringAsFixed(2).replaceAll('.', ',')}%';
  }

  /// Quantidade: sem casas decimais se for inteira.
  String _quantidade(Object? v) {
    if (v is! num) return '—';
    final inteiro = v == v.roundToDouble();
    return inteiro ? v.toInt().toString() : v.toStringAsFixed(4).replaceAll('.', ',');
  }

  Color _corClasse(String? classe) {
    switch (classe) {
      case 'cripto':
        return const Color(0xFFF5B841);
      case 'acao':
        return const Color(0xFF3D8BFF);
      case 'fii':
        return const Color(0xFF3DDC97);
      default:
        return const Color(0xFF8B7CFF);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final pat = (_cart?['patrimonio'] as num?)?.toDouble();
    final caixa = _cart?['disponivel'];
    final investido = _cart?['investido'];
    final rent = _cart?['rent_nao_realizada'];
    final comecou = _cart?['comecou'] == true;
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(title: const Text('Carteira'), backgroundColor: Colors.transparent, elevation: 0),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/carteira/fundo_carteira.png', fit: BoxFit.cover, alignment: Alignment.topCenter),
          Container(color: const Color(0xB30B0930)),
          SafeArea(
            child: RefreshIndicator(
              onRefresh: _carregar,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_carregando && _cart == null)
                    const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
                  else if (_erro != null && _cart == null) ...[
                    Text(_erro!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
                    const SizedBox(height: 8),
                    OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
                  ] else ...[
                    Cabecalho(api: widget.api),
                    const SizedBox(height: 12),
                    _cartao(
                      child: Row(
                        children: [
                          Image.asset('assets/carteira/carteira.webp', width: 56, height: 56),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Carteira', style: tema.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
                                Text('Seus ativos, seu poder!', style: tema.textTheme.bodySmall),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0B0930),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFF3D4BCE)),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text('Valor total', style: tema.textTheme.labelSmall),
                                Text(_moeda(pat), style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900)),
                                if (_cart?['var_dia'] is num)
                                  Text(
                                    '${_percentual(_cart?['var_dia'] / 100)} (último fechamento)',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w800,
                                      color: ((_cart?['var_dia'] as num) >= 0) ? const Color(0xFF6BE58A) : const Color(0xFFFF6B7A),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    if (_serie.length >= 2) ...[
                      _cartao(
                        child: SizedBox(
                          height: 70,
                          width: double.infinity,
                          child: CustomPaint(painter: _SparklinePainter(_serie, _corSerie)),
                        ),
                      ),
                      const SizedBox(height: 10),
                    ],
                    Row(
                      children: [
                        Expanded(child: _mini(tema, 'Disponível', _moeda(caixa))),
                        const SizedBox(width: 8),
                        Expanded(child: _mini(tema, 'Investido', _moeda(investido))),
                        const SizedBox(width: 8),
                        Expanded(child: _mini(tema, 'Resultado', _percentual(rent), cor: (rent is num && rent < 0) ? const Color(0xFFFF6B7A) : const Color(0xFF6BE58A))),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (!comecou)
                      _comecarCartao(tema)
                    else
                      Row(
                        children: [
                          Expanded(
                            child: FilledButton.icon(
                              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF4CC26B), minimumSize: const Size.fromHeight(56)),
                              onPressed: () => _abrirCompra('C'),
                              icon: const Icon(Icons.add_shopping_cart),
                              label: const Text('Comprar', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: FilledButton.icon(
                              style: FilledButton.styleFrom(backgroundColor: const Color(0xFFE0524F), minimumSize: const Size.fromHeight(56)),
                              onPressed: () => _abrirCompra('V'),
                              icon: const Icon(Icons.trending_down),
                              label: const Text('Vender', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                            ),
                          ),
                        ],
                      ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        for (final (i, (chave, rotulo, icone)) in _abas.indexed) ...[
                          if (i > 0) const SizedBox(width: 8),
                          Expanded(child: _aba_tile(tema, chave, rotulo, icone, _contar(chave))),
                        ],
                      ],
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Expanded(
                          child: Container(
                            height: 48,
                            alignment: Alignment.centerLeft,
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            decoration: _caixa(),
                            child: Text('≡  Meus Ativos', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Container(
                            height: 48,
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            decoration: _caixa(),
                            child: DropdownButtonHideUnderline(
                              child: DropdownButton<String>(
                                value: _ordem,
                                isExpanded: true,
                                dropdownColor: const Color(0xFF16134A),
                                items: [for (final o in _ordens) DropdownMenuItem(value: o, child: Text(o))],
                                onChanged: (v) => setState(() => _ordem = v ?? _ordem),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (_posicoes.isEmpty)
                      _cartao(
                        child: Text(
                          _aba == null
                              ? 'Você ainda não tem posições. Compre um ativo para ele aparecer aqui.'
                              : 'Nenhuma posição nesta aba.',
                          style: tema.textTheme.bodyMedium,
                        ),
                      )
                    else
                      GridView.count(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        crossAxisCount: 3,
                        crossAxisSpacing: 8,
                        mainAxisSpacing: 8,
                        childAspectRatio: 0.68,
                        children: [for (final p in _posicoes) _ativo(tema, p)],
                      ),
                  ],
                  const SizedBox(height: 14),
                  _missao(tema),
                  const SizedBox(height: 14),
                  _atalhos(tema),
                  const SizedBox(height: 24),
                  Text(
                    'Jogo educativo. Sem recomendação de compra ou venda.',
                    style: tema.textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Aba com contador: o ícone da classe e o número de ativos no canto.
  Widget _aba_tile(ThemeData tema, String? chave, String rotulo, String icone, int n) {
    final selecionada = _aba == chave;
    return GestureDetector(
      onTap: () => setState(() => _aba = chave),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            height: 84,
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: selecionada ? const Color(0xFF4B2FD6) : const Color(0xFF16134A),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: selecionada ? const Color(0xFFB59BFF) : const Color(0xFF3D4BCE), width: 1.5),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icone.isNotEmpty)
                  Image.asset(icone, height: 34, width: 34, fit: BoxFit.contain)
                else
                  const Icon(Icons.apartment, size: 30, color: Color(0xFF9AD8FF)),
                const SizedBox(height: 4),
                Text(rotulo, style: tema.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800), textAlign: TextAlign.center),
              ],
            ),
          ),
          Positioned(
            left: -4,
            top: -6,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: chave == null ? const Color(0xFFF5B841) : const Color(0xFF6B5CFF),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text('$n', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 12, color: Colors.white)),
            ),
          ),
        ],
      ),
    );
  }

  /// Cartão de um ativo: letra da sigla, nome, quantidade, valor, variação e peso na carteira.
  Widget _ativo(ThemeData tema, Map<String, dynamic> p) {
    final cor = _corClasse(p['classe'] as String?);
    final rotulo = (p['nome'] as String?) ?? (p['id'] as String?) ?? '—';
    final partes = rotulo.split(' · ');
    final nome = partes.length == 2 ? partes[0] : rotulo;
    final sigla = partes.length == 2 ? partes[1] : (p['id'] as String?) ?? '';
    final valor = (p['valor'] as num?)?.toDouble() ?? 0;
    final pct = p['pct'] as num?;
    final patrimonio = (_cart?['patrimonio'] as num?)?.toDouble() ?? 0;
    final peso = patrimonio > 0 ? valor / patrimonio : 0.0;
    final corPct = (pct ?? 0) >= 0 ? const Color(0xFF6BE58A) : const Color(0xFFFF6B7A);
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF28245C), Color(0xFF16134A)],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cor, width: 1.2),
      ),
      child: Column(
        children: [
          Container(
            width: 44,
            height: 44,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: cor.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: cor),
            ),
            child: (p['logo'] is String)
                ? Padding(
                    padding: const EdgeInsets.all(4),
                    child: Image.asset(
                      'assets/logos/${p['logo']}',
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => _sigla(cor, sigla),
                    ),
                  )
                : _sigla(cor, sigla),
          ),
          const SizedBox(height: 6),
          Text(sigla, style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900), overflow: TextOverflow.ellipsis),
          Text(nome, style: tema.textTheme.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(8)),
            child: Text('${_quantidade(p['qtd'])} un.', style: const TextStyle(fontSize: 11)),
          ),
          const SizedBox(height: 4),
          Text(_moeda(valor), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 13)),
          Text(_percentual(pct), style: TextStyle(color: corPct, fontWeight: FontWeight.w800, fontSize: 12)),
          const Spacer(),
          Row(
            children: [
              const Text('Peso', style: TextStyle(fontSize: 10)),
              const SizedBox(width: 4),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(value: peso.clamp(0, 1).toDouble(), minHeight: 5, color: cor, backgroundColor: Colors.white12),
                ),
              ),
              const SizedBox(width: 4),
              Text('${(peso * 100).round()}%', style: const TextStyle(fontSize: 10)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _sigla(Color cor, String sigla) => Text(
        sigla.isEmpty ? '?' : sigla.substring(0, sigla.length < 3 ? sigla.length : 3),
        style: TextStyle(color: cor, fontWeight: FontWeight.w900, fontSize: 12),
      );

  Widget _mini(ThemeData tema, String rotulo, String valor, {Color? cor}) {
    return _cartao(
      child: Column(
        children: [
          Text(rotulo, style: tema.textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(valor, style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900, color: cor)),
        ],
      ),
    );
  }

  BoxDecoration _caixa() => BoxDecoration(
        color: const Color(0xFF16134A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF3D4BCE)),
      );

  Widget _comecarCartao(ThemeData tema) {
    return _cartao(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Comece a sua carteira', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 6),
          Text(
            'Monte sua carteira com ativos da bolsa. Escolha um apelido público: ele aparece no ranking, com o seu retorno em %.',
            style: tema.textTheme.bodySmall,
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _apelido,
            maxLength: 20,
            decoration: const InputDecoration(labelText: 'Apelido público (ex.: investidor_sp)'),
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _aceito,
            onChanged: (v) => setState(() => _aceito = v ?? false),
            title: const Text(
              'Entendo que meu apelido e meu retorno em % aparecem no ranking. Valores em reais nunca aparecem. É uma simulação educacional, sem dinheiro real.',
              style: TextStyle(fontSize: 12),
            ),
          ),
          FilledButton(
            onPressed: _enviando ? null : _comecar,
            child: const Text('Participar'),
          ),
        ],
      ),
    );
  }

  Widget _cartao({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF28245C), Color(0xFF16134A)],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF7A5CFF), width: 1.5),
      ),
      child: child,
    );
  }
}

/// Linha do patrimônio ao longo dos fechamentos (verde se subiu no período, vermelha se caiu).
class _SparklinePainter extends CustomPainter {
  _SparklinePainter(this.valores, this.cor);
  final List<double> valores;
  final Color cor;

  @override
  void paint(Canvas canvas, Size size) {
    if (valores.length < 2) return;
    final minV = valores.reduce((a, b) => a < b ? a : b);
    final maxV = valores.reduce((a, b) => a > b ? a : b);
    final faixa = (maxV - minV).abs() < 1e-9 ? 1.0 : maxV - minV;
    final caminho = ui.Path();
    for (var i = 0; i < valores.length; i++) {
      final x = size.width * i / (valores.length - 1);
      final y = size.height - (valores[i] - minV) / faixa * size.height;
      if (i == 0) {
        caminho.moveTo(x, y);
      } else {
        caminho.lineTo(x, y);
      }
    }
    canvas.drawPath(
      caminho,
      ui.Paint()
        ..color = cor
        ..style = ui.PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = ui.StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter antigo) => antigo.valores != valores || antigo.cor != cor;
}

