"""Aba "Diversificar" do Wallet Game: ensina a montar uma carteira diversificada usando a própria carteira virtual da pessoa.

Só desenha: a conta toda está em diversificacao.py (lógica pura, testada sem Streamlit). Tudo aparece em cartões e barras coloridas.
Nada aqui olha lucro, retorno ou risco medido, e a nota não entra no ranking.
"""
from __future__ import annotations

import html

import streamlit as st

import ativos_jogo as A
import diversificacao as D

CSS = """<style>
.dv-hero{display:flex;gap:16px;align-items:center;flex-wrap:wrap;background:linear-gradient(145deg,#2A1F6E,#160F36);border:1px solid #3D3182;border-radius:20px;padding:16px;margin:6px 0 12px;color:#EDE9FF !important;}
.dv-anel{--p:0;--c:#8B6CFF;flex:0 0 112px;width:112px;height:112px;border-radius:50%;background:conic-gradient(var(--c) calc(var(--p)*1%),#2A2060 0);display:flex;align-items:center;justify-content:center;}
.dv-anel i{width:84px;height:84px;border-radius:50%;background:#160F36;display:flex;flex-direction:column;align-items:center;justify-content:center;font-style:normal;}
.dv-anel b{font-size:1.9rem;line-height:1;color:#FFFFFF !important;} .dv-anel span{font-size:.68rem;color:#BDB5E6 !important;text-transform:uppercase;letter-spacing:.06em;}
.dv-nivel{font-weight:900;font-size:1.25rem;color:#FFFFFF !important;} .dv-resumo{font-size:.95rem;color:#DAD3F7 !important;line-height:1.45;margin-top:4px;}
.dv-sec{font-weight:900;font-size:1.08rem;margin:22px 0 8px;color:#F6F3FF !important;}
.dv-sub{font-size:.85rem;color:#BDB5E6 !important;margin:-4px 0 8px;line-height:1.4;}
.dv-linha{display:flex;align-items:center;gap:10px;margin:8px 0;}
.dv-nome{flex:0 0 150px;font-size:.88rem;font-weight:700;color:#EDE9FF !important;}
.dv-trilho{position:relative;flex:1;height:14px;background:#2A2060;border-radius:99px;overflow:visible;}
.dv-trilho i{position:absolute;left:0;top:0;height:100%;border-radius:99px;}
.dv-trilho u{position:absolute;top:-4px;height:22px;width:3px;background:#FFFFFF;border-radius:2px;opacity:.9;text-decoration:none;}
.dv-val{flex:0 0 92px;text-align:right;font-size:.8rem;color:#CFC8EE !important;}
.dv-leg{font-size:.78rem;color:#BDB5E6 !important;margin-top:6px;}
.dv-card{background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-left:5px solid #7C5CFF;border-radius:16px;padding:12px 14px;margin:8px 0;color:#EDE9FF !important;}
.dv-card.bom{border-left-color:#3DDC97;} .dv-card.atencao{border-left-color:#F2B84B;} .dv-card.info{border-left-color:#7A8CFF;}
.dv-t{font-weight:800;font-size:1rem;color:#F6F3FF !important;line-height:1.3;} .dv-s{font-size:.88rem;color:#CFC8EE !important;line-height:1.45;margin-top:3px;}
.dv-pts{float:right;font-weight:900;font-size:.85rem;color:#C5B3FF !important;white-space:nowrap;margin-left:8px;}
.dv-barra{height:8px;background:#2A2060;border-radius:99px;overflow:hidden;margin-top:8px;} .dv-barra i{display:block;height:100%;background:linear-gradient(90deg,#7C5CFF,#3DDC97);border-radius:99px;}
.dv-passos{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px;}
.dv-passo{display:flex;gap:10px;align-items:center;background:#1B1442;border:1px solid #3D3182;border-radius:14px;padding:10px 12px;color:#EDE9FF !important;}
.dv-passo.ok{border-color:#3DDC97;background:linear-gradient(145deg,#12353A,#160F36);}
.dv-bola{flex:0 0 26px;width:26px;height:26px;border-radius:50%;background:#2A2060;display:flex;align-items:center;justify-content:center;font-weight:900;color:#BDB5E6 !important;font-size:.85rem;}
.dv-passo.ok .dv-bola{background:#3DDC97;color:#0B2A20 !important;}
.dv-passo small{display:block;color:#BDB5E6 !important;font-size:.76rem;}
.dv-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;} .dv-chip{border-radius:99px;padding:3px 10px;font-size:.76rem;font-weight:700;color:#0B0821 !important;}
</style>"""

AULAS = D.AULAS


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _cor_nota(n: int) -> str:
    return "#3DDC97" if n >= 85 else "#8B6CFF" if n >= 65 else "#F2B84B" if n >= 40 else "#FF8A65"


def _hero(a: dict) -> str:
    return (f"<div class='dv-hero'><div class='dv-anel' style='--p:{a['nota']};--c:{_cor_nota(a['nota'])}'><i><b>{a['nota']}</b><span>de 100</span></i></div>"
            f"<div style='flex:1;min-width:200px'><div class='dv-nivel'>{_e(a['nivel'])}</div><div class='dv-resumo'>{_e(a['resumo'])}</div>"
            f"<div class='dv-leg'>Nota de diversificação: avalia como a carteira foi montada. Não olha lucro e não vale no ranking.</div></div></div>")


def _barras(a: dict) -> str:
    linhas = []
    for c in a["comparacao"]:
        atual, alvo = max(0.0, c["atual"]), c["alvo"]
        linhas.append(
            f"<div class='dv-linha'><div class='dv-nome'>{_e(c['nome'].split(' (')[0])}</div>"
            f"<div class='dv-trilho'><i style='width:{min(100, atual * 100):.1f}%;background:{c['cor']}'></i><u style='left:calc({min(100, alvo * 100):.1f}% - 1px)'></u></div>"
            f"<div class='dv-val'><b>{atual:.0%}</b> · ex. {alvo:.0%}</div></div>")
    g_caixa = a["caixa"]
    nota = f"<div class='dv-leg'>A barra mostra quanto você tem; o traço branco, o exemplo didático do perfil. Reserva inclui renda fixa e o caixa parado ({g_caixa:.0%} da carteira está em caixa).</div>"
    return "".join(linhas) + nota


def _quesitos(a: dict) -> str:
    out = []
    for i in a["itens"]:
        pct = 0 if not i["max"] else i["pontos"] / i["max"] * 100
        out.append(f"<div class='dv-card {'bom' if i['ok'] else 'atencao'}'><div class='dv-t'><span class='dv-pts'>{i['pontos']}/{i['max']}</span>"
                   f"{'✓ ' if i['ok'] else ''}{_e(i['titulo'])} · {_e(i['valor'])}</div><div class='dv-s'>{_e(i['texto'])}</div>"
                   f"<div class='dv-barra'><i style='width:{pct:.0f}%'></i></div></div>")
    return "".join(out)


def _desafio(a: dict) -> str:
    passos = []
    for n, e in enumerate(a["desafio"], 1):
        passos.append(f"<div class='dv-passo {'ok' if e['ok'] else ''}'><div class='dv-bola'>{'✓' if e['ok'] else n}</div>"
                      f"<div><div class='dv-t' style='font-size:.92rem'>{_e(e['titulo'])}</div><small>{_e(e['progresso'])}</small></div></div>")
    return "<div class='dv-passos'>" + "".join(passos) + "</div>"


def _dicas(a: dict) -> str:
    return "".join(f"<div class='dv-card {_e(d['tom'])}'><div class='dv-t'>{_e(d['titulo'])}</div><div class='dv-s'>{_e(d['texto'])}</div></div>" for d in a["dicas"])


def _chips_posicoes(a: dict) -> str:
    chips = []
    for tk, w in sorted(a["posicoes"].items(), key=lambda kv: -kv[1])[:12]:
        c = A.classe(tk)
        cor = A.CLASSES[c]["cor"] if c else "#9AA3B2"
        nome = tk.split(":", 1)[-1]
        chips.append(f"<span class='dv-chip' style='background:{cor}'>{_e(nome)} {w:.0%}</span>")
    return f"<div class='dv-chips'>{''.join(chips)}</div>" if chips else ""


def aba_diversificar(cart: dict, est_vazio: dict) -> None:
    """cart: carteira da pessoa ({} se ainda não houve fechamento); est_vazio: estado inicial a usar quando não há carteira."""
    st.markdown(CSS, unsafe_allow_html=True)
    est = cart if cart.get("v") == 1 else est_vazio
    chaves = list(D.PERFIS)
    escolha = st.segmented_control("Perfil de exemplo para comparar", chaves, default=D.PERFIL_PADRAO,
                                  format_func=lambda k: f"{D.PERFIS[k]['icone']} {D.PERFIS[k]['nome']}", key="div_perfil_sel") or D.PERFIL_PADRAO
    st.session_state["div_perfil"] = escolha
    a = D.analisar(est, escolha)
    st.markdown(_hero(a) + _chips_posicoes(a), unsafe_allow_html=True)
    st.caption(f"{D.PERFIS[escolha]['icone']} {D.PERFIS[escolha]['texto']} Exemplo didático, não é recomendação de investimento.")

    st.markdown("<div class='dv-sec'>Desafio: monte uma carteira diversificada</div>", unsafe_allow_html=True)
    feitos = sum(1 for e in a["desafio"] if e["ok"])
    st.markdown(f"<div class='dv-sub'>{feitos} de {len(a['desafio'])} etapas cumpridas. Cumprindo 5 ativos, 3 classes e nenhum acima de 25%, "
                "você ganha os pontos da boa decisão da semana no jogo.</div>" + _desafio(a), unsafe_allow_html=True)
    if D.concluido(a["desafio"]):
        st.success("Desafio completo! Sua carteira está bem espalhada. Agora o aprendizado é mantê-la assim ao longo do tempo.")

    st.markdown("<div class='dv-sec'>Sua carteira × exemplo do perfil</div>", unsafe_allow_html=True)
    st.markdown(_barras(a), unsafe_allow_html=True)

    st.markdown("<div class='dv-sec'>O que ajustar</div>", unsafe_allow_html=True)
    st.markdown(_dicas(a), unsafe_allow_html=True)

    st.markdown("<div class='dv-sec'>Como a nota é calculada</div>", unsafe_allow_html=True)
    st.markdown(_quesitos(a), unsafe_allow_html=True)

    st.markdown("<div class='dv-sec'>Mini-aulas</div>", unsafe_allow_html=True)
    for titulo, texto in AULAS:
        with st.expander(titulo):
            st.write(texto)
    st.caption("Atividade educacional com dinheiro virtual. Não é recomendação de investimento.")
