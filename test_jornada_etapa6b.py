"""Etapa 6b da Jornada: liga de estudo (opcional), estudo com dado real no fim da unidade, banco e PWA."""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import streamlit  # noqa: F401
except ImportError:                                       # ambiente sem Streamlit: só a lógica e os callbacks são exercitados
    from unittest.mock import MagicMock
    sys.modules["streamlit"] = MagicMock()

import educacao as ED
import jornada as JO
import jornada_app as APP
import jornada_conteudo as J
import jornada_liga as JL
from test_jornada import T0, _fazer

RAIZ = Path(__file__).parent


def _prog_com_xp(dias_xp: dict):
    p = ED.normalizar({})
    j = JO._jor(p)
    j["xp_dia"] = dict(dias_xp)
    return {**p, "jornada": JO.normalizar_jornada(j)}


# ------------------------------------------------------------------ semana e XP semanal
def test_semana_comeca_na_segunda_e_usa_iso():
    dom = date(2026, 11, 8)                                # domingo
    assert JL.inicio_semana(dom) == date(2026, 11, 2)
    assert JL.inicio_semana(date(2026, 11, 2)) == date(2026, 11, 2)
    assert JL.semana_id(dom) == "2026-W45" and JL.semana_id(date(2026, 11, 9)) == "2026-W46"


def test_xp_semana_soma_so_a_semana_atual_e_so_estudo():
    p = _prog_com_xp({"2026-11-01": 50, "2026-11-02": 10, "2026-11-05": 15, "2026-11-08": 20})
    assert JL.xp_semana(p, T0) == 45                       # 02, 05 e 08; o dia 01 é da semana anterior
    assert JL.xp_semana(ED.normalizar({}), T0) == 0


def test_xp_semana_cresce_com_licao_real():
    p, r = _fazer(ED.normalizar({}), "l_risco", T0)
    assert JL.xp_semana(p, T0) == r["xp"] > 0


# ------------------------------------------------------------------ documento da pessoa
def test_sanear_descarta_lixo_e_limita():
    d = JL.sanear({"ligado": 1, "semana": "2026-W45", "xp": 10**9, "apelido": "ab", "extra": "x"})
    assert d == {"v": 1, "ligado": True, "semana": "2026-W45", "xp": JL.XP_SEMANA_MAX, "apelido": ""}   # apelido curto demais é descartado
    assert JL.sanear(None) == {"v": 1, "ligado": False, "semana": "", "xp": 0, "apelido": ""}
    assert JL.sanear({"semana": "abc", "xp": "zzz"})["semana"] == "" and JL.sanear({"xp": -5})["xp"] == 0
    assert "extra" not in JL.sanear({"extra": 1}) and "email" not in JL.sanear({"email": "a@b.c"})


def test_ligar_publica_xp_e_desligar_apaga_tudo():
    p, _ = _fazer(ED.normalizar({}), "l_risco", T0)
    on = JL.definir_ligado({}, True, p, "Maria_Estuda", T0)
    assert on["ligado"] and on["xp"] == JL.xp_semana(p, T0) and on["semana"] == "2026-W45" and on["apelido"] == "Maria_Estuda"
    off = JL.definir_ligado(on, False)
    assert off["ligado"] is False and off["xp"] == 0 and off["semana"] == ""


def test_atualizar_nao_muda_a_opcao():
    p = _prog_com_xp({"2026-11-03": 30})
    d = JL.atualizar({"ligado": False}, p, "Joao_Silva", T0)
    assert d["ligado"] is False and d["xp"] == 30
    d = JL.atualizar({"ligado": True}, p, "Joao_Silva", T0)
    assert d["ligado"] is True


def test_pode_participar_exige_apelido_valido():
    assert JL.pode_participar("Maria_Estuda")[0]
    assert not JL.pode_participar("")[0] and not JL.pode_participar("<b>x</b>")[0]


# ------------------------------------------------------------------ ranking
def _linha(ap, xp, ligado=True, sem="2026-W45", eu=False):
    return {"apelido": ap, "xp": xp, "ligado": ligado, "semana": sem, "eu": eu}


def test_ranking_so_mostra_quem_ligou_e_ordena():
    r = JL.montar([_linha("Ana_Lima", 40), _linha("Bia_Souza", 90), _linha("Caio_Dias", 70, ligado=False), _linha("Davi_Reis", 10, eu=True)], "2026-W45")
    assert [x["apelido"] for x in r] == ["Bia_Souza", "Ana_Lima", "Davi_Reis"]
    assert [x["pos"] for x in r] == [1, 2, 3]
    assert "Caio_Dias" not in str(r)


def test_ranking_empate_divide_posicao_e_semana_velha_vale_zero():
    r = JL.montar([_linha("Ana_Lima", 40), _linha("Bia_Souza", 40), _linha("Caio_Dias", 99, sem="2026-W44"), _linha("Davi_Reis", 5)], "2026-W45")
    assert [(x["apelido"], x["pos"], x["xp"]) for x in r] == [("Ana_Lima", 1, 40), ("Bia_Souza", 1, 40), ("Davi_Reis", 3, 5), ("Caio_Dias", 4, 0)]


def test_ranking_sem_apelido_repetido_e_sem_linhas_invalidas():
    r = JL.montar([_linha("Ana_Lima", 40), _linha("ana_lima", 30), _linha("", 99), _linha("<script>", 99), None, "x"], "2026-W45")
    assert [x["apelido"] for x in r] == ["Ana_Lima"]
    assert JL.montar([], "2026-W45") == [] and JL.montar(None, "2026-W45") == []


def test_ranking_limita_o_topo():
    linhas = [_linha(f"Aluno_{i:03d}", i) for i in range(JL.TOPO + 20)]
    assert len(JL.montar(linhas, "2026-W45")) == JL.TOPO


def test_texto_posicao():
    r = JL.montar([_linha("Ana_Lima", 40, eu=True), _linha("Bia_Souza", 90)], "2026-W45")
    assert "2º lugar entre 2" in JL.texto_posicao(r) and "40 XP" in JL.texto_posicao(r)
    assert "ainda não aparece" in JL.texto_posicao([])
    r0 = JL.montar([_linha("Ana_Lima", 0, eu=True)], "2026-W45")
    assert "Estude hoje" in JL.texto_posicao(r0)


def test_ranking_nunca_expoe_email():
    r = JL.montar([{**_linha("Ana_Lima", 40), "email": "ana@x.com"}], "2026-W45")
    assert "email" not in r[0] and "@" not in json.dumps(r)


# ------------------------------------------------------------------ estudo com dado real no fim da unidade
def test_estudo_real_valido_e_no_validar_conteudo():
    assert JO.validar_conteudo() == []
    for uid in JO.ESTUDO_REAL:
        assert uid in J.UNIDADE_POR_ID


def test_estudo_real_so_depois_da_unidade_completa():
    p = ED.normalizar({})
    assert not JO.estudo_real_liberado(p, "u_riscos")
    u = J.UNIDADE_POR_ID["u_riscos"]
    for lid in u["licoes"][:-1]:
        p, _ = _fazer(p, lid, T0)
    assert not JO.estudo_real_liberado(p, "u_riscos")
    p, _ = _fazer(p, u["licoes"][-1], T0)
    assert JO.estudo_real_liberado(p, "u_riscos")
    assert not JO.estudo_real_liberado(p, "u_imp") and not JO.estudo_real_liberado(p, "nao_existe")   # sem roteiro: nada é oferecido


def test_estudo_real_nao_da_xp():
    p, _ = _fazer(ED.normalizar({}), "l_risco", T0)
    antes = JO.xp_total(p)
    p2 = ED.registrar_ativo_estudado(p)
    assert JO.xp_total(p2) == antes


def test_card_do_fim_da_unidade_escapa_html_e_avisa_que_e_opcional():
    h = APP.html_estudo_real({"titulo": "<b>x</b>", "dica": "<i>y</i>"})
    assert "<b>x</b>" not in h and "&lt;b&gt;" in h and "Opcional" in h


# ------------------------------------------------------------------ banco e PWA
def test_banco_tem_funcoes_e_chave_da_liga_de_estudo():
    src = (RAIZ / "banco.py").read_text(encoding="utf-8")
    assert "def edu_liga_ranking" in src and '"edu_liga")' in src and '"comp_ligas", "edu_liga")' in src
    trecho = src[src.index("def edu_liga_ranking"):src.index("def sis_comp_ligas_def")]
    linha_saida = trecho.split("out.append")[1].split("\n")[0]
    assert "SemPermissao" in trecho and '"email":' not in linha_saida          # confere membro; as linhas devolvidas não levam o e-mail


def test_service_worker_e_manifest():
    sw = (RAIZ / "sw.js").read_text(encoding="utf-8")
    assert "bolsa-para-todos-v2" in sw and "icon-maskable-512.png" in sw and "res.ok" in sw
    for arq in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "manifest.webmanifest", "index.html"):
        assert (RAIZ / arq).exists(), arq
    for caminho in ("manifest.webmanifest", "static/manifest.json"):
        m = json.loads((RAIZ / caminho).read_text(encoding="utf-8"))
        assert m["name"] and m["display"] == "standalone" and m["lang"] == "pt-BR"
