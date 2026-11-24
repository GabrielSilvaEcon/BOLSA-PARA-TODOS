import 'package:flutter/material.dart';

/// Ilustrações de fundo dos cartões (recortes das artes do app em assets/cards/): a arte fica encostada à direita, na altura do
/// cartão, e meio apagada, para o texto à esquerda continuar legível. Assim nenhum cartão fica "liso".
const artesCartao = ['velas', 'moedas', 'cidade', 'touro', 'seta', 'cofre', 'arena', 'loja'];

DecorationImage arteCartao(String nome, {double opacidade = 0.45}) => DecorationImage(
      image: AssetImage('assets/cards/$nome.webp'),
      fit: BoxFit.fitHeight,
      alignment: Alignment.centerRight,
      opacity: opacidade,
    );

/// Uma arte fixa para cada texto (o mesmo setor ou indicador sempre com a mesma ilustração).
String arteDe(String chave) => artesCartao[chave.codeUnits.fold<int>(0, (a, b) => a + b) % artesCartao.length];
