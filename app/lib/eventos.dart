import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';
import 'missoes.dart';
import 'navegacao.dart';

/// Eventos e recompensas (atalho da aba Jogos): campanhas de TickerCoins ativas, baú diário e baús de progresso, a temporada do
/// Hunter Pass, o desafio da semana e as últimas TickerCoins ganhas. Só leitura; abrir baús continua na Loja.
class EventosTela extends StatefulWidget {
  const EventosTela({super.key, required this.api});
  final Api api;

  @override
  State<EventosTela> createState() => _EventosTelaState();
}

const _lilas = Color(0xFFD9D4F7);
const _verde = Color(0xFF26D07C);
const _ouro = Color(0xFFF2B84B);

class _EventosTelaState extends State<EventosTela> {
  Map<String, dynamic>? _d;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _erro = null);
    try {
      final r = await widget.api.get('/eventos');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  void _loja() {
    Navigator.of(context).popUntil((r) => r.isFirst);
    abrirAba(4);
  }

  BoxDecoration _caixa(Color cor, [String? arte]) => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: cor.withValues(alpha: 0.9), width: 1.6),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(cor, const Color(0xFF160B5E), 0.5)!, Color.lerp(cor, const Color(0xFF120850), 0.8)!]),
        image: arte == null ? null : arteCartao(arte, opacidade: 0.42),
        boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.3), blurRadius: 12)],
      );

  Widget _titulo(String t, IconData ic, Color cor) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
        child: Row(children: [
          Icon(ic, color: cor, size: 20),
          const SizedBox(width: 6),
          Expanded(child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
        ]),
      );

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
                  const Expanded(child: Text('Eventos e recompensas', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
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
                  if (d['passe'] is Map) Entrada(ordem: 0, child: _passe(d['passe'] as Map)),
                  _titulo('Eventos ativos', Icons.auto_awesome_rounded, const Color(0xFFFFD27A)),
                  Entrada(ordem: 1, child: _ativos(d)),
                  if (d['desafio'] is Map) ...[
                    _titulo('Desafio da semana', Icons.event_available_rounded, const Color(0xFF8DF5C1)),
                    Entrada(ordem: 2, child: _desafio(d['desafio'] as Map)),
                  ],
                  _titulo('Últimas recompensas', Icons.toll_rounded, _ouro),
                  Entrada(ordem: 3, child: _recompensas(((d['recompensas'] as List?) ?? const []).cast<Map>())),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _passe(Map p) {
    final total = (p['total'] as num?)?.toInt() ?? 0, feitos = (p['feitos'] as num?)?.toInt() ?? 0;
    final prox = p['proximo'] as Map?;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _caixa(const Color(0xFFB54BFF), 'loja'),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.workspace_premium_rounded, color: _ouro, size: 30),
          const SizedBox(width: 8),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('HUNTER PASS', style: TextStyle(fontSize: 17, letterSpacing: 1, fontWeight: FontWeight.w900, color: Colors.white)),
              Text('${p['rotulo'] ?? ''} · faltam ${p['dias_restantes'] ?? '—'} dias', style: const TextStyle(fontSize: 12, color: _lilas)),
            ]),
          ),
          Text('$feitos/$total', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: _ouro)),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          for (var i = 0; i < total; i++)
            Expanded(
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: 1),
                duration: Duration(milliseconds: 300 + 80 * i),
                builder: (ctx, v, _) => Container(
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  height: 10,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(999),
                    color: i < feitos ? Color.lerp(const Color(0x55120850), _ouro, v) : const Color(0x55120850),
                    border: Border.all(color: _ouro.withValues(alpha: 0.5)),
                  ),
                ),
              ),
            ),
        ]),
        const SizedBox(height: 8),
        Text(
            p['completo'] == true
                ? 'Temporada completa! Você ganhou todas as honrarias.'
                : prox == null
                    ? 'Estude para avançar nos marcos.'
                    : 'Próximo: ${prox['simbolo'] ?? ''} ${prox['nome'] ?? ''} (faltam ${p['falta'] ?? '—'} XP) · ${prox['honraria'] ?? ''}',
            style: const TextStyle(fontSize: 12.5, color: Colors.white)),
      ]),
    );
  }

  Widget _linha(IconData ic, Color cor, String titulo, String sub, String? premio, {VoidCallback? acao, String? rotulo}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(shape: BoxShape.circle, color: cor.withValues(alpha: 0.3), border: Border.all(color: cor)),
            child: Icon(ic, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(titulo, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Colors.white)),
              Text(sub, style: const TextStyle(fontSize: 12, color: _lilas)),
            ]),
          ),
          if (acao != null)
            FilledButton(
              onPressed: acao,
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), visualDensity: VisualDensity.compact),
              child: Text(rotulo ?? 'Abrir'),
            )
          else if (premio != null)
            Text(premio, style: const TextStyle(fontWeight: FontWeight.w900, color: _ouro)),
        ]),
      );

  Widget _ativos(Map d) {
    final camps = ((d['campanhas'] as List?) ?? const []).cast<Map>();
    final bau = d['bau'] as Map?;
    final pend = (d['baus_pendentes'] as num?)?.toInt() ?? 0;
    final linhas = <Widget>[
      for (final c in camps) _linha(Icons.rocket_launch_rounded, const Color(0xFFFF6B8A), '${c['rotulo']}', 'Até ${c['fim']}', '${c['multiplicador']}× TC'),
      if (bau != null && bau['ativo'] == true)
        bau['aberto'] == true
            ? _linha(Icons.redeem_rounded, _verde, 'Baú diário', 'Já aberto hoje. Volte amanhã!', '+${bau['valor']} TC')
            : _linha(Icons.redeem_rounded, _ouro, 'Baú diário', 'Disponível agora na Loja', null, acao: _loja, rotulo: 'Abrir'),
      if (pend > 0) _linha(Icons.inventory_2_rounded, const Color(0xFF8B6CFF), 'Baús de progresso', '$pend ${pend == 1 ? 'baú esperando' : 'baús esperando'} por você', null, acao: _loja),
    ];
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 6),
      decoration: _caixa(const Color(0xFFFF8A3D), 'moedas'),
      child: linhas.isEmpty
          ? const Padding(
              padding: EdgeInsets.all(10),
              child: Text('Nenhum evento especial agora. Fique de olho: campanhas aparecem aqui.', style: TextStyle(color: Colors.white)),
            )
          : Column(children: linhas),
    );
  }

  Widget _desafio(Map s) {
    final ok = s['ok'] == true;
    final atual = (s['atual'] as num?) ?? 0, alvo = (s['alvo'] as num?) ?? 1;
    return Pressionavel(
      aoTocar: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MissoesTela(api: widget.api))),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: _caixa(ok ? _verde : const Color(0xFF26C6DA), 'velas'),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text('${s['titulo']}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white))),
            Text('+${s['pontos']} pts', style: const TextStyle(fontWeight: FontWeight.w900, color: _ouro)),
          ]),
          Text('${s['texto']}', style: const TextStyle(fontSize: 12.5, color: Colors.white)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(value: (atual / alvo).clamp(0, 1).toDouble(), minHeight: 9, backgroundColor: const Color(0x55120850), color: ok ? _verde : const Color(0xFFFFD76A)),
              ),
            ),
            const SizedBox(width: 8),
            Text(ok ? 'Feito!' : '${atual.round()} / ${alvo.round()}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
          ]),
          const Align(alignment: Alignment.centerRight, child: Text('Ver todas as missões ›', style: TextStyle(fontWeight: FontWeight.w800, color: Color(0xFFB79CFF)))),
        ]),
      ),
    );
  }

  Widget _recompensas(List<Map> rs) => Container(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 6),
        decoration: _caixa(_ouro, 'cofre'),
        child: rs.isEmpty
            ? const Padding(padding: EdgeInsets.all(10), child: Text('Você ainda não ganhou TickerCoins. Estude e jogue para ganhar!', style: TextStyle(color: Colors.white)))
            : Column(children: [
                for (final r in rs) _linha(Icons.toll_rounded, _ouro, '${r['descricao']}', _data('${r['em']}'), '+${r['tc']} TC'),
              ]),
      );

  String _data(String t) => t.length >= 10 ? '${t.substring(8, 10)}/${t.substring(5, 7)}/${t.substring(0, 4)}' : t;
}
