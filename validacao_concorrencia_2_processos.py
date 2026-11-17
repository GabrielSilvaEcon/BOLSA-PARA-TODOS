"""Concorrência real: 2 PROCESSOS Python, mesmo SQLite temporário, ações alternadas. Nenhuma ação pode se perder, `ordem` única, resultado igual ao recalculado."""
import os, sys, json, subprocess, tempfile, time
PROJ = sys.argv[1]; sys.path.insert(0, PROJ); os.chdir(PROJ)
import test_trader_mesa as T
import banco, trader_online_dados as OL, trader_battle as TB
EM = T.EMAILS
if len(sys.argv) > 2:                                           # filho: age como UM jogador, em processo próprio
    dbp, pid, i, t = sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5])
    banco.usar_sqlite(dbp)
    with T.livro():
        for k in range(12):                                     # compra, encerra, compra, encerra... (cada ação com id próprio)
            tipo = "mercado" if k % 2 == 0 else "encerrar"
            d = {"tipo": tipo, "aid": f"p{i}-{k}"}
            if tipo == "mercado": d["direcao"] = "alta"
            OL.agir(pid, EM[i], d, t + 5 + k * 0.1)
    sys.exit(0)
with T.banco_isolado() as pasta:
    T._contas()
    with T.livro():
        r = OL.criar_sala(EM[0], "15m", T.TS, "rapida"); OL.entrar_na_sala(EM[1], r["codigo"], T.TS + 1); OL.iniciar(r["id"], EM[0], T.TS + 2)
        t = T._comecar_replay(r["id"])
    dbp = os.path.join(pasta, "t.db"); pid = r["id"]
    ps = [subprocess.Popen([sys.executable, __file__, PROJ, dbp, pid, str(i), str(t)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for i in range(2)]
    outs = [p.communicate()[0] for p in ps]
    print("códigos de saída:", [p.returncode for p in ps]); [print(o[-300:]) for o in outs if o.strip()]
    ac = OL._row(pid)["dados"]["p"]["acoes"]
    ordens = sorted(a["ordem"] for a in ac)
    print("ações gravadas:", len(ac), "esperado 24 | ordens únicas e sequenciais:", ordens == list(range(1, 25)))
    print("por jogador:", {e: sum(1 for a in ac if a["jogador"] == e) for e in EM}, "| aids únicos:", len({a['aid'] for a in ac}) == 24)
    with T.livro():
        v0 = OL.ler(pid, EM[0], t + 61)["v"]; v1 = OL.ler(pid, EM[1], t + 61)["v"]
    p = OL._row(pid)["dados"]["p"]
    nr = TB._nrp(p); cen = OL._cenario(OL._row(pid)["dados"]); ini = TB.inicio_rodada(cen, 1, nr)
    for e in EM:
        s = TB.simular_jogador(cen["candles"][ini:ini + nr], TB.acoes_da_rodada(p, 1, e), cen["candles"][ini - 1]["c"], True)
        g = p["resultados"][f"1:{e}"]
        print(e, "resultado gravado == recalculado:", abs(sum(t_["ret"] for t_ in s["trades"]) - sum(t_["ret"] for t_ in g["operacoes"])) < 1e-12, "| operações:", len(g["operacoes"]))
