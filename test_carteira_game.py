"""Carteira no formato mobile game (carteira_game): abas por categoria, ordenação e cartões dos ativos."""
import carteira_game as CG

POS = [{"tk": "PETR4", "classe": "acao", "q": 100, "valor": 3890.0, "res": 7.8, "peso": 10.0},
       {"tk": "CRIPTO:BTC", "classe": "cripto", "q": 0.015, "valor": 5280.0, "res": -2.1, "peso": 14.0},
       {"tk": "MXRF11", "classe": "fii", "q": 300, "valor": 2985.0, "res": 1.5, "peso": 8.0}]


def test_contar_e_filtrar_por_categoria():
    n = CG.contar(POS)
    assert n["todos"] == 3 and n["acao"] == 1 and n["cripto"] == 1 and n["fii"] == 1 and n["etf"] == 0
    assert [r["tk"] for r in CG.filtrar(POS, "cripto")] == ["CRIPTO:BTC"]
    assert len(CG.filtrar(POS, "todos")) == 3


def test_ordenar():
    assert [r["tk"] for r in CG.ordenar(POS, "Maior valor")] == ["CRIPTO:BTC", "PETR4", "MXRF11"]
    assert [r["tk"] for r in CG.ordenar(POS, "Melhor resultado")][0] == "PETR4"
    assert [r["tk"] for r in CG.ordenar(POS, "Pior resultado")][0] == "CRIPTO:BTC"


def test_cartao_mostra_dados_reais_e_peso():
    h = CG.html_cartao(POS[0], "x.webp")
    assert "PETR4" in h and "Petrobras" in h and "100 ações" in h and "+7,80%" in h and "width:10%" in h and "x.webp" in h
    h2 = CG.html_cartao(POS[1])
    assert "−2,10%" in h2 and "cg-p d" in h2


def test_cabecalho_sem_historico_nao_inventa_variacao():
    h = CG.html_cab(100056.0, None, 0)
    assert "após o 1º fechamento" in h and "Monte sua carteira" in h
    assert "▲" in CG.html_cab(1000.0, 1.25, 2)


def test_vazio_por_categoria():
    assert "Nenhum ativo ainda" in CG.html_vazio("todos")
    assert "Você ainda não tem ETFs" in CG.html_vazio("etf")
