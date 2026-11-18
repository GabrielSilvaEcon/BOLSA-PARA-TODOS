"""Tela de Ranking (tela inteira, formato mobile game): Ticker Battle, Trade Battle e Carteira, Global ou só Amigos.

Só leitura: nada aqui grava pontos, vitórias ou retorno. Os dados vêm das mesmas fontes de antes (placar dos jogos em jogos_app e ranking
publicado da Competição/Wallet Game). O nome e a foto de cada pessoa são os do perfil dela (amigos_app). O desenho fica em ranking_visual.py.
"""
from __future__ import annotations

import streamlit as st

import banco
import game_ui as G
import jogos as J
import ranking_visual as RV
import usuarios

VISIVEIS = 10          # linhas antes do "ver mais"
LIMITE = 50            # linhas com "ver mais"


def _ss():
    return st.session_state


def _ir(dest: str) -> None:
    _ss()["_nav_pend"] = dest


def _ator():
    try:
        return usuarios.ator()
    except Exception:
        return None


# ------------------------------------------------------------------ avatar, nome e link de cada linha (tudo pelo perfil)
def _meu_src() -> str:
    try:
        import perfis_app as PA
        return PA.meu_avatar()["src_p"]
    except Exception:
        return ""


def _src_de_email(email: str | None) -> str:
    import avatares as AV
    if not email:
        return AV.url(AV.PADRAO, True)
    try:
        import perfis_app as PA
        av, foto = PA.avatar_de_email(email)
        return foto or AV.url(av, True)
    except Exception:
        return AV.url(AV.PADRAO, True)


def _sub(usuario: str | None, eu: bool, extra: str = "") -> str:
    base = "Você" if eu else (f"@{usuario}" if usuario else "")
    return " · ".join(x for x in (base, extra) if x)


# ------------------------------------------------------------------ dados
def _linhas_jogo(jogo: str) -> list[dict] | None:
    """[{pos, nome, sub, valor, src, eu, email}] do Trade Battle ou do Ticker Battle. None se o banco não responder."""
    import amigos_app as AMA
    import jogos_app as JA
    if jogo == J.TICKER:
        try:
            JA.sincronizar_ticker()
        except Exception:
            pass
    rk = JA.ranking(jogo)
    if rk is None:
        return None
    try:
        emails = JA._emails_por_hash()
        usuarios_h = JA._usuarios_por_hash()
    except Exception:
        emails, usuarios_h = {}, {}
    eu_email = (usuarios.usuario() or {}).get("email")
    out = []
    for x in rk["linhas"][:LIMITE] + ([rk["eu"]] if rk.get("eu") and rk["eu"]["pos"] > LIMITE else []):
        email = eu_email if x["eu"] else emails.get(x["h"])
        valor = JA._fmt_valor(jogo, x["valor"]).replace(" vitórias", " vit.").replace(" vitória", " vit.")
        out.append({"pos": x["pos"], "nome": AMA.nome_de_email(email, x.get("apelido", "")), "valor": valor, "eu": x["eu"], "email": email,
                    "usuario": None if x["eu"] else usuarios_h.get(x["h"]),
                    "src": _meu_src() if x["eu"] else _src_de_email(email)})
    for r in out:
        r["sub"] = _sub(r["usuario"], r["eu"])
    return out


def _linhas_carteira() -> list[dict] | None:
    """Ranking da Carteira (Competição/Wallet Game), pelo retorno, como na aba Classificação."""
    import amigos_app as AMA
    import classificacao_visual as CV2
    import competicao_app as CA
    import ranking_ligas as RL
    import ranking_parcial as RP
    import wallet_game as WG
    try:
        rk = CA._publico("comp_ranking")
    except Exception as e:
        banco.registrar_erro("ranking_app.carteira", e)
        return None
    listas, _rot = RP.escolher(rk)
    a = _ator()
    apelido = ""
    if a:
        try:
            apelido = CA._pessoa(a)["perfil"].get("apelido") or ""
        except Exception:
            apelido = ""
    base = [(n, m, c) for _i, n, m, c in WG.RANKS]
    linhas = RL.montar(listas, RL.PERIODOS["Geral"], base, 10_000.0, {"apelido": apelido, "patrimonio": None} if apelido else None)
    itens = RL.ordenar(linhas, RL.ORDENS[0], None, topo=LIMITE)
    eu_email = (usuarios.usuario() or {}).get("email")
    out = []
    for r in itens:
        email = eu_email if r.get("eu") else AMA.email_de_apelido(r.get("apelido", ""))
        liga = (r.get("liga") or ("", ""))[0] if isinstance(r.get("liga"), (tuple, list)) else ""
        usuario = None if r.get("eu") else AMA.usuario_de_apelido(r.get("apelido", ""))
        out.append({"pos": r["pos"], "nome": AMA.nome_de_email(email, r.get("apelido", "")), "valor": CV2.ret_txt(r.get("ret")),
                    "eu": bool(r.get("eu")), "email": email, "usuario": usuario, "sub": _sub(usuario, bool(r.get("eu")), liga),
                    "src": _meu_src() if r.get("eu") else _src_de_email(email)})
    return out


def _so_amigos(linhas: list[dict]) -> list[dict]:
    """Só você e seus amigos, renumerados de 1 em diante."""
    import amigos as AM
    import amigos_app as AMA
    try:
        amigos = {h for h, v in AMA.relacoes().items() if v.get("estado") == AM.AMIGOS}
    except Exception:
        amigos = set()
    out = [dict(r) for r in linhas if r["eu"] or (r.get("email") and banco._h_conta(r["email"]) in amigos)]
    for i, r in enumerate(out, start=1):
        r["pos"] = i
    return out


REGRA = {"ticker": "Vitórias nos duelos, contra o sistema e online.", "trade": "Pontos somados nas partidas terminadas.",
         "carteira": "Retorno da carteira virtual desde a entrada. Atualiza no fechamento do mercado."}
VAZIO = {"ticker": "Ainda ninguém venceu um duelo do Ticker Battle. Seja o primeiro!", "trade": "Ainda ninguém terminou uma partida do Trade Battle. Seja o primeiro!",
         "carteira": "O ranking da Carteira aparece depois do primeiro fechamento com participantes."}
JOGAR = {"ticker": ("Jogar Ticker Battle", "battle"), "trade": ("Jogar Trade Battle", "trader"), "carteira": ("Abrir a Carteira", "competicao")}


# ------------------------------------------------------------------ tela
def _botao(chave: str, html_bloco: str, rotulo: str, on_click, args=()) -> None:
    with st.container(key=chave):
        st.markdown(html_bloco, unsafe_allow_html=True)
        st.button(rotulo, key=f"{chave}_b", on_click=on_click, args=args)


def _escolher(chave: str, valor: str) -> None:
    _ss()[chave] = valor
    _ss().pop("rk_mais", None)


def pagina() -> None:
    ss = _ss()
    aba = ss.get("rk_aba") if ss.get("rk_aba") in {a[0] for a in RV.ABAS} else J.TRADE
    escopo = ss.get("rk_escopo") if ss.get("rk_escopo") in dict(RV.ESCOPOS) else "global"
    chaves = [f"rk_aba_{a[0]}" for a in RV.ABAS] + [f"rk_esc_{e}" for e, _ in RV.ESCOPOS]
    st.markdown(G.css_base() + RV.css() + "".join(G.css_cartao_botao(k) for k in chaves), unsafe_allow_html=True)
    linhas = _linhas_carteira() if aba == "carteira" else _linhas_jogo(aba)
    if linhas is not None and escopo == "amigos":
        linhas = _so_amigos(linhas)
    meu = next((r for r in (linhas or []) if r["eu"]), None)
    try:
        import perfis_app as PA
        meu_nome = (PA.meu_perfil() or {}).get("nome") or (PA.meu_perfil() or {}).get("usuario") or "Jogador"
    except Exception:
        meu_nome = "Jogador"
    try:
        import tickercoins_app as TCA
        tc = TCA.saldo_atual()
    except Exception:
        tc = None
    with st.container(key="rk_tela"):
        st.markdown(RV.html_topo(meu_nome, _meu_src(), meu["pos"] if meu else None, tc), unsafe_allow_html=True)
        st.markdown(RV.html_titulo(), unsafe_allow_html=True)
        with st.container(key="rk_abas"):
            for k, rot, _ic, _c in RV.ABAS:
                _botao(f"rk_aba_{k}", RV.html_aba(k, k == aba), rot, _escolher, ("rk_aba", k))
        with st.container(key="rk_escopo"):
            for k, rot in RV.ESCOPOS:
                _botao(f"rk_esc_{k}", RV.html_escopo(k, k == escopo), rot, _escolher, ("rk_escopo", k))
        st.markdown(RV.html_faixa(REGRA[aba]), unsafe_allow_html=True)
        if linhas is None:
            st.markdown(RV.html_vazio("O ranking não carregou agora. Tente de novo em instantes."), unsafe_allow_html=True)
            return
        if not linhas or (escopo == "amigos" and len(linhas) <= (1 if meu else 0)):
            txt = ("Nenhum amigo seu aparece neste ranking ainda. Convide amigos em Jogos › Amigos." if escopo == "amigos" and linhas is not None
                   else VAZIO[aba])
            st.markdown(RV.html_vazio(txt), unsafe_allow_html=True)
            rot, dest = JOGAR[aba]
            st.button(rot, key="rk_jogar", icon=":material/play_arrow:", width="stretch", on_click=_ir, args=(dest,))
            if not linhas:
                return
        mais = bool(ss.get("rk_mais"))
        mostrar = linhas if mais else linhas[:VISIVEIS]
        if meu and meu not in mostrar:                       # sua posição aparece sempre, mesmo abaixo das mostradas
            mostrar = mostrar + [meu]
        import amigos_app as AMA
        with st.container(key="rk_lista"):
            AMA.lista_clicavel("rk_l", [(RV.html_linha(r), r.get("usuario")) for r in mostrar])
        if len(linhas) > VISIVEIS:
            with st.container(key="rk_mais"):
                st.button("Ver menos ▲" if mais else f"Ver mais ▼ ({len(linhas)})", key="rk_mais_b", width="stretch",
                          on_click=lambda: ss.update(rk_mais=not ss.get("rk_mais")))
        st.caption("Toque em um jogador para ver o perfil. O ranking atualiza sozinho a cada minuto.")
