"""Ticker Battle Online · persistência, fila e salas (tabelas bt_fila e bt_partidas).

Regras de ouro:
- O servidor decide tudo. Cada função recebe o e-mail JÁ validado pela sessão (usuarios.usuario) e confere a participação na partida;
  o lado (a/b), as cartas, os valores e o vencedor vêm do banco, nunca do navegador.
- Atomicidade por compare-and-set: toda escrita na partida só vale se `versao` ainda for a lida (senão relê e tenta de novo);
  reserva de adversário na fila é um UPDATE condicional (só um chamador consegue); índices únicos impedem duas partidas ativas por jogador
  e dois códigos iguais em salas abertas.
- Nada depende da sessão do Streamlit: dá para fechar o app e voltar para a mesma partida (partida_ativa).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import banco
import battle_dados as BD
import battle_online as O

FILA_VALIDADE_S = 25            # cada consulta renova; sem renovar por este tempo a pessoa sai da fila
FILA_MAX_ESPERA_S = 180         # depois disso a busca termina sem adversário
SALA_VALIDADE_MIN = 15          # sala privada sem segundo jogador expira
SINAL_MIN_INTERVALO_S = 5       # presença só é regravada de tempos em tempos (poupa o banco)
TENTATIVAS_CAS = 8
HISTORICO_MAX = 20


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _lin(r: dict) -> dict:
    return {**r, "dados": banco._de_js(r.get("dados"))}


# ------------------------------------------------------------------ leitura
def _partida_row(pid: str) -> dict | None:
    r = banco._selecionar("bt_partidas", {"id": pid}, limite=1)
    return _lin(r[0]) if r else None


def partida_ativa(email: str) -> str | None:
    """Id da partida não encerrada em que a pessoa está (como a ou b), a mais recente."""
    achadas = []
    for col in ("a_email", "b_email"):
        for r in banco._selecionar("bt_partidas", {col: email}, ["id", "status", "criado_em"], ordem="criado_em", desc=True, limite=6):
            if r["status"] in O.ATIVAS:
                achadas.append(r)
    achadas.sort(key=lambda r: r["criado_em"], reverse=True)
    return achadas[0]["id"] if achadas else None


def _snapshot() -> dict:
    return BD.ler_snapshot(banco)


def deck_de(email: str) -> list[str]:
    """Baralho salvo da pessoa (lido do banco, não da sessão do navegador)."""
    return list(BD.ler_pessoa(banco, email).get("deck") or [])


def nick_de(email: str) -> str:
    try:
        c = banco.sis_conta_por_email(email) or {}
        n = (c.get("nome") or "").strip()
    except Exception:
        n = ""
    return (n or email.split("@")[0])[:24]


# ------------------------------------------------------------------ escrita atômica
def _gravar_campos(d: dict, versao: int, agora: datetime) -> dict:
    campos = {"dados": banco._js(d), "versao": versao + 1, "status": d["fase"], "atualizado": O.iso(agora)}
    if d["jog"]["b"] is not None:
        campos["b_email"] = d["jog"]["b"]["email"]
    if d["fase"] in ("finalizada", "cancelada"):
        f = d["final"] or {}
        campos["finalizada_em"] = f.get("em") or O.iso(agora)
        campos["motivo"] = f.get("motivo")
        campos["vencedor"] = d["jog"][f["venc"]]["email"] if f.get("venc") else ""
    return campos


def _mutar(pid: str, fn, agora: datetime) -> dict:
    """Lê, aplica `fn(dados) -> novos dados` e grava só se a versão não mudou (CAS). `fn` pode devolver o MESMO objeto para 'nada a fazer'."""
    for _ in range(TENTATIVAS_CAS):
        r = _partida_row(pid)
        if not r:
            raise O.ErroPartida("Partida não encontrada.")
        d = r["dados"]
        n = fn(d)
        if n is d:
            return d
        try:
            ok = banco._atualizar_n("bt_partidas", {"id": pid, "versao": r["versao"]}, _gravar_campos(n, r["versao"], agora))
        except banco.Duplicado:
            raise O.ErroPartida("Você já está em outra partida.")
        if ok:
            return n
    raise O.ErroPartida("A partida está muito movimentada agora. Tente de novo.")


def _participante(pid: str, email: str) -> tuple[dict, str]:
    r = _partida_row(pid)
    if not r:
        raise O.ErroPartida("Partida não encontrada.")
    lado = O.lado_de(r["dados"], email)
    if lado is None:
        raise O.ErroPartida("Você não participa desta partida.")
    return r, lado


# ------------------------------------------------------------------ fila (busca de adversário)
def _fila_row(email: str) -> dict | None:
    r = banco._selecionar("bt_fila", {"email": email}, limite=1)
    return {**r[0], "baralho": banco._de_js(r[0].get("baralho")).get("deck", [])} if r else None


def _validar_deck(email: str, snap: dict, agora: datetime) -> list[str]:
    from battle import validar_baralho
    deck = deck_de(email)
    ok, msg = validar_baralho(deck, snap, O.hoje_de(agora))
    if not ok:
        raise O.ErroPartida(msg)
    return deck


def entrar_na_fila(email: str, agora: datetime | None = None) -> dict:
    """Coloca a pessoa na fila e já tenta emparelhar. Devolve {'estado': 'partida'|'fila', 'id'?}."""
    agora = agora or agora_utc()
    limpar(agora)
    pid = partida_ativa(email)
    if pid:
        return {"estado": "partida", "id": pid}
    deck = _validar_deck(email, _snapshot(), agora)
    banco._apagar("bt_fila", {"email": email})
    try:
        banco._inserir("bt_fila", {"email": email, "nick": nick_de(email), "baralho": banco._js({"deck": deck}), "criado_em": O.iso(agora),
                                   "expira_em": O.iso(agora + timedelta(seconds=FILA_VALIDADE_S)), "partida_id": ""})
    except banco.Duplicado:
        pass
    return consultar_fila(email, agora)


def sair_da_fila(email: str) -> None:
    banco._apagar("bt_fila", {"email": email})


def consultar_fila(email: str, agora: datetime | None = None) -> dict:
    """Chamado a cada 2–3 s enquanto a pessoa espera: renova a presença na fila e tenta reservar um adversário MAIS ANTIGO.
    Só quem chegou depois reserva quem chegou antes, então dois jogadores nunca se reservam ao mesmo tempo."""
    agora = agora or agora_utc()
    pid = partida_ativa(email)
    if pid:
        banco._apagar("bt_fila", {"email": email})
        return {"estado": "partida", "id": pid}
    eu = _fila_row(email)
    if not eu:
        return {"estado": "fora"}
    if (agora - (O.de_iso(eu["criado_em"]) or agora)).total_seconds() > FILA_MAX_ESPERA_S:
        sair_da_fila(email)
        return {"estado": "expirou"}
    if eu["partida_id"]:                                          # outro jogador me reservou e está criando a partida
        return {"estado": "fila", "reservado": True}
    banco._atualizar_n("bt_fila", {"email": email, "partida_id": ""}, {"expira_em": O.iso(agora + timedelta(seconds=FILA_VALIDADE_S))})
    candidatos = banco._selecionar("bt_fila", {"criado_em": ("lte", eu["criado_em"]), "partida_id": "", "expira_em": ("gt", O.iso(agora))},
                                   ordem="criado_em", limite=10)
    candidatos = [c for c in candidatos if c["email"] != email and (c["criado_em"], c["email"]) < (eu["criado_em"], email)]
    snap = _snapshot()
    for c in candidatos:
        novo_id = uuid.uuid4().hex[:16]
        if not banco._atualizar_n("bt_fila", {"email": email, "partida_id": ""}, {"partida_id": novo_id}):
            return {"estado": "fila", "reservado": True}          # alguém me reservou primeiro
        if not banco._atualizar_n("bt_fila", {"email": c["email"], "partida_id": ""}, {"partida_id": novo_id}):
            banco._atualizar_n("bt_fila", {"email": email, "partida_id": novo_id}, {"partida_id": ""})
            continue                                              # perdi a disputa por este adversário
        try:
            deck_c = banco._de_js(c.get("baralho")).get("deck", [])
            d = O.novo(novo_id, c["email"], c["nick"], deck_c, agora)
            d = O.entrar(d, email, eu["nick"], eu["baralho"], snap, agora, BD.referencia_dos_dados(snap, list(snap)))
            banco._inserir("bt_partidas", {"id": novo_id, "codigo": None, "tipo": "rapida", "status": d["fase"], "a_email": c["email"], "b_email": email,
                                           "versao": 1, "criado_em": O.iso(agora), "atualizado": O.iso(agora), "dados": banco._js(d)})
        except (O.ErroPartida, banco.Duplicado, banco.ErroBanco):
            banco._atualizar_n("bt_fila", {"email": c["email"], "partida_id": novo_id}, {"partida_id": ""})
            banco._atualizar_n("bt_fila", {"email": email, "partida_id": novo_id}, {"partida_id": ""})
            continue
        banco._apagar("bt_fila", {"email": email})
        banco._apagar("bt_fila", {"email": c["email"]})
        return {"estado": "partida", "id": novo_id}
    return {"estado": "fila"}


# ------------------------------------------------------------------ sala privada
def criar_sala(email: str, agora: datetime | None = None) -> dict:
    agora = agora or agora_utc()
    limpar(agora)
    pid = partida_ativa(email)
    if pid:
        r = _partida_row(pid)
        return {"id": pid, "codigo": r.get("codigo") or ""}
    deck = _validar_deck(email, _snapshot(), agora)
    banco._apagar("bt_fila", {"email": email})
    for _ in range(8):
        codigo, novo_id = O.gerar_codigo(), uuid.uuid4().hex[:16]
        d = O.novo(novo_id, email, nick_de(email), deck, agora)
        try:
            banco._inserir("bt_partidas", {"id": novo_id, "codigo": codigo, "tipo": "privada", "status": "aguardando", "a_email": email, "b_email": None,
                                           "versao": 1, "criado_em": O.iso(agora), "atualizado": O.iso(agora), "dados": banco._js(d)})
            return {"id": novo_id, "codigo": codigo}
        except banco.Duplicado:
            pid = partida_ativa(email)
            if pid:                                               # corrida: outra aba já criou
                return {"id": pid, "codigo": (_partida_row(pid) or {}).get("codigo") or ""}
    raise O.ErroPartida("Não foi possível criar a sala agora. Tente de novo.")


def entrar_na_sala(email: str, codigo: str, agora: datetime | None = None) -> dict:
    agora = agora or agora_utc()
    cod = O.normalizar_codigo(codigo)
    if not cod:
        raise O.ErroPartida("Código inválido. Ele tem 6 letras/números.")
    limpar(agora)
    achadas = banco._selecionar("bt_partidas", {"codigo": cod, "status": "aguardando"}, limite=1)
    if not achadas:
        raise O.ErroPartida("Sala não encontrada, já completa ou expirada.")
    pid = achadas[0]["id"]
    ja = partida_ativa(email)
    if ja and ja != pid:
        raise O.ErroPartida("Você já está em outra partida. Termine ou saia dela antes.")
    if ja == pid:
        return {"id": pid}
    deck = _validar_deck(email, _snapshot(), agora)
    snap = _snapshot()
    nick = nick_de(email)
    _mutar(pid, lambda d: O.entrar(d, email, nick, deck, snap, agora, BD.referencia_dos_dados(snap, list(snap))), agora)
    banco._apagar("bt_fila", {"email": email})
    return {"id": pid}


# ------------------------------------------------------------------ partida
def ler(pid: str, email: str, agora: datetime | None = None) -> dict:
    """Consulta de sincronização (polling): confere a participação, registra presença, aplica os prazos e devolve SÓ o que este jogador pode ver."""
    agora = agora or agora_utc()
    r, lado = _participante(pid, email)
    d = r["dados"]
    if d["fase"] in O.ATIVAS:
        sinal_velho = (O.segundos_sem_sinal(d, lado, agora) or 999) >= SINAL_MIN_INTERVALO_S

        def f(x):
            # 1º registra a presença DESTE jogador (quem volta antes de ser julgado continua na partida); 2º aplica os prazos (só o outro pode estar vencido)
            n = O.batida(x, lado, agora) if (O.segundos_sem_sinal(x, lado, agora) or 999) >= SINAL_MIN_INTERVALO_S else x
            return O.avaliar_prazos(n, agora)

        if sinal_velho or O.avaliar_prazos(O.batida(d, lado, agora), agora)["fase"] != d["fase"]:
            d = _mutar(pid, f, agora)
    return O.visao(d, lado, agora)


def estou_pronto(pid: str, email: str, agora: datetime | None = None) -> dict:
    agora = agora or agora_utc()
    _, lado = _participante(pid, email)
    d = _mutar(pid, lambda x: x if x["pronto"][lado] else O.marcar_pronto(O.batida(x, lado, agora), lado, agora), agora)
    return O.visao(d, lado, agora)


def jogar(pid: str, email: str, tk: str, ind: str, agora: datetime | None = None) -> dict:
    """Confirma carta e atributo. O servidor valida, grava na hora e, se o adversário já confirmou, resolve a rodada na mesma gravação."""
    agora = agora or agora_utc()
    _, lado = _participante(pid, email)
    d = _mutar(pid, lambda x: O.escolher(O.batida(x, lado, agora), lado, tk, ind, agora), agora)
    return O.visao(d, lado, agora)


def sair(pid: str, email: str, agora: datetime | None = None) -> dict:
    """Saída voluntária. Sala aguardando/pronta sem jogo: cancela. Partida em andamento: desistência = vitória do adversário (motivo 'abandono')."""
    agora = agora or agora_utc()
    _, lado = _participante(pid, email)

    def f(x):
        if x["fase"] in ("finalizada", "cancelada"):
            return x
        if x["fase"] == "aguardando" or x["jog"]["b"] is None:
            return O._encerrar(x, None, "cancelada", agora)
        if x["fase"] == "pronta" and not any(x["pronto"].values()):
            return O._encerrar(x, None, "cancelada", agora)
        return O._encerrar(x, O.outro(lado), "abandono", agora)
    return O.visao(_mutar(pid, f, agora), lado, agora)


# ------------------------------------------------------------------ histórico
def historico(email: str, limite: int = HISTORICO_MAX) -> list[dict]:
    """Partidas encerradas da pessoa (lidas do banco, valem em qualquer aparelho)."""
    linhas = []
    for col in ("a_email", "b_email"):
        for r in banco._selecionar("bt_partidas", {col: email, "status": "finalizada"}, ordem="criado_em", desc=True, limite=limite):
            linhas.append(_lin(r))
    linhas.sort(key=lambda r: r["criado_em"], reverse=True)
    out = []
    for r in linhas[:limite]:
        d = r["dados"]
        lado = O.lado_de(d, email)
        if lado and d.get("final"):
            out.append(O.registro_historico(d, lado))
    return out


# ------------------------------------------------------------------ limpeza (filas expiradas e partidas abandonadas)
def limpar(agora: datetime | None = None, limite: int = 20) -> int:
    """Remove quem saiu da fila, cancela salas esquecidas e encerra partidas cujo jogador sumiu (também feito pelas consultas)."""
    agora = agora or agora_utc()
    n = 0
    try:
        for r in banco._selecionar("bt_fila", {"expira_em": ("lt", O.iso(agora))}, ["email"], limite=limite):
            n += banco._apagar_n("bt_fila", {"email": r["email"], "expira_em": ("lt", O.iso(agora))})
        corte = O.iso(agora - timedelta(minutes=SALA_VALIDADE_MIN))
        for r in banco._selecionar("bt_partidas", {"status": "aguardando", "atualizado": ("lt", corte)}, ["id"], limite=limite):
            _mutar(r["id"], lambda x: O._encerrar(x, None, "cancelada", agora) if x["fase"] == "aguardando" else x, agora)
            n += 1
        velhas = O.iso(agora - timedelta(seconds=O.PRAZO_RECONEXAO_S + 5))
        for st in ("pronta", "em_jogo"):
            for r in banco._selecionar("bt_partidas", {"status": st, "atualizado": ("lt", velhas)}, ["id"], limite=limite):
                antes = _partida_row(r["id"])
                depois = _mutar(r["id"], lambda x: O.avaliar_prazos(x, agora), agora)
                n += int(bool(antes) and depois.get("fase") != antes["dados"].get("fase"))
    except (banco.ErroBanco, O.ErroPartida):
        pass
    return n
