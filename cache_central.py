"""Etapa 3 · Cache central e inteligente dos dados externos.

Substitui `@st.cache_data` nas funções de coleta que falam com fontes externas. Diferenças em relação ao cache padrão:
  1. NÃO guarda falha por horas. Uma coleta que volta vazia ou com erro (ex.: Yahoo bloqueou por um instante) fica guardada por
     apenas NEG_S segundos; antes ficava pelo TTL inteiro (de 1 a 24 h) e o app mostrava "sem dados" até expirar.
  2. UM pedido por vez para a mesma chave: se 10 usuários pedem o mesmo ativo no mesmo instante, a fonte recebe 1 pedido e os
     outros 9 esperam e reaproveitam (proteção das cotas gratuitas).
  3. Dado antigo em vez de nada: se a fonte falha e existe um resultado bom anterior (até MAX_ANTIGO_S), ele é devolvido com o aviso
     "dado de há X" (nos resultados em dicionário com campo "avisos"). Nunca se inventa valor: é sempre um dado real, mais velho.
  4. Estatísticas (acertos, pedidos à fonte, coalescidos, dados antigos, falhas) para o painel de consumo.
Limites: o cache vive na memória do app (some quando o app dorme ou reinicia, como o do Streamlit); cada função guarda no máximo
MAX_ENTRADAS chaves; durante os testes automatizados fica desligado (use `forcar(True)` nos testes do próprio módulo).
"""
from __future__ import annotations

import copy
import functools
import os
import threading
import time

NEG_S = 120                 # quanto tempo uma falha/vazio fica guardado
MAX_ANTIGO_S = 24 * 3600    # idade máxima do dado antigo servido quando a fonte falha
MAX_ENTRADAS = 400
_META = {"avisos", "fonte", "data", "moeda", "erro", "aviso", "fonte_nome", "atualizado"}

_g = threading.Lock()
_forcado: list = [None]
_stats: dict[str, dict[str, int]] = {}
_registros: list = []       # funções registradas (para limpar)


def forcar(valor: bool | None) -> None:
    """Só para testes: True liga, False desliga, None volta ao automático."""
    _forcado[0] = valor


def _ativo() -> bool:
    if _forcado[0] is not None:
        return bool(_forcado[0])
    return "PYTEST_CURRENT_TEST" not in os.environ


def _conta(nome: str, campo: str) -> None:
    with _g:
        _stats.setdefault(nome, {"acertos": 0, "pedidos": 0, "coalescidos": 0, "antigos": 0, "falhas": 0})[campo] += 1


def _vazio(v) -> bool:
    try:
        return len(v) == 0
    except TypeError:
        return v is None


def _tem_dado(x) -> bool:
    if x is None or isinstance(x, (bool, str)):
        return False
    if isinstance(x, (int, float)):
        return x == x                       # NaN não é dado
    return not _vazio(x)


def resultado_bom(v) -> bool:
    """Regra padrão: tabela/série com linhas; dicionário com algum dado real fora dos campos de aviso e sem 'erro'."""
    if v is None:
        return False
    if isinstance(v, dict):
        if v.get("erro"):
            return False
        return any(_tem_dado(x) for k, x in v.items() if k not in _META)
    return not _vazio(v)


def _idade(seg: float) -> str:
    m = int(seg // 60)
    return f"{m} min" if m < 120 else f"{m // 60} h"


def _anotar(v, idade_s: float):
    v = copy.deepcopy(v)
    if isinstance(v, dict) and isinstance(v.get("avisos"), list):
        v["avisos"].append(f"A fonte não respondeu agora: estes são os últimos dados obtidos, de há {_idade(idade_s)}.")
    return v


def dados(ttl: int = 900, ok=None, nome: str | None = None):
    """Decorador. `ok(resultado) -> bool` diz se o resultado é bom (padrão: `resultado_bom`)."""
    avalia = ok or resultado_bom

    def deco(fn):
        rotulo = nome or f"{fn.__module__}.{fn.__name__}"
        boas: dict = {}        # chave -> (valor, instante) do último resultado bom
        ruins: dict = {}       # chave -> (valor, instante) de falha recente
        travas: dict = {}

        @functools.wraps(fn)
        def wrapper(*a, **k):
            if not _ativo():
                return fn(*a, **k)
            chave = repr((a, sorted(k.items())))
            agora = time.time()
            b = boas.get(chave)
            if b and agora - b[1] < ttl:
                _conta(rotulo, "acertos")
                return copy.deepcopy(b[0])
            r = ruins.get(chave)
            if r and agora - r[1] < NEG_S:
                _conta(rotulo, "acertos")
                return copy.deepcopy(r[0])
            with _g:
                trava = travas.setdefault(chave, threading.Lock())
            esperou = trava.locked()
            with trava:
                agora = time.time()
                b = boas.get(chave)
                if b and agora - b[1] < ttl:
                    _conta(rotulo, "coalescidos" if esperou else "acertos")
                    return copy.deepcopy(b[0])
                r = ruins.get(chave)
                if r and agora - r[1] < NEG_S:
                    _conta(rotulo, "coalescidos" if esperou else "acertos")
                    return copy.deepcopy(r[0])
                _conta(rotulo, "pedidos")
                erro, v = None, None
                try:
                    v = fn(*a, **k)
                except Exception as e:           # noqa: BLE001 - a decisão (antigo ou erro) é tomada abaixo
                    erro = e
                agora = time.time()
                if erro is None and avalia(v):
                    if len(boas) >= MAX_ENTRADAS:
                        boas.pop(min(boas, key=lambda x: boas[x][1]), None)
                    boas[chave] = (copy.deepcopy(v), agora)
                    ruins.pop(chave, None)
                    return v
                _conta(rotulo, "falhas")
                b = boas.get(chave)
                if b and agora - b[1] <= MAX_ANTIGO_S:
                    _conta(rotulo, "antigos")
                    ruins[chave] = (_anotar(b[0], agora - b[1]), agora)
                    return _anotar(b[0], agora - b[1])
                if erro is not None:
                    raise erro
                if len(ruins) >= MAX_ENTRADAS:
                    ruins.pop(min(ruins, key=lambda x: ruins[x][1]), None)
                ruins[chave] = (copy.deepcopy(v), agora)
                return v

        def limpar():
            boas.clear(); ruins.clear()
        wrapper.clear = limpar
        _registros.append(limpar)
        return wrapper
    return deco


def limpar_tudo() -> None:
    for f in list(_registros):
        f()


def estatisticas() -> list[dict]:
    with _g:
        return [{"nome": n, **v} for n, v in sorted(_stats.items())]


def resumo() -> dict:
    est = estatisticas()
    tot = {c: sum(e[c] for e in est) for c in ("acertos", "pedidos", "coalescidos", "antigos", "falhas")}
    consultas = tot["acertos"] + tot["pedidos"] + tot["coalescidos"]
    tot["consultas"] = consultas
    tot["economia_pct"] = round(100 * (tot["acertos"] + tot["coalescidos"]) / consultas, 1) if consultas else 0.0
    return tot
