"""Trader Battle · multiplayer: salas e partida compartilhada no banco (tabelas tb_partidas e tb_jogadores). Sem Streamlit.

Mesmo desenho do Ticker Battle online (battle_online_dados.py), aproveitando o motor atual (trader_battle.py):
- O banco é a fonte oficial. Todo o estado da partida (o dict `p` do motor, sem candles) vive no JSON `dados`; o cenário é só uma
  referência (id/semente), reconstruída igual em qualquer sessão. Nenhum candle futuro é gravado.
- O servidor decide tudo: cada função recebe o e-mail JÁ validado pela sessão (usuarios.usuario) e confere se a pessoa participa da partida.
  O navegador nunca informa quem ele é.
- Concorrência: toda escrita é compare-and-set pela coluna `versao` (relê e reaplica se alguém gravou antes); a regra de negócio roda
  sobre os dados recém-lidos, então estratégias de jogadores diferentes nunca se sobrescrevem. Índice único impede duas partidas ativas
  por pessoa e códigos de sala repetidos; o limite de 4 jogadores e "partida já começou" são checados dentro da própria escrita.
- Relógio: o do servidor (`agora`, em segundos). Fases, revelação de candles e encerramentos usam sempre `p["t_fase"]` gravado, então
  reconectar ou atualizar a página não muda nada do andamento.
- Quem lê (`ler`) também aplica o que o relógio já determinou (fase, fechamento da rodada), de forma idempotente.
"""
from __future__ import annotations

import copy
import secrets
import time

import banco
import trader_battle as TB
import trader_carteira as TCA
import trader_dados as TD

MIN_JOG, MAX_JOG = 2, 4
SALA_VALIDADE_S = 15 * 60          # sala sem início expira
TENTATIVAS_CAS = 10
_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class ErroSala(ValueError):
    """Mensagem pronta para mostrar ao jogador."""


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def gerar_codigo() -> str:
    return "".join(secrets.choice(_ALFABETO) for _ in range(6))


def normalizar_codigo(txt: str) -> str:
    c = "".join(ch for ch in (txt or "").upper() if ch.isalnum())
    return c if len(c) == 6 and all(ch in _ALFABETO for ch in c) else ""


def nick_de(email: str) -> str:
    try:
        n = ((banco.sis_conta_por_email(email) or {}).get("nome") or "").strip()
    except Exception:
        n = ""
    return (n or email.split("@")[0])[:24]


# ------------------------------------------------------------------ leitura/escrita atômica
def _row(pid: str) -> dict | None:
    r = banco._selecionar("tb_partidas", {"id": pid}, limite=1)
    return {**r[0], "dados": banco._de_js(r[0].get("dados"))} if r else None


def _status(d: dict) -> str:
    if d.get("cancelada"):
        return "cancelada"
    p = d.get("p")
    if not p:
        return "aguardando"
    return "finalizada" if p["fase"] == "fim" else "em_jogo"


def _mutar(pid: str, fn, agora: float) -> dict:
    """Lê, aplica `fn(dados) -> novos dados` e grava só se a versão não mudou (CAS). Devolver o MESMO objeto = nada a gravar."""
    for _ in range(TENTATIVAS_CAS):
        r = _row(pid)
        if not r:
            raise ErroSala("Partida não encontrada.")
        d = r["dados"]
        n = fn(d)
        if n is d:
            return d
        st = _status(n)
        campos = {"dados": banco._js(n), "versao": r["versao"] + 1, "status": st, "atualizado": _iso(agora)}
        if st != "aguardando":
            campos["codigo"] = None                                    # o código só existe enquanto a sala aguarda
        if st in ("finalizada", "cancelada"):
            campos["finalizada_em"] = _iso(agora)
        if banco._atualizar_n("tb_partidas", {"id": pid, "versao": r["versao"]}, campos):
            if n.get("p") and len(n["p"]["resultados"]) != len((d.get("p") or {}).get("resultados") or {}):
                TCA.liquidar_seguro(n["p"])                           # resultados novos: lança no patrimônio de todos (idempotente)
            if st in ("finalizada", "cancelada"):
                banco._atualizar_n("tb_jogadores", {"partida_id": pid, "ativo": 1}, {"ativo": 0})
            return n
    raise ErroSala("A partida está muito movimentada agora. Tente de novo.")


def _aposta(email: str, nome: str = "") -> dict:
    """1% do patrimônio de quem vai jogar (calculado aqui, no servidor). Sem caixa livre para isso, a pessoa não entra."""
    try:
        return TCA.aposta_de(email)
    except TCA.SemSaldo as e:
        raise ErroSala((f"{nome}: " if nome else "") + str(e))


def _participante(d: dict, email: str) -> None:
    if email not in [j["email"] for j in d["sala"]["jogadores"]]:
        raise ErroSala("Você não participa desta partida.")


def _cenario(d: dict) -> dict:
    return TD.resolver(d["cen"])


# ------------------------------------------------------------------ salas
def partida_ativa(email: str) -> str | None:
    """Id da partida não encerrada em que a pessoa está (vale em qualquer aparelho/sessão)."""
    r = banco._selecionar("tb_jogadores", {"email": email, "ativo": 1}, ["partida_id"], limite=1)
    return r[0]["partida_id"] if r else None


def criar_sala(email: str, tf: str, agora: float | None = None) -> dict:
    agora = time.time() if agora is None else agora
    if tf not in TB.TIMEFRAMES:
        raise ErroSala("Timeframe inválido.")
    limpar(agora)
    pid = partida_ativa(email)
    if pid:
        return {"id": pid, "codigo": ((_row(pid) or {}).get("dados") or {}).get("sala", {}).get("codigo", "")}
    _aposta(email)
    for _ in range(8):
        codigo, novo = gerar_codigo(), secrets.token_hex(8)
        d = {"sala": {"codigo": codigo, "criador": email, "tf": tf, "criada": agora, "jogadores": [{"email": email, "nick": nick_de(email), "em": agora}]},
             "cen": None, "p": None}
        try:
            banco._inserir("tb_partidas", {"id": novo, "codigo": codigo, "status": "aguardando", "criador": email, "versao": 1, "criado_em": _iso(agora),
                                           "atualizado": _iso(agora), "dados": banco._js(d)})
        except banco.Duplicado:
            continue                                                   # código repetido: sorteia outro
        try:
            banco._inserir("tb_jogadores", {"id": f"{novo}|{email}", "partida_id": novo, "email": email, "entrou_em": _iso(agora), "ativo": 1})
        except banco.Duplicado:                                        # corrida: outra aba já criou/entrou em partida
            banco._apagar("tb_partidas", {"id": novo})
            ja = partida_ativa(email)
            if ja:
                return {"id": ja, "codigo": ""}
            continue
        return {"id": novo, "codigo": codigo}
    raise ErroSala("Não foi possível criar a sala agora. Tente de novo.")


def entrar_na_sala(email: str, codigo: str, agora: float | None = None) -> dict:
    agora = time.time() if agora is None else agora
    cod = normalizar_codigo(codigo)
    if not cod:
        raise ErroSala("Código inválido. Ele tem 6 letras/números.")
    limpar(agora)
    achadas = banco._selecionar("tb_partidas", {"codigo": cod, "status": "aguardando"}, ["id"], limite=1)
    if not achadas:
        raise ErroSala("Sala não encontrada, já começou ou expirou.")
    pid = achadas[0]["id"]
    ja = partida_ativa(email)
    if ja == pid:
        return {"id": pid}
    _aposta(email)
    if ja:
        raise ErroSala("Você já está em outra partida. Termine ou saia dela antes.")
    try:                                                               # reserva a "vaga ativa" da pessoa primeiro (índice único)
        banco._inserir("tb_jogadores", {"id": f"{pid}|{email}", "partida_id": pid, "email": email, "entrou_em": _iso(agora), "ativo": 1})
    except banco.Duplicado:
        raise ErroSala("Você já está em outra partida. Termine ou saia dela antes.")
    nick = nick_de(email)

    def f(d):
        if d.get("cancelada") or d.get("p"):
            raise ErroSala("Esta partida já começou.")
        if any(j["email"] == email for j in d["sala"]["jogadores"]):
            return d
        if len(d["sala"]["jogadores"]) >= MAX_JOG:
            raise ErroSala("Sala cheia: o máximo é 4 jogadores.")
        n = copy.deepcopy(d)
        n["sala"]["jogadores"].append({"email": email, "nick": nick, "em": agora})
        return n
    try:
        _mutar(pid, f, agora)
    except Exception:
        banco._apagar("tb_jogadores", {"id": f"{pid}|{email}"})        # não entrou: devolve a vaga ativa
        raise
    return {"id": pid}


def sair(pid: str, email: str, agora: float | None = None) -> None:
    """Saída ANTES do início: o criador cancela a sala; os outros apenas saem. Depois do início a partida segue (dá para voltar a ela)."""
    agora = time.time() if agora is None else agora

    def f(d):
        _participante(d, email)
        if d.get("p") or d.get("cancelada"):
            return d
        n = copy.deepcopy(d)
        if email == n["sala"]["criador"]:
            n["cancelada"] = True
        else:
            n["sala"]["jogadores"] = [j for j in n["sala"]["jogadores"] if j["email"] != email]
        return n
    d = _mutar(pid, f, agora)
    if not d.get("p") and (d.get("cancelada") or email not in [j["email"] for j in d["sala"]["jogadores"]]):
        banco._atualizar_n("tb_jogadores", {"id": f"{pid}|{email}", "ativo": 1}, {"ativo": 0})      # liberou a vaga ativa da pessoa


def iniciar(pid: str, email: str, agora: float | None = None) -> dict:
    """Só o criador, com 2 a 4 jogadores. Escolhe o cenário único e abre a partida no instante do servidor. Chamar de novo não reinicia nada."""
    agora = time.time() if agora is None else agora

    def f(d):
        _participante(d, email)
        if d.get("cancelada"):
            raise ErroSala("A sala foi cancelada.")
        if d.get("p"):
            return d                                                   # já iniciada: idempotente
        if email != d["sala"]["criador"]:
            raise ErroSala("Só quem criou a sala pode iniciar a partida.")
        jogs = [j["email"] for j in d["sala"]["jogadores"]]
        if not MIN_JOG <= len(jogs) <= MAX_JOG:
            raise ErroSala("São necessários pelo menos 2 jogadores para começar.")
        tf = d["sala"]["tf"]
        semente = int(agora) % 100000
        cen = TD.escolher(tf, semente)
        n = copy.deepcopy(d)
        n["cen"] = TD.referencia(cen, semente)
        apostas = {j["email"]: _aposta(j["email"], j["nick"]) for j in d["sala"]["jogadores"]}
        n["p"] = TB.nova_partida(cen, tf, jogs, agora, pid=pid, multi=True, apostas=apostas)
        return n
    try:
        _mutar(pid, f, agora)
    except TB.ErroTrader as e:
        raise ErroSala(str(e))
    return ler(pid, email, agora)


# ------------------------------------------------------------------ partida
def _publico(p: dict, email: str) -> dict:
    """Só o que a camada de tela precisa do estado; nada de estratégias, desenhos ou pontos dos outros."""
    return {"id": p["id"], "tf": p["tf"], "fase": p["fase"], "t_fase": p["t_fase"], "rodada": p["rodada"], "multi": True,
            "pontos": {email: p["pontos"].get(email, 0.0)}}


def _sincronizar(pid: str, agora: float) -> dict:
    """Aplica o que o relógio já determinou (fases, fechamento e abertura de rodadas). Só grava se algo mudou; corridas se resolvem pelo CAS."""
    def f(d):
        if not d.get("p") or d.get("cancelada"):
            return d
        n = copy.deepcopy(d)
        cen = _cenario(n)
        TB.avancar(n["p"], agora, {cen["id"]: cen})
        return d if n["p"]["versao"] == d["p"]["versao"] else n
    return _mutar(pid, f, agora)


def ler(pid: str, email: str, agora: float | None = None) -> dict:
    """Consulta de sincronização (polling): confere a participação, aplica o relógio e devolve SÓ o que este jogador pode ver (via TB.visao)."""
    agora = time.time() if agora is None else agora
    r = _row(pid)
    if not r:
        raise ErroSala("Partida não encontrada.")
    _participante(r["dados"], email)
    d = r["dados"]
    if d.get("cancelada"):
        return {"estado": "cancelada"}
    if not d.get("p"):
        if agora - d["sala"]["criada"] > SALA_VALIDADE_S:
            limpar(agora)
        s = d["sala"]
        return {"estado": "sala", "sala": {"codigo": s["codigo"], "tf": s["tf"], "n": len(s["jogadores"]), "max": MAX_JOG, "min": MIN_JOG,
                                           "criador": s["criador"] == email,
                                           "jogadores": [{"nick": j["nick"], "voce": j["email"] == email, "criador": j["email"] == s["criador"]} for j in s["jogadores"]]}}
    d = _sincronizar(pid, agora)
    if d.get("cancelada"):
        return {"estado": "cancelada"}
    cen = _cenario(d)
    v = TB.visao(d["p"], cen, agora, email)
    return {"estado": "jogo", "v": v, "p": _publico(d["p"], email)}


def _acao(pid: str, email: str, agora: float, fn) -> None:
    """Aplica uma ação INDIVIDUAL sobre os dados recém-lidos (CAS). `fn(p, cen)` pode levantar TB.ErroTrader (nada é gravado)."""
    def f(d):
        _participante(d, email)
        if not d.get("p") or d.get("cancelada"):
            raise TB.ErroTrader("a partida ainda não começou")
        n = copy.deepcopy(d)
        cen = _cenario(n)
        TB.avancar(n["p"], agora, {cen["id"]: cen})
        fn(n["p"], cen)
        TB.avancar(n["p"], agora, {cen["id"]: cen})
        return d if n["p"]["versao"] == d["p"]["versao"] else n
    _mutar(pid, f, agora)


def salvar(pid: str, email: str, est: dict, marcas: dict | None, agora: float | None = None) -> None:
    agora = time.time() if agora is None else agora

    def fn(p, cen):
        ini = TB.inicio_rodada(cen, p["rodada"])
        ref = cen["candles"][ini - 1]["c"]                              # preço de referência calculado aqui, não vindo do navegador
        TB.salvar_estrategia(p, email, est, marcas, ref, agora)
    _acao(pid, email, agora, fn)


def pronto(pid: str, email: str, agora: float | None = None) -> None:
    agora = time.time() if agora is None else agora
    _acao(pid, email, agora, lambda p, cen: TB.marcar_pronto(p, email, agora))


class Ops:
    """Adaptador usado por trader_grafico.processar: traduz os eventos do componente em ações desta partida compartilhada.
    Erros de sala/banco viram TB.ErroTrader (mensagem ao jogador); nada é gravado quando há erro."""

    def __init__(self, pid: str, email: str):
        self.pid, self.email = pid, email

    def _rodar(self, fn, *a):
        try:
            fn(*a)
        except ErroSala as e:
            raise TB.ErroTrader(str(e))
        except banco.ErroBanco:
            raise TB.ErroTrader("Conexão instável com o servidor. Tente de novo.")

    def salvar(self, est, marcas, ref, agora):
        self._rodar(salvar, self.pid, self.email, est, marcas, agora)

    def replay(self, agora):
        self._rodar(pronto, self.pid, self.email, agora)

    def tempo(self, agora):
        self._rodar(_sincronizar, self.pid, agora)

    def proxima(self, agora):
        self._rodar(pronto, self.pid, self.email, agora)


# ------------------------------------------------------------------ limpeza
def limpar(agora: float | None = None, limite: int = 20) -> int:
    """Cancela salas esquecidas (sem início depois de 15 min)."""
    agora = time.time() if agora is None else agora
    n = 0
    try:
        corte = _iso(agora - SALA_VALIDADE_S)
        for r in banco._selecionar("tb_partidas", {"status": "aguardando", "atualizado": ("lt", corte)}, ["id"], limite=limite):
            def f(d):
                if d.get("p") or d.get("cancelada"):
                    return d
                n2 = copy.deepcopy(d)
                n2["cancelada"] = True
                return n2
            _mutar(r["id"], f, agora)
            n += 1
    except (banco.ErroBanco, ErroSala):
        pass
    return n
