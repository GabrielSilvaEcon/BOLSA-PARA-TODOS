"""Tela de Ranking (ranking_app + ranking_visual): dados dos três rankings, filtro de amigos e HTML das linhas."""
import types

import pytest

import jogos as J
import perfis as PF
import ranking_visual as RV
from test_perfil_foto import _contas

GENTE = (("eu@x.com", "Wall Sticker", "wall_s", 6.8, 4), ("lobo@x.com", "xLoboTH", "xlobo", 41.6, 12),
         ("bia@x.com", "Bia Trader", "bia_t", 12.0, 3), ("leo@x.com", "Léo", "leo_b", -2.5, 1))


@pytest.fixture
def mundo(monkeypatch):
    import amigos_app as AMA
    import banco
    import jogos_app as JA
    import perfis_app as PA
    import ranking_app as RA
    import usuarios
    from test_trader_mesa import banco_isolado
    with banco_isolado():
        atores = _contas(banco, *[g[0] for g in GENTE])
        for a, (em, nome, us, pts, v) in zip(atores, GENTE):
            banco.perfil_jogador_gravar(a, {**PF.vazio(), "nome": nome, "usuario": us, "usuario_k": us})
            d = J.vazio()
            d["apelido"] = us
            d[J.TRADE].update(pts=pts, partidas=5, vitorias=2, melhor=3.0)
            d[J.TICKER].update(v=v, e=0, d=1)
            banco.jogos_placar_gravar(a, d)
        h = banco._h_conta
        banco.cfg_gravar(f"amz|{h('eu@x.com')}|{h('bia@x.com')}", {"estado": "amigos", "em": "2026-11-01"})
        ss = {}
        for m in (AMA, PA, RA, JA):
            monkeypatch.setattr(m, "st", types.SimpleNamespace(session_state=ss))
        for f in ("_placares", "_emails_por_hash", "_usuarios_por_hash"):          # sem o cache do Streamlit no teste
            monkeypatch.setattr(JA, f, getattr(JA, f).__wrapped__)
        monkeypatch.setattr(JA, "sincronizar_ticker", lambda *a, **k: None)
        monkeypatch.setattr(usuarios, "ator", lambda: atores[0])
        monkeypatch.setattr(usuarios, "usuario", lambda: {"email": "eu@x.com", "id": atores[0].id})
        yield types.SimpleNamespace(RA=RA, CA=__import__("competicao_app"), monkeypatch=monkeypatch)


def test_trade_ordena_por_pontos_com_nome_do_perfil(mundo):
    ln = mundo.RA._linhas_jogo(J.TRADE)
    assert [r["nome"] for r in ln] == ["xLoboTH", "Bia Trader", "Wall Sticker", "Léo"]
    assert [r["pos"] for r in ln] == [1, 2, 3, 4]
    eu = next(r for r in ln if r["eu"])
    assert eu["sub"] == "Você · 5 partidas" and eu["usuario"] is None
    assert ln[0]["sub"] == "@xlobo · 5 partidas" and ln[0]["valor"].endswith("pts")


def test_ticker_ordena_por_vitorias(mundo):
    ln = mundo.RA._linhas_jogo(J.TICKER)
    assert [r["nome"] for r in ln][:2] == ["xLoboTH", "Wall Sticker"]
    assert ln[0]["valor"] == "12 vit."


def test_amigos_mostra_so_voce_e_amigos_renumerados(mundo):
    ln = mundo.RA._so_amigos(mundo.RA._linhas_jogo(J.TRADE))
    assert [(r["pos"], r["nome"]) for r in ln] == [(1, "Bia Trader"), (2, "Wall Sticker")]


def test_carteira_usa_o_ranking_publicado(mundo):
    rk = {"listas": {"geral": [{"apelido": "xlobo", "ret": 0.125, "pat": 11250.0, "dias": 9},
                               {"apelido": "wall_s", "ret": 0.032, "pat": 10320.0, "dias": 9}]}, "dia": "2026-11-18"}
    mundo.monkeypatch.setattr(mundo.CA, "_publico", lambda chave: rk)
    mundo.monkeypatch.setattr(mundo.CA, "_pessoa", lambda a: {"perfil": {"apelido": "wall_s"}})
    ln = mundo.RA._linhas_carteira()
    assert [(r["pos"], r["nome"], r["eu"]) for r in ln] == [(1, "xLoboTH", False), (2, "Wall Sticker", True)]
    assert ln[0]["valor"].startswith("+12,5")


def test_linha_html_destaca_o_primeiro_e_voce():
    h1 = RV.html_linha({"pos": 1, "nome": "Ana <b>", "sub": "@ana", "valor": "+3,0 pts", "src": "", "eu": False})
    assert "rk-lin top" in h1 and "&lt;b&gt;" in h1 and "👑" in h1
    h2 = RV.html_linha({"pos": 7, "nome": "Eu", "sub": "Você", "valor": "1 vit.", "src": "x.webp", "eu": True})
    assert " eu'" in h2 and "x.webp" in h2


def test_abas_na_ordem_da_referencia():
    assert [a[1] for a in RV.ABAS] == ["Ticker Battle", "Trade Battle", "Carteira"]


def test_trade_lucratividade_retorno_e_qualidade_formatados(mundo):
    import banco
    import jogos as J
    from test_perfil_foto import _contas  # noqa: F401
    for em, lista in {"lobo@x.com": [(800.0, 4.0, 70)] * 3, "bia@x.com": [(100.0, 9.0, 95)] * 3}.items():
        a = banco.Ator(id="id-" + em, email=em, papel="usuario")
        d = banco.jogos_placar_ler(a)
        for i, (lc, rt, ql) in enumerate(lista):
            d, _ = J.registrar_trade(d, f"{em}{i}", 5, 1, "rapida", None, 1, "x", lucro=lc, retorno=rt, qualidade=ql)
        banco.jogos_placar_gravar(a, d)
    luc = mundo.RA._linhas_jogo(J.TRADE, "lucro")
    assert [r["nome"] for r in luc] == ["xLoboTH", "Bia Trader"] and luc[0]["valor"].startswith("+") and "T$" in luc[0]["valor"]
    ret = mundo.RA._linhas_jogo(J.TRADE, "retorno")
    assert ret[0]["nome"] == "Bia Trader" and ret[0]["valor"] == "+9,00%"
    qual = mundo.RA._linhas_jogo(J.TRADE, "qualidade")
    assert qual[0]["valor"] == "95/100" and qual[0]["sub"].endswith("3 partidas")
