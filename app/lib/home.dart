import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'animacoes.dart';
import 'api.dart';
import 'arte_cartao.dart';
import 'carteira.dart';
import 'cenario.dart';
import 'mercado.dart';
import 'missoes.dart';
import 'navegacao.dart';

/// Tela inicial no formato da referência do TickerHunters (a mesma ordem da Home do app antigo, home_game.py):
///   1. banner com o nome, o touro, a marca e o Hunter Pass da temporada
///   2. Pregão Orbit: a arena do touro contra o urso com os quatro indicadores do dia nos cantos
///   3. Missões diárias: troféu, progresso e o cofre com os pontos que ainda dá para ganhar
///   4. os três acessos (Carteira, Jogar agora e Mercado)
///   5. Cenário econômico (botão próprio, com o último veredito)
/// Dados: `GET /eu` (nome, passe) e `GET /home` (indicadores, missões e cenário).
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);
const _lilas = Color(0xFFD9D4F7);

class _HomeTelaState extends State<HomeTela> {
  Map<String, dynamic>? _eu, _home;
  String? _erro;
  bool _carregando = true;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final r = await Future.wait([widget.api.get('/eu'), widget.api.get('/home').catchError((_) => <String, dynamic>{})]);
      if (mounted) {
        setState(() {
          _eu = r[0];
          _home = r[1];
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = 'Não consegui carregar a sua Home agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  String get _nome {
    final perfil = (_eu?['perfil'] as Map?) ?? {};
    final conta = (_eu?['conta'] as Map?) ?? {};
    for (final n in [perfil['nome'], perfil['usuario'], conta['nome']]) {
      if (n is String && n.trim().isNotEmpty) return n.contains('@') ? n.split('@').first : n.trim();
    }
    final e = '${conta['email'] ?? ''}';
    return e.contains('@') ? e.split('@').first : 'Jogador';
  }

  void _abrir(Widget t) => Navigator.of(context).push(MaterialPageRoute(builder: (_) => t));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/home/fundo_home.png', fit: BoxFit.cover, alignment: Alignment.topCenter),
          Container(color: const Color(0xCC0B0930)),
          SafeArea(
            child: RefreshIndicator(
              onRefresh: _carregar,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 720),
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(12, 10, 12, 24),
                    children: [
                      if (_carregando && _eu == null)
                        const Padding(padding: EdgeInsets.all(60), child: Center(child: CircularProgressIndicator()))
                      else if (_erro != null && _eu == null)
                        _erroTela()
                      else ...[
                        Entrada(ordem: 0, child: _banner()),
                        const SizedBox(height: 12),
                        Entrada(ordem: 1, child: _orbit()),
                        const SizedBox(height: 12),
                        Entrada(ordem: 2, child: _missoes()),
                        const SizedBox(height: 12),
                        Entrada(ordem: 3, child: _acessos()),
                        const SizedBox(height: 12),
                        Entrada(ordem: 4, child: _cenario()),
                      ],
                      const SizedBox(height: 18),
                      const Text('Jogo educativo. Sem recomendação de compra ou venda.', textAlign: TextAlign.center, style: TextStyle(fontSize: 11.5, color: _lilas)),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- 1. banner: plaquinha com o nome, touro, marca e o Hunter Pass
  Widget _banner() {
    final p = (_eu?['passe'] as Map?) ?? const {};
    final total = (p['total'] as num?)?.toInt() ?? 0, feitos = (p['feitos'] as num?)?.toInt() ?? 0;
    final pct = total == 0 ? 0.0 : (p['completo'] == true ? 1.0 : ((feitos + ((p['pct'] as num?) ?? 0).toDouble()) / total).clamp(0.0, 1.0));
    return Pressionavel(
      aoTocar: () => abrirAba(2),
      child: Container(
        height: 132,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: _ouro, width: 2),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF3B1FA8), Color(0xFF160B5E)]),
          image: arteCartao('velas', opacidade: 0.4),
          boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 18)],
        ),
        child: Stack(children: [
          Positioned(left: -6, bottom: -8, child: Flutua(child: _semBorda(Image.asset('assets/home/touro.webp', height: 112)))),
          Positioned(
            left: 100,
            top: 12,
            right: 150,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  gradient: const LinearGradient(colors: [Color(0xFFFFE08A), Color(0xFFF2B84B)]),
                  border: Border.all(color: const Color(0xFF8A4E00), width: 1.5),
                ),
                child: Text(_nome, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Color(0xFF3B2600))),
              ),
              const SizedBox(height: 6),
              Image.asset('assets/logo_th.webp', height: 58, fit: BoxFit.contain, alignment: Alignment.centerLeft),
            ]),
          ),
          Positioned(
            right: 10,
            top: 14,
            bottom: 14,
            width: 136,
            child: Container(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xEE5A2BC8), Color(0xEE2A1278)]),
                border: Border.all(color: const Color(0xFFB59BFF), width: 1.5),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                const Row(children: [
                  Icon(Icons.workspace_premium_rounded, color: _ouro, size: 18),
                  SizedBox(width: 4),
                  Expanded(child: FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text('HUNTER PASS', style: TextStyle(fontWeight: FontWeight.w900, color: Colors.white)))),
                ]),
                const SizedBox(height: 4),
                Text(total == 0 ? '—' : '$feitos / $total marcos', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: _lilas)),
                const SizedBox(height: 6),
                _barra(pct, const [Color(0xFFFFE08A), Color(0xFFF2B84B)]),
                if ('${p['rotulo'] ?? ''}'.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text('${p['rotulo']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 10.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ]),
      ),
    );
  }

  /// As artes do touro, do troféu e do cofre vêm num quadrado escuro: a borda some num degradê redondo.
  Widget _semBorda(Widget img) => ShaderMask(
        blendMode: BlendMode.dstIn,
        shaderCallback: (r) => const RadialGradient(colors: [Colors.white, Colors.white, Colors.transparent], stops: [0, 0.62, 0.98]).createShader(r),
        child: img,
      );

  Widget _barra(double v, List<Color> cores) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: v),
        duration: const Duration(milliseconds: 1100),
        curve: Curves.easeOutCubic,
        builder: (ctx, x, _) => ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: Stack(children: [
            Container(height: 9, color: const Color(0x55120850)),
            FractionallySizedBox(widthFactor: x, child: Container(height: 9, decoration: BoxDecoration(gradient: LinearGradient(colors: cores)))),
          ]),
        ),
      );

  // ---- 2. Pregão Orbit: arena com os quatro indicadores do dia nos cantos
  static const _curto = {'Ibovespa': 'IBOV', 'Dólar': 'DÓLAR', 'Bitcoin': 'BTC', 'Índice do medo': 'MEDO'};

  Widget _orbit() {
    final itens = ((_home?['hoje'] as List?) ?? const []).cast<Map>();
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFF26E0FF), width: 1.6),
        color: const Color(0xFF0B0930),
        boxShadow: const [BoxShadow(color: Color(0x5526E0FF), blurRadius: 18)],
      ),
      child: Column(children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 6),
          decoration: const BoxDecoration(gradient: LinearGradient(colors: [Color(0xFF1B6BFF), Color(0xFF7B2FF7), Color(0xFFFF2E8A)])),
          child: const Text('PREGÃO ORBIT', textAlign: TextAlign.center, style: TextStyle(fontSize: 14, letterSpacing: 2, fontWeight: FontWeight.w900, color: Colors.white)),
        ),
        AspectRatio(
          aspectRatio: 768 / 490,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset('assets/home/arena.webp', fit: BoxFit.cover),
            if (itens.isEmpty)
              const Align(
                alignment: Alignment.bottomCenter,
                child: Padding(padding: EdgeInsets.all(10), child: Text('Sem cotações agora. Elas voltam assim que a fonte responder.', style: TextStyle(fontSize: 11.5, color: Colors.white))),
              ),
            for (final (i, it) in itens.take(4).indexed)
              Align(
                alignment: const [Alignment.topLeft, Alignment.topRight, Alignment.bottomLeft, Alignment.bottomRight][i],
                child: Padding(padding: const EdgeInsets.all(8), child: _tile(it)),
              ),
          ]),
        ),
      ]),
    );
  }

  Widget _tile(Map it) {
    final v = it['var'];
    final nota = '${it['nota'] ?? ''}';
    final cor = v is num ? (v >= 0 ? _verde : _vermelho) : (nota.contains('alto') ? _vermelho : _ouro);
    final txt = v is num ? '${v >= 0 ? '▲ +' : '▼ '}${v.toStringAsFixed(2).replaceAll('.', ',')}%' : '${it['valor']}';
    return Container(
      width: 104,
      padding: const EdgeInsets.fromLTRB(8, 5, 8, 5),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: const Color(0xCC0B0930),
        border: Border.all(color: cor, width: 1.4),
        boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.45), blurRadius: 10)],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
        Text(_curto['${it['rotulo']}'] ?? '${it['rotulo']}', style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w900, letterSpacing: 0.8, color: _lilas)),
        FittedBox(child: Text(txt, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: cor))),
        Text(v is num ? '${it['valor']}' : nota, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 10, color: Colors.white)),
      ]),
    );
  }

  // ---- 3. Missões diárias
  Widget _missoes() {
    final m = (_home?['missoes'] as Map?) ?? const {};
    final total = (m['total'] as num?)?.toInt() ?? 0, feitas = (m['feitas'] as num?)?.toInt() ?? 0;
    final pts = (m['pontos'] as num?)?.toInt() ?? 0;
    final fim = total > 0 && feitas >= total;
    final sub = total == 0 ? 'Sem missões disponíveis agora.' : (fim ? 'Missões de hoje concluídas!' : 'Complete desafios e ganhe recompensas!');
    return Pressionavel(
      aoTocar: () => _abrir(MissoesTela(api: widget.api)),
      child: Container(
        height: 96,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _ouro, width: 1.8),
          gradient: const LinearGradient(colors: [Color(0xFF6B3A12), Color(0xFF2A1046)]),
          image: arteCartao('moedas', opacidade: 0.35),
          boxShadow: const [BoxShadow(color: Color(0x55F2B84B), blurRadius: 14)],
        ),
        child: Row(children: [
          const SizedBox(width: 6),
          Flutua(child: _semBorda(Image.asset('assets/home/trofeu.webp', height: 78))),
          const SizedBox(width: 6),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
              const Text('MISSÕES DIÁRIAS', style: TextStyle(fontSize: 15, letterSpacing: 1, fontWeight: FontWeight.w900, color: Colors.white)),
              Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Color(0xFFFFE6C2))),
              const SizedBox(height: 6),
              Row(children: [
                Expanded(child: _barra(total == 0 ? 0 : feitas / total, const [Color(0xFF2EE88A), Color(0xFF12A83C)])),
                const SizedBox(width: 8),
                Text('$feitas / $total', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
              ]),
            ]),
          ),
          const SizedBox(width: 6),
          Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            _semBorda(Image.asset('assets/home/cofre.webp', height: 54)),
            Text(fim ? '✓ Feito' : (pts > 0 ? '+$pts pts' : ''), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: fim ? _verde : _ouro)),
          ]),
          const SizedBox(width: 10),
        ]),
      ),
    );
  }

  // ---- 4. acessos com a arte dos botões
  Widget _acessos() => Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
        Expanded(child: _botao('assets/home/btn_carteira.webp', 'Carteira', () => _abrir(CarteiraTela(api: widget.api)))),
        const SizedBox(width: 8),
        Expanded(flex: 2, child: Flutua(altura: 3, child: _botao('assets/home/btn_jogar.webp', 'Jogar agora', () => abrirAba(1)))),
        const SizedBox(width: 8),
        Expanded(child: _botao('assets/home/btn_mercado.webp', 'Mercado', () => _abrir(MercadoTela(api: widget.api)))),
      ]);

  Widget _botao(String arquivo, String rotulo, VoidCallback f) => Pressionavel(
        aoTocar: f,
        child: Semantics(button: true, label: rotulo, child: Image.asset(arquivo, fit: BoxFit.contain)),
      );

  // ---- 5. Cenário econômico
  Widget _cenario() {
    final v = '${((_home?['cenario'] as Map?) ?? const {})['veredito'] ?? ''}';
    final (txt, cor) = switch (v) {
      'BOM' => ('Favorável', _verde),
      'RUIM' => ('Desfavorável', _vermelho),
      'NEUTRO' => ('Sinais mistos', _ouro),
      _ => ('Ver leitura', const Color(0xFF8B6CFF)),
    };
    return Pressionavel(
      aoTocar: () => _abrir(CenarioTela(api: widget.api)),
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFF26C6DA), width: 1.8),
          gradient: const LinearGradient(colors: [Color(0xFF0E5B7A), Color(0xFF1A0F5E)]),
          image: arteCartao('cidade', opacidade: 0.5),
          boxShadow: const [BoxShadow(color: Color(0x5526C6DA), blurRadius: 14)],
        ),
        child: Row(children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const RadialGradient(colors: [Color(0xFF4FE0F0), Color(0xFF0E6E8A)]),
              border: Border.all(color: Colors.white, width: 2),
              boxShadow: const [BoxShadow(color: Color(0x8826C6DA), blurRadius: 12)],
            ),
            child: const Icon(Icons.public_rounded, color: Colors.white, size: 30),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('CENÁRIO ECONÔMICO', style: TextStyle(fontSize: 15, letterSpacing: 1, fontWeight: FontWeight.w900, color: Colors.white)),
              const SizedBox(height: 2),
              const Text('Juros · Inflação · Dólar · Emprego', style: TextStyle(fontSize: 12, color: Color(0xFFCFF6FB))),
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0x99120850), border: Border.all(color: cor)),
                child: Text('Brasil: $txt', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: cor)),
              ),
            ]),
          ),
          const Icon(Icons.chevron_right_rounded, color: Colors.white, size: 30),
        ]),
      ),
    );
  }

  Widget _erroTela() => Column(children: [
        Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
        TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
      ]);
}
