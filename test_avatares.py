"""Coleção de Avatares: catálogo, arquivos, raridades, desbloqueio, persistência e bloqueio de avatar não liberado."""
import hashlib
import os
from collections import Counter

import pytest

import avatares as AV
import perfis as PF

PASTA = os.path.join(os.path.dirname(__file__), "static", "avatares")


def test_catalogo_ids_unicos_arquivos_e_cinco_raridades():
    ids = [a["id"] for a in AV.CATALOGO]
    assert len(ids) == len(set(ids)) == 64
    assert Counter(a["raridade"] for a in AV.CATALOGO) == {"comum": 21, "raro": 14, "epico": 18, "lendario": 7, "mitico": 4}
    for a in AV.CATALOGO:
        assert set(a) >= {"id", "nome", "raridade", "desbloqueio", "disponivel", "criado_em"} and a["raridade"] in AV.RARIDADES
        assert a["desbloqueio"]["tipo"] in AV.TIPOS
        if a["arquivo"]:
            assert os.path.exists(os.path.join(PASTA, a["arquivo"])) and os.path.exists(os.path.join(PASTA, a["arquivo"].replace(".webp", "_p.webp")))
            assert AV.url(a["id"]) == "app/static/avatares/" + a["arquivo"]
        else:
            assert AV.url(a["id"]).startswith("data:image/")                    # Coleção Raposa (artes que já existiam)


def test_nenhum_personagem_duplicado_nos_arquivos():
    arqs = [f for f in os.listdir(PASTA) if f.endswith(".webp") and not f.endswith("_p.webp")]
    assert len(arqs) == 58
    hashes = [hashlib.sha256(open(os.path.join(PASTA, f), "rb").read()).hexdigest() for f in arqs]
    assert len(set(hashes)) == len(hashes)
    nomes = [a["nome"] for a in AV.CATALOGO]
    assert len(nomes) == len(set(nomes))


def test_desbloqueio_por_nivel_nas_cinco_raridades():
    def rars(nivel):
        return Counter(AV.POR_ID[i]["raridade"] for i in AV.liberados({"nivel": nivel}))
    assert rars(1) == {"comum": 21}                                            # inicial: só os comuns
    assert rars(3)["raro"] == 2 and "epico" not in rars(3)
    assert rars(10)["raro"] == 14 and rars(10)["epico"] == 3
    assert rars(20)["lendario"] == 2 and "mitico" not in rars(25)
    assert rars(30)["mitico"] == 1 and rars(50) == {"comum": 21, "raro": 14, "epico": 18, "lendario": 7, "mitico": 4}


def test_estrutura_para_conquista_loja_evento_e_temporada(monkeypatch):
    extra = [
        {**AV._item("t_conq", "Teste Conquista", "epico", {"tipo": "conquista", "valor": "primeira_licao", "nome": "Primeira lição"}), "arquivo": "lobo.webp"},
        {**AV._item("t_loja", "Teste Loja", "raro", {"tipo": "loja"}), "arquivo": "lobo.webp", "disponivel": False},
        {**AV._item("t_evento", "Teste Evento", "lendario", {"tipo": "evento", "valor": "Copa"}), "arquivo": "lobo.webp"},
    ]
    monkeypatch.setattr(AV, "CATALOGO", AV.CATALOGO + extra)
    monkeypatch.setattr(AV, "POR_ID", {a["id"]: a for a in AV.CATALOGO})
    lib = AV.liberados({"nivel": 1, "emblemas": {"primeira_licao"}, "concedidos": ["t_evento", "t_loja"]})
    assert "t_conq" in lib and "t_evento" in lib and "t_loja" not in lib         # loja indisponível não libera nem com concessão
    assert AV.como_liberar(AV.POR_ID["t_loja"]) == "Em breve na Loja Ticker" and "Primeira lição" in AV.como_liberar(AV.POR_ID["t_conq"])
    assert AV.como_liberar(AV.POR_ID["leao"]) == "Chegue ao nível 20"


def test_equipar_so_liberado_e_colecao_guardada():
    lib = AV.liberados({"nivel": 1})
    assert AV.pode_equipar("panda", lib) and not AV.pode_equipar("dragao", lib) and not AV.pode_equipar("inventado", lib)
    doc, novos = AV.sincronizar({}, {"nivel": 3}, "2026-11-18")
    assert "urso" in novos and doc["em"]["urso"] == "2026-11-18"
    assert "urso" in AV.liberados({"nivel": 1}, doc["ids"])                       # o que já foi liberado continua valendo
    assert AV.sanear_colecao({"ids": ["leao", "<script>"], "concedidos": ["x"]})["ids"] == ["leao"]
    with pytest.raises(ValueError):
        AV.conceder({}, "nao_existe", "2026-11-18")


def test_moldura_aplicada_pela_interface():
    h = AV.html("leao", 40)
    assert "r-lendario" in h and "--s:40px" in h and "leao_p.webp" in h          # pequeno: arquivo de 96 px
    assert "r-mitico" in AV.html("dragao", 120) and "dragao.webp" in AV.html("dragao", 120)
    assert "r-foto" in AV.html(None, 50, foto="data:image/webp;base64,AAAA")
    assert "r-comum" in AV.html("inexistente", 50)                               # inválido volta ao padrão
    css = AV.css()
    assert all(f".thav.r-{r}" in css for r in AV.RARIDADES) and "prefers-reduced-motion" in css
    assert PF.validar_avatar("touro_cyber") == "touro_cyber"
    with pytest.raises(PF.ErroPerfil):
        PF.validar_avatar("../../etc/passwd")


# ------------------------------------------------------------------ banco e serviço
def test_banco_colecao_da_propria_conta_e_concessao_so_do_sistema():
    import banco
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        banco._inserir("contas", {"id": "id-a", "email": "a@x.com", "nome": "A", "criado_em": "2026-01-01T00:00:00Z"})
        A = banco.Ator(id="id-a", email="a@x.com", papel="usuario")
        with pytest.raises(banco.SemPermissao):
            banco.avatares_colecao_ler(None)
        banco.avatares_colecao_gravar(A, {"ids": ["panda"], "concedidos": ["dragao"]})   # a tela não consegue se conceder nada
        assert banco.avatares_colecao_ler(A)["concedidos"] == []
        banco.sis_avatar_conceder("a@x.com", "dragao", "2026-11-18")
        d = banco.avatares_colecao_ler(A)
        assert d["concedidos"] == ["dragao"] and "dragao" in d["ids"]
        banco.avatares_colecao_gravar(A, {"ids": ["panda"]})
        assert banco.avatares_colecao_ler(A)["concedidos"] == ["dragao"]               # gravar pela tela não apaga a concessão


def test_salvar_recusa_avatar_bloqueado_e_persiste_o_liberado(monkeypatch):
    import types

    import banco
    import perfis_app as PA
    import usuarios
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        banco._inserir("contas", {"id": "id-a", "email": "a@x.com", "nome": "A", "criado_em": "2026-01-01T00:00:00Z"})
        A = banco.Ator(id="id-a", email="a@x.com", papel="usuario")
        sess = types.SimpleNamespace(session_state={})
        monkeypatch.setattr(PA, "st", sess)
        monkeypatch.setattr(usuarios, "ator", lambda: A)
        monkeypatch.setattr(PA, "_ctx_colecao", lambda: {"nivel": 1, "emblemas": set()})
        form = {"nome": "Ana", "usuario": "ana_99", "bio": "", "tema": "sistema", "privacidade": dict(PF.PRIVACIDADE_PADRAO)}
        ok, msg = PA.salvar({**form, "avatar": "leao"})
        assert not ok and "bloqueado" in msg and "nível 20" in msg
        assert PA.salvar({**form, "avatar": "coruja"})[0]
        sess.session_state.clear()                                                     # sair e entrar de novo
        assert PA.meu_perfil()["avatar"] == "coruja" and PA.meu_avatar()["rar"] == "comum"
        monkeypatch.setattr(PA, "_ctx_colecao", lambda: {"nivel": 35, "emblemas": set()})
        sess.session_state.clear()
        assert PA.salvar({**form, "avatar": "dragao"})[0] and PA.meu_avatar()["rar"] == "mitico"
        assert "dragao" in banco.avatares_colecao_ler(A)["ids"]                        # a coleção liberada ficou guardada
        assert "r-mitico" in PA.avatar_html_email("a@x.com", 40)


def test_mesa_recebe_avatar_de_cada_assento_sem_email(monkeypatch):
    import perfis_app as PA
    import trader_battle_app as TBA
    monkeypatch.setattr(TBA, "_email_online", lambda: "eu@x.com")
    monkeypatch.setattr(PA, "meu_avatar", lambda: {"id": "panda", "foto": "", "src": "", "src_p": "", "rar": "comum"})
    monkeypatch.setattr(PA, "avatar_de_email", lambda e: {"b@x.com": ("dragao", ""), "c@x.com": ("foto", "data:image/webp;base64,AAA")}.get(e, ("raposa", "")))
    m = TBA._avatares_assentos({"jogadores": ["b@x.com", "eu@x.com", "c@x.com"]})
    assert set(m) == {"Jogador 1", "Você", "Jogador 3"}
    assert m["Jogador 1"] == {"src": "/app/static/avatares/dragao_p.webp", "cor": AV.RARIDADES["mitico"]["cor"]}
    assert m["Você"]["src"].endswith("panda_p.webp") and m["Jogador 3"]["src"].startswith("data:image/webp")
    assert "@" not in str(m)
    assert TBA._avatares_assentos({"jogadores": ["solo"]})["Você"]["src"].endswith("panda_p.webp")


def test_icones_de_setor():
    import setores as SE
    for i in SE.IDS:
        assert os.path.exists(os.path.join(os.path.dirname(__file__), "static", "setores", f"{i}.webp"))
    assert SE.icone("Bancos").endswith("bancos.webp") and SE.icone("Energia Elétrica").endswith("energia.webp")
    assert SE.id_do_setor("Lajes corporativas") == "construcao" and SE.id_do_setor("Siderurgia e aço") == "siderurgia"
    assert SE.icone("Educação") == "" and SE.icone(None) == ""
