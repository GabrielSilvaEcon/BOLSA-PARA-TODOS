"""Competição · etapa 2 (ligas de amigos e avisos de posição). Sem internet: SQLite temporário e cotações falsas."""
import json
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


# ------------------------------------------------------------------ códigos, nomes, documento da pessoa
def test_codigo_novo_e_valido():
    for _ in range(50):
        c = L.novo_codigo()
        assert len(c) == 8 and L.codigo_valido(c) == c
        assert not set(c) & set("01ILO")


@pytest.mark.parametrize("txt,esperado", [("k7qm-2xpa", "K7QM2XPA"), (" K7QM 2XPA ", "K7QM2XPA"), ("K7QM2XP", None), ("K7QM2XP0", None),
                                          ("", None), (None, None), ("K7QM2XPAA", None), ("K7QM2XP!", None)])
def test_codigo_valido(txt, esperado):
    assert L.codigo_valido(txt) == esperado


def test_convite_por_link_e_colado():
    assert L.extrair_convite("https://app.exemplo.com/competicao?liga=K7QM2XPA") == "K7QM2XPA"
    assert L.codigo_valido("https://app.exemplo.com/competicao?liga=k7qm-2xpa&x=1") == "K7QM2XPA"
    assert L.extrair_convite("https://app.exemplo.com/competicao?liga=<script>") is None
    assert L.link_convite("https://app.exemplo.com/", "K7QM2XPA") == "https://app.exemplo.com/competicao?liga=K7QM2XPA"


@pytest.mark.parametrize("nome,ok", [("Turma da faculdade", True), ("Liga dos Amigos 2026", True), ("ab", False), ("<b>x</b>", False),
                                     ("a" * 31, False), ("admin oficial", False), ("  ", False)])
def test_nome_valido(nome, ok):
    assert L.nome_valido(nome)[0] is ok


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


def test_definicao_nao_guarda_email():
    d = L.nova_definicao("Turma", "Dono@Exemplo.com", 30)
    assert "@" not in json.dumps(d) and d["dono_h"] == L.hash_dono("dono@exemplo.com")
    assert L.nova_definicao("T", "a@b.com", 9999)["max"] == L.MAX_MEMBROS_TETO
    assert "dono_h" not in L.definicao_publica("K7QM2XPA", d)


# ------------------------------------------------------------------ ranking das ligas (lógica pura)
def _est(retornos: list[float]) -> dict:
    hist = [{"d": (date(2026, 11, 2) + timedelta(days=i)).isoformat(), "p": round(C.CAPITAL_INICIAL * (1 + r), 2)} for i, r in enumerate(retornos)]
    e = C.novo_estado("2026-11-02")
    e["hist"] = hist
    return e


def test_montar_ligas_ranking_e_posicoes():
    part = [{"apelido": "ana", "email": "a@x", "estado": _est([0, .01, .02, .03, .04, .05])},
            {"apelido": "bia", "email": "b@x", "estado": _est([0, 0, 0, 0, 0, .02])},
            {"apelido": "cris", "email": "c@x", "estado": _est([])},                           # ainda sem nenhum fechamento
            {"apelido": "dani", "email": "d@x", "estado": _est([0, .1, .1, .1, .1, .1])}]       # fora da liga
    defs = {"K7QM2XPA": L.nova_definicao("Turma", "a@x", 30)}
    ligas = {"a@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 2), True), "b@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 2)),
             "c@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 3))}
    r = L.montar_ligas(defs, ligas, part, date(2026, 11, 7), {L.hash_dono("a@x"): "ana"})
    doc = r["docs"]["K7QM2XPA"]
    assert [x["apelido"] for x in doc["listas"]["geral"]] == ["ana", "bia"]
    assert doc["aguardando"] == ["cris"] and doc["dono"] == "ana" and doc["membros"] == 3
    assert r["posicoes"]["a@x"]["K7QM2XPA"]["geral"] == 1 and r["posicoes"]["b@x"]["K7QM2XPA"]["geral"] == 2
    assert "d@x" not in r["posicoes"]
    assert "@" not in json.dumps(doc) and "email" not in json.dumps(doc)


def test_liga_cheia_fica_com_quem_entrou_primeiro():
    part = [{"apelido": n, "email": f"{n}@x", "estado": _est([0, .01, .02, .03, .04, .05])} for n in ("a", "b", "c")]
    defs = {"K7QM2XPA": {"nome": "Mini", "dono_h": "h", "max": 2}}
    ligas = {"a@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 2)), "b@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 3)),
             "c@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 4))}
    r = L.montar_ligas(defs, ligas, part, date(2026, 11, 7))
    assert r["docs"]["K7QM2XPA"]["membros"] == 2
    assert r["posicoes"]["c@x"]["K7QM2XPA"]["cheia"] is True and "geral" not in r["posicoes"]["c@x"]["K7QM2XPA"]


def test_membro_suspenso_ou_sem_participacao_nao_entra():
    part = [{"apelido": "ana", "email": "a@x", "estado": _est([0, .01, .02, .03, .04, .05])}]
    defs = {"K7QM2XPA": L.nova_definicao("Turma", "a@x", 30)}
    ligas = {"a@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 2)), "fora@x": L.adicionar({}, "K7QM2XPA", date(2026, 11, 2))}
    assert L.montar_ligas(defs, ligas, part, date(2026, 11, 7))["docs"]["K7QM2XPA"]["membros"] == 1


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


def test_criar_ver_e_encerrar_liga(bd):
    dono, amigo, intruso = _conta("dono@x.com"), _conta("amigo@x.com"), _conta("intruso@x.com")
    cod = banco.comp_liga_criar(dono, L.nova_definicao("Turma", dono.email, 30, datetime(2026, 11, 8)))
    assert L.codigo_valido(cod) == cod
    pub = banco.comp_liga_definicao(amigo, cod)
    assert pub["nome"] == "Turma" and "dono_h" not in pub and "dono" not in pub
    assert banco.comp_liga_definicao(amigo, "ZZZZZZZZ") is None
    with pytest.raises(ValueError):
        banco.comp_liga_definicao(amigo, "../../etc")
    # os dados guardados não têm e-mail de ninguém
    linhas = banco._selecionar("config_sistema", {"id": ("comeca", "comp_liga|")}, ["id", "dados"])
    assert linhas and "@" not in json.dumps([banco._de_js(l["dados"]) for l in linhas])
    with pytest.raises(banco.SemPermissao):
        banco.comp_liga_encerrar(intruso, cod)
    with pytest.raises(banco.SemPermissao):
        banco.comp_liga_encerrar(amigo, cod)
    assert banco.comp_liga_definicao(amigo, cod) is not None
    assert banco.comp_liga_encerrar(dono, cod) is True
    assert banco.comp_liga_definicao(amigo, cod) is None
    assert banco.comp_liga_encerrar(dono, cod) is False
    with pytest.raises(banco.SemPermissao):
        banco.comp_liga_encerrar(None, cod)


def test_ranking_da_liga_so_para_membros(bd):
    dono, amigo, intruso = _conta("dono@x.com"), _conta("amigo@x.com"), _conta("intruso@x.com")
    cod = banco.comp_liga_criar(dono, L.nova_definicao("Turma", dono.email, 30))
    banco.sis_comp_publicar(L.CFG_LIGA_RANK + cod, {"dia": "2026-11-09", "nome": "Turma", "listas": {"geral": []}})
    with pytest.raises(banco.SemPermissao):
        banco.comp_liga_ranking_ler(intruso, cod)
    banco.comp_ligas_gravar(amigo, L.adicionar({}, cod, date(2026, 11, 8)))
    assert banco.comp_liga_ranking_ler(amigo, cod)["nome"] == "Turma"
    # trocar o código no documento de OUTRA pessoa não dá acesso: cada um só lê o próprio documento
    with pytest.raises(banco.SemPermissao):
        banco.comp_liga_ranking_ler(intruso, cod)
    assert banco.comp_liga_contagem(amigo, cod) == 1
    with pytest.raises(banco.SemPermissao):
        banco.comp_ligas_ler(None)


def test_publicar_so_aceita_chaves_conhecidas(bd):
    with pytest.raises(ValueError):
        banco.sis_comp_publicar("plano|abc", {})
    with pytest.raises(ValueError):
        banco.sis_comp_publicar("comp_lr|curto", {})
    with pytest.raises(ValueError):
        banco.sis_comp_todos("perfis")


def test_excluir_conta_apaga_as_ligas_do_dono(bd):
    dono, outro = _conta("dono@x.com"), _conta("outro@x.com")
    c1 = banco.comp_liga_criar(dono, L.nova_definicao("Minha", dono.email, 30))
    c2 = banco.comp_liga_criar(outro, L.nova_definicao("Dele", outro.email, 30))
    banco.sis_apagar_conta(dono.id, dono.email)
    assert c1 not in banco.sis_comp_ligas_def() and c2 in banco.sis_comp_ligas_def()


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


def test_fechamento_publica_liga_avisa_e_respeita_privacidade(bd):
    a = _participante("ana@x.com", "ana", "AAAA3")
    b = _participante("bia@x.com", "bia", "BBBB3")
    c = _participante("cris@x.com", "cris", "CCCC3")
    d = _participante("dani@x.com", "dani", "CCCC3")                      # fora da liga
    cod = banco.comp_liga_criar(a, L.nova_definicao("Turma", a.email, 30, datetime(2026, 11, 2)))
    for p in (a, b, c):
        banco.comp_ligas_gravar(p, L.adicionar({}, cod, date(2026, 11, 2), dono=(p is a)))
    banco.comp_ligas_gravar(b, {**L.adicionar({}, cod, date(2026, 11, 2)), "avisos": {"liga": False, "global": True}})   # bia não quer avisos de liga
    ent = Entregas()

    r1 = J.executar(agora=datetime(2026, 11, 9, 18, 30), coletor=_coletor(6), entregar=ent)
    assert r1["status"] == "ok" and r1["ligas"] == 1
    doc = banco.cfg_ler(L.CFG_LIGA_RANK + cod)
    assert [x["apelido"] for x in doc["listas"]["geral"]] == ["ana", "bia", "cris"] and doc["dono"] == "ana" and doc["membros"] == 3
    assert "dani" not in json.dumps(doc) and "@" not in json.dumps(doc)
    assert banco.cfg_ler("comp_ranking")["listas"]["geral_n"] == 4        # o ranking geral continua igual
    avisos_a = banco.notif_listar(a)
    assert any("ranking geral" in n["titulo"] for n in avisos_a) and any("liga" in n["titulo"].lower() for n in avisos_a)
    assert not any("liga" in n["titulo"].lower() for n in banco.notif_listar(b))     # preferência respeitada
    assert not any("liga" in n["titulo"].lower() for n in banco.notif_listar(d))

    # 2º fechamento: bia dispara e passa a ana
    r2 = J.executar(agora=datetime(2026, 11, 10, 18, 30), coletor=_coletor(7), entregar=ent)
    assert r2["status"] == "ok"
    doc2 = banco.cfg_ler(L.CFG_LIGA_RANK + cod)
    assert [x["apelido"] for x in doc2["listas"]["geral"]][0] == "bia"
    na = banco.notif_listar(a)
    textos = " | ".join(n["titulo"] + " " + n["texto"] for n in na)
    assert "caiu para" in textos                                          # ana perdeu a ponta
    nb = " | ".join(n["titulo"] + " " + n["texto"] for n in banco.notif_listar(b))
    assert "Top 3" in nb or "1º" in nb                                    # bia subiu no geral (avisos globais ligados)
    assert all("R$" not in n["texto"] for n in na)                        # nenhum valor em reais nos avisos
    # posição guardada na carteira de cada um
    assert banco.sis_estado_ler("bia@x.com", "comp_cart")["rank"]["ligas"][cod]["geral"] == 1
    # o mesmo aviso gravado duas vezes (reexecução) não duplica
    antes = len(banco.notif_listar(a))
    novo = L.avisos_de_posicao({"geral": 50, "em": "2026-11-10"}, {"geral": 9, "n": {"geral": 4}, "em": "2026-11-11"}, "2026-11-11", None,
                               datetime(2026, 11, 11, tzinfo=UTC))
    assert len(novo) == 1
    J.avisar_posicoes({"ana@x.com": novo}, datetime(2026, 11, 11, tzinfo=UTC), ent)
    J.avisar_posicoes({"ana@x.com": novo}, datetime(2026, 11, 11, tzinfo=UTC), ent)
    assert len(banco.notif_listar(a)) == antes + 1


def test_falha_nas_ligas_nao_derruba_o_ranking_geral(bd, monkeypatch):
    a = _participante("ana@x.com", "ana", "AAAA3")
    monkeypatch.setattr(banco, "sis_comp_ligas_def", lambda *x, **k: (_ for _ in ()).throw(RuntimeError("quebrou")))
    r = J.executar(agora=datetime(2026, 11, 9, 18, 30), coletor=_coletor(6), entregar=Entregas())
    assert r["status"] == "ok" and banco.cfg_ler("comp_ranking")["listas"]["geral_n"] == 1


def test_liga_encerrada_nao_e_publicada_e_dono_suspenso_nao_conta(bd):
    a = _participante("ana@x.com", "ana", "AAAA3")
    b = _participante("bia@x.com", "bia", "BBBB3")
    cod = banco.comp_liga_criar(a, L.nova_definicao("Turma", a.email, 30))
    banco.comp_ligas_gravar(a, L.adicionar({}, cod, date(2026, 11, 2), True))
    banco.comp_ligas_gravar(b, L.adicionar({}, cod, date(2026, 11, 2)))
    banco.sis_atualizar_conta(b.id, {"status": "suspensa"})
    J.executar(agora=datetime(2026, 11, 9, 18, 30), coletor=_coletor(6), entregar=Entregas())
    assert banco.cfg_ler(L.CFG_LIGA_RANK + cod)["membros"] == 1           # suspensa fica de fora
