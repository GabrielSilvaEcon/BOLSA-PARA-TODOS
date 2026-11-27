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
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json
import banco
from paralelo import paralelo
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
app.add_middleware(GZipMiddleware, minimum_size=1024)       # respostas comprimidas: a partida manda o gráfico a cada segundo (~5x menos dados no celular)

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
async def saude() -> dict:
    """Health check do Render: responde na hora e SEM tocar no banco. Antes ele consultava o banco: com o Supabase lento, passava dos 5 s do Render,
    o serviço era dado como falho e reiniciado no meio das partidas (o app via 'connection abort')."""
    return {"ok": True}


@app.get("/saude/banco")
def saude_banco() -> dict:
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
    with banco.pre_carregar_estados(q.email, _CHAVES_ESTADO_TELAS):       # as leituras de estado desta pessoa saem de UMA consulta
        return _eu(q)


# estados da pessoa que as telas iniciais leem (tudo na tabela monitor_estado): carteira (WG), perfil de jogador, placar, ordens/carteira da competição, troféus, equipados da Loja
_CHAVES_ESTADO_TELAS = ("comp_cart", "comp_ordens", "perfil_jogador", "jogos_placar", "trofeus", "tc_equipado")


def _eu(q: "Quem") -> dict:
    a = q.ator
    # leituras independentes entre si: saem juntas (o tempo é o da mais lenta, não a soma). O que depende de outra coisa continua em sequência.
    par = paralelo({"dados": lambda: banco.ler_dados(a, q.email), "moedas": lambda: TC.saldo(q.conta.get("id")),
                    "alertas": lambda: _alertas_nao_lidos(a), "cart": lambda: TCA.situacao(q.email)})
    try:
        perfil = banco.perfil_jogador_ler(a) or {}
    except Exception:
        perfil = {}
    try:
        cart = par["cart"].get()
    except Exception:
        cart = None
    try:
        placar = J.estatisticas(J.sanear(banco.jogos_placar_ler(a)))
    except Exception:
        placar = None
    # progresso de estudo (XP, nível, passe) e Ticker Coins: as mesmas regras do app atual, lidas do banco
    try:
        dados = par["dados"].get() or {}
        prog = ED.normalizar(dados.get("edu_progresso"))
        xp = int(JO.resumo(prog)["xp"])
        nivel = NV.estado(xp)
    except Exception:
        prog, xp, nivel = None, None, None
    try:
        moedas = par["moedas"].get()
    except Exception:
        moedas = None
    try:
        from datetime import datetime, timedelta, timezone
        hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).date()          # horário de Brasília
        passe = PA.estado(JO._jor(prog)["xp_dia"], hoje) if prog is not None else None
    except Exception:
        passe = None
    ranking = _ranking_da_casa(a, q.email)
    try:                                                   # troféus do jogo em que está melhor (a cápsula do troféu no cabeçalho)
        import trofeus as TF
        td = _trof_doc(q.email)
        trofeus = max(td[j]["t"] for j in TF.JOGOS)
    except Exception:
        trofeus = None
    _presente_setup(q)
    return {"trofeus": trofeus, "conta": {"id": q.conta.get("id"), "email": q.email, "nome": q.conta.get("nome")},
            "perfil": {k: perfil.get(k) for k in ("nome", "usuario", "avatar", "bio") if k in perfil}, "carteira": cart, "placar": placar,
            "xp": xp, "nivel": nivel, "moedas": moedas, "passe": passe, "ranking": ranking,
            "avatar_img": _avatar_img(perfil.get("avatar")), "alertas": par["alertas"].get()}


def _presente_setup(q: Quem) -> None:
    """Contas antigas recebem o brinde do setup básico ao abrir o app, uma vez só: as que já passaram do tutorial e as que existem há mais de 1 dia
    (inclui quem veio do app antigo e nunca fez o tutorial novo). Conta recém-criada espera o Baú Iniciante, para a revelação não se perder.
    Qualquer falha aqui é só registrada: nunca atrapalha a abertura do app."""
    try:
        import battle_dados as BD
        import seguranca as seg
        import setups_dados as SD
        criada = seg.de_iso(q.conta.get("criado_em"))
        antiga = bool(criada) and (seg.agora() - criada).total_seconds() > 86400
        if antiga or BD.ler_pessoa(banco, q.email).get("tutorial_concluido"):
            SD.presente_inicial(q.email)
    except Exception as e:
        banco.registrar_erro("api.setups_presente_eu", e)


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
        linhas = banco.sis_comp_todos(J.CH_PLACAR, cache_s=15)
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
        if ativa and (((OL._row(ativa) or {}).get("dados") or {}).get("sala") or {}).get("publica") and not ((OL._row(ativa) or {}).get("dados") or {}).get("p"):
            OL.sair_da_busca(q.email)                      # uma busca de adversário que ficou para trás (app fechado) não é uma sala para voltar: cancela
            ativa = None
    except Exception:
        ativa = None
    ranking = None
    try:
        rk = J.montar_ranking(J.TRADE, banco.sis_comp_todos(J.CH_PLACAR, cache_s=15), q.email)
        if rk and rk.get("eu"):
            ranking = {"pos": int(rk["eu"]["pos"]), "total": int(rk.get("total") or 0), "valor": float(rk["eu"].get("valor") or 0),
                       "nome": rk["eu"].get("apelido") or ""}
    except Exception:
        ranking = None
    return {"corridas": corridas, "ativa": ativa, "ranking": ranking, "xp_dia": TB.XP_PARTIDAS_DIA}


# ------------------------------------------------------------------ Loja Ticker (saldo, recompensas, vitrine e extrato)
def _plano_de(q: "Quem") -> str:
    try:
        import planos
        return planos.plano_de(q.email, q.conta.get("papel"))
    except Exception:
        return "gratuito"


def _prog_estudo(q: "Quem"):
    """(dados, progresso de estudo) da conta, para os baús e o escudo de ofensiva."""
    dados = banco.ler_dados(q.ator, q.email) or {}
    return dados, ED.normalizar(dados.get("edu_progresso"))


def _baus_elegiveis(q: "Quem") -> list[dict]:
    """Baús a que a pessoa tem direito (marcos do Hunter Pass e semana de ofensiva), como no app antigo. Falha = nenhum."""
    try:
        import baus as B
        _, p = _prog_estudo(q)
        hoje = JO.hoje()
        return B.todos(PA.estado(JO._jor(p)["xp_dia"], hoje), JO.ofensiva(p), hoje)
    except Exception:
        return []


def _fmt_quando(iso) -> str:
    d = TC._de_iso(iso)
    return d.astimezone(TC.timezone(TC.timedelta(hours=-3))).strftime("%d/%m %H:%M") if d else ""


KINDS_LOJA = ("tema", "moldura")            # a Loja vende só temas e molduras (decisão do Gabriel); o resto não aparece nem pode ser comprado


@app.get("/loja")
def loja(q: Quem = Depends(quem)) -> dict:
    """Loja Ticker, como a do app antigo (tickercoins_app.pagina_economia): saldo; Recompensas (baú diário e baús de progresso);
    Loja (itens à venda e os que você tem, com a prévia e o estado de cada um); Extrato (totais, benefícios e histórico)."""
    import loja_vitrine as VT
    from datetime import datetime, timedelta, timezone
    cid = q.conta.get("id")
    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    # leituras independentes entre si saem juntas; o que depende de outra (status dos baús) vem depois
    par = paralelo({"hist": lambda: TC.historico(cid, 60), "compras": lambda: TC.compras(cid), "eq": lambda: TC.equipado(q.email), "plano": lambda: _plano_de(q),
                    "bau": lambda: TC.bau_diario(cid), "elegiveis": lambda: _baus_elegiveis(q), "totais": lambda: TC.totais(cid)})
    try:
        hist_bruto = par["hist"].get()                            # a 1ª linha (a mais nova) já traz o saldo atual: uma consulta em vez de duas
        s = int(hist_bruto[0]["saldo_apos"]) if hist_bruto else 0
    except Exception as e:
        _erro(e, 503)
    todas = par["compras"].get()                                   # os pedidos são lidos UMA vez e reaproveitados (benefícios em vigor, lista de compras, "tem" de cada item)
    ativos = TC.vigentes(todas)
    possui = {b["produto_id"] for b in ativos}
    eq = par["eq"].get()
    plano = par["plano"].get()
    itens = []
    for p in TC.produtos():
        stt = VT.status(p, possui, eq, s, hoje)
        ok = TC.pode_comprar(cid, p["id"], plano, ativos_ja_lidos=ativos)[0]
        if not (stt["tem"] or ok):
            continue
        kind = (p.get("efeito") or {}).get("kind")
        if kind not in KINDS_LOJA:
            continue
        itens.append({"id": p["id"], "nome": p["nome"], "desc": p.get("desc") or "", "preco": int(p["preco"]), "raridade": VT.raridade(p),
                      "status": stt, "kind": kind, "equipavel": VT.equipavel(p), "em_uso": eq.get(kind) == p["id"], "previa": VT.previa(p)})
    itens.sort(key=lambda x: (x["status"]["tem"], x["preco"]))
    bau = par["bau"].get()
    pend = [{"indice": i, "rotulo": el.get("rotulo", "Baú"), "raridade": el.get("raridade")}
            for i, el in enumerate(TC.baus_status(cid, par["elegiveis"].get())) if not el["aberto"]]
    compras = [{"nome": (TC.produto(x["produto_id"]) or {}).get("nome", x["produto_id"]), "preco": int(x["preco"]),
                "quando": _fmt_quando(x["criado_em"]), "estado": TC.ROTULO_ESTADO.get(x["estado"], x["estado"])} for x in todas[:20]]
    hist = [{"descricao": x["descricao"] or x["origem"], "delta": int(x["delta"]), "pendente": x["estado"] == "pendente",
             "quando": _fmt_quando(x["criado_em"]), "estado": TC.ROTULO_ESTADO.get(x["estado"], x["estado"]), "saldo_apos": int(x["saldo_apos"])}
            for x in hist_bruto]
    benef = [{"nome": (TC.produto(x["produto_id"]) or {}).get("nome", x["produto_id"]),
              "validade": "Permanente" if not x.get("expira_em") else f"até {_fmt_quando(x['expira_em'])}"} for x in ativos]
    return {"saldo": s, "bau": bau, "baus": pend, "itens": itens, "compras": compras, "totais": par["totais"].get(), "historico": hist, "beneficios": benef}


@app.post("/loja/bau")
def loja_bau(q: Quem = Depends(quem)) -> dict:
    """Abre o baú diário (uma vez por dia; o servidor sorteia e credita)."""
    try:
        res = TC.abrir_bau_diario(q.conta.get("id"))
    except TC.ErroTC as e:
        _erro(e)
    return _ct_bau(q, "diario:" + TC._dia_bau(), res)


@app.post("/loja/bau/{indice}")
def loja_bau_progresso(indice: int, q: Quem = Depends(quem)) -> dict:
    """Abre um baú de progresso (marco do passe ou semana de ofensiva). Uma vez por baú."""
    lista = _baus_elegiveis(q)
    if not 0 <= indice < len(lista):
        raise HTTPException(404, "Baú não encontrado.")
    el = lista[indice]
    try:
        res = {**TC.abrir_bau(q.conta.get("id"), el), "rotulo": el.get("rotulo", "Baú")}
    except TC.ErroTC as e:
        _erro(e)
    return _ct_bau(q, f"{el.get('origem')}:{el.get('ref')}", res)


class Compra(BaseModel):
    pid: str
    req: str                                # identificador do pedido (repetir o mesmo pedido não cobra de novo)


@app.post("/loja/comprar")
def loja_comprar(c: Compra, q: Quem = Depends(quem)) -> dict:
    """Compra um item com TickerCoins (mesmas regras do app antigo). O escudo de ofensiva também abre a janela de 7 dias na Jornada."""
    if ((TC.produto(c.pid) or {}).get("efeito") or {}).get("kind") not in KINDS_LOJA:
        raise HTTPException(400, "Este item não está à venda na Loja.")
    r = TC.comprar(q.conta.get("id"), c.pid, c.req[:64], _plano_de(q))
    if r.get("ok") and not r.get("duplicada") and c.pid == "escudo_ofensiva":
        try:
            dados, p = _prog_estudo(q)
            dados["edu_progresso"] = JO.registrar_escudo(p)
            banco.gravar_dados(q.ator, q.email, dados)
        except Exception as e:
            banco.registrar_erro("api.escudo", e)
    if not r.get("ok"):
        raise HTTPException(400, r.get("erro") or "Não foi possível concluir a compra.")
    return r


class Equipar(BaseModel):
    pid: str | None = None                  # vazio = tirar
    tipo: str


@app.post("/loja/equipar")
def loja_equipar(e: Equipar, q: Quem = Depends(quem)) -> dict:
    """Usa (ou tira) um item que a conta possui: tema, moldura, emblema etc."""
    try:
        return TC.equipar(q.conta.get("id"), q.email, e.pid, e.tipo)
    except TC.ErroTC as x:
        _erro(x)


# ------------------------------------------------------------------ rankings (só partidas online contam)
@app.get("/ranking/{jogo}")
def ranking(jogo: str, metrica: str = "pts", q: Quem = Depends(quem)) -> dict:
    if jogo not in J.JOGOS:
        raise HTTPException(404, "jogo desconhecido")
    try:
        return J.montar_ranking(jogo, banco.sis_comp_todos(J.CH_PLACAR, cache_s=15), q.email, metrica=metrica)
    except ValueError as e:
        _erro(e)


MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _rk_perfis() -> dict:
    """{email: perfil saneado} de todas as contas (uma consulta)."""
    import perfis as PF
    try:
        return {r["email"]: PF.sanear(r["dados"]) for r in banco.sis_comp_todos("perfil_jogador", cache_s=30)}
    except Exception:
        return {}


def _rk_amigos(q: "Quem") -> set[str] | None:
    """Hashes de conta dos amigos (para o filtro Amigos)."""
    import amigos as AM
    try:
        return {h for h, r in banco.social_relacoes(q.ator).items() if r["estado"] == AM.AMIGOS}
    except Exception:
        return set()


def _rk_linha(pos: int, email: str, perfis: dict, eu_email: str, valor, extra: dict | None = None, apelido: str = "") -> dict:
    p = perfis.get(email) or {}
    eu = email == eu_email
    visivel = (p.get("privacidade") or {}).get("visivel") != "ninguem"
    nome = (p.get("nome") or p.get("usuario")) if (visivel or eu) else ""
    av = p.get("avatar") if (visivel or eu) else ""
    return {"pos": pos, "nome": nome or apelido or "Jogador", "usuario": p.get("usuario") if visivel else "", "valor": valor, "eu": eu,
            "avatar_img": _avatar_img(av), **(extra or {})}


@app.get("/trofeus")
def trofeus_meus(q: Quem = Depends(quem)) -> dict:
    """Troféus e divisão da conta logada nos dois jogos, a temporada (mês) e a tabela de divisões com os prêmios.
    Se uma temporada acabou desde a última visita, vem também o resumo dela (uma vez só) para a tela de fim de temporada."""
    import calendar
    import trofeus as TF
    doc = _trof_meu(q)
    doc.pop("aviso_fim", None)
    fim = next((v for k, v in sorted(doc["premios"].items(), reverse=True) if isinstance(v, dict) and not v.get("visto") and v.get("premio")), None)
    if fim:                                                # a tela de fim de temporada aparece uma vez só
        fim = dict(fim)
        doc["premios"][fim["temp"]] = {**fim, "visto": True}
        banco.sis_estado_gravar(q.email, CHAVE_TROFEUS, doc)
    agora = _agora_brt()
    ult_dia = calendar.monthrange(agora.year, agora.month)[1]
    return {"temporada": {"id": doc["temp"], "rotulo": f"{MESES[agora.month - 1].capitalize()} de {agora.year}", "dias_restantes": ult_dia - agora.day + 1},
            "jogos": {j: {"t": doc[j]["t"], "max": doc[j]["max"], "divisao": TF.divisao(doc[j]["t"])} for j in TF.JOGOS},
            "divisoes": TF.tabela(), "fim_temporada": fim, "reset": TF.PISO_RESET}


@app.get("/ranking/{jogo}/tela")
def ranking_tela(jogo: str, filtro: str = "geral", periodo: str = "geral", q: Quem = Depends(quem)) -> dict:
    """Central de rankings (aba Ranking): Trade Battle e Ticker Battle por TROFÉUS da temporada (com a divisão de cada um) e a Carteira
    pelo retorno (geral, mês, semana ou ajustado ao risco), como no app antigo. filtro=amigos mostra só você e seus amigos. Sem e-mail."""
    perfis = _rk_perfis()
    amigos = _rk_amigos(q) if filtro == "amigos" else None
    ok = (lambda email: email == q.email or banco._h_conta(email) in amigos) if amigos is not None else (lambda email: True)
    if jogo == "carteira":
        return _ranking_carteira(q, periodo, perfis, ok)
    if jogo == "semana":
        return _ranking_semana(q, perfis)
    if jogo == "torneio":
        return _ranking_torneio(q, perfis, ok)
    if jogo not in ("trade", "ticker"):
        raise HTTPException(404, "jogo desconhecido")
    import trofeus as TF
    temp = _temporada()
    linhas = []
    try:
        for r in banco.sis_comp_todos(CHAVE_TROFEUS, cache_s=15):
            d = TF.sanear(r["dados"], temp)[0]
            if (d[jogo]["t"] > 0 or any(str(x).startswith(jogo + ":") for x in d["ids"])) and ok(r["email"]):
                linhas.append((d[jogo]["t"], r["email"]))
    except Exception as e:
        _erro(e, 503)
    import bots as BOTS
    if BOTS.BOTS_ATIVOS and filtro != "amigos":              # jogadores da casa, com pontuação baixa, para o ranking não ficar vazio
        perfis = {**perfis, **{f["chave"]: {"nome": f["nome"], "usuario": f["nome"]} for f in BOTS.fantasmas_do_ranking(jogo, temp, _agora_brt().day)}}
        linhas += [(f["trofeus"], f["chave"]) for f in BOTS.fantasmas_do_ranking(jogo, temp, _agora_brt().day)]
    linhas.sort(key=lambda x: (-x[0], x[1]))
    saida = [_rk_linha(i, e, perfis, q.email, t, {"divisao": TF.divisao(t)}) for i, (t, e) in enumerate(linhas, 1)]
    meu = next((x for x in saida if x["eu"]), None)
    if not meu:
        t = _trof_doc(q.email)[jogo]["t"]
        meu = _rk_linha(None, q.email, perfis, q.email, t, {"divisao": TF.divisao(t)})
    return {"jogo": jogo, "nome": J.NOME[jogo], "total": len(saida), "linhas": saida[:100], "eu": meu, "unidade": "troféus",
            "hora": _agora_brt().strftime("%H:%M")}


def _ranking_carteira(q: "Quem", periodo: str, perfis: dict, ok) -> dict:
    """Ranking da Carteira (competição do app antigo): retorno no período ou Sharpe (ajustado ao risco), com os mesmos participantes."""
    import competicao as C
    import ranking_parcial as RP
    per = periodo if periodo in ("geral", "mes", "semana", "risco") else "geral"
    listas, rotulo = RP.escolher(banco.comp_publico_ler("comp_ranking") or {})
    email_de = {}
    try:
        for r in banco.sis_comp_todos("comp_ordens"):
            ap = str(((r["dados"] or {}).get("apelido")) or "")
            if ap:
                email_de[ap] = r["email"]
    except Exception:
        pass
    try:
        meu_ap = str(C.sanear_perfil(banco.comp_ordens_ler(q.ator)).get("apelido") or "")
    except Exception:
        meu_ap = ""
    saida = []
    for x in listas.get(per) or []:
        email = email_de.get(x.get("apelido"), "")
        if not ok(email) and x.get("apelido") != meu_ap:
            continue
        valor = x.get("sh") if per == "risco" else round(float(x.get("ret") or 0) * 100, 2)
        linha = _rk_linha(len(saida) + 1, email, perfis, q.email if x.get("apelido") != meu_ap else email, valor,
                          {"dd": round(float(x.get("dd") or 0) * 100, 2), "dias": x.get("dias")}, apelido=x.get("apelido") or "")
        linha["eu"] = x.get("apelido") == meu_ap
        saida.append(linha)
    return {"jogo": "carteira", "nome": "Carteira", "periodo": per, "total": len(saida), "linhas": saida[:100],
            "eu": next((x for x in saida if x["eu"]), None), "unidade": "Sharpe" if per == "risco" else "% de retorno", "rotulo": rotulo,
            "hora": _agora_brt().strftime("%H:%M")}


# ------------------------------------------------------------------ troféus e temporadas (trofeus.py): só partidas online
CHAVE_TROFEUS = "trofeus"


def _temporada() -> str:
    return _agora_brt().strftime("%Y-%m")


def _trof_doc(email: str) -> dict:
    """Troféus de outra conta (para a conta Elo): só leitura, já na temporada atual."""
    import trofeus as TF
    try:
        return TF.sanear(banco.sis_estado_ler(email, CHAVE_TROFEUS), _temporada())[0]
    except Exception:
        return TF.vazio(_temporada())


def _trof_meu(q: "Quem") -> dict:
    """Troféus da conta logada, aplicando a virada de temporada (e pagando uma vez o prêmio da temporada que acabou)."""
    import trofeus as TF
    bruto = banco.sis_estado_ler(q.email, CHAVE_TROFEUS)
    doc, fim = TF.sanear(bruto, _temporada())
    if fim:
        try:
            TC.creditar(q.conta.get("id"), int(fim["premio"]), "bonus:temporada", f"Fim da temporada {fim['temp']}",
                        f"trof:{q.conta.get('id')}:{fim['temp']}", fim["temp"])
        except Exception as e:
            banco.registrar_erro("api.trofeus_premio", e)
    if fim or not bruto or (bruto or {}).get("temp") != doc["temp"]:
        banco.sis_estado_gravar(q.email, CHAVE_TROFEUS, doc)
    return doc


def _trof_registrar(q: "Quem", jogo: str, pid: str, adversarios: list[str], placar: float, bots: dict | None = None) -> None:
    """Troféus de UMA partida online, contra a média de troféus dos adversários. Guarda o último resultado para a tela de fim."""
    import trofeus as TF
    try:
        doc = _trof_meu(q)
        antes = TF.divisao(doc[jogo]["t"])
        bots = bots or {}
        deles = [(bots[e]["trofeus"] if e in bots else _trof_doc(e)[jogo]["t"]) for e in adversarios if e and e != q.email] or [doc[jogo]["t"]]
        doc, d = TF.registrar(doc, jogo, pid, sum(deles) / len(deles), placar)
        if d is None:
            return
        depois = TF.divisao(doc[jogo]["t"])
        hoje = _agora_brt().date()
        TF.anotar_semana(doc, TF.semana_id(hoje), d)
        TF.anotar_torneio(doc, TF.torneio_id(hoje), d)
        advs = [e for e in adversarios if e and e != q.email]
        for e in advs:
            if e not in bots:                                # bot não tem conta: sem confronto direto
                TF.anotar_h2h(doc, banco._h_conta(e), placar)
        rev = None
        if len(advs) == 1 and advs[0] in bots:               # contra bot: sem revanche de amigo; o nome do adversário é o do bot
            rev = {"h": "", "amigo": False, "placar": None, "nome": bots[advs[0]].get("nome") or "Bot", "avatar_img": ""}
        elif len(advs) == 1:                                 # duelo: dá para pedir revanche (se forem amigos)
            import amigos as AM
            h = banco._h_conta(advs[0])
            try:
                amigo = (banco.social_relacoes(q.ator).get(h) or {}).get("estado") == AM.AMIGOS
            except Exception:
                amigo = False
            try:
                import perfis as PF
                pf = PF.sanear(banco.sis_estado_ler(advs[0], "perfil_jogador"))
                nome, av = pf["nome"] or pf["usuario"] or "Adversário", _avatar_img(pf["avatar"] if pf["avatar"] != PF.FOTO else PF.AVATAR_PADRAO)
            except Exception:
                nome, av = "Adversário", ""
            rev = {"h": h, "amigo": amigo, "placar": doc["h2h"].get(h), "nome": nome, "avatar_img": av}
        doc["ult"] = {"jogo": jogo, "id": str(pid), "delta": d, "t": doc[jogo]["t"], "divisao": depois["nome"], "dv": depois,
                      "resultado": "vitoria" if placar > 0.5 else ("empate" if placar == 0.5 else "derrota"),
                      "subiu": depois["nivel"] > antes["nivel"], "caiu": depois["nivel"] < antes["nivel"], "revanche": rev}
        banco.sis_estado_gravar(q.email, CHAVE_TROFEUS, doc)
    except Exception as e:
        banco.registrar_erro("api.trofeus", e)


def _trof_ultimo(q: "Quem", pid: str) -> dict | None:
    try:
        u = (banco.sis_estado_ler(q.email, CHAVE_TROFEUS) or {}).get("ult") or {}
        return u if u.get("id") == str(pid) else None
    except Exception:
        return None


_EST_FEITAS: dict[tuple[str, str], bool] = {}          # partidas cujas estatísticas de setup já foram tratadas por este processo (não repete leitura a cada consulta)


def _registrar_estatistica_setups(q: Quem, pid: str, p: dict, res: dict | None) -> None:
    """Estatísticas pessoais dos setups (ativações, entradas, resultado). Sem nenhuma ativação na partida: não toca no banco."""
    chave = (q.email, str(pid))
    if chave in _EST_FEITAS:
        return
    try:
        import setups_dados as SD
        import setups_vivo as SV
        linhas = SV.estatistica_do_jogador(p, q.email, (res or {}).get("operacoes"))
        if linhas:
            SD.registrar_estatistica(q.email, str(pid), linhas)
        if len(_EST_FEITAS) > 4000:
            _EST_FEITAS.clear()
        _EST_FEITAS[chave] = True
    except Exception as e:
        banco.registrar_erro("api.setups_estatisticas", e)


def _registrar_ranking(q: Quem, pid: str, p: dict, fz: dict, res: dict | None) -> None:
    """Partida terminada no placar dos jogos (a regra de só contar partida online fica em jogos.registrar_trade).
    Partida contra BOT conta como qualquer outra: o bot vale, nos troféus, os do jogador mais o bônus do nível dele (p["bots"])."""
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
    try:
        meu = next(x for x in fz["placar"] if x["voce"])
        n = len(fz["placar"])
        if n >= 2:
            import trofeus as TF
            _trof_registrar(q, "trade", pid, [j for j in p.get("jogadores") or [] if j != q.email], TF.placar_por_posicao(meu["pos"], n), p.get("bots"))
    except Exception as e:
        banco.registrar_erro("api.trofeus_trade", e)
    _registrar_estatistica_setups(q, pid, p, res)
    try:                                                   # histórico pessoal (solo e online), só para o jogador ver suas partidas
        import historico_jogos as HJ
        meu = next(x for x in fz["placar"] if x["voce"])
        n = len(fz["placar"])
        fin = (res or {}).get("fin") or {}
        doc, mudou = HJ.anotar_trade(banco.sis_estado_ler(q.email, HJ.CHAVE_TRADE), pid, time.strftime("%Y-%m-%d %H:%M"), n, meu["pontos"],
                                     meu["pos"] if n > 1 else None, TB.cfg_de(p).get("formato") or "", fin.get("pnl"), fin.get("pct_aposta"),
                                     (res or {}).get("qualidade_nota"))
        if mudou:
            banco.sis_estado_gravar(q.email, HJ.CHAVE_TRADE, doc)
    except Exception as e:
        banco.registrar_erro("api.historico_trade", e)


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


class _ConflitoSolo(Exception):
    """Alguém gravou a partida no meio da operação: refazer a partir do estado novo."""


def _ler_solo_tok(q: Quem, pid: str) -> tuple[dict, dict, dict, tuple]:
    """Como `_ler_solo`, mais a marca: (`atualizado` que a leitura viu, retrato do estado lido). A gravação só vale se ninguém gravou depois
    (compare-and-set), e o retrato diz se alguma coisa mudou desde a leitura (jogada ou relógio)."""
    r = banco._selecionar("config_sistema", {"id": _chave_solo(q, pid)[:80]}, ["dados", "atualizado"], limite=1)
    d = banco._de_js(r[0]["dados"]) if r else None
    if not d or not d.get("p"):
        raise HTTPException(404, "partida não encontrada")
    return d, d["p"], TD.resolver(d["cen"]), (str(r[0]["atualizado"]), banco._js(d["p"]))


def _gravar_solo_se(q: Quem, pid: str, d: dict, marca: tuple) -> None:
    """Grava só se o estado ainda é o que foi lido. Sem isso, a consulta de cada segundo lia, a jogada gravava e a consulta gravava de volta o estado
    velho: a jogada do jogador sumia (confirmar a estratégia 'resetava'; zerar, comprar e vender 'não faziam nada' até o 2º clique)."""
    import seguranca as seg
    marca = marca[0]
    nova = seg.iso()
    if nova == marca:                                      # duas gravações no mesmo milissegundo: a marca precisa mudar sempre
        nova = seg.iso(seg.agora() + __import__("datetime").timedelta(milliseconds=1))
    if not banco._atualizar_n("config_sistema", {"id": _chave_solo(q, pid)[:80], "atualizado": marca}, {"dados": banco._js(d), "atualizado": nova}):
        raise _ConflitoSolo()


def _com_solo(q: Quem, pid: str, op):
    """Roda `op(d, p, cen, marca)` (ler, aplicar a jogada, gravar) e, se outra requisição gravou no meio, refaz com o estado novo."""
    for _ in range(8):
        d, p, cen, marca = _ler_solo_tok(q, pid)
        try:
            return op(d, p, cen, marca)
        except _ConflitoSolo:
            continue
    raise HTTPException(409, "A partida está muito movimentada agora. Tente de novo.")


def _pagar_xp(q: Quem, pid: str, info: dict) -> dict:
    """XP da partida no progresso de estudo da conta, com as mesmas regras do app antigo (trader_battle_app._pagar_xp):
    uma vez por partida, só nas XP_PARTIDAS_DIA primeiras do dia, nunca TickerCoins. Falha aqui nunca derruba a partida."""
    n = int((info or {}).get("xp") or 0)
    try:
        a = q.ator
        dados = banco.ler_dados(a, q.email) or {}
        p = dict(ED.normalizar(dados.get("edu_progresso")))
        tx = dict(p.get("trader_xp") or {})
        if pid in tx:
            return {"xp": tx[pid]["xp"], "status": "pago"}
        if n <= 0:
            return {"xp": 0, "status": "zero"}
        hoje = JO.hoje().isoformat()
        if sum(1 for v in tx.values() if v.get("d") == hoje) >= TB.XP_PARTIDAS_DIA:
            return {"xp": 0, "status": "limite"}
        j = JO.normalizar_jornada(p.get("jornada"))
        j["xp"] += n
        j["xp_dia"][hoje] = int(j["xp_dia"].get(hoje, 0)) + n
        tx[pid] = {"d": hoje, "xp": n}
        p["jornada"], p["trader_xp"] = j, tx
        dados["edu_progresso"] = p
        banco.gravar_dados(a, q.email, dados)
        return {"xp": n, "status": "pago"}
    except Exception as e:
        banco.registrar_erro("api.pagar_xp", e)
        return {"xp": 0, "status": "erro"}


def _estado_solo(q: Quem, pid: str, d: dict, p: dict, cen: dict, marca: tuple | None = None) -> dict:
    """Avança pelo relógio do servidor e devolve o que a tela desenha. No fim: lança o resultado na Carteira e no placar (uma vez).
    Com `marca` (leitura de `_ler_solo_tok`) a gravação é condicional e só acontece se algo mudou; sem ela (partida nova) grava direto."""
    agora = _agora()
    TB.avancar(p, agora, TD.por_id([cen]))
    try:                                                   # setups equipados: prazo do evento em curso e sinais do candle que acabou de fechar
        import setups_vivo as SV
        SV.processar(p, cen, agora)
    except Exception as e:
        banco.registrar_erro("api.setups_solo", e)
    if p["fase"] == "resultado":
        TB.proxima_rodada(p, agora)
    v = TB.visao(p, cen, agora, q.email)
    fim = p["fase"] == "fim"
    fechar = fim and not d.get("fechada")
    regravar = marca is None                               # partida nova: grava direto
    if marca is not None:
        d["p"] = p
        if fechar or banco._js(p) != marca[1]:             # consulta sem novidade não regrava (menos atropelo); a versão do motor não sobe em toda jogada, então compara o conteúdo
            _gravar_solo_se(q, pid, d, marca)              # perdeu para outra gravação? refaz tudo, ainda sem nenhum efeito colateral
    if fechar:
        TCA.liquidar_seguro(p)
        fz = TB.resumo_final(p, q.email)
        _registrar_ranking(q, pid, p, fz, (p.get("resultados") or {}).get(TB._chave(1, q.email)))
        d["xp_pago"] = _pagar_xp(q, pid, fz.get("xp") or {})
        d["fechada"] = True
        if d.get("desafio"):                              # partida do Desafio do dia: a nota entra no ranking do dia
            _desafio_nota(q, d["desafio"], pid, fz)
        regravar = True                                    # grava o fechamento (a jogada já estava gravada acima)
    if regravar:
        d["p"] = p
        _gravar_solo(q, pid, d)
    try:
        import setups_vivo as SV
        pub = {**p, "setup": SV.visao(p, q.email, agora)}  # o evento e as marcas dos sinais ativados (None se a partida não tem setups)
    except Exception as e:
        banco.registrar_erro("api.setups_solo_visao", e)
        pub = p
    args = TG.args_mesa(v, pub, d.get("estado") or {}, agora)
    out = {"id": pid, "fase": p["fase"], "tela": args}
    if fim:
        res = (p.get("resultados") or {}).get(TB._chave(1, q.email))
        out["fim"] = {"resultado": res, "revelado": TB.revelacao(p, cen), "final": TB.resumo_final(p, q.email), "xp": d.get("xp_pago")}
    return _com_etag(out)


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
    try:                                                   # os setups equipados valem também no solo, congelados no começo (trocar na central não muda esta partida)
        import setups_dados as SD
        import setups_vivo as SV
        p["setups"] = SV.iniciar([q.email], {q.email: SD.equipados(q.email)})
    except Exception as e:
        banco.registrar_erro("api.setups_solo_inicio", e)
    reg = {"p": p, "cen": TD.referencia_corrida(cen, semente), "estado": {}}
    return _estado_solo(q, pid, reg, p, cen)


# ---- Consulta INCREMENTAL da partida (Etapa 2). O servidor sempre monta o estado completo (a verdade é dele) e decide o que ENVIAR:
#   · cliente sem parâmetros (app antigo) ........ resposta completa, igual a antes (mais o campo `e`);
#   · `e` igual ao estado atual .................. resposta mínima {sem_mudanca, e, vol:{seg, prox_ms}} (nada de candles);
#   · mudou, e o cliente declara `n`, `u`, `fk` ... estado completo, mas só com a CAUDA dos candles (a partir do último que o cliente tem);
#   · qualquer divergência (candles a menos, soma diferente, outra fase/rodada, fim da partida) ... resposta completa: o cliente nunca fica com dado incompleto.
# `e` é um hash do estado SEM os campos que mudam a cada segundo (seg, prox_ms), que vão sempre em `vol`.
_VOLATEIS_TELA = ("seg", "prox_ms")


def _etag_tela(tela: dict) -> str:
    import hashlib
    base = {k: v for k, v in tela.items() if k not in _VOLATEIS_TELA}
    return hashlib.md5(json.dumps(base, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:16]


def _soma_candle(c: dict) -> float:
    return round(float(c.get("o", 0)) + float(c.get("h", 0)) + float(c.get("l", 0)) + float(c.get("c", 0)), 6)


def _com_etag(out: dict) -> dict:
    """Marca a resposta completa com a versão do estado (`e`). Respostas de jogadas também levam, para o cliente já consultar de forma incremental depois."""
    tela = out.get("tela")
    if isinstance(tela, dict) and out.get("fase") != "fim" and "fim" not in out and "candles" in tela:
        out["e"] = _etag_tela(tela)
    return out


def _enxuga(out: dict, e: str | None, n: int | None, u: float | None, fk: str | None) -> dict:
    tela = out.get("tela")
    if "e" not in out or not isinstance(tela, dict):
        return out                                                 # fim da partida e telas sem candles: sempre completo
    et = out["e"]
    if e and e == et:
        return {k: out[k] for k in ("estado", "id", "fase", "e") if k in out} | {"sem_mudanca": True, "vol": {k: tela.get(k) for k in _VOLATEIS_TELA}}
    cs = tela["candles"]
    if n and u is not None and fk and fk == tela.get("fase_key") and 2 <= n <= len(cs) and abs(_soma_candle(cs[n - 2]) - u) < 1e-4:
        t2 = {k: v for k, v in tela.items() if k != "candles"}
        t2.update(candles_desde=n - 1, candles_cauda=cs[n - 1:], candles_total=len(cs))
        return {**out, "tela": t2}
    return out


@app.get("/trade/solo/{pid}")
def trade_solo_ver(pid: str, q: Quem = Depends(quem), e: str | None = None, n: int | None = None, u: float | None = None, fk: str | None = None) -> dict:
    return _enxuga(_com_solo(q, pid, lambda d, p, cen, m: _estado_solo(q, pid, d, p, cen, m)), e, n, u, fk)


class Estrategia(BaseModel):
    direcao: str | None = None          # "alta" (Subir), "baixa" (Cair) ou vazio (Aguardar)
    tipo: str | None = None
    marcas: dict | None = None          # desenhos da estratégia: níveis com papel, tendências, zonas e notas (avaliados no fim)


@app.post("/trade/solo/{pid}/estrategia")
def trade_solo_estrategia(pid: str, e: Estrategia, q: Quem = Depends(quem)) -> dict:
    def op(d, p, cen, m):
        ref = cen["candles"][cen["n_analise"] - 1]["c"]
        est = {"direcao": None, "tipo": "aguardar"} if e.direcao in (None, "", "lateral") else {"direcao": e.direcao, "tipo": e.tipo or "continuacao"}
        try:
            TB.salvar_estrategia(p, q.email, est, e.marcas, ref, _agora())     # solo: confirmar já começa o gráfico
        except TB.ErroTrader as x:
            _erro(x)
        return _estado_solo(q, pid, d, p, cen, m)
    return _com_solo(q, pid, op)


class Acao(BaseModel):
    dados: dict                          # mesmo formato da tela atual: {aid, tipo, direcao, q, preco, stop, alvo, dist, qual}


@app.post("/trade/solo/{pid}/acao")
def trade_solo_acao(pid: str, a: Acao, q: Quem = Depends(quem)) -> dict:
    def op(d, p, cen, m):
        try:
            TB.registrar_acao(p, cen, q.email, TG.acao_de(a.dados), _agora())
        except TB.ErroTrader as x:
            _erro(x)
        return _estado_solo(q, pid, d, p, cen, m)
    return _com_solo(q, pid, op)


class DecisaoSetup(BaseModel):
    acao: str
    q: float | None = None


@app.post("/trade/solo/{pid}/setup")
def trade_solo_setup(pid: str, b: DecisaoSetup, q: Quem = Depends(quem)) -> dict:
    """Aceitar (ordem a mercado pelo sistema atual, na quantidade `q` da boleta) ou recusar o setup ativado. O prazo é o do servidor."""
    import setups_vivo as SV
    if b.acao not in ("aceitar", "recusar"):
        raise HTTPException(400, "Escolha aceitar ou recusar.")
    def op(d, p, cen, m):
        agora = _agora()
        TB.avancar(p, agora, TD.por_id([cen]))
        try:
            SV.decidir(p, cen, q.email, b.acao == "aceitar", b.q, agora)
        except TB.ErroTrader as x:
            _erro(x)
        return _estado_solo(q, pid, d, p, cen, m)
    return _com_solo(q, pid, op)


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
    return {"html": _pagina_relatorio(res, TB.revelacao(p, cen), d.get("xp_pago") or {})}


def _pagina_relatorio(res: dict, revelado: dict | None, xp: dict) -> str:
    """Página HTML do relatório (topo + abas Resumo, Operações e Raio-X), a mesma do app antigo."""
    import trader_relatorio as TR
    xp_txt = f"⭐ +{int(xp.get('xp') or 0)} XP nesta partida" if xp.get("status") == "pago" and xp.get("xp") else ""
    paineis = (("Resumo", TR.html_resumo(res, revelado, xp_txt)), ("Operações", TR.html_operacoes(res)), ("Raio-X", TR.html_raiox(TB.explicar_mesa(res))))
    botoes = "".join(f"<button class='{'on' if i == 0 else ''}' onclick='ab({i})'>{n}</button>" for i, (n, _) in enumerate(paineis))
    corpo = "".join(f"<div class='pn{' on' if i == 0 else ''}'>{h}</div>" for i, (_, h) in enumerate(paineis))
    js = ("<script>function ab(i){document.querySelectorAll('.ab button').forEach((b,k)=>b.classList.toggle('on',k===i));"
          "document.querySelectorAll('.pn').forEach((p,k)=>p.classList.toggle('on',k===i))}</script>")
    return ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            + _ABAS_RELATORIO + TR.CSS + "</head><body><section role='dialog'>" + TR.html_topo()
            + f"<div class='ab'>{botoes}</div>{corpo}</section>{js}</body></html>")


# ------------------------------------------------------------------ Trade Battle · salas online (2 a 4 jogadores)
def _sala(fn, *args):
    try:
        return fn(*args)
    except (OL.ErroSala, TB.ErroTrader) as e:
        _erro(e)


class NovaSala(BaseModel):
    corrida: str = "intermediaria"


class Busca(BaseModel):
    corrida: str = "intermediaria"


@app.post("/trade/fila")
def trade_fila_entrar(b: Busca, q: Quem = Depends(quem)) -> dict:
    """Procurar adversário online (1 contra 1). Quem estiver procurando a mesma duração ao mesmo tempo se encontra e a partida começa na hora."""
    t0 = time.time()
    r = _sala(OL.buscar, q.email, b.corrida, _agora())
    if time.time() - t0 > 3:
        print(f"[lento] POST /trade/fila levou {time.time() - t0:.1f}s -> {r.get('estado')}", flush=True)
    return r


@app.get("/trade/fila")
def trade_fila(q: Quem = Depends(quem)) -> dict:
    """Chamado a cada 2 s enquanto procura. {'estado': 'partida'|'fila'|'fora'|'expirou', 'id'?}"""
    t0 = time.time()
    r = _sala(OL.consultar_busca, q.email, _agora())
    if time.time() - t0 > 3:                                  # aparece nos logs do servidor: a busca está lenta (banco, servidor dormindo...)
        print(f"[lento] GET /trade/fila levou {time.time() - t0:.1f}s -> {r.get('estado')}", flush=True)
    return r


@app.post("/trade/fila/sair")
def trade_fila_sair(q: Quem = Depends(quem)) -> dict:
    _sala(OL.sair_da_busca, q.email, _agora())
    return {"ok": True}


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
def sala_ver(pid: str, q: Quem = Depends(quem), e: str | None = None, n: int | None = None, u: float | None = None, fk: str | None = None) -> dict:
    """Sala de espera ("sala": código e jogadores), partida ("jogo": o que a mesa desenha, como na partida solo) ou "cancelada".
    No fim: placar dos jogos e XP (uma vez por partida, como no app antigo). Parâmetros e/n/u/fk: consulta incremental (ver _enxuga)."""
    return _enxuga(_sala_resposta(pid, q), e, n, u, fk)


def _sala_resposta(pid: str, q: Quem, dados: dict | None = None) -> dict:
    """Resposta da partida. `dados` = estado que uma ação acabou de gravar: a resposta sai dele (sem reler o banco), então a jogada responde mais rápido."""
    agora = _agora()
    b = _sala(OL.ler, pid, q.email, agora, dados)
    if b.get("estado") != "jogo":
        return b
    v, p = b["v"], b["p"]
    out = {"estado": "jogo", "id": pid, "fase": p["fase"], "tela": TG.args_mesa(v, p, {}, agora)}
    if p["fase"] == "fim" and v.get("final"):
        _registrar_ranking(q, pid, p, v["final"], v.get("resultado"))
        out["fim"] = {"xp": _pagar_xp(q, pid, (v["final"] or {}).get("xp") or {}), "placar": (v["final"] or {}).get("placar"),
                      "trofeus": _trof_ultimo(q, pid),
                      # o que a tela de resultado do app lê (o mesmo da partida solo). Sem isto ela mostrava "ativo —", lucro "—", 0,0 pts e sempre "EMPATE TÉCNICO"
                      "resultado": v.get("resultado"), "revelado": v.get("revelado"), "final": v.get("final")}
    return _com_etag(out)


@app.get("/trade/salas/{pid}/relatorio")
def sala_relatorio(pid: str, q: Quem = Depends(quem)) -> dict:
    """Relatório do fim da partida em sala (o mesmo da partida solo)."""
    b = _sala(OL.ler, pid, q.email, _agora())
    v = b.get("v") or {}
    if b.get("estado") != "jogo" or (b.get("p") or {}).get("fase") != "fim" or not v.get("resultado"):
        raise HTTPException(400, "A partida ainda não terminou.")
    return {"html": _pagina_relatorio(v["resultado"], v.get("revelado"), _pagar_xp(q, pid, (v.get("final") or {}).get("xp") or {}))}


@app.post("/trade/salas/{pid}/estrategia")
def sala_estrategia(pid: str, e: Estrategia, q: Quem = Depends(quem)) -> dict:
    est = {"direcao": None, "tipo": "aguardar"} if e.direcao in (None, "", "lateral") else {"direcao": e.direcao, "tipo": e.tipo or "continuacao"}
    return _sala_resposta(pid, q, _sala(OL.salvar, pid, q.email, est, e.marcas, _agora()))


@app.post("/trade/salas/{pid}/acao")
def sala_acao(pid: str, a: Acao, q: Quem = Depends(quem)) -> dict:
    return _sala_resposta(pid, q, _sala(OL.agir, pid, q.email, TG.acao_de(a.dados), _agora()))


@app.post("/trade/salas/{pid}/setup")
def sala_setup(pid: str, d: DecisaoSetup, q: Quem = Depends(quem)) -> dict:
    """O dono do setup ativado aceita (ordem a mercado pelo sistema atual, na quantidade `q` da boleta) ou recusa. Prazo, dono e duplicidade são do servidor."""
    if d.acao not in ("aceitar", "recusar"):
        raise HTTPException(400, "Escolha aceitar ou recusar.")
    _, estado = _sala(OL.decidir_setup_com_estado, pid, q.email, d.acao == "aceitar", d.q, _agora())
    return _sala_resposta(pid, q, estado)


@app.post("/trade/salas/{pid}/sair")
def sala_sair(pid: str, q: Quem = Depends(quem)) -> dict:
    _sala(OL.sair, pid, q.email, _agora())
    return {"ok": True}


# ------------------------------------------------------------------ Setups colecionáveis (Meus Setups)
@app.get("/setups")
def setups_listar(q: Quem = Depends(quem)) -> dict:
    """As cartas de setup que a pessoa tem, os equipados (até 2) e quantos faltam. O que ela não desbloqueou não aparece."""
    import setups_dados as SD
    return SD.listar(q.email)


class EquiparSetup(BaseModel):
    id: str


@app.post("/setups/equipar")
def setups_equipar(b: EquiparSetup, q: Quem = Depends(quem)) -> dict:
    """Equipa um setup para as partidas X1 (até 2 ao mesmo tempo). Só quem tem a carta; a conferência é do servidor."""
    import setups as SU
    import setups_dados as SD
    try:
        SD.equipar(q.email, b.id)
    except SU.ErroSetup as e:
        raise HTTPException(400, str(e))
    return SD.listar(q.email)


@app.post("/setups/desequipar")
def setups_desequipar(b: EquiparSetup, q: Quem = Depends(quem)) -> dict:
    import setups_dados as SD
    SD.desequipar(q.email, b.id)
    return SD.listar(q.email)


# ------------------------------------------------------------------ Ticker Battle: duelo contra o sistema (mesmas regras de battle.py)
# O duelo fica no banco com as cartas CONGELADAS no início (como no app antigo, onde ficava na sessão). O app só manda "qual carta" e
# "qual indicador"; o servidor escolhe a adversária (regra fixa e pública), compara os valores reais e guarda o histórico.
CHAVE_TICKER = "tk_api|{h}|{id}"
TK_INDICADORES = ("pl", "dy_12m", "roe")   # as cartas colecionáveis usam só P/L, DY e ROE


def _tk_agora():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=-3)))


def _tk_data(ref) -> str:
    r = str(ref or "")
    return f"{r[8:10]}/{r[5:7]}/{r[:4]}" if len(r) >= 10 else "—"


def _tk_carta(c: dict, hoje, valores: bool = True) -> dict:
    """Carta para a tela: ticker, nome, categoria, data dos dados e (se `valores`) os indicadores válidos já formatados."""
    import battle as BT
    cat = BT.CATEGORIAS.get(c.get("classe"), {"nome": "—", "cor": "#8B6CFF"})
    ok, mot = BT.jogavel(c, hoje)
    # "tk" é o id da carta NO DUELO (cópia de jogo "TK-xxxx" para as cartas da coleção); "ticker" é o código da empresa
    out = {"tk": c.get("id") or c.get("tk"), "ticker": c.get("tk"), "nome": c.get("nome") or c.get("tk"), "classe": c.get("classe"), "categoria": cat["nome"],
           "cor": cat["cor"], "ref": _tk_data(c.get("ref")), "fonte": c.get("fonte") or "", "jogavel": ok, "motivo": mot, "avisos": list(c.get("avisos") or [])}
    if c.get("nivel"):
        out.update(nivel=c["nivel"], rar=c.get("rar"), melhorias=c.get("melhorias") or {})
    if valores:
        ind, real = c.get("ind") or {}, c.get("real") or {}
        out["ind"] = [{"id": i, "v": float(ind[i]), "txt": BT.formatar(i, ind[i]), **({"real": BT.formatar(i, real[i])} if i in real and real[i] != ind[i] else {})}
                      for i in BT.indicadores_validos(c) if i in TK_INDICADORES]
    return out


def _tk_meta() -> dict:
    import battle as BT
    return {i: {k: m[k] for k in ("nome", "curto", "icone", "melhor", "regra", "significa")} for i, m in BT.INDICADORES.items() if i in TK_INDICADORES}


def _tk_snapshot(atualizar: bool = True) -> dict:
    """Cartas do snapshot compartilhado; na central renova poucas cartas vencidas por vez (dados reais, nunca no meio do duelo)."""
    import battle_dados as BD
    agora = _tk_agora().replace(tzinfo=None)
    snap = BD.ler_snapshot(banco)
    if atualizar and BD.pendentes(snap, agora):
        try:
            snap, _ = BD.atualizar(banco, agora)
        except Exception as e:
            banco.registrar_erro("api.ticker_snapshot", e)
    return snap


@app.get("/ticker/central")
def ticker_central(q: Quem = Depends(quem)) -> dict:
    """Central do Ticker Battle: todas as cartas (com os indicadores), o baralho salvo, a sugestão inicial e o histórico de duelos."""
    import battle as BT
    import battle_dados as BD
    hoje = _tk_agora().date()
    snap = _tk_snapshot()
    import cartas_dados as CD
    pes = BD.ler_pessoa(banco, q.email)
    deck, jogo = CD.cartas_do_solo(q.email, snap)
    ok, msg = BT.validar_baralho(deck, jogo, hoje)
    if not ok and len(deck) < BT.BARALHO_MIN:
        msg = f"Equipe pelo menos {BT.BARALHO_MIN} cartas na Coleção para jogar."
    hist = pes["hist"]
    conta = {"vitoria": 0, "derrota": 0, "empate": 0}
    for h in hist:
        if h.get("final") in conta:
            conta[h["final"]] += 1
    cartas = sorted((_tk_carta(c, hoje) for c in snap.values()), key=lambda c: (not c["jogavel"], c["tk"]))
    return {"cartas": cartas, "indicadores": _tk_meta(), "deck": deck, "valido": ok, "msg": msg, "min": BT.BARALHO_MIN, "max": BT.BARALHO_MAX,
            "equipadas": [_tk_carta(jogo[t], hoje) for t in deck], "rodadas": BT.RODADAS, "sugestao": [],
            "tutorial_pendente": not bool(pes.get("tutorial_concluido")),
            "historico": {**conta, "ultimos": [
                {"id": h.get("id"), "ts": str(h.get("ts") or "")[:16].replace("T", " "), "final": h.get("final"), "placar": h.get("placar")} for h in hist[:5]]}}


@app.post("/ticker/tutorial/bau")
def ticker_tutorial_bau(q: Quem = Depends(quem)) -> dict:
    """Tutorial: entrega o Baú Iniciante e marca o tutorial concluído no Battle.
    São BARALHO_MAX cartas: o baralho já nasce cheio, e como o duelo usa só RODADAS delas, dá para escolher quais entram."""
    import battle_dados as BD
    import cartas as C
    import cartas_dados as CD
    pes = BD.ler_pessoa(banco, q.email)
    if pes.get("tutorial_concluido"):
        return {"ja": True, "cartas": []}
    doc, _ = CD.garantir_inicial(q.email)
    cat, cfg = CD.catalogo(), CD.regras()
    import battle as BT
    raridades = ["comum", "comum", "rara", "rara", "epica"][:BT.BARALHO_MAX]   # baralho cheio, respeitando o teto de 1 épica
    tks = C.sortear_inicial(banco._h_conta(q.email), raridades, CD.por_raridade(cat))
    agora = CD._agora_iso()
    res = C.entregar(doc, "tutorial_battle", tks, lambda t: cat[t]["raridade_fixa"], "tutorial_battle", agora)
    if not res["ja"]:
        for t in tks:                                                       # monta o baralho com o que couber
            try: C.equipar(doc, t, agora)
            except C.ErroCarta: pass
        CD.gravar(q.email, doc)
    pes["tutorial_concluido"] = True
    BD.gravar_pessoa(banco, q.email, pes)
    out = {"ja": res["ja"], "cartas": [{**i, **CD.visao_empresa(cat.get(i["tk"]))} for i in res["itens"]]}
    try:                                                   # brinde do Baú Iniciante: a carta do setup básico (e o aviso no sino)
        import setups_dados as SD
        st = SD.presente_inicial(q.email)
        if st:
            out["setup"] = st
    except Exception as e:
        banco.registrar_erro("api.setups_presente_bau", e)
    return out


class BaralhoTk(BaseModel):
    deck: list[str]


@app.post("/ticker/baralho")
def ticker_baralho(b: BaralhoTk, q: Quem = Depends(quem)) -> dict:
    """Antigo: o baralho agora é formado pelas cartas EQUIPADAS na Coleção (o pedido é ignorado; devolve o baralho atual)."""
    import battle as BT
    import cartas_dados as CD
    deck, jogo = CD.cartas_do_solo(q.email, _tk_snapshot(False))
    ok, msg = BT.validar_baralho(deck, jogo, _tk_agora().date())
    return {"deck": deck, "valido": ok, "msg": msg or "O baralho é formado pelas cartas equipadas na Coleção."}


def _tk_chave(q: Quem, did: str) -> str:
    return CHAVE_TICKER.format(h=banco._h_conta(q.email), id=did)


def _tk_ler(q: Quem, did: str) -> dict:
    d = banco.cfg_ler(_tk_chave(q, did))
    if not d or not d.get("duelo"):
        raise HTTPException(404, "duelo não encontrado")
    return d


def _tk_estado(d: dict) -> dict:
    """O que a arena desenha: rodada, placar, as cartas que sobraram na mão (e se cada uma tem adversária) e as rodadas já reveladas."""
    import battle as BT
    hoje = _tk_agora().date()
    du, cartas = d["duelo"], d["cartas"]
    mao = []
    for t in BT.cartas_disponiveis(du):
        if t in cartas:
            c = _tk_carta(cartas[t], hoje)
            c["sem_adv"] = BT.adversaria_da_rodada(du, cartas, t, hoje) is None
            mao.append(c)
    rods = []
    for r in du["rodadas"]:
        e = BT.explicar(r, cartas)
        rods.append({**{k: r[k] for k in ("n", "ind", "va", "vb", "venc", "melhor", "barra_a")},
                     "txt_a": BT.formatar(r["ind"], r["va"]), "txt_b": BT.formatar(r["ind"], r["vb"]), "nome_ind": BT.INDICADORES[r["ind"]]["nome"],
                     "jog": _tk_carta(cartas[r["jog"]], hoje, False), "adv": _tk_carta(cartas[r["adv"]], hoje, False), "raio_x": e})
    return {"id": du["id"], "rodada": min(BT.rodada_atual(du), BT.RODADAS), "total": BT.RODADAS, "placar": du["placar"], "final": du.get("final"),
            "mao": mao, "rodadas": rods}


@app.post("/ticker/duelo")
def ticker_novo(q: Quem = Depends(quem)) -> dict:
    """Começa um Duelo Clássico (3 rodadas) contra o sistema com o baralho salvo. As cartas ficam congeladas até o fim."""
    import battle as BT
    import battle_dados as BD
    hoje = _tk_agora().date()
    import cartas_dados as CD
    snap = _tk_snapshot(False)
    deck, jogo = CD.cartas_do_solo(q.email, snap)           # baralho = cartas equipadas, com os atributos de jogo da coleção
    ok, msg = BT.validar_baralho(deck, jogo, hoje)
    if not ok:
        raise HTTPException(400, msg if len(deck) >= BT.BARALHO_MIN else f"Equipe pelo menos {BT.BARALHO_MIN} cartas na Coleção para jogar.")
    du = BT.novo_duelo(uuid.uuid4().hex[:12], uuid.uuid4().hex, deck, _tk_agora().replace(tzinfo=None), BD.referencia_dos_dados(snap, list(snap)))
    d = {"duelo": du, "cartas": jogo}
    banco.cfg_gravar(_tk_chave(q, du["id"]), d)
    return _tk_estado(d)


@app.get("/ticker/duelo/{did}")
def ticker_ver(did: str, q: Quem = Depends(quem)) -> dict:
    return _tk_estado(_tk_ler(q, did))


@app.get("/ticker/duelo/{did}/adversaria")
def ticker_adversaria(did: str, carta: str, q: Quem = Depends(quem)) -> dict:
    """A carta que o sistema usará se você jogar `carta` agora (SEM os valores dela) e os indicadores que dá para disputar."""
    import battle as BT
    hoje = _tk_agora().date()
    d = _tk_ler(q, did)
    du, cartas = d["duelo"], d["cartas"]
    adv = BT.adversaria_da_rodada(du, cartas, carta, hoje)
    if adv is None:
        raise HTTPException(409, "Não há carta adversária compatível com esta carta. Escolha outra.")
    a = cartas[carta]
    disp = BT.atributos_disputaveis(a, adv, hoje)
    bloq = {i: m for i, m in disp["bloqueados"].items() if a.get("classe") in BT.INDICADORES[i]["classes"] and i in TK_INDICADORES}
    return {"adversaria": _tk_carta(adv, hoje, False), "disputaveis": [i for i in disp["ok"] if i in TK_INDICADORES], "bloqueados": bloq}


class RodadaTk(BaseModel):
    carta: str
    ind: str


@app.post("/ticker/duelo/{did}/rodada")
def ticker_rodada(did: str, r: RodadaTk, q: Quem = Depends(quem)) -> dict:
    """Joga a rodada: o servidor escolhe a adversária, compara e grava. No fim, o duelo entra no histórico (uma vez)."""
    import battle as BT
    import battle_dados as BD
    d = _tk_ler(q, did)
    if r.ind not in TK_INDICADORES:
        raise HTTPException(400, "Indicador fora do jogo.")
    try:
        d["duelo"] = BT.jogar_rodada(d["duelo"], d["cartas"], r.carta, r.ind, _tk_agora().date())
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e) or "Jogada inválida.")
    if d["duelo"].get("final") and not d.get("salvo"):
        try:
            reg = BD.registro_historico(d["duelo"], d["cartas"])
            BD.gravar_pessoa(banco, q.email, BD.adicionar_historico(BD.ler_pessoa(banco, q.email), reg))
            d["salvo"] = True
        except Exception as e:
            banco.registrar_erro("api.ticker_historico", e)
    banco.cfg_gravar(_tk_chave(q, did), d)
    return _tk_estado(d)


# ------------------------------------------------------------------ Ticker Battle ONLINE (mesmas regras de battle_online.py / battle_online_dados.py)
# Fila (encontrar adversário) ou sala privada com código. Cada jogador escolhe carta e indicador EM SEGREDO; quando os dois confirmam,
# o servidor revela e compara (se escolheram indicadores diferentes, cada um precisa vencer o que escolheu). Duelos online contam no ranking.
def _tk_on(fn, *a):
    import battle_online as BO
    try:
        return fn(*a)
    except BO.ErroPartida as e:
        raise HTTPException(400, str(e))
    except banco.ErroBanco as e:
        _erro(e, 503)


def _tk_on_registrar(q: Quem, v: dict) -> None:
    """Duelo online terminado entra no placar dos jogos (uma vez por duelo; repetir não soma)."""
    f = v.get("final") or {}
    if not v.get("encerrada") or f.get("resultado") not in ("vitoria", "derrota", "empate") or f.get("motivo") == "cancelada":
        return
    try:
        doc = banco.jogos_placar_ler(q.ator)
        doc, mudou = J.registrar_ticker(doc, v["id"], f["resultado"], "online", str(f.get("em") or "")[:16].replace("T", " "),
                                        apelido=(v.get("eu") or {}).get("nick") or "")
        if mudou:
            banco.jogos_placar_gravar(q.ator, doc)
    except Exception as e:
        banco.registrar_erro("api.ticker_online_placar", e)
    try:
        import battle_online_dados as BOD
        dados = (BOD._partida_row(v["id"]) or {}).get("dados") or {}
        jog = dados.get("jog") or {}
        outros = [(jog.get(k) or {}).get("email") for k in ("a", "b")]
        bot = dados.get("bot")                                  # jogador da casa: vale os troféus do nível dele (sem conta, sem confronto direto)
        _trof_registrar(q, "ticker", v["id"], [e for e in outros if e and e != q.email],
                        {"vitoria": 1.0, "empate": 0.5, "derrota": 0.0}[f["resultado"]],
                        {bot["email"]: {"trofeus": bot["trofeus"], "nome": bot.get("nome")}} if bot else None)
    except Exception as e:
        banco.registrar_erro("api.trofeus_ticker", e)


def _tk_on_visao(q: Quem, v: dict) -> dict:
    """O que a tela online desenha: a visão segura do jogador (nunca a escolha pendente do adversário), com as cartas no formato do app
    e cada comparação já formatada."""
    import battle as BT
    hoje = _tk_agora().date()
    cartas = {t: _tk_carta(c, hoje) for t, c in (v.get("cartas") or {}).items()}
    for c in cartas.values():
        c["ind"] = [i for i in c.get("ind") or [] if i["id"] in TK_INDICADORES]
    regs = []
    for r in v.get("reg") or []:
        cmp = [{**x, "nome": BT.INDICADORES.get(x["ind"], {}).get("nome", x["ind"]), "txt_a": BT.formatar(x["ind"], x["va"]), "txt_b": BT.formatar(x["ind"], x["vb"])}
               for x in r.get("cmp") or []]
        regs.append({"n": r["n"], "eu": r["eu"], "op": r["op"], "venc": r["venc"], "motivo": r.get("motivo") or "", "cmp": cmp, "lado": v["lado"]})
    _tk_on_registrar(q, v)
    return {**{k: v.get(k) for k in ("id", "fase", "lado", "rod", "rodadas", "eu", "op", "placar", "final", "encerrada")}, "cartas": cartas, "reg": regs,
            "indicadores": _tk_meta(), "trofeus": _trof_ultimo(q, v.get("id")) if v.get("encerrada") else None}


@app.post("/ticker/online/fila")
def tk_on_fila_entrar(q: Quem = Depends(quem)) -> dict:
    import battle_online_dados as BOD
    return _tk_on(BOD.entrar_na_fila, q.email)


@app.get("/ticker/online/fila")
def tk_on_fila(q: Quem = Depends(quem)) -> dict:
    """Chamado a cada 2 s enquanto procura: renova a presença na fila e tenta emparelhar. {'estado': 'partida'|'fila'|'fora'|'expirou', 'id'?}"""
    import battle_online_dados as BOD
    return _tk_on(BOD.consultar_fila, q.email)


@app.post("/ticker/online/fila/sair")
def tk_on_fila_sair(q: Quem = Depends(quem)) -> dict:
    import battle_online_dados as BOD
    _tk_on(BOD.sair_da_fila, q.email)
    return {"ok": True}


@app.post("/ticker/online/sala")
def tk_on_sala(q: Quem = Depends(quem)) -> dict:
    """Cria a sala privada (ou devolve a que já está aberta). {'id', 'codigo'}"""
    import battle_online_dados as BOD
    return _tk_on(BOD.criar_sala, q.email)


class CodigoTk(BaseModel):
    codigo: str


@app.post("/ticker/online/sala/entrar")
def tk_on_sala_entrar(c: CodigoTk, q: Quem = Depends(quem)) -> dict:
    import battle_online_dados as BOD
    return _tk_on(BOD.entrar_na_sala, q.email, c.codigo)


@app.get("/ticker/online/ativa")
def tk_on_ativa(q: Quem = Depends(quem)) -> dict:
    """Duelo online que a pessoa ainda tem aberto (para voltar a ele)."""
    import battle_online_dados as BOD
    return {"id": _tk_on(BOD.partida_ativa, q.email)}


@app.get("/ticker/online/{pid}")
def tk_on_ler(pid: str, q: Quem = Depends(quem)) -> dict:
    """Consulta de sincronização (a cada 1,5 s): presença, prazos e só o que este jogador pode ver."""
    import battle_online_dados as BOD
    v = _tk_on(BOD.ler, pid, q.email)
    out = _tk_on_visao(q, v)
    out["codigo"] = (BOD._partida_row(pid) or {}).get("codigo") or ""
    return out


@app.post("/ticker/online/{pid}/pronto")
def tk_on_pronto(pid: str, q: Quem = Depends(quem)) -> dict:
    import battle_online_dados as BOD
    return _tk_on_visao(q, _tk_on(BOD.estou_pronto, pid, q.email))


@app.post("/ticker/online/{pid}/jogar")
def tk_on_jogar(pid: str, r: RodadaTk, q: Quem = Depends(quem)) -> dict:
    """Confirma carta e indicador (não dá para mudar depois). Se o adversário já confirmou, a rodada é revelada na hora."""
    import battle_online_dados as BOD
    if r.ind not in TK_INDICADORES:
        raise HTTPException(400, "Indicador fora do jogo.")
    return _tk_on_visao(q, _tk_on(BOD.jogar, pid, q.email, r.carta, r.ind))


@app.post("/ticker/online/{pid}/sair")
def tk_on_sair(pid: str, q: Quem = Depends(quem)) -> dict:
    """Sair: sala sem jogo é cancelada; duelo em andamento = desistência (vitória do adversário)."""
    import battle_online_dados as BOD
    return _tk_on_visao(q, _tk_on(BOD.sair, pid, q.email))


# ------------------------------------------------------------------ Cartas colecionáveis (cartas.py / cartas_dados.py / cartas_catalogo.py)
# Catálogo global separado da coleção de cada pessoa. Toda regra (cópias, evolução, equipar, baús) roda AQUI no servidor; o app só pede.
def _ct_inds(c: dict | None) -> dict:
    """{ind: texto} dos 3 indicadores de uma carta do snapshot (ou cópia de jogo)."""
    import battle as BT
    ind = (c or {}).get("ind") or {}
    return {i: BT.formatar(i, ind[i]) for i in TK_INDICADORES if i in ind and BT.valor_valido(i, ind[i])}


def _ct_visao(q: Quem, doc: dict | None = None) -> dict:
    import cartas as C
    import cartas_catalogo as CAT
    import cartas_dados as CD
    cat, cfg = CD.catalogo(), CD.regras()
    doc = doc if doc is not None else CD.garantir_inicial(q.email)[0]
    snap = _tk_snapshot(False)
    lista = []
    for tk, e in cat.items():
        c = doc["cartas"].get(tk)
        item = {"tk": tk, "setor": e["setor"], "icone": e["icone"], "raridade": c["rar"] if c else e["raridade_fixa"], "possui": bool(c)}
        if c:
            pr = C.progresso(cfg, c)
            jogo = C.carta_de_jogo(snap[tk], c, cfg, tk) if tk in snap else None
            item.update(CD.visao_empresa(e), raridade=c["rar"], nivel=c["nivel"], copias=c["copias"], total=c.get("total", 1), precisa=pr["precisa"],
                        pode=pr["pode"], maximo=pr["maximo"], nivel_max=pr["nivel_max"], escolhas=list(c.get("escolhas") or []),
                        melhorias=C.bonus_das_escolhas(c.get("escolhas")), equipada=tk in doc["equip"],
                        real=_ct_inds(snap.get(tk)), jogo=_ct_inds(jogo), ref=_tk_data((snap.get(tk) or {}).get("ref")))
        lista.append(item)
    ordem = {r: i for i, r in enumerate(CAT.RARIDADES)}
    lista.sort(key=lambda x: (not x["possui"], -ordem[x["raridade"]], x["tk"]))
    bonus = {i: ("−4% no P/L" if i == "pl" else "+0,25 p.p. no DY" if i == "dy_12m" else "+1 p.p. no ROE") for i in CAT.INDICADORES}
    sinergias = C.sinergias(list(doc["equip"]), lambda t: (cat.get(t) or {}).get("setor"))
    return {"cartas": lista, "equip": doc["equip"], "equip_max": C.BARALHO_EQUIP, "equip_por_raridade": C.MAX_POR_RARIDADE, "sinergias": sinergias,
            "setores": sorted({e["setor"] for e in cat.values()}), "raridades": list(CAT.RARIDADES),
            "rotulos": CAT.ROTULO_RARIDADE, "indicadores": CAT.ROTULO_IND, "bonus": bonus,
            "descobertas": len(doc["cartas"]), "total": len(cat), "log": doc["log"][:20]}


@app.get("/cartas/colecao")
def cartas_colecao(q: Quem = Depends(quem)) -> dict:
    """A Coleção: todas as cartas do catálogo (as que você não tem vêm só com raridade e setor, para a silhueta) e os 4 espaços equipados."""
    import cartas_dados as CD
    doc, ini = CD.garantir_inicial(q.email)
    out = _ct_visao(q, doc)
    if ini and not ini["ja"]:
        out["inicial"] = [{**i, **CD.visao_empresa(CD.catalogo().get(i["tk"]))} for i in ini["itens"]]
    return out


class EvoluirCarta(BaseModel):
    tk: str
    ind: str


@app.post("/cartas/evoluir")
def cartas_evoluir(b: EvoluirCarta, q: Quem = Depends(quem)) -> dict:
    """Evolui a carta com as cópias dela mesma e grava a melhoria escolhida (P/L, DY ou ROE). Validado no servidor."""
    import cartas as C
    import cartas_dados as CD
    doc = CD.garantir_inicial(q.email)[0]
    try:
        r = C.evoluir(doc, CD.regras(), b.tk, b.ind, CD._agora_iso())
    except C.ErroCarta as e:
        raise HTTPException(400, str(e))
    CD.gravar(q.email, doc)
    return {"evolucao": r, **_ct_visao(q, doc)}


class EquiparCarta(BaseModel):
    tk: str


@app.post("/cartas/equipar")
def cartas_equipar(b: EquiparCarta, q: Quem = Depends(quem)) -> dict:
    """Equipa a carta no espaço da raridade dela (1 por raridade). Se já havia outra, ela sai (devolvida em `saiu`)."""
    import cartas as C
    import cartas_dados as CD
    doc = CD.garantir_inicial(q.email)[0]
    try:
        r = C.equipar(doc, b.tk, CD._agora_iso())
    except C.ErroCarta as e:
        raise HTTPException(400, str(e))
    CD.gravar(q.email, doc)
    return {"equipar": r, **_ct_visao(q, doc)}


class DesequiparCarta(BaseModel):
    tk: str


@app.post("/cartas/desequipar")
def cartas_desequipar(b: DesequiparCarta, q: Quem = Depends(quem)) -> dict:
    import cartas as C
    import cartas_dados as CD
    doc = CD.garantir_inicial(q.email)[0]
    try:
        C.desequipar(doc, b.tk, CD._agora_iso())
    except C.ErroCarta as e:
        raise HTTPException(400, str(e))
    CD.gravar(q.email, doc)
    return _ct_visao(q, doc)


@app.get("/cartas/catalogo")
def cartas_catalogo_app(q: Quem = Depends(quem)) -> dict:
    """Textos das cartas (nome, setor, atividade, fato, arte, raridade) para o app desenhar qualquer carta pelo ticker. Sem valores."""
    import cartas_dados as CD
    return {"empresas": {tk: CD.visao_empresa(e) for tk, e in CD.catalogo().items()}}


def _ct_bau(q: Quem, ref: str, res: dict) -> dict:
    """Cartas do baú que acabou de abrir (uma vez por baú; se algo falhar, as moedas continuam valendo)."""
    import cartas_dados as CD
    out = res
    try:
        r = CD.recompensa_bau(q.email, ref, str(res.get("raridade") or "comum"))
        out = {**res, "cartas": r["itens"]} if not r["ja"] else res
    except Exception as e:
        banco.registrar_erro("api.cartas_bau", e)
    try:                                                   # setups: rolagem à parte, que não mexe nas cartas nem nas moedas do baú
        import setups_dados as SD
        st = SD.recompensa_bau(q.email, ref, str(res.get("raridade") or "comum"))
        if st["setup"]:
            out = {**out, "setup": st["setup"]}
    except Exception as e:
        banco.registrar_erro("api.setups_bau", e)
    return out


def _ct_admin(q: Quem) -> None:
    if q.conta.get("papel") != "admin":
        raise HTTPException(403, "Só a administração pode mudar o catálogo de cartas.")


@app.get("/admin/cartas")
def admin_cartas(q: Quem = Depends(quem)) -> dict:
    """Admin: catálogo completo (com pontos e raridade) e as regras de evolução e baús em vigor."""
    import cartas_dados as CD
    _ct_admin(q)
    return {"empresas": CD.catalogo(), "regras": CD.regras()}


class EmpresaCarta(BaseModel):
    tk: str
    dados: dict


@app.post("/admin/cartas/empresa")
def admin_cartas_empresa(b: EmpresaCarta, q: Quem = Depends(quem)) -> dict:
    """Admin: cadastra ou ajusta uma empresa (textos, arte, pontos de mercado/liquidez/relevância, ativo). A raridade sai dos pontos."""
    import cartas as C
    import cartas_dados as CD
    _ct_admin(q)
    try:
        return CD.admin_salvar_empresa(b.tk, b.dados)
    except C.ErroCarta as e:
        raise HTTPException(400, str(e))


@app.post("/admin/cartas/regras")
def admin_cartas_regras(b: dict, q: Quem = Depends(quem)) -> dict:
    """Admin: tabela de evolução por raridade e nível; quantidade, chances, garantia e prêmio extra de cada baú."""
    import cartas as C
    import cartas_dados as CD
    _ct_admin(q)
    try:
        return CD.admin_salvar_regras(b)
    except C.ErroCarta as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ Perfil (o mesmo do app antigo: perfis.py, perfis_app.py, avatares.py)
def _pf_colecao(q: Quem, prog: dict) -> set:
    """Avatares liberados para a conta (nível real da Jornada + o que já está guardado na coleção). Guarda o que acabou de liberar."""
    import avatares as AV
    from datetime import datetime, timezone
    ctx = {"nivel": prog.get("nivel") or 1, "emblemas": set()}
    try:
        doc, novos = AV.sincronizar(banco.avatares_colecao_ler(q.ator), ctx, datetime.now(timezone.utc).date().isoformat())
        if novos:
            banco.avatares_colecao_gravar(q.ator, doc)
        return AV.liberados({**ctx, "concedidos": doc["concedidos"]}, doc["ids"])
    except Exception as e:
        banco.registrar_erro("api.perfil_colecao", e)
        return AV.liberados({"nivel": 1})


def _pf_prog(q: Quem, dados: dict | None = None) -> dict:
    """`dados`: documento de progresso que o chamador já leu (evita ler a mesma linha duas vezes na mesma requisição)."""
    import perfis as PF
    try:
        return PF.progresso(((dados if dados is not None else banco.ler_dados(q.ator, q.email)) or {}).get("edu_progresso"))
    except Exception:
        return PF.progresso({})


def _pf_loja(q: Quem, tipo: str, ativos: list | None = None, eq: dict | None = None) -> dict:
    """Itens de `tipo` (moldura ou tema) que a conta possui na Loja e o equipado agora (com a prévia para desenhar).
    `ativos`/`eq`: benefícios em vigor e equipados que o chamador já leu (o Perfil monta moldura e tema e antes lia tudo duas vezes)."""
    import loja_vitrine as VT
    try:
        donos = {c["produto_id"] for c in (ativos if ativos is not None else TC.beneficios_ativos(q.conta.get("id")))}
        itens = [{"id": p["id"], "nome": p["nome"], "previa": VT.previa(p)} for p in TC.produtos() if (p.get("efeito") or {}).get("kind") == tipo and p["id"] in donos]
        return {"itens": itens, "equipado": (eq if eq is not None else TC.equipado(q.email)).get(tipo)}
    except Exception:
        return {"itens": [], "equipado": None}


# ------------------------------------------------------------------ Minha conta (app): dados da conta, nome, atividades e cópia dos dados
_ROTULO_ACAO = {   # mesmos textos da tela Minha conta do Streamlit (conta_app._ROTULO_ACAO): (rótulo, tom)
    "conta.criada": ("Conta criada", "ok"), "conta.verificada": ("E-mail confirmado", "ok"),
    "login": ("Entrou com e-mail e senha", "info"), "login.google": ("Entrou com o Google", "info"),
    "logout": ("Saiu da conta", "na"), "senha.alterada": ("Senha alterada", "aviso"),
    "senha.redefinida": ("Senha redefinida por e-mail", "aviso"), "perfil.nome": ("Nome atualizado", "info"),
    "sessoes.encerradas": ("Outros aparelhos desconectados", "aviso"), "dados.exportados": ("Dados baixados", "info"),
    "conta.suspensa": ("Conta suspensa pela administração", "erro"), "conta.reativada": ("Conta reativada", "ok"),
    "preferencias.salvas": ("Preferências salvas", "info"),
}


@app.get("/conta")
def conta_resumo(q: Quem = Depends(quem)) -> dict:
    """Dados da própria conta (nunca hash de senha): nome, e-mail, cadastro, como entra, tipo e se o e-mail está confirmado."""
    import permissoes as perm
    c = banco.sis_conta_por_id(q.conta["id"]) or q.conta
    return {"nome": c.get("nome") or "", "email": c.get("email") or q.email, "cadastro": str(c.get("criado_em") or "")[:10],
            "provedor": c.get("provedor") or "", "tipo": perm.ROTULOS.get(c.get("papel"), "Usuário"),
            "email_verificado": bool(c.get("email_verificado"))}


class ContaNome(BaseModel):
    nome: str


@app.post("/conta/nome")
def conta_nome(d: ContaNome, q: Quem = Depends(quem)) -> dict:
    r = contas.atualizar_nome(q.ator, d.nome)
    if not r.ok:
        raise HTTPException(400, r.msg)
    return {"ok": True, "msg": r.msg, "nome": r.dado}


@app.get("/conta/atividades")
def conta_atividades(q: Quem = Depends(quem)) -> dict:
    """Atividades relevantes da própria conta (entradas, mudanças de senha, preferências e downloads de dados)."""
    itens = []
    for i in banco.atividades_do_ator(q.ator, 40):
        rot, tom = _ROTULO_ACAO.get(i["acao"], (i["acao"], "info"))
        itens.append({"rotulo": rot, "tom": tom, "quando": str(i["quando"] or "")[:16]})
    return {"itens": itens}


@app.get("/conta/dados")
def conta_dados(q: Quem = Depends(quem)) -> dict:
    """Cópia de tudo o que o app guarda sobre a pessoa (direito de acesso e portabilidade). Fica registrado nas atividades."""
    import json as _json
    dados = contas.exportar_meus_dados(q.ator)
    return {"json": _json.dumps(dados, ensure_ascii=False, indent=2, default=str)}


@app.get("/perfil")
def perfil_meu(q: Quem = Depends(quem)) -> dict:
    """Tela Meu Perfil: nome, usuário, avatar (com raridade e moldura), nível e XP, sequência, ranking, moedas, patrimônio,
    desempenho nos jogos, conquistas, bio, privacidade e o que dá para usar da Loja. Só leitura das fontes reais."""
    with banco.pre_carregar_estados(q.email, _CHAVES_ESTADO_TELAS):       # os estados da pessoa saem de UMA consulta
        return _perfil_meu(q)


def _perfil_meu(q: Quem) -> dict:
    import avatares as AV
    import perfis as PF
    a = q.ator
    try:
        doc = PF.sanear(banco.perfil_jogador_ler(a))
    except Exception:
        doc = PF.vazio()
    try:
        dados_edu = banco.ler_dados(a, q.email) or {}                     # lido UMA vez: serve ao progresso e à ofensiva/lições
    except Exception:
        dados_edu = {}
    prog = _pf_prog(q, dados_edu)
    ne = NV.estado(prog["xp"])
    try:
        placar = J.sanear(banco.jogos_placar_ler(a))
    except Exception:
        placar = J.sanear({})
    try:
        linhas = banco.sis_comp_todos(J.CH_PLACAR, cache_s=15)
        rt, rk = J.montar_ranking(J.TRADE, linhas, q.email), J.montar_ranking(J.TICKER, linhas, q.email)
    except Exception:
        rt, rk = None, None
    try:
        res = JO.resumo(ED.normalizar(dados_edu.get("edu_progresso")))
        ofensiva, licoes = int(res.get("ofensiva") or 0), int(res.get("licoes_feitas") or 0)
    except Exception:
        ofensiva, licoes = 0, 0
    try:
        moedas = TC.saldo(q.conta.get("id"))
    except Exception:
        moedas = None
    try:
        pat = (TCA.situacao(q.email) or {}).get("patrimonio")
    except Exception:
        pat = None
    try:
        ativos_loja, eq_loja = TC.beneficios_ativos(q.conta.get("id")), TC.equipado(q.email)      # uma leitura para moldura E tema
    except Exception:
        ativos_loja, eq_loja = [], {}
    av = doc["avatar"] if AV.existe(doc["avatar"]) else PF.AVATAR_PADRAO
    rar = AV.RARIDADES[AV.raridade_de(av)]
    desde = str(q.conta.get("criado_em") or "")[:10]
    return {"nome": doc["nome"] or doc["usuario"] or "Jogador", "usuario": doc["usuario"], "bio": doc["bio"], "desde": desde,
            "avatar": av, "avatar_img": _avatar_img(av), "avatar_nome": AV.POR_ID[av]["nome"], "raridade": {"nome": rar["nome"], "cor": rar["cor"]},
            "nivel": ne, "titulo": prog["titulo"], "xp": prog["xp"], "ofensiva": ofensiva, "licoes": licoes, "moedas": moedas, "patrimonio": pat,
            "ranking": _ranking_da_casa(a, q.email), "jogos": PF.jogos(placar, rt, rk), "estat": J.estatisticas(placar),
            "conquistas": {"ok": prog["conquistas"], "total": prog["conquistas_total"], "medalhas": prog["medalhas"]},
            "privacidade": doc["privacidade"], "moldura": _pf_loja(q, "moldura", ativos_loja, eq_loja), "tema": _pf_loja(q, "tema", ativos_loja, eq_loja),
            "opcoes": {"visivel": PF.VISIVEL, "pedidos": PF.PEDIDOS}}


@app.get("/perfil/avatares")
def perfil_avatares(q: Quem = Depends(quem)) -> dict:
    """Coleção de Avatares: todos os avatares (liberados e bloqueados, com como liberar), por raridade, e o equipado."""
    import avatares as AV
    import perfis as PF
    lib = _pf_colecao(q, _pf_prog(q))
    try:
        eq = PF.sanear(banco.perfil_jogador_ler(q.ator))["avatar"]
    except Exception:
        eq = PF.AVATAR_PADRAO
    itens = [{"id": a["id"], "nome": a["nome"], "img": _avatar_img(a["id"]), "raridade": a["raridade"], "cor": a["rar"]["cor"],
              "liberado": a["liberado"], "equipado": a["equipado"], "como": a["como"]} for a in AV.colecao(lib, eq)]
    tot = AV.totais(lib)
    return {"itens": itens, "raridades": {r: {"nome": v["plural"], "cor": v["cor"], **tot[r]} for r, v in AV.RARIDADES.items()},
            "liberados": len(lib & set(AV.POR_ID)), "total": len(AV.POR_ID)}


class PerfilEdicao(BaseModel):
    nome: str | None = None
    usuario: str | None = None
    bio: str | None = None
    avatar: str | None = None
    privacidade: dict | None = None


@app.post("/perfil")
def perfil_salvar(f: PerfilEdicao, q: Quem = Depends(quem)) -> dict:
    """Salva o perfil com as mesmas regras do app antigo: só campos editáveis; nome de usuário único (reservado antes de liberar o antigo,
    troca no máximo a cada 7 dias); avatar só se estiver liberado na coleção. XP, pontos e conquistas nunca vêm daqui."""
    import avatares as AV
    import perfis as PF
    a = q.ator
    atual = PF.sanear(banco.perfil_jogador_ler(a))
    form = {k: v for k, v in f.model_dump().items() if v is not None}
    if form.get("avatar") not in (None, atual["avatar"]):
        if form["avatar"] == PF.FOTO or not AV.pode_equipar(form["avatar"], _pf_colecao(q, _pf_prog(q))):
            raise HTTPException(400, "Esse avatar ainda está bloqueado. " + AV.como_liberar(AV.POR_ID.get(form["avatar"]) or {"desbloqueio": {}}) + ".")
    try:
        novo, mud = PF.editar(atual, form)
    except PF.ErroPerfil as e:
        raise HTTPException(400, str(e))
    try:
        if "usuario" in mud or (novo["usuario"] and not atual["usuario"]):
            if not banco.usuario_reservar(a, novo["usuario_k"]):
                raise HTTPException(400, "Esse nome de usuário já está em uso. Escolha outro.")
            if atual["usuario_k"] and atual["usuario_k"] != novo["usuario_k"]:
                banco.usuario_liberar(a, atual["usuario_k"])
        banco.perfil_jogador_gravar(a, novo)
        banco.auditar(a.id, "perfil_jogador.salvo", ",".join(sorted(form)))
    except HTTPException:
        raise
    except Exception as e:
        banco.registrar_erro("api.perfil_salvar", e)
        raise HTTPException(503, "Não consegui salvar agora. Tente de novo em instantes.")
    return perfil_meu(q)


# ------------------------------------------------------------------ Aprender (Jornada, como no app antigo: jornada.py, jornada_player.py)
# A lição fica no servidor: o app recebe uma pergunta por vez (sem a resposta), manda a resposta e o servidor corrige. Erro volta ao fim
# da fila (sem vidas). No fim, o progresso de estudo é gravado (XP, ofensiva, revisão) e as TickerCoins da sessão são pagas uma vez.
CHAVE_LICAO = "jor_api|{h}"


def _apr_gravar(q: Quem, dados: dict, p: dict) -> None:
    dados["edu_progresso"] = p
    banco.gravar_dados(q.ator, q.email, dados)


def _apr_ex_tela(ex: dict) -> dict:
    """Exercício para a tela, SEM a resposta certa (ordenar e pares já vêm embaralhados)."""
    out = {"id": ex["id"], "tipo": ex["tipo"], "pergunta": ex["pergunta"]}
    if ex["tipo"] in ("escolha", "completar"):
        out["opcoes"] = list(ex["opcoes"])
    elif ex["tipo"] == "ordenar":
        out["itens"] = JO.embaralhar_itens(ex)
    elif ex["tipo"] == "pares":
        out["esquerda"] = [a for a, _ in ex["pares"]]
        out["direita"] = JO.embaralhar_pares(ex)
    return out


def _apr_sessao(q: Quem) -> dict | None:
    return banco.cfg_ler(CHAVE_LICAO.format(h=banco._h_conta(q.email))) or None


def _apr_estado(s: dict) -> dict:
    ex = JO.exercicio_atual(s)
    return {"sessao": {"total": s["total"], "feitos": s["feitos"], "pct": JO.progresso_sessao(s), "revisao": s["revisao"],
                       "titulo": ("Simulado" if s.get("simulado") else "Teste de nivelamento") if (s.get("nivelamento") or s.get("simulado")) else ("Revisão" if s["revisao"] else jornada_conteudo().LICAO_POR_ID[s["licao"]]["titulo"])},
            "exercicio": _apr_ex_tela(ex) if ex else None}


def jornada_conteudo():
    import jornada_conteudo as JC
    return JC


@app.get("/aprender")
def aprender(q: Quem = Depends(quem)) -> dict:
    """Trilha de estudo: resumo (XP, meta do dia, ofensiva, revisão) e o mapa das unidades com o estado de cada lição (nada fica trancado)."""
    _, p = _prog_estudo(q)
    r = JO.resumo(p)
    ne = NV.estado(r["xp"])
    s = _apr_sessao(q)
    import aprender_areas as AA
    j = JO._jor(p)
    # "mapa" (todas as unidades) continua para os apps antigos; o app novo usa "areas" e abre cada área em /aprender/area/{id}
    return {"resumo": r, "nivel": ne, "mapa": JO.mapa(p), "em_andamento": bool(s and not JO.terminada(s)), "areas": AA.resumo_areas(j["licoes"], j["erros"])}


@app.get("/aprender/area/{area}")
def aprender_area(area: str, cert: str | None = None, q: Quem = Depends(quem)) -> dict:
    """Uma área do Aprender: as trilhas dela (com a próxima lição contada dentro da área) e os erros que esperam revisão ali.
    Em Certificações sem `cert`, devolve a lista de certificações; com `cert`, as trilhas daquela certificação."""
    import aprender_areas as AA
    a = AA.AREA_POR_ID.get(area)
    if not a or (cert is not None and cert not in AA.CERT_POR_ID):
        raise HTTPException(404, "área não encontrada")
    _, p = _prog_estudo(q)
    j = JO._jor(p)
    out = {"area": a, "cert": AA.CERT_POR_ID.get(cert) if cert else None, "erros": len(AA.erros_da_area(j["erros"], area, cert)),
           "nivelamento": AA.tem_nivelamento(area) and cert is None,
           "simulado": {"questoes": AA.SIMULADO_QUESTOES, "corte": AA.SIMULADO_CORTE} if AA.tem_simulado(cert) else None}
    try:
        out["recomendada"] = (banco.sis_estado_ler(q.email, "apr_nivel") or {}).get(area)
    except Exception:
        out["recomendada"] = None
    if area == "certificacoes" and cert is None:
        return {**out, "certificacoes": AA.certificacoes(j["licoes"]), "mapa": []}
    return {**out, "mapa": AA.mapa_area(j["licoes"], area, cert)}


@app.get("/aprender/aula/{aid}")
def aprender_aula(aid: str, q: Quem = Depends(quem)) -> dict:
    """Texto da aula ligada a uma lição (o mesmo do app antigo), no modo de leitura da pessoa."""
    import edu_conteudo as E
    a = E.POR_ID.get(aid)
    if not a:
        raise HTTPException(404, "aula não encontrada")
    _, p = _prog_estudo(q)
    return {"titulo": a["titulo"], "min": a.get("min"), "texto": ED.texto_aula(a, p.get("modo") or "iniciante")}


@app.post("/aprender/licao/{lid}")
def aprender_comecar(lid: str, q: Quem = Depends(quem)) -> dict:
    """Começa a lição (ou a revisão, com lid = 'revisao'). Devolve a 1ª pergunta."""
    if lid == "revisao":
        _, p = _prog_estudo(q)
        s = JO.iniciar_revisao(p)
        if not s:
            raise HTTPException(400, "Nada para revisar agora. Bom trabalho!")
    elif lid.startswith("simulado:"):                    # simulado de uma certificação: simulado:<cert>
        import aprender_areas as AA
        s = AA.iniciar_simulado(lid.split(":", 1)[1], _agora_brt().date().isoformat())
        if not s:
            raise HTTPException(400, "Esta certificação ainda não tem simulado.")
    elif lid.startswith("nivel:"):                       # teste de nivelamento opcional da área: nivel:<area>
        import aprender_areas as AA
        s = AA.iniciar_nivelamento(lid.split(":", 1)[1])
        if not s:
            raise HTTPException(400, "Esta área ainda não tem teste de nivelamento.")
    elif lid.startswith("revisao:"):                     # revisão só de uma área (e certificação): revisao:<area>[:<cert>]
        import aprender_areas as AA
        partes = lid.split(":")
        area, cert = partes[1], (partes[2] if len(partes) > 2 else None)
        if area not in AA.AREA_POR_ID:
            raise HTTPException(404, "área não encontrada")
        _, p = _prog_estudo(q)
        s = AA.iniciar_revisao_area(JO._jor(p)["erros"], area, cert, JO.TAM_REVISAO)
        if not s:
            raise HTTPException(400, "Nada para revisar nesta área. Bom trabalho!")
    else:
        s = JO.iniciar_sessao(lid)
        if not s:
            raise HTTPException(404, "lição não encontrada")
    banco.cfg_gravar(CHAVE_LICAO.format(h=banco._h_conta(q.email)), s)
    return _apr_estado(s)


class RespostaApr(BaseModel):
    id: str
    resposta: object = None


@app.post("/aprender/responder")
def aprender_responder(r: RespostaApr, q: Quem = Depends(quem)) -> dict:
    """Corrige a pergunta atual (no servidor). Devolve se acertou, a explicação, a resposta certa e a próxima pergunta.
    Na última, conclui: grava o progresso (XP, ofensiva, revisão) e paga as TickerCoins da sessão (uma vez)."""
    s = _apr_sessao(q)
    if not s or JO.terminada(s):
        raise HTTPException(400, "Nenhuma lição em andamento.")
    ex = JO.exercicio_atual(s)
    if ex["id"] != r.id:
        raise HTTPException(409, "Essa pergunta já foi respondida.")
    ok, s2 = JO.responder(s, r.resposta)
    out = {"ok": ok, "explicacao": ex.get("explicacao") or "", "certa": JO.resposta_certa_texto(ex)}
    if not JO.terminada(s2):
        banco.cfg_gravar(CHAVE_LICAO.format(h=banco._h_conta(q.email)), s2)
        return {**out, **_apr_estado(s2), "fim": None}
    if s2.get("nivelamento"):                            # nivelamento: sem XP e sem mexer no progresso; guarda só a trilha recomendada
        import aprender_areas as AA
        res = AA.resultado_nivelamento(s2)
        banco.cfg_gravar(CHAVE_LICAO.format(h=banco._h_conta(q.email)), {})
        try:
            rec = banco.sis_estado_ler(q.email, "apr_nivel") or {}
            rec[res["area"]] = (res["recomendada"] or {}).get("id")
            banco.sis_estado_gravar(q.email, "apr_nivel", rec)
        except Exception as e:
            banco.registrar_erro("api.aprender_nivel", e)
        return {**out, "sessao": None, "exercicio": None, "fim": res}
    dados, p = _prog_estudo(q)
    antes = {c["id"] for c in ED.conquistas(p) if c["ok"]}
    p2, res = JO.concluir_sessao(p, s2)
    _apr_gravar(q, dados, p2)
    banco.cfg_gravar(CHAVE_LICAO.format(h=banco._h_conta(q.email)), {})
    novas = [c for c in ED.conquistas(p2) if c["ok"] and c["id"] not in antes]
    tc = 0
    try:
        linhas = TC.recompensar_sessao(q.conta.get("id"), {**res, "ok": True}, [c["id"] for c in novas])
        tc = sum(int(x["delta"]) for x in linhas or [])
    except Exception as e:
        banco.registrar_erro("api.aprender_moedas", e)
    res["conquistas_novas"] = [c["titulo"] for c in novas]
    res["tc"] = tc
    res["nivel_antes"], res["nivel_depois"] = NV.nivel_de(res["xp_antes"]), NV.nivel_de(res["xp_depois"])
    if s2.get("simulado"):
        import aprender_areas as AA
        res.update(AA.resultado_simulado(s2))
    return {**out, "sessao": None, "exercicio": None, "fim": res}


# ------------------------------------------------------------------ Mercado (botão Mercado da Home): Mercado hoje, busca e leitura de uma ação
_MERC_CACHE: dict = {}


_MERC_TTL_VAZIO = 60.0   # a fonte falhou: espera um pouco antes de tentar de novo


def _merc_cache(chave: str, ttl: float, f):
    """Guarda a resposta de `f()` por `ttl` segundos (cotações mudam devagar e as fontes limitam consultas).

    A falha também é guardada, por `_MERC_TTL_VAZIO`. Sem isso, uma fonte fora do ar ou lenta faz CADA
    pedido pagar a espera dela — e a Home é a primeira tela de todo mundo. Pior: como a fonte limita
    consultas, repetir a chamada a cada pedido alimenta o próprio bloqueio que causou a falha.
    HTTPException passa direto: é resposta deliberada (ex.: cripto inexistente), não fonte indisponível."""
    agora = time.time()
    c = _MERC_CACHE.get(chave)
    if c and agora - c[0] < (ttl if c[1] else _MERC_TTL_VAZIO):
        return c[1]
    try:
        v = f()
    except HTTPException:
        raise
    except Exception:
        v = None
    _MERC_CACHE[chave] = (agora, v)
    return v


def _merc_empresa(e: dict) -> dict:
    return {"ticker": e["ticker"], "nome": e["nome"], "setor": e.get("setor"), "logo": _logo_ativo(e["ticker"])}


@app.get("/mercado")
def mercado(q: Quem = Depends(quem)) -> dict:
    """Tela Mercado: Mercado hoje (Ibovespa, dólar, bitcoin e índice do medo), os tipos de ativo e as ações populares."""
    import inicio_painel as IP
    import mercado_api as MA
    import recursos as R
    try:
        hoje = _merc_cache("hoje", 600, IP.mercado_hoje) or []
    except Exception:
        hoje = []
    pop = [_merc_empresa(R.POR_TICKER[t]) for t in R.POPULARES if t in R.POR_TICKER]
    return {"hoje": hoje, "tipos": [{"id": i, "titulo": t, "descricao": d, "pronto": p} for i, t, d, p in MA.TIPOS],
            "populares": pop, "criptos": MA.criptos_populares(), "aviso": MA.AVISO}


@app.get("/mercado/busca")
def mercado_busca(texto: str = "", q: Quem = Depends(quem)) -> dict:
    """Empresas do catálogo pelo nome, código ou setor (ex.: 'petro', 'VALE3', 'bancos')."""
    import recursos as R
    t = (texto or "").strip()[:40]
    if len(t) < 2:
        return {"itens": []}
    import mercado_api as MA
    acoes = [_merc_empresa(e) for e in R.buscar_catalogo(t, 12) if e.get("ticker") in R.POR_TICKER]
    return {"itens": MA.buscar_criptos(t)[:6] + acoes}


def _merc_tk(tk: str) -> str:
    import recursos as R
    t = (tk or "").upper().strip()
    if t not in R.POR_TICKER:
        raise HTTPException(404, "Essa ação ainda não está no Mercado do app.")
    return t


@app.get("/mercado/acao/{tk}")
def mercado_acao(tk: str, q: Quem = Depends(quem)) -> dict:
    """Leitura de uma ação: preço, variação do dia, gráfico de 1 ano, indicadores com faixas, preço justo (Graham e Bazin) e o resumo
    em palavras simples. Contas do app antigo (mercado_api.py)."""
    import mercado_api as MA
    import recursos as R
    t = _merc_tk(tk)
    d = _merc_cache("acao:" + t, 900, lambda: MA.dados_acao(t))
    if not d or not d.get("preco"):
        raise HTTPException(424, "Não consegui os dados dessa ação agora. Tente de novo em instantes.")  # 424 e não 5xx: o app não fica repetindo
    serie = _merc_cache("hist:" + t + ":1a", 900, lambda: MA.historico(t, "1a")) or []
    d = {**d, "var_dia": MA.var_dia(serie)}
    out = MA.montar_acao(t, d, R.POR_TICKER[t])
    out["logo"] = _logo_ativo(t)
    out["serie"] = serie
    return out


@app.get("/mercado/acao/{tk}/historico")
def mercado_acao_historico(tk: str, periodo: str = "1a", q: Quem = Depends(quem)) -> dict:
    import mercado_api as MA
    t = _merc_tk(tk)
    p = periodo if periodo in MA.PERIODOS else "1a"
    return {"periodo": p, "serie": _merc_cache(f"hist:{t}:{p}", 900, lambda: MA.historico(t, p)) or []}


@app.get("/mercado/cripto/{gid}")
def mercado_cripto(gid: str, q: Quem = Depends(quem)) -> dict:
    """Leitura de uma criptomoeda: preço em dólar, gráfico de 1 ano e os seis quadros do app antigo (cripto.py, CoinGecko)."""
    import cripto as CR
    import mercado_api as MA
    g = (gid or "").lower().strip()
    if not MA.ID_CRIPTO.fullmatch(g):
        raise HTTPException(404, "Criptomoeda não encontrada.")

    def ler():
        try:
            return CR.analisar_moeda(g)
        except CR.ErroAPI as e:
            if "404" in str(e):
                raise HTTPException(404, "Criptomoeda não encontrada.")
            return None
    m = _merc_cache("cripto:" + g, 600, ler)
    if not m or m.get("preco") is None:
        raise HTTPException(424, "Não consegui os dados dessa criptomoeda agora. Tente de novo em instantes.")
    return MA.montar_cripto(m)


# ------------------------------------------------------------------ Cenário econômico (botão da tela inicial) e dados da Home
@app.get("/cenario")
def cenario(q: Quem = Depends(quem)) -> dict:
    """Cenário econômico do Brasil: o mesmo cálculo da página Economia do app antigo (macro_servico, cache de 30 min para todos)."""
    import cenario_api as CA
    import macro_servico as MS

    def ler():
        try:
            return MS.cenario_compartilhado()
        except Exception as e:
            banco.registrar_erro("api.cenario", e)
            return None
    foto = _merc_cache("cenario", 1800, ler)
    if not foto or not foto.get("indicadores"):
        raise HTTPException(424, "Não consegui os indicadores da economia agora. Tente de novo em instantes.")
    return CA.montar(foto)


@app.get("/home")
def home(q: Quem = Depends(quem)) -> dict:
    """O que a tela inicial mostra além do /eu: Pregão Orbit (4 indicadores do Mercado hoje), missões do dia e o último veredito
    do cenário econômico (leitura já gravada, sem consultar as fontes)."""
    import home_game as HG
    import jogar
    import macro_servico as MS
    try:
        prog = ED.normalizar((banco.ler_dados(q.ator, q.email) or {}).get("edu_progresso"))
        miss = HG.resumo_missoes(jogar.resumo(prog)["missoes"])
    except Exception:
        miss = HG.resumo_missoes([])
    try:
        ex = MS.ler_exibicao()
        ger = ((ex or {}).get("snap") or {}).get("geral") or {}
        cen = {"veredito": ger.get("v")} if ger.get("v") else None
    except Exception:
        cen = None
    try:
        from datetime import datetime, timedelta
        agora = _agora_brt()
        fim = datetime.combine(agora.date() + timedelta(days=1), datetime.min.time(), tzinfo=agora.tzinfo)
        meu = banco.cfg_ler(f"dsd|{agora.date().isoformat()}|{banco._h_conta(q.email)}") or {}
        dsd = {"jogou": bool(meu), "terminou": meu.get("nota") is not None, "nota": meu.get("nota"), "termina_em": int((fim - agora).total_seconds())}
    except Exception:
        dsd = None
    try:                                                   # o topo da Home: a melhor divisão entre os dois jogos e a melhor nota do desafio
        import trofeus as TF
        doc = _trof_meu(q)
        jogo = max(TF.JOGOS, key=lambda j: doc[j]["t"])
        comp = {"jogo": jogo, "t": doc[jogo]["t"], "divisao": TF.divisao(doc[jogo]["t"]), "desafio_max": doc.get("dsd_max"),
                "jogos": {j: {"t": doc[j]["t"], "divisao": TF.divisao(doc[j]["t"])} for j in TF.JOGOS}}
        st = _torneio_status()
        t = doc.get("trn") or {}
        trn = {"aberto": st["aberto"], "segundos": st.get("segundos"), "inscrito": bool(t.get("id") == st["id"] and t.get("insc"))}
    except Exception:
        comp, trn = None, None
    try:                                                   # pedidos de amizade esperando resposta (bolinha no botão Amigos)
        import amigos as AM
        pedidos = sum(1 for r in (banco.social_relacoes(q.ator) or {}).values() if r.get("estado") == AM.RECEBIDA)
    except Exception:
        pedidos = 0
    return {"missoes": miss, "cenario": cen, "desafio": dsd, "competicao": comp, "torneio": trn, "amigos": {"pedidos": pedidos}}


@app.get("/home/cotacoes")
def home_cotacoes(q: Quem = Depends(quem)) -> dict:
    """Ibovespa e dólar do dia, à parte da Home: dependem de uma fonte externa que pode demorar ou cair, e a
    primeira tela do app não pode esperar por ela. O app desenha a Home na hora e preenche quando isto chega."""
    import inicio_painel as IP
    try:
        hoje = _merc_cache("hoje", 600, IP.mercado_hoje) or []
    except Exception:
        hoje = []
    return {"hoje": hoje[:4]}


# ------------------------------------------------------------------ Histórico de partidas e Missões
@app.get("/jogos/historico")
def jogos_historico(q: Quem = Depends(quem)) -> dict:
    """Todas as partidas do jogador nos dois jogos (solo e online), da mais nova para a mais antiga (historico_jogos.py)."""
    import battle_dados as BD
    import historico_jogos as HJ
    try:
        trade = banco.sis_estado_ler(q.email, HJ.CHAVE_TRADE)
    except Exception:
        trade = {}
    try:
        placar = J.sanear(banco.jogos_placar_ler(q.ator))
    except Exception:
        placar = {}
    try:
        tk = BD.ler_pessoa(banco, q.email).get("hist") or []
    except Exception:
        tk = []
    return HJ.montar(trade, placar, tk)


@app.get("/missoes")
def missoes(q: Quem = Depends(quem)) -> dict:
    """Todas as missões: as de estudo (do dia e o desafio da semana, jogar.py) e as da carteira (do dia, da semana e especiais,
    wallet_game.py). Só leitura: quem conclui e paga é o próprio jogo, como no app antigo."""
    import jogar
    out = {"estudo": None, "carteira": [], "regra": jogar.REGRA}
    try:
        prog = ED.normalizar((banco.ler_dados(q.ator, q.email) or {}).get("edu_progresso"))
        r = jogar.resumo(prog)
        out["estudo"] = {"dia": r["missoes"], "semana": r["semanal"], "pontos": r["pontos"], "ofensiva": r["ofensiva"], "xp_hoje": r["xp_hoje"]}
    except Exception as e:
        banco.registrar_erro("api.missoes_estudo", e)
    try:
        import wallet_game as W
        res = W.avaliar(q.email, q.conta.get("id"), registrar_visita=False)
        for m in res.get("missoes") or []:
            out["carteira"].append({"id": m.get("id"), "periodo": m.get("periodo"), "nome": m.get("nome"), "descricao": m.get("descricao"),
                                    "objetivo": m.get("objetivo"), "progresso": m.get("progresso") or 0, "meta": m.get("meta") or 1,
                                    "feita": bool(m.get("feita")), "recompensa": m.get("recompensa") or {}})
    except Exception as e:
        banco.registrar_erro("api.missoes_carteira", e)
    return out


# ------------------------------------------------------------------ Eventos e recompensas, e o glossário da Ajuda (atalhos da aba Jogos)
@app.get("/eventos")
def eventos(q: Quem = Depends(quem)) -> dict:
    """Eventos ativos e recompensas (como jogos_app.pagina_eventos do app antigo, só leitura): campanhas de TickerCoins, baú diário,
    baús de progresso, a temporada do Hunter Pass, o desafio da semana e as últimas TickerCoins ganhas. Resgates ficam na Loja."""
    from datetime import datetime, timedelta, timezone
    cid = q.conta.get("id")
    agora = datetime.now(timezone.utc)
    out = {"campanhas": [], "bau": None, "baus_pendentes": 0, "passe": None, "desafio": None, "recompensas": []}
    try:
        for c in TC.config().get("campanhas") or []:
            ini, fim = TC._de_iso(c.get("inicio")), TC._de_iso(c.get("fim"))
            if ini and fim and ini <= agora < fim:
                out["campanhas"].append({"rotulo": str(c.get("rotulo") or "Campanha"), "fim": (fim - timedelta(hours=3)).strftime("%d/%m %H:%M"),
                                         "multiplicador": c.get("multiplicador", 1)})
    except Exception:
        pass
    try:
        out["bau"] = TC.bau_diario(cid)
        out["baus_pendentes"] = sum(1 for el in TC.baus_status(cid, _baus_elegiveis(q)) if not el["aberto"])
    except Exception:
        pass
    try:
        prog = ED.normalizar((banco.ler_dados(q.ator, q.email) or {}).get("edu_progresso"))
        hoje = (agora - timedelta(hours=3)).date()
        pa = PA.estado(JO._jor(prog)["xp_dia"], hoje)
        out["passe"] = {k: pa.get(k) for k in ("rotulo", "dias_restantes", "feitos", "total", "falta", "completo", "xp")}
        out["passe"]["proximo"] = {k: (pa.get("proximo") or {}).get(k) for k in ("nome", "simbolo", "honraria", "xp")} if pa.get("proximo") else None
        import jogar as JG
        d = JG.desafio_semana(prog)
        out["desafio"] = {k: d.get(k) for k in ("titulo", "texto", "atual", "alvo", "ok", "pontos")}
    except Exception:
        pass
    try:
        for r in TC.historico(cid, 40) if cid else []:
            if int(r.get("delta") or 0) > 0:
                out["recompensas"].append({"descricao": str(r.get("descricao") or "Ticker Coins"), "em": str(r.get("criado_em") or "")[:10],
                                           "tc": int(r["delta"])})
            if len(out["recompensas"]) >= 10:
                break
    except Exception:
        pass
    return out


@app.get("/ajuda/glossario")
def ajuda_glossario(q: Quem = Depends(quem)) -> dict:
    """Os termos do glossário central do app (o mesmo dos tooltips do app antigo): o que é e para que serve."""
    import glossario as GL
    return {"termos": [{"termo": k, "oque": v[0], "pra_que": v[1]} for k, v in sorted(GL.GLOSSARIO.items(), key=lambda x: x[0].lower())]}


@app.get("/ajuda/glossario/completo")
def ajuda_glossario_completo(q: Quem = Depends(quem)) -> dict:
    """O mesmo glossário da tela Glossário do Streamlit: glossário do app + indicadores + termos extras + glossário central (nome completo,
    níveis Iniciante/Intermediário/Avançado, fórmula, exemplo, interpretação e limitações). A rota antiga (/ajuda/glossario) continua para os apps antigos."""
    import educacao as ED
    import glossario as GL
    import glossario_central as GC
    out = []
    for it in ED.buscar_glossario("", GL.GLOSSARIO):
        d = {"termo": it["termo"], "definicao": it.get("definicao") or "", "uso": it.get("uso") or "", "formula": it.get("formula") or ""}
        if it.get("relacionados"):
            d["relacionados"] = list(it["relacionados"])
        e = GC.achar(it["central"]) if it.get("central") else None
        if e:
            niveis = {m: [{"r": r, "t": t} for r, t in (GC.explicacao(e["sigla"], m) or {}).get("linhas", [])] for m in ("iniciante", "intermediario", "avancado")}
            d["central"] = {"pt": e["pt"], "en": e["en"], "alias": list(e["alias"]),
                            "classes": ([GC.CLASSE_ROTULO[c] for c in e["classes"]] if len(e["classes"]) < len(GC.CLASSES) else ["Todas as classes de ativos"]), "niveis": niveis}
        out.append(d)
    return {"termos": out}


# ------------------------------------------------------------------ Social (atalho Amigos da aba Jogos): amigos, pedidos, classificação e desafios
# As regras são as do app antigo (amigos.py + banco.py, seção "Amigos"): tudo parte da conta logada, a outra ponta é um hash de conta
# (nunca o e-mail) que só o servidor resolve, e bloqueio esconde os perfis nos dois sentidos.
class SocialAlvo(BaseModel):
    h: str


class SocialPedido(BaseModel):
    usuario: str


class SocialResposta(BaseModel):
    h: str
    aceitar: bool


class SocialDenuncia(BaseModel):
    h: str
    motivo: str
    texto: str = ""


class SocialDesafio(BaseModel):
    h: str
    jogo: str                     # trade | ticker
    corrida: str | None = None    # só no Trade Battle (padrão: a primeira duração do jogo)


def _social_erro(fn, *a):
    import amigos as AM
    try:
        return fn(*a)
    except (AM.ErroAmigos, ValueError) as e:
        raise HTTPException(400, str(e) or "Pedido inválido.")
    except banco.SemPermissao as e:
        raise HTTPException(403, str(e))


def _social_cartao(h: str, email: str, doc: dict, placares: dict, ativos: dict, amigo: bool) -> dict | None:
    """Linha da lista: nome, @usuario, avatar, nível (se mostra), atividade (só amigos) e o placar dos dois jogos (se mostra)."""
    import amigos as AM
    import perfis as PF
    from datetime import datetime, timezone
    p = PF.sanear(doc)
    if not p["usuario"]:
        return None
    pv = p["privacidade"]
    x = {"h": h, "usuario": p["usuario"], "nome": p["nome"] or p["usuario"], "avatar_img": _avatar_img(p["avatar"] if p["avatar"] != PF.FOTO else PF.AVATAR_PADRAO)}
    if pv["mostrar_nivel"]:
        try:
            x["nivel"] = NV.nivel_de(PF.progresso((banco.sis_dados_de(email) or {}).get("edu_progresso"))["xp"])
        except Exception:
            x["nivel"] = None
    if amigo:
        x["atividade"] = AM.atividade(ativos.get(email), datetime.now(timezone.utc))
    if pv["mostrar_jogos"]:
        d = J.sanear(placares.get(email))
        x["trade"] = {"pts": d[J.TRADE]["pts"], "vitorias": d[J.TRADE]["vitorias"], "partidas": d[J.TRADE]["partidas"]}
        x["ticker"] = {"v": d[J.TICKER]["v"], "e": d[J.TICKER]["e"], "d": d[J.TICKER]["d"]}
    return x


@app.get("/social")
def social(q: Quem = Depends(quem)) -> dict:
    """Tudo da tela Social: eu, amigos (com atividade e placar), pedidos recebidos e enviados e convites para jogar ainda válidos."""
    import amigos as AM
    from datetime import datetime, timedelta, timezone
    a = q.ator
    rel = _social_erro(banco.social_relacoes, a)
    mapa = banco.sis_perfis_por_hash()
    placares = {r["email"]: r["dados"] for r in banco.sis_comp_todos(J.CH_PLACAR, cache_s=15)}
    try:
        ativos = banco.sis_ativos_desde((datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds"))
    except Exception:
        ativos = {}
    eu_h = banco._h_conta(q.email)
    out = {"eu": None, "amigos": [], "recebidos": [], "enviados": [], "convites": []}
    import trofeus as TF
    meu_trof = _trof_doc(q.email)
    if eu_h in mapa:
        out["eu"] = _social_cartao(eu_h, q.email, mapa[eu_h][1], placares, ativos, False)
    for h, r in rel.items():
        if h not in mapa:
            continue
        c = _social_cartao(h, mapa[h][0], mapa[h][1], placares, ativos, r["estado"] == AM.AMIGOS)
        if c:
            {AM.AMIGOS: out["amigos"], AM.RECEBIDA: out["recebidos"], AM.ENVIADA: out["enviados"]}[r["estado"]].append(c)
    amigos_h = {x["h"] for x in out["amigos"]}
    riv = TF.rival(meu_trof, amigos_h)
    try:
        todos = {e: d for e, d in _trof_todos() if banco._h_conta(e) in amigos_h or e == q.email}
        coroa = _coroa_semana(q, amigos_h, todos)
    except Exception:
        coroa = None
    for x in out["amigos"]:
        x["h2h"] = meu_trof["h2h"].get(x["h"])
        x["rival"] = x["h"] == riv
        x["coroa"] = x["h"] == coroa
    if out["eu"]:
        out["eu"]["coroa"] = eu_h == coroa
    try:
        for cv in banco.convites_recebidos(a):
            de = next((x for x in out["amigos"] if x["h"] == cv["h"]), None)
            if de:
                out["convites"].append({"h": cv["h"], "usuario": de["usuario"], "nome": de["nome"], "avatar_img": de["avatar_img"],
                                        "jogo": cv["jogo"], "jogo_nome": AM.JOGOS_CONVITE.get(cv["jogo"], cv["jogo"]), "codigo": cv["codigo"]})
    except Exception:
        pass
    return out


@app.get("/social/buscar")
def social_buscar(texto: str = "", q: Quem = Depends(quem)) -> dict:
    """Jogadores pelo nome ou @usuario (sem quem bloqueou ou foi bloqueado, sem perfis invisíveis e sem a própria conta)."""
    import amigos as AM
    import perfis as PF
    t = (texto or "").strip()[:30]
    if len(t.lstrip("@")) < 2:
        return {"itens": []}
    a = q.ator
    eu = banco._h_conta(q.email)
    rel = _social_erro(banco.social_relacoes, a)
    esconder = set(banco.social_bloqueados(a)) | banco.social_bloqueado_por(a) | {eu}
    itens = []
    for h, (email, doc) in banco.sis_perfis_por_hash().items():
        p = PF.sanear(doc)
        if h in esconder or not p["usuario"] or p["privacidade"]["visivel"] == "ninguem":
            continue
        itens.append({"h": h, "usuario": p["usuario"], "nome": p["nome"] or p["usuario"],
                      "avatar_img": _avatar_img(p["avatar"] if p["avatar"] != PF.FOTO else PF.AVATAR_PADRAO),
                      "estado": (rel.get(h) or {}).get("estado")})
    return {"itens": AM.buscar(itens, t)[:15]}


@app.post("/social/pedir")
def social_pedir(d: SocialPedido, q: Quem = Depends(quem)) -> dict:
    r = _social_erro(banco.amigo_pedir, q.ator, d.usuario.strip().lstrip("@"))
    return {"ok": True, "resultado": r, "msg": "Agora vocês são amigos!" if r == "aceito" else "Pedido de amizade enviado."}


@app.post("/social/responder")
def social_responder(d: SocialResposta, q: Quem = Depends(quem)) -> dict:
    if not _social_erro(banco.amigo_responder, q.ator, d.h, d.aceitar):
        raise HTTPException(400, "Esse pedido não existe mais.")
    return {"ok": True}


@app.post("/social/remover")
def social_remover(d: SocialAlvo, q: Quem = Depends(quem)) -> dict:
    """Desfaz a amizade, cancela o pedido enviado ou recusa o recebido."""
    _social_erro(banco.amigo_remover, q.ator, d.h)
    return {"ok": True}


@app.post("/social/bloquear")
def social_bloquear(d: SocialAlvo, q: Quem = Depends(quem)) -> dict:
    _social_erro(banco.bloquear, q.ator, d.h)
    return {"ok": True}


@app.post("/social/denunciar")
def social_denunciar(d: SocialDenuncia, q: Quem = Depends(quem)) -> dict:
    ok = _social_erro(banco.denunciar, q.ator, d.h, d.motivo, d.texto)
    return {"ok": True, "msg": "Denúncia enviada. Obrigado por avisar." if ok else "Você já denunciou este perfil hoje."}


@app.get("/social/perfil/{h}")
def social_perfil(h: str, q: Quem = Depends(quem)) -> dict:
    """Perfil de outro jogador, filtrado pela privacidade dele (perfis.publico; amigos veem mais)."""
    import amigos as AM
    import perfis as PF
    par = banco.sis_perfis_por_hash().get(str(h))
    if not par:
        raise HTTPException(404, "Jogador não encontrado.")
    email, doc = par
    alvo = _social_erro(banco.perfil_alvo, q.ator, PF.sanear(doc)["usuario"])
    if not alvo:
        raise HTTPException(404, "Este perfil não está disponível.")
    amigo = alvo["rel"] == AM.AMIGOS
    p = PF.sanear(doc)
    if not alvo["completo"]:
        return {**PF.restrito(doc), "h": h, "rel": alvo["rel"], "avatar_img": _avatar_img(PF.restrito(doc)["avatar"]), "restrito": True}
    prog = PF.progresso((banco.sis_dados_de(email) or {}).get("edu_progresso"))
    rt = rk = None
    try:
        linhas = banco.sis_comp_todos(J.CH_PLACAR, cache_s=15)
        placar = J.sanear(next((r["dados"] for r in linhas if r["email"] == email), None))
        rt, rk = J.montar_ranking(J.TRADE, linhas, email), J.montar_ranking(J.TICKER, linhas, email)   # posição de quem está sendo visto (igual ao Streamlit)
    except Exception:
        placar = J.sanear(None)
    try:
        desde = (banco.sis_conta_por_email(email) or {}).get("criado_em")
    except Exception:
        desde = ""
    pub = PF.publico(doc, desde, prog, PF.jogos(placar, rt, rk), amigo=amigo, estat=J.estatisticas(placar), historico=PF.historico_publico(placar)) or PF.restrito(doc)
    av = p["avatar"] if p["avatar"] != PF.FOTO else PF.AVATAR_PADRAO
    extra: dict = {}
    if pub.get("xp") is not None:
        import nivel as NV
        ne = NV.estado(pub["xp"])
        extra = {"xp_pct": ne["pct"], "xp_max": bool(ne["maximo"])}        # barra de XP do perfil (o app não recalcula nível)
    return {**{k: v for k, v in pub.items() if k != "foto"}, **extra, "h": h, "rel": alvo["rel"], "avatar_img": _avatar_img(av), "restrito": False}


CHAVE_DESAFIO = "dsf|{de}|{para}"       # o desafio PvP pendente de `de` para `para`: {jogo, id} da partida escondida
DESAFIO_VALIDO_S = 180                   # quem desafia espera no máximo 3 minutos


@app.post("/social/desafiar")
def social_desafiar(d: SocialDesafio, q: Quem = Depends(quem)) -> dict:
    """Desafio PvP direto: cria a partida online escondida (o mesmo motor da sala privada, sem código na tela) e manda o convite ao
    amigo. Quem desafia espera em GET /social/desafio; quando o amigo aceita, a partida começa sozinha para os dois."""
    import amigos as AM
    rel = (_social_erro(banco.social_relacoes, q.ator).get(d.h) or {}).get("estado")
    if rel != AM.AMIGOS:
        raise HTTPException(400, "Você só pode desafiar amigos.")
    if d.jogo == "trade":
        corrida = d.corrida if d.corrida in TB.CORRIDAS else NovaSala().corrida
        s = _sala(OL.criar_sala, q.email, TB.CORRIDAS[corrida]["tf"], _agora(), TB.FORMATO_PADRAO, corrida)
    elif d.jogo == "ticker":
        import battle_online_dados as BOD
        s = _tk_on(BOD.criar_sala, q.email)
    else:
        raise HTTPException(400, "Jogo inválido.")
    sid, cod = s.get("id"), s.get("codigo") or ""
    if not cod:
        raise HTTPException(400, "Você já está em uma partida em andamento. Termine ou saia dela para desafiar.")
    _social_erro(banco.convite_jogo_enviar, q.ator, d.h, d.jogo, cod)
    banco.cfg_gravar(CHAVE_DESAFIO.format(de=banco._h_conta(q.email), para=d.h), {"jogo": d.jogo, "id": sid, "em": time.time()})
    return {"jogo": d.jogo, "id": sid}


def _desafio_fase(jogo: str, pid: str, email: str) -> str:
    """'aguardando' (ninguém entrou ainda), 'comecou' (a partida está valendo) ou 'cancelada'."""
    if jogo == "trade":
        b = _sala(OL.ler, pid, email, _agora())
        if b.get("estado") == "cancelada":
            return "cancelada"
        return "comecou" if b.get("estado") == "jogo" else "aguardando"
    import battle_online_dados as BOD
    v = _tk_on(BOD.ler, pid, email)
    f = v.get("fase")
    return "aguardando" if f == "aguardando" else ("cancelada" if f == "cancelada" else "comecou")


@app.get("/social/desafio")
def social_desafio(h: str, q: Quem = Depends(quem)) -> dict:
    """Situação do desafio que a conta logada mandou para `h`: aguardando, aceito (a partida começou), recusado ou expirado."""
    eu = banco._h_conta(q.email)
    dsf = banco.cfg_ler(CHAVE_DESAFIO.format(de=eu, para=_social_erro(banco._hash_ok, h))) or {}
    if not dsf.get("id"):
        return {"estado": "expirado"}
    if dsf.get("recusado"):
        return {"estado": "recusado", "jogo": dsf["jogo"], "id": dsf["id"]}
    fase = _desafio_fase(dsf["jogo"], dsf["id"], q.email)
    if fase == "comecou":
        return {"estado": "aceito", "jogo": dsf["jogo"], "id": dsf["id"]}
    if fase == "cancelada" or time.time() - float(dsf.get("em") or 0) > DESAFIO_VALIDO_S:
        return {"estado": "expirado", "jogo": dsf["jogo"], "id": dsf["id"]}
    return {"estado": "aguardando", "jogo": dsf["jogo"], "id": dsf["id"], "resta": max(0, int(DESAFIO_VALIDO_S - (time.time() - float(dsf.get("em") or 0))))}


@app.post("/social/desafio/cancelar")
def social_desafio_cancelar(d: SocialAlvo, q: Quem = Depends(quem)) -> dict:
    """Quem desafiou desiste (ou o tempo acabou): fecha a partida escondida e apaga o convite."""
    eu, outro = banco._h_conta(q.email), _social_erro(banco._hash_ok, d.h)
    chave = CHAVE_DESAFIO.format(de=eu, para=outro)
    dsf = banco.cfg_ler(chave) or {}
    if dsf.get("id"):
        try:
            if _desafio_fase(dsf["jogo"], dsf["id"], q.email) == "aguardando":
                if dsf["jogo"] == "trade":
                    _sala(OL.sair, dsf["id"], q.email, _agora())
                else:
                    import battle_online_dados as BOD
                    _tk_on(BOD.sair, dsf["id"], q.email)
        except HTTPException:
            pass
    banco.cfg_apagar(chave)
    banco.cfg_apagar(f"cvj|{outro}|{eu}")
    return {"ok": True}


@app.post("/social/convite/entrar")
def social_convite_entrar(d: SocialAlvo, q: Quem = Depends(quem)) -> dict:
    """Aceitar o desafio: entra na partida do amigo e ela começa na hora para os dois (sem sala de espera nem código)."""
    cv = next((c for c in _social_erro(banco.convites_recebidos, q.ator) if c["h"] == d.h), None)
    if not cv:
        raise HTTPException(400, "Esse desafio expirou.")
    try:
        if cv["jogo"] == "trade":
            s = _sala(OL.entrar_na_sala, q.email, cv["codigo"], _agora())
            criador = (((OL._row(s["id"]) or {}).get("dados") or {}).get("sala") or {}).get("criador")
            _sala(OL.iniciar, s["id"], criador, _agora())
        else:
            import battle_online_dados as BOD
            s = _tk_on(BOD.entrar_na_sala, q.email, cv["codigo"])
            dados = (BOD._partida_row(s["id"]) or {}).get("dados") or {}
            for e in (q.email, ((dados.get("jog") or {}).get("a") or {}).get("email")):
                if e:
                    _tk_on(BOD.estou_pronto, s["id"], e)
    finally:
        banco.convite_apagar(q.ator, d.h)
    return {"jogo": cv["jogo"], "id": s.get("id")}


@app.post("/social/convite/recusar")
def social_convite_recusar(d: SocialAlvo, q: Quem = Depends(quem)) -> dict:
    """Recusar o desafio: avisa quem desafiou (que está esperando) e apaga o convite."""
    eu, de = banco._h_conta(q.email), _social_erro(banco._hash_ok, d.h)
    chave = CHAVE_DESAFIO.format(de=de, para=eu)
    dsf = banco.cfg_ler(chave)
    if dsf:
        banco.cfg_gravar(chave, {**dsf, "recusado": True})
    _social_erro(banco.convite_apagar, q.ator, d.h)
    return {"ok": True}


# ------------------------------------------------------------------ Desafio do dia (desafio_dia.py): o mesmo gráfico para todos, 1 tentativa
CHAVE_DSD_CEN = "dsd_cen|{dia}"             # o gráfico do dia (fixado na primeira consulta: muda nada se entrarem gráficos novos)
CHAVE_DSD = "dsd|{dia}|{h}"                 # a tentativa de cada conta: {email, pid, inicio, nota?, fim?}


def _dsd_dia(delta: int = 0) -> str:
    from datetime import timedelta
    return (_agora_brt() + timedelta(days=delta)).date().isoformat()


def _dsd_cenario(dia: str) -> dict:
    import desafio_dia as DD
    ref = banco.cfg_ler(CHAVE_DSD_CEN.format(dia=dia))
    if ref:
        cen = TD.resolver(ref)
        if cen:
            return cen
    sem = DD.semente(dia)
    cen = TD.escolher_corrida(DD.CORRIDA, sem)
    try:
        banco._cfg_inserir(CHAVE_DSD_CEN.format(dia=dia), TD.referencia_corrida(cen, sem))
    except banco.Duplicado:                                   # outra pessoa fixou o gráfico ao mesmo tempo: vale o dela
        return TD.resolver(banco.cfg_ler(CHAVE_DSD_CEN.format(dia=dia)))
    return cen


def _dsd_resultados(dia: str) -> list[dict]:
    try:
        return [r["dados"] for r in banco._cfg_prefixo(f"dsd|{dia}|", 5000)]
    except Exception:
        return []


def _desafio_nota(q: "Quem", dia: str, pid: str, fz: dict) -> None:
    try:
        meu = next(x for x in fz["placar"] if x["voce"])
        chave = CHAVE_DSD.format(dia=dia, h=banco._h_conta(q.email))
        r = banco.cfg_ler(chave) or {}
        if r.get("pid") == pid and r.get("nota") is None:
            nota = round(float(meu["pontos"]), 1)
            banco.cfg_gravar(chave, {**r, "nota": nota, "fim": time.strftime("%Y-%m-%dT%H:%M:%S")})
            doc = _trof_meu(q)
            if nota > float(doc.get("dsd_max", float("-inf"))):
                doc["dsd_max"] = nota
                banco.sis_estado_gravar(q.email, CHAVE_TROFEUS, doc)
    except Exception as e:
        banco.registrar_erro("api.desafio_nota", e)


def _dsd_ranking(q: "Quem", dia: str, filtro: str = "geral") -> dict:
    import desafio_dia as DD
    todos = DD.ordenar(_dsd_resultados(dia))
    perfis = _rk_perfis()
    amigos = _rk_amigos(q) if filtro == "amigos" else None
    linhas = []
    for r in todos:
        e = r.get("email") or ""
        if amigos is not None and e != q.email and banco._h_conta(e) not in amigos:
            continue
        linhas.append(_rk_linha(r["pos"], e, perfis, q.email, r["nota"]))
    return {"total": len(todos), "linhas": linhas[:100], "eu": next((x for x in linhas if x["eu"]), None)}


def _dsd_pagar_ontem(q: "Quem") -> dict | None:
    """Prêmio do desafio de ontem para quem terminou, pago uma vez (a chave do crédito impede pagar de novo)."""
    import desafio_dia as DD
    ontem = _dsd_dia(-1)
    try:
        eu = next((r for r in DD.ordenar(_dsd_resultados(ontem)) if r.get("email") == q.email), None)
        pr = DD.premio(eu["pos"]) if eu else None
        if not pr:
            return None
        lin = TC.creditar(q.conta.get("id"), pr["tc"], "bonus:desafio_dia", f"Desafio do dia {ontem}: {pr['rotulo']}",
                          f"dsd:{q.conta.get('id')}:{ontem}", ontem)
        return {**pr, "dia": ontem, "pos": eu["pos"], "novo": not (lin or {}).get("duplicado")}
    except Exception as e:
        banco.registrar_erro("api.desafio_premio", e)
        return None


@app.get("/desafio")
def desafio(q: Quem = Depends(quem)) -> dict:
    """Tela do Desafio do dia: quanto falta, quantos jogaram, se você já jogou (e sua nota e posição), o top 3 de ontem,
    a tabela de prêmios e o prêmio de ontem (pago aqui, uma vez)."""
    import desafio_dia as DD
    from datetime import datetime, timedelta
    dia = _dsd_dia()
    agora = _agora_brt()
    fim = datetime.combine(agora.date() + timedelta(days=1), datetime.min.time(), tzinfo=agora.tzinfo)
    res = _dsd_resultados(dia)
    meu = banco.cfg_ler(CHAVE_DSD.format(dia=dia, h=banco._h_conta(q.email))) or None
    rk = _dsd_ranking(q, dia)
    ontem = _dsd_ranking(q, _dsd_dia(-1))
    return {"dia": dia, "termina_em": int((fim - agora).total_seconds()), "jogaram": len(res),
            "meu": ({"pid": meu.get("pid"), "nota": meu.get("nota"), "terminou": meu.get("nota") is not None,
                     "pos": (rk.get("eu") or {}).get("pos"), "de": rk["total"]} if meu else None),
            "top_ontem": ontem["linhas"][:3], "premios": DD.tabela_premios(), "premio_ontem": _dsd_pagar_ontem(q)}


@app.post("/desafio/jogar")
def desafio_jogar(q: Quem = Depends(quem)) -> dict:
    """Começa a única tentativa do dia (já conta como tentativa). Volta a mesma partida se ela ainda não acabou."""
    import desafio_dia as DD
    dia = _dsd_dia()
    chave = CHAVE_DSD.format(dia=dia, h=banco._h_conta(q.email))
    feito = banco.cfg_ler(chave)
    if feito:
        if feito.get("nota") is None and feito.get("pid"):
            try:
                return _com_solo(q, feito["pid"], lambda d, p, cen, m: _estado_solo(q, feito["pid"], d, p, cen, m))
            except HTTPException:
                pass
        raise HTTPException(409, "Você já jogou o Desafio do dia hoje. Volte amanhã!")
    try:
        cen = _dsd_cenario(dia)
        apostas = {q.email: TCA.capital_corrida(q.email, q.conta.get("id"))}
        pid = uuid.uuid4().hex[:10]
        p = TB.nova_partida(cen, cen["tf"], [q.email], _agora(), pid=pid, apostas=apostas, corrida=DD.CORRIDA)
    except TCA.SemSaldo as e:
        _erro(e, 409)
    except TB.ErroTrader as e:
        _erro(e, 409)
    try:
        banco._cfg_inserir(chave, {"email": q.email, "pid": pid, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S")})
    except banco.Duplicado:
        raise HTTPException(409, "Você já jogou o Desafio do dia hoje. Volte amanhã!")
    reg = {"p": p, "cen": TD.referencia_corrida(cen, DD.semente(dia)), "estado": {}, "desafio": dia}
    return _estado_solo(q, pid, reg, p, cen)


@app.get("/desafio/ranking")
def desafio_ranking(dia: str | None = None, filtro: str = "geral", q: Quem = Depends(quem)) -> dict:
    d = dia if dia in (_dsd_dia(), _dsd_dia(-1)) else _dsd_dia()
    return {"dia": d, **_dsd_ranking(q, d, filtro), "hora": _agora_brt().strftime("%H:%M")}


# ------------------------------------------------------------------ ranking semanal entre amigos (com a coroa) e torneio de fim de semana
def _trof_todos() -> list[tuple[str, dict]]:
    import trofeus as TF
    temp = _temporada()
    out = []
    try:
        for r in banco.sis_comp_todos(CHAVE_TROFEUS, cache_s=15):
            out.append((r["email"], TF.sanear(r["dados"], temp)[0]))
    except Exception:
        pass
    return out


def _coroa_semana(q: "Quem", amigos_h: set[str], docs: dict) -> str | None:
    """Hash do 1º da semana PASSADA entre você e seus amigos (quem usa a coroa nesta semana). Precisa de saldo positivo."""
    import trofeus as TF
    from datetime import timedelta
    passada = TF.semana_id(_agora_brt().date() - timedelta(days=7))
    melhor, pts = None, 0
    for email, d in docs.items():
        h = banco._h_conta(email)
        if email != q.email and h not in amigos_h:
            continue
        p = TF.pontos_semana_passada(d, passada)
        if p is not None and p > pts:
            melhor, pts = h, p
    return melhor


def _ranking_semana(q: "Quem", perfis: dict) -> dict:
    """Você e seus amigos pelo saldo de troféus desta semana (os dois jogos). Zera toda segunda; o 1º da semana passada usa a coroa."""
    import trofeus as TF
    sem = TF.semana_id(_agora_brt().date())
    amigos = _rk_amigos(q) or set()
    docs = {e: d for e, d in _trof_todos() if e == q.email or banco._h_conta(e) in amigos}
    docs.setdefault(q.email, _trof_doc(q.email))
    coroa = _coroa_semana(q, amigos, docs)
    linhas = sorted(((TF.pontos_semana(d, sem), e) for e, d in docs.items()), key=lambda x: (-x[0], x[1]))
    saida = [_rk_linha(i, e, perfis, q.email, p, {"coroa": banco._h_conta(e) == coroa}) for i, (p, e) in enumerate(linhas, 1)]
    from datetime import timedelta
    hoje = _agora_brt().date()
    return {"jogo": "semana", "nome": "Semana dos amigos", "total": len(saida), "linhas": saida, "eu": next((x for x in saida if x["eu"]), None),
            "unidade": "troféus na semana", "zera_em_dias": 7 - hoje.weekday(), "hora": _agora_brt().strftime("%H:%M")}


def _torneio_status() -> dict:
    """O torneio atual (aberto de sexta a domingo) ou o próximo, com quanto falta para abrir ou fechar."""
    import trofeus as TF
    from datetime import datetime, timedelta
    agora = _agora_brt()
    hoje = agora.date()
    tid = TF.torneio_id(hoje)
    if tid:
        fim = datetime.combine(date_from_iso(tid) + timedelta(days=3), datetime.min.time(), tzinfo=agora.tzinfo)
        return {"id": tid, "aberto": True, "segundos": int((fim - agora).total_seconds())}
    sexta = hoje + timedelta(days=(4 - hoje.weekday()) % 7)
    ini = datetime.combine(sexta, datetime.min.time(), tzinfo=agora.tzinfo)
    return {"id": sexta.isoformat(), "aberto": False, "segundos": int((ini - agora).total_seconds())}


def date_from_iso(s: str):
    from datetime import date
    return date.fromisoformat(s)


def _torneio_classificacao(tid: str) -> list[tuple[int, str]]:
    import trofeus as TF
    out = []
    for e, d in _trof_todos():
        t = d.get("trn") or {}
        if t.get("id") == tid and t.get("insc"):
            out.append((TF.pontos_torneio(t), e))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out


def _ranking_torneio(q: "Quem", perfis: dict, ok) -> dict:
    st = _torneio_status()
    cl = [(p, e) for p, e in _torneio_classificacao(st["id"]) if ok(e)]
    saida = [_rk_linha(i, e, perfis, q.email, p) for i, (p, e) in enumerate(cl, 1)]
    return {"jogo": "torneio", "nome": "Torneio de fim de semana", "total": len(saida), "linhas": saida[:100], "eu": next((x for x in saida if x["eu"]), None),
            "unidade": "pontos", "hora": _agora_brt().strftime("%H:%M")}


def _torneio_premio_anterior(q: "Quem") -> dict | None:
    """Prêmio do torneio do fim de semana passado para o top 3, pago uma vez (a chave do crédito impede pagar de novo)."""
    import trofeus as TF
    from datetime import timedelta
    hoje = _agora_brt().date()
    sexta_passada = hoje - timedelta(days=(hoje.weekday() - 4) % 7 or 7)
    tid = sexta_passada.isoformat()
    if TF.torneio_id(hoje) == tid:                         # ainda é o fim de semana dele: nada a pagar
        return None
    cl = _torneio_classificacao(tid)
    pos = next((i for i, (p, e) in enumerate(cl, 1) if e == q.email and p > 0), None)
    if not pos or pos > len(TF.TORNEIO_PREMIOS):
        return None
    tc = TF.TORNEIO_PREMIOS[pos - 1]
    try:
        lin = TC.creditar(q.conta.get("id"), tc, "bonus:torneio", f"Torneio de fim de semana {tid}: {pos}º lugar", f"trn:{q.conta.get('id')}:{tid}", tid)
        return {"id": tid, "pos": pos, "tc": tc, "novo": not (lin or {}).get("duplicado")}
    except Exception as e:
        banco.registrar_erro("api.torneio_premio", e)
        return None


@app.get("/torneio")
def torneio(q: Quem = Depends(quem)) -> dict:
    """Torneio de fim de semana: aberto de sexta a domingo, para quem se inscreve. Valem as 5 melhores partidas online (troféus
    ganhos em cada uma; perder não tira pontos). Top 3 ganha TC na segunda."""
    import trofeus as TF
    st = _torneio_status()
    doc = _trof_meu(q)
    t = doc.get("trn") or {}
    meu = t if t.get("id") == st["id"] else {}
    rk = _ranking_torneio(q, _rk_perfis(), lambda e: True)
    return {**st, "inscrito": bool(meu.get("insc")), "pontos": TF.pontos_torneio(meu), "partidas": len(meu.get("jogos") or []),
            "melhores": sorted((max(0, int(x)) for x in (meu.get("jogos") or [])), reverse=True)[:TF.TORNEIO_PARTIDAS],
            "conta": TF.TORNEIO_PARTIDAS, "premios": list(TF.TORNEIO_PREMIOS), "inscritos": rk["total"], "top": rk["linhas"][:10], "eu": rk["eu"],
            "premio_anterior": _torneio_premio_anterior(q)}


@app.post("/torneio/inscrever")
def torneio_inscrever(q: Quem = Depends(quem)) -> dict:
    import trofeus as TF
    st = _torneio_status()
    if not st["aberto"]:
        raise HTTPException(400, "As inscrições abrem na sexta-feira.")
    doc = _trof_meu(q)
    TF.inscrever(doc, st["id"])
    banco.sis_estado_gravar(q.email, CHAVE_TROFEUS, doc)
    return {"ok": True}


@app.post("/social/revanche")
def social_revanche(d: SocialAlvo, jogo: str = "ticker", q: Quem = Depends(quem)) -> dict:
    """Revanche: o mesmo desafio PvP direto de /social/desafiar, para o adversário da última partida (só entre amigos)."""
    return social_desafiar(SocialDesafio(h=d.h, jogo=jogo), q)


# ------------------------------------------------------------------ Carteira: extrato de operações e conquistas (atalhos "Mais da sua carteira")
@app.get("/carteira/historico")
def carteira_historico(q: Quem = Depends(quem)) -> dict:
    """Extrato da carteira virtual (o mesmo 'ext' do app antigo): compras, vendas, proventos, desdobramentos e ordens recusadas,
    do mais novo para o mais antigo, com o nome e o logo de cada ativo."""
    import ativos_jogo as A
    est = banco.comp_carteira_ler(q.ator) or {}
    itens = []
    for x in reversed((est.get("ext") or [])[-200:]):
        if not isinstance(x, dict):
            continue
        tk = str(x.get("t") or "")
        try:
            rot = A.rotulo(tk)
        except Exception:
            rot = tk
        itens.append({**{k: x.get(k) for k in ("d", "tipo", "t", "q", "p", "v", "r", "m")}, "rotulo": rot, "logo": _logo_ativo(tk)})
    compras = sum(1 for x in itens if x["tipo"] in ("compra", "aporte"))
    vendas = [x for x in itens if x["tipo"] == "venda"]
    return {"itens": itens, "resumo": {"compras": compras, "vendas": len(vendas), "resultado_vendas": round(sum(float(x.get("r") or 0) for x in vendas), 2),
                                        "proventos": round(sum(float(x.get("v") or 0) for x in itens if x["tipo"] == "provento"), 2)}}


@app.get("/carteira/conquistas")
def carteira_conquistas(q: Quem = Depends(quem)) -> dict:
    """Conquistas da carteira (wallet_game do app antigo): as desbloqueadas com a data e as que faltam, com a recompensa."""
    try:
        import wallet_game as W
        res = W.avaliar(q.email, q.conta.get("id"), registrar_visita=False)
        cs = [{k: c.get(k) for k in ("id", "nome", "descricao", "emblema", "cor", "recompensa", "desbloqueada_em")} for c in res.get("conquistas") or []]
    except Exception as e:
        banco.registrar_erro("api.carteira_conquistas", e)
        cs = []
    return {"itens": cs, "ok": sum(1 for c in cs if c.get("desbloqueada_em")), "total": len(cs)}


# ------------------------------------------------------------------ Tour guiado do primeiro acesso (tour.py)
CHAVE_TOUR = "tour"


class TourPasso(BaseModel):
    passo: int | None = None
    marco: str | None = None
    pular: bool = False
    reiniciar: bool = False


def _tour_marco_ok(q: "Quem", marco: str) -> bool:
    """Confere no servidor os marcos que dá para conferir: aprender (uma lição feita) e comprar (uma compra na carteira)."""
    try:
        if marco == "aprender":
            prog = ED.normalizar((banco.ler_dados(q.ator, q.email) or {}).get("edu_progresso"))
            return bool(JO._jor(prog)["licoes"])
        if marco == "comprar":
            est = banco.comp_carteira_ler(q.ator) or {}
            return any(isinstance(x, dict) and x.get("tipo") == "compra" for x in (est.get("ext") or [])) or bool(est.get("pos"))
    except Exception as e:
        banco.registrar_erro("api.tour_marco", e)
        return False
    return True


@app.get("/tour")
def tour_estado(q: Quem = Depends(quem)) -> dict:
    """Onde o jogador parou no tour, os marcos cumpridos e os prêmios de cada marco."""
    import tour as TO
    doc = TO.sanear(banco.sis_estado_ler(q.email, CHAVE_TOUR))
    return {**doc, "ativo": TO.ativo(doc), "premios": TO.PREMIOS}


@app.post("/tour")
def tour_passo(d: TourPasso, q: Quem = Depends(quem)) -> dict:
    """Guarda o passo do tour; cumpre um marco (pagando o prêmio uma vez); pula ou recomeça o tour."""
    import tour as TO
    doc = banco.sis_estado_ler(q.email, CHAVE_TOUR)
    ganho = 0
    if d.reiniciar:
        doc = TO.reiniciar(doc)
    elif d.pular:
        doc = TO.pular(doc)
    else:
        if d.marco is not None and d.marco not in TO.PREMIOS:
            raise HTTPException(400, "Marco inválido.")
        if d.marco is not None and not _tour_marco_ok(q, d.marco):
            raise HTTPException(409, "Esse passo ainda não foi feito.")
        doc, ganho = TO.avancar(doc, d.passo, d.marco)
        if ganho:
            try:
                TC.creditar(q.conta.get("id"), ganho, "bonus:tour", f"Tour do primeiro acesso: {d.marco}", f"tour:{q.conta.get('id')}:{d.marco}", d.marco)
            except Exception as e:
                banco.registrar_erro("api.tour_premio", e)
                ganho = 0
    doc = TO.sanear(doc)
    banco.sis_estado_gravar(q.email, CHAVE_TOUR, doc)
    return {**doc, "ativo": TO.ativo(doc), "tc": ganho}
