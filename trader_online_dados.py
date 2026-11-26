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
import random

import bot_jogo as BJ
import bots as BOTS
import setups_dados as SD
import setups_vivo as SV
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
    """Nome público na sala: o nome de usuário do perfil de jogador (nunca o nome real nem o e-mail da conta)."""
    try:
        n = str((banco.sis_estado_ler(email, "perfil_jogador") or {}).get("usuario") or "").strip()
    except Exception:
        n = ""
    return (n or "Jogador")[:24]


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
            if n.get("p") and TB.motor_de(n["p"]) == TB.MOTOR_MESA and n["p"]["fase"] in ("analise", "replay") and _faltam_stakes(n["p"]):
                _garantir_stakes(pid, agora)                          # mesa: aposta de 1% da rodada nova, já com a rodada anterior lançada
            if st in ("finalizada", "cancelada"):
                banco._atualizar_n("tb_jogadores", {"partida_id": pid, "ativo": 1}, {"ativo": 0})
            return n
    raise ErroSala("A partida está muito movimentada agora. Tente de novo.")


def _capital(email: str, nome: str = "") -> dict:
    """Partida corrida: 5% do caixa livre de cada jogador (calculado aqui, no servidor)."""
    try:
        return TCA.capital_corrida(email)
    except TCA.SemSaldo as e:
        raise ErroSala((f"{nome}: " if nome else "") + str(e))


def _aposta(email: str, nome: str = "", mesa: bool = False) -> dict:
    """1% do patrimônio de quem vai jogar (calculado aqui, no servidor). Sem caixa livre para isso (mesa: 3% do patrimônio), a pessoa não entra."""
    try:
        return TCA.aposta_de(email, mesa=mesa)
    except TCA.SemSaldo as e:
        raise ErroSala((f"{nome}: " if nome else "") + str(e))


def _faltam_stakes(p: dict) -> bool:
    return any(TB._chave(p["rodada"], j) not in (p.get("stakes") or {}) for j in (p.get("apostas") or {}))


def _garantir_stakes(pid: str, agora: float) -> None:
    """Mesa: grava, UMA vez por jogador e rodada, a aposta de referência = 1% do patrimônio do INÍCIO da rodada. Antes de ler o patrimônio, lança (idempotente)
    as rodadas já fechadas, para a aposta refletir o resultado anterior mesmo quando outra sessão foi quem abriu a rodada. Falha aqui não derruba a partida:
    sem registro, a rodada usa a aposta anterior (TB._stake)."""
    try:
        r = _row(pid)
        p = ((r or {}).get("dados") or {}).get("p")
        if not p or not _faltam_stakes(p):
            return
        TCA.liquidar_seguro(p)
        novas = {j: TCA.aposta_rodada(j, ap.get("conta")) for j, ap in (p.get("apostas") or {}).items() if TB._chave(p["rodada"], j) not in (p.get("stakes") or {})}
        rod = p["rodada"]

        def f(d):
            if not d.get("p") or d["p"]["rodada"] != rod:                  # a rodada já virou: esta aposta não vale mais
                return d
            n = copy.deepcopy(d)
            for j, a in novas.items():
                TB.definir_stake(n["p"], j, rod, a["stake"], a["pat"])    # idempotente: só grava se ainda não existe
            return d if n["p"]["versao"] == d["p"]["versao"] else n
        _mutar(pid, f, agora)
    except Exception as e:
        try:
            banco.registrar_erro("trader_online._garantir_stakes", e)
        except Exception:
            pass


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


def criar_sala(email: str, tf: str, agora: float | None = None, formato: str = TB.FORMATO_PADRAO, corrida: str | None = None) -> dict:
    """`corrida` = rapida / intermediaria / longa (partida corrida, sem rodadas; o tempo gráfico vem da duração).
    `formato` = rapida (3 rodadas) / normal (5) / longa (10): salas da mesa por rodadas, mantidas para compatibilidade."""
    agora = time.time() if agora is None else agora
    if corrida is not None:
        if corrida not in TB.CORRIDAS:
            raise ErroSala("Duração de partida inválida.")
        tf, formato = TB.CORRIDAS[corrida]["tf"], None
    elif tf not in TB.TIMEFRAMES:
        raise ErroSala("Timeframe inválido.")
    elif formato not in TB.FORMATOS:
        raise ErroSala("Formato de partida inválido.")
    elif formato not in TD.formatos_disponiveis(tf):
        raise ErroSala("Ainda não há cenários reais deste timeframe para esse formato. Escolha um formato menor ou outro timeframe.")
    limpar(agora)
    pid = partida_ativa(email)
    if pid:
        return {"id": pid, "codigo": ((_row(pid) or {}).get("dados") or {}).get("sala", {}).get("codigo", "")}
    _capital(email) if corrida else _aposta(email)
    for _ in range(8):
        codigo, novo = gerar_codigo(), secrets.token_hex(8)
        d = {"sala": {"codigo": codigo, "criador": email, "tf": tf, "formato": formato, "corrida": corrida, "criada": agora, "jogadores": [{"email": email, "nick": nick_de(email), "em": agora}]},
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
    return _entrar(email, achadas[0]["id"], agora)


def _entrar(email: str, pid: str, agora: float, publica: bool = False) -> dict:
    """Entra na sala `pid`. `publica`: entrada pela BUSCA de adversário (só em sala de busca, no máximo 2 jogadores)."""
    ja = partida_ativa(email)
    if ja == pid:
        return {"id": pid}
    sala = (((_row(pid) or {}).get("dados")) or {}).get("sala") or {}
    _capital(email) if sala.get("corrida") else _aposta(email)
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
        if publica and (not d["sala"].get("publica") or len(d["sala"]["jogadores"]) >= 2):
            raise ErroSala("Esta busca já achou adversário.")
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


# ------------------------------------------------------------------ busca de adversário (Trade Battle online, 1 contra 1)
# Não há criar sala nem código: quem quer jogar online "procura", e quem estiver procurando ao mesmo tempo (mesma duração) se encontra. Cada busca é uma sala
# marcada como `publica`; quem chega depois entra na mais ANTIGA que ainda esteja viva, então duas buscas nunca se escolhem uma à outra. Amigos se desafiam
# pelo convite (social), que cria a sala escondida e começa na hora.
BUSCA_VIVA_S = 12          # a busca só vale enquanto o app dela continua consultando (a cada 2 s)
BUSCA_MAX_ESPERA_S = 90    # depois disso a busca expira ("ninguém apareceu")


def _buscas_vivas(corrida: str, agora: float, ignorar: str) -> list[dict]:
    """Buscas públicas esperando adversário, da mais antiga para a mais nova (desempate pelo id)."""
    out = []
    for r in banco._selecionar("tb_partidas", {"status": "aguardando"}, ["id"], ordem="criado_em", limite=60):
        row = _row(r["id"])
        d = (row or {}).get("dados") or {}
        sala = d.get("sala") or {}
        if (not sala.get("publica") or d.get("cancelada") or d.get("p") or sala.get("corrida") != corrida or sala.get("criador") == ignorar
                or len(sala.get("jogadores") or []) >= 2 or agora - float(sala.get("visto") or 0) > BUSCA_VIVA_S):
            continue
        out.append({"id": row["id"], "criador": sala["criador"], "criada": float(sala.get("criada") or 0)})
    return sorted(out, key=lambda x: (x["criada"], x["id"]))


def _entrar_na_mais_antiga(email: str, corrida: str, agora: float, mais_nova_que: tuple | None = None) -> dict | None:
    for c in _buscas_vivas(corrida, agora, email):
        if mais_nova_que is not None and (c["criada"], c["id"]) >= mais_nova_que:
            continue                                                   # só entra em buscas MAIS ANTIGAS que a sua
        try:
            _entrar(email, c["id"], agora, publica=True)
        except ErroSala:
            continue                                                   # outro chegou primeiro: tenta a próxima
        iniciar(c["id"], c["criador"], agora)                          # os dois já estão: a partida começa na hora (o servidor inicia pelo criador da busca)
        return {"estado": "partida", "id": c["id"]}
    return None


def buscar(email: str, corrida: str, agora: float | None = None) -> dict:
    """Entra na busca: se há uma busca mais antiga esperando, a partida já começa; senão fica esperando. {'estado': 'partida'|'fila', 'id'}."""
    agora = time.time() if agora is None else agora
    if corrida not in TB.CORRIDAS:
        raise ErroSala("Duração de partida inválida.")
    limpar(agora)
    ja = partida_ativa(email)
    if ja:
        return consultar_busca(email, agora)
    _capital(email)
    achou = _entrar_na_mais_antiga(email, corrida, agora)
    if achou:
        return achou
    sala = criar_sala(email, "", agora, corrida=corrida)
    pid = sala["id"]

    def f(d):
        n = copy.deepcopy(d)
        n["sala"]["publica"], n["sala"]["visto"] = True, agora
        return n
    _mutar(pid, f, agora)
    return {"estado": "fila", "id": pid}


def consultar_busca(email: str, agora: float | None = None) -> dict:
    """Chamado a cada 2 s por quem está procurando: renova a presença e tenta achar uma busca mais antiga. {'estado': 'partida'|'fila'|'fora'|'expirou', 'id'?}"""
    agora = time.time() if agora is None else agora
    pid = partida_ativa(email)
    if not pid:
        return {"estado": "fora"}
    d = (_row(pid) or {}).get("dados") or {}
    sala = d.get("sala") or {}
    if d.get("p"):
        return {"estado": "partida", "id": pid}
    if d.get("cancelada") or not sala.get("publica"):
        return {"estado": "fora"}
    if email == sala.get("criador"):
        if len(sala.get("jogadores") or []) >= 2:                      # alguém entrou e ainda não começou: começa agora
            try:
                iniciar(pid, email, agora)
            except ErroSala:
                pass
            return {"estado": "partida", "id": pid}
        if agora - float(sala.get("criada") or agora) > BUSCA_MAX_ESPERA_S:
            sair(pid, email, agora)
            return {"estado": "expirou"}
        minha = (float(sala.get("criada") or 0), pid)
        outra = _entrar_na_mais_antiga_trocando(email, sala.get("corrida"), pid, agora, minha)
        if outra:
            return outra
        if BOTS.BOTS_ATIVOS and agora - float(sala.get("criada") or agora) >= BOTS.BOT_ESPERA_S:
            return _partida_com_bot(email, pid, agora)                    # ninguém apareceu: treino contra um bot (sempre identificado como bot)
        if agora - float(sala.get("visto") or 0) > 3:                  # renova a presença sem gravar a cada consulta
            def f(dd):
                n = copy.deepcopy(dd)
                n["sala"]["visto"] = agora
                return n
            _mutar(pid, f, agora)
    return {"estado": "fila", "id": pid}


def _partida_com_bot(email: str, pid: str, agora: float) -> dict:
    """Coloca um bot na busca do jogador e começa a partida na hora. Idempotente: se o bot já está lá, só devolve a partida."""
    try:
        troféus = int((banco.sis_estado_ler(email, "trofeus") or {}).get("trade", {}).get("t") or 0)
    except Exception:
        troféus = 0
    bot = BOTS.novo(pid, int(agora) % 997, troféus)

    def f(d):
        if d.get("p") or d.get("cancelada") or any(BOTS.eh_bot(j["email"]) for j in d["sala"]["jogadores"]) or len(d["sala"]["jogadores"]) != 1:
            return d
        n = copy.deepcopy(d)
        n["sala"]["jogadores"].append({"email": bot["email"], "nick": bot["nome"], "em": agora, "bot": True, "nivel": bot["nivel"], "trofeus": bot["trofeus"], "semente": bot["semente"]})
        return n
    d = _mutar(pid, f, agora)
    b = next((j for j in d["sala"]["jogadores"] if BOTS.eh_bot(j["email"])), None)
    if b:
        try:
            iniciar(pid, email, agora)                                # (o bot não tem conta: não entra em tb_jogadores, só na sala e na partida)
        except (TB.ErroTrader, ErroSala) as e:                        # sem gráfico real guardado (ou cenário inválido): encerra a busca e avisa, em vez de ficar tentando até expirar
            sair(pid, email, agora)
            return {"estado": "sem_graficos", "mensagem": str(e)}
        except Exception as e:                                        # falha inesperada (banco lento, etc.): registra e deixa a próxima consulta tentar de novo, sem derrubar a busca com erro 500
            banco.registrar_erro("trade.bot_iniciar", e)
            return {"estado": "fila", "id": pid, "aviso": "tentando de novo"}
        return {"estado": "partida", "id": pid}
    return {"estado": "fila", "id": pid}


def _entrar_na_mais_antiga_trocando(email: str, corrida: str, meu_pid: str, agora: float, minha: tuple) -> dict | None:
    """Duas buscas criadas ao mesmo tempo: a mais nova desiste da sua e entra na mais antiga (a mais antiga nunca faz o contrário)."""
    for c in _buscas_vivas(corrida, agora, email):
        if (c["criada"], c["id"]) >= minha:
            continue
        sair(meu_pid, email, agora)                                    # cancela a minha busca (libera a vaga ativa) e entra na outra
        achou = _entrar_na_mais_antiga(email, corrida, agora, mais_nova_que=minha)
        return achou or {"estado": "fila", "id": criar_busca_de_novo(email, corrida, agora)}
    return None


def criar_busca_de_novo(email: str, corrida: str, agora: float) -> str:
    sala = criar_sala(email, "", agora, corrida=corrida)

    def f(d):
        n = copy.deepcopy(d)
        n["sala"]["publica"], n["sala"]["visto"] = True, agora
        return n
    _mutar(sala["id"], f, agora)
    return sala["id"]


def sair_da_busca(email: str, agora: float | None = None) -> None:
    """Cancelar a busca (a sala de busca só existe enquanto ninguém entrou)."""
    agora = time.time() if agora is None else agora
    pid = partida_ativa(email)
    if not pid:
        return
    d = (_row(pid) or {}).get("dados") or {}
    if (d.get("sala") or {}).get("publica") and not d.get("p"):
        sair(pid, email, agora)


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
        formato = d["sala"].get("formato")                              # sala criada antes da mesa não tem formato: começa com as regras antigas
        semente = int(agora) % 100000
        corrida = d["sala"].get("corrida")
        if corrida in TB.CORRIDAS:                                      # partida corrida: cenário da duração e capital de 5% do caixa de cada um
            cen = TD.escolher_corrida(corrida, semente)
            n = copy.deepcopy(d)
            n["cen"] = TD.referencia_corrida(cen, semente)
            apostas = {j["email"]: _capital(j["email"], j["nick"]) for j in d["sala"]["jogadores"] if not BOTS.eh_bot(j["email"])}
            for j in d["sala"]["jogadores"]:                              # o bot joga com o MESMO capital do jogador: a comparação é justa
                if BOTS.eh_bot(j["email"]):
                    apostas[j["email"]] = {**next(iter(apostas.values())), "conta": ""}
            n["p"] = TB.nova_partida(cen, cen["tf"], jogs, agora, pid=pid, multi=True, apostas=apostas, corrida=corrida)
            equip = {j["email"]: ([] if BOTS.eh_bot(j["email"]) else SD.equipados(j["email"])) for j in d["sala"]["jogadores"]}
            n["p"]["setups"] = SV.iniciar(jogs, equip)                    # o setup de cada um fica congelado: trocar na central não muda esta partida
            ref = cen["candles"][cen["n_analise"] - 1]["c"]
            ini_r = TB.inicio_rodada(cen, 1, TB._nrp(n["p"]))
            for j in d["sala"]["jogadores"]:
                if not BOTS.eh_bot(j["email"]):
                    continue
                nivel = BOTS.NIVEL[j["nivel"]]                            # o bot tem plano de operações e nível de dificuldade; confirma a estratégia na hora
                plano = BJ.plano_do_bot(cen, ini_r, TB._nrp(n["p"]), nivel, int(j.get("semente") or semente))
                n["p"].setdefault("bots", {})[j["email"]] = {"nivel": nivel["id"], "nome": j["nick"], "trofeus": int(j["trofeus"]), "plano": plano["plano"]}
                rnd = random.Random(int(j.get("semente") or semente) + 7)
                certo = plano["direcao"]                                  # estratégia como a de uma pessoa: tipo variado e, às vezes, o lado errado
                lado = certo if rnd.random() < nivel["acerto"] else ("baixa" if certo == "alta" else "alta")
                TB.salvar_estrategia(n["p"], j["email"], {"direcao": lado, "tipo": rnd.choice(("continuacao", "continuacao", "reversao", "rompimento")), "confianca": rnd.randint(2, 4)}, None, ref, agora)
            return n
        cen = TD.escolher(tf, semente, rodadas=TB.FORMATOS[formato]) if formato in TB.FORMATOS else TD.escolher(tf, semente)
        n = copy.deepcopy(d)
        n["cen"] = TD.referencia(cen, semente)
        apostas = {j["email"]: _aposta(j["email"], j["nick"], mesa=formato in TB.FORMATOS) for j in d["sala"]["jogadores"]}
        n["p"] = TB.nova_partida(cen, tf, jogs, agora, pid=pid, multi=True, apostas=apostas, formato=formato if formato in TB.FORMATOS else None)
        return n
    try:
        _mutar(pid, f, agora)
    except TB.ErroTrader as e:
        raise ErroSala(str(e))
    return ler(pid, email, agora)


# ------------------------------------------------------------------ partida
def _publico(p: dict, email: str, agora: float | None = None) -> dict:
    """Só o que a camada de tela precisa do estado; nada de estratégias, desenhos ou pontos dos outros."""
    return {"id": p["id"], "tf": p["tf"], "fase": p["fase"], "t_fase": p["t_fase"], "rodada": p["rodada"], "multi": True,
            "pontos": {email: p["pontos"].get(email, 0.0)},
            "cfg": p.get("cfg"), "pausas": p.get("pausas"),          # só tempo/configuração (nada privado): o gráfico precisa do ritmo e da pausa
            "setup": SV.visao(p, email, time.time() if agora is None else agora)}   # só o evento e as marcas dos sinais ATIVADOS, do ponto de vista de quem pergunta


def _sincronizar(pid: str, agora: float) -> dict:
    """Aplica o que o relógio já determinou (fases, fechamento e abertura de rodadas). Só grava se algo mudou; corridas se resolvem pelo CAS."""
    def f(d):
        if not d.get("p") or d.get("cancelada"):
            return d
        n = copy.deepcopy(d)
        cen = _cenario(n)
        TB.avancar(n["p"], agora, {cen["id"]: cen})
        SV.processar(n["p"], cen, agora)                              # setups: prazo do evento em curso e sinais do candle que acabou de fechar
        BJ.agir(n["p"], cen, agora)                                   # bots de treino: as operações do plano que já chegaram na hora
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
        return {"estado": "sala", "sala": {"codigo": s["codigo"], "tf": s["tf"], "formato": s.get("formato"), "corrida": s.get("corrida"), "n": len(s["jogadores"]), "max": MAX_JOG, "min": MIN_JOG,
                                           "criador": s["criador"] == email,
                                           "jogadores": [{"nick": j["nick"], "voce": j["email"] == email, "criador": j["email"] == s["criador"]} for j in s["jogadores"]]}}
    d = _sincronizar(pid, agora)
    if d.get("cancelada"):
        return {"estado": "cancelada"}
    cen = _cenario(d)
    v = TB.visao(d["p"], cen, agora, email)
    return {"estado": "jogo", "v": v, "p": _publico(d["p"], email, agora)}


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
        ini = TB.inicio_rodada(cen, p["rodada"], TB._nrp(p))
        ref = cen["candles"][ini - 1]["c"]                              # preço de referência calculado aqui, não vindo do navegador
        TB.salvar_estrategia(p, email, est, marcas, ref, agora)
    _acao(pid, email, agora, fn)


def encerrar(pid: str, email: str, agora: float | None = None) -> None:
    """O jogador encerra a própria operação durante o replay (o servidor fixa o momento pelo relógio dele)."""
    agora = time.time() if agora is None else agora
    _acao(pid, email, agora, lambda p, cen: TB.encerrar_operacao(p, cen, email, agora))


def agir(pid: str, email: str, dados: dict, agora: float | None = None) -> None:
    """Ação da mesa (comprar, vender, ordem, mover, cancelar, encerrar). Tudo roda dentro do CAS sobre os dados recém-lidos, com o relógio do servidor:
    fase, pausa, candles revelados, duplicidade (`aid`) e regras da mesa são conferidos aqui. Erro ou clique repetido = nada é gravado de novo."""
    agora = time.time() if agora is None else agora
    _acao(pid, email, agora, lambda p, cen: TB.registrar_acao(p, cen, email, dados, agora))


def decidir_setup(pid: str, email: str, aceitar: bool, q=None, agora: float | None = None) -> dict:
    """O dono do setup ativado aceita (manda uma ordem a mercado pelo sistema atual) ou recusa. Fase, prazo, dono e duplicidade são conferidos aqui,
    dentro do CAS, com o relógio do servidor."""
    agora = time.time() if agora is None else agora
    out: dict = {}
    _acao(pid, email, agora, lambda p, cen: out.update(SV.decidir(p, cen, email, aceitar, q, agora)))
    return out


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

    def encerrar(self, agora):
        self._rodar(encerrar, self.pid, self.email, agora)

    def agir(self, dados, agora):
        self._rodar(agir, self.pid, self.email, dados, agora)


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
