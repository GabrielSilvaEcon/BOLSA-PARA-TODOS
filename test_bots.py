"""Bots de treino: aparecem só quando ninguém mais está procurando, são sempre identificados e contam para ranking e troféus (com dificuldade real)."""
import json

import pytest

import api.main as API
import bot_jogo as BJ
import bots as BOTS
import setups_vivo as SV
import trader_battle as TB
import trader_dados as TD
import trader_online_dados as OL
from test_setups import A, T0, tick
from test_social_api import dois  # noqa: F401  (duas contas)
from test_trader_mesa import EMAILS, TS, _contas, banco_isolado, livro


@pytest.fixture
def mundo(monkeypatch):
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    with banco_isolado():
        _contas()
        with livro(pat=300_000.0, caixa=200_000.0):
            yield EMAILS


def test_sozinho_ate_o_tempo_a_busca_continua_e_depois_entra_um_bot_identificado(mundo):
    a = mundo[0]
    r = OL.buscar(a, "rapida", TS)
    assert r["estado"] == "fila"
    assert OL.consultar_busca(a, TS + BOTS.BOT_ESPERA_S - 1)["estado"] == "fila"          # ainda dá tempo de aparecer gente de verdade
    r2 = OL.consultar_busca(a, TS + BOTS.BOT_ESPERA_S + 0.5)
    assert r2["estado"] == "partida" and r2["id"] == r["id"] and "bot" not in r2
    p = OL._row(r["id"])["dados"]["p"]
    bot = next(j for j in p["jogadores"] if BOTS.eh_bot(j))
    assert sorted(p["jogadores"]) == sorted([a, bot])
    assert p["apostas"][bot]["stake"] == p["apostas"][a]["stake"]                         # mesmo capital: comparação justa
    assert TB._chave(1, bot) in p["estrategias"]                                          # o bot já confirmou a estratégia (a partida só espera o jogador)
    assert p["bots"][bot]["plano"] and p["bots"][bot]["nivel"] == "normal"                # tem plano de operações e nível de dificuldade
    assert p["bots"][bot]["trofeus"] == BOTS.trofeus_do_bot(0, BOTS.NIVEL["normal"])
    assert TB._rotulos(p, a)[bot].startswith("Jogador ")                                      # na mesa é um jogador comum


def test_chamar_de_novo_nao_cria_outro_bot(mundo):
    a = mundo[0]
    pid = OL.buscar(a, "rapida", TS)["id"]
    OL.consultar_busca(a, TS + 20)
    OL.consultar_busca(a, TS + 21)
    OL.consultar_busca(a, TS + 22)
    p = OL._row(pid)["dados"]["p"]
    assert len([j for j in p["jogadores"] if BOTS.eh_bot(j)]) == 1


def test_gente_de_verdade_aparecendo_a_tempo_ganha_do_bot(mundo):
    a, b = mundo[0], mundo[1]
    pid = OL.buscar(a, "rapida", TS)["id"]
    assert OL.buscar(b, "rapida", TS + 5)["estado"] == "partida"
    p = OL._row(pid)["dados"]["p"]
    assert not BOTS.tem_bot(p) and sorted(p["jogadores"]) == sorted([a, b])


def test_com_os_bots_desligados_a_busca_so_espera_gente(mundo, monkeypatch):
    monkeypatch.setattr(BOTS, "BOTS_ATIVOS", False)
    a = mundo[0]
    OL.buscar(a, "rapida", TS)
    assert OL.consultar_busca(a, TS + 60)["estado"] == "fila"


def _partida_com_bot(nivel="normal", semente=3):
    cen = TD.demo_corrida("rapida", 11)
    sp = TB.CORRIDAS["rapida"]
    bot = BOTS.PREFIXO + "xyz"
    p = TB.nova_partida(cen, sp["tf"], [A, bot], 1000.0, pid="sala1", multi=True, apostas={j: {"stake": 10_000.0, "pat": 500_000.0} for j in (A, bot)}, corrida="rapida")
    for j in (A, bot):
        TB.salvar_estrategia(p, j, {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, None, 0, T0)
    p["setups"] = SV.iniciar([A, bot], {A: [], bot: []})
    ini = TB.inicio_rodada(cen, 1, TB._nrp(p))
    plano = BJ.plano_do_bot(cen, ini, TB._nrp(p), BOTS.NIVEL[nivel], semente)
    p["bots"] = {bot: {"nivel": nivel, "nome": "Bot Touro", "trofeus": 100, "plano": plano["plano"]}}
    return p, cen, bot


def test_o_bot_opera_o_plano_pelo_sistema_de_ordens_sem_pausar_o_jogador():
    p, cen, bot = _partida_com_bot("mestre")
    assert p["bots"][bot]["plano"]
    n_acoes = 0
    for k in range(1, 61):
        t = T0 + k * 4.0 + 0.2
        tick(p, cen, t)
        BJ.agir(p, cen, t)
        assert not TB.pausada(p)
    acoes = [a for a in p["acoes"] if a.get("jogador") == bot]
    assert any(a["aid"].startswith("bot:") and a["aid"].endswith(":a") for a in acoes)         # abriu pelo registrar_acao
    assert all(t["estado"] in ("fechada", "pulada") for t in p["bots"][bot]["plano"])
    pl = TB.placar_final(p)
    assert {x["jogador"] if "jogador" in x else x.get("email") for x in pl} >= {bot} or len(pl) == 2   # o bot está no placar


def test_agir_e_idempotente():
    p, cen, bot = _partida_com_bot()
    t = T0 + 30 * 4.0 + 0.2
    tick(p, cen, t)
    BJ.agir(p, cen, t)
    antes = json.dumps(p["acoes"], sort_keys=True)
    assert BJ.agir(p, cen, t) is False
    assert json.dumps(p["acoes"], sort_keys=True) == antes


def test_nivel_do_bot_sobe_com_os_troféus_do_jogador():
    assert [BOTS.nivel_para(t)["id"] for t in (0, 199, 200, 999, 1000, 3500)] == ["normal", "normal", "dificil", "dificil", "mestre", "mestre"]
    b0, b1 = BOTS.novo("abc", 1, 0), BOTS.novo("abc", 1, 1500)
    assert b0["trofeus"] == 0 and b1["trofeus"] == 1500 + BOTS.NIVEL["mestre"]["trofeus"]       # o bot nunca vale menos que o jogador


def test_dificuldade_cresce_com_o_nivel():
    cen = TD.demo_corrida("rapida", 11)
    passos = cen["candles"][50:50 + 80]
    taxa = {}
    for nid, nv in BOTS.NIVEL.items():
        certas = total = 0
        for sem in range(300):
            for t in BJ.planejar(passos, nv, sem):
                fut = passos[t["fecha"]]["c"] - passos[t["abre"] - 1]["c"]
                certas += (fut >= 0) == (t["dir"] == "alta")
                total += 1
        taxa[nid] = certas / total
    assert taxa["normal"] < taxa["dificil"] < taxa["mestre"]
    assert 0.55 < taxa["normal"] < 0.7 and taxa["mestre"] > 0.75                               # nem trivial nem invencível


def test_partida_com_bot_conta_para_ranking_e_troféus_com_o_valor_do_bot(monkeypatch):
    p, _, bot = _partida_com_bot()
    jog = []
    tro = []
    monkeypatch.setattr(API.J, "registrar_trade", lambda *a, **k: jog.append(a) or ({}, False))
    monkeypatch.setattr(API.banco, "jogos_placar_ler", lambda ator: {})
    monkeypatch.setattr(API.banco, "jogos_placar_gravar", lambda *a, **k: None)
    monkeypatch.setattr(API, "_trof_registrar", lambda q, jogo, pid, advs, placar, bots=None: tro.append((advs, placar, bots)))
    class Q:
        email = A
        ator = None
    fz = {"placar": [{"voce": True, "pos": 1, "pontos": 10}, {"voce": False, "pos": 2, "pontos": 5}], "rodadas": [1]}
    API._registrar_ranking(Q(), "sala1", p, fz, None)
    assert len(jog) == 1                                                                        # entrou no placar de jogos
    assert tro and tro[0][0] == [bot] and tro[0][2][bot]["trofeus"] == 100 and tro[0][1] == 1.0   # e nos troféus, contra o valor do bot


def test_api_busca_sem_ninguem_vira_treino_contra_bot_e_a_partida_abre(dois, monkeypatch):
    ana, _ = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json()
    assert r["estado"] == "fila"
    t["agora"] += BOTS.BOT_ESPERA_S + 1
    r2 = ana.get("/trade/fila").json()
    assert r2["estado"] == "partida" and "bot" not in r2
    assert ana.get(f"/trade/salas/{r['id']}").status_code == 200
    assert ana.post(f"/trade/salas/{r['id']}/estrategia", json={"direcao": "alta"}).status_code == 200      # o jogador confirma; o bot já tinha confirmado
    t["agora"] += 6
    v = ana.get(f"/trade/salas/{r['id']}")
    assert v.status_code == 200 and v.json()["tela"]["modo"] == "replay"                                   # o replay começa sem esperar mais ninguém
    rotulos = json.dumps(v.json())
    assert "Jogador 2" in rotulos and "Bot 2" not in rotulos                                # o adversário aparece como jogador comum


def test_nome_do_bot_e_de_jogador_comum_e_estrategia_varia():
    nomes = {BOTS.novo(f"p{i}", i)["nome"] for i in range(30)}
    assert len(nomes) > 10 and not any("bot" in n.lower() for n in nomes)
    assert BOTS.rotulo(BOTS.PREFIXO + "x") == "Jogador"


def test_ranking_de_troféus_tem_jogadores_da_casa_com_pontuacao_baixa(dois, monkeypatch):
    ana, _ = dois
    for jogo in ("trade", "ticker"):
        r = ana.get(f"/ranking/{jogo}/tela").json()
        assert r["total"] >= 8 and max(l["valor"] for l in r["linhas"]) <= 260 and all(l["nome"] for l in r["linhas"])
        assert ana.get(f"/ranking/{jogo}/tela", params={"filtro": "amigos"}).json()["total"] <= 2     # só amigos de verdade
    monkeypatch.setattr(BOTS, "BOTS_ATIVOS", False)
    assert ana.get("/ranking/trade/tela").json()["total"] <= 2


def test_sem_grafico_real_a_busca_avisa_e_encerra_em_vez_de_expirar(mundo, monkeypatch):
    def sem(f, s, banco=None, permitir_demo=False):
        raise TD.SemCenarios("Os gráficos reais desta duração ainda estão sendo preparados.")
    monkeypatch.setattr(TD, "escolher_corrida", sem)
    a = mundo[0]
    OL.buscar(a, "rapida", TS)
    r = OL.consultar_busca(a, TS + BOTS.BOT_ESPERA_S + 1)
    assert r["estado"] == "sem_graficos" and "preparados" in r["mensagem"]
    assert OL.consultar_busca(a, TS + BOTS.BOT_ESPERA_S + 3)["estado"] == "fora"                       # a busca foi encerrada, sem ficar presa


def test_health_check_nao_depende_do_banco(monkeypatch):
    from fastapi.testclient import TestClient
    def lento(*a, **k):
        raise AssertionError("o health check não pode consultar o banco")
    monkeypatch.setattr(API.banco, "pronto", lento)
    assert TestClient(API.app).get("/saude").json() == {"ok": True}


def test_lote_e_capital_da_tela_online_seguem_o_capital_real_do_jogador(dois, monkeypatch):
    """Bug do vídeo: com caixa pequeno a tela mostrava '1 lote = 16 ações' (capital simbólico de T$ 10.000) e a compra de 1 lote era barrada."""
    import trader_carteira as TCA
    ana, _ = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    monkeypatch.setattr(TCA, "situacao", lambda email: {"pat": 20000.0, "caixa": 9446.8})            # capital da partida = 5% = T$ 472,34
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json()
    t["agora"] += BOTS.BOT_ESPERA_S + 1
    ana.get("/trade/fila")
    ana.post(f"/trade/salas/{r['id']}/estrategia", json={"direcao": "alta"})
    t["agora"] += 40
    tela = ana.get(f"/trade/salas/{r['id']}").json()["tela"]
    assert tela["plano_cfg"]["capital"] == 472.34
    assert tela["lote"] * tela["ref"] <= 472.34 * 0.1 + tela["ref"]                                      # 1 lote cabe (10% do capital)
    assert tela["lote"] * tela["ref"] < 472.34
