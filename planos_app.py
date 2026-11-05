"""Página pública de Planos: o que cada plano oferece, em linguagem simples, com os limites reais lidos de planos.py.

Os três modos de experiência (Iniciante, Intermediário, Avançado), todas as classes de ativos e todas as ferramentas valem em
todos os planos: o plano só muda a QUANTIDADE de uso diário. Preços vêm de precificacao.py (definidos pelo administrador);
sem preço definido, a página mostra "Em breve" em vez de inventar um valor. Nenhum pagamento é feito aqui.
"""
from __future__ import annotations

import html

import streamlit as st

import planos
import precificacao

E = html.escape

PERFIL = {
    "gratuito": {"nome": "Gratuito", "frase": "Para conhecer o app e dar os primeiros passos.", "cor": "#3DDC97", "tom": "g"},
    "plus": {"nome": "Investidor Plus", "frase": "Para acompanhar seus investimentos com mais fôlego.", "cor": "#8B6CFF", "tom": "p"},
    "premium": {"nome": "Investidor Premium", "frase": "Para quem quer usar tudo sem se preocupar com limites.", "cor": "#F2B84B", "tom": "o"},
}
EM_TODOS = ["Os três modos de experiência: Iniciante, Intermediário e Avançado",
            "Todas as classes de ativos: ações, FIIs, fundos, ETFs, renda fixa e criptomoedas",
            "Educação financeira completa, com trilhas e exercícios",
            "Seus dados e carteiras ficam guardados na sua conta"]
FAQ = [
    ("Preciso pagar para usar o app?", "Não. O plano Gratuito é completo para começar: você usa todas as ferramentas, só com limites menores por dia."),
    ("O modo Iniciante, Intermediário ou Avançado muda o preço?", "Não. Os modos mudam só a forma como o app mostra as informações. Você troca quando quiser, de graça, em qualquer plano."),
    ("O que acontece se eu atingir um limite do dia?", "O app avisa qual limite foi atingido e libera de novo à meia-noite. Nada é apagado."),
    ("Se meu plano pago vencer, perco meus dados?", "Não. Você volta ao plano Gratuito e tudo o que cadastrou continua na sua conta. Há alguns dias de carência antes disso."),
    ("Como pago?", "O pagamento online ainda está sendo preparado. Se você recebeu um cupom, resgate em Minha conta, na seção de assinatura."),
]


def linhas_do_plano(pl: str) -> list[str]:
    """Frases curtas com os limites reais do plano (lidos de planos.limite)."""
    L = lambda r: planos.limite(pl, r)
    return [f"{L('ia_mensagens')} perguntas por dia à assistente de IA",
            f"{L('ia_resumos')} resumos com IA por dia",
            f"Até {L('alertas_max')} alertas de mercado ativos",
            f"Alertas conferidos a cada {L('verificacao_min')} minutos",
            f"Até {L('carteira_posicoes')} posições na carteira",
            f"Compare até {L('comparador_ativos')} ativos de uma vez",
            f"{L('atualizar_dados')} atualizações manuais de dados por dia"]


def preco_texto(pl: str, cfg: dict) -> tuple[str, str]:
    if pl == "gratuito":
        return "R$ 0", "para sempre"
    v = (cfg.get("preco") or {}).get(pl) or 0
    if v <= 0:
        return "Em breve", "preço a definir"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "por mês"


def html_planos(atual: str | None, cfg: dict) -> str:
    cards = []
    for pl in ("gratuito", "plus", "premium"):
        p = PERFIL[pl]
        preco, sub = preco_texto(pl, cfg)
        itens = "".join(f"<li>{E(x)}</li>" for x in linhas_do_plano(pl))
        selo = "<span class='pl-selo atual'>Seu plano</span>" if atual == pl else ""
        cards.append(
            f"<article class='pl-card {p['tom']}{' dest' if atual == pl else ''}' aria-label='Plano {E(p['nome'])}'>"
            f"<header><div class='pl-nome'>{E(p['nome'])}{selo}</div><p class='pl-frase'>{E(p['frase'])}</p>"
            f"<div class='pl-preco'><b{'' if preco.startswith('R$') else ' class=\'sem\''}>{E(preco)}</b><span>{E(sub)}</span></div></header>"
            f"<div class='pl-sub'>O que você usa por dia</div><ul>{itens}</ul></article>")
    todos = "".join(f"<li>{E(x)}</li>" for x in EM_TODOS)
    return (f"<section class='pl-wrap'><div class='pl-grade'>{''.join(cards)}</div>"
            f"<aside class='pl-todos'><div class='pl-todos-t'>Em todos os planos</div><ul>{todos}</ul></aside></section>")


CSS = """<style>
.pl-wrap{margin:8px 0 24px}
.pl-grade{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;align-items:stretch}
.pl-card{position:relative;background:#1B1442;border:1px solid rgba(189,181,230,.22);border-radius:16px;padding:0 0 20px;
  box-shadow:0 14px 30px -18px rgba(0,0,0,.6);overflow:hidden;display:flex;flex-direction:column}
.pl-card::before{content:"";display:block;height:6px;background:var(--c)}
.pl-card.g{--c:#3DDC97}.pl-card.p{--c:#8B6CFF}.pl-card.o{--c:#F2B84B}
.pl-card.dest{border-color:var(--c);box-shadow:0 0 0 2px var(--c),0 18px 36px -18px rgba(0,0,0,.7)}
.pl-card header{padding:20px 20px 12px}
.pl-nome{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font-weight:800;font-size:1.2rem;color:#FFFFFF;letter-spacing:-.015em}
.pl-selo{font-size:.7rem;font-weight:700;padding:3px 10px;border-radius:999px;letter-spacing:.01em}
.pl-selo.atual{background:rgba(61,220,151,.16);color:#3DDC97}
.pl-frase{margin:6px 0 14px;color:#BDB5E6;font-weight:500;font-size:.92rem;line-height:1.45;min-height:2.8em}
.pl-preco{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.pl-preco b{font-family:var(--mono,'JetBrains Mono',monospace);font-size:1.9rem;letter-spacing:-.03em;color:#FFFFFF}
.pl-preco b.sem{font-family:inherit;font-size:1.4rem}
.pl-preco span{color:#BDB5E6;font-size:.85rem;font-weight:600}
.pl-sub{padding:0 20px;margin:4px 0 8px;font-size:.78rem;font-weight:700;color:#BDB5E6;letter-spacing:.02em}
.pl-card ul,.pl-todos ul{list-style:none;margin:0;padding:0 20px}
.pl-card li{position:relative;padding:7px 0 7px 26px;border-top:1px solid rgba(189,181,230,.16);font-size:.9rem;font-weight:500;color:#EDE9FF;line-height:1.4}
.pl-card li::before{content:"";position:absolute;left:2px;top:12px;width:12px;height:7px;border-left:2.5px solid var(--c);border-bottom:2.5px solid var(--c);transform:rotate(-45deg)}
.pl-todos{margin-top:16px;border:1px dashed rgba(189,181,230,.35);border-radius:16px;padding:16px 4px;background:rgba(27,20,66,.6)}
.pl-todos-t{padding:0 20px 6px;font-weight:800;color:#FFFFFF}
.pl-todos ul{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:24px}
.pl-todos li{padding:5px 0 5px 22px;position:relative;font-size:.88rem;font-weight:500;color:#EDE9FF;line-height:1.4}
.pl-todos li::before{content:"";position:absolute;left:2px;top:10px;width:10px;height:6px;border-left:2.5px solid #3DDC97;border-bottom:2.5px solid #3DDC97;transform:rotate(-45deg)}
@media (max-width:900px){.pl-grade{grid-template-columns:1fr}.pl-todos ul{grid-template-columns:1fr}.pl-frase{min-height:0}}
</style>"""


def pagina_planos() -> None:
    import tema
    try:
        import conta_app
        conta_app._css()
    except Exception:
        pass
    st.markdown(tema.cabecalho("🧭", "Planos", "Escolha quanto você quer usar por dia. O app inteiro e os três modos de experiência valem em todos os planos."),
                unsafe_allow_html=True)
    atual = None
    try:
        import usuarios
        u = usuarios.usuario()
        if u:
            atual = planos.plano_de(u["email"], u.get("papel"))
    except Exception:
        pass
    st.markdown(CSS + html_planos(atual, precificacao.config()), unsafe_allow_html=True)
    st.caption("Já tem um cupom ou quer ver sua assinatura? Abra **Minha conta** no menu.")
    with st.expander("Comparar os planos lado a lado", icon=":material/table_rows:"):
        linhas = [{"Recurso": r["rotulo"], **{planos.ROTULO[p]: planos.limite(p, rid) for p in ("gratuito", "plus", "premium")}}
                  for rid, r in planos.RECURSOS.items() if r.get("aplicado")]
        st.dataframe(linhas, hide_index=True, width="stretch")
    st.markdown("#### Perguntas frequentes")
    for q, a in FAQ:
        with st.expander(q):
            st.write(a)
    st.caption("Os limites podem ser ajustados pela equipe conforme o uso real do app. Nada aqui é recomendação de investimento.")
