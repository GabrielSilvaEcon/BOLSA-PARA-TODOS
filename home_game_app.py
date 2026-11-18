"""Adaptador do Streamlit para a Home "mobile game": lê os dados que o app já tem e desenha os blocos de home_game.py.

Nada aqui grava dados nem muda regra de XP, Ticker Coins, ranking, missões ou jogos. Cada bloco lê o seu dado dentro de try/except:
se um falhar, aparece o estado vazio dele e o resto da tela continua.
"""
from __future__ import annotations

import streamlit as st

import game_ui as G
import home_game as HG


# ------------------------------------------------------------------ leitura dos dados (sempre com reserva, nunca derruba a tela)
def _xp(educacao_app) -> int | None:
    try:
        import jornada
        return int(jornada.resumo(educacao_app.prog())["xp"])
    except Exception:
        return None


def _nome() -> str:
    try:
        import perfis_app
        n = (perfis_app.meu_perfil() or {}).get("usuario")
        if n:
            return str(n)
    except Exception:
        pass
    try:
        import usuarios
        return usuarios.primeiro_nome() or "Jogador"
    except Exception:
        return "Jogador"


def _moedas():
    try:
        import tickercoins_app
        return tickercoins_app.saldo_atual()
    except Exception:
        return None


def _posicao() -> tuple[int | None, int | None]:
    """(posição, total de jogadores) no ranking geral: a mesma leitura que o ranking da Home sempre usou. Sem carteira no jogo, (None, total)."""
    try:
        import home_app
        import home_dados as HD
        import ranking_parcial as RP
        logado, participa, est, apelido, rk = home_app._jogo()
        listas, rotulo = RP.escolher(rk)
        geral = listas.get("geral") or []
        mr = (est or {}).get("rank") or {}
        n = mr.get("n")
        total = listas.get("geral_n") if rotulo else ((n.get("geral") if isinstance(n, dict) else n) or listas.get("geral_n"))
        r = HD.ranking_resumo(geral, total, None if rotulo else mr.get("geral"), apelido if participa else None, None)
        eu = r.get("eu")
        return (eu["pos"] if eu else None), r.get("total")
    except Exception:
        return None, None


def _missoes(educacao_app) -> dict:
    try:
        import jogar
        return HG.resumo_missoes(jogar.resumo(educacao_app.prog())["missoes"])
    except Exception:
        return HG.resumo_missoes([])


def _passe(educacao_app) -> dict | None:
    """Situação do passe da temporada (o "Hunter Pass" da Home): marcos feitos, total e progresso até o próximo."""
    try:
        from datetime import datetime, timedelta, timezone
        import jornada as JO
        import passe as PA
        hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).date()          # horário de Brasília
        return PA.estado(JO._jor(educacao_app.prog())["xp_dia"], hoje)
    except Exception:
        return None


def _moeda_html() -> str:
    try:
        import moedas_arte
        return moedas_arte.img("tc", 20)
    except Exception:
        return "🪙"


# ------------------------------------------------------------------ tela
def _cartao_botao(chave: str, html_cartao: str, rotulo: str, ir, destino: str, estado: dict | None = None) -> None:
    """Cartão HTML que é botão inteiro: o st.button fica por cima, invisível (CSS em game_ui.css_cartao_botao)."""
    with st.container(key=chave):
        st.markdown(html_cartao, unsafe_allow_html=True)
        st.button(rotulo, key=f"{chave}_b", on_click=ir, args=(destino, estado) if estado else (destino,))


def renderizar(ir, mercado_fn, educacao_app) -> None:
    """Desenha a Home: HUD (nível, Ticker Coins, ranking), banner com o Hunter Pass, Pregão Orbit, missões e os três acessos.
    `ir(destino, estado=None)`: navega (a _ir_home do app). `mercado_fn()`: cotações já em cache (a mesma do bloco 'Mercado hoje').
    `educacao_app`: o módulo que guarda o progresso de estudo (XP, passe e missões)."""
    botoes = ("hg_hud_nivel", "hg_hud_tc", "hg_hud_rk", "hg_ban", "hg_miss", "hg_ac_carteira", "hg_ac_jogar", "hg_ac_mercado")
    st.markdown(G.css_base() + HG.css() + "".join(G.css_cartao_botao(k) for k in botoes), unsafe_allow_html=True)
    nivel = None
    xp = _xp(educacao_app)
    if xp is not None:
        try:
            import nivel as NV
            nivel = NV.estado(xp)
        except Exception:
            nivel = None
    pos, total = _posicao()
    try:
        itens = mercado_fn() or []
    except Exception:
        itens = []
    with st.container(key="hg_tela"):
        with st.container(key="hg_hud"):
            _cartao_botao("hg_hud_nivel", HG.html_hud_nivel(nivel), "Meu nível e perfil", ir, "perfil")
            _cartao_botao("hg_hud_tc", HG.html_hud_moedas(_moedas(), _moeda_html()), "Ticker Coins e loja", ir, "economia")
            _cartao_botao("hg_hud_rk", HG.html_hud_rank(pos, total), "Ranking", ir, "jogos-ranking")
        _cartao_botao("hg_ban", HG.html_banner(_nome(), _passe(educacao_app)), "Abrir o Hunter Pass", ir, "jornada", {"jor_vista": "passe"})
        st.markdown(HG.html_orbit(itens), unsafe_allow_html=True)
        _cartao_botao("hg_miss", HG.html_missoes(_missoes(educacao_app)), "Ver todas as missões", ir, "missoes")
        with st.container(key="hg_acessos"):
            for chave, rot, destino in HG.ACESSOS:
                _cartao_botao(f"hg_ac_{chave}", HG.html_acesso(chave), rot, ir, destino)
