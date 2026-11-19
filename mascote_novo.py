"""Mascote do TickerHunters (touro roxo de jaqueta TH), no lugar do Caramelo em todo o app. Módulo puro.

As artes ficam em static/mascote/ (recortes das artes do dono, ver IMAGENS.md, seção 0):
  principal.webp  braços cruzados (fundo transparente)
  apontando.webp  apontando para quem joga (fundo transparente)
  rosto.webp      rosto quadrado com o fundo da arte (avatar, selos, placar do Trade Battle)
Cada pose antiga do Caramelo aponta para uma dessas artes. Quando chegarem as poses que faltam (animado, pensativo, celebrando, triste...),
basta salvar o arquivo em static/mascote/ e trocar a linha correspondente em POSE_ARQ.
"""
from __future__ import annotations

import base64
import functools
import os

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "mascote")
ARQUIVOS = ("principal", "apontando", "rosto")

# pose antiga (Caramelo, telas e sprites) -> arte nova
POSE_ARQ = {
    "inicio": "principal", "capa": "principal", "perfil": "principal", "carteira": "principal", "wallet": "principal",
    "loja": "principal", "conquistas": "principal", "celebrando": "principal", "triste": "principal", "dormindo": "principal",
    "analise": "apontando", "aprender": "apontando", "ajuda": "apontando", "animado": "apontando", "pensativo": "apontando",
    "surpreso": "apontando", "chamando": "apontando",
    "rosto": "rosto",
}


def arquivo(pose: str) -> str:
    """Nome do arquivo (sem extensão) da pose; pose desconhecida -> principal."""
    return pose if pose in ARQUIVOS else POSE_ARQ.get(pose, "principal")


@functools.lru_cache(maxsize=8)
def _dados(nome: str) -> tuple[str, int, int] | None:
    caminho = os.path.join(PASTA, f"{nome}.webp")
    try:
        with open(caminho, "rb") as f:
            bruto = f.read()
    except OSError:
        return None
    w = h = 0
    try:
        from PIL import Image
        with Image.open(caminho) as im:
            w, h = im.size
    except Exception:
        w = h = 0
    return base64.b64encode(bruto).decode("ascii"), w, h


def sprite(pose: str) -> tuple[str, int, int] | None:
    """(base64, largura, altura) no formato dos dicionários de sprites (arte_sprites, arte_analisar...). None se o arquivo faltar."""
    return _dados(arquivo(pose))


def uri(pose: str = "principal") -> str | None:
    """data URI da pose (None se o arquivo não estiver no repositório)."""
    d = sprite(pose)
    return f"data:image/webp;base64,{d[0]}" if d else None


def url_estatica(pose: str = "rosto") -> str:
    """Endereço servido pelo próprio app (cache do navegador)."""
    return f"app/static/mascote/{arquivo(pose)}.webp"
