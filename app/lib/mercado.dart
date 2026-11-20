import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;

/// Mercado (botão Mercado da Home; a área Analisar do app antigo): Mercado hoje, busca de empresas, tipos de ativo e ações
/// populares. Cada ação abre a AcaoTela com preço, gráfico, resumo em palavras simples, preço justo e indicadores.
/// As contas vêm do servidor (mercado_api.py, as mesmas do app antigo). Leitura educativa, sem recomendação.
class MercadoTela extends StatefulWidget {
  const MercadoTela({super.key, required this.api});
  final Api api;

  @override
  State<MercadoTela> createState() => _MercadoTelaState();
}

const _lilas = Color(0xFFD9D4F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);

String _num(num v, int casas) {
  final s = v.abs().toStringAsFixed(casas);
  final p = s.split('.');
  final b = StringBuffer();
  for (var i = 0; i < p[0].length; i++) {
    if (i > 0 && (p[0].length - i) % 3 == 0) b.write('.');
    b.write(p[0][i]);
  }
  return '${v < 0 ? '-' : ''}$b${casas > 0 ? ',${p[1]}' : ''}';
}

String _brl(Object? v) => v is num ? 'R\$ ${_num(v, 2)}' : '—';
String _pct(Object? v, {bool sinal = false}) => v is num ? '${sinal && v >= 0 ? '+' : ''}${_num(v, 2)}%' : '—';

Color _corFaixa(String? f) => switch (f) { 'bom' => _verde, 'medio' => _ouro, 'ruim' => _vermelho, _ => const Color(0xFF8C86B8) };

BoxDecoration _caixa([Color borda = const Color(0xFF6A4FE6)]) => BoxDecoration(
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: borda, width: 1.6),
      gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xE6231388), Color(0xE6160B5E)]),
      boxShadow: [BoxShadow(color: borda.withValues(alpha: 0.3), blurRadius: 12)],
    );

Widget _titulo(String t, {IconData? ic}) => Padding(
      padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
      child: Row(children: [
        if (ic != null) ...[Icon(ic, color: const Color(0xFFB59BFF), size: 20), const SizedBox(width: 6)],
        Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
      ]),
    );

/// Logo do ativo (ícone do setor) num disco; sem logo, as iniciais.
Widget logoAtivo(Object? logo, String tk, {double tam = 44}) => Container(
      width: tam,
      height: tam,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const RadialGradient(colors: [Color(0xFF3B2A9E), Color(0xFF1B1462)]),
        border: Border.all(color: const Color(0xFF8B6CFF), width: 1.5),
      ),
      alignment: Alignment.center,
      padding: EdgeInsets.all(tam * 0.16),
      child: logo is String && logo.isNotEmpty ? Image.asset('assets/logos/$logo', fit: BoxFit.contain, errorBuilder: (_, __, ___) => _iniciais(tk, tam)) : _iniciais(tk, tam),
    );

Widget _iniciais(String tk, double tam) => Text(tk.length >= 2 ? tk.substring(0, 2) : tk, style: TextStyle(fontSize: tam * 0.32, fontWeight: FontWeight.w900, color: Colors.white));

class _MercadoTelaState extends State<MercadoTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  final _busca = TextEditingController();
  final _foco = FocusNode();
  Timer? _espera;
  List<Map>? _achados;
  bool _buscando = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  @override
  void dispose() {
    _busca.dispose();
    _foco.dispose();
    _espera?.cancel();
    super.dispose();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/mercado');
      if (mounted) {
        setState(() {
          _d = r;
          _erro = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  void _digitou(String t) {
    _espera?.cancel();
    if (t.trim().length < 2) {
      setState(() {
        _achados = null;
        _buscando = false;
      });
      return;
    }
    setState(() => _buscando = true);
    _espera = Timer(const Duration(milliseconds: 350), () async {
      try {
        final r = await widget.api.get('/mercado/busca?texto=${Uri.encodeQueryComponent(t.trim())}');
        if (mounted && _busca.text == t) {
          setState(() {
            _achados = ((r['itens'] as List?) ?? const []).cast<Map>();
            _buscando = false;
          });
        }
      } catch (_) {
        if (mounted) setState(() => _buscando = false);
      }
    });
  }

  void _abrir(Map e) => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AcaoTela(api: widget.api, ticker: '${e['ticker']}', nome: '${e['nome']}', logo: e['logo'])));

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  const Expanded(child: Text('Mercado', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                Entrada(ordem: 0, child: _campoBusca()),
                if (_achados != null || _buscando) Entrada(ordem: 0, child: _resultados()),
                if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
                if (d == null && _erro != null) Padding(padding: const EdgeInsets.all(20), child: Text(_erro!, style: const TextStyle(color: Colors.white))),
                if (d != null) ...[
                  if (((d['hoje'] as List?) ?? const []).isNotEmpty) ...[
                    _titulo('Mercado hoje', ic: Icons.show_chart_rounded),
                    Entrada(ordem: 1, child: _hoje(((d['hoje'] as List?) ?? const []).cast<Map>())),
                  ],
                  _titulo('Explorar por tipo', ic: Icons.explore_rounded),
                  Entrada(ordem: 2, child: _tipos(((d['tipos'] as List?) ?? const []).cast<Map>())),
                  _titulo('Ações populares', ic: Icons.local_fire_department_rounded),
                  for (final (i, e) in ((d['populares'] as List?) ?? const []).cast<Map>().indexed) Entrada(ordem: 3 + i, child: _linhaEmpresa(e)),
                  const SizedBox(height: 14),
                  Text('${d['aviso'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 11.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _campoBusca() => Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          color: const Color(0xE6160B5E),
          border: Border.all(color: const Color(0xFF8B6CFF), width: 1.6),
          boxShadow: const [BoxShadow(color: Color(0x558B6CFF), blurRadius: 14)],
        ),
        child: TextField(
          controller: _busca,
          focusNode: _foco,
          onChanged: _digitou,
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(vertical: 14),
            prefixIcon: const Icon(Icons.search_rounded, color: Color(0xFFB59BFF)),
            suffixIcon: _busca.text.isEmpty
                ? null
                : IconButton(
                    icon: const Icon(Icons.close_rounded, color: _lilas),
                    onPressed: () {
                      _busca.clear();
                      _digitou('');
                    }),
            hintText: 'Busque uma empresa: Petrobras, VALE3, bancos…',
            hintStyle: const TextStyle(color: Color(0xFF9C93D6), fontWeight: FontWeight.w500),
          ),
        ),
      );

  Widget _resultados() {
    final r = _achados ?? const [];
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(6),
      decoration: _caixa(),
      child: _buscando && r.isEmpty
          ? const Padding(padding: EdgeInsets.all(14), child: Center(child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))))
          : r.isEmpty
              ? const Padding(padding: EdgeInsets.all(14), child: Text('Nenhuma empresa encontrada.', style: TextStyle(color: _lilas)))
              : Column(children: [for (final e in r) _linhaEmpresa(e, compacta: true)]),
    );
  }

  Widget _hoje(List<Map> itens) => GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: 2.1,
        children: [
          for (final it in itens)
            Container(
              padding: const EdgeInsets.fromLTRB(12, 8, 10, 8),
              decoration: _caixa(it['var'] is num ? ((it['var'] as num) >= 0 ? _verde : _vermelho).withValues(alpha: 0.8) : const Color(0xFF6A4FE6)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                Text('${it['rotulo']}', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: _lilas)),
                FittedBox(child: Text('${it['valor']}', style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Colors.white))),
                Text(it['nota'] != null ? '${it['nota']}' : _pct(it['var'], sinal: true),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: it['var'] is num ? ((it['var'] as num) >= 0 ? _verde : _vermelho) : _ouro)),
              ]),
            ),
        ],
      );

  static const _iconeTipo = {
    'acoes': (Icons.candlestick_chart_rounded, Color(0xFF8B6CFF)),
    'fundos': (Icons.apartment_rounded, Color(0xFF2BA7C9)),
    'rf': (Icons.account_balance_rounded, Color(0xFF3DDC97)),
    'cripto': (Icons.currency_bitcoin_rounded, Color(0xFFF2B84B)),
    'macro': (Icons.public_rounded, Color(0xFFFF6B8A)),
  };

  Widget _tipos(List<Map> tipos) => Wrap(spacing: 8, runSpacing: 8, children: [
        for (final t in tipos)
          LayoutBuilder(builder: (ctx, c) {
            final (ic, cor) = _iconeTipo['${t['id']}'] ?? (Icons.category_rounded, const Color(0xFF8B6CFF));
            final pronto = t['pronto'] == true;
            final w = (MediaQuery.sizeOf(ctx).width.clamp(0, 720) - 32) / 2;
            return SizedBox(
              width: w,
              child: Pressionavel(
                aoTocar: () => pronto ? _foco.requestFocus() : ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${t['titulo']}: chega na próxima etapa do Mercado.'))),
                child: Opacity(
                  opacity: pronto ? 1 : 0.62,
                  child: Container(
                    height: 92,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(18),
                      gradient: LinearGradient(colors: [Color.lerp(cor, Colors.black, 0.25)!, Color.lerp(cor, const Color(0xFF140A55), 0.7)!]),
                      border: Border.all(color: Color.lerp(cor, Colors.white, 0.35)!, width: 1.4),
                      boxShadow: [BoxShadow(color: cor.withValues(alpha: pronto ? 0.45 : 0.15), blurRadius: 12)],
                    ),
                    child: Row(children: [
                      Icon(ic, color: Colors.white, size: 30),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                          Text('${t['titulo']}', maxLines: 2, style: const TextStyle(fontSize: 14, height: 1.1, fontWeight: FontWeight.w900, color: Colors.white)),
                          const SizedBox(height: 2),
                          Text(pronto ? '${t['descricao']}' : 'Em breve', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11, color: Color(0xEEFFFFFF))),
                        ]),
                      ),
                    ]),
                  ),
                ),
              ),
            );
          }),
      ]);

  Widget _linhaEmpresa(Map e, {bool compacta = false}) => Padding(
        padding: EdgeInsets.only(bottom: compacta ? 2 : 8),
        child: Pressionavel(
          aoTocar: () => _abrir(e),
          child: Container(
            padding: const EdgeInsets.fromLTRB(10, 9, 8, 9),
            decoration: compacta ? null : _caixa(),
            child: Row(children: [
              Hero(tag: 'logo-${e['ticker']}', child: logoAtivo(e['logo'], '${e['ticker']}', tam: compacta ? 38 : 44)),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${e['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
                  Text('${e['ticker']} · ${e['setor'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: _lilas)),
                ]),
              ),
              const Icon(Icons.chevron_right_rounded, color: Colors.white),
            ]),
          ),
        ),
      );
}

/// Uma ação: preço e variação, gráfico (6 meses, 1 ano, 5 anos), resumo em palavras simples, preço justo e indicadores.
class AcaoTela extends StatefulWidget {
  const AcaoTela({super.key, required this.api, required this.ticker, this.nome, this.logo});
  final Api api;
  final String ticker;
  final String? nome;
  final Object? logo;

  @override
  State<AcaoTela> createState() => _AcaoTelaState();
}

class _AcaoTelaState extends State<AcaoTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String _periodo = '1a';
  final Map<String, List<Map>> _series = {};
  String? _aberto; // indicador com a explicação aberta

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _erro = null);
    try {
      final r = await widget.api.get('/mercado/acao/${widget.ticker}');
      if (mounted) {
        setState(() {
          _d = r;
          _series['1a'] = ((r['serie'] as List?) ?? const []).cast<Map>();
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  Future<void> _trocarPeriodo(String p) async {
    setState(() => _periodo = p);
    if (_series.containsKey(p)) return;
    try {
      final r = await widget.api.get('/mercado/acao/${widget.ticker}/historico?periodo=$p');
      if (mounted) setState(() => _series[p] = ((r['serie'] as List?) ?? const []).cast<Map>());
    } catch (_) {
      if (mounted) setState(() => _series[p] = const []);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  Expanded(child: Text(widget.ticker, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                Entrada(ordem: 0, child: _topo(d)),
                if (d == null && _erro == null)
                  const Padding(
                    padding: EdgeInsets.all(36),
                    child: Column(children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 12),
                      Text('Buscando os dados da empresa…', style: TextStyle(color: _lilas)),
                    ]),
                  ),
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
                  const SizedBox(height: 10),
                  Entrada(ordem: 1, child: _grafico()),
                  _titulo('Em palavras simples', ic: Icons.lightbulb_rounded),
                  for (final (i, c) in ((d['resumo'] as List?) ?? const []).cast<Map>().indexed) Entrada(ordem: 2 + i, child: _cartaoResumo(c)),
                  _titulo('Preço justo', ic: Icons.gps_fixed_rounded),
                  Entrada(ordem: 5, child: _precoJusto((d['preco_justo'] as Map?) ?? const {})),
                  _titulo('Indicadores', ic: Icons.analytics_rounded),
                  Entrada(ordem: 6, child: _indicadores(((d['indicadores'] as List?) ?? const []).cast<Map>())),
                  if (((d['alertas'] as List?) ?? const []).isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: _caixa(_ouro),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        const Row(children: [
                          Icon(Icons.info_rounded, color: _ouro, size: 18),
                          SizedBox(width: 6),
                          Text('Sobre os dados', style: TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                        ]),
                        for (final a in (d['alertas'] as List)) Padding(padding: const EdgeInsets.only(top: 4), child: Text('• $a', style: const TextStyle(fontSize: 12, color: _lilas))),
                      ]),
                    ),
                  ],
                  const SizedBox(height: 14),
                  Text('${d['aviso'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 11.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _topo(Map? d) {
    final v = d?['var_dia'];
    final cor = v is num ? (v >= 0 ? _verde : _vermelho) : _lilas;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: _ouro, width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2E1CA0), Color(0xFF140A55)]),
        boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
      ),
      child: Row(children: [
        Hero(tag: 'logo-${widget.ticker}', child: logoAtivo(d?['logo'] ?? widget.logo, widget.ticker, tam: 58)),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${d?['nome'] ?? widget.nome ?? widget.ticker}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white)),
            Text('${widget.ticker}${d?['setor'] != null ? ' · ${d!['setor']}' : ''}', style: const TextStyle(fontSize: 12.5, color: _lilas)),
            const SizedBox(height: 6),
            if (d != null)
              Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: ((d['preco'] as num?) ?? 0).toDouble()),
                  duration: const Duration(milliseconds: 900),
                  curve: Curves.easeOutCubic,
                  builder: (ctx, x, _) => Text(_brl(x), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Colors.white)),
                ),
                const SizedBox(width: 8),
                if (v is num)
                  Container(
                    margin: const EdgeInsets.only(bottom: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: cor.withValues(alpha: 0.18), border: Border.all(color: cor)),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(v >= 0 ? Icons.arrow_drop_up_rounded : Icons.arrow_drop_down_rounded, color: cor, size: 18),
                      Text('${_pct(v.abs())} hoje', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: cor)),
                    ]),
                  ),
              ]),
          ]),
        ),
      ]),
    );
  }

  Widget _grafico() {
    final s = _series[_periodo];
    final pts = [for (final p in s ?? const <Map>[]) ((p['c'] as num?) ?? 0).toDouble()];
    final sobe = pts.length >= 2 && pts.last >= pts.first;
    final cor = sobe ? _verde : _vermelho;
    final varPer = pts.length >= 2 && pts.first > 0 ? (pts.last / pts.first - 1) * 100 : null;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 10),
      decoration: _caixa(),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          for (final (id, rot) in const [('6m', '6 meses'), ('1a', '1 ano'), ('5a', '5 anos')]) ...[
            Pressionavel(
              aoTocar: () => _trocarPeriodo(id),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(999),
                  color: _periodo == id ? const Color(0xFF8B6CFF) : const Color(0x332E1CA0),
                  border: Border.all(color: const Color(0xFF8B6CFF)),
                ),
                child: Text(rot, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white)),
              ),
            ),
            const SizedBox(width: 6),
          ],
          const Spacer(),
          if (varPer != null) Text(_pct(varPer, sinal: true), style: TextStyle(fontWeight: FontWeight.w900, color: cor)),
        ]),
        const SizedBox(height: 10),
        SizedBox(
          height: 170,
          child: s == null
              ? const Center(child: CircularProgressIndicator())
              : pts.length < 2
                  ? const Center(child: Text('Gráfico indisponível agora.', style: TextStyle(color: _lilas)))
                  : TweenAnimationBuilder<double>(
                      key: ValueKey(_periodo),
                      tween: Tween(begin: 0, end: 1),
                      duration: const Duration(milliseconds: 900),
                      curve: Curves.easeOutCubic,
                      builder: (ctx, t, _) => CustomPaint(size: Size.infinite, painter: _Linha(pts, cor, t)),
                    ),
        ),
        if (s != null && s.length >= 2)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Row(children: [
              Text(_data('${s.first['t']}'), style: const TextStyle(fontSize: 11, color: _lilas)),
              const Spacer(),
              Text(_data('${s.last['t']}'), style: const TextStyle(fontSize: 11, color: _lilas)),
            ]),
          ),
      ]),
    );
  }

  String _data(String t) => t.length >= 10 ? '${t.substring(8, 10)}/${t.substring(5, 7)}/${t.substring(0, 4)}' : t;

  static const _iconeResumo = {'preco': Icons.gps_fixed_rounded, 'saude': Icons.favorite_rounded, 'dividendos': Icons.payments_rounded};

  Widget _cartaoResumo(Map c) {
    final cor = _corFaixa('${c['status']}');
    final linhas = ((c['linhas'] as List?) ?? const []).cast<List>();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: _caixa(cor.withValues(alpha: 0.85)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(shape: BoxShape.circle, color: cor.withValues(alpha: 0.2), border: Border.all(color: cor)),
            child: Icon(_iconeResumo['${c['id']}'] ?? Icons.info_rounded, color: cor, size: 19),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${c['titulo']}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
              const SizedBox(height: 3),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: cor.withValues(alpha: 0.2), border: Border.all(color: cor)),
                child: Text('${c['texto']}', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: cor)),
              ),
            ]),
          ),
        ]),
        for (final l in linhas)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Row(children: [
              Expanded(child: Text('${l[0]}', style: const TextStyle(fontSize: 13, color: _lilas))),
              Text(c['id'] == 'preco' ? _brl(l[1]) : (l[1] is num ? 'R\$ ${_num(l[1] as num, 2)}' : '—'), style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Colors.white)),
            ]),
          ),
        if (c['nivel_divida'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Row(children: [
              const Expanded(child: Text('Nível de dívida', style: TextStyle(fontSize: 13, color: _lilas))),
              Text('${c['nivel_divida']}', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Colors.white)),
            ]),
          ),
        if ('${c['nota'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text('${c['nota']}', style: const TextStyle(fontSize: 11.5, color: Color(0xFFB8B0E8)))),
      ]),
    );
  }

  Widget _precoJusto(Map pj) {
    final preco = _d?['preco'];
    Widget metodo(String nome, Map m) {
      final cor = _corFaixa('${m['status']}');
      final margem = m['margem'];
      return Expanded(
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: _caixa(cor.withValues(alpha: 0.85)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(nome, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
            const SizedBox(height: 4),
            FittedBox(child: Text(m['justo'] is num ? _brl(m['justo']) : 'Sem dados', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: m['justo'] is num ? Colors.white : _lilas))),
            if (margem is num) ...[
              const SizedBox(height: 4),
              Text(margem >= 0 ? 'Margem de ${_num(margem, 0)}%' : '${_num(-margem, 0)}% acima', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: cor)),
              const SizedBox(height: 6),
              _BarraMargem(margem: margem.toDouble(), alvo: ((pj['margem_alvo'] as num?) ?? 20).toDouble(), cor: cor),
            ],
            const SizedBox(height: 6),
            Text('${m['aviso'] ?? m['como'] ?? ''}', style: const TextStyle(fontSize: 11, color: Color(0xFFB8B0E8))),
          ]),
        ),
      );
    }

    return Column(children: [
      IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          metodo('Graham', (pj['graham'] as Map?) ?? const {}),
          const SizedBox(width: 8),
          metodo('Bazin', (pj['bazin'] as Map?) ?? const {}),
        ]),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Text('Preço hoje: ${_brl(preco)}. Margem de segurança é quanto o preço está abaixo do valor estimado; a referência aqui é ${pj['margem_alvo'] ?? 20}%.',
            style: const TextStyle(fontSize: 11.5, color: _lilas)),
      ),
    ]);
  }

  Widget _indicadores(List<Map> ind) => Wrap(spacing: 8, runSpacing: 8, children: [
        for (final i in ind)
          LayoutBuilder(builder: (ctx, c) {
            final w = (MediaQuery.sizeOf(ctx).width.clamp(0, 720) - 32) / 2;
            final cor = _corFaixa('${i['faixa']}');
            final v = i['valor'];
            final aberto = _aberto == i['id'];
            return SizedBox(
              width: aberto ? w * 2 + 8 : w,
              child: Pressionavel(
                aoTocar: () => setState(() => _aberto = aberto ? null : '${i['id']}'),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  padding: const EdgeInsets.all(12),
                  decoration: _caixa(cor.withValues(alpha: 0.8)),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Container(width: 9, height: 9, decoration: BoxDecoration(shape: BoxShape.circle, color: cor, boxShadow: [BoxShadow(color: cor, blurRadius: 6)])),
                      const SizedBox(width: 6),
                      Expanded(child: Text('${i['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: _lilas))),
                      Icon(aberto ? Icons.expand_less_rounded : Icons.info_outline_rounded, size: 16, color: _lilas),
                    ]),
                    const SizedBox(height: 4),
                    Text(v is num ? (i['pct'] == true ? _pct(v) : _num(v, 2)) : '—', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white)),
                    if (aberto) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${i['explica']}', style: const TextStyle(fontSize: 12, color: Colors.white))),
                  ]),
                ),
              ),
            );
          }),
        const Text('Cor do ponto: faixa geral de referência (verde, amarelo, vermelho). Cada setor tem seus próprios patamares.', style: TextStyle(fontSize: 11, color: _lilas)),
      ]);
}

/// Barra da margem de segurança: de -50% a +60%, com a marca da margem de referência.
class _BarraMargem extends StatelessWidget {
  const _BarraMargem({required this.margem, required this.alvo, required this.cor});
  final double margem, alvo;
  final Color cor;

  @override
  Widget build(BuildContext context) {
    double pos(double m) => ((m + 50) / 110).clamp(0.0, 1.0);
    return LayoutBuilder(builder: (ctx, c) {
      final w = c.maxWidth;
      return SizedBox(
        height: 12,
        child: Stack(children: [
          Container(decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0x335B4BD6))),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: pos(margem)),
            duration: const Duration(milliseconds: 1000),
            curve: Curves.easeOutCubic,
            builder: (ctx, v, _) => Container(width: w * v, decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: cor)),
          ),
          Positioned(left: w * pos(alvo) - 1, top: 0, bottom: 0, child: Container(width: 2, color: Colors.white)),
        ]),
      );
    });
  }
}

/// Linha de preço com área degradê, desenhada da esquerda para a direita (t de 0 a 1).
class _Linha extends CustomPainter {
  _Linha(this.v, this.cor, this.t);
  final List<double> v;
  final Color cor;
  final double t;

  @override
  void paint(Canvas c, Size s) {
    final lo = v.reduce(min), hi = v.reduce(max);
    final faixa = hi - lo == 0 ? 1.0 : hi - lo;
    Offset p(int i) => Offset(s.width * i / (v.length - 1), s.height - 6 - (v[i] - lo) / faixa * (s.height - 12));
    final n = max(2, (v.length * t).ceil());
    for (var k = 1; k <= 3; k++) {
      final y = s.height * k / 4;
      c.drawLine(Offset(0, y), Offset(s.width, y), Paint()..color = const Color(0x22FFFFFF));
    }
    final linha = Path()..moveTo(p(0).dx, p(0).dy);
    for (var i = 1; i < n; i++) {
      linha.lineTo(p(i).dx, p(i).dy);
    }
    final area = Path.from(linha)
      ..lineTo(p(n - 1).dx, s.height)
      ..lineTo(0, s.height)
      ..close();
    c.drawPath(
        area, Paint()..shader = LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [cor.withValues(alpha: 0.35), cor.withValues(alpha: 0)]).createShader(Offset.zero & s));
    c.drawPath(
        linha,
        Paint()
          ..color = cor
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.4
          ..strokeJoin = StrokeJoin.round);
    final fim = p(n - 1);
    c.drawCircle(fim, 7, Paint()..color = cor.withValues(alpha: 0.3));
    c.drawCircle(fim, 4, Paint()..color = cor);
  }

  @override
  bool shouldRepaint(_Linha o) => o.t != t || o.v != v;
}
