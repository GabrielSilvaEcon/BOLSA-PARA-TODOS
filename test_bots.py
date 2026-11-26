"""Bots de treino: aparecem só quando ninguém mais está procurando, são sempre identificados e não mexem em troféus nem ranking."""
import json

import pytest

import api.main as API
import bots as BOTS
import setups as SU
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
    assert r2["estado"] == "partida" and r2["id"] == r["id"] and r2["bot"] in BOTS.NOMES
    p = OL._row(r["id"])["dados"]["p"]
    bot = next(j for j in p["jogadores"] if BOTS.eh_bot(j))
    assert sorted(p["jogadores"]) == sorted([a, bot])
    assert p["apostas"][bot]["stake"] == p["apostas"][a]["stake"]                         # mesmo capital: comparação justa
    assert TB._chave(1, bot) in p["estrategias"]                                          # o bot já confirmou a estratégia (a partida só espera o jogador)
    assert p["setups"]["equip"][bot] and p["setups"]["equip"][bot][0] in BOTS.SETUPS      # joga com um setup que não depende de marcação
    assert TB._rotulos(p, a)[bot].startswith("Bot ")                                      # sempre identificado como bot


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


def _partida_com_bot():
    cen = TD.demo_corrida("rapida", 11)
    sp = TB.CORRIDAS["rapida"]
    bot = BOTS.PREFIXO + "xyz"
    p = TB.nova_partida(cen, sp["tf"], [A, bot], 1000.0, pid="sala1", multi=True, apostas={j: {"stake": 10_000.0, "pat": 500_000.0} for j in (A, bot)}, corrida="rapida")
    for j in (A, bot):
        TB.salvar_estrategia(p, j, {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, None, 0, T0)
    p["setups"] = SV.iniciar([A, bot], {A: [], bot: ["setup_classico"]})
    return p, cen, bot


def test_o_bot_entra_pelo_setup_na_hora_sem_pausar_a_partida_do_jogador(monkeypatch):
    p, cen, bot = _partida_com_bot()
    monkeypatch.setattr(SU, "detectar", lambda sid, v: {"direcao": "alta", "stop": round(v[-1]["c"] * 0.99, 2), "alvo": round(v[-1]["c"] * 1.02, 2), "motivo": "t"})
    tick(p, cen, T0 + 3 * 4.0 + 0.2)
    s = p["setups"]
    assert s["evento"] is None and not TB.pausada(p)                                       # nenhuma janela, nenhuma pausa para o jogador
    assert [x["jogador"] for x in s["sinais"]] == [bot] and s["sinais"][0]["estado"] == "aceito"
    assert any(a.get("jogador") == bot and a.get("aid", "").startswith("setup:") for a in p["acoes"])   # a ordem entrou pelo sistema de ordens
    marca = SV.visao(p, A, T0 + 13)["marcas"][0]
    assert marca["meu"] is False and "stop" not in marca                                    # o jogador vê que o adversário entrou, sem stop nem alvo dele


def test_partida_com_bot_nao_conta_para_ranking_nem_troféus(monkeypatch):
    p, _, _ = _partida_com_bot()
    chamadas = []
    monkeypatch.setattr(API.J, "registrar_trade", lambda *a, **k: chamadas.append(a) or ({}, False))
    API._registrar_ranking(None, "sala1", p, {"placar": []}, None)
    assert chamadas == []                                                                   # treino: nada de ranking
    p2 = {**p, "jogadores": [A, "b@x.com"]}
    p2["jogadores"] = [A, "outro@x.com"]
    assert not BOTS.tem_bot(p2)


def test_api_busca_sem_ninguem_vira_treino_contra_bot_e_a_partida_abre(dois, monkeypatch):
    ana, _ = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json()
    assert r["estado"] == "fila"
    t["agora"] += BOTS.BOT_ESPERA_S + 1
    r2 = ana.get("/trade/fila").json()
    assert r2["estado"] == "partida" and r2["bot"]
    assert ana.get(f"/trade/salas/{r['id']}").status_code == 200
    assert ana.post(f"/trade/salas/{r['id']}/estrategia", json={"direcao": "alta"}).status_code == 200      # o jogador confirma; o bot já tinha confirmado
    t["agora"] += 6
    v = ana.get(f"/trade/salas/{r['id']}")
    assert v.status_code == 200 and v.json()["tela"]["modo"] == "replay"                                   # o replay começa sem esperar mais ninguém
    rotulos = json.dumps(v.json())
    assert "Bot 2" in rotulos and "Jogador 2" not in rotulos                                # o adversário aparece como bot
