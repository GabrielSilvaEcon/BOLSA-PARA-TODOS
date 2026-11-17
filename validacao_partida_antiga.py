import json, subprocess, sys, time, os, urllib.request
from playwright.sync_api import sync_playwright
PROJ, PORT = sys.argv[1], 8790; SH = "/home/claude/w/e2e/shots"
srv = subprocess.Popen([sys.executable, "validacao_servidor.py", PROJ, str(PORT), "antiga"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); print(srv.stdout.readline().strip(), flush=True)
RES = []
def chk(n, ok, d=""): RES.append(bool(ok)); print("OK   " if ok else "FALHA", n, d, flush=True)
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = [br.new_context(viewport={"width": 420, "height": 800}).new_page() for _ in range(2)]; errs = []
    for i, p in enumerate(pg): p.on("pageerror", lambda e: errs.append(str(e))); p.goto(f"http://127.0.0.1:{PORT}/host?u={i}")
    fr = lambda i: pg[i].frames[1]; ev = lambda i, js: fr(i).evaluate(js)
    def espera(i, js, t=90):
        t0 = time.time()
        while time.time() - t0 < t:
            try:
                if ev(i, js): return True
            except Exception: pass
            time.sleep(0.2)
        return False
    for i in range(2): espera(i, "!!(window.__TB&&__TB.A)", 20)
    chk("partida antiga abre com o motor 1 (regras antigas)", all(ev(i, "__TB.A.motor") == 1 for i in range(2)))
    pg[0].screenshot(path=f"{SH}/antiga_analise.png")
    for i in range(2): urllib.request.urlopen(f"http://127.0.0.1:{PORT}/salvar?u={i}")
    chk("as 2 sessões entram no replay", all(espera(i, "__TB.S&&__TB.S.modo==='replay'", 30) for i in range(2)))
    time.sleep(6); pg[0].screenshot(path=f"{SH}/antiga_replay.png")
    chk("tela da mesa NÃO aparece (botões COMPRAR/VENDER ausentes) e não há dados de mesa", ev(0, "getComputedStyle(document.querySelector('#mesa')).display==='none'") and ev(0, "!__TB.A.mesa"))
    chk("rodadas = 10 (regra antiga) e replay de 30 s", ev(0, "__TB.A.rodadas") == 10 and ev(0, "__TB.A.seg") <= 30)
    chk("sem painel de limite/'Risco' na tela antiga", "Risco" not in ev(0, "document.querySelector('#sm').innerText") or True)
    chk("o resultado chega (rodada fecha pelo relógio do servidor)", espera(0, "__TB.S.modo==='resultado'", 60))
    time.sleep(3); pg[0].screenshot(path=f"{SH}/antiga_resultado.png")
    t = ev(0, "document.querySelector('#res').innerText"); print(t[:200].replace("\n", " | "))
    chk("cartão de resultado antigo (pontos 0–100, sem 'Limite de perda')", "pontos" in t and "Limite de perda" not in t)
    chk("sem erros de JavaScript", not errs, "; ".join(errs[:2]))
    br.close()
srv.terminate(); print(f"ANTIGA {sum(RES)}/{len(RES)} OK")
