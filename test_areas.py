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
    sem_lugar = {p for p in _url_paths_do_app() if A.area_da_pagina(p) is None and p not in A.SEMPRE and p not in A.FORA_DO_APP}
    assert sem_lugar == set()


def test_areas_so_listam_paginas_que_existem():
    existentes = _url_paths_do_app()
    inventadas = {p for a in A.AREAS for p in a["paginas"]} - existentes
    assert inventadas == set()


def test_paginas_da_area_e_area_da_pagina():
    assert A.ids() == ["aprender", "analisar", "wallet"]                # só três áreas
    assert A.paginas_da_area("wallet") == ["competicao"]
    assert A.paginas_da_area("aprender") == ["jornada", "missoes", "educacao", "glossario"]
    assert "carteira" in A.paginas_da_area("analisar")             # Carteira fica dentro de Analisar
    assert A.area_da_pagina("fiis") == "analisar" and A.area_da_pagina("macro") == "analisar"
    assert all(A.area_da_pagina(p) is None for p in A.FORA_DO_APP)                # ferramentas complexas fora do app
    assert A.area_da_pagina("educacao") == "aprender" and A.area_da_pagina("missoes") == "aprender"
    assert A.area_da_pagina("competicao") == "wallet"
    assert A.area_da_pagina("inicio") is None and A.area_da_pagina("ajuda") is None
    assert A.paginas_da_area("nao-existe") == []


def test_paginas_visiveis_inclui_sempre():
    v = A.paginas_visiveis("wallet")
    assert v == list(A.SEMPRE) + ["competicao"]
    assert "fiis" not in v and "educacao" not in v


def test_area_ativa_nao_troca_em_paginas_fora_das_areas():
    assert A.area_ativa("fiis", "aprender") == "analisar"
    assert A.area_ativa("inicio", "wallet") == "wallet"
    assert A.area_ativa("ajuda", None) == A.area_padrao()
    assert A.area_ativa("conta", "area-que-nao-existe") == A.area_padrao()
    assert A.area_ativa("inicio", "ativos") == A.area_padrao()          # id de uma versão intermediária guardado numa sessão aberta


def test_lembrar_nao_altera_a_original_e_ignora_paginas_fora():
    original = {"analisar": "fiis"}
    nova = A.lembrar(original, "etfs")
    assert original == {"analisar": "fiis"} and nova == {"analisar": "etfs"}
    assert A.lembrar(original, "inicio") == original


def test_memoria_antiga_invalida_volta_ao_padrao():
    assert A.ultima_pagina("aprender", {"aprender": "pagina-removida"}) == "jornada"


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


def test_inicio_nao_repete_os_botoes_da_barra():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    i = texto.index("def pagina_inicio():")
    corpo = texto[i:texto.index("\ndef ", i + 10)]
    assert "_cartoes_das_areas" not in corpo and "def _cartoes_das_areas" not in texto
    assert "def _abrir_area(" in texto


def test_jornada_e_glossario_sao_paginas_do_menu():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert 'url_path="jornada"' in texto and 'url_path="glossario"' in texto
    assert A.area_da_pagina("jornada") == "aprender" and A.area_da_pagina("glossario") == "aprender"
    assert A.ultima_pagina("aprender", None) == "jornada"          # a Jornada abre primeiro


def test_tela_analisar_tem_cartoes_validos():
    assert A.problemas() == []                                       # todo link dos cartões está na própria área
    app = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert set(A.HUBS) == {"analisar"} and A.pagina_inicial("analisar") in _url_paths_do_app()
    urls = [u for c in A.HUBS["analisar"]["cartoes"] for u, _ in c["paginas"]]
    assert len(urls) == len(set(urls))                               # nenhuma página repetida entre cartões
    assert {"preco-justo", "fiis", "renda-fixa", "criptomoedas", "carteira"} <= set(urls)
    assert 'url_path="analisar"' in app


def test_trilha_das_paginas():
    assert A.trilha("preco-justo")[0]["nome"] == "Analisar" and A.trilha("preco-justo")[1] == "analisar"
    assert A.trilha("analisar") is None and A.trilha("inicio") is None and A.trilha("ajuda") is None
    assert A.trilha("glossario")[1] == "jornada"                   # Aprender: raiz é a primeira página
    assert A.trilha("wallet") is None                               # já é a raiz de Jogar
    assert A.trilha("carteira")[1] == "analisar"


def test_memoria_das_areas_e_gravada_no_perfil_e_limpa():
    assert "areas_mem" in (RAIZ / "usuarios.py").read_text(encoding="utf-8").split("PREFIXOS")[0]    # entra em usuarios.CHAVES
    suja = {"ativos": "fiis", "analisar": "pagina-removida", "aprender": "glossario", "wallet": "competicao", 7: "x"}
    assert A.limpar(suja) == {"aprender": "glossario", "wallet": "competicao"}   # área antiga e página inválida saem
    assert A.limpar({"analisar": "analisar"}) == {}                             # a tela-raiz não é "última página"
    assert A.limpar(None) == {} and A.limpar("texto") == {}
    assert A.lembrar(suja, "macro") == {"aprender": "glossario", "wallet": "competicao", "analisar": "macro"}
