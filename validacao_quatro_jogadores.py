import json, subprocess, sys, time, re, os, urllib.request
from playwright.sync_api import sync_playwright
PROJ, PORT = sys.argv[1], 8766
SH = "/home/claude/w/e2e/shots"; os.makedirs(SH, exist_ok=True)
srv = subprocess.Popen([sys.executable, "validacao_servidor.py", PROJ, str(PORT), "rapida"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print(srv.stdout.readline().strip(), flush=True)
NOMES = ["Ana", "Bia", "Caio", "Dani"]; RES = []
def chk(nome, ok, det=""):
    RES.append((nome, bool(ok), det)); print(("OK   " if ok else "FALHA"), nome, det, flush=True)
def est(): return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/estado").read())
def traf(u): return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/trafego?u={u}").read())
with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = [br.new_context(viewport={"width": 420, "height": 800}, device_scale_factor=1) for _ in range(4)]   # 4 contextos = 4 sessões isoladas
    pg = [c.new_page() for c in ctx]; errs = [[] for _ in range(4)]
    for i, p in enumerate(pg):
        p.on("pageerror", lambda e, i=i: errs[i].append(str(e))); p.on("console", lambda m, i=i: errs[i].append(m.text) if m.type == "error" else None)
        p.goto(f"http://127.0.0.1:{PORT}/host?u={i}")
    fr = lambda i: pg[i].frames[1]
    def ev(i, js): return fr(i).evaluate(js)
    def espera(i, js, t=90):
        t0 = time.time()
        while time.time() - t0 < t:
            try:
                if ev(i, js): return True
            except Exception: pass
            time.sleep(0.15)
        return False
    def shot(i, nome): pg[i].screenshot(path=f"{SH}/{nome}_{NOMES[i]}.png")
    def clique(i, sel): fr(i).click(sel, timeout=4000)
    for i in range(4): chk(f"{NOMES[i]} carregou o componente", espera(i, "!!(window.__TB&&__TB.A&&__TB.A.motor===2)", 20))
    def leitura(i, dirc="#b-buy"):
        espera(i, "__TB.S&&__TB.S.modo==='analise'", 30); clique(i, dirc); espera(i, "!document.querySelector('#conf').disabled", 5); clique(i, "#conf")
    def todos_em_replay(): return all(espera(i, "__TB.S&&__TB.S.modo==='replay'", 60) for i in range(4))
    def rev(i): return ev(i, "__TB.A.revelados")
    def ate(i, n, t=90): return espera(i, f"__TB.A.revelados>={n}", t)
    # ------------------------------------------------------------- RODADA 1
    for i, d in enumerate(["#b-sell", "#b-buy", "#b-buy", "#b-sell"]): leitura(i, d)
    chk("4 sessões confirmaram a leitura e entraram juntas no replay", todos_em_replay())
    for i in range(4): shot(i, "r1_00_inicio")
    for i in range(4): ate(i, 3)
    t_ent = time.time()
    clique(0, "#m-sell"); clique(1, "#m-buy")                                          # Ana vende, Bia compra; Caio fica de fora
    ate(3, 5); clique(3, "#m-sell")                                                   # Dani vende 2 candles depois (entrada diferente da Ana: limites diferentes)
    time.sleep(2.5)
    for i in (1, 3):                                                                  # stop/alvo pelo painel avançado (valores distintivos para o teste de privacidade)
        clique(i, "#m-adv")
    fr(1).fill("#g-alvo", "12,2719"); clique(1, "#g-alvo-b"); time.sleep(1.8); fr(1).fill("#g-stop", "9,4137"); clique(1, "#g-stop-b"); time.sleep(1.8)
    fr(3).fill("#g-stop", "11,3331"); clique(3, "#g-stop-b"); time.sleep(1.8)
    for i in (1, 3): clique(i, "#m-adv")
    for i in range(4): shot(i, "r1_01_posicoes")
    cj = ev(2, "JSON.stringify(__TB.A.adversarios)")
    adv = json.loads(cj); chk("Caio (nunca operou) vê as 3 entradas dos adversários em tempo real", len(adv) == 3 and all(a["ops"] and a["ops"][0]["aberta"] for a in adv), cj[:200])
    mc = ev(2, "JSON.stringify(__TB.A.mesa)"); chk("Caio não tem posição e pode abrir", json.loads(mc)["posicao"] is None and json.loads(mc)["pode_abrir"])
    lim_d = json.loads(ev(3, "JSON.stringify(__TB.A.mesa.limite)"))["preco"]; chk("Dani tem limite próprio diferente do da Ana", lim_d and abs(lim_d - 4 * json.loads(ev(3, "JSON.stringify(__TB.A.mesa.posicao)"))["preco_entrada"]) < 1e-6 and lim_d != json.loads(ev(0, "JSON.stringify(__TB.A.mesa.limite)"))["preco"], f"limite Dani={lim_d}")
    a_mesa = json.loads(ev(0, "JSON.stringify(__TB.A.mesa)")); lim_a = a_mesa["limite"]["preco"]
    chk("Ana vê o próprio preço de limite (4× a entrada, linha LIMITE 3%)", lim_a and abs(lim_a - 4 * a_mesa["posicao"]["preco_entrada"]) < 1e-6, f"limite={lim_a}")
    chk("Bia vê o próprio stop e alvo", json.loads(ev(1, "JSON.stringify(__TB.A.mesa.posicao)"))["stop"] == 9.4137 and json.loads(ev(1, "JSON.stringify(__TB.A.mesa.posicao)"))["alvo"] == 12.2719)
    # ------------------------------------------------------------- o spike (candle 8) → limite da Ana, alvo da Bia, stop da Dani
    for i in range(4): ate(i, 11)
    time.sleep(2)
    for i in range(4): shot(i, "r1_02_apos_spike")
    am = json.loads(ev(0, "JSON.stringify(__TB.A.mesa)"))
    chk("Ana: limite de 3% acionado, posição encerrada, bloqueada", am["limite"]["bloqueado"] and am["posicao"] is None and am["operacoes"][0]["motivo"] == "limite", json.dumps(am["operacoes"]))
    chk("Ana: botões COMPRAR/VENDER desabilitados e aviso na tela", ev(0, "document.querySelector('#m-buy').disabled&&document.querySelector('#m-sell').disabled") and "limite de perda atingido" in ev(0, "document.querySelector('#sm').innerText"))
    bm = json.loads(ev(1, "JSON.stringify(__TB.A.mesa)")); dm = json.loads(ev(3, "JSON.stringify(__TB.A.mesa)"))
    chk("Bia saiu no alvo e Dani no stop, sem bloqueio", bm["operacoes"][0]["motivo"] == "alvo" and dm["operacoes"][0]["motivo"] == "stop" and not bm["limite"]["bloqueado"] and not dm["limite"]["bloqueado"])
    chk("Bia e Dani podem operar de novo (nova operação na hora, direção contrária)", bm["pode_abrir"] and dm["pode_abrir"])
    clique(1, "#m-sell"); time.sleep(2.2)
    chk("Bia reabre na direção contrária", json.loads(ev(1, "JSON.stringify(__TB.A.mesa.posicao)"))["direcao"] == "baixa")
    clique(2, "#m-buy"); time.sleep(2.2); clique(2, "#m-enc"); time.sleep(2.2)                   # Caio só agora opera e encerra (preço 45 plano: 0%)
    # ------------------------------------------------------------- resultado da rodada
    for i in range(4): espera(i, "__TB.S.modo==='resultado'", 90)
    time.sleep(2.5)
    for i in range(4):
        fr(i).evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)"); shot(i, "r1_03_resultado")
    E = est(); R = E["resultados"]
    pts = {n: R[f"1:{e}"]["pontos"] for n, e in zip(NOMES, ["ana@x.com", "bia@x.com", "caio@x.com", "dani@x.com"])}
    chk("Resultado r1: Ana −3% (pnl −3000, limite_atingido) e pontos < 0", R["1:ana@x.com"]["pnl"] == -3000.0 and R["1:ana@x.com"]["limite"] and R["1:ana@x.com"]["pontos"] < 0, json.dumps(R["1:ana@x.com"]))
    chk("Resultado r1: Bia > 0 (alvo), Dani < 0 (stop), Caio = 0", R["1:bia@x.com"]["pontos"] != 0 and R["1:dani@x.com"]["pontos"] < 0 and R["1:caio@x.com"]["pontos"] == 0, json.dumps(pts))
    chk("Caixa da Ana (começou com exatamente 3%) não ficou negativa", E["caixa"]["ana@x.com"] == 0.0, str(E["caixa"]["ana@x.com"]))
    rs = ev(0, "document.querySelector('#res').innerText")
    chk("Cartão da Ana mostra o valor em T$ e o Raio-X cita o limite de perda", "3.000" in rs and "Limite de perda" in rs, rs[:160].replace("\n", " | "))
    chk("Ledger: 1 lançamento por jogador com pnl≠0 na rodada 1", sorted(k.split(":")[-1] for k in E["lanc"] if ":1:" in k) == ["ana@x.com", "bia@x.com", "dani@x.com"], str(list(E["lanc"])))
    # ------------------------------------------------------------- RODADAS 2 e 3
    for rod in (2, 3):
        for i in range(4):
            espera(i, f"__TB.A.rodada=={rod}&&__TB.S.modo==='analise'", 30); leitura(i)
        chk(f"Rodada {rod}: as 4 sessões voltam ao replay juntas", todos_em_replay())
        for i in range(4): ate(i, 3)
        if rod == 2:
            clique(0, "#m-buy"); time.sleep(2.2)
            chk("Rodada 2: limite da Ana zerado (reset por rodada) e ela voltou a operar", json.loads(ev(0, "JSON.stringify(__TB.A.mesa.posicao)")) is not None and not json.loads(ev(0, "JSON.stringify(__TB.A.mesa.limite)"))["bloqueado"])
            shot(0, "r2_ana_reabre")
        for i in range(4): espera(i, "__TB.S.modo==='resultado'", 90)
        time.sleep(2.5)
        for i in range(4): shot(i, f"r{rod}_resultado")
    time.sleep(8)
    E = est(); P = E["pontos"]
    # ------------------------------------------------------------- fim: pontos/ranking e privacidade
    soma = {e: round(sum(E["resultados"][f"{r}:{e}"]["pontos"] for r in (1, 2, 3)), 1) for e in P}
    chk("Fim da partida: pontos de cada jogador = soma das 3 rodadas (4 jogadores)", E["fase"] == "fim" and all(abs(P[e] - soma[e]) < 0.11 for e in P), json.dumps(P))
    rk = sorted(P, key=lambda e: -P[e]); chk("Ranking por pontos (calculado no servidor) tem ordem total coerente", [P[e] for e in rk] == sorted(P.values(), reverse=True), " > ".join(f"{e.split('@')[0]} {P[e]}" for e in rk))
    for i in range(4): shot(i, "r9_fim")
    CAMPOS_PUB = {"direcao", "preco_entrada", "indice_entrada", "aberta", "preco_saida", "indice_saida"}
    for i, e in enumerate(["ana@x.com", "bia@x.com", "caio@x.com", "dani@x.com"]):
        rend = [json.loads(x) for x in traf(i)]; rend = [x for x in rend if x.get("args")]
        def tem(k, txt): return re.search(r"(?<![\d.])" + re.escape(k) + r"(?!\d)", txt) is not None
        meus = {"ana@x.com": [repr(lim_a)], "bia@x.com": ["9.4137", "12.2719"], "dani@x.com": ["11.3331", repr(lim_d)], "caio@x.com": []}[e]
        alheios = [k for k in ("9.4137", "12.2719", "11.3331", repr(lim_a), repr(lim_d)) if k not in meus]
        # 1) ANTES de o servidor executar (candles revelados <= 8 na rodada 1) nenhum valor alheio pode ter chegado ao navegador
        antes = "".join(json.dumps(x) for x in rend if x["args"]["rodada"] == 1 and x["args"]["revelados"] <= 8 and x["args"]["modo"] == "replay")
        vaz = [k for k in alheios if tem(k, antes)]
        chk(f"Privacidade de {NOMES[i]}: antes da execução, nenhum stop/alvo/limite alheio chegou ao navegador ({len(rend)} respostas)", not vaz and len(antes) > 1000, f"vazou={vaz}")
        # 2) sempre: dos adversários só os 6 campos públicos; stop/alvo/ordens só dentro da própria mesa
        campos = {k for x in rend for a in x["args"]["adversarios"] for o in a["ops"] for k in o}
        chk(f"Privacidade de {NOMES[i]}: dos adversários chegam só os campos públicos (entrada/saída executadas)", campos <= CAMPOS_PUB, str(campos - CAMPOS_PUB))
        adv_txt = "".join(json.dumps(x["args"]["adversarios"]) for x in rend)
        chk(f"Privacidade de {NOMES[i]}: nenhum stop, alvo, ordem, limite ou motivo nos dados dos adversários", not re.search(r'"(stop|alvo|limite|ordens|motivo|pend)', adv_txt))
        chk(f"Controle de {NOMES[i]}: a busca acha os PRÓPRIOS valores (o teste não é cego)", all(tem(k, "".join(json.dumps(x["args"].get("mesa")) for x in rend)) for k in meus))
        t = "".join(json.dumps(x) for x in rend)
        chk(f"Privacidade de {NOMES[i]}: nunca recebeu os pontos de outros jogadores", all(f'"{o}"' not in t for o in P if o != e))
    for i in range(4): chk(f"{NOMES[i]}: sem erros de JavaScript no navegador", not errs[i], "; ".join(errs[i][:2]))
    br.close()
srv.terminate()
json.dump({"res": RES, "estado": E}, open("/home/claude/w/e2e/resultado.json", "w"), default=str, ensure_ascii=False, indent=1)
print(f"\nTOTAL {sum(1 for r in RES if r[1])}/{len(RES)} OK")
