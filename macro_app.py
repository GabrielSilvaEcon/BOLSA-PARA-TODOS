"""Página Economia: inteligência econômica do Bússola B3.

Seções: resumo do cenário geral, indicadores e tendências, histórico, interpretação conjunta, setores favorecidos e pressionados,
cenário por setor, impacto na carteira REAL, alertas recentes e auditoria das fontes. Os números vêm de macro_servico (cache central
compartilhado, sem custo por usuário); as regras estão em macro_cenario e macro_alertas. Nada aqui usa IA nem recomenda compra ou venda.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

import experiencia_app as EA
import leitura as LT
import macro_alertas as AL
import macro_ativos as MA
import macro_cenario as MC
import macro_fontes as MF
import macro_servico as MS
import paleta as P

_COR = {"BOM": P.BOM, "NEUTRO": P.OURO, "RUIM": P.RUIM}
_ROT = {"BOM": "BOM", "NEUTRO": "NEUTRO", "RUIM": "RUIM"}
_FRASE = {"BOM": "condições relativamente favoráveis", "NEUTRO": "sinais mistos, sem direção forte", "RUIM": "condições relativamente desfavoráveis"}
_COR_STATUS = {"atualizado": P.BOM, "provisorio": P.OURO, "revisado": P.OURO, "desatualizado": P.RUIM, "indisponivel": P.RUIM}
AVISO = "Leitura educacional do ambiente econômico. Não prevê o preço de nenhum ativo e não é recomendação de compra ou venda."


# ------------------------------------------------------------------ formatação e blocos HTML
def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _n(v, c=2) -> str:
    if v is None or v != v:
        return "—"
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data(iso) -> str:
    try:
        return pd.Timestamp(iso).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return "—"


def casas(unidade: str) -> int:
    u = unidade.lower()
    if "milh" in u or "pontos-base" in u:
        return 0
    if "%" in u or "us$" in u or "r$ por us$" in u:
        return 2
    if "pontos" in u:
        return 1
    return 2 if "r$" not in u else 0


def valor_fmt(r: dict) -> str:
    return "—" if r.get("valor") is None else f"{_n(r['valor'], casas(r['unidade']))} {r['unidade'].replace('% ao ano', '% a.a.')}".strip()


def _chip(txt, cor=None) -> str:
    cor = cor or P.MUDO
    return (f"<span style='display:inline-block;margin:2px 6px 2px 0;padding:2px 10px;border-radius:999px;font-size:.74rem;font-weight:700;"
            f"color:{cor};border:1px solid {cor}55;background:{cor}18'>{_e(txt)}</span>")


def _card(corpo: str, cor: str | None = None) -> str:
    borda = f"border-left:6px solid {cor};" if cor else ""
    return (f"<div style='background:{P.BG_2};border:1px solid {P.LINHA};{borda}border-radius:18px;padding:14px 18px;margin:6px 0 10px'>{corpo}</div>")


def _bloco(titulo: str, itens: list[str], vazio: str = "Nada relevante no momento.") -> str:
    li = "".join(f"<li style='margin:3px 0'>{_e(i)}</li>" for i in itens) or f"<li style='color:{P.MUDO}'>{_e(vazio)}</li>"
    return (f"<div style='background:{P.BG_2};border:1px solid {P.LINHA};border-radius:16px;padding:12px 16px;height:100%'>"
            f"<div style='color:{P.MARCA_CLARA};font-weight:800;font-size:.9rem;margin-bottom:4px'>{_e(titulo)}</div>"
            f"<ul style='margin:0 0 0 18px;padding:0;color:{P.TEXTO_2};font-size:.88rem;line-height:1.45'>{li}</ul></div>")


def barra_fator(f: dict, dif: dict) -> str:
    """Barra de -1 a +1 de um fator (neutra: o fator alto não é 'bom' nem 'ruim' por si, depende do setor)."""
    v = f["valor"]
    if v is None:
        return _card(f"<b style='color:{P.TEXTO_2}'>{_e(f['nome'])}</b> {_chip('sem dado atual', P.RUIM)}"
                     f"<div style='color:{P.MUDO};font-size:.82rem;margin-top:4px'>{_e(f.get('motivo') or 'Sem dado confiável nas fontes.')}</div>")
    pos = (v + 1) / 2 * 100
    mag = abs(v)
    inten = "em torno do normal" if mag < 0.2 else "moderado" if mag < 0.5 else "forte" if mag < 0.8 else "muito forte"
    sentido = dif["alto"] if v > 0 else dif["baixo"]
    desc = "Intensidade " + inten + (f": {sentido}" if mag >= 0.2 else "")
    marcador = (f"<span style='position:absolute;top:-4px;left:{pos:.1f}%;width:4px;height:16px;margin-left:-2px;border-radius:3px;"
                f"background:#fff;box-shadow:0 0 0 2px {P.BG_2}'></span>")
    barra = (f"<div style='position:relative;height:8px;border-radius:5px;margin:12px 2px 4px;background:linear-gradient(90deg,{P.MARCA}33,{P.MARCA_CLARA}66,{P.MARCA})'>{marcador}</div>"
             f"<div style='display:flex;justify-content:space-between;color:{P.MUDO};font-size:.7rem'><span>{_e(dif['baixo'])}</span><span>{_e(dif['alto'])}</span></div>")
    return _card(f"<div style='display:flex;justify-content:space-between;gap:8px'><b style='color:{P.TEXTO_2}'>{_e(f['nome'])}</b>"
                 f"<span style='color:{P.MARCA_CLARA};font-weight:700;font-size:.82rem'>{_e(desc)}</span></div>{barra}"
                 f"<div style='color:{P.MUDO};font-size:.82rem;margin-top:6px'>{_e(f['texto'])}</div>")


def cartao_veredito(titulo: str, c: dict, modo: str, desde=None, ate=None) -> str:
    cor = _COR[c["veredito"]]
    conf = {"Alta": P.BOM, "Média": P.OURO, "Baixa": P.RUIM}[c["confianca"]]
    chips = _chip(f"Confiança {c['confianca'].lower()}" + (f" ({c['confianca_pontos']}/100)" if modo == "avancado" else ""), conf)
    d0, d1 = c.get("dados_de") or desde, c.get("dados_ate") or ate
    if d1:
        chips += _chip(f"Dados de {_data(d0)} a {_data(d1)}" if d0 and d0 != d1 else f"Dados até {_data(d1)}")
    if modo == "avancado":
        chips += _chip(f"Nota {c['nota']:+.2f}".replace(".", ",") + " (de −1 a +1)") + _chip(f"Cobertura {int(c['cobertura'] * 100)}%")
    motivo = c.get("motivo_neutro")
    frase = _FRASE[c["veredito"]] if not (c["veredito"] == "NEUTRO" and motivo) else f"{_FRASE['NEUTRO']} ({motivo})"
    if c["veredito"] == "NEUTRO" and motivo and motivo.startswith("dados insuf"):
        frase = "dados insuficientes para uma leitura segura"
    return _card(f"<div style='display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:10px'>"
                 f"<div><div style='color:{P.MUDO};font-size:.8rem;font-weight:700'>{_e(titulo)}</div>"
                 f"<div style='color:{cor};font-size:2.1rem;font-weight:800;line-height:1.1'>{_ROT[c['veredito']]}</div>"
                 f"<div style='color:{P.TEXTO_2};font-size:.92rem'>{_e(frase[0].upper() + frase[1:])}</div></div>"
                 f"<div style='text-align:right'>{chips}</div></div>", cor)


def cartao_indicador(r: dict, modo: str) -> str:
    cor = _COR_STATUS[r["status"]]
    if r["status"] == "indisponivel":
        corpo = (f"<div style='color:{P.MUDO};font-size:.78rem;font-weight:700'>{_e(r['nome'])}</div>"
                 f"<div style='color:{P.RUIM};font-size:1.1rem;font-weight:800;margin:6px 0'>Indisponível</div>{_chip('Indisponível', P.RUIM)}"
                 f"<div style='color:{P.MUDO};font-size:.76rem;margin-top:6px'>Nenhuma fonte devolveu dado válido. Veja a causa na aba Fontes.</div>")
        return _card(corpo, P.RUIM)
    var = ""
    if r.get("variacao") is not None:
        seta = "▲" if r["variacao"] > 0 else "▼" if r["variacao"] < 0 else "■"
        var = f"<span style='color:{P.MUDO};font-size:.82rem'>{seta} {_n(abs(r['variacao']), 2)} {'p.p.' if r.get('tipo_variacao') == 'p.p.' else '%'} vs. período anterior</span>"
    extra = ""
    if r.get("v12") is not None and MF.CATALOGO[r["id"]]["var"] == "pct":
        extra = f"<div style='color:{P.MUDO};font-size:.76rem'>12 meses: {'+' if r['v12'] >= 0 else '−'}{_n(abs(r['v12']), 1)}%</div>"
    aviso = f"<div style='color:{cor};font-size:.74rem;margin-top:4px'>{_e(r['motivo'])}</div>" if r["status"] in ("desatualizado", "revisado") and r.get("motivo") else ""
    detalhes = f"<div style='color:{P.MUDO};font-size:.72rem;margin-top:6px'>{_e(r['periodo_ref'])} · {_e(r['fonte'])}"
    if modo != "iniciante":
        detalhes += f" · {_e(r['codigo'])}"
    detalhes += "</div>"
    corpo = (f"<div style='color:{P.MUDO};font-size:.78rem;font-weight:700'>{_e(r['nome'])}</div>"
             f"<div style='color:{P.TEXTO_2};font-size:1.45rem;font-weight:800;margin:4px 0'>{_e(valor_fmt(r))}</div>{var}{extra}"
             f"<div style='margin-top:4px'>{_chip(r['status_rotulo'], cor)}</div>{aviso}{detalhes}")
    return _card(corpo)


# ------------------------------------------------------------------ resumo e detalhe do cenário
def _detalhe(c: dict, fatores: dict, modo: str, st_=st) -> None:
    n = 2 if modo == "iniciante" else 4
    acontece = []
    for k in c.get("contribuicoes", [])[:3]:
        if k["texto"] and k["texto"] not in acontece:
            acontece.append(k["texto"])
    favor = [f"{k['nome']}: {k['mecanismo']}." for k in c.get("favor", [])[:n] if k.get("mecanismo")]
    contra = [f"{k['nome']}: {k['mecanismo']}." for k in c.get("contra", [])[:n] if k.get("mecanismo")]
    riscos = [f"{k['nome']}: {k['mecanismo']}." for k in c.get("riscos", [])]
    a, b = st_.columns(2)
    a.markdown(_bloco("O que está acontecendo", acontece, "Sem dados atuais suficientes."), unsafe_allow_html=True)
    b.markdown(_bloco("Pontos a favor" if c["veredito"] != "RUIM" else "Pontos a favor (menores)", favor, "Nenhum fator relevante a favor."), unsafe_allow_html=True)
    c1, c2 = st_.columns(2)
    c1.markdown(_bloco("Pontos contra", contra, "Nenhum fator relevante contra."), unsafe_allow_html=True)
    c2.markdown(_bloco("Riscos a acompanhar", riscos, "Nenhum risco forte identificado."), unsafe_allow_html=True)
    d1, d2 = st_.columns(2)
    d1.markdown(_bloco("O que poderia mudar esta avaliação", c.get("muda", []), "Sem gatilhos claros."), unsafe_allow_html=True)
    lim = list(c.get("limitacoes", []))
    if c["confianca"] != "Alta":
        lim.append("A confiança não é alta: trate a leitura como indicativa.")
    d2.markdown(_bloco("Limitações desta análise", lim, "Cobertura de dados completa para este setor."), unsafe_allow_html=True)
    if modo == "avancado":
        with st_.expander("Como a nota foi calculada", icon=":material/calculate:"):
            linhas = "".join(f"<tr><td>{_e(k['nome'])}</td><td style='text-align:right'>{k['peso']:+.2f}</td><td style='text-align:right'>{k['valor']:+.2f}</td>"
                             f"<td style='text-align:right;color:{P.BOM if k['efeito'] > 0 else P.RUIM}'>{k['efeito']:+.3f}</td></tr>".replace(".", ",")
                             for k in c.get("contribuicoes", []))
            st_.markdown(f"<table style='width:100%;font-size:.84rem;color:{P.TEXTO_2}'><tr><th style='text-align:left'>Fator</th><th>Peso do setor</th><th>Valor do fator</th><th>Efeito</th></tr>{linhas}</table>"
                         f"<div style='color:{P.MUDO};font-size:.78rem;margin-top:6px'>Nota = soma dos efeitos ÷ soma dos pesos com dado atual. BOM ≥ +0,18; RUIM ≤ −0,18.</div>", unsafe_allow_html=True)


def _lista_setores(titulo: str, itens: list[dict], cor: str) -> str:
    if not itens:
        return _bloco(titulo, [], "Nenhum setor ou classe com esta classificação agora.")
    chips = "".join(_chip(f"{c['nome']} ({c['nota']:+.2f})".replace(".", ","), cor) for c in itens[:12])
    return (f"<div style='background:{P.BG_2};border:1px solid {P.LINHA};border-radius:16px;padding:12px 16px'>"
            f"<div style='color:{P.MARCA_CLARA};font-weight:800;font-size:.9rem;margin-bottom:6px'>{_e(titulo)}</div>{chips}</div>")


def _mapa(cen: dict) -> str:
    chips = "".join(_chip(f"{c['nome']} · {_ROT[c['veredito']].lower()}", _COR[c["veredito"]]) for k, c in cen.items() if k != "geral")
    return f"<div style='margin:4px 0 8px'>{chips}</div>"


# ------------------------------------------------------------------ seções
def _aba_resumo(foto: dict, modo: str) -> None:
    cen, fat = foto["cenarios"], foto["fatores"]
    g = cen["geral"]
    st.markdown(cartao_veredito("Cenário econômico geral do Brasil", g, modo, foto.get("dados_desde"), foto.get("dados_ate")), unsafe_allow_html=True)
    st.markdown(f"<div style='color:{P.TEXTO_2};margin:-2px 0 10px'>{_e(MC.texto_geral(g, modo))}</div>", unsafe_allow_html=True)
    R = foto["indicadores"]
    v = lambda i: (R.get(i) or {}).get("valor") if (R.get(i) or {}).get("status") != "indisponivel" else None
    try:
        EA.mostrar_varios([LT.macro(v("selic_meta"), v("ipca_12m"), v("dolar"), v("desemprego"), EA.modo())], "Leitura da economia")
    except Exception:
        pass
    _detalhe(g, fat, modo)
    st.markdown("#### Interpretação conjunta da economia")
    st.caption("Cada barra é um fator da economia, calculado a partir de vários indicadores (nível e direção). Fator alto não é bom nem ruim por si só: depende do setor.")
    ordem = [k for k in MC.FATORES]
    for fid in ordem:
        st.markdown(barra_fator(fat[fid], MC.FATORES[fid]), unsafe_allow_html=True)
    st.caption(AVISO)


def _aba_indicadores(foto: dict, modo: str, plot, grid) -> None:
    R = foto["indicadores"]
    grupos = list(MF.GRUPOS)
    gsel = st.segmented_control("Grupo", grupos, default=grupos[0], format_func=MF.GRUPOS.get, key="mac_grupo") or grupos[0]
    ids = MF.indicadores_do_grupo(gsel)
    for i in range(0, len(ids), 3):
        cols = st.columns(3)
        for col, ind in zip(cols, ids[i:i + 3]):
            with col:
                st.markdown(cartao_indicador(R[ind], modo), unsafe_allow_html=True)
                spec = MF.CATALOGO[ind]
                if modo != "avancado":
                    st.caption(spec["por_que"])
    st.markdown("#### Histórico dos indicadores")
    disp = [i for i in R if R[i]["status"] != "indisponivel"]
    if not disp:
        st.warning("Nenhum indicador disponível agora. Veja a aba Fontes.")
        return
    c1, c2 = st.columns([3, 2])
    pad = disp.index(MF.indicadores_do_grupo(gsel)[0]) if MF.indicadores_do_grupo(gsel)[0] in disp else 0
    ind = c1.selectbox("Indicador", disp, index=pad, format_func=lambda i: R[i]["nome"], key="mac_hist_ind")
    anos = c2.segmented_control("Período", [1, 2, 5, 10], default=2, format_func=lambda x: f"{x} ano{'s' if x > 1 else ''}", key="macro_anos") or 2
    r = R[ind]
    s = MF.para_serie(r)
    s = s.loc[s.index >= s.index.max() - pd.DateOffset(years=anos)]
    if len(s) < 2:
        st.info("Histórico curto demais para este período.")
    else:
        import plotly.graph_objects as go
        fig = go.Figure()
        spec = MF.CATALOGO[ind]
        if spec["modo"] == "preco":
            fig.add_bar(x=s.index, y=s, marker_color=P.MARCA)
        else:
            fig.add_scatter(x=s.index, y=s, mode="lines", line=dict(color=P.MARCA, width=2, shape="hv" if ind in ("selic_meta", "focus_selic") else "linear"))
        fig.update_layout(height=300, **plot)
        fig.update_yaxes(**grid, title_text=r["unidade"])
        st.plotly_chart(fig, width="stretch", key=f"mac_graf_{ind}")
        csv = pd.DataFrame({"data": s.index.strftime("%Y-%m-%d"), "valor": s.values}).to_csv(index=False, sep=";", decimal=",")
        st.download_button("Baixar este histórico (CSV)", csv, file_name=f"{ind}.csv", mime="text/csv", key=f"mac_csv_{ind}", icon=":material/download:")
    st.caption(f"Fonte: {r['fonte']} ({r['codigo']}) · último dado: {r['periodo_ref']} · consultado em {_data(r.get('atualizado_em'))}. "
               "Séries do IBGE e do Banco Central podem ser revisadas depois de divulgadas.")


def _aba_setores(foto: dict, modo: str) -> None:
    cen, fat = foto["cenarios"], foto["fatores"]
    bons, ruins = MC.beneficiados_e_pressionados(cen)
    a, b = st.columns(2)
    a.markdown(_lista_setores("Setores e classes beneficiados", bons, P.BOM), unsafe_allow_html=True)
    b.markdown(_lista_setores("Setores e classes pressionados", ruins, P.RUIM), unsafe_allow_html=True)
    st.markdown("#### Mapa de setores e classes de ativos")
    st.markdown(_mapa(cen), unsafe_allow_html=True)
    st.markdown("#### Cenário específico")
    chaves = [k for k in cen if k != "geral"]
    sel = st.selectbox("Escolha o setor ou a classe", chaves, format_func=lambda k: cen[k]["nome"], key="mac_setor")
    c = cen[sel]
    st.markdown(cartao_veredito(c["nome"], c, modo, foto.get("dados_desde"), foto.get("dados_ate")), unsafe_allow_html=True)
    if c["veredito"] == "NEUTRO" and c.get("motivo_neutro", "").startswith("dados insuf"):
        st.warning("Dados insuficientes: a classificação neutra aqui significa falta de informação, não equilíbrio de sinais.")
    _detalhe(c, fat, modo)
    st.caption(AVISO + " O cenário do setor complementa, e não substitui, a análise da empresa ou do ativo.")


def _pesos_reais() -> dict:
    try:
        import notif_app
        return {k.replace(".SA", ""): v for k, v in notif_app._pesos_carteira().items()}
    except Exception:
        return {}


def _aba_carteira(foto: dict, modo: str) -> None:
    ss = st.session_state
    fat, ind = foto["fatores"], foto["indicadores"]
    st.markdown(_card(f"<b style='color:{P.TEXTO_2}'>Carteira real</b><div style='color:{P.MUDO};font-size:.86rem'>Só os ativos que você registrou na carteira real "
                      "entram aqui e nos alertas econômicos. Ativos pesquisados, exemplos e a carteira fictícia ficam de fora.</div>"), unsafe_allow_html=True)
    pos = MA.posicoes_reais({"cart_real": ss.get("cart_real"), "cart_rf": ss.get("cart_rf")})
    _linhas_posicoes(pos, fat, ind, modo, _pesos_reais(), "real")
    with st.expander("Ver a carteira fictícia (simulação, separada da real)", icon=":material/science:"):
        st.caption("Simulação: não gera alertas econômicos e não se mistura com a carteira real.")
        pos_f = MA.posicoes_reais({"cart_real": ss.get("cart_ficticia")})
        _linhas_posicoes(pos_f, fat, ind, modo, {}, "fict")


def _linhas_posicoes(pos: list, fat: dict, ind: dict, modo: str, pesos: dict, pref: str) -> None:
    if not pos:
        st.info("Nenhum ativo aqui ainda. Registre compras na página Carteira para ver o impacto do cenário econômico." if pref == "real"
                else "A carteira fictícia está vazia.")
        return
    try:
        import recursos as rec
        infos = {p["ativo"]: rec.info(p["ativo"]) for p in pos}
    except Exception:
        infos = {}
    linhas = AL.avaliar_posicoes(pos, fat, ind, None, infos, None, pesos)
    resumo = {"BOM": 0, "NEUTRO": 0, "RUIM": 0, None: 0}
    for l in linhas:
        resumo[l["veredito"]] += 1
    st.markdown("".join(_chip(f"{resumo[v]} {r}", _COR[v]) for v, r in (("BOM", "favoráveis"), ("NEUTRO", "neutros"), ("RUIM", "desfavoráveis")) if resumo[v])
                + (_chip(f"{resumo[None]} sem classificação", P.MUDO) if resumo[None] else ""), unsafe_allow_html=True)
    for i, l in enumerate(sorted(linhas, key=lambda x: (x["veredito"] is None, -(x.get("peso") or 0)))):
        with st.container(border=True):
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            peso = f" · {_n(l['peso'], 1)}% da carteira" if l.get("peso") else ""
            c1.markdown(f"**{_e(l['ticker'])}** {_chip(l['classe_rotulo'])}{_chip(l['setor'])}<span style='color:{P.MUDO};font-size:.8rem'>{peso}</span>", unsafe_allow_html=True)
            if l["veredito"]:
                c2.markdown(_chip(f"Cenário {l['veredito'].lower()} · confiança {l['confianca'].lower()}", _COR[l["veredito"]]), unsafe_allow_html=True)
            else:
                c2.markdown(_chip("Sem classificação", P.MUDO), unsafe_allow_html=True)
            st.caption(l["justificativa"])
            if l["veredito"]:
                with st.expander("Sensibilidades e motivos", icon=":material/tune:"):
                    sens = pd.DataFrame([{"Fator": k, "Sensibilidade": v["nivel"], "Efeito": v["sentido"]} for k, v in l["sens"].items()])
                    st.dataframe(sens, hide_index=True, width="stretch")
                    st.caption(f"Perfil: {l['origem']}. " + ("Os pesos de sensibilidade vêm do setor e são educacionais." if modo != "avancado"
                                                              else "Pesos do setor " + (f"com ajuste próprio {l['ajuste']}." if l["ajuste"] else "sem ajuste próprio.")))
                    for k in (l["cenario"].get("contra") or [])[:2]:
                        st.markdown(f"- Contra: {k['mecanismo']}.")
                    for k in (l["cenario"].get("favor") or [])[:2]:
                        st.markdown(f"- A favor: {k['mecanismo']}.")
    st.caption("O cenário econômico não diz se o ativo está barato ou caro, nem manda comprar ou vender: complementa a análise do próprio ativo.")


def _aba_alertas() -> None:
    try:
        import banco
        import notif_app
        a = notif_app._ator()
    except Exception:
        a = None
    if not a:
        st.info("Entre na sua conta para receber e consultar os alertas do cenário econômico.")
        return
    st.markdown(_card(f"<b style='color:{P.TEXTO_2}'>Como os alertas funcionam</b><div style='color:{P.MUDO};font-size:.86rem'>"
                      "O monitor avisa quando o cenário de um setor da sua carteira real muda de classificação (neutro, bom, ruim), quando a nota se move muito "
                      "ou quando surge um risco econômico forte. Não avisa só porque o cenário continua igual. Escolha o que receber em Notificações > Preferências.</div>"),
                unsafe_allow_html=True)
    try:
        lista = banco.notif_listar(a, categoria="macro", limite=15)
    except Exception:
        lista = []
    if not lista:
        st.info("Nenhum alerta econômico ainda. Eles aparecem aqui quando o cenário de um ativo da sua carteira real mudar de forma relevante.")
        return
    pesos = notif_app._pesos_carteira()
    for n in lista:
        notif_app._cartao(n, "macro", pesos)


def _aba_fontes(foto: dict, modo: str) -> None:
    R = foto["indicadores"]
    cob = foto["cobertura"]
    ct = cob["contagem"]
    st.markdown("".join(_chip(f"{ct.get(k, 0)} {MF.STATUS_ROTULO[k].split(' (')[0].lower()}", _COR_STATUS[k]) for k in MF.STATUS_ROTULO if ct.get(k)), unsafe_allow_html=True)
    linhas = []
    for i, r in R.items():
        linhas.append({"Indicador": r["nome"], "Grupo": MF.GRUPOS[r["grupo"]], "Estado": r["status_rotulo"], "Último valor": valor_fmt(r) if r["valor"] is not None else "—",
                       "Período": r.get("periodo_ref") or "—", "Fonte": r.get("fonte") or "—", "Código": r.get("codigo") or "—",
                       "Observação": r.get("motivo") or ""})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    indisp = [r for r in R.values() if r["status"] in ("indisponivel", "desatualizado")]
    if indisp:
        st.markdown("#### O que continua sem dado e por quê")
        for r in indisp:
            with st.expander(f"{r['nome']} · {r['status_rotulo'].lower()}", icon=":material/report:"):
                st.write(r.get("motivo") or "")
                for t in r.get("tentativas", []):
                    st.markdown(f"- **{t['fonte']}** ({t['codigo']}): {'usada' if t['ok'] else t['motivo']}")
    with st.expander("Itens do pedido sem fonte pública gratuita estável", icon=":material/block:"):
        for k, v in MF.NAO_COBERTOS.items():
            st.markdown(f"- **{k}:** {v}")
    st.caption("Cada indicador tenta as fontes em ordem (Banco Central, IBGE, Ipeadata, FRED, Focus) e só aceita dado com frequência e faixa de valores plausíveis. "
               "Nada é inventado para preencher lacunas. Um dado desatualizado nunca é usado no cálculo do cenário.")


# ------------------------------------------------------------------ alertas gerados ao abrir a página (quando o monitor não está rodando)
def registrar_alertas_da_pagina(foto: dict) -> int:
    """Gera os alertas da conta logada com a MESMA regra do monitor (estado compartilhado em monitor_estado). Falha nunca quebra a página."""
    try:
        import banco
        import notif as N
        import notif_app
        import seguranca as seg
        a = notif_app._ator()
        if not a:
            return 0
        ss = st.session_state
        pos = MA.posicoes_reais({"cart_real": ss.get("cart_real"), "cart_rf": ss.get("cart_rf")})
        if not pos:
            return 0
        prefs = N.normalizar_prefs(ss.get("notif_prefs"))
        agora = seg.agora()
        estado = banco.sis_estado_ler(a.email, "mon") or {}
        notifs, novo = AL.avaliar_conta(pos, foto["fatores"], foto["indicadores"], estado.get("macro"), prefs.get("macro"), agora, _pesos_reais())
        if novo != estado.get("macro"):
            estado["macro"] = novo
            banco.sis_estado_gravar(a.email, "mon", estado)
        notifs = [n for n in notifs if N.passa_prefs(n, prefs)]
        peso = notif_app._pesos_carteira()
        for n in notifs:
            n["importancia"], mot = N.pontuar(n, peso)
            if mot:
                n["dados"]["prioridade_motivo"] = mot
        recentes = banco.sis_notif_recentes(a.email, seg.somar(-7 * 86400, agora))
        notifs, _ = N.suprimir(notifs, recentes, prefs, agora)
        if prefs["agrupar"]:
            notifs, _ = N.agrupar(notifs)
        novas = sum(1 for n in notifs if banco.notif_inserir(a, n))
        if novas:
            notif_app.contagem_nao_lidas(True)
        return novas
    except Exception as e:                       # noqa: BLE001
        try:
            import banco
            banco.registrar_erro("macro_app.alertas", e)
        except Exception:
            pass
        return 0


# ------------------------------------------------------------------ página
def pagina(cabecalho, md, plot, grid) -> None:
    cabecalho("🌐", "Cenário econômico",
              "Juros, inflação, atividade, dólar e crédito analisados em conjunto: o que significam para cada setor e para a sua carteira real.")
    modo = EA.modo()
    with st.spinner("Lendo os indicadores..."):
        foto = MS.cenario_compartilhado()
    if not foto or not foto.get("indicadores"):
        st.error("Não consegui carregar os indicadores agora. Tente novamente em alguns minutos.")
        return
    cob = foto["cobertura"]
    if cob["contagem"].get("indisponivel", 0) or cob["contagem"].get("desatualizado", 0):
        st.caption(f"{cob['contagem'].get('indisponivel', 0)} indicador(es) indisponível(is) e {cob['contagem'].get('desatualizado', 0)} desatualizado(s): "
                   "a confiança da análise considera isso. Detalhes na aba Fontes.")
    chave = foto.get("dados_ate")
    if st.session_state.get("_macro_reg") != chave:                  # no máximo uma vez por sessão e por atualização de dados
        st.session_state["_macro_reg"] = chave
        registrar_alertas_da_pagina(foto)
    abas = st.tabs(["Resumo", "Indicadores", "Setores", "Minha carteira real", "Alertas", "Fontes"])
    with abas[0]:
        _aba_resumo(foto, modo)
    with abas[1]:
        _aba_indicadores(foto, modo, plot, grid)
    with abas[2]:
        _aba_setores(foto, modo)
    with abas[3]:
        _aba_carteira(foto, modo)
    with abas[4]:
        _aba_alertas()
    with abas[5]:
        _aba_fontes(foto, modo)
