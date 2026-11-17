"""Perfil de jogador: validação, campos que o formulário não pode mudar, privacidade, nome de usuário exclusivo e permissões no banco."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import perfis as PF

TEMAS = {"sistema": "Automático", "claro": "Claro", "escuro": "Escuro"}
AGORA = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ validação
@pytest.mark.parametrize("u,ok", [("Ana_99", True), ("a.b-c", True), ("ab", False), ("com espaco", False), ("<b>x</b>", False), ("x" * 21, False), ("admin", False)])
def test_nome_de_usuario(u, ok):
    if ok:
        assert PF.validar_usuario(u) == u
    else:
        with pytest.raises(PF.ErroPerfil):
            PF.validar_usuario(u)


def test_nome_de_exibicao_bio_e_avatar():
    assert PF.validar_nome("  Ana   Souza ") == "Ana Souza"
    for ruim in ("A", "x" * 31, "Ana <script>", "admin"):
        with pytest.raises(PF.ErroPerfil):
            PF.validar_nome(ruim)
    assert PF.validar_bio("Gosto de FIIs​ e dividendos.\n\n\n\nE de gráficos.") == "Gosto de FIIs e dividendos.\n\nE de gráficos."
    for ruim in ("veja https://golpe.com", "www.site.com", "<img src=x>", "x" * 161):
        with pytest.raises(PF.ErroPerfil):
            PF.validar_bio(ruim)
    assert PF.validar_avatar("raposa_animada") == "raposa_animada"
    with pytest.raises(PF.ErroPerfil):
        PF.validar_avatar("https://minha-foto.com/x.png")              # sem imagem externa: só os avatares do app


def test_formulario_nao_muda_xp_pontos_conquistas_nem_dados_da_conta():
    atual = PF.inicial("Ana_99")
    form = {"nome": "Ana", "xp": 99999, "nivel": 50, "conquistas": 999, "pontos": 1e9, "email": "x@y.com", "id": "outro", "patrimonio": 1e9,
            "usuario_k": "zzz", "privacidade": {"publico": False, "hack": True}}
    novo, mud = PF.editar(atual, form, AGORA, TEMAS)
    assert novo["nome"] == "Ana" and novo["privacidade"]["publico"] is False and "hack" not in novo["privacidade"]
    assert not set(novo) & {"xp", "nivel", "conquistas", "pontos", "email", "id", "patrimonio"} and novo["usuario_k"] == "ana_99" and mud == {}


def test_troca_de_usuario_respeita_intervalo_e_tema_vai_para_as_preferencias():
    atual = PF.inicial("Ana_99")
    novo, mud = PF.editar(atual, {"usuario": "AnaTrader", "tema": "escuro"}, AGORA, TEMAS)
    assert mud == {"usuario": "AnaTrader", "tema": "escuro"} and novo["usuario_k"] == "anatrader" and novo["usuario_em"]
    with pytest.raises(PF.ErroPerfil):
        PF.editar(novo, {"usuario": "AnaOutra"}, AGORA + timedelta(days=2), TEMAS)
    novo2, mud2 = PF.editar(novo, {"usuario": "anatrader"}, AGORA + timedelta(days=2), TEMAS)   # só maiúsculas/minúsculas: não é troca
    assert "usuario" not in mud2 and novo2["usuario"] == "anatrader"
    assert PF.editar(novo, {"usuario": "AnaOutra"}, AGORA + timedelta(days=8), TEMAS)[1]["usuario"] == "AnaOutra"
    with pytest.raises(PF.ErroPerfil):
        PF.editar(atual, {"tema": "neon"}, AGORA, TEMAS)


# ------------------------------------------------------------------ público × privado
PROG = {"xp": 120, "nivel": 3, "titulo": "Aprendiz", "conquistas": 2, "conquistas_total": 10}
JOGOS = {"trade": {"pontos": 50.0, "partidas": 2, "vitorias": 1, "posicao": 3}, "ticker": {"vitorias": 4, "empates": 0, "derrotas": 1, "posicao": None}}


def test_perfil_publico_so_tem_campos_permitidos_e_nada_financeiro():
    doc = {**PF.inicial("Ana_99"), "bio": "Oi!", "email": "ana@x.com", "patrimonio": 123456, "carteira": [1], "saldo": 9, "senha": "x"}
    pub = PF.publico(doc, "2026-01-05T10:00:00", PROG, JOGOS)
    assert set(pub) <= set(PF.PUBLICOS) and pub["desde"] == "2026-01" and pub["nivel"] == 3 and pub["jogos"]["trade"]["posicao"] == 3
    txt = json.dumps(pub).lower()
    assert not any(f'"{k}"' in txt for k in PF.PROIBIDOS) and "ana@x.com" not in txt and "123456" not in txt


def test_privacidade_esconde_o_que_a_pessoa_desligou():
    doc = PF.editar(PF.inicial("Ana_99"), {"bio": "Oi!", "privacidade": {"mostrar_bio": False, "mostrar_nivel": False, "mostrar_jogos": False,
                                                                           "mostrar_conquistas": False}}, AGORA, TEMAS)[0]
    pub = PF.publico(doc, "2026-01-05", PROG, JOGOS)
    assert set(pub) == {"usuario", "nome", "avatar", "desde"}
    privado = PF.editar(doc, {"privacidade": {"publico": False}}, AGORA, TEMAS)[0]
    assert PF.publico(privado, "2026-01-05", PROG, JOGOS) is None and PF.publico(PF.vazio(), "", PROG, JOGOS) is None


def test_visao_privada_e_da_propria_conta():
    priv = PF.privado(PF.inicial("Ana_99"), {"id": "c1", "email": "ana@x.com", "criado_em": "2026-01-05T10:00:00"}, PROG, JOGOS, "escuro")
    assert priv["id"] == "c1" and priv["email"] == "ana@x.com" and priv["desde"] == "2026-01-05" and priv["tema"] == "escuro" and priv["xp"] == 120


def test_dados_derivados_vem_das_fontes_reais():
    import jornada as JO
    p = {"jornada": {**JO.nova_jornada(), "xp": 130}}
    pr = PF.progresso(p)
    import nivel as NV
    assert pr["xp"] == 130 and pr["nivel"] == NV.nivel_de(130) and pr["titulo"] == NV.titulo(pr["nivel"]) and pr["conquistas_total"] > 0
    import jogos as J
    doc, _ = J.registrar_trade({}, "p1", 40, 3, "rapida", 1, 2, "x")
    jg = PF.jogos(doc, {"eu": {"pos": 2}}, None)
    assert jg["trade"] == {"pontos": 40.0, "partidas": 1, "vitorias": 1, "posicao": 2} and jg["ticker"]["posicao"] is None


def test_documento_adulterado_volta_ao_padrao():
    d = PF.sanear({"usuario": "<script>", "nome": "x", "avatar": "http://x", "bio": "https://golpe", "privacidade": {"publico": "sim"}})
    assert d["usuario"] == "" and d["nome"] == "" and d["avatar"] == PF.AVATAR_PADRAO and d["bio"] == "" and d["privacidade"]["publico"] is True


# ------------------------------------------------------------------ banco: só a própria conta grava; nome de usuário exclusivo
def test_banco_reserva_exclusiva_permissoes_e_exclusao():
    import banco
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        for e in ("a@x.com", "b@x.com", "c@x.com"):
            banco._inserir("contas", {"id": "id-" + e, "email": e, "nome": e, "criado_em": "2026-01-01T00:00:00Z"})
        A, B, C_ = (banco.Ator(id="id-" + e, email=e, papel="usuario") for e in ("a@x.com", "b@x.com", "c@x.com"))
        assert banco.usuario_reservar(A, "ana_99") and banco.usuario_reservar(A, "ana_99")       # repetir para a mesma conta é ok
        assert not banco.usuario_reservar(B, "ana_99")                                           # outra conta não pega
        assert not banco.usuario_liberar(B, "ana_99") and banco.cfg_ler("usuario|ana_99")      # nem libera o nome de outra
        banco.comp_ordens_gravar(C_, {"apelido": "CaioBull", "apelido_k": "caiobull"})            # apelido antigo da Competição vale
        assert not banco.usuario_reservar(A, "caiobull") and banco.usuario_reservar(C_, "caiobull")
        with pytest.raises(ValueError):
            banco.usuario_reservar(A, "nome inválido!")
        with pytest.raises(banco.SemPermissao):
            banco.perfil_jogador_gravar(None, PF.inicial("x_x_x"))
        banco.perfil_jogador_gravar(A, PF.inicial("Ana_99"))
        assert banco.perfil_jogador_ler(B) == {}                                                 # cada um lê só o próprio
        email, doc = banco.sis_perfil_por_usuario("ana_99")
        assert email == "a@x.com" and doc["usuario"] == "Ana_99" and banco.sis_perfil_por_usuario("ninguem") is None
        banco.sis_apagar_conta("id-a@x.com", "a@x.com")                                          # excluir a conta libera o nome
        assert not banco.cfg_ler("usuario|ana_99") and banco.usuario_reservar(B, "ana_99")
