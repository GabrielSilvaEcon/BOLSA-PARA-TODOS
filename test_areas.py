import re
from pathlib import Path

import areas as A

RAIZ = Path(__file__).parent


def _url_paths_do_app():
    """url_paths registrados no app.py (lidos do texto, sem importar o Streamlit)."""
    return set(re.findall(r'url_path="([a-z0-9-]+)"', (RAIZ / "app.py").read_text(encoding="utf-8")))


def test_lista_valida():
    assert A.problemas() == []
    assert 3 <= len(A.AREAS) <= A.MAX_AREAS


def test_toda_pagina_do_app_tem_lugar():
    # nenhuma página pode ficar sem área nem fora de SEMPRE (senão sumiria do menu)
    sem_lugar = {p for p in _url_paths_do_app() if A.area_da_pagina(p) is None and p not in A.SEMPRE}
    assert sem_lugar == set()


def test_areas_so_listam_paginas_que_existem():
    existentes = _url_paths_do_app()
    inventadas = {p for a in A.AREAS for p in a["paginas"]} - existentes
    assert inventadas == set()


def test_paginas_da_area_e_area_da_pagina():
    assert A.paginas_da_area("jogar") == ["competicao"]
    assert A.paginas_da_area("aprender") == ["jornada", "educacao", "glossario"]
    assert A.paginas_da_area("analisar")[0] == "carteira"          # Carteira é a primeira página de Analisar
    assert A.area_da_pagina("fiis") == "analisar"
    assert A.area_da_pagina("educacao") == "aprender"
    assert A.area_da_pagina("competicao") == "jogar"
    assert A.area_da_pagina("inicio") is None and A.area_da_pagina("ajuda") is None
    assert A.paginas_da_area("nao-existe") == []


def test_paginas_visiveis_inclui_sempre():
    v = A.paginas_visiveis("jogar")
    assert v == list(A.SEMPRE) + ["competicao"]
    assert "fiis" not in v and "educacao" not in v


def test_area_ativa_nao_troca_em_paginas_fora_das_areas():
    assert A.area_ativa("fiis", "aprender") == "analisar"
    assert A.area_ativa("inicio", "jogar") == "jogar"
    assert A.area_ativa("ajuda", None) == A.area_padrao()
    assert A.area_ativa("conta", "area-que-nao-existe") == A.area_padrao()


def test_ultima_pagina_lembrada():
    mem = A.lembrar({}, "fiis")
    mem = A.lembrar(mem, "educacao")
    assert A.ultima_pagina("analisar", mem) == "fiis"
    assert A.ultima_pagina("aprender", mem) == "educacao"
    assert A.ultima_pagina("jogar", mem) == "competicao"            # sem memória: página padrão
    assert A.ultima_pagina("jogar", None) == "competicao"
    assert A.ultima_pagina("nao-existe", mem) == ""


def test_lembrar_nao_altera_a_original_e_ignora_paginas_fora():
    original = {"analisar": "fiis"}
    nova = A.lembrar(original, "etfs")
    assert original == {"analisar": "fiis"} and nova == {"analisar": "etfs"}
    assert A.lembrar(original, "inicio") == original


def test_memoria_antiga_invalida_volta_ao_padrao():
    assert A.ultima_pagina("analisar", {"analisar": "pagina-removida"}) == "carteira"


def test_problemas_detecta_erros(monkeypatch=None):
    salvo = list(A.AREAS)
    try:
        A.AREAS[:] = salvo + [{"id": "x", "nome": "X", "icone": "", "paginas": ["fiis", "inicio"]}]
        txt = " ".join(A.problemas())
        assert "fiis" in txt and "inicio" in txt
        A.AREAS[:] = salvo + [{"id": f"x{i}", "nome": "X", "icone": "", "paginas": [f"p{i}"]} for i in range(3)]
        assert any("máximo" in p for p in A.problemas())
    finally:
        A.AREAS[:] = salvo
    assert A.problemas() == []


def test_app_tem_a_chave_e_o_filtro():
    # o menu lê areas.py e só filtra quando AREAS_ATIVAS é True; para desfazer a A2b, basta pôr False
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert re.search(r"^AREAS_ATIVAS = (True|False)\b", texto, re.M)
    assert "import areas\n" in texto and "def _visivel(" in texto
    assert "_seletor_de_areas" in texto and "areas.lembrar(" in texto


def test_seletor_fica_no_topo_e_nao_no_menu_lateral():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert texto.count("_seletor_de_areas()") == 2          # definição + uma chamada
    chamada = texto.index("    _seletor_de_areas()  ")      # a chamada no topo da tela
    assert texto.index("\nmenu_navegacao()") < chamada < texto.index("\n    pg.run()")


def test_barra_do_rodape_tem_chave_propria():
    # plano B da A4: BARRA_RODAPE = False deixa os botões só no topo
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert re.search(r"^BARRA_RODAPE = (True|False)\b", texto, re.M)
    assert "_CSS_AREAS_RODAPE if BARRA_RODAPE else" in texto
    assert "position:fixed" in texto[texto.index("_CSS_AREAS_RODAPE = ("):texto.index("def _visivel(")]


def test_cada_area_tem_descricao_para_o_cartao():
    assert all(a.get("descricao") for a in A.AREAS)


def test_inicio_mostra_cartoes_das_areas():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    i = texto.index("def pagina_inicio():")
    corpo = texto[i:texto.index("\ndef ", i + 10)]
    assert "if AREAS_ATIVAS:\n        _cartoes_das_areas()" in corpo
    assert corpo.index("experiencia_app.inicio()") < corpo.index("_cartoes_das_areas()")   # depois da escolha de nível
    assert "def _abrir_area(" in texto and "PG_CART" in texto[texto.index("def _cartoes_das_areas"):texto.index("def _seletor_de_areas")]


def test_jornada_e_glossario_sao_paginas_do_menu():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert 'url_path="jornada"' in texto and 'url_path="glossario"' in texto
    assert A.area_da_pagina("jornada") == "aprender" and A.area_da_pagina("glossario") == "aprender"
    assert A.ultima_pagina("aprender", None) == "jornada"          # a Jornada abre primeiro


def test_paginas_finas_so_reaproveitam_as_abas():
    edu = (RAIZ / "educacao_app.py").read_text(encoding="utf-8")
    assert "jornada_app.aba(prog, _set, _estudo_unidade)" in edu and "_aba_glossario()" in edu
    assert edu.count("jornada_app.aba(prog, _set, _estudo_unidade)") == 2   # aba antiga + página nova (nada removido)
