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
import passe as PA
import usuarios

_e = lambda x: html.escape(str(x), quote=True)
BRT = timezone(timedelta(hours=-3))

CSS = """<style>
.pf-hero,.pf-top{max-width:560px;margin:8px auto 12px;border-radius:24px;padding:16px;background:linear-gradient(135deg,#3A2C86,#1B1545);border:1px solid rgba(197,179,255,.45);box-shadow:0 4px 0 rgba(10,8,40,.55)}
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
def html_perfil(nome: str, est: dict, r: dict, unidades: int, col: list[dict], selos_txt: list[str], titulos: list[str]) -> str:
    ok, total = EM.totais(col)
    leg = ("Nível máximo alcançado." if est["maximo"] else f"Faltam {est['falta']} XP para {est['proximo_titulo']}")
    hero = (f"<div class='pf-hero'><div class='pf-id'>{ART.mascote(humor='perfil', tamanho=88)}"
            f"<div class='tx'><div class='pf-nome'>{_e(nome)}</div><span class='pf-tit'>{_e(est['titulo'])}</span>"
            f"<div class='pf-niv'>Nível {est['nivel']} · {est['xp']} XP</div></div></div>"
            f"{_barra(est['pct'])}<div class='pf-leg'>{_e(leg)}</div></div>")
    kpis = (("XP de estudo", r["xp"]), ("Ofensiva atual", f"{r['ofensiva']} d"), ("Melhor ofensiva", f"{r.get('melhor_ofensiva', 0)} d"),
            ("Lições feitas", r["licoes_feitas"]), ("Unidades completas", unidades), ("Emblemas", f"{ok}/{total}"))
    grade = "<div class='pf-grid'>" + "".join(f"<div class='pf-k'><div class='v'>{_e(v)}</div><div class='l'>{_e(l)}</div></div>" for l, v in kpis) + "</div>"
    honras = [f"🏆 {t}" for t in selos_txt] + [f"🎖️ {t}" for t in titulos]
    hon = ("<div class='pf-hon'>" + "".join(f"<span class='pf-chip'>{_e(h)}</span>" for h in honras) + "</div>") if honras else (
        "<div class='pf-vazio'>Ainda sem honrarias. Estude na Jornada e suba no passe da temporada para ganhar as primeiras.</div>")
    emb = [i["emblema"] for c in col for i in c["itens"] if i["ok"]][:12]
    embl = ("<div class='pf-emb'>" + "".join(f"<span>{_e(x)}</span>" for x in emb) + "</div>") if emb else (
        "<div class='pf-vazio'>Seus emblemas aparecem aqui quando você conquistar o primeiro.</div>")
    nota = ("<div class='pf-nota'>O perfil mostra só o que você já fez no app. Emblemas, títulos e selos são honrarias: não pagam XP, "
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
    selos = []
    try:
        import competicao_temporadas as CT
        selos = [t for t in (CT.descricao_selo(s) for s in ((cart or {}).get("selos") or []) if isinstance(s, dict)) if t]
    except Exception:
        selos = []
    u = usuarios.usuario()
    nome = (u or {}).get("nome") or "Jogador"
    pas = PA.estado(_xp_dia(p), _agora().date())
    st.markdown(html_perfil(nome, est, r, unidades, col, selos, pas["titulos"]), unsafe_allow_html=True)
