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
