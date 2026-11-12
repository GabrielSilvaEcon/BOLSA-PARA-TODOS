"""Visual da aba "Meu patrimônio" da Wallet Game (home-broker com cara de jogo).

Só apresenta dados que a Wallet Game já calcula (competicao.patrimonio, posições, histórico, missões). Nenhuma conta nova de
preço médio, resultado ou saldo é feita aqui, e nada é inventado: sem histórico não há gráfico, sem posição não há linha.
As funções `html_*` não dependem do Streamlit (testáveis); `mostrar` desenha a tela.
"""
from __future__ import annotations

import html
from datetime import date, datetime

import arte_tickerhunters as AT
import ativos_jogo as A
import competicao as C
import moedas_arte as MA
from wallet_game import moeda

try:
    import streamlit as st
except ImportError:           # testes puros rodam sem o Streamlit
    st = None

Q = "html body .stApp.stApp"
VERDE, VERMELHO, NEUTRO = "#2EE59D", "#FF5B6E", "#8FA6D8"
_UNID = {"acao": "ações", "fii": "cotas", "etf": "cotas", "fundo": "cotas", "rf": "títulos", "cripto": "un."}


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _pct(v: float, casas: int = 1) -> str:
    return f"{v:+.{casas}f}%".replace(".", ",")


def _cor(v) -> str:
    return VERDE if (v or 0) > 0 else (VERMELHO if (v or 0) < 0 else NEUTRO)


# ------------------------------------------------------------------ dados
def serie_patrimonio(est: dict, pat_liq: float) -> list[tuple[str, float]]:
    """Patrimônio de cada fechamento (sem bônus) + o valor de agora. Vazio/1 ponto = sem gráfico."""
    pts = []
    for x in est.get("hist") or []:
        try:
            pts.append((str(x["d"]), C._liq(x)))
        except Exception:
            continue
    if pts:
        pts.append((date.today().isoformat(), float(pat_liq)))
    return pts


def variacao(pts: list[tuple[str, float]], hoje: date | None = None) -> tuple[float | None, str]:
    """Variação % nos últimos 30 dias; se a carteira é mais nova, desde o início. (None, '') sem dados."""
    if len(pts) < 2:
        return None, ""
    hoje = hoje or date.today()
    base, rot = pts[0], "desde o início"
    for d, v in pts[:-1]:
        try:
            dias = (hoje - datetime.fromisoformat(d[:10]).date()).days
        except ValueError:
            continue
        if dias >= 30:
            base, rot = (d, v), "últimos 30 dias"
    if base[1] <= 0:
        return None, ""
    return (pts[-1][1] / base[1] - 1) * 100, rot


def posicoes(est: dict) -> list[dict]:
    """Posições da carteira já com valor e resultado (mesma conta da tabela antiga: último preço / preço médio)."""
    out = []
    pat = max(C.patrimonio(est), 1.0)
    for tk, p in (est.get("pos") or {}).items():
        px = (est.get("ult") or {}).get(tk) or p["pm"]
        v = p["q"] * px
        c = A.classe(tk)
        out.append({"tk": tk, "classe": c, "q": p["q"], "pm": p["pm"], "px": px, "valor": v,
                    "res": (px / p["pm"] - 1) * 100 if p["pm"] else 0.0, "peso": v / pat * 100})
    return sorted(out, key=lambda r: -r["valor"])


def investido(est: dict) -> float:
    return sum(r["valor"] for r in posicoes(est))


def missao_ativa(res: dict | None) -> dict | None:
    """Primeira missão ainda não feita (diárias, semanais, especiais). Devolve a do sistema atual, sem criar outra."""
    if not res:
        return None
    ms = res.get("missoes") or []
    for per in ("dia", "semana", "especial"):
        for m in ms:
            if m.get("periodo") == per and not m.get("feita"):
                return m
    return None


def fala(n_pos: int, ret: float | None) -> tuple[str, str]:
    """(texto do balão, pose do Caramelo) conforme a situação real da carteira."""
    if n_pos == 0:
        return "Vamos montar sua carteira? Toque em Comprar!", "animado"
    if ret is None or abs(ret) < 0.05:
        return "Carteira montada! Acompanhe e diversifique.", "animado"
    if ret > 0:
        return "Boa estratégia! Sua carteira está indo bem!", "celebrando"
    return "Oscilar faz parte. Diversificar ajuda a segurar!", "pensativo"


# ------------------------------------------------------------------ HTML
def spark(vals: list[float], cor: str, uid: str, w: int = 160, h: int = 52, ponto: bool = False) -> str:
    """Mini gráfico de linha com preenchimento em degradê (SVG, sem biblioteca)."""
    v = [float(x) for x in vals if x == x]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    amp = max(hi - lo, abs(hi) * 0.004, 1e-9)           # variação minúscula aparece quase reta, sem exagerar
    pad = 4
    xs = [pad + i * (w - 2 * pad) / (len(v) - 1) for i in range(len(v))]
    ys = [h - pad - (x - lo) / amp * (h - 2 * pad) for x in v]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"{xs[0]:.1f},{h} {pts} {xs[-1]:.1f},{h}"
    gid = f"g{_e(uid)}"
    dot = f"<circle cx='{xs[-1]:.1f}' cy='{ys[-1]:.1f}' r='3.2' fill='#fff' stroke='{cor}' stroke-width='2'/>" if ponto else ""
    return (f"<svg class='cv-sp' viewBox='0 0 {w} {h}' preserveAspectRatio='none' aria-hidden='true'>"
            f"<defs><linearGradient id='{gid}' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{cor}' stop-opacity='.55'/>"
            f"<stop offset='1' stop-color='{cor}' stop-opacity='0'/></linearGradient></defs>"
            f"<polygon points='{area}' fill='url(#{gid})'/>"
            f"<polyline points='{pts}' fill='none' stroke='{cor}' stroke-width='2.4' stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/>{dot}</svg>")


def html_patrimonio(pat: float, caixa: float, inv: float, var: float | None, rot: str, serie: list[float], n_pos: int, ret: float | None) -> str:
    base = var if var is not None else ret
    cor = _cor(base if base is not None and abs(base) >= 0.05 else 0)
    valor = moeda(pat)
    cls = " m" if len(valor) > 14 else ""
    seta = "" if var is not None and abs(var) < 0.05 else ("▲" if (var or 0) > 0 else "▼")
    delta = (f"<div class='cv-dl' style='color:{cor}'><span>{seta}</span><b>{_pct(abs(var) if abs(var) < 0.05 else var)}</b><i>({_e(rot)})</i></div>" if var is not None
             else "<div class='cv-dl sem'>O gráfico aparece depois do primeiro fechamento.</div>")
    texto, pose = fala(n_pos, ret)
    cav = AT.img(AT.pose(pose), 112, alt="Caramelo, o mascote")
    return (f"<div class='cv-card cv-pat'><div class='cv-pl'>"
            f"<div class='cv-tt'>{AT.img('saco_dinheiro', 26)}<span>Meu Patrimônio</span></div>"
            f"<div class='cv-val{cls}'>{_e(valor.replace('T$ ', ''))}<small>T$</small></div>{delta}"
            f"<div class='cv-spw'>{spark(serie, cor, 'pat', 200, 56)}</div></div>"
            f"<div class='cv-pr'><div class='cv-bal'>{_e(texto)}</div><div class='cv-mas'>{cav}</div></div>"
            f"<div class='cv-mini'><div class='cv-m'>{AT.img('moedas_pilha', 34)}<div><span>Disponível</span><b>{_e(moeda(caixa, 0 if caixa >= 1000 else 2))}</b></div></div>"
            f"<div class='cv-m'>{AT.img('grafico_alta', 34)}<div><span>Investido</span><b>{_e(moeda(inv, 0 if inv >= 1000 else 2))}</b></div></div></div></div>")


def html_ativo(r: dict, sp: list[float] | None, i: int) -> str:
    c = r["classe"]
    cl = A.CLASSES.get(c) or {"cor": "#8B6CFF", "icone": "•"}
    rot = A.rotulo(r["tk"])
    codigo = rot.split(" · ")[-1] if " · " in rot else rot
    nome = rot.split(" · ")[0] if " · " in rot else ""
    cor = _cor(r["res"])
    graf = spark(sp, cor, f"a{i}", 120, 38) if sp else "<span class='cv-nsp'>sem histórico</span>"
    return (f"<div class='cv-a'><div class='cv-ai' style='--c:{_e(cl['cor'])}'>{_e(cl['icone'])}</div>"
            f"<div class='cv-an'><b>{_e(codigo)}</b><span>{_e(A.texto_qtd(r['tk'], r['q']))} {_UNID.get(c, 'un.')}</span></div>"
            f"<div class='cv-asp'>{graf}</div>"
            f"<div class='cv-av'><b>{_e(moeda(r['valor']))}</b><span style='color:{cor}'>{_pct(r['res'])}</span></div></div>")


def html_desempenho(ret: float, lucro: float, serie_ret: list[float]) -> str:
    cor = _cor(ret)
    seta = "↗" if ret >= 0 else "↘"
    return (f"<div class='cv-card cv-des'><div class='cv-ch'>{AT.img('barras_verdes', 24)}<b>Meu Desempenho</b>"
            f"<span class='cv-info' title='Inclui ganhos e perdas ainda não realizados (posições abertas). Bônus não contam.'>i</span></div>"
            f"<div class='cv-rent' style='color:{cor}'><span>{seta}</span>{_pct(ret * 100)}</div>"
            f"<div class='cv-rl'>Rentabilidade total</div>"
            f"<div class='cv-spd'>{spark(serie_ret, cor, 'des', 160, 46)}</div>"
            f"<div class='cv-rl2'>Lucro/prejuízo: <b style='color:{cor}'>{_e(moeda(lucro))}</b></div></div>")


def html_missao(m: dict | None, todas: bool = False) -> str:
    cab = f"<div class='cv-ch'>{AT.img('trofeu', 24)}<b>Minhas Missões</b></div>"
    if not m:
        return (f"<div class='cv-card cv-mis'>{cab}<div class='cv-mb'>{AT.img('medalha_estrela', 54)}"
                f"<div class='cv-mt'><b>Tudo em dia!</b><span>Nenhuma missão pendente agora.</span></div></div></div>")
    meta = m.get("meta") or 1
    pct = min(100.0, (m.get("progresso") or 0) / meta * 100)
    rec = m.get("recompensa") or {}
    pr = []
    if rec.get("tc"):
        pr.append(f"{MA.img('tc', 22)}<b>+{int(rec['tc'])}</b>")
    elif rec.get("xp"):
        pr.append(f"<b>+{int(rec['xp'])} XP</b>")
    elif rec.get("capital"):
        pr.append(f"<b>+{_e(moeda(rec['capital'], 0))}</b>")
    return (f"<div class='cv-card cv-mis'>{cab}<div class='cv-mb'>{AT.img('medalha_estrela', 54)}"
            f"<div class='cv-mt'><b>{_e(m['nome'])}</b><span>{(m.get('progresso') or 0):.0f} / {meta}</span>"
            f"<div class='cv-pb'><i style='width:{pct:.0f}%'></i></div></div><div class='cv-rw'>{''.join(pr)}</div></div></div>")


CSS = f"""<style>
{Q} .cv-card{{background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C;border-radius:22px;padding:14px;margin:10px 0;box-shadow:0 8px 22px rgba(2,6,23,.45),inset 0 1px 0 rgba(120,160,255,.14);box-sizing:border-box;max-width:100%}}
{Q} .cv-pat{{display:grid;grid-template-columns:minmax(0,1fr) 118px;gap:6px 8px;position:relative;background:radial-gradient(circle at 85% 20%,rgba(46,229,157,.16),transparent 55%),linear-gradient(160deg,#10204A,#0A1433 78%)}}
{Q} .cv-pl{{min-width:0}}
{Q} .cv-tt{{display:flex;align-items:center;gap:8px;font-weight:800;font-size:1.02rem}}{Q} .cv-tt span{{color:#F4F7FF !important;-webkit-text-fill-color:#F4F7FF !important}}
{Q} .cv-val{{font-weight:900;font-size:clamp(1.55rem,8vw,2.2rem);line-height:1.1;color:#fff;margin:6px 0 2px;letter-spacing:-.01em;overflow-wrap:anywhere;animation:cv-pop .5s ease-out}}
{Q} .cv-val.m{{font-size:clamp(1.3rem,6.6vw,1.8rem)}}
{Q} .cv-val small{{font-size:.5em;font-weight:800;color:#9FB6EA;margin-left:5px}}
{Q} .cv-dl{{display:flex;flex-wrap:wrap;align-items:baseline;gap:5px;font-weight:800;font-size:.92rem}}{Q} .cv-dl i{{font-style:normal;font-weight:600;color:#9FB6EA;font-size:.78rem}}
{Q} .cv-dl.sem{{color:#9FB6EA;font-weight:600;font-size:.78rem}}
{Q} .cv-spw{{margin-top:6px;height:56px}}{Q} .cv-sp{{width:100%;height:100%;display:block}}
{Q} .cv-pr{{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;min-width:0}}
{Q} .cv-bal{{background:#FFE9C2;color:#4A2E08;font-weight:800;font-size:.7rem;line-height:1.2;border-radius:14px 14px 4px 14px;padding:6px 8px;text-align:center;box-shadow:0 3px 8px rgba(0,0,0,.35)}}
{Q} .cv-mas{{animation:cv-flut 3.6s ease-in-out infinite;filter:drop-shadow(0 6px 10px rgba(0,0,0,.4))}}{Q} .cv-mas img{{max-width:100%;height:auto;display:block}}
{Q} .cv-mini{{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:2px}}
{Q} .cv-m{{display:flex;align-items:center;gap:8px;background:rgba(12,24,58,.85);border:1px solid #2B4A8C;border-radius:16px;padding:8px 10px;min-width:0}}
{Q} .cv-m div{{min-width:0}}{Q} .cv-m span{{display:block;font-size:.72rem;color:#9FB6EA;font-weight:700}}{Q} .cv-m b{{display:block;font-size:.98rem;color:#fff;font-weight:900;overflow-wrap:anywhere}}
{Q} .cv-m img{{flex:none;height:30px;width:auto}}
{Q} .cv-ch{{display:flex;align-items:center;gap:8px;color:#F4F7FF;font-size:1rem}}{Q} .cv-ch b{{font-weight:800}}
{Q} .cv-info{{margin-left:auto;width:20px;height:20px;border-radius:50%;border:1.5px solid #7E96CC;color:#9FB6EA;font-size:.7rem;font-weight:800;display:grid;place-items:center;font-style:italic}}
{Q} .cv-ativos{{padding:12px 12px 6px}}
{Q} .cv-a{{display:grid;grid-template-columns:42px minmax(0,1fr) minmax(54px,84px) auto;align-items:center;gap:10px;padding:10px 2px;border-top:1px solid rgba(80,115,190,.28)}}
{Q} .cv-a:first-of-type{{margin-top:8px}}
{Q} .cv-ai{{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:1.3rem;background:radial-gradient(circle at 30% 20%,color-mix(in srgb,var(--c) 55%,#fff),var(--c) 72%);box-shadow:0 3px 0 color-mix(in srgb,var(--c) 45%,#050B1F)}}
{Q} .cv-an b{{display:block;color:#fff;font-weight:900;font-size:1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}{Q} .cv-an span{{color:#9FB6EA;font-size:.8rem;font-weight:600}}
{Q} .cv-asp{{height:34px;min-width:0}}{Q} .cv-nsp{{font-size:.64rem;color:#6F86B8}}
{Q} .cv-av{{text-align:right;white-space:nowrap}}{Q} .cv-av b{{display:block;color:#fff;font-weight:800;font-size:.9rem}}{Q} .cv-av span{{font-weight:900;font-size:.88rem}}
{Q} .cv-vz{{color:#9FB6EA;font-size:.86rem;padding:10px 4px 6px}}
{Q} .cv-des .cv-rent{{display:flex;align-items:center;gap:6px;font-weight:900;font-size:1.6rem;margin-top:8px;line-height:1.1}}{Q} .cv-rl{{color:#9FB6EA;font-size:.8rem;font-weight:700}}{Q} .cv-rl2{{color:#9FB6EA;font-size:.74rem;margin-top:4px}}
{Q} .cv-spd{{height:46px;margin-top:6px}}
{Q} .cv-mb{{display:flex;align-items:center;gap:10px;margin-top:10px}}{Q} .cv-mb img{{flex:none}}
{Q} .cv-mt{{flex:1;min-width:0}}{Q} .cv-mt b{{display:block;color:#fff;font-size:.9rem;line-height:1.2}}{Q} .cv-mt span{{color:#9FB6EA;font-size:.8rem;font-weight:700}}
{Q} .cv-pb{{height:9px;background:#1B2C5C;border-radius:99px;overflow:hidden;margin-top:6px}}{Q} .cv-pb i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#2EE59D,#8BE04E);transition:width .6s}}
{Q} .cv-rw{{flex:none;text-align:center;color:#FFD66B;font-weight:900;font-size:.95rem;display:flex;flex-direction:column;align-items:center;gap:2px}}
{Q} .cv-duo{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:0 10px}}
{Q} .st-key-cv_trade{{margin:12px 0 6px}}
{Q} .st-key-cv_trade [data-testid="stHorizontalBlock"]{{gap:12px !important;flex-wrap:nowrap !important}}
{Q} .st-key-cv_trade [data-testid="stColumn"]{{min-width:0 !important;flex:1 1 0 !important}}
{Q} .st-key-cv_comprar button,{Q} .st-key-cv_vender button{{min-height:58px !important;border-radius:999px !important;width:100% !important;border:0 !important;transition:transform .1s,box-shadow .1s,filter .2s}}
{Q} .st-key-cv_comprar button{{background:linear-gradient(180deg,#38E26B,#12A83C) !important;box-shadow:0 5px 0 #0B7A2B,0 8px 20px rgba(46,229,100,.38) !important}}
{Q} .st-key-cv_vender button{{background:linear-gradient(180deg,#FF5B5B,#D61F2C) !important;box-shadow:0 5px 0 #A0121D,0 8px 20px rgba(255,80,80,.36) !important}}
{Q} .st-key-cv_comprar button:active,{Q} .st-key-cv_vender button:active{{transform:translateY(4px) scale(.985);box-shadow:0 1px 0 rgba(0,0,0,.5) !important}}
{Q} .st-key-cv_comprar button :is(p,span),{Q} .st-key-cv_vender button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:900 !important;font-size:1.15rem !important}}
{Q} .st-key-cv_comprar button:hover,{Q} .st-key-cv_vender button:hover{{filter:brightness(1.08)}}
{Q} .st-key-cv_vt button,{Q} .st-key-cv_vm button{{background:transparent !important;border:0 !important;box-shadow:none !important;min-height:34px !important;width:auto !important;padding:0 6px !important;margin-left:auto}}
{Q} .st-key-cv_vt button :is(p,span),{Q} .st-key-cv_vm button :is(p,span){{color:#2EE59D !important;-webkit-text-fill-color:#2EE59D !important;font-weight:800 !important;font-size:.9rem !important}}
{Q} .st-key-cv_vt,{Q} .st-key-cv_vm{{display:flex;justify-content:flex-end}}
{Q} .cv-sec{{font-weight:800;color:#9FB6EA;font-size:.8rem;letter-spacing:.05em;text-transform:uppercase;margin:12px 2px 6px}}
{Q} .st-key-cv_atalhos [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:8px !important}}{Q} .st-key-cv_atalhos [data-testid="stColumn"]{{min-width:0 !important}}
{Q} .st-key-cv_atalhos button{{border-radius:16px !important;min-height:48px !important;background:linear-gradient(160deg,#10204A,#0A1433) !important;border:1px solid #2B4A8C !important;box-shadow:0 3px 0 #050B1F !important}}
{Q} .st-key-cv_atalhos button :is(p,span){{color:#E8EEFF !important;-webkit-text-fill-color:#E8EEFF !important;font-weight:800 !important;font-size:.82rem !important}}
@keyframes cv-pop{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@keyframes cv-flut{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
{Q} .cv-card{{animation:cv-pop .4s ease-out}}
@media (prefers-reduced-motion:reduce){{{Q} .cv-card,{Q} .cv-val,{Q} .cv-mas{{animation:none !important}}}}
</style>"""
CSS_PARADO = f"<style>{Q} .cv-card,{Q} .cv-val,{Q} .cv-mas{{animation:none !important}}</style>"


# ------------------------------------------------------------------ tela
def _ir(destino: str, lado: str | None = None) -> None:
    st.session_state["wg_sec"] = destino
    st.session_state.pop("cn_sel", None)          # abre na vitrine de ativos
    if lado:
        st.session_state["comp_lado"] = lado


def _alternar(chave: str) -> None:
    st.session_state[chave] = not st.session_state.get(chave, False)


def _sparks(pos: list[dict], limite: int = 8) -> dict:
    """Preço dos últimos 30 dias de cada ativo (só ações/FIIs/ETFs; sem histórico, sem gráfico). Falha nunca derruba a tela."""
    out = {}
    try:
        import carteira as CT
    except Exception:
        return out
    for r in pos[:limite]:
        if r["classe"] not in ("acao", "fii", "etf"):
            continue
        try:
            s = CT._hist(r["tk"], "1mo")
            if s is not None and len(s) >= 2:
                out[r["tk"]] = [float(x) for x in s.values[-30:]]
        except Exception:
            continue
    return out


def mostrar(est: dict, res: dict | None) -> None:
    """Desenha: patrimônio com o Caramelo, meus ativos, Comprar/Vender, desempenho e missão."""
    import fx_arte as FX
    st.markdown(CSS + ("" if FX.animar_padrao(st.session_state) else CSS_PARADO), unsafe_allow_html=True)
    pat = C.patrimonio(est)
    cap, apt = C.capital_de(est), C.aportes(est)
    ret = (pat - apt) / cap - 1                      # mesma conta da Wallet Game: bônus não contam como resultado
    pos = posicoes(est)
    inv = sum(r["valor"] for r in pos)
    pts = serie_patrimonio(est, pat - apt)
    var, rot = variacao(pts)
    serie = [v for _, v in pts]
    st.markdown(html_patrimonio(pat, float(est.get("caixa", 0)), inv, var, rot, serie, len(pos), ret), unsafe_allow_html=True)

    # ---- Meus ativos
    ver_todos = st.session_state.get("cv_todos", False)
    mostra = pos if ver_todos else pos[:3]
    sp = _sparks(mostra)
    linhas = "".join(html_ativo(r, sp.get(r["tk"]), i) for i, r in enumerate(mostra))
    if not pos:
        linhas = "<div class='cv-vz'>Nenhuma posição ainda. Todo o seu capital está disponível: toque em Comprar para começar.</div>"
    st.markdown(f"<div class='cv-card cv-ativos'><div class='cv-ch'>{AT.img('bau_aberto', 26)}<b style='font-size:1.08rem'>Meus Ativos</b></div>{linhas}</div>", unsafe_allow_html=True)
    if len(pos) > 3:
        st.button(f"Ver menos ↑" if ver_todos else f"Ver todos ({len(pos)}) →", key="cv_vt", on_click=_alternar, args=("cv_todos",))

    # ---- Comprar / Vender (abrem o fluxo de negociação que já existe)
    with st.container(key="cv_trade"):
        c1, c2 = st.columns(2)
        c1.button("Comprar", key="cv_comprar", icon=":material/shopping_cart:", on_click=_ir, args=("Negociar", "Comprar"), width="stretch")
        c2.button("Vender", key="cv_vender", icon=":material/north_east:", on_click=_ir, args=("Negociar", "Vender"), width="stretch",
                  disabled=not pos, help=None if pos else "Você ainda não tem ativos para vender.")

    # ---- Desempenho + Missões
    sr = [(v / cap - 1) * 100 for _, v in pts] if pts else []
    lucro = pat - apt - cap
    st.markdown("<div class='cv-duo'>" + html_desempenho(ret, lucro, sr) + html_missao(missao_ativa(res)) + "</div>", unsafe_allow_html=True)
    if res:
        st.button("Ver todas as missões →", key="cv_vm", on_click=_ir, args=("Missões do jogo",))
        st.markdown("<div class='cv-sec'>Mais do jogo</div>", unsafe_allow_html=True)
        with st.container(key="cv_atalhos"):
            c1, c2, c3 = st.columns(3)
            c1.button("Bônus", key="cv_at_b", icon=":material/redeem:", on_click=_ir, args=("Bônus e sequência",), width="stretch")
            c2.button("Conquistas", key="cv_at_c", icon=":material/emoji_events:", on_click=_ir, args=("Conquistas",), width="stretch")
            c3.button("Ranking", key="cv_at_r", icon=":material/leaderboard:", on_click=_ir, args=("Classificação",), width="stretch")
