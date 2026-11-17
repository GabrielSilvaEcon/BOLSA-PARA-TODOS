"""Foto de perfil (validação, recorte, reprocessamento) e o serviço de edição do perfil (salvar, foto, usuário duplicado, persistência)."""
import base64
import io
import types

import pytest
from PIL import Image

import perfil_foto as FT
import perfis as PF


def _img(fmt="PNG", tam=(400, 300), modo="RGB", cor=(200, 40, 90), exif_rot=None) -> bytes:
    im = Image.new(modo, tam, cor if modo != "RGBA" else cor + (120,))
    b = io.BytesIO()
    if exif_rot:
        ex = Image.Exif()
        ex[0x0112] = exif_rot
        im.save(b, fmt, exif=ex)
    else:
        im.save(b, fmt)
    return b.getvalue()


# ------------------------------------------------------------------ imagem
@pytest.mark.parametrize("fmt,nome", [("PNG", "png"), ("JPEG", "jpeg"), ("WEBP", "webp")])
def test_formato_pelos_bytes_e_saida_webp_quadrada(fmt, nome):
    dados = _img(fmt)
    assert FT.formato(dados) == nome
    out = FT.processar(dados)
    assert FT.formato(out) == "webp" and len(out) <= FT.MAX_SAIDA_KB * 1024
    assert Image.open(io.BytesIO(out)).size == (FT.LADO, FT.LADO)


def test_recusa_formato_falso_corrompido_vazio_grande_e_pequeno():
    with pytest.raises(FT.ErroFoto, match="Formato"):
        FT.processar(b"GIF89a" + b"\0" * 200)                                        # GIF (ou .exe renomeado) não passa
    with pytest.raises(FT.ErroFoto, match="Formato"):
        FT.processar(b"<svg onload=alert(1)></svg>")
    with pytest.raises(FT.ErroFoto, match="corrompido"):
        FT.processar(_img()[:60])                                                      # PNG truncado
    with pytest.raises(FT.ErroFoto, match="Nenhuma"):
        FT.processar(b"")
    with pytest.raises(FT.ErroFoto, match="limite"):
        FT.processar(b"\x89PNG\r\n\x1a\n" + b"\0" * (FT.TAM_MAX_MB * 1024 * 1024 + 1))
    with pytest.raises(FT.ErroFoto, match="pequena"):
        FT.processar(_img(tam=(40, 40)))


def test_recusa_bomba_de_pixels(monkeypatch):
    monkeypatch.setattr(FT, "MAX_PIXELS", 10_000)
    with pytest.raises(FT.ErroFoto, match="pixels"):
        FT.processar(_img(tam=(200, 200)))


def test_transparencia_rotacao_e_metadados_descartados():
    out = Image.open(io.BytesIO(FT.processar(_img(modo="RGBA"))))
    assert out.mode == "RGB" and not out.info.get("exif")
    em_pe = FT.abrir(_img("JPEG", tam=(400, 200), exif_rot=6))                         # foto de celular girada 90°
    assert em_pe.size == (200, 400)


def test_recorte_zoom_e_posicao():
    im = Image.new("RGB", (400, 200))
    im.paste((255, 0, 0), (0, 0, 200, 200))                                           # metade esquerda vermelha
    im.paste((0, 0, 255), (200, 0, 400, 200))
    esq = FT.recortar(im, 1.0, -1.0, 0.0, 50).getpixel((25, 25))
    dir_ = FT.recortar(im, 1.0, 1.0, 0.0, 50).getpixel((25, 25))
    assert esq[0] > 200 and dir_[2] > 200
    assert FT.recortar(im, 99, 5, -5, 80).size == (80, 80)                            # valores fora da faixa são limitados


def test_documento_e_uri_so_aceitam_webp_valido():
    w = FT.processar(_img())
    doc = FT.documento(w, "2026-11-17T10:00:00+00:00")
    assert set(doc) == {"v", "webp", "h", "em"} and FT.uri(doc).startswith("data:image/webp;base64,")
    with pytest.raises(FT.ErroFoto):
        FT.documento(_img(), "x")                                                     # PNG cru não é aceito como foto final
    assert FT.uri({"webp": base64.b64encode(b"<script>").decode()}) == ""
    assert FT.uri({"webp": "não é base64!"}) == "" and FT.uri(None) == ""


# ------------------------------------------------------------------ banco e serviço
def _contas(banco, *emails):
    for e in emails:
        banco._inserir("contas", {"id": "id-" + e, "email": e, "nome": e, "criado_em": "2026-01-01T00:00:00Z"})
    return [banco.Ator(id="id-" + e, email=e, papel="usuario") for e in emails]


def test_banco_foto_so_da_propria_conta_e_validada():
    import banco
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        A, B = _contas(banco, "a@x.com", "b@x.com")
        doc = FT.documento(FT.processar(_img()), "2026-11-17")
        with pytest.raises(banco.SemPermissao):
            banco.perfil_foto_gravar(None, doc)
        with pytest.raises(banco.SemPermissao):
            banco.perfil_foto_ler(None)
        with pytest.raises(ValueError):
            banco.perfil_foto_gravar(A, {"webp": base64.b64encode(_img()).decode()})    # não é WebP
        banco.perfil_foto_gravar(A, {**doc, "extra": "x" * 50})
        salvo = banco.perfil_foto_ler(A)
        assert salvo["webp"] == doc["webp"] and "extra" not in salvo
        assert not banco.perfil_foto_ler(B)                                             # outra conta não vê
        banco.perfil_foto_apagar(A)
        assert FT.uri(banco.perfil_foto_ler(A)) == ""


@pytest.fixture
def servico(monkeypatch):
    """perfis_app com sessão falsa e a conta logada trocável (sem servidor Streamlit)."""
    import banco
    import perfis_app as PA
    import usuarios
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        A, B = _contas(banco, "a@x.com", "b@x.com")
        sess = {"logado": A}
        st_falso = types.SimpleNamespace(session_state={})
        monkeypatch.setattr(PA, "st", st_falso)
        monkeypatch.setattr(usuarios, "ator", lambda: sess["logado"])

        def trocar(ator):                                                               # "sair e entrar de novo" com outra conta
            sess["logado"] = ator
            st_falso.session_state.clear()
        yield types.SimpleNamespace(PA=PA, banco=banco, A=A, B=B, ss=st_falso.session_state, trocar=trocar)


def _form(**kw):
    base = {"nome": "Ana", "usuario": "ana_99", "bio": "", "avatar": "raposa", "tema": "sistema", "privacidade": dict(PF.PRIVACIDADE_PADRAO)}
    return {**base, **kw}


def test_salvar_edita_e_persiste_apos_sair_e_entrar(servico):
    PA, s = servico.PA, servico
    ok, msg = PA.salvar(_form(nome="Ana Trader", bio="Gosto de dividendos."))
    assert ok and msg == "Perfil atualizado!"
    assert s.ss["_pj_doc"]["nome"] == "Ana Trader"                                    # a interface usa o valor novo na hora
    s.trocar(s.A)                                                                       # sessão nova: lê do banco
    p = PA.meu_perfil()
    assert (p["nome"], p["usuario"], p["bio"]) == ("Ana Trader", "ana_99", "Gosto de dividendos.")


def test_usuario_duplicado_e_recusado_e_nada_muda(servico):
    PA, s = servico.PA, servico
    assert PA.salvar(_form())[0]
    s.trocar(s.B)
    assert PA.salvar(_form(nome="Bia", usuario="bia_1"))[0]
    ok, msg = PA.salvar(_form(nome="Bia", usuario="ANA_99", bio="tentei"))             # mesmo nome com outra caixa
    assert not ok and "em uso" in msg
    s.trocar(s.B)
    assert PA.meu_perfil()["usuario"] == "bia_1" and PA.meu_perfil()["bio"] == ""


def test_validacao_com_mensagem_clara_e_campos_proibidos_ignorados(servico):
    PA, s = servico.PA, servico
    ok, msg = PA.salvar(_form(usuario="a b"))
    assert not ok and msg
    ok, msg = PA.salvar(_form(bio="veja http://golpe.com"))
    assert not ok and msg
    assert PA.salvar({**_form(), "xp": 99999, "pontos": 1e9, "conquistas": ["tudo"], "email": "x@y.com"})[0]
    doc = s.banco.perfil_jogador_ler(s.A)
    assert not {"xp", "pontos", "conquistas", "email"} & set(doc)


def test_foto_enviada_substituida_e_removida(servico):
    PA, s = servico.PA, servico
    f1 = FT.processar(_img(cor=(255, 0, 0)))
    assert PA.salvar(_form(avatar=PF.FOTO), foto_webp=f1)[0]
    s.trocar(s.A)
    assert PA.meu_perfil()["avatar"] == PF.FOTO and PA.minha_foto_uri().endswith(base64.b64encode(f1).decode())
    f2 = FT.processar(_img(cor=(0, 255, 0)))                                             # substituir depois
    assert PA.salvar(_form(avatar=PF.FOTO), foto_webp=f2)[0]
    assert PA.minha_foto_uri().endswith(base64.b64encode(f2).decode())                 # cache da foto foi renovado
    assert PA.salvar(_form(avatar=PF.FOTO), remover_foto=True)[0]
    s.trocar(s.A)
    assert PA.meu_perfil()["avatar"] == PF.AVATAR_PADRAO and PA.minha_foto_uri() == ""


def test_foto_escolhida_sem_arquivo_volta_ao_avatar_e_falha_de_gravacao_e_clara(servico, monkeypatch):
    PA, s = servico.PA, servico
    assert PA.salvar(_form(avatar=PF.FOTO))[0]
    assert PA.meu_perfil()["avatar"] == PF.AVATAR_PADRAO
    antes = dict(PA.meu_perfil())

    def falha(*a, **k):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(s.banco, "perfil_foto_gravar", falha)
    ok, msg = PA.salvar(_form(nome="Outro"), foto_webp=FT.processar(_img()))
    assert not ok and "Tente de novo" in msg
    s.trocar(s.A)
    assert PA.meu_perfil()["nome"] == antes["nome"]                                     # nada ficou pela metade


def test_cancelar_descarta_rascunho_sem_tocar_no_salvo(servico):
    PA, s = servico.PA, servico
    assert PA.salvar(_form(nome="Ana Salva"))[0]
    s.ss.update(pe_nome="Rascunho", pe_bio="não salvar", pe_foto=b"x")
    PA._cancelar()
    assert not any(k in s.ss for k in ("pe_nome", "pe_bio", "pe_foto")) and s.ss["_nav_pend"] == "perfil"
    s.trocar(s.A)
    assert PA.meu_perfil()["nome"] == "Ana Salva"


def test_estatisticas_nao_editaveis_vem_do_placar():
    import jogos as J
    d, _ = J.registrar_trade({}, "p1", 12.0, 3, "rapida", 1, 3, "2026-11-17")
    d, _ = J.registrar_trade(d, "p2", -4.0, 3, "rapida", 2, 2, "2026-11-17")
    d, _ = J.registrar_trade(d, "p3", 5.0, 3, "rapida", 1, 1, "2026-11-17")            # solo: partida, mas sem vitória/derrota
    d, _ = J.registrar_ticker(d, "d1", "vitoria", "online", "2026-11-17")
    d, _ = J.registrar_ticker(d, "d2", "empate", "online", "2026-11-17")
    e = J.estatisticas(d)
    assert (e["partidas"], e["vitorias"], e["derrotas"], e["empates"], e["disputadas"]) == (5, 2, 1, 1, 4)
    assert e["taxa"] == 50.0 and J.estatisticas({})["taxa"] is None
