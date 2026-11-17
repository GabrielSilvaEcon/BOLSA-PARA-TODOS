"""Foto de perfil: validação, recorte e reprocessamento da imagem enviada. Lógica pura (Pillow): sem Streamlit, sem banco e sem rede.

Segurança (o arquivo enviado nunca é guardado como veio):
 · Tamanho: até TAM_MAX_MB. Formato conferido pelos BYTES do arquivo (assinatura), não pelo nome: só JPEG, PNG ou WebP.
 · Abertura protegida contra "bombas de descompressão" (limite de pixels) e verificação de integridade do Pillow.
 · A imagem é sempre redesenhada: rotação do celular corrigida, convertida para RGB, recortada em quadrado e salva de novo em
   WebP de LADO px. Metadados (EXIF, GPS), perfis embutidos, animação e qualquer conteúdo escondido no arquivo original são descartados.
 · O resultado tem tamanho limitado (MAX_SAIDA_KB): é isso que vai para o banco.
"""
from __future__ import annotations

import base64
import hashlib
import io

from PIL import Image, ImageOps, UnidentifiedImageError

TAM_MAX_MB = 5
MAX_PIXELS = 40_000_000          # 40 megapixels: acima disso a imagem é recusada (evita travar o servidor)
LADO = 320                       # foto final: 320 × 320
LADO_PREVIA = 220
QUALIDADE = 82
MAX_SAIDA_KB = 120
ZOOM_MAX = 3.0
FORMATOS = {"jpeg": "JPEG", "png": "PNG", "webp": "WebP"}


class ErroFoto(ValueError):
    """Imagem recusada (mensagem pronta para a tela)."""


def formato(dados: bytes) -> str | None:
    """Formato pela assinatura dos bytes (o nome e o tipo informados pelo navegador não são confiáveis)."""
    if dados[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    return None


def abrir(dados: bytes) -> Image.Image:
    """Confere tamanho, formato, dimensões e integridade; devolve a imagem já com a rotação do celular corrigida, em RGB."""
    if not dados:
        raise ErroFoto("Nenhuma imagem recebida. Escolha um arquivo e tente de novo.")
    if len(dados) > TAM_MAX_MB * 1024 * 1024:
        raise ErroFoto(f"A imagem tem {len(dados) / 1024 / 1024:.1f} MB. O limite é {TAM_MAX_MB} MB.")
    if not formato(dados):
        raise ErroFoto("Formato não aceito. Envie uma foto em JPG, PNG ou WebP.")
    try:
        with Image.open(io.BytesIO(dados)) as im:
            if im.width * im.height > MAX_PIXELS:
                raise ErroFoto("A imagem é grande demais em pixels. Envie uma foto menor.")
            im.verify()                                          # integridade do arquivo (precisa reabrir depois)
        im = Image.open(io.BytesIO(dados))
        if im.width * im.height > MAX_PIXELS:
            raise ErroFoto("A imagem é grande demais em pixels. Envie uma foto menor.")
        if im.width < 64 or im.height < 64:
            raise ErroFoto("A imagem é pequena demais. Use uma foto com pelo menos 64 × 64 pixels.")
        im.seek(0)                                               # imagem animada: só o primeiro quadro
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            fundo = Image.new("RGB", im.size, (26, 20, 56))
            rgba = im.convert("RGBA")
            fundo.paste(rgba, mask=rgba.split()[-1])
            return fundo
        return im.convert("RGB")
    except ErroFoto:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise ErroFoto("Não consegui ler essa imagem (o arquivo parece corrompido). Tente outra foto.")


def recortar(im: Image.Image, zoom: float = 1.0, x: float = 0.0, y: float = 0.0, lado: int = LADO) -> Image.Image:
    """Recorte quadrado: `zoom` 1 a ZOOM_MAX (1 = maior quadrado possível); `x`, `y` de -1 a 1 movem o recorte (0 = centro)."""
    z = max(1.0, min(float(zoom), ZOOM_MAX))
    x, y = max(-1.0, min(float(x), 1.0)), max(-1.0, min(float(y), 1.0))
    w, h = im.size
    q = min(w, h) / z
    cx = w / 2 + x * (w - q) / 2
    cy = h / 2 + y * (h - q) / 2
    caixa = (round(cx - q / 2), round(cy - q / 2), round(cx + q / 2), round(cy + q / 2))
    return im.crop(caixa).resize((lado, lado), Image.LANCZOS)


def para_webp(im: Image.Image) -> bytes:
    for q in (QUALIDADE, 70, 55):
        b = io.BytesIO()
        im.save(b, "WEBP", quality=q, method=6)
        if b.tell() <= MAX_SAIDA_KB * 1024:
            return b.getvalue()
    raise ErroFoto("Não consegui reduzir a imagem o suficiente. Tente outra foto.")


def processar(dados: bytes, zoom: float = 1.0, x: float = 0.0, y: float = 0.0, lado: int = LADO) -> bytes:
    """Do arquivo enviado à foto final (WebP quadrado). Levanta ErroFoto com mensagem clara em qualquer recusa."""
    return para_webp(recortar(abrir(dados), zoom, x, y, lado))


def documento(webp: bytes, agora_iso: str) -> dict:
    """O que vai para o banco: a foto já reprocessada (base64), um hash e a data. Nada do arquivo original."""
    if formato(webp) != "webp" or len(webp) > MAX_SAIDA_KB * 1024:
        raise ErroFoto("Foto inválida.")
    return {"v": 1, "webp": base64.b64encode(webp).decode("ascii"), "h": hashlib.sha256(webp).hexdigest()[:16], "em": str(agora_iso)[:25]}


def uri(doc) -> str:
    """data URI da foto guardada ('' se não houver ou se o documento não for uma foto válida)."""
    try:
        b = base64.b64decode(str((doc or {}).get("webp") or ""), validate=True)
    except Exception:
        return ""
    if formato(b) != "webp" or len(b) > MAX_SAIDA_KB * 1024:
        return ""
    return "data:image/webp;base64," + base64.b64encode(b).decode("ascii")
