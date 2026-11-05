"""Etapas 16 e 17 · Manutenção do banco, backup das configurações e checagem de continuidade.

16 · OTIMIZAÇÃO: o banco guarda contadores e configurações em `config_sistema`. Sem faxina ele só cresce (uso por conta e por dia,
    consumo por fonte e por dia, tentativas de cupom). `limpar()` apaga o que passou do prazo (uso 40 dias, consumo diário 120 dias,
    tentativas de cupom 3 dias) em lotes pequenos, no máximo uma vez por dia (pelo monitor). Nada que defina plano, cupom, teste
    ou configuração é apagado. As buscas por prefixo (`comeca`) usam o índice da chave em vez de varrer a tabela.
17 · CONTINUIDADE: `backup_config()` exporta o que não dá para recriar (plano e validade de cada conta, cupons e resgates, testes grátis,
    todas as configurações) e `restaurar_config()` devolve; `continuidade()` resume o que protege o app se uma parte cair.
Os contadores de uso/consumo e as cópias de cache NÃO entram no backup: recomeçam sozinhos.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

RETENCAO = {"uso|": 40, "consumo|": 120, "cupom_tent|": 3}
LOTE = 300
PREFIXOS_BACKUP = ("plano|", "cupom|", "resgate|", "teste|")
CFGS_BACKUP = ("consumo_cfg", "prioridade", "planos_cfg", "custos_cfg", "precos_cfg", "assin_cfg", "abuso_cfg")
VERSAO = 1


def _data_do_id(i: str) -> date | None:
    partes = str(i).split("|")
    try:
        return date.fromisoformat(partes[1])
    except (IndexError, ValueError):
        return None


def limpar(hoje: date, lote: int = LOTE) -> dict:
    """Apaga contadores vencidos. Os ids começam pela data, então o mais antigo vem primeiro e para no primeiro que ainda vale."""
    import banco
    apagados = {}
    for pref, dias in RETENCAO.items():
        corte = hoje - timedelta(days=dias)
        n = 0
        try:
            for r in banco._selecionar("config_sistema", {"id": ("comeca", pref)}, ["id"], ordem="id", limite=lote):
                d = _data_do_id(r["id"])
                if d is None or d >= corte:
                    if d is not None and d >= corte:
                        break
                    continue
                banco._apagar("config_sistema", {"id": r["id"]})
                n += 1
        except Exception:
            pass
        apagados[pref] = n
    return apagados


def limpar_se_for_a_vez(hoje: date) -> dict | None:
    """Uma faxina por dia (marca em `manut|dia`... que não é apagada por si mesma: o id não começa por prefixo de retenção)."""
    import banco
    try:
        if (banco.cfg_ler("manutencao_ultima") or {}).get("dia") == hoje.isoformat():
            return None
        r = limpar(hoje)
        banco.cfg_gravar("manutencao_ultima", {"dia": hoje.isoformat(), "apagados": r})
        return r
    except Exception:
        return None


def tamanho() -> dict:
    """Quantos registros há por tipo em config_sistema (para o administrador acompanhar o crescimento)."""
    import banco
    out = {}
    for rotulo, pref in (("Uso por conta e dia", "uso|"), ("Consumo por fonte e dia", "consumo|"), ("Cópias de cache", "cache|"),
                         ("Planos de contas", "plano|"), ("Cupons", "cupom|"), ("Resgates de cupom", "resgate|")):
        try:
            out[rotulo] = banco._contar("config_sistema", {"id": ("comeca", pref)})
        except Exception:
            out[rotulo] = None
    return out


# ---------------------------------------------------------------- Etapa 17: backup das configurações
def backup_config() -> dict:
    import banco
    itens = {}
    for pref in PREFIXOS_BACKUP:
        for r in banco._selecionar("config_sistema", {"id": ("comeca", pref)}, ["id", "dados"], limite=20000):
            itens[r["id"]] = banco._de_js(r["dados"]) or {}
    for k in CFGS_BACKUP:
        v = banco.cfg_ler(k)
        if v:
            itens[k] = v
    return {"versao": VERSAO, "criado": date.today().isoformat(), "itens": itens}


def _chave_valida(k: str) -> bool:
    return k in CFGS_BACKUP or any(k.startswith(p) for p in PREFIXOS_BACKUP)


def restaurar_config(bruto: dict) -> dict:
    """Grava de volta só chaves conhecidas e dados no formato esperado. Devolve {'restaurados': n, 'ignorados': n}."""
    import banco
    if not isinstance(bruto, dict) or bruto.get("versao") != VERSAO or not isinstance(bruto.get("itens"), dict):
        raise ValueError("Arquivo de backup inválido ou de outra versão.")
    ok = ign = 0
    for k, v in bruto["itens"].items():
        if _chave_valida(str(k)) and isinstance(v, dict) and len(str(k)) <= 120 and len(json.dumps(v)) < 60000:
            banco.cfg_gravar(str(k), v)
            ok += 1
        else:
            ign += 1
    try:
        import assinaturas
        import abuso
        import planos
        assinaturas.limpar_cache(); abuso.limpar(); planos._cache.update({"cfg": None, "t": 0.0, "planos": {}})
    except Exception:
        pass
    return {"restaurados": ok, "ignorados": ign}


def backup_para_arquivo(chave: str) -> tuple[bytes, str]:
    import backup_seg
    return backup_seg.backup_json_cifrado(backup_config(), chave)


def restaurar_de_arquivo(cifrado: bytes, chave: str) -> dict:
    import backup_seg
    try:
        bruto = json.loads(backup_seg.decifrar(cifrado, chave).decode("utf-8"))
    except Exception:
        raise ValueError("Não consegui abrir o arquivo: chave errada ou arquivo corrompido.")
    return restaurar_config(bruto)


# ---------------------------------------------------------------- continuidade
def continuidade(agora_iso: str | None = None) -> list[dict]:
    """Lista de verificações reais: {nome, situacao ('ok'|'aviso'|'erro'), detalhe}."""
    import banco
    import consumo
    from datetime import datetime, timezone
    itens = []
    sup = banco.backend() == "supabase"
    itens.append({"nome": "Banco de dados", "situacao": "ok" if sup else "aviso",
                  "detalhe": "Supabase (dados sobrevivem a reinícios)" if sup else "Arquivo local: pode se perder quando o app reinicia"})
    try:
        ult = banco.monitor_ultima(1)
        if not ult:
            itens.append({"nome": "Monitor automático", "situacao": "aviso", "detalhe": "Nenhuma execução registrada ainda"})
        else:
            ini = datetime.fromisoformat(str(ult[0]["inicio"]).replace("Z", "+00:00"))
            agora = datetime.fromisoformat(agora_iso.replace("Z", "+00:00")) if agora_iso else datetime.now(timezone.utc)
            h = (agora - ini).total_seconds() / 3600
            itens.append({"nome": "Monitor automático", "situacao": "ok" if h <= 6 else "aviso" if h <= 30 else "erro",
                          "detalhe": f"Última execução há {h:.0f} h ({ult[0]['status']})"})
    except Exception:
        itens.append({"nome": "Monitor automático", "situacao": "aviso", "detalhe": "Não consegui ler as execuções"})
    itens.append({"nome": "Cache no banco", "situacao": "ok" if banco.cfg_disponivel() else "aviso",
                  "detalhe": "Dados guardados: o app serve o último dado real se uma fonte cair" if banco.cfg_disponivel() else "Tabela de configuração ausente"})
    try:
        pausadas = [i["nome"] for i in consumo.resumo() if i["situacao"] == "pausado"]
        itens.append({"nome": "Fontes de dados", "situacao": "aviso" if pausadas else "ok",
                      "detalhe": ("Pausadas por falhas: " + ", ".join(pausadas)) if pausadas else "Nenhuma fonte pausada"})
    except Exception:
        pass
    try:
        ult = banco.cfg_ler("backup_config_ultimo") or {}
        if not ult.get("dia"):
            itens.append({"nome": "Backup das configurações", "situacao": "aviso", "detalhe": "Nenhum backup gerado ainda"})
        else:
            dias = (date.today() - date.fromisoformat(ult["dia"])).days
            itens.append({"nome": "Backup das configurações", "situacao": "ok" if dias <= 30 else "aviso", "detalhe": f"Último há {dias} dia(s)"})
    except Exception:
        pass
    return itens
