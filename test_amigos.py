"""Amigos, bloqueios, denúncias, convites e o acesso ao perfil de outra pessoa (permissões no banco, não só na tela)."""
from datetime import datetime, timedelta, timezone

import pytest

import amigos as AM
import perfis as PF


def _setup(banco, *nomes, priv=None):
    atores = []
    for n in nomes:
        e = f"{n.lower()}@x.com"
        banco._inserir("contas", {"id": "id-" + e, "email": e, "nome": "Nome Real " + n, "criado_em": "2026-01-01T00:00:00Z"})
        a = banco.Ator(id="id-" + e, email=e, papel="usuario")
        assert banco.usuario_reservar(a, n.lower())
        doc = PF.inicial(n)
        if priv and n in priv:
            doc = PF.editar(doc, {"privacidade": priv[n]})[0]
        banco.perfil_jogador_gravar(a, doc)
        atores.append(a)
    return atores


@pytest.fixture
def bd():
    import banco
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        yield banco


def _h(banco, a):
    return banco._h_conta(a.email)


# ------------------------------------------------------------------ regras puras
def test_regras_do_pedido():
    with pytest.raises(AM.ErroAmigos, match="si mesmo"):
        AM.conferir_pedido("a", "a", None, False, True, 0, 0)
    with pytest.raises(AM.ErroAmigos, match="Não é possível"):
        AM.conferir_pedido("a", "b", None, True, True, 0, 0)
    with pytest.raises(AM.ErroAmigos, match="já são amigos"):
        AM.conferir_pedido("a", "b", AM.AMIGOS, False, True, 0, 0)
    with pytest.raises(AM.ErroAmigos, match="não está recebendo"):
        AM.conferir_pedido("a", "b", None, False, False, 0, 0)
    with pytest.raises(AM.ErroAmigos, match="limite"):
        AM.conferir_pedido("a", "b", None, False, True, AM.MAX_AMIGOS, 0)
    assert AM.conferir_pedido("a", "b", AM.RECEBIDA, False, False, 0, 0) == "aceitar"      # ele já pediu: aceitar vale mesmo com pedidos fechados
    assert AM.conferir_pedido("a", "b", None, False, True, 0, 0) == "enviar"


def test_busca_atividade_convite_e_comparacao():
    itens = [{"usuario": "Ana_99", "nome": "Ana Lúcia"}, {"usuario": "bia", "nome": "Beatriz"}]
    assert [x["usuario"] for x in AM.buscar(itens, "@ANA")] == ["Ana_99"] and len(AM.buscar(itens, "lucia")) == 1 and len(AM.buscar(itens, "")) == 2
    ag = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
    assert AM.atividade("2026-11-17T08:00:00+00:00", ag) == "hoje" and AM.atividade("2026-11-12T08:00:00Z", ag) == "semana"
    assert AM.atividade("2026-10-01T00:00:00Z", ag) is None and AM.atividade(None, ag) is None
    assert AM.convite_valido({"jogo": "trade", "codigo": "ABC", "em": (ag - timedelta(minutes=5)).isoformat()}, ag)
    assert not AM.convite_valido({"jogo": "trade", "codigo": "ABC", "em": (ag - timedelta(hours=2)).isoformat()}, ag)
    assert not AM.convite_valido({"jogo": "xadrez", "codigo": "ABC", "em": ag.isoformat()}, ag)
    import jogos as J
    d1, _ = J.registrar_trade({}, "p1", 30, 3, "r", 1, 2, "x")
    d2, _ = J.registrar_trade({}, "p2", 50, 3, "r", 2, 2, "x")
    cmp = AM.comparar({"usuario": "eu", "eu": True, "placar": d1}, [{"usuario": "bia", "placar": d2}, {"usuario": "oculto", "placar": None}], J.TRADE)
    assert [r["usuario"] for r in cmp] == ["bia", "eu"] and cmp[1]["eu"] and cmp[1]["taxa"] == 100 and cmp[0]["pos"] == 1


def test_privacidade_quem_ve_e_quem_pede():
    pv = PF.validar_privacidade({"visivel": "amigos", "pedidos": "ninguem"})
    assert not PF.pode_ver(pv, False) and PF.pode_ver(pv, True) and PF.pode_ver(pv, False, dono=True) and not PF.aceita_pedidos(pv)
    assert not PF.pode_ver({"visivel": "ninguem"}, True) and PF.pode_ver({}, False)
    assert PF.validar_privacidade({"publico": False})["visivel"] == "ninguem"                  # documento antigo continua privado


def test_publico_com_estatisticas_historico_e_medalhas():
    import jogos as J
    d, _ = J.registrar_trade({}, "p1", 30, 3, "rapida", 1, 2, "2026-11-17 10:00")
    d, _ = J.registrar_ticker(d, "d1", "derrota", "online", "2026-11-17 11:00")
    prog = {"xp": 50, "nivel": 2, "titulo": "Aprendiz", "conquistas": 1, "conquistas_total": 9, "medalhas": [{"emblema": "🎓", "nome": "Primeira lição"}]}
    hist = PF.historico_publico(d)
    assert hist[0]["jogo"] == J.TICKER and hist[0]["r"] == "d" and set(hist[1]) == {"em", "jogo", "pts", "pos", "n"}
    pub = PF.publico(PF.inicial("Ana_99"), "2026-01", prog, PF.jogos(d), estat=J.estatisticas(d), historico=hist)
    assert pub["estat"]["vitorias"] == 1 and pub["estat"]["derrotas"] == 1 and pub["medalhas"][0]["nome"] == "Primeira lição" and len(pub["historico"]) == 2
    so_amigos = PF.editar(PF.inicial("Ana_99"), {"privacidade": {"visivel": "amigos", "mostrar_historico": False, "mostrar_jogos": False}})[0]
    assert PF.publico(so_amigos, "", prog, PF.jogos(d), estat=J.estatisticas(d), historico=hist) is None
    pub = PF.publico(so_amigos, "", prog, PF.jogos(d), amigo=True, estat=J.estatisticas(d), historico=hist)
    assert "historico" not in pub and "estat" not in pub and "jogos" not in pub


# ------------------------------------------------------------------ banco
def test_pedido_aceite_recusa_cancelamento_e_remocao(bd):
    A, B, C = _setup(bd, "Ana", "Bia", "Caio")
    assert bd.amigo_pedir(A, "bia") == "enviado"
    assert bd.social_relacoes(A)[_h(bd, B)]["estado"] == AM.ENVIADA and bd.social_relacoes(B)[_h(bd, A)]["estado"] == AM.RECEBIDA
    with pytest.raises(AM.ErroAmigos, match="já enviou"):
        bd.amigo_pedir(A, "bia")
    assert not bd.amigo_responder(A, _h(bd, B), True)                       # quem enviou não pode "aceitar" o próprio pedido
    assert not bd.amigo_responder(C, _h(bd, A), True)                       # nem um terceiro
    assert bd.amigo_responder(B, _h(bd, A), True)
    assert bd.social_relacoes(A)[_h(bd, B)]["estado"] == AM.AMIGOS == bd.social_relacoes(B)[_h(bd, A)]["estado"]
    assert bd.amigo_pedir(C, "ana") == "enviado" and bd.amigo_responder(A, _h(bd, C), False)
    assert _h(bd, A) not in bd.social_relacoes(C)                           # recusado: some dos dois lados
    assert bd.amigo_pedir(C, "bia") == "enviado" and bd.amigo_remover(C, _h(bd, B))   # cancelar pedido enviado
    assert not bd.social_relacoes(B).get(_h(bd, C))
    assert not bd.amigo_remover(C, _h(bd, A))                               # não havia relação
    assert bd.amigo_remover(A, _h(bd, B)) and not bd.social_relacoes(B)
    with pytest.raises(bd.SemPermissao):
        bd.amigo_pedir(None, "bia")
    with pytest.raises(AM.ErroAmigos, match="não encontrado"):
        bd.amigo_pedir(A, "ninguem")
    with pytest.raises(ValueError):
        bd.amigo_remover(A, "'; drop table contas; --")


def test_pedidos_cruzados_viram_amizade_e_pedidos_fechados(bd):
    A, B, C = _setup(bd, "Ana", "Bia", "Caio", priv={"Caio": {"pedidos": "ninguem"}})
    assert bd.amigo_pedir(A, "bia") == "enviado" and bd.amigo_pedir(B, "ana") == "aceito"
    assert bd.social_relacoes(A)[_h(bd, B)]["estado"] == AM.AMIGOS
    with pytest.raises(AM.ErroAmigos, match="não está recebendo"):
        bd.amigo_pedir(A, "caio")
    with pytest.raises(AM.ErroAmigos, match="si mesmo"):
        bd.amigo_pedir(A, "ana")


def test_bloqueio_desfaz_amizade_e_esconde_perfis(bd):
    A, B = _setup(bd, "Ana", "Bia")
    bd.amigo_pedir(A, "bia")
    bd.amigo_responder(B, _h(bd, A), True)
    assert bd.perfil_alvo(A, "bia")["rel"] == AM.AMIGOS
    bd.bloquear(B, _h(bd, A))
    assert not bd.social_relacoes(A) and not bd.social_relacoes(B)
    assert bd.perfil_alvo(A, "bia") is None and bd.perfil_alvo(B, "ana") is None          # nos dois sentidos
    with pytest.raises(AM.ErroAmigos):
        bd.amigo_pedir(A, "bia")
    assert not bd.desbloquear(A, _h(bd, B))                                 # só quem bloqueou desbloqueia
    assert bd.social_bloqueados(B) == [_h(bd, A)] and bd.desbloquear(B, _h(bd, A))
    assert bd.perfil_alvo(A, "bia")["completo"]


def test_perfil_alvo_respeita_privacidade(bd):
    A, B, C = _setup(bd, "Ana", "Bia", "Caio", priv={"Bia": {"visivel": "amigos"}, "Caio": {"visivel": "ninguem"}})
    v = bd.perfil_alvo(A, "bia")
    assert v and not v["completo"] and v["rel"] is None                     # só amigos: cartão básico para poder pedir amizade
    assert bd.perfil_alvo(A, "caio") is None and bd.perfil_alvo(C, "caio")["dono"]
    bd.amigo_pedir(A, "bia")
    bd.amigo_responder(B, _h(bd, A), True)
    assert bd.perfil_alvo(A, "bia")["completo"]
    assert bd.perfil_alvo(A, "nome inválido!") is None
    with pytest.raises(bd.SemPermissao):
        bd.perfil_alvo(None, "bia")


def test_convites_so_entre_amigos_e_expiram(bd, monkeypatch):
    A, B, C = _setup(bd, "Ana", "Bia", "Caio")
    with pytest.raises(AM.ErroAmigos, match="só pode convidar amigos"):
        bd.convite_jogo_enviar(A, _h(bd, B), "trade", "ABC123")
    bd.amigo_pedir(A, "bia")
    bd.amigo_responder(B, _h(bd, A), True)
    bd.convite_jogo_enviar(A, _h(bd, B), "ticker", "XY-12<b>")
    cv = bd.convites_recebidos(B)
    assert len(cv) == 1 and cv[0]["codigo"] == "XY12b" and cv[0]["jogo"] == "ticker" and cv[0]["h"] == _h(bd, A)
    assert not bd.convites_recebidos(C) and not bd.convites_recebidos(A)
    notifs = bd._selecionar("notificacoes", {"email": B.email}, ["titulo", "pagina"])
    assert any("convidou" in n["titulo"] for n in notifs) and any("quer ser seu amigo" in n["titulo"] for n in notifs)
    bd.convite_apagar(B, _h(bd, A))
    assert not bd.convites_recebidos(B)
    bd.convite_jogo_enviar(A, _h(bd, B), "trade", "QQQ111")
    bd.cfg_gravar(f"cvj|{_h(bd, B)}|{_h(bd, A)}", {"jogo": "trade", "codigo": "QQQ111", "em": "2020-01-01T00:00:00+00:00"})
    assert not bd.convites_recebidos(B)                                     # sala velha: convite some
    with pytest.raises(ValueError):
        bd.convite_jogo_enviar(A, _h(bd, B), "xadrez", "A")


def test_denuncia_uma_por_dia_e_admin_avisado(bd):
    A, B = _setup(bd, "Ana", "Bia")
    bd._inserir("contas", {"id": "adm", "email": "adm@x.com", "nome": "Adm", "papel": "admin", "criado_em": "2026-01-01T00:00:00Z"})
    with pytest.raises(AM.ErroAmigos):
        bd.denunciar(A, _h(bd, B), "inventado")
    with pytest.raises(AM.ErroAmigos):
        bd.denunciar(A, _h(bd, A), "bio")
    assert bd.denunciar(A, _h(bd, B), "bio", "texto ofensivo") and not bd.denunciar(A, _h(bd, B), "golpe")
    den = bd.sis_denuncias()
    assert den[0]["alvo_usuario"] == "Bia" and den[0]["motivo"] == "bio" and "@x.com" not in str(den)
    assert any("Denúncia" in n["titulo"] for n in bd._selecionar("notificacoes", {"email": "adm@x.com"}, ["titulo"]))


def test_excluir_conta_apaga_relacoes(bd):
    A, B = _setup(bd, "Ana", "Bia")
    bd.amigo_pedir(A, "bia")
    bd.amigo_responder(B, _h(bd, A), True)
    bd.bloquear(A, _h(bd, B))
    bd.desbloquear(A, _h(bd, B))
    bd.amigo_pedir(A, "bia")
    bd.sis_apagar_conta(A.id, A.email)
    assert not bd.social_relacoes(B) and not bd._cfg_prefixo("amz|") and not bd._cfg_prefixo("blq|")


def test_perfil_basico_para_quem_ja_joga(bd):
    A, = _setup(bd, "Ana")
    bd._inserir("contas", {"id": "id-z", "email": "zeca@x.com", "nome": "Nome Real Zeca", "criado_em": "2026-01-01T00:00:00Z"})
    assert bd.sis_perfil_padrao("zeca@x.com", "Zeca_Bull")
    email, doc = bd.sis_perfil_por_usuario("zeca_bull")
    assert email == "zeca@x.com" and doc["usuario"] == "Zeca_Bull" and doc["nome"] == "Zeca_Bull" and "Nome Real" not in str(doc)
    assert not bd.sis_perfil_padrao("zeca@x.com", "Outro_Nome")                 # já tem perfil: não mexe
    bd._inserir("contas", {"id": "id-w", "email": "w@x.com", "nome": "W", "criado_em": "2026-01-01T00:00:00Z"})
    assert not bd.sis_perfil_padrao("w@x.com", "ana")                           # nome de outra conta: não toma
    assert bd.perfil_alvo(A, "zeca_bull")["completo"]


def test_nome_de_qualquer_ranking_leva_ao_perfil(bd, monkeypatch):
    import types
    import amigos_app as AMA
    monkeypatch.setattr(AMA, "st", types.SimpleNamespace(session_state={}))
    A, B = _setup(bd, "Ana", "Bia", priv={"Bia": {"visivel": "ninguem"}})
    bd.sis_estado_gravar(A.email, "comp_ordens", {"apelido": "AnaWallet", "apelido_k": "anawallet"})
    bd._inserir("contas", {"id": "id-z", "email": "zeca@x.com", "nome": "Nome Real Zeca", "criado_em": "2026-01-01T00:00:00Z"})
    bd.sis_estado_gravar("zeca@x.com", "comp_ordens", {"apelido": "ZecaBull", "apelido_k": "zecabull"})
    assert AMA.usuario_de_apelido("AnaWallet") == "Ana"            # apelido da Competição → nome de usuário do perfil
    assert AMA.usuario_de_apelido("ana") == "Ana"                  # o próprio nome de usuário (salas online)
    assert AMA.usuario_de_apelido("ZecaBull") == "ZecaBull"        # jogava sem perfil: ganha o perfil básico do apelido público
    assert bd.sis_perfil_por_usuario("zecabull")[0] == "zeca@x.com"
    assert AMA.usuario_de_apelido("bia") is None                   # perfil escondido de todos: sem link
    assert AMA.usuario_de_apelido("Jogador") is None and AMA.usuario_de_apelido("") is None


def test_nome_nas_salas_online_e_o_usuario_nunca_o_nome_real(bd):
    import battle_online_dados as BD
    import trader_online_dados as TOD
    A, = _setup(bd, "Ana")
    assert TOD.nick_de(A.email) == "Ana" == BD.nick_de(A.email)
    bd._inserir("contas", {"id": "id-z", "email": "zeca@x.com", "nome": "Nome Real Zeca", "criado_em": "2026-01-01T00:00:00Z"})
    assert TOD.nick_de("zeca@x.com") == "Jogador" == BD.nick_de("zeca@x.com")
