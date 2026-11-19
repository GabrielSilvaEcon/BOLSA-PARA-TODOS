"""Servidor do jogo (etapa 1 do plano de migração): o motor atual do TickerHunters exposto como API para o app novo (Flutter).

Nada de regra nova aqui: cada rota só chama os módulos puros que o app em Streamlit já usa (contas, banco, trader_battle, trader_qtd,
trader_dados, trader_carteira, trader_online_dados, jogos, perfis) e devolve JSON. Mesmo banco (Supabase), mesmas contas, mesmos testes.

Login: o app novo entra pelo Supabase Auth (e-mail ou Google, pelo plugin do Flutter) e manda o token dele em toda chamada,
`Authorization: Bearer <token>`. O servidor confirma o token com o próprio Supabase e liga o e-mail à conta do jogo (criada na 1ª vez).
Também aceita o token de sessão do app atual (`POST /auth/entrar`, e-mail e senha), enquanto os dois apps existem.

Rodar localmente:  uvicorn api.main:app --reload      ·  documentação interativa em /docs
Ainda não está aqui (próximas partes da etapa 1): login com Google, XP da partida (fica no progresso de estudo) e as telas de Aprender/Analisar.
"""
from __future__ import annotations

import os
import random
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import banco
import contas
import educacao as ED
import jogos as J
import jornada as JO
import nivel as NV
import passe as PA
import tickercoins as TC
import trader_battle as TB
import trader_carteira as TCA
import trader_dados as TD
import trader_grafico as TG
import trader_online_dados as OL

app = FastAPI(title="TickerHunters · servidor do jogo", version="0.1.0")
ORIGENS = [o.strip() for o in os.environ.get("BPT_API_ORIGENS", "*").split(",") if o.strip()]   # link de teste do app (GitHub Pages) etc.
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS, allow_methods=["*"], allow_headers=["*"])

CHAVE_SOLO = "tb_api|{h}|{pid}"          # partida solo guardada no banco (no Streamlit ela ficava só na sessão do navegador)


def _agora() -> float:
    return time.time()


# ------------------------------------------------------------------ quem está chamando
class Quem(BaseModel):
    conta: dict
    email: str
    token: str

    @property
    def ator(self) -> banco.Ator:
        return contas.ator_de(self.conta)


_CACHE_AUTH: dict[str, tuple[float, dict | None]] = {}
CACHE_AUTH_S = 60                       # o token do Supabase é conferido no máximo 1 vez por minuto (o app chama o servidor o tempo todo)


def _usuario_supabase(tok: str) -> dict | None:
    """Usuário do Supabase Auth dono deste token (o próprio Supabase confirma: token falso ou vencido = None)."""
    sb = banco._supabase()
    if not sb:
        return None
    import requests
    url, key = sb
    try:
        r = requests.get(f"{url}/auth/v1/user", headers={"apikey": key, "Authorization": f"Bearer {tok}"}, timeout=8)
    except Exception:
        return None
    return r.json() if r.status_code == 200 else None


def _conta_do_token(tok: str) -> dict | None:
    if tok.count(".") != 2:                                         # token de sessão do app atual (e-mail e senha)
        return contas.validar_sessao(tok)
    c = _CACHE_AUTH.get(tok)
    if c and time.time() - c[0] < CACHE_AUTH_S:
        return c[1]
    u = _usuario_supabase(tok)
    conta = None
    if u and u.get("email") and (u.get("email_confirmed_at") or u.get("confirmed_at")):       # só e-mail confirmado entra no jogo
        meta = u.get("user_metadata") or {}
        r = contas.login_google(u["email"], meta.get("full_name") or meta.get("name") or "")  # cria ou reativa a conta do jogo
        conta = r.dado if r.ok else None
    if len(_CACHE_AUTH) > 5000:
        _CACHE_AUTH.clear()
    _CACHE_AUTH[tok] = (time.time(), conta)
    return conta


def quem(authorization: str = Header(default="")) -> Quem:
    tok = authorization.removeprefix("Bearer ").strip()
    conta = _conta_do_token(tok) if tok else None
    if not conta:
        raise HTTPException(401, "Sessão inválida ou expirada: entre de novo.")
    return Quem(conta={k: v for k, v in conta.items() if k != "senha_hash"}, email=conta["email"], token=tok)


def _erro(e: Exception, status: int = 400):
    raise HTTPException(status, str(e) or e.__class__.__name__)


# ------------------------------------------------------------------ básico
@app.get("/saude")
def saude() -> dict:
    ok, msg = banco.pronto()
    return {"ok": True, "banco": bool(ok), "detalhe": msg if not ok else ""}


class Entrar(BaseModel):
    email: str
    senha: str
    lembrar: bool = True


@app.post("/auth/entrar")
def entrar(d: Entrar) -> dict:
    r = contas.entrar(d.email, d.senha, cliente="app", lembrar=d.lembrar)
    if not r.ok:
        raise HTTPException(401, r.msg)
    c = r.dado["conta"]
    return {"token": r.dado["token"], "conta": {"id": c.get("id"), "email": c.get("email"), "nome": c.get("nome")}}


@app.post("/auth/sair")
def sair(q: Quem = Depends(quem)) -> dict:
    contas.encerrar_sessao(q.token, q.conta.get("id"))
    return {"ok": True}


def _ranking_da_casa(a, email: str) -> dict:
    """Posição da pessoa no ranking geral, com as mesmas regras da Home do Streamlit (ranking oficial ou parcial do dia).
    Só lê o banco; nunca derruba a Home (em caso de erro devolve posição vazia)."""
    vazio = {"pos": None, "total": None, "rotulo": None, "participa": False}
    try:
        import competicao as C
        import home_dados as HD
        import ranking_parcial as RP
        perfil = C.sanear_perfil(banco.comp_ordens_ler(a))
        cart = banco.comp_carteira_ler(a) or {}
        est = cart if cart.get("v") == 1 else None
        rk = banco.comp_publico_ler("comp_ranking") or {}
        participa = bool(perfil.get("aceite"))
        apelido = str(perfil.get("apelido") or "")
        listas, rotulo = RP.escolher(rk)
        geral = listas.get("geral") or []
        mr = (est or {}).get("rank") or {}
        n = mr.get("n")
        total = listas.get("geral_n") if rotulo else ((n.get("geral") if isinstance(n, dict) else n) or listas.get("geral_n"))
        if rotulo:
            r = HD.ranking_resumo(geral, total, None, apelido if participa else None, None, dia=rk.get("dia"), parcial=rotulo)
        else:
            r = HD.ranking_resumo(geral, total, mr.get("geral"), apelido if participa else None, None, dia=rk.get("dia"))
        eu = r.get("eu") or {}
        return {"pos": eu.get("pos"), "total": r.get("total"), "rotulo": rotulo, "participa": participa}
    except Exception as e:
        banco.registrar_erro("api.ranking_da_casa", e)
        return vazio


@app.get("/eu")
def eu(q: Quem = Depends(quem)) -> dict:
    """O que o cabeçalho e a Home mostram: conta, perfil de jogador, carteira (caixa e patrimônio) e o placar dos jogos."""
    a = q.ator
    try:
        perfil = banco.perfil_jogador_ler(a) or {}
    except Exception:
        perfil = {}
    try:
        cart = TCA.situacao(q.email)
    except Exception:
        cart = None
    try:
        placar = J.estatisticas(J.sanear(banco.jogos_placar_ler(a)))
    except Exception:
        placar = None
    # progresso de estudo (XP, nível, passe) e Ticker Coins: as mesmas regras do app atual, lidas do banco
    try:
        dados = banco.ler_dados(a, q.email) or {}
        prog = ED.normalizar(dados.get("edu_progresso"))
        xp = int(JO.resumo(prog)["xp"])
        nivel = NV.estado(xp)
    except Exception:
        prog, xp, nivel = None, None, None
    try:
        moedas = TC.saldo(q.conta.get("id"))
    except Exception:
        moedas = None
    try:
        from datetime import datetime, timedelta, timezone
        hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).date()          # horário de Brasília
        passe = PA.estado(JO._jor(prog)["xp_dia"], hoje) if prog is not None else None
    except Exception:
        passe = None
    ranking = _ranking_da_casa(a, q.email)
    return {"conta": {"id": q.conta.get("id"), "email": q.email, "nome": q.conta.get("nome")},
            "perfil": {k: perfil.get(k) for k in ("nome", "usuario", "avatar", "bio") if k in perfil}, "carteira": cart, "placar": placar,
            "xp": xp, "nivel": nivel, "moedas": moedas, "passe": passe, "ranking": ranking,
            "avatar_img": _avatar_img(perfil.get("avatar")), "alertas": _alertas_nao_lidos(a)}


def _alertas_nao_lidos(a):
    """Quantos alertas ainda não lidos (o número do sino). None se o banco não responder."""
    try:
        return banco.notif_contar(a, lida=False)
    except Exception:
        return None


def _avatar_img(avatar) -> str:
    """Imagem do avatar equipado: caminho do arquivo do app ('avatares/x.webp') ou data URI (avatares feitos em código). Padrão se faltar."""
    try:
        import avatares as AV
        u = AV.url(str(avatar or ""), True)
        if u.startswith("app/static/avatares/"):
            return "avatares/" + u.split("app/static/avatares/", 1)[1]
        return u
    except Exception:
        return ""


# ------------------------------------------------------------------ carteira (posições por ativo)
@app.get("/carteira")
def carteira(q: Quem = Depends(quem)) -> dict:
    """Carteira da pessoa: a da competição (depois de começar) ou a do jogo (antes). Mesma regra da tela do Streamlit."""
    import ativos_jogo as A
    import carteira_unica as CU
    import competicao as C
    import wallet_game as WG
    try:
        perfil = C.sanear_perfil(banco.comp_ordens_ler(q.ator))
    except Exception:
        perfil = {}
    try:
        if perfil.get("aceite"):
            cart = banco.comp_carteira_ler(q.ator) or {}
            est = cart if cart.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora_brt().date().isoformat())
        else:
            est = WG.sincronizar(q.email)
    except Exception as e:
        _erro(e)
    r = CU.resumo(est)
    posicoes = [{"id": x["id"], "nome": A.rotulo(x["id"]), "classe": x.get("classe"), "qtd": x["qtd"], "pm": x["pm"],
                 "preco": x["preco"], "valor": x["valor"], "pct": x["pct"], "lucro_nao_realizado": x["lucro_nao_realizado"],
                "logo": _logo_ativo(x["id"])}
                for x in r["posicoes"]]
    return {"disponivel": r["disponivel"], "investido": r["investido"], "valor_atual": r["valor_atual"],
            "nao_realizado": r["nao_realizado"], "patrimonio": r["patrimonio"], "posicoes": posicoes,
            "rent_nao_realizada": r["rent_nao_realizada"], "comecou": bool(perfil.get("aceite")), "apelido": perfil.get("apelido") or "",
            "ranking": _ranking_da_casa(q.ator, q.email).get("pos"), "moedas": _moedas_seguro(q),
            "serie": _serie_patrimonio(est), "var_dia": _var_dia(est), "missao": _missao_ativa_seguro(q)}


def _logo_ativo(tk: str):
    """Logo do ativo na pasta de logos do app: 'setores/x.webp' (ação) ou 'cripto/x.webp'. None se não houver."""
    try:
        import setores as SE
        u = SE.icone_ativo(tk)
        return u.split("app/static/", 1)[1] if u and "app/static/" in u else None
    except Exception:
        return None


def _serie_patrimonio(est: dict) -> list[dict]:
    """Patrimônio de cada fechamento (sem aportes) + o de agora. Mesma conta do gráfico do Streamlit."""
    import competicao as C
    try:
        pat_liq = C.patrimonio(est) - C.aportes(est)
        pts = []
        for x in est.get("hist") or []:
            try:
                pts.append({"d": str(x["d"])[:10], "v": round(float(C._liq(x)), 2)})
            except Exception:
                continue
        if pts:
            pts.append({"d": _agora_brt().date().isoformat(), "v": round(float(pat_liq), 2)})
        return pts[-90:]
    except Exception:
        return []


def _var_dia(est: dict):
    """Variação % desde o último fechamento (o mesmo critério do cartão do Streamlit)."""
    s = _serie_patrimonio(est)
    if len(s) < 2 or not s[-2]["v"] or s[-2]["v"] <= 0:
        return None
    return round((s[-1]["v"] / s[-2]["v"] - 1) * 100, 2)


def _missao_ativa_seguro(q: "Quem"):
    """Primeira missão ainda não feita (diária, semanal ou especial), como no Streamlit. Sem efeito colateral de XP aqui."""
    try:
        import wallet_game as W
        res = W.avaliar(q.email, q.conta.get("id"), registrar_visita=False)
    except Exception:
        return None
    ms = res.get("missoes") or []
    for per in ("dia", "semana", "especial"):
        for m in ms:
            if m.get("periodo") == per and not m.get("feita"):
                return {"nome": m.get("nome"), "progresso": m.get("progresso") or 0, "meta": m.get("meta") or 1,
                        "recompensa": m.get("recompensa") or {}}
    return None


def _moedas_seguro(q: "Quem"):
    try:
        return TC.saldo(q.conta.get("id"))
    except Exception:
        return None


class ComecarIn(BaseModel):
    apelido: str
    aceito: bool = False


class OrdemIn(BaseModel):
    ativo: str
    qtd: float
    lado: str = "C"                     # "C" compra · "V" venda


def _agora_brt():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)


@app.post("/carteira/comecar")
def carteira_comecar(body: ComecarIn, q: Quem = Depends(quem)) -> dict:
    """Entra na competição da carteira: escolhe o apelido público e confirma o regulamento (mesma regra do app antigo)."""
    import competicao as C
    a = q.ator
    perfil = C.sanear_perfil(banco.comp_ordens_ler(a))
    if perfil.get("aceite"):
        return {"ok": True, "apelido": perfil.get("apelido") or ""}
    if not body.aceito:
        raise HTTPException(400, "Marque a confirmação para participar.")
    ok, msg = C.apelido_valido(body.apelido)
    if not ok:
        raise HTTPException(400, msg)
    if not banco.comp_apelido_livre(a, C.chave_apelido(body.apelido)):
        raise HTTPException(400, "Esse apelido já está em uso. Escolha outro.")
    novo = {"apelido": body.apelido.strip(), "aceite": True, "entrada": _agora_brt().date().isoformat(), "drip": False, "pend": []}
    banco.comp_ordens_gravar(a, C.sanear_perfil(novo))
    return {"ok": True, "apelido": novo["apelido"]}


@app.get("/carteira/preco")
def carteira_preco(ativo: str, q: Quem = Depends(quem)) -> dict:
    """Cotação atual de um ativo (B3, EUA e cripto). Fundos e Tesouro ainda não têm preço ao vivo aqui."""
    import ativos_jogo as A
    import cotacoes_jogo as CJ
    tk = ativo.upper().strip()
    if not A.valido(tk):
        raise HTTPException(400, "Ativo não encontrado no jogo.")
    px = CJ.preco_agora(tk)
    if not px:
        raise HTTPException(400, "Sem cotação ao vivo para esse ativo agora.")
    return {"ativo": tk, "rotulo": A.rotulo(tk), "px": px}


@app.post("/carteira/ordem")
def carteira_ordem(body: OrdemIn, q: Quem = Depends(quem)) -> dict:
    """Compra ou venda na hora, ao preço atual. Mesmas regras do motor do jogo (caixa, limite de concentração e limite diário)."""
    import ativos_jogo as A
    import competicao as C
    import cotacoes_jogo as CJ
    import planos as PL
    a = q.ator
    perfil = C.sanear_perfil(banco.comp_ordens_ler(a))
    if not perfil.get("aceite"):
        raise HTTPException(400, "Comece a sua carteira primeiro.")
    lado = {"C": "C", "COMPRAR": "C", "V": "V", "VENDER": "V"}.get(str(body.lado or "").upper().strip())
    if not lado:
        raise HTTPException(400, "Escolha compra ou venda.")
    tk = body.ativo.upper().strip()
    if not A.valido(tk):
        raise HTTPException(400, "Ativo não encontrado no jogo.")
    qtd = A.norm_qtd(tk, body.qtd)
    if not A.qtd_valida(tk, qtd):
        raise HTTPException(400, f"Quantidade inválida para {A.rotulo(tk)}. Esse tipo de ativo aceita múltiplos de {A.texto_qtd(tk, A.passo(tk))}.")
    liberado, info = PL.usar("comp_ordens_dia", email=q.email, papel=None)
    if not liberado:
        raise HTTPException(429, (info or {}).get("mensagem") or "Limite diário de ordens atingido.")
    px = CJ.preco_agora(tk)
    if not px:
        raise HTTPException(400, "Sem cotação ao vivo para esse ativo agora. Tente de novo em instantes.")
    agora = _agora_brt()
    atual = banco.comp_carteira_ler(a) or {}
    base = atual if atual.get("v") == 1 else C.novo_estado(perfil.get("entrada") or agora.date().isoformat())
    ok, msg, novo = C.executar_agora(base, perfil.get("pend") or [], lado, tk, qtd, px, agora)
    if not ok:
        raise HTTPException(400, msg)
    banco.comp_carteira_gravar(a, novo)
    verbo = "Compra" if lado == "C" else "Venda"
    return {"ok": True, "msg": f"{verbo} executada: {A.texto_qtd(tk, qtd)} × {A.rotulo(tk)} a R$ {px:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."),
            "px": px, "caixa": float(novo.get("caixa", 0))}


# ------------------------------------------------------------------ alertas (o sino do cabeçalho)
class LidasIn(BaseModel):
    ids: list[str] = []


@app.get("/alertas")
def alertas(q: Quem = Depends(quem)) -> dict:
    """Últimos alertas da pessoa (os mesmos da tela Alertas do app antigo), do mais novo para o mais antigo."""
    try:
        itens = banco.notif_listar(q.ator, limite=50)
    except Exception as e:
        _erro(e)
    return {"itens": [{"id": n.get("id"), "titulo": n.get("titulo") or "", "texto": n.get("texto") or "", "quando": str(n.get("quando") or ""),
                       "lida": bool(n.get("lida")), "importancia": n.get("importancia") or "", "ativo": n.get("ativo") or ""} for n in itens]}


@app.post("/alertas/lidas")
def alertas_lidas(body: LidasIn, q: Quem = Depends(quem)) -> dict:
    """Marca os alertas como lidos (zera o número do sino para eles)."""
    try:
        n = banco.notif_marcar(q.ator, body.ids, True) if body.ids else 0
    except Exception as e:
        _erro(e)
    return {"ok": True, "marcados": n}


# ------------------------------------------------------------------ Central de Jogos (o que o "Jogar agora" abre)
@app.get("/jogos/central")
def jogos_central(q: Quem = Depends(quem)) -> dict:
    """Números da Central de Jogos, com as mesmas regras do app antigo (jogos_app.pagina_central):
    vitórias e partidas (placar dos dois jogos), melhor posição nos rankings, sequência de estudo e o desafio da semana."""
    a = q.ator
    try:
        es = J.estatisticas(J.sanear(banco.jogos_placar_ler(a)))
    except Exception:
        es = {}
    pos = []
    try:
        linhas = banco.sis_comp_todos(J.CH_PLACAR)
        for jogo in (J.TRADE, J.TICKER):
            rk = J.montar_ranking(jogo, linhas, q.email)
            if rk and rk.get("eu"):
                pos.append((int(rk["eu"]["pos"]), J.NOME[jogo].split()[0]))
    except Exception:
        pass
    melhor = min(pos) if pos else None
    ofensiva, desafio = 0, None
    try:
        dados = banco.ler_dados(a, q.email) or {}
        prog = ED.normalizar(dados.get("edu_progresso"))
        ofensiva = int(JO.resumo(prog).get("ofensiva") or 0)
        import jogar as JG
        d = JG.desafio_semana(prog)
        desafio = {k: d.get(k) for k in ("titulo", "texto", "atual", "alvo", "ok", "pontos")}
    except Exception:
        pass
    return {"vitorias": int(es.get("vitorias") or 0), "partidas": int(es.get("partidas") or 0),
            "melhor": {"pos": melhor[0], "jogo": melhor[1]} if melhor else None, "ofensiva": ofensiva, "desafio": desafio}


# ------------------------------------------------------------------ tela inicial do Trade Battle
@app.get("/trade/central")
def trade_central(q: Quem = Depends(quem)) -> dict:
    """O que a tela inicial do Trade Battle mostra (trader_battle_app._central): as durações (com quantos gráficos reais há),
    a sala em andamento da pessoa e a faixa do ranking do jogo."""
    corridas = []
    for f, sp in TB.CORRIDAS.items():
        try:
            reais = len(TD.listar_corrida(f))
        except Exception:
            reais = 0
        corridas.append({"id": f, "rotulo": TB.ROTULO_CORRIDA[f], "grafico": TB.TIMEFRAMES[sp["tf"]]["nome"],
                         "minutos": round((TB.T_ANALISE_S + sp["n_replay"] * TB.SEG_POR_CANDLE) / 60), "reais": reais})
    try:
        ativa = OL.partida_ativa(q.email)
    except Exception:
        ativa = None
    ranking = None
    try:
        rk = J.montar_ranking(J.TRADE, banco.sis_comp_todos(J.CH_PLACAR), q.email)
        if rk and rk.get("eu"):
            ranking = {"pos": int(rk["eu"]["pos"]), "total": int(rk.get("total") or 0), "valor": float(rk["eu"].get("valor") or 0),
                       "nome": rk["eu"].get("apelido") or ""}
    except Exception:
        ranking = None
    return {"corridas": corridas, "ativa": ativa, "ranking": ranking, "xp_dia": TB.XP_PARTIDAS_DIA}


# ------------------------------------------------------------------ rankings (só partidas online contam)
@app.get("/ranking/{jogo}")
def ranking(jogo: str, metrica: str = "pts", q: Quem = Depends(quem)) -> dict:
    if jogo not in J.JOGOS:
        raise HTTPException(404, "jogo desconhecido")
    try:
        return J.montar_ranking(jogo, banco.sis_comp_todos(J.CH_PLACAR), q.email, metrica=metrica)
    except ValueError as e:
        _erro(e)


def _registrar_ranking(q: Quem, pid: str, p: dict, fz: dict, res: dict | None) -> None:
    """Partida terminada no placar dos jogos (a regra de só contar partida online fica em jogos.registrar_trade)."""
    try:
        meu = next(x for x in fz["placar"] if x["voce"])
        n = len(fz["placar"])
        fin = (res or {}).get("fin") or {}
        doc = banco.jogos_placar_ler(q.ator)
        doc, mudou = J.registrar_trade(doc, pid, meu["pontos"], len(fz["rodadas"]), TB.cfg_de(p).get("formato") or "",
                                       meu["pos"] if n > 1 else None, n, time.strftime("%Y-%m-%d %H:%M"),
                                       lucro=fin.get("pnl"), retorno=fin.get("pct_aposta"), qualidade=(res or {}).get("qualidade_nota"))
        if mudou:
            banco.jogos_placar_gravar(q.ator, doc)
    except Exception as e:
        banco.registrar_erro("api.registrar_ranking", e)


# ------------------------------------------------------------------ Trade Battle · solo
def _chave_solo(q: Quem, pid: str) -> str:
    return CHAVE_SOLO.format(h=banco._h_conta(q.email), pid=pid)


def _ler_solo(q: Quem, pid: str) -> tuple[dict, dict, dict]:
    d = banco.cfg_ler(_chave_solo(q, pid))
    if not d or not d.get("p"):
        raise HTTPException(404, "partida não encontrada")
    cen = TD.resolver(d["cen"])
    return d, d["p"], cen


def _gravar_solo(q: Quem, pid: str, d: dict) -> None:
    banco.cfg_gravar(_chave_solo(q, pid), d)


def _estado_solo(q: Quem, pid: str, d: dict, p: dict, cen: dict) -> dict:
    """Avança pelo relógio do servidor e devolve o que a tela desenha. No fim: lança o resultado na Carteira e no placar (uma vez)."""
    agora = _agora()
    TB.avancar(p, agora, TD.por_id([cen]))
    if p["fase"] == "resultado":
        TB.proxima_rodada(p, agora)
    v = TB.visao(p, cen, agora, q.email)
    fim = p["fase"] == "fim"
    if fim and not d.get("fechada"):
        TCA.liquidar_seguro(p)
        fz = TB.resumo_final(p, q.email)
        _registrar_ranking(q, pid, p, fz, (p.get("resultados") or {}).get(TB._chave(1, q.email)))
        d["fechada"] = True
    d["p"] = p
    _gravar_solo(q, pid, d)
    args = TG.args_mesa(v, p, d.get("estado") or {}, agora)
    out = {"id": pid, "fase": p["fase"], "tela": args}
    if fim:
        res = (p.get("resultados") or {}).get(TB._chave(1, q.email))
        out["fim"] = {"resultado": res, "revelado": TB.revelacao(p, cen), "final": TB.resumo_final(p, q.email)}
    return out


class NovaPartida(BaseModel):
    corrida: str = "intermediaria"


@app.post("/trade/solo")
def trade_solo_nova(d: NovaPartida, q: Quem = Depends(quem)) -> dict:
    if d.corrida not in TB.CORRIDAS:
        raise HTTPException(400, "duração inválida")
    semente = random.randrange(100000)
    try:
        cen = TD.escolher_corrida(d.corrida, semente)                  # só gráficos reais (sem nenhum guardado: erro claro)
        apostas = {q.email: TCA.capital_corrida(q.email, q.conta.get("id"))}
        pid = uuid.uuid4().hex[:10]
        p = TB.nova_partida(cen, cen["tf"], [q.email], _agora(), pid=pid, apostas=apostas, corrida=d.corrida)
    except TCA.SemSaldo as e:
        _erro(e, 409)
    except TB.ErroTrader as e:
        _erro(e, 409)
    reg = {"p": p, "cen": TD.referencia_corrida(cen, semente), "estado": {}}
    return _estado_solo(q, pid, reg, p, cen)


@app.get("/trade/solo/{pid}")
def trade_solo_ver(pid: str, q: Quem = Depends(quem)) -> dict:
    d, p, cen = _ler_solo(q, pid)
    return _estado_solo(q, pid, d, p, cen)


class Estrategia(BaseModel):
    direcao: str | None = None          # "alta" (Subir), "baixa" (Cair) ou vazio (Aguardar)
    tipo: str | None = None


@app.post("/trade/solo/{pid}/estrategia")
def trade_solo_estrategia(pid: str, e: Estrategia, q: Quem = Depends(quem)) -> dict:
    d, p, cen = _ler_solo(q, pid)
    ref = cen["candles"][cen["n_analise"] - 1]["c"]
    est = {"direcao": None, "tipo": "aguardar"} if e.direcao in (None, "", "lateral") else {"direcao": e.direcao, "tipo": e.tipo or "continuacao"}
    try:
        TB.salvar_estrategia(p, q.email, est, None, ref, _agora())     # solo: confirmar já começa o gráfico
    except TB.ErroTrader as x:
        _erro(x)
    return _estado_solo(q, pid, d, p, cen)


class Acao(BaseModel):
    dados: dict                          # mesmo formato da tela atual: {aid, tipo, direcao, q, preco, stop, alvo, dist, qual}


@app.post("/trade/solo/{pid}/acao")
def trade_solo_acao(pid: str, a: Acao, q: Quem = Depends(quem)) -> dict:
    d, p, cen = _ler_solo(q, pid)
    try:
        TB.registrar_acao(p, cen, q.email, TG.acao_de(a.dados), _agora())
    except TB.ErroTrader as x:
        _erro(x)
    return _estado_solo(q, pid, d, p, cen)


_ABAS_RELATORIO = """<style>
html,body{margin:0;background:transparent;font-family:'Source Sans 3','Source Sans Pro',system-ui,sans-serif;color:#fff}
section[role=dialog]{padding:14px 12px 16px;min-height:100vh;box-sizing:border-box}
.ab{display:flex;gap:6px;margin:4px 0 10px}.ab button{flex:1;padding:8px 4px;border-radius:12px;border:1.5px solid #5B4BD6;background:#1B1460;
color:#D9D4F7;font:800 13px inherit;font-family:inherit}.ab button.on{background:linear-gradient(90deg,#7C5CFF,#B06BFF);color:#fff;border-color:#B9A8FF}
.pn{display:none}.pn.on{display:block}
</style>"""


@app.get("/trade/solo/{pid}/relatorio")
def trade_solo_relatorio(pid: str, q: Quem = Depends(quem)) -> dict:
    """Relatório do fim da partida corrida, o mesmo do app antigo (trader_relatorio): topo, e as abas Resumo, Operações e Raio-X.
    Devolve uma página HTML pronta para o app mostrar."""
    import trader_relatorio as TR
    d, p, cen = _ler_solo(q, pid)
    if p.get("fase") != "fim":
        raise HTTPException(400, "A partida ainda não terminou.")
    res = (p.get("resultados") or {}).get(TB._chave(1, q.email))
    if not res:
        raise HTTPException(404, "Sem resultado para esta partida.")
    revelado = TB.revelacao(p, cen)
    paineis = (("Resumo", TR.html_resumo(res, revelado, "")), ("Operações", TR.html_operacoes(res)), ("Raio-X", TR.html_raiox(TB.explicar_mesa(res))))
    botoes = "".join(f"<button class='{'on' if i == 0 else ''}' onclick='ab({i})'>{n}</button>" for i, (n, _) in enumerate(paineis))
    corpo = "".join(f"<div class='pn{' on' if i == 0 else ''}'>{h}</div>" for i, (_, h) in enumerate(paineis))
    js = ("<script>function ab(i){document.querySelectorAll('.ab button').forEach((b,k)=>b.classList.toggle('on',k===i));"
          "document.querySelectorAll('.pn').forEach((p,k)=>p.classList.toggle('on',k===i))}</script>")
    pagina = ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
              + _ABAS_RELATORIO + TR.CSS + "</head><body><section role='dialog'>" + TR.html_topo()
              + f"<div class='ab'>{botoes}</div>{corpo}</section>{js}</body></html>")
    return {"html": pagina}


# ------------------------------------------------------------------ Trade Battle · salas online (2 a 4 jogadores)
def _sala(fn, *args):
    try:
        return fn(*args)
    except (OL.ErroSala, TB.ErroTrader) as e:
        _erro(e)


class NovaSala(BaseModel):
    corrida: str = "intermediaria"


@app.post("/trade/salas")
def sala_criar(d: NovaSala, q: Quem = Depends(quem)) -> dict:
    if d.corrida not in TB.CORRIDAS:
        raise HTTPException(400, "duração inválida")
    return _sala(OL.criar_sala, q.email, TB.CORRIDAS[d.corrida]["tf"], _agora(), TB.FORMATO_PADRAO, d.corrida)


class Codigo(BaseModel):
    codigo: str


@app.post("/trade/salas/entrar")
def sala_entrar(d: Codigo, q: Quem = Depends(quem)) -> dict:
    return _sala(OL.entrar_na_sala, q.email, d.codigo, _agora())


@app.post("/trade/salas/{pid}/iniciar")
def sala_iniciar(pid: str, q: Quem = Depends(quem)) -> dict:
    _sala(OL.iniciar, pid, q.email, _agora())
    return sala_ver(pid, q)


@app.get("/trade/salas/{pid}")
def sala_ver(pid: str, q: Quem = Depends(quem)) -> dict:
    b = _sala(OL.ler, pid, q.email, _agora())
    v = b.get("v")
    if v and v.get("fase") == "fim" and v.get("final"):
        _registrar_ranking(q, pid, b["p"], v["final"], v.get("resultado"))
    return b


@app.post("/trade/salas/{pid}/estrategia")
def sala_estrategia(pid: str, e: Estrategia, q: Quem = Depends(quem)) -> dict:
    est = {"direcao": None, "tipo": "aguardar"} if e.direcao in (None, "", "lateral") else {"direcao": e.direcao, "tipo": e.tipo or "continuacao"}
    _sala(OL.salvar, pid, q.email, est, None, _agora())
    return sala_ver(pid, q)


@app.post("/trade/salas/{pid}/acao")
def sala_acao(pid: str, a: Acao, q: Quem = Depends(quem)) -> dict:
    _sala(OL.agir, pid, q.email, TG.acao_de(a.dados), _agora())
    return sala_ver(pid, q)


@app.post("/trade/salas/{pid}/sair")
def sala_sair(pid: str, q: Quem = Depends(quem)) -> dict:
    _sala(OL.sair, pid, q.email, _agora())
    return {"ok": True}
