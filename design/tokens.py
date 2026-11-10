"""Tokens compartilhados pelos três ambientes. Valores em px, exceto onde indicado. Sem dependências."""
from __future__ import annotations

import json

FONTE = "Inter"
FONTE_PILHA = "'Inter','Segoe UI',system-ui,-apple-system,Roboto,sans-serif"
FONTE_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"

TEXTO = {"xs": 12, "sm": 14, "md": 16, "lg": 20, "xl": 24, "xxl": 32}
ESPACO = {"1": 4, "2": 8, "3": 12, "4": 16, "5": 24, "6": 32}
RAIO = {"campo": 8, "cartao": 12, "painel": 16, "pilula": 999}
TOQUE_MIN = 48            # altura mínima de qualquer alvo de toque (Material: 48 dp)
BARRA_ALTURA = 64         # barra inferior, sem contar a área segura do aparelho
CABECALHO_ALTURA = 48     # cabeçalho compacto no celular
ELEVACAO = {"0": "none", "1": "0 1px 2px rgba(0,0,0,.18)", "2": "0 6px 18px -8px rgba(0,0,0,.45)", "3": "0 18px 40px -14px rgba(0,0,0,.6)"}
ICONE = {"sm": 18, "md": 24, "lg": 32}
Z = {"barra": 990, "folha": 1100, "toast": 1200}
MOVIMENTO_MS = 160        # transições: só opacidade, cor e deslocamento curto
LARGURAS_ALVO = (360, 390, 430)   # larguras de celular validadas
CELULAR_MAX = 640         # até aqui vale o layout de celular
TABLET_MAX = 1100         # até aqui a barra inferior fica fixa no rodapé


def como_dict() -> dict:
    return {"fonte": FONTE, "texto": TEXTO, "espaco": ESPACO, "raio": RAIO, "toque_min": TOQUE_MIN,
            "barra_altura": BARRA_ALTURA, "cabecalho_altura": CABECALHO_ALTURA, "movimento_ms": MOVIMENTO_MS,
            "elevacao": ELEVACAO, "icone": ICONE, "z": Z, "larguras_alvo": list(LARGURAS_ALVO), "celular_max": CELULAR_MAX, "tablet_max": TABLET_MAX}


def como_json() -> str:
    """Para reaproveitar os tokens numa futura camada mobile (React Native ou Flutter)."""
    return json.dumps(como_dict(), ensure_ascii=False, indent=2)
