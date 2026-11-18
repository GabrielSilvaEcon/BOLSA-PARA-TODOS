"""Coleção de avatares do TickerHunters: catálogo oficial, raridades, desbloqueio e moldura. Lógica pura (sem Streamlit e sem banco).

 · Catálogo: um personagem por desenho (as repetições das cartelas foram descartadas). As imagens ficam em static/avatares/<id>.webp
   (256 px) e <id>_p.webp (96 px, para listas), servidas pelo próprio app com cache do navegador. As 6 raposas que já existiam continuam
   valendo (Coleção Raposa, comuns e iniciais): quem já as usa não perde nada.
 · Raridade: definida AQUI, nos metadados (a cor da moldura das cartelas originais não conta). A moldura é desenhada pela interface (CSS),
   nunca gravada na imagem.
 · Desbloqueio: cada avatar tem uma regra (tipo + valor). Tipos prontos: inicial, nivel, conquista, loja, evento, temporada.
   Hoje a coleção usa inicial e nivel (escolha do dono do app); loja/evento/temporada ficam prontos para configurar depois, sem preço inventado:
   enquanto "disponivel" for False o avatar aparece bloqueado com "Em breve".
 · Quem pode equipar: só o que está liberado para a conta (o serviço confere no servidor antes de gravar).
"""
from __future__ import annotations

import html as _h

RARIDADES = {   # ordem, nome, cor da borda, segunda cor (brilho)
    "comum": {"ordem": 1, "nome": "Comum", "plural": "Comuns", "cor": "#C9CEDB", "cor2": "#8A90A6", "dica": "Mais fácil de obter"},
    "raro": {"ordem": 2, "nome": "Raro", "plural": "Raros", "cor": "#3FA4FF", "cor2": "#1F5FD6", "dica": "Desbloqueio intermediário"},
    "epico": {"ordem": 3, "nome": "Épico", "plural": "Épicos", "cor": "#B66BFF", "cor2": "#7A2FE0", "dica": "Conquistas especiais"},
    "lendario": {"ordem": 4, "nome": "Lendário", "plural": "Lendários", "cor": "#FFC93C", "cor2": "#E08A12", "dica": "Personagens exclusivos"},
    "mitico": {"ordem": 5, "nome": "Mítico", "plural": "Míticos", "cor": "#FF4D5E", "cor2": "#B3122A", "dica": "Extremamente exclusivos"},
}
TIPOS = ("inicial", "nivel", "conquista", "loja", "evento", "temporada")
PASTA_URL = "app/static/avatares/"      # Streamlit serve ./static em app/static (enableStaticServing)
CRIADO_EM = "2026-11-18"
PADRAO = "raposa"

# Coleção nova (id, nome, raridade, nível para liberar). Nível 1 = inicial (grátis para todos).
_NOVOS = (
    ("raposa_trader", "Raposa Trader", "comum", 1),
    ("golden", "Golden Lucro", "comum", 1),
    ("coruja", "Coruja Analista", "comum", 1),
    ("pinguim", "Pinguim Executivo", "comum", 1),
    ("panda", "Panda Holder", "comum", 1),
    ("urso_bone", "Urso de Boné", "comum", 1),
    ("corgi", "Corgi Animado", "comum", 1),
    ("coala", "Coala Zen", "comum", 1),
    ("pato", "Pato do Dividendo", "comum", 1),
    ("lhama", "Lhama Estilosa", "comum", 1),
    ("guaxinim", "Guaxinim Esperto", "comum", 1),
    ("ourico", "Ouriço Investidor", "comum", 1),
    ("hipopotamo", "Hipopótamo Chefe", "comum", 1),
    ("husky", "Husky Feliz", "comum", 1),
    ("gato", "Gato Descolado", "comum", 1),
    ("urso", "Urso Bear Market", "raro", 3),
    ("touro_executivo", "Touro Executivo", "raro", 3),
    ("tubarao", "Tubarão do Mercado", "raro", 4),
    ("girafa", "Girafa Visionária", "raro", 4),
    ("panda_dj", "Panda DJ", "raro", 5),
    ("pinguim_inverno", "Pinguim de Inverno", "raro", 5),
    ("crocodilo", "Crocodilo Corretor", "raro", 6),
    ("rinoceronte", "Rinoceronte Blindado", "raro", 6),
    ("panda_bambu", "Panda do Bambu", "raro", 6),
    ("tucano", "Tucano Tropical", "raro", 7),
    ("panda_vermelho", "Panda-Vermelho", "raro", 7),
    ("panda_analista", "Panda Analista", "raro", 7),
    ("raposa_estilo", "Raposa Estilosa", "raro", 8),
    ("feneco", "Feneco do Deserto", "raro", 8),
    ("lobo", "Lobo de Wall Street", "epico", 10),
    ("leopardo", "Leopardo Ostentação", "epico", 10),
    ("gorila", "Gorila Holder", "epico", 10),
    ("flamingo", "Flamingo Tropical", "epico", 11),
    ("gata_executiva", "Gata Executiva", "epico", 11),
    ("aguia", "Águia Executiva", "epico", 11),
    ("gorila_dj", "Gorila DJ", "epico", 12),
    ("gato_dj", "Gato DJ", "epico", 12),
    ("touro_investidor", "Touro Investidor", "epico", 12),
    ("pinguim_pixel", "Pinguim Pixel", "epico", 13),
    ("lagarto", "Lagarto Punk", "epico", 13),
    ("gorila_terno", "Gorila de Terno", "epico", 13),
    ("trex", "T-Rex Sniper", "epico", 14),
    ("rinoceronte_sombrio", "Rinoceronte Sombrio", "epico", 14),
    ("flamingo_terno", "Flamingo de Terno", "epico", 14),
    ("cobra", "Cobra Detetive", "epico", 15),
    ("leopardo_selvagem", "Leopardo Selvagem", "epico", 15),
    ("raposa_mistica", "Raposa Mística", "epico", 15),
    ("leao", "Leão Rei", "lendario", 20),
    ("unicornio", "Unicórnio", "lendario", 20),
    ("touro_verde", "Touro Verde", "lendario", 21),
    ("pantera", "Pantera Negra", "lendario", 22),
    ("robo", "Robô Quant", "lendario", 23),
    ("lobo_eletrico", "Lobo Elétrico", "lendario", 24),
    ("pinguim_bitcoin", "Pinguim Bitcoin", "lendario", 25),
    ("aguia_rei", "Águia Rei", "mitico", 30),
    ("touro_cyber", "Touro Cyber", "mitico", 32),
    ("dragao", "Dragão de Fogo", "mitico", 35),
    ("touro_sombrio", "Touro Sombrio", "mitico", 40),
)

# Coleção Raposa (artes que o app já tinha, embutidas nos módulos de arte): continuam valendo para quem já usa.
_RAPOSAS = (
    ("raposa", "Raposa Hunter", "arte_conta", "avatar"),
    ("raposa_confiante", "Raposa Confiante", "arte_cartela", "raposa_confiante"),
    ("raposa_animada", "Raposa Animada", "arte_cartela", "raposa_animada"),
    ("raposa_vitoriosa", "Raposa Vitoriosa", "arte_cartela", "raposa_vitoriosa"),
    ("raposa_pensativa", "Raposa Pensativa", "arte_cartela", "raposa_pensativa"),
    ("raposa_surpresa", "Raposa Surpresa", "arte_cartela", "raposa_surpresa"),
)


def _item(i, nome, rar, desb, arquivo=None, arte=None):
    return {"id": i, "nome": nome, "raridade": rar, "desbloqueio": desb, "arquivo": arquivo, "arte": arte, "disponivel": True,
            "criado_em": CRIADO_EM}


CATALOGO = ([_item(i, n, "comum", {"tipo": "inicial"}, arte=(m, k)) for i, n, m, k in _RAPOSAS]
            + [_item(i, n, r, {"tipo": "inicial"} if lv <= 1 else {"tipo": "nivel", "valor": lv}, arquivo=f"{i}.webp") for i, n, r, lv in _NOVOS])
POR_ID = {a["id"]: a for a in CATALOGO}


def existe(avatar_id) -> bool:
    return avatar_id in POR_ID


def raridade_de(avatar_id) -> str:
    return (POR_ID.get(avatar_id) or {}).get("raridade", "comum")


def url(avatar_id: str, pequeno: bool = False) -> str:
    """Endereço da imagem (estática, com cache do navegador) ou data URI das raposas antigas. Avatar inexistente → padrão."""
    a = POR_ID.get(avatar_id) or POR_ID[PADRAO]
    if a["arte"]:
        try:
            import importlib
            m, k = a["arte"]
            return importlib.import_module(m).uri(k)
        except Exception:
            return ""
    return PASTA_URL + (a["arquivo"].replace(".webp", "_p.webp") if pequeno else a["arquivo"])


# ------------------------------------------------------------------ desbloqueio
def _cumpre(a: dict, ctx: dict) -> bool:
    d = a["desbloqueio"]
    t = d.get("tipo")
    if not a.get("disponivel", True):
        return False
    if t == "inicial":
        return True
    if t == "nivel":
        return int(ctx.get("nivel") or 1) >= int(d.get("valor") or 1)
    if t == "conquista":
        return d.get("valor") in set(ctx.get("emblemas") or ())
    return a["id"] in set(ctx.get("concedidos") or ())       # loja, evento, temporada: só quando o sistema concedeu


def liberados(ctx: dict, guardados=()) -> set[str]:
    """Ids liberados para a conta: os que ela já tinha guardado na coleção + os que cumpre agora (nível real, conquistas, concessões)."""
    return {a["id"] for a in CATALOGO if _cumpre(a, ctx)} | {i for i in guardados if i in POR_ID}


def pode_equipar(avatar_id: str, lib: set[str]) -> bool:
    return avatar_id in POR_ID and avatar_id in lib


def como_liberar(a: dict) -> str:
    d = a["desbloqueio"]
    t = d.get("tipo")
    if not a.get("disponivel", True) or t in ("loja", "evento", "temporada") and not d.get("valor"):
        return {"loja": "Em breve na Loja Ticker", "evento": "Em breve em um evento", "temporada": "Em breve em uma temporada"}.get(t, "Em breve")
    return {"inicial": "Liberado para todos", "nivel": f"Chegue ao nível {d.get('valor')}", "conquista": "Ganhe a conquista " + str(d.get("nome") or d.get("valor")),
            "loja": "Disponível na Loja Ticker", "evento": f"Evento {d.get('valor')}", "temporada": f"Temporada {d.get('valor')}"}.get(t, "")


# ------------------------------------------------------------------ coleção da conta (o que fica guardado)
def sanear_colecao(doc) -> dict:
    d = doc if isinstance(doc, dict) else {}
    ids = [str(x) for x in (d.get("ids") or []) if str(x) in POR_ID]
    em = {k: str(v)[:10] for k, v in (d.get("em") or {}).items() if k in ids} if isinstance(d.get("em"), dict) else {}
    conc = [str(x) for x in (d.get("concedidos") or []) if str(x) in POR_ID]
    return {"v": 1, "ids": sorted(set(ids)), "em": em, "concedidos": sorted(set(conc))}


def sincronizar(doc, ctx: dict, hoje: str) -> tuple[dict, list[str]]:
    """Guarda na coleção tudo o que a conta liberou (para valer mesmo se a regra mudar depois). Devolve (doc, ids novos)."""
    d = sanear_colecao(doc)
    lib = liberados({**ctx, "concedidos": d["concedidos"]}, d["ids"])
    novos = sorted(lib - set(d["ids"]))
    if novos:
        d["ids"] = sorted(set(d["ids"]) | set(novos))
        d["em"].update({i: hoje for i in novos})
    return d, novos


def conceder(doc, avatar_id: str, hoje: str) -> dict:
    """Concessão do sistema (loja, evento, temporada). Só aceita ids do catálogo."""
    if avatar_id not in POR_ID:
        raise ValueError("avatar desconhecido")
    d = sanear_colecao(doc)
    d["concedidos"] = sorted(set(d["concedidos"]) | {avatar_id})
    if avatar_id not in d["ids"]:
        d["ids"] = sorted(set(d["ids"]) | {avatar_id})
        d["em"][avatar_id] = hoje
    return d


def colecao(lib: set[str], equipado: str | None = None, filtro: str | None = None) -> list[dict]:
    """Itens da grade (ordem: raridade, nível, nome), com liberado/bloqueado, equipado e como liberar."""
    out = []
    for a in CATALOGO:
        if filtro and a["raridade"] != filtro:
            continue
        out.append({**a, "liberado": a["id"] in lib, "equipado": a["id"] == equipado, "como": como_liberar(a),
                    "rar": RARIDADES[a["raridade"]]})
    return sorted(out, key=lambda x: (x["rar"]["ordem"], int(x["desbloqueio"].get("valor") or 1) if x["desbloqueio"].get("tipo") == "nivel" else 0, x["nome"]))


def totais(lib: set[str]) -> dict:
    out = {r: {"total": 0, "ok": 0} for r in RARIDADES}
    for a in CATALOGO:
        out[a["raridade"]]["total"] += 1
        out[a["raridade"]]["ok"] += int(a["id"] in lib)
    return out


# ------------------------------------------------------------------ moldura (aplicada pela interface)
def html(avatar_id: str | None, tamanho: int = 48, foto: str = "", pequeno: bool | None = None, extra: str = "") -> str:
    """<span> com a imagem e a moldura da raridade. A foto (data URI da foto enviada) substitui a arte e usa moldura neutra.
    O tamanho vale para qualquer lugar (lista, ranking, perfil). Precisa do CSS de css() na página (vai no CSS global do app)."""
    pq = tamanho <= 72 if pequeno is None else pequeno
    if foto:
        src, rar = foto, "foto"
    else:
        aid = avatar_id if avatar_id in POR_ID else PADRAO
        src, rar = url(aid, pq), raridade_de(aid)
    return (f"<span class='thav r-{rar}{(' ' + extra) if extra else ''}' style='--s:{int(tamanho)}px'>"
            f"<img src='{_h.escape(src, quote=True)}' alt='' loading='lazy' decoding='async'></span>")


def chip(raridade: str) -> str:
    r = RARIDADES.get(raridade)
    return f"<span class='thrar r-{raridade}'>{r['nome']}</span>" if r else ""


def css(prefixo: str = "html body .stApp.stApp.stApp") -> str:
    p = prefixo
    regras = [
        f"{p} .thav{{--s:48px;--rc:#C9CEDB;--rc2:#8A90A6;--g:0;position:relative;display:inline-block;flex:0 0 auto;width:var(--s);height:var(--s);"
        "border-radius:50%;padding:calc(var(--s) * .055);background:conic-gradient(from 210deg,var(--rc),var(--rc2),var(--rc),var(--rc2),var(--rc));"
        "box-shadow:0 0 calc(var(--s) * .12 * var(--g)) color-mix(in srgb,var(--rc) 70%,transparent);vertical-align:middle}",
        f"{p} .thav img{{display:block;width:100%;height:100%;border-radius:50%;object-fit:cover;background:#1B1545;"
        "box-shadow:inset 0 0 0 1px rgba(0,0,0,.35)}",
        f"{p} .thav.r-comum{{--rc:#D5DAE6;--rc2:#7E849A;--g:.35}}",
        f"{p} .thav.r-raro{{--rc:#4FB0FF;--rc2:#1F5FD6;--g:.8}}",
        f"{p} .thav.r-epico{{--rc:#C07BFF;--rc2:#6E22D8;--g:1.15}}",
        f"{p} .thav.r-lendario{{--rc:#FFD45E;--rc2:#D9800F;--g:1.5}}",
        f"{p} .thav.r-mitico{{--rc:#FF5A6B;--rc2:#9E0F27;--g:1.9}}",
        f"{p} .thav.r-foto{{--rc:#34E85E;--rc2:#14C9B5;--g:.6}}",
        f"{p} .thav.r-lendario::after,{p} .thav.r-mitico::after{{content:'';position:absolute;inset:-2px;border-radius:50%;pointer-events:none;"
        "background:conic-gradient(from 0deg,transparent 0 70%,rgba(255,255,255,.55) 78%,transparent 86%);"
        "-webkit-mask:radial-gradient(farthest-side,transparent calc(100% - calc(var(--s) * .07)),#000 0);"
        "mask:radial-gradient(farthest-side,transparent calc(100% - calc(var(--s) * .07)),#000 0)}",
        "@media (prefers-reduced-motion:no-preference){" + f"{p} .thav.r-lendario::after{{animation:thgira 6s linear infinite}}"
        f"{p} .thav.r-mitico::after{{animation:thgira 3.5s linear infinite}}{p} .thav.r-mitico{{animation:thpulsa 2.4s ease-in-out infinite}}" + "}",
        "@keyframes thgira{to{transform:rotate(360deg)}}",
        "@keyframes thpulsa{50%{box-shadow:0 0 calc(var(--s) * .3) color-mix(in srgb,var(--rc) 80%,transparent)}}",
        f"{p} .thrar{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.66rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;"
        "border:1px solid currentColor;line-height:1.5}",
    ] + [f"{p} .thrar.r-{k}{{color:{v['cor']} !important;-webkit-text-fill-color:{v['cor']} !important;background:color-mix(in srgb,{v['cor']} 14%,transparent)}}"
         for k, v in RARIDADES.items()]
    return "<style>" + "".join(regras) + "</style>"
