"""TickerCoins (TC): moeda virtual interna do TickerHunters. Módulo sem Streamlit (as telas ficam em tickercoins_app.py).

O que é e o que NÃO é
 · É um crédito de uso DENTRO do app: ganha-se por estudo (e, no futuro, por anúncios recompensados) e gasta-se na Loja Ticker.
 · NÃO é dinheiro, investimento nem valor mobiliário; não tem saque, conversão, transferência entre pessoas nem negociação.
 · É independente do XP da Jornada, da carteira de investimentos e dos pontos do Wallet Game: nenhum desses sistemas é alterado.

Como o saldo é protegido (tudo no servidor)
 · Livro-razão (tabela tc_livro): cada movimentação é uma linha com número de ordem (seq) por conta e o saldo depois dela. O saldo é a
   última linha; nunca vem do navegador e nunca fica só em st.session_state.
 · Idempotência: cada lançamento tem uma `chave` única ("rec:licao:L1", "compra:<req>"). Repetir o pedido devolve o lançamento já feito.
 · Concorrência: índice único (conta_id, seq). Dois pedidos simultâneos tentam o mesmo seq; o segundo falha, relê o saldo e tenta de
   novo, então um débito nunca passa do saldo. Funciona igual no SQLite e no Supabase (REST), sem depender de transação SQL.
 · Saldo negativo é impossível: o débito confere o saldo antes e a corrida é resolvida pelo seq.
 · Quem pede nunca informa a quantidade: valores vêm da configuração (config_sistema, chave tc_config) ou do catálogo.
Configuração (preços, recompensas, limites, campanhas) em `config()`; o administrador altera pelo painel, sem mexer no código.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import banco
import permissoes
import seguranca as seg

MOEDA = {"id": "tickercoin", "nome": "TickerCoins", "simbolo": "TC"}
AVISO = ("TickerCoins são créditos de uso dentro do app. Não são dinheiro, investimento nem valor mobiliário, "
         "não podem ser sacadas, transferidas, vendidas ou convertidas em dinheiro.")
MAX_VALOR = 100_000

ESTADOS = ("confirmada", "pendente", "cancelada", "estornada")
ROTULO_ESTADO = {"confirmada": "Confirmada", "pendente": "Pendente de validação", "cancelada": "Cancelada", "estornada": "Estornada"}


class ErroTC(Exception):
    """Erro de regra (mensagem própria para a pessoa)."""


class SaldoInsuficiente(ErroTC):
    pass


# ------------------------------------------------------------------ tempo
def _agora(agora: datetime | None = None) -> datetime:
    return (agora or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _de_iso(txt: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(txt)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def inicio_do_dia(agora: datetime | None = None) -> datetime:
    """Meia-noite de Brasília (UTC-3) do dia de `agora`, em UTC."""
    loc = _agora(agora) - timedelta(hours=3)
    return loc.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=3)


def fim_do_dia(agora: datetime | None = None) -> datetime:
    return inicio_do_dia(agora) + timedelta(days=1)


# ------------------------------------------------------------------ configuração (administrador altera; nada de preço fixo no código)
CFG_PADRAO = {
    "recompensas": {
        "licao": {"rotulo": "Concluir uma lição pela primeira vez", "valor": 5, "ativo": True},
        "licao_perfeita": {"rotulo": "Lição sem nenhum erro (primeira vez)", "valor": 2, "ativo": True},
        "revisao": {"rotulo": "Concluir uma revisão de erros (1 por dia)", "valor": 1, "ativo": True},
        "conquista": {"rotulo": "Desbloquear uma conquista da Jornada", "valor": 10, "ativo": True},
        "desafio": {"rotulo": "Concluir um desafio educativo", "valor": 8, "ativo": True},
    },
    "limite_diario_ganhos": 40,                 # teto de TC por dia vindos de atividades (anúncios têm limite próprio)
    "anuncios": {"ativo": False, "valor": 3, "limite_dia": 5, "intervalo_min": 10},
    "campanhas": [],                            # [{"id","rotulo","multiplicador","inicio","fim"}] (datas ISO); multiplica recompensas de atividade
    "produtos": {},                             # {produto_id: {"preco","ativo","validade_h"}}: sobrescreve o catálogo
}
_CFG = {"v": None, "t": 0.0}
_LOCK = threading.Lock()


def _mesclar(base: dict, extra: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "produtos":
            for k2, v2 in v.items():
                if isinstance(v2, dict) and isinstance(out[k].get(k2), dict):
                    out[k][k2].update(v2)
                else:
                    out[k][k2] = v2
        else:
            out[k] = v
    return out


def config(forcar: bool = False) -> dict:
    """Configuração em vigor (padrão + o que o administrador salvou). Cache curto; falha do banco usa o padrão."""
    if not forcar and _CFG["v"] is not None and time.time() - _CFG["t"] < 30:
        return _CFG["v"]
    salvo = {}
    try:
        salvo = banco.cfg_ler("tc_config") or {}
    except Exception:
        pass
    _CFG["v"], _CFG["t"] = _mesclar(CFG_PADRAO, salvo), time.time()
    return _CFG["v"]


def salvar_config(ator, novo: dict, justificativa: str = "") -> dict:
    """Só administrador (permissão admin.tickercoins). Valida, grava e audita."""
    exigir(ator, "admin.tickercoins")
    cfg = _mesclar(CFG_PADRAO, banco.cfg_ler("tc_config") or {})
    cfg = _mesclar(cfg, novo or {})
    _validar_config(cfg)
    banco.auditar(ator.id, "tc.config", None, {"just": str(justificativa)[:160]}, obrigatorio=True)
    banco.cfg_gravar("tc_config", cfg)
    _CFG["v"] = None
    return cfg


def _validar_config(cfg: dict) -> None:
    for k, r in cfg["recompensas"].items():
        if not isinstance(r.get("valor"), int) or not (0 <= r["valor"] <= 1000):
            raise ErroTC(f"Valor inválido na recompensa “{k}”.")
    if not (0 <= int(cfg["limite_diario_ganhos"]) <= 10_000):
        raise ErroTC("Limite diário inválido.")
    a = cfg["anuncios"]
    if not (0 <= int(a["valor"]) <= 1000 and 0 <= int(a["limite_dia"]) <= 100 and 0 <= int(a["intervalo_min"]) <= 1440):
        raise ErroTC("Valores de anúncio inválidos.")
    for pid, o in cfg["produtos"].items():
        if "preco" in o and not (isinstance(o["preco"], int) and 0 <= o["preco"] <= MAX_VALOR):
            raise ErroTC(f"Preço inválido em “{pid}”.")


def exigir(ator, permissao: str) -> None:
    if not ator or not permissoes.tem(getattr(ator, "papel", None), permissao):
        raise banco.SemPermissao("Sem permissão para esta operação.")


# ------------------------------------------------------------------ disponibilidade do banco
_DISP = {"ok": None, "t": 0.0}


def disponivel() -> tuple[bool, str]:
    """(ok, motivo). No Supabase as tabelas tc_* precisam ter sido criadas com o script SQL (Administração > Banco)."""
    if _DISP["ok"] is not None and time.time() - _DISP["t"] < 60:
        return _DISP["ok"]
    try:
        banco.pronto()
        banco._contar("tc_livro", {"id": "-"})
        banco._contar("tc_compras", {"id": "-"})
        res = (True, "")
    except Exception:
        res = (False, "As tabelas do TickerCoins ainda não existem no banco. O administrador precisa rodar o script SQL atualizado.")
    _DISP["ok"], _DISP["t"] = res, time.time()
    return res


# ------------------------------------------------------------------ livro-razão
def _ultimo(conta_id: str) -> tuple[int, int]:
    r = banco._selecionar("tc_livro", {"conta_id": conta_id}, ["seq", "saldo_apos"], ordem="seq", desc=True, limite=1)
    return (int(r[0]["seq"]), int(r[0]["saldo_apos"])) if r else (0, 0)


def saldo(conta_id: str) -> int:
    """Saldo atual (última linha do livro). Conta sem lançamentos = 0 (a carteira nasce sozinha no primeiro lançamento)."""
    if not conta_id:
        return 0
    return _ultimo(conta_id)[1]


def _por_chave(chave: str) -> dict | None:
    r = banco._selecionar("tc_livro", {"chave": chave}, None, limite=1)
    return _tratar(r[0]) if r else None


def _tratar(r: dict) -> dict:
    r = dict(r)
    r["dados"] = banco._de_js(r.get("dados")) if r.get("dados") is not None else {}
    return r


def _valor_ok(v) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0 or v > MAX_VALOR:
        raise ErroTC("Valor inválido.")
    return v


def _lancar(conta_id: str, tipo: str, delta: int, estado: str, origem: str, descricao: str, chave: str,
            ref: str = "", dados: dict | None = None, exige_saldo: bool = False, agora: datetime | None = None) -> dict:
    """Grava uma linha do livro. Devolve a linha (com "duplicado": True se a chave já existia: nada foi lançado de novo)."""
    if not conta_id or not chave:
        raise ErroTC("Conta ou chave ausente.")
    for _ in range(8):
        antigo = _por_chave(chave)
        if antigo:
            antigo["duplicado"] = True
            return antigo
        seq, sal = _ultimo(conta_id)
        novo = sal + delta
        if exige_saldo and novo < 0:
            raise SaldoInsuficiente(f"Saldo insuficiente: você tem {sal} TC e precisa de {-delta}.")
        linha = {"id": uuid.uuid4().hex, "conta_id": conta_id, "seq": seq + 1, "delta": int(delta), "saldo_apos": novo, "tipo": tipo,
                 "estado": estado, "origem": str(origem)[:60], "descricao": str(descricao)[:200], "chave": str(chave)[:120],
                 "ref": str(ref)[:120], "criado_em": _iso(_agora(agora)), "dados": banco._js(dados or {})}
        try:
            banco._inserir("tc_livro", linha)
            linha["dados"] = dados or {}
            linha["duplicado"] = False
            return linha
        except banco.Duplicado:
            continue                      # outro pedido ocupou este seq (ou esta chave): relê e tenta de novo
    raise ErroTC("O saldo está sendo atualizado por outro pedido. Tente de novo.")


def creditar(conta_id: str, valor: int, origem: str, descricao: str, chave: str, ref: str = "", dados: dict | None = None,
             agora: datetime | None = None) -> dict:
    return _lancar(conta_id, "credito", _valor_ok(valor), "confirmada", origem, descricao, chave, ref, dados, agora=agora)


def debitar(conta_id: str, valor: int, origem: str, descricao: str, chave: str, ref: str = "", dados: dict | None = None,
            agora: datetime | None = None) -> dict:
    return _lancar(conta_id, "debito", -_valor_ok(valor), "confirmada", origem, descricao, chave, ref, dados, exige_saldo=True, agora=agora)


def registrar_pendente(conta_id: str, valor: int, origem: str, descricao: str, chave: str, dados: dict | None = None,
                       agora: datetime | None = None) -> dict:
    """Recompensa aguardando validação (ex.: anúncio ainda não confirmado pelo provedor). Não mexe no saldo."""
    d = {**(dados or {}), "valor": _valor_ok(valor)}
    return _lancar(conta_id, "pendente", 0, "pendente", origem, descricao, chave, "", d, agora=agora)


def confirmar_pendente(conta_id: str, chave_pendente: str, agora: datetime | None = None) -> dict:
    p = _por_chave(chave_pendente)
    if not p or p["conta_id"] != conta_id or p["tipo"] != "pendente":
        raise ErroTC("Recompensa pendente não encontrada.")
    if p["estado"] == "cancelada":
        raise ErroTC("Esta recompensa foi cancelada.")
    linha = creditar(conta_id, int(p["dados"].get("valor", 0)), p["origem"], p["descricao"], f"conf:{chave_pendente}", chave_pendente, agora=agora)
    if p["estado"] == "pendente":
        banco._atualizar("tc_livro", {"id": p["id"]}, {"estado": "confirmada"})
    return linha


def cancelar_pendente(conta_id: str, chave_pendente: str) -> None:
    p = _por_chave(chave_pendente)
    if not p or p["conta_id"] != conta_id or p["tipo"] != "pendente" or p["estado"] != "pendente":
        raise ErroTC("Nada a cancelar.")
    banco._atualizar("tc_livro", {"id": p["id"]}, {"estado": "cancelada"})


def estornar(conta_id: str, chave_original: str, motivo: str, agora: datetime | None = None) -> dict:
    """Desfaz um DÉBITO (devolve as moedas). Idempotente. Estornar um crédito é recusado se deixaria o saldo negativo."""
    o = _por_chave(chave_original)
    if not o or o["conta_id"] != conta_id:
        raise ErroTC("Lançamento não encontrado.")
    if o["tipo"] not in ("debito", "credito") or o["estado"] not in ("confirmada", "estornada"):
        raise ErroTC("Este lançamento não pode ser estornado.")
    chave = f"estorno:{chave_original}"
    delta = -int(o["delta"])
    linha = _lancar(conta_id, "estorno", delta, "confirmada", "estorno", f"Estorno: {motivo}"[:200], chave, chave_original,
                    exige_saldo=delta < 0, agora=agora)
    if o["estado"] == "confirmada":
        banco._atualizar("tc_livro", {"id": o["id"]}, {"estado": "estornada"})
    return linha


def historico(conta_id: str, limite: int = 100) -> list[dict]:
    if not conta_id:
        return []
    return [_tratar(r) for r in banco._selecionar("tc_livro", {"conta_id": conta_id}, None, ordem="seq", desc=True, limite=limite)]


def conferir_saldo(conta_id: str) -> dict:
    """Recalcula o saldo somando o livro inteiro e compara com a última linha (auditoria de integridade)."""
    linhas = banco._selecionar("tc_livro", {"conta_id": conta_id}, ["seq", "delta", "saldo_apos"], ordem="seq", limite=100_000)
    soma = sum(int(x["delta"]) for x in linhas)
    ultimo = int(linhas[-1]["saldo_apos"]) if linhas else 0
    corrente, ok = 0, True
    for x in linhas:
        corrente += int(x["delta"])
        ok = ok and corrente == int(x["saldo_apos"])
    return {"ok": ok and soma == ultimo and soma >= 0, "soma": soma, "ultimo": ultimo, "linhas": len(linhas)}


def totais(conta_id: str) -> dict:
    """Total recebido e total usado (só lançamentos confirmados)."""
    rec = uso = 0
    for x in banco._selecionar("tc_livro", {"conta_id": conta_id}, ["delta", "tipo", "estado"], limite=100_000):
        if x["estado"] == "pendente" or x["tipo"] == "pendente":
            continue
        d = int(x["delta"])
        if d > 0:
            rec += d
        else:
            uso += -d
    return {"recebido": rec, "usado": uso}


# ------------------------------------------------------------------ recompensas por atividade
def _multiplicador(agora: datetime) -> tuple[int, str]:
    m, rot = 1, ""
    for c in config().get("campanhas") or []:
        ini, fim = _de_iso(c.get("inicio")), _de_iso(c.get("fim"))
        if ini and fim and ini <= agora < fim and int(c.get("multiplicador", 1)) > m:
            m, rot = int(c["multiplicador"]), str(c.get("rotulo", "Campanha"))
    return m, rot


def ganhos_hoje(conta_id: str, agora: datetime | None = None) -> int:
    """TC recebidos hoje por ATIVIDADES (o teto diário vale para eles; ajustes do administrador e estornos não contam)."""
    ini = _iso(inicio_do_dia(agora))
    rows = banco._selecionar("tc_livro", {"conta_id": conta_id, "criado_em": ("gte", ini), "origem": ("comeca", "atividade")},
                             ["delta", "tipo"], limite=500)
    return sum(int(r["delta"]) for r in rows if r["tipo"] == "credito")


def recompensar(conta_id: str, evento: str, ref: str, descricao: str = "", agora: datetime | None = None) -> dict | None:
    """Credita a recompensa de um evento CONCLUÍDO. `ref` identifica o fato (id da lição, da conquista, data da revisão): mesma
    ref = mesma recompensa, uma vez só (atualizar a página ou repetir o pedido não duplica). Devolve None se não houve crédito
    novo (desligada, já paga, teto do dia atingido); caso contrário a linha do livro."""
    if not conta_id:
        return None
    cfg = config()
    r = cfg["recompensas"].get(evento)
    if not r or not r.get("ativo") or int(r.get("valor", 0)) <= 0:
        return None
    agora = _agora(agora)
    chave = f"rec:{evento}:{ref}"
    if _por_chave(chave):
        return None
    mult, camp = _multiplicador(agora)
    valor = int(r["valor"]) * mult
    resta = int(cfg["limite_diario_ganhos"]) - ganhos_hoje(conta_id, agora)
    if resta <= 0:
        return None
    valor = min(valor, resta)
    desc = descricao or r["rotulo"]
    if camp:
        desc += f" ({camp}: x{mult})"
    linha = creditar(conta_id, valor, f"atividade:{evento}", desc, chave, str(ref), agora=agora)
    return None if linha.get("duplicado") else linha


def recompensar_sessao(conta_id: str, resultado: dict, conquistas_novas: list | None = None, agora: datetime | None = None) -> list[dict]:
    """Aplica as regras ao resultado de uma sessão da Jornada (o dict de `jornada.concluir_sessao`). Nunca levanta erro."""
    out = []
    try:
        if not resultado or not resultado.get("ok"):
            return out
        agora = _agora(agora)
        if resultado.get("revisao"):
            x = recompensar(conta_id, "revisao", (agora - timedelta(hours=3)).strftime("%Y-%m-%d"), agora=agora)
            return [x] if x else out
        lic = resultado.get("licao")
        if lic:
            for ev, cond in (("licao", True), ("licao_perfeita", bool(resultado.get("perfeita")))):
                if cond:
                    x = recompensar(conta_id, ev, lic, agora=agora)
                    if x:
                        out.append(x)
        for c in conquistas_novas or []:
            x = recompensar(conta_id, "conquista", str(c), f"Conquista: {c}", agora=agora)
            if x:
                out.append(x)
    except Exception as e:
        try:
            banco.registrar_erro("tickercoins.recompensar", e)
        except Exception:
            pass
    return out


# ------------------------------------------------------------------ anúncios recompensados (estrutura pronta; sem provedor = indisponível)
class ProvedorAnuncio:
    """Adaptador de um provedor de anúncios recompensados (AdMob no Android, outro provedor na web).
    Herde, implemente `configurado` e `verificar` e registre com `registrar_provedor`. Nada aqui simula anúncio."""
    nome = "provedor"

    def configurado(self) -> bool:
        return False

    def verificar(self, payload: dict) -> dict | None:
        """Valida a notificação do provedor (assinatura/SSV). Devolve {"tx": id_único_da_transação, "conta_id": quem assistiu}
        se for autêntica e a visualização foi concluída; None se for inválida. NUNCA devolve valor: o valor vem da configuração."""
        return None


PROVEDORES: dict[str, ProvedorAnuncio] = {}


def registrar_provedor(p: ProvedorAnuncio) -> None:
    PROVEDORES[p.nome] = p


def anuncios_status() -> dict:
    """{"disponivel": bool, "motivo": str}. Só fica disponível com a opção ligada pelo administrador E um provedor configurado."""
    a = config()["anuncios"]
    if not any(p.configurado() for p in PROVEDORES.values()):
        return {"disponivel": False, "motivo": "Em preparação: ainda não há provedor de anúncios conectado."}
    if not a.get("ativo"):
        return {"disponivel": False, "motivo": "Anúncios recompensados desativados no momento."}
    return {"disponivel": True, "motivo": ""}


def _tentativa_invalida(conta_id: str | None, provedor: str, motivo: str) -> None:
    try:
        banco.auditar(conta_id, "tc.fraude", None, {"prov": str(provedor)[:30], "motivo": str(motivo)[:80]})
    except Exception:
        pass


def creditar_anuncio(conta_id: str, provedor: str, payload: dict, agora: datetime | None = None) -> dict:
    """Credita um anúncio concluído, SÓ se o provedor confirmar a autenticidade. Devolve {"ok", "erro", "linha"}."""
    agora = _agora(agora)
    st = anuncios_status()
    p = PROVEDORES.get(provedor)
    if not st["disponivel"] or p is None:
        _tentativa_invalida(conta_id, provedor, "provedor indisponível")
        return {"ok": False, "erro": st["motivo"] or "Provedor desconhecido."}
    try:
        res = p.verificar(payload or {})
    except Exception:
        res = None
    if not res or not res.get("tx") or res.get("conta_id") != conta_id:
        _tentativa_invalida(conta_id, provedor, "notificação inválida")
        return {"ok": False, "erro": "Não foi possível confirmar a visualização do anúncio."}
    a = config()["anuncios"]
    ini = _iso(inicio_do_dia(agora))
    hoje = banco._selecionar("tc_livro", {"conta_id": conta_id, "criado_em": ("gte", ini), "origem": ("comeca", "anuncio")}, ["criado_em", "tipo"],
                             ordem="criado_em", desc=True, limite=200)
    hoje = [x for x in hoje if x["tipo"] == "credito"]
    chave = f"anuncio:{provedor}:{res['tx']}"
    if _por_chave(chave):
        return {"ok": False, "erro": "Esta recompensa já foi creditada.", "duplicada": True}
    if len(hoje) >= int(a["limite_dia"]):
        _tentativa_invalida(conta_id, provedor, "limite diário")
        return {"ok": False, "erro": "Você atingiu o limite diário de anúncios recompensados."}
    if hoje:
        ult = _de_iso(hoje[0]["criado_em"])
        if ult and agora - ult < timedelta(minutes=int(a["intervalo_min"])):
            _tentativa_invalida(conta_id, provedor, "intervalo")
            return {"ok": False, "erro": f"Aguarde {int(a['intervalo_min'])} minutos entre os anúncios."}
    linha = creditar(conta_id, int(a["valor"]), f"anuncio:{provedor}", "Anúncio recompensado assistido", chave, str(res["tx"]), agora=agora)
    return {"ok": True, "linha": linha}


# ------------------------------------------------------------------ catálogo da Loja Ticker (só o que o app realmente entrega)
CATEGORIAS = {"ferramentas": "Ferramentas e análises", "educacao": "Educação", "personalizacao": "Personalização", "experiencias": "Experiências e desafios"}

# efeito.kind: "distintivo" (mostrado ao lado do nome), "moldura" (aro do avatar), "bonus_limite" (+N no limite DIÁRIO de um recurso até a meia-noite)
CATALOGO = [
    {"id": "dist_cacador", "categoria": "personalizacao", "nome": "Distintivo Caçador", "descricao": "Um alvo ao lado do seu nome.",
     "icone": "alvo", "cor": "#8B6CFF", "preco": 30, "validade_h": None, "efeito": {"kind": "distintivo", "emoji": "🎯"}},
    {"id": "dist_estudioso", "categoria": "personalizacao", "nome": "Distintivo Estudioso", "descricao": "Um livro ao lado do seu nome.",
     "icone": "livro", "cor": "#2BA7C9", "preco": 30, "validade_h": None, "efeito": {"kind": "distintivo", "emoji": "📚"}},
    {"id": "dist_touro", "categoria": "personalizacao", "nome": "Distintivo Touro", "descricao": "Um touro ao lado do seu nome.",
     "icone": "grafico", "cor": "#3DDC97", "preco": 45, "validade_h": None, "efeito": {"kind": "distintivo", "emoji": "🐂"}},
    {"id": "dist_foguete", "categoria": "personalizacao", "nome": "Distintivo Foguete", "descricao": "Um foguete ao lado do seu nome.",
     "icone": "raio", "cor": "#FF9B3D", "preco": 60, "validade_h": None, "efeito": {"kind": "distintivo", "emoji": "🚀"}},
    {"id": "mold_ouro", "categoria": "personalizacao", "nome": "Moldura Ouro", "descricao": "Aro dourado no seu avatar.",
     "icone": "estrela", "cor": "#F2B84B", "preco": 80, "validade_h": None, "efeito": {"kind": "moldura", "cor": "#F2B84B"}},
    {"id": "mold_esmeralda", "categoria": "personalizacao", "nome": "Moldura Esmeralda", "descricao": "Aro verde no seu avatar.",
     "icone": "escudo", "cor": "#3DDC97", "preco": 60, "validade_h": None, "efeito": {"kind": "moldura", "cor": "#3DDC97"}},
    {"id": "mold_neon", "categoria": "personalizacao", "nome": "Moldura Neon", "descricao": "Aro roxo brilhante no seu avatar.",
     "icone": "raio", "cor": "#B02FC8", "preco": 70, "validade_h": None, "efeito": {"kind": "moldura", "cor": "#B02FC8"}},
    {"id": "ext_noticias", "categoria": "ferramentas", "nome": "+10 atualizações de notícias hoje",
     "descricao": "Mais 10 atualizações manuais da Central de notícias até a meia-noite.", "icone": "livro", "cor": "#6E8BFF", "preco": 8,
     "validade_h": "meia_noite", "efeito": {"kind": "bonus_limite", "recurso": "noticias_atualizar", "extra": 10}, "planos_excluidos": ["premium"]},
    {"id": "ext_ia", "categoria": "ferramentas", "nome": "+10 mensagens ao assistente hoje",
     "descricao": "Mais 10 mensagens ao assistente de IA até a meia-noite.", "icone": "lupa", "cor": "#FF6B8A", "preco": 12,
     "validade_h": "meia_noite", "efeito": {"kind": "bonus_limite", "recurso": "ia_mensagens", "extra": 10}, "planos_excluidos": ["premium"]},
    {"id": "ext_resumos", "categoria": "ferramentas", "nome": "+10 resumos com IA hoje",
     "descricao": "Mais 10 resumos de ativos com IA até a meia-noite.", "icone": "balanca", "cor": "#FF9B3D", "preco": 12,
     "validade_h": "meia_noite", "efeito": {"kind": "bonus_limite", "recurso": "ia_resumos", "extra": 10}, "planos_excluidos": ["premium"]},
]
# Categorias sem conteúdo real hoje: aparecem como "em preparação", sem preço nem botão de compra (nada é vendido sem ser entregue).
EM_PREPARACAO = {
    "educacao": "Aulas e materiais exclusivos: ainda não há conteúdo exclusivo para desbloquear.",
    "experiencias": "Desafios e experiências extras: ainda não existem desafios adicionais que possam ser liberados sem afetar a classificação do jogo.",
}
_POR_ID = {p["id"]: p for p in CATALOGO}


def produto(pid: str) -> dict | None:
    """Produto com as configurações do administrador (preço, ativo, validade) aplicadas."""
    base = _POR_ID.get(pid)
    if not base:
        return None
    o = (config().get("produtos") or {}).get(pid) or {}
    p = dict(base)
    p["preco"] = int(o.get("preco", base["preco"]))
    p["ativo"] = bool(o.get("ativo", True))
    if "validade_h" in o:
        p["validade_h"] = o["validade_h"]
    return p


def produtos(categoria: str | None = None, so_ativos: bool = True) -> list[dict]:
    out = [produto(p["id"]) for p in CATALOGO if not categoria or p["categoria"] == categoria]
    return [p for p in out if p and (p["ativo"] or not so_ativos)]


def rotulo_validade(v) -> str:
    if v is None:
        return "Permanente"
    if v == "meia_noite":
        return "Até a meia-noite"
    if v == 24:
        return "24 horas"
    if v % 24 == 0:
        return f"{v // 24} dias"
    return f"{v} horas"


def _expira_em(p: dict, agora: datetime) -> str | None:
    v = p.get("validade_h")
    if v is None:
        return None
    if v == "meia_noite":
        return _iso(fim_do_dia(agora))
    return _iso(agora + timedelta(hours=int(v)))


# ------------------------------------------------------------------ compras e benefícios
def _compra(r: dict) -> dict:
    r = dict(r)
    r["dados"] = banco._de_js(r.get("dados")) if r.get("dados") is not None else {}
    return r


def compras(conta_id: str, limite: int = 200) -> list[dict]:
    if not conta_id:
        return []
    return [_compra(r) for r in banco._selecionar("tc_compras", {"conta_id": conta_id}, None, ordem="criado_em", desc=True, limite=limite)]


def _vigente(c: dict, agora: datetime) -> bool:
    """Benefício em vigor? A validade é conferida aqui, no servidor, a cada leitura: vencido deixa de valer sozinho."""
    if c["estado"] != "confirmada":
        return False
    exp = _de_iso(c.get("expira_em"))
    return exp is None or agora < exp


def beneficios_ativos(conta_id: str, agora: datetime | None = None) -> list[dict]:
    agora = _agora(agora)
    return [c for c in compras(conta_id) if _vigente(c, agora)]


def pode_comprar(conta_id: str, pid: str, plano: str = "gratuito", agora: datetime | None = None) -> tuple[bool, str]:
    """(ok, motivo). Confere disponibilidade, plano (sem cobrar por algo que o plano já cobre) e duplicidade."""
    p = produto(pid)
    if not p or not p["ativo"]:
        return False, "Produto indisponível."
    if plano in (p.get("planos_excluidos") or []):
        return False, "Seu plano já inclui este recurso em volume maior: não precisa gastar moedas."
    ativos = [c for c in beneficios_ativos(conta_id, agora) if c["produto_id"] == pid]
    if ativos:
        return False, "Você já tem este benefício ativo." if p["validade_h"] is not None else "Você já tem este item."
    return True, ""


def comprar(conta_id: str, pid: str, req_id: str, plano: str = "gratuito", agora: datetime | None = None) -> dict:
    """Compra com débito seguro e entrega. `req_id` (gerado uma vez por confirmação) torna o pedido idempotente: clicar duas vezes
    não cobra duas vezes. Se a entrega falhar, as moedas voltam. Devolve {"ok", "erro", "compra", "duplicada"}."""
    agora = _agora(agora)
    if not conta_id or not req_id:
        return {"ok": False, "erro": "Faça login para comprar."}
    cid = f"c_{req_id}"
    ja = banco._selecionar("tc_compras", {"id": cid}, None, limite=1)
    if ja:
        return {"ok": True, "compra": _compra(ja[0]), "duplicada": True}
    ok, motivo = pode_comprar(conta_id, pid, plano, agora)
    if not ok:
        return {"ok": False, "erro": motivo}
    p = produto(pid)
    chave = f"compra:{req_id}"
    try:
        deb = debitar(conta_id, p["preco"], "loja", f"Compra: {p['nome']}", chave, pid, {"produto": pid}, agora=agora)
    except SaldoInsuficiente as e:
        return {"ok": False, "erro": str(e)}
    except ErroTC as e:
        return {"ok": False, "erro": str(e)}
    linha = {"id": cid, "conta_id": conta_id, "produto_id": pid, "preco": p["preco"], "estado": "confirmada", "criado_em": _iso(agora),
             "expira_em": _expira_em(p, agora), "usos_restantes": None, "livro_chave": chave, "dados": banco._js({"nome": p["nome"]})}
    try:
        banco._inserir("tc_compras", linha)
    except banco.Duplicado:
        return {"ok": True, "compra": _compra(banco._selecionar("tc_compras", {"id": cid}, None, limite=1)[0]), "duplicada": True}
    except Exception as e:                                    # falha na entrega: as moedas voltam (estorno idempotente)
        try:
            estornar(conta_id, chave, "falha na entrega do benefício", agora)
        except Exception:
            banco.registrar_erro("tickercoins.estorno", e)
        return {"ok": False, "erro": "Não foi possível entregar o benefício. Suas moedas foram devolvidas."}
    return {"ok": True, "compra": _compra(linha), "duplicada": bool(deb.get("duplicado"))}


def estornar_compra(ator, compra_id: str, motivo: str) -> dict:
    """Administrador: devolve as moedas e encerra o benefício. Auditado."""
    exigir(ator, "admin.tickercoins")
    r = banco._selecionar("tc_compras", {"id": compra_id}, None, limite=1)
    if not r:
        raise ErroTC("Compra não encontrada.")
    c = _compra(r[0])
    banco.auditar(ator.id, "tc.estorno", c["conta_id"], {"compra": compra_id, "motivo": str(motivo)[:120]}, obrigatorio=True)
    linha = estornar(c["conta_id"], c["livro_chave"], motivo or "estorno administrativo")
    banco._atualizar("tc_compras", {"id": compra_id}, {"estado": "estornada"})
    return linha


# bônus de limite diário (usado por planos.py só quando o limite do plano já acabou)
_BONUS = {}


def bonus_limite(conta_id: str, recurso: str, agora: datetime | None = None) -> int:
    """Soma dos '+N' de benefícios comprados e ainda vigentes para um recurso diário. Cache de 15 s por conta. Nunca levanta erro."""
    try:
        if not conta_id:
            return 0
        t = time.time()
        c = _BONUS.get(conta_id)
        if c is None or t - c[0] > 15:
            c = (t, beneficios_ativos(conta_id, agora))
            _BONUS[conta_id] = c
            if len(_BONUS) > 500:
                _BONUS.pop(next(iter(_BONUS)), None)
        total = 0
        for b in c[1]:
            p = _POR_ID.get(b["produto_id"])
            if p and p["efeito"]["kind"] == "bonus_limite" and p["efeito"]["recurso"] == recurso and _vigente(b, _agora(agora)):
                total += int(p["efeito"]["extra"])
        return total
    except Exception:
        return 0


def esquecer_cache(conta_id: str) -> None:
    _BONUS.pop(conta_id, None)


# ------------------------------------------------------------------ itens de personalização (distintivo e moldura equipados)
def _chave_equip() -> str:
    return "tc_equipado"


def equipado(email: str) -> dict:
    try:
        return banco.sis_estado_ler(email, _chave_equip()) or {}
    except Exception:
        return {}


def equipar(conta_id: str, email: str, pid: str | None, tipo: str, agora: datetime | None = None) -> dict:
    """Equipa (ou tira, com pid=None) o distintivo ou a moldura. Só vale para item que a conta possui."""
    if tipo not in ("distintivo", "moldura"):
        raise ErroTC("Tipo inválido.")
    atual = dict(equipado(email))
    if pid is None:
        atual.pop(tipo, None)
    else:
        p = _POR_ID.get(pid)
        if not p or p["efeito"]["kind"] != tipo or not any(c["produto_id"] == pid for c in beneficios_ativos(conta_id, agora)):
            raise ErroTC("Você não possui este item.")
        atual[tipo] = pid
    try:
        banco.sis_estado_gravar(email, _chave_equip(), atual)
    except Exception:
        raise ErroTC("Não foi possível salvar a escolha agora.")
    return atual


def aparencia(email: str) -> dict:
    """{"distintivo": emoji|None, "moldura": cor|None} do que a pessoa equipou (para as telas)."""
    e = equipado(email)
    d, m = _POR_ID.get(e.get("distintivo")), _POR_ID.get(e.get("moldura"))
    return {"distintivo": d["efeito"]["emoji"] if d else None, "moldura": m["efeito"]["cor"] if m else None}


# ------------------------------------------------------------------ administração (cada operação exige permissão e é auditada)
def admin_ajustar(ator, conta_id: str, valor: int, justificativa: str) -> dict:
    """Adiciona (valor > 0) ou remove (valor < 0) moedas, com justificativa obrigatória. Auditado; remover nunca passa do saldo."""
    exigir(ator, "admin.tickercoins")
    just = str(justificativa or "").strip()
    if len(just) < 5:
        raise ErroTC("Informe a justificativa (mínimo 5 caracteres).")
    if not isinstance(valor, int) or valor == 0 or abs(valor) > MAX_VALOR:
        raise ErroTC("Valor inválido.")
    if not banco.sis_conta_por_id(conta_id):
        raise ErroTC("Conta não encontrada.")
    banco.auditar(ator.id, "tc.ajuste", conta_id, {"valor": valor, "just": just[:160]}, obrigatorio=True)
    chave = f"admin:{uuid.uuid4().hex}"
    linha = _lancar(conta_id, "ajuste", valor, "confirmada", "administrador", f"Ajuste administrativo: {just}"[:200], chave, exige_saldo=valor < 0)
    esquecer_cache(conta_id)
    return linha


def admin_conta(ator, email: str) -> dict | None:
    exigir(ator, "admin.tickercoins.ver")
    c = banco.sis_conta_por_email(email)
    if not c:
        return None
    return {"conta": {"id": c["id"], "email": c["email"], "nome": c.get("nome", "")}, "saldo": saldo(c["id"]), "totais": totais(c["id"]),
            "historico": historico(c["id"], 60), "compras": compras(c["id"], 60), "integridade": conferir_saldo(c["id"])}


def admin_compras_recentes(ator, limite: int = 100) -> list[dict]:
    exigir(ator, "admin.tickercoins.ver")
    return [_compra(r) for r in banco._selecionar("tc_compras", None, None, ordem="criado_em", desc=True, limite=limite)]


def admin_fraudes(ator, limite: int = 100) -> list[dict]:
    exigir(ator, "admin.tickercoins.ver")
    return banco._selecionar("auditoria", {"acao": ("comeca", "tc.fraude")}, None, ordem="quando", desc=True, limite=limite)


def admin_estatisticas(ator) -> dict:
    exigir(ator, "admin.tickercoins.ver")
    rec = uso = 0
    contas = set()
    for x in banco._selecionar("tc_livro", None, ["conta_id", "delta", "tipo"], ordem="criado_em", desc=True, limite=5000):
        if x["tipo"] == "pendente":
            continue
        contas.add(x["conta_id"])
        d = int(x["delta"])
        rec += max(d, 0)
        uso += max(-d, 0)
    compras_ = banco._selecionar("tc_compras", None, ["produto_id", "estado", "preco"], limite=5000)
    por = {}
    for c in compras_:
        if c["estado"] == "confirmada":
            por[c["produto_id"]] = por.get(c["produto_id"], 0) + 1
    return {"contas_com_moedas": len(contas), "recebido": rec, "usado": uso, "compras": sum(por.values()), "por_produto": por,
            "fraudes": banco._contar("auditoria", {"acao": ("comeca", "tc.fraude")}), "amostra": "últimos 5.000 lançamentos"}
