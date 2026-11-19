import 'package:flutter/material.dart';

import 'api.dart';
import 'home.dart';

void main() {
  runApp(const TickerHuntersApp());
}

class TickerHuntersApp extends StatelessWidget {
  const TickerHuntersApp({super.key});

  @override
  Widget build(BuildContext context) {
    const roxo = Color(0xFF7A5CFF);
    const fundo = Color(0xFF0B0828);
    return MaterialApp(
      title: 'TickerHunters',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: fundo,
        colorScheme: ColorScheme.fromSeed(seedColor: roxo, brightness: Brightness.dark, surface: fundo),
      ),
      home: HomeTela(api: Api()),
    );
  }
}
