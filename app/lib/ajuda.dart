import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';

/// Central de Ajuda (atalho da aba Jogos): perguntas frequentes sobre cada parte do app novo e o glossário de termos do mercado
/// (o mesmo glossário central do app antigo, vindo do servidor). Uma busca filtra as perguntas e os termos ao mesmo tempo.
class AjudaTela extends StatefulWidget {
  const AjudaTela({super.key, required this.api});
  final Api api;

  @override
  State<AjudaTela> createState() => _AjudaTelaState();
}

const _lilas = Color(0xFFD4E2F7);

// (seção, ícone, cor, arte, [(pergunta, resposta)])
const _faq = [
  (
    'Começando',
    Icons.rocket_launch_rounded,
    Color(0xFF6CA3FF),
    'velas',
    [
      (
        'O que é o TickerHunters?',
        'Um jogo para aprender a investir: você estuda no Aprender, treina nos jogos e monta uma carteira virtual, tudo com dinheiro de mentira (T\$) e dados reais do mercado.'
      ),
      ('O que são Ticker Coins (TC)?', 'A moeda do jogo. Você ganha estudando, jogando e cumprindo missões, e usa na Loja para comprar temas e molduras. TC não é dinheiro de verdade.'),
      ('Como subo de nível?', 'Ganhando XP: cada lição, revisão, missão e partida dá XP. A barra do nível fica no topo da tela e no seu Perfil.'),
      ('O que é o Hunter Pass?', 'O passe da temporada (um mês). Cada marco de XP que você atinge libera um símbolo ou título para o seu perfil. Ele aparece na tela inicial e em Eventos.'),
    ]
  ),
  (
    'Jogos',
    Icons.sports_esports_rounded,
    Color(0xFF26D07C),
    'arena',
    [
      (
        'Como funciona o Trade Battle?',
        'Você recebe um gráfico real sem saber qual é o ativo, monta a sua estratégia (pode desenhar no gráfico) e opera enquanto o tempo passa. No fim, o ativo e as datas são revelados.'
      ),
      (
        'Como a nota do Trade Battle é calculada?',
        '70% vem da operação (resultado e controle de risco) e 30% da sua leitura do gráfico, quando você desenha suportes, resistências e alvos. Desenhar é opcional.'
      ),
      (
        'Como funciona o Ticker Battle?',
        'Você monta um baralho de 3 a 10 cartas de empresas. Em cada rodada, escolhe uma carta e um dos 5 indicadores; vence quem tiver o melhor número. É melhor de 3.'
      ),
      ('Quais partidas contam para o ranking?', 'Só as online (contra outras pessoas). As partidas contra o sistema são treino: aparecem no seu Histórico de partidas, mas não mudam o ranking.'),
    ]
  ),
  (
    'Aprender',
    Icons.menu_book_rounded,
    Color(0xFF2BA7C9),
    'cidade',
    [
      ('Como funciona a trilha?', 'São unidades com lições curtas. Nada fica trancado: você pode fazer na ordem que quiser. A próxima lição recomendada pisca com "COMEÇAR".'),
      ('E se eu errar uma pergunta?', 'Ela volta no fim da lição e vai para a Revisão. Não há vidas: errar faz parte de aprender.'),
      ('O que é a sequência (ofensiva)?', 'Quantos dias seguidos você estudou. Estude um pouco todo dia para não perder a sequência.'),
    ]
  ),
  (
    'Carteira e Mercado',
    Icons.account_balance_wallet_rounded,
    Color(0xFFF2B84B),
    'moedas',
    [
      ('O que é a Carteira?', 'Uma carteira virtual com T\$ para você comprar e vender ativos reais, ao preço real, e acompanhar o resultado. As missões da carteira dão XP, TC e mais capital.'),
      ('O que mostra o Mercado?', 'Como estão Ibovespa, dólar e bitcoin hoje, e a leitura de cada ação (preço justo, saúde e dividendos) ou criptomoeda (tendência, risco e diluição).'),
      ('O que é o preço justo?', 'Uma estimativa de quanto a ação vale pelos métodos de Graham (lucro e patrimônio) e Bazin (dividendos). É um ponto de partida para estudar, não uma garantia.'),
      ('O que é o Cenário econômico?', 'Um resumo de juros, inflação, dólar e emprego no Brasil, com os setores que tendem a ganhar ou sofrer nesse ambiente.'),
    ]
  ),
  (
    'Loja e perfil',
    Icons.storefront_rounded,
    Color(0xFFFF6B8A),
    'loja',
    [
      ('O que tem na Loja?', 'Temas e molduras para o seu perfil, comprados com TC, e o baú diário com TC de presente.'),
      ('Como troco meu avatar ou nome?', 'Toque no seu avatar no topo da tela, abra o Perfil e toque em Editar. O nome de usuário pode ser trocado de novo depois de 7 dias.'),
    ]
  ),
  (
    'Segurança',
    Icons.verified_user_rounded,
    Color(0xFF4F9BFF),
    'cofre',
    [
      ('O app recomenda investimentos?', 'Não. Tudo aqui é educativo: as leituras explicam os números, mas nunca dizem para comprar ou vender.'),
      ('De onde vêm os dados?', 'De fontes públicas: B3 (via Yahoo e Fundamentus), CoinGecko, Banco Central e IBGE. Às vezes uma fonte demora; tente de novo em instantes.'),
    ]
  ),
];

class _AjudaTelaState extends State<AjudaTela> {
  final _busca = TextEditingController();
  List<Map>? _termos;
  String _q = '';
  String? _aberto;

  @override
  void initState() {
    super.initState();
    widget.api.get('/ajuda/glossario').then((r) {
      if (mounted) setState(() => _termos = ((r['termos'] as List?) ?? const []).cast<Map>());
    }).catchError((_) {
      if (mounted) setState(() => _termos = const []);
    });
  }

  @override
  void dispose() {
    _busca.dispose();
    super.dispose();
  }

  String _sem(String s) {
    const de = 'áàâãäéèêëíìîïóòôõöúùûüç', para = 'aaaaaeeeeiiiiooooouuuuc';
    final b = StringBuffer();
    for (final ch in s.toLowerCase().split('')) {
      final i = de.indexOf(ch);
      b.write(i >= 0 ? para[i] : ch);
    }
    return b.toString();
  }

  bool _bate(String t) => _q.isEmpty || _sem(t).contains(_sem(_q));

  @override
  Widget build(BuildContext context) {
    final termos = (_termos ?? const <Map>[]).where((t) => _bate('${t['termo']} ${t['oque']}')).toList();
    var ordem = 0;
    return Scaffold(
      backgroundColor: const Color(0xFF0A2755),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
              Row(children: [
                IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                const Expanded(child: Text('Central de Ajuda', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
              ]),
              Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  color: const Color(0xE60B2C5E),
                  border: Border.all(color: const Color(0xFF6CA3FF), width: 1.6),
                ),
                child: TextField(
                  controller: _busca,
                  onChanged: (t) => setState(() => _q = t.trim()),
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(vertical: 14),
                    prefixIcon: Icon(Icons.search_rounded, color: Color(0xFF9BBFFF)),
                    hintText: 'Busque: ranking, preço justo, P/L…',
                    hintStyle: TextStyle(color: Color(0xFF93ADD6), fontWeight: FontWeight.w500),
                  ),
                ),
              ),
              for (final (secao, ic, cor, arte, perguntas) in _faq)
                if (perguntas.any((p) => _bate('${p.$1} ${p.$2}'))) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
                    child: Row(children: [
                      Icon(ic, color: cor, size: 20),
                      const SizedBox(width: 6),
                      Text(secao, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
                    ]),
                  ),
                  Entrada(
                    ordem: ordem++,
                    child: Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: cor.withValues(alpha: 0.9), width: 1.6),
                        gradient: LinearGradient(
                            begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(cor, const Color(0xFF0B2C5E), 0.5)!, Color.lerp(cor, const Color(0xFF082450), 0.8)!]),
                        image: arteCartao(arte, opacidade: 0.35),
                      ),
                      child: Column(children: [
                        for (final (i, p) in perguntas.where((p) => _bate('${p.$1} ${p.$2}')).indexed) ...[
                          if (i > 0) const Divider(height: 1, color: Color(0x33FFFFFF)),
                          _pergunta(p.$1, p.$2),
                        ],
                      ]),
                    ),
                  ),
                ],
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
                child: Row(children: [
                  const Icon(Icons.translate_rounded, color: Color(0xFFFFD27A), size: 20),
                  const SizedBox(width: 6),
                  const Expanded(child: Text('Glossário do investidor', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
                  if (_termos != null) Text('${termos.length} termos', style: const TextStyle(fontSize: 12, color: _lilas)),
                ]),
              ),
              if (_termos == null) const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator())),
              if (_termos != null && termos.isEmpty) const Text('Nenhum termo encontrado.', style: TextStyle(color: _lilas)),
              for (final t in termos) _termo(t),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _pergunta(String p, String r) {
    final aberto = _aberto == p || _q.isNotEmpty;
    return InkWell(
      onTap: () => setState(() => _aberto = _aberto == p ? null : p),
      child: AnimatedSize(
        duration: const Duration(milliseconds: 250),
        alignment: Alignment.topCenter,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(p, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w900, color: Colors.white))),
              Icon(aberto ? Icons.expand_less_rounded : Icons.expand_more_rounded, color: Colors.white),
            ]),
            if (aberto) Padding(padding: const EdgeInsets.only(top: 6), child: Text(r, style: const TextStyle(fontSize: 13, height: 1.35, color: Color(0xFFEDF4FF)))),
          ]),
        ),
      ),
    );
  }

  Widget _termo(Map t) {
    final id = 'g_${t['termo']}';
    final aberto = _aberto == id;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Pressionavel(
        aoTocar: () => setState(() => _aberto = aberto ? null : id),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            color: const Color(0xD9103570),
            border: Border.all(color: aberto ? const Color(0xFFFFD27A) : const Color(0xFF4F88E6), width: 1.4),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text('${t['termo']}', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Color(0xFFFFE08A)))),
              Icon(aberto ? Icons.expand_less_rounded : Icons.expand_more_rounded, color: Colors.white, size: 20),
            ]),
            Text('${t['oque']}', style: const TextStyle(fontSize: 12.5, color: Colors.white)),
            if (aberto) Padding(padding: const EdgeInsets.only(top: 4), child: Text('Para que serve: ${t['pra_que']}', style: const TextStyle(fontSize: 12.5, color: Color(0xFFB8F5D6)))),
          ]),
        ),
      ),
    );
  }
}
