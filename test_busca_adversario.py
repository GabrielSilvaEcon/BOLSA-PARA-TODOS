"""Trade Battle online: não há criar sala nem código. Quem procura adversário (mesma duração, ao mesmo tempo) se encontra e a partida começa na hora."""
import pytest

import trader_dados as TD
import trader_online_dados as OL
from test_social_api import dois  # noqa: F401  (duas contas)
from test_trader_mesa import EMAILS, TS, _contas, banco_isolado, livro


@pytest.fixture
def mundo(monkeypatch):
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    with banco_isolado():
        _contas()
        with livro(pat=300_000.0, caixa=200_000.0):
            yield EMAILS


def test_duas_buscas_da_mesma_duracao_se_encontram_e_a_partida_comeca_na_hora(mundo):
    a, b = mundo[0], mundo[1]
    r1 = OL.buscar(a, "rapida", TS)
    assert r1["estado"] == "fila"
    r2 = OL.buscar(b, "rapida", TS + 1)
    assert r2["estado"] == "partida" and r2["id"] == r1["id"]
    d = OL._row(r2["id"])["dados"]
    assert d["p"] and sorted(d["p"]["jogadores"]) == sorted([a, b])                        # os dois jogadores, já em jogo
    assert OL.consultar_busca(a, TS + 2) == {"estado": "partida", "id": r1["id"]}           # quem esperava descobre na consulta seguinte


def test_duracoes_diferentes_nao_se_encontram(mundo):
    a, b = mundo[0], mundo[1]
    assert OL.buscar(a, "rapida", TS)["estado"] == "fila"
    assert OL.buscar(b, "longa", TS + 1)["estado"] == "fila"
    assert OL.partida_ativa(a) != OL.partida_ativa(b)


def test_o_terceiro_nao_entra_numa_partida_que_ja_tem_dois(mundo):
    a, b, c = mundo[0], mundo[1], "c@x.com"
    _contas([c])
    OL.buscar(a, "rapida", TS)
    OL.buscar(b, "rapida", TS + 1)
    assert OL.buscar(c, "rapida", TS + 2)["estado"] == "fila"                               # procura sozinho, em outra busca
    assert OL.partida_ativa(c) not in (OL.partida_ativa(a), None)


def test_busca_antiga_demais_sem_consultar_e_ignorada(mundo):
    a, b = mundo[0], mundo[1]
    OL.buscar(a, "rapida", TS)
    assert OL.buscar(b, "rapida", TS + OL.BUSCA_VIVA_S + 5)["estado"] == "fila"             # o app de A parou de consultar: não vale mais


def test_duas_buscas_criadas_ao_mesmo_tempo_se_resolvem_a_mais_nova_entra_na_mais_antiga(mundo):
    a, b = mundo[0], mundo[1]
    pa = OL.criar_busca_de_novo(a, "rapida", TS)
    pb = OL.criar_busca_de_novo(b, "rapida", TS + 0.5)                                       # ninguém viu ninguém na hora de criar
    assert OL.consultar_busca(a, TS + 1)["estado"] == "fila"                                  # a mais antiga espera
    r = OL.consultar_busca(b, TS + 1.5)                                                       # a mais nova desiste da sua e entra na outra
    assert r["estado"] == "partida" and r["id"] == pa
    assert OL._row(pb)["dados"].get("cancelada")


def test_cancelar_a_busca_libera_a_pessoa(mundo):
    a = mundo[0]
    OL.buscar(a, "rapida", TS)
    OL.sair_da_busca(a, TS + 1)
    assert OL.partida_ativa(a) is None and OL.consultar_busca(a, TS + 2)["estado"] == "fora"


def test_busca_que_ninguem_atendeu_expira(mundo):
    a = mundo[0]
    OL.buscar(a, "rapida", TS)
    assert OL.consultar_busca(a, TS + OL.BUSCA_MAX_ESPERA_S + 1)["estado"] == "expirou"
    assert OL.partida_ativa(a) is None


def test_sala_privada_de_amigos_nunca_entra_na_busca(mundo):
    a, b = mundo[0], mundo[1]
    OL.criar_sala(a, "", TS, corrida="rapida")                                                # sala escondida do desafio entre amigos
    assert OL.buscar(b, "rapida", TS + 1)["estado"] == "fila"                                 # a busca não puxa para dentro dela
    assert OL.partida_ativa(a) != OL.partida_ativa(b)


def test_quem_ja_esta_em_partida_volta_para_ela(mundo):
    a, b = mundo[0], mundo[1]
    OL.buscar(a, "rapida", TS)
    OL.buscar(b, "rapida", TS + 1)
    assert OL.buscar(a, "rapida", TS + 5)["estado"] == "partida"                              # não cria outra busca em cima


def test_duracao_invalida_e_recusada(mundo):
    with pytest.raises(OL.ErroSala):
        OL.buscar(mundo[0], "inexistente", TS)


def test_api_duas_pessoas_procurando_se_encontram(dois, monkeypatch):
    import api.main as API
    ana, bia = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    monkeypatch.setattr(API, "_agora", lambda: 6_000_000.0)
    r1 = ana.post("/trade/fila", json={"corrida": "rapida"}).json()
    assert r1["estado"] == "fila" and ana.get("/trade/fila").json()["estado"] == "fila"
    r2 = bia.post("/trade/fila", json={"corrida": "rapida"}).json()
    assert r2["estado"] == "partida" and r2["id"] == r1["id"]
    assert ana.get("/trade/fila").json() == {"estado": "partida", "id": r1["id"]}
    assert ana.get(f"/trade/salas/{r1['id']}").status_code == 200 and bia.get(f"/trade/salas/{r1['id']}").status_code == 200   # a partida abre para os dois
    assert bia.post("/trade/fila", json={"corrida": "rapida"}).json()["estado"] == "partida"                                    # quem já está jogando volta para ela


def test_api_busca_esquecida_nao_vira_voltar_para_sua_sala_na_central_e_pode_ser_cancelada(dois, monkeypatch):
    import api.main as API
    ana, _ = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    monkeypatch.setattr(API, "_agora", lambda: 6_100_000.0)
    assert ana.post("/trade/fila", json={"corrida": "longa"}).json()["estado"] == "fila"
    assert ana.get("/trade/central").json()["ativa"] is None                       # o app foi fechado e voltou: a busca esquecida é cancelada
    assert ana.get("/trade/fila").json()["estado"] == "fora"
    assert ana.post("/trade/fila", json={"corrida": "longa"}).json()["estado"] == "fila"
    assert ana.post("/trade/fila/sair").json() == {"ok": True} and ana.get("/trade/fila").json()["estado"] == "fora"
