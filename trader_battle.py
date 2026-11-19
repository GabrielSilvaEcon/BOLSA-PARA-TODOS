"""Trader Battle · regras puras (sem Streamlit, sem rede).

Jogo de análise técnica sobre cenários históricos reais: o jogador analisa o gráfico até um ponto, registra a estratégia e depois assiste
ao replay candle a candle. Este módulo guarda TUDO o que decide o jogo: validação de cenários, relógio do servidor, proteção dos candles
futuros, indicadores sobre o que já foi revelado e a avaliação da estratégia. A interface só desenha o que `visao()` devolve.

CONTINUIDADE: a partida é UM cenário contínuo (mesmo ativo e timeframe): n_analise candles de histórico + RODADAS blocos de replay, um por
rodada, em sequência cronológica. A rodada r começa vendo tudo até o fim da rodada r-1; a pontuação de cada rodada é calculada sobre a fatia
daquela rodada, com a mesma fórmula de sempre.

Pensado para o multiplayer (2 a 4 jogadores): o estado da partida é um dicionário JSON com `versao`, sem candles dentro; as estratégias
ficam por jogador; todas as funções recebem `agora` (relógio do servidor) e nenhuma depende do navegador.

DOIS MOTORES CONVIVEM (um único arquivo, sem motor paralelo):
· motor 1 (antigo): partidas SEM `cfg`. Estratégia única travada na análise, `avaliar` (0 a 100, sem pontos negativos), 30 s de replay, 10 rodadas.
  É o que continua valendo, sem nenhuma alteração, para toda partida gravada antes da mesa. `cfg_de(p)` devolve essas regras para ela.
· motor 2 (mesa de operações): partidas COM `cfg` (formato rapida/normal/longa = 3/5/10 rodadas; 24 candles em 60 s). O jogador opera ao vivo durante o replay.
  Fonte da verdade = lista append-only `p["acoes"]`; `simular_mesa` é pura e recalcula o estado a partir dela e dos candles já revelados.
  Pontos: `avaliar_mesa`. Patrimônio: `financeiro_mesa` (aposta de referência = 1% do patrimônio do início da rodada, fixa; resultados das operações se somam).
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime

RODADAS = 10
MIN_CENARIOS_REAIS = 3                     # abaixo disso a central avisa "modo demonstração" (não depende do número de rodadas)
T_ANALISE_S = 120
T_REPLAY_S = 30                            # duração do replay: tempo suficiente para acompanhar a operação e encerrá-la quando quiser
ESPERA_ENTRADA = 0.25                      # fração do replay em que a ordem limite espera o preço tocar a entrada; depois disso entra a mercado
                                           # (0 = sempre a mercado no 1º candle). Assim a operação SEMPRE acontece, tocando ou não o preço de entrada.
T_RESULTADO_S = 4                          # só no multiplayer: tempo do resultado antes da próxima rodada começar sozinha (igual para todos)
# n_analise = histórico que a pessoa vê (dobrado: 120 e 100 candles). na_aceitos inclui o tamanho antigo (60 e 50) só para que cenários reais já
# guardados continuem válidos; os novos sempre saem com o tamanho de n_analise, e a escolha prefere esses.
TIMEFRAMES = {"15m": {"nome": "15 minutos", "n_analise": 120, "na_aceitos": (120, 60), "n_replay": 24, "passo_min": 15, "max_dias": 28},
              "1h": {"nome": "1 hora", "n_analise": 100, "na_aceitos": (100, 50), "n_replay": 16, "passo_min": 60, "max_dias": 70},
              # partida corrida (motor 2 com quantidade livre): 5 minutos e 1 dia só existem nela
              "5m": {"nome": "5 minutos", "n_analise": 360, "na_aceitos": (360,), "n_replay": 84, "passo_min": 5, "max_dias": 20},
              "1d": {"nome": "1 dia", "n_analise": 300, "na_aceitos": (300,), "n_replay": 120, "passo_min": 1440, "max_dias": 900}}
# ---- PARTIDA CORRIDA (nov/2026): sem rodadas. Uma leitura no início, histórico 3x maior e um replay longo em que se opera com quantidade livre
# (regras em trader_qtd.py). Cada duração usa um tempo gráfico: rápida = 15 minutos, intermediária = 1 hora, longa = 1 dia.
# CANDLE SE FORMANDO (etapa D): o replay guarda os candles MENORES reais (`sub`) e cada um é um passo da partida. O candle do gráfico é a soma
# dos passos já revelados (abertura do 1º, máxima e mínima de todos, fechamento do último): ele cresce na tela exatamente como aconteceu.
# A simulação (ordens, stop, alvo, taxa) roda passo a passo nesses preços reais; nada entre dois passos é inventado.
CORRIDAS = {"rapida": {"tf": "15m", "sub": "5m", "k": 3, "n_analise": 300, "n_replay": 56},         # 56 × 15 min = 2 pregões · 3 passos por candle
            "intermediaria": {"tf": "1h", "sub": "5m", "k": 12, "n_analise": 300, "n_replay": 56},  # 56 × 1 h ≈ 8 pregões · 12 passos por candle
            "longa": {"tf": "1d", "sub": "1h", "k": 7, "n_analise": 300, "n_replay": 80}}           # 80 dias ≈ 4 meses · ~7 passos (horas do pregão)
ROTULO_CORRIDA = {"rapida": "Rápida", "intermediaria": "Intermediária", "longa": "Longa"}
SEG_POR_CANDLE = 4.0
JOGADORES_MIN, JOGADORES_MAX = 1, 4          # nesta etapa joga 1; a estrutura já aceita 2 a 4
DIRECOES = ("alta", "baixa", "lateral")
ESTRATEGIAS = ("continuacao", "reversao", "rompimento", "aguardar")
ROTULO_ESTRATEGIA = {"continuacao": "Continuação", "reversao": "Reversão", "rompimento": "Rompimento", "aguardar": "Aguardar"}
MAX_MARCAS = {"niveis": 6, "tendencias": 4, "notas": 6}
FASES = ("analise", "replay", "resultado", "fim")

# ---- MESA DE OPERAÇÕES (motor 2). Tudo o que é novo mora aqui, centralizado para facilitar ajuste. Partidas SEM `cfg` seguem o motor 1 (regras antigas).
MOTOR_LEGADO, MOTOR_MESA = 1, 2
FORMATOS = {"rapida": 3, "normal": 5, "longa": 10}          # nº de rodadas por formato; o servidor só aceita estes valores
ROTULO_FORMATO = {"rapida": "Rápida", "normal": "Normal", "longa": "Longa"}
FORMATO_PADRAO = "normal"
N_REPLAY_MESA = 24                                         # candles por rodada (nunca se muda a quantidade: ajusta-se o intervalo)
T_REPLAY_MESA_S = 60.0                                     # 60 s / 24 candles = 2,5 s por candle
MAX_ACOES_RODADA = 40                                      # por jogador e por rodada (proteção contra excesso de gravações)
PONTOS_MAX = 100.0                                         # teto de pontos por rodada (mesmo teto da pontuação antiga)
MOD_EDU = 0.25                                             # o modulador educacional muda a pontuação em no máximo ±25%, nunca o sinal
PONTOS_MIN_SINAL = 0.1                                     # lucro/prejuízo, por menor que seja, nunca arredonda para 0 ponto
UNIDADE_MIN = 0.0025                                       # piso da "unidade da rodada" (evita divisão por ~0 em histórico sem variação)
EPS_X = 1e-12                                              # abaixo disso o resultado conta como zero
TIPOS_ENTRADA = ("mercado", "limite", "stop_entrada")
LIMITE_PERDA_PCT_PAT = 0.03                                # limite de perda da rodada: 3% do patrimônio do INÍCIO da rodada (realizado + não realizado)


class ErroTrader(ValueError):
    """Ação inválida (estratégia fora das regras, fase errada, cenário inconsistente)."""


# ------------------------------------------------------------------ cenários
def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def validar_cenario(c: dict) -> tuple[bool, str]:
    """Um cenário só entra no jogo se estiver completo e coerente. Nada é preenchido ou corrigido: na dúvida, é recusado."""
    try:
        tf = c["tf"]
        cfg = TIMEFRAMES[tf]
        cand = c["candles"]
        na = int(c["n_analise"])
    except (KeyError, TypeError, ValueError):
        return False, "cenário incompleto"
    if not c.get("id") or not c.get("ticker"):
        return False, "sem identificação"
    if c.get("corrida") is not None:
        sp = CORRIDAS.get(c["corrida"])
        if not sp or sp["tf"] != tf or na != sp["n_analise"]:
            return False, "quantidade de candles diferente da prevista"
        g, vt = c.get("grupo"), c.get("velas_t")                 # candle se formando: passo -> candle do gráfico (0, 0, 0, 1, 1, ...)
        if (not isinstance(g, list) or not g or len(cand) != na + len(g) or g[0] != 0 or g[-1] != sp["n_replay"] - 1
                or any(not isinstance(x, int) or isinstance(x, bool) or y - x not in (0, 1) for x, y in zip(g, g[1:]))
                or not isinstance(vt, list) or len(vt) != sp["n_replay"]):
            return False, "passos do replay incompletos (sem os candles menores reais)"
    elif na not in cfg["na_aceitos"] or len(cand) not in (na + RODADAS * cfg["n_replay"], na + RODADAS * N_REPLAY_MESA):
        return False, "quantidade de candles diferente da prevista"
    ant = None
    for k in cand:
        if not isinstance(k, dict):
            return False, "candle em formato inesperado"
        o, h, l, cl, v = (_num(k.get(x)) for x in ("o", "h", "l", "c", "v"))
        if None in (o, h, l, cl, v) or min(o, h, l, cl) <= 0 or v < 0:
            return False, "candle com valor ausente ou inválido"
        if h < max(o, cl) - 1e-9 or l > min(o, cl) + 1e-9 or h < l:
            return False, "candle impossível (máxima/mínima inconsistentes)"
        try:
            t = datetime.fromisoformat(str(k["t"]))
        except (KeyError, ValueError):
            return False, "horário inválido"
        if ant is not None:
            dh = (t - ant).total_seconds() / 60
            if dh <= 0:
                return False, "candles fora de ordem"
            if dh > cfg["passo_min"] and dh > 5 * 24 * 60:      # lacuna de mais de 5 dias: histórico interrompido
                return False, "lacuna grande no histórico"
        ant = t
    return True, ""


def candles_sem_data(candles: list[dict]) -> list[dict]:
    """Candles como vão para a TELA: só o horário (HH:MM) e o dia da partida (1, 2, 3...), nunca a data do calendário, para que ninguém
    procure o histórico fora do jogo. A contagem começa no 1º candle da lista (sempre o 1º do cenário), então é estável entre atualizações."""
    out, dia, ant = [], 0, None
    for k in candles:
        t = str(k["t"])
        if t[:10] != ant:
            dia, ant = dia + 1, t[:10]
        out.append({**k, "t": t[11:16], "d": dia})
    return out


def formando(c: dict) -> bool:
    """Cenário com o candle se formando (passos = candles menores reais)."""
    return bool(c.get("grupo"))


def agrupar(subs: list[dict], grupo: list[int], velas_t: list[str] | None = None) -> list[dict]:
    """Candles do gráfico a partir dos passos já revelados: abertura do 1º passo, máxima e mínima de todos, fechamento do último, volume somado.
    O último pode estar incompleto (é o candle que está se formando). `velas_t`: horário de início de cada candle do gráfico."""
    out, ult = [], None
    for k, g in zip(subs, grupo):
        if g != ult:
            out.append({"t": velas_t[g] if velas_t else k["t"], "o": k["o"], "h": k["h"], "l": k["l"], "c": k["c"], "v": k["v"]})
            ult = g
        else:
            m = out[-1]
            m["h"], m["l"], m["c"], m["v"] = max(m["h"], k["h"]), min(m["l"], k["l"]), k["c"], m["v"] + k["v"]
    return out


def velas_replay(c: dict, ini: int, n: int) -> list[dict]:
    """Os n primeiros passos do replay, já como candles do gráfico (cenário sem passos: os próprios candles)."""
    if not formando(c):
        return [dict(k) for k in c["candles"][ini:ini + n]]
    return agrupar(c["candles"][ini:ini + n], c["grupo"][:n], c.get("velas_t"))


def cenario_em_velas(c: dict) -> dict:
    """O cenário inteiro com o replay em candles do gráfico (para a pontuação, o mercado real e a revelação)."""
    if not formando(c):
        return c
    na = int(c["n_analise"])
    return {**{k: v for k, v in c.items() if k not in ("grupo", "velas_t")}, "candles": c["candles"][:na] + velas_replay(c, na, len(c["grupo"]))}


def _idx_vela(c: dict, i: int) -> int:
    """Índice do passo -> índice do candle do gráfico (dentro do replay)."""
    g = c.get("grupo")
    if not g:
        return i
    return g[max(0, min(len(g) - 1, int(i)))]


def _em_velas(st: dict, c: dict) -> dict:
    """Estado da simulação com os índices das operações em candles do gráfico (para desenhar e pontuar). O original não é alterado."""
    if not formando(c):
        return st
    out = dict(st)
    out["trades"] = [{**t, "i_entrada": _idx_vela(c, t["i_entrada"]), "i_exc": _idx_vela(c, t["i_exc"]), "i_saida": _idx_vela(c, t["i_saida"]),
                      "p_entrada": t["i_entrada"], "p_saida": t["i_saida"]} for t in st["trades"]]
    if st.get("pos"):
        out["pos"] = {**st["pos"], "i_entrada": _idx_vela(c, st["pos"]["i_entrada"]), "i_exc": _idx_vela(c, st["pos"]["i_exc"])}
    return out


def rotulo_horario(k: dict) -> str:
    """Rótulo do eixo de tempo para um candle de `candles_sem_data` (ex.: 'D2 14:30')."""
    return f"D{k['d']} {k['t']}"


def dataframe(candles: list[dict]):
    """Candles do jogo → DataFrame OHLCV (formato do analise_tecnica)."""
    import pandas as pd
    idx = pd.to_datetime([k["t"] for k in candles])
    return pd.DataFrame({"Open": [k["o"] for k in candles], "High": [k["h"] for k in candles], "Low": [k["l"] for k in candles],
                         "Close": [k["c"] for k in candles], "Volume": [k["v"] for k in candles]}, index=idx)


# ------------------------------------------------------------------ rodadas contínuas
def _nr(c: dict) -> int:
    return TIMEFRAMES[c["tf"]]["n_replay"]


def inicio_rodada(c: dict, r: int, nr: int | None = None) -> int:
    """Quantos candles já são histórico quando a análise da rodada r começa (índice do primeiro candle do replay da rodada r).
    `nr` = candles por rodada da PARTIDA (cfg); sem ele vale o tamanho antigo do timeframe."""
    return c["n_analise"] + (r - 1) * (nr or _nr(c))


def cenario_da_rodada(c: dict, r: int, nr: int | None = None) -> dict:
    """Fatia do cenário usada para avaliar a rodada r: histórico até o começo dela + o replay dela. Os blocos seguintes ficam de fora."""
    nr = nr or _nr(c)
    ini = inicio_rodada(c, r, nr)
    return {**c, "candles": c["candles"][:ini + nr], "n_analise": ini}


def capacidade_rodadas(c: dict) -> int:
    """Quantas rodadas de N_REPLAY_MESA candles o cenário comporta (o 1h antigo, com 160 candles de replay, comporta 6)."""
    return max(0, (len(c["candles"]) - int(c["n_analise"])) // N_REPLAY_MESA)


# ------------------------------------------------------------------ configuração por partida (motor 1 = antigo, motor 2 = mesa)
def motor_de(p: dict) -> int:
    return MOTOR_MESA if p.get("cfg") else MOTOR_LEGADO


def cfg_de(p: dict) -> dict:
    """ÚNICO ponto que diz quantas rodadas, candles e segundos uma partida tem. Partida antiga (sem `cfg`) devolve as regras antigas, inalteradas."""
    c = p.get("cfg")
    if c:
        return c
    return {"v": 1, "motor": MOTOR_LEGADO, "formato": "legado", "rodadas": RODADAS, "n_replay": TIMEFRAMES[p["tf"]]["n_replay"], "t_replay_s": float(T_REPLAY_S)}


def _nrp(p: dict) -> int:
    return int(cfg_de(p)["n_replay"])


def config_mesa(formato: str) -> dict:
    if formato not in FORMATOS:
        raise ErroTrader("formato de partida inválido")
    return {"v": 2, "motor": MOTOR_MESA, "formato": formato, "rodadas": FORMATOS[formato], "n_replay": N_REPLAY_MESA, "t_replay_s": float(T_REPLAY_MESA_S)}


def config_corrida(formato: str, n_passos: int | None = None) -> dict:
    """Partida corrida: UMA rodada longa, quantidade livre (trader_qtd) e capital de 5% do caixa livre da Carteira.
    `n_replay` conta PASSOS (candles menores reais); `n_velas` = candles do gráfico. O relógio dá SEG_POR_CANDLE a cada candle do gráfico."""
    import trader_qtd as TQ
    sp = CORRIDAS.get(formato)
    if not sp:
        raise ErroTrader("formato de partida inválido")
    return {"v": 4, "motor": MOTOR_MESA, "formato": formato, "rodadas": 1, "n_replay": int(n_passos or sp["n_replay"]), "n_velas": sp["n_replay"],
            "t_replay_s": float(sp["n_replay"] * SEG_POR_CANDLE), "qtd": True, "taxa": TQ.TAXA_B3, "pct_capital": TQ.PCT_CAPITAL}


def qtd_de(p: dict) -> bool:
    return bool(cfg_de(p).get("qtd"))


CAPITAL_SEM_CONTA = 10_000.0     # partida sem conta/carteira (testes, demonstração): capital simbólico, sem efeito em dinheiro


def capital_de(p: dict, jog: str) -> float:
    ap = _stake(p, 1, jog)
    return float(ap["stake"]) if ap and float(ap.get("stake") or 0) > 0 else CAPITAL_SEM_CONTA


# ------------------------------------------------------------------ partida (estado JSON, sem candles)
PCT_APOSTA = 0.01              # a pessoa entra com 1% do patrimônio (da Wallet Game); esse valor é o capital de cada operação
# O limite é medido em "apostas" (retorno acumulado): 3% do patrimônio ÷ 1% por aposta = 3 apostas. Derivado das duas constantes, nunca digitado à parte.
LIMITE_PERDA_X = round(LIMITE_PERDA_PCT_PAT / PCT_APOSTA, 9)


def financeiro_rodada(r: dict, aposta: dict | None) -> dict | None:
    """Efeito em dinheiro de UMA rodada, calculado só no servidor. A operação usa o valor apostado inteiro, sem alavancagem:
    resultado = aposta × variação do preço entre a entrada e a saída (para quem vende, a conta é ao contrário).
    Quem aguardou não mexe no patrimônio. Toda operação é concluída (stop, alvo, encerramento manual ou fim do replay). Sem aposta devolve None."""
    if not aposta:
        return None
    op, est = r.get("operacao"), r["estrategia"]
    ret = 0.0
    if op and op.get("executada"):
        e, sai = float(op.get("preco_entrada") or est["entrada"]), float(op["saida"])
        ret = ((sai - e) if est["direcao"] == "alta" else (e - sai)) / e
    stake, pat = float(aposta["stake"]), float(aposta["pat"])
    pnl = round(stake * ret, 2)
    return {"aposta": stake, "pnl": pnl, "pct_aposta": round(ret * 100, 3), "pct_pat": round(pnl / pat * 100, 4) if pat > 0 else 0.0, "pat_ini": pat,
            "operou": bool(op and op.get("executada"))}


def nova_partida(cenario: dict, tf: str, jogadores: list[str], agora: float, pid: str | None = None, multi: bool = False,
                 apostas: dict | None = None, formato: str | None = None, corrida: str | None = None) -> dict:
    """`formato` (rapida/normal/longa) cria uma partida da MESA (motor 2). Sem ele nasce uma partida no motor antigo (usado só por testes e legado)."""
    if tf not in TIMEFRAMES:
        raise ErroTrader("timeframe inválido")
    if not (JOGADORES_MIN <= len(jogadores) <= JOGADORES_MAX) or len(set(jogadores)) != len(jogadores):
        raise ErroTrader("número de jogadores inválido")
    ok, why = validar_cenario(cenario)
    if not ok or cenario["tf"] != tf:
        raise ErroTrader(f"cenário recusado: {why or 'timeframe diferente'}")
    p = {"id": pid or uuid.uuid4().hex[:10], "tf": tf, "jogadores": list(jogadores), "cenario": cenario["id"], "cenarios": [cenario["id"]] * RODADAS,
            "demo": bool(cenario.get("demo")), "rodada": 1, "fase": "analise", "t_fase": float(agora), "versao": 1,
            "estrategias": {}, "travadas": {}, "resultados": {}, "pontos": {j: 0.0 for j in jogadores}, "multi": bool(multi), "prontos": {}, "apostas": dict(apostas or {}), "encerradas": {}}
    if corrida is not None:
        if cenario.get("corrida") != corrida or CORRIDAS[corrida]["tf"] != tf:
            raise ErroTrader("o cenário não é desta duração de partida")
        cfg = config_corrida(corrida, len(cenario["grupo"]))
        p["cfg"] = cfg
        p["cenarios"] = [cenario["id"]]
        p["acoes"], p["seq_acao"], p["pausas"] = [], 0, []
        p["stakes"] = {_chave(1, j): {"stake": float(ap["stake"]), "pat": float(ap["pat"])} for j, ap in (apostas or {}).items()}
    elif formato is not None:
        cfg = config_mesa(formato)
        if capacidade_rodadas(cenario) < cfg["rodadas"]:
            raise ErroTrader(f"o cenário não comporta {cfg['rodadas']} rodadas de {N_REPLAY_MESA} candles")
        p["cfg"] = cfg
        p["cenarios"] = [cenario["id"]] * cfg["rodadas"]
        p["acoes"], p["seq_acao"], p["pausas"] = [], 0, []
        p["stakes"] = {_chave(1, j): {"stake": float(ap["stake"]), "pat": float(ap["pat"])} for j, ap in (apostas or {}).items()}
    return p


def resumo_financeiro(p: dict, jog: str) -> dict | None:
    """Soma do que a partida rendeu (ou custou) ao jogador nas rodadas já encerradas. None quando ele jogou sem aposta."""
    ap = (p.get("apostas") or {}).get(jog)
    if not ap:
        return None
    fins = [p["resultados"][_chave(r, jog)].get("fin") for r in range(1, cfg_de(p)["rodadas"] + 1) if _chave(r, jog) in p["resultados"]]
    fins = [f for f in fins if f]
    pnl = round(sum(f["pnl"] for f in fins), 2)
    pat = float(ap["pat"])
    return {"aposta": float(ap["stake"]), "pnl": pnl, "pct_aposta": round(pnl / float(ap["stake"]) * 100, 3) if ap["stake"] else 0.0,
            "pct_pat": round(pnl / pat * 100, 4) if pat > 0 else 0.0, "pat_ini": pat, "pat_fim": round(pat + pnl, 2),
            "rodadas": [f["pnl"] for f in fins], "encerradas": len(fins)}


def _chave(rod: int, jog: str) -> str:
    return f"{rod}:{jog}"


# ---- pausa técnica: intervalos [ini, fim] gravados na partida. É do SERVIDOR (para os dois jogadores ao mesmo tempo); nenhum jogador pausa sozinho.
def pausada(p: dict) -> bool:
    return any(x.get("fim") is None for x in p.get("pausas") or [])


def _pausado_em(p: dict, a: float, b: float) -> float:
    """Segundos de pausa dentro de [a, b] (pausa em aberto vale até b)."""
    tot = 0.0
    for x in p.get("pausas") or []:
        f = x["fim"] if x.get("fim") is not None else b
        tot += max(0.0, min(f, b) - max(x["ini"], a))
    return tot


def _decorrido(p: dict, agora: float) -> float:
    """Segundos de relógio da fase atual, sem contar as pausas."""
    return max(0.0, (agora - p["t_fase"]) - _pausado_em(p, p["t_fase"], agora))


def _prazo(p: dict, dur: float) -> float:
    """Instante oficial em que a fase atual termina, empurrado pelas pausas. Infinito enquanto uma pausa em aberto o alcançar."""
    fim = p["t_fase"] + dur
    for x in sorted(p.get("pausas") or [], key=lambda y: y["ini"]):
        a = max(x["ini"], p["t_fase"])
        if a >= fim:
            break
        if x.get("fim") is None:
            return math.inf
        if x["fim"] > a:
            fim += x["fim"] - a
    return fim


def pausar(p: dict, agora: float, cenarios_por_id: dict | None = None) -> bool:
    """Pausa técnica compartilhada. Aplica antes o que o relógio já decidiu. Repetir é inofensivo. Devolve True se pausou agora."""
    avancar(p, agora, cenarios_por_id)
    if pausada(p) or p["fase"] == "fim":
        return False
    p.setdefault("pausas", []).append({"ini": float(agora), "fim": None})
    p["versao"] += 1
    return True


def retomar(p: dict, agora: float) -> bool:
    """Retoma para todos no mesmo instante: o tempo parado não conta em nenhuma fase."""
    mudou = False
    for x in p.get("pausas") or []:
        if x.get("fim") is None:
            x["fim"] = max(float(agora), x["ini"])
            mudou = True
    if mudou:
        p["versao"] += 1
    return mudou


def segundos_restantes(p: dict, agora: float) -> int:
    """Cronômetro do servidor: análise ou replay. Nas outras fases, 0."""
    if p["fase"] == "analise":
        return max(0, math.ceil(T_ANALISE_S - _decorrido(p, agora)))
    if p["fase"] == "replay":
        return max(0, math.ceil(cfg_de(p)["t_replay_s"] - _decorrido(p, agora)))
    if p["fase"] == "resultado" and p.get("multi"):
        return max(0, math.ceil(T_RESULTADO_S - _decorrido(p, agora)))
    return 0


def n_revelados(p: dict, agora: float) -> int:
    """Quantos candles do replay já podem aparecer, pelo relógio do servidor. Só existe na fase do replay (e vale tudo depois)."""
    cfg = cfg_de(p)
    n = int(cfg["n_replay"])
    if p["fase"] in ("resultado", "fim"):
        return n
    if p["fase"] != "replay":
        return 0
    return min(n, int(_decorrido(p, agora) / (cfg["t_replay_s"] / n)))


# ------------------------------------------------------------------ estratégia
def validar_estrategia(est: dict, preco_ref: float) -> dict:
    """Normaliza e valida a estratégia. Aguardar é sempre válida. Operar exige direção alta/baixa, entrada, stop e alvo coerentes."""
    if not isinstance(est, dict):
        raise ErroTrader("estratégia inválida")
    direcao = est.get("direcao")
    tipo = est.get("tipo")
    if direcao not in DIRECOES:
        raise ErroTrader("escolha a direção esperada")
    if tipo not in ESTRATEGIAS:
        raise ErroTrader("escolha a estratégia")
    conf = est.get("confianca")
    if not isinstance(conf, int) or not 1 <= conf <= 5:
        raise ErroTrader("a confiança vai de 1 a 5")
    out = {"direcao": direcao, "tipo": tipo, "confianca": conf, "entrada": None, "stop": None, "alvo": None}
    if tipo != "aguardar" and direcao in ("alta", "baixa"):
        e, s, a = (_num(est.get(k)) for k in ("entrada", "stop", "alvo"))
        if None in (e, s, a) or min(e, s, a) <= 0:
            raise ErroTrader("para operar, informe entrada, stop e alvo")
        ok = (s < e < a) if direcao == "alta" else (a < e < s)
        if not ok:
            raise ErroTrader("stop e alvo precisam ficar em lados opostos da entrada" + (" (stop abaixo e alvo acima)" if direcao == "alta" else " (alvo abaixo e stop acima)"))
        if abs(e / preco_ref - 1) > 0.08:
            raise ErroTrader("a entrada está muito longe do preço atual")
        out.update(entrada=e, stop=s, alvo=a)
    elif tipo != "aguardar" and direcao == "lateral":
        raise ErroTrader("para operar, a direção precisa ser alta ou baixa; para lateralização, escolha Aguardar")
    return out


def validar_marcas(m: dict | None) -> dict:
    """Desenhos e anotações registrados no gráfico (níveis de preço, linhas de tendência por dois pontos e notas curtas)."""
    m = m or {}
    niveis = []
    for x in (m.get("niveis") or [])[:MAX_MARCAS["niveis"]]:
        v = _num(x.get("preco") if isinstance(x, dict) else x)
        if v and v > 0:
            niveis.append({"preco": v, "rotulo": str((x.get("rotulo") if isinstance(x, dict) else "") or "")[:20]})
    tend = []
    for x in (m.get("tendencias") or [])[:MAX_MARCAS["tendencias"]]:
        try:
            i1, i2 = int(x["i1"]), int(x["i2"])
            p1, p2 = float(x["p1"]), float(x["p2"])
        except (KeyError, TypeError, ValueError):
            continue
        if i1 != i2 and p1 > 0 and p2 > 0 and min(i1, i2) >= 0:
            tend.append({"i1": i1, "p1": p1, "i2": i2, "p2": p2})
    notas = []
    for x in (m.get("notas") or [])[:MAX_MARCAS["notas"]]:
        try:
            notas.append({"i": int(x["i"]), "preco": float(x["preco"]), "texto": str(x.get("texto") or "")[:40]})
        except (KeyError, TypeError, ValueError):
            continue
    return {"niveis": niveis, "tendencias": tend, "notas": notas}


def salvar_estrategia(p: dict, jog: str, est: dict, marcas: dict | None, preco_ref: float, agora: float) -> dict:
    """Registra (ou atualiza) a estratégia durante a análise. Depois de travada ou fora da análise, é recusada: ninguém muda a estratégia vendo o replay."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    avancar(p, agora)
    if p["fase"] != "analise":
        raise ErroTrader("a análise já terminou")
    k = _chave(p["rodada"], jog)
    if p["travadas"].get(k):
        raise ErroTrader("a estratégia já foi travada")
    if qtd_de(p):                                          # partida corrida: a estratégia é a boleta do início, confirmada UMA vez
        if k in p["estrategias"]:
            raise ErroTrader("a estratégia já foi confirmada")
        p["estrategias"][k] = {**validar_plano(p, jog, est, preco_ref), "marcas": validar_marcas(marcas), "salva_em": float(agora)}
    else:
        p["estrategias"][k] = {**(validar_leitura(est) if motor_de(p) == MOTOR_MESA else validar_estrategia(est, preco_ref)), "marcas": validar_marcas(marcas), "salva_em": float(agora)}
    p["versao"] += 1
    if (p.get("multi") or qtd_de(p)) and all(_chave(p["rodada"], j) in p["estrategias"] for j in p["jogadores"]):
        _travar(p)                                         # multiplayer: quando TODOS confirmaram, o replay começa sozinho (sem botão 'pronto')
        p["fase"], p["t_fase"] = "replay", float(agora)
        p["versao"] += 1
    return p["estrategias"][k]


def _travar(p: dict) -> None:
    """Fecha a análise: quem não registrou nada fica com 'Aguardar' sem estratégia (também é uma decisão válida).
    Na partida corrida, a ordem planejada na boleta do início entra sozinha como a 1ª ação de cada jogador, no 1º preço do replay."""
    for j in p["jogadores"]:
        k = _chave(p["rodada"], j)
        if p["travadas"].get(k):
            continue
        p["travadas"][k] = True
        p["estrategias"].setdefault(k, {"direcao": None, "tipo": "aguardar", "confianca": None, "entrada": None, "stop": None, "alvo": None,
                                        "marcas": {"niveis": [], "tendencias": [], "notas": []}, "sem_registro": True})
        plano = p["estrategias"][k].get("plano")
        if qtd_de(p) and plano and not any(a["jogador"] == j and a.get("aid") == "plano" for a in p.get("acoes") or []):
            p["seq_acao"] = int(p.get("seq_acao", 0)) + 1
            p.setdefault("acoes", []).append({**plano, "aid": "plano", "jogador": j, "rodada": p["rodada"], "n_rev": 0, "ordem": p["seq_acao"],
                                              "t": float(p.get("t_fase", 0.0))})


def validar_plano(p: dict, jog: str, est: dict, preco_ref: float) -> dict:
    """Estratégia da partida corrida: só a leitura do mercado (Subir, Cair ou Aguardar), confirmada uma vez no início.
    Nenhuma ordem nasce aqui: comprar e vender só depois que o gráfico começa a andar (campos de ordem enviados junto são ignorados)."""
    if not isinstance(est, dict):
        raise ErroTrader("estratégia inválida")
    dirc = est.get("direcao")
    if dirc in (None, "", "lateral") or est.get("tipo") == "aguardar":
        return {"direcao": "lateral", "tipo": "aguardar", "confianca": None, "entrada": None, "stop": None, "alvo": None, "plano": None}
    if dirc not in ("alta", "baixa"):
        raise ErroTrader("escolha Subir, Cair ou Aguardar")
    tipo = est.get("tipo") if est.get("tipo") in ESTRATEGIAS else "continuacao"
    return {"direcao": dirc, "tipo": tipo, "confianca": None, "entrada": None, "stop": None, "alvo": None, "plano": None}


def iniciar_replay(p: dict, jog: str, agora: float) -> None:
    """Fim antecipado da análise (nesta etapa, com 1 jogador; no multiplayer só quando todos estiverem prontos)."""
    avancar(p, agora)
    if p["fase"] != "analise":
        return
    if _chave(p["rodada"], jog) not in p["estrategias"]:
        raise ErroTrader("salve a estratégia antes de iniciar o replay")
    _travar(p)
    p["fase"], p["t_fase"] = "replay", float(agora)
    p["versao"] += 1


def _avancar_uma(p: dict, agora: float, cenarios_por_id: dict | None) -> None:
    cfg = cfg_de(p)
    if p["fase"] == "analise":
        prazo = _prazo(p, T_ANALISE_S)
        if agora >= prazo:
            _travar(p)
            p["fase"], p["t_fase"] = "replay", prazo           # o replay começa na hora certa, mesmo que ninguém estivesse olhando
            p["versao"] += 1
    if p["fase"] == "replay":
        prazo = _prazo(p, cfg["t_replay_s"])
        if agora >= prazo:
            p["fase"], p["t_fase"] = "resultado", prazo
            p["versao"] += 1
            if cenarios_por_id:
                fechar_rodada(p, cenarios_por_id[p["cenarios"][p["rodada"] - 1]])
    if p.get("multi") and p["fase"] == "resultado" and cenarios_por_id:
        prazo = _prazo(p, T_RESULTADO_S)
        if agora >= prazo:
            fechar_rodada(p, cenarios_por_id[p["cenarios"][p["rodada"] - 1]])      # idempotente
            proxima_rodada(p, prazo)                           # a próxima rodada começa no instante oficial, igual para todos


def avancar(p: dict, agora: float, cenarios_por_id: dict | None = None) -> dict:
    """Aplica as mudanças de fase que o relógio do servidor já determinou. Chamar de novo é inofensivo.
    Se ninguém consultou por um tempo, encadeia quantas fases forem necessárias (cada uma com o seu horário oficial)."""
    for _ in range(16):
        antes = (p["versao"], p["fase"], p["rodada"])
        _avancar_uma(p, agora, cenarios_por_id)
        if (p["versao"], p["fase"], p["rodada"]) == antes:
            break
    return p


# ------------------------------------------------------------------ multiplayer: ninguém avança a partida sozinho
def marcar_pronto(p: dict, jog: str, agora: float) -> bool:
    """Multiplayer: o jogador diz 'estou pronto' (fim antecipado da análise ou do resultado). A fase só muda quando TODOS marcarem
    (ou quando o relógio do servidor decidir). Devolve True se esta chamada fez a fase mudar. Marcar de novo é inofensivo."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    avancar(p, agora)
    fase = p["fase"]
    if fase not in ("analise", "resultado"):
        return False
    if fase == "analise" and _chave(p["rodada"], jog) not in p["estrategias"]:
        raise ErroTrader("salve a estratégia antes de iniciar o replay")
    k = f"{p['rodada']}:{fase}:{jog}"
    if p["prontos"].get(k):
        return False
    p["prontos"][k] = True
    p["versao"] += 1
    if not all(p["prontos"].get(f"{p['rodada']}:{fase}:{j}") for j in p["jogadores"]):
        return False
    if fase == "analise":
        _travar(p)
        p["fase"], p["t_fase"] = "replay", float(agora)
    else:
        proxima_rodada(p, agora)
        return True
    p["versao"] += 1
    return True


def prontos_da_fase(p: dict, jog: str) -> dict:
    fase = p["fase"]
    ks = [f"{p['rodada']}:{fase}:{j}" for j in p["jogadores"]]
    return {"eu": bool(p["prontos"].get(f"{p['rodada']}:{fase}:{jog}")), "n": sum(1 for k in ks if p["prontos"].get(k)), "total": len(ks)}


def fechar_rodada(p: dict, cenario: dict) -> None:
    """Calcula no servidor o resultado de cada jogador na rodada atual (uma única vez)."""
    if motor_de(p) == MOTOR_MESA:
        return _fechar_rodada_mesa(p, cenario)
    novo = False
    for j in p["jogadores"]:
        k = _chave(p["rodada"], j)
        if k in p["resultados"]:
            continue
        r = avaliar(cenario_da_rodada(cenario, p["rodada"]), p["estrategias"][k], (p.get("encerradas") or {}).get(k))
        r["fin"] = financeiro_rodada(r, (p.get("apostas") or {}).get(j))
        p["resultados"][k] = r
        p["pontos"][j] = round(p["pontos"][j] + r["pontos"], 1)
        novo = True
    if novo:
        p["versao"] += 1


def proxima_rodada(p: dict, agora: float) -> None:
    if p["fase"] != "resultado":
        raise ErroTrader("a rodada ainda não terminou")
    if p["rodada"] >= cfg_de(p)["rodadas"]:
        p["fase"] = "fim"
    else:
        p["rodada"] += 1
        p["fase"], p["t_fase"] = "analise", float(agora)
    p["versao"] += 1


# ------------------------------------------------------------------ o que o jogador pode ver
def _n_rev_rodada(p: dict, r: int, agora: float) -> int:
    """Candles do replay da rodada r já revelados (rodadas passadas: todos; futuras: nenhum)."""
    n = _nrp(p)
    if r < p["rodada"] or p["fase"] in ("resultado", "fim") and r == p["rodada"]:
        return n
    if r > p["rodada"]:
        return 0
    return n_revelados(p, agora) if p["fase"] == "replay" else 0


def entrada_executada(p: dict, cenario: dict, agora: float, r: int, jog: str) -> dict | None:
    """Entrada JÁ EXECUTADA do jogador na rodada r: só existe se a estratégia está travada e a execução já aconteceu num candle REVELADO
    (ordem limite tocada, ou entrada a mercado depois da espera). Devolve o preço real da execução e o candle; nunca a intenção ainda não executada."""
    k = _chave(r, jog)
    est = p["estrategias"].get(k)
    if not est or not p["travadas"].get(k) or est.get("tipo") == "aguardar" or est.get("entrada") is None:
        return None
    ini, nr = inicio_rodada(cenario, r), _nr(cenario)
    rev = cenario["candles"][ini:ini + _n_rev_rodada(p, r, agora)]
    ex = execucao(rev, est["entrada"], nr)
    if ex is None:
        return None
    i, preco, tipo = ex
    return {"rodada": r, "jogador": jog, "preco": preco, "indice": ini + i, "direcao": est["direcao"], "tipo": tipo}


def operacao_viva(p: dict, cenario: dict, agora: float, r: int, jog: str) -> dict | None:
    """Situação da operação do jogador na rodada r usando SÓ os candles já revelados (e o encerramento manual, se houve).
    estado: aguardando (ordem limite esperando) · aberta · fechada (stop, alvo, manual ou fim) · cancelada (encerrou antes de executar)."""
    k = _chave(r, jog)
    est = p["estrategias"].get(k)
    if not est or not p["travadas"].get(k) or est.get("tipo") == "aguardar" or est.get("entrada") is None:
        return None
    ini, nr = inicio_rodada(cenario, r), _nr(cenario)
    nrev = _n_rev_rodada(p, r, agora)
    enc = (p.get("encerradas") or {}).get(k)
    rev = cenario["candles"][ini:ini + (min(nrev, enc) if enc else nrev)]
    if not rev:
        return {"estado": "aguardando", "encerravel": False, "pct": 0.0, "por": None, "preco_entrada": None, "preco_saida": None, "indice_saida": None}
    st = _simular(rev, est, nr)
    alta = est["direcao"] == "alta"
    out = {"estado": st["estado"], "encerravel": False, "pct": 0.0, "por": st.get("por"), "preco_entrada": st.get("preco_entrada"),
           "preco_saida": st.get("saida"), "indice_saida": None if st.get("candle_saida") is None else ini + st["candle_saida"]}
    if enc and st["estado"] == "aguardando":
        out["estado"] = "cancelada"
    elif enc and st["estado"] == "aberta":
        out.update(estado="fechada", por="manual", preco_saida=st["ultimo"], indice_saida=ini + st["candle_ultimo"])
    elif st["estado"] == "aberta" and (r < p["rodada"] or p["fase"] in ("resultado", "fim")):      # rodada acabou sem stop, alvo nem encerramento: sai no último preço
        out.update(estado="fechada", por="fim", preco_saida=st["ultimo"], indice_saida=ini + st["candle_ultimo"])
    px, sai = out["preco_entrada"], out["preco_saida"] if out["estado"] == "fechada" else (st.get("ultimo") if st["estado"] == "aberta" else None)
    if px and sai:
        out["pct"] = round(((sai - px) if alta else (px - sai)) / px * 100, 3)
    out["encerravel"] = bool(p["fase"] == "replay" and r == p["rodada"] and not enc and out["estado"] in ("aguardando", "aberta") and nrev >= 1)
    return out


def encerrar_operacao(p: dict, cenario: dict, jog: str, agora: float) -> None:
    """O jogador encerra a operação quando quiser, durante o replay. O servidor fixa o momento pelo SEU relógio (candles já revelados) e a
    operação sai ao fechamento do último candle revelado. Se a ordem ainda esperava a entrada, ela é cancelada. Repetir é inofensivo."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    if motor_de(p) == MOTOR_MESA:
        raise ErroTrader("nesta partida, encerre a posição pela mesa (registrar_acao)")
    avancar(p, agora)
    if p["fase"] != "replay":
        raise ErroTrader("só dá para encerrar a operação durante o replay")
    k = _chave(p["rodada"], jog)
    est = p["estrategias"].get(k)
    if not est or est.get("tipo") == "aguardar" or est.get("entrada") is None:
        raise ErroTrader("você não tem operação nesta rodada")
    enc = p.setdefault("encerradas", {})
    if k in enc:
        return
    n = n_revelados(p, agora)
    if n < 1:
        raise ErroTrader("aguarde o primeiro candle do replay")
    ini = inicio_rodada(cenario, p["rodada"])
    st = _simular(cenario["candles"][ini:ini + n], est, _nr(cenario))
    if st["estado"] == "fechada":
        raise ErroTrader("a operação já foi encerrada pelo " + ("stop" if st["por"] == "stop" else "alvo"))
    enc[k] = n
    p["versao"] += 1


def pode_ver_adversarios(p: dict, cenario: dict, agora: float, jog: str) -> bool:
    """Regra de visibilidade: o jogador só enxerga as entradas executadas dos adversários depois de ter executado ao menos uma entrada
    própria na partida (vale individualmente e permanece até o fim)."""
    return any(entrada_executada(p, cenario, agora, r, jog) for r in range(1, p["rodada"] + 1))


def entradas_adversarios(p: dict, cenario: dict, agora: float, jog: str) -> list[dict]:
    """Entradas executadas dos adversários na rodada atual, rotuladas por posição ('Jogador N'). Sem identidade real, sem stop/alvo, sem planejado."""
    if not pode_ver_adversarios(p, cenario, agora, jog):
        return []
    out = []
    for n, j in enumerate(p["jogadores"], 1):
        if j == jog:
            continue
        e = entrada_executada(p, cenario, agora, p["rodada"], j)
        if e:
            out.append({"rotulo": f"Jogador {n}", "preco": e["preco"], "indice": e["indice"]})
    return out


def _marcas_anteriores(p: dict, jog: str) -> dict:
    """Desenhos pessoais mais recentes do próprio jogador em rodadas anteriores (só dele; serve para reconstruir a tela se o gráfico for remontado)."""
    for r in range(p["rodada"] - 1, 0, -1):
        m = (p["estrategias"].get(_chave(r, jog)) or {}).get("marcas")
        if m and any(m.get(k) for k in ("niveis", "tendencias", "notas")):
            return m
    return {}


def visao(p: dict, cenario: dict, agora: float, jog: str) -> dict:
    """ÚNICO caminho de dados para a tela: só devolve candles já revelados da rodada atual (e o histórico das anteriores).
    Os candles futuros não existem aqui, então não há como vazar. O jogador precisa ser da partida (identidade validada pelo servidor).
    Na mesa (motor 2) devolve também `mesa` (a posição, as ordens e os resultados SÓ do próprio jogador) e `adversarios` (só entradas e saídas já executadas)."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    cfg, mesa = cfg_de(p), motor_de(p) == MOTOR_MESA
    nr = int(cfg["n_replay"])
    cand = cenario["candles"]
    ini = inicio_rodada(cenario, p["rodada"], nr)
    if p["fase"] == "analise":
        visiveis = cand[:ini]
    elif p["fase"] == "replay":
        visiveis = cand[:ini] + velas_replay(cenario, ini, n_revelados(p, agora))
    else:
        visiveis = cand[:ini] + velas_replay(cenario, ini, nr)
    k = _chave(p["rodada"], jog)
    fim = p["fase"] in ("resultado", "fim")
    oculto = qtd_de(p) and p["fase"] != "fim"                 # corrida: o ativo e a data só aparecem no fim (ninguém pesquisa o futuro fora do jogo)
    v = {"ticker": "Ativo oculto" if oculto else cenario["ticker"], "nome": "Ativo oculto" if oculto else (cenario.get("nome") or cenario["ticker"]),
         "oculto": oculto, "revelado": revelacao(p, cenario) if qtd_de(p) and p["fase"] == "fim" else None, "tf": cenario["tf"], "demo": bool(cenario.get("demo")),
         "fonte": cenario.get("fonte", ""), "rodada": p["rodada"], "rodadas": cfg["rodadas"], "fase": p["fase"], "segundos": segundos_restantes(p, agora),
         "n_analise": ini, "candles": [dict(c) for c in visiveis], "revelados": max(0, len(visiveis) - ini),
         "total_replay": int(cfg.get("n_velas") or nr), "motor": motor_de(p), "formato": cfg.get("formato"), "pausada": pausada(p),
         "estrategia": p["estrategias"].get(k), "travada": bool(p["travadas"].get(k)), "pontos": p["pontos"].get(jog, 0.0),
         "resultado": p["resultados"].get(k) if fim else None,
         "adversarios": [] if mesa else entradas_adversarios(p, cenario, agora, jog), "jogador": jog, "marcas_ant": _marcas_anteriores(p, jog),
         "multi": bool(p.get("multi")), "prontos": prontos_da_fase(p, jog) if p["fase"] in ("analise", "resultado") else None,
         "confirmados": {"eu": k in p["estrategias"], "n": sum(1 for j in p["jogadores"] if _chave(p["rodada"], j) in p["estrategias"]),
                         "total": len(p["jogadores"])} if p["fase"] == "analise" else None,
         "pontos_rodadas": [round(p["resultados"][_chave(r, jog)]["pontos"], 1) for r in range(1, cfg["rodadas"] + 1) if _chave(r, jog) in p["resultados"]],
         "propria": None if mesa else entrada_executada(p, cenario, agora, p["rodada"], jog),
         "operacao": None if mesa or p["fase"] not in ("replay", "resultado", "fim") else operacao_viva(p, cenario, agora, p["rodada"], jog),
         "aposta": (p.get("apostas") or {}).get(jog), "fin_total": resumo_financeiro(p, jog),
         "placar_rodada": placar_rodada(p, jog) if fim else None, "final": resumo_final(p, jog) if p["fase"] == "fim" else None}
    if mesa:
        v["mesa"] = _visao_mesa(p, cenario, agora, jog)
        v["adversarios"] = _adversarios_mesa(p, cenario, agora, jog)
    return v


# ------------------------------------------------------------------ mesa: o que cada jogador pode ver
def _sim_rodada(p: dict, cenario: dict, agora: float, jog: str):
    """Simulação do jogador na rodada atual usando SÓ os candles já revelados (na fase do resultado, a rodada inteira, já fechada)."""
    if p["fase"] not in ("replay", "resultado", "fim"):
        return None
    nr, r = _nrp(p), p["rodada"]
    ini = inicio_rodada(cenario, r, nr)
    n = n_revelados(p, agora)
    st = _sim_jog(p, jog, cenario["candles"][ini:ini + n], acoes_da_rodada(p, r, jog), cenario["candles"][ini - 1]["c"], p["fase"] != "replay")
    return _em_velas(st, cenario), ini, n


def _ops_publicas(st: dict, ini: int) -> list[dict]:
    """O que o adversário PODE ver: direção, preço de entrada e preço de saída já executados. Nunca stop, alvo, ordem pendente, motivo da saída ou ids."""
    out = [{"direcao": t["direcao"], "preco_entrada": t["entrada"], "indice_entrada": ini + t["i_entrada"], "aberta": False,
            "preco_saida": t["saida"], "indice_saida": ini + t["i_saida"]} for t in st["trades"]]
    pos = st["pos"]
    if pos:
        out.append({"direcao": pos["direcao"], "preco_entrada": pos["entrada"], "indice_entrada": ini + pos["i_entrada"], "aberta": True, "preco_saida": None, "indice_saida": None})
    return out


def _adversarios_mesa(p: dict, cenario: dict, agora: float, jog: str) -> list[dict]:
    """Entradas e saídas dos adversários, em tempo real, SEM exigir que o jogador tenha operado: cada uma aparece quando o servidor a executa."""
    out = []
    for n, j in enumerate(p["jogadores"], 1):
        if j == jog:
            continue
        r = _sim_rodada(p, cenario, agora, j)
        if r is not None:
            st = r[0]
            pos = st["pos"]
            aberto = _lado(pos["direcao"]) * (st["preco_atual"] - pos["entrada"]) / pos["entrada"] if pos else 0.0
            if qtd_de(p):
                import trader_qtd as TQ
                aberto = TQ.aberto(st, st["preco_atual"]) / st["cap"] if st["cap"] else 0.0
            # resultado da rodada (realizado + aberto, em % da aposta), calculado só com o que já é público: entradas e saídas executadas
            out.append({"rotulo": f"Jogador {n}", "ops": _ops_publicas(st, r[1]), "total_pct": round((sum(t["ret"] for t in st["trades"]) + aberto) * 100, 3)})
    return out


def _visao_mesa(p: dict, cenario: dict, agora: float, jog: str) -> dict | None:
    """Mesa PRIVADA do jogador: posição, stop, alvo, ordens pendentes e resultados. Só ele recebe isto."""
    r = _sim_rodada(p, cenario, agora, jog)
    if r is None:
        return None
    st, ini, n = r
    ap = _stake(p, p["rodada"], jog)
    if qtd_de(p):
        import trader_qtd as TQ
        return TQ.visao(st, ini, p["fase"] == "replay" and not pausada(p), n, _nrp(p), len(acoes_da_rodada(p, p["rodada"], jog)), MAX_ACOES_RODADA,
                        float(ap["pat"]) if ap else None)
    stake = float(ap["stake"]) if ap else None

    def val(x):
        return None if stake is None else round(stake * x, 2)
    pos, px = st["pos"], st["preco_atual"]
    realizado = sum(t["ret"] for t in st["trades"])
    aberto = _lado(pos["direcao"]) * (px - pos["entrada"]) / pos["entrada"] if pos else 0.0
    base, pend = pos or st["pend"], st["pend"]
    lim_preco = preco_limite_perda(pos, realizado, st["limite_x"])
    usado = max(0.0, -(realizado + aberto)) / st["limite_x"] * LIMITE_PERDA_PCT_PAT * 100        # % do patrimônio já perdido (≥ 3,0 = limite atingido)
    ordens = []
    if pend:
        ordens.append({"id": "entrada", "tipo": pend["tipo"], "direcao": pend["direcao"], "preco": pend["preco"]})
    if base:
        for c in ("stop", "alvo"):
            if base.get(c) is not None:
                ordens.append({"id": c, "preco": base[c]})
    ativo = p["fase"] == "replay" and not pausada(p)
    return {"preco_atual": px, "stake": stake, "pat_ini": float(ap["pat"]) if ap else None,
            "posicao": None if not pos else {"direcao": pos["direcao"], "preco_entrada": pos["entrada"], "indice_entrada": ini + pos["i_entrada"], "stop": pos["stop"], "alvo": pos["alvo"]},
            "ordens": ordens,
            "operacoes": [{"n": t["n"], "direcao": t["direcao"], "preco_entrada": t["entrada"], "indice_entrada": ini + t["i_entrada"], "preco_saida": t["saida"],
                           "indice_saida": ini + t["i_saida"], "motivo": t["motivo"], "pct": round(t["ret"] * 100, 3), "val": val(t["ret"])} for t in st["trades"]],
            "n_encerradas": len(st["trades"]), "realizado_pct": round(realizado * 100, 3), "realizado_val": val(realizado),
            "aberto_pct": round(aberto * 100, 3), "aberto_val": val(aberto), "total_pct": round((realizado + aberto) * 100, 3), "total_val": val(realizado + aberto),
            "limite": {"pct_pat": LIMITE_PERDA_PCT_PAT * 100, "usado_pct_pat": round(usado, 3), "bloqueado": bool(st["bloq"]), "preco": lim_preco},
            "pode_abrir": bool(ativo and not st["bloq"] and not pos and not pend and n < _nrp(p) and len(acoes_da_rodada(p, p["rodada"], jog)) < MAX_ACOES_RODADA),
            "pode_encerrar": bool(ativo and pos), "pode_cancelar": bool(ativo and (pend or (pos and (pos["stop"] is not None or pos["alvo"] is not None)))),
            "pode_gerir": bool(ativo and (pos or pend))}


_ROT_MOTIVO = {"stop": "no stop", "stop_movel": "no stop móvel", "limite": "no limite de perda", "alvo": "no alvo", "manual": "encerrada por você", "fim": "no fim da rodada"}


def explicar_mesa(r: dict) -> list[tuple[str, str]]:
    """Raio-X da rodada da mesa em linguagem simples: resultado financeiro e como ele virou pontos."""
    est, real, pt = r["estrategia"], r["real"], r["partes"]
    nome = {"alta": "alta", "baixa": "baixa", "lateral": "lateralização"}
    linhas = []
    if est.get("sem_registro"):
        linhas.append(("Sua leitura", "Você não registrou a leitura do gráfico no tempo."))
    else:
        if est.get("confianca") is None:                    # partida corrida: a estratégia é a boleta do início
            leitura = {"alta": "o preço ia subir", "baixa": "o preço ia cair"}.get(est.get("direcao"))
            linhas.append(("Sua estratégia", f"Você disse que {leitura}." if leitura else "Você preferiu aguardar para ler o mercado."))
        else:
            linhas.append(("Sua leitura", f"Você registrou: {nome.get(est.get('direcao'), '')} ({ROTULO_ESTRATEGIA.get(est.get('tipo'), '').lower()}), confiança {est.get('confianca')}/5."))
    linhas.append(("O mercado", f"O preço foi de {real['ref']:.2f} para {real['fim']:.2f} ({real['mov_pct']:+.1f}%): {nome[real['direcao']]}."))
    ops = r.get("operacoes") or []
    if not ops:
        if r.get("qualidade_nota") is not None:          # partida corrida: a leitura ainda vale para o ranking de Qualidade
            linhas.append(("Operações", "Você não operou: sem lucro, sem prejuízo e 0 ponto na partida."))
            linhas.append(("Qualidade", f"Sua leitura vale nota {r['qualidade_nota']:.0f}/100 no ranking de Qualidade."))
            return linhas
        linhas.append(("Operações", "Você não operou nesta rodada: sem lucro, sem prejuízo e 0 ponto."))
        return linhas
    for t in ops:
        lado = "Compra" if t["direcao"] == "alta" else "Venda"
        if "q" in t:                                        # partida corrida: quantidade e resultado em T$ (com as taxas)
            val = f"{abs(t['pnl']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linhas.append((f"Operação {t['n']}", f"{lado} de {t['q']} ações, preço médio {t['entrada']:.2f} → {t['saida']:.2f} {_ROT_MOTIVO.get(t['motivo'], '')}: "
                                                 f"{'+' if t['pnl'] >= 0 else '−'}T$ {val} ({t['ret'] * 100:+.2f}% do capital)."))
            continue
        linhas.append((f"Operação {t['n']}", f"{lado} {t['entrada']:.2f} → {t['saida']:.2f} {_ROT_MOTIVO.get(t['motivo'], '')}: {t['ret'] * 100:+.2f}%."))
    if r.get("limite_atingido") and r.get("qtd"):
        linhas.append(("Limite de perda", "A perda chegou ao capital da partida (5% do saldo disponível): a posição foi encerrada e não houve novas entradas."))
    elif r.get("limite_atingido"):
        linhas.append(("Limite de perda", f"A perda acumulada chegou a {LIMITE_PERDA_PCT_PAT * 100:.0f}% do patrimônio: posições encerradas, ordens pendentes canceladas e novas entradas bloqueadas até a próxima rodada. O prejuízo real foi mantido."))
    q = pt["q"]
    if "peso_res" in pt:                                    # partida corrida: 70% resultado + 30% qualidade
        linhas.append(("Resultado", f"Lucro de {pt['x'] * 100:+.2f}% do capital (movimento típico do ativo: {pt['unidade'] * 100:.2f}%) → {pt['res']:+.1f} de 100."))
        conf = f" · confiança {q['confianca']:+.2f}" if est.get("confianca") else ""
        linhas.append(("Qualidade", f"Direção {q['direcao']:+.0f} · entrada {q['entrada']:+.2f} · risco {q['risco']:+.2f}{conf} → nota {r['qualidade_nota']:.0f}/100."))
        linhas.append(("Pontos", f"70% × {pt['res']:+.1f} + 30% × {pt['qual'] * 100:+.0f} = {r['pontos']:+.1f}. O lucro pesa mais; a qualidade da análise completa."))
        return linhas
    linhas.append(("Resultado", f"Soma das operações: {pt['x'] * 100:+.2f}% (unidade da rodada: {pt['unidade'] * 100:.2f}%) → {pt['base']:+.1f} pontos."))
    linhas.append(("Qualidade", f"Direção {q['direcao']:+.0f} · entrada {q['entrada']:+.2f} · risco {q['risco']:+.2f} · confiança {q['confianca']:+.2f} = {q['total']:+.2f} (ajuste de até ±25%)."))
    linhas.append(("Pontos", f"{pt['base']:+.1f} × {pt['fator']:.2f} = {r['pontos']:+.1f}. Lucro e prejuízo valem no patrimônio e nos pontos, sem compensação."))
    return linhas


def retorno_pct(res: dict | None) -> float | None:
    """Retorno de uma rodada da mesa em % da aposta (soma das operações). None no motor antigo ou sem resultado."""
    if not res or res.get("motor") != MOTOR_MESA:
        return None
    return round(sum(t["ret"] for t in res.get("operacoes") or []) * 100, 3)


# ---- XP (única recompensa do jogo; nenhuma TickerCoin: o dinheiro é só o lucro/prejuízo das operações na Wallet Game)
# XP = colocação (cresce com o tamanho da sala) + bônus da pontuação (só a parte positiva). Nunca é negativo.
XP_POSICAO = {2: (20, 10), 3: (30, 18, 10), 4: (40, 25, 15, 8)}     # nº de jogadores que jogaram → XP do 1º, 2º, 3º, 4º
XP_SOLO = 10                                                           # partida individual (ou sala em que só você jogou): sem colocação
XP_POR_PONTOS = 10                                                     # +1 XP a cada 10 pontos positivos da partida (100 pontos = +10 XP)
XP_PARTIDAS_DIA = 3                                                    # só as 3 primeiras partidas do dia valem XP


def jogou(p: dict, jog: str) -> bool:
    """Registrou a leitura em pelo menos uma rodada (quem só deixou o tempo passar não conta como jogador)."""
    return any(k.split(":", 1)[1] == jog and not e.get("sem_registro") for k, e in p["estrategias"].items())


def xp_da_partida(p: dict, jog: str) -> dict:
    """XP que a partida TERMINADA vale para `jog`: colocação entre quem de fato jogou (protege contra sala com 'fantasma'; mais jogadores,
    mais XP) + bônus pela pontuação positiva. Pontuação negativa não tira XP. Empate em pontos divide a melhor colocação.
    O limite diário e o crédito ficam com quem grava o progresso (a tela)."""
    nada = {"xp": 0, "pos": None, "n": 0, "xp_pos": 0, "xp_pts": 0}
    if p["fase"] != "fim" or jog not in p["jogadores"] or not jogou(p, jog):
        return nada
    pts = {x["jog"]: x["pontos"] for x in placar_final(p)}
    bonus = max(0, int(pts[jog] // XP_POR_PONTOS))
    ativos = [j for j in p["jogadores"] if jogou(p, j)]
    if len(ativos) < 2:
        return {"xp": XP_SOLO + bonus, "pos": None, "n": 1, "xp_pos": XP_SOLO, "xp_pts": bonus}
    pos = 1 + sum(1 for j in ativos if pts[j] > pts[jog])
    base = XP_POSICAO[len(ativos)][pos - 1]
    return {"xp": base + bonus, "pos": pos, "n": len(ativos), "xp_pos": base, "xp_pts": bonus}


def _rotulos(p: dict, jog: str) -> dict:
    """Como cada jogador aparece para `jog`: ele mesmo é 'Você', os outros 'Jogador N' (nunca o e-mail)."""
    return {j: ("Você" if j == jog else f"Jogador {n}") for n, j in enumerate(p["jogadores"], 1)}


def placar_rodada(p: dict, jog: str) -> list[dict]:
    """Pontos e retorno de cada jogador na rodada ATUAL já fechada (só existe depois do fechamento; nada do futuro)."""
    rot, out = _rotulos(p, jog), []
    for j in p["jogadores"]:
        res = p["resultados"].get(_chave(p["rodada"], j))
        if res:
            out.append({"rotulo": rot[j], "voce": j == jog, "pts": round(float(res["pontos"]), 1), "ret_pct": retorno_pct(res)})
    return out


def revelacao(p: dict, cenario: dict) -> dict:
    """Fim da partida corrida: qual era o ativo e de quando eram os candles do replay (datas reais)."""
    nr = _nrp(p)
    ini = inicio_rodada(cenario, 1, nr)
    rep = velas_replay(cenario, ini, nr)

    def br(t):
        t = str(t)
        return f"{t[8:10]}/{t[5:7]}/{t[:4]}"
    return {"ticker": cenario["ticker"], "nome": cenario.get("nome") or cenario["ticker"], "de": br(rep[0]["t"]) if rep else "", "ate": br(rep[-1]["t"]) if rep else "",
            "tf_nome": TIMEFRAMES[cenario["tf"]]["nome"], "demo": bool(cenario.get("demo"))}


def resumo_final(p: dict, jog: str) -> dict:
    """Tudo o que a tela de fim de partida mostra, já rotulado para `jog`: classificação, pontos por rodada e o Raio-X das rodadas DELE."""
    rot, n_rod = _rotulos(p, jog), cfg_de(p)["rodadas"]
    pl = [{"rotulo": rot[x["jog"]], "voce": x["jog"] == jog, "pos": x["pos"], "pontos": x["pontos"], "ret_pct": x["ret_pct"]} for x in placar_final(p)]
    meus = [p["resultados"].get(_chave(k, jog)) for k in range(1, n_rod + 1)]
    return {"placar": pl, "rodadas": [round(float(r["pontos"]), 1) if r else 0.0 for r in meus],
            "raiox": [[k, explicar(r)] for k, r in enumerate(meus, 1) if r], "xp": xp_da_partida(p, jog)}


def placar_final(p: dict) -> list[dict]:
    """Classificação da partida: pontos somados de todas as rodadas (o que decide) e retorno somado em % da aposta.
    Empate em pontos mantém a ordem de entrada na sala. Só números: quem chama decide os rótulos (nunca o e-mail na tela)."""
    out = []
    for n, j in enumerate(p["jogadores"], 1):
        rets = [retorno_pct(p["resultados"].get(_chave(r, j))) for r in range(1, cfg_de(p)["rodadas"] + 1)]
        out.append({"jog": j, "n": n, "pontos": round(float(p["pontos"].get(j, 0.0)), 1),
                    "ret_pct": None if all(x is None for x in rets) else round(sum(x or 0.0 for x in rets), 3)})
    out.sort(key=lambda x: -x["pontos"])
    for i, x in enumerate(out, 1):
        x["pos"] = i
    return out


# ------------------------------------------------------------------ indicadores (sempre sobre o que já foi revelado)
def indicadores(candles: list[dict], cfg: dict) -> dict:
    """Médias móveis, RSI e zonas de suporte/resistência calculados só com os candles recebidos (nunca com o futuro).
    cfg: {'sma': n|0, 'ema': n|0, 'rsi': n|0, 'sr': bool}. Devolve listas alinhadas aos candles (None onde não há valor)."""
    import analise_tecnica as AT
    out = {"sma": None, "ema": None, "rsi": None, "sr": {"suportes": [], "resistencias": []}, "avisos": []}
    if len(candles) < 5:
        return out
    df = dataframe(candles)

    def _serie(nome, col, **kw):
        r, why = AT.tentar(nome, df, **kw)
        if r is None:
            out["avisos"].append(f"{nome}: {why}")
            return None
        return [None if (v != v) else float(v) for v in r[col].tolist()]
    if cfg.get("sma"):
        out["sma"] = _serie("SMA", "SMA", n=int(cfg["sma"]))
    if cfg.get("ema"):
        out["ema"] = _serie("EMA", "EMA", n=int(cfg["ema"]))
    if cfg.get("rsi"):
        out["rsi"] = _serie("RSI", "RSI", n=int(cfg["rsi"]))
    if cfg.get("sr"):
        try:
            z = AT.suportes_resistencias(df)
            out["sr"] = {"suportes": [{"preco": x["preco"], "toques": x["toques"]} for x in z["suportes"]],
                         "resistencias": [{"preco": x["preco"], "toques": x["toques"]} for x in z["resistencias"]]}
        except Exception:
            out["avisos"].append("Suporte/resistência indisponível agora.")
    return out


# ------------------------------------------------------------------ avaliação (servidor)
def _atr(cand: list[dict], n: int = 14) -> float:
    base = cand[-(n + 1):]
    trs = []
    for i in range(1, len(base)):
        pc = base[i - 1]["c"]
        trs.append(max(base[i]["h"] - base[i]["l"], abs(base[i]["h"] - pc), abs(base[i]["l"] - pc)))
    return sum(trs) / len(trs) if trs else 0.0


def mercado_real(cenario: dict) -> dict:
    """O que o mercado fez no replay: movimento líquido, direção real (lateral se o movimento ficou dentro de 1 ATR) e extremos."""
    na = cenario["n_analise"]
    cand = cenario["candles"]
    ref = cand[na - 1]["c"]
    rep = cand[na:]
    fim = rep[-1]["c"]
    atr = _atr(cand[:na])
    mov = fim - ref
    if atr <= 0 or abs(mov) < atr:
        d = "lateral"
    else:
        d = "alta" if mov > 0 else "baixa"
    return {"ref": ref, "fim": fim, "mov_pct": (fim / ref - 1) * 100, "direcao": d, "atr": atr,
            "maxima": max(k["h"] for k in rep), "minima": min(k["l"] for k in rep)}


def execucao(cand_replay: list[dict], entrada: float, n_replay: int) -> tuple[int, float, str] | None:
    """Quando e a que preço a operação entra. A ordem é limite: executa no preço da entrada se um dos primeiros candles (ESPERA_ENTRADA do replay)
    o tocar. Se não tocar, entra a mercado, na abertura do candle seguinte à espera. Só usa os candles recebidos, então não vaza o futuro:
    devolve None enquanto a ordem ainda está esperando. Devolve (índice do candle, preço, 'limite' | 'mercado')."""
    espera = max(0, int(n_replay * ESPERA_ENTRADA))
    for i, k in enumerate(cand_replay):
        if i < espera and k["l"] <= entrada <= k["h"]:
            return i, entrada, "limite"
        if i >= espera:
            return i, k["o"], "mercado"
    return None


def _simular(rev: list[dict], est: dict, n_replay: int) -> dict:
    """Passo único da simulação sobre os candles recebidos. estado: aguardando · aberta · fechada (stop/alvo). Não decide o fim do replay."""
    e, s, a, alta = est["entrada"], est["stop"], est["alvo"], est["direcao"] == "alta"
    ex = execucao(rev, e, n_replay)
    if ex is None:
        return {"estado": "aguardando"}
    i0, px, tipo = ex
    risco = abs(e - s) or 1e-9
    base = {"preco_entrada": px, "tipo_entrada": tipo, "candle_entrada": i0, "executada": True}

    def r_de(saida):
        return ((saida - px) if alta else (px - saida)) / risco
    for i in range(i0 if tipo == "limite" else i0 + 1, len(rev)):        # entrada a mercado: stop/alvo só valem a partir do candle seguinte
        k = rev[i]
        bateu_stop = k["l"] <= s if alta else k["h"] >= s
        bateu_alvo = k["h"] >= a if alta else k["l"] <= a
        if bateu_stop:                                                    # stop e alvo no mesmo candle: vale o stop (hipótese conservadora)
            return {**base, "estado": "fechada", "por": "stop", "saida": s, "motivo": "Stop atingido.", "r": r_de(s), "candle_saida": i}
        if bateu_alvo:
            return {**base, "estado": "fechada", "por": "alvo", "saida": a, "motivo": "Alvo atingido.", "r": r_de(a), "candle_saida": i}
    return {**base, "estado": "aberta", "ultimo": rev[-1]["c"], "candle_ultimo": len(rev) - 1}


def simular_operacao(cand_replay: list[dict], est: dict, ate: int | None = None) -> dict:
    """Resultado FINAL da operação. Ela sempre se conclui: sai no stop, no alvo, quando o jogador encerra (`ate` = candles revelados nesse
    momento) ou, sem nada disso, no último fechamento do replay. Não ficar tocando a entrada não a impede: depois da espera, entra a mercado.
    Única exceção: se o jogador encerrar ANTES de a ordem executar, a ordem é cancelada (sem lucro nem prejuízo)."""
    n = len(cand_replay)
    manual = ate is not None and 0 < ate < n
    rev = cand_replay[:ate] if manual else cand_replay
    st = _simular(rev, est, n)
    nulo = {"executada": False, "saida": None, "r": 0.0, "candle_entrada": None, "candle_saida": None, "preco_entrada": None, "tipo_entrada": None, "por": None}
    if st["estado"] == "aguardando":
        return {**nulo, "motivo": "Você encerrou antes de a ordem ser executada: a ordem foi cancelada." if manual else "A ordem não chegou a ser executada.", "por": "cancelada"}
    if st["estado"] == "fechada":
        return st
    saida = st["ultimo"]
    alta = est["direcao"] == "alta"
    risco = abs(est["entrada"] - est["stop"]) or 1e-9
    px = st["preco_entrada"]
    return {**st, "estado": "fechada", "por": "manual" if manual else "fim", "saida": saida, "r": ((saida - px) if alta else (px - saida)) / risco,
            "candle_saida": st["candle_ultimo"],
            "motivo": f"Você encerrou a operação no candle {st['candle_ultimo'] + 1}." if manual else "Replay terminou sem stop nem alvo; encerrada no último preço."}


def avaliar(cenario: dict, est: dict, ate: int | None = None) -> dict:
    """Pontuação educativa (0 a 100), calculada no servidor:
    · direção (até 40): acertou 40; 'aguardar' vale 40 se o mercado ficou lateral, senão 15 (ficou de fora);
    · operação (até 40): R realizado de −1 a 3 vira 0 a 40 (0 R = 20); ordem cancelada por você antes de executar vale 15;
    · confiança (±10): quem acerta com mais confiança ganha, quem erra com mais confiança perde.
    Não é recomendação nem mede lucro real."""
    real = mercado_real(cenario)
    rep = cenario["candles"][cenario["n_analise"]:]
    aguardou = est["tipo"] == "aguardar" or est["direcao"] in (None, "lateral")
    acertou = None
    if est["direcao"] is None:
        pts_dir, acertou = (40.0 if real["direcao"] == "lateral" else 15.0), real["direcao"] == "lateral"
    elif est["tipo"] == "aguardar":
        pts_dir = 40.0 if real["direcao"] == "lateral" else 15.0
        acertou = real["direcao"] == "lateral"
    else:
        acertou = est["direcao"] == real["direcao"]
        pts_dir = 40.0 if acertou else 0.0
    op = None
    pts_op = 20.0 if aguardou else 0.0
    if not aguardou:
        op = simular_operacao(rep, est, ate)
        pts_op = 15.0 if not op["executada"] else max(0.0, min(40.0, 20.0 + max(-1.0, min(3.0, op["r"])) * (20.0 / 3.0 if op["r"] >= 0 else 20.0)))
    conf = est.get("confianca")
    pts_conf = 0.0
    if conf and acertou is not None:
        pts_conf = (conf - 1) * 2.5 * (1 if acertou else -1)
    total = max(0.0, min(100.0, pts_dir + pts_op + pts_conf))
    return {"pontos": round(total, 1), "real": real, "acertou_direcao": acertou, "operacao": op, "partes": {"direcao": pts_dir, "operacao": round(pts_op, 1),
            "confianca": pts_conf}, "estrategia": est}


_RE_DEC = re.compile(r"(?<=\d)\.(?=\d)")
_RE_NEG = re.compile(r"(?<![\w.,])-(?=\d)")


def _ptbr(linhas: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Números do Raio-X no padrão brasileiro do app: vírgula decimal e sinal de menos tipográfico (42,09 · −3,00%)."""
    return [(t, _RE_NEG.sub("−", _RE_DEC.sub(",", x))) for t, x in linhas]


def explicar(r: dict) -> list[tuple[str, str]]:
    """Raio-X em linguagem simples: o que a pessoa previu, o que o mercado fez e como cada parte virou pontos."""
    if r.get("motor") == MOTOR_MESA:
        return _ptbr(explicar_mesa(r))
    est, real, op, pt = r["estrategia"], r["real"], r["operacao"], r["partes"]
    nome = {"alta": "alta", "baixa": "baixa", "lateral": "lateralização"}
    linhas = []
    if est.get("sem_registro"):
        linhas.append(("Estratégia", "Nenhuma estratégia foi registrada no tempo: contou como Aguardar, sem operação."))
    else:
        prev = "aguardar" if est["tipo"] == "aguardar" else f"{nome.get(est['direcao'], '')} ({ROTULO_ESTRATEGIA[est['tipo']].lower()})"
        linhas.append(("Sua leitura", f"Você registrou: {prev}" + (f", confiança {est['confianca']}/5." if est.get("confianca") else ".")))
    linhas.append(("O mercado", f"O preço foi de {real['ref']:.2f} para {real['fim']:.2f} ({real['mov_pct']:+.1f}%): {nome[real['direcao']]}. "
                   "Lateral = movimento líquido menor que 1 ATR (a variação média dos candles)."))
    if op is not None:
        if not op["executada"]:
            linhas.append(("Operação", op["motivo"]))
        else:
            como = "a mercado" if op.get("tipo_entrada") == "mercado" else "no preço limite"
            linhas.append(("Operação", f"Entrou {como} em {op['preco_entrada']:.2f}. {op['motivo']} Resultado: {op['r']:+.1f} R (R = o risco entre entrada e stop)."))
    elif est["tipo"] == "aguardar" or est.get("sem_registro"):
        linhas.append(("Operação", "Você ficou de fora. Aguardar vale pontos quando o mercado não oferece direção clara."))
    linhas.append(("Pontos", f"Direção {pt['direcao']:.0f} + operação {pt['operacao']:.0f} + confiança {pt['confianca']:+.1f} = {r['pontos']:.1f} de 100."))
    return _ptbr(linhas)


# ====================================================================================================================================
# MESA DE OPERAÇÕES (motor 2) · simulador central, registro de ações, financeiro e pontuação.
# O servidor é a única fonte da verdade: o estado de cada jogador é SEMPRE recalculado a partir da lista append-only `p["acoes"]` e dos
# candles já revelados (`simular_mesa` é uma função pura, sem relógio e sem acesso ao futuro). Nada é guardado "meio calculado".
# ====================================================================================================================================
def _lado(direcao: str) -> int:
    return 1 if direcao == "alta" else -1


def _lado_ok(direcao: str, campo: str, preco: float, ref: float) -> bool:
    """O stop fica do lado perdedor do preço de referência e o alvo do lado ganhador (compra: stop abaixo, alvo acima; venda: o inverso)."""
    if campo == "stop":
        return preco < ref if _lado(direcao) == 1 else preco > ref
    return preco > ref if _lado(direcao) == 1 else preco < ref


def _abrir(st: dict, direcao: str, preco: float, i_ent: int, i_exc: int, tipo: str, stop, alvo) -> None:
    """i_ent: candle onde fica o marcador de entrada; i_exc: primeiro candle que conta para a excursão da operação."""
    st["pos"] = {"direcao": direcao, "entrada": float(preco), "i_entrada": i_ent, "i_exc": i_exc, "tipo_entrada": tipo, "stop": stop, "alvo": alvo,
                 "com_stop": stop is not None}


def _fechar(st: dict, preco: float, indice: int, motivo: str) -> None:
    pos = st["pos"]
    ret = _lado(pos["direcao"]) * (preco - pos["entrada"]) / pos["entrada"]
    st["trades"].append({"n": len(st["trades"]) + 1, "direcao": pos["direcao"], "entrada": pos["entrada"], "i_entrada": pos["i_entrada"], "i_exc": pos["i_exc"],
                         "tipo_entrada": pos["tipo_entrada"], "saida": float(preco), "i_saida": indice, "motivo": motivo, "ret": ret, "com_stop": pos["com_stop"]})
    st["pos"] = None
    if sum(t["ret"] for t in st["trades"]) <= -st["limite_x"] + EPS_X:             # limite de perda atingido (o prejuízo realizado NÃO é truncado nem apagado)
        st["bloq"] = True
        st["pend"] = None                                                         # ordens pendentes canceladas; novas entradas bloqueadas até a próxima rodada


def preco_limite_perda(pos: dict | None, realizado: float, limite_x: float = LIMITE_PERDA_X) -> float | None:
    """Preço em que o resultado acumulado da rodada (realizado + posição aberta) chega a −limite. Age como um stop implícito, com as regras do stop.
    None se não há posição ou se o nível ficaria em zero/negativo (uma compra não chega ao limite com a posição sozinha)."""
    if not pos:
        return None
    falta = -limite_x - realizado                       # negativo: quanto a posição ainda pode perder, em fração da entrada
    nivel = pos["entrada"] * (1 + falta) if _lado(pos["direcao"]) == 1 else pos["entrada"] * (1 - falta)
    return nivel if nivel > 0 else None


def _aplicar(st: dict, a: dict, px: float, i: int) -> None:
    """Aplica UMA ação no instante em que `i` candles já estavam revelados. `px` = último fechamento revelado (ou a referência, se i = 0).
    Ação que não cabe no estado (duas posições, stop do lado errado...) é ignorada e contada; o registro já a recusa antes de gravar."""
    t = a["tipo"]
    if t in TIPOS_ENTRADA and st["bloq"]:
        st["ignoradas"] += 1                                                   # limite de perda atingido: nenhuma entrada nova nesta rodada
        return
    if t == "mercado":
        if st["pos"] or st["pend"]:
            st["ignoradas"] += 1
            return
        stop, alvo = a.get("stop"), a.get("alvo")
        stop = stop if stop is not None and _lado_ok(a["direcao"], "stop", stop, px) else None
        alvo = alvo if alvo is not None and _lado_ok(a["direcao"], "alvo", alvo, px) else None
        _abrir(st, a["direcao"], px, i - 1, i, "mercado", stop, alvo)         # a mercado: no fechamento do último candle revelado
    elif t in ("limite", "stop_entrada"):
        if st["pos"] or st["pend"]:
            st["ignoradas"] += 1
            return
        st["pend"] = {"tipo": t, "direcao": a["direcao"], "preco": a["preco"], "stop": a.get("stop"), "alvo": a.get("alvo"), "ordem": a["ordem"]}
    elif t in ("definir_stop", "mover_stop", "definir_alvo", "mover_alvo"):
        campo = "stop" if t.endswith("stop") else "alvo"
        o = st["pos"] or st["pend"]
        if o is None or not _lado_ok(o["direcao"], campo, a["preco"], px if st["pos"] else o["preco"]):
            st["ignoradas"] += 1
            return
        o[campo] = a["preco"]
        if campo == "stop" and st["pos"]:
            st["pos"]["com_stop"] = True
    elif t == "cancelar":                                                      # cancelar nunca gera lucro nem prejuízo
        o = a.get("qual")                                                      # qual ordem cancelar (não confundir com `ordem`, a sequência de processamento)
        if o in ("entrada", "todas"):
            st["pend"] = None
        alvo_o = st["pos"] or st["pend"]
        if alvo_o is not None:
            if o in ("stop", "todas"):
                alvo_o["stop"] = None
            if o in ("alvo", "todas"):
                alvo_o["alvo"] = None
    elif t == "encerrar":
        if st["pos"]:
            _fechar(st, px, i - 1, "manual")
        else:
            st["ignoradas"] += 1


def _candle(st: dict, k: dict, i: int) -> None:
    """Processa o candle i: primeiro a entrada pendente, depois stop/alvo da posição. Gap: se a abertura já passou do nível, executa na abertura."""
    pe = st["pend"]
    if st["pos"] is None and pe:
        lado, nivel, fill = _lado(pe["direcao"]), pe["preco"], None
        if pe["tipo"] == "limite":                                              # compra abaixo / venda acima do preço de quando foi enviada
            if lado == 1 and k["l"] <= nivel:
                fill = k["o"] if k["o"] <= nivel else nivel
            elif lado == -1 and k["h"] >= nivel:
                fill = k["o"] if k["o"] >= nivel else nivel
        else:                                                                   # stop de entrada: compra acima / venda abaixo (rompimento)
            if lado == 1 and k["h"] >= nivel:
                fill = k["o"] if k["o"] >= nivel else nivel
            elif lado == -1 and k["l"] <= nivel:
                fill = k["o"] if k["o"] <= nivel else nivel
        if fill is not None:
            st["pend"] = None
            _abrir(st, pe["direcao"], fill, i, i, pe["tipo"], pe.get("stop"), pe.get("alvo"))
    pos = st["pos"]
    if pos is None:
        return
    lado, stop, alvo = _lado(pos["direcao"]), pos["stop"], pos["alvo"]
    motivo_stop = "stop"
    lim = preco_limite_perda(pos, sum(t["ret"] for t in st["trades"]), st["limite_x"])
    if lim is not None and (stop is None or (lim > stop if lado == 1 else lim < stop)):   # vale o mais próximo; no empate vale o stop do jogador
        stop, motivo_stop = lim, "limite"
    bateu_stop = stop is not None and (k["l"] <= stop if lado == 1 else k["h"] >= stop)
    bateu_alvo = alvo is not None and (k["h"] >= alvo if lado == 1 else k["l"] <= alvo)
    if bateu_stop:                                                              # stop e alvo no mesmo candle: vale o stop
        gap = k["o"] <= stop if lado == 1 else k["o"] >= stop
        _fechar(st, k["o"] if gap else stop, i, motivo_stop)                   # gap desfavorável: sai na abertura (a perda pode passar do limite: não se trunca)
    elif bateu_alvo:
        gap = k["o"] >= alvo if lado == 1 else k["o"] <= alvo
        _fechar(st, k["o"] if gap else alvo, i, "alvo")                        # gap além do alvo: sai na abertura


def simular_jogador(candles: list[dict], acoes: list[dict], preco_ref: float, final: bool = False, limite_x: float = LIMITE_PERDA_X) -> dict:
    """Estado de UM jogador na rodada, a partir dos candles que existem (só os revelados, na visão) e das ações dele, na ordem de processamento.
    Uma ação tomada com n_rev = i vale a partir do candle i: a mercado, no fechamento do candle i−1; pendente, só do candle i em diante.
    final=True: fim da rodada (posição aberta sai no último preço e as pendentes expiram sem execução)."""
    n = len(candles)
    st = {"pos": None, "pend": None, "trades": [], "ignoradas": 0, "bloq": False, "limite_x": float(limite_x)}
    por_i: dict[int, list] = {}
    for a in sorted(acoes, key=lambda x: x["ordem"]):
        por_i.setdefault(min(max(int(a["n_rev"]), 0), n), []).append(a)
    px = float(preco_ref)
    for i in range(n + 1):
        for a in por_i.get(i, ()):
            _aplicar(st, a, px, i)
        if i == n:
            break
        _candle(st, candles[i], i)
        px = candles[i]["c"]
    if final:
        if st["pos"]:
            _fechar(st, px, n - 1, "fim")
        st["pend"] = None
    st["preco_atual"] = px
    return st


def _sim_jog(p: dict, jog: str, candles: list[dict], acoes: list[dict], ref: float, final: bool) -> dict:
    """Simulação de um jogador na partida: quantidade livre (corrida) ou aposta fixa (mesa de rodadas)."""
    if qtd_de(p):
        import trader_qtd as TQ
        return TQ.simular(candles, acoes, ref, capital_de(p, jog), final, float(cfg_de(p).get("taxa", TQ.TAXA_B3)))
    return simular_jogador(candles, acoes, ref, final)


def simular_mesa(candles: list[dict], acoes: list[dict], preco_ref: float | None = None, final: bool = False, jogadores: list[str] | None = None) -> dict:
    """Simulador central da mesa. Os jogadores não interferem uns nos outros: cada um tem a própria posição, ordens e resultado.
    Devolve {jogador: estado}. `preco_ref` = último fechamento do histórico (preço visível antes do 1º candle do replay)."""
    ref = float(candles[0]["o"] if preco_ref is None else preco_ref)
    nomes = list(jogadores) if jogadores is not None else sorted({a["jogador"] for a in acoes})
    return {j: simular_jogador(candles, [a for a in acoes if a["jogador"] == j], ref, final) for j in nomes}


# ------------------------------------------------------------------ registro das ações (única porta de entrada)
def _preco_obrig(d: dict, campo: str = "preco") -> float:
    v = _num(d.get(campo))
    if v is None or v <= 0:
        raise ErroTrader("informe um preço válido")
    return v


def _validar_acao(d: dict, sim: dict, px: float, n: int, nr: int) -> dict:
    """Normaliza e valida uma ação contra o estado atual do jogador (e o preço atual = último fechamento revelado). Nada é corrigido."""
    if not isinstance(d, dict):
        raise ErroTrader("ação inválida")
    t, pos, pend = d.get("tipo"), sim["pos"], sim["pend"]
    if t in TIPOS_ENTRADA:
        if sim.get("bloq"):
            raise ErroTrader("limite de perda da rodada atingido (3% do patrimônio): novas entradas bloqueadas até a próxima rodada")
        dirc = d.get("direcao")
        if dirc not in ("alta", "baixa"):
            raise ErroTrader("escolha comprar ou vender")
        if pos:
            raise ErroTrader("você já tem uma posição aberta: encerre-a antes de abrir outra")
        if pend:
            raise ErroTrader("você já tem uma ordem de entrada pendente: cancele-a antes")
        if n >= nr:
            raise ErroTrader("o replay acabou: não dá mais para abrir operação")
        out = {"tipo": t, "direcao": dirc}
        ref = px
        if t != "mercado":
            ref = out["preco"] = _preco_obrig(d)
            if t == "limite":
                ok, msg = (ref < px, "a compra limite precisa ficar abaixo do preço atual") if dirc == "alta" else (ref > px, "a venda limite precisa ficar acima do preço atual")
            else:
                ok, msg = (ref > px, "a compra stop precisa ficar acima do preço atual") if dirc == "alta" else (ref < px, "a venda stop precisa ficar abaixo do preço atual")
            if not ok:
                raise ErroTrader(msg)
        for campo in ("stop", "alvo"):
            if d.get(campo) in (None, ""):
                continue
            v = _preco_obrig(d, campo)
            if not _lado_ok(dirc, campo, v, ref):
                raise ErroTrader(f"o {campo} está do lado errado da entrada" + (" (stop abaixo e alvo acima)" if dirc == "alta" else " (alvo abaixo e stop acima)"))
            out[campo] = v
        return out
    if t in ("definir_stop", "mover_stop", "definir_alvo", "mover_alvo"):
        campo = "stop" if t.endswith("stop") else "alvo"
        o = pos or pend
        if not o:
            raise ErroTrader("você não tem posição nem ordem pendente")
        existe = o.get(campo) is not None
        if t.startswith("definir") and existe:
            raise ErroTrader(f"já existe um {campo}: mova-o em vez de criar outro")
        if t.startswith("mover") and not existe:
            raise ErroTrader(f"não há {campo} para mover")
        pr = _preco_obrig(d)
        if not _lado_ok(o["direcao"], campo, pr, px if pos else o["preco"]):
            raise ErroTrader(f"o {campo} está do lado errado do preço" + (" (stop abaixo e alvo acima)" if o["direcao"] == "alta" else " (alvo abaixo e stop acima)"))
        return {"tipo": t, "preco": pr}
    if t == "cancelar":
        o = d.get("qual")
        if o not in ("entrada", "stop", "alvo", "todas"):
            raise ErroTrader("escolha qual ordem cancelar")
        base = pos or pend or {}
        tem = {"entrada": bool(pend), "stop": base.get("stop") is not None, "alvo": base.get("alvo") is not None}
        if not (any(tem.values()) if o == "todas" else tem[o]):
            raise ErroTrader("não há ordem para cancelar")
        return {"tipo": "cancelar", "qual": o}
    if t == "encerrar":
        if not pos:
            raise ErroTrader("você não tem posição aberta")
        return {"tipo": "encerrar"}
    raise ErroTrader("ação desconhecida")


def acoes_da_rodada(p: dict, r: int, jog: str | None = None) -> list[dict]:
    return [a for a in (p.get("acoes") or []) if a["rodada"] == r and (jog is None or a["jogador"] == jog)]


def registrar_acao(p: dict, cenario: dict, jog: str, dados: dict, agora: float) -> tuple[dict, bool]:
    """Única porta de entrada das ações da mesa. O SERVIDOR decide tudo: fase, pausa, quantos candles estão revelados (pelo relógio dele), preço atual e
    ordem de processamento. Devolve (ação gravada, nova). `aid` repetido (clique duplo, reenvio, reconexão) devolve a ação já gravada, sem novo efeito."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    if motor_de(p) != MOTOR_MESA:
        raise ErroTrader("esta partida usa as regras antigas")
    avancar(p, agora)
    if p["fase"] != "replay":
        raise ErroTrader("só dá para operar durante o replay")
    if pausada(p):
        raise ErroTrader("partida em pausa técnica")
    aid = str((dados or {}).get("aid") or "")[:48]
    if not aid:
        raise ErroTrader("ação sem identificador")
    acoes = p.setdefault("acoes", [])
    for a in acoes:
        if a["jogador"] == jog and a["aid"] == aid:
            return a, False
    r, nr = p["rodada"], _nrp(p)
    minhas = acoes_da_rodada(p, r, jog)
    if len(minhas) >= MAX_ACOES_RODADA:
        raise ErroTrader("limite de ordens da rodada atingido")
    n = n_revelados(p, agora)
    ini = inicio_rodada(cenario, r, nr)
    sim = _sim_jog(p, jog, cenario["candles"][ini:ini + n], minhas, cenario["candles"][ini - 1]["c"], False)
    val = None
    if qtd_de(p):
        import trader_qtd as TQ
        try:
            val = TQ.validar(dados, sim, sim["preco_atual"], n, nr, _preco_obrig)
        except TQ.ErroQtd as e:
            raise ErroTrader(str(e))
    ac = {**(val or _validar_acao(dados, sim, sim["preco_atual"], n, nr)), "aid": aid, "jogador": jog, "rodada": r, "n_rev": n, "ordem": int(p.get("seq_acao", 0)) + 1, "t": float(agora)}
    p["seq_acao"] = ac["ordem"]
    acoes.append(ac)
    p["versao"] += 1
    return ac, True


# ------------------------------------------------------------------ financeiro (patrimônio) e pontuação da rodada
def _stake(p: dict, r: int, jog: str) -> dict | None:
    """Aposta de referência da rodada r: 1% do patrimônio calculado no INÍCIO da rodada, fixa durante ela (cada operação usa este mesmo valor, não é
    recalculada a cada operação). Sem registro da rodada, vale a mais recente anterior, depois a aposta da partida. Sem nenhuma: None."""
    s = p.get("stakes") or {}
    for rr in range(r, 0, -1):
        if _chave(rr, jog) in s:
            return s[_chave(rr, jog)]
    return (p.get("apostas") or {}).get(jog)


def definir_stake(p: dict, jog: str, rodada: int, stake: float, pat: float) -> bool:
    """Grava a aposta da rodada UMA vez (repetir é inofensivo). Devolve True se gravou agora."""
    k = _chave(rodada, jog)
    st = p.setdefault("stakes", {})
    if k in st:
        return False
    st[k] = {"stake": round(float(stake), 2), "pat": round(float(pat), 2)}
    p["versao"] += 1
    return True


def financeiro_mesa(trades: list[dict], ap: dict | None) -> dict | None:
    """Efeito em dinheiro da rodada: soma de TODAS as operações encerradas, cada uma com a mesma aposta de referência (stake × retorno).
    Como as operações se acumulam, a perda da rodada pode ultrapassar 1% do patrimônio (cada operação perde no máximo a aposta, mas há várias).
    Sem aposta, devolve None."""
    if not ap:
        return None
    stake, pat = float(ap["stake"]), float(ap["pat"])
    x = sum(t["ret"] for t in trades)
    pnl = round(stake * x, 2)
    return {"aposta": stake, "pnl": pnl, "pct_aposta": round(x * 100, 3), "pct_pat": round(pnl / pat * 100, 4) if pat > 0 else 0.0, "pat_ini": pat,
            "operou": bool(trades), "n_ops": len(trades), "ops": [{"n": t["n"], "pnl": round(stake * t["ret"], 2), "pct": round(t["ret"] * 100, 3)} for t in trades]}


def _excursao(t: dict, rep: list[dict]) -> float:
    """Qualidade da entrada de UMA operação, de −1 a +1: (ganho máximo a favor − máximo contra) / (soma dos dois), medidos nos candles em que ela esteve aberta."""
    seg = rep[t["i_exc"]:t["i_saida"] + 1]
    if not seg:
        return 0.0
    e = t["entrada"]
    if t["direcao"] == "alta":
        mfe, mae = max(0.0, max(k["h"] for k in seg) / e - 1), max(0.0, 1 - min(k["l"] for k in seg) / e)
    else:
        mfe, mae = max(0.0, 1 - min(k["l"] for k in seg) / e), max(0.0, max(k["h"] for k in seg) / e - 1)
    return 0.0 if mfe + mae <= 0 else (mfe - mae) / (mfe + mae)


def avaliar_mesa(cen_r: dict, est: dict, trades: list[dict]) -> dict:
    """Pontuação da rodada na mesa (determinística e calculada só no servidor), sobre TODAS as operações encerradas.
    x   = soma dos retornos das operações (venda: sinal invertido).
    U   = unidade da rodada = (ATR14 do histórico ÷ preço de referência) × √(candles da rodada): o movimento típico de uma rodada daquele ativo.
    base = PONTOS_MAX × tanh(x / U): lucro → positivo, prejuízo → negativo, zero → 0, cresce com o tamanho do resultado e satura em ±100.
    q (−1 a +1) = média de 4 componentes educacionais, todos determinísticos:
      direção   +1 se a direção declarada na análise = direção real do mercado; −1 se oposta; 0 se uma delas é lateral ou nada foi declarado;
      entrada   média, entre as operações, de (ganho máximo a favor − máximo contra) / (soma dos dois) enquanto a operação esteve aberta;
      risco     2 × (operações que tiveram stop) ÷ (operações) − 1;
      confiança (confiança − 1) ÷ 4 × (sinal da componente direção): confiante e certo ganha, confiante e errado perde, confiança 1 vale 0.
    pontos = base × (1 + 0,25·q) se x > 0, base × (1 − 0,25·q) se x < 0: o fator fica em [0,75; 1,25], então NUNCA muda o sinal (a educação só ajusta o tamanho).
    Sem operação: 0 ponto. Quantidade de operações não pontua: conta só o resultado líquido (os custos da etapa 2 entrarão nele)."""
    real = mercado_real(cen_r)
    rep = cen_r["candles"][cen_r["n_analise"]:]
    x = sum(t["ret"] for t in trades)
    unidade = max((real["atr"] / real["ref"]) * math.sqrt(len(rep)), UNIDADE_MIN) if real["ref"] > 0 else UNIDADE_MIN
    decl, dreal = est.get("direcao"), real["direcao"]
    d = 0.0 if decl is None else (1.0 if decl == dreal else (0.0 if "lateral" in (decl, dreal) else -1.0))
    if not trades:
        return {"motor": MOTOR_MESA, "pontos": 0.0, "real": real, "acertou_direcao": (d > 0) if d else None, "operacao": None, "operacoes": [], "estrategia": est,
                "partes": {"x": 0.0, "unidade": unidade, "base": 0.0, "fator": 1.0, "q": {"direcao": d, "entrada": 0.0, "risco": 0.0, "confianca": 0.0, "total": 0.0}}}
    e = sum(_excursao(t, rep) for t in trades) / len(trades)
    rk = 2.0 * sum(1 for t in trades if t["com_stop"]) / len(trades) - 1.0
    conf = est.get("confianca")
    c = ((conf - 1) / 4.0) * (1 if d > 0 else (-1 if d < 0 else 0)) if conf else 0.0
    q = (d + e + rk + c) / 4.0
    base = PONTOS_MAX * math.tanh(x / unidade)
    fator = 1 + MOD_EDU * q if x > 0 else 1 - MOD_EDU * q
    pts = max(-PONTOS_MAX, min(PONTOS_MAX, base * fator))
    if abs(x) <= EPS_X:
        pts = 0.0
    elif abs(pts) < PONTOS_MIN_SINAL:
        pts = math.copysign(PONTOS_MIN_SINAL, x)
    return {"motor": MOTOR_MESA, "pontos": round(pts, 1), "real": real, "acertou_direcao": (d > 0) if d else None, "operacao": None, "operacoes": [dict(t) for t in trades],
            "estrategia": est, "partes": {"x": x, "unidade": unidade, "base": round(base, 2), "fator": round(fator, 3),
                                          "q": {"direcao": d, "entrada": round(e, 3), "risco": rk, "confianca": round(c, 3), "total": round(q, 3)}}}


PESO_RESULTADO = 0.7            # partida corrida: o lucro pesa mais (70%) e a qualidade da análise/operação completa (30%)


def avaliar_corrida(cen_r: dict, est: dict, trades: list[dict]) -> dict:
    """Pontuação da partida corrida (determinística, só no servidor), de −100 a +100:
      resultado = 100 × tanh(x / U), com x = lucro ÷ capital e U = movimento típico do ativo na partida (o mesmo de avaliar_mesa);
      qualidade = média dos componentes educacionais (direção, entrada, risco, confiança), de −1 a +1;
      pontos    = 70% × resultado + 30% × (qualidade × 100). Sem operação: 0 ponto (a qualidade da leitura ainda vale para o ranking de Qualidade).
    `qualidade_nota` (0 a 100) é o que o ranking de Qualidade usa: 50 = neutro, 100 = tudo certo."""
    base = avaliar_mesa(cen_r, est, trades)
    pt = base["partes"]
    q = pt["q"]
    if trades:                                              # sem confiança (saiu da boleta): direção, entrada e risco
        qual = q["total"] if est.get("confianca") else (q["direcao"] + q["entrada"] + q["risco"]) / 3.0
    else:                                                   # sem operação: só a leitura conta
        qual = (q["direcao"] + q["confianca"]) / 2.0 if est.get("confianca") else q["direcao"] / 2.0
    res = PONTOS_MAX * math.tanh(pt["x"] / pt["unidade"]) if trades else 0.0
    pts = PESO_RESULTADO * res + (1 - PESO_RESULTADO) * qual * PONTOS_MAX if trades else 0.0
    pts = max(-PONTOS_MAX, min(PONTOS_MAX, pts))
    if trades and abs(pt["x"]) > EPS_X and abs(pts) < PONTOS_MIN_SINAL:
        pts = math.copysign(PONTOS_MIN_SINAL, pts or pt["x"])
    base["pontos"] = round(pts, 1)
    base["qualidade_nota"] = round(50 * (qual + 1), 1)
    base["partes"] = {**pt, "res": round(res, 2), "qual": round(qual, 3), "peso_res": PESO_RESULTADO}
    return base


def validar_leitura(est: dict) -> dict:
    """Análise da mesa: a pessoa registra a leitura (direção, tipo e confiança) e os desenhos. Entrada, stop e alvo agora são ordens enviadas no replay."""
    if not isinstance(est, dict):
        raise ErroTrader("estratégia inválida")
    if est.get("direcao") not in DIRECOES:
        raise ErroTrader("escolha a direção esperada")
    if est.get("tipo") not in ESTRATEGIAS:
        raise ErroTrader("escolha a estratégia")
    conf = est.get("confianca")
    if not isinstance(conf, int) or isinstance(conf, bool) or not 1 <= conf <= 5:
        raise ErroTrader("a confiança vai de 1 a 5")
    return {"direcao": est["direcao"], "tipo": est["tipo"], "confianca": conf, "entrada": None, "stop": None, "alvo": None}


def _fechar_rodada_mesa(p: dict, cenario: dict) -> None:
    """Resultado de cada jogador na rodada atual, calculado uma única vez (idempotente): simula a rodada inteira com as ações gravadas, fecha o que ficou
    aberto no último preço, soma TODAS as operações e calcula patrimônio (`fin`) e pontos. Nenhuma operação entra duas vezes."""
    nr, r = _nrp(p), p["rodada"]
    ini = inicio_rodada(cenario, r, nr)
    rep, ref = cenario["candles"][ini:ini + nr], cenario["candles"][ini - 1]["c"]
    cen_r = cenario_em_velas(cenario) if formando(cenario) else cenario_da_rodada(cenario, r, nr)
    novo = False
    for j in p["jogadores"]:
        k = _chave(r, j)
        if k in p["resultados"]:
            continue
        sim = _em_velas(_sim_jog(p, j, rep, acoes_da_rodada(p, r, j), ref, True), cenario)
        res = (avaliar_corrida if qtd_de(p) else avaliar_mesa)(cen_r, p["estrategias"][k], sim["trades"])
        if qtd_de(p):
            import trader_qtd as TQ
            res["fin"] = TQ.financeiro(sim["trades"], _stake(p, r, j))
            res["qtd"] = True
            res["relatorio"] = TQ.relatorio(sim)
        else:
            res["fin"] = financeiro_mesa(sim["trades"], _stake(p, r, j))
        res["limite_atingido"] = bool(sim["bloq"])
        p["resultados"][k] = res
        p["pontos"][j] = round(p["pontos"][j] + res["pontos"], 1)
        novo = True
    if novo:
        p["versao"] += 1
