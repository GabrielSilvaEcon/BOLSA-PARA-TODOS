"""Etapa 6 da Jornada: sons, preferência de som, conquistas novas, animações (HTML puro) e lembrete de estudo."""
import io
import sys
import wave
from datetime import datetime, timedelta, timezone

try:
    import streamlit  # noqa: F401
except ImportError:                                       # ambiente sem Streamlit: só os callbacks são exercitados
    from unittest.mock import MagicMock
    sys.modules["streamlit"] = MagicMock()

import streamlit as st

import educacao as ED
import jornada as JO
import jornada_app as APP
import jornada_player as PL
import jornada_som as SOM
import notif as N
from test_jornada import T0, _certo, _errado, _fazer


# ------------------------------------------------------------------ sons
def test_sons_sao_wav_validos_curtos_e_sem_distorcao():
    import struct
    for nome in SOM.NOMES:
        b = SOM.wav(nome)
        with wave.open(io.BytesIO(b), "rb") as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SOM.TAXA)
            quadros = w.readframes(w.getnframes())
        amostras = struct.unpack(f"<{len(quadros) // 2}h", quadros)
        assert 0.15 < SOM.duracao(nome) < 1.0                          # curtos: menos de 1 s
        assert len(b) < 40_000                                         # leves
        assert max(abs(a) for a in amostras) <= SOM.VOLUME * 32767 + 2   # nunca passa do volume combinado (sem distorção)
        assert max(abs(a) for a in amostras) > 3000                    # e não é silêncio
        assert abs(amostras[0]) < 600 and abs(amostras[-1]) < 60       # começa e termina perto de zero: sem estalo
    assert SOM.wav("acerto") is SOM.wav("acerto")                      # cache


def test_sons_sao_diferentes_entre_si_e_nome_desconhecido_nao_existe():
    assert len({SOM.wav(n) for n in SOM.NOMES}) == len(SOM.NOMES)
    assert SOM.existe("acerto") and not SOM.existe("nada")
    assert SOM.som_da_resposta(True) == "acerto" and SOM.som_da_resposta(False) == "erro"
    assert SOM.som_do_resultado({"meta_nova": True}) == "meta" and SOM.som_do_resultado({"meta_nova": False}) == "concluida"


# ------------------------------------------------------------------ preferência de som
def test_som_padrao_ligado_e_gravado_na_conta():
    p = ED.novo_progresso()
    assert JO.som_ligado(p)
    p = JO.definir_som(p, False)
    assert not JO.som_ligado(p)
    assert not JO.som_ligado(ED.normalizar(p))                          # sobrevive à normalização que lê/grava no perfil
    p, _ = _fazer(p, "l_risco", T0)
    assert not JO.som_ligado(p)                                         # concluir lição não religa o som
    assert not JO.som_ligado(JO.definir_meta(p, 30))                    # nem mudar a meta
    assert JO.resumo(p, T0)["som"] is False


def test_som_valor_invalido_volta_ao_padrao():
    for lixo in ("false", 0, None, "nao", []):
        assert ED.normalizar({"jornada": {"som": lixo}})["jornada"]["som"] is True
    assert ED.normalizar({"jornada": {"som": False}})["jornada"]["som"] is False
    assert JO.som_ligado({})                                            # perfil antigo, sem o campo: som ligado


# ------------------------------------------------------------------ resultado da sessão
def test_meta_nova_so_na_sessao_que_bate_a_meta():
    p = ED.novo_progresso()                                             # meta 20: 15 XP por lição perfeita
    p, r1 = _fazer(p, "l_risco", T0)
    assert not r1["meta_nova"] and not r1["meta_atingida"] and r1["primeiro_do_dia"]
    p, r2 = _fazer(p, "l_juros", T0)
    assert r2["meta_nova"] and r2["meta_atingida"] and not r2["primeiro_do_dia"]
    assert SOM.som_do_resultado(r2) == "meta"
    p, r3 = _fazer(p, "l_risco", T0)
    assert r3["meta_atingida"] and not r3["meta_nova"]                  # já estava batida: sem fanfarra de novo
    assert SOM.som_do_resultado(r3) == "concluida"


# ------------------------------------------------------------------ conquistas
def _estudar_dias(p, dias_atras):
    for d in dias_atras:
        p, _ = _fazer(p, "l_risco", T0 - timedelta(days=d))
    return p


def _ok(p):
    return {c["id"] for c in ED.conquistas(p) if c["ok"]}


def test_conquistas_novas_comecam_bloqueadas():
    ids = {c["id"] for c in ED.conquistas(ED.novo_progresso())}
    assert {"licao_perfeita", "ofensiva_3", "ofensiva_7", "ofensiva_30"} <= ids
    assert not (_ok(ED.novo_progresso()) & {"licao_perfeita", "ofensiva_3", "ofensiva_7", "ofensiva_30"})


def test_primeira_licao_perfeita():
    p, _ = _fazer(ED.novo_progresso(), "l_juros", T0, errar_primeiro=True)
    assert "licao_perfeita" not in _ok(p)                               # com erro não vale
    p, _ = _fazer(p, "l_risco", T0)
    assert "licao_perfeita" in _ok(p)


def test_conquistas_de_ofensiva_3_7_30_e_nao_somem_se_a_ofensiva_for_perdida():
    p = _estudar_dias(ED.novo_progresso(), [2, 1, 0])
    assert {"ofensiva_3"} <= _ok(p) and not ({"ofensiva_7", "ofensiva_30"} & _ok(p))
    p = _estudar_dias(ED.novo_progresso(), range(6, -1, -1))
    assert {"ofensiva_3", "ofensiva_7"} <= _ok(p) and "ofensiva_30" not in _ok(p)
    p = _estudar_dias(ED.novo_progresso(), range(29, -1, -1))
    assert {"ofensiva_3", "ofensiva_7", "ofensiva_30"} <= _ok(p)
    assert JO.melhor_ofensiva(p) == 30
    # a sequência atual se perde (passam-se 10 dias sem estudar), mas a conquista fica
    assert JO.ofensiva(p, T0 + timedelta(days=10)) == 0 and JO.melhor_ofensiva(p) == 30
    assert "ofensiva_30" in _ok(p)


def test_dias_com_buraco_nao_contam_como_sequencia():
    p = _estudar_dias(ED.novo_progresso(), [6, 5, 3, 2, 0])             # 2 + 2 + 1: nunca chega a 3
    assert JO.melhor_ofensiva(p) == 2 and "ofensiva_3" not in _ok(p)
    assert JO.melhor_ofensiva(ED.novo_progresso()) == 0


def test_conquistas_nao_premiam_operar():
    textos = " ".join(c["titulo"] + c["descricao"] for c in ED.conquistas(ED.novo_progresso())).lower()
    assert not any(x in textos for x in ("lucro", "operaç", "compra", "venda", "rentab"))


# ------------------------------------------------------------------ player: sons pendentes, toggle e conquistas no fim
def _novo_estado():
    st.session_state = {}
    caixa = {"p": ED.novo_progresso()}
    return caixa, (lambda: caixa["p"]), (lambda p: caixa.update(p=p))


def test_resposta_deixa_som_pendente_que_so_toca_uma_vez(monkeypatch):
    caixa, prog, set_prog = _novo_estado()
    PL.iniciar("l_risco")
    ex = JO.exercicio_atual(st.session_state["jor_sessao"])
    PL._verificar(ex["id"], _certo(ex))
    assert st.session_state["jor_som"] == "acerto"
    tocados = []
    monkeypatch.setattr(PL, "_tocar", tocados.append)
    PL._som_pendente(True)
    PL._som_pendente(True)                                              # segunda chamada (ex.: outro rerun): nada
    assert tocados == ["acerto"] and "jor_som" not in st.session_state
    PL._continuar(prog, set_prog)
    ex = JO.exercicio_atual(st.session_state["jor_sessao"])
    PL._verificar(ex["id"], _errado(ex))
    assert st.session_state["jor_som"] == "erro"


def test_som_desligado_descarta_sem_tocar(monkeypatch):
    _novo_estado()
    st.session_state["jor_som"] = "acerto"
    tocados = []
    monkeypatch.setattr(PL, "_tocar", tocados.append)
    PL._som_pendente(False)
    assert tocados == [] and "jor_som" not in st.session_state


def test_toggle_grava_na_conta():
    caixa, prog, set_prog = _novo_estado()
    st.session_state["jor_som_sw"] = False
    PL._mudar_som(prog, set_prog)
    assert not JO.som_ligado(caixa["p"])
    st.session_state["jor_som_sw"] = True
    PL._mudar_som(prog, set_prog)
    assert JO.som_ligado(caixa["p"])


def test_tocar_nao_quebra_se_o_streamlit_falhar(monkeypatch):
    _novo_estado()

    def falha(*a, **k):
        raise RuntimeError("sem áudio")
    monkeypatch.setattr(PL.st, "audio", falha, raising=False)
    PL._tocar("acerto")                                                 # só ignora
    PL._tocar("nao_existe")


def _jogar(lid, caixa, prog, set_prog):
    PL.iniciar(lid)
    while st.session_state["jor_fase"] != "fim":
        ex = JO.exercicio_atual(st.session_state["jor_sessao"])
        PL._verificar(ex["id"], _certo(ex))
        PL._continuar(prog, set_prog)
    return st.session_state["jor_resultado"]


def test_fim_da_licao_informa_conquista_nova_so_uma_vez():
    caixa, prog, set_prog = _novo_estado()
    r = _jogar("l_risco", caixa, prog, set_prog)
    assert "Lição perfeita" in r["conquistas_novas"]
    assert st.session_state["jor_som"] in ("concluida", "meta") and st.session_state["jor_recente"] == "l_risco"
    html = PL.html_fim(r)
    assert "Conquista desbloqueada" in html and "Lição perfeita" in html
    r2 = _jogar("l_juros", caixa, prog, set_prog)
    assert "Lição perfeita" not in r2["conquistas_novas"]               # já tinha: não repete
    PL.sair()
    assert "jor_recente" in st.session_state                            # sobrevive a sair(): o mapa precisa dele


def test_revisao_nao_marca_licao_recente():
    caixa, prog, set_prog = _novo_estado()
    caixa["p"], _ = _fazer(caixa["p"], "l_juros", T0, errar_primeiro=True)
    PL.iniciar_revisao(caixa["p"])
    while st.session_state["jor_fase"] != "fim":
        ex = JO.exercicio_atual(st.session_state["jor_sessao"])
        PL._verificar(ex["id"], _certo(ex))
        PL._continuar(prog, set_prog)
    assert "jor_recente" not in st.session_state


# ------------------------------------------------------------------ animações (HTML/CSS puros)
def test_barra_anima_so_quando_enche():
    assert "anima" in PL.html_barra(0.5, "x", de=0.25) and "--de:25%" in PL.html_barra(0.5, "x", de=0.25)
    assert "anima" not in PL.html_barra(0.5, "x", de=0.5)               # errou: a barra não anda
    assert "anima" not in PL.html_barra(0.5, "x")
    assert "width:100%" in PL.html_barra(7, "x") and "width:0%" in PL.html_barra(-1, "x")


def test_tela_final_tem_contagem_confete_e_escapa_texto():
    base = {"xp": 15, "acertos_primeira": 6, "total": 6, "revisao": False, "ofensiva": 3, "meta_atingida": False}
    h = PL.html_fim({**base, "perfeita": True})
    assert "--alvo:15" in h and "aria-label='+15'" in h and "jor-confete" in h
    assert "jor-confete" not in PL.html_fim({**base, "perfeita": False})        # sem festa para lição com erro
    assert "jor-confete" not in PL.html_fim({**base, "perfeita": True, "revisao": True})
    assert "jor-confete" in PL.html_fim({**base, "perfeita": False, "meta_nova": True})
    assert "<script" not in PL.html_fim({**base, "perfeita": True, "conquistas_novas": ["<script>x</script>"]})
    assert PL.html_confete() == PL.html_confete()                               # determinístico
    assert "prefers-reduced-motion" in PL.CSS                                    # respeita quem pede menos movimento


def test_mapa_anima_so_o_icone_recente_concluido():
    p, _ = _fazer(ED.novo_progresso(), "l_risco", T0)
    m = JO.mapa(p)
    css = APP.css_icones(m, "l_risco")
    assert "st-key-jor_nc_l_risco" in css and "jor-conquista" in css and "jor-selo" in css
    assert "jor-conquista" not in APP.css_icones(m, None)
    assert "jor-conquista" not in APP.css_icones(m, "l_juros")                  # lição ainda não concluída: sem animação


def test_stats_chama_viva_e_barra_da_meta():
    r = JO.resumo(_fazer(ED.novo_progresso(), "l_risco", T0)[0], T0)
    h = APP.html_stats(r)
    assert "viva" in h and "jor-metabar" in h and "width:75%" in h              # 15 de 20 XP
    r0 = JO.resumo(ED.novo_progresso(), T0)
    assert "viva" not in APP.html_stats(r0) and "width:0%" in APP.html_stats(r0)


# ------------------------------------------------------------------ lembrete de estudo (notif.py)
H19 = datetime(2026, 11, 9, 22, 0, tzinfo=timezone.utc)     # segunda-feira, 19h em Brasília


def _prefs(**estudo):
    return N.normalizar_prefs({"estudo": {"ativo": True, "hora": "18:00", **estudo}})


def _res(p=None, agora=H19):
    return JO.resumo(p or ED.novo_progresso(), agora)


def test_lembrete_vem_desligado_e_normaliza_lixo():
    assert N.normalizar_prefs(None)["estudo"] == {"ativo": False, "hora": "18:00"}
    assert N.normalizar_prefs({"estudo": {"ativo": "sim", "hora": "25:99"}})["estudo"] == {"ativo": False, "hora": "18:00"}
    assert N.normalizar_prefs({"estudo": "x"})["estudo"]["ativo"] is False
    assert N.normalizar_prefs({"estudo": {"ativo": True, "hora": "07:30"}})["estudo"] == {"ativo": True, "hora": "07:30"}
    assert N.lembrete_estudo(_res(), N.normalizar_prefs(None), H19) is None     # desligado: nada


def test_lembrete_so_depois_da_hora_e_se_nao_estudou():
    cedo = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)                    # 17h em Brasília
    assert N.lembrete_estudo(_res(agora=cedo), _prefs(), cedo) is None
    n = N.lembrete_estudo(_res(), _prefs(), H19)
    assert n and n["categoria"] == "estudo" and n["pagina"] == "educacao" and n["importancia"] == "media"
    p, _ = _fazer(ED.novo_progresso(), "l_risco", H19)
    assert N.lembrete_estudo(_res(p), _prefs(), H19) is None                    # já estudou hoje: não incomoda


def test_lembrete_texto_com_e_sem_ofensiva_e_uma_vez_por_dia():
    sem = N.lembrete_estudo(_res(), _prefs(), H19)
    assert "ofensiva" not in sem["titulo"].lower() and "3 minutos" in sem["titulo"]
    p = ED.novo_progresso()
    p, _ = _fazer(p, "l_risco", H19 - timedelta(days=1))                         # estudou ontem: ofensiva de 1 dia viva
    com = N.lembrete_estudo(_res(p), _prefs(), H19)
    assert "ofensiva de 1 dia" in com["titulo"] and "Faltam 20 XP" in com["texto"]
    de_novo = N.lembrete_estudo(_res(p), _prefs(), H19 + timedelta(minutes=45))
    assert de_novo["dedup"] == com["dedup"]                                      # mesma chave no mesmo dia: o banco descarta a repetição
    amanha = N.lembrete_estudo(_res(p, H19 + timedelta(days=1)), _prefs(), H19 + timedelta(days=1))
    assert amanha is None or amanha["dedup"] != com["dedup"]


def test_lembrete_respeita_dia_e_horario_permitidos_e_categoria_desligada():
    so_fds = N.normalizar_prefs({"estudo": {"ativo": True, "hora": "18:00"}, "horario": {"inicio": "08:00", "fim": "22:00", "dias": [5, 6]}})
    assert N.lembrete_estudo(_res(), so_fds, H19) is None                        # segunda-feira não vale
    tarde = datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)                    # 23h em Brasília: fora da janela 08–22
    assert N.lembrete_estudo(_res(agora=tarde), _prefs(), tarde) is None
    off = N.normalizar_prefs({"estudo": {"ativo": True, "hora": "18:00"}, "categorias_off": ["estudo"]})
    n = N.lembrete_estudo(_res(), off, H19)
    assert n and not N.passa_prefs(n, off)                                       # a pessoa pode silenciar a categoria


def test_categoria_estudo_aceita_no_banco():
    import banco
    assert "estudo" in banco.CATEGORIAS_NOTIF and "estudo" in N.CATEGORIAS


# ------------------------------------------------------------------ monitor: entrega do lembrete
def test_monitor_avisar_estudo_insere_entrega_e_deduplica(monkeypatch):
    import monitor
    inseridos, atualizados, entregas = [], [], []

    def inserir(email, n):
        if n["dedup"] in inseridos:
            return None
        inseridos.append(n["dedup"])
        return "id1"
    monkeypatch.setattr(monitor.banco, "sis_notif_inserir", inserir)
    monkeypatch.setattr(monitor.banco, "sis_notif_atualizar_dados", lambda i, d: atualizados.append(d))

    def entregar(n, prefs, destinos, agora, enviadas, url_app, dormir):
        entregas.append((prefs["importancia_min_externo"], enviadas))
        return {"ntfy": {"ok": True}}
    prefs = N.normalizar_prefs({"estudo": {"ativo": True, "hora": "18:00"}, "ntfy_topico": "abcdefghijklmnop1234", "canais": {"ntfy": True}})
    dados = {"edu_progresso": ED.novo_progresso()}
    assert monitor.avisar_estudo("a@b.com", dados, prefs, H19, entregar) is True
    assert entregas == [("baixa", 0)] and atualizados and atualizados[0]["entregas"]["ntfy"]["ok"]
    assert monitor.avisar_estudo("a@b.com", dados, prefs, H19 + timedelta(minutes=15), entregar) is False      # mesma data: já avisado
    assert len(entregas) == 1
    estudou, _ = _fazer(ED.novo_progresso(), "l_risco", H19)
    assert monitor.avisar_estudo("c@d.com", {"edu_progresso": estudou}, prefs, H19, entregar) is False           # já estudou hoje
    assert monitor.avisar_estudo("c@d.com", {}, N.normalizar_prefs(None), H19, entregar) is False               # lembrete desligado
    assert monitor.avisar_estudo("c@d.com", {"edu_progresso": "lixo"}, prefs, H19 + timedelta(days=1), entregar) in (True, False)  # dado ruim não quebra
