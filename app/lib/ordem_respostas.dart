/// Guarda a ordem das respostas do servidor numa partida.
///
/// Os pedidos saem do app por dois caminhos ao mesmo tempo: o relógio consulta o estado a cada
/// segundo e as jogadas (confirmar a estratégia, operar) mandam o seu próprio pedido. O servidor
/// atende cada um quando chega, então um GET do relógio disparado ANTES de uma confirmação pode
/// ser atendido antes dela e só chegar de volta depois — trazendo o retrato anterior à jogada.
/// Aplicado assim, ele desfaz na tela o que a jogada acabou de mudar.
///
/// Cada pedido leva um número crescente; a resposta de um pedido mais velho que o último já
/// aplicado é descartada.
class OrdemRespostas {
  int _proximo = 0;
  int _aplicado = -1;

  /// Número do pedido que está saindo agora.
  int novo() => _proximo++;

  /// A resposta do pedido [id] ainda vale? `false` = chegou atrasada, depois de uma mais nova.
  bool aceitar(int id) {
    if (id < _aplicado) return false;
    _aplicado = id;
    return true;
  }
}
