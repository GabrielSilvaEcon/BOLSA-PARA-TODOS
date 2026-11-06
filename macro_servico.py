"""Orquestra os indicadores e o cenário para a página, o monitor e os alertas.

Um só cálculo compartilhado: os indicadores vêm do cache central (1 consulta por indicador a cada ~3 h, para TODOS os usuários) e o cenário
é calculado uma vez por atualização e reaproveitado. Nada aqui é feito por usuário, e nenhum passo usa IA.
Só o cruzamento com a carteira real (barato, em memória) é feito por conta.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import cache_central
import macro_cenario as MC
import macro_fontes as MF

CH_VEREDITOS = "macro_veredictos"
CH_ULTIMOS = "macro_ultimos"
# Leitura de EXIBIÇÃO (Início): separada do estado do monitor. CH_VEREDITOS/CH_ULTIMOS guardam o histórico usado para histerese e para
# detectar transições (alertas) e só o monitor escreve neles. CH_EXIBICAO é só "a última leitura válida para mostrar", gravada pelo
# monitor e pela página Economia sem tocar no histórico.
CH_EXIBICAO = "macro_exibicao"
EXIBICAO_MIN_INTERVALO_S = 600
EXIBICAO_VELHA_DIAS = 3


def _estado_global(chave: str) -> dict:
    try:
        import banco
        return banco.cfg_ler(chave) or {}
    except Exception:
        return {}


def indicadores(ids=None, coletor=None) -> dict:
    """Resolve todos os indicadores (em paralelo, com cache). `coletor(id) -> resultado` é injetável nos testes."""
    import macro_rede
    coletor = coletor or macro_rede.indicador
    ids = list(ids or MF.CATALOGO)
    anteriores = _estado_global(CH_ULTIMOS)
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(lambda i: _seguro(coletor, i), ids))
    return {i: MF.marcar_revisao(r, anteriores.get(i)) for i, r in zip(ids, res)}


def _seguro(coletor, i):
    try:
        return coletor(i)
    except Exception as e:                                 # noqa: BLE001 - uma fonte quebrada não derruba a página
        return MF._indisponivel(MF.CATALOGO[i], [], f"erro ao consultar as fontes ({e.__class__.__name__})")


def _bom(r) -> bool:
    return bool(r) and bool(r.get("indicadores"))


@cache_central.dados(ttl=1800, ok=_bom, nome="macro.cenario", persistir=False)
def cenario_compartilhado() -> dict:
    """Foto completa (indicadores + fatores + cenários), calculada uma vez e reaproveitada por todos."""
    R = indicadores()
    ant = {k: v.get("v") for k, v in _estado_global(CH_VEREDITOS).items() if isinstance(v, dict)}
    c = MC.calcular(R, ant)
    return {"indicadores": R, **c}


def guardar_estado_global(foto: dict) -> None:
    """O monitor grava o que precisa para a próxima execução: vereditos (histerese) e últimos valores (detecta revisão)."""
    try:
        import banco
        banco.cfg_gravar(CH_VEREDITOS, MC.snapshot_vereditos(foto["cenarios"]))
        banco.cfg_gravar(CH_ULTIMOS, {i: {"data": r.get("data"), "valor": r.get("valor")} for i, r in foto["indicadores"].items() if r.get("data")})
    except Exception:
        pass


# ---------------------------------------------------------------- leitura de exibição (Início)
def montar_exibicao(foto: dict, origem: str, agora_iso: str) -> dict | None:
    """Registro pequeno para mostrar no Início. None se a foto não tem cenário (nada de gravar leitura vazia)."""
    if not foto or not foto.get("indicadores") or not foto.get("cenarios"):
        return None
    snap = MC.snapshot_vereditos(foto["cenarios"])
    if not isinstance(snap.get("geral"), dict):
        return None
    return {"em": agora_iso, "dados_ate": foto.get("dados_ate"), "origem": origem, "snap": snap}


def deve_gravar(anterior: dict | None, novo: dict | None, agora_ts: float, ts_anterior: float | None) -> bool:
    """Evita registros repetidos: grava se não havia leitura, se mudou algum veredito/nota ou se os dados são mais novos;
    caso contrário só renova a data depois do intervalo mínimo."""
    if not novo:
        return False
    if not anterior or not isinstance(anterior.get("snap"), dict):
        return True
    if anterior["snap"] != novo["snap"] or anterior.get("dados_ate") != novo.get("dados_ate"):
        return True
    return ts_anterior is None or agora_ts - ts_anterior >= EXIBICAO_MIN_INTERVALO_S


def gravar_exibicao(foto: dict, origem: str, agora=None) -> bool:
    """Grava a leitura de exibição (nunca o histórico do monitor). Devolve True se gravou. Falha nunca atrapalha a página."""
    try:
        import banco
        from datetime import datetime, timezone
        agora = agora or datetime.now(timezone.utc)
        novo = montar_exibicao(foto, origem, agora.isoformat(timespec="seconds"))
        ant = banco.cfg_ler(CH_EXIBICAO) or None
        ts_ant = None
        if ant and ant.get("em"):
            try:
                ts_ant = datetime.fromisoformat(ant["em"]).timestamp()
            except Exception:
                ts_ant = None
        if not deve_gravar(ant, novo, agora.timestamp(), ts_ant):
            return False
        banco.cfg_gravar(CH_EXIBICAO, novo)
        return True
    except Exception:
        return False


def ler_exibicao() -> dict | None:
    """Última leitura válida para mostrar: a de exibição; se ainda não existe, o snapshot antigo do monitor (somente leitura).
    Devolve {'snap', 'em', 'origem'} ou None."""
    try:
        import banco
        e = banco.cfg_ler(CH_EXIBICAO)
        if isinstance(e, dict) and isinstance(e.get("snap"), dict) and isinstance(e["snap"].get("geral"), dict):
            return {"snap": e["snap"], "em": e.get("em"), "origem": e.get("origem") or "n/d"}
        leg = banco.cfg_ler(CH_VEREDITOS)
        if isinstance(leg, dict) and isinstance(leg.get("geral"), dict):
            return {"snap": leg, "em": None, "origem": "monitor (leitura antiga)"}
    except Exception:
        pass
    return None


def idade_da_leitura(em_iso: str | None, agora=None) -> dict:
    """{'texto', 'velha'}: 'leitura de 03/11 às 14:20' e se passou de EXIBICAO_VELHA_DIAS. Sem data → texto neutro e velha=False."""
    from datetime import datetime, timezone
    if not em_iso:
        return {"texto": "leitura anterior (data não registrada)", "velha": False}
    try:
        d = datetime.fromisoformat(em_iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        agora = agora or datetime.now(timezone.utc)
        loc = d.astimezone(timezone.utc).timestamp() - 3 * 3600          # Brasília (UTC-3), sem depender de zoneinfo
        t = datetime.fromtimestamp(loc, tz=timezone.utc)
        return {"texto": f"leitura de {t:%d/%m} às {t:%H:%M}", "velha": (agora - d).total_seconds() > EXIBICAO_VELHA_DIAS * 86400}
    except Exception:
        return {"texto": "leitura anterior (data não registrada)", "velha": False}
