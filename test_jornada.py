from datetime import datetime, timedelta, timezone

import edu_conteudo as E
import educacao as ED
import jornada as JO
import jornada_conteudo as J

T0 = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)   # 12h em Brasília


def _certo(ex):
    t = ex["tipo"]
    if t in ("escolha", "completar", "vf"):
        return ex["correta"]
    if t == "ordenar":
        return list(ex["itens"])
    return {a: b for a, b in ex["pares"]}


def _errado(ex):
    t = ex["tipo"]
    if t in ("escolha", "completar"):
        return (ex["correta"] + 1) % len(ex["opcoes"])
    if t == "vf":
        return not ex["correta"]
    if t == "ordenar":
        return list(reversed(ex["itens"]))
    return {a: ex["pares"][0][1] for a, _ in ex["pares"]}


def _fazer(p, lid, agora, errar_primeiro=False):
    s = JO.iniciar_sessao(lid)
    errou = False
    while not JO.terminada(s):
        ex = JO.exercicio_atual(s)
        if errar_primeiro and not errou:
            errou = True
            ok, s = JO.responder(s, _errado(ex))
            assert not ok
        else:
            ok, s = JO.responder(s, _certo(ex))
            assert ok
    return JO.concluir_sessao(p, s, agora)


def test_conteudo_valido():
    assert JO.validar_conteudo() == []


def test_corrigir_cada_tipo_e_resposta_invalida():
    for ex in J.EX_POR_ID.values():
        assert JO.corrigir(ex, _certo(ex)) is True
        assert JO.corrigir(ex, _errado(ex)) is False
        assert JO.corrigir(ex, None) is False
    ex = next(e for e in J.EX_POR_ID.values() if e["tipo"] == "escolha")
    assert JO.corrigir(ex, True) is False            # bool não vale como índice


def test_erro_volta_ao_fim_e_nao_bloqueia():
    s = JO.iniciar_sessao("l_risco")
    primeiro = s["fila"][0]
    ok, s = JO.responder(s, _errado(JO.exercicio_atual(s)))
    assert not ok and s["fila"][-1] == primeiro and s["feitos"] == 0 and s["erros_ids"] == [primeiro]
    assert len(s["fila"]) == s["total"]               # nada se perde


def test_licao_perfeita_e_com_erro():
    p = ED.novo_progresso()
    p, r = _fazer(p, "l_risco", T0)
    assert r["xp"] == JO.XP_LICAO + JO.XP_BONUS_PERFEITA and r["perfeita"]
    p, r = _fazer(p, "l_juros", T0, errar_primeiro=True)
    assert r["xp"] == JO.XP_LICAO and not r["perfeita"]
    assert JO.xp_total(p) == 25 and JO.erros_para_revisar(p) == 1


def test_revisao_limpa_erro_e_da_xp():
    p, _ = _fazer(ED.novo_progresso(), "l_juros", T0, errar_primeiro=True)
    s = JO.iniciar_revisao(p)
    assert s and s["revisao"] and s["total"] == 1
    while not JO.terminada(s):
        _, s = JO.responder(s, _certo(JO.exercicio_atual(s)))
    p, r = JO.concluir_sessao(p, s, T0)
    assert r["xp"] == JO.XP_REVISAO and JO.erros_para_revisar(p) == 0 and JO.iniciar_revisao(p) is None


def test_ofensiva_meta_e_fuso():
    p = ED.novo_progresso()
    for d in range(3):                                # 3 dias seguidos
        p, _ = _fazer(p, "l_risco", T0 - timedelta(days=2 - d))
    assert JO.ofensiva(p, T0) == 3
    assert JO.ofensiva(p, T0 + timedelta(days=1)) == 3        # hoje ainda sem estudo: sequência de ontem viva
    assert JO.ofensiva(p, T0 + timedelta(days=2)) == 0        # passou um dia inteiro: zerou
    assert JO.meta_atingida(p, T0) is False and JO.xp_hoje(p, T0) == 15
    p, _ = _fazer(p, "l_juros", T0)
    assert JO.meta_atingida(p, T0)                            # 15 + 15 >= 20
    madrugada = datetime(2026, 11, 8, 2, 30, tzinfo=timezone.utc)   # ainda dia 7 em Brasília
    assert JO.hoje(madrugada).isoformat() == "2026-11-07"


def test_mapa_nada_trancado():
    p = ED.novo_progresso()
    estados = [l["estado"] for l in JO.mapa(p)[0]["licoes"]]
    assert estados == ["proxima", "livre", "livre"]
    p, _ = _fazer(p, "l_risco", T0)
    estados = [l["estado"] for l in JO.mapa(p)[0]["licoes"]]
    assert estados == ["concluida", "proxima", "livre"]


def test_integra_com_progresso_da_conta_e_lixo():
    p, _ = _fazer(ED.novo_progresso(), "l_risco", T0)
    q = ED.normalizar(p)                                       # o que é gravado/lido no perfil
    assert q["jornada"]["xp"] == 15 and "l_risco" in q["jornada"]["licoes"]
    sujo = ED.normalizar({"jornada": {"xp": "abc", "licoes": {"nao_existe": {}}, "erros": ["x"], "xp_dia": {"data_ruim": 5}, "meta_dia": 9999}})
    assert sujo["jornada"]["xp"] == 0 and sujo["jornada"]["licoes"] == {} and sujo["jornada"]["erros"] == []
    assert sujo["jornada"]["xp_dia"] == {} and sujo["jornada"]["meta_dia"] == 200
    assert ED.normalizar(None)["jornada"]["xp"] == 0


def test_aulas_referenciadas_existem():
    assert all(l["aula"] in E.POR_ID for l in J.LICOES)


def test_icones_svg_validos():
    import xml.etree.ElementTree as ET
    import jornada_icones as IC
    for nome in IC.ICONES:
        ET.fromstring(IC.svg(nome))                    # XML bem formado
        assert IC.uri(nome).startswith("data:image/svg+xml;base64,")
    assert IC.svg("nao_existe") == IC.svg("estrela")   # nome desconhecido não quebra
    assert all(IC.existe(l["svg"]) for u in JO.mapa(ED.novo_progresso()) for l in u["licoes"])
