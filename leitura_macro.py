"""
leitura_macro.py - Assistente que resume O QUE OS DADOS ESTAO DIZENDO (nao o que cada indicador e).

Cada funcao ler_* recebe a serie (DataFrame com coluna 'valor', indice de datas) e devolve
{"titulo", "tom", "texto"} ou None se nao houver dados. tom: "pos" | "neg" | "neu".
As regras sao simples e transparentes (limiares comentados), para voce poder ajustar.
"""
from __future__ import annotations

import pandas as pd


# ------------------------------------------------------------------ utilitarios
def _n(v: float, c: int = 2) -> str:
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sinal(v: float, c: int = 2, suf: str = "") -> str:
    return ("+" if v >= 0 else "−") + _n(abs(v), c) + suf


def _limpa(df) -> pd.Series | None:
    if df is None or len(df) == 0 or "valor" not in df:
        return None
    s = df["valor"].dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s if len(s) >= 3 else None


def _antes(s: pd.Series, dias: int):
    """Valor da serie ha 'dias' dias (ou o mais proximo anterior)."""
    ant = s.loc[: s.index[-1] - pd.Timedelta(days=dias)]
    return float(ant.iloc[-1]) if len(ant) else None


def _janela(s: pd.Series, anos: int) -> pd.Series:
    return s.loc[s.index >= s.index[-1] - pd.DateOffset(years=anos)]


def _posicao(s: pd.Series, anos: int) -> str:
    """Onde o ultimo valor esta dentro do periodo escolhido."""
    j = _janela(s, anos)
    if len(j) < 5:
        return ""
    ult, mn, mx = float(j.iloc[-1]), float(j.min()), float(j.max())
    tag = f"nos últimos {anos} ano{'s' if anos > 1 else ''}"
    if ult >= mx:
        return f"É o maior valor {tag}."
    if ult <= mn:
        return f"É o menor valor {tag}."
    pr = float((j <= ult).mean() * 100)
    return f"Está acima de {_n(pr, 0)}% das leituras {tag} (mín. {_n(mn)}, máx. {_n(mx)})."


def _ultima_mudanca(s: pd.Series):
    """(data em que passou ao valor atual, valor anterior) - util para a Selic, que anda em degraus."""
    atual = s.iloc[-1]
    dif = s[s != atual]
    if dif.empty:
        return None
    pos = s.index.get_loc(dif.index[-1])
    if pos + 1 >= len(s):
        return None
    return s.index[pos + 1], float(dif.iloc[-1])


def _leitura(titulo: str, tom: str, partes: list) -> dict:
    return {"titulo": titulo, "tom": tom, "texto": " ".join(p for p in partes if p)}


# ------------------------------------------------------------------ Banco Central
def ler_selic(df, ipca_df=None, anos: int = 2):
    s = _limpa(df)
    if s is None:
        return None
    atual = float(s.iloc[-1])
    p = [f"A Selic meta está em {_n(atual)}% a.a."]
    m = _ultima_mudanca(s)
    if m:
        data, ant = m
        mov = atual - ant
        p.append(f"O último movimento foi em {data:%d/%m/%Y}: {'alta' if mov > 0 else 'queda'} de "
                 f"{_n(abs(mov))} p.p. (de {_n(ant)}% para {_n(atual)}%).")
    a12 = _antes(s, 365)
    traj = 0
    if a12 is not None:
        d = atual - a12
        if abs(d) < 0.25:
            p.append("Está praticamente no mesmo nível de 12 meses atrás.")
        else:
            traj = 1 if d > 0 else -1
            p.append(f"Há 12 meses estava em {_n(a12)}% ({_sinal(d, 2)} p.p. desde então).")

    tom = "neu"
    ipca = _limpa(ipca_df)
    if ipca is not None:
        real = atual - float(ipca.iloc[-1])
        p.append(f"Descontado o IPCA de 12 meses ({_n(float(ipca.iloc[-1]))}%), o juro real fica em "
                 f"cerca de {_n(real)} p.p.")
        # limiares: >=7 muito restritivo | 4 a 7 restritivo | <4 moderado
        if real >= 7:
            tom = "neg"
            p.append("É um patamar muito alto: a renda fixa paga bem sem risco, o capital das empresas fica caro "
                     "e o peso costuma recair mais sobre empresas endividadas e de crescimento.")
        elif real >= 4:
            p.append("É um patamar ainda restritivo: a renda fixa segue competitiva com a bolsa, e sinais de "
                     "queda da Selic tendem a ajudar o valuation das ações.")
        else:
            tom = "pos"
            p.append("É um patamar moderado: reduz o apelo da renda fixa e costuma favorecer o valuation das ações.")
    if traj < 0:
        p.append("A trajetória em 12 meses é de queda, o que alivia o custo de capital.")
    elif traj > 0:
        p.append("A trajetória em 12 meses é de alta, o que pressiona o custo de capital.")
    return _leitura("Selic (juros)", tom, p)


def ler_ipca(df, anos: int = 2):
    s = _limpa(df)
    if s is None:
        return None
    atual = float(s.iloc[-1])
    p = [f"O IPCA em 12 meses está em {_n(atual)}% (referência {s.index[-1]:%m/%Y})."]
    # meta 3,0% com tolerancia de 1,5 p.p. (teto 4,5%)
    if atual > 4.5:
        tom = "neg"
        p.append("Está acima do teto da banda de tolerância da meta (4,5%).")
    elif atual > 3.5:
        tom = "neu"
        p.append("Está dentro da banda da meta, mas acima do centro (3%).")
    else:
        tom = "pos"
        p.append("Está próximo ou abaixo do centro da meta (3%).")
    a3, a12 = _antes(s, 92), _antes(s, 365)
    if a3 is not None:
        d = atual - a3
        if abs(d) >= 0.15:
            p.append(f"Em 3 meses {'acelerou' if d > 0 else 'desacelerou'} {_n(abs(d))} p.p.")
            p.append("Isso reduz a margem para cortes de juros." if d > 0 else "Isso abre espaço para cortes de juros.")
    if a12 is not None:
        p.append(f"Há 12 meses estava em {_n(a12)}%.")
    return _leitura("Inflação (IPCA)", tom, p)


def ler_dolar(df, anos: int = 2):
    s = _limpa(df)
    if s is None:
        return None
    atual = float(s.iloc[-1])
    p = [f"O dólar está em R$ {_n(atual)} (leitura de {s.index[-1]:%d/%m/%Y})."]
    a3, a12 = _antes(s, 92), _antes(s, 365)
    if a3:
        p.append(f"Variação em 3 meses: {_sinal((atual / a3 - 1) * 100, 1, '%')}.")
    v12 = None
    if a12:
        v12 = (atual / a12 - 1) * 100
        p.append(f"Em 12 meses: {_sinal(v12, 1, '%')}.")
    p.append(_posicao(s, anos))
    # limiar de 8% em 12 meses
    if v12 is not None and v12 >= 8:
        p.append("O real se desvalorizou: costuma favorecer exportadoras (commodities, papel e celulose) e "
                 "pressionar quem tem custos ou dívidas em dólar, além da inflação.")
    elif v12 is not None and v12 <= -8:
        p.append("O real se valorizou: alivia custos, dívidas em dólar e inflação, mas reduz a receita em reais "
                 "das exportadoras.")
    else:
        p.append("O câmbio está relativamente estável em 12 meses, sem grande efeito adicional sobre as empresas.")
    return _leitura("Dólar (câmbio)", "neu", p)


def ler_desemprego(df, anos: int = 2):
    s = _limpa(df)
    if s is None:
        return None
    atual = float(s.iloc[-1])
    p = [f"O desemprego (PNAD) está em {_n(atual, 1)}% (referência {s.index[-1]:%m/%Y})."]
    a12 = _antes(s, 365)
    tom = "neu"
    if a12 is not None:
        d = atual - a12
        p.append(f"Há 12 meses estava em {_n(a12, 1)}% ({_sinal(d, 1)} p.p.).")
        if d <= -0.5:
            tom = "pos"
            p.append("A queda sustenta renda e consumo (varejo, serviços), mas um mercado de trabalho apertado "
                     "também pode manter a inflação de serviços e os juros altos.")
        elif d >= 0.5:
            tom = "neg"
            p.append("A alta enfraquece a renda e o consumo e tende a aumentar a inadimplência.")
        else:
            p.append("Sem mudança relevante no último ano.")
    p.append(_posicao(s, anos))
    return _leitura("Emprego (desemprego)", tom, p)


# ------------------------------------------------------------------ Ipeadata
# titulo (igual ao de IPEA_CATEGORIAS) -> (tipo, sentido, frase se subir, frase se cair)
#   tipo: "nivel" (variacao em %), "taxa" (variacao em p.p.), "mensal" (taxa mensal em %)
#   sentido: +1 alta e boa | -1 alta e ruim | 0 neutro
SPEC_IPEA = {
    "Risco-País EMBI+ Brasil (pontos)": ("nivel", -1,
        "Risco maior encarece o capital e costuma pesar sobre a bolsa.",
        "Risco menor barateia o capital e costuma ajudar a bolsa."),
    "IPCA mensal (%)": ("mensal", -1,
        "Inflação mensal mais forte repassa custos ao consumidor.",
        "Inflação mensal mais fraca alivia o consumidor."),
    "IGP-M mensal (%)": ("mensal", -1,
        "Mais pressão nos custos de atacado e nos reajustes de aluguéis e contratos de elétricas.",
        "Menos pressão nos reajustes de aluguéis e contratos de elétricas."),
    "INCC mensal (%)": ("mensal", -1,
        "Custo da obra subindo comprime a margem de construtoras e incorporadoras.",
        "Custo da obra mais comportado ajuda as margens de construtoras."),
    "IBC-Br (prévia do PIB)": ("nivel", 1,
        "Atividade em expansão favorece cíclicas, consumo e indústria.",
        "Atividade perdendo fôlego pede cautela com empresas cíclicas."),
    "Produção industrial (geral)": ("nivel", 1,
        "Indústria em alta indica demanda firme para bens de capital e insumos.",
        "Indústria em queda indica demanda mais fraca para bens de capital e insumos."),
    "Vendas no varejo (PMC)": ("nivel", 1,
        "Consumo mais forte favorece o varejo.",
        "Consumo mais fraco pressiona o varejo."),
    "Desemprego PNAD (%)": ("taxa", -1,
        "Desemprego maior enfraquece renda, consumo e crédito.",
        "Desemprego menor sustenta renda, consumo e crédito."),
}


def ler_ipea(titulo: str, df, unidade_pts: bool = False):
    spec = SPEC_IPEA.get(titulo)
    s = _limpa(df)
    if spec is None or s is None:
        return None
    tipo, sentido, f_sobe, f_cai = spec
    atual = float(s.iloc[-1])
    nome = titulo.split(" (")[0]
    p = []
    sobe = None
    if tipo == "mensal":
        acum12 = float(((1 + s.tail(12) / 100).prod() - 1) * 100) if len(s) >= 12 else None
        media12 = float(s.tail(12).mean()) if len(s) >= 12 else None
        p.append(f"{nome}: {_n(atual)}% em {s.index[-1]:%m/%Y}.")
        if acum12 is not None:
            p.append(f"O acumulado dos últimos 12 meses é de cerca de {_n(acum12)}%.")
        if media12 is not None and abs(atual - media12) >= 0.1:
            sobe = atual > media12
            p.append(f"O mês ficou {'acima' if sobe else 'abaixo'} da média dos últimos 12 meses ({_n(media12)}%).")
    else:
        ref = _antes(s, 365)
        suf = " pts" if unidade_pts else ""
        casas = 0 if tipo == "nivel" and atual > 200 else 1
        p.append(f"{nome}: {_n(atual, casas)}{suf if tipo == 'nivel' else '%'} em {s.index[-1]:%m/%Y}.")
        if ref:
            if tipo == "nivel":
                v = (atual / ref - 1) * 100
                sobe = v > 0 if abs(v) >= 1 else None
                p.append(f"Em 12 meses: {_sinal(v, 1, '%')}.")
            else:
                v = atual - ref
                sobe = v > 0 if abs(v) >= 0.3 else None
                p.append(f"Em 12 meses: {_sinal(v, 1)} p.p.")
    if sobe is None:
        tom = "neu"
        p.append("Sem mudança relevante frente ao período de comparação.")
    else:
        p.append(f_sobe if sobe else f_cai)
        tom = "neu" if sentido == 0 else ("pos" if (sobe and sentido > 0) or (not sobe and sentido < 0) else "neg")
    return _leitura(nome, tom, p)


# ------------------------------------------------------------------ sintese
def montar_sintese(leituras: list) -> str:
    leituras = [l for l in leituras if l]
    if not leituras:
        return "Sem dados suficientes para resumir o cenário agora."
    pos = [l["titulo"] for l in leituras if l["tom"] == "pos"]
    neg = [l["titulo"] for l in leituras if l["tom"] == "neg"]
    neu = [l for l in leituras if l["tom"] == "neu"]
    if len(neg) > len(pos) + 1:
        quadro = "predominantemente de cautela"
    elif len(pos) > len(neg) + 1:
        quadro = "predominantemente favorável"
    else:
        quadro = "misto"
    txt = (f"Dos {len(leituras)} indicadores lidos, {len(pos)} sinalizam ambiente favorável, {len(neg)} pedem "
           f"atenção e {len(neu)} estão neutros. O quadro é {quadro}.")
    if neg:
        txt += " Pontos de atenção: " + ", ".join(neg) + "."
    if pos:
        txt += " Pontos favoráveis: " + ", ".join(pos) + "."
    return txt


def texto_plano(sintese: str, leituras: list) -> str:
    linhas = ["LEITURA DO CENÁRIO ECONÔMICO", "", sintese, ""]
    icone = {"pos": "[+]", "neg": "[-]", "neu": "[=]"}
    for l in leituras:
        if l:
            linhas.append(f"{icone[l['tom']]} {l['titulo']}: {l['texto']}")
    linhas += ["", "Leitura automática por regras simples sobre os dados; não é recomendação de investimento."]
    return "\n".join(linhas)
