"""Efeitos sonoros da Jornada — gerados em código (síntese simples), sem arquivos de terceiros e sem direitos autorais.

- Quatro sons curtos (menos de 1 s, poucos KB cada): acerto, erro, lição concluída e meta do dia.
- Lógica pura (sem Streamlit): `wav(nome)` devolve os bytes de um WAV mono 16 bits; o player decide quando tocar.
- Tudo é calculado uma vez e guardado em cache de memória. Se algo falhar, quem chama simplesmente fica sem som.
- A pessoa controla o som (botão "Som" da Jornada, guardado em progresso["jornada"]["som"]).
"""
from __future__ import annotations

import io
import math
import struct
import wave
from functools import lru_cache

TAXA = 16000                      # Hz: suficiente para tons de até ~2 kHz e deixa cada arquivo pequeno
VOLUME = 0.32                     # pico (0..1): discreto, para não assustar
NOMES = ("acerto", "erro", "concluida", "meta")

# Notas (Hz) — escala de Dó maior/Mi, escolhida por soar leve; as sequências abaixo são originais.
_DO4, _MI4, _SOL4 = 261.63, 329.63, 392.00
_DO5, _MI5, _SOL5, _SI5 = 523.25, 659.25, 783.99, 987.77
_DO6, _MI6, _SOL6 = 1046.50, 1318.51, 1567.98

# Cada nota: (frequência inicial, frequência final, duração em s, início em s, ganho). Frequência final ≠ inicial faz um deslize.
_PARTITURAS: dict[str, list[tuple[float, float, float, float, float]]] = {
    # dois tons subindo
    "acerto": [(_MI5, _MI5, 0.11, 0.00, 1.0), (_SI5, _SI5, 0.20, 0.09, 1.0)],
    # tom grave e suave, descendo devagar (não é um "buzzer" agressivo)
    "erro": [(220.0, 174.6, 0.34, 0.00, 1.0)],
    # pequena melodia ascendente em arpejo
    "concluida": [(_DO5, _DO5, 0.14, 0.00, 0.9), (_MI5, _MI5, 0.14, 0.12, 0.9), (_SOL5, _SOL5, 0.14, 0.24, 0.9), (_DO6, _DO6, 0.38, 0.36, 1.0)],
    # fanfarra curta: dois toques e um acorde final que "brilha"
    "meta": [(_SOL5, _SOL5, 0.10, 0.00, 0.9), (_SOL5, _SOL5, 0.10, 0.12, 0.9), (_DO6, _DO6, 0.16, 0.24, 1.0),
             (_MI6, _MI6, 0.50, 0.38, 0.8), (_SOL5, _SOL5, 0.50, 0.38, 0.6), (_DO6, _DO6, 0.50, 0.38, 0.6), (_SOL6, _SOL6, 0.40, 0.46, 0.4)],
}


def _nota(f0: float, f1: float, dur: float, ganho: float, suave: bool) -> list[float]:
    """Uma nota: seno com um toque de harmônicos (timbre de sino), ataque curto e decaimento exponencial. Sem estalos nas pontas."""
    n = max(1, int(TAXA * dur))
    ataque = max(1, int(TAXA * 0.008))
    saida: list[float] = []
    fase = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t                                    # deslize linear de frequência
        fase += 2 * math.pi * f / TAXA
        corpo = math.sin(fase) + (0.18 if suave else 0.30) * math.sin(2 * fase) + 0.06 * math.sin(3 * fase)
        env = min(1.0, (i + 1) / ataque) * math.exp(-3.2 * t) * (1 - t) ** 0.35   # ataque, decaimento e fecho a zero
        saida.append(corpo * env * ganho)
    return saida


def _mixar(partitura: list[tuple[float, float, float, float, float]], suave: bool) -> list[float]:
    fim = max(ini + dur for _f0, _f1, dur, ini, _g in partitura)
    buf = [0.0] * (int(TAXA * fim) + 1)
    for f0, f1, dur, ini, g in partitura:
        off = int(TAXA * ini)
        for i, v in enumerate(_nota(f0, f1, dur, g, suave)):
            if off + i < len(buf):
                buf[off + i] += v
    pico = max((abs(v) for v in buf), default=1.0) or 1.0
    return [v / pico * VOLUME for v in buf]                       # normaliza: nunca passa de VOLUME (sem distorção)


@lru_cache(maxsize=len(NOMES))
def wav(nome: str) -> bytes:
    """Bytes de um arquivo WAV (mono, 16 bits, 16 kHz). Nome desconhecido levanta KeyError (quem chama deve usar `existe`)."""
    amostras = _mixar(_PARTITURAS[nome], suave=(nome == "erro"))
    bruto = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in amostras)
    with io.BytesIO() as b:
        with wave.open(b, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(TAXA)
            w.writeframes(bruto)
        return b.getvalue()


def existe(nome) -> bool:
    return nome in _PARTITURAS


def duracao(nome: str) -> float:
    with wave.open(io.BytesIO(wav(nome)), "rb") as w:
        return w.getnframes() / w.getframerate()


# ------------------------------------------------------------------ qual som tocar (puro, testável)
def som_da_resposta(ok: bool) -> str:
    return "acerto" if ok else "erro"


def som_do_resultado(r: dict) -> str:
    """Tela final: a meta do dia recém-batida tem fanfarra própria; fora isso, o som de lição concluída."""
    return "meta" if r.get("meta_nova") else "concluida"
