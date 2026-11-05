"""Indicadores macroeconômicos: catálogo, cadeia de fontes alternativas, validação e estado de cada dado.

Módulo puro (sem Streamlit e sem rede): quem busca os dados é injetado em `resolver(...)` (ver macro_rede.py). Por isso tudo aqui é testável.

O que ele garante, indicador por indicador:
  - tenta as fontes na ordem do catálogo (Banco Central, IBGE, Ipeadata, FRED, Focus) e para na primeira que devolve dado VÁLIDO;
  - valida o dado antes de aceitar (frequência esperada, faixa plausível de valores, mínimo de observações). Série com cara de errada
    é recusada e a causa fica registrada, em vez de aparecer como se fosse o indicador pedido;
  - registra cada tentativa (fonte, código, motivo da falha): é o diagnóstico mostrado na tela e usado para corrigir a causa real;
  - classifica o dado: atualizado, provisório (sujeito a revisão), revisado (mudou desde a última leitura), desatualizado ou
    indisponível. Dado antigo nunca é apresentado como atual e nada é inventado para preencher lacuna.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


class FonteErro(Exception):
    """Falha de uma fonte, com o motivo em português (vai para o diagnóstico)."""


# ------------------------------------------------------------------ catálogo
GRUPOS = {
    "juros": "Política monetária e juros",
    "inflacao": "Inflação",
    "atividade": "Atividade econômica",
    "trabalho": "Mercado de trabalho",
    "credito": "Crédito e endividamento",
    "fiscal": "Setor fiscal",
    "externo": "Câmbio e cenário externo",
}
STATUS_ROTULO = {"atualizado": "Atualizado", "provisorio": "Provisório (pode ser revisado)", "revisado": "Revisado",
                 "desatualizado": "Desatualizado", "indisponivel": "Indisponível"}
FREQ_DIAS = {"diaria": (1, 6), "mensal": (24, 36), "trimestral": (80, 100), "anual": (330, 400)}
FREQ_ROTULO = {"diaria": "diária", "mensal": "mensal", "trimestral": "trimestral", "anual": "anual"}
_PERIODOS_ANO = {"diaria": 252, "mensal": 12, "trimestral": 4, "anual": 1}

CATALOGO: dict[str, dict] = {}


def _i(id_, nome, grupo, unidade, freq, fontes, faixa=None, idade=None, modo="valor", var="pp", revisavel=False, glossario=None,
       por_que="", fonte_nome=None):
    """modo: 'valor' (mostra como vem), 'preco' (índice de preços vira variação % mensal se vier como nível) ou 'indice' (nível + variação 12m).
    var: 'pp' (diferença em pontos percentuais) ou 'pct' (variação percentual). idade = dias máximos para ainda ser 'atualizado'."""
    padrao_idade = {"diaria": 10, "mensal": 80, "trimestral": 170, "anual": 450}
    CATALOGO[id_] = dict(id=id_, nome=nome, grupo=grupo, unidade=unidade, freq=freq, fontes=fontes, faixa=faixa,
                         idade=idade or padrao_idade[freq], modo=modo, var=var, revisavel=revisavel, glossario=glossario,
                         por_que=por_que, fonte_nome=fonte_nome)


def sgs(codigo, anos=10):
    return {"tipo": "sgs", "codigo": codigo, "anos": anos}


def ipea(codigo):
    return {"tipo": "ipea", "codigo": codigo}


def ipea_busca(termos, preferir=(), evitar=()):
    return {"tipo": "ipea_busca", "termos": list(termos), "preferir": list(preferir), "evitar": list(evitar)}


def sidra(tabela, classif="", incl=(), excl=(), periodos=60):
    return {"tipo": "sidra", "tabela": tabela, "classif": classif, "incl": list(incl), "excl": list(excl), "periodos": periodos}


def fred(codigo):
    return {"tipo": "fred", "codigo": codigo}


def focus(indicador, ref="atual"):
    return {"tipo": "focus", "indicador": indicador, "ref": ref}


# --- política monetária e juros
_i("selic_meta", "Taxa Selic (meta do Copom)", "juros", "% ao ano", "diaria", [sgs(432, 10)], (0, 50), glossario="Selic",
   por_que="Custo básico do dinheiro no país: define quanto a renda fixa paga e quanto custa o crédito.")
_i("cdi", "Taxa DI/CDI (anualizada)", "juros", "% ao ano", "diaria", [sgs(4389, 5)], (0, 50), glossario="CDI",
   por_que="Referência da renda fixa pós-fixada e de grande parte dos fundos.")
_i("selic_mes", "Selic acumulada no mês", "juros", "% no mês", "mensal", [ipea("BM12_SELC12"), sgs(4390, 10), ipea("BM12_TJOVER12")], (0, 3), glossario="Selic",
   por_que="Quanto a Selic rendeu em cada mês.")
_i("focus_selic", "Expectativa de mercado para a Selic (fim do ano)", "juros", "% ao ano", "diaria", [focus("Selic", "atual")], (0, 50), idade=14,
   por_que="O que o mercado espera para os juros até dezembro (pesquisa Focus do Banco Central).")
# --- inflação
_i("ipca_mensal", "IPCA (variação mensal)", "inflacao", "% no mês", "mensal", [sgs(433, 10), ipea("PRECOS12_IPCA12"), ipea("PRECOS12_IPCAG12")], (-2, 6), modo="preco",
   glossario="IPCA", por_que="Inflação oficial: reajusta contratos e corrói o poder de compra.")
_i("ipca_12m", "IPCA (acumulado em 12 meses)", "inflacao", "% em 12 meses", "mensal", [sgs(13522, 10)], (-2, 30), glossario="IPCA",
   por_que="Inflação dos últimos 12 meses, comparada à meta do Banco Central.")
_i("ipca15", "IPCA-15 (prévia da inflação)", "inflacao", "% no mês", "mensal", [sgs(7478, 10)], (-2, 6), glossario="IPCA-15",
   por_que="Prévia do IPCA: antecipa a direção da inflação do mês.")
_i("inpc", "INPC (inflação para famílias de menor renda)", "inflacao", "% no mês", "mensal", [sgs(188, 10)], (-2, 6), glossario="INPC",
   por_que="Inflação sentida por famílias com renda de 1 a 5 salários mínimos.")
_i("igpm", "IGP-M (índice geral de preços do mercado)", "inflacao", "% no mês", "mensal",
   [sgs(189, 10), ipea("PRECOS12_IGPM12"), ipea("IGP12_IGPMG12"), ipea("IGP12_IGPM12")], (-5, 15), modo="preco", glossario="IGP-M",
   por_que="Indexador de aluguéis (shoppings, galpões) e de contratos de energia.")
_i("incc", "INCC (custo nacional da construção)", "inflacao", "% no mês", "mensal",
   [sgs(192, 10), ipea("IGP12_INCCG12"), ipea("IGP12_INCC12"), ipea_busca(["INCC"], preferir=["mensal", "variação", "m"], evitar=["di", "10", "ipc"])],
   (-2, 6), modo="preco", glossario="INCC", por_que="Pressão de custos em construtoras e incorporadoras.")
_i("nucleo_ipca", "Núcleo do IPCA (média aparada com suavização)", "inflacao", "% no mês", "mensal", [sgs(4466, 10)], (-1, 3), glossario="Núcleo da inflação",
   por_que="Retira os preços mais voláteis para mostrar a tendência da inflação.")
_i("focus_ipca", "Expectativa de mercado para o IPCA (ano corrente)", "inflacao", "% no ano", "diaria", [focus("IPCA", "atual")], (-2, 30), idade=14,
   por_que="O que o mercado espera para a inflação do ano (pesquisa Focus).")
# --- atividade
_i("ibcbr", "IBC-Br (prévia mensal do PIB)", "atividade", "pontos (índice)", "mensal", [ipea("SGS12_IBCBR12"), sgs(24364, 10), sgs(24363, 10)], (30, 500), idade=110,
   modo="indice", var="pct", revisavel=True, glossario="IBC-Br", por_que="Termômetro mensal da economia: o país está crescendo?")
_i("pim", "Produção industrial (indústria geral)", "atividade", "pontos (índice)", "mensal",
   [sidra(8888, "c544/129314", incl=["ajuste sazonal", "número-índice"], excl=["variação", "acumulad"]),
    sgs(21859, 10), ipea_busca(["produção industrial", "indústria geral"], preferir=["quantum", "geral", "dessaz"], evitar=["extrativa", "transforma", "mensal em"])],
   (20, 400), idade=110, modo="indice", var="pct", revisavel=True, glossario="PIM-PF", por_que="Demanda e desempenho das indústrias e dos bens de capital.")
_i("pmc", "Vendas no varejo (volume, PMC)", "atividade", "pontos (índice)", "mensal",
   [sidra(8880, "c11046/56734", incl=["ajuste sazonal"], excl=["variação"]),
    sidra(8880, "c11046/all", incl=["ajuste sazonal", "número-índice"], excl=["variação", "receita"]),
    ipea_busca(["vendas", "varejo"], preferir=["quantum", "volume", "restrito", "dessaz"], evitar=["ampliado", "nominal"])],
   (20, 400), idade=110, modo="indice", var="pct", revisavel=True, glossario="PMC", por_que="Força do consumo das famílias (Assaí, Carrefour, Magazine Luiza).")
_i("pms", "Volume de serviços (PMS)", "atividade", "pontos (índice)", "mensal",
   [sidra(5906, "c11046/all", incl=["ajuste sazonal", "número-índice"], excl=["variação", "receita"])], (20, 400), idade=110, modo="indice", var="pct",
   revisavel=True, glossario="PMS", por_que="Setor de serviços responde por cerca de dois terços da economia.")
_i("pib", "PIB (variação trimestral frente ao mesmo trimestre do ano anterior)", "atividade", "% a/a", "trimestral",
   [sidra(5932, "c11255/90707", incl=["mesmo trimestre do ano anterior"], excl=["acumulad"], periodos=24)], (-15, 15), idade=250, revisavel=True, glossario="PIB",
   por_que="Tamanho e ritmo da economia: base do consumo, do lucro das empresas e da arrecadação.")
_i("confianca_consumidor", "Confiança do consumidor (FGV)", "atividade", "pontos (índice)", "mensal", [sgs(4393, 10)], (30, 150), glossario="ICC",
   por_que="Disposição das famílias para consumir: antecipa o varejo.")
# --- trabalho
_i("desemprego", "Taxa de desocupação (PNAD Contínua)", "trabalho", "% da força de trabalho", "mensal",
   [sgs(24369, 10), sidra(6381, "", incl=["taxa de desocupação"], excl=["subutiliza"]), ipea_busca(["desocupação", "PNAD"], preferir=["taxa", "mensal"], evitar=["região", "estado"])],
   (1, 25), idade=110, revisavel=True, glossario="PNAD", por_que="Capacidade de consumo e de endividamento da população.")
_i("rendimento", "Rendimento médio real habitual (PNAD Contínua)", "trabalho", "R$ por mês", "mensal",
   [sidra(6390, "", incl=["rendimento médio", "habitual"], excl=["massa", "variação"])], (500, 20000), idade=110, revisavel=True, glossario="PNAD",
   por_que="Renda do trabalhador, já descontada a inflação.")
_i("massa_salarial", "Massa de rendimento real habitual (PNAD Contínua)", "trabalho", "R$ milhões por mês", "mensal",
   [sidra(6392, "", incl=["massa de rendimento", "habitual"], excl=["variação"])], (1e4, 5e6), idade=110, revisavel=True, glossario="PNAD",
   por_que="Total de renda do trabalho na economia: sustenta o consumo.")
# --- crédito
_i("inadimplencia", "Inadimplência da carteira de crédito", "credito", "% da carteira", "mensal", [sgs(21082, 10)], (0, 20), idade=100, glossario="Inadimplência",
   por_que="Parcela dos empréstimos com atraso acima de 90 dias: pressiona bancos e consumo.")
_i("juros_credito", "Taxa média de juros do crédito", "credito", "% ao ano", "mensal", [sgs(20714, 10)], (3, 120), idade=100,
   por_que="Custo médio do empréstimo para empresas e famílias.")
_i("concessoes", "Concessões de crédito (total)", "credito", "R$ milhões", "mensal", [sgs(20631, 10)], (1e4, 5e6), idade=100, modo="indice", var="pct",
   por_que="Volume de empréstimos novos: mostra se o crédito está fluindo.")
_i("endividamento", "Endividamento das famílias (% da renda)", "credito", "% da renda de 12 meses", "mensal", [sgs(29037, 10)], (10, 120), idade=110,
   por_que="Quanto das famílias já está comprometido com dívidas.")
# --- fiscal
_i("divida_bruta", "Dívida bruta do governo geral (% do PIB)", "fiscal", "% do PIB", "mensal", [sgs(13762, 10)], (30, 130), idade=110, glossario="DBGG",
   por_que="Tamanho da dívida pública em relação ao PIB: afeta juros longos e risco-país.")
_i("divida_liquida", "Dívida líquida do setor público (% do PIB)", "fiscal", "% do PIB", "mensal", [sgs(4513, 10)], (10, 100), idade=110,
   por_que="Dívida pública descontados os ativos do governo.")
_i("primario_12m", "Resultado primário do setor público (12 meses, % do PIB)", "fiscal", "% do PIB", "mensal", [sgs(5793, 10)], (-10, 10), idade=110,
   glossario="Resultado primário", por_que="Receitas menos despesas, sem juros: positivo = o governo economiza para pagar a dívida.")
# --- câmbio e externo
_i("dolar", "Dólar comercial (venda)", "externo", "R$ por US$", "diaria", [sgs(1, 5)], (1, 15), glossario="Câmbio",
   por_que="Afeta exportadoras (receita em dólar) e empresas que importam insumos.")
_i("embi", "Risco-país (EMBI+ Brasil)", "externo", "pontos-base", "diaria", [ipea("BM12_EMBI12"), ipea("JPM366_EMBI366")], (50, 3000), idade=20, glossario="Risco-país",
   por_que="Prêmio de risco exigido para investir no Brasil.")
_i("fed_funds", "Juros dos Estados Unidos (Fed Funds)", "externo", "% ao ano", "diaria", [fred("DFF")], (0, 25), idade=10, glossario="Fed Funds",
   por_que="Juros americanos atraem capital para fora do Brasil quando sobem e pressionam ativos de risco.")
_i("us10y", "Treasury de 10 anos dos EUA", "externo", "% ao ano", "diaria", [fred("DGS10")], (0, 25), idade=10, glossario="Treasury",
   por_que="Taxa livre de risco global: referência para valuation de ações e cripto.")
_i("us_cpi", "Inflação dos Estados Unidos (CPI)", "externo", "pontos (índice)", "mensal", [fred("CPIAUCSL")], (100, 1000), idade=80, modo="indice", var="pct",
   por_que="Inflação americana: define o ritmo dos juros nos EUA.")
_i("brent", "Petróleo Brent", "externo", "US$ por barril", "diaria", [fred("DCOILBRENTEU")], (10, 250), idade=12, glossario="Brent",
   por_que="Receita de petroleiras e custo de combustíveis e transporte.")
_i("minerio", "Minério de ferro", "externo", "US$ por tonelada", "mensal", [fred("PIORECRUSDM")], (20, 400), idade=100,
   por_que="Receita de mineradoras e siderúrgicas.")
_i("dxy", "Dólar global (índice amplo ponderado pelo comércio)", "externo", "pontos (índice)", "diaria", [fred("DTWEXBGS")], (50, 250), idade=12,
   por_que="Força do dólar frente às principais moedas: dólar forte costuma pressionar emergentes.")
_i("vix", "VIX (medo no mercado americano)", "externo", "pontos", "diaria", [fred("VIXCLS")], (5, 120), idade=10, glossario="VIX",
   por_que="Mede a aversão a risco: sobe quando o mercado fica nervoso.")

# Itens do pedido que NÃO têm fonte pública gratuita e estável hoje (aparecem em "Cobertura", com o motivo).
NAO_COBERTOS = {
    "Curva de juros (DI futuro)": "A B3 não oferece API pública gratuita; a pesquisa Focus (expectativa da Selic) cobre parte da informação.",
    "Geração de empregos formais (Novo Caged)": "O Ministério do Trabalho publica planilhas, sem API estável. Fica para uma etapa futura.",
    "Resultado nominal e despesas/receitas do governo": "As séries do Banco Central e do Tesouro precisam de conferência de código; cobertos por dívida e resultado primário.",
    "Condições de financiamento": "Não existe série pública única; juros, inadimplência e concessões de crédito formam o retrato.",
    "Consumo das famílias (contas nacionais)": "Só sai junto com o PIB trimestral; use varejo, confiança e renda como termômetros mensais.",
    "Inflação internacional além dos EUA": "Sem fonte única gratuita; a inflação americana é a referência global usada.",
}


def indicadores_do_grupo(grupo: str) -> list[str]:
    return [k for k, v in CATALOGO.items() if v["grupo"] == grupo]


# ------------------------------------------------------------------ séries
def _serie(df) -> pd.Series:
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    s = df["valor"] if hasattr(df, "columns") and "valor" in df.columns else df
    s = pd.to_numeric(pd.Series(s), errors="coerce").dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]


def validar_frequencia(s: pd.Series, freq: str) -> str | None:
    """None se a frequência dos dados bate com a esperada; senão o motivo."""
    if len(s) < 3:
        return None
    dias = pd.Series(s.index).diff().dt.days.dropna()
    mediana = float(dias.tail(24).median())
    lo, hi = FREQ_DIAS[freq]
    if freq == "diaria":
        return None if mediana <= 7 else f"a série vem com intervalo de ~{mediana:.0f} dias, mas o esperado era diário"
    return None if lo <= mediana <= hi else f"intervalo médio de {mediana:.0f} dias não bate com a frequência {FREQ_ROTULO[freq]} esperada"


def validar_faixa(valor: float, faixa) -> str | None:
    if not faixa:
        return None
    lo, hi = faixa
    return None if lo <= valor <= hi else f"último valor ({valor:g}) fora da faixa plausível ({lo:g} a {hi:g}): pode ser outra série"


def aplicar_modo(s: pd.Series, modo: str) -> pd.Series:
    """'preco': se a fonte entregou o NÍVEL do índice (mediana > 30), converte em variação % de um período."""
    if modo == "preco" and len(s) > 3 and abs(float(s.abs().median())) > 30:
        return (s.pct_change() * 100).dropna()
    return s


def _passo(freq: str) -> int:
    return _PERIODOS_ANO[freq]


def estatisticas(s: pd.Series, freq: str, modo: str, var: str) -> dict:
    """Nível, variação do período anterior, variação em 12 meses, aceleração e posição histórica. Só números reais da série."""
    if s.empty:
        return {}
    n = _passo(freq)
    ult = float(s.iloc[-1])
    ant = float(s.iloc[-2]) if len(s) > 1 else None
    out = {"valor": ult, "anterior": ant}
    if ant is not None:
        out["variacao"] = (ult / ant - 1) * 100 if var == "pct" and ant not in (0, None) else ult - ant
    k = {"diaria": 21, "mensal": 3, "trimestral": 1, "anual": 1}[freq]
    out["tipo_variacao"] = "%" if var == "pct" else "p.p."
    if len(s) > n:
        base = float(s.iloc[-1 - n])
        out["v12"] = (ult / base - 1) * 100 if base else None
        out["d12"] = ult - base
    if len(s) > k:
        base = float(s.iloc[-1 - k])
        out["v_curto"] = (ult / base - 1) * 100 if base else None
        out["d_curto"] = ult - base
        if len(s) > 2 * k:
            base2 = float(s.iloc[-1 - 2 * k])
            out["d_curto_ant"] = float(s.iloc[-1 - k]) - base2
    janela = s.tail(max(n * 5, 24)) if freq != "diaria" else s.tail(1260)
    out["percentil"] = float((janela <= ult).mean() * 100) if len(janela) >= 12 else None
    out["media_5a"] = float(janela.mean()) if len(janela) >= 12 else None
    return out


def comprimir(s: pd.Series, freq: str, max_pontos: int = 150) -> list:
    """Série para guardar/exibir: diária vira o último valor de cada mês (leve, sem perder a leitura do histórico)."""
    if s.empty:
        return []
    if freq == "diaria" and len(s) > max_pontos:
        s = s.groupby([s.index.year, s.index.month]).tail(1)
    s = s.tail(max_pontos)
    return [[i.strftime("%Y-%m-%d"), round(float(v), 6)] for i, v in s.items()]


def _agora(agora):
    agora = agora or datetime.now(timezone.utc)
    return agora.replace(tzinfo=None) if agora.tzinfo else agora


def status_do_dado(spec: dict, ultima, agora=None, anterior_snapshot: dict | None = None, valor=None) -> tuple[str, str]:
    """(status, motivo). 'desatualizado' = última observação mais velha que o limite do indicador."""
    agora = _agora(agora)
    idade = (agora - pd.Timestamp(ultima).to_pydatetime()).days
    if idade > spec["idade"]:
        return "desatualizado", f"última observação em {pd.Timestamp(ultima):%m/%Y}, há {idade} dias (limite de {spec['idade']})"
    ant = anterior_snapshot or {}
    if ant.get("data") == pd.Timestamp(ultima).strftime("%Y-%m-%d") and ant.get("valor") is not None and valor is not None \
            and abs(float(ant["valor"]) - float(valor)) > 1e-9 * max(1.0, abs(float(valor))) and abs(float(ant["valor"]) - float(valor)) > 0.005:
        return "revisado", f"o valor de {pd.Timestamp(ultima):%m/%Y} mudou de {ant['valor']:g} para {valor:g} desde a leitura anterior"
    if spec["revisavel"] and idade <= spec["idade"] - 20:
        return "provisorio", "a fonte revisa esta série nas divulgações seguintes"
    return "atualizado", ""


# ------------------------------------------------------------------ resolução com fontes alternativas
def _indisponivel(spec, tentativas, motivo):
    return {"id": spec["id"], "nome": spec["nome"], "grupo": spec["grupo"], "unidade": spec["unidade"], "freq": spec["freq"], "status": "indisponivel",
            "status_rotulo": STATUS_ROTULO["indisponivel"], "motivo": motivo, "valor": None, "data": None, "fonte": None, "codigo": None,
            "serie": [], "tentativas": tentativas}


def resolver(ind_id: str, buscadores: dict, agora=None, anterior: dict | None = None) -> dict:
    """Resolve UM indicador. `buscadores[tipo](fonte_spec)` devolve (DataFrame com coluna 'valor', meta dict) ou levanta FonteErro.
    Nunca levanta exceção: no pior caso devolve o indicador como 'indisponivel', com o motivo de cada tentativa."""
    spec = CATALOGO[ind_id]
    tentativas = []
    for f in spec["fontes"]:
        tipo = f["tipo"]
        rot = {"sgs": "Banco Central (SGS)", "ipea": "Ipeadata", "ipea_busca": "Ipeadata (busca no catálogo)", "sidra": "IBGE (SIDRA)",
               "fred": "FRED (Federal Reserve de St. Louis)", "focus": "Banco Central (Focus)"}[tipo]
        cod = f.get("codigo") or (f"tabela {f['tabela']}" if tipo == "sidra" else ", ".join(f.get("termos", [])) or f.get("indicador", ""))
        t = {"fonte": rot, "codigo": str(cod), "ok": False, "motivo": ""}
        tentativas.append(t)
        fn = buscadores.get(tipo)
        if fn is None:
            t["motivo"] = "fonte não configurada"
            continue
        try:
            df, meta = fn(f)
        except FonteErro as e:
            t["motivo"] = str(e)[:300]
            continue
        except Exception as e:                      # noqa: BLE001 - qualquer falha vira motivo, nunca derruba a página
            t["motivo"] = f"erro inesperado ({e.__class__.__name__})"
            continue
        s = aplicar_modo(_serie(df), spec["modo"])
        if len(s) < 3:
            t["motivo"] = "a fonte respondeu, mas com menos de 3 observações"
            continue
        erro = validar_faixa(float(s.iloc[-1]), spec["faixa"]) or validar_frequencia(s, spec["freq"])
        if erro:
            t["motivo"] = "dado recusado: " + erro
            continue
        t["ok"] = True
        est = estatisticas(s, spec["freq"], spec["modo"], spec["var"])
        status, motivo = status_do_dado(spec, s.index[-1], agora, anterior, est["valor"])
        t["motivo"] = "usada"
        meta = meta or {}
        return {"id": spec["id"], "nome": spec["nome"], "grupo": spec["grupo"], "unidade": meta.get("unidade") or spec["unidade"], "freq": spec["freq"],
                "status": status, "status_rotulo": STATUS_ROTULO[status], "motivo": motivo, "valor": est["valor"], "anterior": est.get("anterior"),
                "variacao": est.get("variacao"), "tipo_variacao": est.get("tipo_variacao"), "v12": est.get("v12"), "d12": est.get("d12"),
                "v_curto": est.get("v_curto"), "d_curto": est.get("d_curto"), "d_curto_ant": est.get("d_curto_ant"),
                "percentil": est.get("percentil"), "media_5a": est.get("media_5a"), "data": s.index[-1].strftime("%Y-%m-%d"),
                "periodo_ref": periodo_ref(s.index[-1], spec["freq"]), "fonte": rot, "codigo": str(meta.get("codigo") or cod),
                "serie_nome": meta.get("nome") or "", "serie": comprimir(s, spec["freq"]), "tentativas": tentativas,
                "atualizado_em": _agora(agora).strftime("%Y-%m-%dT%H:%M:%S")}
    motivos = "; ".join(f"{t['fonte']} ({t['codigo']}): {t['motivo']}" for t in tentativas)
    return _indisponivel(spec, tentativas, "Nenhuma fonte devolveu dado válido. " + motivos)


def periodo_ref(data, freq: str) -> str:
    d = pd.Timestamp(data)
    if freq == "trimestral":
        return f"{(d.month - 1) // 3 + 1}º trimestre de {d.year}"
    if freq == "diaria":
        return f"{d:%d/%m/%Y}"
    if freq == "anual":
        return f"{d.year}"
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    return f"{meses[d.month - 1]} de {d.year}"


def marcar_revisao(res: dict, anterior: dict | None) -> dict:
    """Se a leitura anterior era da MESMA data e o valor mudou, o dado foi revisado pela fonte (não é uma observação nova)."""
    if not res or res.get("status") not in ("atualizado", "provisorio") or not anterior:
        return res
    if anterior.get("data") == res.get("data") and anterior.get("valor") is not None and res.get("valor") is not None \
            and abs(float(anterior["valor"]) - float(res["valor"])) > max(0.005, 1e-9 * abs(float(res["valor"]))):
        res = dict(res)
        res["status"], res["status_rotulo"] = "revisado", STATUS_ROTULO["revisado"]
        res["motivo"] = f"o valor de {periodo_ref(res['data'], res['freq'])} mudou de {anterior['valor']:g} para {res['valor']:g} desde a leitura anterior"
    return res


def resolver_todos(buscadores: dict, agora=None, anteriores: dict | None = None, ids=None) -> dict:
    anteriores = anteriores or {}
    return {i: resolver(i, buscadores, agora, anteriores.get(i)) for i in (ids or CATALOGO)}


def para_serie(ind: dict) -> pd.Series:
    """Reconstrói a série (índice de datas) de um resultado guardado."""
    if not ind or not ind.get("serie"):
        return pd.Series(dtype=float)
    return pd.Series([v for _, v in ind["serie"]], index=pd.to_datetime([d for d, _ in ind["serie"]]), dtype=float)


def cobertura(resultados: dict) -> dict:
    """Resumo para a tela: quantos indicadores por estado e quais continuam indisponíveis."""
    cont = {k: 0 for k in STATUS_ROTULO}
    for r in resultados.values():
        cont[r["status"]] = cont.get(r["status"], 0) + 1
    return {"total": len(resultados), "contagem": cont, "indisponiveis": [r["id"] for r in resultados.values() if r["status"] == "indisponivel"],
            "desatualizados": [r["id"] for r in resultados.values() if r["status"] == "desatualizado"]}
