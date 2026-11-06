"""Busca universal de ativos (módulo puro, sem Streamlit).

Primeira versão: reconhece por FORMATO o que a pessoa digitou e diz para onde ir.
 · CNPJ válido (14 dígitos) → fundo (CVM)
 · TD-IPCA-2035 (Tesouro) ou RF-<id> (título salvo na carteira) → renda fixa
 · ETF conhecido (BOVA11, IVVB11, VOO, QQQ...) → ETFs
 · XXXX11 na lista de FIIs → FIIs (fora da lista e não conhecido como ação/ETF: FII "provável")
 · XXXX3/4/... e units cadastradas → ação da B3
 · par de cripto (BTC-USD, BTC/USDT) → modo Criptomoedas (a moeda é escolhida pelo nome lá)
 · qualquer outro texto (nome de empresa, ticker dos EUA) → "texto": o app usa a busca por nome que já existia.
Busca por nome de fundo ou de cripto fica para uma versão futura.
"""
from __future__ import annotations

import re

MODO_DA_CLASSE = {"acao": "Ações", "fii": "FIIs", "etf": "ETFs", "fundo": "Fundos", "renda_fixa": "Renda fixa", "cripto": "Criptomoedas"}
ROTULO_CLASSE = {"acao": "ação", "fii": "FII", "etf": "ETF", "fundo": "fundo", "renda_fixa": "título de renda fixa", "cripto": "criptomoeda"}
_B3 = re.compile(r"[A-Z]{4}\d{1,2}")
_TD = re.compile(r"TD-[A-Z]+-\d{4}")
_RF = re.compile(r"RF-[A-Z0-9]{4,12}")
_CRIPTO = re.compile(r"[A-Z0-9]{2,10}(-|/)(USD|USDT|BRL|BTC|USDC)")


def separar(texto: str) -> list[str]:
    """Termos separados por vírgula, ponto e vírgula ou quebra de linha. Espaços só separam quando TODOS os pedaços parecem código."""
    termos = []
    for p in re.split(r"[,;\n]+", texto or ""):
        p = p.strip()
        if not p:
            continue
        sub = p.split()
        if len(sub) > 1 and all(_B3.fullmatch(s.upper().replace(".SA", "")) for s in sub):
            termos += sub
        else:
            termos.append(p)
    return termos[:10]


def _cnpj():
    import fundos as fd
    return fd


def interpretar(termo: str, catalogo=(), eh_fii=None, etfs=None) -> dict:
    """{'classe', 'codigo', 'modo', 'confianca', 'aviso'}. classe 'texto' = deixe a busca por nome resolver; None = vazio ou inválido."""
    bruto = str(termo or "").strip()
    if not bruto:
        return {"classe": None, "codigo": "", "modo": None, "confianca": None, "aviso": "Digite um ticker, um CNPJ ou um código de título."}
    fd = _cnpj()
    digitos = fd.so_digitos(bruto)
    if len(digitos) == 14 and re.fullmatch(r"[\d.\-/\s]+", bruto):
        if fd.cnpj_valido(bruto):
            return _res("fundo", fd.formatar_cnpj(bruto), "alta")
        return {"classe": None, "codigo": bruto, "modo": None, "confianca": None, "aviso": "Esse CNPJ não é válido. Confira os 14 números."}
    c = bruto.upper().replace(".SA", "").strip()
    if _TD.fullmatch(c) or _RF.fullmatch(c):
        return _res("renda_fixa", c, "alta")
    if etfs is None:
        import comparador
        etfs = comparador.ETFS_CONHECIDOS
    if c in etfs:
        return _res("etf", c, "alta")
    if _CRIPTO.fullmatch(c):
        return _res("cripto", c, "provável", aviso="Para criptomoedas, escolha a moeda pelo nome na tela de Criptomoedas.")
    if _B3.fullmatch(c):
        if c in set(catalogo):
            return _res("acao", c, "alta")
        if c.endswith("11"):
            na_lista = bool(eh_fii(c)) if eh_fii else False
            return _res("fii", c, "alta" if na_lista else "provável")
        return _res("acao", c, "provável")
    return {"classe": "texto", "codigo": bruto, "modo": None, "confianca": None, "aviso": None}


def _res(classe: str, codigo: str, conf: str, aviso: str | None = None) -> dict:
    return {"classe": classe, "codigo": codigo, "modo": MODO_DA_CLASSE[classe], "confianca": conf, "aviso": aviso}


def mensagem(r: dict) -> str:
    """Frase curta para a pessoa depois de reconhecido o ativo."""
    if not r.get("classe") or r["classe"] == "texto":
        return r.get("aviso") or ""
    base = f"Reconhecemos {r['codigo']} como {ROTULO_CLASSE[r['classe']]} e abrimos em {r['modo']}."
    if r.get("confianca") == "provável":
        base += " Se não for isso, escolha o tipo certo nas abas acima."
    return base + (" " + r["aviso"] if r.get("aviso") else "")
