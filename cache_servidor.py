"""Cache em memória do servidor, curto e controlado (Etapa 2 de desempenho).

Regras:
 · SÓ para dado público ou igual para todos (ranking, perfis públicos, configuração). Nunca saldo, inventário, resultado, operação ou estado de partida.
 · Validade curta (TTL). Quem grava o dado chama `invalidar` (neste processo, a mudança aparece na hora); em outros processos vale o TTL.
 · O cache vive na memória de UM processo: com mais de um worker cada um tem o seu (nada é presumido como compartilhado) e a validade curta limita o atraso.
 · Cache nunca derruba nada: se algo falhar aqui dentro, o dado é produzido direto, como se o cache não existisse.
 · Quem pede recebe uma CÓPIA (a menos que declare `somente_leitura=True`), então ninguém altera o que ficou guardado.
"""
from __future__ import annotations

import copy
import threading
import time


class CacheTTL:
    def __init__(self, ttl_s: float, max_itens: int = 128, relogio=time.monotonic):
        self.ttl, self.max, self._rel = float(ttl_s), int(max_itens), relogio
        self._d: dict = {}
        self._lock = threading.Lock()
        self.acertos = self.erros = 0

    def obter(self, chave, produzir, ttl_s: float | None = None, somente_leitura: bool = False):
        ttl = self.ttl if ttl_s is None else float(ttl_s)
        try:
            agora = self._rel()
            with self._lock:
                x = self._d.get(chave)
            if x is not None and agora - x[0] < ttl:
                self.acertos += 1
                return x[1] if somente_leitura else copy.deepcopy(x[1])
        except Exception:
            return produzir()                                   # cache indisponível: segue sem ele
        valor = produzir()                                      # (fora do lock: duas threads podem produzir ao mesmo tempo, o resultado é o mesmo)
        self.erros += 1
        try:
            with self._lock:
                if len(self._d) >= self.max:
                    self._d.clear()
                self._d[chave] = (self._rel(), valor)
        except Exception:
            pass
        return valor if somente_leitura else copy.deepcopy(valor)

    def invalidar(self, chave=None) -> None:
        with self._lock:
            if chave is None:
                self._d.clear()
            else:
                self._d.pop(chave, None)


# um cache para os dados públicos de leitura (ranking, perfis, documentos da competição)
PUBLICO = CacheTTL(ttl_s=15)
