"""Gera os efeitos sonoros do app do zero (sem amostras de terceiros, então sem licença). Uso: python3 tools/som/gerar.py"""
import wave, numpy as np, pathlib
SR = 22050
OUT = pathlib.Path(__file__).resolve().parents[2] / "app" / "assets" / "som"

def tom(f, d, vol=0.5, tipo="seno", ataque=0.004, queda=6.0, f2=None):
    t = np.arange(int(SR * d)) / SR
    freq = f if f2 is None else np.linspace(f, f2, t.size)
    fase = 2 * np.pi * np.cumsum(np.broadcast_to(freq, t.shape)) / SR
    onda = np.sin(fase) if tipo == "seno" else np.sign(np.sin(fase)) * 0.5 + 0.5 * np.sin(fase)
    env = np.exp(-queda * t / d) * np.minimum(1, t / ataque)
    return onda * env * vol

def seq(partes, gap=0.0):
    return np.concatenate([np.concatenate([p, np.zeros(int(SR * gap))]) for p in partes])

def mix(*ondas):
    n = max(o.size for o in ondas)
    r = np.zeros(n)
    for o in ondas: r[:o.size] += o
    return r

def salvar(nome, onda):
    onda = onda / max(1.0, np.abs(onda).max()) * 0.9
    with wave.open(str(OUT / f"{nome}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((onda * 32767).astype("<i2").tobytes())

salvar("toque", tom(880, 0.05, 0.35, queda=9))
salvar("moeda", seq([tom(988, 0.07, 0.4, "quad"), tom(1319, 0.28, 0.4, "quad", queda=5)]))
salvar("vitoria", seq([mix(tom(f, 0.22, 0.35), tom(f * 2, 0.22, 0.12)) for f in (523, 659, 784)] + [mix(tom(1047, 0.7, 0.35, queda=3), tom(784, 0.7, 0.25, queda=3), tom(659, 0.7, 0.2, queda=3))], 0.0))
salvar("empate", seq([tom(587, 0.18, 0.35), tom(587, 0.35, 0.35, queda=4)], 0.05))
salvar("derrota", seq([tom(392, 0.22, 0.35), tom(311, 0.5, 0.35, queda=4)], 0.03))
salvar("ativar", mix(tom(300, 0.45, 0.4, queda=3, f2=1200), tom(450, 0.45, 0.2, queda=3, f2=1800)))
salvar("erro", tom(180, 0.18, 0.4, "quad", queda=6))
