"""Passe de temporada GRATUITO (Fase 4). Módulo puro, sem Streamlit, sem rede e sem banco.

- Uma temporada = um mês do calendário (mesmas janelas de `competicao_temporadas`, em horário de Brasília).
- O avanço vem SÓ do XP de estudo da Jornada feito dentro do mês (`jornada.xp_dia`). Nada é gravado: tudo é derivado do que o app já guarda,
  então o passe não pode ser adulterado nem duplicar nada, e o histórico das temporadas passadas sai do mesmo registro de XP por dia.
- Não existe passe pago nem trilha premium. Os marcos são honrarias simbólicas do perfil: NÃO pagam XP, Ticker Coins nem T$,
  então as três economias seguem independentes e nada é convertido automaticamente.
- O registro de XP por dia guarda os últimos `jornada.LIMITE_DIAS` dias; temporadas mais antigas que isso não aparecem no histórico.
"""
from __future__ import annotations

from datetime import date, timedelta

import competicao_temporadas as CT

# (XP de estudo acumulado na temporada, nome do marco, símbolo, honraria)
MARCOS = (
    (30, "Marco 1", "🌱", "Símbolo no perfil"),
    (70, "Marco 2", "📘", "Símbolo no perfil"),
    (120, "Marco 3", "🔥", "Título do perfil: Aprendiz da temporada"),
    (180, "Marco 4", "🧭", "Símbolo no perfil"),
    (250, "Marco 5", "⚡", "Símbolo no perfil"),
    (330, "Marco 6", "🎯", "Título do perfil: Constante da temporada"),
    (420, "Marco 7", "🧠", "Símbolo no perfil"),
    (520, "Marco 8", "🏅", "Símbolo no perfil"),
    (630, "Marco 9", "💎", "Símbolo no perfil"),
    (760, "Marco 10", "👑", "Selo de temporada completa"),
)
TIPO = "mensal"
JANELA_DIAS = 395          # tolerância sobre o registro de 400 dias do XP por dia


def id_atual(hoje: date) -> str:
    return CT.id_temporada(TIPO, hoje)


def xp_na_temporada(xp_dia: dict, tid: str) -> int:
    """Soma o XP de estudo dos dias dentro da janela da temporada (inclusive os dois extremos)."""
    ini, fim = CT.limites(tid)
    total = 0
    for k, v in (xp_dia or {}).items():
        try:
            d = date.fromisoformat(str(k))
            n = int(v)
        except (TypeError, ValueError):
            continue
        if ini <= d <= fim and n > 0:
            total += n
    return total


def marcos_de(xp: int) -> list[dict]:
    """Lista dos marcos com o estado de cada um para um XP de temporada."""
    xp = max(0, int(xp))
    return [{"n": i + 1, "xp": lim, "nome": nome, "simbolo": simb, "honraria": hon, "ok": xp >= lim}
            for i, (lim, nome, simb, hon) in enumerate(MARCOS)]


def estado(xp_dia: dict, hoje: date, tid: str | None = None) -> dict:
    """Situação do passe: datas, dias restantes, XP, marco atual e o próximo, progresso e a lista de marcos."""
    tid = tid or id_atual(hoje)
    ini, fim = CT.limites(tid)
    xp = xp_na_temporada(xp_dia, tid)
    marcos = marcos_de(xp)
    feitos = sum(1 for m in marcos if m["ok"])
    proximo = next((m for m in marcos if not m["ok"]), None)
    base = marcos[feitos - 1]["xp"] if feitos else 0
    pct = 1.0 if proximo is None else min(1.0, (xp - base) / max(1, proximo["xp"] - base))
    encerrada = hoje > fim
    return {"id": tid, "rotulo": CT.rotulo(tid), "inicio": ini, "fim": fim, "encerrada": encerrada,
            "dias_restantes": 0 if encerrada else (fim - hoje).days, "dias_total": (fim - ini).days + 1,
            "xp": xp, "marcos": marcos, "feitos": feitos, "total": len(marcos), "proximo": proximo,
            "falta": 0 if proximo is None else proximo["xp"] - xp, "pct": pct, "completo": proximo is None,
            "titulos": [m["honraria"].split(": ", 1)[1] for m in marcos if m["ok"] and m["honraria"].startswith("Título")]}


def historico(xp_dia: dict, hoje: date, quantas: int = 6) -> list[dict]:
    """Temporadas ENCERRADAS mais recentes, da mais nova para a mais antiga, com o marco alcançado em cada uma.
    Só entram meses que começam dentro do registro de XP por dia e nos quais houve estudo."""
    limite = hoje - timedelta(days=JANELA_DIAS)
    saida = []
    for tid in CT.recentes(TIPO, hoje, max(2, quantas) + 12)[1:]:
        if CT.limites(tid)[0] < limite:
            break
        e = estado(xp_dia, hoje, tid)
        if e["xp"] > 0:
            saida.append({k: e[k] for k in ("id", "rotulo", "inicio", "fim", "xp", "feitos", "total", "completo")})
        if len(saida) >= quantas:
            break
    return saida


def data_br(d: date) -> str:
    return d.strftime("%d/%m/%Y")
