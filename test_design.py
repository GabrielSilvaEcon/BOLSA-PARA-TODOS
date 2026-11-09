"""Design system v2 (Etapa 2): tokens, contraste das paletas, CSS gerado e ligação com o app. Roda sem Streamlit."""
import json
import re
from pathlib import Path

import areas as A
import paleta as P
from design import componentes as C, css as D, temas as T, tokens as K

RAIZ = Path(__file__).parent


def test_tokens_validos():
    assert K.TOQUE_MIN >= 48 and K.CABECALHO_ALTURA >= 44 and K.BARRA_ALTURA >= 56
    assert list(K.TEXTO.values()) == sorted(K.TEXTO.values())
    assert json.loads(K.como_json())["toque_min"] == K.TOQUE_MIN


def test_paletas_passam_no_contraste():
    for tid in T.TEMAS:
        for a, b, minimo in T.pares_de_contraste(tid):
            assert P.contraste(a, b) >= minimo, (tid, a, b)
    for cor in T.DESTAQUE_NA_CONCHA.values():
        assert P.contraste(cor, T.CONCHA["fundo"]) >= 4.5
    assert P.contraste(T.CONCHA["inativo"], T.CONCHA["fundo"]) >= 4.5


def test_tres_temas_e_cada_area_tem_o_seu():
    assert set(T.TEMAS) == {"aprender", "analise", "wallet"}
    for a in A.AREAS:
        assert T.tema_da_area(a["id"]) in T.TEMAS
    assert T.tema_da_pagina("competicao", A.area_da_pagina) == "wallet"
    assert T.tema_da_pagina("jornada", A.area_da_pagina) == "aprender"
    assert T.tema_da_pagina("preco-justo", A.area_da_pagina) == "analise"
    assert T.tema_da_pagina("inicio", A.area_da_pagina) == "analise"      # sem área
    assert T.tema_da_pagina("pagina-que-nao-existe", A.area_da_pagina) == "analise"


def test_css_bem_formado():
    for tid in T.TEMAS:
        s = D.css(tid, len(A.AREAS) + 1)
        assert s.startswith("<style>") and s.endswith("</style>") and s.count("<style>") == 1
        assert s.count("{") == s.count("}") and s.count("(") == s.count(")")
        assert "\n\n" not in s                                           # linha em branco quebraria o bloco HTML do markdown
        assert "safe-area-inset-bottom" in s and "prefers-reduced-motion" in s
        assert f"repeat({len(A.AREAS) + 1}," in s
        assert T.TEMAS[tid]["destaque"] in s


def test_css_so_mexe_no_que_a_etapa_2_promete():
    s = D.css("analise", 4)
    assert "stSidebar" not in s and "stMain\"] {" not in s
    assert not re.search(r"\.stApp\{[^}]*background", s)                 # não troca o fundo das páginas (Etapas 3 a 5)


def test_componentes_escapam_e_nao_inventam_numero():
    h = C.indicador("<b>x</b>", "1", 2.5)
    assert "<b>x</b>" not in h and "&lt;b&gt;" in h and "dz-pos" in h
    assert "dz-neg" in C.indicador("a", "b", -0.1) and "dz-var" not in C.indicador("a", "b", None)
    assert C.numero_br(None) == "indisponível" and C.numero_br(True) == "indisponível"
    assert C.numero_br(1234.5, 2) == "1.234,50" and C.numero_br(1.5, 1, sinal=True) == "+1,5"
    assert C.skeleton(3).count("<i ") == 3 and C.skeleton(99).count("<i ") == 8


def test_app_liga_a_v2_por_chave():
    src = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert "DESIGN_V2 = True" in src and "design_css.css(" in src
    assert "if not DESIGN_V2:" in src                                    # com a chave desligada o CSS antigo da barra volta
