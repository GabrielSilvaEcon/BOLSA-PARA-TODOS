"""Gera o CSS do design system v2 a partir dos tokens e do tema da página aberta.

Escopo da Etapa 2: variáveis (--dz-*), barra inferior, cabeçalho compacto e componentes compartilhados (dz-*).
Não troca o fundo nem as cores das páginas (isso é das Etapas 3 a 5) e não mexe em nenhuma regra de negócio.
Convenção: seletores do app começam por `.stApp` (vencem o CSS antigo sem acumular `!important` em cadeia).
"""
from __future__ import annotations

from . import tokens as K
from . import temas as T


def variaveis(tema_id: str) -> str:
    t = T.TEMAS.get(tema_id) or T.TEMAS["analise"]
    c = T.CONCHA
    v = {
        "--dz-fonte": K.FONTE_PILHA, "--dz-toque": f"{K.TOQUE_MIN}px", "--dz-barra-h": f"{K.BARRA_ALTURA}px",
        "--dz-cab-h": f"{K.CABECALHO_ALTURA}px", "--dz-ms": f"{K.MOVIMENTO_MS}ms",
        "--dz-r-campo": f"{K.RAIO['campo']}px", "--dz-r-cartao": f"{K.RAIO['cartao']}px", "--dz-r-painel": f"{K.RAIO['painel']}px",
        "--dz-fundo": t["fundo"], "--dz-cartao": t["cartao"], "--dz-elevado": t["elevado"], "--dz-borda": t["borda"],
        "--dz-texto": t["texto"], "--dz-apoio": t["apoio"], "--dz-destaque": t["destaque"], "--dz-sobre": t["sobre_destaque"],
        "--dz-pos": t["positivo"], "--dz-neg": t["negativo"],
        "--dz-concha": c["fundo"], "--dz-concha-borda": c["borda"], "--dz-inativo": c["inativo"], "--dz-ativo-txt": c["texto_ativo"],
        "--dz-ativo": T.DESTAQUE_NA_CONCHA.get(tema_id, T.DESTAQUE_NA_CONCHA["analise"]),
    }
    return ":root{" + ";".join(f"{k}:{x}" for k, x in v.items()) + "}"


def barra_inferior(n_itens: int) -> str:
    """Barra de navegação principal: igual nos três ambientes, estilo Android (ícone sobre o rótulo, item ativo com pílula suave)."""
    b = "html body .stApp .st-key-barra_areas"      # prefixo extra: o tema.py antigo estiliza estes botões com seletores fortes
    base = (
        f"{b} [data-testid=\"stHorizontalBlock\"]{{display:grid !important;grid-template-columns:repeat({n_itens},minmax(0,1fr)) !important;gap:2px !important;width:100% !important}}"
        f"{b} [data-testid=\"stColumn\"]{{width:auto !important;min-width:0 !important;flex:none !important}}"
        f"{b} .stButton > button{{display:flex !important;flex-direction:column !important;align-items:center;justify-content:center;gap:2px !important;"
        "min-height:var(--dz-toque) !important;width:100%;padding:6px 2px !important;border-radius:var(--dz-r-painel) !important;outline:0 !important;"
        "box-shadow:none !important;backdrop-filter:none !important;transform:none !important;background:transparent !important;border:0 !important;"
        "transition:background var(--dz-ms) ease,color var(--dz-ms) ease}"
        f"{b} .stButton > button:is(:hover,:focus,:focus-visible){{border:0 !important;box-shadow:none !important;outline:0 !important}}"
        f"{b} .stButton > button > div{{display:flex !important;flex-direction:column;align-items:center;gap:2px;margin:0}}"
        f"{b} .stButton > button p{{display:flex !important;flex-direction:column;align-items:center;gap:2px;margin:0;line-height:1.1;"
        "font-family:var(--dz-fonte);font-size:.72rem !important;font-weight:600 !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}"
        f"{b} .stButton > button [data-testid=\"stIconMaterial\"]{{font-size:1.5rem !important;margin:0 !important}}"
        f"{b} .stButton > button :is(p,span,[data-testid=\"stIconMaterial\"]){{color:var(--dz-inativo) !important}}"
        f"{b} .stButton > button:active{{background:rgba(255,255,255,.08) !important}}"
        f"{b} .stButton > button[data-testid^=\"stBaseButton-primary\"]{{background:color-mix(in srgb,var(--dz-ativo) 20%,transparent) !important}}"
        f"{b} .stButton > button[data-testid^=\"stBaseButton-primary\"] :is(p,span,[data-testid=\"stIconMaterial\"]){{color:var(--dz-ativo) !important}}"
    )
    fixa = (
        f"@media (max-width:{K.TABLET_MAX}px){{{b}{{position:fixed;left:0;right:0;bottom:0;width:100% !important;z-index:990;box-sizing:border-box;"
        "padding:4px 8px calc(4px + env(safe-area-inset-bottom,0px));background:var(--dz-concha);border-top:1px solid var(--dz-concha-borda);"
        "border-radius:0;box-shadow:0 -8px 24px -12px rgba(0,0,0,.6)}"
        f"{b} [data-testid=\"stHorizontalBlock\"]{{max-width:520px;margin:0 auto}}"
        f".stApp .block-container{{padding-bottom:calc(var(--dz-barra-h) + env(safe-area-inset-bottom,0px) + 24px) !important}}}}"
    )
    topo = (  # computador: a barra continua no topo da página, compacta e com o mesmo comportamento
        f"@media (min-width:{K.TABLET_MAX + 1}px){{{b}{{background:var(--dz-concha);border:1px solid var(--dz-concha-borda);"
        "border-radius:var(--dz-r-painel);padding:4px;margin-bottom:12px}"
        f"{b} .stButton > button p{{flex-direction:row;font-size:.85rem !important}}}}"
    )
    return base + fixa + topo


def sensacao_de_app(n_itens: int) -> str:
    """Jeito de aplicativo (inspirado em jogos): barra inferior só com ícones e item ativo expandido, botões com relevo, seções em
    fichas que rolam de lado, sem âncoras de título nem rolagem de página inteira escondendo o que importa."""
    b = "html body .stApp.stApp .st-key-barra_areas"
    q = "html body .stApp.stApp"
    ativo = "[data-testid^=\"stBaseButton-primary\"]"
    barra = (
        f"@media (max-width:{K.TABLET_MAX}px){{"
        f"{b} [data-testid=\"stHorizontalBlock\"]{{display:flex !important;gap:4px !important;align-items:stretch !important}}"
        f"{b} [data-testid=\"stColumn\"]{{flex:1 1 0 !important;width:auto !important;transition:flex .2s ease}}"
        f"{b} [data-testid=\"stColumn\"]:has(button{ativo}){{flex:2.3 1 0 !important}}"
        f"{b} .stButton > button:not({ativo}) p{{font-size:0 !important;gap:0 !important}}"
        f"{b} .stButton > button:not({ativo}) [data-testid=\"stIconMaterial\"]{{font-size:1.75rem !important}}"
        f"{b} .stButton > button{ativo}{{min-height:58px !important;background:color-mix(in srgb,var(--dz-ativo) 22%,var(--dz-concha)) !important;"
        "box-shadow:inset 0 3px 0 var(--dz-ativo) !important;border-radius:14px !important}"
        f"{b} .stButton > button{ativo} p{{font-size:.8rem !important;font-weight:800 !important}}"
        "}"
    )
    relevo = (
        f"{q} [data-testid=\"stMain\"] .stButton:not(.st-key-barra_areas *) > button[data-testid^=\"stBaseButton-secondary\"]"
        "{border-radius:16px !important;border:2px solid var(--dz-borda) !important;box-shadow:0 4px 0 rgba(0,0,0,.38) !important;font-weight:700;"
        "transition:transform .08s ease,box-shadow .08s ease}"
        f"{q} [data-testid=\"stMain\"] .stButton:not(.st-key-barra_areas *) > button[data-testid^=\"stBaseButton-primary\"]"
        "{border-radius:16px !important;box-shadow:0 4px 0 color-mix(in srgb,var(--dz-destaque) 50%,#000) !important;font-weight:800;"
        "transition:transform .08s ease,box-shadow .08s ease}"
        f"{q} [data-testid=\"stMain\"] .stButton:not(.st-key-barra_areas *) > button:active"
        "{transform:translateY(3px);box-shadow:0 1px 0 rgba(0,0,0,.38) !important}"
    )
    fichas = (
        f"{q} [class*=\"st-key-abasel_\"] [data-testid=\"stButtonGroup\"]{{flex-wrap:nowrap !important;overflow-x:auto;gap:8px !important;padding:2px 2px 8px;"
        "scrollbar-width:none;-webkit-overflow-scrolling:touch;scroll-snap-type:x proximity}"
        f"{q} [class*=\"st-key-abasel_\"] [data-testid=\"stButtonGroup\"]::-webkit-scrollbar{{display:none}}"
        f"{q} [class*=\"st-key-abasel_\"] :is([data-testid^=\"stButtonGroup\"],[role=\"group\"],[data-testid^=\"stButtonGroup\"]>div)"
        "{flex-wrap:nowrap !important;overflow-x:auto;scrollbar-width:none;max-width:100%}"
        f"{q} [class*=\"st-key-abasel_\"] :is([role=\"group\"],[data-testid^=\"stButtonGroup\"]>div)::-webkit-scrollbar{{display:none}}"
        f"{q} [class*=\"st-key-abasel_\"] button{{flex:none !important;white-space:nowrap;min-height:42px;padding:0 16px !important;border-radius:999px !important;"
        "border:2px solid var(--dz-borda) !important;background:var(--dz-cartao) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important;scroll-snap-align:start}"
        f"{q} [class*=\"st-key-abasel_\"] button :is(p,span){{color:var(--dz-texto) !important;font-weight:700 !important}}"
        f"{q} [class*=\"st-key-abasel_\"] button[data-testid=\"stBaseButton-pillsActive\"]{{background:var(--dz-destaque) !important;"
        "border-color:var(--dz-destaque) !important;box-shadow:0 3px 0 color-mix(in srgb,var(--dz-destaque) 50%,#000) !important}"
        f"{q} [class*=\"st-key-abasel_\"] button[data-testid=\"stBaseButton-pillsActive\"] :is(p,span){{color:var(--dz-sobre) !important}}"
    )
    limpeza = f"{q} [data-testid=\"stHeaderActionElements\"]{{display:none !important}}"
    ajuda = (
        f"{q} .st-key-aj_btn_box{{display:flex !important;justify-content:flex-end;height:auto !important;margin:0 0 -6px !important}}"
        f"{q} .st-key-aj_btn_box button{{min-height:36px !important;width:36px !important;padding:0 !important;border-radius:50% !important;"
        "border:1px solid var(--dz-borda) !important;background:var(--dz-cartao) !important;box-shadow:0 2px 0 rgba(0,0,0,.35) !important;opacity:1 !important}"
        f"{q} .st-key-aj_btn_box button :is(span,svg,[data-testid=\"stIconMaterial\"]){{color:var(--dz-destaque) !important}}"
    )
    h = f"{q} .st-key-hud_topo"
    hud = (
        f"@media (max-width:{K.TABLET_MAX}px){{{h}{{position:fixed;top:var(--dz-cab-h,48px);left:0;right:0;z-index:999;box-sizing:border-box;padding:5px 10px;"
        "background:var(--dz-concha);border-bottom:1px solid var(--dz-concha-borda);box-shadow:0 6px 16px -10px rgba(0,0,0,.6)}"
        f"{h} [data-testid=\"stHorizontalBlock\"]{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px !important;max-width:520px;margin:0 auto}}"
        f"{h} [data-testid=\"stColumn\"]{{width:auto !important;min-width:0 !important;flex:none !important}}"
        f"{h} [data-testid=\"stPageLink\"]{{width:100% !important}}"
        f"{h} a{{width:100% !important;display:flex !important;align-items:center;justify-content:center;gap:6px;min-height:34px !important;padding:0 10px !important;border-radius:999px !important;"
        "background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;text-decoration:none !important;box-shadow:0 2px 0 rgba(0,0,0,.35)}"
        f"{h} a :is(p,span){{color:var(--dz-texto) !important;font-weight:800 !important;font-size:.9rem !important;white-space:nowrap}}"
        f"{h} [data-testid=\"stColumn\"]:nth-child(1) [data-testid=\"stIconMaterial\"]{{color:#FF9B3D !important}}"
        f"{h} [data-testid=\"stColumn\"]:nth-child(2) [data-testid=\"stIconMaterial\"]{{color:var(--dz-ativo) !important}}"
        f"{h} [data-testid=\"stColumn\"]:nth-child(3) [data-testid=\"stIconMaterial\"]{{color:#F2B84B !important}}"
        f"{q} .block-container{{padding-top:calc(var(--dz-cab-h,48px) + 26px) !important}}}}"
        f"@media (min-width:{K.TABLET_MAX + 1}px){{{h}{{display:none !important}}}}"
    )
    return barra + relevo + fichas + limpeza + ajuda + hud


def acordeao() -> str:
    """Barras que abrem e fecham (cada análise com o resultado na barra)."""
    q = "html body .stApp.stApp"
    b = f"{q} [class*=\"st-key-acdbar_\"]"
    return (
        f"{b}{{margin:0 0 8px}}"
        f"{b} button{{width:100% !important;justify-content:flex-start !important;text-align:left !important;min-height:56px;border-radius:16px !important;"
        "padding:10px 14px !important;background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important}"
        f"{b} button :is(p,span){{text-align:left !important;white-space:normal !important;color:var(--dz-texto) !important;font-weight:700 !important}}"
        f"{b} button[data-testid^=\"stBaseButton-primary\"]{{border-color:var(--dz-destaque) !important;background:color-mix(in srgb,var(--dz-destaque) 14%,var(--dz-cartao)) !important}}"
        f"{b} button [data-testid=\"stIconMaterial\"]{{color:var(--dz-destaque) !important;margin-left:auto;order:2}}"
        f"{q} [class*=\"st-key-acdon_\"]{{margin:0 0 10px}}"
    )


def controles_mobile() -> str:
    """Etapa 3: radios horizontais e controles segmentados viram fichas que quebram linha; gráficos sem sobra lateral."""
    q = "html body .stApp.stApp"
    return (
        f"@media (max-width:900px){{"
        f"{q} [class*=\"st-key-leit_item_\"]>[data-testid=\"stVerticalBlock\"]{{gap:12px !important}}"
        f"{q} .st-key-aj_btn_box{{position:relative;height:0 !important;margin:-10px 0 0 !important;overflow:visible;z-index:5}}"
        f"{q} .st-key-aj_btn_box button{{position:absolute !important;right:58px;top:-58px;margin:0 !important}}"
        f"{q} .leit-tit{{display:block;line-height:1.3 !important;margin:0 0 2px !important}}"
        f"{q} [class*=\"st-key-leit_res_\"]{{position:relative;margin-top:4px !important}}"
        f"{q} [data-testid=\"stSegmentedControl\"]{{margin-top:10px}}"
        f"{q} [data-testid=\"stRadio\"] [role=\"radiogroup\"]{{flex-wrap:wrap !important;gap:8px !important}}"
        f"{q} [data-testid=\"stMain\"] :is(h4,h5,h6){{font-size:1.05rem !important;line-height:1.25 !important;font-weight:800 !important;color:#E4DFFF !important;margin:.9rem 0 .35rem !important}}"
        f"{q} [data-testid=\"stRadio\"] [role=\"radiogroup\"] label{{border:1px solid var(--dz-borda);background:var(--dz-cartao);border-radius:999px;padding:6px 12px !important;margin:0 !important}}"
        f"{q} [data-testid=\"stRadio\"] [role=\"radiogroup\"] label:has(input:checked){{border-color:var(--dz-destaque);box-shadow:0 0 0 1px var(--dz-destaque) inset}}"
        f"{q} [data-testid=\"stSegmentedControl\"] [role=\"group\"],{q} [data-testid=\"stSegmentedControl\"] > div{{width:100% !important}}"
        f"{q} [data-testid=\"stMain\"] [data-testid=\"stHorizontalBlock\"]:has(>[data-testid=\"stColumn\"]:nth-child(3)):not(:has([data-testid=\"stPlotlyChart\"],[data-testid=\"stDataFrame\"],[data-testid=\"stHorizontalBlock\"])):not(.st-key-barra_areas *):not(.st-key-hud_topo *):not(.st-key-topo_perfil *):not(:has([class*=\"st-key-pop_\"],[class*=\"st-key-ex_\"],[class*=\"st-key-barra_areas\"]))"
        f"{{flex-wrap:wrap !important;row-gap:10px !important;column-gap:10px !important}}"
        f"{q} [data-testid=\"stMain\"] [data-testid=\"stHorizontalBlock\"]:has(>[data-testid=\"stColumn\"]:nth-child(3)):not(:has([data-testid=\"stPlotlyChart\"],[data-testid=\"stDataFrame\"],[data-testid=\"stHorizontalBlock\"])):not(.st-key-barra_areas *):not(.st-key-hud_topo *):not(.st-key-topo_perfil *):not(:has([class*=\"st-key-pop_\"],[class*=\"st-key-ex_\"],[class*=\"st-key-barra_areas\"]))"
        f">[data-testid=\"stColumn\"]{{flex:1 1 calc(50% - 5px) !important;min-width:calc(50% - 5px) !important;width:auto !important}}"
        f"{q} [data-testid=\"stMain\"] [data-testid=\"stMarkdownContainer\"]>ul{{list-style:none !important;padding:0 !important;margin:8px 0 !important}}"
        f"{q} [data-testid=\"stMain\"] [data-testid=\"stMarkdownContainer\"]>ul>li{{background:var(--dz-cartao);border:1px solid var(--dz-borda);"
        f"border-left:3px solid var(--dz-destaque);border-radius:12px;padding:10px 12px !important;margin:6px 0 !important;line-height:1.45}}"
        f"{q} [data-testid=\"stMetric\"] :is([data-testid=\"stMetricValue\"],[data-testid=\"stMetricLabel\"]) *{{white-space:normal !important;overflow:visible !important;text-overflow:clip !important}}"
        f"{q} [data-testid=\"stMetricValue\"]{{font-size:1.35rem !important;line-height:1.2}}"
        f"{q} [data-testid=\"stPlotlyChart\"]{{margin-left:-6px;margin-right:-6px;touch-action:pan-y}}"
        f"}}"
    )


def hubs_compactos() -> str:
    """Celular: telas de entrada (Analisar) mais baixas; as páginas de cada cartão ficam em 2 colunas."""
    q = "html body .stApp.stApp"
    return (
        f"@media (max-width:{K.CELULAR_MAX}px){{"
        f"{q} .an-hero{{padding:12px !important;margin-bottom:10px !important}}"
        f"{q} .an-hero h1{{font-size:1.3rem !important}}"
        f"{q} .an-hero p{{font-size:.85rem !important;margin:4px 0 6px !important}}"
        f"{q} .an-sec{{margin:8px 0 4px !important}}"
        f"{q} [class*=\"st-key-an_card_\"]>[data-testid=\"stVerticalBlock\"]{{display:grid !important;grid-template-columns:1fr 1fr;gap:6px !important}}"
        f"{q} [class*=\"st-key-an_card_\"]>[data-testid=\"stVerticalBlock\"]>:first-child{{grid-column:1/-1}}"
        f"{q} .st-key-an_func a{{min-height:44px}}"
        f"{q} [data-testid=\"stHorizontalBlock\"]:has([class*=\"st-key-pop_\"]),{q} [data-testid=\"stHorizontalBlock\"]:has([class*=\"st-key-ex_\"])"
        "{display:grid !important;grid-template-columns:1fr 1fr;gap:8px !important}"
        f"{q} [data-testid=\"stHorizontalBlock\"]:has([class*=\"st-key-pop_\"])>[data-testid=\"stColumn\"],"
        f"{q} [data-testid=\"stHorizontalBlock\"]:has([class*=\"st-key-ex_\"])>[data-testid=\"stColumn\"]{{width:auto !important;min-width:0 !important;flex:none !important}}"
        f"{q} [class*=\"st-key-pop_\"] button p,{q} [class*=\"st-key-ex_\"] button p{{font-size:.9rem !important;white-space:normal;line-height:1.15}}"
        f"{q} .hero2 h1{{font-size:1.45rem !important;line-height:1.2 !important}}"
        f"{q} .hero2 p{{font-size:.88rem !important;line-height:1.4 !important}}"
        f"{q} .h2-tico svg{{width:92px !important;height:auto !important}}"
        f"html body .stApp.stApp [data-testid=\"stMain\"] .st-key-in_atalhos a[data-testid=\"stPageLink-NavLink\"]{{min-height:104px !important;padding:10px 6px !important;gap:7px !important}}"
        f"html body .stApp.stApp [data-testid=\"stMain\"] .st-key-in_atalhos a[data-testid=\"stPageLink-NavLink\"]:before{{width:46px !important;height:46px !important}}"
        "}"
    )


def compactar() -> str:
    """Celular: cabeçalho de página enxuto (linha de apoio atrás do botão "i"), menos espaço entre blocos e entre títulos."""
    q = "html body .stApp.stApp"
    return (
        f"@media (max-width:{K.CELULAR_MAX}px){{"
        f"{q} .pghead{{display:block;padding:10px 54px 10px 12px !important;margin:0 0 10px !important;overflow:visible !important}}"
        f"{q} .pghead::after{{display:none !important}}"
        f"{q} .pghead .pgsub{{display:none !important}}"
        f"{q} .pghead .pgt{{font-size:1.25rem !important;display:flex;align-items:center;gap:10px;line-height:1.2}}"
        f"{q} .pghead .pgmais{{display:block !important;position:absolute;top:9px;right:10px}}"
        f"{q} .pgmais>summary{{list-style:none;cursor:pointer;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;"
        "border:1px solid var(--dz-borda);background:var(--dz-cartao);color:var(--dz-texto);font-weight:800;font-style:italic}"
        f"{q} .pgmais>summary::-webkit-details-marker{{display:none}}"
        f"{q} .pgmais[open] .pgmais-t{{position:absolute;right:0;top:42px;width:min(82vw,320px);z-index:6;padding:10px 12px;background:var(--dz-cartao);"
        "border:1px solid var(--dz-borda);border-radius:14px;box-shadow:0 12px 28px -12px rgba(0,0,0,.7);font-size:.88rem;line-height:1.4;color:var(--dz-texto)}"
        f"{q} [data-testid=\"stMain\"] [data-testid=\"stVerticalBlock\"]{{gap:.65rem !important}}"
        f"{q} [data-testid=\"stMain\"] :is(h2,h3,h4){{margin:.35rem 0 .15rem !important;padding-top:.25rem !important}}"
        "}"
    )


def cabecalho_compacto() -> str:
    """Celular: cabeçalho nativo de 48 px (era ~60) e menos espaço no topo da página."""
    return (
        f"@media (max-width:{K.CELULAR_MAX}px){{"
        ".stApp header[data-testid=\"stHeader\"]{height:var(--dz-cab-h) !important;min-height:var(--dz-cab-h) !important}"
        ".stApp .block-container{padding-top:calc(var(--dz-cab-h) + .5rem) !important}"
        ".stApp [data-testid=\"stMain\"] :is(.stButton,.stFormSubmitButton) > button{min-height:var(--dz-toque)}}"
    )


def componentes() -> str:
    return (
        ".dz-cartao{background:var(--dz-cartao);border:1px solid var(--dz-borda);border-radius:var(--dz-r-cartao);padding:12px 14px;margin-bottom:8px}"
        ".dz-cartao-t{font-size:.78rem;font-weight:600;color:var(--dz-apoio);margin-bottom:6px}"
        ".dz-ind{background:var(--dz-cartao);border:1px solid var(--dz-borda);border-radius:var(--dz-r-cartao);padding:10px 12px}"
        ".dz-ind-r{font-size:.75rem;font-weight:500;color:var(--dz-apoio)}"
        ".dz-ind-v{font-size:1.25rem;font-weight:700;color:var(--dz-texto);font-variant-numeric:tabular-nums;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}"
        ".dz-ind-d{font-size:.72rem;color:var(--dz-apoio);margin-top:2px}"
        ".dz-var{font-size:.8rem;font-weight:600}.dz-pos{color:var(--dz-pos)}.dz-neg{color:var(--dz-neg)}.dz-neu{color:var(--dz-apoio)}"
        ".dz-selo{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.72rem;font-weight:600;border:1px solid var(--dz-borda);color:var(--dz-apoio)}"
        ".dz-selo-positivo{color:var(--dz-pos);border-color:var(--dz-pos)}.dz-selo-negativo{color:var(--dz-neg);border-color:var(--dz-neg)}"
        ".dz-selo-destaque{color:var(--dz-destaque);border-color:var(--dz-destaque)}"
        ".dz-skel{display:flex;flex-direction:column;gap:10px;padding:8px 0}"
        ".dz-skel i{display:block;height:14px;border-radius:7px;background:linear-gradient(90deg,var(--dz-elevado) 25%,var(--dz-borda) 50%,var(--dz-elevado) 75%);"
        "background-size:200% 100%;animation:dz-brilho 1.4s ease-in-out infinite}"
        "@keyframes dz-brilho{0%{background-position:200% 0}100%{background-position:-200% 0}}"
        ".dz-ico{flex:none;vertical-align:middle}"
        ".dz-tc-lista{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin:4px 0 12px}"
        ".dz-tc{background:var(--dz-cartao);border:1px solid var(--dz-borda);border-radius:var(--dz-r-cartao);padding:10px 12px}"
        ".dz-tc-t{font-weight:700;color:var(--dz-texto);margin-bottom:6px;overflow-wrap:anywhere}"
        ".dz-tc-g{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:6px 12px}"
        ".dz-tc-p span{display:block;font-size:.72rem;color:var(--dz-apoio)}.dz-tc-p b{font-weight:600;color:var(--dz-texto);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}"
        ".dz-hr{background:linear-gradient(160deg,color-mix(in srgb,var(--dz-destaque) 14%,var(--dz-cartao)),var(--dz-cartao));border:1px solid var(--dz-borda);"
        "border-radius:var(--dz-r-cartao);padding:14px;margin:6px 0 12px}"
        ".dz-hr-c{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.dz-hr-id{flex:1 1 140px;min-width:0}"
        ".dz-hr-t{font-size:1.15rem;font-weight:800;color:var(--dz-texto);overflow-wrap:anywhere}.dz-hr-s{font-size:.8rem;color:var(--dz-apoio);margin-top:2px}"
        ".dz-hr-dir{display:flex;flex-direction:column;align-items:flex-end;gap:6px}.dz-hr-v{font-size:1.25rem;font-weight:800;color:var(--dz-texto);font-variant-numeric:tabular-nums}"
        ".dz-hr-g{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:12px}"
        ".dz-hr-d{background:color-mix(in srgb,var(--dz-fundo) 55%,transparent);border:1px solid var(--dz-borda);border-radius:12px;padding:8px 10px}"
        ".dz-hr-d span{display:block;font-size:.7rem;letter-spacing:.04em;text-transform:uppercase;color:var(--dz-apoio)}"
        ".dz-hr-d b{font-size:1rem;color:var(--dz-texto);font-variant-numeric:tabular-nums}"
        ".dz-msg{display:flex;gap:10px;align-items:flex-start;border-radius:var(--dz-r-cartao);padding:10px 12px;margin-bottom:8px;font-size:.88rem;line-height:1.4;"
        "background:var(--dz-cartao);border:1px solid var(--dz-borda);color:var(--dz-texto)}"
        ".dz-msg-sucesso{border-color:var(--dz-pos)}.dz-msg-sucesso .dz-ico{color:var(--dz-pos)}"
        ".dz-msg-erro{border-color:var(--dz-neg)}.dz-msg-erro .dz-ico{color:var(--dz-neg)}"
        ".dz-msg-aviso{border-color:#E0A526}.dz-msg-aviso .dz-ico{color:#E0A526}.dz-msg-info .dz-ico{color:var(--dz-destaque)}"
        ".dz-vazio{text-align:center;padding:28px 16px;color:var(--dz-apoio)}.dz-vazio-t{font-weight:700;color:var(--dz-texto);margin-top:8px}.dz-vazio-x{font-size:.85rem;margin-top:4px}"
        ".dz-bp-t{display:flex;justify-content:space-between;font-size:.78rem;color:var(--dz-apoio);margin-bottom:4px}"
        "html body .stApp.stApp .dz-anel-r,html body .stApp.stApp .dz-bp-t,html body .stApp.stApp .dz-cartao-t,html body .stApp.stApp .dz-conq-i,html body .stApp.stApp .dz-conq-x,html body .stApp.stApp .dz-hr-s,html body .stApp.stApp .dz-ind-d,html body .stApp.stApp .dz-ind-r,html body .stApp.stApp .dz-pos-d,html body .stApp.stApp .dz-posc-c,html body .stApp.stApp .dz-rk-p,html body .stApp.stApp .dz-rk-s,html body .stApp.stApp .dz-vazio,html body .stApp.stApp .dz-bp-t span{color:var(--dz-apoio) !important}"
        "html body .stApp.stApp .dz-bp-t{gap:10px;white-space:nowrap}"
        ".dz-bp-f{height:10px;border-radius:999px;background:var(--dz-elevado);overflow:hidden}"
        ".dz-bp-f i{display:block;height:100%;border-radius:999px;background:var(--dz-destaque);transition:width 400ms ease}"
        ".dz-anel{text-align:center}.dz-anel-n{font:700 26px var(--dz-fonte);fill:var(--dz-texto)}.dz-anel-r{font-size:.78rem;color:var(--dz-apoio);margin-top:2px}"
        ".dz-anel circle:nth-of-type(2){transition:stroke-dasharray 500ms ease}"
        ".dz-conq{display:flex;gap:12px;align-items:center;background:var(--dz-cartao);border:1px solid var(--dz-borda);border-radius:var(--dz-r-cartao);padding:10px 12px;margin-bottom:8px}"
        ".dz-conq-i{display:grid;place-items:center;width:44px;height:44px;border-radius:50%;background:var(--dz-destaque);color:var(--dz-sobre)}"
        ".dz-conq-t{font-weight:700;color:var(--dz-texto)}.dz-conq-x{font-size:.8rem;color:var(--dz-apoio)}"
        ".dz-conq-off{opacity:.7}.dz-conq-off .dz-conq-i{background:var(--dz-elevado);color:var(--dz-apoio)}"
        ".dz-etapas{display:flex;gap:6px;align-items:center}.dz-etapas i{width:10px;height:10px;border-radius:50%;background:var(--dz-elevado);border:1px solid var(--dz-borda)}"
        ".dz-etapas i.ok{background:var(--dz-pos);border-color:var(--dz-pos)}.dz-etapas i.now{background:var(--dz-destaque);border-color:var(--dz-destaque);width:14px;height:14px}"
        ".dz-grade{display:grid;gap:8px;grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:8px}"
        "@media (min-width:700px){.dz-g3{grid-template-columns:repeat(3,minmax(0,1fr))}.dz-g4{grid-template-columns:repeat(4,minmax(0,1fr))}}"
        ".dz-g1{grid-template-columns:minmax(0,1fr)}"
        ".dz-rklista{display:flex;flex-direction:column;gap:6px;margin-bottom:8px}"
        ".dz-rk{display:flex;align-items:center;gap:12px;background:var(--dz-cartao);border:1px solid var(--dz-borda);border-radius:var(--dz-r-cartao);padding:10px 12px}"
        ".dz-voce{border-color:var(--dz-destaque);background:color-mix(in srgb,var(--dz-destaque) 14%,var(--dz-cartao))}"
        ".dz-rk-p{min-width:32px;text-align:center;font-weight:800;font-size:1.05rem;color:var(--dz-apoio);font-variant-numeric:tabular-nums}"
        ".dz-rk-n{flex:1;min-width:0}.dz-rk-nome{font-weight:700;color:var(--dz-texto);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".dz-rk-s{font-size:.74rem;color:var(--dz-apoio)}.dz-rk-v{font-weight:800;font-variant-numeric:tabular-nums;font-size:1.05rem}"
        ".dz-posc{background:var(--dz-cartao);border:1px solid var(--dz-borda);border-left:4px solid var(--dz-destaque);border-radius:var(--dz-r-cartao);padding:10px 12px;margin-bottom:8px}"
        ".dz-posc-t{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px}.dz-posc-t>div:first-child{min-width:0;flex:1}.dz-posc-n{font-weight:700;color:var(--dz-texto);overflow-wrap:anywhere}"
        ".dz-posc-c{font-size:.74rem;color:var(--dz-apoio)}.dz-posc-v{flex:none;white-space:nowrap;text-align:right;font-weight:800;color:var(--dz-texto);font-variant-numeric:tabular-nums}"
        ".dz-pos-d{font-size:.72rem;color:var(--dz-apoio);margin-top:6px}"
        ".dz-entra{animation:dz-entra 220ms ease-out both}@keyframes dz-entra{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}"
        "@media (prefers-reduced-motion:reduce){.dz-skel i,.dz-entra,.dz-bp-f i{animation:none;transition:none}.stApp [data-testid=\"stDialog\"] div[role=\"dialog\"]{animation:none !important}.stApp *{transition:none !important}}"
    )


def widgets() -> str:
    """Botões, campos, abas, avisos e folha inferior do Streamlit, com a mesma cara em todas as telas.
    Só usa cores de destaque (funcionam em fundo claro e escuro) e geometria; o fundo das páginas continua sendo das Etapas 3 a 5."""
    fora = ":not(.st-key-barra_areas *)"      # a barra inferior tem estilo próprio
    b = f".stApp [data-testid=\"stMain\"] .stButton > button{fora}"
    return (
        f"{b}{{border-radius:var(--dz-r-painel);min-height:var(--dz-toque);font-weight:600;transition:transform var(--dz-ms) ease,filter var(--dz-ms) ease}}"
        f"{b}:active{{transform:scale(.98)}}"
        f"{b}[data-testid^=\"stBaseButton-primary\"]{{background:var(--dz-destaque);border:0;color:var(--dz-sobre)}}"
        f"{b}[data-testid^=\"stBaseButton-primary\"] :is(p,span){{color:var(--dz-sobre)}}"
        f"{b}[data-testid^=\"stBaseButton-primary\"]:hover{{filter:brightness(1.08)}}"
        ".stApp :is(button,input,textarea,[role=\"tab\"],[role=\"switch\"]):focus-visible{outline:2px solid var(--dz-ativo);outline-offset:2px}"
        ".stApp [data-baseweb=\"input\"],.stApp [data-baseweb=\"select\"] > div,.stApp [data-baseweb=\"textarea\"]{border-radius:var(--dz-r-campo)}"
        ".stApp [data-testid=\"stAlert\"]{border-radius:var(--dz-r-cartao)}"
        ".stApp [data-baseweb=\"tab-list\"] button[role=\"tab\"]{min-height:var(--dz-toque)}"
        f"@media (max-width:{K.CELULAR_MAX}px){{"
        ".stApp [data-testid=\"stDialog\"]{align-items:flex-end !important;padding:0 !important}"
        f".stApp [data-testid=\"stDialog\"] div[role=\"dialog\"]{{width:100% !important;max-width:100% !important;margin:0 !important;max-height:90dvh;"
        "border-radius:var(--dz-r-painel) var(--dz-r-painel) 0 0 !important;padding-bottom:env(safe-area-inset-bottom,0px);animation:dz-sobe 220ms ease-out}"
        "@keyframes dz-sobe{from{transform:translateY(24px);opacity:0}to{transform:none;opacity:1}}"
        ".stApp :is(input,textarea){font-size:16px !important}}"      # abaixo de 16 px o iPhone dá zoom ao focar; no Android evita o salto do teclado
    )


def legado() -> str:
    """Faz as classes antigas (cartões, KPIs, cabeçalho de página, métricas, expansores, formulários) usarem as cores do tema da área.
    Cada área ganha o seu fundo (Aprender índigo e verde-limão, Análise azul-noite e violeta, Wallet Game carvão e dourado).
    Elementos com cor própria no atributo style (status, alertas) não são tocados."""
    p = "html body .stApp"
    q = "html body .stApp.stApp"      # um pouco mais forte: vence as regras antigas de mesma força
    livre = ":not([style*=\"border\"]):not([style*=\"background\"])"
    return (
        f"{p}{{background:radial-gradient(120% 45% at 50% -8%,color-mix(in srgb,var(--dz-destaque) 15%,transparent),transparent 62%),var(--dz-fundo) !important}}"
        f"{p} :is(.cartao,.card,.kpi,.mini,.ctx,.vazio,[data-testid=\"stMetric\"],[data-testid=\"stExpander\"],[data-testid=\"stForm\"]){livre}"
        "{background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;border-radius:var(--dz-r-cartao) !important;box-shadow:none !important}"
        f"{p} .pghead{{background:linear-gradient(135deg,color-mix(in srgb,var(--dz-destaque) 22%,var(--dz-cartao)),var(--dz-cartao)) !important;"
        "border:1px solid var(--dz-borda) !important;border-radius:var(--dz-r-painel) !important}"
        f"{p} :is([data-testid=\"stCaptionContainer\"],[data-testid=\"stCaptionContainer\"] p,small){{color:var(--dz-apoio) !important;opacity:1 !important}}"
        f"@media (max-width:{K.CELULAR_MAX}px){{{p} [data-testid=\"stAlert\"]{{padding:0 !important;border:0 !important;background:transparent !important;box-shadow:none !important}}"
        f"{p} [data-testid=\"stAlertContainer\"]{{padding:.7rem .9rem !important;border-radius:var(--dz-r-cartao) !important;line-height:1.45}}"
        f"{p} [data-testid^=\"stAlertContent\"] p{{margin:0 !important;line-height:1.45 !important}}}}"
        f"{q} .stTabs [role=\"tab\"]{{border-radius:999px !important}}"
        f"{q} .stTabs [role=\"tab\"][aria-selected=\"true\"]{{background:var(--dz-destaque) !important;background-image:none !important;border:0 !important;box-shadow:none !important}}"
        f"{q} .stTabs [role=\"tab\"][aria-selected=\"true\"] :is(p,span,div){{color:var(--dz-sobre) !important;-webkit-text-fill-color:var(--dz-sobre) !important}}"
        f"{q} .stTabs [data-baseweb=\"tab-highlight\"],{q} .stTabs [data-baseweb=\"tab-border\"]{{display:none !important}}"
        f"{q} .dz-msg,{q} .dz-msg div{{color:var(--dz-texto) !important;-webkit-text-fill-color:var(--dz-texto) !important}}"
        f"{q} .dz-msg{{margin-bottom:14px !important}}"
        f"{q} .stTabs [role=\"tab\"]{{padding:6px 14px !important;height:auto !important;min-height:36px !important;line-height:1.2 !important}}"
        f"{q} .stTabs [role=\"tablist\"]>div:not([role]){{display:none !important}}"
        f"{p} [data-testid=\"stElementContainer\"]:has(>[data-testid=\"stMarkdown\"] [data-testid=\"stMarkdownContainer\"]>style:only-child){{display:none !important}}"
        f"{p} [data-testid=\"stMain\"] hr{{border-color:var(--dz-borda) !important;opacity:.6}}"
        f"{p} .kpi,{p} .card{{margin-bottom:12px !important}}"
        f"{q} [data-testid=\"stMarkdownContainer\"]:has(>.kpi),{q} [data-testid=\"stMarkdownContainer\"]:has(>.card){{padding-bottom:12px}}"
        f"{q} [data-testid=\"stPlotlyChart\"]{{background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important}}"
        f"{q} [data-testid=\"stPlotlyChart\"] .main-svg>.bg,{q} [data-testid=\"stPlotlyChart\"] .main-svg .plotbg .bg{{fill:transparent !important}}"
        f"{q} [data-testid=\"stPlotlyChart\"] :is(.xtick,.ytick,.g-xtitle,.g-ytitle,.gtitle,.legendtext,.annotation-text,.slicetext) text,"
        f"{q} [data-testid=\"stPlotlyChart\"] :is(.xtick,.ytick,.legendtext,.annotation-text,.slicetext) tspan{{fill:var(--dz-texto) !important}}"
        f"{q} [data-testid=\"stPlotlyChart\"] .gridlayer path{{stroke:rgba(255,255,255,.10) !important}}"
        f"{q} [data-testid=\"stPlotlyChart\"] .zerolinelayer path{{stroke:rgba(255,255,255,.28) !important}}"
        f"{q} [data-testid=\"stMain\"] a[data-testid=\"stPageLink-NavLink\"]{{height:auto !important;min-height:44px;border-radius:18px !important;padding:8px 14px !important}}"
        f"{q} [data-testid=\"stMain\"] a[data-testid=\"stPageLink-NavLink\"] :is(p,span){{white-space:normal !important;overflow:visible !important;text-overflow:clip !important;line-height:1.3 !important}}"
        f"{p} [data-testid=\"stElementContainer\"]:has(>[data-testid=\"stMarkdown\"] [data-testid=\"stMarkdownContainer\"]:empty){{display:none !important}}"
        f"{q} [class*=\"st-key-abaoff_\"],{q} [class*=\"st-key-abaoff_\"] *{{display:none !important}}"
        f"{q} [data-testid=\"stExpander\"] summary :is([data-testid=\"stIconMaterial\"],svg){{color:var(--dz-destaque) !important;fill:currentColor}}"
        f"{q} .jor-metabar{{margin-bottom:14px !important}}{q} .st-key-jor_som_sw{{margin-top:8px !important}}"
        f"{q} .dz-rklista,{q} .dz-tc-lista,{q} .dz-msg{{margin-bottom:16px !important}}"
        f"{p} .pgi{{background:color-mix(in srgb,var(--dz-destaque) 20%,transparent) !important;color:var(--dz-destaque) !important}}"
    )


def navegacao() -> str:
    """Atalho da conta no canto do cabeçalho e 'voltar' das sub-páginas, com cara de app."""
    return (
        ".stApp .st-key-topo_perfil{position:fixed;top:4px;left:10px;z-index:1000001;width:min(280px,calc(100vw - 20px)) !important}"      # acima do cabeçalho do Streamlit (z-index ~1000000)
        ".stApp .st-key-topo_perfil>[data-testid=\"stVerticalBlock\"]{flex-direction:row !important;align-items:center;gap:8px !important}"
        ".stApp .st-key-topo_perfil [data-testid=\"stElementContainer\"]{width:auto !important}"
        ".stApp .st-key-topo_perfil [data-testid=\"stElementContainer\"]:first-child{margin-right:auto}"
        ".stApp .st-key-topo_perfil .wm{display:flex;align-items:center;gap:8px;white-space:nowrap}"
        ".stApp .st-key-topo_perfil .wm-t{font-weight:900;font-size:1.02rem;letter-spacing:-.01em;color:#fff !important;-webkit-text-fill-color:#fff}"
        ".stApp .st-key-topo_perfil .wm-t em{font-style:normal;color:var(--dz-destaque) !important;-webkit-text-fill-color:var(--dz-destaque)}"
        ".stApp .st-key-topo_perfil :is(button,a){display:flex;align-items:center;justify-content:center;min-width:40px;min-height:40px;padding:0 12px;gap:6px;border-radius:999px;"
        "background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;color:var(--dz-texto) !important;text-decoration:none;font-size:.8rem;font-weight:600;box-shadow:none !important}"
        ".stApp .st-key-topo_perfil :is(button,a):hover{border-color:var(--dz-destaque) !important}"
        ".stApp .st-key-topo_perfil [data-testid=\"stPopover\"]{width:auto !important}"
        f"@media (max-width:{K.CELULAR_MAX}px){{.stApp .st-key-topo_perfil :is(button,a){{padding:0;width:40px}}.stApp .st-key-topo_perfil :is(button,a) p{{display:none}}"
        ".stApp .st-key-topo_perfil button [data-testid=\"stIconMaterial\"]:not(:first-child){display:none}}"
        ".stApp .st-key-trilha_voltar a{display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:0 12px;border-radius:999px;background:var(--dz-cartao);"
        "border:1px solid var(--dz-borda);color:var(--dz-apoio);text-decoration:none;font-size:.8rem;font-weight:600}"
        ".stApp .st-key-trilha_voltar a:hover{color:var(--dz-texto);border-color:var(--dz-destaque)}"
        ".stApp .st-key-trilha_voltar{margin-bottom:4px}"
        "@keyframes dz-fade{from{opacity:0}to{opacity:1}}"
        ".stApp [data-testid=\"stMain\"] .block-container{animation:dz-fade 200ms ease-out}"
        "@media (prefers-reduced-motion:reduce){.stApp [data-testid=\"stMain\"] .block-container{animation:none}}"
    )


def marca() -> str:
    """Nome no cabeçalho: 'Hunters' na cor de marca (o resto do .wm-t continua do tema.py)."""
    return (".wm-t em{font-style:normal;background:none !important;-webkit-text-fill-color:" + T.MARCA["cor"] + " !important;color:" + T.MARCA["cor"] + " !important}")


def css(tema_id: str, n_itens: int) -> str:
    """CSS completo da v2 (uma tag <style>, sem linhas em branco, para o st.markdown não quebrar o bloco)."""
    return "<style>@import url('" + K.FONTE_URL + "');\n" + "\n".join([variaveis(tema_id), barra_inferior(n_itens), cabecalho_compacto(), widgets(), legado(), navegacao(), componentes(), marca(), sensacao_de_app(n_itens), compactar(), hubs_compactos(), controles_mobile(), acordeao()]) + "</style>"
