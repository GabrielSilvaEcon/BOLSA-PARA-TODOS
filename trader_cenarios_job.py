"""Preparação diária dos gráficos reais do Trade Battle. Roda FORA do Streamlit (GitHub Actions, depois do pregão), igual ao fechamento da competição.

Por que todo dia: o Yahoo só guarda os candles de 5 minutos dos últimos ~60 dias. Cada execução baixa o que existe hoje, monta os trechos completos
(histórico + candles menores reais do replay) e guarda no banco SÓ os que ainda não existem. O que foi guardado fica para sempre, então a biblioteca
de gráficos cresce dia após dia, mesmo depois que o Yahoo apaga os dados antigos. Nada é inventado: trecho com candle faltando fica de fora.

Variáveis de ambiente: BPT_SUPABASE_URL e BPT_SUPABASE_KEY (as mesmas da competição). Uso manual: `python trader_cenarios_job.py [rapida intermediaria longa]`.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

import yf_config  # noqa: F401

BRT = timezone(timedelta(hours=-3))


def baixador(dormir=time.sleep):
    """`baixar(codigo, periodo, intervalo)` do Yahoo, com cache dentro da execução (rápida e intermediária usam os mesmos 5 minutos)."""
    import analise_tecnica_app as ATA
    import dados
    cache: dict = {}

    def baixar(cod: str, periodo: str, intervalo: str) -> dict:
        k = (cod, periodo, intervalo)
        if k not in cache:
            res, err = None, "sem dados"
            for i in range(2):
                res, err = dados._chart_yahoo(cod, periodo, intervalo, "div,splits")
                if res:
                    break
                dormir(1.5)
            cache[k] = ATA._parse_chart(res, intraday=intervalo.endswith("m")) if res else {"erro": err or "sem dados"}
        return cache[k]
    return baixar


def _perfil(df) -> str:
    """Resumo do que veio do Yahoo: dias, candles por dia (mín/mediana/máx), horário do 1º e do último, e dias com buraco."""
    if df is None or not len(df):
        return "vazio"
    import pandas as pd
    por_dia = pd.Series(df.index.date).value_counts().sort_index()
    ini = pd.Series(df.index).groupby(df.index.date).min().dt.strftime("%H:%M").value_counts().head(3).to_dict()
    fim = pd.Series(df.index).groupby(df.index.date).max().dt.strftime("%H:%M").value_counts().head(3).to_dict()
    zero = (df["Volume"].fillna(0) <= 0)
    zh = pd.Series(zero.values, index=df.index.strftime("%H:%M")).groupby(level=0).mean().round(2)
    return (f"{len(por_dia)} dias · candles/dia min {por_dia.min()} med {int(por_dia.median())} max {por_dia.max()} · "
            f"abre {ini} · fecha {fim} · de {df.index[0]} até {df.index[-1]} · volume zero {zero.mean():.1%} {zh[zh > 0].to_dict()}")


def diagnostico(formatos: list[str], ativos: list[str], candidatos: list[str]) -> int:
    """Só olha (não grava nada): por que cada ativo gerou ou não gerou trechos, e o formato dos dados do Yahoo."""
    import analise_tecnica as AT
    import trader_battle as TB
    import trader_dados as TD
    baixar = baixador()
    agora = datetime.now(BRT).replace(tzinfo=None).isoformat(timespec="minutes")
    for f in formatos:
        sp = TB.CORRIDAS[f]
        print(f"===== {f}: gráfico {sp['tf']} formado por {sp['sub']} · {sp['n_replay']} candles no replay")
        for cod in ativos:
            dfs = {}
            for t in (sp["tf"], sp["sub"]):
                r = baixar(cod, TD.PERIODO_CORRIDA[t], TD.INTERVALO_YAHOO[t])
                dfs[t] = None if r.get("erro") else AT.limpar_ohlcv(r["df"])[0]
                print(f"  {cod} {t}: {r.get('erro') or _perfil(dfs[t])}")
            if all(d is not None for d in dfs.values()):
                mot: dict = {}
                cs = TD.montar_corridas(dfs[sp["tf"]], dfs[sp["sub"]], f, cod, agora, 3, [], mot)
                print(f"  {cod} -> {len(cs)} trechos · motivos {mot}")
    for cod in candidatos:
        r = baixar(cod, "5d", "1d")
        print(f"  candidato {cod}: {r.get('erro') or 'ok'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import trader_battle as TB
    import trader_dados as TD
    argv = list(argv or [])
    formatos = [f for f in argv if f in TB.CORRIDAS] or list(TB.CORRIDAS)
    if "--diagnostico" in argv:
        ativos = [a for a in argv if a.isupper() and not a.startswith(("+", "-"))] or list(TD.ATIVOS[:4])
        cand = [a[1:] for a in argv if a.startswith("+")]
        return diagnostico(formatos, ativos, cand)
    agora = datetime.now(BRT).replace(tzinfo=None).isoformat(timespec="minutes")
    baixar = baixador()
    falhou = 0
    for f in formatos:
        try:
            rel = TD.preparar_corrida(f, baixar, agora)
        except Exception as e:
            print(f"[{f}] erro: {e.__class__.__name__}: {e}")
            falhou += 1
            continue
        print(f"[{f}] novos: {rel['novos']} · guardados: {rel['total']} · sem trecho novo: {len(rel['falhas'])}")
        for cod, motivo in sorted(rel["falhas"].items()):
            print(f"    {cod}: {motivo}")
    return 1 if falhou == len(formatos) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
