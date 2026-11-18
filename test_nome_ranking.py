"""Nome e foto do perfil nos rankings: qualquer nome público (apelido da Competição, NickName do placar dos jogos, @usuário ou nome de
exibição) leva à conta da pessoa, e o ranking mostra o nome do perfil dela."""
import base64
import types

import pytest

import perfil_foto as FT
import perfis as PF
from test_perfil_foto import _contas, _img


@pytest.fixture
def mundo(monkeypatch):
    import amigos_app as AMA
    import banco
    import jogos as J
    import perfis_app as PA
    import usuarios
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        A, B, C = _contas(banco, "a@x.com", "b@x.com", "c@x.com")
        sess = {"logado": B}
        ss = {}
        monkeypatch.setattr(PA, "st", types.SimpleNamespace(session_state=ss))
        monkeypatch.setattr(AMA, "st", types.SimpleNamespace(session_state=ss))
        monkeypatch.setattr(usuarios, "ator", lambda: sess["logado"])

        def entrar(ator):
            sess["logado"] = ator
            ss.clear()
        base = {"bio": "", "avatar": "raposa", "tema": "sistema", "privacidade": dict(PF.PRIVACIDADE_PADRAO)}
        entrar(A)
        assert PA.salvar({**base, "nome": "Ana Trader", "usuario": "ana_99"})[0]
        banco.jogos_placar_gravar(A, {**J.vazio(), "apelido": "anaplay"})       # NickName antigo, de quando jogou
        entrar(C)
        assert PA.salvar({**base, "nome": "Carlos", "usuario": "carlos_x",
                          "privacidade": {**PF.PRIVACIDADE_PADRAO, "visivel": "ninguem"}})[0]
        banco.jogos_placar_gravar(C, {**J.vazio(), "apelido": "cacau"})
        entrar(B)
        yield types.SimpleNamespace(AMA=AMA, PA=PA, A=A, B=B, C=C, entrar=entrar, base=base)


def test_ranking_mostra_o_nome_do_perfil(mundo):
    AMA = mundo.AMA
    assert AMA.nome_exibicao("anaplay") == "Ana Trader"          # NickName do placar
    assert AMA.nome_exibicao("ANA_99") == "Ana Trader"           # @usuário, sem diferença de maiúsculas
    assert AMA.nome_exibicao("ana trader") == "Ana Trader"       # nome de exibição
    assert AMA.nome_exibicao("desconhecido") == "desconhecido"   # sem conta achada: fica o nome do ranking
    assert AMA.nome_exibicao("cacau") == "cacau"                 # perfil oculto: o nome do perfil não aparece


def test_foto_acha_a_conta_pelo_nickname_do_placar(mundo):
    AMA, PA = mundo.AMA, mundo.PA
    mundo.entrar(mundo.A)
    foto = FT.processar(_img(cor=(255, 0, 0)))
    assert PA.salvar({**mundo.base, "nome": "Ana Trader", "usuario": "ana_99", "avatar": PF.FOTO}, foto_webp=foto)[0]
    mundo.entrar(mundo.B)
    html = AMA.avatar_por_apelido("anaplay", 30) or ""
    assert base64.b64encode(foto).decode()[:40] in html          # a foto nova, mesmo com o apelido antigo


def test_nome_novo_aparece_logo_depois_de_salvar(mundo):
    AMA, PA = mundo.AMA, mundo.PA
    mundo.entrar(mundo.A)
    assert AMA.nome_exibicao("anaplay") == "Ana Trader"
    assert PA.salvar({**mundo.base, "nome": "Ana Investe", "usuario": "ana_99"})[0]
    assert AMA.nome_exibicao("anaplay") == "Ana Investe"         # o índice da sessão é renovado ao salvar
