"""
Passo 20 · Fontes de dados do comparador (sem Streamlit e sem rede própria: quem busca é quem chama).

O que este módulo faz
 · CATÁLOGO das fontes (gratuitas e oficiais primeiro): plano gratuito, limite, chave, uso comercial, redistribuição e histórico,
   com a data em que cada informação foi conferida e se ela vem do site oficial ou é o que o app já sabia.
 · LIMITADOR de consultas (intervalo mínimo e máximo por janela) e novas tentativas com espera, para não estourar limite de ninguém.
 · CADEIA DE FONTES: tenta a fonte principal e, se falhar, a alternativa AUTORIZADA; registra de onde veio cada série, confere se a
   alternativa é comparável e acusa divergência. NUNCA mistura fontes em silêncio e nunca inventa dado.
 · POLÍTICA DE CACHE por tipo de dado (cotação curta, histórico longo, câmbio e macro médios, cadastro longo).

Regras: nenhuma fonte paga é ativada sem autorização; chaves só em secrets/variáveis de ambiente (nunca no código nem em mensagens).
"""
from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field

import pandas as pd

CONFERIDO_EM = "2026-11-04"

# =============================================================================== cache (segundos)
TTL = {"cotacao": 900, "historico": 6 * 3600, "cambio": 3600, "macro": 12 * 3600, "cadastro": 24 * 3600, "fundamentos": 6 * 3600}


def ttl(tipo: str) -> int:
    """Validade do cache por tipo de dado. Tipo desconhecido usa a mais conservadora (cotação)."""
    return TTL.get(tipo, TTL["cotacao"])


# =============================================================================== catálogo de fontes
# status: "ativa" (já em uso no app) · "reserva" (só entra se a principal falhar) · "desativada" (documentada; precisa da sua autorização)
FONTES = [
    {"id": "yahoo", "nome": "Yahoo Finance", "classes": ["acao", "etf", "fii", "cripto"], "tipo": "não oficial", "status": "ativa", "chave": False,
     "limite": "Sem limite publicado; o Yahoo bloqueia servidores com muitas consultas.", "historico": "até 5 anos pelo gráfico; máximo pela biblioteca",
     "comercial": "Não há API pública oficial: os termos do Yahoo restringem uso comercial e redistribuição. Confirme antes de operar comercialmente.",
     "redistribuicao": "Não permitida sem licença.", "verificado": "site oficial não consultado (conhecimento do projeto)"},
    {"id": "bcb", "nome": "Banco Central do Brasil (SGS)", "classes": ["macro", "cambio"], "tipo": "oficial", "status": "ativa", "chave": False,
     "limite": "Sem chave; consultas por série com intervalo de datas (a API pede janelas de até 10 anos).", "historico": "longo",
     "comercial": "Dados abertos do governo.", "redistribuicao": "Permitida citando a fonte.", "verificado": "site oficial não consultado nesta sessão"},
    {"id": "cvm", "nome": "CVM (dados abertos de fundos e FIIs)", "classes": ["fundo", "fii"], "tipo": "oficial", "status": "ativa", "chave": False,
     "limite": "Arquivos mensais públicos, sem chave.", "historico": "meses solicitados", "comercial": "Dados abertos.",
     "redistribuicao": "Permitida citando a fonte.", "verificado": "site oficial não consultado nesta sessão"},
    {"id": "tesouro", "nome": "Tesouro Nacional (Tesouro Transparente)", "classes": ["renda_fixa"], "tipo": "oficial", "status": "ativa", "chave": False,
     "limite": "Arquivo público de preços e taxas, sem chave.", "historico": "longo", "comercial": "Dados abertos.",
     "redistribuicao": "Permitida citando a fonte.", "verificado": "site oficial não consultado nesta sessão"},
    {"id": "coingecko", "nome": "CoinGecko (plano Demo)", "classes": ["cripto"], "tipo": "gratuita", "status": "ativa", "chave": False,
     "limite": "100 consultas por minuto e 10 mil créditos por mês (tabela de preços oficial).", "historico": "1 ano (diário)",
     "comercial": "A tabela oficial não informa licença para o Demo (só os planos pagos aparecem como 'Commercial').",
     "redistribuicao": "Exige atribuição (cite a CoinGecko).", "verificado": f"{CONFERIDO_EM}, coingecko.com/en/api/pricing"},
    {"id": "brapi", "nome": "Brapi (plano gratuito)", "classes": ["acao", "fii", "etf"], "tipo": "gratuita", "status": "reserva", "chave": True,
     "limite": "15.000 requisições por mês, 1 ativo por consulta, histórico de até 3 meses.", "historico": "até 3 meses",
     "comercial": "O site diz que a API pode ser usada em aplicações comerciais, mas coloca o plano gratuito como 'protótipo sem receita'; confirme nos termos.",
     "redistribuicao": "Não verificada.", "verificado": f"{CONFERIDO_EM}, brapi.dev/faq"},
    {"id": "fmp", "nome": "Financial Modeling Prep (plano gratuito)", "classes": ["acao"], "tipo": "gratuita", "status": "reserva", "chave": True,
     "limite": "250 consultas por dia, 500 MB de tráfego em 30 dias, só bolsas dos EUA e lista limitada de símbolos, histórico de até 5 anos.",
     "historico": "5 anos", "comercial": "A página de planos não diz se o plano gratuito vale para uso comercial.",
     "redistribuicao": "A própria página diz: exibir ou redistribuir dados do FMP exige um Acordo de Exibição e Licenciamento de Dados.",
     "verificado": f"{CONFERIDO_EM}, site.financialmodelingprep.com/pricing-plans"},
    {"id": "twelvedata", "nome": "Twelve Data (plano Basic)", "classes": ["acao", "etf", "cripto"], "tipo": "gratuita", "status": "desativada", "chave": True,
     "limite": "8 créditos por minuto e 800 por dia.", "historico": "não verificado",
     "comercial": "Não verificado.", "redistribuicao": "Não verificada.", "verificado": f"{CONFERIDO_EM}, support.twelvedata.com (só os limites)"},
    {"id": "alphavantage", "nome": "Alpha Vantage (chave gratuita)", "classes": ["acao", "etf", "cripto"], "tipo": "gratuita", "status": "desativada", "chave": True,
     "limite": "25 requisições por dia; dados em tempo real e com atraso de 15 min dos EUA são premium.", "historico": "não verificado",
     "comercial": "A página não trata de uso comercial; vale o Termo de Serviço.", "redistribuicao": "Não informada na página.",
     "verificado": f"{CONFERIDO_EM}, alphavantage.co/support"},
    {"id": "b3", "nome": "B3 (dados de mercado)", "classes": ["acao", "fii", "etf"], "tipo": "oficial (licenciada)", "status": "desativada", "chave": False,
     "limite": "Dados em tempo real e histórico completo são produtos licenciados.", "historico": "—",
     "comercial": "Exige contrato de licença com a B3. Não ativada.", "redistribuicao": "Exige licença.", "verificado": "não consultado"},
]
_POR_ID = {f["id"]: f for f in FONTES}


def fonte(id_: str) -> dict | None:
    return _POR_ID.get(id_)


NOME_DA_CHAVE = {"brapi": "BRAPI_TOKEN"}          # nome já usado pelo app; as demais seguem FONTE_API_KEY (ex.: FMP_API_KEY)


def chave_da_fonte(id_: str) -> str | None:
    """Chave da API (secrets ou variável de ambiente). Devolve None se não houver. Nunca é registrada nem exibida."""
    nome = NOME_DA_CHAVE.get(id_, f"{id_.upper()}_API_KEY")
    try:
        import streamlit as st
        v = st.secrets.get(nome)
        if v:
            return str(v)
    except Exception:
        pass
    return os.environ.get(nome) or None


def fontes_usaveis(classe: str | None = None) -> list[dict]:
    """Fontes ativas ou de reserva (nunca as desativadas), na ordem do catálogo; as que exigem chave só se a chave existir."""
    out = []
    for f in FONTES:
        if f["status"] not in ("ativa", "reserva"):
            continue
        if classe and classe not in f["classes"]:
            continue
        if f["chave"] and not chave_da_fonte(f["id"]):
            continue
        out.append(f)
    return out


def tabela_fontes() -> pd.DataFrame:
    rot = {"ativa": "Em uso", "reserva": "Reserva", "desativada": "Desativada (precisa da sua autorização)"}
    return pd.DataFrame([{"Fonte": f["nome"], "Tipo": f["tipo"], "Situação": rot[f["status"]], "Chave": "sim" if f["chave"] else "não",
                          "Limite do plano gratuito": f["limite"], "Histórico": f["historico"], "Uso comercial": f["comercial"],
                          "Redistribuição": f["redistribuicao"], "Conferido em": f["verificado"]} for f in FONTES])


# =============================================================================== controle de consultas
class Limitador:
    """Controla a taxa de consultas de uma fonte: espaça as chamadas (`intervalo` s) e respeita no máximo `maximo` por `janela` s.
    `esperar()` dorme o necessário (relógio e sono injetáveis para teste) e devolve quanto esperou."""

    def __init__(self, maximo: int = 30, janela: float = 60.0, intervalo: float = 0.0, relogio=time.monotonic, dormir=time.sleep):
        self.maximo, self.janela, self.intervalo = int(maximo), float(janela), float(intervalo)
        self._rel, self._dor = relogio, dormir
        self._marcas: list[float] = []
        self._trava = threading.Lock()

    def esperar(self) -> float:
        with self._trava:
            esperou = 0.0
            agora = self._rel()
            self._marcas = [t for t in self._marcas if agora - t < self.janela]
            falta = 0.0
            if self.intervalo and self._marcas:
                falta = max(falta, self._marcas[-1] + self.intervalo - agora)
            if len(self._marcas) >= self.maximo:
                falta = max(falta, self._marcas[0] + self.janela - agora)
            if falta > 0:
                self._dor(falta)
                esperou = falta
                agora = self._rel()
                self._marcas = [t for t in self._marcas if agora - t < self.janela]
            self._marcas.append(agora)
            return esperou

    @property
    def usadas(self) -> int:
        agora = self._rel()
        return len([t for t in self._marcas if agora - t < self.janela])


LIMITADORES = {"yahoo": Limitador(30, 60, 0.2), "coingecko": Limitador(20, 60, 1.0), "bcb": Limitador(30, 60, 0.2),
               "brapi": Limitador(10, 60, 1.0), "cvm": Limitador(10, 60, 0.5)}


def com_tentativas(fn, tentativas: int = 3, espera: float = 1.0, dormir=time.sleep, limitador: Limitador | None = None):
    """Chama `fn()` até `tentativas` vezes, com espera crescente (1×, 2×, 4×...). Respeita o limitador. Devolve (resultado, erros).
    Se todas falharem, resultado é None e `erros` traz o NOME do tipo de cada erro (nunca a mensagem: pode conter chave ou URL)."""
    erros: list[str] = []
    for i in range(max(1, tentativas)):
        try:
            if limitador is not None:
                limitador.esperar()
            return fn(), erros
        except Exception as e:
            erros.append(e.__class__.__name__)
            if i < tentativas - 1:
                dormir(espera * (2 ** i))
    return None, erros


# =============================================================================== cadeia de fontes
@dataclass
class Tentativa:
    fonte: str
    ok: bool
    motivo: str = ""
    n: int = 0
    inicio: str | None = None
    fim: str | None = None


@dataclass
class Resultado:
    serie: pd.Series
    fonte: str = ""
    tentativas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    divergencia: dict | None = None
    usou_alternativa: bool = False


def _limpa(s) -> pd.Series:
    if s is None or len(s) == 0:
        return pd.Series(dtype=float)
    x = pd.Series(pd.to_numeric(pd.Series(s).values, errors="coerce"), index=pd.DatetimeIndex(pd.Series(s).index))
    if x.index.tz is not None:
        x.index = x.index.tz_localize(None)
    x.index = x.index.normalize()
    x = x[~x.index.duplicated(keep="last")].sort_index().dropna()
    return x[x > 0]


def comparar_fontes(a: pd.Series, b: pd.Series, tol_preco: float = 0.03, minimo_comum: int = 20) -> dict:
    """Confere se duas séries de preço são do mesmo ativo: no último dia comum, a diferença relativa do preço e a do retorno desde o primeiro dia comum.
    ok=False quando passa de `tol_preco` (3%): o chamador mostra o aviso e NÃO mistura as séries."""
    x, y = _limpa(a), _limpa(b)
    comum = x.index.intersection(y.index)
    if len(comum) < minimo_comum:
        return {"ok": None, "motivo": f"só {len(comum)} datas em comum (mínimo {minimo_comum}): não deu para conferir"}
    d_preco = abs(float(x[comum[-1]]) / float(y[comum[-1]]) - 1)
    r_x = float(x[comum[-1]] / x[comum[0]] - 1)
    r_y = float(y[comum[-1]] / y[comum[0]] - 1)
    d_ret = abs(r_x - r_y)
    ok = d_ret <= tol_preco
    return {"ok": ok, "dif_preco": d_preco, "dif_retorno": d_ret, "datas_comuns": int(len(comum)), "ultima_data": comum[-1].date().isoformat(),
            "motivo": "" if ok else f"o retorno do período difere {d_ret * 100:.1f} pontos entre as fontes (limite {tol_preco * 100:.0f})"}


def buscar_serie(cadeia: list[tuple[str, object]], minimo_pontos: int = 30, conferir: bool = False, tol: float = 0.03) -> Resultado:
    """Percorre `cadeia` = [(id_da_fonte, função_sem_argumentos)] até uma devolver série com `minimo_pontos` pontos.
    Fonte não autorizada (desativada) é pulada e registrada. Com `conferir=True` consulta também a próxima fonte para validar a primeira
    (divergência vira aviso; a série principal continua sendo a da primeira fonte; as séries NUNCA são misturadas)."""
    res = Resultado(pd.Series(dtype=float))
    achadas: list[tuple[str, pd.Series]] = []
    for fid, fn in cadeia:
        meta = fonte(fid)
        if meta is not None and meta["status"] == "desativada":
            res.tentativas.append(Tentativa(fid, False, "fonte desativada: precisa da sua autorização"))
            continue
        try:
            s = _limpa(fn())
        except Exception as e:
            res.tentativas.append(Tentativa(fid, False, f"falhou ({e.__class__.__name__})"))
            continue
        if len(s) < minimo_pontos:
            res.tentativas.append(Tentativa(fid, False, f"só {len(s)} pontos (mínimo {minimo_pontos})", len(s)))
            continue
        res.tentativas.append(Tentativa(fid, True, "", len(s), s.index[0].date().isoformat(), s.index[-1].date().isoformat()))
        achadas.append((fid, s))
        if not conferir or len(achadas) >= 2:
            break
    if not achadas:
        res.avisos.append("Nenhuma fonte autorizada devolveu histórico suficiente.")
        return res
    res.serie, res.fonte = achadas[0][1], achadas[0][0]
    res.usou_alternativa = bool(res.tentativas) and not res.tentativas[0].ok
    if res.usou_alternativa:
        nome = (fonte(res.fonte) or {}).get("nome", res.fonte)
        res.avisos.append(f"A fonte principal não respondeu; os dados vêm de outra fonte autorizada ({nome}). Confira o período coberto.")
    if len(achadas) == 2:
        res.divergencia = comparar_fontes(achadas[0][1], achadas[1][1], tol)
        if res.divergencia.get("ok") is False:
            res.avisos.append(f"Divergência entre {achadas[0][0]} e {achadas[1][0]}: {res.divergencia['motivo']}. Mantive só a primeira fonte.")
    return res


def rotulo_fonte(id_: str) -> str:
    return (fonte(id_) or {}).get("nome", id_)
