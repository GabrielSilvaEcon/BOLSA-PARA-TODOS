"""Ícones dos setores da economia (arte enviada pelo dono do app, em static/setores/<id>.webp, 192 px).

`icone(setor)` aceita o nome do setor como está no catálogo de ações (recursos.CATALOGO) e devolve o endereço da imagem, ou "" se o
setor não tiver ícone próprio (a tela usa então o ícone da classe do ativo). Servido pelo próprio app, com cache do navegador.
"""
from __future__ import annotations

PASTA_URL = "app/static/setores/"
IDS = ("bancos", "petroleo", "varejo", "energia", "industria", "celular", "tecnologia", "mineracao", "saude", "telecom",
       "imobiliario", "automotivo", "aereo", "alimentos", "ouro", "agro", "logistica", "siderurgia", "construcao", "combustiveis")

# setor do catálogo → ícone
POR_SETOR = {
    "Bancos": "bancos", "Seguros e Serviços Financeiros": "bancos", "Petróleo e Gás": "petroleo", "Varejo": "varejo", "Consumo": "varejo",
    "Energia Elétrica": "energia", "Indústria e Bens de Capital": "industria", "Química": "industria", "Telecom e Tecnologia": "telecom",
    "Mineração e Siderurgia": "mineracao", "Saúde": "saude", "Construção e Imobiliário": "construcao", "Alimentos e Bebidas": "alimentos",
    "Agronegócio": "agro", "Papel e Celulose": "agro", "Transporte e Logística": "logistica",
}
# palavras para setores que não estão no catálogo (FIIs, ETFs, notícias, setores digitados)
_PALAVRAS = (("banc", "bancos"), ("segur", "bancos"), ("financ", "bancos"), ("petr", "petroleo"), ("gás", "petroleo"), ("varej", "varejo"),
             ("consum", "varejo"), ("energ", "energia"), ("elétr", "energia"), ("indústr", "industria"), ("quím", "industria"),
             ("tecnolog", "tecnologia"), ("softw", "tecnologia"), ("semicond", "tecnologia"), ("telecom", "telecom"), ("miner", "mineracao"),
             ("siderur", "siderurgia"), ("aço", "siderurgia"), ("saúde", "saude"), ("hospital", "saude"), ("farm", "saude"),
             ("imobili", "imobiliario"), ("lajes", "construcao"), ("shopping", "imobiliario"), ("construç", "construcao"), ("aliment", "alimentos"),
             ("bebida", "alimentos"), ("agro", "agro"), ("papel", "agro"), ("celulose", "agro"), ("logíst", "logistica"), ("transport", "logistica"),
             ("naveg", "logistica"), ("aére", "aereo"), ("aviação", "aereo"), ("automot", "automotivo"), ("veícul", "automotivo"),
             ("ouro", "ouro"), ("metais", "ouro"), ("combust", "combustiveis"), ("distribui", "combustiveis"))


def id_do_setor(setor: str | None) -> str | None:
    s = str(setor or "").strip()
    if not s:
        return None
    if s in POR_SETOR:
        return POR_SETOR[s]
    b = s.lower()
    return next((i for p, i in _PALAVRAS if p in b), None)


def icone(setor: str | None) -> str:
    i = id_do_setor(setor)
    return PASTA_URL + i + ".webp" if i else ""
