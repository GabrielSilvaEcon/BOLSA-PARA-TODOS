import 'dart:async';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'estrategia.dart';
import 'partida.dart';

/// Modo AO VIVO (cripto, dados públicos da Binance): o jogador lê o gráfico de agora, desenha e escolhe Subir, Cair ou Aguardar. O futuro ainda não
/// aconteceu, então ninguém sabe a resposta. Depois de alguns candles fechados o servidor confere (direção e desenhos) e a nota aparece aqui.
class VivoTela extends StatefulWidget {
  const VivoTela({super.key, required this.api});
  final Api api;

  @override
  State<VivoTela> createState() => _VivoTelaState();
}

class _VivoTelaState extends State<VivoTela> {
  List<Map<String, dynamic>> _moedas = const [];
  List<Map<String, dynamic>> _duracoes = const [];
  List<Map<String, dynamic>> _itens = const [];
  String _moeda = 'BTC';
  String _tf = '5m';
  bool _carregando = true, _abrindo = false;
  String _erro = '';
  Timer? _relogio;

  static const _azul = Color(0xFF3B7BFF);
  static const _lilas = Color(0xFFB5C8E6);

  @override
  void initState() {
    super.initState();
    _carregar();
    _relogio = Timer.periodic(const Duration(seconds: 20), (_) => _atualizarLeituras());
  }

  @override
  void dispose() {
    _relogio?.cancel();
    super.dispose();
  }

  List<Map<String, dynamic>> _lista(dynamic v) => [for (final x in (v as List? ?? const [])) if (x is Map) x.cast<String, dynamic>()];

  Future<void> _carregar() async {
    try {
      final m = await widget.api.get('/vivo/moedas');
      final p = await widget.api.get('/vivo/previsoes');
      if (!mounted) return;
      setState(() {
        _moedas = _lista(m['moedas']);
        _duracoes = _lista(m['duracoes']);
        _itens = _lista(p['itens']);
        _carregando = false;
        _erro = '';
      });
    } catch (e) {
      if (mounted) setState(() {
        _carregando = false;
        _erro = e.toString();
      });
    }
  }

  Future<void> _atualizarLeituras() async {
    if (!mounted || _carregando) return;
    try {
      final p = await widget.api.get('/vivo/previsoes');
      if (mounted) setState(() => _itens = _lista(p['itens']));
    } catch (_) {}
  }

  Future<void> _ler() async {
    if (_abrindo) return;
    setState(() {
      _abrindo = true;
      _erro = '';
    });
    try {
      final r = await widget.api.get('/vivo/$_moeda/$_tf/tela');
      if (!mounted) return;
      final tela = (r['tela'] as Map).cast<String, dynamic>();
      await Navigator.of(context).push(MaterialPageRoute(
        builder: (ctx) => Scaffold(
          body: EstrategiaView(
            api: widget.api,
            base: '/vivo/$_moeda/$_tf',
            args: tela,
            aoResponder: (_) => Navigator.of(ctx).pop(true),
            aoVoltar: () => Navigator.of(ctx).pop(false),
          ),
        ),
      ));
      await _atualizarLeituras();
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    } finally {
      if (mounted) setState(() => _abrindo = false);
    }
  }

  /// Trade Battle ao vivo: a mesa de sempre (compra e venda com quantidade, stop e alvo) sobre o mercado de agora, por 1 hora, candles de 5 minutos.
  Future<void> _trade() async {
    await Navigator.of(context, rootNavigator: true).push(MaterialPageRoute(builder: (_) => PartidaTela(api: widget.api, inicio: '/trade/vivo', corpoInicio: {'moeda': _moeda})));
    _atualizarLeituras();
  }

  String _nomeMoeda(String id) => [for (final m in _moedas) if (m['id'] == id) '${m['nome']}'].firstOrNull ?? id;

  Widget _chip(String rotulo, bool ativo, VoidCallback f) => Pressionavel(
        aoTocar: f,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            color: ativo ? _azul : const Color(0xFF14284F),
            border: Border.all(color: ativo ? const Color(0xFF8FB4F0) : const Color(0x553A6FD8)),
          ),
          child: Text(rotulo, style: TextStyle(color: Colors.white, fontWeight: ativo ? FontWeight.w900 : FontWeight.w600)),
        ),
      );

  Widget _leitura(Map<String, dynamic> it) {
    final estado = '${it['estado']}';
    final r = it['resultado'] as Map?;
    final dir = switch (it['direcao']) { 'alta' => 'Subir', 'baixa' => 'Cair', _ => 'Aguardar' };
    String linha;
    Color cor = _lilas;
    String? nota;
    if (estado == 'conferida') {
      final n = r?['nota'];
      nota = n == null ? '—' : '${(n as num).toStringAsFixed(0)}';
      final real = switch (r?['real']) { 'alta' => 'subiu', 'baixa' => 'caiu', _ => 'ficou de lado' };
      linha = 'O preço $real (${((r?['mov_pct'] as num?) ?? 0).toStringAsFixed(2)}%).${r?['direcao_ok'] == true ? ' Você acertou a direção.' : r?['direcao_ok'] == false ? ' Você errou a direção.' : ''}';
      if (n is num) cor = n >= 50 ? const Color(0xFF43F0A6) : const Color(0xFFFF8A8A);
    } else if (estado == 'expirada') {
      linha = 'Encerrada sem nota (o gráfico andou demais para conferir).';
    } else {
      final f = (it['faltam'] as num?)?.toInt() ?? (it['horizonte'] as num?)?.toInt() ?? 0;
      linha = 'Aguardando ${f > 0 ? '$f candle${f == 1 ? '' : 's'} fechar${f == 1 ? '' : 'em'}' : 'a conferência'}…';
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: const Color(0xFF10274A), borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x553A6FD8))),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${_nomeMoeda('${it['moeda']}')} · ${it['tf']} · $dir', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
            const SizedBox(height: 3),
            Text(linha, style: const TextStyle(color: _lilas, fontSize: 12.5)),
          ]),
        ),
        if (nota != null) Text(nota, style: TextStyle(color: cor, fontSize: 26, fontWeight: FontWeight.w900)),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final dur = [for (final d in _duracoes) if (d['id'] == _tf) d].firstOrNull;
    final min = dur == null ? 0 : ((dur['segundos'] as num).toInt() / 60).round();
    return Scaffold(
      backgroundColor: const Color(0xFF081528),
      appBar: AppBar(title: const Text('Ao vivo · Cripto', style: TextStyle(fontWeight: FontWeight.w900)), backgroundColor: Colors.transparent, foregroundColor: Colors.white),
      body: _carregando
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _carregar,
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 28), children: [
                const Text('Leia o gráfico de agora, desenhe e diga se vai subir, cair ou aguardar. O mercado é de verdade e o futuro ainda não aconteceu: o servidor confere quando os candles fecharem.',
                    style: TextStyle(color: _lilas, height: 1.35)),
                const SizedBox(height: 14),
                const Text('Moeda', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Wrap(spacing: 8, runSpacing: 8, children: [for (final m in _moedas) _chip('${m['id']}', _moeda == m['id'], () => setState(() => _moeda = '${m['id']}'))]),
                const SizedBox(height: 14),
                const Text('Duração do gráfico', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Wrap(spacing: 8, runSpacing: 8, children: [for (final d in _duracoes) _chip('${d['id']}', _tf == d['id'], () => setState(() => _tf = '${d['id']}'))]),
                if (dur != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text('A conferência sai em ~$min min (${dur['candles']} candles).', style: const TextStyle(color: _lilas, fontSize: 12.5))),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _abrindo ? null : _ler,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50), backgroundColor: const Color(0xFF14C98F), foregroundColor: const Color(0xFF06240F)),
                  child: Text(_abrindo ? 'Abrindo…' : 'LER O GRÁFICO AO VIVO', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
                ),
                if (_erro.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_erro, style: const TextStyle(color: Color(0xFFFF8A8A)))),
                const SizedBox(height: 10),
                OutlinedButton(
                  onPressed: _trade,
                  style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(50), foregroundColor: Colors.white, side: const BorderSide(color: Color(0xFFFF5C7A), width: 1.4)),
                  child: Text('🔴 TRADE BATTLE AO VIVO · $_moeda · 1 hora', style: const TextStyle(fontWeight: FontWeight.w900)),
                ),
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: Text('A mesa de sempre (comprar, vender, stop e alvo) sobre o mercado de agora, candles de 5 minutos, sessão de 1 hora. O preço aparece dividido por uma potência de 10 (ex.: BTC ÷1.000) para caber no capital.',
                      style: TextStyle(color: _lilas, fontSize: 12)),
                ),
                const SizedBox(height: 22),
                const Text('Minhas leituras', style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w900)),
                const SizedBox(height: 8),
                if (_itens.isEmpty) const Text('Você ainda não fez nenhuma leitura ao vivo.', style: TextStyle(color: _lilas)) else for (final it in _itens) _leitura(it),
                const SizedBox(height: 10),
                const Text('Dados de mercado públicos. Jogo educativo, sem recomendação de compra ou venda.', style: TextStyle(color: _lilas, fontSize: 11.5)),
              ]),
            ),
    );
  }
}
