"""Competição · etapa 3, parte 3: o fechamento diário publica as temporadas, congela a encerrada e concede selos. Sem internet: SQLite temporário."""
import json
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import banco  # noqa: E402
import competicao_job as J  # noqa: E402
import seguranca as seg  # noqa: E402


@pytest.fixture()
def bd(tmp_path):
    banco.usar_sqlite(tmp_path / "t.db")
    banco.migrar_sqlite()
    yield banco
    banco.usar_sqlite(None)


def _uteis(ini, fim):
    d, out = date.fromisoformat(ini), []
    while d <= date.fromisoformat(fim):
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DIAS = _uteis("2026-10-01", "2026-11-06")
TAXAS = {"AAAA3": 0.004, "BBBB3": 0.003, "CCCC3": 0.002, "DDDD3": 0.001, "EEEE3": 0.0005, "FFFF3": 0.0002}


def _coletor(ate):
    dias = [d for d in DIAS if d <= ate]

    def coleta(tk):
        r = TAXAS.get(tk, 0.0)
        return {"fech": {d: round(100 * (1 + r) ** i, 4) for i, d in enumerate(dias)}, "div": {}, "spl": {}}
    return coleta


class Entregas:
    def __call__(self, *a, **k):
        return {}


def _participante(email, apelido, ticker):
    cid = seg.novo_id()
    banco.sis_criar_conta({"id": cid, "email": email, "nome": apelido, "papel": "usuario", "status": "ativa",
                           "email_verificado": 1, "provedor": "senha", "criado_em": seg.iso()})
    ordem = {"id": f"o-{apelido}", "ts": "2026-10-01T09:00:00", "l": "C", "t": ticker, "q": 300, "x": "2026-10-01"}
    banco.sis_estado_gravar(email, "comp_ordens", {"apelido": apelido, "apelido_k": apelido, "aceite": True, "entrada": "2026-10-01",
                                                    "drip": False, "pend": [ordem]})


def _montar():
    for i, tk in enumerate(TAXAS):
        _participante(f"p{i}@x.com", f"jog{i}", tk)


def test_fechamento_congela_outubro_e_concede_selos_uma_vez(bd):
    _montar()
    r1 = J.executar(agora=datetime(2026, 11, 2, 18, 30), coletor=_coletor("2026-11-02"), entregar=Entregas())
    assert r1["status"] == "ok" and r1["encerradas"] == ["2026-10", "2026-T3"] and r1["selos"] == 4
    out = banco.comp_temp_ler("2026-10")
    assert out["encerrada"] and [x["apelido"] for x in out["lista"]][:3] == ["jog0", "jog1", "jog2"]
    assert "@" not in json.dumps(out) and "posicoes" not in out
    nov = banco.comp_temp_ler("2026-11")
    assert nov["encerrada"] is False and banco.comp_temp_ler("2026-T4")["n"] == 6
    assert banco.comp_temp_ler("2026-T3")["encerrada"] and banco.comp_temp_ler("2026-T3")["n"] == 0
    cart = banco.sis_estado_ler("p0@x.com", "comp_cart")
    assert [s["selo"] for s in cart["selos"]] == ["ouro", "equilibrio"]          # série lisa: o líder também tem o melhor Sharpe
    assert cart["rank"]["temp"]["2026-T4"]["pos"] == 1
    assert [s["selo"] for s in banco.sis_estado_ler("p1@x.com", "comp_cart")["selos"]] == ["prata"]

    titulos = [n["titulo"] for n in banco.notif_listar(banco.Ator("x", "p0@x.com", "usuario"))]
    assert "Você ganhou o selo Ouro" in titulos and "Você ganhou o selo Equilíbrio" in titulos
    assert not any("selo" in n["titulo"] for n in banco.notif_listar(banco.Ator("x", "p5@x.com", "usuario")))      # sem selo, sem aviso

    gerado = out["gerado_em"]
    r2 = J.executar(agora=datetime(2026, 11, 3, 18, 30), coletor=_coletor("2026-11-03"), entregar=Entregas())
    assert r2["status"] == "ok" and r2["encerradas"] == [] and r2["selos"] == 0
    assert banco.comp_temp_ler("2026-10")["gerado_em"] == gerado                       # congelada: não foi republicada
    assert len(banco.sis_estado_ler("p0@x.com", "comp_cart")["selos"]) == 2             # sem selo duplicado
    assert banco.comp_temp_ler("2026-11")["gerado"] == "2026-11-03"
    assert sum("selo" in n["titulo"] for n in banco.notif_listar(banco.Ator("x", "p0@x.com", "usuario"))) == 2     # nenhum aviso repetido


def test_falha_nas_temporadas_nao_derruba_o_ranking_geral(bd, monkeypatch):
    _montar()
    import competicao_temporadas as T
    monkeypatch.setattr(T, "planejar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quebrou")))
    r = J.executar(agora=datetime(2026, 11, 2, 18, 30), coletor=_coletor("2026-11-02"), entregar=Entregas())
    assert r["status"] == "ok" and banco.cfg_ler("comp_ranking")["listas"]["geral_n"] == 6 and r["temporadas"] == 0


def test_publicacao_e_leitura_so_aceitam_temporada_valida(bd):
    for ruim in ("comp_temp|2026-13", "comp_temp|2026-T5", "comp_temp|x", "comp_temp|2026-11|a"):
        with pytest.raises(ValueError):
            banco.sis_comp_publicar(ruim, {})
    banco.sis_comp_publicar("comp_temp|2026-T4", {"ok": 1})
    assert banco.comp_temp_ler("2026-T4") == {"ok": 1} and banco.comp_temp_ler("2026-09") == {}
    with pytest.raises(ValueError):
        banco.comp_temp_ler("../x")
