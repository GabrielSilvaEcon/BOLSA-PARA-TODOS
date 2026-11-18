"""Kit visual do TickerHunters (aprovado pelo dono do app): uma fonte única para o topo das telas, a tela de plano e o estilo base
dos botões. Sem Streamlit: só devolve HTML/CSS (o CSS vai no CSS global do app, uma vez por execução).

 · topo(titulo, sub, assunto): cabeçalho padrão de página. A ilustração do assunto (static/ilustracoes) entra pela direita e se funde
   ao fundo; o título fica à esquerda, com a última palavra na cor do assunto. Usado por tema.cabecalho (35 telas).
 · plano(...): cartão da tela de plano (cadeado, o que a ferramenta faz, o que o plano libera, botão de planos fica no app).
 · css(): estilo do topo, do cartão de plano e o padrão dos botões (verde = ação principal; contorno = ação neutra).
"""
from __future__ import annotations

import html

_e = html.escape
Q = "html body .stApp.stApp.stApp"
URL = "app/static/ilustracoes/"

# assunto → (imagem, cor de destaque, segunda cor)
ASSUNTOS = {
    "analisar": ("analisar", "#9C84FF", "#22D3EE"),
    "analisar_touro": ("analisar_touro", "#B06BFF", "#3DDC6A"),     # tela Analisar: o mascote novo apontando com o celular
    "carteira": ("carteira", "#34E85E", "#14C98F"),
    "aprender": ("aprender", "#22D3EE", "#B6F23E"),
    "jogos": ("jogos", "#34E85E", "#FF6B87"),
    "plano": ("plano", "#FFC93C", "#8B6CFF"),
    "inicio": ("inicio", "#B6F23E", "#8B6CFF"),
}

# título da página → assunto (o resto cai em "analisar", que é a maioria das telas com cabeçalho)
_POR_TITULO = (
    (("carteira", "risco", "relatório", "simulador", "gestão"), "carteira"),
    (("educação", "glossário", "jornada", "aprender", "professor"), "aprender"),
    (("plano", "manutenção", "disponível no plano"), "plano"),
    (("ajuda",), "inicio"),
)


def assunto_do_titulo(titulo: str) -> str:
    t = str(titulo or "").lower()
    return next((a for chaves, a in _POR_TITULO if any(c in t for c in chaves)), "analisar")


def _titulo_html(titulo: str) -> str:
    """Última palavra na cor do assunto ('Preço <em>justo</em>'); títulos com ' · ' destacam a parte depois do ponto."""
    t = str(titulo or "").strip()
    if " · " in t:
        a, b = t.split(" · ", 1)
        return f"{_e(a)} <em>{_e(b)}</em>"
    p = t.rsplit(" ", 1)
    return f"{_e(p[0])} <em>{_e(p[1])}</em>" if len(p) == 2 else _e(t)


def topo(titulo: str, sub: str = "", assunto: str | None = None) -> str:
    a = assunto if assunto in ASSUNTOS else assunto_do_titulo(titulo)
    img, c1, c2 = ASSUNTOS[a]
    s = f"<p>{_e(sub)}</p>" if sub else ""
    return (f"<div class='kt-topo' style='--ac:{c1};--ac2:{c2}'><img src='{URL}{img}.webp' alt='' loading='eager'>"
            f"<div class='t'><h1>{_titulo_html(titulo)}</h1>{s}</div></div>")


def plano(ferramenta: str, plano_nome: str, plano_atual: str, inclui: list[str], total: int) -> str:
    """Cartão da tela de plano. `inclui`: até 6 nomes de ferramentas que o plano libera; `total`: quantas libera no total."""
    itens = "".join(f"<li><span class='ok'>✓</span>{_e(t)}</li>" for t in inclui[:6])
    mais = f"<div class='mais'>e mais {total - min(len(inclui), 6)} ferramentas</div>" if total > 6 else ""
    return (f"<div class='kt-plano'><img src='{URL}plano.webp' alt=''><div class='cad'>🔒</div>"
            f"<h2>{_e(ferramenta)} faz parte do <em>{_e(plano_nome)}</em></h2>"
            f"<p>Seu plano atual é {_e(plano_atual)}. Nada do que você já fez se perde e o resto do app continua liberado.</p>"
            + (f"<div class='lib'>O {_e(plano_nome)} libera</div><ul>{itens}</ul>{mais}" if itens else "") + "</div>")


def css() -> str:
    q = Q
    return "<style>" + "".join((
        # ---- topo de página
        f"{q} .kt-topo{{position:relative;min-height:138px;margin:0 0 12px;border-radius:24px;overflow:hidden;background:#0B0828;"
        "border:2px solid color-mix(in srgb,var(--ac) 60%,transparent);box-shadow:0 0 20px color-mix(in srgb,var(--ac) 22%,transparent)}",
        f"{q} .kt-topo img{{position:absolute;right:0;top:0;height:100%;width:58%;object-fit:cover;object-position:center 22%;"
        "-webkit-mask:linear-gradient(90deg,transparent 0,#000 40%);mask:linear-gradient(90deg,transparent 0,#000 40%)}",
        f"{q} .kt-topo::after{{content:'';position:absolute;inset:0;pointer-events:none;"
        "background:linear-gradient(90deg,#0E0940 34%,transparent 74%),radial-gradient(80% 90% at 0 100%,color-mix(in srgb,var(--ac2) 22%,transparent),transparent 60%)}",
        f"{q} .kt-topo .t{{position:relative;z-index:2;padding:16px 14px;max-width:62%}}",
        f"{q} .kt-topo h1{{margin:0 !important;padding:0 !important;font-size:1.42rem !important;font-weight:900 !important;line-height:1.12 !important;"
        "color:#fff !important;-webkit-text-fill-color:#fff !important;text-wrap:balance}",
        f"{q} .kt-topo h1 em{{font-style:normal;color:var(--ac) !important;-webkit-text-fill-color:var(--ac) !important;"
        "text-shadow:0 0 14px color-mix(in srgb,var(--ac) 45%,transparent)}",
        f"{q} .kt-topo p{{margin:6px 0 0 !important;font-size:.8rem !important;line-height:1.32 !important;color:#E6E1FF !important;-webkit-text-fill-color:#E6E1FF !important;"
        "display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}",
        f"{q} .kt-topo h1 a{{display:none !important}}",
        # ---- tela de plano
        f"{q} .kt-plano{{position:relative;overflow:hidden;text-align:center;padding:150px 16px 16px;border-radius:24px;margin:0 0 10px;"
        "background:linear-gradient(180deg,transparent 0,#120B46 150px),#120B46;border:1.5px solid rgba(255,201,60,.55);box-shadow:0 0 22px rgba(255,201,60,.16)}",
        f"{q} .kt-plano img{{position:absolute;left:0;right:0;top:0;width:100%;height:190px;object-fit:cover;object-position:center 25%;"
        "-webkit-mask:linear-gradient(180deg,#000 55%,transparent);mask:linear-gradient(180deg,#000 55%,transparent)}",
        f"{q} .kt-plano .cad{{position:relative;width:58px;height:58px;margin:0 auto;border-radius:50%;display:grid;place-items:center;font-size:1.7rem;"
        "background:radial-gradient(circle at 30% 25%,#FFE9A8,#E0A21A);box-shadow:0 0 18px rgba(255,201,60,.6)}",
        f"{q} .kt-plano h2{{position:relative;margin:10px 0 4px !important;padding:0 !important;font-size:1.22rem !important;font-weight:900 !important;line-height:1.2 !important;"
        "color:#fff !important;-webkit-text-fill-color:#fff !important;text-wrap:balance}",
        f"{q} .kt-plano h2 em{{font-style:normal;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}",
        f"{q} .kt-plano h2 a{{display:none !important}}",
        f"{q} .kt-plano p{{position:relative;margin:0 auto 12px !important;max-width:38ch;font-size:.86rem !important;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}",
        f"{q} .kt-plano .lib{{font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#FFE08A !important;-webkit-text-fill-color:#FFE08A !important}}",
        f"{q} .kt-plano ul{{list-style:none;margin:8px 0 6px !important;padding:0 !important;display:grid;grid-template-columns:1fr 1fr;gap:6px 10px;text-align:left}}",
        f"{q} .kt-plano li{{display:flex;align-items:center;gap:6px;margin:0 !important;font-size:.8rem;font-weight:700;color:#fff !important;-webkit-text-fill-color:#fff !important}}",
        f"{q} .kt-plano li .ok{{flex:0 0 18px;height:18px;border-radius:50%;display:grid;place-items:center;font-size:.68rem;background:rgba(52,232,94,.2);"
        "color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}",
        f"{q} .kt-plano .mais{{font-size:.76rem;color:#9C94C9 !important;-webkit-text-fill-color:#9C94C9 !important}}",
        f"{q} .st-key-kt_planos_bt a,{q} .st-key-kt_planos_bt button{{width:100% !important;justify-content:center !important;min-height:48px !important;border-radius:16px !important;"
        "border:0 !important;background:linear-gradient(90deg,#FFE08A,#E0A21A) !important;box-shadow:0 0 16px rgba(255,201,60,.4) !important}",
        f"{q} .st-key-kt_planos_bt :is(p,span){{color:#3A2400 !important;-webkit-text-fill-color:#3A2400 !important;font-weight:900 !important}}",
        f"{q} .st-key-kt_voltar_bt a{{justify-content:center !important;width:100% !important}}",
        "@media (max-width:420px){" + f"{q} .kt-plano ul{{grid-template-columns:1fr}}{q} .kt-topo h1{{font-size:1.24rem !important}}" + "}",
    )) + "</style>"
