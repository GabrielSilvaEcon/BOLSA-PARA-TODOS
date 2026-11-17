"""Central de Jogos: placar por conta, rankings por jogo, idempotência, anti-manipulação e ligas de amigos (sem rede e sem Streamlit)."""
import json

import pytest

import competicao_ligas as L
import jogos as J


def _linhas(*docs):
    return [{"email": e, "dados": d} for e, d in docs]


# ------------------------------------------------------------------ registro de partidas
def test_trade_soma_uma_vez_por_partida_e_guarda_historico():
    d, m = J.registrar_trade({}, "p1", 42.5, 3, "rapida", 1, 3, "2026-11-17 10:00", apelido="Ana")
    assert m and d["apelido"] == "Ana" and d["trade"]["pts"] == 42.5 and d["trade"]["partidas"] == 1 and d["trade"]["vitorias"] == 1
    d2, m2 = J.registrar_trade(d, "p1", 42.5, 3, "rapida", 1, 3, "2026-11-17 10:00")
    assert not m2 and d2["trade"]["pts"] == 42.5 and d2["trade"]["partidas"] == 1          # atualizar a página não soma de novo
    d3, _ = J.registrar_trade(d2, "p2", -10, 3, "rapida", None, 1, "2026-11-17 11:00")
    assert d3["trade"]["pts"] == 32.5 and d3["trade"]["partidas"] == 2 and d3["trade"]["vitorias"] == 1   # partida solo não conta vitória
    assert [h["id"] for h in d3["trade"]["hist"]] == ["p2", "p1"] and d3["trade"]["melhor"] == 42.5


def test_trade_limita_pontos_ao_teto_do_formato():
    d, _ = J.registrar_trade({}, "p1", 99999, 3, "rapida", None, 1, "x")
    assert d["trade"]["pts"] == 300.0                                                        # 3 rodadas × 100 pontos no máximo
    d, _ = J.registrar_trade({}, "p2", float("nan"), 3, "rapida", None, 1, "x")
    assert d["trade"]["pts"] == 0.0


def test_ticker_conta_vitorias_empates_derrotas_uma_vez_por_duelo():
    d = {}
    for did, r in (("a", "vitoria"), ("b", "derrota"), ("c", "empate"), ("a", "vitoria"), ("d", "invalido")):
        d, _ = J.registrar_ticker(d, did, r, "sistema", "2026-11-17 10:00")
    k = J.sanear(d)["ticker"]
    assert (k["v"], k["e"], k["d"]) == (1, 1, 1) and len(k["ids"]) == 3


def test_documento_adulterado_nao_distorce_o_ranking():
    falso = {"apelido": "<b>x</b>" * 10, "trade": {"pts": 1e12, "partidas": 1, "vitorias": 50}, "ticker": {"v": "muitas"}}
    d = J.sanear(falso)
    assert d["trade"]["pts"] == 1000.0 and d["trade"]["vitorias"] == 1 and d["ticker"]["v"] == 0 and len(d["apelido"]) <= 20


# ------------------------------------------------------------------ rankings
def test_ranking_separado_por_jogo_ordenado_e_sem_email():
    a, _ = J.registrar_trade({}, "1", 50, 3, "rapida", None, 1, "x", apelido="Ana")
    b, _ = J.registrar_trade({}, "2", 80, 3, "rapida", None, 1, "x", apelido="Bia")
    c, _ = J.registrar_ticker({}, "d1", "vitoria", "online", "x", apelido="Caio")
    linhas = _linhas(("a@x.com", a), ("b@x.com", b), ("c@x.com", c))
    rt = J.montar_ranking(J.TRADE, linhas, "a@x.com")
    assert [x["apelido"] for x in rt["linhas"]] == ["Bia", "Ana"] and rt["eu"]["pos"] == 2 and rt["total"] == 2   # Caio não jogou Trade
    rk = J.montar_ranking(J.TICKER, linhas, "a@x.com")
    assert [x["apelido"] for x in rk["linhas"]] == ["Caio"] and rk["eu"] is None
    assert "@" not in json.dumps(rt) + json.dumps(rk)


def test_variacao_de_posicao_desde_o_inicio_do_dia():
    a, _ = J.registrar_trade({}, "1", 10, 3, "rapida", None, 1, "x", apelido="Ana")
    b, _ = J.registrar_trade({}, "2", 20, 3, "rapida", None, 1, "x", apelido="Bia")
    linhas = _linhas(("a@x.com", a), ("b@x.com", b))
    r0 = J.montar_ranking(J.TRADE, linhas)
    base, novo = J.base_do_dia(None, "2026-11-17", r0)
    assert novo and novo["dia"] == "2026-11-17"
    a2, _ = J.registrar_trade(a, "3", 50, 3, "rapida", None, 1, "x")                          # Ana passa a Bia
    r1 = J.montar_ranking(J.TRADE, _linhas(("a@x.com", a2), ("b@x.com", b)), "a@x.com", J.base_do_dia(novo, "2026-11-17", r0)[0])
    assert r1["eu"]["pos"] == 1 and r1["eu"]["var"] == 1 and r1["linhas"][1]["var"] == -1
    assert J.base_do_dia(novo, "2026-11-18", r1)[1]["dia"] == "2026-11-18"                    # dia novo: nova base


def test_ranking_entre_amigos_e_campeoes_desligado():
    a, _ = J.registrar_trade({}, "1", 10, 3, "rapida", None, 1, "x", apelido="Ana")
    b, _ = J.registrar_trade({}, "2", 20, 3, "rapida", None, 1, "x", apelido="Bia")
    r = J.ranking_entre(J.TRADE, _linhas(("a@x.com", a), ("b@x.com", b)), {"a@x.com"}, "a@x.com")
    assert r["total"] == 1 and r["eu"]["pos"] == 1
    assert J.ranking_campeoes() is None                                                      # sem fórmula arbitrária


def test_jogo_desconhecido_e_recusado():
    with pytest.raises(ValueError):
        J.montar_ranking("xadrez", [])


# ------------------------------------------------------------------ ligas de amigos (sistema existente)
def test_liga_nome_codigo_e_convite():
    assert L.nome_valido("Turma da faculdade")[0] and not L.nome_valido("ab")[0] and not L.nome_valido("admin oficial")[0]
    d = L.nova_definicao("  Turma   da faculdade ", 999)
    assert d["nome"] == "Turma da faculdade" and d["max"] == L.MAX_MEMBROS_TETO
    assert L.formatar_codigo("ABCD2345") == "ABCD-2345" and L.codigo_valido("abcd-2345") == "ABCD2345"
    link = L.link_convite("https://app.exemplo", "ABCD2345")
    assert link == "https://app.exemplo/jogos-amigos?liga=ABCD2345" and L.extrair_convite(link) == "ABCD2345"


# ------------------------------------------------------------------ banco (SQLite temporário): placar e ligas
def test_banco_placar_e_ligas_de_amigos():
    import banco
    from datetime import date
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        for e in ("a@x.com", "b@x.com"):
            banco._inserir("contas", {"id": "id-" + e, "email": e, "nome": e, "criado_em": "2026-01-01T00:00:00Z"})
        A, B = (banco.Ator(id="id-" + e, email=e, papel="usuario") for e in ("a@x.com", "b@x.com"))
        d, _ = J.registrar_trade(banco.jogos_placar_ler(A), "p1", 30, 3, "rapida", None, 1, "x", apelido="Ana")
        banco.jogos_placar_gravar(A, d)
        todos = banco.sis_comp_todos(J.CH_PLACAR)                                     # uma consulta para todos
        assert len(todos) == 1 and J.sanear(todos[0]["dados"])["trade"]["pts"] == 30
        with pytest.raises(banco.SemPermissao):
            banco.jogos_placar_gravar(None, d)                                      # sem conta não grava
        cod = banco.comp_liga_criar(A, L.nova_definicao("Turma da faculdade", 10))
        banco.comp_ligas_gravar(A, L.adicionar({}, cod, date(2026, 11, 17), dono=True))
        banco.comp_ligas_gravar(B, L.adicionar({}, cod, date(2026, 11, 17)))
        assert banco.comp_liga_definicao(B, cod)["nome"] == "Turma da faculdade" and banco.comp_liga_contagem(A, cod) == 2
        with pytest.raises(banco.SemPermissao):
            banco.comp_liga_encerrar(B, cod)                                         # só quem criou encerra
        assert banco.comp_liga_encerrar(A, cod) and banco.comp_liga_definicao(A, cod) is None
