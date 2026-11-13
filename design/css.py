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


_ESPADAS = ("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' "
            "stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 3L17 17M14.5 19.5l5-5M17 17l4 4M21 3L7 17M9.5 19.5l-5-5M7 17l-4 4'/%3E%3C/svg%3E")


def sensacao_de_app(n_itens: int) -> str:
    """Jeito de aplicativo (inspirado em jogos): barra inferior só com ícones e item ativo expandido, botões com relevo, seções em
    fichas que rolam de lado, sem âncoras de título nem rolagem de página inteira escondendo o que importa."""
    b = "html body .stApp.stApp .st-key-barra_areas"
    q = "html body .stApp.stApp"
    ativo = "[data-testid^=\"stBaseButton-primary\"]"
    jg = "[data-testid=\"stColumn\"]:has(.st-key-area_btn_jogar)"
    barra = (
        f"@media (max-width:{K.TABLET_MAX}px){{"
        f"{b}{{background:linear-gradient(180deg,#14103A,#0A0722) !important;border-top:1px solid rgba(139,108,255,.55) !important;"
        "border-radius:26px 26px 0 0 !important;box-shadow:0 -10px 30px -8px rgba(110,75,255,.45) !important;overflow:visible !important}"
        f"{b} [data-testid=\"stHorizontalBlock\"]{{display:flex !important;gap:2px !important;align-items:flex-end !important;overflow:visible !important}}"
        f"{b} [data-testid=\"stColumn\"]{{flex:1 1 0 !important;width:auto !important;min-width:0 !important;overflow:visible !important}}"
        f"{b} .stButton > button{{min-height:58px !important;background:transparent !important;border:0 !important;box-shadow:none !important;"
        "border-radius:14px !important;position:relative}"
        f"{b} .stButton > button p{{font-size:.76rem !important;font-weight:700 !important}}"
        f"{b} .stButton > button [data-testid=\"stIconMaterial\"]{{font-size:1.7rem !important}}"
        f"{b} .stButton > button:not({ativo}) *{{color:#E4DEFF !important;-webkit-text-fill-color:#E4DEFF !important;background:transparent !important}}"
        f"{b} .stButton > button > div,{b} .stButton > button [data-testid=\"stMarkdownContainer\"]{{display:flex !important;flex-direction:column !important;align-items:center !important;gap:2px !important}}"
        f"{b} .stButton > button p{{flex-direction:column !important}}"
        f"{b} .stButton > button{ativo}{{background:transparent !important;box-shadow:none !important}}"
        f"{b} .stButton > button{ativo} *{{color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important;background:transparent !important;"
        "text-shadow:0 0 12px rgba(255,201,60,.65)}"
        f"{b} .stButton > button{ativo}::after{{content:\"\";position:absolute;left:28%;right:28%;bottom:3px;height:3px;border-radius:3px;"
        "background:#FFB020;box-shadow:0 0 10px 2px rgba(255,176,32,.8)}"
        # Jogar: aba central elevada, roxa, com brilho
        f"{b} {jg}{{flex:1.25 1 0 !important}}"
        f"{b} {jg} .stButton > button{{min-height:78px !important;margin-top:-18px;border-radius:26px 26px 14px 14px !important;"
        "background:linear-gradient(180deg,rgba(150,90,255,.55),rgba(60,30,150,.35)) !important;border:1px solid rgba(190,150,255,.75) !important;"
        "box-shadow:0 0 26px 2px rgba(150,90,255,.7),inset 0 1px 0 rgba(255,255,255,.35) !important}"
        f"{b} {jg} .stButton > button *{{color:#E56BFF !important;-webkit-text-fill-color:#E56BFF !important;text-shadow:0 0 12px rgba(229,107,255,.7)}}"
        # ícone de espadas cruzadas desenhado por máscara (o nome "swords" não existe na fonte de ícones do Streamlit)
        f"{b} {jg} .stButton > button [data-testid=\"stIconMaterial\"]{{font-size:0 !important;width:2.3rem !important;height:2.3rem !important;"
        "background:currentColor !important;-webkit-mask:url(\"" + _ESPADAS + "\") center/contain no-repeat;mask:url(\"" + _ESPADAS + "\") center/contain no-repeat;"
        "filter:drop-shadow(0 0 6px rgba(229,107,255,.8))}"
        f"{b} {jg} .stButton > button{ativo} *{{color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}"
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
    hud = ""          # a faixa de indicadores (linha 2 do cabeçalho) tem estilo próprio em cabecalho_global.py
    return barra + relevo + fichas + limpeza + ajuda + hud


def _fundo_cabecalho() -> str:
    try:
        import fundos_cabecalho
        return fundos_cabecalho.css()
    except Exception:
        return ""


def acordeao() -> str:
    """Navegação das seções de cada tela (secoes.abas): botões compactos no topo, ícone redondo colorido em cima e nome embaixo, 2 ou 3 por
    linha; o botão da seção ativa fica destacado e só o conteúdo dela aparece. (O nome da função é o antigo; não há mais barras que abrem.)"""
    q = "html body .stApp.stApp.stApp"
    n = f"{q} [class*=\"st-key-acdnav_\"]"
    ac = "var(--ac,var(--dz-destaque))"
    return (
        f"{n}{{margin:0 0 8px}}"
        f"{n} button{{width:100% !important;min-height:60px !important;height:auto !important;border-radius:16px !important;padding:6px 4px !important;gap:3px !important;display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;"
        f"background:linear-gradient(160deg,color-mix(in srgb,{ac} 14%,var(--dz-cartao)),var(--dz-cartao) 75%) !important;"
        f"border:1px solid color-mix(in srgb,{ac} 45%,transparent) !important;box-shadow:0 3px 0 color-mix(in srgb,{ac} 28%,#0B0821) !important;transition:transform .08s,box-shadow .08s}}"
        f"{n} button:active{{transform:translateY(2px);box-shadow:0 1px 0 color-mix(in srgb,{ac} 28%,#0B0821) !important}}"
        f"{n} button>div{{display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;gap:3px !important;width:100% !important;margin:0 !important}}"
        f"{n} button [data-testid=\"stMarkdownContainer\"]{{flex:0 0 auto;min-width:0;margin:0 !important;padding:0 !important;width:auto !important}}"
        f"{n} button [data-testid=\"stIconMaterial\"]{{flex:0 0 26px;width:26px;height:26px;border-radius:50%;display:grid !important;place-items:center;font-size:16px !important;color:#fff !important;margin:0 !important;"
        f"background:radial-gradient(circle at 30% 18%,rgba(255,255,255,.45),transparent 52%),{ac};box-shadow:0 2px 0 color-mix(in srgb,{ac} 55%,#0B0821)}}"
        f"{n} button :is(p,span):not([data-testid=\"stIconMaterial\"]){{font-size:.74rem !important;font-weight:800 !important;line-height:1.1 !important;color:var(--dz-texto) !important;text-align:center !important;white-space:normal !important;overflow-wrap:anywhere}}"
        f"{n} button[data-testid^=\"stBaseButton-primary\"]{{border-color:{ac} !important;"
        f"background:linear-gradient(160deg,color-mix(in srgb,{ac} 34%,var(--dz-cartao)),color-mix(in srgb,{ac} 12%,var(--dz-cartao)) 80%) !important;"
        f"box-shadow:0 3px 0 color-mix(in srgb,{ac} 50%,#0B0821),0 0 0 2px color-mix(in srgb,{ac} 22%,transparent) !important}}"
        f"{q} [class*=\"st-key-acdon_\"]{{margin:2px 0 14px}}"
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
        f"{q} [data-testid=\"stRadio\"]:not([class*=\"st-key-jor_r_\"] [data-testid=\"stRadio\"]) [role=\"radiogroup\"]{{flex-wrap:wrap !important;gap:8px !important}}"
        f"{q} [class*=\"st-key-jor_r_\"] [data-testid=\"stWidgetLabel\"]{{display:none !important}}"
        f"{q} [data-testid=\"stExpander\"] summary [data-testid=\"stIconMaterial\"]{{color:#BDB5E6 !important}}"
        f"{q} [data-testid=\"stMain\"] :is(h4,h5,h6){{font-size:1.05rem !important;line-height:1.25 !important;font-weight:800 !important;color:#E4DFFF !important;margin:.9rem 0 .35rem !important}}"
        f"{q} [data-testid=\"stRadio\"]:not([class*=\"st-key-jor_r_\"] [data-testid=\"stRadio\"]) [role=\"radiogroup\"] label{{border:1px solid var(--dz-borda);background:var(--dz-cartao);border-radius:999px;padding:6px 12px !important;margin:0 !important}}"
        f"{q} [data-testid=\"stRadio\"]:not([class*=\"st-key-jor_r_\"] [data-testid=\"stRadio\"]) [role=\"radiogroup\"] label:has(input:checked){{border-color:var(--dz-destaque);box-shadow:0 0 0 1px var(--dz-destaque) inset}}"
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
        "html body .stApp.stApp .st-key-topo_perfil{position:fixed;top:0;left:0;right:44px;height:var(--dz-cab-h,48px);box-sizing:border-box;padding:0 4px 0 10px;z-index:1000001;width:auto !important;"
        "display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;align-items:center !important;gap:2px !important}"
        "html body .stApp.stApp .st-key-topo_perfil [data-testid=\"stElementContainer\"]{width:auto !important;margin:0 !important}"
        "html body .stApp.stApp .st-key-topo_perfil [data-testid=\"stElementContainer\"]:first-child{margin-right:auto !important}"
        "html body .stApp.stApp .st-key-topo_perfil [data-testid=\"stMarkdownContainer\"]{margin:0 !important;padding:0 !important}"
        "html body .stApp.stApp .st-key-topo_perfil .wm{display:flex;align-items:center;gap:8px;white-space:nowrap;margin:0 !important;padding:0 !important}"
        "html body .stApp.stApp .st-key-topo_perfil .wm svg{display:block;flex:none}"
        "html body .stApp.stApp .st-key-topo_perfil .wm-t{font-weight:900;font-size:1.02rem;letter-spacing:-.01em;color:#fff !important;-webkit-text-fill-color:#fff}"
        "html body .stApp.stApp .st-key-topo_perfil .wm-t em{font-style:normal;color:var(--dz-destaque) !important;-webkit-text-fill-color:var(--dz-destaque)}"
        "html body .stApp.stApp .st-key-topo_perfil :is(button,a){display:flex;align-items:center;justify-content:center;width:44px !important;min-width:44px;height:44px;min-height:44px;padding:0 !important;"
        "border-radius:12px !important;background:transparent !important;border:none !important;box-shadow:none !important;color:var(--dz-texto) !important;text-decoration:none;transition:background .15s}"
        "html body .stApp.stApp .st-key-topo_perfil :is(button,a):is(:hover,:focus,:focus-visible,:active){box-shadow:none !important;outline:none !important;border:none !important;background:rgba(255,255,255,.08) !important}"
        "html body .stApp.stApp .st-key-topo_perfil :is(button,a):active{background:rgba(255,255,255,.16) !important}"
        "html body .stApp.stApp .st-key-topo_perfil :is(button,a) p{display:none !important}"
        "html body .stApp.stApp .st-key-topo_perfil [data-testid=\"stPopover\"]{width:auto !important}"
        "html body .stApp.stApp .st-key-topo_perfil button [data-testid=\"stIconMaterial\"]{font-size:26px !important;color:var(--dz-texto) !important}"
        "html body .stApp.stApp .st-key-topo_perfil button [data-testid=\"stIconMaterial\"]:not(:first-child){display:none !important}"
        "html body .stApp.stApp .st-key-topo_perfil button svg,html body .stApp.stApp .st-key-topo_perfil button [data-testid=\"stPopoverButtonChevron\"]{display:none !important}"
        "html body .stApp.stApp [data-testid=\"stDialog\"] a[data-testid=\"stPageLink-NavLink\"]{display:flex !important;width:100% !important;justify-content:flex-start !important;gap:12px;min-height:48px;padding:0 14px !important;"
        "border-radius:14px !important;background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;box-shadow:none !important;text-decoration:none}"
        "html body .stApp.stApp [data-testid=\"stDialog\"] a[data-testid=\"stPageLink-NavLink\"] :is(p,span){color:var(--dz-texto) !important;font-weight:600 !important}"
        "html body .stApp.stApp [data-testid=\"stDialog\"] a[data-testid=\"stPageLink-NavLink\"] [data-testid=\"stIconMaterial\"]{color:var(--dz-destaque) !important}"
        "html body .stApp.stApp [data-testid=\"stDialog\"] button[data-testid=\"stBaseButton-tertiary\"]{width:100%;justify-content:flex-start;min-height:48px;padding:0 14px;border-radius:14px;"
        "background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;box-shadow:none !important}"
        "html body .stApp.stApp [data-testid=\"stDialog\"] button[data-testid=\"stBaseButton-tertiary\"] :is(p,span){color:var(--dz-texto) !important;font-weight:600 !important}"
        "html body .stApp.stApp [data-testid=\"stToolbarActions\"],.stApp [data-testid=\"stAppDeployButton\"],.stApp .stAppDeployButton{display:none !important}"
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


def fichas_globais() -> str:
    """Controles segmentados do app inteiro (estilo antigo: retângulos colados e cortados) viram fichas em pílula que quebram linha,
    com a cor de destaque do tema; vale também para a Wallet Game, Negociar, Ranking, Notícias etc."""
    q = "html body .stApp.stApp [data-testid=\"stMain\"]"
    sc = f"{q} [data-testid=\"stSegmentedControl\"]"
    return (
        f"{sc}{{max-width:100%;overflow:visible}}"
        f"{sc} :is([role=\"group\"],[data-testid^=\"stButtonGroup\"],[data-testid^=\"stButtonGroup\"]>div){{display:flex !important;flex-wrap:wrap !important;gap:8px !important;"
        "width:100% !important;max-width:100% !important;overflow:visible !important;border:0 !important;background:transparent !important;box-shadow:none !important}"
        f"{sc} button{{flex:0 1 auto !important;min-height:42px;padding:6px 14px !important;border-radius:999px !important;border:2px solid var(--dz-borda) !important;"
        "background:var(--dz-cartao) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important;white-space:normal !important;max-width:100%;margin:0 !important}"
        f"{sc} button :is(p,span){{color:var(--dz-texto) !important;font-weight:700 !important;line-height:1.15 !important;font-size:.88rem !important}}"
        f"{sc} button:active{{transform:translateY(2px);box-shadow:0 1px 0 rgba(0,0,0,.35) !important}}"
        f"{sc} button[data-testid$=\"Active\"]{{background:var(--dz-destaque) !important;border-color:var(--dz-destaque) !important;"
        "box-shadow:0 3px 0 color-mix(in srgb,var(--dz-destaque) 50%,#000) !important}"
        f"{sc} button[data-testid$=\"Active\"] :is(p,span){{color:var(--dz-sobre) !important;-webkit-text-fill-color:var(--dz-sobre) !important}}"
        f"{q} :is([data-testid=\"stSelectbox\"],[data-testid=\"stNumberInput\"],[data-testid=\"stTextInput\"]){{max-width:100%}}"
        # avisos que aparecem e somem (st.toast; ficam fora do .stApp, por isso o seletor não o usa): cartão de vidro roxo do app, sem a moldura interna
        "html body [data-testid=\"stToast\"]{background:linear-gradient(160deg,#3A2A75,#241C4D) !important;border:1px solid rgba(139,108,255,.55) !important;"
        "border-left:4px solid #8BE04E !important;border-radius:18px !important;box-shadow:0 14px 30px -12px rgba(0,0,0,.7) !important;padding:6px 10px !important;max-width:min(420px,calc(100vw - 1.5rem)) !important}"
        "html body [data-testid=\"stToast\"] *{border:0 !important;background:transparent !important;box-shadow:none !important;outline:0 !important;color:#F1EEFF !important}"
        "html body [data-testid=\"stToastContainer\"],html body [data-testid=\"stToast\"]>div{border-radius:18px !important}"
        "html body [data-testid=\"stToast\"] [data-testid=\"stMarkdownContainer\"] p{font-size:.92rem !important;font-weight:700 !important;line-height:1.35 !important;margin:0 !important}"
        "html body [data-testid=\"stToast\"] [data-testid=\"stToastDynamicIcon\"],html body [data-testid=\"stToast\"] [data-testid=\"stToastIcon\"]{font-size:1.25rem !important;margin-right:6px !important}"
        # padronização: números em cartões lado a lado (2 por linha, mesmo no celular), abas em cápsula e avisos como cartões
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] [data-testid=\"stHorizontalBlock\"]:has(>[data-testid=\"stColumn\"] [data-testid=\"stMetric\"]){flex-wrap:wrap !important;gap:8px !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] [data-testid=\"stHorizontalBlock\"]:has(>[data-testid=\"stColumn\"] [data-testid=\"stMetric\"])>[data-testid=\"stColumn\"]{flex:1 1 calc(50% - 8px) !important;min-width:calc(50% - 8px) !important;width:auto !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMetric\"]{padding:12px 14px !important;border-radius:16px !important;background:var(--dz-cartao) !important;"
        "border:1px solid var(--dz-borda) !important;border-left:4px solid var(--dz-destaque) !important;min-height:0 !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMetricLabel\"] *{font-size:.7rem !important;letter-spacing:.05em !important;text-transform:uppercase !important;font-weight:800 !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMetricValue\"],html body .stApp.stApp.stApp [data-testid=\"stMetricValue\"] *{font-size:1.2rem !important;font-weight:800 !important;line-height:1.2 !important}"
        "html body .stApp.stApp.stApp .stTabs [data-baseweb=\"tab-list\"]{border-bottom:0 !important;background:var(--dz-cartao) !important;padding:4px !important;border-radius:999px !important;gap:4px !important;width:100% !important;flex-wrap:nowrap !important;overflow-x:auto}"
        "html body .stApp.stApp.stApp .stTabs [role=\"tab\"]{flex:1 1 0 !important;justify-content:center !important;min-width:max-content}"
        "html body .stApp.stApp.stApp [data-testid=\"stAlert\"]{border-radius:16px !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stExpander\"]{border-radius:16px !important;background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stExpander\"] summary p{font-weight:800 !important}"
        # caixas de escolha e de pesquisa: maiores, com brilho na cor do destaque e rótulo pequeno em cima
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] :is([data-testid=\"stSelectbox\"],[data-testid=\"stMultiSelect\"],[data-testid=\"stTextInput\"]) label p{font-size:.74rem !important;font-weight:800 !important;"
        "letter-spacing:.06em !important;text-transform:uppercase !important;color:#BDB5E6 !important;margin-bottom:2px !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] :is([data-baseweb=\"select\"]>div,[data-baseweb=\"input\"]){min-height:54px !important;border-radius:18px !important;"
        "background:linear-gradient(160deg,color-mix(in srgb,var(--dz-destaque) 14%,var(--dz-cartao)),var(--dz-cartao) 80%) !important;"
        "border:1.5px solid color-mix(in srgb,var(--dz-destaque) 55%,transparent) !important;box-shadow:0 8px 20px -14px var(--dz-destaque) !important;padding-left:6px !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] :is([data-baseweb=\"select\"]>div,[data-baseweb=\"input\"]):focus-within{border-color:var(--dz-destaque) !important;"
        "box-shadow:0 0 0 3px color-mix(in srgb,var(--dz-destaque) 28%,transparent) !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] [data-baseweb=\"select\"] input::placeholder,html body .stApp.stApp.stApp [data-testid=\"stMain\"] [data-baseweb=\"input\"] input::placeholder{color:#9D94CC !important;opacity:1 !important}"
        "html body .stApp.stApp.stApp [data-testid=\"stMain\"] [data-baseweb=\"select\"] svg{color:var(--dz-destaque) !important;fill:var(--dz-destaque) !important}"
        # botões padronizados: seletor de profundidade em pílulas iguais às do resto do app; abas sem a linha embaixo
        "html body .stApp.stApp.stApp .st-key-home_prof :is([role=\"group\"],[data-testid^=\"stButtonGroup\"],[data-testid^=\"stButtonGroup\"]>div){display:flex !important;flex-wrap:nowrap !important;gap:8px !important;"
        "width:100% !important;border:0 !important;background:transparent !important;box-shadow:none !important;overflow:visible !important}"
        "html body .stApp.stApp.stApp .st-key-home_prof button{flex:1 1 0 !important;min-width:0 !important;min-height:42px !important;border-radius:999px !important;"
        "border:2px solid var(--dz-borda) !important;background:var(--dz-cartao) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important;padding:6px 8px !important;margin:0 !important}"
        "html body .stApp.stApp.stApp .st-key-home_prof button :is(p,span){font-size:.82rem !important;font-weight:800 !important;color:var(--dz-texto) !important;white-space:nowrap !important}"
        "html body .stApp.stApp.stApp .st-key-home_prof button:is([aria-checked=\"true\"],[aria-pressed=\"true\"],[data-testid$=\"Active\"]){background:var(--dz-destaque) !important;border-color:var(--dz-destaque) !important}"
        "html body .stApp.stApp.stApp .st-key-home_prof button:is([aria-checked=\"true\"],[aria-pressed=\"true\"],[data-testid$=\"Active\"]) :is(p,span){color:var(--dz-sobre) !important}"
        "html body .stApp.stApp.stApp .stTabs :is([data-baseweb=\"tab-highlight\"],[data-baseweb=\"tab-border\"]){display:none !important;height:0 !important;background:transparent !important}"
        + _fundo_cabecalho()
    )


def css(tema_id: str, n_itens: int) -> str:
    """CSS completo da v2 (uma tag <style>, sem linhas em branco, para o st.markdown não quebrar o bloco)."""
    return "<style>@import url('" + K.FONTE_URL + "');\n" + "\n".join([variaveis(tema_id), barra_inferior(n_itens), cabecalho_compacto(), widgets(), legado(), navegacao(), componentes(), marca(), sensacao_de_app(n_itens), compactar(), hubs_compactos(), controles_mobile(), acordeao(), fichas_globais()]) + "</style>"
