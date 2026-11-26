"""Setups ao vivo no X1: detecção, pausa sincronizada, janela de decisão e execução (opera sobre o estado `p` da partida; sem banco, sem rede).

Tudo aqui roda DENTRO da transação da partida (trader_online_dados._mutar, com CAS), com o relógio do servidor. O navegador só desenha e manda a decisão.

GARANTIAS
 · Sem sinal retroativo. Só se avalia o candle que ACABOU de fechar no replay (nunca o histórico da análise, nunca o que ainda se forma). Se ninguém
   consultou por um tempo e o candle já "envelheceu" (FRESCOR_S de partida), ele é descartado em silêncio: sinal velho não vira entrada.
 · Sem futuro. Os detectores só recebem candles fechados; o gatilho de um setup armado só olha passos JÁ revelados pelo relógio.
 · Sem duplicidade. O id do sinal leva o candle; um candle de um jogador só gera um sinal. A ordem usa `aid` = id do sinal, e o motor já ignora aid repetido.
 · Pausa do servidor. Reaproveita trader_battle.pausar/retomar: congela a partida para todos de uma vez e o tempo parado não conta em nenhuma fase.
   O motor já recusa ordens durante a pausa. O prazo é do servidor e é aplicado a cada consulta: nenhum navegador mede o próprio cronômetro.
 · Só o dono decide. Quem não ativou o setup nunca consegue aceitar ou recusar.
 · O adversário vê a ativação (nome do setup, sentido e ponto no gráfico), mas não o stop e o alvo, e nunca quem equipou o quê antes de ativar.

ESTADO (`p["setups"]`, JSON puro)
    equip    {jogador: [até 2 ids de setups equipados], congelados quando a partida começa}      varrido  {jogador: candles fechados já avaliados}
    armado   {jogador: {setup: gatilho esperando o preço}}                                    n, ultimo  {jogador: ativações, candle da última}
    regioes  {'rodada|jogador': [regiões de interesse marcadas na estratégia, CONGELADAS no começo do replay]}
    sinais   [{id, jogador, setup, direcao, candle, preco, stop, alvo, motivo, regiao, t, estado, ...}]       evento  {sinal, t_ini, prazo} | None
"""
from __future__ import annotations

import bisect
import copy
import math

import setups as SU
import trader_battle as TB

ANIM_S = 4.0         # a animação da mira (detecção, aquisição, travamento, ativação)
DESTAQUE_S = 5.0     # só nos padrões de candle: depois da mira, o gráfico apaga e destaca os candles do padrão para o jogador memorizar (4 a 6 s)
JANELA_S = 19.0      # a janela de decisão que se abre depois da animação (a partida fica pausada para os dois nesse tempo)
FRESCOR_S = 3.0      # um candle (ou um passo) só gera sinal se acabou de acontecer: segundos de partida, sem contar pausas
RECARGA = 8          # candles entre duas ativações do mesmo jogador
TETO = 2             # ativações por jogador, por partida
RESTANTES = 3        # sem ativar nos últimos candles: não sobra tempo para a ordem executar
ESTADOS_FINAIS = ("aceito", "recusado", "expirado")


# ------------------------------------------------------------------ começo da partida
def iniciar(jogadores: list[str], equipados: dict) -> dict:
    """Congela os setups equipados (até 2) de cada jogador no começo da partida. `equipados` já vem validado (só as cartas que a pessoa tem)."""
    return {"v": 1, "equip": {j: list(equipados.get(j) or []) for j in jogadores}, "varrido": {}, "armado": {}, "n": {}, "ultimo": {}, "sinais": [], "evento": None, "regioes": {}}


# ------------------------------------------------------------------ relógio e candles do replay
def _passos_ate(cen: dict, m: int) -> int:
    """Quantos passos do replay compõem os `m` primeiros candles do gráfico."""
    g = cen.get("grupo")
    return m if not g else bisect.bisect_left(g, m)


def _fechados(cen: dict, n: int) -> int:
    """Quantos candles do replay estão FECHADOS quando `n` passos já foram revelados (o último pode estar se formando)."""
    g = cen.get("grupo")
    if not g:
        return n
    if n <= 0:
        return 0
    ult = g[n - 1]
    return ult + 1 if (n >= len(g) or g[n] != ult) else ult


def _dt(p: dict) -> float:
    cfg = TB.cfg_de(p)
    return float(cfg["t_replay_s"]) / max(1, int(cfg["n_replay"]))


def _lote(p: dict, cen: dict, jog: str, ini: int) -> int:
    return TB.lote_de(p, jog, cen["candles"][ini - 1]["c"])


# ------------------------------------------------------------------ sinais e evento
def _sinal(p: dict, s: dict, jog: str, sid: str, candle: int, sig: dict, preco: float, agora: float) -> dict | None:
    n_jog = p["jogadores"].index(jog) + 1
    id_ = f"{p['id']}:{n_jog}:{candle}"
    if any(x["id"] == id_ for x in s["sinais"]):
        return None
    n_pad = (SU.PADROES.get(sid) or {}).get("n")                      # padrão de candle: quais candles o formam (a lição destaca e amplia estes)
    pad = {"candles": list(range(candle - n_pad + 1, candle + 1))} if n_pad else None
    return {"id": id_, "jogador": jog, "setup": sid, "direcao": sig["direcao"], "candle": candle, "preco": round(float(preco), 4), "padrao": pad,
            "stop": sig.get("stop"), "alvo": sig.get("alvo"), "motivo": sig.get("motivo", ""), "regiao": sig.get("regiao"),
            "t": float(agora), "estado": "aberto"}


def _destaque(sinal: dict) -> float:
    return DESTAQUE_S if sinal.get("padrao") else 0.0


def _disparar(p: dict, cen: dict, s: dict, sinal: dict, agora: float) -> bool:
    """Registra o sinal, pausa a partida para os dois e abre a janela. False se não deu para pausar (nada é registrado)."""
    if not TB.pausar(p, agora, {cen["id"]: cen}):
        return False
    jog = sinal["jogador"]
    s["sinais"].append(sinal)
    s["n"][jog] = s["n"].get(jog, 0) + 1
    s["ultimo"][jog] = sinal["candle"]
    s["armado"].pop(jog, None)
    s["evento"] = {"sinal": sinal["id"], "t_ini": float(agora), "prazo": float(agora) + ANIM_S + _destaque(sinal) + JANELA_S}
    p["versao"] += 1
    return True


def _posicionado(p: dict, cen: dict, jog: str, ini: int, n: int) -> str | None:
    """'aberta' se o jogador tem posição aberta, 'pendente' se tem uma ordem de entrada esperando; None se está livre. Usa o simulador da partida."""
    acoes = TB.acoes_da_rodada(p, p["rodada"], jog)
    if not acoes:
        return None
    sim = TB._sim_jog(p, jog, cen["candles"][ini:ini + n], acoes, cen["candles"][ini - 1]["c"], False)
    if sim.get("pos"):
        return "aberta"
    return "pendente" if sim.get("pend") else None


def _tentar(p: dict, cen: dict, s: dict, sinal: dict, ini: int, n: int, agora: float) -> bool:
    """Regra para um setup que ativa com o jogador JÁ posicionado (posição aberta ou entrada pendente): o jogo não pausa nem abre a janela, porque uma
    segunda ordem mexeria na posição e no stop/alvo que ele está acompanhando. O sinal fica registrado como 'ignorado' (não gasta o teto de ativações) e o
    jogador recebe um aviso. Livre: abre a janela normalmente. True se abriu a janela."""
    estado = _posicionado(p, cen, sinal["jogador"], ini, n)
    if estado is None:
        return _disparar(p, cen, s, sinal, agora)
    sinal["estado"] = "ignorado"
    sinal["motivo_ignorado"] = "posição aberta" if estado == "aberta" else "entrada pendente"
    s["sinais"].append(sinal)
    s["ultimo"][sinal["jogador"]] = sinal["candle"]                    # a recarga continua valendo: sem aviso repetido a cada candle
    s["armado"].pop(sinal["jogador"], None)
    p["versao"] += 1
    return False


def _resolver(p: dict, s: dict, sinal_id: str, estado: str, agora: float) -> None:
    sinal = next(x for x in s["sinais"] if x["id"] == sinal_id)
    sinal["estado"], sinal["t_dec"] = estado, float(agora)
    s["evento"] = None
    TB.retomar(p, agora)
    p["versao"] += 1


# ------------------------------------------------------------------ o que roda a cada consulta
def processar(p: dict, cen: dict, agora: float) -> bool:
    """Aplica o prazo do evento em curso e procura sinais novos. Chamar de novo é inofensivo. Devolve True se algo mudou."""
    s = p.get("setups")
    if not s or p["fase"] != "replay":
        return False
    ev = s["evento"]
    if ev:
        if agora >= ev["prazo"]:
            _resolver(p, s, ev["sinal"], "expirado", agora)          # sem resposta no prazo = recusa
            return True
        return False                                                 # evento em curso: nada novo enquanto a partida está parada
    if TB.pausada(p):
        return False
    cfg = TB.cfg_de(p)
    nr = int(cfg["n_replay"])
    ini = TB.inicio_rodada(cen, p["rodada"], nr)
    n = TB.n_revelados(p, agora)
    m = _fechados(cen, n)                                            # candles do replay já fechados
    total = int(cfg.get("n_velas") or nr)
    dec, dt, g = TB._decorrido(p, agora), _dt(p), cen.get("grupo")
    mudou = False
    for jog in p["jogadores"]:
        ids = _equipados(s, jog)
        if not ids or s["n"].get(jog, 0) >= TETO:
            continue
        if any(sid in SU.PADROES for sid in ids):             # cartas de padrão: congela já as regiões marcadas (não espera o 1º candle fechar)
            _regioes(p, s, cen, jog, ini)
        armados = s["armado"].get(jog) or {}
        if "gatilho" in armados:                                     # estado de antes dos 2 espaços: descarta
            armados = {}
        for sid in ids:
            arm = armados.get(sid)
            if not arm:
                continue
            ga = arm["candle"] - ini                                 # 1) um gatilho armado esperando o preço
            a, b = _passos_ate(cen, ga + 1), _passos_ate(cen, ga + 1 + arm["validade"])
            k = next((k for k in range(a, min(b, n)) if _rompeu(arm, cen["candles"][ini + k])), None)
            if k is not None:
                armados.pop(sid, None)
                mudou = True
                idade = dec - (k + 1) * dt
                candle = ini + (g[k] if g else k)
                if idade <= FRESCOR_S and total - (candle - ini + 1) >= RESTANTES and candle - s["ultimo"].get(jog, -999) >= RECARGA:
                    sinal = _sinal(p, s, jog, sid, candle, arm, arm["gatilho"], agora)
                    if sinal and _tentar(p, cen, s, sinal, ini, n, agora):
                        return True                                  # um evento por vez: o resto espera a janela fechar
            elif n >= b:
                armados.pop(sid, None)                               # a validade acabou sem o preço chegar
                mudou = True
        if m > s["varrido"].get(jog, 0):                             # 2) o candle que acabou de fechar, para cada setup equipado
            s["varrido"][jog] = m
            mudou = True
            if m < 1 or dec - _passos_ate(cen, m) * dt > FRESCOR_S or total - m < RESTANTES:
                continue                                             # histórico, velho demais ou sem tempo de operar: nunca é sinal
            fechados = cen["candles"][:ini] + TB.velas_replay(cen, ini, _passos_ate(cen, m))
            candle = ini + m - 1
            for sid in ids:
                sig = SU.detectar(sid, fechados, _regioes(p, s, cen, jog, ini)) if sid in SU.PADROES else SU.detectar(sid, fechados)
                if not sig:
                    continue
                if "gatilho" in sig:                                 # setup armado: só prepara; quem dispara é o preço, nos candles seguintes
                    armados[sid] = {**sig, "candle": candle}
                    s["armado"][jog] = armados
                elif candle - s["ultimo"].get(jog, -999) >= RECARGA:
                    sinal = _sinal(p, s, jog, sid, candle, sig, fechados[-1]["c"], agora)
                    if sinal and _tentar(p, cen, s, sinal, ini, n, agora):
                        return True
    if mudou:
        p["versao"] += 1
    return mudou


def _regioes(p: dict, s: dict, cen: dict, jog: str, ini: int) -> list[dict]:
    """As regiões de interesse do jogador nesta rodada, congeladas na primeira vez que o replay precisa delas. Vêm da estratégia (travada: o servidor
    recusa desenho depois que a análise acaba), então nada que o jogador marque depois do início da partida entra aqui."""
    chave = f"{p['rodada']}|{jog}"
    cong = s.setdefault("regioes", {})
    if chave not in cong:
        est = p["estrategias"].get(TB._chave(p["rodada"], jog)) or {}
        analise = cen["candles"][:ini]
        ref = analise[-1]["c"] if analise else 0.0
        cong[chave] = SU.regioes_das_marcas(est.get("marcas"), SU._atr(analise, 14), ref, p["id"], p["jogadores"].index(jog) + 1, p["rodada"],
                                            est.get("salva_em") or p.get("t_fase") or 0.0)
        p["versao"] += 1
    return cong[chave]


def _equipados(s: dict, jog: str) -> list:
    e = s["equip"].get(jog)
    return [e] if isinstance(e, str) else list(e or [])


def _rompeu(arm: dict, x: dict) -> bool:
    return x["h"] > arm["gatilho"] if arm["direcao"] == "alta" else x["l"] < arm["gatilho"]


# ------------------------------------------------------------------ a decisão do dono
def decidir(p: dict, cen: dict, jog: str, aceitar: bool, q, agora: float) -> dict:
    """Aceita ou recusa o sinal em curso. Só o dono, só dentro do prazo (relógio do servidor). Aceitar manda uma ordem a mercado pelo sistema atual
    (quantidade e limites validados por ele; stop e alvo do setup vão junto se o motor os aceitar). Devolve {'resultado': ...}."""
    s = p.get("setups")
    if not s or jog not in p["jogadores"]:
        raise TB.ErroTrader("esta partida não tem setups")
    ev = s["evento"]
    if ev and agora >= ev["prazo"]:
        _resolver(p, s, ev["sinal"], "expirado", agora)
        return {"resultado": "expirado"}
    if not ev:
        raise TB.ErroTrader("não há setup esperando decisão")
    sinal = next(x for x in s["sinais"] if x["id"] == ev["sinal"])
    if sinal["jogador"] != jog:
        raise TB.ErroTrader("só quem ativou o setup pode decidir")
    if not aceitar:
        _resolver(p, s, sinal["id"], "recusado", agora)
        return {"resultado": "recusado"}
    pausas, versao = copy.deepcopy(p.get("pausas")), p["versao"]    # se a ordem for recusada a pausa volta como estava: a janela segue aberta
    TB.retomar(p, agora)                                             # o motor só aceita ordem com a partida rodando
    ini = TB.inicio_rodada(cen, p["rodada"], int(TB.cfg_de(p)["n_replay"]))
    try:
        qtd = int(q) if isinstance(q, (int, float)) and not isinstance(q, bool) and math.isfinite(q) and q >= 1 else _lote(p, cen, jog, ini)
    except (TypeError, ValueError, OverflowError):
        qtd = _lote(p, cen, jog, ini)
    aid = f"setup:{sinal['id']}"[:48]
    base = {"aid": aid, "tipo": "mercado", "direcao": sinal["direcao"], "q": qtd}
    protecao = {k: sinal[k] for k in ("stop", "alvo") if sinal.get(k) is not None}
    try:
        try:
            acao, _nova = TB.registrar_acao(p, cen, jog, {**base, **protecao}, agora)
        except TB.ErroTrader as e:
            if not protecao or not any(w in str(e) for w in ("stop", "alvo")):
                raise
            acao, _nova = TB.registrar_acao(p, cen, jog, base, agora)    # o preço já passou do stop ou do alvo: entra sem a proteção em vez de perder a entrada
            protecao = {}
    except TB.ErroTrader:
        p["pausas"], p["versao"] = pausas, versao
        raise
    acao["sinal"] = sinal["id"]
    sinal["aid"], sinal["q"], sinal["protegido"] = aid, qtd, bool(protecao)
    _resolver(p, s, sinal["id"], "aceito", agora)
    return {"resultado": "aceito", "aid": aid}


# ------------------------------------------------------------------ o que cada jogador pode ver
def visao(p: dict, email: str, agora: float) -> dict | None:
    """Evento em curso e marcas dos sinais ATIVADOS, do ponto de vista de `email`. Nunca expõe o setup equipado de ninguém antes de ele ativar,
    nem o stop e o alvo para quem não é o dono."""
    s = p.get("setups")
    if not s:
        return None
    rot = {j: (None if j == email else f"Jogador {i}") for i, j in enumerate(p["jogadores"], 1)}
    marcas = [{"id": x["id"], "candle": x["candle"], "preco": x["preco"], "direcao": x["direcao"], "setup": x["setup"], "estado": x["estado"],
               "meu": x["jogador"] == email,
               **({"stop": x["stop"], "alvo": x["alvo"], "protegido": x.get("protegido")} if x["jogador"] == email else {})} for x in s["sinais"] if x["estado"] != "ignorado"]
    avisos = [{"id": x["id"], "texto": f"{(SU.info(x['setup']) or {}).get('nome', 'Setup')} sinalizou {'COMPRA' if x['direcao'] == 'alta' else 'VENDA'}, mas você já tem "
                                       + ("uma posição aberta" if x.get("motivo_ignorado") == "posição aberta" else "uma entrada pendente") + ": o sinal foi ignorado."}
              for x in s["sinais"] if x["estado"] == "ignorado" and x["jogador"] == email]
    ev, out = s["evento"], None
    if ev:
        x = next(x for x in s["sinais"] if x["id"] == ev["sinal"])
        info = SU.info(x["setup"]) or {}
        dono = x["jogador"] == email
        out = {"sinal": x["id"], "setup": {"id": x["setup"], "nome": info.get("nome"), "raridade": info.get("raridade"), "cores": info.get("cores"),
                                           "assets": info.get("assets"), "provisorio": info.get("provisorio"), "resumo": info.get("resumo"), "saida": info.get("saida")},
               "dono": "Você" if dono else rot[x["jogador"]], "voce_e_dono": dono, "direcao": x["direcao"], "candle": x["candle"], "preco": x["preco"],
               "stop": x["stop"] if dono else None, "alvo": x["alvo"] if dono else None, "motivo": x["motivo"] if dono else "",
               "padrao": ({"candles": x["padrao"]["candles"], "licao": (SU.PADROES.get(x["setup"]) or {}).get("licao")} if x.get("padrao") else None),   # a lição é para os dois: o que o adversário não vê é a região, o stop e o alvo
               "regiao": x.get("regiao") if dono else None,                  # a região que o jogador marcou: o adversário não vê onde estão as marcas dele
               "anim_ms": int(ANIM_S * 1000), "destaque_ms": int(_destaque(x) * 1000), "janela_ms": int(JANELA_S * 1000),
               "decorrido_ms": max(0, int((agora - ev["t_ini"]) * 1000)), "restante_ms": max(0, int((ev["prazo"] - agora) * 1000)),
               "pode_decidir": bool(dono and agora < ev["prazo"])}
    return {"evento": out, "marcas": marcas, "avisos": avisos}
