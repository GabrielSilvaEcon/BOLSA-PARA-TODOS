"""Competição · Etapa 2 — ligas de amigos por convite e avisos de posição. Lógica pura (sem Streamlit e sem rede), testável isoladamente.

Como as ligas se encaixam sem tabela nova e sem quebrar o isolamento entre usuários:
 · Cada pessoa tem um documento próprio `comp_ligas` (só ela grava): as ligas de que participa e se quer receber avisos.
 · Cada liga tem uma definição `comp_liga|CÓDIGO` na configuração do sistema (nome, limite de membros e um hash do dono, nunca o e-mail).
   Só o dono cria e encerra. Entrar numa liga é só a pessoa gravar o código no próprio documento (não há lista de membros compartilhada,
   então não existe disputa de escrita quando vários amigos entram ao mesmo tempo).
 · O fechamento diário cruza os documentos, monta o ranking de cada liga e publica `comp_lr|CÓDIGO` (apelido e retorno %, nunca e-mail
   nem valores em reais). A tela só lê esse ranking e só entrega a quem é membro da liga.
 · Depois do ranking, compara a posição de ontem com a de hoje e gera os avisos ("você subiu para 3º").
Educacional: carteira virtual, sem dinheiro real, sem recomendação de investimento.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlparse

import competicao as C

CH_LIGAS = "comp_ligas"            # documento da pessoa (o app grava): ligas e preferência de avisos
CFG_LIGA = "comp_liga|"            # definição da liga (o app grava, só o dono) — prefixo + código
CFG_LIGA_RANK = "comp_lr|"         # ranking da liga (só o fechamento grava) — prefixo + código
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"    # sem I, L, O, 0 e 1: fácil de ler e ditar
TAM_CODIGO = 8
MAX_LIGAS_PESSOA = 30
MAX_MEMBROS_PADRAO = 30
MAX_MEMBROS_TETO = 500
TOPO_LIGA = 500
LIMIARES_GERAL = (1, 3, 10, 100)    # subir até aqui no ranking geral gera aviso

_NOME = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 _.\-]{1,28}[A-Za-zÀ-ÿ0-9]")
_CODIGO = re.compile(r"[" + ALFABETO + r"]{" + str(TAM_CODIGO) + r"}")


# ------------------------------------------------------------------ códigos, nomes e convites
def novo_codigo() -> str:
    return "".join(secrets.choice(ALFABETO) for _ in range(TAM_CODIGO))


def codigo_valido(txt) -> str | None:
    """Código normalizado (maiúsculas, sem espaços/hífens) ou None. Aceita 'abcd-2345' e cola de link inteiro com ?liga=."""
    s = str(txt or "").strip()
    if "liga=" in s:
        s = extrair_convite(s) or ""
    s = re.sub(r"[\s\-]", "", s).upper()
    return s if _CODIGO.fullmatch(s) else None


def extrair_convite(valor) -> str | None:
    """Código de um link de convite (…/competicao?liga=CÓDIGO) ou de um parâmetro já isolado. None se não for um código válido."""
    s = str(valor or "").strip()
    if "liga=" in s:
        try:
            q = parse_qs(urlparse(s).query)
            s = (q.get("liga") or [""])[0]
        except Exception:
            return None
    s = re.sub(r"[\s\-]", "", s).upper()
    return s if _CODIGO.fullmatch(s) else None


def formatar_codigo(codigo: str) -> str:
    c = str(codigo or "")
    return f"{c[:4]}-{c[4:]}" if len(c) == TAM_CODIGO else c


def link_convite(url_base: str, codigo: str) -> str:
    base = str(url_base or "").rstrip("/")
    return f"{base}/competicao?liga={codigo}" if base else f"?liga={codigo}"


def nome_valido(nome: str) -> tuple[bool, str]:
    n = re.sub(r"\s+", " ", str(nome or "")).strip()
    if not _NOME.fullmatch(n):
        return False, "Use de 3 a 30 caracteres: letras, números, espaço, ponto, hífen ou sublinhado."
    base = re.sub(r"[\d_.\- ]", "", n.lower())
    if any(r in base for r in C._RESERVADOS) or any(b in base for b in C._BLOQUEADOS):
        return False, "Esse nome não é permitido. Escolha outro."
    return True, ""


def limpar_nome(nome: str) -> str:
    return re.sub(r"\s+", " ", str(nome or "")).strip()[:30]


def hash_dono(email: str) -> str:
    """Identifica o dono sem guardar o e-mail na definição da liga (LGPD)."""
    return hashlib.sha256(str(email or "").strip().lower().encode()).hexdigest()[:24]


# ------------------------------------------------------------------ definição e documento da pessoa
def nova_definicao(nome: str, email_dono: str, max_membros: int, agora: datetime | None = None) -> dict:
    ag = agora or datetime.now(timezone.utc)
    try:
        m = int(max_membros)
    except Exception:
        m = MAX_MEMBROS_PADRAO
    return {"v": 1, "nome": limpar_nome(nome), "dono_h": hash_dono(email_dono), "max": max(2, min(m, MAX_MEMBROS_TETO)),
            "criada": ag.strftime("%Y-%m-%d")}


def sanear_definicao(doc) -> dict | None:
    d = doc if isinstance(doc, dict) else {}
    if not d.get("nome") or not d.get("dono_h"):
        return None
    try:
        m = max(2, min(int(d.get("max") or MAX_MEMBROS_PADRAO), MAX_MEMBROS_TETO))
    except Exception:
        m = MAX_MEMBROS_PADRAO
    return {"v": 1, "nome": limpar_nome(d["nome"]), "dono_h": str(d["dono_h"])[:24], "max": m, "criada": str(d.get("criada") or "")[:10]}


def definicao_publica(codigo: str, d: dict) -> dict:
    """O que qualquer pessoa com o código pode ver antes de entrar: nome e tamanho máximo (nunca o dono)."""
    return {"codigo": codigo, "nome": d["nome"], "max": d["max"], "criada": d.get("criada", "")}


def sanear_ligas(doc) -> dict:
    """Documento da pessoa: só campos conhecidos, tipos e tamanhos conferidos, sem repetir liga."""
    d = doc if isinstance(doc, dict) else {}
    vistos, ligas = set(), []
    for x in (d.get("ligas") or [])[:MAX_LIGAS_PESSOA * 2]:
        try:
            c = codigo_valido(x.get("c"))
            if c and c not in vistos:
                vistos.add(c)
                ligas.append({"c": c, "em": date.fromisoformat(str(x.get("em"))[:10]).isoformat(), "dono": bool(x.get("dono"))})
        except Exception:
            continue
    av = d.get("avisos") if isinstance(d.get("avisos"), dict) else {}
    return {"v": 1, "ligas": ligas[:MAX_LIGAS_PESSOA], "avisos": {"liga": bool(av.get("liga", True)), "global": bool(av.get("global", True))}}


def codigos(doc: dict) -> list[str]:
    return [x["c"] for x in sanear_ligas(doc)["ligas"]]


def donas(doc: dict) -> list[str]:
    return [x["c"] for x in sanear_ligas(doc)["ligas"] if x["dono"]]


def participa(doc: dict, codigo: str) -> bool:
    return codigo in codigos(doc)


def adicionar(doc: dict, codigo: str, hoje: date, dono: bool = False) -> dict:
    d = sanear_ligas(doc)
    if codigo in [x["c"] for x in d["ligas"]]:
        return d
    d["ligas"].append({"c": codigo, "em": hoje.isoformat(), "dono": bool(dono)})
    return sanear_ligas(d)


def remover(doc: dict, codigo: str) -> dict:
    d = sanear_ligas(doc)
    d["ligas"] = [x for x in d["ligas"] if x["c"] != codigo]
    return d


# ------------------------------------------------------------------ ranking de cada liga (fechamento diário)
def montar_ligas(defs: dict, ligas_por_email: dict, participantes: list[dict], hoje: date, hash_para_apelido: dict | None = None) -> dict:
    """defs: {código: definição}. ligas_por_email: {email: documento comp_ligas}. participantes: o mesmo formato de C.montar_ranking
    ([{'apelido','email','estado'}], já sem contas suspensas e sem apelido repetido).
    Devolve {'docs': {código: documento público}, 'posicoes': {email: {código: {geral, mes, semana, n, nome, cheia}}}}."""
    por_email = {p["email"]: p for p in participantes}
    apelido_dono = hash_para_apelido or {}
    docs: dict[str, dict] = {}
    posicoes: dict[str, dict] = {}
    for codigo, raw in defs.items():
        d = sanear_definicao(raw)
        if not d:
            continue
        membros = []
        for em, doc in ligas_por_email.items():
            if em not in por_email:
                continue
            for x in sanear_ligas(doc)["ligas"]:
                if x["c"] == codigo:
                    membros.append((x["em"], em))
        if not membros:
            continue
        membros.sort()                                            # quem entrou primeiro tem a vaga se a liga lotar
        dentro, fora = membros[:d["max"]], membros[d["max"]:]
        part = [por_email[em] for _, em in dentro]
        rk = C.montar_ranking(part, hoje, topo=TOPO_LIGA)
        quali = {p["email"] for p in part if len(p["estado"].get("hist") or []) >= C.MIN_DIAS_RANKING}
        aguardando = sorted((p["apelido"] for p in part if p["email"] not in quali), key=str.lower)
        docs[codigo] = {"gerado": hoje.isoformat(), "dia": hoje.isoformat(), "nome": d["nome"], "dono": apelido_dono.get(d["dono_h"], ""),
                        "membros": len(dentro), "max": d["max"], "listas": rk["listas"], "aguardando": aguardando}
        for _, em in dentro:
            posicoes.setdefault(em, {})[codigo] = {**(rk["posicoes"].get(em) or {}), "n": rk["listas"].get("geral_n", 0), "nome": d["nome"], "cheia": False}
        for _, em in fora:
            posicoes.setdefault(em, {})[codigo] = {"n": 0, "nome": d["nome"], "cheia": True}
    return {"docs": docs, "posicoes": posicoes}


# ------------------------------------------------------------------ avisos de posição
def _aviso(dedup: str, importancia: str, titulo: str, texto: str, quando: datetime) -> dict:
    return {"dedup": dedup, "categoria": "carteira", "ativo": "", "importancia": importancia, "titulo": titulo[:200], "texto": texto[:1500],
            "origem": "competicao", "regra_id": "competicao", "grupo": "competicao", "pagina": "competicao",
            "quando": quando.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") if quando.tzinfo else quando.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dados": {"competicao": True}}


def _ordinal(n: int) -> str:
    return f"{n}º"


def avisos_de_posicao(ant: dict | None, novo: dict, dia: str, preferencias: dict | None, quando: datetime) -> list[dict]:
    """Notificações de quem mudou de posição entre o fechamento anterior (`ant`, o campo `rank` da carteira) e o de hoje (`novo`).
    Regras, para não virar spam:
     · ranking geral: só avisa a entrada no ranking, a chegada a Top 100, Top 10, Top 3 e 1º lugar, e a perda da liderança;
     · ligas: um único aviso por dia reunindo todas as ligas em que a posição mudou (subir, cair ou entrar);
     · nunca reavisa o mesmo dia (reexecução do fechamento) e respeita a preferência da pessoa por tipo."""
    ant = ant or {}
    if ant.get("em") == dia:
        return []                                                  # este fechamento já foi processado
    pref = {"liga": True, "global": True, **(preferencias or {})}
    out: list[dict] = []
    # ----- ranking geral
    pn, po, n = novo.get("geral"), ant.get("geral"), (novo.get("n") or {}).get("geral", 0)
    if pref["global"] and pn:
        if not po:
            out.append(_aviso("comp|g|entrada", "baixa", "Você entrou no ranking geral",
                              f"Você está em {_ordinal(pn)} de {n} no ranking geral da competição.", quando))
        elif pn < po:
            marcos = [t for t in LIMIARES_GERAL if po > t >= pn]
            if marcos:
                t = min(marcos)
                if t == 1:
                    out.append(_aviso(f"comp|g|sobe|1|{dia}", "alta", "Você é o 1º do ranking geral", f"Você assumiu a liderança entre {n} participantes.", quando))
                else:
                    out.append(_aviso(f"comp|g|sobe|{t}|{dia}", "media" if t <= 10 else "baixa", f"Você subiu para {_ordinal(pn)} no ranking geral",
                                      f"Você entrou no Top {t} (de {n} participantes).", quando))
        elif po == 1 and pn > 1:
            out.append(_aviso(f"comp|g|perde|{dia}", "media", f"Você caiu para {_ordinal(pn)} no ranking geral",
                              "Você deixou a liderança do ranking geral. Dá para retomá-la nos próximos pregões.", quando))
    # ----- ligas (um aviso só)
    if pref["liga"]:
        ant_l, novo_l = ant.get("ligas") or {}, novo.get("ligas") or {}
        linhas, subiu, lider = [], 0, False
        for codigo, x in sorted(novo_l.items(), key=lambda kv: kv[1].get("nome", "")):
            pos, nome, tam = x.get("geral"), x.get("nome", "liga"), x.get("n", 0)
            if not pos or tam < 2 or x.get("cheia"):
                continue
            antes = (ant_l.get(codigo) or {}).get("geral")
            if antes is None:
                linhas.append(f"{nome}: você entrou no ranking em {_ordinal(pos)} de {tam}")
            elif pos < antes:
                linhas.append(f"{nome}: subiu para {_ordinal(pos)} de {tam}")
                subiu += 1
                lider = lider or pos == 1
            elif pos > antes:
                linhas.append(f"{nome}: caiu para {_ordinal(pos)} de {tam}")
        if linhas:
            if len(linhas) == 1:
                titulo = "Mudança na sua liga: " + linhas[0].split(":", 1)[0]
            else:
                titulo = f"Mudanças em {len(linhas)} das suas ligas"
            out.append(_aviso(f"comp|ligas|{dia}", "media" if lider else "baixa", titulo, " • ".join(linhas), quando))
    return out
