"""Jornada de educação financeira (estilo Duolingo) — SÓ DADOS. A lógica fica em jornada.py.

Tipos de exercício e campos:
- escolha:   pergunta, opcoes, correta (índice), explicacao
- completar: pergunta com "___", opcoes, correta (índice), explicacao
- vf:        pergunta (afirmação), correta (True/False), explicacao
- ordenar:   pergunta, itens (JÁ NA ORDEM CORRETA; a tela embaralha), explicacao
- pares:     pergunta, pares [(a, b), ...], explicacao

Ícones: cada unidade/lição usa `icone_svg` (nome em jornada_icones.py); `icone` (emoji) fica só como reserva.
Regras: números de exemplo são HIPOTÉTICOS e dizem isso; nada recomenda compra ou venda.
"""
from __future__ import annotations

TIPOS = ("escolha", "completar", "vf", "ordenar", "pares")

UNIDADES = [
    dict(id="u_inicio", titulo="Primeiros passos", icone="🌱", icone_svg="broto", cor="#2DD4A0",
         descricao="Retorno, risco, juros compostos e inflação.",
         licoes=["l_risco", "l_juros", "l_inflacao"]),
]

LICOES = [
    dict(id="l_risco", unidade="u_inicio", titulo="Retorno e risco", icone="⚖️", icone_svg="balanca", aula="fund_1", exercicios=[
        dict(tipo="escolha", pergunta="Um investimento promete ganho muito alto e \"sem risco\". O que fazer?",
             opcoes=["Aproveitar rápido, antes que acabe", "Desconfiar: retorno maior costuma vir com risco maior",
                     "Confiar se um amigo indicou", "Investir tudo de uma vez"], correta=1,
             explicacao="Retorno e risco andam juntos. Promessa de ganho alto e garantido é o sinal clássico de fraude ou de risco escondido."),
        dict(tipo="vf", pergunta="Retorno esperado maior costuma vir acompanhado de risco maior.", correta=True,
             explicacao="É a relação básica entre risco e retorno: quem aceita mais incerteza espera ser compensado."),
        dict(tipo="completar", pergunta="Risco é a chance de o resultado ser ___ do esperado.",
             opcoes=["diferente", "igual", "garantido", "menor só para os outros"], correta=0,
             explicacao="Risco é a incerteza: o resultado pode ficar acima ou abaixo do esperado."),
        dict(tipo="pares", pergunta="Ligue cada conceito ao seu significado.",
             pares=[("Retorno", "Quanto o dinheiro rendeu"),
                    ("Risco", "Chance de o resultado fugir do esperado"),
                    ("Liquidez", "Rapidez para virar dinheiro sem perda relevante")],
             explicacao="Retorno, risco e liquidez são as três perguntas básicas antes de qualquer investimento."),
        dict(tipo="vf", pergunta="Se alguém garante ganho alto, o investimento é seguro.", correta=False,
             explicacao="Garantia de ganho alto é alerta de golpe. Na dúvida, consulte as fontes oficiais, como a CVM."),
    ]),
    dict(id="l_juros", unidade="u_inicio", titulo="Juros compostos", icone="📈", icone_svg="grafico", aula="juros_1", exercicios=[
        dict(tipo="escolha", pergunta="No juro composto, os juros de cada período são calculados sobre...",
             opcoes=["só o valor inicial", "o valor inicial mais os juros já acumulados", "só os aportes novos", "nenhum valor"],
             correta=1, explicacao="É o \"juro sobre juro\": a base de cálculo cresce a cada período."),
        dict(tipo="escolha", pergunta="Exemplo hipotético: R$ 1.000 rendendo 10% ao ano, a juros compostos. Quanto após 2 anos?",
             opcoes=["R$ 1.200", "R$ 1.210", "R$ 1.100", "R$ 1.020"], correta=1,
             explicacao="1.000 × 1,10 = 1.100 no 1º ano; 1.100 × 1,10 = 1.210 no 2º. No juro simples seriam R$ 1.200."),
        dict(tipo="ordenar", pergunta="Exemplo hipotético (10% ao ano): coloque os saldos de R$ 1.000 em ordem, do início ao ano 3.",
             itens=["R$ 1.000 (início)", "R$ 1.100 (ano 1)", "R$ 1.210 (ano 2)", "R$ 1.331 (ano 3)"],
             explicacao="Cada ano multiplica o saldo anterior por 1,10, então o ganho em reais aumenta a cada ano."),
        dict(tipo="vf", pergunta="Começar a investir mais cedo tende a aumentar o efeito dos juros compostos.", correta=True,
             explicacao="Mais tempo significa mais períodos de juro sobre juro."),
        dict(tipo="completar", pergunta="No juro composto, o dinheiro cresce em reais cada vez ___ ao longo do tempo.",
             opcoes=["mais rápido", "mais devagar", "igual", "para trás"], correta=0,
             explicacao="A base de cálculo aumenta, então o valor dos juros em reais também aumenta."),
    ]),
    dict(id="l_inflacao", unidade="u_inicio", titulo="Inflação", icone="🛒", icone_svg="carrinho", aula="infl_1", exercicios=[
        dict(tipo="escolha", pergunta="O que é inflação?",
             opcoes=["Queda geral dos preços", "Aumento geral e contínuo dos preços", "Aumento do salário mínimo", "Alta do dólar"],
             correta=1, explicacao="É a perda do poder de compra da moeda: com o mesmo dinheiro, compra-se menos."),
        dict(tipo="vf", pergunta="Se o investimento rende 5% e a inflação é 6% no mesmo período, o poder de compra aumentou.",
             correta=False, explicacao="O dinheiro cresceu menos do que os preços, então o poder de compra caiu (rendimento real negativo)."),
        dict(tipo="completar", pergunta="Rendimento acima da inflação é chamado de rendimento ___.",
             opcoes=["real", "nominal", "bruto", "fixo"], correta=0,
             explicacao="O rendimento real é o que sobra depois de descontar a inflação."),
        dict(tipo="pares", pergunta="Ligue cada termo ao seu significado.",
             pares=[("Taxa nominal", "Rendimento sem descontar a inflação"),
                    ("Taxa real", "Rendimento depois de descontar a inflação"),
                    ("IPCA", "Índice oficial de inflação do Brasil (IBGE)")],
             explicacao="O IPCA, medido pelo IBGE, é a referência oficial de inflação no Brasil."),
        dict(tipo="escolha", pergunta="Dinheiro parado por anos, sem render, em um país com inflação positiva...",
             opcoes=["mantém o poder de compra", "perde poder de compra", "dobra de valor", "fica protegido pelo governo"],
             correta=1, explicacao="Sem rendimento, o valor nominal fica igual, mas os preços sobem: o poder de compra diminui."),
    ]),
]

# ---- índices (ids dos exercícios são gerados: <lição>_<n>)
for _l in LICOES:
    for _i, _e in enumerate(_l["exercicios"], 1):
        _e["id"] = f"{_l['id']}_{_i}"
        _e["licao"] = _l["id"]

LICAO_POR_ID = {l["id"]: l for l in LICOES}
UNIDADE_POR_ID = {u["id"]: u for u in UNIDADES}
EX_POR_ID = {e["id"]: e for l in LICOES for e in l["exercicios"]}
