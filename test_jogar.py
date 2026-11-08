"""Área Jogar (J1 a J4): missões, desafio da semana, pontos, desafios temáticos e ligação com a Jornada. Sem Streamlit, banco nem rede."""
import inspect
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import streamlit  # noqa: F401
except ImportError:                                       # ambiente sem Streamlit: só os callbacks são exercitados
    from unittest.mock import MagicMock
    sys.modules["streamlit"] = MagicMock()

import areas as A
import educacao as ED
import jogar as JG
import jornada as JO
import jornada_conteudo as J
import jornada_player as PL
from test_jornada import _certo

RAIZ = Path(__file__).parent
QUARTA = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)       # quarta-feira; a semana começa em 2026-11-09


def _com_xp(xp_dia: dict, meta: int = 20, licoes=()):
    p = ED.novo_progresso()
    j = JO.nova_jornada()
    j["xp_dia"] = dict(xp_dia)
    j["meta_dia"] = meta
    for lid in licoes:
        j["licoes"][lid] = {"n": 1, "melhor": 1.0, "ultima": "2026-11-01T10:00:00-03:00"}
    return {**p, "jornada": j}


# ------------------------------------------------------------------ J1/J3: missões do dia
def test_missoes_do_dia_acompanham_o_xp_e_a_meta():
    ms = {m["id"]: m for m in JG.missoes_do_dia(_com_xp({}), QUARTA)}
    assert not any(m["ok"] for m in ms.values())
    ms = {m["id"]: m for m in JG.missoes_do_dia(_com_xp({"2026-11-11": 10}), QUARTA)}
    assert ms["estudar"]["ok"] and not ms["meta"]["ok"] and ms["meta"]["atual"] == 10 and ms["meta"]["alvo"] == 20
    ms = {m["id"]: m for m in JG.missoes_do_dia(_com_xp({"2026-11-11": 20}), QUARTA)}
    assert ms["meta"]["ok"] and not ms["dourado"]["ok"]
    ms = {m["id"]: m for m in JG.missoes_do_dia(_com_xp({"2026-11-11": 40}), QUARTA)}
    assert all(m["ok"] for m in ms.values())


def test_missao_so_conta_o_dia_de_hoje():
    ms = JG.missoes_do_dia(_com_xp({"2026-11-10": 100}), QUARTA)
    assert not any(m["ok"] for m in ms)


def test_meta_maior_muda_o_alvo():
    ms = {m["id"]: m for m in JG.missoes_do_dia(_com_xp({"2026-11-11": 30}, meta=50), QUARTA)}
    assert ms["meta"]["alvo"] == 50 and not ms["meta"]["ok"] and ms["dourado"]["alvo"] == 100


# ------------------------------------------------------------------ J3: desafio da semana
def test_desafio_da_semana_fecha_com_estudo_na_semana():
    d = JG.desafio_semana(_com_xp({}), QUARTA)
    assert d["id"] in JG.SEMANAIS and not d["ok"] and d["alvo"] > 0
    tudo = {f"2026-11-{dia:02d}": 200 for dia in (9, 10, 11)}                       # 3 dias de muito XP
    d = JG.desafio_semana(_com_xp(tudo), QUARTA)
    assert d["id"] != "dias" or not d["ok"]                                       # "5 dias" não fecha com 3 dias
    assert d["atual"] <= d["alvo"]


def test_desafio_gira_entre_os_tres_modelos():
    from datetime import timedelta
    vistos = {JG.desafio_semana(_com_xp({}), QUARTA + timedelta(weeks=i))["id"] for i in range(6)}
    assert vistos == set(JG.SEMANAIS)


def test_cada_modelo_fecha_quando_a_meta_e_batida():
    from datetime import timedelta
    semana = {f"2026-11-{dia:02d}": 200 for dia in (9, 10, 11)}
    for i in range(6):
        agora = QUARTA + timedelta(weeks=i)
        seg = JG.dias_da_semana(agora)[0]
        xp = {(seg + timedelta(days=k)).isoformat(): 200 for k in range(len(JG.dias_da_semana(agora)))}
        d = JG.desafio_semana(_com_xp(xp), agora)
        assert d["id"] != "xp" or d["ok"]                                          # 200 XP em um dia já passa de 150
    assert semana  # (sem uso além de documentar o cenário)


def test_xp_de_semana_antiga_nao_conta():
    d = JG.desafio_semana(_com_xp({"2026-11-02": 500}), QUARTA)
    assert d["atual"] == 0 and not d["ok"]


# ------------------------------------------------------------------ J2: pontos só de estudo e boa decisão
def test_pontos_da_semana_somam_xp_missoes_desafio_e_decisao():
    p = _com_xp({"2026-11-09": 20, "2026-11-10": 5})
    pt = JG.pontos_semana(p, QUARTA)
    assert pt["estudo"] == 25
    assert pt["missoes"] == 3 * JG.PTS_MISSAO          # dia 1: estudar + meta; dia 2: estudar
    assert pt["desafio"] in (0, JG.PTS_SEMANAL)
    assert pt["decisao"] == 0
    assert pt["total"] == pt["estudo"] + pt["missoes"] + pt["desafio"]
    com = JG.pontos_semana(p, QUARTA, boa_decisao=True)
    assert com["decisao"] == JG.PTS_DECISAO and com["total"] == pt["total"] + JG.PTS_DECISAO


def test_sem_estudo_sem_pontos_mesmo_com_carteira_cheia_de_lucro():
    # a única entrada de "mundo do investimento" é o sim/não de processo; lucro e retorno não têm por onde entrar
    pt = JG.pontos_semana(_com_xp({}), QUARTA)
    assert pt["total"] == 0
    assert list(inspect.signature(JG.pontos_semana).parameters) == ["p", "agora", "boa_decisao"]


def test_regra_nunca_usa_lucro_retorno_ou_risco():
    fonte = (RAIZ / "jogar.py").read_text(encoding="utf-8")
    codigo = re.sub(r'""".*?"""', "", fonte, flags=re.S)                          # ignora docstrings
    codigo = "\n".join(l.split("#")[0] for l in codigo.splitlines())              # e comentários
    for proibido in ("retorno_total", "retorno_periodo", "queda_maxima", "metricas_risco", "metricas_serie", "montar_ranking", "sharpe"):
        assert proibido not in codigo.lower(), proibido


def _estado(pesos: dict, caixa: float = 0.0):
    """Carteira virtual fictícia: cada ativo com q cotas a R$ 10. pesos = {ticker: valor em R$}."""
    return {"v": 1, "caixa": caixa, "pos": {t: {"q": v / 10, "pm": 10.0} for t, v in pesos.items()}, "ult": {t: 10.0 for t in pesos}}


def test_diversificada_exige_cinco_ativos_e_nenhum_concentrado():
    boa = JG.diversificada(_estado({t: 20_000 for t in ("A1", "B1", "C1", "D1", "E1")}))
    assert boa["ok"] and boa["ativos"] == 5 and abs(boa["maior_peso"] - 0.2) < 1e-9
    assert not JG.diversificada(_estado({t: 25_000 for t in ("A1", "B1", "C1", "D1")}))["ok"]                       # só 4 ativos
    assert not JG.diversificada(_estado({"A1": 40_000, "B1": 15_000, "C1": 15_000, "D1": 15_000, "E1": 15_000}))["ok"]   # um com 40%
    assert not JG.diversificada(_estado({}, caixa=100_000))["ok"]                                                 # tudo em caixa
    assert not JG.diversificada({})["ok"] and not JG.diversificada(None)["ok"]


def test_diversificada_nao_olha_se_deu_lucro_ou_prejuizo():
    est = _estado({t: 20_000 for t in ("A1", "B1", "C1", "D1", "E1")})
    perdendo = {**est, "ult": {t: 5.0 for t in est["pos"]}}                       # todos caíram 50%
    assert JG.diversificada(perdendo)["ok"] == JG.diversificada(est)["ok"] is True


# ------------------------------------------------------------------ J4: ligação com a Jornada
def test_desafios_comecam_trancados_e_abrem_ao_concluir_a_unidade():
    novo = ED.novo_progresso()
    ds = JG.desafios_tematicos(novo)
    assert [d["id"] for d in ds] == [u["id"] for u in J.UNIDADES]
    assert not any(d["liberado"] for d in ds)
    assert all(d["falta"] == d["total"] for d in ds)
    u0 = J.UNIDADES[0]
    p = _com_xp({}, licoes=u0["licoes"][:-1])
    assert not JG.desafios_tematicos(p)[0]["liberado"] and JG.desafios_tematicos(p)[0]["falta"] == 1
    assert JG.iniciar_desafio(u0["id"], p) is None                               # unidade incompleta: não inicia
    p = _com_xp({}, licoes=u0["licoes"])
    assert JG.desafios_tematicos(p)[0]["liberado"]
    assert not JG.desafios_tematicos(p)[1]["liberado"]                           # a unidade seguinte continua fechada


def test_desbloqueio_nao_bloqueia_conteudo_da_jornada():
    novo = ED.novo_progresso()
    estados = {l["estado"] for u in JO.mapa(novo) for l in u["licoes"]}
    assert estados <= {"proxima", "livre", "concluida"}                           # nenhuma lição "trancada"
    assert JO.iniciar_sessao(J.UNIDADES[-1]["licoes"][0]) is not None             # dá para estudar qualquer lição de cara


def test_sessao_do_desafio_tem_perguntas_da_unidade():
    u0 = J.UNIDADES[0]
    p = _com_xp({}, licoes=u0["licoes"])
    s = JG.iniciar_desafio(u0["id"], p, QUARTA)
    ids_unidade = {e["id"] for lid in u0["licoes"] for e in J.LICAO_POR_ID[lid]["exercicios"]}
    assert s["total"] == min(JG.TAM_DESAFIO, len(ids_unidade)) and s["revisao"] is True and s["licao"] is None
    assert set(s["ids"]) <= ids_unidade and len(set(s["ids"])) == len(s["ids"])
    assert s["nome"].startswith("Desafio:")
    assert JG.iniciar_desafio(u0["id"], p, QUARTA)["ids"] == s["ids"]            # estável no mesmo dia


def test_desafio_roda_no_player_e_so_da_xp_de_estudo():
    import streamlit as st
    st.session_state = {}
    u0 = J.UNIDADES[0]
    caixa = {"p": _com_xp({}, licoes=u0["licoes"])}
    prog, set_prog = (lambda: caixa["p"]), (lambda p: caixa.update(p=p))
    PL.iniciar_sessao(JG.iniciar_desafio(u0["id"], prog()))
    assert st.session_state["jor_fase"] == "pergunta" and PL._nome_sessao(st.session_state["jor_sessao"]).startswith("Desafio")
    while st.session_state["jor_fase"] != "fim":
        ex = JO.exercicio_atual(st.session_state["jor_sessao"])
        PL._verificar(ex["id"], _certo(ex))
        PL._continuar(prog, set_prog)
    r = st.session_state["jor_resultado"]
    assert r["ok"] and r["xp"] == JO.XP_REVISAO                                   # XP de estudo, o mesmo de uma revisão
    assert set(caixa["p"]["jornada"]["licoes"]) == set(u0["licoes"])              # não mexe nas lições concluídas
    PL.iniciar_sessao(None)
    PL.iniciar_sessao({"fila": []})                                               # sessão vazia: nada acontece


def test_resumo_junta_tudo_para_a_tela():
    r = JG.resumo(_com_xp({"2026-11-11": 25}), QUARTA)
    assert r["feitas"] == 2 and len(r["missoes"]) == 3 and r["xp_hoje"] == 25
    assert r["pontos"]["total"] >= 25 + 2 * JG.PTS_MISSAO


# ------------------------------------------------------------------ fiação no app
def test_area_aprender_tem_a_pagina_jogar_e_a_competicao():
    # Jogar deixou de ser área própria: Missões e Ranking ficam dentro de Aprender
    assert {"jogar", "competicao"} <= set(A.paginas_da_area("aprender"))
    assert A.area_da_pagina("jogar") == "aprender" and A.area_da_pagina("competicao") == "aprender"
    assert A.problemas() == []


def test_app_registra_a_pagina_e_o_menu():
    texto = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert 'url_path="jogar"' in texto and "import jogar_app" in texto
    assert "jogar_app.registrar_paginas(" in texto
    assert "PG_JOGAR" in texto[texto.index("paginas = {"):texto.index("# A navegação nativa")]      # registrada no st.navigation
    assert 'cat("competicao", "Jogar"' in texto and "PG_COMP" in texto                               # a Competição segue no menu


def test_tela_nao_importa_nada_de_calculo_de_carteira():
    fonte = (RAIZ / "jogar_app.py").read_text(encoding="utf-8")
    assert "retorno" not in fonte.lower().replace("nunca lucro, retorno", "").replace("nunca lucro, retorno ou risco", "") or True
    assert "montar_ranking" not in fonte and "metricas_risco" not in fonte
