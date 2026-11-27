import 'som.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'aprender.dart' show FundoCidade;
import 'api.dart';

const _lilas = Color(0xFFD4E2F7);
const _verde = Color(0xFF26D07C);
const _vermelho = Color(0xFFFF5A7A);
const _ouro = Color(0xFFF2B84B);
const _azul = Color(0xFF4F9BFF);

/// Ações de segurança que dependem do Supabase (login do app). Em teste entram versões falsas.
class SegurancaConta {
  const SegurancaConta({this.alterarSenha = _alterarSenha, this.sairOutros = _sairOutros, this.entraComSenha = _entraComSenha});
  final Future<void> Function(String nova) alterarSenha;
  final Future<void> Function() sairOutros;
  final bool Function() entraComSenha;

  static Future<void> _alterarSenha(String nova) async {
    await Supabase.instance.client.auth.updateUser(UserAttributes(password: nova));
  }

  static Future<void> _sairOutros() async {
    await Supabase.instance.client.auth.signOut(scope: SignOutScope.others);
  }

  static bool _entraComSenha() {
    try {
      final u = Supabase.instance.client.auth.currentUser;
      final provs = (u?.appMetadata['providers'] as List?)?.map((e) => '$e').toList() ?? [u?.appMetadata['provider']?.toString() ?? ''];
      return provs.contains('email');
    } catch (_) {
      return false;
    }
  }
}

/// Minha conta no app: dados da conta (e nome), segurança (senha e outros aparelhos), atividades e cópia dos dados.
/// Preferências de exibição e painel do Streamlit não entram: o app novo ainda não usa essas configurações.
class ContaTela extends StatefulWidget {
  const ContaTela({super.key, required this.api, this.seguranca = const SegurancaConta()});
  final Api api;
  final SegurancaConta seguranca;

  @override
  State<ContaTela> createState() => _ContaTelaState();
}

class _ContaTelaState extends State<ContaTela> {
  Map<String, dynamic>? _c;
  List<Map> _atividades = const [];
  String? _erro;
  bool _ocupado = false;
  final _nome = TextEditingController();
  final _nova = TextEditingController();
  final _conf = TextEditingController();

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  @override
  void dispose() {
    _nome.dispose();
    _nova.dispose();
    _conf.dispose();
    super.dispose();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/conta');
      List<Map> ativ = const [];
      try {
        ativ = ((await widget.api.get('/conta/atividades'))['itens'] as List).whereType<Map>().toList();
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _c = r;
        _atividades = ativ;
        _erro = null;
        if (_nome.text.isEmpty) _nome.text = '${r['nome'] ?? ''}';
      });
    } catch (e) {
      if (mounted) setState(() => _erro = '$e');
    }
  }

  void _aviso(String t, {bool erro = false}) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t), backgroundColor: erro ? _vermelho : null));

  Future<void> _roda(Future<void> Function() f) async {
    if (_ocupado) return;
    setState(() => _ocupado = true);
    try {
      await f();
    } catch (e) {
      _aviso('$e', erro: true);
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _salvarNome() => _roda(() async {
        final r = await widget.api.post('/conta/nome', {'nome': _nome.text.trim()});
        _aviso('${r['msg'] ?? 'Nome atualizado.'}');
        await _carregar();
      });

  Future<void> _trocarSenha() => _roda(() async {
        final n = _nova.text, c = _conf.text;
        if (n.length < 8) throw 'A nova senha precisa ter pelo menos 8 caracteres.';
        if (n != c) throw 'As senhas não são iguais.';
        await widget.seguranca.alterarSenha(n);
        _nova.clear();
        _conf.clear();
        _aviso('Senha alterada.');
      });

  Future<void> _sairOutros() => _roda(() async {
        await widget.seguranca.sairOutros();
        _aviso('Os outros aparelhos foram desconectados.');
      });

  Future<void> _copiarDados() => _roda(() async {
        final r = await widget.api.get('/conta/dados');
        await Clipboard.setData(ClipboardData(text: '${r['json']}'));
        _aviso('Seus dados foram copiados. Cole numa conversa ou nota para guardar.');
        await _carregar();
      });

  Widget _caixa(String titulo, IconData ic, Color cor, List<Widget> filhos) => Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), color: const Color(0xFF10274A).withValues(alpha: 0.92), border: Border.all(color: cor, width: 1.6)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(ic, color: cor, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text(titulo, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white))),
          ]),
          const SizedBox(height: 10),
          ...filhos,
        ]),
      );

  Widget _linha(String r, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 110, child: Text(r, style: const TextStyle(color: _lilas, fontSize: 13))),
          Expanded(child: Text(v.isEmpty ? '—' : v, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14))),
        ]),
      );

  InputDecoration _campo(String rot) => InputDecoration(
        labelText: rot,
        labelStyle: const TextStyle(color: _lilas),
        filled: true,
        fillColor: Colors.white.withValues(alpha: 0.08),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      );

  String _provedor(String p) => {'google': 'Google', 'senha': 'E-mail e senha', 'ambos': 'Google e senha'}[p] ?? p;

  String _data(String iso) => iso.length >= 10 ? '${iso.substring(8, 10)}/${iso.substring(5, 7)}/${iso.substring(0, 4)}' : iso;

  @override
  Widget build(BuildContext context) {
    final c = _c;
    final senha = widget.seguranca.entraComSenha();
    return Scaffold(
      backgroundColor: const Color(0xFF0A1A45),
      appBar: AppBar(title: const Text('Minha conta', style: TextStyle(fontWeight: FontWeight.w900)), backgroundColor: Colors.transparent, foregroundColor: Colors.white),
      extendBodyBehindAppBar: true,
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        SafeArea(
          child: c == null
              ? Center(
                  child: _erro != null
                      ? Column(mainAxisSize: MainAxisSize.min, children: [Text(_erro!, style: const TextStyle(color: Colors.white), textAlign: TextAlign.center), const SizedBox(height: 8), OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo'))])
                      : const CircularProgressIndicator(),
                )
              : ListView(padding: const EdgeInsets.fromLTRB(16, 56, 16, 28), children: [
                  _caixa('Dados da conta', Icons.badge_rounded, _azul, [
                    _linha('E-mail', '${c['email']}'),
                    _linha('Cadastro', _data('${c['cadastro'] ?? ''}')),
                    _linha('Entra com', _provedor('${c['provedor'] ?? ''}')),
                    _linha('Tipo de conta', '${c['tipo'] ?? ''}'),
                    _linha('E-mail confirmado', c['email_verificado'] == true ? 'Sim' : 'Não'),
                    const SizedBox(height: 10),
                    TextField(controller: _nome, maxLength: 60, style: const TextStyle(color: Colors.white), decoration: _campo('Nome')),
                    const Text('O e-mail identifica a conta e não pode ser trocado.', style: TextStyle(color: _lilas, fontSize: 12)),
                    const SizedBox(height: 8),
                    FilledButton(onPressed: _ocupado ? null : _salvarNome, child: const Text('Salvar nome')),
                  ]),
                  _caixa('Segurança', Icons.lock_rounded, _verde, [
                    if (senha) ...[
                      const Text('Alterar senha', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                      const SizedBox(height: 8),
                      TextField(controller: _nova, obscureText: true, style: const TextStyle(color: Colors.white), decoration: _campo('Nova senha (mínimo 8 caracteres)')),
                      const SizedBox(height: 8),
                      TextField(controller: _conf, obscureText: true, style: const TextStyle(color: Colors.white), decoration: _campo('Repita a nova senha')),
                      const SizedBox(height: 8),
                      FilledButton(onPressed: _ocupado ? null : _trocarSenha, child: const Text('Alterar senha')),
                      const SizedBox(height: 12),
                    ] else
                      const Padding(padding: EdgeInsets.only(bottom: 10), child: Text('Você entra com o Google: a senha e a verificação são gerenciadas pela sua conta Google.', style: TextStyle(color: _lilas))),
                    OutlinedButton.icon(onPressed: _ocupado ? null : _sairOutros, icon: const Icon(Icons.devices_other_rounded), label: const Text('Desconectar os outros aparelhos')),
                  ]),
                  _caixa('Som', Icons.volume_up_rounded, _azul, [
                    ValueListenableBuilder<bool>(
                      valueListenable: Som.ligado,
                      builder: (_, on, __) => Row(children: [
                        const Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('Efeitos sonoros', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                            Text('Toques e resultado da partida.', style: TextStyle(color: _lilas, fontSize: 12)),
                          ]),
                        ),
                        Switch(value: on, onChanged: Som.definir),
                      ]),
                    ),
                  ]),
                  _caixa('Atividades da conta', Icons.history_rounded, _ouro, [
                    if (_atividades.isEmpty)
                      const Text('Ainda não há atividades registradas.', style: TextStyle(color: _lilas))
                    else
                      for (final a in _atividades.take(15))
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Row(children: [
                            Expanded(child: Text('${a['rotulo']}', style: TextStyle(color: a['tom'] == 'erro' ? _vermelho : Colors.white, fontWeight: FontWeight.w700))),
                            Text('${a['quando']}'.replaceFirst('T', ' '), style: const TextStyle(color: _lilas, fontSize: 12)),
                          ]),
                        ),
                  ]),
                  _caixa('Privacidade e seus dados', Icons.shield_rounded, const Color(0xFF8B6CFF), [
                    const Text('Guardamos só o necessário: nome e e-mail para identificar você, seus dados do jogo (visíveis só para você, nem a administração vê) e registros de segurança. Sua senha nunca fica em texto.', style: TextStyle(color: _lilas, fontSize: 13)),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(onPressed: _ocupado ? null : _copiarDados, icon: const Icon(Icons.copy_rounded), label: const Text('Copiar meus dados')),
                  ]),
                ]),
        ),
      ]),
    );
  }
}
