"""Trader Battle × carteira da Wallet Game (sem Streamlit).

Regras:
 · a pessoa só entra com 1% do patrimônio (caixa + posições) e precisa ter esse valor livre no caixa;
 · cada rodada vira UM lançamento no livro `wg_creditos` (tipo "trader", com sinal), com chave única `trader:<partida>:<rodada>:<email>`:
   o mesmo resultado nunca é lançado duas vezes, mesmo que várias sessões tentem ao mesmo tempo;
 · o lançamento mexe no caixa e no patrimônio, mas não conta como aporte: entra no retorno da carteira como resultado de verdade;
 · a pontuação do jogo não muda e não depende deste módulo.
Valores em T$ (dinheiro virtual da Wallet Game)."""
from __future__ import annotations

from datetime import datetime, timezone

import banco
import competicao as C
import trader_battle as TB
import wallet_game as WG


class SemSaldo(Exception):
    pass


def conta_id(email: str) -> str | None:
    try:
        r = banco._selecionar("contas", {"email": email}, ["id"], limite=1)
        return r[0]["id"] if r else None
    except Exception:
        return None


def situacao(email: str) -> dict:
    """Patrimônio e caixa livre de quem joga (a carteira é sincronizada com o livro antes de ler)."""
    est = WG.sincronizar(email)
    return {"pat": round(C.patrimonio(est), 2), "caixa": round(float(est.get("caixa", 0.0)), 2)}


def aposta_de(email: str, conta: str | None = None) -> dict:
    """{'stake', 'pat', 'conta'}: 1% do patrimônio de agora. Levanta SemSaldo se não há patrimônio ou caixa livre para a aposta."""
    s = situacao(email)
    stake = round(s["pat"] * TB.PCT_APOSTA, 2)
    if s["pat"] <= 0 or stake <= 0:
        raise SemSaldo("Você ainda não tem patrimônio na Wallet Game para apostar.")
    if s["caixa"] < stake:
        raise SemSaldo(f"Para jogar você precisa de {WG.moeda(stake)} livres no caixa (1% do seu patrimônio). Hoje o caixa livre é {WG.moeda(s['caixa'])}.")
    return {"stake": stake, "pat": s["pat"], "conta": conta or conta_id(email) or ""}


def liquidar(p: dict, agora: datetime | None = None) -> int:
    """Lança no livro o resultado das rodadas já encerradas que ainda não foram lançadas. Idempotente. Devolve quantos lançamentos novos."""
    n = 0
    apostas = p.get("apostas") or {}
    if not apostas:
        return 0
    agora = agora or datetime.now(timezone.utc)
    tocados = set()
    for j, ap in apostas.items():
        for rod in range(1, TB.RODADAS + 1):
            r = p["resultados"].get(f"{rod}:{j}")
            fin = r.get("fin") if r else None
            if not fin or not fin["pnl"]:
                continue
            conta = ap.get("conta") or conta_id(j)
            if not conta:
                continue
            sinal = "lucro" if fin["pnl"] > 0 else "prejuízo"
            desc = f"Trader Battle · rodada {rod}: {sinal} de {WG.moeda(abs(fin['pnl']))} ({fin['pct_aposta']:+.2f}% da aposta)"
            try:
                if WG._inserir_credito(j, conta, f"trader:{p['id']}:{rod}:{j}", "trader", fin["pnl"], WG.hoje_brt(agora).isoformat(), desc,
                                       {"partida": p["id"], "rodada": rod, "aposta": fin["aposta"], "pct_aposta": fin["pct_aposta"]}, agora):
                    n += 1
                    tocados.add(j)
            except Exception as e:
                banco.registrar_erro("trader_carteira.liquidar", e)
    for j in tocados:
        try:
            WG.sincronizar(j)
        except Exception as e:
            banco.registrar_erro("trader_carteira.sync", e)
    return n


def liquidar_seguro(p: dict) -> int:
    try:
        return liquidar(p)
    except Exception as e:
        try:
            banco.registrar_erro("trader_carteira", e)
        except Exception:
            pass
        return 0
