"""ETAPA 1 · linha de base do backend. NÃO altera o jogo: só mede (substitui funções do banco por versões que contam e cronometram, dentro do teste).
Rodar: MEDIR=1 python -m pytest medicao/test_baseline_backend.py -s   (sem MEDIR=1 é ignorado, para não entrar na suíte normal).
Limite importante: aqui o banco é SQLite local. Contagem de chamadas, bytes e tempo de processamento valem; o tempo de banco/rede de PRODUÇÃO não."""
import json
import os
import statistics
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytestmark = pytest.mark.skipif(os.environ.get("MEDIR") != "1", reason="medição manual (MEDIR=1)")

import banco  # noqa: E402
from test_api import _cartas_teste, cli  # noqa: E402,F401

ROTAS = ["/loja", "/perfil", "/eu", "/ticker/central", "/trade/central", "/carteira", "/ranking/trade/tela", "/trofeus", "/setups", "/missoes"]
N = 15


class Medidor:
    def __init__(self):
        self.con = 0
        self.t_banco = 0.0
        self.ativos = 0
        self.max_ativos = 0
        self.prof = threading.local()
        self.lock = threading.Lock()

    def zera(self):
        self.con, self.t_banco, self.max_ativos = 0, 0.0, 0


def instala(mp, m: Medidor):
    orig_con = banco._con

    def con(*a, **k):
        with m.lock:
            m.con += 1
        return orig_con(*a, **k)
    mp.setattr(banco, "_con", con)
    nomes = [n for n in dir(banco) if callable(getattr(banco, n)) and (n.startswith(("_selecionar", "_contar", "_inserir", "_atualizar", "_apagar", "sis_", "cfg_", "jogos_", "comp_", "social_")))]
    for n in nomes:
        f = getattr(banco, n)

        def envolve(f=f):
            def w(*a, **k):
                d = getattr(m.prof, "d", 0)
                m.prof.d = d + 1
                t0 = time.perf_counter()
                if d == 0:
                    with m.lock:
                        m.ativos += 1
                        m.max_ativos = max(m.max_ativos, m.ativos)
                try:
                    return f(*a, **k)
                finally:
                    m.prof.d = d
                    if d == 0:
                        with m.lock:
                            m.t_banco += time.perf_counter() - t0
                            m.ativos -= 1
            return w
        mp.setattr(banco, n, envolve())


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def test_rotas(cli, monkeypatch):
    _cartas_teste()
    m = Medidor()
    instala(monkeypatch, m)
    res = {}
    for r in ROTAS:
        tempos, internos, dbs, tdb, tam, erros, seq, par, rede = [], [], [], [], [], 0, [], [], []
        for i in range(N + 1):
            m.zera()
            t0 = time.perf_counter()
            try:
                x = cli.get(r)
                ok = x.status_code < 400
                n = len(x.content)
                nr = int(x.headers.get('content-length', n))
            except Exception:
                ok, n, nr = False, 0, 0
            t = time.perf_counter() - t0
            erros += 0 if ok else 1
            if i == 0:
                primeira = round(t * 1000, 1)
                continue
            tempos.append(t * 1000); tdb.append(m.t_banco * 1000); internos.append((t - m.t_banco) * 1000); dbs.append(m.con); tam.append(n); rede.append(nr); par.append(m.max_ativos)
        res[r] = {"1a_ms": primeira, "total_p50_ms": round(statistics.median(tempos), 1), "total_p95_ms": round(pct(tempos, 95), 1), "interno_p50_ms": round(statistics.median(internos), 1),
                  "banco_local_p50_ms": round(statistics.median(tdb), 1), "chamadas_ao_banco": int(statistics.median(dbs)), "bytes": int(statistics.median(tam)), "bytes_na_rede": int(statistics.median(rede)),
                  "consultas_sequenciais": int(statistics.median(dbs)), "consultas_paralelas_max": max(par), "erros": erros}
    print("\nBASELINE_ROTAS " + json.dumps(res, ensure_ascii=False))
    assert all(v["erros"] == 0 for v in res.values())
