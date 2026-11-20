import 'dart:convert';

import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'navegacao.dart';

/// Meu Perfil (como no app antigo, perfis_app.pagina_meu_perfil): avatar com raridade, nível e XP, sequência, ranking, moedas e
/// patrimônio, desempenho nos jogos, conquistas, "Sobre mim" e as opções da conta. Editar abre a edição (nome, usuário, bio, avatar,
/// moldura e tema da Loja, privacidade). Dados do servidor (`GET /perfil`); nada de XP, pontos ou conquistas é editável.
class PerfilTela extends StatefulWidget {
  const PerfilTela({super.key, required this.api, this.aoSair});
  final Api api;
  final Future<void> Function()? aoSair;

  @override
  State<PerfilTela> createState() => _PerfilTelaState();
}

const _lilas = Color(0xFFD9D4F7);

/// Imagem de avatar vinda do servidor: arquivo do app ("avatares/x.webp") ou data URI. Sem imagem, o mascote.
Widget imagemAvatar(Object? img, {BoxFit fit = BoxFit.cover}) {
  final mascote = Image.asset('assets/home/mascote_principal.webp', fit: fit);
  final t = img is String && img.isNotEmpty ? img : null;
  if (t == null) return mascote;
  if (t.startsWith('data:')) {
    return Image.memory(base64Decode(t.substring(t.indexOf(',') + 1)), fit: fit, errorBuilder: (_, __, ___) => mascote);
  }
  return Image.asset('assets/$t', fit: fit, errorBuilder: (_, __, ___) => mascote);
}

Color _hex(Object? h, [Color p = const Color(0xFF8B6CFF)]) {
  final s = '${h ?? ''}'.replaceFirst('#', '');
  final v = s.length == 6 ? int.tryParse(s, radix: 16) : null;
  return v == null ? p : Color(0xFF000000 | v);
}

String _milhar(num v) {
  final s = v.abs().round().toString();
  final b = StringBuffer(v < 0 ? '-' : '');
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write('.');
    b.write(s[i]);
  }
  return b.toString();
}

/// Avatar grande no anel da raridade, girando devagar (o brilho da borda dá a volta).
class AvatarRaridade extends StatefulWidget {
  const AvatarRaridade({super.key, required this.img, required this.cor, this.tamanho = 96});
  final Object? img;
  final Color cor;
  final double tamanho;

  @override
  State<AvatarRaridade> createState() => _AvatarRaridadeState();
}

class _AvatarRaridadeState extends State<AvatarRaridade> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 6))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.tamanho;
    return SizedBox(
      width: t,
      height: t,
      child: Stack(alignment: Alignment.center, children: [
        AnimatedBuilder(
          animation: _c,
          builder: (ctx, _) => Transform.rotate(
            angle: _c.value * 6.283,
            child: Container(
              width: t,
              height: t,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: SweepGradient(colors: [widget.cor, Colors.white, widget.cor, widget.cor.withValues(alpha: 0.4), widget.cor]),
                boxShadow: [BoxShadow(color: widget.cor.withValues(alpha: 0.6), blurRadius: 16)],
              ),
            ),
          ),
        ),
        ClipOval(child: SizedBox(width: t - 8, height: t - 8, child: ColoredBox(color: const Color(0xFF1B1545), child: imagemAvatar(widget.img)))),
      ]),
    );
  }
}

class _PerfilTelaState extends State<PerfilTela> {
  Map<String, dynamic>? _d;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/perfil');
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

  Future<void> _editar({bool privacidade = false}) async {
    final d = _d;
    if (d == null) return;
    final mudou = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => EditarPerfilTela(api: widget.api, perfil: d, abrirPrivacidade: privacidade)));
    if (mudou == true) {
      _carregar();
      saldoMudou.value++; // o cabeçalho relê o avatar
    }
  }

  Future<void> _sair() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF16104A),
        title: const Text('Sair da sua conta neste aparelho?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('Sim, sair')),
        ],
      ),
    );
    if (ok == true) await widget.aoSair?.call();
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(fit: StackFit.expand, children: [
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFF0A0A5A), Color(0xFF1C0870), Color(0xFF14054E), Color(0xFF050038)],
              stops: [0, 0.35, 0.7, 1],
            ),
          ),
        ),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(10, 4, 10, 24), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  const Expanded(child: Text('Meu perfil', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Colors.white))),
                  if (d != null)
                    TextButton.icon(
                      onPressed: () => _editar(),
                      icon: const Icon(Icons.edit_rounded, size: 18),
                      label: const Text('Editar'),
                    ),
                ]),
                if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
                if (d == null && _erro != null) _caixa(child: Text(_erro!, style: const TextStyle(color: Colors.white))),
                if (d != null) ...[
                  Entrada(ordem: 0, child: _hero(d)),
                  const SizedBox(height: 10),
                  Entrada(ordem: 1, child: _xp(d)),
                  const SizedBox(height: 10),
                  Entrada(ordem: 2, child: _numeros(d)),
                  const SizedBox(height: 10),
                  Entrada(ordem: 3, child: _desempenho(d)),
                  const SizedBox(height: 10),
                  Entrada(ordem: 4, child: _conquistas(d)),
                  const SizedBox(height: 10),
                  Entrada(ordem: 5, child: _sobre(d)),
                  const SizedBox(height: 10),
                  Entrada(ordem: 6, child: _conta()),
                  const SizedBox(height: 8),
                  const Text('Pontos, vitórias, XP e conquistas vêm dos jogos e da Jornada e não podem ser editados.',
                      textAlign: TextAlign.center, style: TextStyle(fontSize: 11.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _hero(Map d) {
    final rar = (d['raridade'] as Map?) ?? const {};
    final cor = _hex(rar['cor']);
    final nv = (d['nivel'] as Map?) ?? const {};
    final desde = '${d['desde'] ?? ''}';
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 16, 14, 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFF2B84B), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2E1CA0), Color(0xFF140A55)]),
        boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
      ),
      child: Row(children: [
        Stack(clipBehavior: Clip.none, alignment: Alignment.bottomCenter, children: [
          AvatarRaridade(img: d['avatar_img'], cor: cor, tamanho: 96),
          Positioned(
            bottom: -10,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                gradient: const LinearGradient(colors: [Color(0xFFFFE08A), Color(0xFFF2B84B)]),
                border: Border.all(color: const Color(0xFFFFF1B8)),
              ),
              child: Text('Nível ${nv['nivel'] ?? '—'}', style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: Color(0xFF3B2600))),
            ),
          ),
        ]),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${d['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: Colors.white)),
            Text('${d['usuario']}'.isEmpty ? 'Escolha seu nome de usuário em Editar' : '@${d['usuario']}',
                style: const TextStyle(fontSize: 13.5, color: Color(0xFFB59BFF), fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: cor.withValues(alpha: 0.2), border: Border.all(color: cor)),
              child: Text('${rar['nome'] ?? ''} · ${d['avatar_nome'] ?? ''}', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: cor)),
            ),
            const SizedBox(height: 6),
            Text('${d['titulo'] ?? ''} · Aprender. Jogar. Evoluir.', style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic, color: _lilas)),
            if (desde.length >= 10)
              Text('No TickerHunters desde ${desde.substring(8, 10)}/${desde.substring(5, 7)}/${desde.substring(0, 4)}',
                  style: const TextStyle(fontSize: 11.5, color: _lilas)),
          ]),
        ),
      ]),
    );
  }

  Widget _xp(Map d) {
    final nv = (d['nivel'] as Map?) ?? const {};
    final pct = ((nv['pct'] as num?) ?? 0).toDouble().clamp(0.0, 1.0);
    final falta = nv['maximo'] == true ? 'Nível máximo!' : 'faltam ${nv['falta'] ?? '—'} XP para o nível ${((nv['nivel'] as num?) ?? 0) + 1}';
    return _caixa(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.star_rounded, color: Color(0xFFFFC93C)),
          const SizedBox(width: 4),
          Text('${d['xp'] ?? 0} XP', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
          const Spacer(),
          Text(falta, style: const TextStyle(fontSize: 12, color: _lilas)),
        ]),
        const SizedBox(height: 8),
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: pct),
          duration: const Duration(milliseconds: 1200),
          curve: Curves.easeOutCubic,
          builder: (ctx, v, _) => ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: Stack(children: [
              Container(height: 14, color: const Color(0x335B4BD6)),
              FractionallySizedBox(
                widthFactor: v,
                child: Container(height: 14, decoration: const BoxDecoration(gradient: LinearGradient(colors: [Color(0xFF7B2FF7), Color(0xFFB54BFF), Color(0xFFFF6AD5)]))),
              ),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _numeros(Map d) {
    final rk = (d['ranking'] as Map?) ?? const {};
    final pat = d['patrimonio'] as num?;
    Widget item(IconData ic, Color cor, String v, String t) => Expanded(
          child: Column(children: [
            Icon(ic, color: cor, size: 26),
            const SizedBox(height: 2),
            FittedBox(child: Text(v, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white))),
            Text(t, style: const TextStyle(fontSize: 11, color: _lilas)),
          ]),
        );
    Widget sep() => const VerticalDivider(width: 1, thickness: 1, color: Color(0x596A4FE6));
    final of = (d['ofensiva'] as num?)?.toInt() ?? 0;
    return _caixa(
      child: IntrinsicHeight(
        child: Row(children: [
          item(Icons.local_fire_department_rounded, const Color(0xFFFF8A3D), '$of ${of == 1 ? 'dia' : 'dias'}', 'Sequência'),
          sep(),
          item(Icons.emoji_events_rounded, const Color(0xFFFFC93C), rk['pos'] == null ? '—' : '#${rk['pos']}', 'Ranking'),
          sep(),
          item(Icons.toll_rounded, const Color(0xFFF2B84B), d['moedas'] == null ? '—' : _milhar(d['moedas'] as num), 'Ticker Coins'),
          sep(),
          item(Icons.account_balance_wallet_rounded, const Color(0xFF26D07C), pat == null ? '—' : 'T\$ ${_milhar(pat)}', 'Patrimônio'),
        ]),
      ),
    );
  }

  Widget _desempenho(Map d) {
    final es = (d['estat'] as Map?) ?? const {};
    final taxa = (es['taxa'] as num?)?.toDouble();
    final jg = (d['jogos'] as Map?) ?? const {};
    final t = (jg['trade'] as Map?) ?? const {}, k = (jg['ticker'] as Map?) ?? const {};
    String pos(Object? p) => p == null ? '—' : '#$p';
    return _caixa(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Row(children: [
          Icon(Icons.bar_chart_rounded, color: Color(0xFFB59BFF)),
          SizedBox(width: 6),
          Text('Desempenho', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          SizedBox(
            width: 92,
            height: 92,
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: (taxa ?? 0) / 100),
              duration: const Duration(milliseconds: 1300),
              curve: Curves.easeOutCubic,
              builder: (ctx, v, _) => Stack(alignment: Alignment.center, children: [
                SizedBox(
                  width: 86,
                  height: 86,
                  child: CircularProgressIndicator(value: v, strokeWidth: 9, backgroundColor: const Color(0x335B4BD6), color: const Color(0xFF26D07C), strokeCap: StrokeCap.round),
                ),
                Column(mainAxisSize: MainAxisSize.min, children: [
                  Text(taxa == null ? '—' : '${(v * 100).round()}%', style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Colors.white)),
                  const Text('vitórias', style: TextStyle(fontSize: 10, color: _lilas)),
                ]),
              ]),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(children: [
              _linha('Partidas', '${es['partidas'] ?? 0}', Icons.play_arrow_rounded),
              _linha('Vitórias', '${es['vitorias'] ?? 0}', Icons.emoji_events_rounded),
              _linha('Derrotas', '${es['derrotas'] ?? 0}', Icons.close_rounded),
            ]),
          ),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: _jogo('Trade Battle', '${pos(t['posicao'])} · ${(((t['pontos'] as num?) ?? 0) + 0.0).abs() < 0.05 ? '0' : (t['pontos'] as num).toStringAsFixed(1).replaceAll('.', ',')} pts', const Color(0xFF26D07C))),
          const SizedBox(width: 8),
          Expanded(child: _jogo('Ticker Battle', '${pos(k['posicao'])} · ${k['vitorias'] ?? 0} vit.', const Color(0xFF8B6CFF))),
        ]),
      ]),
    );
  }

  Widget _linha(String t, String v, IconData ic) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Icon(ic, size: 18, color: const Color(0xFFB59BFF)),
          const SizedBox(width: 6),
          Expanded(child: Text(t, style: const TextStyle(color: _lilas))),
          Text(v, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        ]),
      );

  Widget _jogo(String nome, String v, Color cor) => Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: cor.withValues(alpha: 0.14), border: Border.all(color: cor)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(nome, style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
          Text(v, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: cor)),
        ]),
      );

  Widget _conquistas(Map d) {
    final c = (d['conquistas'] as Map?) ?? const {};
    final med = ((c['medalhas'] as List?) ?? const []).cast<Map>();
    return _caixa(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.military_tech_rounded, color: Color(0xFFFFC93C)),
          const SizedBox(width: 6),
          const Expanded(child: Text('Conquistas', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white))),
          Text('${c['ok'] ?? 0} de ${c['total'] ?? 0}', style: const TextStyle(fontWeight: FontWeight.w800, color: _lilas)),
        ]),
        const SizedBox(height: 8),
        if (med.isEmpty)
          const Text('Conclua lições na Jornada para ganhar as primeiras medalhas.', style: TextStyle(color: _lilas))
        else
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final (i, m) in med.indexed)
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: 1),
                duration: Duration(milliseconds: 500 + 80 * i.clamp(0, 10)),
                curve: Curves.elasticOut,
                builder: (ctx, v, f) => Transform.scale(scale: v, child: f),
                child: Tooltip(
                  message: '${m['nome']}',
                  child: Container(
                    width: 52,
                    height: 52,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: const RadialGradient(colors: [Color(0xFF3B2A9E), Color(0xFF1B1462)]),
                      border: Border.all(color: const Color(0xFFF2B84B), width: 2),
                      boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 8)],
                    ),
                    child: Text('${m['emblema'] ?? '🏅'}', style: const TextStyle(fontSize: 24)),
                  ),
                ),
              ),
          ]),
      ]),
    );
  }

  Widget _sobre(Map d) {
    final bio = '${d['bio'] ?? ''}';
    return _caixa(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Row(children: [
          Icon(Icons.person_rounded, color: Color(0xFFB59BFF)),
          SizedBox(width: 6),
          Text('Sobre mim', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        ]),
        const SizedBox(height: 6),
        Text(bio.isEmpty ? 'Conte um pouco sobre você em Editar.' : bio, style: TextStyle(color: bio.isEmpty ? _lilas : Colors.white, height: 1.35)),
      ]),
    );
  }

  Widget _conta() {
    Widget op(IconData ic, String t, VoidCallback f, {Color cor = Colors.white}) => Pressionavel(
          aoTocar: f,
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0xFF6A4FE6), width: 1.5),
              gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF2E1CA0), Color(0xFF1C0F78)]),
            ),
            child: Row(children: [
              Icon(ic, color: cor),
              const SizedBox(width: 12),
              Expanded(child: Text(t, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: cor))),
              Icon(Icons.chevron_right_rounded, color: cor),
            ]),
          ),
        );
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Padding(
        padding: EdgeInsets.only(left: 4, bottom: 8, top: 4),
        child: Text('Conta', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
      ),
      op(Icons.edit_rounded, 'Editar perfil', () => _editar()),
      op(Icons.lock_rounded, 'Privacidade', () => _editar(privacidade: true)),
      op(Icons.storefront_rounded, 'Loja Ticker (molduras e temas)', () {
        Navigator.of(context).maybePop();
        abrirAba(4);
      }),
      if (widget.aoSair != null) op(Icons.logout_rounded, 'Sair da conta', _sair, cor: const Color(0xFFFF8FA3)),
    ]);
  }
}

Widget _caixa({required Widget child}) => Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF6A4FE6), width: 2),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF231388), Color(0xFF160B5E)]),
        boxShadow: const [BoxShadow(color: Color(0x556A4FE6), blurRadius: 12)],
      ),
      child: child,
    );

/// Editar perfil: nome, nome de usuário, bio, avatar (Coleção de Avatares), moldura e tema da Loja e privacidade. Nada é gravado até Salvar.
class EditarPerfilTela extends StatefulWidget {
  const EditarPerfilTela({super.key, required this.api, required this.perfil, this.abrirPrivacidade = false});
  final Api api;
  final Map<String, dynamic> perfil;
  final bool abrirPrivacidade;

  @override
  State<EditarPerfilTela> createState() => _EditarPerfilTelaState();
}

class _EditarPerfilTelaState extends State<EditarPerfilTela> {
  late final _nome = TextEditingController(text: '${widget.perfil['nome'] ?? ''}');
  late final _usuario = TextEditingController(text: '${widget.perfil['usuario'] ?? ''}');
  late final _bio = TextEditingController(text: '${widget.perfil['bio'] ?? ''}');
  late String _avatar = '${widget.perfil['avatar']}';
  late Object? _avatarImg = widget.perfil['avatar_img'];
  late final Map<String, dynamic> _priv = Map<String, dynamic>.from((widget.perfil['privacidade'] as Map?) ?? const {});
  late String? _moldura = (widget.perfil['moldura'] as Map?)?['equipado'] as String?;
  late String? _tema = (widget.perfil['tema'] as Map?)?['equipado'] as String?;
  Map<String, dynamic>? _col;
  String _filtro = 'todos';
  bool _salvando = false;
  String _erro = '';
  final _rolagem = ScrollController();
  final _chavePriv = GlobalKey();

  @override
  void initState() {
    super.initState();
    widget.api.get('/perfil/avatares').then((r) {
      if (mounted) setState(() => _col = r);
    }).catchError((_) {});
    if (widget.abrirPrivacidade) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final c = _chavePriv.currentContext;
        if (c != null) Scrollable.ensureVisible(c, duration: const Duration(milliseconds: 500));
      });
    }
  }

  @override
  void dispose() {
    _nome.dispose();
    _usuario.dispose();
    _bio.dispose();
    _rolagem.dispose();
    super.dispose();
  }

  Future<void> _salvar() async {
    setState(() {
      _salvando = true;
      _erro = '';
    });
    try {
      final p = widget.perfil;
      final corpo = <String, dynamic>{
        if (_nome.text.trim() != '${p['nome'] ?? ''}') 'nome': _nome.text.trim(),
        if (_usuario.text.trim() != '${p['usuario'] ?? ''}') 'usuario': _usuario.text.trim(),
        if (_bio.text.trim() != '${p['bio'] ?? ''}') 'bio': _bio.text.trim(),
        if (_avatar != '${p['avatar']}') 'avatar': _avatar,
        'privacidade': _priv,
      };
      await widget.api.post('/perfil', corpo);
      for (final (tipo, novo) in [('moldura', _moldura), ('tema', _tema)]) {
        if (novo != (widget.perfil[tipo] as Map?)?['equipado']) await widget.api.post('/loja/equipar', {'pid': novo, 'tipo': tipo});
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Perfil atualizado!')));
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rarCor = _hex(((_col?['itens'] as List?)?.cast<Map>().firstWhere((a) => a['id'] == _avatar, orElse: () => const {}) ?? const {})['cor'],
        _hex((widget.perfil['raridade'] as Map?)?['cor']));
    return Scaffold(
      backgroundColor: const Color(0xFF110C3A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF110C3A),
        title: const Text('Editar perfil', style: TextStyle(fontWeight: FontWeight.w900)),
        actions: [
          TextButton(onPressed: _salvando ? null : _salvar, child: const Text('Salvar', style: TextStyle(fontWeight: FontWeight.w900))),
        ],
      ),
      body: ListView(controller: _rolagem, padding: const EdgeInsets.fromLTRB(14, 8, 14, 30), children: [
        Center(child: AvatarRaridade(img: _avatarImg, cor: rarCor, tamanho: 110)),
        const SizedBox(height: 14),
        _campo('Nome de exibição', _nome, max: 30),
        _campo('Nome de usuário (@)', _usuario, max: 20, ajuda: 'Único no app. Dá para trocar uma vez a cada 7 dias.'),
        _campo('Bio', _bio, max: 160, linhas: 3),
        const SizedBox(height: 6),
        _titulo('Coleção de avatares', _col == null ? '' : '${_col!['liberados']} de ${_col!['total']} liberados'),
        _colecao(),
        const SizedBox(height: 14),
        _titulo('Moldura e tema (da Loja)', ''),
        _itensLoja('moldura', 'Moldura', _moldura, (v) => setState(() => _moldura = v)),
        const SizedBox(height: 8),
        _itensLoja('tema', 'Tema do app', _tema, (v) => setState(() => _tema = v)),
        const SizedBox(height: 14),
        KeyedSubtree(key: _chavePriv, child: _titulo('Privacidade', '')),
        _privacidade(),
        if (_erro.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_erro, style: const TextStyle(color: Color(0xFFFF8FA3), fontWeight: FontWeight.w700))),
        const SizedBox(height: 16),
        SizedBox(
          height: 52,
          child: FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
            onPressed: _salvando ? null : _salvar,
            icon: _salvando ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white)) : const Icon(Icons.check_rounded),
            label: const Text('Salvar perfil'),
          ),
        ),
      ]),
    );
  }

  Widget _titulo(String t, String s) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(children: [
          Expanded(child: Text(t, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white))),
          Text(s, style: const TextStyle(color: _lilas)),
        ]),
      );

  Widget _campo(String rot, TextEditingController c, {int max = 30, int linhas = 1, String? ajuda}) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: TextField(
          controller: c,
          maxLength: max,
          maxLines: linhas,
          decoration: InputDecoration(
            labelText: rot,
            helperText: ajuda,
            filled: true,
            fillColor: const Color(0xFF1B1462),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
          ),
        ),
      );

  Widget _colecao() {
    final c = _col;
    if (c == null) return const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator()));
    final rar = (c['raridades'] as Map?) ?? const {};
    final itens = ((c['itens'] as List?) ?? const []).cast<Map>().where((a) => _filtro == 'todos' || a['raridade'] == _filtro).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SizedBox(
        height: 38,
        child: ListView(scrollDirection: Axis.horizontal, children: [
          for (final (k, nome, cor) in [
            ('todos', 'Todos', const Color(0xFF8B6CFF)),
            for (final e in rar.entries) ('${e.key}', '${(e.value as Map)['nome']} ${(e.value as Map)['ok']}/${(e.value as Map)['total']}', _hex((e.value as Map)['cor'])),
          ])
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: ChoiceChip(
                label: Text(nome),
                selected: _filtro == k,
                selectedColor: cor.withValues(alpha: 0.35),
                side: BorderSide(color: cor),
                onSelected: (_) => setState(() => _filtro = k),
              ),
            ),
        ]),
      ),
      const SizedBox(height: 10),
      LayoutBuilder(builder: (ctx, cc) {
        final n = cc.maxWidth >= 560 ? 6 : 4;
        final w = (cc.maxWidth - 8 * (n - 1)) / n;
        return Wrap(spacing: 8, runSpacing: 10, children: [
          for (final a in itens)
            SizedBox(
              width: w,
              child: Pressionavel(
                aoTocar: a['liberado'] == true
                    ? () => setState(() {
                          _avatar = '${a['id']}';
                          _avatarImg = a['img'];
                        })
                    : () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('🔒 ${a['nome']}: ${a['como']}'))),
                child: Column(children: [
                  Stack(alignment: Alignment.center, children: [
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: w - 6,
                      height: w - 6,
                      padding: const EdgeInsets.all(3),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _hex(a['cor']),
                        boxShadow: _avatar == a['id'] ? [BoxShadow(color: _hex(a['cor']), blurRadius: 14, spreadRadius: 2)] : null,
                      ),
                      child: ClipOval(
                        child: ColorFiltered(
                          colorFilter: a['liberado'] == true
                              ? const ColorFilter.mode(Colors.transparent, BlendMode.dst)
                              : const ColorFilter.matrix([0.2, 0.2, 0.2, 0, 0, 0.2, 0.2, 0.2, 0, 0, 0.2, 0.2, 0.2, 0, 0, 0, 0, 0, 1, 0]),
                          child: ColoredBox(color: const Color(0xFF1B1545), child: imagemAvatar(a['img'])),
                        ),
                      ),
                    ),
                    if (a['liberado'] != true) const Icon(Icons.lock_rounded, color: Colors.white70),
                    if (_avatar == a['id'])
                      Positioned(
                        right: 0,
                        top: 0,
                        child: Container(
                          width: 22,
                          height: 22,
                          decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFF26D07C), border: Border.all(color: Colors.white, width: 2)),
                          child: const Icon(Icons.check, size: 13, color: Colors.white),
                        ),
                      ),
                  ]),
                  const SizedBox(height: 3),
                  Text('${a['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 11, color: a['liberado'] == true ? Colors.white : _lilas)),
                ]),
              ),
            ),
        ]);
      }),
    ]);
  }

  Widget _itensLoja(String tipo, String rot, String? atual, ValueChanged<String?> f) {
    final itens = (((widget.perfil[tipo] as Map?)?['itens'] as List?) ?? const []).cast<Map>();
    if (itens.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0xFF1B1462), border: Border.all(color: const Color(0x666A4FE6))),
        child: Text('$rot: você ainda não tem. Troque seus Ticker Coins na Loja.', style: const TextStyle(color: _lilas)),
      );
    }
    return DropdownButtonFormField<String?>(
      initialValue: itens.any((i) => i['id'] == atual) ? atual : null,
      decoration: InputDecoration(labelText: rot, filled: true, fillColor: const Color(0xFF1B1462), border: OutlineInputBorder(borderRadius: BorderRadius.circular(14))),
      dropdownColor: const Color(0xFF1B1462),
      items: [
        const DropdownMenuItem(value: null, child: Text('Nenhum')),
        for (final i in itens) DropdownMenuItem(value: '${i['id']}', child: Text('${i['nome']}')),
      ],
      onChanged: f,
    );
  }

  Widget _privacidade() {
    final op = (widget.perfil['opcoes'] as Map?) ?? const {};
    final vis = (op['visivel'] as Map?) ?? const {}, ped = (op['pedidos'] as Map?) ?? const {};
    Widget sw(String k, String t) => SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(t, style: const TextStyle(color: Colors.white)),
          value: _priv[k] != false,
          onChanged: (v) => setState(() => _priv[k] = v),
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xFF1B1462), border: Border.all(color: const Color(0x666A4FE6))),
      child: Column(children: [
        DropdownButtonFormField<String>(
          initialValue: vis.containsKey(_priv['visivel']) ? '${_priv['visivel']}' : null,
          decoration: const InputDecoration(labelText: 'Quem vê meu perfil'),
          dropdownColor: const Color(0xFF1B1462),
          items: [for (final e in vis.entries) DropdownMenuItem(value: '${e.key}', child: Text('${e.value}'))],
          onChanged: (v) => setState(() => _priv['visivel'] = v),
        ),
        DropdownButtonFormField<String>(
          initialValue: ped.containsKey(_priv['pedidos']) ? '${_priv['pedidos']}' : null,
          decoration: const InputDecoration(labelText: 'Quem pode me pedir amizade'),
          dropdownColor: const Color(0xFF1B1462),
          items: [for (final e in ped.entries) DropdownMenuItem(value: '${e.key}', child: Text('${e.value}'))],
          onChanged: (v) => setState(() => _priv['pedidos'] = v),
        ),
        sw('mostrar_bio', 'Mostrar minha bio'),
        sw('mostrar_nivel', 'Mostrar nível e XP'),
        sw('mostrar_conquistas', 'Mostrar conquistas'),
        sw('mostrar_jogos', 'Mostrar desempenho nos jogos'),
        sw('mostrar_historico', 'Mostrar últimas partidas'),
      ]),
    );
  }
}
