"""Acesso às artes do TickerHunters (Caramelo, baús, ranks, moedas, ícones) recortadas das cartelas. Módulo puro.
As imagens ficam em `arte_sprites.py` (WebP em base64, um arquivo só: nada de pasta de imagens para subir).
Para usar uma arte nova: recortar da cartela, acrescentar em arte_sprites.SPRITES e, se for de um grupo, no mapa abaixo."""
from __future__ import annotations

import html

from arte_icones import ICONES                  # cartela 2: 62 ícones 3D (nomes simples: fogo, raio, escudo_ok, ...)
from arte_sprites import SPRITES as _SPRITES_1

SPRITES = {**_SPRITES_1, **ICONES}              # nome igual = o novo (mais elaborado) substitui o antigo (ex.: alerta)
for _novo, _velho in (("escudo_coroa", "em_escudo_coroa"), ("escudo_grafico", "em_escudo_grafico"), ("escudo_roxo", "em_escudo_roxo")):
    SPRITES[_velho] = ICONES[_novo]             # emblemas passam a usar os escudos com louros da cartela 2

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


_CSS_VAZIO = ("<style>html body .stApp .tv-vazio{max-width:560px;margin:10px auto;padding:16px 14px;text-align:center;border-radius:18px;border:1.5px dashed rgba(197,179,255,.4);background:#1A1438}"
              "html body .stApp .tv-vazio img{display:block;margin:0 auto 6px;filter:drop-shadow(0 4px 8px rgba(0,0,0,.45))}"
              "html body .stApp .tv-vazio b{display:block;font-size:1rem;color:#F6F3FF !important;-webkit-text-fill-color:#F6F3FF !important}"
              "html body .stApp .tv-vazio span{display:block;margin-top:4px;font-size:.84rem;line-height:1.4;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}</style>")


def html_vazio(titulo: str, texto: str = "", pose_id: str = "pensativo", altura: int = 72) -> str:
    """Estado vazio com o Caramelo (decorativo, sem animação): título curto e uma linha de orientação. Troca o texto cru por um cartão."""
    t = f"<span>{html.escape(texto)}</span>" if texto else ""
    return f"{_CSS_VAZIO}<div class='tv-vazio'>{img(pose(pose_id), altura)}<b>{html.escape(titulo)}</b>{t}</div>"

