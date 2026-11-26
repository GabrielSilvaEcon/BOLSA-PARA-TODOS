"""ETAPA 1 · linha de base da PARTIDA (consultas, bytes, candles, ação→confirmação, dois jogadores ao mesmo tempo).
Rodar: MEDIR=1 python -m pytest medicao/test_baseline_partida.py -s . Só mede; banco SQLite local, relógio da partida simulado (1 s por consulta, como o app)."""
import json
import os
import statistics
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytestmark = pytest.mark.skipif(os.environ.get("MEDIR") != "1", reason="medição manual (MEDIR=1)")

import api.main as API  # noqa: E402
import banco  # noqa: E402
import bots as BOTS  # noqa: E402
import trader_dados as TD  # noqa: E402
import trader_online_dados as OL  # noqa: E402
from test_social_api import dois  # noqa: E402,F401


def _contador(mp):
    c = {"con": 0, "cas_falhas": 0, "cas_total": 0}
    lock = threading.Lock()
    orig = banco._con
    mp.setattr(banco, "_con", lambda *a, **k: (c.__setitem__("con", c["con"] + 1), orig(*a, **k))[1])
    o2 = banco._atualizar_n

    def upd(tabela, filtros, campos):
        ok = o2(tabela, filtros, campos)
        if tabela == "tb_partidas":
            with lock:
                c["cas_total"] += 1
                c["cas_falhas"] += 0 if ok else 1
        return ok
    mp.setattr(banco, "_atualizar_n", upd)
    return c


def test_partida_completa_com_bot(dois, monkeypatch):
    ana, _ = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    c = _contador(monkeypatch)
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json(); pid = r["id"]
    t["agora"] += BOTS.BOT_ESPERA_S + 1; ana.get("/trade/fila")
    ana.post(f"/trade/salas/{pid}/estrategia", json={"direcao": "alta"})
    polls, bytes_, candles, dbs, tempos, ucand = 0, [], [], [], [], None
    lat_acao, db_acao, bytes_acao = [], [], []
    inicio_jogo = t["agora"]
    k = 0
    for k in range(1000):
        t["agora"] += 1.0
        c["con"] = 0; t0 = time.perf_counter()
        x = ana.get(f"/trade/salas/{pid}"); dt = (time.perf_counter() - t0) * 1000
        v = x.json(); polls += 1
        bytes_.append(len(x.content)); dbs.append(c["con"]); tempos.append(dt)
        candles.append(len(v["tela"]["candles"]) if v.get("tela") else 0)
        if v.get("fase") == "replay" and k % 8 == 3:                       # uma jogada a cada ~8 s
            c["con"] = 0; t0 = time.perf_counter()
            y = ana.post(f"/trade/salas/{pid}/acao", json={"dados": {"aid": f"m{k}", "tipo": "mercado", "direcao": "alta" if (k // 8) % 2 == 0 else "baixa", "q": 1}})
            lat_acao.append((time.perf_counter() - t0) * 1000); db_acao.append(c["con"]); bytes_acao.append(len(y.content))
        if v.get("fase") == "fim":
            break
    dur = t["agora"] - inicio_jogo
    res = {"segundos_de_partida_simulados": round(dur), "consultas": polls, "consultas_por_minuto": round(polls / (dur / 60), 1),
           "bytes_por_consulta_p50": int(statistics.median(bytes_)), "bytes_por_consulta_max": max(bytes_), "total_baixado_KB": round(sum(bytes_) / 1024 + sum(bytes_acao) / 1024),
           "candles_por_consulta_p50": int(statistics.median(candles)), "candles_por_consulta_max": max(candles),
           "chamadas_banco_por_consulta_p50": int(statistics.median(dbs)), "chamadas_banco_por_consulta_max": max(dbs),
           "processamento_consulta_p50_ms": round(statistics.median(tempos), 1), "processamento_consulta_p95_ms": round(sorted(tempos)[int(len(tempos) * .95)], 1),
           "jogadas": len(lat_acao), "jogada_p50_ms": round(statistics.median(lat_acao), 1) if lat_acao else None, "jogada_banco_chamadas": int(statistics.median(db_acao)) if db_acao else None,
           "jogada_bytes_resposta": int(statistics.median(bytes_acao)) if bytes_acao else None, "cas_gravacoes": c["cas_total"], "cas_conflitos": c["cas_falhas"]}
    print("\nBASELINE_PARTIDA_BOT " + json.dumps(res, ensure_ascii=False))
    assert polls > 10


def test_dois_jogadores_operando_ao_mesmo_tempo(dois, monkeypatch):
    ana, bia = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    c = _contador(monkeypatch)
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json()
    r2 = bia.post("/trade/fila", json={"corrida": "rapida"}).json()
    assert r2["estado"] == "partida", r2
    pid = r2["id"]
    for cli in (ana, bia):
        cli.post(f"/trade/salas/{pid}/estrategia", json={"direcao": "alta"})
    t["agora"] += 45
    for cli in (ana, bia):
        cli.get(f"/trade/salas/{pid}")
    lat, status, falhas0 = [], [], c["cas_falhas"]
    lock = threading.Lock()

    def jogar(cli, i):
        for n in range(12):
            t0 = time.perf_counter()
            x = cli.post(f"/trade/salas/{pid}/acao", json={"dados": {"aid": f"s{i}-{n}", "tipo": "mercado", "direcao": "alta" if n % 2 == 0 else "baixa", "q": 1}})
            with lock:
                lat.append((time.perf_counter() - t0) * 1000); status.append(x.status_code)
            cli.get(f"/trade/salas/{pid}")
    th = [threading.Thread(target=jogar, args=(cli, i)) for i, cli in enumerate((ana, bia))]
    t0 = time.perf_counter()
    [x.start() for x in th]; [x.join() for x in th]
    res = {"jogadas_simultaneas": len(lat), "jogada_p50_ms": round(statistics.median(lat), 1), "jogada_p95_ms": round(sorted(lat)[int(len(lat) * .95)], 1), "jogada_max_ms": round(max(lat), 1),
           "status": {str(s): status.count(s) for s in set(status)}, "conflitos_de_gravacao": c["cas_falhas"] - falhas0, "duracao_total_s": round(time.perf_counter() - t0, 2)}
    print("\nBASELINE_PARTIDA_2J " + json.dumps(res, ensure_ascii=False))


def test_partida_completa_incremental_e_completa_lado_a_lado(dois, monkeypatch):
    """Etapa 2: o MESMO instante consultado de duas formas (protocolo incremental × estado completo), para comparar bytes (decodificados e na rede)."""
    from test_etapa2_desempenho import aplicar_cliente, consulta
    ana, _ = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    c = _contador(monkeypatch)
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json(); pid = r["id"]
    t["agora"] += BOTS.BOT_ESPERA_S + 1; ana.get("/trade/fila")
    ana.post(f"/trade/salas/{pid}/estrategia", json={"direcao": "alta"})
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    inc_dec, inc_rede, cheio_dec, cheio_rede, tipos, dbs_inc, tempos = [], [], [], [], {"minima": 0, "cauda": 0, "completa": 0}, [], []
    for k in range(1000):
        t["agora"] += 1.0
        c["con"] = 0; t0 = time.perf_counter()
        x = ana.get(f"/trade/salas/{pid}", params=consulta(est)); tempos.append((time.perf_counter() - t0) * 1000); dbs_inc.append(c["con"])
        j = x.json()
        tipos["minima" if j.get("sem_mudanca") else ("cauda" if "candles_cauda" in (j.get("tela") or {}) else "completa")] += 1
        inc_dec.append(len(x.content)); inc_rede.append(int(x.headers.get("content-length", len(x.content))))
        aplicar_cliente(est, j)
        y = ana.get(f"/trade/salas/{pid}")
        cheio_dec.append(len(y.content)); cheio_rede.append(int(y.headers.get("content-length", len(y.content))))
        if j.get("fase") == "fim":
            break
    mins = [b for b, j in zip(inc_dec, range(len(inc_dec)))]
    res = {"consultas": len(inc_dec), "tipos_de_resposta": tipos,
           "incremental": {"decodificado_KB_total": round(sum(inc_dec) / 1024), "rede_KB_total": round(sum(inc_rede) / 1024), "decodificado_p50_B": int(statistics.median(inc_dec)), "rede_p50_B": int(statistics.median(inc_rede)),
                           "banco_por_consulta_p50": int(statistics.median(dbs_inc)), "processamento_p50_ms": round(statistics.median(tempos), 1)},
           "completa": {"decodificado_KB_total": round(sum(cheio_dec) / 1024), "rede_KB_total": round(sum(cheio_rede) / 1024), "decodificado_p50_B": int(statistics.median(cheio_dec)), "rede_p50_B": int(statistics.median(cheio_rede))},
           "reducao_decodificado_pct": round(100 * (1 - sum(inc_dec) / sum(cheio_dec)), 1), "reducao_rede_pct": round(100 * (1 - sum(inc_rede) / sum(cheio_rede)), 1), "minimas_p50_B": None}
    minimas = [b for b in inc_dec if b < 2000]
    res["minimas_p50_B"] = int(statistics.median(minimas)) if minimas else None
    print("\nBASELINE_PARTIDA_INCREMENTAL " + json.dumps(res, ensure_ascii=False))
