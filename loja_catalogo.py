"""Catálogo de itens COSMÉTICOS da Loja Ticker (Fase 8). Módulo puro: sem Streamlit, sem banco, sem rede.

Como a loja é modular
- Cada item é um dicionário feito por `_item(...)`. Para vender algo novo basta acrescentar UMA linha em ITENS (ou em ITENS_SAZONAIS).
- Cada tipo de item (`kind`) é uma FAMÍLIA em FAMILIAS: diz o rótulo, o grupo da vitrine e se é "equipável" (um por vez, no seu espaço).
  Para criar um tipo novo (ex.: "trilha_som") acrescente uma linha em FAMILIAS e, se quiser uma subcategoria nova, uma em SUBGRUPOS.
- A vitrine (loja_vitrine.py) e a tela (tickercoins_app.py) leem tudo daqui: nada de lista de categorias escrita à mão nas telas.
- Compra, débito, extrato, estorno e idempotência continuam todos em tickercoins.py. Cosmético só DEBITA Ticker Coins: nunca concede XP, TC ou T$.

Raridade e preço: cada raridade tem uma FAIXA de preço (calibrada pelo teto de 40 TC/dia que o app paga por atividades).
Sazonal: `janela=("MM-DD","MM-DD")` só permite COMPRAR dentro das datas (pode atravessar o ano). Quem comprou fica com o item para sempre.
"""
from __future__ import annotations

from datetime import date

# ------------------------------------------------------------------ raridade
RARIDADES = {
    "comum": {"rotulo": "Comum", "cor": "#9FB2C8", "ordem": 1, "faixa": (30, 80)},
    "raro": {"rotulo": "Raro", "cor": "#4DA3FF", "ordem": 2, "faixa": (90, 200)},
    "epico": {"rotulo": "Épico", "cor": "#B06BFF", "ordem": 3, "faixa": (220, 400)},
    "lendario": {"rotulo": "Lendário", "cor": "#FFB938", "ordem": 4, "faixa": (450, 900)},
}

# ------------------------------------------------------------------ famílias (tipos de item)
# kind -> rótulo no singular, subgrupo da vitrine, equipável (um por vez no espaço `kind`)
FAMILIAS = {
    "tema": {"rotulo": "Tema visual", "sub": "temas", "equipavel": True},
    "moldura": {"rotulo": "Moldura", "sub": "molduras", "equipavel": True},
    "fundo": {"rotulo": "Fundo do perfil", "sub": "fundos", "equipavel": True},
    "efeito_nivel": {"rotulo": "Efeito de nível", "sub": "efeitos", "equipavel": True},
    "efeito_conquista": {"rotulo": "Efeito de conquista", "sub": "efeitos", "equipavel": True},
    "efeito_bau": {"rotulo": "Efeito de baú", "sub": "efeitos", "equipavel": True},
    "selo": {"rotulo": "Selo", "sub": "selos", "equipavel": True},
    "distintivo": {"rotulo": "Emblema", "sub": "selos", "equipavel": True},
    "bonus_limite": {"rotulo": "Benefício", "sub": "beneficios", "equipavel": False},
}
# (id, rótulo, grupo principal, texto de "em preparação" quando não há item real)
SUBGRUPOS = (
    ("temas", "Temas visuais", "temas", "Nenhum tema disponível agora."),
    ("molduras", "Molduras", "especiais", "Nenhuma moldura disponível agora."),
    ("fundos", "Fundos de perfil", "especiais", "Nenhum fundo disponível agora."),
    ("efeitos", "Efeitos", "especiais", "Efeitos de baú chegam quando o app tiver baús de recompensa: hoje não existe baú para abrir."),
    ("selos", "Selos e emblemas", "especiais", "Nenhum selo disponível agora."),
    ("beneficios", "Benefícios", "beneficios", "Nenhum benefício disponível agora."),
)
# Grupos principais mostrados como abas da loja (a terceira é a que já existia: bônus de uso diário).
GRUPOS = (("temas", "Temas visuais"), ("especiais", "Itens especiais"), ("beneficios", "Benefícios"))


def equipaveis() -> tuple:
    return tuple(k for k, f in FAMILIAS.items() if f["equipavel"])


def subgrupo_de(kind: str) -> str | None:
    f = FAMILIAS.get(kind)
    return f["sub"] if f else None


# ------------------------------------------------------------------ temas visuais
# Paleta no mesmo formato de design/temas.py (+ "brilho": duas cores de luz no fundo). Contraste conferido nos testes (WCAG).
_POS, _NEG = "#4BE3A0", "#FF7A93"


def _paleta(fundo, cartao, elevado, borda, texto, apoio, destaque, sobre, secundaria, brilho):
    return {"fundo": fundo, "cartao": cartao, "elevado": elevado, "borda": borda, "texto": texto, "apoio": apoio,
            "destaque": destaque, "sobre_destaque": sobre, "secundaria": secundaria, "positivo": _POS, "negativo": _NEG, "brilho": brilho}


PALETAS = {
    "oceano": _paleta("#071A33", "#0E2B4D", "#163D69", "#2A5C99", "#EAF4FF", "#A9C6E8", "#38B6FF", "#04121F", "#2F7DE1", ("#1B6FD1", "#38B6FF")),
    "ouro": _paleta("#0A1033", "#141D48", "#1E2B66", "#8A6D1E", "#FFF8E6", "#D3C9A6", "#F2B84B", "#1A1202", "#C9A24B", ("#F2B84B", "#3B4CCA")),
    "esmeralda": _paleta("#06140E", "#0E2619", "#163A27", "#1F6B43", "#E9FBF1", "#A6D6BA", "#2EE59D", "#04140B", "#1FA97A", ("#1FA97A", "#2EE59D")),
    "safira": _paleta("#050A38", "#0F1A66", "#18297F", "#3D63FF", "#F1F5FF", "#C0CAE6", "#D5DDEB", "#0B1230", "#3D63FF", ("#3D63FF", "#D5DDEB")),
    "aurora": _paleta("#0D0A2E", "#1B1452", "#2A2075", "#6A4BE0", "#F5F2FF", "#CDC3F7", "#7DE3FF", "#06121A", "#9B6BFF", ("#9B6BFF", "#2BD4C0")),
    "natal": _paleta("#0A1F14", "#13301F", "#1D4429", "#B3202A", "#FFF6EA", "#F0D6C6", "#FF6B74", "#2A0508", "#E2B04A", ("#C2242F", "#2E8B57")),
}


# ------------------------------------------------------------------ itens
def _item(pid, kind, nome, desc, raridade, preco, cor, efeito, *, janela=None, evento=None, validade_h=None) -> dict:
    return {"id": pid, "categoria": "personalizacao", "nome": nome, "descricao": desc, "icone": "estrela", "cor": cor, "preco": preco,
            "validade_h": validade_h, "raridade": raridade, "janela": janela, "evento": evento, "efeito": {"kind": kind, **efeito}}


ITENS = [
    # --- temas visuais
    _item("tema_oceano", "tema", "Tema Oceano", "Azul-marinho e azul: o app inteiro no clima do mar.", "raro", 120, "#38B6FF", {"paleta": "oceano"}),
    _item("tema_esmeralda", "tema", "Tema Esmeralda", "Verde sobre tons escuros, calmo e elegante.", "raro", 150, "#2EE59D", {"paleta": "esmeralda"}),
    _item("tema_safira", "tema", "Tema Safira", "Azul intenso com detalhes em prata.", "raro", 180, "#3D63FF", {"paleta": "safira"}),
    _item("tema_ouro", "tema", "Tema Ouro", "Dourado sobre azul-marinho, o visual de quem chegou longe.", "epico", 300, "#F2B84B", {"paleta": "ouro"}),
    _item("tema_aurora", "tema", "Tema Aurora", "Roxo e azul com luzes suaves no fundo.", "lendario", 600, "#9B6BFF", {"paleta": "aurora", "luz": True}),
    # --- molduras (aro em volta do Caramelo no perfil)
    _item("mold_bronze", "moldura", "Moldura Bronze", "Aro bronze no seu perfil.", "comum", 40, "#CD7F32", {"cor": "#CD7F32", "estilo": "solido"}),
    _item("mold_prata", "moldura", "Moldura Prata", "Aro prateado no seu perfil.", "raro", 100, "#C7D0E0", {"cor": "#C7D0E0", "estilo": "solido"}),
    _item("mold_platina", "moldura", "Moldura Platina", "Aro platina com brilho suave.", "epico", 260, "#9FE7F5", {"cor": "#9FE7F5", "estilo": "brilho"}),
    _item("mold_diamante", "moldura", "Moldura Diamante", "Aro cristalino com brilho azul.", "epico", 360, "#6FB6FF", {"cor": "#6FB6FF", "estilo": "brilho"}),
    _item("mold_lend_aurora", "moldura", "Moldura Lendária Aurora", "Aro que muda de cor devagar.", "lendario", 650, "#9B6BFF",
          {"cor": "#9B6BFF", "estilo": "gira", "cores": ["#9B6BFF", "#2BD4C0", "#38B6FF"]}),
    _item("mold_lend_solar", "moldura", "Moldura Lendária Solar", "Aro dourado com brilho que pulsa de leve.", "lendario", 750, "#FFB938",
          {"cor": "#FFB938", "estilo": "pulsa"}),
    # --- fundos do cartão de perfil
    _item("fundo_noite", "fundo", "Fundo Noite Azul", "Degradê azul-noite no seu cartão de perfil.", "comum", 50, "#2F7DE1",
          {"de": "#17306B", "para": "#0B1233"}),
    _item("fundo_floresta", "fundo", "Fundo Floresta", "Degradê verde-escuro no seu cartão de perfil.", "raro", 110, "#2EE59D",
          {"de": "#14573A", "para": "#071A12"}),
    _item("fundo_aurora", "fundo", "Fundo Aurora", "Degradê roxo e azul com luz no canto.", "epico", 280, "#9B6BFF",
          {"de": "#4B34A8", "para": "#101A52", "luz": "#2BD4C0"}),
    # --- efeitos de celebração (cores e formato do confete)
    _item("fx_nivel_estrelas", "efeito_nivel", "Subida de nível: Chuva de estrelas", "Estrelas douradas ao subir de nível.", "raro", 140, "#FFD66B",
          {"formas": "estrela", "cores": ["#FFD66B", "#FFF1B8", "#F2B84B"]}),
    _item("fx_nivel_neon", "efeito_nivel", "Subida de nível: Neon", "Faíscas neon ao subir de nível.", "epico", 300, "#7DE3FF",
          {"formas": "bolha", "cores": ["#7DE3FF", "#B06BFF", "#2BD4C0"]}),
    _item("fx_conquista_fogos", "efeito_conquista", "Conquista: Fogos", "Cores de fogos de artifício nas suas conquistas.", "raro", 150, "#FF6B8A",
          {"formas": "bolha", "cores": ["#FF6B8A", "#FFD66B", "#7DE3FF", "#3DDC97"]}),
    _item("fx_conquista_ouro", "efeito_conquista", "Conquista: Chuva de ouro", "Chuva dourada nas suas conquistas.", "epico", 320, "#F2B84B",
          {"formas": "estrela", "cores": ["#F2B84B", "#FFD66B", "#FFF1B8"]}),
    # --- selos decorativos (aparecem ao lado do nome no perfil)
    _item("selo_cometa", "selo", "Selo Cometa", "Um cometa ao lado do seu nome.", "raro", 130, "#7DE3FF", {"emoji": "☄️"}),
    _item("selo_coroa", "selo", "Selo Coroa", "Uma coroa ao lado do seu nome.", "epico", 340, "#FFB938", {"emoji": "👑"}),
]

# Itens de data comemorativa: só COMPRÁVEIS na janela; depois de comprados ficam para sempre.
ITENS_SAZONAIS = [
    _item("tema_natal", "tema", "Tema Natal", "Verde e vermelho de Natal, só na temporada.", "epico", 320, "#FF6B74", {"paleta": "natal"},
          janela=("12-01", "01-06"), evento="Natal"),
    _item("mold_natal", "moldura", "Moldura de Natal", "Aro festivo vermelho e verde.", "raro", 140, "#FF6B74",
          {"cor": "#FF6B74", "estilo": "gira", "cores": ["#FF6B74", "#2E8B57", "#E2B04A"]}, janela=("12-01", "01-06"), evento="Natal"),
    _item("fundo_natal", "fundo", "Fundo de Natal", "Degradê verde e vermelho no cartão de perfil.", "raro", 120, "#2E8B57",
          {"de": "#1B5E3A", "para": "#3D0B12", "luz": "#E2B04A"}, janela=("12-01", "01-06"), evento="Natal"),
]

TODOS = ITENS + ITENS_SAZONAIS
POR_ID = {i["id"]: i for i in TODOS}


# ------------------------------------------------------------------ regras puras
def _md(d: date) -> str:
    return f"{d.month:02d}-{d.day:02d}"


def na_janela(item: dict, hoje: date) -> bool:
    """True se o item pode ser COMPRADO hoje. Sem janela, sempre. A janela pode atravessar o ano (12-01 a 01-06)."""
    j = item.get("janela")
    if not j:
        return True
    a, b, h = j[0], j[1], _md(hoje)
    return (a <= h <= b) if a <= b else (h >= a or h <= b)


def texto_janela(item: dict) -> str:
    j = item.get("janela")
    if not j:
        return ""
    f = lambda s: f"{s[3:]}/{s[:2]}"
    return f"{item.get('evento') or 'Temporada'}: {f(j[0])} a {f(j[1])}"


def paleta_do_item(item: dict | None) -> dict | None:
    if not item or (item.get("efeito") or {}).get("kind") != "tema":
        return None
    return PALETAS.get(item["efeito"].get("paleta"))


def validar() -> list[str]:
    """Problemas do catálogo (lista vazia = ok). Usada nos testes para que um item novo mal feito não passe despercebido."""
    erros, vistos = [], set()
    for i in TODOS:
        pid, ef = i["id"], i["efeito"]
        if pid in vistos:
            erros.append(f"{pid}: id repetido")
        vistos.add(pid)
        if ef["kind"] not in FAMILIAS:
            erros.append(f"{pid}: tipo desconhecido {ef['kind']}")
        r = RARIDADES.get(i["raridade"])
        if not r:
            erros.append(f"{pid}: raridade inválida")
        elif not (r["faixa"][0] <= i["preco"] <= r["faixa"][1]):
            erros.append(f"{pid}: preço {i['preco']} fora da faixa de {i['raridade']}")
        if ef["kind"] == "tema" and ef.get("paleta") not in PALETAS:
            erros.append(f"{pid}: paleta inexistente")
    return erros
