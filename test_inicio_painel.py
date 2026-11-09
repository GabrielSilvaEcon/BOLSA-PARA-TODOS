"""Testes do painel do Início (sem rede, sem Streamlit)."""
import inicio_painel as IP
import areas


def test_formatacao():
    assert IP._num(1234567.891, 2) == "1.234.567,89"
    assert IP.fmt_var(1.234) == "+1,23%" and IP.fmt_var(-0.5) == "-0,50%" and IP.fmt_var(None) == "n/d"
    assert IP.classe_var(0.0) == "up" and IP.classe_var(-1) == "dn" and IP.classe_var(None) == "na"


def test_blocos_sem_dados_somem():
    assert IP.html_mercado([]) == "" and IP.html_ativos([]) == ""


def test_html_escapa_texto():
    h = IP.html_ativos([{"codigo": "<b>X</b>", "nome": "A&B", "preco": "R$ 1,00", "var": 1.0}])
    assert "<b>X</b>" not in h and "A&amp;B" in h


def test_mercado_hoje_usa_o_que_respondeu(monkeypatch):
    monkeypatch.setattr(IP, "cotacoes", lambda s: {"^BVSP": (130000.0, 0.5), "BTC-USD": (60000.0, -2.0)})
    monkeypatch.setattr(IP, "selic_atual", lambda: 10.5)
    itens = IP.mercado_hoje()
    assert [i["rotulo"] for i in itens] == ["Ibovespa", "Bitcoin", "Selic (meta)"]
    assert itens[0]["valor"] == "130.000" and itens[2]["valor"] == "10,50% a.a."


def test_aprender_barra():
    h = IP.html_aprender("Lição", "Unidade", 3, 12, 1, 40)
    assert "width:25%" in h and "1 dia seguido" in h and "3 de 12 lições" in h


def test_atalhos_apontam_para_paginas_da_area_analisar():
    na_area = set(areas.paginas_da_area("analisar"))
    assert all(url in na_area for _, _, url, _, _ in IP.ATALHOS)
