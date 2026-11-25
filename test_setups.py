"""Setups colecionáveis do Trade Game: catálogo e artes modulares, detectores, coleção, baús, e a ativação ao vivo no X1 (pausa sincronizada,
janela de 5 s, aceitar e recusar, ausência de sinais retroativos)."""
import copy
import json

import pytest

import cartas_catalogo as CAT
import setups as SU
import setups_vivo as SV
import trader_battle as TB
import trader_dados as TD
from test_api import cli  # noqa: F401  (fixture: um jogador com conta e sessão)
from test_social_api import dois  # noqa: F401  (fixture: dois jogadores com conta e sessão)

A, B = "a@x.com", "b@x.com"
T0 = 1002.0                                   # instante em que o replay começa nas partidas montadas abaixo
AG = "2026-11-25T10:00:00"


# ====================================================================================== catálogo e artes modulares
def test_catalogo_tem_os_quatro_setups_iniciais_com_todos_os_campos():
    cat = {s["id"]: s for s in SU.catalogo()}
    assert set(cat) == {"larry_williams", "turtle_trading", "mark_minervini", "setup_classico"}
    for s in cat.values():
        assert s["nome"] and s["resumo"] and s["caracteristicas"] and s["indicadores"] and s["regra"]["compra"] and s["raridade"] in CAT.RARIDADES
        assert set(s["assets"]) == {"carta", "ativacao", "moldura", "icone", "efeitos"} and s["cores"]["principal"]
        assert s["id"] in SU.DETECTORES


def test_so_a_arte_que_existe_vale_e_o_setup_se_declara_provisorio_sozinho():
    larry = SU.info("larry_williams")
    assert larry["assets"]["carta"] == "assets/setups/larry_williams/carta.jpg"      # a arte enviada, usada como veio
    assert larry["assets"]["ativacao"] is None and larry["provisorio"]               # falta a arte da animação: ainda provisório
    assert SU.info("turtle_trading")["assets"]["carta"] is None and SU.info("turtle_trading")["provisorio"]


def test_trocar_arte_provisoria_pela_definitiva_nao_pede_codigo(tmp_path, monkeypatch):
    """Basta copiar o arquivo para a pasta do setup e escrever o nome no setup.json. Nome digitado errado não vira link quebrado."""
    pasta = tmp_path / "turtle_trading"
    pasta.mkdir()
    base = json.loads(open(f"{SU.PASTA}/turtle_trading/setup.json", encoding="utf-8").read())
    monkeypatch.setattr(SU, "PASTA", str(tmp_path))

    def carregar(assets):
        (pasta / "setup.json").write_text(json.dumps({**base, "assets": assets}), encoding="utf-8")
        SU.recarregar()
        return SU.info("turtle_trading")
    try:
        assert carregar({"carta": "carta.webp"})["assets"]["carta"] is None            # o arquivo ainda não existe
        (pasta / "carta.webp").write_bytes(b"x")
        (pasta / "ativacao.webp").write_bytes(b"x")
        (pasta / "fx.webp").write_bytes(b"x")
        s = carregar({"carta": "carta.webp", "ativacao": "ativacao.webp", "efeitos": ["fx.webp", "nao_existe.webp"]})
        assert s["assets"]["carta"] == "assets/setups/turtle_trading/carta.webp" and not s["provisorio"]
        assert s["assets"]["efeitos"] == ["assets/setups/turtle_trading/fx.webp"]       # só os que existem
    finally:
        monkeypatch.undo()
        SU.recarregar()


def test_setup_json_invalido_falha_alto(tmp_path, monkeypatch):
    pasta = tmp_path / "turtle_trading"
    pasta.mkdir()
    base = json.loads(open(f"{SU.PASTA}/turtle_trading/setup.json", encoding="utf-8").read())
    monkeypatch.setattr(SU, "PASTA", str(tmp_path))
    try:
        for ruim, msg in (({"id": "outro"}, "id precisa ser igual"), ({"raridade": "mitica"}, "raridade inválida"), ({"nome": " "}, "falta o nome")):
            (pasta / "setup.json").write_text(json.dumps({**base, **ruim}), encoding="utf-8")
            SU.recarregar()
            with pytest.raises(SU.ErroSetup, match=msg):
                SU.catalogo()
    finally:
        monkeypatch.undo()
        SU.recarregar()


# ====================================================================================== detectores
def velas(closes, amp=0.004, vol=1000.0):
    out, ant = [], closes[0]
    for i, c in enumerate(closes):
        out.append({"t": str(i), "o": ant, "c": c, "h": max(ant, c) * (1 + amp / 2), "l": min(ant, c) * (1 - amp / 2), "v": vol})
        ant = c
    return out


def sinais(setup_id, v, desde=0):
    """Todos os sinais que o detector daria olhando um candle de cada vez, como o jogo faz."""
    return [(i, SU.detectar(setup_id, v[:i + 1])) for i in range(desde, len(v)) if SU.detectar(setup_id, v[:i + 1])]


def test_turtle_so_o_primeiro_fechamento_alem_do_canal_e_sinal():
    base = [100.0] * 210
    v = velas(base + [102.0, 103.0, 104.0], amp=0.02)                 # o canal vai até a máxima 101; três fechamentos acima dele
    s = sinais("turtle_trading", v, 205)
    assert [(i, x["direcao"]) for i, x in s] == [(210, "alta")]       # só o primeiro: os seguintes não são sinais novos
    baixo = velas(base + [98.0, 97.0], amp=0.02)
    assert [(i, x["direcao"]) for i, x in sinais("turtle_trading", baixo, 205)] == [(210, "baixa")]
    assert sinais("turtle_trading", velas(base + [100.5], amp=0.02), 205) == []        # fechou dentro do canal: nada


def test_turtle_precisa_de_historico_suficiente():
    assert SU.detectar("turtle_trading", velas([100.0] * 50 + [110.0])) is None


def _alta_depois_de_queda():
    return [100 - 0.6 * i for i in range(60)] + [64 * 1.03 ** k for k in range(1, 12)]


def test_classico_cruzamento_de_medias_com_ifr_confirmando():
    v = velas(_alta_depois_de_queda())
    s = sinais("setup_classico", v)
    assert len(s) == 1 and s[0][1]["direcao"] == "alta"
    assert s[0][0] >= 60                                              # nasce na virada, nunca durante a queda
    espelho = velas([200 - c for c in _alta_depois_de_queda()])
    assert [x["direcao"] for _, x in sinais("setup_classico", espelho)] == ["baixa"]
    assert sinais("setup_classico", velas([100.0 + (i % 2) * 0.01 for i in range(80)])) == []        # mercado parado: nada


def _tendencia_com_recuo(recuo=True, tendencia=1):
    base = [100 * (1 + 0.003 * tendencia) ** i for i in range(120)]
    if recuo:
        for _ in range(4):
            base.append(base[-1] * (1 - 0.008 * tendencia))
        base.append(base[-1] * (1 + 0.015 * tendencia))
    return base


def test_larry_williams_arma_na_virada_da_mme9_e_so_depois_o_preco_dispara():
    v = velas(_tendencia_com_recuo())
    arm = [(i, x) for i, x in sinais("larry_williams", v, 100)]
    assert len(arm) == 1
    i, x = arm[0]
    a = v[i]
    assert x["direcao"] == "alta" and "gatilho" in x                       # armado, não dispara sozinho
    assert x["gatilho"] == a["h"] and x["stop"] == a["l"]                  # gatilho na máxima e stop na mínima do candle de virada
    assert x["alvo"] == pytest.approx(a["h"] + 2 * (a["h"] - a["l"]))      # alvo 2:1
    assert x["validade"] == 1


def test_larry_williams_so_compra_como_diz_a_carta_e_so_a_favor_da_tendencia(monkeypatch):
    queda = velas(_tendencia_com_recuo(tendencia=-1))
    assert sinais("larry_williams", queda, 100) == []                      # a carta só descreve a compra
    monkeypatch.setattr(SU, "LW_VENDE", True)
    venda = sinais("larry_williams", queda, 100)
    assert len(venda) == 1 and venda[0][1]["direcao"] == "baixa"           # o espelho existe, desligado por padrão
    assert venda[0][1]["gatilho"] == queda[venda[0][0]]["l"]
    contra = [100 * 0.997 ** i for i in range(120)] + [50 * 1.02 ** k for k in range(1, 4)]       # MME9 vira para cima, mas abaixo da MME50
    assert sinais("larry_williams", velas(contra), 100) == []


def _serie_minervini(final_close=0.0035, final_vol=1000.0, contracao=True):
    n = 260
    c = [100 * 1.002 ** i for i in range(n)]
    v = velas(c, amp=0.008)
    if contracao:
        for j, i in enumerate(range(n - 26, n - 1)):                       # a volatilidade vai se apertando nos 25 candles antes do rompimento
            hr = 0.004 - (0.004 - 0.0004) * j / 24
            v[i]["h"], v[i]["l"] = c[i] * (1 + hr), c[i] * (1 - hr)
    ant = c[-2]
    v[-1] = {"t": "x", "o": ant, "c": ant * (1 + final_close), "h": ant * (1 + final_close) * 1.0005, "l": ant, "v": final_vol}
    return v


def test_minervini_tendencia_contracao_e_rompimento_do_pivo():
    s = SU.detectar("mark_minervini", _serie_minervini())
    assert s and s["direcao"] == "alta"
    assert SU.detectar("mark_minervini", _serie_minervini(final_close=0.0001)) is None        # não rompeu o pivô
    assert SU.detectar("mark_minervini", _serie_minervini(final_vol=100.0)) is None            # o volume secou
    assert SU.detectar("mark_minervini", _serie_minervini(contracao=False)) is None            # a volatilidade não contraiu
    queda = velas([100 * 0.998 ** i for i in range(260)])
    assert SU.detectar("mark_minervini", queda) is None                                         # sem tendência de alta
    assert SU.detectar("mark_minervini", velas([100.0] * 100)) is None                          # histórico curto demais


def test_detector_so_olha_para_tras():
    """Acrescentar candles ao FIM nunca muda o que o detector disse sobre os candles anteriores: não há por onde o futuro entrar."""
    v = velas(_tendencia_com_recuo())
    for sid in SU.DETECTORES:
        for i in range(100, len(v) - 1):
            assert SU.detectar(sid, v[:i + 1]) == SU.detectar(sid, copy.deepcopy(v[:i + 1]))
    assert SU.detectar("larry_williams", []) is None and SU.detectar("inexistente", v) is None


# ====================================================================================== coleção e baús
def test_conquista_e_permanente_e_so_se_equipa_o_que_se_tem():
    d = SU.colecao_vazia()
    assert SU.conquistar(d, "turtle_trading", "bau_raro", AG) is True
    assert SU.conquistar(d, "turtle_trading", "bau_raro", AG) is False             # não duplica
    with pytest.raises(SU.ErroSetup, match="carta"):
        SU.equipar(d, "larry_williams", AG)                                         # sem a carta, sem o setup
    with pytest.raises(SU.ErroSetup, match="desconhecido"):
        SU.equipar(d, "inventado", AG)
    assert SU.equipar(d, "turtle_trading", AG) == {"equipados": ["turtle_trading"]}
    SU.conquistar(d, "larry_williams", "bau_comum", AG)
    assert SU.equipar(d, "larry_williams", AG) == {"equipados": ["turtle_trading", "larry_williams"]}     # até 2 ao mesmo tempo
    assert SU.equipar(d, "larry_williams", AG)["equipados"] == ["turtle_trading", "larry_williams"]       # repetir não duplica
    SU.conquistar(d, "mark_minervini", "bau_comum", AG)
    with pytest.raises(SU.ErroSetup, match="2 setups"):
        SU.equipar(d, "mark_minervini", AG)                                         # os 2 espaços estão ocupados
    assert SU.desequipar(d, "turtle_trading", AG) == {"equipados": ["larry_williams"]}
    assert SU.equipar(d, "mark_minervini", AG)["equipados"] == ["larry_williams", "mark_minervini"]       # trocar = desequipar um e equipar outro


def test_colecao_do_formato_antigo_vira_lista_e_mais_de_dois_equipados_adulterados_sao_cortados():
    d = SU.colecao_vazia()
    for i in ("turtle_trading", "larry_williams", "mark_minervini"):
        SU.conquistar(d, i, "t", AG)
    antigo = {k: v for k, v in d.items() if k != "equipados"} | {"equipado": "larry_williams"}
    assert SU.normalizar(antigo)["equipados"] == ["larry_williams"]
    d["equipados"] = ["turtle_trading", "larry_williams", "mark_minervini", "turtle_trading", "inventado"]
    assert SU.normalizar(d)["equipados"] == ["turtle_trading", "larry_williams"]


def test_normalizar_nunca_perde_conquista_mas_descarta_equipado_invalido():
    d = SU.colecao_vazia()
    SU.conquistar(d, "turtle_trading", "t", AG)
    d["equipados"] = ["larry_williams"]                                             # adulterado: equipado sem ter a carta
    n = SU.normalizar(d)
    assert "turtle_trading" in n["itens"] and n["equipados"] == []
    assert SU.normalizar(None) == SU.colecao_vazia() and SU.normalizar({"v": 9}) == SU.colecao_vazia()


def test_bau_e_deterministico_e_so_traz_setup_que_ela_ainda_nao_tem():
    d = SU.colecao_vazia()
    baus = CAT.BAUS
    todos = {s["id"] for s in SU.catalogo()}
    assert SU.sortear_do_bau("s1", "lendario", d, baus, {"lendario": 1.0}) == SU.sortear_do_bau("s1", "lendario", d, baus, {"lendario": 1.0})
    ganhos = set()
    for i in range(len(todos)):
        sid = SU.sortear_do_bau(f"x{i}", "lendario", d, baus, {"lendario": 1.0})
        assert sid in todos and sid not in d["itens"]
        SU.conquistar(d, sid, "t", AG)
        ganhos.add(sid)
    assert ganhos == todos                                                          # sem repetir, até acabar
    assert SU.sortear_do_bau("y", "lendario", d, baus, {"lendario": 1.0}) is None   # tem todos: nada mais sai


def test_bau_sem_chance_nao_traz_setup_e_a_raridade_segue_os_pesos_do_proprio_bau():
    d = SU.colecao_vazia()
    assert all(SU.sortear_do_bau(f"z{i}", "comum", d, CAT.BAUS, {"comum": 0.0}) is None for i in range(200))
    assert SU.sortear_do_bau("w", "tier_que_nao_existe", d, CAT.BAUS) is None        # tier sem chance configurada: nada

    def parte_de_lendaria(tier):
        n = sum(SU.info(SU.sortear_do_bau(f"{tier}{i}", tier, d, CAT.BAUS, {tier: 1.0}))["raridade"] == "lendaria" for i in range(3000))
        return n / 3000
    comum, lendario = parte_de_lendaria("comum"), parte_de_lendaria("lendario")
    assert comum < 0.04 and 0.08 < lendario < 0.17 and lendario > 3 * comum          # baú melhor favorece setup mais raro (pesos 1 e 12)


# ====================================================================================== ativação ao vivo (sobre o estado da partida)
@pytest.fixture
def jogo():
    cen = TD.demo_corrida("rapida", 11)
    sp = TB.CORRIDAS["rapida"]
    jogs = [A, B]
    p = TB.nova_partida(cen, sp["tf"], jogs, 1000.0, pid="sala1", multi=True, apostas={j: {"stake": 10_000.0, "pat": 500_000.0} for j in jogs}, corrida="rapida")
    for j in jogs:
        TB.salvar_estrategia(p, j, {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, None, 0, T0)
    assert p["fase"] == "replay" and p["t_fase"] == T0
    p["setups"] = SV.iniciar(jogs, {A: ["turtle_trading"], B: []})
    return p, cen


def tick(p, cen, t):
    """O que o servidor faz a cada consulta: aplica o relógio e depois os setups."""
    TB.avancar(p, t, TD.por_id([cen]))
    return SV.processar(p, cen, t)


def sempre(monkeypatch, direcao="alta"):
    monkeypatch.setattr(SU, "detectar", lambda sid, v: {"direcao": direcao, "motivo": "teste"})


def ini_de(p, cen):
    return TB.inicio_rodada(cen, p["rodada"], int(TB.cfg_de(p)["n_replay"]))


def test_o_historico_da_analise_nunca_gera_sinal(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)                                                   # um detector que SEMPRE acharia sinal em qualquer candle
    assert tick(p, cen, T0 - 0.5) is False and p["setups"]["evento"] is None              # antes do replay: nada
    assert tick(p, cen, T0 + 0.5) is False and p["setups"]["evento"] is None              # nenhum candle do replay fechou ainda
    assert tick(p, cen, T0 + SV.TB.SEG_POR_CANDLE + 0.2)                                    # fechou o 1º candle do replay: agora sim
    sinal = p["setups"]["sinais"][0]
    assert sinal["candle"] == ini_de(p, cen)                                                # o 1º candle do replay, nunca um da análise
    assert all(x["candle"] >= ini_de(p, cen) for x in p["setups"]["sinais"])


def test_candle_que_ja_envelheceu_nao_vira_sinal(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    tick(p, cen, T0 + 5 * 4.0 + 3.9)                                                       # o 5º candle fechou há 3,9 s (limite 3 s): descartado
    assert p["setups"]["sinais"] == [] and p["setups"]["varrido"][A] == 5                  # e não volta a ser avaliado depois
    assert tick(p, cen, T0 + 6 * 4.0 + 0.2)                                                # o 6º, recém-fechado, vale


def test_so_quem_tem_setup_equipado_ativa_e_o_estado_antigo_nao_quebra(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    p["setups"]["equip"][A] = []
    assert tick(p, cen, T0 + 4.2) is False and p["setups"]["sinais"] == []                 # ninguém equipou nada
    del p["setups"]
    assert tick(p, cen, T0 + 8.2) is False and SV.visao(p, A, T0 + 8.2) is None            # partida sem setups: tudo segue igual


def test_ativacao_pausa_a_partida_para_os_dois_e_o_relogio_do_replay_congela(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    assert tick(p, cen, t) and TB.pausada(p)
    ev = p["setups"]["evento"]
    assert ev["prazo"] == pytest.approx(t + SV.ANIM_S + SV.JANELA_S)                       # 4 s de animação + 5 s de decisão
    n0 = TB.n_revelados(p, t)
    assert TB.n_revelados(p, t + 6.0) == n0                                                # o replay não anda enquanto o evento está aberto
    for jog in (A, B):                                                                       # nenhum dos dois opera durante a pausa
        with pytest.raises(TB.ErroTrader, match="pausa"):
            TB.registrar_acao(p, cen, jog, {"aid": "x" + jog, "tipo": "mercado", "direcao": "alta", "q": 1}, t + 1)


def test_os_dois_veem_o_evento_mas_so_o_dono_decide_e_o_adversario_nao_ve_o_stop(jogo, monkeypatch):
    p, cen = jogo
    ini = ini_de(p, cen)
    monkeypatch.setattr(SU, "detectar", lambda sid, v: {"direcao": "alta", "gatilho": 0.01, "stop": 1.5, "alvo": 99.0, "validade": 1, "motivo": "armado"}
                        if len(v) == ini + 3 else None)
    tick(p, cen, T0 + 3 * 4.0 + 0.2)                                                       # candle 3 fecha: o setup ARMA, mas ainda não ativa
    assert p["setups"]["evento"] is None and p["setups"]["armado"][A]
    assert tick(p, cen, T0 + 3 * 4.0 + 1.5)                                                # o preço supera o gatilho no candle seguinte: ativa
    t = T0 + 3 * 4.0 + 1.5
    dono, outro = SV.visao(p, A, t + 1)["evento"], SV.visao(p, B, t + 1)["evento"]
    assert dono and outro and dono["sinal"] == outro["sinal"] and dono["setup"]["nome"] == outro["setup"]["nome"] == "Turtle Trading"
    assert dono["pode_decidir"] and dono["voce_e_dono"] and dono["dono"] == "Você"
    assert not outro["pode_decidir"] and not outro["voce_e_dono"] and outro["dono"] == "Jogador 1"
    assert dono["stop"] == 1.5 and dono["alvo"] == 99.0                                    # o dono vê as proteções
    assert outro["stop"] is None and outro["alvo"] is None and outro["motivo"] == ""       # o adversário não
    assert dono["restante_ms"] == outro["restante_ms"] == int((SV.ANIM_S + SV.JANELA_S - 1) * 1000)         # mesmo prazo nas duas telas (vem do servidor)
    assert dono["anim_ms"] == 4000 and dono["janela_ms"] == 5000
    assert "equip" not in json.dumps(SV.visao(p, B, t))                                    # quem equipou o quê nunca vai para o adversário
    with pytest.raises(TB.ErroTrader, match="só quem ativou"):
        SV.decidir(p, cen, B, True, None, t + 1)


def test_aceitar_manda_ordem_a_mercado_pelo_sistema_atual_retoma_e_nao_duplica(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    sinal = p["setups"]["sinais"][0]
    r = SV.decidir(p, cen, A, True, None, t + 2)
    assert r["resultado"] == "aceito" and not TB.pausada(p) and p["setups"]["evento"] is None
    a = p["acoes"][-1]
    assert a["aid"] == f"setup:{sinal['id']}" and a["tipo"] == "mercado" and a["direcao"] == "alta" and a["jogador"] == A and a["sinal"] == sinal["id"]
    assert sinal["estado"] == "aceito" and sinal["aid"] == a["aid"]                         # a operação fica ligada ao sinal
    assert a["q"] == TB.lote_de(p, A, cen["candles"][ini_de(p, cen) - 1]["c"])             # sem quantidade informada: 1 lote
    with pytest.raises(TB.ErroTrader, match="não há setup"):
        SV.decidir(p, cen, A, True, None, t + 3)                                           # clicar de novo não faz nada
    assert len([x for x in p["acoes"] if x["aid"] == a["aid"]]) == 1
    n = TB.n_revelados(p, t + 2)
    assert TB.n_revelados(p, t + 6) > n                                                    # a partida voltou a andar


def test_aceitar_usa_a_quantidade_da_boleta_e_o_motor_valida_os_limites(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    with pytest.raises(TB.ErroTrader, match="cabem no máximo"):
        SV.decidir(p, cen, A, True, 10_000_000, t + 1)                                     # quantidade absurda: o motor recusa, nada é gravado
    assert TB.pausada(p) is True and p["setups"]["evento"] is not None                      # e a janela continua aberta para tentar de novo
    assert SV.decidir(p, cen, A, True, 7, t + 2)["resultado"] == "aceito" and p["acoes"][-1]["q"] == 7


def test_stop_e_alvo_do_setup_vao_na_ordem_e_se_o_motor_recusar_entra_sem_eles(jogo, monkeypatch):
    p, cen = jogo
    ini = ini_de(p, cen)
    preco = cen["candles"][ini - 1]["c"]
    for stop, alvo, protegido in ((preco * 0.98, preco * 1.04, True), (preco * 1.5, preco * 1.04, False)):       # o 2º tem o stop do lado errado
        p2, cen2 = copy.deepcopy(p), cen
        monkeypatch.setattr(SU, "detectar", lambda sid, v, s=stop, a=alvo: {"direcao": "alta", "gatilho": 0.01, "stop": s, "alvo": a, "validade": 1, "motivo": "x"}
                            if len(v) == ini + 1 else None)
        tick(p2, cen2, T0 + 4.2)
        tick(p2, cen2, T0 + 5.5)
        assert p2["setups"]["evento"], "o setup armado deveria ter ativado"
        assert SV.decidir(p2, cen2, A, True, None, T0 + 6.5)["resultado"] == "aceito"
        a = p2["acoes"][-1]
        assert p2["setups"]["sinais"][0]["protegido"] is protegido
        assert (a.get("stop") is not None) is protegido and (a.get("alvo") is not None) is protegido       # a entrada nunca se perde por causa da proteção


def test_recusar_nao_executa_nada_e_retoma_a_partida(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    assert SV.decidir(p, cen, A, False, None, t + 1)["resultado"] == "recusado"
    assert p["setups"]["sinais"][0]["estado"] == "recusado" and not TB.pausada(p) and not p.get("acoes")


def test_sem_resposta_em_5_segundos_vira_recusa_automatica_e_a_partida_retoma(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    assert tick(p, cen, t + SV.ANIM_S + SV.JANELA_S - 0.1) is False and TB.pausada(p)      # ainda dentro do prazo
    assert tick(p, cen, t + SV.ANIM_S + SV.JANELA_S + 0.1)                                  # estourou: o servidor resolve na consulta de qualquer um
    assert p["setups"]["sinais"][0]["estado"] == "expirado" and not TB.pausada(p) and not p.get("acoes")


def test_decidir_depois_do_prazo_nao_executa_nada(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    assert SV.decidir(p, cen, A, True, None, t + 20)["resultado"] == "expirado"             # o relógio é do servidor: cliente atrasado perde
    assert not p.get("acoes") and p["setups"]["sinais"][0]["estado"] == "expirado" and not TB.pausada(p)


def test_tempo_parado_nao_conta_e_o_replay_continua_de_onde_parou(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    antes = TB.n_revelados(p, t)
    SV.decidir(p, cen, A, False, None, t + 3.0)                                              # recusou depois de 3 s de pausa
    assert TB.n_revelados(p, t + 3.0) == antes                                               # exatamente onde parou
    assert TB.n_revelados(p, t + 3.0 + 4.0) > antes


def test_recarga_e_teto_de_ativacoes_por_jogador(jogo, monkeypatch):
    p, cen = jogo
    sempre(monkeypatch)
    t, disparos = T0 + 4.2, []
    for _ in range(400):
        antes = len(p["setups"]["sinais"])
        tick(p, cen, t)
        if len(p["setups"]["sinais"]) > antes:
            disparos.append(p["setups"]["sinais"][-1]["candle"])
            SV.decidir(p, cen, A, False, None, t + 0.5)
        t += 0.5
    assert 1 <= len(disparos) <= SV.TETO
    assert all(b - a >= SV.RECARGA for a, b in zip(disparos, disparos[1:]))                  # espaço mínimo entre duas ativações


def test_dois_setups_equipados_sao_avaliados_cada_um_e_so_um_evento_por_vez(jogo, monkeypatch):
    p, cen = jogo
    ini = ini_de(p, cen)
    p["setups"]["equip"][A] = ["turtle_trading", "larry_williams"]
    vistos = []
    monkeypatch.setattr(SU, "detectar", lambda sid, v: vistos.append(sid) or (
        {"direcao": "alta", "stop": 1.0, "alvo": 99.0, "motivo": sid} if sid == "larry_williams" and len(v) == ini + 3 else None))
    tick(p, cen, T0 + 3 * 4.0 + 0.2)
    assert {"turtle_trading", "larry_williams"} <= set(vistos), "os dois equipados são avaliados"
    ev = p["setups"]["evento"]
    assert ev and next(x for x in p["setups"]["sinais"] if x["id"] == ev["sinal"])["setup"] == "larry_williams"


def test_setup_armado_que_o_preco_nao_alcanca_expira_sem_evento(jogo, monkeypatch):
    p, cen = jogo
    ini = ini_de(p, cen)
    monkeypatch.setattr(SU, "detectar", lambda sid, v: {"direcao": "alta", "gatilho": 1e9, "stop": 1.0, "alvo": 2e9, "validade": 1, "motivo": "x"}
                        if len(v) == ini + 2 else None)
    for k in range(1, 8):
        tick(p, cen, T0 + k * 2.0)
    assert p["setups"]["sinais"] == [] and not any(p["setups"]["armado"].values()) and p["setups"]["evento"] is None


def test_sinal_armado_nao_vale_se_o_rompimento_ja_e_velho(jogo, monkeypatch):
    p, cen = jogo
    ini = ini_de(p, cen)
    monkeypatch.setattr(SU, "detectar", lambda sid, v: {"direcao": "alta", "gatilho": 0.01, "stop": 0.005, "alvo": 9.0, "validade": 1, "motivo": "x"}
                        if len(v) == ini + 1 else None)
    tick(p, cen, T0 + 4.2)                                                                    # arma no 1º candle
    assert p["setups"]["armado"][A]
    tick(p, cen, T0 + 4.0 + 4.0 + 3.9)                                                        # só consultaram 3,9 s depois de o preço romper: velho
    assert p["setups"]["sinais"] == []


def test_a_pontuacao_e_o_resultado_nao_mudam_com_os_setups(jogo, monkeypatch):
    """Recusar não deixa rastro no motor: a partida termina igual a uma sem setups."""
    p, cen = jogo
    q = copy.deepcopy(p)
    del q["setups"]
    sempre(monkeypatch)
    t = T0 + 4.2
    tick(p, cen, t)
    SV.decidir(p, cen, A, False, None, t)
    fim = T0 + TB.cfg_de(p)["t_replay_s"] + 1
    for x in (p, q):
        TB.avancar(x, fim, TD.por_id([cen]))
    assert p["fase"] == q["fase"] == "resultado" and p["resultados"].keys() == q["resultados"].keys()
    for k in p["resultados"]:
        assert p["resultados"][k]["pontos"] == q["resultados"][k]["pontos"]


# ====================================================================================== X1 de verdade (sala, banco, CAS) e API
def _conquistar(email, *ids, equipar=None):
    import setups_dados as SD
    d = SD.ler(email)
    for i in ids:
        SU.conquistar(d, i, "teste", AG)
    for e in ([equipar] if isinstance(equipar, str) else equipar or []):
        SU.equipar(d, e, AG)
    SD.gravar(email, d)


def test_x1_com_banco_congela_o_setup_e_mostra_o_mesmo_evento_para_os_dois(monkeypatch):
    import trader_online_dados as OL
    from test_trader_mesa import EMAILS, TS, _contas, banco_isolado, livro
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    dono, outro = EMAILS[0], EMAILS[1]
    with banco_isolado():
        _contas()
        with livro(pat=300_000.0, caixa=200_000.0):
            _conquistar(dono, "turtle_trading", "larry_williams", equipar="turtle_trading")
            r = OL.criar_sala(dono, "15m", TS, corrida="rapida")
            OL.entrar_na_sala(outro, r["codigo"], TS + 1)
            OL.iniciar(r["id"], dono, TS + 2)
            pid = r["id"]
            assert OL._row(pid)["dados"]["p"]["setups"]["equip"] == {dono: ["turtle_trading"], outro: []}
            _conquistar(dono, "larry_williams", equipar="larry_williams")                      # equipar outro na central DEPOIS de começar
            assert OL._row(pid)["dados"]["p"]["setups"]["equip"][dono] == ["turtle_trading"]       # não muda a partida em andamento
            t0 = TS + 10
            for e in (dono, outro):
                OL.salvar(pid, e, {"direcao": "alta", "tipo": "continuacao"}, None, t0)
            sempre(monkeypatch)
            ev_dono = OL.ler(pid, dono, t0 + 4.2)
            ev_outro = OL.ler(pid, outro, t0 + 4.3)
            a, b = ev_dono["p"]["setup"]["evento"], ev_outro["p"]["setup"]["evento"]
            assert a and b and a["sinal"] == b["sinal"] and a["setup"]["nome"] == b["setup"]["nome"] == "Turtle Trading"
            assert ev_dono["v"]["pausada"] and ev_outro["v"]["pausada"]                         # a partida parou para os dois
            assert a["pode_decidir"] is True and b["pode_decidir"] is False
            assert abs(a["restante_ms"] - b["restante_ms"]) <= 200                                # o mesmo cronômetro, o do servidor
            with pytest.raises(TB.ErroTrader, match="só quem ativou"):
                OL.decidir_setup(pid, outro, True, None, t0 + 5)
            with pytest.raises(TB.ErroTrader, match="pausa"):
                OL.agir(pid, outro, {"aid": "z1", "tipo": "mercado", "direcao": "alta", "q": 1}, t0 + 5)
            assert OL.decidir_setup(pid, dono, True, 5, t0 + 6) == {"resultado": "aceito", "aid": f"setup:{a['sinal']}"}
            dados = OL._row(pid)["dados"]["p"]
            assert dados["acoes"][-1]["aid"] == f"setup:{a['sinal']}" and dados["acoes"][-1]["q"] == 5
            depois = OL.ler(pid, outro, t0 + 7)
            assert not depois["v"]["pausada"] and depois["p"]["setup"]["evento"] is None        # retomou nas duas telas
            assert [m["estado"] for m in depois["p"]["setup"]["marcas"]] == ["aceito"]            # e a marca do sinal ativado aparece para o adversário
            with pytest.raises(TB.ErroTrader, match="não há setup"):
                OL.decidir_setup(pid, dono, True, 5, t0 + 7)


def test_x1_sem_resposta_o_servidor_recusa_na_consulta_de_qualquer_jogador(monkeypatch):
    import trader_online_dados as OL
    from test_trader_mesa import EMAILS, TS, _contas, banco_isolado, livro
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    dono, outro = EMAILS[0], EMAILS[1]
    with banco_isolado():
        _contas()
        with livro(pat=300_000.0, caixa=200_000.0):
            _conquistar(dono, "turtle_trading", equipar="turtle_trading")
            r = OL.criar_sala(dono, "15m", TS, corrida="rapida")
            OL.entrar_na_sala(outro, r["codigo"], TS + 1)
            OL.iniciar(r["id"], dono, TS + 2)
            pid, t0 = r["id"], TS + 10
            for e in (dono, outro):
                OL.salvar(pid, e, {"direcao": "alta", "tipo": "continuacao"}, None, t0)
            sempre(monkeypatch)
            assert OL.ler(pid, dono, t0 + 4.2)["p"]["setup"]["evento"]
            v = OL.ler(pid, outro, t0 + 4.2 + SV.ANIM_S + SV.JANELA_S + 0.2)                    # o ADVERSÁRIO consulta depois do prazo
            assert v["p"]["setup"]["evento"] is None and not v["v"]["pausada"]
            assert [m["estado"] for m in v["p"]["setup"]["marcas"]] == ["expirado"]
            assert not OL._row(pid)["dados"]["p"].get("acoes")


def test_api_meus_setups_lista_so_o_conquistado_e_equipar_confere_a_propriedade(cli):
    from test_api import EU
    assert cli.get("/setups").json() == {"itens": [], "equipados": [], "limite": 2, "conquistados": 0, "total": 4}
    assert cli.post("/setups/equipar", json={"id": "turtle_trading"}).status_code == 400            # ainda não desbloqueou
    _conquistar(EU, "turtle_trading")
    r = cli.get("/setups").json()
    assert [i["id"] for i in r["itens"]] == ["turtle_trading"] and r["conquistados"] == 1 and r["total"] == 4 and r["equipados"] == []
    assert "larry_williams" not in json.dumps(r) and "Minervini" not in json.dumps(r)               # o que não desbloqueou não aparece
    i = r["itens"][0]
    assert i["caracteristicas"] and i["indicadores"] and i["regra"]["compra"] and i["assets"]["carta"] is None and i["provisorio"]
    assert cli.post("/setups/equipar", json={"id": "larry_williams"}).status_code == 400
    assert cli.post("/setups/equipar", json={"id": "inventado"}).status_code == 400
    assert cli.post("/setups/equipar", json={"id": "turtle_trading"}).json()["equipados"] == ["turtle_trading"]
    assert cli.get("/setups").json()["itens"][0]["equipado"] is True                                  # persistido na conta
    _conquistar(EU, "larry_williams")
    assert cli.post("/setups/equipar", json={"id": "larry_williams"}).json()["equipados"] == ["turtle_trading", "larry_williams"]   # o segundo espaço
    _conquistar(EU, "mark_minervini")
    assert cli.post("/setups/equipar", json={"id": "mark_minervini"}).status_code == 400            # só 2 ao mesmo tempo
    assert cli.post("/setups/desequipar", json={"id": "turtle_trading"}).json()["equipados"] == ["larry_williams"]
    assert cli.post("/setups/equipar", json={"id": "mark_minervini"}).json()["equipados"] == ["larry_williams", "mark_minervini"]
    assert cli.get("/setups").json()["conquistados"] == 3


def test_api_bau_pode_trazer_setup_uma_vez_so_e_nao_mexe_nas_outras_recompensas(cli, monkeypatch):
    import test_api as T
    T._cartas_teste()
    for tier in SU.CHANCE_BAU:
        monkeypatch.setitem(SU.CHANCE_BAU, tier, 1.0)
    cli.post("/ticker/tutorial/bau")
    r = cli.post("/loja/bau").json()
    assert r["cartas"] and all(c["tk"] and c["raridade"] for c in r["cartas"])                        # as cartas do baú continuam as mesmas
    assert r["setup"]["nova"] is True and r["setup"]["id"] in {s["id"] for s in SU.catalogo()}
    assert cli.get("/setups").json()["conquistados"] == 1                                              # gravado para sempre
    de_novo = cli.post("/loja/bau").json()
    assert "setup" not in de_novo and "cartas" not in de_novo                                          # o mesmo baú não entrega duas vezes
    assert cli.get("/setups").json()["conquistados"] == 1


def test_api_se_a_roleta_de_setup_falhar_o_bau_continua_igual(cli, monkeypatch):
    import setups_dados as SD
    import test_api as T
    T._cartas_teste()
    cli.post("/ticker/tutorial/bau")
    monkeypatch.setattr(SD, "recompensa_bau", lambda *a: (_ for _ in ()).throw(RuntimeError("falhou")))
    r = cli.post("/loja/bau").json()
    assert r["cartas"] and "setup" not in r                                                            # as cartas e as moedas não dependem dos setups


def test_api_x1_de_ponta_a_ponta_com_dois_jogadores(dois, monkeypatch):
    """Sala, equipar, estratégia, ativação, pausa nas duas telas, só o dono decide, aceitar e retomar, tudo pela API."""
    import api.main as API
    ana, bia = dois
    t = {"agora": 5_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    _conquistar("ana@x.com", "turtle_trading")
    assert ana.post("/setups/equipar", json={"id": "turtle_trading"}).status_code == 200
    sala = ana.post("/trade/salas", json={"corrida": "rapida"}).json()
    assert bia.post("/trade/salas/entrar", json={"codigo": sala["codigo"]}).status_code == 200
    pid = sala["id"]
    assert ana.post(f"/trade/salas/{pid}/iniciar").status_code == 200
    t["agora"] += 5
    for c in (ana, bia):
        assert c.post(f"/trade/salas/{pid}/estrategia", json={"direcao": "alta"}).status_code == 200
    sempre(monkeypatch)
    t["agora"] += 4.2
    va, vb = ana.get(f"/trade/salas/{pid}").json(), bia.get(f"/trade/salas/{pid}").json()
    ea, eb = va["tela"]["setup"]["evento"], vb["tela"]["setup"]["evento"]
    assert ea and eb and ea["sinal"] == eb["sinal"] and va["tela"]["pausada"] and vb["tela"]["pausada"]
    assert ea["pode_decidir"] and not eb["pode_decidir"]
    assert bia.post(f"/trade/salas/{pid}/setup", json={"acao": "aceitar"}).status_code == 400    # o adversário não decide
    assert ana.post(f"/trade/salas/{pid}/setup", json={"acao": "talvez"}).status_code == 400      # só aceitar ou recusar
    t["agora"] += 2
    r = ana.post(f"/trade/salas/{pid}/setup", json={"acao": "aceitar", "q": 3})
    assert r.status_code == 200 and r.json()["tela"]["setup"]["evento"] is None and not r.json()["tela"]["pausada"]
    assert r.json()["tela"]["mesa"]["fila"][0]["q"] == 3                                          # a ordem entrou no sistema atual de execução
    assert ana.post(f"/trade/salas/{pid}/setup", json={"acao": "aceitar"}).status_code == 400    # e não duplica
