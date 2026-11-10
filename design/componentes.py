"""HTML dos componentes reutilizáveis do design system v2. Só apresentação: recebem valores já calculados e os formatam.

Usam as classes `dz-*` definidas em css.py e as cores do tema da página (variáveis CSS). Todo texto vindo de fora é escapado.
"""
from __future__ import annotations

import html

from .icones import icone


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


def _pct(v) -> float:
    try:
        return max(0.0, min(float(v), 100.0))
    except (TypeError, ValueError):
        return 0.0


def mensagem(texto: str, tom: str = "info", titulo: str = "") -> str:
    """Aviso em cartão com ícone: info, sucesso, aviso ou erro. A cor nunca é o único sinal (há ícone e texto)."""
    tom = tom if tom in {"info", "sucesso", "aviso", "erro"} else "info"
    ic = {"info": "info", "sucesso": "check", "aviso": "alerta", "erro": "alerta"}[tom]
    t = f"<b>{_e(titulo)}</b> " if titulo else ""
    return f"<div class='dz-msg dz-msg-{tom}' role='status'>{icone(ic, 20)}<div>{t}{_e(texto)}</div></div>"


def vazio(titulo: str, texto: str = "", icone_nome: str = "info") -> str:
    """Estado vazio: ícone grande, título e uma frase dizendo o que fazer."""
    tx = f"<div class='dz-vazio-x'>{_e(texto)}</div>" if texto else ""
    return f"<div class='dz-vazio'>{icone(icone_nome, 40)}<div class='dz-vazio-t'>{_e(titulo)}</div>{tx}</div>"


def barra_progresso(valor, rotulo: str = "", detalhe: str = "") -> str:
    """Barra de 0 a 100 com rótulo à esquerda e detalhe à direita."""
    v = _pct(valor)
    topo = f"<div class='dz-bp-t'><span>{_e(rotulo)}</span><span>{_e(detalhe)}</span></div>" if (rotulo or detalhe) else ""
    return (f"<div class='dz-bp'>{topo}<div class='dz-bp-f' role='progressbar' aria-valuemin='0' aria-valuemax='100' aria-valuenow='{v:.0f}'>"
            f"<i style='width:{v:.1f}%'></i></div></div>")


def anel(valor, rotulo: str = "", tam: int = 96, texto_central: str = "") -> str:
    """Anel de progresso (0 a 100) com o número no centro. Serve para nota de diversificação, nível e metas."""
    v = _pct(valor)
    r = 42
    circ = 2 * 3.14159265 * r
    centro = _e(texto_central) if texto_central else f"{v:.0f}"
    t = max(48, min(int(tam), 200))
    return (f"<div class='dz-anel' style='width:{t}px'><svg viewBox='0 0 100 100' width='{t}' height='{t}' role='img' aria-label='{_e(rotulo or centro)}'>"
            f"<circle cx='50' cy='50' r='{r}' fill='none' stroke='var(--dz-borda)' stroke-width='9'/>"
            f"<circle cx='50' cy='50' r='{r}' fill='none' stroke='var(--dz-destaque)' stroke-width='9' stroke-linecap='round' "
            f"stroke-dasharray='{circ * v / 100:.2f} {circ:.2f}' transform='rotate(-90 50 50)'/>"
            f"<text x='50' y='56' text-anchor='middle' class='dz-anel-n'>{centro}</text></svg>"
            f"<div class='dz-anel-r'>{_e(rotulo)}</div></div>")


def conquista(titulo: str, texto: str = "", conquistada: bool = True, icone_nome: str = "trofeu") -> str:
    """Medalha de conquista. Bloqueada fica apagada e com cadeado (o texto continua legível)."""
    ic = icone(icone_nome if conquistada else "cadeado", 28)
    cls = "dz-conq" + ("" if conquistada else " dz-conq-off")
    tx = f"<div class='dz-conq-x'>{_e(texto)}</div>" if texto else ""
    return f"<div class='{cls}'><div class='dz-conq-i'>{ic}</div><div><div class='dz-conq-t'>{_e(titulo)}</div>{tx}</div></div>"


def etapas(total: int, atual: int) -> str:
    """Bolinhas de etapa de uma trilha ou desafio: concluídas, atual e futuras."""
    n = max(1, min(int(total), 12))
    a = max(0, min(int(atual), n))
    pts = "".join(f"<i class='{'ok' if i < a else ('now' if i == a else '')}'></i>" for i in range(n))
    return f"<div class='dz-etapas' aria-label='etapa {min(a + 1, n)} de {n}'>{pts}</div>"


def grade(itens_html: list, colunas: int = 2) -> str:
    """Grade de cartões (2 colunas no celular, até `colunas` em telas largas). Cada item é HTML já seguro."""
    c = max(1, min(int(colunas), 4))
    return f"<div class='dz-grade dz-g{c}'>" + "".join(itens_html) + "</div>"


def lista_ranking(itens: list, medalhas: bool = False) -> str:
    """Ranking em cartões. Cada item: dict com pos, nome, valor (texto já formatado), tom (número: >0 verde, <0 vermelho),
    sub (linha de apoio, opcional) e voce (bool). O 1º a 3º ganham medalha quando `medalhas`."""
    if not itens:
        return ""
    med = {1: "🥇", 2: "🥈", 3: "🥉"} if medalhas else {}
    out = []
    for x in itens:
        pos = x.get("pos")
        tom = x.get("tom")
        cls = "neu"
        if isinstance(tom, (int, float)) and not isinstance(tom, bool):
            cls = "pos" if tom > 0 else ("neg" if tom < 0 else "neu")
        voce = " dz-voce" if x.get("voce") else ""
        sub = f"<div class='dz-rk-s'>{_e(x.get('sub'))}</div>" if x.get("sub") else ""
        tag = "<span class='dz-selo dz-selo-destaque'>você</span>" if x.get("voce") else ""
        out.append(
            f"<div class='dz-rk{voce}'><div class='dz-rk-p'>{_e(med.get(pos, pos))}</div>"
            f"<div class='dz-rk-n'><div class='dz-rk-nome'>{_e(x.get('nome'))} {tag}</div>{sub}</div>"
            f"<div class='dz-rk-v dz-{cls}'>{_e(x.get('valor'))}</div></div>")
    return "<div class='dz-rklista'>" + "".join(out) + "</div>"


def cartao_posicao(titulo: str, classe: str, valor: str, resultado, peso, detalhe: str = "", cor: str = "") -> str:
    """Posição da carteira: ativo, classe, valor, resultado colorido e barra de peso (0 a 100)."""
    try:
        r = float(resultado)
        cls = "pos" if r > 0 else ("neg" if r < 0 else "neu")
        rtxt = f"{'+' if r > 0 else ''}{numero_br(r, 1)}%"
    except (TypeError, ValueError):
        cls, rtxt = "neu", "—"
    cor_css = f" style='border-left-color:{_e(cor)}'" if cor and cor.startswith("#") and len(cor) in (4, 7) else ""
    d = f"<div class='dz-pos-d'>{_e(detalhe)}</div>" if detalhe else ""
    return (f"<div class='dz-posc'{cor_css}><div class='dz-posc-t'><div><div class='dz-posc-n'>{_e(titulo)}</div>"
            f"<div class='dz-posc-c'>{_e(classe)}</div></div><div class='dz-posc-v'>{_e(valor)}"
            f"<div class='dz-var dz-{cls}'>{_e(rtxt)}</div></div></div>{barra_progresso(peso, 'Peso na carteira', f'{_pct(peso):.0f}%')}{d}</div>")
