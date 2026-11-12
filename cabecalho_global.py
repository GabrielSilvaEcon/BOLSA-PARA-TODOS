"""Cabeçalho global do TickerHunters (única fonte de estilo).

Linha 1 (container `topo_perfil`, criado em app._topo_acoes): logo + nome à esquerda; busca, sino e perfil à direita. Fica sobre o cabeçalho
nativo do Streamlit (o menu ⋮ dele continua livre à direita).
Linha 2 (container `hud_topo`, criado em app.py): faixa de indicadores (sequência, XP, Ticker Coins, patrimônio T$), fixa logo abaixo da linha 1.
Todo o CSS da faixa e do sino mora aqui; o design/css.py cuida só da posição base da linha 1.
"""
from __future__ import annotations

NBSP = " "
Q = "html body .stApp.stApp.stApp"
LARGURA = 1100            # largura útil no computador: a faixa e a linha 1 se alinham com o conteúdo
ALTURA_FAIXA = 57         # px: 6 + 44 + 6 + borda
ALTURA_FAIXA_ESTREITA = 49

_MAT = {"dias": "#FF9B3D", "xp": "#F2B84B", "tc": "#F2B84B", "ts": "#3DDC97"}


def peso(valor: str, rotulo: str) -> int:
    """Largura relativa do indicador: o texto mais longo (valor ou rótulo) manda; assim nada é cortado."""
    return max(len(valor), round(len(rotulo) * 0.78)) + 4


def css(itens: list[tuple[str, str, str]], n_alertas: int = 0, imagens: dict | None = None, xp_pct: float | None = None) -> str:
    """`itens`: [(id, valor, rótulo)] na ordem da faixa. `imagens`: {id: data-uri} para trocar o ícone por arte própria (moedas)."""
    n = max(len(itens), 1)
    cols = " ".join(f"minmax(0,{peso(v, r)}fr)" for _i, v, r in itens) or "minmax(0,1fr)"
    cols_e = " ".join(f"minmax(0,{len(v) + 5}fr)" for _i, v, _r in itens) or "minmax(0,1fr)"
    rot = "".join(f'{Q} .st-key-hud_i_{i}{{--lb:"{r}"}}' for i, _v, r in itens)
    cor = "".join(f'{Q} .st-key-hud_i_{i} [data-testid="stIconMaterial"]{{color:{c} !important}}' for i, c in _MAT.items())
    img = "".join(f'{Q} .st-key-hud_i_{i} [data-testid="stIconMaterial"]{{font-size:0 !important;color:transparent !important;width:24px;height:24px;'
                  f'background:url("{u}") center/contain no-repeat;display:inline-block;flex:none}}' for i, u in (imagens or {}).items() if u)
    sino = (f'{Q} .st-key-topo_perfil [data-testid="stPageLink"] a::after{{content:"{n_alertas if n_alertas < 100 else "99+"}";position:absolute;top:3px;right:2px;'
            "min-width:18px;height:18px;padding:0 4px;box-sizing:border-box;border-radius:9px;background:#FF3B30;color:#fff;font-size:.62rem;font-weight:800;"
            "display:grid;place-items:center;line-height:1}") if n_alertas > 0 else ""
    barra = ""
    if xp_pct is not None:                                   # progresso até o próximo nível: linha fina no pé da faixa
        p = max(0.0, min(1.0, float(xp_pct))) * 100
        barra = (f"{Q} .st-key-hud_topo:after{{content:'';position:absolute;left:0;bottom:0;height:3px;width:{p:.0f}%;"
                 "background:linear-gradient(90deg,#3DDC97,#2BA7C9);border-radius:0 3px 3px 0;transition:width .6s ease}")
    return "<style>" + barra + (
        # ---- linha 1: sino (mesmo tamanho dos outros ícones) e alinhamento com o conteúdo
        f'{Q} .st-key-topo_perfil [data-testid="stPageLink"]{{width:auto !important}}'
        f'{Q} .st-key-topo_perfil [data-testid="stPageLink"] a[data-testid="stPageLink-NavLink"]{{position:relative;overflow:visible;width:44px !important;min-width:44px !important;'
        "height:44px !important;min-height:44px !important;padding:0 !important;justify-content:center !important;background:transparent !important;border:0 !important;box-shadow:none !important}"
        f'{Q} .st-key-topo_perfil a [data-testid="stIconMaterial"]{{font-size:26px !important;color:var(--dz-texto) !important}}'
        + sino +
        f"@media (min-width:{LARGURA}px){{{Q} .st-key-topo_perfil{{padding-left:max(10px,calc((100vw - {LARGURA}px)/2)) !important;"
        f"right:max(44px,calc((100vw - {LARGURA}px)/2 + 44px)) !important}}}}"
        # ---- linha 2: faixa fixa de indicadores
        f"{Q} .st-key-hud_topo{{position:fixed !important;top:var(--dz-cab-h,48px);left:0;right:0;width:auto !important;z-index:999;box-sizing:border-box;"
        f"padding:6px max(8px,calc((100vw - {LARGURA}px)/2)) 6px !important;background:var(--dz-concha,#0F0B2B);border-bottom:1px solid var(--dz-concha-borda,rgba(189,181,230,.16));"
        "box-shadow:0 6px 16px -10px rgba(0,0,0,.6)}"
        f'{Q} .st-key-hud_topo [data-testid="stHorizontalBlock"]{{display:grid !important;grid-template-columns:{cols} !important;gap:6px !important;'
        "flex-wrap:nowrap !important;max-width:720px;margin:0 auto}"
        f'{Q} .st-key-hud_topo [data-testid="stColumn"]{{width:auto !important;min-width:0 !important;flex:none !important}}'
        f'{Q} .st-key-hud_topo [data-testid="stVerticalBlock"],{Q} .st-key-hud_topo [data-testid="stPageLink"]{{width:100% !important;gap:0 !important}}'
        f'{Q} .st-key-hud_topo a{{width:100% !important;box-sizing:border-box;display:flex !important;align-items:center !important;justify-content:flex-start !important;gap:6px !important;'
        "min-height:44px !important;padding:4px 8px !important;border-radius:14px !important;overflow:hidden;text-decoration:none !important;"
        "background:var(--dz-cartao,#1B1442) !important;border:1px solid var(--dz-borda,rgba(189,181,230,.22)) !important;box-shadow:0 2px 0 rgba(0,0,0,.35)}"
        f'{Q} .st-key-hud_topo a [data-testid="stIconMaterial"]{{flex:0 0 22px;font-size:22px !important;width:22px;height:22px}}'
        f'{Q} .st-key-hud_topo a [data-testid="stMarkdownContainer"]{{min-width:0;flex:1 1 auto;margin:0 !important}}'
        f'{Q} .st-key-hud_topo a :is(p,span):not([data-testid="stIconMaterial"]){{margin:0 !important;font-weight:800 !important;line-height:1.1 !important;'
        "font-size:clamp(.74rem,3.4vw,.92rem) !important;white-space:nowrap !important;text-wrap:nowrap !important;overflow-wrap:normal !important;word-break:keep-all !important;"
        "color:var(--dz-texto,#fff) !important;-webkit-text-fill-color:var(--dz-texto,#fff) !important}"
        f'{Q} .st-key-hud_topo a p::after{{content:var(--lb);display:block;margin-top:2px;font-size:.6rem;font-weight:600;letter-spacing:0;'
        "color:var(--dz-apoio,#BDB5E6);-webkit-text-fill-color:var(--dz-apoio,#BDB5E6)}"
        + cor + img + rot +
        f"{Q} .st-key-hud_i_ts a{{border-color:rgba(61,220,151,.5) !important;background:rgba(61,220,151,.1) !important}}"
        # celular estreito: só ícone e valor (o rótulo some para nada ser cortado)
        f"@media (max-width:400px){{{Q} .st-key-hud_topo [data-testid=\"stHorizontalBlock\"]{{grid-template-columns:{cols_e} !important;gap:4px !important}}"
        f"{Q} .st-key-hud_topo a p::after{{display:none}}{Q} .st-key-hud_topo a{{min-height:36px !important;padding:2px 5px !important;gap:4px !important}}"
        f"{Q} .st-key-hud_topo a [data-testid=\"stIconMaterial\"]{{flex:0 0 20px;font-size:20px !important;width:20px;height:20px}}"
        f"{Q} .st-key-hud_i_tc [data-testid=\"stIconMaterial\"],{Q} .st-key-hud_i_ts [data-testid=\"stIconMaterial\"]{{width:20px !important;height:20px !important}}"
        f"{Q} .st-key-hud_topo a :is(p,span):not([data-testid=\"stIconMaterial\"]){{font-size:clamp(.66rem,3vw,.8rem) !important}}"
        f"{Q} .st-key-hud_topo{{padding-top:5px !important;padding-bottom:5px !important}}"
        f"{Q} [data-testid=\"stMain\"] .block-container{{padding-top:calc(var(--dz-cab-h,48px) + {ALTURA_FAIXA_ESTREITA}px + 12px) !important}}}}"
        # blocos que só carregam <style> não ocupam espaço (cada um somava um vão de ~16 px no topo das páginas)
        f'{Q} [data-testid="stMain"] [data-testid="stElementContainer"]:has(>[data-testid="stMarkdown"] style):not(:has(>[data-testid="stMarkdown"] :is(p,div,h1,h2,h3,h4,ul,ol,table,img,svg,a,span))){{display:none !important}}'
        # espaço para o conteúdo não ficar sob a faixa
        f"@media (min-width:401px){{{Q} [data-testid=\"stMain\"] .block-container{{padding-top:calc(var(--dz-cab-h,48px) + {ALTURA_FAIXA}px + 14px) !important}}}}"
    ) + "</style>"
