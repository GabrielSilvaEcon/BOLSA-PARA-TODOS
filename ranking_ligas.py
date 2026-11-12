"""Classificação da Wallet Game: uma lista só, em cartões, com retorno, patrimônio, queda máxima, Sharpe e pregões; quem escolhe a ordem é a pessoa.

A classificação mostra SOMENTE participantes reais (o ranking publicado). Perfis fictícios existem apenas para testes automatizados:
`montar(..., demo=True)` os gera, e nenhuma tela passa esse argumento. Funções puras, sem rede e sem Streamlit; nada daqui é gravado."""
from __future__ import annotations

import html
import random

DEMO = False                      # nunca ligar em produção: a competição representa só usuários reais
POR_LIGA = 6
ORDENS = ("Retorno", "Patrimônio", "Risco")
PERIODOS = {"Geral": "geral", "Mês": "mes", "Semana": "semana"}
TOPO = 10

_NOMES = ["Lobo da Bolsa", "Tati Dividendos", "Renda Zen", "Mestre Selic", "Bia Valor", "Caçador de Alta", "Nina FIIs", "Pedro Graham",
          "Lu Bazin", "Aporte Diário", "Gui Longo Prazo", "Clara Carteira", "Zeca Trader", "Duda Índice", "Ravi Quant", "Maju Cripto",
          "Téo Small Caps", "Sofi Reserva", "Leo Fluxo", "Ana Paciente", "Rafa Tendência", "Kaká Bonds", "Ju Rebalanceia", "Davi Hedge",
          "Íris Proventos", "Beto Dolar", "Lari Ouro", "Nando Value", "Pâmela ETF", "Caio Momentum", "Vivi Caixa", "Hugo Beta",
          "Mel Dividend", "Otto Risco", "Rita Giro", "Saulo Curva", "Tânia Spread", "Uri Alfa", "Vera Hedge", "Wagner Swing"]


def liga_de(pat, cap, base: list):
    """(nome, cor) da liga para um patrimônio. `base` = [(nome, minimo para capital de 10.000, cor)]; outros capitais usam faixas proporcionais."""
    if pat is None:
        return None
    esc = (float(cap) if cap else 10_000.0) / 10_000.0
    atual = None
    for n, m, c in base:
        if float(pat) >= m * esc:
            atual = (n, c)
    return atual


def demonstracao(base: list, cap_ref: float, periodo: str = "geral") -> list[dict]:
    """Perfis fictícios, POR_LIGA em cada liga, com todos os números. Determinístico (a mesma lista a cada abertura)."""
    esc = cap_ref / 10_000.0
    nomes = _NOMES[:]
    random.Random("classificacao").shuffle(nomes)
    out, k = [], 0
    for i, (n, m, _c) in enumerate(base):
        prox = base[i + 1][1] if i + 1 < len(base) else None
        piso = max(m * esc, 0.7 * cap_ref)
        teto = prox * esc - 1 if prox else m * esc * 1.6
        for j in range(POR_LIGA):
            rnd = random.Random(f"{n}-{j}")
            pat = round(piso + (teto - piso) * rnd.random() ** 0.8, 2)
            ret_g = pat / cap_ref - 1
            fator = {"geral": 1.0, "mes": 0.18, "semana": 0.05}.get(periodo, 1.0)
            ret = ret_g * fator + rnd.uniform(-0.01, 0.01) * (0 if periodo == "geral" else 1)
            dd = round(rnd.uniform(0.02, 0.28), 4)
            out.append({"apelido": nomes[k % len(nomes)], "ret": round(ret, 4), "pat": pat, "dd": dd, "sh": round(ret_g / max(dd, 0.02) * 0.35, 2),
                        "dias": rnd.randint(8, 140), "cap": cap_ref, "demo": True})
            k += 1
    return out


def montar(listas: dict, periodo: str, base: list, cap_ref: float, eu: dict | None = None, demo: bool | None = None) -> list[dict]:
    """Linhas da classificação: pessoas reais (ranking publicado) + perfis de demonstração. `eu` = {"apelido", "patrimonio"} completa o que ainda
    não foi publicado para a própria pessoa. Cada linha traz a liga calculada pelo patrimônio."""
    demo = DEMO if demo is None else demo
    sh = {str(x.get("apelido", "")).lower(): x.get("sh") for x in (listas.get("risco") or [])}
    nome_eu = str((eu or {}).get("apelido") or "").lower()
    rows = []
    for x in listas.get(periodo) or []:
        ap = str(x.get("apelido", ""))
        r = {"apelido": ap, "ret": x.get("ret"), "pat": x.get("pat"), "dd": x.get("dd"), "sh": sh.get(ap.lower()), "dias": x.get("dias"),
             "cap": x.get("cap") or cap_ref, "demo": False, "eu": bool(nome_eu) and ap.lower() == nome_eu}
        if r["eu"] and r["pat"] is None and eu.get("patrimonio") is not None:
            r["pat"], r["cap"] = float(eu["patrimonio"]), cap_ref
        rows.append(r)
    if demo:
        rows += demonstracao(base, cap_ref, periodo)
    for r in rows:
        r["liga"] = liga_de(r.get("pat"), r.get("cap"), base)
    return rows


def ordenar(rows: list[dict], ordem: str, liga: str | None = None, topo: int = TOPO) -> list[dict]:
    """Filtra pela liga (None = todas), ordena pelo critério escolhido e numera. Sem o dado, a linha vai para o fim. Fica o topo e, se estiver
    abaixo dele, a própria pessoa."""
    campo = {"Retorno": "ret", "Patrimônio": "pat", "Risco": "sh"}.get(ordem, "ret")
    itens = [dict(r) for r in rows if not liga or (r.get("liga") and r["liga"][0] == liga)]
    itens.sort(key=lambda r: (r.get(campo) is None, -(r.get(campo) or 0), str(r.get("apelido", "")).lower()))
    for i, r in enumerate(itens, 1):
        r["pos"] = i
    return itens[:topo] + [r for r in itens[topo:] if r.get("eu")]


def _compacto(v) -> str:
    if v is None:
        return "—"
    v = float(v)
    for lim, suf in ((1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"T$ {v / lim:,.1f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"T$ {v:,.0f}".replace(",", ".")


def _pc(v, sinal: bool = True) -> str:
    if v is None:
        return "—"
    v = float(v) * 100
    v = 0.0 if abs(v) < 0.005 else v
    return (f"{v:+.2f}%" if sinal else f"{v:.2f}%").replace(".", ",")


CSS = """<style>
html body .stApp.stApp .cl-l{display:flex;flex-direction:column;gap:8px;margin:8px 0;}
html body .stApp.stApp .cl-c{background:#241C4D;border:1px solid #3B3170;border-radius:16px;padding:10px 12px;box-sizing:border-box;max-width:100%;}
html body .stApp.stApp .cl-c.eu{border-color:#3DDC97;background:#1F3A44;}
html body .stApp.stApp .cl-t{display:flex;align-items:center;gap:10px;}
html body .stApp.stApp .cl-p{width:30px;text-align:center;font-weight:900;color:#CFC8EE;font-size:1rem;flex:none;}
html body .stApp.stApp .cl-n{flex:1;min-width:0;}
html body .stApp.stApp .cl-nome{font-weight:800;color:#F6F3FF;font-size:.95rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
html body .stApp.stApp .cl-tag{display:inline-block;border-radius:999px;padding:1px 8px;font-size:.68rem;font-weight:800;margin:3px 4px 0 0;border:1px solid #5B5190;color:#CFC8EE;}
html body .stApp.stApp .cl-tag.eu{border-color:#3DDC97;color:#3DDC97;}
html body .stApp.stApp .cl-v{font-weight:900;font-size:1.05rem;color:#FFD66B;text-align:right;flex:none;}
html body .stApp.stApp .cl-v.pos{color:#8BE04E;}
html body .stApp.stApp .cl-v.neg{color:#FF6B8A;}
html body .stApp.stApp .cl-g{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px;padding-top:8px;border-top:1px solid #3B3170;}
html body .stApp.stApp .cl-g div{min-width:0;}
html body .stApp.stApp .cl-g b{display:block;color:#F6F3FF;font-size:.8rem;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
html body .stApp.stApp .cl-g i{display:block;color:#9C94C9;font-size:.66rem;font-style:normal;margin-top:1px;}
html body .stApp.stApp .cl-g .on b{color:#FFD66B;}
html body .stApp.stApp .cl-f{color:#9C94C9;font-size:.72rem;margin:2px 2px 0;}
</style>"""


def html_cartoes(itens: list[dict], ordem: str) -> str:
    """Cartões da classificação. O valor grande à direita e o campo em dourado seguem a ordem escolhida."""
    med = {1: "🥇", 2: "🥈", 3: "🥉"}
    out = []
    for r in itens:
        pos = r["pos"]
        liga = r.get("liga")
        tags = (f"<span class='cl-tag' style='border-color:{html.escape(liga[1])}99;color:{html.escape(liga[1])}'>{html.escape(liga[0])}</span>" if liga else "")
        tags += "<span class='cl-tag eu'>você</span>" if r.get("eu") else ""
        tags += "<span class='cl-tag'>demonstração</span>" if r.get("demo") else ""
        ret = r.get("ret")
        grande, cls = {"Retorno": (_pc(ret), "pos" if (ret or 0) > 0 else ("neg" if (ret or 0) < 0 else "")),
                       "Patrimônio": (_compacto(r.get("pat")), ""),
                       "Risco": (f"Sharpe {str(round(r['sh'], 2)).replace('.', ',')}" if r.get("sh") is not None else "—", "")}[ordem]
        dias = r.get("dias")
        cel = [("Retorno", "Retorno", _pc(ret)), ("Patrimônio", "Patrimônio", _compacto(r.get("pat"))),
               ("", "Queda máx.", _pc(r.get("dd"), False)), ("Risco", "Pregões", str(dias) if dias is not None else "—")]
        grade = "".join(f"<div class='{'on' if k == ordem else ''}'><b>{html.escape(v)}</b><i>{html.escape(rot)}</i></div>" for k, rot, v in cel)
        out.append(f"<div class='cl-c{' eu' if r.get('eu') else ''}'><div class='cl-t'><div class='cl-p'>{med.get(pos, pos)}</div>"
                   f"<div class='cl-n'><div class='cl-nome'>{html.escape(str(r.get('apelido', '')))}</div><div>{tags}</div></div>"
                   f"<div class='cl-v {cls}'>{html.escape(grande)}</div></div><div class='cl-g'>{grade}</div></div>")
    return CSS + "<div class='cl-l'>" + "".join(out) + "</div>"
