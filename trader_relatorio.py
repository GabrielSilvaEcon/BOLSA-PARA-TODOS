"""Trade Battle · relatório do fim da partida corrida (só HTML/CSS; sem Streamlit).

Abre num pop-up que cabe na tela do celular SEM ROLAGEM, em três abas:
  Resumo      → ativo revelado, lucro, retorno, pontos, nota de qualidade e as estatísticas da partida
  Operações   → as operações (até OPS_MAX; o resto vira "+N")
  Raio-X      → como o resultado virou pontos (explicação já pronta do motor)
Tudo vem do resultado gravado pelo servidor (fin, relatorio, pontos, qualidade_nota). Nada é recalculado aqui.
"""
from __future__ import annotations

import html

_E = html.escape
OPS_MAX = 7
_MOTIVO = {"stop": "stop", "alvo": "alvo", "manual": "você", "fim": "fim", "limite": "limite"}


def _br(v: float, casas: int = 2) -> str:
    return f"{abs(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _t(v) -> str:
    if v is None:
        return "—"
    return ("+" if v > 0.004 else "−" if v < -0.004 else "") + "T$ " + _br(v)


def _p(v, casas: int = 2) -> str:
    if v is None:
        return "—"
    return ("+" if v > 0.0004 else "−" if v < -0.0004 else "") + _br(v, casas) + "%"


def _cor(v) -> str:
    return "" if v is None or abs(v) < 0.004 else ("up" if v > 0 else "down")


def html_resumo(res: dict, revelado: dict | None, xp_txt: str = "") -> str:
    fin, rel = res.get("fin") or {}, res.get("relatorio") or {}
    pnl, ret, pts, ql = fin.get("pnl"), fin.get("pct_aposta"), res.get("pontos"), res.get("qualidade_nota")
    rv = ""
    if revelado:
        sim = " · simulado" if revelado.get("demo") else ""
        rv = (f"<div class='rr-rv'><small>O ativo era</small><b>{_E(revelado['ticker'])}</b>"
              f"<span>{_E(revelado['tf_nome'])} · {_E(revelado['de'])} a {_E(revelado['ate'])}{sim}</span></div>")
    grandes = (f"<div class='rr-g'><div class='{_cor(pnl)}'><small>Lucro</small><b>{_t(pnl)}</b></div>"
               f"<div class='{_cor(ret)}'><small>Retorno</small><b>{_p(ret)}</b></div>"
               f"<div class='{_cor(pts)}'><small>Pontos</small><b>{'—' if pts is None else ('+' if pts > 0 else '−' if pts < 0 else '') + _br(pts, 1)}</b></div>"
               f"<div><small>Qualidade</small><b>{'—' if ql is None else f'{ql:.0f}/100'}</b></div></div>")
    n = rel.get("n_ops", 0)
    stats = [("Operações", str(n)), ("Taxa de acerto", "—" if rel.get("taxa_acerto") is None else f"{_br(rel['taxa_acerto'], 0)}%"),
             ("Ganho médio", _t(rel.get("ganho_medio"))), ("Perda média", _t(rel.get("perda_media"))),
             ("Ganho ÷ perda", "—" if rel.get("payoff") is None else _br(rel["payoff"])),
             ("Maior queda", "—" if not n else f"{_t(-rel.get('maior_queda', 0))} ({_br(rel.get('maior_queda_pct', 0))}%)"),
             ("Com stop", "—" if not n else f"{rel.get('com_stop', 0)} de {n}"), ("Taxas pagas", "—" if not n else "T$ " + _br(rel.get("taxas", 0)))]
    tab = "".join(f"<div><span>{_E(k)}</span><b>{_E(v)}</b></div>" for k, v in stats)
    xp = f"<div class='rr-xp'>{xp_txt}</div>" if xp_txt else ""
    return f"{rv}{grandes}<div class='rr-s'>{tab}</div>{xp}"


def html_operacoes(res: dict) -> str:
    ops = res.get("operacoes") or []
    if not ops:
        return "<div class='rr-vz'>Você não operou nesta partida.</div>"
    lin = []
    for t in ops[:OPS_MAX]:
        lado = "Compra" if t["direcao"] == "alta" else "Venda"
        lin.append(f"<div class='rr-op'><i>{t['n']}</i><span>{lado} {t.get('q', '')}<small>{_br(t['entrada'])} → {_br(t['saida'])} · {_MOTIVO.get(t['motivo'], '')}</small></span>"
                   f"<b class='{_cor(t.get('pnl'))}'>{_t(t.get('pnl'))}</b></div>")
    mais = f"<div class='rr-mais'>+{len(ops) - OPS_MAX} operações (todas estão no Raio-X)</div>" if len(ops) > OPS_MAX else ""
    return "".join(lin) + mais


def html_raiox(linhas: list[tuple[str, str]]) -> str:
    """Raio-X do pop-up: sem as linhas de cada operação (elas estão na aba Operações), para caber sem rolar."""
    linhas = [(k, v) for k, v in linhas if not str(k).startswith("Operação ")]
    return "".join(f"<div class='rr-rx'><b>{_E(k)}</b><span>{_E(v)}</span></div>" for k, v in linhas)


CSS = ("<style>"
       "html body .rr-rv{display:flex;flex-direction:column;align-items:center;gap:1px;padding:6px;border-radius:12px;border:1.5px solid #F2B84B;"
       "background:linear-gradient(160deg,rgba(242,184,75,.16),#150F55);margin-bottom:6px}"
       "html body .rr-rv small{font-size:.66rem;font-weight:800;color:#FFE3A3}html body .rr-rv b{font-size:1.25rem;font-weight:900;color:#fff;line-height:1.1}"
       "html body .rr-rv span{font-size:.68rem;font-weight:700;color:#D9D4F7}"
       "html body .rr-g{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-bottom:6px}"
       "html body .rr-g>div{display:flex;flex-direction:column;align-items:center;padding:5px 2px;border-radius:10px;background:#1B1546;border:1px solid #3A3182}"
       "html body .rr-g small{font-size:.58rem;font-weight:800;color:#C9C2F2}html body .rr-g b{font-size:.78rem;font-weight:900;color:#fff;white-space:nowrap}"
       "html body .up b,html body b.up{color:#3DDC97 !important}html body .down b,html body b.down{color:#FF5B6E !important}"
       "html body .rr-s{display:grid;grid-template-columns:1fr 1fr;gap:3px 8px;padding:6px 8px;border-radius:10px;background:#140F3A;border:1px solid #2B2470}"
       "html body .rr-s>div{display:flex;justify-content:space-between;gap:4px;font-size:.68rem;line-height:1.35}"
       "html body .rr-s span{color:#C9C2F2;white-space:nowrap}html body .rr-s b{color:#fff;font-weight:800;white-space:nowrap}"
       "html body .rr-xp{margin-top:6px;font-size:.72rem;font-weight:800;color:#FFE3A3;text-align:center}"
       "html body .rr-op{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:6px;padding:4px 6px;border-radius:9px;"
       "background:#1B1546;border:1px solid #3A3182;margin-bottom:3px}"
       "html body .rr-op i{font-style:normal;font-size:.66rem;font-weight:900;color:#C9C2F2}"
       "html body .rr-op span{display:flex;flex-direction:column;font-size:.74rem;font-weight:800;color:#fff;line-height:1.15;min-width:0}"
       "html body .rr-op small{font-size:.62rem;font-weight:700;color:#C9C2F2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
       "html body .rr-op b{font-size:.76rem;font-weight:900;color:#fff;white-space:nowrap}"
       "html body .rr-mais,html body .rr-vz{font-size:.7rem;font-weight:700;color:#C9C2F2;text-align:center;padding:4px}"
       "html body .rr-rx{display:flex;flex-direction:column;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.06)}"
       "html body .rr-rx b{font-size:.68rem;font-weight:900;color:#FFE3A3}html body .rr-rx span{font-size:.7rem;line-height:1.3;color:#EDE9FF}"
       "html body [data-testid='stTabs'] button{min-height:30px !important;padding:0 10px !important}"
       "</style>")
