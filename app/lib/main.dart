import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'abertura.dart';
import 'api.dart';
import 'config.dart';
import 'diag/diag.dart';
import 'diag/diag_tela.dart';
import 'login.dart';
import 'navegacao.dart';
import 'tour.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (kDiag) await Diag.iniciar(); // APK de diagnóstico: mede abertura, quadros e memória (no app normal não roda)
  final configurado = supabaseUrl.isNotEmpty && supabaseKey.isNotEmpty;
  if (configurado) {
    await Supabase.initialize(url: supabaseUrl, anonKey: supabaseKey);
  }
  runApp(TickerHuntersApp(configurado: configurado));
}

class TickerHuntersApp extends StatelessWidget {
  const TickerHuntersApp({super.key, required this.configurado});
  final bool configurado;

  @override
  Widget build(BuildContext context) {
    const azul = Color(0xFF3B7BFF);
    const fundo = Color(0xFF0A1638);
    return MaterialApp(
      title: 'TickerHunters',
      navigatorKey: kDiag ? diagNavKey : null,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: fundo,
        colorScheme: ColorScheme.fromSeed(seedColor: azul, brightness: Brightness.dark, surface: fundo),
        // mesma letra do app antigo (Source Sans, a fonte padrão do Streamlit)
        textTheme: GoogleFonts.sourceSans3TextTheme(ThemeData(brightness: Brightness.dark).textTheme),
      ),
      home: configurado ? const AberturaTela(depois: PortaDeEntrada()) : const _SemConfiguracao(),
      // tour guiado do primeiro acesso: fica por cima de tudo (inclusive das telas cheias, como a lição)
      builder: (context, child) => Stack(children: [child ?? const SizedBox.shrink(), const TourCamada(), if (kDiag) const DiagAlca()]),
    );
  }
}

/// Mostra o login enquanto não há sessão, e o app (Home e barra de baixo) quando há. Troca sozinha ao entrar ou sair.
class PortaDeEntrada extends StatelessWidget {
  const PortaDeEntrada({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<AuthState>(
      stream: Supabase.instance.client.auth.onAuthStateChange,
      builder: (context, _) {
        final sessao = Supabase.instance.client.auth.currentSession;
        if (sessao == null) return const LoginTela();
        final api = Api(tokenAtual: () => Supabase.instance.client.auth.currentSession?.accessToken);
        return Principal(api: api);
      },
    );
  }
}

class _SemConfiguracao extends StatelessWidget {
  const _SemConfiguracao();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Padding(padding: EdgeInsets.all(24), child: Text('App sem configuração do Supabase. Avise o administrador.', textAlign: TextAlign.center))),
    );
  }
}
