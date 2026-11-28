"""Tira os textos que mudam de carta da folha 2x2 do VERSO das cartas de setup (comum, rara, épica, lendária), deixando só a moldura, os títulos fixos e os
nomes dos 6 espaços. Os textos variáveis (nome do setup, ícone, como funciona, quando ativa, saída sugerida e os valores) são escritos pelo app em cima.

Uso:  python3 tools/cartas_setup/limpar_verso.py <folha_2x2.png> <pasta_saida>
Saída: verso_<raridade>_vazio.png (cada carta, tamanho original) e folha_limpa.png.
Como: dentro de retângulos medidos na folha, acha os pixels CLAROS (o texto), engorda um pouco e apaga com inpainting (o fundo escuro volta).
"""
import sys
import pathlib

import cv2
import numpy as np

# retângulos (x0, y0, x1, y1) da 1ª carta (canto superior esquerdo) numa folha 1024 x 1536; as outras cartas são a mesma coisa deslocada
TEXTOS = [
    (160, 36, 392, 72),      # nome do setup (a etiqueta da raridade, logo abaixo, fica)
    (116, 160, 410, 200),    # como funciona (2 linhas)
    (116, 237, 330, 258),    # quando ativa
    (116, 296, 290, 318),    # saída sugerida
    (62, 426, 250, 459),     # valor 1 (ativações)
    (274, 426, 465, 459),    # valor 2 (entradas)
    (62, 516, 250, 556),     # valor 3 (acerto)
    (274, 516, 465, 556),    # valor 4 (lucro total)
    (62, 604, 250, 646),     # valor 5 (retorno médio)
    (274, 604, 465, 646),    # valor 6 (melhor entrada)
]
ICONE = (94, 70, 41)         # (cx, cy, raio) do que tem dentro do círculo do canto
DESLOC = {"comum": (0, 0), "rara": (504, 0), "epica": (0, 770), "lendaria": (504, 770)}
LIMIAR = 118                 # luminância acima disso, dentro dos retângulos, é texto
W, H = 512, 768


def mascara(carta: np.ndarray) -> np.ndarray:
    cinza = cv2.cvtColor(carta, cv2.COLOR_BGR2GRAY)
    m = np.zeros(cinza.shape, np.uint8)
    for x0, y0, x1, y1 in TEXTOS:
        m[y0:y1, x0:x1] = (cinza[y0:y1, x0:x1] > LIMIAR).astype(np.uint8) * 255
    cx, cy, r = ICONE
    disco = np.zeros(cinza.shape, np.uint8)
    cv2.circle(disco, (cx, cy), r, 255, -1)
    m = cv2.bitwise_or(m, cv2.bitwise_and(disco, (cinza > LIMIAR - 30).astype(np.uint8) * 255))
    return cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=1)


def limpar(carta: np.ndarray) -> np.ndarray:
    return cv2.inpaint(carta, mascara(carta), 5, cv2.INPAINT_TELEA)


if __name__ == "__main__":
    folha = cv2.imread(sys.argv[1])
    saida = pathlib.Path(sys.argv[2])
    saida.mkdir(parents=True, exist_ok=True)
    limpa = folha.copy()
    for nome, (dx, dy) in DESLOC.items():
        carta = folha[dy:dy + H, dx:dx + W].copy()
        nova = limpar(carta)
        cv2.imwrite(str(saida / f"verso_{nome}_vazio.png"), nova)
        limpa[dy:dy + H, dx:dx + W] = nova
    cv2.imwrite(str(saida / "folha_limpa.png"), limpa)
    print("ok")
