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
    try:
        s = TC.saldo(cid)
    except Exception as e:
        _erro(e, 503)
    possui = {b["produto_id"] for b in TC.beneficios_ativos(cid)}
    eq = TC.equipado(q.email)
    plano = _plano_de(q)
    itens = []
    for p in TC.produtos():
        stt = VT.status(p, possui, eq, s, hoje)
        ok = TC.pode_comprar(cid, p["id"], plano)[0]
        if not (stt["tem"] or ok):
            continue
        kind = (p.get("efeito") or {}).get("kind")
        if kind not in KINDS_LOJA:
            continue
        itens.append({"id": p["id"], "nome": p["nome"], "desc": p.get("desc") or "", "preco": int(p["preco"]), "raridade": VT.raridade(p),
                      "status": stt, "kind": kind, "equipavel": VT.equipavel(p), "em_uso": eq.get(kind) == p["id"], "previa": VT.previa(p)})
    itens.sort(key=lambda x: (x["status"]["tem"], x["preco"]))
    bau = TC.bau_diario(cid)
    pend = [{"indice": i, "rotulo": el.get("rotulo", "Baú"), "raridade": el.get("raridade")}
            for i, el in enumerate(TC.baus_status(cid, _baus_elegiveis(q))) if not el["aberto"]]
    compras = [{"nome": (TC.produto(x["produto_id"]) or {}).get("nome", x["produto_id"]), "preco": int(x["preco"]),
                "quando": _fmt_quando(x["criado_em"]), "estado": TC.ROTULO_ESTADO.get(x["estado"], x["estado"])} for x in TC.compras(cid, 20)]
    hist = [{"descricao": x["descricao"] or x["origem"], "delta": int(x["delta"]), "pendente": x["estado"] == "pendente",
             "quando": _fmt_quando(x["criado_em"]), "estado": TC.ROTULO_ESTADO.get(x["estado"], x["estado"]), "saldo_apos": int(x["saldo_apos"])}
            for x in TC.historico(cid, 60)]
    benef = [{"nome": (TC.produto(x["produto_id"]) or {}).get("nome", x["produto_id"]),
              "validade": "Permanente" if not x.get("expira_em") else f"até {_fmt_quando(x['expira_em'])}"} for x in TC.beneficios_ativos(cid)]
    return {"saldo": s, "bau": bau, "baus": pend, "itens": itens, "compras": compras, "totais": TC.totais(cid), "historico": hist, "beneficios": benef}


@app.post("/loja/bau")
def loja_bau(q: Quem = Depends(quem)) -> dict:
    """Abre o baú diário (uma vez por dia; o servidor sorteia e credita)."""
    try:
        return TC.abrir_bau_diario(q.conta.get("id"))
    except TC.ErroTC as e:
        _erro(e)


@app.post("/loja/bau/{indice}")
def loja_bau_progresso(indice: int, q: Quem = Depends(quem)) -> dict:
    """Abre um baú de progresso (marco do passe ou semana de ofensiva). Uma vez por baú."""
    lista = _baus_elegiveis(q)
    if not 0 <= indice < len(lista):
        raise HTTPException(404, "Baú não encontrado.")
    try:
        return {**TC.abrir_bau(q.conta.get("id"), lista[indice]), "rotulo": lista[indice].get("rotulo", "Baú")}
    except TC.ErroTC as e:
        _erro(e)


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
        return J.montar_ranking(jogo, banco.sis_comp_todos(J.CH_PLACAR), q.email, metrica=metrica)
    except ValueError as e:
        _erro(e)


@app.get("/ranking/{jogo}/tela")
def ranking_tela(jogo: str, q: Quem = Depends(quem)) -> dict:
    """Tela Ranking Geral, igual à do app antigo (jogos_app.pagina_ranking): pódio, sua posição e a classificação (até 50),
    com o nome do perfil, o avatar equipado e a variação de posição desde o início do dia. Nunca envia e-mail."""
    import perfis as PF
    if jogo not in J.JOGOS:
        raise HTTPException(404, "jogo desconhecido")
    try:
        placares = banco.sis_comp_todos(J.CH_PLACAR)
    except Exception as e:
        _erro(e, 503)
    rk = J.montar_ranking(jogo, placares, q.email)
    try:                                                   # variação do dia: mesma base guardada que o app antigo usa
        hoje = _agora_brt().date().isoformat()
        chave = f"jogos_rk|{jogo}"
        base, novo = J.base_do_dia(banco.cfg_ler(chave), hoje, rk)
        if novo:
            banco.cfg_gravar(chave, novo)
        rk = J.montar_ranking(jogo, placares, q.email, base)
    except Exception as e:
        banco.registrar_erro("api.ranking_base", e)
    email_de = {J.hash_conta(r.get("email", "")): r.get("email", "") for r in placares}
    perfis = {}
    try:
        for r in banco.sis_comp_todos("perfil_jogador"):
            perfis[r["email"]] = PF.sanear(r["dados"])
    except Exception:
        perfis = {}

    def linha(x: dict) -> dict:
        p = perfis.get(email_de.get(x["h"], "")) or {}
        visivel = (p.get("privacidade") or {}).get("visivel") != "ninguem"
        nome = (p.get("nome") or p.get("usuario")) if (visivel or x["eu"]) else ""
        av = p.get("avatar") if (visivel or x["eu"]) else ""
        return {"pos": x["pos"], "nome": nome or x["apelido"], "valor": x["valor"], "partidas": x.get("partidas", 0), "var": x.get("var"),
                "eu": x["eu"], "avatar_img": _avatar_img(av)}

    linhas = [linha(x) for x in rk["linhas"][:50]]
    return {"jogo": jogo, "nome": J.NOME[jogo], "total": rk["total"], "linhas": linhas, "eu": linha(rk["eu"]) if rk.get("eu") else None,
            "hora": _agora_brt().strftime("%H:%M")}


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
        d["xp_pago"] = _pagar_xp(q, pid, fz.get("xp") or {})
        d["fechada"] = True
    d["p"] = p
    _gravar_solo(q, pid, d)
    args = TG.args_mesa(v, p, d.get("estado") or {}, agora)
    out = {"id": pid, "fase": p["fase"], "tela": args}
    if fim:
        res = (p.get("resultados") or {}).get(TB._chave(1, q.email))
        out["fim"] = {"resultado": res, "revelado": TB.revelacao(p, cen), "final": TB.resumo_final(p, q.email), "xp": d.get("xp_pago")}
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
    marcas: dict | None = None          # desenhos da estratégia: níveis com papel, tendências, zonas e notas (avaliados no fim)


@app.post("/trade/solo/{pid}/estrategia")
def trade_solo_estrategia(pid: str, e: Estrategia, q: Quem = Depends(quem)) -> dict:
    d, p, cen = _ler_solo(q, pid)
    ref = cen["candles"][cen["n_analise"] - 1]["c"]
    est = {"direcao": None, "tipo": "aguardar"} if e.direcao in (None, "", "lateral") else {"direcao": e.direcao, "tipo": e.tipo or "continuacao"}
    try:
        TB.salvar_estrategia(p, q.email, est, e.marcas, ref, _agora())     # solo: confirmar já começa o gráfico
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
    """Sala de espera ("sala": código e jogadores), partida ("jogo": o que a mesa desenha, como na partida solo) ou "cancelada".
    No fim: placar dos jogos e XP (uma vez por partida, como no app antigo)."""
    agora = _agora()
    b = _sala(OL.ler, pid, q.email, agora)
    if b.get("estado") != "jogo":
        return b
    v, p = b["v"], b["p"]
    out = {"estado": "jogo", "id": pid, "fase": p["fase"], "tela": TG.args_mesa(v, p, {}, agora)}
    if p["fase"] == "fim" and v.get("final"):
        _registrar_ranking(q, pid, p, v["final"], v.get("resultado"))
        out["fim"] = {"xp": _pagar_xp(q, pid, (v["final"] or {}).get("xp") or {}), "placar": (v["final"] or {}).get("placar")}
    return out


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
    _sala(OL.salvar, pid, q.email, est, e.marcas, _agora())
    return sala_ver(pid, q)


@app.post("/trade/salas/{pid}/acao")
def sala_acao(pid: str, a: Acao, q: Quem = Depends(quem)) -> dict:
    _sala(OL.agir, pid, q.email, TG.acao_de(a.dados), _agora())
    return sala_ver(pid, q)


@app.post("/trade/salas/{pid}/sair")
def sala_sair(pid: str, q: Quem = Depends(quem)) -> dict:
    _sala(OL.sair, pid, q.email, _agora())
    return {"ok": True}


# ------------------------------------------------------------------ Ticker Battle: duelo contra o sistema (mesmas regras de battle.py)
# O duelo fica no banco com as cartas CONGELADAS no início (como no app antigo, onde ficava na sessão). O app só manda "qual carta" e
# "qual indicador"; o servidor escolhe a adversária (regra fixa e pública), compara os valores reais e guarda o histórico.
CHAVE_TICKER = "tk_api|{h}|{id}"
TK_INDICADORES = ("dy_12m", "ret_12m", "vol", "roe", "pl")   # no app novo, só 5 indicadores por carta (os mais didáticos)


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
    out = {"tk": c.get("tk"), "nome": c.get("nome") or c.get("tk"), "classe": c.get("classe"), "categoria": cat["nome"], "cor": cat["cor"],
           "ref": _tk_data(c.get("ref")), "fonte": c.get("fonte") or "", "jogavel": ok, "motivo": mot, "avisos": list(c.get("avisos") or [])}
    if valores:
        ind = c.get("ind") or {}
        out["ind"] = [{"id": i, "v": float(ind[i]), "txt": BT.formatar(i, ind[i])} for i in BT.indicadores_validos(c) if i in TK_INDICADORES]
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
    pes = BD.ler_pessoa(banco, q.email)
    deck = [t for t in pes["deck"] if t in snap]
    ok, msg = BT.validar_baralho(deck, snap, hoje)
    hist = pes["hist"]
    conta = {"vitoria": 0, "derrota": 0, "empate": 0}
    for h in hist:
        if h.get("final") in conta:
            conta[h["final"]] += 1
    cartas = sorted((_tk_carta(c, hoje) for c in snap.values()), key=lambda c: (not c["jogavel"], c["tk"]))
    return {"cartas": cartas, "indicadores": _tk_meta(), "deck": deck, "valido": ok, "msg": msg, "min": BT.BARALHO_MIN, "max": BT.BARALHO_MAX,
            "rodadas": BT.RODADAS, "sugestao": BT.baralho_padrao(snap, hoje), "historico": {**conta, "ultimos": [
                {"id": h.get("id"), "ts": str(h.get("ts") or "")[:16].replace("T", " "), "final": h.get("final"), "placar": h.get("placar")} for h in hist[:5]]}}


class BaralhoTk(BaseModel):
    deck: list[str]


@app.post("/ticker/baralho")
def ticker_baralho(b: BaralhoTk, q: Quem = Depends(quem)) -> dict:
    """Guarda o baralho (só cartas que existem, sem repetir, até o máximo). Devolve se ele já vale para jogar."""
    import battle as BT
    import battle_dados as BD
    hoje = _tk_agora().date()
    snap = _tk_snapshot(False)
    deck = []
    for t in b.deck:
        if t in snap and t not in deck:
            deck.append(t)
    if len(deck) > BT.BARALHO_MAX:
        raise HTTPException(400, f"O baralho aceita no máximo {BT.BARALHO_MAX} cartas.")
    pes = BD.ler_pessoa(banco, q.email)
    if not BD.gravar_pessoa(banco, q.email, {**pes, "deck": deck}):
        raise HTTPException(503, "Não consegui salvar o baralho agora. Tente de novo.")
    ok, msg = BT.validar_baralho(deck, snap, hoje)
    return {"deck": deck, "valido": ok, "msg": msg}


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
    snap = _tk_snapshot(False)
    pes = BD.ler_pessoa(banco, q.email)
    ok, msg = BT.validar_baralho(pes["deck"], snap, hoje)
    if not ok:
        raise HTTPException(400, msg)
    du = BT.novo_duelo(uuid.uuid4().hex[:12], uuid.uuid4().hex, list(pes["deck"]), _tk_agora().replace(tzinfo=None),
                       BD.referencia_dos_dados(snap, list(snap)))
    d = {"duelo": du, "cartas": {t: dict(c) for t, c in snap.items()}}
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
            "indicadores": _tk_meta()}


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


def _pf_prog(q: Quem) -> dict:
    import perfis as PF
    try:
        return PF.progresso((banco.ler_dados(q.ator, q.email) or {}).get("edu_progresso"))
    except Exception:
        return PF.progresso({})


def _pf_loja(q: Quem, tipo: str) -> dict:
    """Itens de `tipo` (moldura ou tema) que a conta possui na Loja e o equipado agora (com a prévia para desenhar)."""
    import loja_vitrine as VT
    try:
        donos = {c["produto_id"] for c in TC.beneficios_ativos(q.conta.get("id"))}
        itens = [{"id": p["id"], "nome": p["nome"], "previa": VT.previa(p)} for p in TC.produtos() if (p.get("efeito") or {}).get("kind") == tipo and p["id"] in donos]
        return {"itens": itens, "equipado": TC.equipado(q.email).get(tipo)}
    except Exception:
        return {"itens": [], "equipado": None}


@app.get("/perfil")
def perfil_meu(q: Quem = Depends(quem)) -> dict:
    """Tela Meu Perfil: nome, usuário, avatar (com raridade e moldura), nível e XP, sequência, ranking, moedas, patrimônio,
    desempenho nos jogos, conquistas, bio, privacidade e o que dá para usar da Loja. Só leitura das fontes reais."""
    import avatares as AV
    import perfis as PF
    a = q.ator
    try:
        doc = PF.sanear(banco.perfil_jogador_ler(a))
    except Exception:
        doc = PF.vazio()
    prog = _pf_prog(q)
    ne = NV.estado(prog["xp"])
    try:
        placar = J.sanear(banco.jogos_placar_ler(a))
    except Exception:
        placar = J.sanear({})
    try:
        linhas = banco.sis_comp_todos(J.CH_PLACAR)
        rt, rk = J.montar_ranking(J.TRADE, linhas, q.email), J.montar_ranking(J.TICKER, linhas, q.email)
    except Exception:
        rt, rk = None, None
    try:
        ofensiva = int(JO.resumo(ED.normalizar((banco.ler_dados(a, q.email) or {}).get("edu_progresso"))).get("ofensiva") or 0)
    except Exception:
        ofensiva = 0
    try:
        moedas = TC.saldo(q.conta.get("id"))
    except Exception:
        moedas = None
    try:
        pat = (TCA.situacao(q.email) or {}).get("patrimonio")
    except Exception:
        pat = None
    av = doc["avatar"] if AV.existe(doc["avatar"]) else PF.AVATAR_PADRAO
    rar = AV.RARIDADES[AV.raridade_de(av)]
    desde = str(q.conta.get("criado_em") or "")[:10]
    return {"nome": doc["nome"] or doc["usuario"] or "Jogador", "usuario": doc["usuario"], "bio": doc["bio"], "desde": desde,
            "avatar": av, "avatar_img": _avatar_img(av), "avatar_nome": AV.POR_ID[av]["nome"], "raridade": {"nome": rar["nome"], "cor": rar["cor"]},
            "nivel": ne, "titulo": prog["titulo"], "xp": prog["xp"], "ofensiva": ofensiva, "moedas": moedas, "patrimonio": pat,
            "ranking": _ranking_da_casa(a, q.email), "jogos": PF.jogos(placar, rt, rk), "estat": J.estatisticas(placar),
            "conquistas": {"ok": prog["conquistas"], "total": prog["conquistas_total"], "medalhas": prog["medalhas"]},
            "privacidade": doc["privacidade"], "moldura": _pf_loja(q, "moldura"), "tema": _pf_loja(q, "tema"),
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
