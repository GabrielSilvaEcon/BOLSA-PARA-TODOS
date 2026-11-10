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
        ".dz-msg{display:flex;gap:10px;align-items:flex-start;border-radius:var(--dz-r-cartao);padding:10px 12px;margin-bottom:8px;font-size:.88rem;line-height:1.4;"
        "background:var(--dz-cartao);border:1px solid var(--dz-borda);color:var(--dz-texto)}"
        ".dz-msg-sucesso{border-color:var(--dz-pos)}.dz-msg-sucesso .dz-ico{color:var(--dz-pos)}"
        ".dz-msg-erro{border-color:var(--dz-neg)}.dz-msg-erro .dz-ico{color:var(--dz-neg)}"
        ".dz-msg-aviso{border-color:#E0A526}.dz-msg-aviso .dz-ico{color:#E0A526}.dz-msg-info .dz-ico{color:var(--dz-destaque)}"
        ".dz-vazio{text-align:center;padding:28px 16px;color:var(--dz-apoio)}.dz-vazio-t{font-weight:700;color:var(--dz-texto);margin-top:8px}.dz-vazio-x{font-size:.85rem;margin-top:4px}"
        ".dz-bp-t{display:flex;justify-content:space-between;font-size:.78rem;color:var(--dz-apoio);margin-bottom:4px}"
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
        ".dz-posc-t{display:flex;justify-content:space-between;gap:10px;margin-bottom:8px}.dz-posc-n{font-weight:700;color:var(--dz-texto)}"
        ".dz-posc-c{font-size:.74rem;color:var(--dz-apoio)}.dz-posc-v{text-align:right;font-weight:800;color:var(--dz-texto);font-variant-numeric:tabular-nums}"
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
    livre = ":not([style*=\"border\"]):not([style*=\"background\"])"
    return (
        f"{p}{{background:radial-gradient(120% 45% at 50% -8%,color-mix(in srgb,var(--dz-destaque) 15%,transparent),transparent 62%),var(--dz-fundo) !important}}"
        f"{p} :is(.cartao,.card,.kpi,.mini,.ctx,.vazio,[data-testid=\"stMetric\"],[data-testid=\"stExpander\"],[data-testid=\"stForm\"]){livre}"
        "{background:var(--dz-cartao) !important;border:1px solid var(--dz-borda) !important;border-radius:var(--dz-r-cartao) !important;box-shadow:none !important}"
        f"{p} .pghead{{background:linear-gradient(135deg,color-mix(in srgb,var(--dz-destaque) 22%,var(--dz-cartao)),var(--dz-cartao)) !important;"
        "border:1px solid var(--dz-borda) !important;border-radius:var(--dz-r-painel) !important}"
        f"{p} :is([data-testid=\"stCaptionContainer\"],[data-testid=\"stCaptionContainer\"] p,small){{color:var(--dz-apoio) !important;opacity:1 !important}}"
        f"@media (max-width:{K.CELULAR_MAX}px){{{p} [data-testid=\"stAlert\"]{{padding:0 !important}}}}"
        f"{p} .stTabs [data-baseweb=\"tab\"]{{border-radius:999px !important}}"
        f"{p} .stTabs [data-baseweb=\"tab\"][aria-selected=\"true\"]{{background:var(--dz-destaque) !important;box-shadow:none !important}}"
        f"{p} .stTabs [data-baseweb=\"tab\"][aria-selected=\"true\"] :is(p,span,div){{color:var(--dz-sobre) !important;-webkit-text-fill-color:var(--dz-sobre) !important}}"
        f"{p} .stTabs [data-baseweb=\"tab-highlight\"]{{display:none !important}}"
        f"{p} .pgi{{background:color-mix(in srgb,var(--dz-destaque) 20%,transparent) !important;color:var(--dz-destaque) !important}}"
    )


def navegacao() -> str:
    """Atalho da conta no canto do cabeçalho e 'voltar' das sub-páginas, com cara de app."""
    return (
        ".stApp .st-key-topo_perfil{position:fixed;top:6px;left:64px;z-index:1000001;width:auto !important}"      # acima do cabeçalho do Streamlit (z-index ~1000000), ao lado do botão ☰
        ".stApp .st-key-topo_perfil a{display:flex;align-items:center;justify-content:center;min-width:36px;min-height:36px;padding:0 10px;gap:6px;border-radius:999px;"
        "background:var(--dz-cartao);border:1px solid var(--dz-borda);color:var(--dz-texto);text-decoration:none;font-size:.8rem;font-weight:600}"
        ".stApp .st-key-topo_perfil a:hover{border-color:var(--dz-destaque)}"
        f"@media (max-width:{K.CELULAR_MAX}px){{.stApp .st-key-topo_perfil a{{padding:0;width:36px}}.stApp .st-key-topo_perfil a p{{display:none}}}}"
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
    return "<style>@import url('" + K.FONTE_URL + "');\n" + "\n".join([variaveis(tema_id), barra_inferior(n_itens), cabecalho_compacto(), widgets(), legado(), navegacao(), componentes(), marca()]) + "</style>"
