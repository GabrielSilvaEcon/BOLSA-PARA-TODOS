"""Passo 23 — Notificações inteligentes: regras puras, sem Streamlit e sem rede (por isso testáveis e usáveis pelo monitor).

O que este módulo faz e NÃO duplica:
  - Os três motores de alerta que já existiam continuam sendo a fonte dos avisos de inteligência (intel.avaliar_alertas), de notícias e
    eventos (noticias_eventos.avaliar_alertas_ne) e técnicos (analise_tecnica.avaliar_alertas_tec). Aqui só se converte o disparo deles em
    uma notificação padrão (`de_disparo`) para ser guardada no banco, deduplicada e entregue.
  - O que era novo no pedido vira regras do monitor: preço acima/abaixo, valorização/queda percentual, máxima/mínima do período, variação
    incomum e mudança de indicador fundamentalista, cada uma só para as classes de ativo compatíveis (COMPAT).
  - Priorização "inteligente": regra explicável (`pontuar`/`explicar`), sem chamada a IA externa e sem inventar fatos. Cada explicação
    separa o FATO (o que a fonte/dado mostra) da INTERPRETAÇÃO (leitura do app) e informa a incerteza. Nada aqui é recomendação.
Nenhuma função compra, vende ou altera posições.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timedelta, timezone

import seguranca as seg

CATEGORIAS = {"preco": "Preço", "tecnico": "Técnico", "fundamentalista": "Fundamentos", "carteira": "Carteira e risco",
              "noticia": "Notícias", "evento": "Eventos e calendário", "macro": "Cenário econômico", "sistema": "Sistema"}
IMPORTANCIAS = ("alta", "media", "baixa")
ROTULO_IMPORT = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}
_ORDEM = {"alta": 3, "media": 2, "baixa": 1}
CANAIS = {"app": "No aplicativo", "email": "E-mail", "telegram": "Telegram", "ntfy": "Push no celular (ntfy)"}
EXTERNOS = ("email", "telegram", "ntfy")

# ------------------------------------------------------------------ classes e compatibilidade
CLASSES = {"acao": "Ações", "bdr": "BDRs", "fii": "FIIs", "etf": "ETFs", "cripto": "Criptomoedas", "fundo": "Fundos de investimento",
           "renda_fixa": "Renda fixa"}
_COM_COTACAO = ("acao", "bdr", "fii", "etf", "cripto")          # têm cotação de mercado em tempo (quase) real
TIPOS_MON = {
    "preco_acima": {"rotulo": "Preço acima de um valor", "classes": _COM_COTACAO},
    "preco_abaixo": {"rotulo": "Preço abaixo de um valor", "classes": _COM_COTACAO},
    "alta_pct": {"rotulo": "Valorização percentual", "classes": _COM_COTACAO},
    "queda_pct": {"rotulo": "Queda percentual", "classes": _COM_COTACAO},
    "extremo": {"rotulo": "Máxima ou mínima do período", "classes": _COM_COTACAO},
    "variacao_incomum": {"rotulo": "Variação incomum", "classes": _COM_COTACAO},
    "fund_mudanca": {"rotulo": "Mudança em indicador fundamentalista", "classes": ("acao", "bdr", "fii")},
}
INDICADORES = {
    "acao": {"pl": "P/L", "pvp": "P/VP", "dy": "Dividend yield (%)", "roe": "ROE (%)", "margem_liq": "Margem líquida (%)",
             "div_pl": "Dívida líquida/Patrimônio", "ev_ebitda": "EV/EBITDA"},
    "fii": {"pvp": "P/VP", "dy": "Dividend yield (%)"},
}
INDICADORES["bdr"] = INDICADORES["acao"]
ALTERNATIVAS = {
    "renda_fixa": "Renda fixa não tem cotação de mercado diária: use o alerta de vencimento (Central de inteligência) e os limites da carteira.",
    "fundo": "Fundos de investimento têm cota, não preço de mercado: use os alertas de carteira e de risco.",
    "cripto_fund": "Para criptomoedas, os indicadores próprios (atividade de rede, oferta, capitalização, TVL) aparecem na Central de inteligência.",
}
_RE_ATIVO = re.compile(r"[^A-Za-z0-9.\-^=]")


def tipos_para_classe(classe: str) -> dict:
    return {k: v["rotulo"] for k, v in TIPOS_MON.items() if classe in v["classes"]}


def compativel(tipo: str, classe: str) -> bool:
    return tipo in TIPOS_MON and classe in TIPOS_MON[tipo]["classes"]


def nova_regra_mon(tipo: str, ativo: str, classe: str, params: dict | None = None, importancia: str = "media", ativa: bool = True,
                   id_: str | None = None) -> dict:
    """Regra do monitor. Levanta ValueError (texto amigável) se o tipo não combina com a classe ou se o valor é inválido."""
    if tipo not in TIPOS_MON:
        raise ValueError("Tipo de alerta desconhecido.")
    if classe not in CLASSES:
        raise ValueError("Classe de ativo desconhecida.")
    if not compativel(tipo, classe):
        raise ValueError(ALTERNATIVAS.get(classe) or f"Este alerta não se aplica a {CLASSES[classe].lower()}.")
    a = _RE_ATIVO.sub("", str(ativo or "")).upper()[:24]
    if not a:
        raise ValueError("Informe o ativo.")
    p = dict(params or {})

    def num(k, lo, hi, padrao=None, obrigatorio=False):
        v = p.get(k, padrao)
        if v in (None, ""):
            if obrigatorio:
                raise ValueError("Informe o valor do alerta.")
            return
        try:
            f = float(str(v).replace(",", "."))
        except ValueError:
            raise ValueError("Valor inválido.") from None
        if not math.isfinite(f) or not lo <= f <= hi:
            raise ValueError(f"O valor deve ficar entre {lo:g} e {hi:g}.")
        p[k] = f

    if tipo in ("preco_acima", "preco_abaixo"):
        num("nivel", 0.0000001, 1e9, obrigatorio=True)
    elif tipo in ("alta_pct", "queda_pct"):
        num("limite_pct", 0.1, 1000, 5, True)
        p["janela"] = p.get("janela") if p.get("janela") in ("1d", "5d", "30d") else "1d"
    elif tipo == "extremo":
        p["sentido"] = p.get("sentido") if p.get("sentido") in ("max", "min") else "max"
        p["periodo"] = p.get("periodo") if p.get("periodo") in ("3m", "6m", "52s") else "52s"
    elif tipo == "variacao_incomum":
        num("desvios", 2, 10, 3)
    elif tipo == "fund_mudanca":
        if p.get("campo") not in INDICADORES.get(classe, {}):
            raise ValueError("Escolha um indicador compatível com a classe do ativo.")
        num("limite_pct", 1, 1000, 15)
    imp = importancia if importancia in IMPORTANCIAS else "media"
    base = f"mon:{tipo}:{a}:" + ",".join(f"{k}={v}" for k, v in sorted(p.items()))
    return {"id": id_ or re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:90], "tipo": tipo, "ativo": a, "classe": classe,
            "params": p, "importancia": imp, "ativa": bool(ativa), "origem": "monitor"}


def descrever_regra_mon(r: dict) -> str:
    p, t = r.get("params") or {}, r["tipo"]
    if t in ("preco_acima", "preco_abaixo"):
        return f"{TIPOS_MON[t]['rotulo']} {_num(p.get('nivel'))}"
    if t in ("alta_pct", "queda_pct"):
        return f"{TIPOS_MON[t]['rotulo']} de {_num(p.get('limite_pct'))}% em {p.get('janela', '1d').replace('d', ' dia(s)')}"
    if t == "extremo":
        return f"{'Máxima' if p.get('sentido') == 'max' else 'Mínima'} de {({'3m': '3 meses', '6m': '6 meses', '52s': '52 semanas'}).get(p.get('periodo'), '52 semanas')}"
    if t == "variacao_incomum":
        return f"Variação diária acima de {_num(p.get('desvios', 3))} desvios-padrão"
    if t == "fund_mudanca":
        return f"Mudança de {_num(p.get('limite_pct'))}% em {INDICADORES.get(r.get('classe'), {}).get(p.get('campo'), p.get('campo'))}"
    return TIPOS_MON.get(t, {}).get("rotulo", t)


def _num(v, casas: int = 2) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "n/d"
    return f"{f:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".").rstrip("0").rstrip(",") if casas else f"{f:.0f}"


def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ------------------------------------------------------------------ avaliação das regras do monitor
def _janela_dias(j: str) -> int:
    return {"1d": 1, "5d": 5, "30d": 21}.get(j, 1)


def _desvio(xs: list[float]) -> float | None:
    xs = [x for x in xs if _ok(x)]
    if len(xs) < 20:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def avaliar_monitor(regras: list[dict], dados: dict, estado: dict | None = None, agora: datetime | None = None) -> tuple[list[dict], dict]:
    """Avalia as regras com os dados já coletados. `dados[ativo] = {'classe','preco','fech':[..antigo→recente..],'ind':{}}`.
    `estado` = {'hit': {regra_id: bool}, 'ind': {ativo: {campo: valor}}}. O aviso só sai na PASSAGEM de "não atendida" para "atendida"
    (por isso não repete a cada verificação). Devolve (disparos no formato dos motores do app, novo estado). Sem dado, não dispara."""
    agora = agora or seg.agora()
    est = {"hit": dict((estado or {}).get("hit") or {}), "ind": {k: dict(v) for k, v in ((estado or {}).get("ind") or {}).items()}}
    out: list[dict] = []

    def disparar(r, titulo, texto, valor, assin, dados_extra=None):
        out.append({"regra_id": r["id"], "ativo": r["ativo"], "tipo": r["tipo"], "prioridade": r.get("importancia", "media"), "titulo": titulo,
                    "texto": texto, "valor": valor, "assinatura": assin, "data": agora.isoformat(timespec="minutes"), "dados": dados_extra or {}})

    for r in regras or []:
        if not r.get("ativa", True) or r.get("origem", "monitor") != "monitor":
            continue
        d = dados.get(r["ativo"])
        if not d or not compativel(r["tipo"], d.get("classe") or r.get("classe")):
            continue
        t, P, a = r["tipo"], r.get("params") or {}, r["ativo"]
        preco, fech = d.get("preco"), [x for x in (d.get("fech") or []) if _ok(x)]
        atendida, titulo, texto, valor = None, "", "", None
        if t in ("preco_acima", "preco_abaixo") and _ok(preco) and _ok(P.get("nivel")):
            nv = float(P["nivel"])
            atendida = preco >= nv if t == "preco_acima" else preco <= nv
            titulo = f"{a}: preço {'acima' if t == 'preco_acima' else 'abaixo'} de {_num(nv)}"
            texto = f"Última cotação disponível: {_num(preco)}. Nível definido por você: {_num(nv)}."
            valor = preco
        elif t in ("alta_pct", "queda_pct") and len(fech) > _janela_dias(P.get("janela", "1d")):
            n = _janela_dias(P.get("janela", "1d"))
            ref = fech[-1 - n]
            if ref:
                v = (fech[-1] / ref - 1) * 100
                lim = float(P.get("limite_pct", 5))
                atendida = v >= lim if t == "alta_pct" else v <= -lim
                titulo = f"{a}: {'valorização' if v >= 0 else 'queda'} de {_num(abs(v))}%"
                texto = f"Variação de {_num(v)}% em {P.get('janela', '1d').replace('d', ' dia(s)')} (limite escolhido: {_num(lim)}%)."
                valor = v
        elif t == "extremo":
            n = {"3m": 63, "6m": 126, "52s": 252}.get(P.get("periodo"), 252)
            ant = fech[:-1][-n:]
            if len(ant) >= max(20, n // 3) and fech:
                ultimo = fech[-1]
                if P.get("sentido", "max") == "max":
                    atendida, ref = ultimo > max(ant), max(ant)
                else:
                    atendida, ref = ultimo < min(ant), min(ant)
                lado = "máxima" if P.get("sentido", "max") == "max" else "mínima"
                titulo = f"{a}: nova {lado} do período"
                texto = f"Fechamento de {_num(ultimo)} superou a {lado} anterior ({_num(ref)}) em {len(ant)} pregões."
                valor = ultimo
        elif t == "variacao_incomum" and len(fech) >= 25:
            rets = [(fech[i] / fech[i - 1] - 1) * 100 for i in range(1, len(fech) - 1) if fech[i - 1]]
            sd = _desvio(rets[-60:])
            if sd and fech[-2]:
                v = (fech[-1] / fech[-2] - 1) * 100
                k = float(P.get("desvios", 3))
                atendida = abs(v) >= k * sd and abs(v) >= 1.0
                titulo = f"{a}: variação incomum de {_num(v)}%"
                texto = f"Movimento de {_num(v)}% no último pregão, {_num(abs(v) / sd, 1)} vezes o desvio-padrão recente ({_num(sd)}%)."
                valor = v
        elif t == "fund_mudanca":
            campo = P.get("campo")
            atual = (d.get("ind") or {}).get(campo)
            ant = (est["ind"].get(a) or {}).get(campo)
            if _ok(atual):
                est["ind"].setdefault(a, {})[campo] = atual
                if _ok(ant) and ant:
                    v = (atual / ant - 1) * 100
                    lim = float(P.get("limite_pct", 15))
                    atendida = abs(v) >= lim
                    nome = INDICADORES.get(d.get("classe") or r.get("classe"), {}).get(campo, campo)
                    titulo = f"{a}: {nome} {'subiu' if v > 0 else 'caiu'} {_num(abs(v))}%"
                    texto = (f"{nome} passou de {_num(ant)} para {_num(atual)}. Múltiplos como P/L e P/VP também mudam quando o preço muda; "
                             f"a leitura de indicadores depende da data do balanço na fonte.")
                    valor = v
                    if atendida:
                        est["hit"][r["id"]] = False      # mudança é um evento: após avisar, o novo valor vira a referência
        if atendida is None:
            continue
        antes = bool(est["hit"].get(r["id"], False))
        est["hit"][r["id"]] = bool(atendida)
        if atendida and not antes:
            disparar(r, titulo, texto, valor, f"{r['id']}:{agora.date().isoformat()}", {"fonte": "Dados de mercado das fontes do app"})
    return out, est


# ------------------------------------------------------------------ carteira (limites do usuário)
def metricas_carteira(posicoes: list[dict], dados: dict) -> dict | None:
    """posicoes: [{'ativo','qtd','classe'}]; dados[ativo]['preco'] e ['fech']. Valor atual por preço de mercado; drawdown e volatilidade
    usam as quantidades ATUAIS aplicadas ao histórico de preços (aproximação: ignora compras e vendas passadas)."""
    vals = {}
    for p in posicoes or []:
        d = dados.get(p["ativo"]) or {}
        if _ok(d.get("preco")) and _ok(p.get("qtd")) and p["qtd"] > 0:
            vals[p["ativo"]] = (d["preco"] * p["qtd"], p.get("classe") or "acao")
    tot = sum(v for v, _ in vals.values())
    if not vals or tot <= 0:
        return None
    pesos = {a: v / tot * 100 for a, (v, _) in vals.items()}
    pcl: dict = {}
    for a, (v, c) in vals.items():
        pcl[c] = pcl.get(c, 0) + v / tot * 100
    out = {"pesos": pesos, "pesos_classe": pcl, "maior_peso": max(pesos.values()), "maior_ativo": max(pesos, key=pesos.get), "total": tot}
    n = min((len(dados[a].get("fech") or []) for a in vals), default=0)
    if n >= 30:
        qt = {p["ativo"]: p["qtd"] for p in posicoes}
        serie = [sum(dados[a]["fech"][-n + i] * qt[a] for a in vals) for i in range(n)]
        pico, dd = serie[0], 0.0
        for x in serie:
            pico = max(pico, x)
            dd = min(dd, (x / pico - 1) * 100)
        rets = [(serie[i] / serie[i - 1] - 1) for i in range(1, n) if serie[i - 1]]
        sd = _desvio(rets[-60:])
        out["drawdown_pct"] = dd
        out["vol_anual_pct"] = sd * math.sqrt(252) * 100 if sd else None
        out["vol_20d_pct"] = _desvio(rets[-20:]) * math.sqrt(252) * 100 if len(rets) >= 20 and _desvio(rets[-20:]) else None
        if len(vals) >= 2:
            ativos = list(vals)[:12]
            rs = {a: [(dados[a]["fech"][-n + i] / dados[a]["fech"][-n + i - 1] - 1) for i in range(1, n)] for a in ativos}
            cs = []
            for i, x in enumerate(ativos):
                for y in ativos[i + 1:]:
                    c = _corr(rs[x][-60:], rs[y][-60:])
                    if c is not None:
                        cs.append(c)
            out["corr_media"] = sum(cs) / len(cs) if cs else None
    return out


def _corr(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


LIMITES_CARTEIRA = {"ativo": 20.0, "classe": 80.0, "drawdown": 15.0, "volatilidade": 35.0, "correlacao": 0.8, "variacao_alocacao": 10.0}


def avaliar_carteira(limites: dict | None, met: dict | None, estado: dict | None = None, alvo: dict | None = None,
                     agora: datetime | None = None) -> tuple[list[dict], dict]:
    """Compara a carteira com os limites escolhidos pela pessoa (os mesmos de Gestão de risco quando existem) e com a alocação-alvo
    informada, se houver. Cada aviso explica o motivo e sugere ações PARA AVALIAÇÃO; nada é executado."""
    agora = agora or seg.agora()
    lim = {**LIMITES_CARTEIRA, **{k: float(v) for k, v in (limites or {}).items() if k in LIMITES_CARTEIRA and _ok(v)}}
    est = {"hit": dict((estado or {}).get("hit") or {}), "peso_ant": dict((estado or {}).get("peso_ant") or {})}
    out: list[dict] = []
    if not met:
        return out, est

    def ev(chave, cond, titulo, texto, acoes, valor, imp="media"):
        antes = bool(est["hit"].get(chave, False))
        est["hit"][chave] = bool(cond)
        if cond and not antes:
            out.append({"regra_id": f"carteira:{chave}", "ativo": "", "tipo": "carteira", "prioridade": imp, "titulo": titulo,
                        "texto": texto + " Possíveis ações para avaliar: " + "; ".join(acoes) + ".", "valor": valor,
                        "assinatura": f"{chave}:{agora.date().isoformat()}", "data": agora.isoformat(timespec="minutes"),
                        "dados": {"fonte": "Cálculo do app sobre sua carteira e cotações das fontes"}})

    a, w = met["maior_ativo"], met["maior_peso"]
    ev("conc_ativo", w >= lim["ativo"], f"Concentração: {a} pesa {_num(w, 1)}% da carteira",
       f"{a} ultrapassou o limite de {_num(lim['ativo'], 0)}% por ativo definido por você.",
       ["revisar se o peso reflete sua convicção", "avaliar aportes em outros ativos em vez de vender", "ajustar o limite, se ele não faz mais sentido"], w,
       "alta" if w >= lim["ativo"] * 1.5 else "media")
    for cl, pc in (met.get("pesos_classe") or {}).items():
        ev(f"classe_{cl}", pc >= lim["classe"] and len(met.get("pesos_classe") or {}) > 1, f"Exposição alta em {CLASSES.get(cl, cl).lower()}: {_num(pc, 1)}%",
           f"{CLASSES.get(cl, cl)} somam {_num(pc, 1)}% da carteira (limite de {_num(lim['classe'], 0)}% por classe).",
           ["comparar com seu perfil de risco", "considerar diversificar em outras classes nos próximos aportes"], pc)
    dd = met.get("drawdown_pct")
    if _ok(dd):
        ev("drawdown", dd <= -lim["drawdown"], f"Queda acumulada da carteira: {_num(dd, 1)}% do pico recente",
           f"A carteira, com as quantidades atuais, está {_num(abs(dd), 1)}% abaixo do pico do período (limite escolhido: {_num(lim['drawdown'], 0)}%). "
           f"É uma aproximação: não considera compras e vendas passadas.", ["rever a tese dos ativos que mais caíram", "checar se a queda é do mercado ou de um ativo específico"], dd, "alta")
    vol = met.get("vol_20d_pct") or met.get("vol_anual_pct")
    if _ok(vol):
        ev("volatilidade", vol >= lim["volatilidade"], f"Volatilidade da carteira elevada: {_num(vol, 1)}% ao ano",
           f"A volatilidade recente anualizada é {_num(vol, 1)}% (limite escolhido: {_num(lim['volatilidade'], 0)}%).",
           ["verificar se o risco está compatível com seu horizonte", "avaliar ativos menos voláteis para parte da carteira"], vol)
    cm = met.get("corr_media")
    if _ok(cm):
        ev("correlacao", cm >= lim["correlacao"], f"Ativos se movendo juntos: correlação média {_num(cm, 2)}",
           f"A correlação média entre seus ativos está em {_num(cm, 2)} (limite {_num(lim['correlacao'], 2)}): a diversificação pode estar menor do que parece.",
           ["incluir ativos de classes ou setores diferentes"], cm, "baixa")
    if alvo:
        for cl, ap in alvo.items():
            if not _ok(ap):
                continue
            atual = (met.get("pesos_classe") or {}).get(cl, 0.0)
            ev(f"rebal_{cl}", abs(atual - ap) >= lim["variacao_alocacao"], f"Rebalanceamento: {CLASSES.get(cl, cl).lower()} fora da alocação-alvo",
               f"{CLASSES.get(cl, cl)} estão em {_num(atual, 1)}% e a meta é {_num(ap, 1)}% (diferença acima de {_num(lim['variacao_alocacao'], 0)} p.p.).",
               ["rebalancear com novos aportes", "avaliar custos e impostos antes de vender"], atual - ap)
    return out, est


# ------------------------------------------------------------------ conversão e padronização
_CAT = {"variacao_preco": "preco", "nivel_preco": "preco", "preco_acima": "preco", "preco_abaixo": "preco", "alta_pct": "preco", "queda_pct": "preco",
        "extremo": "preco", "variacao_incomum": "preco", "indicador": "fundamentalista", "dividendo": "fundamentalista", "resultado": "fundamentalista",
        "fund_mudanca": "fundamentalista", "volatilidade": "tecnico", "liquidez": "tecnico", "noticia": "noticia", "risco": "carteira", "carteira": "carteira",
        "desbloqueio": "evento", "vencimento_rf": "evento", "noticia_urgente": "noticia", "comunicado": "noticia", "noticia_ativo": "noticia",
        "regulatorio": "noticia", "sentimento": "noticia", "juros": "evento", "resultado_empresa": "evento", "cripto_evento": "evento",
        "cruz_medias": "tecnico", "rsi_zona": "tecnico", "macd_cruz": "tecnico", "rompe_sr": "tecnico", "volume_alto": "tecnico",
        "mudanca_tendencia": "tecnico", "padrao": "tecnico", "personalizada": "tecnico",
        "macro_mudanca": "macro", "macro_intensidade": "macro", "macro_risco": "macro"}
PAGINA_ORIGEM = {"intel": "inteligencia", "noticias": "noticias", "tecnica": "tecnica-avancada", "risco": "risco", "carteira": "gestao-carteira", "macro": "macro"}
PAGINA_CLASSE = {"acao": "preco-justo", "bdr": "preco-justo", "fii": "fiis", "etf": "etfs", "cripto": "criptomoedas", "fundo": "fundos-acoes",
                 "renda_fixa": "renda-fixa"}


def categoria_de(tipo: str, origem: str = "") -> str:
    if origem == "noticias" and tipo in ("indicador", "dividendo", "resultado_empresa"):
        return "evento"
    return _CAT.get(tipo, "sistema")


def de_disparo(d: dict, origem: str = "intel", agora: datetime | None = None, classe: str | None = None) -> dict:
    """Converte o disparo de qualquer motor do app em notificação padrão. A deduplicação usa regra+ativo+assinatura; avisos que
    dependem de um fato único (notícia, evento, candle técnico) valem uma vez; os demais, uma vez por dia."""
    agora = agora or seg.agora()
    tipo = str(d.get("tipo") or "")
    cat = "carteira" if origem in ("carteira", "risco") else categoria_de(tipo, origem)
    ativo = str(d.get("ativo") or "")
    ativo = "" if ativo.lower() in ("carteira", "mercado") else ativo.upper()
    unico = origem in ("noticias", "tecnica")
    dedup = f"{origem}|{d.get('regra_id', '')}|{ativo}|{d.get('assinatura', '')}" + ("" if unico else f"|{agora.date().isoformat()}")
    dados = dict(d.get("dados") or {})
    for k in ("valor", "detectado_em"):
        if d.get(k) is not None:
            dados[k] = d[k]
    pagina = PAGINA_ORIGEM.get(origem) or PAGINA_CLASSE.get(classe or "", "") or "inteligencia"
    return {"dedup": dedup, "categoria": cat, "ativo": ativo, "importancia": d.get("prioridade") if d.get("prioridade") in IMPORTANCIAS else "media",
            "titulo": str(d.get("titulo") or "Alerta")[:200], "texto": str(d.get("texto") or "")[:1500], "origem": origem,
            "regra_id": str(d.get("regra_id") or ""), "grupo": f"{ativo}|{cat}", "pagina": pagina,
            "quando": (agora.astimezone(timezone.utc) if agora.tzinfo else agora.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dados": dados}


def de_sistema(titulo: str, texto: str, dedup: str, importancia: str = "baixa", agora: datetime | None = None) -> dict:
    agora = agora or seg.agora()
    return de_disparo({"tipo": "sistema", "regra_id": "sistema", "ativo": "", "prioridade": importancia, "titulo": titulo, "texto": texto,
                       "assinatura": dedup}, "sistema", agora)


# ------------------------------------------------------------------ prioridade e explicação (regras explicáveis)
def pontuar(n: dict, carteira: dict | None = None) -> tuple[str, str]:
    """(importância final, motivo). Nunca REBAIXA o que a pessoa escolheu; só sobe quando o ativo pesa na carteira ou a fonte é oficial."""
    pontos = _ORDEM.get(n.get("importancia"), 2)
    motivos = []
    peso = (carteira or {}).get(str(n.get("ativo") or "").upper())
    if peso is not None and n.get("ativo"):
        pontos += 1 if peso >= 5 else 0.5
        motivos.append(f"{n['ativo']} pesa {_num(peso, 1)}% da sua carteira")
    if (n.get("dados") or {}).get("fonte_oficial"):
        pontos += 0.5
        motivos.append("a fonte é oficial")
    final = "alta" if pontos >= 3.5 else "media" if pontos >= 2 else "baixa"
    if _ORDEM[final] < _ORDEM.get(n.get("importancia"), 2):
        final = n["importancia"]
    return final, ("Subiu de prioridade porque " + " e ".join(motivos) + ".") if _ORDEM[final] > _ORDEM.get(n.get("importancia"), 2) else ""


_INTERP = {
    "preco": "O preço chegou a uma condição que você definiu. Movimentos de preço sozinhos não dizem se o ativo está barato ou caro.",
    "tecnico": "Sinais técnicos descrevem o comportamento recente do preço e do volume; não preveem o que vem depois.",
    "fundamentalista": "Mudanças em indicadores podem refletir o balanço, o preço ou a forma de cálculo da fonte. Vale conferir o relatório da empresa.",
    "carteira": "O alerta compara a carteira com os limites que você escolheu. Limites são referências pessoais, não regras do mercado.",
    "noticia": "A notícia é o que a fonte publicou; o impacto no preço é uma interpretação e pode não se confirmar.",
    "evento": "Datas e eventos vêm das fontes indicadas e podem mudar. Resultados e decisões reais só valem depois de divulgados.",
    "macro": "O cenário econômico descreve condições (juros, inflação, atividade, câmbio) que favorecem ou pressionam um setor. Não prevê o preço do ativo e não substitui a análise da empresa.",
    "sistema": "Aviso do próprio aplicativo.",
}
_CONSEQ = {
    "preco": "Possível necessidade de rever o preço-alvo, o tamanho da posição ou o prazo da tese.",
    "tecnico": "Pode indicar mudança de ritmo do preço no curto prazo, com chance real de sinal falso.",
    "fundamentalista": "Pode alterar o valor justo estimado e a comparação com ativos parecidos.",
    "carteira": "Pode aumentar o risco total da carteira ou fugir da alocação planejada.",
    "noticia": "Pode afetar o ativo e outros ligados ao mesmo setor, se a informação se confirmar.",
    "evento": "Pode movimentar o ativo ou o mercado perto da data.",
    "macro": "Pode mudar o ambiente em que o setor do ativo opera. Vale conferir a análise do ativo antes de qualquer decisão.",
    "sistema": "",
}


def explicar(n: dict, carteira: dict | None = None, base_peso: str = "") -> dict:
    """Explicação sem invenção: só usa o que já está na notificação e no peso do ativo na carteira."""
    cat = n.get("categoria") if n.get("categoria") in CATEGORIAS else "sistema"
    fonte = (n.get("dados") or {}).get("fonte")
    peso = (carteira or {}).get(str(n.get("ativo") or "").upper())
    rel = (f"{n['ativo']} representa {_num(peso, 1)}% da sua carteira{(' ' + base_peso) if base_peso else ''}." if peso is not None and n.get("ativo")
           else f"{n['ativo']} não aparece na sua carteira registrada." if n.get("ativo") and carteira is not None else "")
    return {"fato": n.get("texto") or n.get("titulo") or "", "fonte": fonte or "", "interpretacao": _INTERP[cat], "carteira": rel,
            "consequencias": _CONSEQ[cat], "incerteza": ("Dados de fontes gratuitas podem ter atraso ou falhas. " if cat != "sistema" else "")
            + "Isto não é recomendação de compra ou venda."}


# ------------------------------------------------------------------ preferências
PREFS_PADRAO = {"ativo": True, "canais": {"app": True, "email": False, "telegram": False, "ntfy": False}, "telegram_chat": "", "ntfy_topico": "",
                "importancia_min": "baixa", "importancia_min_externo": "alta", "categorias_off": [], "intervalo_min_h": 6, "max_externas_dia": 10,
                "agrupar": True, "horario": {"inicio": "08:00", "fim": "22:00", "dias": [0, 1, 2, 3, 4, 5, 6]}, "verificar_a_cada_min": 60,
                "alvo_classes": {}, "macro": {"ativo": True, "mudanca": True, "intensidade": True, "risco": True, "neutro": False, "somente_ruim": False}}
FREQUENCIAS_MIN = {15: "15 minutos", 30: "30 minutos", 60: "1 hora", 240: "4 horas", 1440: "1 vez por dia"}
_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_RE_NTFY = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_RE_CHAT = re.compile(r"^-?\d{5,20}$")


def _int(v, lo, hi, padrao):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return padrao


def normalizar_prefs(p) -> dict:
    p = p if isinstance(p, dict) else {}
    base = PREFS_PADRAO
    canais = {k: bool((p.get("canais") or {}).get(k, base["canais"][k])) for k in CANAIS}
    canais["app"] = True              # o aviso dentro do app não se desliga: é a fonte do histórico
    h = p.get("horario") if isinstance(p.get("horario"), dict) else {}
    horario = {"inicio": h.get("inicio") if _RE_HORA.match(str(h.get("inicio", ""))) else base["horario"]["inicio"],
               "fim": h.get("fim") if _RE_HORA.match(str(h.get("fim", ""))) else base["horario"]["fim"],
               "dias": sorted({d for d in (h.get("dias") if isinstance(h.get("dias"), list) else base["horario"]["dias"]) if isinstance(d, int) and 0 <= d <= 6}) or [0, 1, 2, 3, 4, 5, 6]}
    chat = str(p.get("telegram_chat") or "").strip()
    top = str(p.get("ntfy_topico") or "").strip()
    alvo = {k: float(v) for k, v in (p.get("alvo_classes") or {}).items() if k in CLASSES and _ok(v) and 0 <= v <= 100} if isinstance(p.get("alvo_classes"), dict) else {}
    return {"ativo": bool(p.get("ativo", True)), "canais": canais, "telegram_chat": chat if _RE_CHAT.match(chat) else "",
            "ntfy_topico": top if _RE_NTFY.match(top) else "",
            "importancia_min": p.get("importancia_min") if p.get("importancia_min") in IMPORTANCIAS else base["importancia_min"],
            "importancia_min_externo": p.get("importancia_min_externo") if p.get("importancia_min_externo") in IMPORTANCIAS else base["importancia_min_externo"],
            "categorias_off": [c for c in (p.get("categorias_off") or []) if c in CATEGORIAS and c != "sistema"] if isinstance(p.get("categorias_off"), list) else [],
            "intervalo_min_h": _int(p.get("intervalo_min_h"), 0, 168, base["intervalo_min_h"]),
            "max_externas_dia": _int(p.get("max_externas_dia"), 1, 50, base["max_externas_dia"]),
            "agrupar": bool(p.get("agrupar", True)), "horario": horario,
            "verificar_a_cada_min": p.get("verificar_a_cada_min") if p.get("verificar_a_cada_min") in FREQUENCIAS_MIN else base["verificar_a_cada_min"],
            "alvo_classes": alvo,
            "macro": {k: bool((p.get("macro") if isinstance(p.get("macro"), dict) else {}).get(k, v)) for k, v in base["macro"].items()}}


def novo_topico_ntfy() -> str:
    """Nome de tópico imprevisível: quem souber o nome recebe os avisos, então ele funciona como senha. Não reutilize em outros lugares."""
    import secrets
    alfabeto = "abcdefghjkmnpqrstuvwxyz23456789"        # só minúsculas e números sem confusão (sem l, i, o, 0, 1): fácil de ler e copiar
    return "bpt-" + "".join(secrets.choice(alfabeto) for _ in range(26))


def hora_local(agora: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return agora.astimezone(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        return agora.astimezone(timezone(timedelta(hours=-3)))


def dentro_do_horario(prefs: dict, agora: datetime | None = None) -> bool:
    agora = hora_local(agora or seg.agora())
    h = prefs["horario"]
    if agora.weekday() not in h["dias"]:
        return False
    ini, fim = h["inicio"], h["fim"]
    atual = agora.strftime("%H:%M")
    return ini <= atual <= fim if ini <= fim else (atual >= ini or atual <= fim)


def passa_prefs(n: dict, prefs: dict) -> bool:
    """Filtro de qualquer aviso (inclusive no app): tipo desligado ou importância abaixo do mínimo não entra."""
    if not prefs["ativo"] or n.get("categoria") in prefs["categorias_off"]:
        return False
    return _ORDEM.get(n.get("importancia"), 2) >= _ORDEM[prefs["importancia_min"]]


def canais_externos(n: dict, prefs: dict, destinos: dict, agora: datetime | None = None, enviadas_hoje: int = 0) -> list[str]:
    """Canais externos que podem receber ESTA notificação agora. `destinos` = {'email': 'x@y', 'telegram': chat, 'ntfy': topico} já validados."""
    agora = agora or seg.agora()
    if not passa_prefs(n, prefs) or _ORDEM.get(n.get("importancia"), 2) < _ORDEM[prefs["importancia_min_externo"]]:
        return []
    if enviadas_hoje >= prefs["max_externas_dia"] or not dentro_do_horario(prefs, agora):
        return []
    return [c for c in EXTERNOS if prefs["canais"].get(c) and destinos.get(c)]


# ------------------------------------------------------------------ deduplicação, intervalo mínimo e agrupamento
def suprimir(novas: list[dict], recentes: list[dict], prefs: dict, agora: datetime | None = None) -> tuple[list[dict], int]:
    """Remove repetidas na mesma rodada e avisos parecidos (mesma regra e ativo) dentro do intervalo mínimo — salvo se a nova é mais
    importante que a anterior. `recentes` = linhas do banco com regra_id, ativo, importancia, quando."""
    agora = agora or seg.agora()
    horas = prefs["intervalo_min_h"]
    ult: dict = {}
    for r in recentes or []:
        t = seg.de_iso(r.get("quando"))
        k = (r.get("regra_id"), r.get("ativo") or "")
        if t and (k not in ult or t > ult[k][0]):
            ult[k] = (t, r.get("importancia"))
    vistos, ficam, supr = set(), [], 0
    for n in sorted(novas, key=lambda x: -_ORDEM.get(x.get("importancia"), 2)):
        k = (n.get("regra_id"), n.get("ativo") or "")
        if n["dedup"] in vistos:
            supr += 1
            continue
        if horas and n.get("origem") not in ("noticias", "tecnica", "sistema") and k in ult:
            t, imp = ult[k]
            if agora - t < timedelta(hours=horas) and _ORDEM.get(n.get("importancia"), 2) <= _ORDEM.get(imp, 2):
                supr += 1
                continue
        vistos.add(n["dedup"])
        ficam.append(n)
    return ficam, supr


def agrupar(novas: list[dict], minimo: int = 2) -> tuple[list[dict], int]:
    """Junta, na mesma rodada, avisos do mesmo ativo e da mesma categoria em UMA notificação (a mais importante lidera). Devolve (lista, nº juntados)."""
    grupos: dict = {}
    for n in novas:
        grupos.setdefault((n.get("ativo") or "", n.get("categoria")), []).append(n)
    out, juntados = [], 0
    for (ativo, cat), g in grupos.items():
        if len(g) < minimo or not ativo:
            out += g
            continue
        g = sorted(g, key=lambda x: -_ORDEM.get(x.get("importancia"), 2))
        lider = dict(g[0])
        lider["titulo"] = f"{ativo}: {len(g)} avisos de {CATEGORIAS.get(cat, cat).lower()}"[:200]
        lider["texto"] = " • ".join(x["titulo"] for x in g)[:1500]
        lider["dedup"] = "grp|" + hashlib.sha1("|".join(sorted(x["dedup"] for x in g)).encode()).hexdigest()[:20]
        lider["dados"] = {**(g[0].get("dados") or {}), "itens": [{"titulo": x["titulo"], "texto": x["texto"], "regra_id": x.get("regra_id")} for x in g]}
        out.append(lider)
        juntados += len(g) - 1
    return out, juntados


# ------------------------------------------------------------------ texto de mensagem externa (sem dados pessoais além do aviso)
def texto_externo(n: dict, url_app: str = "") -> tuple[str, str]:
    """(assunto, corpo) para e-mail/Telegram/push. Não leva valores da carteira, só o que está no aviso e o aviso de que não é recomendação."""
    assunto = f"[Bússola B3] {n['titulo']}"[:150]
    linhas = [n["titulo"], "", n.get("texto") or "", "", f"Importância: {ROTULO_IMPORT.get(n.get('importancia'), '')} · {CATEGORIAS.get(n.get('categoria'), '')}"]
    if (n.get("dados") or {}).get("url"):
        linhas.append(f"Fonte: {n['dados']['url']}")
    if url_app:
        linhas.append(f"Abrir no app: {url_app}")
    linhas += ["", "Aviso automático. Não é recomendação de compra ou venda."]
    return assunto, "\n".join(linhas)
