"""Trade Battle · relatório do fim da partida corrida (só HTML/CSS; sem Streamlit).

Abre num pop-up que cabe na tela do celular SEM ROLAGEM, em três abas, no visual de jogo (referência enviada pelo dono, nov/2026):
  topo        → mascote (touro TH) + faixa "Relatório da partida"
  Resumo      → faixa da revelação (ativo e período, com mini-gráfico e touro ao fundo), 4 destaques com ícone (lucro, retorno,
                pontos, qualidade; a cor segue o sinal), estatísticas com ícone e o XP numa fita
  Operações   → as operações (até OPS_MAX; o resto vira "+N")
  Raio-X      → como o resultado virou pontos (explicação já pronta do motor)
Tudo vem do resultado gravado pelo servidor (fin, relatorio, pontos, qualidade_nota). Nada é recalculado aqui.
No celular os destaques ficam em 2 × 2 e as estatísticas em uma coluna.
"""
from __future__ import annotations

import html

_E = html.escape
OPS_MAX = 7
_MOTIVO = {"stop": "stop", "stop_movel": "stop móvel", "alvo": "alvo", "manual": "você", "fim": "fim", "limite": "limite"}


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


def _ic(nome: str) -> str:
    """Ícone 3D do app (arte_tickerhunters); sem a arte, nada (o texto continua)."""
    try:
        import arte_tickerhunters as AT
        return f"<img class='rr-i' src='{AT.uri(nome)}' alt=''>" if AT.existe(nome) else ""
    except Exception:
        return ""


def html_topo() -> str:
    """Mascote (touro TH) + faixa com o título."""
    try:
        import mascote_novo as MN
        m = MN.uri("principal")
    except Exception:
        m = None
    masc = f"<img class='rr-masc' src='{m}' alt=''>" if m else ""
    return f"<div class='rr-top'>{masc}<div class='rr-fx'>{_ic('grafico_alta')}<b>Relatório da partida</b></div></div>"


_SPARK = ("<svg class='rr-sp' viewBox='0 0 120 50' preserveAspectRatio='none' aria-hidden='true'>"
          "<polyline points='0,44 14,38 26,40 38,30 50,33 62,22 74,26 88,14 100,18 120,4' fill='none' stroke='#3DDC97' stroke-width='2.5'/>"
          + "".join(f"<rect x='{4 + i * 12}' y='{40 - h}' width='5' height='{h}' fill='{c}' opacity='.55'/>"
                    for i, (h, c) in enumerate([(8, '#3DDC97'), (12, '#FF5B6E'), (10, '#3DDC97'), (16, '#3DDC97'), (9, '#FF5B6E'),
                                                (20, '#3DDC97'), (14, '#3DDC97'), (24, '#3DDC97')])) + "</svg>")


def html_resumo(res: dict, revelado: dict | None, xp_txt: str = "") -> str:
    fin, rel = res.get("fin") or {}, res.get("relatorio") or {}
    pnl, ret, pts, ql = fin.get("pnl"), fin.get("pct_aposta"), res.get("pontos"), res.get("qualidade_nota")
    rv = ""
    if revelado:
        sim = " · simulado" if revelado.get("demo") else ""
        rv = (f"<div class='rr-rv'>{_SPARK}{_ic('touro').replace('rr-i', 'rr-tr')}<small>O ativo era</small><b>{_E(revelado['ticker'])}</b>"
              f"<span>📅 {_E(revelado['tf_nome'])} · {_E(revelado['de'])} a {_E(revelado['ate'])}{sim}</span></div>")
    ptxt = "—" if pts is None else ("+" if pts > 0 else "−" if pts < 0 else "") + _br(pts, 1)
    qcor = "" if ql is None else ("up" if ql >= 60 else "down" if ql < 40 else "mid")
    grandes = (f"<div class='rr-g'>"
               f"<div class='c-luc {_cor(pnl)}'>{_ic('grafico_alta')}<small>Lucro</small><b>{_t(pnl)}</b></div>"
               f"<div class='c-ret {_cor(ret)}'>{_ic('dinheiro_alta')}<small>Retorno</small><b>{_p(ret)}</b></div>"
               f"<div class='c-pts {'gold' if pts and pts > 0 else _cor(pts)}'>{_ic('moeda_estrela')}<small>Pontos</small><b>{ptxt}</b></div>"
               f"<div class='c-ql {qcor}'>{_ic('medalha_roxa')}<small>Qualidade</small><b>{'—' if ql is None else f'{ql:.0f}/100'}</b></div></div>")
    n = rel.get("n_ops", 0)
    sem_stop = bool(n) and not rel.get("com_stop")
    stats = [("checklist", "Operações", str(n), ""),
             ("escudo_ok", "Taxa de acerto", "—" if rel.get("taxa_acerto") is None else f"{_br(rel['taxa_acerto'], 0)}%", ""),
             ("moedas_pilha", "Ganho médio", _t(rel.get("ganho_medio")), _cor(rel.get("ganho_medio"))),
             ("urso", "Perda média", _t(rel.get("perda_media")), _cor(rel.get("perda_media"))),
             ("alvo", "Ganho ÷ perda", "—" if rel.get("payoff") is None else _br(rel["payoff"]), ""),
             ("cronometro", "Maior queda", "—" if not n else f"{_t(-rel.get('maior_queda', 0))} ({_br(rel.get('maior_queda_pct', 0))}%)", ""),
             ("escudo_prata", "Com stop", "—" if not n else f"{rel.get('com_stop', 0)} de {n}", "warn" if sem_stop else ""),
             ("ticket", "Taxas pagas", "—" if not n else "T$ " + _br(rel.get("taxas", 0)), "")]
    tab = "".join(f"<div class='{c}'>{_ic(ic)}<span>{_E(k)}</span><b>{_E(v)}</b></div>" for ic, k, v, c in stats)
    aviso = "<div class='rr-av'>⚠ Você operou sem stop: na vida real, uma queda forte levaria muito mais do que o planejado.</div>" if sem_stop else ""
    xp = f"<div class='rr-xp'><span>{xp_txt}</span></div>" if xp_txt else ""
    return f"{rv}{grandes}<div class='rr-s'>{tab}</div>{aviso}{xp}"


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


# O pop-up do Streamlit fica fora de .stApp: os seletores usam `html body` e o `section[role=dialog]` do próprio pop-up.
_D = "html body section[role='dialog']"
CSS = ("<style>"
       # moldura do pop-up e o título padrão escondido (a faixa própria substitui)
       f"{_D}{{background:radial-gradient(120% 80% at 50% 0%,#3B2A9E 0%,#1A1258 45%,#0D0A33 100%) !important;border:2px solid #7A5CFF !important;"
       "border-radius:22px !important;box-shadow:0 0 30px rgba(122,92,255,.55) !important}"
       f"{_D}>h2,{_D} h2:first-child{{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}"
       f"{_D} button[aria-label='Close']{{background:linear-gradient(180deg,#6B4BFF,#3B22B8) !important;border:2px solid #B79CFF !important;"
       "border-radius:12px !important;color:#fff !important;box-shadow:0 0 12px rgba(139,92,255,.6) !important;z-index:5}"
       f"{_D} button[aria-label='Close'] svg{{fill:#fff !important;color:#fff !important}}"
       # topo: mascote + faixa
       "html body .rr-top{position:relative;display:flex;align-items:flex-end;gap:6px;margin:-6px 0 6px;padding-right:40px;min-height:64px}"
       "html body .rr-masc{width:74px;height:auto;flex:none;margin-bottom:-8px;filter:drop-shadow(0 4px 8px rgba(0,0,0,.5))}"
       "html body .rr-fx{flex:1;display:flex;align-items:center;gap:6px;padding:8px 12px;border-radius:14px;transform:skewX(-6deg);"
       "background:linear-gradient(90deg,#7A4DFF,#4B2BC9);border:2px solid #B79CFF;box-shadow:0 0 16px rgba(122,77,255,.6)}"
       "html body .rr-fx b{transform:skewX(6deg);font-size:1.08rem;font-weight:900;font-style:italic;color:#fff;white-space:nowrap;text-shadow:0 2px 0 rgba(0,0,0,.35)}"
       "html body .rr-fx .rr-i{width:26px;height:26px;transform:skewX(6deg)}"
       # abas com ícone (e o bug da aba selecionada branca corrigido)
       f"{_D} [data-testid='stTabs'] [role='tablist']{{gap:6px;border:0 !important}}"
       f"{_D} [data-testid='stTab']{{min-height:32px !important;padding:0 12px !important;border-radius:12px !important;background:#1B1546 !important;"
       "border:1px solid #3A3182 !important;color:#D9D4F7 !important}"
       f"{_D} [data-testid='stTab'][aria-selected='true']{{background:linear-gradient(180deg,#7A5CFF,#4B2BC9) !important;border-color:#B79CFF !important;"
       "color:#fff !important;box-shadow:0 0 12px rgba(122,92,255,.6)}"
       f"{_D} [data-testid='stTab'] p{{color:inherit !important;-webkit-text-fill-color:currentColor !important;font-weight:800 !important;font-size:.82rem !important}}"
       f"{_D} [data-baseweb='tab-highlight'],{_D} [data-baseweb='tab-border']{{display:none !important}}"
       # revelação
       "html body .rr-rv{position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:center;gap:1px;padding:8px 6px;border-radius:14px;"
       "border:2px solid #6FE3FF;background:linear-gradient(120deg,#2B2A9E,#1B1A6E 55%,#2A1C78);box-shadow:0 0 16px rgba(111,227,255,.35);margin-bottom:6px}"
       "html body .rr-rv .rr-sp{position:absolute;left:0;bottom:0;width:30%;height:52%;opacity:.45}"
       "html body .rr-rv .rr-tr{position:absolute;right:4px;bottom:-4px;width:64px;height:64px;opacity:.28}"
       "html body .rr-rv small,html body .rr-rv b,html body .rr-rv span{position:relative}"
       "html body .rr-rv small{font-size:.7rem;font-weight:800;color:#E6E1FF}html body .rr-rv b{font-size:1.5rem;font-weight:900;color:#fff;line-height:1.05;letter-spacing:.5px}"
       "html body .rr-rv span{font-size:.7rem;font-weight:700;color:#D9D4F7}"
       # 4 destaques (cor pelo sinal)
       "html body .rr-g{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-bottom:6px}"
       "html body .rr-g>div{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;column-gap:5px;padding:6px 7px;border-radius:13px;"
       "background:linear-gradient(160deg,#1E1A5A,#151046);border:1.5px solid #3A3182}"
       "html body .rr-g .rr-i{grid-row:1/3;width:26px;height:26px}"
       "html body .rr-g small{font-size:.62rem;font-weight:800;color:#C9C2F2}html body .rr-g b{font-size:.86rem;font-weight:900;color:#fff;white-space:nowrap}"
       "html body .rr-g>div.up{border-color:#2FAF7A;background:linear-gradient(160deg,#123B3A,#151046)}html body .rr-g .up b{color:#3DDC97}"
       "html body .rr-g>div.down{border-color:#B8344A;background:linear-gradient(160deg,#3E1430,#151046)}html body .rr-g .down b{color:#FF5B6E}"
       "html body .rr-g>div.gold{border-color:#C98A1A;background:linear-gradient(160deg,#3A2A10,#151046)}html body .rr-g .gold b{color:#FFC94A}"
       "html body .rr-g>div.mid b{color:#FFE3A3}"
       # estatísticas com ícone
       "html body .rr-s{display:grid;grid-template-columns:1fr 1fr;gap:3px 12px;padding:7px 9px;border-radius:13px;background:#140F3A;border:1.5px solid #2B2470}"
       "html body .rr-s>div{display:grid;grid-template-columns:18px minmax(0,1fr) auto;align-items:center;gap:6px;font-size:.7rem;line-height:1.5}"
       "html body .rr-s .rr-i{width:18px;height:18px}"
       "html body .rr-s span{color:#C9C2F2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}html body .rr-s b{color:#fff;font-weight:800;white-space:nowrap}"
       "html body .rr-s .up b{color:#3DDC97}html body .rr-s .down b{color:#FF5B6E}html body .rr-s .warn b,html body .rr-s .warn span{color:#FFB648}"
       "html body .rr-av{margin-top:5px;padding:4px 8px;border-radius:10px;font-size:.68rem;font-weight:800;color:#FFB648;background:rgba(255,182,72,.1);border:1px solid rgba(255,182,72,.45)}"
       # fita do XP
       "html body .rr-xp{display:flex;justify-content:center;margin-top:7px}"
       "html body .rr-xp span{padding:5px 22px;font-size:.8rem;font-weight:900;color:#FFE3A3;background:linear-gradient(90deg,transparent,#3A2A9E 18%,#3A2A9E 82%,transparent);"
       "border-top:1px solid rgba(183,156,255,.5);border-bottom:1px solid rgba(183,156,255,.5)}"
       "html body .up b,html body b.up{color:#3DDC97 !important}html body .down b,html body b.down{color:#FF5B6E !important}"
       # operações e raio-x
       "html body .rr-op{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:6px;padding:4px 6px;border-radius:9px;"
       "background:#1B1546;border:1px solid #3A3182;margin-bottom:3px}"
       "html body .rr-op i{font-style:normal;font-size:.66rem;font-weight:900;color:#C9C2F2}"
       "html body .rr-op span{display:flex;flex-direction:column;font-size:.74rem;font-weight:800;color:#fff;line-height:1.15;min-width:0}"
       "html body .rr-op small{font-size:.62rem;font-weight:700;color:#C9C2F2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
       "html body .rr-op b{font-size:.76rem;font-weight:900;color:#fff;white-space:nowrap}"
       "html body .rr-mais,html body .rr-vz{font-size:.7rem;font-weight:700;color:#C9C2F2;text-align:center;padding:4px}"
       "html body .rr-rx{display:flex;flex-direction:column;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.06)}"
       "html body .rr-rx b{font-size:.68rem;font-weight:900;color:#FFE3A3}html body .rr-rx span{font-size:.7rem;line-height:1.3;color:#EDE9FF}"
       # celular: destaques 2 × 2 e estatísticas em uma coluna
       "@media (max-width:560px){html body .rr-g{grid-template-columns:1fr 1fr}html body .rr-s{grid-template-columns:1fr;gap:1px}"
       "html body .rr-masc{width:62px}html body .rr-fx b{font-size:.95rem}}"
       "</style>")
