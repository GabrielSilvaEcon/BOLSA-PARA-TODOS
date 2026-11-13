"""Meu Perfil (tela nova, igual à referência). Só apresentação: regras de dados em perfil_dados.py, nível em nivel.py, emblemas em emblemas.py.

Nada aqui grava dados nem paga XP, TickerCoins ou T$. Sem dado real mostra estado vazio (nunca número inventado).
Carteira virtual = T$ (dinheiro fictício). Educacional: sem dinheiro real e sem recomendação de investimento.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

import streamlit as st

import arte_conta as AC
import arte_perfil as AP
import perfil_dados as D

_e = lambda x: html.escape(str(x), quote=True)
BRT = timezone(timedelta(hours=-3))
_P = "html body .stApp.stApp.stApp"

CSS = """<style>
.pt{max-width:560px;margin:0 auto;display:flex;flex-direction:column;gap:12px}
.pt *{box-sizing:border-box}
.pt-c{position:relative;overflow:hidden;border-radius:22px;padding:14px;background:radial-gradient(circle at 100% 0,rgba(139,108,255,.28),transparent 55%),linear-gradient(145deg,#2A2060,#150F3A);border:1px solid rgba(197,179,255,.28);box-shadow:0 4px 0 rgba(0,0,0,.28)}
.pt-c .ilu{position:absolute;right:-6px;bottom:-6px;width:84px;height:84px;object-fit:contain;opacity:.16;pointer-events:none}
.pt-t{display:flex;align-items:center;gap:8px;font-weight:900;font-size:1.02rem;color:#fff !important;-webkit-text-fill-color:#fff !important}
.pt-t img{width:26px;height:26px;object-fit:contain}
.pt-hero{display:flex;gap:14px;align-items:center}
.pt-av{flex:0 0 96px;width:96px;height:96px;border-radius:50%;padding:4px;background:conic-gradient(#7C5CFF,#22d3ee,#3DDC97,#F2B84B,#FF6B8A,#7C5CFF);box-shadow:0 0 18px rgba(124,92,255,.55)}
.pt-av div{width:100%;height:100%;border-radius:50%;background:#1B1545 center/cover no-repeat;border:3px solid #1B1545}
.pt-hero .tx{min-width:0;flex:1}
.pt-nome{font-weight:900;font-size:1.3rem;line-height:1.15;color:#fff !important;-webkit-text-fill-color:#fff !important;overflow-wrap:anywhere}
.pt-niv{display:inline-flex;align-items:center;gap:6px;margin-top:6px;padding:4px 12px;border-radius:999px;font-weight:900;font-size:.85rem;background:linear-gradient(135deg,#5B3FD6,#3A2C86);border:1px solid rgba(255,214,107,.6);color:#fff !important;-webkit-text-fill-color:#fff !important}
.pt-tag{margin-top:6px;font-size:.84rem;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}
.pt-xp{margin-top:10px;display:flex;align-items:center;gap:10px}
.pt-bar{flex:1;height:11px;border-radius:999px;background:rgba(255,255,255,.14);overflow:hidden}
.pt-bar i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#7C5CFF,#a78bfa)}
.pt-xp b{font-size:.78rem;font-weight:800;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;white-space:nowrap}
.pt-pat{display:flex;align-items:center;gap:12px}
.pt-pat img{width:58px;height:58px;object-fit:contain}
.pt-pat .v{font-weight:900;font-size:1.6rem;line-height:1.1;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}
.pt-pat .m{margin-top:2px;font-weight:800;font-size:.84rem}
.pt-pat .m.up{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}
.pt-pat .m.dn{color:#FF6B8A !important;-webkit-text-fill-color:#FF6B8A !important}
.pt-pat .m.nd{color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important;font-weight:600}
.pt-k3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.pt-k{position:relative;overflow:hidden;border-radius:18px;padding:10px 8px 10px;text-align:center;background:radial-gradient(circle at 50% 0,rgba(43,167,255,.2),transparent 65%),linear-gradient(145deg,#2A2060,#150F3A);border:1px solid rgba(197,179,255,.28);box-shadow:0 3px 0 rgba(0,0,0,.28)}
.pt-k img{width:40px;height:40px;object-fit:contain}
.pt-k .l{margin-top:2px;font-size:.7rem;font-weight:700;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}
.pt-k .v{font-weight:900;font-size:1.35rem;line-height:1.15;color:#fff !important;-webkit-text-fill-color:#fff !important}
.pt-k .v small{font-size:.78rem;font-weight:700;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}
.pt-k .d{margin-top:4px;font-size:.66rem;font-weight:700;line-height:1.2;color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}
.pt-k .pb{height:6px;border-radius:999px;background:rgba(255,255,255,.14);overflow:hidden;margin-top:6px}
.pt-k .pb i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#22d3ee,#2BA7FF)}
.pt-don{display:flex;align-items:center;gap:14px;margin-top:10px}
.pt-ring{flex:0 0 104px;width:104px;height:104px;border-radius:50%;display:grid;place-items:center}
.pt-ring div{width:62%;height:62%;border-radius:50%;background:#1B1545;display:grid;place-items:center}
.pt-ring img{width:30px;height:30px;object-fit:contain}
.pt-leg{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}
.pt-leg div{display:flex;align-items:center;gap:8px;font-size:.86rem;font-weight:700;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}
.pt-leg i{width:10px;height:10px;border-radius:50%;flex:none}
.pt-leg b{margin-left:auto;font-weight:900}
.pt-info{margin-top:10px;padding:9px 12px;border-radius:14px;background:rgba(255,255,255,.07);border:1px solid rgba(197,179,255,.25);font-size:.82rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}
.pt-info b{color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}
.pt-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.pt-chips span{padding:3px 10px;border-radius:999px;font-size:.74rem;font-weight:800;background:rgba(139,108,255,.22);border:1px solid rgba(197,179,255,.4);color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}
.pt-vz{margin-top:10px;font-size:.84rem;line-height:1.35;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}
.pt-at{display:flex;gap:12px;align-items:center;padding:9px 0;border-top:1px solid rgba(255,255,255,.1)}
.pt-at:first-of-type{border-top:0;margin-top:6px}
.pt-at .ic{flex:0 0 38px;height:38px;border-radius:50%;display:grid;place-items:center;font-size:1.15rem;background:#3A2C86;border:2px solid #8B6CFF}
.pt-at .ic.c{background:#3A2C10;border-color:#F2B84B}
.pt-at b{display:block;font-size:.88rem;color:#fff !important;-webkit-text-fill-color:#fff !important}
.pt-at span{display:block;font-size:.82rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}
.pt-at small{display:block;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}
.pt-ev{display:flex;align-items:stretch;gap:10px;margin-top:8px}
.pt-ev svg{flex:1;min-width:0;height:auto;max-height:150px}
.pt-ev .g{flex:0 0 112px;align-self:center;text-align:center;padding:10px 6px;border-radius:16px;background:rgba(255,255,255,.07);border:1px solid rgba(197,179,255,.25);font-size:.72rem;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}
.pt-ev .g b{display:block;font-size:1.3rem;font-weight:900}
.pt-ev .g b.up{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}
.pt-ev .g b.dn{color:#FF6B8A !important;-webkit-text-fill-color:#FF6B8A !important}
.pt-em{display:flex;gap:6px;justify-content:space-between;margin-top:10px}
.pt-em div{flex:1;min-width:0;text-align:center;font-size:.68rem;font-weight:700;line-height:1.2;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}
.pt-em .hx{width:56px;height:62px;margin:0 auto 4px;display:grid;place-items:center;font-size:1.6rem;clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);background:linear-gradient(160deg,var(--c),#1B1545 130%)}
.pt-em .lk .hx{background:#2A2358;filter:grayscale(1);opacity:.7}
.pt-nota{font-size:.74rem;line-height:1.35;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important;text-align:center;margin-top:2px}
@media (max-width:380px){.pt-hero{flex-direction:column;text-align:center}.pt-don{flex-direction:column}}
</style>"""
CSS = "".join(l.strip() for l in CSS.splitlines())


def _img(nome: str, alt: str = "") -> str:
    return f"<img src='{AP.uri(nome)}' alt='{_e(alt)}'>"


def _ilu(nome: str) -> str:
    return f"<img class='ilu' src='{AP.uri(nome)}' alt=''>"


def _moeda(v: float) -> str:
    s = f"{v:,.0f}".replace(",", ".")
    return f"T$ {s}"


def _pct(v: float) -> str:
    return f"{v:+.1f}%".replace(".", ",")


def html_hero(nome: str, est: dict) -> str:
    barra = f"{est['pct'] * 100:.0f}"
    xp = "Nível máximo" if est["maximo"] else f"{est['xp_no_nivel']:,} / {est['xp_faixa']:,} XP".replace(",", ".")
    return (f"<div class='pt-c pt-hero'><div class='pt-av'><div style=\"background-image:url('{AC.uri('avatar')}')\"></div></div>"
            f"<div class='tx'><div class='pt-nome'>{_e(nome)}</div><span class='pt-niv'>⭐ Nível {est['nivel']}</span>"
            f"<div class='pt-tag'>{_e(est['titulo'])}</div>"
            f"<div class='pt-xp'><div class='pt-bar'><i style='width:{barra}%'></i></div><b>{_e(xp)}</b></div></div></div>")


def html_patrimonio(valor: float | None, var: float | None) -> str:
    if valor is None:
        corpo = "<div class='v'>—</div><div class='m nd'>Entre na competição para ter uma carteira virtual.</div>"
    else:
        if var is None:
            m = "<div class='m nd'>Variação aparece após alguns pregões.</div>"
        else:
            m = f"<div class='m {'up' if var >= 0 else 'dn'}'>{'↑' if var >= 0 else '↓'} {_pct(var)} este mês</div>"
        corpo = f"<div class='v'>{_moeda(valor)}</div>{m}"
    return (f"<div class='pt-c'><div class='pt-t'>Meu Patrimônio Virtual</div><div class='pt-pat' style='margin-top:8px'>{_img('moedas')}<div>{corpo}</div></div>"
            "<div class='pt-vz' style='margin-top:8px'>Dinheiro fictício (T$): é só simulação.</div></div>")


def html_stats(feitas: int, total: int, n_trades: int, n_conq: int) -> str:
    pct = (feitas / total * 100) if total else 0
    return ("<div class='pt-k3'>"
            f"<div class='pt-k'>{_img('livro')}<div class='l'>Lições</div><div class='v'>{feitas}<small> / {total}</small></div>"
            f"<div class='pb'><i style='width:{pct:.0f}%'></i></div><div class='d' style='color:#CFC8EE !important'>Continue aprendendo!</div></div>"
            f"<div class='pt-k'>{_img('grafico')}<div class='l'>Trades</div><div class='v'>{n_trades}</div><div class='d'>{_e(D.dica_trades(n_trades))}</div></div>"
            f"<div class='pt-k'>{_img('trofeu')}<div class='l'>Conquistas</div><div class='v'>{n_conq}</div>"
            f"<div class='d' style='color:#FFD66B !important'>Veja suas medalhas!</div></div></div>")


def html_investidor(aloc: list[dict], perfil: dict | None, interesses: list[str]) -> str:
    if aloc:
        pcts = D.pcts_inteiros(aloc)
        ini, partes = 0.0, []
        for i in aloc:
            fim = ini + i["pct"]
            partes.append(f"{i['cor']} {ini:.2f}% {fim:.2f}%")
            ini = fim
        leg = "".join(f"<div><i style='background:{i['cor']}'></i>{_e(i['nome'])}<b>{p}%</b></div>" for i, p in zip(aloc, pcts))
        corpo = (f"<div class='pt-don'><div class='pt-ring' style='background:conic-gradient({','.join(partes)})'><div>{_img('grafico')}</div></div>"
                 f"<div class='pt-leg'>{leg}</div></div>")
    else:
        corpo = "<div class='pt-vz'>Sua carteira virtual ainda não tem posições. Faça sua primeira compra para ver a alocação por classe.</div>"
    if perfil:
        chips = "".join(f"<span>{_e(x)}</span>" for x in interesses)
        info = (f"<div class='pt-info'>Perfil escolhido: <b>{_e(perfil['titulo'])}</b>"
                + (f"<div class='pt-chips'>{chips}</div>" if chips else "") + "</div>")
    else:
        info = ""
    return f"<div class='pt-c'>{_ilu('banco')}<div class='pt-t'>{_img('grafico')}Meu Perfil de Investidor</div>{corpo}{info}</div>"


def html_atividades(itens: list[dict]) -> str:
    if not itens:
        corpo = "<div class='pt-vz'>Sem atividades ainda. Suas compras e conquistas aparecem aqui.</div>"
    else:
        linhas = []
        for a in itens:
            conq = a["tipo"] == "conquista"
            linhas.append(f"<div class='pt-at'><div class='ic{' c' if conq else ''}'>{'🏆' if conq else '📊'}</div>"
                          f"<div><b>{_e(a['titulo'])}</b><span>{_e(a['detalhe'])}</span><small>{_e(a['quando_txt'])}</small></div></div>")
        corpo = "".join(linhas)
    return f"<div class='pt-c'>{_ilu('raio')}<div class='pt-t'>{_img('raio')}Últimas Atividades</div>{corpo}</div>"


def svg_evolucao(pontos: list[dict]) -> str:
    """Linha do patrimônio por fechamento (sem bônus). Eixo X com a primeira e a última data."""
    W, H, ml, mb = 300.0, 130.0, 8.0, 22.0
    vs = [p["v"] for p in pontos]
    lo, hi = min(vs), max(vs)
    span = (hi - lo) or 1.0
    n = len(pontos)
    xy = [(ml + (W - 2 * ml) * (i / (n - 1)), 10 + (H - mb - 14) * (1 - (p["v"] - lo) / span)) for i, p in enumerate(pontos)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"{xy[0][0]:.1f},{H - mb:.1f} {linha} {xy[-1][0]:.1f},{H - mb:.1f}"
    dots = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.4' fill='#22d3ee' stroke='#0B3B4A' stroke-width='1.2'/>" for x, y in xy)
    grade = "".join(f"<line x1='{ml}' x2='{W - ml}' y1='{10 + k * (H - mb - 14) / 3:.1f}' y2='{10 + k * (H - mb - 14) / 3:.1f}' stroke='rgba(255,255,255,.08)'/>" for k in range(4))
    d0 = pontos[0]["d"][8:10] + "/" + pontos[0]["d"][5:7]
    return (f"<svg viewBox='0 0 {W:.0f} {H:.0f}' role='img' aria-label='Evolução do patrimônio virtual'>{grade}"
            f"<polygon points='{area}' fill='rgba(34,211,238,.16)'/><polyline points='{linha}' fill='none' stroke='#22d3ee' stroke-width='2.4' stroke-linejoin='round'/>{dots}"
            f"<text x='{ml}' y='{H - 5}' fill='#CFC8EE' font-size='10'>{d0}</text><text x='{W - ml}' y='{H - 5}' fill='#CFC8EE' font-size='10' text-anchor='end'>Hoje</text>"
            "</svg>")


def html_evolucao(pontos: list[dict], var: float | None) -> str:
    if len(pontos) < 2:
        corpo = "<div class='pt-vz'>O gráfico aparece depois de dois pregões com a carteira virtual.</div>"
    else:
        g = ""
        if var is not None:
            g = f"<div class='g'><b class='{'up' if var >= 0 else 'dn'}'>{'▲' if var >= 0 else '▼'} {_pct(var)}</b>no último mês</div>"
        corpo = f"<div class='pt-ev'>{svg_evolucao(pontos)}{g}</div>"
    return f"<div class='pt-c'>{_ilu('grafico')}<div class='pt-t'>{_img('grafico')}Minha Evolução</div>{corpo}</div>"


def html_emblemas(col: list[dict]) -> str:
    itens = [i for c in col for i in c["itens"]]
    ok = [i for i in itens if i["ok"]]
    falta = [i for i in itens if not i["ok"]]
    mostrar = (ok[:4] + falta)[:4]
    if not mostrar:
        corpo = "<div class='pt-vz'>Seus emblemas aparecem aqui.</div>"
    else:
        cel = "".join(f"<div class='{'' if i['ok'] else 'lk'}'><span class='hx' style='--c:{_e(i['cor'])}'>{'' if not i['ok'] else _e(i['emblema'])}"
                      f"{'🔒' if not i['ok'] else ''}</span>{_e(i['nome'])}</div>" for i in mostrar)
        corpo = f"<div class='pt-em'>{cel}</div>"
    return f"<div class='pt-c'>{_ilu('medalha')}<div class='pt-t'>{_img('medalha')}Meus Emblemas</div>{corpo}</div>"


def _agora() -> datetime:
    return datetime.now(BRT)


def _dados_onb() -> tuple[str, dict | None, list[str]]:
    """(apelido, perfil escolhido, rótulos dos interesses) do onboarding concluído; vazio se não concluiu."""
    try:
        import onboarding as O
        o = O.normalizar(st.session_state.get("onb"))
        p = O.perfil_do_usuario(o)
        perfil = next((x for x in O.PERFIS if x["id"] == o.get("perfil")), None) if p else None
        nomes = {i["id"]: i["titulo"] for i in O.INTERESSES}
        return o.get("nick") or "", perfil, [nomes[i] for i in (o.get("interesses") or []) if i in nomes]
    except Exception:
        return "", None, []


def tela(prog) -> None:
    """Meu Perfil completo. `prog` = função que devolve o progresso de estudo (a mesma da Jornada)."""
    import emblemas as EM
    import emblemas_app as EMA
    import jornada as JO
    import nivel as NV
    import perfil_app as PF
    import usuarios
    st.markdown(CSS, unsafe_allow_html=True)
    p = prog()
    r = JO.resumo(p)
    est = NV.estado(r["xp"])
    total = sum(len(u["licoes"]) for u in JO.mapa(p))
    res, cart = PF._wallet()
    conqs = (res or {}).get("conquistas") or []
    col = EM.colecao(EMA.contexto_da_tela(res, cart))
    nick, perfil, interesses = _dados_onb()
    nome = nick or usuarios.primeiro_nome() or "Jogador"
    agora = _agora()
    aloc, valor, var, pontos = [], None, None, []
    if cart:
        import competicao as C
        try:
            import ativos_jogo as A
            aloc = D.alocacao(cart, A.classe)
        except Exception:
            aloc = []
        valor = C.patrimonio(cart) - C.aportes(cart)
        var = D.variacao(cart, agora.date())
        pontos = D.evolucao(cart)
    n_conq = sum(1 for c in conqs if c.get("desbloqueada_em"))
    corpo = (html_hero(nome, est) + html_patrimonio(valor, var) + html_stats(r["licoes_feitas"], total, D.trades(cart), n_conq)
             + html_investidor(aloc, perfil, interesses) + html_atividades(D.atividades(cart, conqs, agora))
             + html_evolucao(pontos, var) + html_emblemas(col)
             + "<div class='pt-nota'>Só mostra o que você já fez no app. Carteira virtual em T$ (fictício): simulação educacional, sem recomendação de investimento.</div>")
    st.markdown(CSS + f"<div class='pt'>{corpo}</div>", unsafe_allow_html=True)
    if cart:
        st.button("Ir para a carteira virtual", key="pt_ir_cart", icon=":material/account_balance_wallet:", width="stretch",
                  on_click=lambda: st.session_state.__setitem__("_nav_pend", "competicao"))
    with st.expander("Ver todos os emblemas"):
        for c in col:
            st.markdown(f"**{c['categoria']}** · {c['ok']}/{c['total']}")
            st.markdown(" ".join(f"{i['emblema'] if i['ok'] else '🔒'} {i['nome']}" for i in c["itens"]))
