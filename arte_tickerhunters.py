"""Acesso às artes do TickerHunters (Caramelo, baús, ranks, moedas, ícones) recortadas das cartelas. Módulo puro.
As imagens ficam em `arte_sprites.py` (WebP em base64, um arquivo só: nada de pasta de imagens para subir).
Para usar uma arte nova: recortar da cartela, acrescentar em arte_sprites.SPRITES e, se for de um grupo, no mapa abaixo."""
from __future__ import annotations

import html

from arte_sprites import SPRITES

# --- grupos (nome lógico -> nome do sprite)
POSES = {"rosto": "caramelo_rosto", "animado": "caramelo_animado", "pensativo": "caramelo_pensativo", "celebrando": "caramelo_celebrando",
         "surpreso": "caramelo_surpreso", "triste": "caramelo_triste", "dormindo": "caramelo_dormindo"}
BAUS = {"comum": "bau_comum", "raro": "bau_raro", "epico": "bau_epico", "lendario": "bau_lendario"}
RANKS = ("bronze", "prata", "ouro", "platina", "diamante", "mestre")
RANK_ROTULO = {"bronze": "Bronze", "prata": "Prata", "ouro": "Ouro", "platina": "Platina", "diamante": "Diamante", "mestre": "Mestre"}
MOEDAS = {"xp": "xp", "tc": "tc", "ts": "ts"}
RAR_COR = {"comum": "#9FB2C8", "raro": "#4DA3FF", "epico": "#B06BFF", "lendario": "#FFB938"}
RAR_ROTULO = {"comum": "Comum", "raro": "Raro", "epico": "Épico", "lendario": "Lendário"}


def existe(nome: str) -> bool:
    return nome in SPRITES


def uri(nome: str) -> str:
    """data:URI do sprite. Nome desconhecido -> KeyError (erro de programação, os testes pegam)."""
    return "data:image/webp;base64," + SPRITES[nome][0]


def tamanho(nome: str) -> tuple[int, int]:
    return SPRITES[nome][1], SPRITES[nome][2]


def img(nome: str, altura: int = 64, alt: str = "", cls: str = "") -> str:
    """<img> do sprite com a altura pedida (largura proporcional). `alt` vazio = decorativa (some para leitores de tela)."""
    w, h = tamanho(nome)
    larg = max(1, round(w * altura / h))
    c = f" class='{html.escape(cls)}'" if cls else ""
    a = f" alt='{html.escape(alt, quote=True)}'" if alt else " alt='' aria-hidden='true'"
    return f"<img src='{uri(nome)}' width='{larg}' height='{altura}'{a}{c} decoding='async'>"


def pose(nome: str = "animado") -> str:
    return POSES.get(nome, POSES["animado"])


def bau(raridade: str) -> str:
    return BAUS.get(raridade, BAUS["comum"])


def rank(rank_id: str) -> str:
    return f"rank_{rank_id}" if rank_id in RANKS else "rank_bronze"


def raridade_ok(r: str | None) -> str:
    return r if r in RAR_COR else "comum"
