"""Etapa 3 · Cache central e inteligente dos dados externos.

Substitui `@st.cache_data` nas funções de coleta que falam com fontes externas. Diferenças em relação ao cache padrão:
  1. NÃO guarda falha por horas. Uma coleta que volta vazia ou com erro (ex.: Yahoo bloqueou por um instante) fica guardada por
     apenas NEG_S segundos; antes ficava pelo TTL inteiro (de 1 a 24 h) e o app mostrava "sem dados" até expirar.
  2. UM pedido por vez para a mesma chave: se 10 usuários pedem o mesmo ativo no mesmo instante, a fonte recebe 1 pedido e os
     outros 9 esperam e reaproveitam (proteção das cotas gratuitas).
  3. Dado antigo em vez de nada: se a fonte falha e existe um resultado bom anterior (até MAX_ANTIGO_S), ele é devolvido com o aviso
     "dado de há X" (nos resultados em dicionário com campo "avisos"). Nunca se inventa valor: é sempre um dado real, mais velho.
  4. SOBREVIVE a reinícios: resultados bons e pequenos (até MAX_BYTES) são gravados no Supabase (tabela config_sistema) e lidos de
     volta quando a memória está vazia (app que acordou, ou dado aquecido pelo monitor do GitHub). Formato JSON próprio, sem pickle.
  5. Estatísticas (acertos, pedidos à fonte, coalescidos, dados antigos, falhas) para o painel de consumo.
Limites: o cache vive na memória do app (some quando o app dorme ou reinicia, como o do Streamlit); cada função guarda no máximo
MAX_ENTRADAS chaves; durante os testes automatizados fica desligado (use `forcar(True)` nos testes do próprio módulo).
"""
from __future__ import annotations

import copy
import datetime as _dt
import functools
import hashlib
import json
import math
import os
import threading
import time

NEG_S = 120                 # quanto tempo uma falha/vazio fica guardado
MAX_ANTIGO_S = 24 * 3600    # idade máxima do dado antigo servido quando a fonte falha
MAX_ENTRADAS = 400
MAX_BYTES = 250_000          # acima disso o resultado fica só na memória
PAUSA_PERSISTENCIA_S = 300  # depois de uma falha do banco, não tenta gravar/ler por este tempo
_META = {"avisos", "fonte", "data", "moeda", "erro", "aviso", "fonte_nome", "atualizado"}

_g = threading.Lock()
_forcado: list = [None]
_stats: dict[str, dict[str, int]] = {}
_pers = {"pausa_ate": 0.0}
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
        _stats.setdefault(nome, {"acertos": 0, "pedidos": 0, "coalescidos": 0, "antigos": 0, "falhas": 0, "do_banco": 0})[campo] += 1


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


# ---------------------------------------------------------------- formato de gravação (JSON; sem pickle)
class _NaoSerializa(Exception):
    pass


def _enc(x):
    import numpy as np
    import pandas as pd
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return {"__f": "nan"} if math.isnan(x) else {"__f": "inf" if x > 0 else "-inf"} if math.isinf(x) else x
    if isinstance(x, pd.Timestamp):
        return {"__ts": x.isoformat()}
    if isinstance(x, _dt.datetime):
        return {"__dt": x.isoformat()}
    if isinstance(x, _dt.date):
        return {"__date": x.isoformat()}
    if isinstance(x, dict):
        return {"__d": [[_enc(k), _enc(v)] for k, v in x.items()]}
    if isinstance(x, list):
        return {"__l": [_enc(v) for v in x]}
    if isinstance(x, tuple):
        return {"__t": [_enc(v) for v in x]}
    if isinstance(x, pd.DataFrame):
        if isinstance(x.columns, pd.MultiIndex) or isinstance(x.index, pd.MultiIndex):
            raise _NaoSerializa("índice múltiplo")
        return {"__df": {"i": [_enc(v) for v in x.index.tolist()], "c": [_enc(v) for v in x.columns.tolist()],
                         "d": [[_enc(v) for v in linha] for linha in x.astype(object).values.tolist()],
                         "in": x.index.name, "tz": str(x.index.tz) if getattr(x.index, "tz", None) is not None else None}}
    if isinstance(x, pd.Series):
        if isinstance(x.index, pd.MultiIndex):
            raise _NaoSerializa("índice múltiplo")
        return {"__s": {"i": [_enc(v) for v in x.index.tolist()], "d": [_enc(v) for v in x.astype(object).tolist()], "n": x.name,
                        "in": x.index.name, "tz": str(x.index.tz) if getattr(x.index, "tz", None) is not None else None}}
    raise _NaoSerializa(type(x).__name__)


def _dec(x):
    import pandas as pd
    if not isinstance(x, dict):
        return x
    if "__f" in x:
        return float(x["__f"])
    if "__ts" in x:
        return pd.Timestamp(x["__ts"])
    if "__dt" in x:
        return _dt.datetime.fromisoformat(x["__dt"])
    if "__date" in x:
        return _dt.date.fromisoformat(x["__date"])
    if "__d" in x:
        return {_dec(k): _dec(v) for k, v in x["__d"]}
    if "__l" in x:
        return [_dec(v) for v in x["__l"]]
    if "__t" in x:
        return tuple(_dec(v) for v in x["__t"])
    if "__df" in x or "__s" in x:
        bloco = x.get("__df") or x["__s"]
        idx = pd.Index([_dec(v) for v in bloco["i"]])
        if len(idx) and all(isinstance(v, pd.Timestamp) for v in idx):
            idx = pd.DatetimeIndex(idx)
        if bloco.get("tz") and isinstance(idx, pd.DatetimeIndex) and idx.tz is None:
            idx = idx.tz_localize(bloco["tz"])
        idx.name = bloco.get("in")
        if "__df" in x:
            df = pd.DataFrame([[_dec(v) for v in l] for l in bloco["d"]], index=idx, columns=[_dec(v) for v in bloco["c"]])
            return df.infer_objects()
        return pd.Series([_dec(v) for v in bloco["d"]], index=idx, name=bloco.get("n")).infer_objects()
    raise _NaoSerializa("marcador desconhecido")


def _chave_banco(rotulo: str, chave: str) -> str:
    return "cache|" + hashlib.sha1(f"{rotulo}|{chave}".encode()).hexdigest()[:30]


def _persistencia_ligada() -> bool:
    if time.time() < _pers["pausa_ate"]:
        return False
    if _forcado[0] is True:
        return True
    try:
        import banco
        return banco.backend() == "supabase"
    except Exception:
        return False


def _ler_banco(rotulo: str, chave: str):
    """(valor, instante) gravado antes, ou None."""
    if not _persistencia_ligada():
        return None
    try:
        import banco
        d = banco.cfg_ler(_chave_banco(rotulo, chave))
        if not d or "v" not in d:
            return None
        return _dec(d["v"]), float(d["t"])
    except Exception:
        _pers["pausa_ate"] = time.time() + PAUSA_PERSISTENCIA_S
        return None


def _gravar_banco(rotulo: str, chave: str, v, instante: float) -> None:
    if not _persistencia_ligada():
        return
    try:
        corpo = {"n": rotulo, "t": instante, "v": _enc(v)}
        if len(json.dumps(corpo, ensure_ascii=False)) > MAX_BYTES:
            return
    except Exception:                      # tipo que não sabemos gravar com segurança: fica só na memória
        return

    def tarefa():
        try:
            import banco
            banco.cfg_gravar(_chave_banco(rotulo, chave), corpo)
        except Exception:
            _pers["pausa_ate"] = time.time() + PAUSA_PERSISTENCIA_S
    if _forcado[0] is True:
        tarefa()                           # nos testes, síncrono
    else:
        threading.Thread(target=tarefa, daemon=True).start()


def dados(ttl: int = 900, ok=None, nome: str | None = None, persistir: bool = True):
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
                p = _ler_banco(rotulo, chave) if persistir else None
                if p:
                    boas[chave] = (p[0], p[1])
                    if agora - p[1] < ttl:                # gravado por outro processo/antes do reinício e ainda válido
                        _conta(rotulo, "do_banco")
                        return copy.deepcopy(p[0])
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
                    if persistir:
                        _gravar_banco(rotulo, chave, v, agora)
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
    tot = {c: sum(e[c] for e in est) for c in ("acertos", "pedidos", "coalescidos", "antigos", "falhas", "do_banco")}
    consultas = tot["acertos"] + tot["pedidos"] + tot["coalescidos"]
    tot["consultas"] = consultas + tot["do_banco"]
    tot["economia_pct"] = round(100 * (tot["acertos"] + tot["coalescidos"] + tot["do_banco"]) / tot["consultas"], 1) if tot["consultas"] else 0.0
    return tot
