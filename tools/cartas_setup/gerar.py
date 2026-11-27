"""Gera as 8 artes das cartas de setup (frente e verso × comum, rara, épica, lendária) a partir das imagens feitas pela IA.

Uso:  python tools/cartas_setup/gerar.py <comum.png> <rara.png> <lendaria.jpg> <verso_rara_folha.png> <saida>

 · recorta cada carta pelo contorno (tira o fundo e o brilho de fora) com cantos arredondados e transparência;
 · leva todas ao mesmo tamanho (768 x 1176);
 · a frente ÉPICA sai da RARA com o matiz girado para roxo; os versos saem do verso azul (rara) girando o matiz (épica, lendária) ou
   tirando a cor (comum). Se a IA entregar artes prontas, basta salvar com os mesmos nomes em app/assets/cartas_setup/.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw

W, H = 768, 1176


def limites(a: np.ndarray, margem: int = 2):
    """Bordas externas da carta: onde a luminância cai em relação ao fundo, andando do lado de fora para dentro."""
    lum = a.astype(float).mean(axis=2)
    h, w = lum.shape

    def acha(serie, inicio=0):
        base = serie[inicio:inicio + 5].mean()
        for i in range(inicio, len(serie)):
            if abs(serie[i] - base) > 14:
                return i
        return inicio
    esq = acha(lum[h // 2, :])
    dir_ = w - 1 - acha(lum[h // 2, ::-1])
    topo = acha(lum[:, w // 2])
    base = h - 1 - acha(lum[::-1, w // 2])
    return esq - margem, topo - margem, dir_ + margem, base + margem


def recorta(im: Image.Image, caixa, raio_pct=0.06) -> Image.Image:
    im = im.convert("RGBA").crop(caixa).resize((W, H), Image.LANCZOS)
    m = Image.new("L", (W * 3, H * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, W * 3 - 1, H * 3 - 1], radius=int(W * 3 * raio_pct), fill=255)
    im.putalpha(m.resize((W, H), Image.LANCZOS))
    return im


def gira(im: Image.Image, delta: int, faixa=(125, 172), smin=50) -> Image.Image:
    """Gira o matiz só dos pixels azulados e saturados (o urso e o escudo mantêm as cores)."""
    rgba = im.convert("RGBA")
    hsv = np.asarray(rgba.convert("RGB").convert("HSV")).astype(float)
    mask = (hsv[:, :, 0] > faixa[0]) & (hsv[:, :, 0] < faixa[1]) & (hsv[:, :, 1] > smin)
    hsv[:, :, 0][mask] = (hsv[:, :, 0][mask] + delta) % 256
    out = Image.fromarray(hsv.astype("uint8"), "HSV").convert("RGBA")
    out.putalpha(rgba.getchannel("A"))
    return out


def prata(im: Image.Image) -> Image.Image:
    """Tira a cor dos brilhos azuis (linhas e bordas claras viram prata) e mantém o azul-marinho escuro do fundo."""
    rgba = im.convert("RGBA")
    hsv = np.asarray(rgba.convert("RGB").convert("HSV")).astype(float)
    azul = (hsv[:, :, 0] > 125) & (hsv[:, :, 0] < 172)
    v = hsv[:, :, 2] / 255.0
    fator = np.clip((v - 0.35) / 0.4, 0, 1)             # só o que é claro perde a saturação
    hsv[:, :, 1] = np.where(azul, hsv[:, :, 1] * (1 - 0.85 * fator), hsv[:, :, 1])
    out = Image.fromarray(hsv.astype("uint8"), "HSV").convert("RGBA")
    out.putalpha(rgba.getchannel("A"))
    return out


def main(comum, rara, lendaria, folha_verso, saida):
    import os
    os.makedirs(saida, exist_ok=True)
    arq = {}
    for nome, caminho in (("comum", comum), ("rara", rara), ("lendaria", lendaria)):
        im = Image.open(caminho).convert("RGB")
        arq[nome] = recorta(im, limites(np.asarray(im)))
    arq["epica"] = gira(arq["rara"], 40)
    # verso azul: a carta da direita da folha (a folha tem transparência fora das cartas)
    folha = Image.open(folha_verso).convert("RGBA")
    meio = folha.width // 2
    dire = folha.crop((meio, 0, folha.width, folha.height))
    alfa = np.asarray(dire.getchannel("A")) > 200
    ys, xs = np.where(alfa)
    caixa = (int(np.percentile(xs, 0.2)), int(np.percentile(ys, 0.2)), int(np.percentile(xs, 99.8)), int(np.percentile(ys, 99.8)))
    verso = recorta(dire.convert("RGB"), caixa)
    versos = {"rara": verso, "comum": prata(verso), "epica": gira(verso, 40), "lendaria": gira(verso, -118, faixa=(125, 172))}
    for nome, im in arq.items():
        im.save(f"{saida}/frente_{nome}.webp", quality=88, method=6)
    for nome, im in versos.items():
        im.save(f"{saida}/verso_{nome}.webp", quality=88, method=6)


if __name__ == "__main__":
    main(*sys.argv[1:6])
