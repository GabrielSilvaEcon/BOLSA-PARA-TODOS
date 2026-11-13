"""Ticker Battle · dados das cartas e histórico (sem Streamlit).

As cartas NÃO têm dados próprios: os indicadores vêm da infraestrutura que o app já usa (comparador_dados/comparador_desempenho para preço, retorno,
volatilidade e queda máxima; dados.buscar_fundamentus para os fundamentos das ações), todos já protegidos pelo cache central e pelos limitadores.
O resultado fica num SNAPSHOT compartilhado no banco (config_sistema, chave `battle_cartas`): quem abre o Battle depois de 24 h atualiza só as cartas
vencidas (poucas por vez) e todos os outros jogadores reaproveitam. Nenhuma rodada nem partida consulta a rede: as disputas leem o snapshot.
Falha de uma fonte = a carta fica sem aquele indicador (nunca valor inventado).
Histórico e baralho de cada pessoa: monitor_estado (chave `battle`), com a mesma persistência das demais contas.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pandas as pd

import ativos_jogo as A
import battle as B

CH_SNAPSHOT = "battle_cartas"
CH_PESSOA = "battle"
VALIDADE_H = 24
VALIDADE_FALHA_H = 1
LOTE_ATUALIZACAO = 6              # cartas atualizadas por abertura de tela (o resto continua na próxima)
MAX_HISTORICO = 30
MIN_PREGOES = 120                 # menos que isso em 12 meses: sem indicadores de preço

CATEGORIAS_ATIVAS = ("acao",)     # por enquanto só ações, que têm arte de carta; FIIs, ETFs e cripto voltam quando houver arte
ACOES = {"PETR4": "Petrobras", "VALE3": "Vale", "ITUB4": "Itaú", "BBDC4": "Bradesco", "ABEV3": "Ambev", "WEGE3": "Weg", "EMBR3": "Embraer",
         "UGPA3": "Ultra", "BRKM5": "Braskem", "BBAS3": "Banco do Brasil", "SANB11": "Santander", "MGLU3": "Magazine Luiza", "TIMS3": "TIM",
         "SUZB3": "Suzano", "B3SA3": "B3", "CPFE3": "CPFL Energia"}
FIIS = tuple(A.FIIS_LIQUIDOS[:8])
ETFS = ("BOVA11", "IVVB11", "SMAL11", "IMAB11", "DIVO11", "HASH11")
CRIPTOS = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana", "XRP": "ripple", "ADA": "cardano"}
NOMES_ETF = {"BOVA11": "iShares Ibovespa", "IVVB11": "iShares S&P 500", "SMAL11": "iShares Small Caps", "IMAB11": "ETF IMA-B", "DIVO11": "ETF Dividendos",
             "HASH11": "ETF Cripto Hashdex"}


def universo() -> list[dict]:
    """[{tk, classe, nome, codigo (para a coleta), moeda}] das cartas ativas do Battle (só categorias com análise real e arte de carta)."""
    out = [{"tk": t, "classe": "acao", "nome": n, "codigo": t, "moeda": "BRL"} for t, n in ACOES.items()]
    out += [{"tk": t, "classe": "fii", "nome": f"Fundo imobiliário {t[:4]}", "codigo": t, "moeda": "BRL"} for t in FIIS]
    out += [{"tk": t, "classe": "etf", "nome": NOMES_ETF.get(t, t), "codigo": t, "moeda": "BRL"} for t in ETFS]
    out += [{"tk": A.id_cripto(s), "classe": "cripto", "nome": A.NOMES_CRIPTO.get(s, s), "codigo": gid, "moeda": "USD", "simbolo": s} for s, gid in CRIPTOS.items()]
    return [c for c in out if c["classe"] in CATEGORIAS_ATIVAS]


# ------------------------------------------------------------------ cálculo (puro)
def indicadores_de_preco(preco, prov=None) -> dict:
    """Retorno total, volatilidade e queda máxima dos últimos 12 meses + dividend yield 12m. Usa os cálculos do próprio app
    (comparador_desempenho). {} se a série for curta. Chaves: ret_12m, vol, queda_max, dy_12m (só se houver proventos), ref (última data)."""
    import comparador_desempenho as D
    s = D.limpar(preco)
    if s is None or len(s) < MIN_PREGOES:
        return {}
    fim = s.index[-1]
    s12 = s[s.index >= fim - pd.Timedelta(days=365)]
    if len(s12) < MIN_PREGOES:
        return {}
    ir, _info = D.retorno_total(s12, prov)
    out = {"ref": fim.strftime("%Y-%m-%d")}
    if len(ir) >= 2 and float(ir.iloc[0]) > 0:
        out["ret_12m"] = float(ir.iloc[-1] / ir.iloc[0] - 1)
    m = D.metricas_risco(s12)
    if m.get("vol_anual") is not None:
        out["vol"] = float(m["vol_anual"])
    if m.get("mdd") is not None:
        out["queda_max"] = abs(float(m["mdd"]))
    if prov is not None and len(prov):
        p = pd.Series(pd.to_numeric(pd.Series(prov).values, errors="coerce"), index=pd.DatetimeIndex(pd.Series(prov).index))
        if p.index.tz is not None:
            p.index = p.index.tz_localize(None)
        ult = float(s12.iloc[-1])
        if ult > 0:
            out["dy_12m"] = float(p[(p.index > fim - pd.Timedelta(days=365)) & (p.index <= fim)].clip(lower=0).sum() / ult)
    return out


def indicadores_fundamentos(d: dict | None) -> dict:
    """P/L, P/VP, ROE, margem líquida e dívida/PL de uma ação, a partir do dicionário de dados.buscar_fundamentus (frações; dív/PL em % no app → fração aqui)."""
    if not d or d.get("erro") or not d.get("preco"):
        return {}

    def n(v):
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        return x if math.isfinite(x) else None
    preco, lpa, vpa = n(d.get("preco")), n(d.get("lpa")), n(d.get("vpa"))
    out = {}
    if preco and lpa:
        out["pl"] = preco / lpa
    if preco and vpa:
        out["pvp"] = preco / vpa
    if n(d.get("roe")) is not None:
        out["roe"] = n(d["roe"])
    if n(d.get("margem_liq")) is not None:
        out["margem_liq"] = n(d["margem_liq"])
    if n(d.get("div_pl")) is not None:
        out["div_pl"] = n(d["div_pl"]) / 100.0
    return out


def montar_carta(base: dict, preco=None, prov=None, fund: dict | None = None, agora: datetime | None = None, fonte: str = "") -> dict:
    """Junta tudo numa carta: {tk, nome, classe, moeda, ind{...}, ref, gerado, fonte, avisos}. Indicador sem dado fica de fora."""
    agora = agora or datetime.now()
    ind = {}
    pr = indicadores_de_preco(preco, prov) if preco is not None else {}
    ref = pr.pop("ref", None)
    ind.update(pr)
    avisos = []
    if base["classe"] == "acao":
        fu = indicadores_fundamentos(fund)
        ind.update(fu)
        if not fu:
            avisos.append("Fundamentos (P/L, ROE…) indisponíveis agora.")
    if not ref:
        avisos.append("Sem histórico de preço suficiente.")
    ind = {k: v for k, v in ind.items() if B.valor_valido(k, v) and k in B.INDICADORES and base["classe"] in B.INDICADORES[k]["classes"]}
    fontes = [x for x in (fonte, "Fundamentus/Yahoo" if base["classe"] == "acao" and fund else "") if x]
    return {"tk": base["tk"], "nome": base["nome"], "classe": base["classe"], "moeda": base.get("moeda", "BRL"), "ind": ind, "ref": ref,
            "gerado": agora.strftime("%Y-%m-%dT%H:%M:%S"), "fonte": " + ".join(fontes), "avisos": avisos}


# ------------------------------------------------------------------ coleta (rede passa pelo cache do app; função trocável nos testes)
def coletar_padrao(base: dict) -> dict:
    """Coleta UMA carta com a infraestrutura existente. Nunca levanta erro: falha vira carta sem indicadores."""
    preco = prov = fund = None
    fonte = ""
    try:
        import comparador_dados as CD
        item = CD.coletar_item(base["codigo"], base["classe"], proventos=base["classe"] != "cripto")
        if len(item.get("preco") if item.get("preco") is not None else []):
            preco, prov, fonte = item["preco"], item.get("prov"), item.get("fonte", "")
    except Exception:
        pass
    if base["classe"] == "acao":
        try:
            import dados
            fund = dados.buscar_fundamentus(base["codigo"])
        except Exception:
            fund = None
    return montar_carta(base, preco, prov, fund, fonte=fonte)


# ------------------------------------------------------------------ snapshot compartilhado
def _vencida(carta: dict, agora: datetime) -> bool:
    try:
        validade = VALIDADE_H if carta.get("ind") else VALIDADE_FALHA_H     # carta sem dados (fonte falhou) é tentada de novo mais cedo
        return agora - datetime.fromisoformat(carta["gerado"]) > timedelta(hours=validade)
    except (KeyError, TypeError, ValueError):
        return True


def ler_snapshot(banco_) -> dict:
    """{tk: carta} guardado no banco (vazio se não existir ou o banco falhar)."""
    try:
        d = banco_.cfg_ler(CH_SNAPSHOT) or {}
        ativas = {c["tk"] for c in universo()}
        return {t: c for t, c in (d.get("cartas") or {}).items() if t in ativas}          # cartas de categorias desativadas ficam fora
    except Exception:
        return {}


def pendentes(snapshot: dict, agora: datetime) -> list[dict]:
    """Cartas do universo que faltam no snapshot ou estão vencidas (as que faltam primeiro)."""
    uni = universo()
    falta = [b for b in uni if b["tk"] not in snapshot]
    velhas = [b for b in uni if b["tk"] in snapshot and _vencida(snapshot[b["tk"]], agora)]
    return falta + velhas


def atualizar(banco_, agora: datetime, coletor=coletar_padrao, lote: int = LOTE_ATUALIZACAO) -> tuple[dict, int]:
    """Atualiza até `lote` cartas pendentes e grava o snapshot. Devolve (snapshot, quantas ainda pendentes). Falha do banco não derruba o jogo."""
    snap = ler_snapshot(banco_)
    novas = {}
    for base in pendentes(snap, agora)[:lote]:
        c = coletor(base)
        antiga = snap.get(base["tk"])
        if not c.get("ind") and antiga and antiga.get("ind"):       # fonte falhou: mantém a carta antiga (dado real, mais velho; o Battle barra se passar do limite)
            continue
        novas[base["tk"]] = c
    if novas:
        snap = {**snap, **novas}
        try:
            banco_.cfg_gravar(CH_SNAPSHOT, {"v": 1, "cartas": snap, "atualizado": agora.strftime("%Y-%m-%dT%H:%M:%S")})
        except Exception as e:
            try:
                banco_.registrar_erro("battle_dados.snapshot", e)
            except Exception:
                pass
    return snap, len(pendentes(snap, agora))


# ------------------------------------------------------------------ estado da pessoa (baralho e histórico)
def estado_vazio() -> dict:
    return {"v": 1, "deck": [], "hist": []}


def normalizar_estado(e) -> dict:
    e = e if isinstance(e, dict) else {}
    return {"v": 1, "deck": [str(t) for t in (e.get("deck") or [])][:B.BARALHO_MAX], "hist": list(e.get("hist") or [])[:MAX_HISTORICO]}


def ler_pessoa(banco_, email: str) -> dict:
    try:
        return normalizar_estado(banco_.sis_estado_ler(email, CH_PESSOA))
    except Exception:
        return estado_vazio()


def gravar_pessoa(banco_, email: str, estado: dict) -> bool:
    try:
        banco_.sis_estado_gravar(email, CH_PESSOA, normalizar_estado(estado))
        return True
    except Exception as e:
        try:
            banco_.registrar_erro("battle_dados.pessoa", e)
        except Exception:
            pass
        return False


def registro_historico(duelo: dict, cartas: dict) -> dict:
    """Linha do histórico: tudo que o servidor usou para decidir (cartas, indicadores, valores, datas e fontes de referência)."""
    return {"id": duelo["id"], "ts": duelo["ts"], "deck": duelo["deck"], "modo": duelo["modo"], "adversario": duelo["adversario"], "seed": duelo["seed"],
            "placar": duelo["placar"], "final": duelo["final"], "dados_gerados_em": duelo.get("dados_gerados_em", ""),
            "rodadas": [{**r, "nome_jog": (cartas.get(r["jog"]) or {}).get("nome", r["jog"]), "nome_adv": (cartas.get(r["adv"]) or {}).get("nome", r["adv"])}
                        for r in duelo["rodadas"]]}


def adicionar_historico(estado: dict, reg: dict) -> dict:
    e = normalizar_estado(estado)
    if any(h.get("id") == reg["id"] for h in e["hist"]):
        return e
    e["hist"] = ([reg] + e["hist"])[:MAX_HISTORICO]
    return e


def referencia_dos_dados(cartas: dict, tks: list[str]) -> str:
    """Data mais antiga de referência entre as cartas usadas (para registrar no histórico)."""
    ds = sorted(str((cartas.get(t) or {}).get("ref") or "") for t in tks if (cartas.get(t) or {}).get("ref"))
    return ds[0] if ds else ""
