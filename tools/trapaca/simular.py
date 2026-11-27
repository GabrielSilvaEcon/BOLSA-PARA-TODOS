"""Simulador de trapaça da nota dos desenhos (trader_leitura.avaliar_desenhos).

Roda "jogadores" SEM nenhuma habilidade de leitura (só truques) sobre muitos cenários e mede a nota que cada truque rende. Se um truque sem leitura
tira nota alta, a nota não separa quem lê bem de quem chuta. O ponto neutro do jogo é 50 (ver trader_battle: qual + (nota/50 - 1)): acima disso a
nota SOMA pontos; abaixo, tira.

Uso: python3 tools/trapaca/simular.py [N cenários por formato]   (padrão 300)
Os cenários são simulados (passeio aleatório com a volatilidade do demo_corrida): servem para comparar truques entre si, não para prever notas reais.
"""
import statistics as st
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import trader_battle as TB      # noqa: E402
import trader_dados as TD       # noqa: E402
import trader_leitura as TL     # noqa: E402


def lv(papel, p):
    return {"papel": papel, "preco": p}


def truques(ref, atr, n, rep):
    r, a = ref, atr
    cima = max(c["h"] for c in rep)
    baixo = min(c["l"] for c in rep)
    return {
        "nada": {},
        "rompimento 1 ATR nos dois lados": {"niveis": [lv("rompimento", r + a), lv("rompimento", r - a)]},
        "rompimento 2 ATR nos dois lados": {"niveis": [lv("rompimento", r + 2 * a), lv("rompimento", r - 2 * a)]},
        "resistência acima + suporte abaixo (2 ATR)": {"niveis": [lv("resistencia", r + 2 * a), lv("suporte", r - 2 * a)]},
        "6 níveis variados (spam)": {"niveis": [lv("rompimento", r + 2 * a), lv("rompimento", r - 2 * a), lv("resistencia", r + 3 * a),
                                                lv("suporte", r - 3 * a), lv("alvo", r + 2 * a), lv("alvo", r - 2 * a)]},
        "4 tendências planas coladas no preço": {"tendencias": [
            {"i1": n - 20, "p1": r - 0.5 * a, "i2": n - 1, "p2": r - 0.5 * a},
            {"i1": n - 20, "p1": r - 1.0 * a, "i2": n - 1, "p2": r - 1.0 * a},
            {"i1": n - 20, "p1": r + 0.5 * a, "i2": n - 1, "p2": r + 0.5 * a, },
            {"i1": n - 20, "p1": r + 1.0 * a, "i2": n - 1, "p2": r + 1.0 * a}]},
        "tudo junto (6 níveis + 4 tendências + 3 zonas)": {
            "niveis": [lv("rompimento", r + 2 * a), lv("rompimento", r - 2 * a), lv("resistencia", r + 3 * a), lv("suporte", r - 3 * a),
                       lv("alvo", r + 2 * a), lv("alvo", r - 2 * a)],
            "tendencias": [{"i1": n - 20, "p1": r - 0.5 * a, "i2": n - 1, "p2": r - 0.5 * a}, {"i1": n - 20, "p1": r + 0.5 * a, "i2": n - 1, "p2": r + 0.5 * a}],
            "zonas": [{"i1": n, "i2": n + 20, "p1": r + 2 * a, "p2": r + 3 * a, "reacao": "baixa"}, {"i1": n, "i2": n + 20, "p1": r - 3 * a, "p2": r - 2 * a, "reacao": "alta"}]},
        "ORÁCULO (vê o futuro: teto teórico)": {"niveis": [lv("alvo", cima), lv("alvo", baixo)]},
    }


def simular(n_por_formato=300):
    notas, nada_avaliado = {}, {}
    for formato in ("rapida", "intermediaria", "longa"):
        for seed in range(n_por_formato):
            cen = TD.demo_corrida(formato, 1000 + seed)
            na = cen["n_analise"]
            cand = cen["candles"]
            ref, atr, rep = cand[na - 1]["c"], TB._atr(cand[:na]), cand[na:]
            for nome, marcas in truques(ref, atr, na, rep).items():
                r = TL.avaliar_desenhos(marcas, na, rep, ref, atr)
                notas.setdefault(nome, []).append(r["nota"])
    return notas


def relatorio(notas):
    linhas = [f"{'truque (sem ler o gráfico)':52} {'nota média':>10} {'% acima de 50':>14} {'% sem nota':>11}"]
    for nome, v in notas.items():
        ok = [x for x in v if x is not None]
        media = st.mean(ok) if ok else float("nan")
        acima = 100 * sum(1 for x in ok if x > 50) / len(ok) if ok else 0
        semnota = 100 * (len(v) - len(ok)) / len(v)
        linhas.append(f"{nome:52} {media:10.1f} {acima:13.0f}% {semnota:10.0f}%")
    return "\n".join(linhas)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print(relatorio(simular(n)))
