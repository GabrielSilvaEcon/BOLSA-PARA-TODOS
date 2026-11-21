import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';

/// Atalhos "Mais da sua carteira": o extrato de operações e as conquistas da carteira virtual (as mesmas do app antigo).
const _lilas = Color(0xFFD9D4F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);

String _n(num v, int c) {
  final s = v.abs().toStringAsFixed(c);
  final p = s.split('.');
  final b = StringBuffer();
  for (var i = 0; i < p[0].length; i++) {
    if (i > 0 && (p[0].length - i) % 3 == 0) b.write('.');
    b.write(p[0][i]);
  }
  return '${v < 0 ? '-' : ''}$b${c > 0 ? ',${p[1]}' : ''}';
}

String _data(Object? d) {
  final t = '${d ?? ''}';
  return t.length >= 10 ? '${t.substring(8, 10)}/${t.substring(5, 7)}/${t.substring(0, 4)}' : t;
}

Widget _base(BuildContext context, String titulo, Widget? corpo, String? erro, Future<void> Function() recarregar, List<Widget> Function() itens) => Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: recarregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  Expanded(child: Text(titulo, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                if (corpo == null && erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
                if (corpo == null && erro != null) Padding(padding: const EdgeInsets.all(20), child: Text(erro, style: const TextStyle(color: Colors.white))),
                if (corpo != null) ...itens(),
              ]),
            ),
          ),
        ),
      ]),
    );

/// Extrato da carteira: compras, vendas (com o resultado), proventos, desdobramentos e ordens recusadas.
class HistoricoCarteiraTela extends StatefulWidget {
  const HistoricoCarteiraTela({super.key, required this.api});
  final Api api;

  @override
  State<HistoricoCarteiraTela> createState() => _HistoricoCarteiraTelaState();
}

class _HistoricoCarteiraTelaState extends State<HistoricoCarteiraTela> {
  Map<String, dynamic>? _d;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/carteira/historico');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  static const _visual = {
    'compra': (Icons.add_shopping_cart_rounded, Color(0xFF4F9BFF), 'Compra'),
    'venda': (Icons.sell_rounded, Color(0xFFF2B84B), 'Venda'),
    'provento': (Icons.payments_rounded, Color(0xFF26D07C), 'Provento'),
    'desdobramento': (Icons.call_split_rounded, Color(0xFFB54BFF), 'Desdobramento'),
    'recusada': (Icons.block_rounded, Color(0xFFFF5A7A), 'Ordem recusada'),
  };

  @override
  Widget build(BuildContext context) {
    final itens = ((_d?['itens'] as List?) ?? const []).cast<Map>();
    final r = (_d?['resumo'] as Map?) ?? const {};
    return _base(context, 'Histórico da carteira', _d == null ? null : const SizedBox(), _erro, _carregar, () {
      Widget dado(String v, String t, Color c) => Expanded(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 3),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [c.withValues(alpha: 0.42), c.withValues(alpha: 0.12)]),
                border: Border.all(color: c.withValues(alpha: 0.85), width: 1.5),
              ),
              child: Column(children: [
                FittedBox(child: Text(v, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
                Text(t, style: const TextStyle(fontSize: 11, color: Colors.white)),
              ]),
            ),
          );
      final rv = (r['resultado_vendas'] as num?) ?? 0;
      return [
        Entrada(
          ordem: 0,
          child: Row(children: [
            dado('${r['compras'] ?? 0}', 'compras', const Color(0xFF4F9BFF)),
            dado('${r['vendas'] ?? 0}', 'vendas', _ouro),
            dado('T\$ ${_n(rv, 2)}', 'resultado das vendas', rv >= 0 ? _verde : _vermelho),
            dado('T\$ ${_n((r['proventos'] as num?) ?? 0, 2)}', 'proventos', _verde),
          ]),
        ),
        const SizedBox(height: 12),
        if (itens.isEmpty)
          const Padding(padding: EdgeInsets.all(20), child: Text('Nenhuma operação ainda. Compre seu primeiro ativo na Carteira!', textAlign: TextAlign.center, style: TextStyle(color: Colors.white))),
        for (final (i, x) in itens.indexed)
          Entrada(
            ordem: 1 + i.clamp(0, 12),
            child: Builder(builder: (ctx) {
              final (ic, cor, rot) = _visual['${x['tipo']}'] ?? (Icons.receipt_long_rounded, const Color(0xFF8B6CFF), '${x['tipo']}');
              final res = x['r'];
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: cor.withValues(alpha: 0.85), width: 1.5),
                  gradient: LinearGradient(colors: [Color.lerp(cor, const Color(0xFF160B5E), 0.6)!, const Color(0xEE120850)]),
                  image: arteCartao(arteDe('${x['tipo']}'), opacidade: 0.3),
                ),
                child: Row(children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(shape: BoxShape.circle, color: cor.withValues(alpha: 0.3), border: Border.all(color: cor)),
                    child: x['logo'] is String
                        ? Padding(padding: const EdgeInsets.all(7), child: Image.asset('assets/logos/${x['logo']}', errorBuilder: (_, __, ___) => Icon(ic, color: Colors.white)))
                        : Icon(ic, color: Colors.white, size: 22),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('$rot · ${x['rotulo'] ?? x['t'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                      Text(
                          [
                            _data(x['d']),
                            if (x['q'] is num) '${_n(x['q'] as num, (x['q'] as num) % 1 == 0 ? 0 : 4)} un.',
                            if (x['p'] is num) 'a T\$ ${_n(x['p'] as num, 2)}',
                            if ('${x['m'] ?? ''}'.isNotEmpty) '${x['m']}',
                          ].join(' · '),
                          style: const TextStyle(fontSize: 12, color: _lilas)),
                    ]),
                  ),
                  if (x['v'] is num || res is num)
                    Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      if (x['v'] is num) Text('T\$ ${_n(x['v'] as num, 2)}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                      if (res is num) Text('${res >= 0 ? '+' : ''}T\$ ${_n(res, 2)}', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: res >= 0 ? _verde : _vermelho)),
                    ]),
                ]),
              );
            }),
          ),
      ];
    });
  }
}

/// Conquistas da carteira: as desbloqueadas (com a data) e as que faltam (apagadas, com a recompensa).
class ConquistasCarteiraTela extends StatefulWidget {
  const ConquistasCarteiraTela({super.key, required this.api});
  final Api api;

  @override
  State<ConquistasCarteiraTela> createState() => _ConquistasCarteiraTelaState();
}

class _ConquistasCarteiraTelaState extends State<ConquistasCarteiraTela> {
  Map<String, dynamic>? _d;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/carteira/conquistas');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  Color _cor(Object? h) {
    final s = '${h ?? ''}'.replaceFirst('#', '');
    final v = s.length == 6 ? int.tryParse(s, radix: 16) : null;
    return v == null ? _ouro : Color(0xFF000000 | v);
  }

  @override
  Widget build(BuildContext context) {
    final itens = ((_d?['itens'] as List?) ?? const []).cast<Map>();
    return _base(context, 'Conquistas da carteira', _d == null ? null : const SizedBox(), _erro, _carregar, () {
      final ok = (_d?['ok'] as num?)?.toInt() ?? 0, total = (_d?['total'] as num?)?.toInt() ?? 0;
      return [
        Entrada(
          ordem: 0,
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _ouro, width: 2),
              gradient: const LinearGradient(colors: [Color(0xFF6B3A12), Color(0xFF2A1046)]),
              image: arteCartao('loja', opacidade: 0.4),
            ),
            child: Row(children: [
              const Text('🏅', style: TextStyle(fontSize: 40)),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('$ok de $total conquistas', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white)),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(value: total == 0 ? 0 : ok / total, minHeight: 9, backgroundColor: const Color(0x55120850), color: _ouro),
                  ),
                ]),
              ),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        for (final (i, c) in itens.indexed)
          Entrada(
            ordem: 1 + i,
            child: Builder(builder: (ctx) {
              final feita = c['desbloqueada_em'] != null;
              final cor = _cor(c['cor']);
              final tc = ((c['recompensa'] as Map?)?['tc']);
              return Opacity(
                opacity: feita ? 1 : 0.6,
                child: Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: feita ? cor : const Color(0xFF6A4FE6), width: feita ? 2 : 1.2),
                    gradient: LinearGradient(colors: [Color.lerp(cor, const Color(0xFF160B5E), feita ? 0.5 : 0.8)!, const Color(0xEE120850)]),
                    boxShadow: [if (feita) BoxShadow(color: cor.withValues(alpha: 0.4), blurRadius: 12)],
                  ),
                  child: Row(children: [
                    Container(
                      width: 52,
                      height: 52,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(shape: BoxShape.circle, color: cor.withValues(alpha: 0.25), border: Border.all(color: feita ? cor : Colors.white24, width: 2)),
                      child: feita ? Text('${c['emblema'] ?? '🏅'}', style: const TextStyle(fontSize: 26)) : const Icon(Icons.lock_rounded, color: Colors.white54),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${c['nome']}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white)),
                        Text('${c['descricao']}', style: const TextStyle(fontSize: 12, color: _lilas)),
                        if (feita) Text('Desbloqueada em ${_data(c['desbloqueada_em'])}', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: cor)),
                      ]),
                    ),
                    if (tc is num && tc > 0) Text('+$tc TC', style: const TextStyle(fontWeight: FontWeight.w900, color: _ouro)),
                  ]),
                ),
              );
            }),
          ),
      ];
    });
  }
}
