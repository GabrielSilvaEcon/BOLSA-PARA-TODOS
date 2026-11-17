"""Perfil de jogador: identidade pública centralizada do TickerHunters. Lógica pura: sem Streamlit, sem banco e sem rede.

Uma fonte para cada dado (nada é copiado):
 · ID único e data de criação → tabela `contas` (id, criado_em). Nunca editáveis aqui.
 · Nome de usuário, nome de exibição, avatar, biografia e privacidade → documento `perfil_jogador` da própria conta (monitor_estado).
   O nome de usuário é o NickName do cadastro; a exclusividade é garantida por uma reserva atômica (`usuario|<nome>` em config_sistema,
   guardando só um hash da conta) e respeita os apelidos que já existem na Competição.
 · Nível, XP e conquistas → calculados na hora a partir do progresso real da Jornada (jornada, nivel, emblemas). O formulário nunca os recebe.
 · Preferência visual → a mesma `prefs.tema` do app (o perfil só edita a preferência existente).
 · Desempenho nos jogos → o placar real da Central de Jogos (`jogos_placar`). Nenhuma pontuação paralela.
Público × privado: `publico()` só devolve campos de uma lista fechada e respeita a privacidade; patrimônio, carteira, saldos, e-mail
e o ID interno nunca saem para outra pessoa (teste garante).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

import competicao as C

CH_PERFIL = "perfil_jogador"
CFG_USUARIO = "usuario|"                 # reserva do nome de usuário (id = prefixo + nome em minúsculas; dados = hash da conta)
VERSAO = 1
NOME_MIN, NOME_MAX = 2, 30
BIO_MAX = 160
TROCA_USUARIO_DIAS = 7                   # intervalo mínimo entre trocas de nome de usuário (evita confusão e abuso nos rankings)

# Avatares: só as artes que o app já tem (sem upload; nada de imagem enviada pela pessoa). id → (módulo de arte, chave)
AVATARES = {
    "raposa": ("arte_conta", "avatar"),
    "raposa_confiante": ("arte_cartela", "raposa_confiante"),
    "raposa_animada": ("arte_cartela", "raposa_animada"),
    "raposa_vitoriosa": ("arte_cartela", "raposa_vitoriosa"),
    "raposa_pensativa": ("arte_cartela", "raposa_pensativa"),
    "raposa_surpresa": ("arte_cartela", "raposa_surpresa"),
}
AVATAR_PADRAO = "raposa"
FOTO = "foto"                            # avatar = foto enviada pela pessoa (guardada à parte, já reprocessada: perfil_foto.py)
# Privacidade. `visivel`: quem abre o perfil (todos os jogadores logados, só amigos ou ninguém). `pedidos`: quem pode enviar solicitação de amizade.
# mostrar_jogos = estatísticas competitivas (vitórias, derrotas, taxa, pontos, posições); mostrar_historico = últimas partidas.
VISIVEL = {"todos": "Todos os jogadores", "amigos": "Só meus amigos", "ninguem": "Ninguém (só eu)"}
PEDIDOS = {"todos": "Qualquer jogador", "ninguem": "Ninguém"}
PRIVACIDADE_PADRAO = {"visivel": "todos", "mostrar_bio": True, "mostrar_nivel": True, "mostrar_conquistas": True, "mostrar_jogos": True,
                      "mostrar_historico": True, "pedidos": "todos"}
EDITAVEIS = ("nome", "usuario", "bio", "avatar", "privacidade", "tema")   # tudo o mais que vier do formulário é ignorado
PUBLICOS = ("usuario", "nome", "avatar", "foto", "bio", "desde", "nivel", "titulo", "xp", "conquistas", "medalhas", "jogos", "estat", "historico")
HIST_PUBLICO = 10                        # últimas partidas mostradas no perfil de outra pessoa
PROIBIDOS = ("email", "id", "conta_id", "patrimonio", "carteira", "caixa", "saldo", "tc", "pat", "senha", "papel")


class ErroPerfil(ValueError):
    """Dado de perfil inválido (mensagem pronta para a tela)."""


def _limpo(txt) -> str:
    """Texto sem caracteres de controle nem formatação invisível, espaços normalizados."""
    s = unicodedata.normalize("NFC", str(txt or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "C" or ch in "\n")
    return re.sub(r"[ \t]+", " ", s).strip()


def _proibido(txt: str) -> bool:
    base = re.sub(r"[\d_.\- ]", "", txt.lower())
    return any(r in base for r in C._RESERVADOS) or any(b in base for b in C._BLOQUEADOS)


# ------------------------------------------------------------------ validação de cada campo editável
def validar_usuario(usuario) -> str:
    """Nome de usuário: mesmas regras do NickName (3 a 20 caracteres, letras, números, ponto, hífen, sublinhado; sem palavras bloqueadas)."""
    u = _limpo(usuario)
    ok, msg = C.apelido_valido(u)
    if not ok:
        raise ErroPerfil(msg)
    return u


def chave_usuario(usuario: str) -> str:
    return C.chave_apelido(usuario)


def validar_nome(nome) -> str:
    n = _limpo(nome).replace("\n", " ")
    if not (NOME_MIN <= len(n) <= NOME_MAX):
        raise ErroPerfil(f"O nome de exibição precisa ter de {NOME_MIN} a {NOME_MAX} caracteres.")
    if re.search(r"[<>{}\[\]\\]", n):
        raise ErroPerfil("O nome de exibição não pode ter os caracteres < > { } [ ] \\.")
    if _proibido(n):
        raise ErroPerfil("Esse nome de exibição não é permitido. Escolha outro.")
    return n


def validar_bio(bio) -> str:
    b = re.sub(r"\n{3,}", "\n\n", _limpo(bio))
    if len(b) > BIO_MAX:
        raise ErroPerfil(f"A biografia pode ter no máximo {BIO_MAX} caracteres.")
    if re.search(r"https?://|www\.|<[a-z/!]", b, re.I):
        raise ErroPerfil("A biografia não pode ter links nem marcações HTML.")
    if b and _proibido(b.replace("\n", " ")):
        raise ErroPerfil("A biografia tem palavras não permitidas.")
    return b


def validar_avatar(avatar) -> str:
    a = str(avatar or "")
    if a not in AVATARES and a != FOTO:
        raise ErroPerfil("Escolha um dos avatares disponíveis.")
    return a


def validar_privacidade(p) -> dict:
    d = p if isinstance(p, dict) else {}
    out = {k: (d[k] if isinstance(d.get(k), bool) else v) for k, v in PRIVACIDADE_PADRAO.items() if isinstance(v, bool)}
    vis = d.get("visivel")
    if vis not in VISIVEL:                                   # documento antigo: `publico` (sim/não) vira todos/ninguém
        vis = "ninguem" if d.get("publico") is False else PRIVACIDADE_PADRAO["visivel"]
    out["visivel"] = vis
    out["pedidos"] = d.get("pedidos") if d.get("pedidos") in PEDIDOS else PRIVACIDADE_PADRAO["pedidos"]
    return out


def pode_ver(privacidade: dict, amigo: bool, dono: bool = False) -> bool:
    """Quem pode abrir o perfil (decisão única, usada pelo banco antes de entregar qualquer dado)."""
    if dono:
        return True
    vis = validar_privacidade(privacidade)["visivel"]
    return vis == "todos" or (vis == "amigos" and bool(amigo))


def aceita_pedidos(privacidade: dict) -> bool:
    return validar_privacidade(privacidade)["pedidos"] == "todos"


def validar_tema(tema, temas: dict) -> str:
    if tema not in temas:
        raise ErroPerfil("Preferência visual inválida.")
    return tema


# ------------------------------------------------------------------ documento da conta
def vazio() -> dict:
    return {"v": VERSAO, "usuario": "", "usuario_k": "", "nome": "", "avatar": AVATAR_PADRAO, "bio": "", "privacidade": dict(PRIVACIDADE_PADRAO),
            "usuario_em": "", "atualizado": ""}


def sanear(doc) -> dict:
    """Documento gravado com tipos conferidos. Campo inválido volta ao padrão (nunca derruba a tela)."""
    d = doc if isinstance(doc, dict) else {}
    out = vazio()
    try:
        out["usuario"] = validar_usuario(d.get("usuario")) if d.get("usuario") else ""
    except ErroPerfil:
        out["usuario"] = ""
    out["usuario_k"] = chave_usuario(out["usuario"]) if out["usuario"] else ""
    for campo, fn in (("nome", validar_nome), ("bio", validar_bio), ("avatar", validar_avatar)):
        try:
            out[campo] = fn(d.get(campo)) if d.get(campo) else out[campo]
        except ErroPerfil:
            pass
    out["privacidade"] = validar_privacidade(d.get("privacidade"))
    out["usuario_em"] = str(d.get("usuario_em") or "")[:25]
    out["atualizado"] = str(d.get("atualizado") or "")[:25]
    return out


def inicial(apelido: str) -> dict:
    """Perfil de quem ainda não tem um: nasce do NickName do cadastro (nome de exibição = o próprio NickName, nunca o nome real)."""
    d = vazio()
    try:
        u = validar_usuario(apelido)
        d.update(usuario=u, usuario_k=chave_usuario(u), nome=u)
    except ErroPerfil:
        pass
    return d


def editar(atual: dict, form: dict, agora: datetime | None = None, temas: dict | None = None) -> tuple[dict, dict]:
    """Aplica o formulário ao perfil. Só os campos de EDITAVEIS são lidos (XP, pontos, conquistas, e-mail... vindos do formulário são
    ignorados). Devolve (perfil_novo, mudancas) onde mudancas pode ter `usuario` (troca a reservar) e `tema` (vai para prefs).
    Levanta ErroPerfil com mensagem clara se algum campo for inválido."""
    ag = agora or datetime.now(timezone.utc)
    a = sanear(atual)
    f = {k: v for k, v in (form or {}).items() if k in EDITAVEIS}
    novo, mud = dict(a), {}
    if "nome" in f:
        novo["nome"] = validar_nome(f["nome"])
    if "bio" in f:
        novo["bio"] = validar_bio(f["bio"])
    if "avatar" in f:
        novo["avatar"] = validar_avatar(f["avatar"])
    if "privacidade" in f:
        novo["privacidade"] = validar_privacidade({**a["privacidade"], **(f["privacidade"] if isinstance(f["privacidade"], dict) else {})})
    if "tema" in f and temas is not None:
        mud["tema"] = validar_tema(f["tema"], temas)
    if "usuario" in f:
        u = validar_usuario(f["usuario"])
        if chave_usuario(u) != a["usuario_k"]:
            if a["usuario_em"]:
                try:
                    dias = (ag - datetime.fromisoformat(a["usuario_em"])).total_seconds() / 86400
                except ValueError:
                    dias = TROCA_USUARIO_DIAS
                if dias < TROCA_USUARIO_DIAS:
                    raise ErroPerfil(f"Você trocou o nome de usuário há pouco. Dá para trocar de novo em {TROCA_USUARIO_DIAS - int(dias)} dia(s).")
            mud["usuario"] = u
            if a["usuario_k"]:                                     # só TROCA conta no intervalo (escolher o primeiro nome é livre)
                novo["usuario_em"] = ag.isoformat(timespec="seconds")
        novo["usuario"], novo["usuario_k"] = u, chave_usuario(u)
    novo["atualizado"] = ag.isoformat(timespec="seconds")
    return novo, mud


# ------------------------------------------------------------------ dados derivados (fontes reais) e projeções
def progresso(edu_progresso) -> dict:
    """Nível, título, XP e conquistas a partir do progresso REAL da Jornada (o mesmo cálculo das telas do app)."""
    import emblemas as EM
    import jornada as JO
    import nivel as NV
    p = edu_progresso if isinstance(edu_progresso, dict) else {}
    try:
        res = JO.resumo(p)
        unidades = sum(1 for u in JO.mapa(p) if u.get("completa"))
    except Exception:
        res, unidades = {"xp": 0}, 0
    xp = int(res.get("xp") or 0)
    nv = NV.nivel_de(xp)
    col = EM.colecao(EM.contexto(res, unidades, nv, [], False))                       # conquistas de estudo (não depende de carteira)
    ok, total = EM.totais(col)
    medalhas = [{"emblema": str(i.get("emblema") or "🏅")[:4], "nome": str(i.get("nome") or "")[:40]} for c in col for i in c["itens"] if i["ok"]]
    return {"xp": xp, "nivel": nv, "titulo": NV.titulo(nv), "conquistas": ok, "conquistas_total": total, "medalhas": medalhas}


def jogos(doc_placar, ranking_trade: dict | None = None, ranking_ticker: dict | None = None) -> dict:
    """Desempenho nos jogos a partir do placar real da Central de Jogos (sem recalcular nada)."""
    import jogos as J
    d = J.sanear(doc_placar)
    pos = lambda rk: (rk or {}).get("eu", {}).get("pos") if (rk or {}).get("eu") else None
    return {"trade": {"pontos": d["trade"]["pts"], "partidas": d["trade"]["partidas"], "vitorias": d["trade"]["vitorias"], "posicao": pos(ranking_trade)},
            "ticker": {"vitorias": d["ticker"]["v"], "empates": d["ticker"]["e"], "derrotas": d["ticker"]["d"], "posicao": pos(ranking_ticker)}}


def historico_publico(doc_placar) -> list[dict]:
    """Últimas partidas dos dois jogos, só o resultado (data, jogo, pontos ou resultado). Sem adversários e sem ids."""
    import jogos as J
    d = J.sanear(doc_placar)
    out = [{"em": str(h.get("em") or "")[:16], "jogo": J.TRADE, "pts": round(float(h.get("pts") or 0), 1),
            "pos": h.get("pos") if isinstance(h.get("pos"), int) else None, "n": int(h.get("n") or 1)} for h in d[J.TRADE]["hist"]]
    out += [{"em": str(h.get("em") or "")[:16], "jogo": J.TICKER, "r": h.get("r") if h.get("r") in ("v", "e", "d") else ""} for h in d[J.TICKER]["hist"]]
    return sorted(out, key=lambda h: h["em"], reverse=True)[:HIST_PUBLICO]


def publico(perfil: dict, desde: str, prog: dict, jogos_: dict | None, foto_uri: str = "", *, amigo: bool = False,
            estat: dict | None = None, historico: list | None = None) -> dict | None:
    """Visão de OUTRA pessoa: só campos de PUBLICOS, filtrados pela privacidade. None se ela não deixa esta pessoa ver o perfil
    (visível a ninguém, ou só a amigos e quem vê não é amigo) ou se não tem nome de usuário."""
    p = sanear(perfil)
    pv = p["privacidade"]
    if not pode_ver(pv, amigo) or not p["usuario"]:
        return None
    out = {"usuario": p["usuario"], "nome": p["nome"] or p["usuario"], "avatar": p["avatar"] if (p["avatar"] != FOTO or foto_uri) else AVATAR_PADRAO,
           "desde": str(desde or "")[:7]}
    if out["avatar"] == FOTO:
        out["foto"] = foto_uri
    if pv["mostrar_bio"] and p["bio"]:
        out["bio"] = p["bio"]
    if pv["mostrar_nivel"]:
        out.update(nivel=prog["nivel"], titulo=prog["titulo"], xp=prog["xp"])
    if pv["mostrar_conquistas"]:
        out["conquistas"] = {"ok": prog["conquistas"], "total": prog["conquistas_total"]}
        out["medalhas"] = list(prog.get("medalhas") or [])
    if pv["mostrar_jogos"] and jogos_:
        out["jogos"] = jogos_
        if estat:
            out["estat"] = {k: estat[k] for k in ("partidas", "vitorias", "empates", "derrotas", "taxa") if k in estat}
    if pv["mostrar_historico"] and historico:
        out["historico"] = historico[:HIST_PUBLICO]
    assert set(out) <= set(PUBLICOS)
    return out


def restrito(perfil: dict) -> dict:
    """Cartão mínimo de um perfil "só amigos" visto por quem não é amigo: nome, usuário e avatar do app (sem foto, bio ou estatísticas)."""
    p = sanear(perfil)
    return {"usuario": p["usuario"], "nome": p["nome"] or p["usuario"], "avatar": p["avatar"] if p["avatar"] != FOTO else AVATAR_PADRAO}


def privado(perfil: dict, conta: dict, prog: dict, jogos_: dict | None, tema: str) -> dict:
    """Visão da PRÓPRIA pessoa: tudo do perfil + ID, e-mail e data de criação da conta (dela mesma) + preferência visual."""
    return {**sanear(perfil), "id": conta.get("id"), "email": conta.get("email"), "desde": str(conta.get("criado_em") or "")[:10],
            **prog, "jogos": jogos_, "tema": tema}
