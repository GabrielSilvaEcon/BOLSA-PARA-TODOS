"""Layout compacto para smartphones: garante que a camada só mexe em espaço, só em telas pequenas e em nenhum elemento de navegação."""
import re
from pathlib import Path

import layout_mobile as LM

RAIZ = Path(__file__).parent

PERMITIDAS = {"padding", "padding-top", "padding-bottom", "padding-left", "padding-right",
              "margin", "margin-top", "margin-bottom", "margin-left", "margin-right",
              "gap", "row-gap", "column-gap", "min-height"}


def _regras():
    """[(seletor, {propriedade: valor})] de dentro do @media, sem comentários."""
    txt = re.sub(r"/\*.*?\*/", "", LM.css(), flags=re.S)
    txt = re.sub(r"</?style>", "", txt).strip()
    m = re.fullmatch(r"@media \(max-width:(\d+)px\)\{(.*)\}", txt, flags=re.S)
    assert m, "todo o CSS precisa estar dentro de um único @media (max-width)"
    assert int(m.group(1)) == LM.LARGURA_MAX <= 640
    out = []
    for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", m.group(2)):
        decl = {}
        for d in corpo.split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decl[k.strip()] = v.strip()
        out.append((" ".join(sel.split()), decl))
    return out


def test_chaves_equilibradas_e_media_unico():
    css = LM.css()
    assert css.count("{") == css.count("}")
    assert css.count("@media") == 1


def test_so_mexe_em_espaco():
    for sel, decl in _regras():
        for prop in decl:
            if prop.startswith("--m-"):
                continue                                           # variáveis de ajuste da própria camada
            if prop == "display":
                assert decl[prop] == "none" and ("style:only-child" in sel or ":empty" in sel), sel   # só o item fantasma
                continue
            assert prop in PERMITIDAS, f"{prop} não é de espaçamento ({sel})"


def test_identidade_visual_intocada():
    css = LM.css().lower()
    for proibido in ("color", "background", "gradient", "font", "border", "radius", "shadow", "filter", "transform", "opacity", "content:",
                     "line-height", "letter-spacing", "width", "height:"):
        assert proibido not in css.replace("min-height", "").replace("max-width", "").replace("padding-", "p-"), proibido


def test_nao_mexe_na_navegacao_nem_no_menu_lateral():
    css = LM.css()
    for alvo in ("stSidebar", "barra_areas", "nav_", "st-key-nav", "stPageLink", "stButton", "stTabs"):
        assert alvo not in css, alvo


def test_item_fantasma_so_pega_markdown_que_tem_apenas_style():
    fantasma = [(s, d) for s, d in _regras() if d.get("display") == "none"]
    assert len(fantasma) == 1
    sel = fantasma[0][0]
    assert sel.count("style:only-child") == 2 and ":empty" in sel          # nenhum markdown com texto ou HTML visível entra aqui


def test_seletores_globais_tem_especificidade_zero():
    sels = [s for s, _ in _regras()]
    assert any(s.startswith(":where([data-testid=\"stMain\"]) [data-testid=\"stVerticalBlock\"]") for s in sels)
    assert any(s.startswith(":where([data-testid=\"stMain\"]) [data-testid=\"stHorizontalBlock\"]") for s in sels)


def test_valores_nao_viram_aperto_demais():
    # conforto de toque e leitura: nenhum min-height abaixo de 44 px, nenhum gap abaixo de 8 px
    for sel, decl in _regras():
        if "min-height" in decl:
            assert int(re.sub(r"\D", "", decl["min-height"])) >= 44, sel
    css = LM.css()
    assert "--m-gap:.6rem" in css and "--m-pad:12px" in css and "--m-sec:12px" in css


def test_app_liga_a_camada_por_ultimo_e_com_chave():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert re.search(r"^LAYOUT_COMPACTO = (True|False)\b", texto, re.M)
    assert "import layout_mobile" in texto
    ini = texto.index("if LAYOUT_COMPACTO:\n    st.markdown(layout_mobile.css()")
    assert texto.index("    _seletor_de_areas()  ") < ini < texto.index("if not acesso_liberado(pg.url_path):")     # antes de qualquer página, depois dos CSS globais
    assert texto.count("layout_mobile.css()") == 1                                                                  # injetado uma vez por execução


def test_desktop_e_tablet_ficam_como_estao():
    # nenhuma regra fora do @media: acima de 640 px nada muda
    assert re.sub(r"\s", "", LM.css()).startswith("<style>/*layoutcompactoparasmartphones*/@media(max-width:640px){")
