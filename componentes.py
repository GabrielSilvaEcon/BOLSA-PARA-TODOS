"""HTML dos componentes reutilizáveis do design system v2. Só apresentação: recebem valores já calculados e os formatam.

Usam as classes `dz-*` definidas em css.py e as cores do tema da página (variáveis CSS). Todo texto vindo de fora é escapado.
"""
from __future__ import annotations

import html


def _e(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def numero_br(v, casas: int = 2, sinal: bool = False) -> str:
    """Formata como no Brasil (1.234,56). Dado ausente vira 'indisponível' (nunca um número inventado)."""
    if v is None or isinstance(v, bool):
        return "indisponível"
    try:
        s = f"{float(v):{'+' if sinal else ''},.{casas}f}"
    except (TypeError, ValueError):
        return "indisponível"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def cartao(conteudo_html: str, titulo: str = "") -> str:
    """Cartão simples. `conteudo_html` é HTML já seguro, montado por quem chama."""
    t = f"<div class='dz-cartao-t'>{_e(titulo)}</div>" if titulo else ""
    return f"<div class='dz-cartao'>{t}{conteudo_html}</div>"


def indicador(rotulo: str, valor: str, variacao=None, detalhe: str = "") -> str:
    """Indicador financeiro com hierarquia: rótulo pequeno, valor grande, variação colorida (verde/vermelho/neutro).
    `variacao` é um número já calculado (ex.: 1.5 = +1,5%); None não mostra variação."""
    v = ""
    if variacao is not None and not isinstance(variacao, bool):
        try:
            x = float(variacao)
            cls = "pos" if x > 0 else ("neg" if x < 0 else "neu")
            seta = "▲" if x > 0 else ("▼" if x < 0 else "•")
            v = f"<span class='dz-var dz-{cls}'>{seta} {numero_br(x, 2, sinal=True)}%</span>"
        except (TypeError, ValueError):
            v = ""
    d = f"<div class='dz-ind-d'>{_e(detalhe)}</div>" if detalhe else ""
    return f"<div class='dz-ind'><div class='dz-ind-r'>{_e(rotulo)}</div><div class='dz-ind-v'>{_e(valor)}{v}</div>{d}</div>"


def selo(texto: str, tom: str = "neutro") -> str:
    tom = tom if tom in {"neutro", "positivo", "negativo", "destaque"} else "neutro"
    return f"<span class='dz-selo dz-selo-{tom}'>{_e(texto)}</span>"


def skeleton(linhas: int = 3) -> str:
    """Carregamento no formato do conteúdo (blocos cinza com brilho suave), no lugar do spinner."""
    n = max(1, min(int(linhas), 8))
    return "<div class='dz-skel'>" + "".join(f"<i style='width:{w}%'></i>" for w in ([92, 76, 84, 60, 88, 70, 80, 55][:n])) + "</div>"
