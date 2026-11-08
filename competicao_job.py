"""Fechamento diário da competição. Roda FORA do Streamlit (GitHub Actions, depois do pregão), igual ao monitor.

Por que fora do Streamlit: precisa rodar todo dia útil mesmo com o app fechado e valorizar todas as carteiras de uma vez, com uma única
rodada de consultas de preço (e não uma por pessoa). Cada execução: trava o dia no banco (não roda duas vezes), baixa o fechamento do
universo líquido, aplica o pregão a cada carteira (proventos, desdobramentos, ordens a preço de fechamento, reinvestimento, valorização),
calcula o ranking e publica só apelido e retorno %. Só funciona com o Supabase (com SQLite local não há banco compartilhado com o app).

Variáveis de ambiente: BPT_SUPABASE_URL e BPT_SUPABASE_KEY (as mesmas do monitor). Uso manual: `python competicao_job.py --forcar`.
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import banco
import competicao as C
import seguranca as seg

BRT = timezone(timedelta(hours=-3))
HORA_MINIMA = 18               # só depois do fim do pregão (a B3 encerra por volta das 17h55)
MAX_PARTICIPANTES = 5000
TAXA_FALHA_MAX = 0.5           # se mais da metade das cotações falhar, a fonte caiu: não publica números errados


def agora_brt() -> datetime:
    return datetime.now(BRT).replace(tzinfo=None)


def coletor_yahoo(ticker: str) -> dict:
    """Último mês de fechamentos (sem ajuste por proventos), proventos e desdobramentos de um ticker da B3."""
    import pandas as pd
    import yfinance as yf
    import dados
    h = yf.Ticker(dados.sym_yf(ticker)).history(period="1mo", interval="1d", auto_adjust=False, actions=True)
    if h is None or h.empty:
        raise RuntimeError("sem dados")
    idx = pd.to_datetime(h.index)
    idx = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
    fech, div, spl = {}, {}, {}
    for d, c in zip(idx, h["Close"]):
        if c == c and c > 0:
            fech[d.date().isoformat()] = float(c)
    if "Dividends" in h:
        for d, x in zip(idx, h["Dividends"]):
            if x == x and x > 0:
                div[d.date().isoformat()] = float(x)
    if "Stock Splits" in h:
        for d, x in zip(idx, h["Stock Splits"]):
            if x == x and x > 0 and abs(x - 1) > 1e-9:
                spl[d.date().isoformat()] = float(x)
    return {"fech": fech, "div": div, "spl": spl}


def baixar_universo(tickers: list[str], coletor, dormir=time.sleep, paralelo: int = 4) -> tuple[dict, list[str]]:
    """{ticker: dados} dos que deram certo e a lista dos que falharam (2 tentativas cada)."""
    def um(tk):
        for i in range(2):
            try:
                return tk, coletor(tk), None
            except Exception as e:
                erro = e.__class__.__name__
                dormir(1.0 if i == 0 else 0)
        return tk, None, erro
    ok, falhas = {}, []
    with ThreadPoolExecutor(max_workers=paralelo) as ex:
        for tk, d, erro in ex.map(um, tickers):
            if d and d.get("fech"):
                ok[tk] = d
            else:
                falhas.append(tk)
    return ok, falhas


def dados_do_dia(cotacoes: dict, dia: str) -> dict:
    return {tk: {"c": d["fech"].get(dia), "div": d["div"].get(dia, 0.0), "split": d["spl"].get(dia, 1.0)} for tk, d in cotacoes.items()}


def publicar_precos(cotacoes: dict, dia: str) -> dict:
    precos = {}
    for tk, d in cotacoes.items():
        c = d["fech"].get(dia)
        if not c:
            continue
        ant = [v for k, v in sorted(d["fech"].items()) if k < dia]
        precos[tk] = {"c": round(c, 4), "v": round((c / ant[-1] - 1) * 100, 2) if ant else 0.0}
    return {"dia": dia, "gerado": seg.iso(), "precos": precos}


def executar(agora: datetime | None = None, coletor=coletor_yahoo, forcar: bool = False, dormir=time.sleep) -> dict:
    agora = agora or agora_brt()
    hoje = agora.date()
    if not forcar and (hoje.weekday() >= 5 or agora.hour < HORA_MINIMA):
        return {"status": "fora_do_horario"}
    slot = f"comp-{hoje.isoformat()}"
    if not banco.sis_exec_iniciar(slot):
        return {"status": "ja_rodou"}
    try:
        ativos = {c["email"] for c in banco.sis_contas_monitoraveis(MAX_PARTICIPANTES)}      # contas suspensas saem da competição
        perfis = {r["email"]: C.sanear_perfil(r["dados"]) for r in banco.sis_comp_todos("comp_ordens", MAX_PARTICIPANTES)}
        perfis = {em: p for em, p in perfis.items() if em in ativos and p["aceite"] and p["apelido"]}
        carteiras = {r["email"]: r["dados"] for r in banco.sis_comp_todos("comp_cart", MAX_PARTICIPANTES)}

        base = C.universo_base()
        precisa = {tk for em in perfis for tk in list((carteiras.get(em) or {}).get("pos", {}))}
        precisa |= {o["t"] for p in perfis.values() for o in p["pend"]}
        tickers = sorted(set(base) | precisa)
        cotacoes, falhas = baixar_universo(tickers, coletor, dormir)
        if tickers and len(falhas) / len(tickers) > TAXA_FALHA_MAX:
            banco.sis_exec_liberar(slot)                       # libera para a nova tentativa do agendador
            return {"status": "falhou", "motivo": f"{len(falhas)} de {len(tickers)} cotações falharam"}

        datas = sorted({d for c in cotacoes.values() for d in c["fech"] if d <= hoje.isoformat()})
        if not datas:
            banco.sis_exec_liberar(slot)
            return {"status": "falhou", "motivo": "nenhuma data de pregão"}
        dia_alvo = datas[-1]
        if dia_alvo < hoje.isoformat() and not forcar:
            banco.sis_exec_finalizar(slot, "sem_pregao", {"ultimo": dia_alvo})                  # feriado: nada a fazer hoje
            return {"status": "sem_pregao", "ultimo_pregao": dia_alvo}

        dias_cache: dict[str, dict] = {}
        estados, processados = {}, 0
        for em, p in perfis.items():
            est = carteiras.get(em) or C.novo_estado(p["entrada"] or dia_alvo)
            if est.get("v") != 1:
                est = C.novo_estado(p["entrada"] or dia_alvo)
            ini = est.get("inicio") or p["entrada"] or dia_alvo
            falta = [d for d in datas if d >= ini and (est.get("ult_dia") is None or d > est["ult_dia"])]
            for d in falta:
                dias_cache.setdefault(d, dados_do_dia(cotacoes, d))
                est = C.processar_dia(est, p["pend"], d, dias_cache[d], reinvestir=p["drip"])
            estados[em] = est
            processados += 1 if falta else 0

        # apelido repetido (cadastro simultâneo): fica o mais antigo; os demais saem do ranking até trocarem
        vistos, conflito = {}, set()
        for em in sorted(perfis, key=lambda e: (perfis[e]["entrada"], e)):
            k = perfis[em]["apelido_k"]
            if k in vistos:
                conflito.add(em)
            else:
                vistos[k] = em
        part = [{"apelido": perfis[em]["apelido"], "email": em, "estado": estados[em]} for em in perfis if em not in conflito]
        rk = C.montar_ranking(part, date.fromisoformat(dia_alvo))
        totais = {n: rk["listas"].get(n + "_n", 0) for n in ("geral", "mes", "semana")}
        for em, est in estados.items():
            est["rank"] = {**(rk["posicoes"].get(em) or {}), "n": totais, "conflito": em in conflito, "em": dia_alvo}
            banco.sis_estado_gravar(em, "comp_cart", est)

        if banco.cfg_disponivel():
            banco.sis_comp_publicar("comp_ranking", {"gerado": seg.iso(), "dia": dia_alvo, "listas": rk["listas"]})
            banco.sis_comp_publicar("comp_precos", publicar_precos(cotacoes, dia_alvo))
        resumo = {"dia": dia_alvo, "carteiras": len(estados), "atualizadas": processados, "cotacoes": len(cotacoes), "falhas": len(falhas)}
        banco.sis_exec_finalizar(slot, "ok", resumo)
        return {"status": "ok", **resumo}
    except Exception as e:
        banco.registrar_erro("competicao_job", e)
        banco.sis_exec_liberar(slot)
        return {"status": "falhou", "motivo": e.__class__.__name__}


def main() -> int:
    try:
        __import__("protecao").iniciar()
    except Exception as e:
        print("aviso: proteção de rede não iniciada:", e.__class__.__name__)
    r = executar(forcar="--forcar" in sys.argv)
    print(r)
    return 1 if r["status"] == "falhou" else 0


if __name__ == "__main__":
    sys.exit(main())
