"""Servidor de teste (NÃO faz parte do projeto): reproduz o laço de _frag_mesa_online do app Streamlit usando as funções REAIS do projeto
(OL.ler → G.args_mesa → G.processar com OL.Ops), com banco SQLite TEMPORÁRIO e livro de carteira falso. Um navegador por jogador."""
import json, os, sys, threading, time, mimetypes
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
PROJ = sys.argv[1]; PORT = int(sys.argv[2]); FORMATO = sys.argv[3] if len(sys.argv) > 3 else "rapida"
sys.path.insert(0, PROJ); os.chdir(PROJ)
import banco, tempfile
import trader_battle as TB, trader_dados as TD, trader_online_dados as OL, trader_grafico as G, trader_carteira as TCA

EM = ["ana@x.com", "bia@x.com", "caio@x.com", "dani@x.com"]
PAT = {e: 100000.0 for e in EM}; CAIXA0 = {e: 100000.0 for e in EM}; CAIXA0["ana@x.com"] = 3000.0     # ana joga com EXATAMENTE 3% de caixa
LANC = {}

def preco(i):
    if i < 8:
        o = 10.0 + 0.02 * i; return o, o + 0.03, o - 0.01, o + 0.02
    if i == 8: return 10.18, 45.0, 10.18, 45.0
    if i < 24: return 45.0, 45.0, 45.0, 45.0
    if i < 48:
        o = 45.0 * (1 + 0.001 * (i - 24)); return o, o * 1.001, o * 0.999, o * 1.001
    return 45.0, 45.0, 45.0, 45.0
cfg = TB.TIMEFRAMES["15m"]; cand = []
for i in range(cfg["n_analise"] + TB.RODADAS * TB.N_REPLAY_MESA):
    o, h, l, c = (10.0, 10.05, 9.95, 10.0) if i < cfg["n_analise"] else preco(i - cfg["n_analise"])
    cand.append({"t": (datetime(2026, 1, 5, 10, 0) + timedelta(minutes=15 * i)).isoformat(), "o": o, "h": h, "l": l, "c": c, "v": 1000})
CEN = {"id": "E2E-SPIKE", "ticker": "TESTE3", "tf": "15m", "n_analise": cfg["n_analise"], "candles": cand, "demo": True}
TD.escolher = lambda tf, semente, banco=None, rodadas=None: CEN
TD._CACHE_CEN[("E2E-SPIKE", "15m")] = CEN

tmp = tempfile.mkdtemp(prefix="e2e_"); banco.usar_sqlite(os.path.join(tmp, "t.db")); banco.migrar_sqlite()
for e in EM: banco._inserir("contas", {"id": "id-" + e, "email": e, "nome": e.split("@")[0], "criado_em": "2026-01-01T00:00:00Z"})
def inserir(email, conta, chave, tipo, valor, dia, desc, meta, agora):
    if chave in LANC: return False
    LANC[chave] = {"email": email, "valor": valor}; return True
def do(e): return sum(v["valor"] for v in LANC.values() if v["email"] == e)
TCA.WG._inserir_credito, TCA.WG.sincronizar, TCA.conta_id = inserir, (lambda e: {}), (lambda e: "id-" + e)
TCA.situacao = lambda e: {"pat": PAT[e] + do(e), "caixa": CAIXA0[e] + do(e)}
ANTIGA = FORMATO == "antiga"
if ANTIGA: EM = EM[:2]
r = OL.criar_sala(EM[0], "15m", None, "rapida" if ANTIGA else FORMATO)
for e in EM[1:]: OL.entrar_na_sala(e, r["codigo"], None)
if ANTIGA:                                                   # sala gravada antes da mesa: sem formato → regras antigas (motor 1)
    d = OL._row(r["id"])["dados"]; d["sala"].pop("formato"); banco._atualizar_n("tb_partidas", {"id": r["id"]}, {"dados": banco._js(d)})
OL.iniciar(r["id"], EM[0], None); PID = r["id"]
EST = {e: {} for e in EM}; TRAFEGO = {e: [] for e in EM}; LOCK = threading.Lock()

HOST = """<!doctype html><meta charset=utf-8><body style="margin:0;background:#111"><iframe id=f style="width:420px;height:780px;border:0" src="/comp/index.html"></iframe><script>
const u=new URLSearchParams(location.search).get('u'),f=document.getElementById('f');let ready=false;
async function render(){const r=await fetch('/render?u='+u),j=await r.json();window.__estado=j.estado;if(j.args)f.contentWindow.postMessage({type:'streamlit:render',args:j.args,disabled:false,theme:{}},'*')}
window.addEventListener('message',async ev=>{const d=ev.data;if(!d||!d.isStreamlitMessage)return;
 if(d.type==='streamlit:componentReady'){ready=true;render()}
 else if(d.type==='streamlit:setComponentValue'){await fetch('/evento?u='+u,{method:'POST',body:JSON.stringify(d.value)});render()}});
setInterval(()=>{if(ready)render()},1000);</script>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ct="application/json"):
        b = body if isinstance(body, bytes) else body.encode(); self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/host": return self._send(200, HOST, "text/html; charset=utf-8")
        if u.path.startswith("/comp/"):
            f = os.path.join(PROJ, "trader_front", u.path[6:]); return self._send(200, open(f, "rb").read(), mimetypes.guess_type(f)[0] or "text/html")
        if u.path == "/render":
            e = EM[int(q["u"][0])]; now = time.time()
            b = OL.ler(PID, e, now)
            if b.get("estado") != "jogo" or b["p"]["fase"] == "fim":
                out = {"estado": "fim", "pontos": b.get("p", {}).get("pontos")}
            else:
                args = G.args_mesa(b["v"], b["p"], EST[e], now); out = {"estado": b["p"]["fase"], "args": args}
            s = json.dumps(out, default=str); TRAFEGO[e].append(s); return self._send(200, s)
        if u.path == "/estado":
            d = OL._row(PID)["dados"]["p"]
            return self._send(200, json.dumps({"fase": d["fase"], "rodada": d["rodada"], "pontos": d["pontos"], "lanc": LANC, "caixa": {e: TCA.situacao(e)["caixa"] for e in EM},
                "resultados": {k: {"pontos": v["pontos"], "pnl": (v.get("fin") or {}).get("pnl"), "limite": v.get("limite_atingido"), "ops": [(t["direcao"], round(t["entrada"], 4), round(t["saida"], 4), t["motivo"]) for t in v["operacoes"]]} for k, v in d["resultados"].items()},
                "n_acoes": len(d["acoes"])}, default=str))
        if u.path == "/salvar":
            e = EM[int(q["u"][0])]; OL.salvar(PID, e, {"direcao": "alta", "tipo": "continuacao", "confianca": 3, "entrada": 10.0, "stop": 9.8, "alvo": 10.6}, None, time.time()); return self._send(200, "{}")
        if u.path == "/trafego":
            e = EM[int(q["u"][0])]; return self._send(200, json.dumps(TRAFEGO[e]))
        self._send(404, "{}")
    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query); e = EM[int(q["u"][0])]
        val = json.loads(self.rfile.read(int(self.headers["Content-Length"]) or 0) or "null"); now = time.time()
        with LOCK:
            b = OL.ler(PID, e, now)
            if b.get("estado") == "jogo":
                G.processar(b["p"], val, EST[e], e, b["v"]["candles"][-1]["c"], now, OL.Ops(PID, e))
        self._send(200, "{}")
print("PRONTO", PID, flush=True)
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
