"""Competição · etapa 2 (ligas de amigos e avisos de posição). Sem internet: SQLite temporário e cotações falsas."""
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import banco  # noqa: E402
import competicao as C  # noqa: E402
import competicao_job as J  # noqa: E402
import competicao_ligas as L  # noqa: E402
import seguranca as seg  # noqa: E402

UTC = timezone.utc


@pytest.mark.parametrize("txt,esperado", [("k7qm-2xpa", "K7QM2XPA"), (" K7QM 2XPA ", "K7QM2XPA"), ("K7QM2XP", None), ("K7QM2XP0", None),
                                          ("", None), (None, None), ("K7QM2XPAA", None), ("K7QM2XP!", None)])
def test_codigo_valido(txt, esperado):
    assert L.codigo_valido(txt) == esperado


def test_documento_da_pessoa_saneado():
    sujo = {"ligas": [{"c": "k7qm2xpa", "em": "2026-11-02", "dono": 1}, {"c": "K7QM2XPA", "em": "2026-11-03"}, {"c": "ruim", "em": "2026-11-02"},
                      {"c": "AAAAAAAA", "em": "não é data"}, "lixo", None], "avisos": {"liga": 0}, "extra": "x" * 1000}
    d = L.sanear_ligas(sujo)
    assert d["ligas"] == [{"c": "K7QM2XPA", "em": "2026-11-02", "dono": True}]
    assert d["avisos"] == {"liga": False, "global": True}
    assert "extra" not in d
    assert L.sanear_ligas(None) == {"v": 1, "ligas": [], "avisos": {"liga": True, "global": True}}


def test_adicionar_remover_sem_repetir():
    d = L.adicionar({}, "K7QM2XPA", date(2026, 11, 2))
    d = L.adicionar(d, "K7QM2XPA", date(2026, 11, 5), dono=True)
    assert len(d["ligas"]) == 1 and d["ligas"][0]["em"] == "2026-11-02" and not d["ligas"][0]["dono"]
    assert L.participa(d, "K7QM2XPA") and L.remover(d, "K7QM2XPA")["ligas"] == []


# ------------------------------------------------------------------ ranking das ligas (lógica pura)
def _est(retornos: list[float]) -> dict:
    hist = [{"d": (date(2026, 11, 2) + timedelta(days=i)).isoformat(), "p": round(C.CAPITAL_INICIAL * (1 + r), 2)} for i, r in enumerate(retornos)]
    e = C.novo_estado("2026-11-02")
    e["hist"] = hist
    return e


# ------------------------------------------------------------------ avisos de posição
AGORA = datetime(2026, 11, 9, 21, 30, tzinfo=UTC)


def _r(geral=None, n=100, ligas=None, em="2026-11-06"):
    return {"geral": geral, "n": {"geral": n}, "ligas": ligas or {}, "em": em}


def test_avisos_entrada_no_ranking_geral_uma_vez():
    av = L.avisos_de_posicao({}, _r(12, 340, em="2026-11-09"), "2026-11-09", None, AGORA)
    assert len(av) == 1 and "entrou no ranking geral" in av[0]["titulo"] and "12º de 340" in av[0]["texto"]
    assert av[0]["dedup"] == "comp|g|entrada" and av[0]["origem"] == "competicao" and av[0]["pagina"] == "competicao"


@pytest.mark.parametrize("antes,depois,marco", [(150, 90, 100), (50, 9, 10), (30, 3, 3), (4, 1, 1), (12, 2, 3)])
def test_avisos_marcos_do_ranking_geral(antes, depois, marco):
    av = L.avisos_de_posicao(_r(antes), _r(depois, em="2026-11-09"), "2026-11-09", None, AGORA)
    assert len(av) == 1 and f"comp|g|sobe|{marco}|2026-11-09" == av[0]["dedup"]


def test_sem_aviso_quando_nao_cruza_marco_ou_cai_fora_do_topo():
    assert L.avisos_de_posicao(_r(50), _r(40, em="2026-11-09"), "2026-11-09", None, AGORA) == []
    assert L.avisos_de_posicao(_r(5), _r(8, em="2026-11-09"), "2026-11-09", None, AGORA) == []


def test_perde_a_lideranca():
    av = L.avisos_de_posicao(_r(1), _r(2, em="2026-11-09"), "2026-11-09", None, AGORA)
    assert len(av) == 1 and "caiu para 2º" in av[0]["titulo"]


def test_avisos_de_liga_viram_um_so_por_dia():
    ant = _r(None, ligas={"AAAAAAAA": {"geral": 3, "nome": "Turma"}, "BBBBBBBB": {"geral": 1, "nome": "Família"}})
    novo = _r(None, ligas={"AAAAAAAA": {"geral": 2, "n": 5, "nome": "Turma"}, "BBBBBBBB": {"geral": 2, "n": 4, "nome": "Família"},
                           "CCCCCCCC": {"geral": 1, "n": 3, "nome": "Novos"}}, em="2026-11-09")
    av = L.avisos_de_posicao(ant, novo, "2026-11-09", None, AGORA)
    assert len(av) == 1 and av[0]["dedup"] == "comp|ligas|2026-11-09" and av[0]["titulo"] == "Mudanças em 3 das suas ligas"
    assert "Turma: subiu para 2º de 5" in av[0]["texto"] and "Família: caiu para 2º de 4" in av[0]["texto"] and "Novos: você entrou" in av[0]["texto"]
    assert av[0]["importancia"] == "baixa"        # só vira "média" quando a pessoa SOBE para 1º; entrar já em 1º ou cair não conta


def test_aviso_de_liga_media_quando_assume_a_lideranca():
    ant = _r(None, ligas={"AAAAAAAA": {"geral": 2, "nome": "Turma"}})
    novo = _r(None, ligas={"AAAAAAAA": {"geral": 1, "n": 5, "nome": "Turma"}}, em="2026-11-09")
    av = L.avisos_de_posicao(ant, novo, "2026-11-09", None, AGORA)
    assert len(av) == 1 and av[0]["importancia"] == "media" and "Turma" in av[0]["titulo"]


def test_preferencias_desligam_os_avisos():
    ant = _r(150, ligas={"AAAAAAAA": {"geral": 3, "nome": "Turma"}})
    novo = _r(3, ligas={"AAAAAAAA": {"geral": 1, "n": 5, "nome": "Turma"}}, em="2026-11-09")
    assert len(L.avisos_de_posicao(ant, novo, "2026-11-09", None, AGORA)) == 2
    assert len(L.avisos_de_posicao(ant, novo, "2026-11-09", {"liga": False}, AGORA)) == 1
    assert L.avisos_de_posicao(ant, novo, "2026-11-09", {"liga": False, "global": False}, AGORA) == []


def test_liga_com_um_unico_membro_nao_gera_aviso():
    novo = _r(None, ligas={"AAAAAAAA": {"geral": 1, "n": 1, "nome": "Sozinho"}}, em="2026-11-09")
    assert L.avisos_de_posicao(_r(None), novo, "2026-11-09", None, AGORA) == []


def test_reexecucao_do_mesmo_dia_nao_reavisa():
    assert L.avisos_de_posicao(_r(150, em="2026-11-09"), _r(3, em="2026-11-09"), "2026-11-09", None, AGORA) == []


# ------------------------------------------------------------------ banco (SQLite temporário): isolamento e permissões
@pytest.fixture()
def bd(tmp_path):
    banco.usar_sqlite(tmp_path / "t.db")
    banco.migrar_sqlite()
    yield banco
    banco.usar_sqlite(None)


def _conta(email, status="ativa", papel="usuario"):
    cid = seg.novo_id()
    banco.sis_criar_conta({"id": cid, "email": email, "nome": email.split("@")[0], "papel": papel, "status": status,
                           "email_verificado": 1, "provedor": "senha", "criado_em": seg.iso()})
    return banco.Ator(cid, email, papel)


def test_publicar_so_aceita_chaves_conhecidas(bd):
    with pytest.raises(ValueError):
        banco.sis_comp_publicar("plano|abc", {})
    with pytest.raises(ValueError):
        banco.sis_comp_publicar("comp_lr|curto", {})
    with pytest.raises(ValueError):
        banco.sis_comp_todos("perfis")


# ------------------------------------------------------------------ fechamento completo com ligas e avisos
DIAS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09"]


def _serie(valores: list[float], extra: dict | None = None) -> dict:
    return {"fech": {d: v for d, v in zip(DIAS + ["2026-11-10"], valores)}, "div": {}, "spl": {}, **(extra or {})}


PRECOS = {"AAAA3": [100, 101, 102, 104, 107, 110, 90],     # sobe até o dia 6 e despenca no dia 7
          "BBBB3": [100, 100, 100, 100, 100, 101, 120],    # parado e dispara no dia 7
          "CCCC3": [100, 100, 100, 101, 101, 101, 101]}


def _coletor(ate: int):
    def coleta(tk):
        v = PRECOS.get(tk, [10.0] * 7)[:ate]
        return {"fech": {d: x for d, x in zip(DIAS + ["2026-11-10"], v)}, "div": {}, "spl": {}}
    return coleta


class Entregas:
    def __init__(self):
        self.chamadas = []

    def __call__(self, n, prefs, destinos, agora=None, enviadas_hoje=0, url_app="", dormir=None):
        self.chamadas.append((n["titulo"], destinos.get("email")))
        return {}


def _participante(email, apelido, ticker):
    a = _conta(email)
    ordem = {"id": f"o-{apelido}", "ts": "2026-11-02T09:00:00", "l": "C", "t": ticker, "q": 300, "x": "2026-11-02"}
    banco.sis_estado_gravar(email, "comp_ordens", {"apelido": apelido, "apelido_k": apelido, "aceite": True, "entrada": "2026-11-02",
                                                     "drip": False, "pend": [ordem]})
    return a


def test_fechamento_publica_ranking_geral_e_avisa_sem_ligas(bd):
    a = _participante("ana@x.com", "ana", "AAAA3")
    b = _participante("bia@x.com", "bia", "BBBB3")
    _participante("cris@x.com", "cris", "CCCC3")
    ent = Entregas()
    r1 = J.executar(agora=datetime(2026, 11, 9, 18, 30), coletor=_coletor(6), entregar=ent)
    assert r1["status"] == "ok" and "ligas" not in r1                      # ligas foram retiradas do fechamento
    assert banco.cfg_ler("comp_ranking")["listas"]["geral_n"] == 3
    assert any("ranking geral" in n["titulo"] for n in banco.notif_listar(a))
    r2 = J.executar(agora=datetime(2026, 11, 10, 18, 30), coletor=_coletor(7), entregar=ent)
    assert r2["status"] == "ok"
    nb = " | ".join(n["titulo"] + " " + n["texto"] for n in banco.notif_listar(b))
    assert "Top 3" in nb or "1º" in nb                                    # bia subiu no geral
    assert "ligas" not in (banco.sis_estado_ler("bia@x.com", "comp_cart")["rank"])
    assert all("R$" not in n["texto"] for n in banco.notif_listar(a))     # nenhum valor em reais nos avisos
    antes = len(banco.notif_listar(a))
    novo = L.avisos_de_posicao({"geral": 50, "em": "2026-11-10"}, {"geral": 9, "n": {"geral": 4}, "em": "2026-11-11"}, "2026-11-11", None,
                               datetime(2026, 11, 11, tzinfo=UTC))
    assert len(novo) == 1
    J.avisar_posicoes({"ana@x.com": novo}, datetime(2026, 11, 11, tzinfo=UTC), ent)
    J.avisar_posicoes({"ana@x.com": novo}, datetime(2026, 11, 11, tzinfo=UTC), ent)
    assert len(banco.notif_listar(a)) == antes + 1
