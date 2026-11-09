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
    b = ".stApp .st-key-barra_areas"
    base = (
        f"{b} [data-testid=\"stHorizontalBlock\"]{{display:grid !important;grid-template-columns:repeat({n_itens},minmax(0,1fr)) !important;gap:2px !important;width:100% !important}}"
        f"{b} [data-testid=\"stColumn\"]{{width:auto !important;min-width:0 !important;flex:none !important}}"
        f"{b} .stButton > button{{min-height:var(--dz-toque) !important;width:100%;padding:6px 2px !important;border-radius:var(--dz-r-painel) !important;"
        "box-shadow:none !important;backdrop-filter:none !important;transform:none !important;background:transparent !important;border:0 !important;"
        "transition:background var(--dz-ms) ease,color var(--dz-ms) ease}"
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
        "@media (prefers-reduced-motion:reduce){.dz-skel i{animation:none}.stApp *{transition:none !important}}"
    )


def css(tema_id: str, n_itens: int) -> str:
    """CSS completo da v2 (uma tag <style>, sem linhas em branco, para o st.markdown não quebrar o bloco)."""
    return "<style>@import url('" + K.FONTE_URL + "');\n" + "\n".join([variaveis(tema_id), barra_inferior(n_itens), cabecalho_compacto(), componentes()]) + "</style>"
