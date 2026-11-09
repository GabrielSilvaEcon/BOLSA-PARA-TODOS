"""Configuração única do yfinance (importar ANTES de qualquer uso do yfinance).

Resolve dois ruídos/falhas vistos no log:
  * "Failed to create TzCache" / "OperationalError: database is locked": o yfinance guarda o fuso de cada ticker num SQLite dentro da
    pasta de cache do usuário. Em hospedagem com disco somente-leitura (ou com várias threads abrindo o mesmo arquivo) isso falha.
    Aqui o cache vai para uma pasta temporária própria do processo, sempre gravável.
  * "HTTP Error 404 ... quoteSummary" / "No data found, symbol may be delisted": o Yahoo responde assim para papéis que saíram da bolsa
    ou quando bloqueia a consulta. O app já trata a falha (usa Fundamentus, API de gráfico e fontes reservas), então a mensagem do
    yfinance é só ruído. Para vê-la de novo: defina a variável de ambiente YF_LOG=1.
"""
from __future__ import annotations

import logging
import os
import tempfile

_FEITO = False


def configurar() -> None:
    global _FEITO
    if _FEITO:
        return
    _FEITO = True
    try:
        import yfinance as yf
    except Exception:
        return
    try:
        pasta = os.path.join(tempfile.gettempdir(), f"yf_tz_cache_{os.getpid()}")
        os.makedirs(pasta, exist_ok=True)
        yf.set_tz_cache_location(pasta)
    except Exception:
        pass  # sem cache de fuso o yfinance continua funcionando, só mais devagar
    if os.environ.get("YF_LOG") != "1":
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)


configurar()
