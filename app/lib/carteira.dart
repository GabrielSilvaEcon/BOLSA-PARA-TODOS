import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'api.dart';
import 'carteira_extra.dart';
import 'compra.dart';
import 'missoes.dart';
import 'navegacao.dart';
import 'ranking.dart';

/// Carteira igual à do app antigo (carteira_game.py + carteira_visual.py), com as mesmas medidas e cores:
///   1. cartão "Carteira" com o valor total e a variação desde o último fechamento
///   2. Disponível · Investido · Resultado
///   3. Comprar (verde) e Vender (vermelho)
///   4. abas por categoria com o número de ativos (a fileira rola de lado)
///   5. "Meus Ativos" + ordenação
///   6. grade de cartões dos ativos (logo, código, nome, quantidade, valor, resultado e peso), com o desenho de fundo de cada categoria
///   7. Ranking e Minhas Missões lado a lado, e os atalhos "Mais da sua carteira"
/// Dados do servidor (`GET /carteira`). O cabeçalho (nível, moedas, ranking, sino) é o fixo do app.
class CarteiraTela extends StatefulWidget {
  const CarteiraTela({super.key, required this.api});
  final Api api;

  @override
  State<CarteiraTela> createState() => _CarteiraTelaState();
}

// ------------------------------------------------------------------ cores e textos do app antigo
const _branco = Color(0xFFF4F6FF);
const _lila = Color(0xFFC2D5F2);
const _verde = Color(0xFF3DDC97);
const _vermelho = Color(0xFFFF5B6E);

/// Cor de cada categoria (a borda e o desenho do cartão).
const _corClasse = {
  'acao': Color(0xFF3DA9FF),
  'fii': Color(0xFF2EE5D0),
  'etf': Color(0xFF6B99FF),
  'cripto': Color(0xFFFFB020),
  'fundo': Color(0xFF3DDC6A),
  'rf': Color(0xFF8BA6FF),
};

/// Unidade da quantidade por categoria.
const _unidade = {'acao': 'ações', 'fii': 'cotas', 'etf': 'cotas', 'fundo': 'cotas', 'rf': 'títulos', 'cripto': 'un.'};

/// Abas: (classe, rótulo, ícone). Classe nula = todos.
const _abas = <(String?, String, String)>[
  (null, 'Todos', 'assets/carteira/valor.webp'),
  ('acao', 'Ações', 'assets/carteira/acoes.webp'),
  ('fii', 'FIIs', '🏢'),
  ('cripto', 'Cripto', 'assets/carteira/cripto.webp'),
  ('etf', 'ETFs', 'assets/carteira/etf.webp'),
  ('fundo', 'Fundos', 'assets/carteira/fundo.webp'),
  ('rf', 'Renda fixa', '🏦'),
];

const _ordens = ['Maior valor', 'Melhor resultado', 'Pior resultado', 'Nome'];

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

  void _emBreve(String nome) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$nome: em breve no app novo')));

  // ------------------------------------------------------------------ dados
  List<Map<String, dynamic>> get _todas => ((_cart?['posicoes'] as List?) ?? const []).cast<Map<String, dynamic>>();

  int _contar(String? classe) => classe == null ? _todas.length : _todas.where((p) => p['classe'] == classe).length;

  List<Map<String, dynamic>> get _visiveis {
    final lista = _aba == null ? [..._todas] : _todas.where((p) => p['classe'] == _aba).toList();
    num valor(Map<String, dynamic> p) => (p['valor'] as num?) ?? 0;
    num res(Map<String, dynamic> p) => (p['pct'] as num?) ?? 0;
    switch (_ordem) {
      case 'Melhor resultado':
        lista.sort((a, b) => res(b).compareTo(res(a)));
        break;
      case 'Pior resultado':
        lista.sort((a, b) => res(a).compareTo(res(b)));
        break;
      case 'Nome':
        lista.sort((a, b) => _codigo(a).compareTo(_codigo(b)));
        break;
      default:
        lista.sort((a, b) => valor(b).compareTo(valor(a)));
    }
    return lista;
  }

  String _codigo(Map<String, dynamic> p) {
    final rot = (p['nome'] as String?) ?? (p['id'] as String?) ?? '';
    return rot.contains(' · ') ? rot.split(' · ').last : rot;
  }

  // ------------------------------------------------------------------ formatos (iguais aos do app antigo)
  /// "T$ 1.234,56"; com `semCentavos`, "T$ 1.234".
  String _moeda(Object? v, {bool semCentavos = false}) {
    if (v is! num) return '—';
    final neg = v < 0;
    final cents = (v.abs() * 100).round();
    final inteiro = (cents ~/ 100).toString();
    final buf = StringBuffer();
    for (var i = 0; i < inteiro.length; i++) {
      if (i > 0 && (inteiro.length - i) % 3 == 0) buf.write('.');
      buf.write(inteiro[i]);
    }
    final centavos = semCentavos ? '' : ',${(cents % 100).toString().padLeft(2, '0')}';
    return '${neg ? '−' : ''}T\$ $buf$centavos';
  }

  /// 1.2345 (já em %) vira "+1,23%"; negativo com o sinal de menos tipográfico.
  String _pct(num? v) {
    if (v == null) return '—';
    final s = '${v >= 0 ? '+' : '−'}${v.abs().toStringAsFixed(2).replaceAll('.', ',')}%';
    return s;
  }

  Color _corPct(num? v) => (v == null || v.abs() < 0.005) ? _lila : (v > 0 ? _verde : _vermelho);

  String _seta(num? v) => (v == null || v.abs() < 0.005) ? '' : (v > 0 ? '▲ ' : '▼ ');

  /// Quantidade como no app antigo: inteira sem casas; fracionária com até 4 casas.
  String _qtd(Object? v) {
    if (v is! num) return '—';
    if (v == v.roundToDouble()) return v.toInt().toString();
    var s = v.toStringAsFixed(4);
    s = s.replaceFirst(RegExp(r'0+$'), '');
    return s.replaceAll('.', ',');
  }

  // ------------------------------------------------------------------ tela
  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/carteira/fundo_carteira.png', fit: BoxFit.cover, alignment: Alignment.topCenter),
          Container(color: const Color(0x990B0930)),
          RefreshIndicator(
            onRefresh: _carregar,
            child: LayoutBuilder(
              builder: (context, caixa) {
                final largura = math.min(caixa.maxWidth, 520.0);
                return ListView(
                  padding: EdgeInsets.symmetric(horizontal: math.max(8, (caixa.maxWidth - largura) / 2 + 8), vertical: 10),
                  children: [
                    if (_carregando && _cart == null)
                      const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
                    else if (_erro != null && _cart == null) ...[
                      Text(_erro!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
                      const SizedBox(height: 8),
                      OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
                    ] else
                      ..._conteudo(tema, largura - 16),
                    const SizedBox(height: 16),
                    const Text(
                      'Jogo educativo. Sem recomendação de compra ou venda.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 11, color: _lila),
                    ),
                    const SizedBox(height: 8),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _conteudo(ThemeData tema, double largura) {
    final comecou = _cart?['comecou'] == true;
    final temPos = _todas.isNotEmpty;
    final colunas = largura >= 544 ? 4 : (largura <= 314 ? 2 : 3);
    final visiveis = _visiveis;
    return [
      _cabecalhoCarteira(),
      const SizedBox(height: 8),
      _resumo(),
      const SizedBox(height: 12),
      if (!comecou)
        _comecarCartao(tema)
      else
        Row(
          children: [
            Expanded(child: _botaoJogo('Comprar', Icons.shopping_cart_outlined, const [Color(0xFF38E26B), Color(0xFF12A83C)], const Color(0xFF0B7A2B), () => _abrirCompra('C'))),
            const SizedBox(width: 12),
            Expanded(
              child: _botaoJogo('Vender', Icons.north_east, const [Color(0xFFFF5B5B), Color(0xFFD61F2C)], const Color(0xFFA0121D), temPos ? () => _abrirCompra('V') : null),
            ),
          ],
        ),
      const SizedBox(height: 10),
      _fileiraAbas(largura),
      const SizedBox(height: 8),
      _barraOrdem(),
      const SizedBox(height: 8),
      if (visiveis.isEmpty)
        _vazio()
      else
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: EdgeInsets.zero,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: colunas,
            crossAxisSpacing: 6,
            mainAxisSpacing: 6,
            mainAxisExtent: 136,
          ),
          itemCount: visiveis.length,
          itemBuilder: (_, i) => _cartaoAtivo(visiveis[i]),
        ),
      const SizedBox(height: 12),
      IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(child: _cartaoRanking()),
            const SizedBox(width: 10),
            Expanded(child: _cartaoMissao()),
          ],
        ),
      ),
      const SizedBox(height: 14),
      _atalhos(),
    ];
  }

  // ---- 1. cartão Carteira
  Widget _cabecalhoCarteira() {
    final pat = _cart?['patrimonio'];
    final varDia = _cart?['var_dia'] as num?;
    final frase = _todas.isNotEmpty ? 'Seus ativos, seu poder!' : 'Monte sua carteira: toque em Comprar!';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1C2070), Color(0xFF0F1240)]),
        border: Border.all(color: const Color(0xFF4A5BD0), width: 1.5),
        boxShadow: const [BoxShadow(color: Color(0x884A5BD0), blurRadius: 16, spreadRadius: -6)],
      ),
      child: Row(
        children: [
          Container(
            width: 50,
            height: 50,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const RadialGradient(colors: [Color(0xFF1E3A7A), Color(0xFF0B1236)]),
              border: Border.all(color: _verde, width: 1.5),
            ),
            child: ClipOval(child: Image.asset('assets/carteira/carteira_urso.webp', width: 47, height: 47, fit: BoxFit.cover)),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text('Carteira', style: TextStyle(fontSize: 24, height: 1.1, fontWeight: FontWeight.w900, color: _branco)),
                ),
                Text(frase, maxLines: 2, style: const TextStyle(fontSize: 11.2, fontWeight: FontWeight.w700, color: _lila)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
            decoration: BoxDecoration(
              color: const Color(0xB3080A28),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF3A4FB0)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                const Text('Valor total', style: TextStyle(fontSize: 9.6, fontWeight: FontWeight.w700, color: _lila)),
                Text(_moeda(pat), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: _branco)),
                if (varDia != null)
                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(text: '${_seta(varDia)}${_pct(varDia)} '),
                        const TextSpan(text: '(último fechamento)', style: TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ),
                    style: TextStyle(fontSize: 10.2, fontWeight: FontWeight.w900, color: _corPct(varDia)),
                  )
                else
                  const Text('variação após o 1º fechamento', style: TextStyle(fontSize: 10.2, fontWeight: FontWeight.w700, color: _lila)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---- 2. resumo
  Widget _resumo() {
    final caixa = (_cart?['disponivel'] as num?) ?? 0;
    final inv = (_cart?['investido'] as num?) ?? 0;
    final rent = _cart?['rent_nao_realizada'] as num?;
    final ret = rent == null ? null : rent * 100;
    Widget item(String rotulo, String valor, {Color cor = _branco}) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 5),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1C2366), Color(0xFF121646)]),
              border: Border.all(color: const Color(0xFF2B3A8C)),
            ),
            child: Column(
              children: [
                Text(rotulo, style: const TextStyle(fontSize: 9.6, fontWeight: FontWeight.w700, color: _lila)),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(valor, style: TextStyle(fontSize: 13.4, fontWeight: FontWeight.w900, color: cor)),
                ),
              ],
            ),
          ),
        );
    return Row(
      children: [
        item('Disponível', _moeda(caixa, semCentavos: caixa >= 1000)),
        const SizedBox(width: 6),
        item('Investido', _moeda(inv, semCentavos: inv >= 1000)),
        const SizedBox(width: 6),
        item('Resultado', _pct(ret), cor: ret == null || ret.abs() < 0.005 ? _branco : _corPct(ret)),
      ],
    );
  }

  // ---- 3. Comprar / Vender (botão de jogo: degradê, sombra embaixo e afunda ao tocar)
  Widget _botaoJogo(String rotulo, IconData icone, List<Color> cores, Color base, VoidCallback? acao) {
    return _BotaoJogo(rotulo: rotulo, icone: icone, cores: cores, base: base, acao: acao);
  }

  // ---- 4. abas (4 por tela; a fileira rola de lado)
  Widget _fileiraAbas(double largura) {
    final w = (largura - 18) / 4;
    return SizedBox(
      height: 66,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.only(top: 8),
        clipBehavior: Clip.none,
        itemCount: _abas.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (_, i) {
          final (classe, rotulo, icone) = _abas[i];
          return SizedBox(width: math.max(74, w), child: _aba1(classe, rotulo, icone, _contar(classe)));
        },
      ),
    );
  }

  Widget _aba1(String? classe, String rotulo, String icone, int n) {
    final on = _aba == classe;
    return GestureDetector(
      onTap: () => setState(() => _aba = classe),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            height: 58,
            width: double.infinity,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: on ? const [Color(0xFF2F5FB0), Color(0xFF153C7A)] : const [Color(0xFF1C2366), Color(0xFF121646)],
              ),
              border: Border.all(color: on ? const Color(0xFF6B99FF) : const Color(0xFF2B3A8C), width: on ? 2 : 1.5),
              boxShadow: on ? const [BoxShadow(color: Color(0xFF6B99FF), blurRadius: 14, spreadRadius: -2)] : null,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                icone.startsWith('assets/') ? Image.asset(icone, height: 24, fit: BoxFit.contain) : Text(icone, style: const TextStyle(fontSize: 19, height: 1)),
                const SizedBox(height: 2),
                Text(rotulo, maxLines: 1, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: _branco)),
              ],
            ),
          ),
          Positioned(
            top: -7,
            left: -3,
            child: ClipPath(
              clipper: _Hexagono(),
              child: Container(
                constraints: const BoxConstraints(minWidth: 20),
                height: 20,
                padding: const EdgeInsets.symmetric(horizontal: 4),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: on ? const [Color(0xFFFFE27A), Color(0xFFE9A80C)] : const [Color(0xFF8B8FFF), Color(0xFF4A4FB0)],
                  ),
                ),
                child: Text('$n', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w900, color: on ? const Color(0xFF2A1800) : Colors.white)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- 5. Meus Ativos + ordenar
  Widget _barraOrdem() {
    final caixa = BoxDecoration(
      color: const Color(0xFF121646),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: const Color(0xFF3A4FB0), width: 1.5),
    );
    return Row(
      children: [
        Expanded(
          child: Container(
            height: 38,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            alignment: Alignment.centerLeft,
            decoration: caixa,
            child: const Text('☰ Meus Ativos', style: TextStyle(fontSize: 13.8, fontWeight: FontWeight.w900, color: _branco)),
          ),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: Container(
            height: 38,
            padding: const EdgeInsets.symmetric(horizontal: 10),
            decoration: caixa,
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _ordem,
                isExpanded: true,
                dropdownColor: const Color(0xFF121646),
                iconEnabledColor: _branco,
                style: const TextStyle(fontSize: 13.8, color: _branco),
                items: [for (final o in _ordens) DropdownMenuItem(value: o, child: Text(o))],
                onChanged: (v) => setState(() => _ordem = v ?? _ordem),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _vazio() {
    final rotulo = _abas.firstWhere((a) => a.$1 == _aba).$2;
    final texto = _aba == null ? 'Nenhum ativo ainda. Todo o seu capital está disponível: toque em Comprar para começar.' : 'Você ainda não tem $rotulo. Toque em Comprar para escolher.';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF3A4FB0), width: 1.5),
      ),
      child: Text(texto, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: _lila)),
    );
  }

  // ---- 6. cartão de um ativo
  Widget _cartaoAtivo(Map<String, dynamic> p) {
    final classe = (p['classe'] as String?) ?? 'acao';
    final cor = _corClasse[classe] ?? const Color(0xFF6CA3FF);
    final rot = (p['nome'] as String?) ?? (p['id'] as String?) ?? '—';
    final codigo = rot.contains(' · ') ? rot.split(' · ').last : rot;
    final nome = rot.contains(' · ') ? rot.split(' · ').first : (classe == 'rf' ? 'título de renda fixa' : '');
    final res = p['pct'] is num ? (p['pct'] as num) * 100 : null;
    final pat = (_cart?['patrimonio'] as num?)?.toDouble() ?? 0;
    final valor = (p['valor'] as num?)?.toDouble() ?? 0;
    final peso = pat > 0 ? (valor / pat * 100).clamp(0, 100).toDouble() : 0.0;
    final fundoTopo = Color.lerp(const Color(0xFF141A5A), cor, 0.26)!;
    final logo = p['logo'];
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        gradient: LinearGradient(begin: Alignment.topCenter, end: const Alignment(0, 0.5), colors: [fundoTopo, const Color(0xFF0B0E36)]),
        border: Border.all(color: cor, width: 1.5),
        boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.55), blurRadius: 10, spreadRadius: -4)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10.5),
        child: Stack(
          children: [
            Positioned.fill(child: CustomPaint(painter: _FundoCarta(classe, cor))),
            Padding(
              padding: const EdgeInsets.all(4),
              child: Column(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    margin: const EdgeInsets.only(top: 1, bottom: 2),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: const Color(0x8C080824),
                      borderRadius: BorderRadius.circular(9),
                      border: Border.all(color: cor.withValues(alpha: 0.6)),
                      boxShadow: const [BoxShadow(color: Color(0x80000000), blurRadius: 4, offset: Offset(0, 2))],
                    ),
                    child: logo is String ? Image.asset('assets/logos/$logo', width: 24, height: 24, fit: BoxFit.contain, errorBuilder: (_, __, ___) => _iconeClasse(classe)) : _iconeClasse(classe),
                  ),
                  Text(codigo,
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.8, height: 1.1, fontWeight: FontWeight.w900, color: _branco, shadows: [Shadow(blurRadius: 3)])),
                  Text(nome, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 9, height: 1.15, fontWeight: FontWeight.w700, color: _lila)),
                  Container(
                    margin: const EdgeInsets.only(top: 2, bottom: 1),
                    padding: const EdgeInsets.symmetric(horizontal: 6),
                    decoration: BoxDecoration(color: const Color(0x66000000), borderRadius: BorderRadius.circular(99)),
                    child: Text('${_qtd(p['qtd'])} ${_unidade[classe] ?? 'un.'}', maxLines: 1, style: const TextStyle(fontSize: 8.6, fontWeight: FontWeight.w700, color: _lila)),
                  ),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(_moeda(valor), style: const TextStyle(fontSize: 11.8, height: 1.2, fontWeight: FontWeight.w900, color: _branco, shadows: [Shadow(blurRadius: 3)])),
                  ),
                  Text('${_seta(res)}${_pct(res)}', style: TextStyle(fontSize: 10.6, height: 1.1, fontWeight: FontWeight.w900, color: _corPct(res))),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(color: const Color(0x73000000), borderRadius: BorderRadius.circular(6)),
                    child: Row(
                      children: [
                        const Text('Peso', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, color: _lila)),
                        const SizedBox(width: 3),
                        Expanded(
                          child: Container(
                            height: 4,
                            alignment: Alignment.centerLeft,
                            decoration: BoxDecoration(color: const Color(0x24FFFFFF), borderRadius: BorderRadius.circular(99)),
                            child: FractionallySizedBox(
                              widthFactor: peso / 100,
                              child: Container(
                                decoration: BoxDecoration(
                                  color: cor,
                                  borderRadius: BorderRadius.circular(99),
                                  boxShadow: [BoxShadow(color: cor, blurRadius: 6)],
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 3),
                        Text('${peso.round()}%', style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w800, color: _lila)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _iconeClasse(String classe) {
    const emo = {'acao': '📈', 'fii': '🏢', 'etf': '🧺', 'cripto': '🪙', 'fundo': '💼', 'rf': '🏦'};
    return Text(emo[classe] ?? '•', style: const TextStyle(fontSize: 17));
  }

  // ---- 7. Ranking e Missões (cartões do app antigo)
  BoxDecoration get _cvCard => BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment(0.6, 1), colors: [Color(0xFF10204A), Color(0xFF0A1433)]),
        border: Border.all(color: const Color(0xFF2B4A8C)),
        boxShadow: const [BoxShadow(color: Color(0x73020617), blurRadius: 22, offset: Offset(0, 8))],
      );

  Widget _tituloCartao(String titulo) => Row(
        children: [
          Image.asset('assets/carteira/trofeu.webp', width: 24, height: 24),
          const SizedBox(width: 6),
          Expanded(child: Text(titulo, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: _branco))),
        ],
      );

  Widget _link(String texto, VoidCallback acao) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: GestureDetector(
          onTap: acao,
          child: Text(texto, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: Color(0xFF9DB8FF))),
        ),
      );

  Widget _cartaoRanking() {
    final pos = _cart?['ranking'];
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _cvCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _tituloCartao('Ranking'),
          const SizedBox(height: 10),
          if (pos is num)
            Text('${pos.toInt()}º', style: const TextStyle(fontSize: 30, height: 1, fontWeight: FontWeight.w900, color: _branco))
          else
            const Text('Você entra no ranking no próximo fechamento.', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: _lila)),
          const Spacer(),
          _link('Ver classificação →', () {
            rankingPedido.value = 'carteira';
            Navigator.of(context).popUntil((r) => r.isFirst);
            abrirAba(3);
          }),
        ],
      ),
    );
  }

  Widget _cartaoMissao() {
    final m = _cart?['missao'] as Map?;
    final prog = (m?['progresso'] as num?) ?? 0;
    final meta = ((m?['meta'] as num?) ?? 1) == 0 ? 1 : ((m?['meta'] as num?) ?? 1);
    final rec = (m?['recompensa'] as Map?) ?? const {};
    String premio() {
      if (rec['tc'] is num) return '+${(rec['tc'] as num).round()} TC';
      if (rec['xp'] is num) return '+${(rec['xp'] as num).round()} XP';
      if (rec['capital'] is num) return '+${_moeda(rec['capital'], semCentavos: true)}';
      return '';
    }

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _cvCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _tituloCartao('Minhas Missões'),
          const SizedBox(height: 10),
          if (m == null) ...[
            const Text('Tudo em dia!', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: _branco)),
            const Text('Nenhuma missão pendente agora.', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: _lila)),
          ] else ...[
            Text('${m['nome'] ?? ''}', maxLines: 2, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: _branco)),
            const SizedBox(height: 2),
            Text('${prog.round()} / ${meta.round()}', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: _lila)),
            const SizedBox(height: 5),
            Container(
              height: 7,
              alignment: Alignment.centerLeft,
              decoration: BoxDecoration(color: const Color(0x24FFFFFF), borderRadius: BorderRadius.circular(99)),
              child: FractionallySizedBox(
                widthFactor: (prog / meta).clamp(0, 1).toDouble(),
                child: Container(decoration: BoxDecoration(color: const Color(0xFFFFD76A), borderRadius: BorderRadius.circular(99))),
              ),
            ),
            if (premio().isNotEmpty) ...[
              const SizedBox(height: 5),
              Text(premio(), style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w900, color: Color(0xFFFFD76A))),
            ],
          ],
          const Spacer(),
          _link('Ver todas as missões →', () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MissoesTela(api: widget.api)))),
        ],
      ),
    );
  }

  Widget _atalhos() {
    const itens = [
      ('Conquistas', Icons.workspace_premium),
      ('Histórico', Icons.newspaper),
      ('Gestão', Icons.shield_outlined),
      ('Simulador', Icons.rocket_launch_outlined),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Mais da sua carteira', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: _branco)),
        const SizedBox(height: 8),
        Row(
          children: [
            for (final (i, (rotulo, icone)) in itens.indexed) ...[
              if (i > 0) const SizedBox(width: 6),
              Expanded(
                child: GestureDetector(
                  onTap: () => switch (rotulo) {
                    'Histórico' => Navigator.of(context).push(MaterialPageRoute(builder: (_) => HistoricoCarteiraTela(api: widget.api))),
                    'Conquistas' => Navigator.of(context).push(MaterialPageRoute(builder: (_) => ConquistasCarteiraTela(api: widget.api))),
                    _ => _emBreve(rotulo),
                  },
                  child: Container(
                    height: 70,
                    decoration: _cvCard.copyWith(borderRadius: BorderRadius.circular(16)),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(icone, color: const Color(0xFF9AD8FF), size: 26),
                        const SizedBox(height: 4),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Text(rotulo, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: _branco)),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }

  // ---- começar a carteira (quem ainda não participa)
  Widget _comecarCartao(ThemeData tema) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _cvCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Comece a sua carteira', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: _branco)),
          const SizedBox(height: 6),
          const Text(
            'Monte sua carteira com ativos da bolsa. Escolha um apelido público: ele aparece no ranking, com o seu retorno em %.',
            style: TextStyle(fontSize: 12, color: _lila),
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
          FilledButton(onPressed: _enviando ? null : _comecar, child: const Text('Participar')),
        ],
      ),
    );
  }
}

/// Botão de jogo (Comprar / Vender): degradê de cima para baixo, "degrau" escuro embaixo e afunda ao tocar.
class _BotaoJogo extends StatefulWidget {
  const _BotaoJogo({required this.rotulo, required this.icone, required this.cores, required this.base, required this.acao});
  final String rotulo;
  final IconData icone;
  final List<Color> cores;
  final Color base;
  final VoidCallback? acao;

  @override
  State<_BotaoJogo> createState() => _BotaoJogoState();
}

class _BotaoJogoState extends State<_BotaoJogo> {
  bool _apertado = false;

  @override
  Widget build(BuildContext context) {
    final ativo = widget.acao != null;
    return Opacity(
      opacity: ativo ? 1 : 0.5,
      child: GestureDetector(
        onTapDown: ativo ? (_) => setState(() => _apertado = true) : null,
        onTapCancel: () => setState(() => _apertado = false),
        onTapUp: ativo
            ? (_) {
                setState(() => _apertado = false);
                widget.acao!();
              }
            : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 90),
          height: 58,
          margin: EdgeInsets.only(top: _apertado ? 4 : 0, bottom: _apertado ? 1 : 5),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: widget.cores),
            boxShadow: [
              BoxShadow(color: widget.base, offset: Offset(0, _apertado ? 1 : 5)),
              BoxShadow(color: widget.cores.first.withValues(alpha: 0.38), blurRadius: 20, offset: const Offset(0, 8)),
            ],
          ),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Row(
              children: [
                Icon(widget.icone, color: Colors.white, size: 26),
                const SizedBox(width: 8),
                Text(widget.rotulo, style: const TextStyle(color: Colors.white, fontSize: 21, fontWeight: FontWeight.w900)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Hexágono do número de ativos de cada aba (o mesmo recorte do app antigo).
class _Hexagono extends CustomClipper<ui.Path> {
  @override
  ui.Path getClip(Size s) => ui.Path()
    ..moveTo(s.width * 0.25, 0)
    ..lineTo(s.width * 0.75, 0)
    ..lineTo(s.width, s.height / 2)
    ..lineTo(s.width * 0.75, s.height)
    ..lineTo(s.width * 0.25, s.height)
    ..lineTo(0, s.height / 2)
    ..close();

  @override
  bool shouldReclip(covariant CustomClipper<ui.Path> antigo) => false;
}

/// Desenho de fundo da carta, na cor da categoria (o mesmo do app antigo): velas (ações), prédios (FIIs), cubos (ETFs),
/// rede de blocos (cripto), moedas (fundos) e degraus (renda fixa), com brilho no topo e feixes de luz na diagonal.
/// Desenhado num quadro de 116 × 150, que cobre a carta inteira presa embaixo (como o "slice" do SVG original).
class _FundoCarta extends CustomPainter {
  _FundoCarta(this.classe, this.cor);
  final String classe;
  final Color cor;

  @override
  void paint(Canvas canvas, Size size) {
    // brilho no topo
    final brilho = ui.Paint()..shader = ui.Gradient.radial(Offset(size.width / 2, size.height * 0.12), size.longestSide * 0.7, [cor.withValues(alpha: 0.45), cor.withValues(alpha: 0)]);
    canvas.drawRect(Offset.zero & size, brilho);

    final k = math.max(size.width / 116, size.height / 150);
    canvas.save();
    canvas.translate((size.width - 116 * k) / 2, size.height - 150 * k);
    canvas.scale(k);
    final luz = ui.Paint()..color = const Color(0x0DFFFFFF);
    canvas.drawPath(
        ui.Path()
          ..moveTo(70, 0)
          ..lineTo(116, 0)
          ..lineTo(116, 40)
          ..close(),
        luz);
    canvas.drawPath(
        ui.Path()
          ..moveTo(-10, 60)
          ..lineTo(60, -10)
          ..lineTo(74, -10)
          ..lineTo(4, 60)
          ..close(),
        luz);

    canvas.saveLayer(null, ui.Paint()..color = const Color(0x80000000));
    final traco = ui.Paint()
      ..style = ui.PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = cor.withValues(alpha: 0.55);
    ui.Paint cheio(double a) => ui.Paint()..color = cor.withValues(alpha: a);
    switch (classe) {
      case 'fii':
        for (final (x, y, w) in const [(4.0, 96.0, 22.0), (30.0, 78.0, 26.0), (60.0, 104.0, 18.0), (82.0, 70.0, 24.0)]) {
          final r = Rect.fromLTWH(x, y, w, 150 - y);
          canvas.drawRect(r, cheio(0.16));
          canvas.drawRect(r, traco);
          for (var j = 0; j < math.max(1, (w - 6) ~/ 7); j++) {
            for (var q = 0; q < math.max(1, (150 - y - 10) ~/ 10); q++) {
              canvas.drawRect(Rect.fromLTWH(x + 4 + j * 7, y + 6 + q * 10, 3, 4), cheio(0.5));
            }
          }
        }
        break;
      case 'etf':
        for (final (x, y) in const [(14.0, 112.0), (38.0, 112.0), (62.0, 112.0), (26.0, 98.0), (50.0, 98.0), (74.0, 112.0), (38.0, 84.0)]) {
          canvas.drawPath(
              ui.Path()
                ..moveTo(x, y)
                ..relativeLineTo(12, -7)
                ..relativeLineTo(12, 7)
                ..relativeLineTo(-12, 7)
                ..close(),
              cheio(0.30));
          canvas.drawPath(
              ui.Path()
                ..moveTo(x, y)
                ..relativeLineTo(12, 7)
                ..relativeLineTo(0, 14)
                ..relativeLineTo(-12, -7)
                ..close(),
              cheio(0.18));
          canvas.drawPath(
              ui.Path()
                ..moveTo(x + 24, y)
                ..relativeLineTo(-12, 7)
                ..relativeLineTo(0, 14)
                ..relativeLineTo(12, -7)
                ..close(),
              cheio(0.10));
        }
        break;
      case 'cripto':
        const pts = [Offset(18, 96), Offset(52, 82), Offset(88, 100), Offset(34, 126), Offset(74, 130), Offset(100, 70)];
        for (final (a, b) in const [(0, 1), (1, 2), (0, 3), (3, 4), (4, 2), (2, 5), (1, 4)]) {
          canvas.drawLine(pts[a], pts[b], traco);
        }
        for (final p in pts) {
          final r = RRect.fromRectAndRadius(Rect.fromCenter(center: p, width: 10, height: 10), const Radius.circular(2));
          canvas.drawRRect(r, cheio(0.35));
          canvas.drawRRect(r, traco..strokeWidth = 1);
        }
        break;
      case 'fundo':
        for (final (x, n) in const [(24.0, 5), (52.0, 8), (82.0, 6)]) {
          for (var q = 0; q < n; q++) {
            final r = Rect.fromCenter(center: Offset(x, 140.0 - q * 6), width: 26, height: 9);
            canvas.drawOval(r, cheio(0.22));
            canvas.drawOval(r, traco);
          }
        }
        break;
      case 'rf':
        for (var i = 0; i < 5; i++) {
          final r = RRect.fromRectAndRadius(Rect.fromLTWH(8.0 + i * 20, 136.0 - i * 12, 18, 14.0 + i * 12), const Radius.circular(2));
          canvas.drawRRect(r, cheio(0.12 + i * 0.05));
          canvas.drawRRect(r, traco);
        }
        break;
      default: // ações: velas e linha de alta
        const verm = Color(0xFFFF5B6E);
        for (final (x, y, h, sobe) in const [
          (10.0, 118.0, 16.0, true),
          (24.0, 108.0, 18.0, true),
          (38.0, 114.0, 12.0, false),
          (52.0, 96.0, 20.0, true),
          (66.0, 100.0, 14.0, false),
          (80.0, 84.0, 20.0, true),
          (94.0, 72.0, 22.0, true),
        ]) {
          final c = sobe ? cor : verm;
          canvas.drawLine(Offset(x + 3, y - 6), Offset(x + 3, y + h + 6), ui.Paint()..color = c.withValues(alpha: 0.5));
          canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(x, y, 6, h), const Radius.circular(1)), ui.Paint()..color = c.withValues(alpha: 0.38));
        }
        final linha = ui.Path()..moveTo(4, 128);
        for (final p in const [Offset(30, 112), Offset(50, 116), Offset(72, 92), Offset(96, 74), Offset(112, 60)]) {
          linha.lineTo(p.dx, p.dy);
        }
        canvas.drawPath(
            linha,
            ui.Paint()
              ..style = ui.PaintingStyle.stroke
              ..strokeWidth = 2
              ..color = cor.withValues(alpha: 0.7));
    }
    canvas.restore(); // camada com 50% de opacidade
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _FundoCarta antigo) => antigo.classe != classe || antigo.cor != cor;
}
