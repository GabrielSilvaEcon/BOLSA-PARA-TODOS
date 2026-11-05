"""Alertas de atividade suspeita (Passo 22). Módulo puro: recebe os registros de auditoria/erros e devolve alertas.

Nada é bloqueado aqui (o bloqueio de tentativas está em contas.py); isto só enxerga padrões e avisa o administrador.
Limiares ficam em LIMIARES para ajuste. Os detalhes dos registros já chegam sem senha, token ou e-mail.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import timedelta

import seguranca as seg

NIVEIS = ("alto", "medio", "baixo")
LIMIARES = {
    "forca_bruta_alto": 10, "forca_bruta_medio": 5, "janela_min": 15,
    "varredura_contas": 8, "bloqueios_1h": 3, "links_reset_1h": 5, "exportacoes_1h": 3, "suspensoes_1h": 3,
    "erros_1h": 20, "sucesso_apos_falhas": 5,
}


def _det(row) -> dict:
    try:
        d = json.loads(row.get("detalhes") or "{}")
        return d if isinstance(d, dict) else {}
    except (TypeError, ValueError):
        return {}


def _t(row):
    return seg.de_iso(row.get("quando"))


def _alerta(nivel, titulo, detalhe, quando=None) -> dict:
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "quando": quando or ""}


def analisar(auditoria: list[dict], erros: list[dict] | None = None, bloqueios_rede: list[dict] | None = None,
             agora=None) -> list[dict]:
    agora = agora or seg.agora()
    L = LIMIARES
    jan = agora - timedelta(minutes=L["janela_min"])
    h1 = agora - timedelta(hours=1)
    out: list[dict] = []

    ev = [(r, _t(r)) for r in auditoria or []]
    ev = [(r, t) for r, t in ev if t]

    # 1) muitas falhas contra o mesmo e-mail (força bruta)
    por_chave = Counter(_det(r).get("chave") for r, t in ev if r["acao"] == "login.falha" and t >= jan and _det(r).get("chave"))
    for ch, n in por_chave.items():
        if n >= L["forca_bruta_alto"]:
            out.append(_alerta("alto", "Possível ataque de força bruta", f"{n} senhas erradas em {L['janela_min']} min contra a mesma conta (final {ch[-4:]}).", seg.iso(agora)))
        elif n >= L["forca_bruta_medio"]:
            out.append(_alerta("medio", "Várias senhas erradas seguidas", f"{n} falhas em {L['janela_min']} min na mesma conta (final {ch[-4:]}).", seg.iso(agora)))

    # 2) o mesmo navegador/rede tentando várias contas (varredura de contas)
    por_cli = defaultdict(set)
    for r, t in ev:
        d = _det(r)
        if r["acao"] == "login.falha" and t >= jan and d.get("cliente"):
            por_cli[d["cliente"]].add(d.get("chave"))
    for cli, chaves in por_cli.items():
        if len(chaves) >= L["varredura_contas"]:
            out.append(_alerta("alto", "Um mesmo navegador testou várias contas", f"{len(chaves)} e-mails diferentes em {L['janela_min']} min (origem final {cli[-4:]}).", seg.iso(agora)))

    # 3) limite de tentativas sendo atingido
    n_bloq = sum(1 for r, t in ev if r["acao"] == "login.bloqueado" and t >= h1)
    if n_bloq >= L["bloqueios_1h"]:
        out.append(_alerta("medio", "Limite de tentativas atingido várias vezes", f"{n_bloq} bloqueios na última hora.", seg.iso(agora)))

    # 4) login correto logo depois de muitas falhas na mesma conta
    falhas_conta = Counter(r.get("ator_id") for r, t in ev if r["acao"] == "login.falha" and t >= jan and r.get("ator_id"))
    for r, t in ev:
        if r["acao"] in ("login", "login.google") and t >= jan and falhas_conta.get(r.get("ator_id"), 0) >= L["sucesso_apos_falhas"]:
            out.append(_alerta("alto", "Entrada bem-sucedida após várias falhas", "Uma conta recebeu várias senhas erradas e depois entrou. Confirme com o dono da conta.", seg.iso(t)))
            break

    # 5) muitos pedidos de link de recuperação
    links = Counter(_det(r).get("chave") for r, t in ev if r["acao"] == "senha.link_pedido" and t >= h1 and _det(r).get("chave"))
    for ch, n in links.items():
        if n >= L["links_reset_1h"]:
            out.append(_alerta("medio", "Muitos pedidos de recuperação de senha", f"{n} pedidos na última hora para o mesmo e-mail (final {ch[-4:]}).", seg.iso(agora)))

    # 6) ações administrativas sensíveis
    for r, t in ev:
        if r["acao"] == "conta.papel" and t >= agora - timedelta(days=7):
            d = _det(r)
            out.append(_alerta("alto" if d.get("para") in ("admin", "suporte") else "baixo", "Privilégio de conta alterado",
                               f"Papel mudou de {d.get('de', '?')} para {d.get('para', '?')}.", seg.iso(t)))
    if sum(1 for r, t in ev if r["acao"] == "conta.suspensa" and t >= h1) >= L["suspensoes_1h"]:
        out.append(_alerta("medio", "Várias contas suspensas em pouco tempo", "Confirme se foi uma ação intencional da administração.", seg.iso(agora)))
    if any(r["acao"] == "backup.contas" and t >= agora - timedelta(days=1) for r, t in ev):
        out.append(_alerta("baixo", "Backup administrativo gerado nas últimas 24 h", "Guarde o arquivo em local protegido e apague cópias antigas.", seg.iso(agora)))

    # 7) exportação de dados pessoais repetida
    exp = Counter(r.get("ator_id") for r, t in ev if r["acao"] == "dados.exportados" and t >= h1)
    for _, n in exp.items():
        if n >= L["exportacoes_1h"]:
            out.append(_alerta("medio", "Exportação de dados repetida", f"{n} exportações da mesma conta na última hora.", seg.iso(agora)))

    # 8) erros em excesso
    er = [r for r in (erros or []) if (t := _t(r)) and t >= h1]
    if len(er) >= L["erros_1h"]:
        out.append(_alerta("medio", "Muitos erros do aplicativo", f"{len(er)} erros na última hora; veja a aba Erros.", seg.iso(agora)))

    # 9) rede: pedidos recusados pela proteção
    internos = [b for b in (bloqueios_rede or []) if "interno" in str(b.get("motivo"))]
    if internos:
        out.append(_alerta("alto", "Pedido a endereço interno recusado", f"{len(internos)} tentativa(s) de acessar rede interna (proteção SSRF).", ""))
    outros = [b for b in (bloqueios_rede or []) if "interno" not in str(b.get("motivo"))]
    if outros:
        out.append(_alerta("baixo", "Pedidos de rede recusados", f"{len(outros)} pedido(s) recusado(s); veja a aba Segurança > Rede.", ""))

    ordem = {n: i for i, n in enumerate(NIVEIS)}
    return sorted(out, key=lambda a: ordem.get(a["nivel"], 9))
