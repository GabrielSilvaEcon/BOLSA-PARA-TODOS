"""Partida solo: uma consulta (a cada segundo) e uma jogada do jogador chegando ao mesmo tempo não podem se atropelar.
Antes, a consulta lia o estado, a jogada gravava, e a consulta gravava de volta o estado velho: a jogada sumia (confirmar a estratégia 'resetava',
zerar/comprar/vender 'não fazia nada' e só funcionava no 2º clique)."""
import pytest

import api.main as API
import trader_battle as TB
from test_api import cli  # noqa: F401


def _nova(cli, monkeypatch):
    t = {"agora": 8_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    pid = cli.post("/trade/solo", json={"corrida": "rapida"}).json()["id"]
    return pid, t


def _no_meio_da_consulta(monkeypatch, fazer):
    """Na 1ª vez que a consulta mexe no estado, `fazer()` acontece 'ao mesmo tempo' (depois de a consulta ler, antes de gravar)."""
    orig, uma = TB.avancar, {"v": True}

    def av(p, agora, cens=None):
        if uma["v"]:
            uma["v"] = False
            fazer()
        return orig(p, agora, cens)
    monkeypatch.setattr(TB, "avancar", av)


def test_confirmar_estrategia_nao_some_se_a_consulta_chega_junto(cli, monkeypatch):
    pid, t = _nova(cli, monkeypatch)
    t["agora"] += 5
    r_in = {}
    _no_meio_da_consulta(monkeypatch, lambda: r_in.update(r=cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})))
    assert cli.get(f"/trade/solo/{pid}").status_code == 200                 # a consulta que estava no ar
    assert r_in["r"].status_code == 200, r_in["r"].text
    v = cli.get(f"/trade/solo/{pid}").json()
    assert v["fase"] == "replay", "a estratégia confirmada tem que continuar valendo"


def test_ordem_nao_some_se_a_consulta_chega_junto(cli, monkeypatch):
    pid, t = _nova(cli, monkeypatch)
    t["agora"] += 5
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
    t["agora"] += 1
    _no_meio_da_consulta(monkeypatch, lambda: cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 2}}))
    cli.get(f"/trade/solo/{pid}")
    t["agora"] += 3
    m = cli.get(f"/trade/solo/{pid}").json()["tela"]["mesa"]
    assert m["posicao"] and m["posicao"]["q"] == 2, "a compra do primeiro clique não pode ter sumido"


def test_consultas_sem_novidade_nao_regravam_o_estado(cli, monkeypatch):
    pid, t = _nova(cli, monkeypatch)
    t["agora"] += 5
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
    gravacoes = []
    import banco
    orig = banco._atualizar_n
    monkeypatch.setattr(banco, "_atualizar_n", lambda *a, **k: gravacoes.append(a[0]) or orig(*a, **k))
    cli.get(f"/trade/solo/{pid}"); cli.get(f"/trade/solo/{pid}"); cli.get(f"/trade/solo/{pid}")
    assert gravacoes.count("config_sistema") <= 1, "consulta que não muda nada não precisa gravar (menos atropelo)"


def test_consulta_que_tem_novidade_perde_a_corrida_refaz_e_a_jogada_continua_valendo(cli, monkeypatch):
    """A consulta também tem algo para gravar (o relógio andou): ela tenta, descobre que a jogada gravou antes, relê e refaz sem apagar a jogada."""
    pid, t = _nova(cli, monkeypatch)
    t["agora"] += 5
    orig, uma, tentativas = TB.avancar, {"v": True}, {"n": 0}

    def av(p, agora, cens=None):
        tentativas["n"] += 1
        if uma["v"]:
            uma["v"] = False
            cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
            r = orig(p, agora, cens)
            p["versao"] += 1                                                # a consulta "tem novidade": vai tentar gravar
            return r
        return orig(p, agora, cens)
    monkeypatch.setattr(TB, "avancar", av)
    assert cli.get(f"/trade/solo/{pid}").status_code == 200
    assert tentativas["n"] >= 3, "a consulta perdeu a corrida e refez a partir do estado novo"
    assert cli.get(f"/trade/solo/{pid}").json()["fase"] == "replay"
