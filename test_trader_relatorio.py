"""Relatório do fim da partida corrida (pop-up sem rolagem): conteúdo das três abas."""
import trader_relatorio as TR

RES = {"pontos": -5.3, "qualidade_nota": 18.0,
       "fin": {"pnl": 223.58, "pct_aposta": 2.236},
       "relatorio": {"n_ops": 4, "acertos": 3, "erros": 1, "taxa_acerto": 75.0, "ganho_medio": 139.49, "perda_media": -194.88, "payoff": 0.72,
                     "maior_queda": 228.11, "maior_queda_pct": 2.28, "com_stop": 0, "taxas": 15.92},
       "operacoes": [{"n": i, "direcao": "alta", "q": 100, "entrada": 10.0, "saida": 10.5, "motivo": "manual", "pnl": 50.0} for i in range(1, 10)]}


def test_resumo_traz_ativo_revelado_resultados_e_estatisticas():
    h = TR.html_resumo(RES, {"ticker": "PETR4", "tf_nome": "1 hora", "de": "24/04/2024", "ate": "07/05/2024"}, "⭐ +15 XP")
    for txt in ("PETR4", "+T$ 223,58", "+2,24%", "−5,3", "18/100", "75%", "0,72", "−T$ 228,11 (2,28%)", "0 de 4", "+15 XP"):
        assert txt in h, txt


def test_operacoes_mostra_no_maximo_7_e_avisa_o_resto():
    h = TR.html_operacoes(RES)
    assert h.count("class='rr-op'") == TR.OPS_MAX and "+2 operações" in h
    assert "não operou" in TR.html_operacoes({"operacoes": []})


def test_raiox_sem_as_linhas_de_cada_operacao():
    h = TR.html_raiox([("Sua leitura", "a"), ("Operação 1", "b"), ("Pontos", "c")])
    assert "Operação 1" not in h and "Pontos" in h
