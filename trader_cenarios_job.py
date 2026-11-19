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


def main(argv: list[str] | None = None) -> int:
    import trader_battle as TB
    import trader_dados as TD
    formatos = [f for f in (argv or []) if f in TB.CORRIDAS] or list(TB.CORRIDAS)
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
