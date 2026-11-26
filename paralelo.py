"""Leituras independentes em paralelo (Etapa 2 de desempenho). Para telas que fazem várias consultas ao banco que NÃO dependem umas das outras:
em vez de esperar uma ida ao banco por vez, as idas acontecem juntas.

Segurança:
 · só leituras independentes (nunca gravações, nunca etapas em que uma depende do resultado da outra);
 · cada tarefa roda no contexto da requisição (ContextVar copiado: a pré-carga de estados e o isolamento por pessoa continuam valendo);
 · o erro de cada tarefa fica guardado e só sobe quando QUEM CHAMOU lê o resultado, então cada try/except original continua tratando o seu caso;
 · as threads do pool são fixas, então cada uma mantém a sua sessão HTTP com o banco (conexões reaproveitadas);
 · se o pool não estiver disponível, as tarefas rodam em sequência, como antes.
"""
from __future__ import annotations

import concurrent.futures
import contextvars

_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="leitura")


class Resultado:
    __slots__ = ("valor", "erro")

    def __init__(self, valor=None, erro=None):
        self.valor, self.erro = valor, erro

    def get(self):
        if self.erro is not None:
            raise self.erro
        return self.valor


def paralelo(tarefas: dict) -> dict:
    """{nome: função sem argumentos} → {nome: Resultado}. O tempo total é o da tarefa mais lenta, não a soma."""
    futuros = {}
    try:
        for nome, f in tarefas.items():
            futuros[nome] = _POOL.submit(contextvars.copy_context().run, f)
    except Exception:
        futuros = {}                                              # pool indisponível: sequencial
    saida = {}
    for nome, f in tarefas.items():
        try:
            saida[nome] = Resultado(valor=futuros[nome].result() if nome in futuros else f())
        except Exception as e:
            saida[nome] = Resultado(erro=e)
    return saida
