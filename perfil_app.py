"""Perfil do jogador e Passe de temporada (Fase 4). Só apresentação: as regras estão em nivel.py, emblemas.py e passe.py.

Nada daqui grava dados nem mexe em XP, Ticker Coins ou T$. O mascote é sempre o Caramelo (sem avatar personalizado) e o passe é gratuito.
Educacional: carteira virtual, sem dinheiro real, sem recomendação de investimento.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

import streamlit as st

import emblemas as EM
import emblemas_app as EMA
import jornada as JO
import jornada_arte as ART
import nivel as NV
import novidades as NO
import visual_loja as VL
import passe as PA
import usuarios

_e = lambda x: html.escape(str(x), quote=True)
BRT = timezone(timedelta(hours=-3))

CSS = """<style>
.pf-hero,.pf-top{max-width:560px;margin:8px auto 12px;border-radius:24px;padding:16px;background:linear-gradient(135deg,#3A2C86,#1B1545);border:1px solid rgba(197,179,255,.45);box-shadow:0 4px 0 rgba(10,8,40,.55)}
.pf-en{font-size:1.05rem;margin-left:4px}
.pf-id{display:flex;align-items:center;gap:14px}
.pf-id .tx{min-width:0;flex:1}
.pf-nome{font-weight:900;font-size:1.25rem;line-height:1.15;color:#fff !important;overflow-wrap:anywhere}
.pf-tit{display:inline-block;margin-top:6px;padding:3px 12px;border-radius:999px;font-weight:800;font-size:.8rem;background:rgba(242,184,75,.18);border:1px solid rgba(242,184,75,.6);color:#FFD66B !important}
.pf-niv{margin-top:6px;font-size:.85rem;font-weight:800;color:#CFC8EE !important}
.pf-bar,.ps-bar{height:12px;border-radius:999px;background:rgba(255,255,255,.14);overflow:hidden;margin-top:12px}
.pf-bar i,.ps-bar i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#7C5CFF,#3DDC97)}
.pf-leg{margin-top:6px;font-size:.78rem;color:#CFC8EE !important}
.pf-grid{max-width:560px;margin:0 auto;display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.pf-k{border-radius:18px;padding:12px;background:#241C4D;border:1px solid rgba(197,179,255,.28);box-shadow:0 3px 0 rgba(0,0,0,.25)}
.pf-k .v{font-weight:900;font-size:1.35rem;color:#fff !important}
.pf-k .l{margin-top:2px;font-size:.76rem;font-weight:700;color:#CFC8EE !important}
.pf-sec,.ps-sec{max-width:560px;margin:20px auto 8px;font-weight:900;font-size:.9rem;letter-spacing:.04em;text-transform:uppercase;color:#C5B3FF !important}
.pf-hon{max-width:560px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px}
.pf-chip{padding:6px 12px;border-radius:999px;font-weight:800;font-size:.8rem;background:#241C4D;border:1px solid rgba(242,184,75,.5);color:#F6F3FF !important}
.pf-vazio{max-width:560px;margin:0 auto;font-size:.85rem;color:#BDB5E6 !important}
.pf-emb{max-width:560px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px}
.pf-emb span{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;font-size:1.4rem;background:#241C4D;border:1px solid rgba(197,179,255,.35)}
.pf-nota,.ps-nota{max-width:560px;margin:14px auto 0;font-size:.76rem;line-height:1.35;color:#BDB5E6 !important}
.ps-h{display:flex;justify-content:space-between;align-items:center;gap:10px}
.ps-h b{font-size:1.1rem;font-weight:900;color:#fff !important}
.ps-livre{padding:3px 10px;border-radius:999px;font-weight:800;font-size:.72rem;background:rgba(61,220,151,.16);border:1px solid #3DDC97;color:#3DDC97 !important}
.ps-datas{margin-top:8px;font-size:.82rem;font-weight:700;color:#EDE9FF !important}
.ps-datas i{font-style:normal;color:#FFD66B !important}
.ps-xp{margin-top:10px;font-size:1.6rem;font-weight:900;color:#fff !important}
.ps-xp small{font-size:.8rem;font-weight:700;color:#CFC8EE !important}
.ps-leg{margin-top:6px;font-size:.8rem;color:#CFC8EE !important}
.ps-m{max-width:560px;margin:0 auto 8px;display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:18px;background:#241C4D;border:1px solid rgba(255,255,255,.12)}
.ps-m.ok{border-color:rgba(61,220,151,.7);background:linear-gradient(135deg,rgba(61,220,151,.16),#241C4D)}
.ps-m.prox{border-color:#F2B84B}
.ps-m .s{flex:0 0 46px;height:46px;border-radius:50%;display:grid;place-items:center;font-size:1.5rem;background:#2A2358}
.ps-m.ok .s{background:radial-gradient(circle at 30% 20%,rgba(255,255,255,.35),transparent 55%),#3DDC97}
.ps-m:not(.ok) .s{filter:grayscale(1);opacity:.6}
.ps-m .t{min-width:0;flex:1}
.ps-m .n{font-weight:800;font-size:.92rem;color:#F6F3FF !important}
.ps-m .d{font-size:.76rem;color:#CFC8EE !important}
.ps-m .x{font-weight:800;font-size:.78rem;white-space:nowrap;color:#CFC8EE !important}
.ps-m.ok .x{color:#3DDC97 !important}
.ps-h2{max-width:560px;margin:0 auto 8px;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 12px;border-radius:16px;background:#1D1642;border:1px solid rgba(255,255,255,.12)}
.ps-h2 .n{font-weight:800;font-size:.9rem;color:#F6F3FF !important}
.ps-h2 .d{font-size:.74rem;color:#CFC8EE !important}
.ps-h2 .r{text-align:right;font-weight:800;font-size:.82rem;color:#FFD66B !important}
@media (max-width:380px){.pf-grid{gap:8px}.pf-k{padding:10px}.pf-k .v{font-size:1.15rem}.pf-nome{font-size:1.1rem}.pf-id{gap:10px}.ps-m{gap:8px;padding:8px 10px}.ps-m .s{flex-basis:40px;height:40px;font-size:1.3rem}.ps-m .x{font-size:.72rem}.ps-xp{font-size:1.4rem}}
</style>"""


# ------------------------------------------------------------------ dados
def _agora() -> datetime:
    return datetime.now(timezone.utc).astimezone(BRT)


def _wallet() -> tuple[dict | None, dict | None]:
    """(resultado do Wallet Game, carteira) da pessoa, ou (None, None) se ela não participa ou o banco não responde. Nunca levanta erro."""
    try:
        a = usuarios.ator()
        if not a:
            return None, None
        import banco
        import competicao_app as CA
        import wallet_game_app as WGA
        if not banco.cfg_disponivel():
            return None, None
        pessoa = CA._pessoa(a)
        if not pessoa["perfil"].get("aceite"):
            return None, pessoa.get("cart")
        return WGA.resultado(a), pessoa.get("cart")
    except Exception:
        return None, None


def _barra(pct: float, classe: str = "pf-bar") -> str:
    return f"<div class='{classe}'><i style='width:{max(0.0, min(1.0, pct)) * 100:.0f}%'></i></div>"


# ------------------------------------------------------------------ HTML
def html_perfil(nome: str, est: dict, r: dict, unidades: int, col: list[dict], titulos: list[str], ap: dict | None = None) -> str:
    ok, total = EM.totais(col)
    leg = ("Nível máximo alcançado." if est["maximo"] else f"Faltam {est['falta']} XP para {est['proximo_titulo']}")
    ap = ap or {}
    enfeite = "".join(_e(x["emoji"]) for x in (ap.get("selo"), {"emoji": ap.get("distintivo")} if isinstance(ap.get("distintivo"), str) else ap.get("distintivo")) if x and x.get("emoji"))
    fundo = VL.estilo_fundo(ap.get("fundo"))
    hero = (f"<div class='pf-hero'{(' style=' + chr(34) + fundo + chr(34)) if fundo else ''}><div class='pf-id'>{VL.html_moldura(ART.mascote(humor='perfil', tamanho=88), ap.get('moldura'))}"
            f"<div class='tx'><div class='pf-nome'>{_e(nome)}{(' <span class=' + chr(39) + 'pf-en' + chr(39) + '>' + enfeite + '</span>') if enfeite else ''}</div><span class='pf-tit'>{_e(est['titulo'])}</span>"
            f"<div class='pf-niv'>Nível {est['nivel']} · {est['xp']} XP</div></div></div>"
            f"{_barra(est['pct'])}<div class='pf-leg'>{_e(leg)}</div></div>")
    kpis = (("XP de estudo", r["xp"]), ("Ofensiva atual", f"{r['ofensiva']} d"), ("Melhor ofensiva", f"{r.get('melhor_ofensiva', 0)} d"),
            ("Lições feitas", r["licoes_feitas"]), ("Unidades completas", unidades), ("Emblemas", f"{ok}/{total}"))
    grade = "<div class='pf-grid'>" + "".join(f"<div class='pf-k'><div class='v'>{_e(v)}</div><div class='l'>{_e(l)}</div></div>" for l, v in kpis) + "</div>"
    honras = [f"🎖️ {t}" for t in titulos]
    hon = ("<div class='pf-hon'>" + "".join(f"<span class='pf-chip'>{_e(h)}</span>" for h in honras) + "</div>") if honras else (
        "<div class='pf-vazio'>Ainda sem honrarias. Estude na Jornada e suba no passe da temporada para ganhar as primeiras.</div>")
    emb = [i["emblema"] for c in col for i in c["itens"] if i["ok"]][:12]
    embl = ("<div class='pf-emb'>" + "".join(f"<span>{_e(x)}</span>" for x in emb) + "</div>") if emb else (
        "<div class='pf-vazio'>Seus emblemas aparecem aqui quando você conquistar o primeiro.</div>")
    nota = ("<div class='pf-nota'>O perfil mostra só o que você já fez no app. Emblemas e títulos são honrarias: não pagam XP, "
            "Ticker Coins nem T$.</div>")
    return (hero + grade + "<div class='pf-sec'>Honrarias</div>" + hon + "<div class='pf-sec'>Emblemas</div>" + embl + nota)


def html_passe(e: dict, hist: list[dict]) -> str:
    quando = "Temporada encerrada" if e["encerrada"] else ("Termina hoje" if e["dias_restantes"] == 0 else
                                                          f"Faltam {e['dias_restantes']} dia{'s' if e['dias_restantes'] != 1 else ''}")
    if e["completo"]:
        leg = "Passe completo! Você chegou ao último marco da temporada."
    else:
        p = e["proximo"]
        leg = f"Faltam {e['falta']} XP para o {p['nome']} ({p['simbolo']})"
    topo = (f"<div class='pf-top'><div class='ps-h'><b>{_e(e['rotulo'])}</b><span class='ps-livre'>Passe gratuito</span></div>"
            f"<div class='ps-datas'>{PA.data_br(e['inicio'])} <i>até</i> {PA.data_br(e['fim'])} · {_e(quando)}</div>"
            f"<div class='ps-xp'>{e['xp']} <small>XP de estudo na temporada</small></div>{_barra(e['pct'], 'ps-bar')}"
            f"<div class='ps-leg'>{_e(leg)} · {e['feitos']}/{e['total']} marcos</div></div>")
    linhas = []
    for m in e["marcos"]:
        cls = "ok" if m["ok"] else ("prox" if e["proximo"] and m["n"] == e["proximo"]["n"] else "")
        linhas.append(f"<div class='ps-m {cls}'><div class='s'>{_e(m['simbolo'])}</div><div class='t'><div class='n'>{_e(m['nome'])}</div>"
                      f"<div class='d'>{_e(m['honraria'])}</div></div><div class='x'>{'✓ ' if m['ok'] else ''}{m['xp']} XP</div></div>")
    if hist:
        h = "".join(f"<div class='ps-h2'><div><div class='n'>{_e(x['rotulo'])}</div><div class='d'>{PA.data_br(x['inicio'])} a {PA.data_br(x['fim'])}</div></div>"
                    f"<div class='r'>{x['feitos']}/{x['total']} marcos<br>{x['xp']} XP</div></div>" for x in hist)
    else:
        h = "<div class='pf-vazio'>Quando uma temporada terminar, o resultado dela fica guardado aqui.</div>"
    nota = ("<div class='ps-nota'>O passe é gratuito e acompanha só o XP de estudo da Jornada feito dentro do mês. Os marcos são honrarias do perfil: "
            "não pagam XP, Ticker Coins nem T$. Cada temporada começa do zero no dia 1.</div>")
    return (topo + "<div class='ps-sec'>Marcos da temporada</div>" + "".join(linhas)
            + "<div class='ps-sec'>Temporadas anteriores</div>" + h + nota)


# ------------------------------------------------------------------ telas
def _xp_dia(p: dict) -> dict:
    return JO._jor(p)["xp_dia"]


def tela_passe(prog) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    p = prog()
    hoje = _agora().date()
    xd = _xp_dia(p)
    st.markdown(html_passe(PA.estado(xd, hoje), PA.historico(xd, hoje)), unsafe_allow_html=True)


def tela_perfil(prog) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    p = prog()
    r = {**JO.resumo(p), "melhor_ofensiva": JO.melhor_ofensiva(p)}
    est = NV.estado(r["xp"])
    unidades = sum(1 for u in JO.mapa(p) if u.get("completa"))
    res, cart = _wallet()
    col = EM.colecao(EMA.contexto_da_tela(res, cart))
    u = usuarios.usuario()
    nome = (u or {}).get("nome") or "Jogador"
    pas = PA.estado(_xp_dia(p), _agora().date())
    try:
        import loja_aparencia as LA
        ap = LA.atual()
    except Exception:
        ap = {}
    st.markdown(VL.CSS_MOLDURA, unsafe_allow_html=True)
    st.markdown(html_perfil(nome, est, r, unidades, col, pas["titulos"], ap), unsafe_allow_html=True)


# ------------------------------------------------------------------ celebração de novidades (emblema novo / marco do passe)
CSS_FESTA = """<style>
.cl-f{position:relative;overflow:hidden;margin:8px 0 12px;padding:16px 14px;border-radius:24px;text-align:center;background:linear-gradient(135deg,#4B34A8,#1B1545);
 border:1px solid rgba(255,214,107,.75);box-shadow:0 0 22px rgba(255,214,107,.28)}
.cl-f .t{font-weight:900;font-size:1.2rem;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}
.cl-f .l{display:flex;align-items:center;justify-content:center;gap:10px;margin-top:10px;padding:8px 10px;border-radius:16px;background:rgba(255,255,255,.08);border:1px solid var(--c,#C5B3FF)}
.cl-f .l b{font-size:1.7rem;line-height:1}
.cl-f .l span{font-weight:800;color:#fff !important;-webkit-text-fill-color:#fff !important;text-align:left;font-size:.95rem}
.cl-f .l small{display:block;font-weight:500;color:#C5B3FF !important;-webkit-text-fill-color:#C5B3FF !important;font-size:.76rem}
.cl-f i{position:absolute;top:-12px;width:8px;height:14px;border-radius:2px;opacity:.9;animation:cl-cai 2.8s linear infinite}
.cl-f i:nth-child(1){left:8%;background:#FFD66B}.cl-f i:nth-child(2){left:26%;background:#3DDC97;animation-delay:.5s}
.cl-f i:nth-child(3){left:46%;background:#FF6B8A;animation-delay:1s}.cl-f i:nth-child(4){left:66%;background:#8B6CFF;animation-delay:.3s}
.cl-f i:nth-child(5){left:86%;background:#FFD66B;animation-delay:.8s}
@keyframes cl-cai{0%{transform:translateY(0) rotate(0)}100%{transform:translateY(190px) rotate(300deg);opacity:.2}}
@media (prefers-reduced-motion:reduce){.cl-f i{animation:none;display:none}}
</style>"""
CSS_FESTA = "".join(l.strip() for l in CSS_FESTA.splitlines())


def html_festa(emblemas: list[dict], marcos: list[dict], fx: dict | None = None) -> str:
    """Cartão de comemoração. `emblemas` = itens da coleção; `marcos` = itens de PA.marcos_de. Nada aqui paga XP, TC ou T$."""
    linhas = [f"<div class='l' style='--c:{html.escape(e['cor'])}'><b>{html.escape(e['emblema'])}</b>"
              f"<span>Emblema: {html.escape(e['nome'])}<small>{html.escape(e['descricao'])}</small></span></div>" for e in emblemas]
    linhas += [f"<div class='l' style='--c:#3DDC97'><b>{html.escape(m['simbolo'])}</b>"
               f"<span>Passe: {html.escape(m['nome'])}<small>{html.escape(m['honraria'])} · {m['xp']} XP na temporada</small></span></div>" for m in marcos]
    n = len(linhas)
    conf = VL.html_confete(fx, 10) if fx else "<i></i><i></i><i></i><i></i><i></i>"
    return ((VL.CSS_CONFETE if fx else "") + f"<div class='cl-f'>{conf}<div class='t'>{'Nova conquista!' if n == 1 else 'Novas conquistas!'}</div>"
            + "".join(linhas) + "</div>")


def _visto(prog, set_prog, emb: list[str], passe: list[str]) -> None:
    p = prog()
    p["jornada"] = NO.registrar(JO._jor(p), emb, passe)
    set_prog(p)


def _abrir_perfil_festa(prog, set_prog, emb, passe) -> None:
    _visto(prog, set_prog, emb, passe)
    st.session_state["jor_vista"] = "perfil"


_POP_CSS = ("<style>html body [data-testid='stDialog'] [role='dialog'] " + '.cl-pop{display:flex;align-items:center;gap:12px;background:url(data:image/svg+xml;utf8,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20viewBox=%270%200%20400%20200%27%20preserveAspectRatio=%27xMidYMax%20slice%27%3E%3Cdefs%3E%3ClinearGradient%20id=%27g%27%20x1=%270%27%20y1=%270%27%20x2=%270%27%20y2=%271%27%3E%3Cstop%20offset=%270%27%20stop-color=%27%232EE59D%27%20stop-opacity=%27.14%27/%3E%3Cstop%20offset=%271%27%20stop-color=%27%232EE59D%27%20stop-opacity=%270%27/%3E%3C/linearGradient%3E%3C/defs%3E%3Cg%20stroke-width=%273%27%20stroke-linecap=%27round%27%20opacity=%27.2%27%3E%3Cg%20stroke=%27%232EE59D%27%3E%3Cpath%20d=%27M250%20150v-40M250%20135v-20%27/%3E%3Cpath%20d=%27M280%20140v-50%27/%3E%3Cpath%20d=%27M310%20120v-60%27/%3E%3Cpath%20d=%27M340%20100v-60%27/%3E%3Cpath%20d=%27M370%2080v-55%27/%3E%3C/g%3E%3Cg%20stroke=%27%23FF5B6E%27%3E%3Cpath%20d=%27M220%20160v-30%27/%3E%3Cpath%20d=%27M190%20170v-25%27/%3E%3C/g%3E%3C/g%3E%3Cg%20fill=%27%232EE59D%27%20opacity=%27.12%27%3E%3Crect%20x=%27243%27%20y=%27115%27%20width=%2714%27%20height=%2728%27%20rx=%273%27/%3E%3Crect%20x=%27273%27%20y=%2798%27%20width=%2714%27%20height=%2734%27%20rx=%273%27/%3E%3Crect%20x=%27303%27%20y=%2775%27%20width=%2714%27%20height=%2738%27%20rx=%273%27/%3E%3Crect%20x=%27333%27%20y=%2755%27%20width=%2714%27%20height=%2736%27%20rx=%273%27/%3E%3Crect%20x=%27363%27%20y=%2735%27%20width=%2714%27%20height=%2734%27%20rx=%273%27/%3E%3C/g%3E%3Cg%20fill=%27%23FF5B6E%27%20opacity=%27.12%27%3E%3Crect%20x=%27213%27%20y=%27135%27%20width=%2714%27%20height=%2720%27%20rx=%273%27/%3E%3Crect%20x=%27183%27%20y=%27148%27%20width=%2714%27%20height=%2716%27%20rx=%273%27/%3E%3C/g%3E%3Cpath%20d=%27M20%20175%20L90%20150%20L140%20160%20L200%20120%20L260%20125%20L330%2070%20L395%2025%20L395%20200%20L20%20200Z%27%20fill=%27url%28%23g%29%27/%3E%3Cpath%20d=%27M20%20175%20L90%20150%20L140%20160%20L200%20120%20L260%20125%20L330%2070%20L395%2025%27%20fill=%27none%27%20stroke=%27%2336B7E8%27%20stroke-width=%273%27%20opacity=%27.22%27/%3E%3Cg%20fill=%27%23FFD76A%27%20opacity=%27.14%27%3E%3Ccircle%20cx=%2740%27%20cy=%2730%27%20r=%272%27/%3E%3Ccircle%20cx=%27120%27%20cy=%2755%27%20r=%271.6%27/%3E%3Ccircle%20cx=%27190%27%20cy=%2725%27%20r=%272%27/%3E%3Ccircle%20cx=%2770%27%20cy=%2795%27%20r=%271.5%27/%3E%3Ccircle%20cx=%27160%27%20cy=%2785%27%20r=%271.5%27/%3E%3C/g%3E%3C/svg%3E) right bottom/auto 120% no-repeat,radial-gradient(circle at 15% 0%,rgba(242,184,75,.2),transparent 55%),linear-gradient(160deg,#2A2160,#1A1440 80%);border:1px solid #4B3F9A;border-radius:16px;padding:8px 12px;margin:6px 0;box-shadow:0 0 14px rgba(242,184,75,.14)}'.replace("html body [data-testid='stDialog'] [role='dialog'] ", "")
            + "html body [data-testid='stDialog'] [role='dialog'] .cl-pop .ic{flex:none;display:grid;place-items:center;width:48px;font-size:2rem;line-height:1}"
              "html body [data-testid='stDialog'] [role='dialog'] .cl-pop .tx b{display:block;color:#FFD66B;font-size:1rem;font-weight:900}"
              "html body [data-testid='stDialog'] [role='dialog'] .cl-pop .tx span{color:#EDE9FF;font-size:.9rem}</style>")


def html_pop(emblemas: list[dict], marcos: list[dict]) -> str:
    """Mesmo cartão dos pop-ups da Wallet Game (`wg-pop`): ícone, título dourado e descrição. Nada aqui paga XP, TC ou T$."""
    def linha(ic, t, d):
        return f"<div class='cl-pop'><div class='ic'>{html.escape(ic)}</div><div class='tx'><b>{html.escape(t)}</b><span>{html.escape(d)}</span></div></div>"
    return "".join([linha(e["emblema"], "Emblema: " + e["nome"], e["descricao"]) for e in emblemas]
                   + [linha(m["simbolo"], "Passe: " + m["nome"], f"{m['honraria']} · {m['xp']} XP na temporada") for m in marcos])


def _fechar_festa(prog, set_prog, emb, passe, perfil: bool) -> None:
    _visto(prog, set_prog, emb, passe)
    if perfil:
        st.session_state["jor_vista"] = "perfil"
    st.rerun()


def _conteudo_festa(itens, marcos, fx, prog, set_prog, emb, passe) -> None:
    unico = len(itens) == 1 and not marcos                       # um emblema novo: animação própria (fx_arte); vários itens: cartões do pop-up
    feito = False
    if unico:
        try:
            import fx_arte as FX
            e = itens[0]
            st.markdown(FX.CSS + FX.html_emblema(e["nome"], e["descricao"], "raro", emoji=e["emblema"], animar=FX.animar_padrao(st.session_state),
                                                 cores=(fx or {}).get("cores")), unsafe_allow_html=True)
            feito = True
        except Exception:
            feito = False
    if not feito:
        st.markdown(_POP_CSS + html_pop(itens, marcos), unsafe_allow_html=True)
    if st.button("Legal!", key="jor_festa_ok", type="primary", width="stretch"):
        _fechar_festa(prog, set_prog, emb, passe, False)
    if st.button("Ver no perfil", key="jor_festa_perfil", width="stretch"):
        _fechar_festa(prog, set_prog, emb, passe, True)


def celebrar(prog, set_prog) -> None:
    """Mostra uma vez cada emblema novo e marco novo do passe, num pop-up no padrão dos demais. Na primeira leitura só registra o que já existia.
    Fechar o pop-up pelo X conta como visto (não reaparece). Nunca levanta erro."""
    try:
        p = prog()
        j = JO._jor(p)
        res, cart = _wallet()
        col = EM.colecao(EMA.contexto_da_tela(res, cart))
        pas = PA.estado(_xp_dia(p), _agora().date())
        emb, passe = NO.ids_emblemas(col), NO.ids_passe(pas)
        c = NO.comparar(NO.vistos(j), emb, passe)
        if c["primeira"]:
            _visto(prog, set_prog, emb, passe)
            return
        if not c["emb"] and not c["passe"]:
            return
        itens = [i for k in col for i in k["itens"] if i["id"] in c["emb"]]
        marcos = [m for m in pas["marcos"] if f"{pas['id']}:{m['xp']}" in c["passe"]]
        try:
            import loja_aparencia as LA
            fx = LA.efeito("efeito_conquista")
        except Exception:
            fx = None
        _visto(prog, set_prog, emb, passe)                       # marca como visto já na abertura: o X do pop-up não deixa o aviso voltar
        titulo = "Nova conquista!" if len(itens) + len(marcos) == 1 else "Novas conquistas!"
        dlg = getattr(st, "dialog", None)
        if dlg is None:
            _conteudo_festa(itens, marcos, fx, prog, set_prog, emb, passe)
            return
        dlg(titulo, width="small")(_conteudo_festa)(itens, marcos, fx, prog, set_prog, emb, passe)
    except Exception:
        pass
