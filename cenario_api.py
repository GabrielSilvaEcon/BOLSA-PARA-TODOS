"""Cenário econômico no app novo (botão da tela inicial): os mesmos indicadores e o mesmo cálculo da página Economia do app antigo
(macro_fontes, macro_cenario, macro_servico), resumidos para o celular. Sem Streamlit. Educativo: descreve o ambiente, não prevê o mercado.

`montar(foto)` é puro (testado sem rede); a foto vem de macro_servico.cenario_compartilhado(), que tem cache de 30 min para todos.
"""
from __future__ import annotations

AVISO = "Leitura educativa com dados do Banco Central, IBGE e outras fontes públicas. Descreve o ambiente; não diz se um ativo vai subir ou cair."

# Os números grandes da tela, na ordem: (id do indicador, rótulo curto, explicação simples)
PRINCIPAIS = (
    ("selic_meta", "Juros (Selic)", "Juros básicos do país. Juros altos deixam o crédito caro e a renda fixa atraente."),
    ("ipca_12m", "Inflação 12 meses", "Quanto os preços subiram em um ano. O dinheiro parado perde esse poder de compra."),
    ("juro_real", "Juro real", "Quanto os juros ficam acima da inflação."),
    ("dolar", "Dólar", "Dólar alto encarece importados e ajuda quem vende para fora."),
    ("desemprego", "Desemprego", "Menos desemprego costuma significar mais consumo e lucro das empresas."),
    ("focus_selic", "Selic esperada", "Onde o mercado acha que a Selic vai estar no fim do ano."),
)
# Fatores mostrados como barras (de -1 a +1), na ordem da tela
FATORES_TELA = ("juro_real", "juro_tendencia", "inflacao", "atividade", "emprego", "cambio", "aversao_risco")
CLASSES_APP = ("acao", "cripto")          # fundos e renda fixa não fazem parte do app novo


def _valor(R: dict, i: str):
    r = R.get(i) or {}
    if r.get("status") == "indisponivel" or r.get("valor") is None:
        return None
    try:
        return float(r["valor"])
    except (TypeError, ValueError):
        return None


def _serie(r: dict, pontos: int = 24) -> list[float]:
    s = [v for _, v in (r.get("serie") or []) if isinstance(v, (int, float))]
    return [round(float(v), 4) for v in s[-pontos:]]


def principais(R: dict) -> list[dict]:
    selic, ipca = _valor(R, "selic_meta"), _valor(R, "ipca_12m")
    out = []
    for i, rot, explica in PRINCIPAIS:
        if i == "juro_real":
            v = None if selic is None or ipca is None else ((1 + selic / 100) / (1 + ipca / 100) - 1) * 100
            out.append({"id": i, "rotulo": rot, "valor": v, "unidade": "% ao ano", "ref": None, "explica": explica, "serie": []})
            continue
        r = R.get(i) or {}
        out.append({"id": i, "rotulo": rot, "valor": _valor(R, i), "unidade": r.get("unidade") or "", "ref": r.get("periodo_ref"),
                    "explica": explica, "serie": _serie(r)})
    return out


def montar(foto: dict) -> dict:
    """Resposta de GET /cenario: veredito geral, números principais, fatores e os setores beneficiados e pressionados."""
    import macro_cenario as MC
    R, cen, fat = foto.get("indicadores") or {}, foto.get("cenarios") or {}, foto.get("fatores") or {}
    g = cen.get("geral") or {"veredito": "NEUTRO", "nota": 0.0, "confianca": "Baixa", "confianca_pontos": 0}
    bons, ruins = MC.beneficiados_e_pressionados(cen)

    def setor(c):
        top = (c.get("favor") or c.get("contra") or [{}])[0]
        return {"nome": c["nome"], "classe": c["classe"], "nota": c["nota"], "motivo": top.get("mecanismo") or ""}
    bons = [setor(c) for c in bons if c.get("classe") in CLASSES_APP][:5]
    ruins = [setor(c) for c in ruins if c.get("classe") in CLASSES_APP][:5]
    fatores = [{"id": f, "nome": fat[f]["nome"], "valor": fat[f]["valor"], "texto": fat[f].get("texto") or ""}
               for f in FATORES_TELA if f in fat and fat[f].get("valor") is not None]
    return {"geral": {"veredito": g["veredito"], "nota": g.get("nota"), "confianca": g.get("confianca"), "texto": MC.texto_geral(g, "iniciante")},
            "principais": principais(R), "fatores": fatores, "beneficiados": bons, "pressionados": ruins,
            "dados_ate": foto.get("dados_ate"), "aviso": AVISO}
