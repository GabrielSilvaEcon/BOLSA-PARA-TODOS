"""Arte das duas moedas do app (módulo puro, sem Streamlit).
 · TickerCoin (TC): moeda dourada real do app (Economia Ticker, Loja, recompensas).
 · T$: dinheiro virtual verde, só da Wallet Game.
Imagens em moeda_tc.webp e moeda_ts.webp na raiz do repositório. Sem elas, cai em texto/emoji (nada quebra)."""
from __future__ import annotations

import base64
import functools
import os

PASTA = os.path.dirname(os.path.abspath(__file__))


@functools.lru_cache(maxsize=4)
def uri(qual: str) -> str | None:
    """data URI da moeda ('tc' ou 'ts'); None se o arquivo não estiver no repositório."""
    try:
        with open(os.path.join(PASTA, f"moeda_{qual}.webp"), "rb") as f:
            return "data:image/webp;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


def img(qual: str, tamanho: int = 24, alt: str = "") -> str:
    u = uri(qual)
    if not u:
        return "🪙" if qual == "tc" else "💵"
    return (f'<img src="{u}" alt="{alt or ("TickerCoin" if qual == "tc" else "T$")}" width="{tamanho}" height="{tamanho}" '
            f'style="width:{tamanho}px;height:{tamanho}px;object-fit:contain;vertical-align:middle;display:inline-block">')
