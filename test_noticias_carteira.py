"""Cor dos cartões de notícia pelo efeito na carteira: lógica pura (noticias_eventos.efeito_carteira) e cartão HTML (noticias_app.card_html)."""
import sys

try:
    import streamlit  # noqa: F401
except ImportError:                                       # ambiente sem Streamlit: só a lógica e o HTML são exercitados
    from unittest.mock import MagicMock
    sys.modules["streamlit"] = MagicMock()

import noticias_app as APP
import noticias_eventos as N

ATIVOS = [
    {"id": "PETR4", "nome": "Petróleo Brasileiro S.A. - Petrobras", "classe": "acao", "setor": "Petróleo", "peso": 30},
    {"id": "MXRF11", "classe": "fii", "subgrupo": "papel", "peso": 20},
    {"id": "TESOURO PREFIXADO", "classe": "renda_fixa", "peso": 10},
    {"id": "VALE3", "nome": "Vale", "classe": "acao", "peso": 40},
    {"id": "BTC", "classe": "cripto", "peso": 0},          # favorito sem peso: fora da carteira
]


def _grupo(titulo, espec=False, nivel="veiculo", resumo=""):
    g = {"id": "g1", "titulo": titulo, "resumo": resumo, "n_fontes": 1, "melhor_fonte": nivel, "especulativo": espec, "categorias": [],
         "fonte": "Reuters", "fontes": ["Reuters"], "n_noticias": 1, "relevancia": 70, "status": "reportado por veículo reconhecido", "membros": []}
    g["sentimento"] = N.classificar_sentimento(titulo + " " + resumo, espec and nivel != "oficial")["sentimento"]
    g["sentimento_grupo"] = g["sentimento"]
    return g


def _ef(titulo, **kw):
    g = _grupo(titulo, **kw)
    g["efeito"] = N.efeito_carteira(g, N.analisar_impacto(g, ATIVOS), ATIVOS)
    return g


def test_alta_de_juros_pode_pressionar_a_carteira():
    e = _ef("Copom eleva a Selic em 0,50 ponto")["efeito"]
    assert e["classe"] == "desfavoravel" and e["cls"] == "bad" and e["score"] <= -N.LIMIAR_EFEITO
    assert {x["id"] for x in e["afetados"]} == {"VALE3", "PETR4", "MXRF11", "TESOURO PREFIXADO"}


def test_queda_de_juros_pode_favorecer_e_fii_de_papel_fica_misto():
    e = _ef("Copom corta a Selic em 0,50 ponto")["efeito"]
    assert e["classe"] == "favoravel" and e["cls"] == "good"
    assert next(x for x in e["afetados"] if x["id"] == "MXRF11")["sinal"] == "◆"


def test_mencao_direta_usa_o_tom_da_noticia():
    bom = _ef("Petrobras anuncia lucro recorde no trimestre")["efeito"]
    ruim = _ef("Petrobras sofre multa e queda de produção")["efeito"]
    assert bom["classe"] == "favoravel" and ruim["classe"] == "desfavoravel"
    assert [x["id"] for x in bom["afetados"]] == ["PETR4"]


def test_mencao_sem_tom_definido_fica_neutra():
    e = _ef("Petrobras divulga calendário de eventos")["efeito"]
    assert e["classe"] == "neutro" and "não indica" in e["motivo"]


def test_favorito_sem_peso_nao_conta():
    e = _ef("Bitcoin dispara e bate recorde")["efeito"]
    assert e["classe"] == "neutro" and e["afetados"] == []


def test_noticia_sem_relacao_com_a_carteira_e_neutra():
    e = _ef("Prefeitura anuncia obras na avenida central")["efeito"]
    assert e["classe"] == "neutro" and e["cls"] == "na" and "Nenhuma posição" in e["motivo"]


def test_especulativa_sem_fonte_oficial_e_incerta_mas_oficial_conta():
    e = _ef("Petrobras deve anunciar lucro recorde, segundo fontes", espec=True)["efeito"]
    assert e["classe"] == "incerto" and e["cls"] == "fair"
    e2 = _ef("Petrobras deve anunciar lucro recorde, segundo fontes", espec=True, nivel="oficial")["efeito"]
    assert e2["classe"] != "incerto"


def test_saldo_ponderado_pelo_peso_e_misto_quando_equilibrado():
    ativos = [{"id": "AAA3", "classe": "acao", "peso": 50}, {"id": "BBB3", "classe": "acao", "peso": 50}]
    g = _grupo("Notícia qualquer")
    imps = [{"ativos": [{"id": "AAA3", "direcao": N.B, "porque": "x"}, {"id": "BBB3", "direcao": N.P, "porque": "y"}]}]
    assert N.efeito_carteira(g, imps, ativos)["classe"] == "misto"
    ativos[0]["peso"], ativos[1]["peso"] = 90, 10
    assert N.efeito_carteira(g, imps, ativos)["classe"] == "favoravel"


def test_sinais_opostos_no_mesmo_ativo_viram_misto_e_sem_dados_nao_quebra():
    ativos = [{"id": "AAA3", "classe": "acao", "peso": 100}]
    g = _grupo("Notícia qualquer")
    imps = [{"ativos": [{"id": "AAA3", "direcao": N.B, "porque": "x"}]}, {"ativos": [{"id": "AAA3", "direcao": N.P, "porque": "y"}]}]
    assert N.efeito_carteira(g, imps, ativos)["afetados"][0]["sinal"] == "◆"
    assert N.efeito_carteira(g, [], [])["classe"] == "neutro" and N.efeito_carteira(g, None, None)["classe"] == "neutro"


def test_cartao_pinta_pelo_efeito_na_carteira_e_mostra_o_tom_a_parte():
    g = _ef("Petrobras sofre multa e queda de produção")
    h = APP.card_html(g, modo="carteira")
    assert 'class="nw bad' in h and "Pode pressionar sua carteira" in h and "Tom: ▼ Negativo" in h and "PETR4 ▼" in h and "nw-p" in h


def test_cartao_modo_tom_ignora_o_efeito():
    g = _ef("Petrobras anuncia lucro recorde no trimestre")
    g["sentimento_grupo"] = "negativo"                      # tom diferente do efeito: o modo "tom" tem que seguir o tom
    h = APP.card_html(g, modo="tom")
    assert 'class="nw bad' in h and "carteira" not in h.split("nw-top")[1].split("</div>")[0]


def test_cartao_sem_efeito_cai_no_tom_mesmo_no_modo_carteira():
    g = _grupo("Petrobras anuncia lucro recorde no trimestre")
    h = APP.card_html(g, modo="carteira")
    assert 'class="nw good' in h and "▲ Positivo" in h


def test_cartao_escapa_html_do_motivo_e_do_id():
    g = _grupo("Titulo")
    g["efeito"] = {"classe": "desfavoravel", "cls": "bad", "rotulo": "▼ Pode pressionar sua carteira", "score": -1, "peso_afetado": 10, "motivo": "<b>x</b>",
                   "afetados": [{"id": "<img>", "sinal": "▼", "cls": "bad", "peso": 10, "porque": "<script>y</script>"}]}
    h = APP.card_html(g, modo="carteira")
    assert "<script>" not in h and "<img>" not in h and "&lt;script&gt;" in h


def test_modo_cor_sem_carteira_e_sempre_tom():
    assert APP.modo_cor({"ativos": [{"id": "BTC", "peso": 0}]}) == "tom"
    assert APP.modo_cor({"ativos": []}) == "tom"
    assert "Tom positivo" in APP.legenda_cor_html("tom") and "favorecer" in APP.legenda_cor_html("carteira")
