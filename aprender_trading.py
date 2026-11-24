"""Aprender · área TRADING (fase 3) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Quatro trilhas: a bolsa por dentro, leitura do gráfico, Wyckoff e gestão/psicologia. O foco é entender e controlar risco, não
prometer ganho: análise técnica trabalha com probabilidades, e operar com frequência é arriscado. Números são HIPOTÉTICOS.
Nada aqui recomenda comprar ou vender um ativo. A prática fica no Trade Battle (dinheiro virtual).
"""
from __future__ import annotations

AREA = "trading"

UNIDADES = [
    dict(id="ut_bolsa", area=AREA, titulo="A bolsa por dentro", icone="🏛️", icone_svg="predio", cor="#4DA3FF",
         descricao="Como a bolsa funciona, tipos de ordem, book de ofertas e candles.",
         licoes=["lt_bolsa", "lt_ordens", "lt_candles"]),
    dict(id="ut_grafico", area=AREA, titulo="Leitura do gráfico", icone="📉", icone_svg="grafico", cor="#2DD4A0",
         descricao="Tendência, suporte e resistência, volume e price action.",
         licoes=["lt_tendencia", "lt_suporte", "lt_volume", "lt_price_action"]),
    dict(id="ut_wyckoff", area=AREA, titulo="Método Wyckoff", icone="🔁", icone_svg="alvo", cor="#B07CFF",
         descricao="As fases do mercado e os sinais de acumulação e distribuição.",
         licoes=["lt_wyckoff_fases", "lt_wyckoff_acumulacao"]),
    dict(id="ut_gestao", area=AREA, titulo="Gestão e psicologia", icone="🧠", icone_svg="escudo", cor="#FF5A7A",
         descricao="Stop e alvo, risco-retorno, tamanho da posição, emoções e plano.",
         licoes=["lt_stop", "lt_risco_retorno", "lt_psicologia", "lt_plano"]),
]

NIVEIS = {"lt_price_action": "intermediario", "lt_wyckoff_fases": "avancado", "lt_wyckoff_acumulacao": "avancado",
          "lt_risco_retorno": "intermediario", "lt_volume": "intermediario", "lt_plano": "intermediario"}

_A = dict(assunto="tecnica", dificuldade="iniciante", fontes=["b3", "cvm"], relacionadas=[])
AULAS = [
    dict(_A, id="at_bolsa", titulo="Como a bolsa funciona", min=4,
         iniciante="A bolsa (no Brasil, a **B3**) é o lugar onde compradores e vendedores negociam ações e outros ativos. Você não negocia direto na bolsa: "
                   "usa uma **corretora**, que envia as suas ordens.\n\n"
                   "**O preço** nasce do encontro entre quem quer comprar e quem quer vender. Se há mais gente querendo comprar, o preço tende a subir; se há "
                   "mais gente querendo vender, tende a cair.\n\n"
                   "**Exemplo do dia a dia:** é como uma feira: se o tomate acaba cedo, quem chega depois paga mais caro.\n\n"
                   "**Na prática:** o horário de negociação, as taxas e as regras ficam no site da B3 e na sua corretora. Confira antes de operar.",
         intermediario="Cada negócio tem uma ponta compradora e uma vendedora: para alguém comprar, alguém precisa vender. Ativos com pouca **liquidez** "
                       "(poucos negócios) têm diferenças maiores entre o preço de compra e o de venda, e isso encarece entrar e sair."),
    dict(_A, id="at_ordens", titulo="Tipos de ordem e book de ofertas", min=5,
         iniciante="**Ordem a mercado:** compra ou vende pelo melhor preço disponível agora. É rápida, mas o preço pode ser pior do que você esperava.\n\n"
                   "**Ordem limitada:** você define o preço máximo para comprar (ou mínimo para vender). Só executa se o mercado chegar nele.\n\n"
                   "**Ordem stop:** fica \"armada\" e só é enviada quando o preço atinge um valor. É muito usada para limitar perdas.\n\n"
                   "**Book de ofertas:** a lista das ordens de compra e de venda que estão esperando. A diferença entre a melhor compra e a melhor venda é o **spread**.\n\n"
                   "**Na prática:** em ativos com pouca liquidez, prefira ordens limitadas.",
         intermediario="O book mostra intenções, não garantias: ordens podem ser canceladas a qualquer momento. Uma ordem stop vira ordem a mercado (ou "
                       "limitada, conforme o tipo) quando é disparada; em movimentos bruscos, a execução pode sair longe do preço do stop (o chamado **slippage**)."),
    dict(_A, id="at_candles", titulo="Candlesticks", min=5,
         iniciante="O **candle** (vela) resume o que o preço fez num período, como um dia ou 15 minutos. Ele mostra quatro preços: **abertura**, "
                   "**fechamento**, **máxima** e **mínima**.\n\n"
                   "**Corpo:** vai da abertura ao fechamento. Candle de **alta** (normalmente verde) fecha acima da abertura; de **baixa** (normalmente vermelho), "
                   "abaixo.\n\n"
                   "**Sombras (pavios):** as linhas finas acima e abaixo do corpo mostram até onde o preço foi na máxima e na mínima.\n\n"
                   "**Na prática:** um único candle diz pouco. O que importa é o conjunto e o contexto.",
         intermediario="Sombra longa mostra rejeição: uma sombra inferior grande indica que o preço caiu, mas compradores o trouxeram de volta. O mesmo "
                       "candle pode significar coisas diferentes no topo, no fundo ou no meio de um movimento."),
    dict(_A, id="at_tendencia", titulo="Tendências", min=4,
         iniciante="**Tendência de alta:** topos e fundos cada vez **mais altos**. **Tendência de baixa:** topos e fundos cada vez **mais baixos**. "
                   "**Lateral:** o preço anda de lado, sem direção clara.\n\n"
                   "**Exemplo:** se o preço faz fundo em 10, sobe a 14, corrige a 12 e sobe a 16, os fundos (10, 12) e os topos (14, 16) estão subindo: tendência de alta.\n\n"
                   "**Médias móveis** ajudam a ver a direção, suavizando o sobe e desce.\n\n"
                   "**Na prática:** \"a tendência é sua amiga\", mas ela acaba um dia. Por isso existe o stop.",
         intermediario="A tendência depende do **tempo gráfico**: um ativo pode estar em alta no diário e em baixa no gráfico de 15 minutos. Defina o "
                       "tempo gráfico da sua operação e olhe um maior para o contexto."),
    dict(_A, id="at_suporte", titulo="Suporte e resistência", min=4,
         iniciante="**Suporte** é uma região onde o preço costuma parar de cair, porque aparecem compradores. **Resistência** é uma região onde o preço "
                   "costuma parar de subir, porque aparecem vendedores.\n\n"
                   "**Exemplo:** se o preço bateu em R$ 20 três vezes e voltou a subir, R$ 20 virou um suporte.\n\n"
                   "**Rompimento:** quando o preço passa da região com força. Um suporte rompido pode virar resistência, e vice-versa.\n\n"
                   "**Na prática:** pense em **regiões**, não em preços exatos.",
         intermediario="Quanto mais vezes uma região é testada e respeitada, mais relevante ela fica, mas cada teste também consome as ordens que estavam ali. "
                       "Rompimentos falsos são comuns: muitos operadores esperam o fechamento do candle ou um reteste antes de agir."),
    dict(_A, id="at_volume", titulo="Volume", min=4,
         iniciante="**Volume** é a quantidade negociada num período. Ele mostra a **força** por trás de um movimento.\n\n"
                   "**Exemplo:** uma alta com volume alto tem muita participação; uma alta com volume baixíssimo pode ser fraca.\n\n"
                   "**Na prática:** olhe o volume junto com o preço, principalmente em rompimentos de suporte ou resistência.",
         intermediario="Volume crescente na direção da tendência costuma confirmá-la; volume que diminui enquanto o preço avança pode indicar perda de força. "
                       "Picos de volume em quedas fortes às vezes marcam momentos de pânico (capitulação)."),
    dict(_A, id="at_price_action", titulo="Price action", min=5,
         iniciante="**Price action** é ler o que o próprio preço está fazendo, com poucos ou nenhum indicador: candles, topos e fundos, suportes e resistências.\n\n"
                   "**Padrões comuns:** **martelo** (sombra inferior longa num fundo, sinal de rejeição da queda), **engolfo** (um candle que \"engole\" o corpo do "
                   "anterior) e **pullback** (a volta do preço a uma região rompida antes de seguir).\n\n"
                   "**Na prática:** padrão sem contexto é só um desenho. O mesmo padrão vale mais perto de um suporte ou resistência importante.",
         intermediario="Price action é sobre probabilidade, não certeza. Defina com antecedência o que invalida a sua leitura (onde fica o stop) e teste as "
                       "suas regras em dados passados ou no Trade Battle antes de usar dinheiro real."),
    dict(_A, id="at_wyckoff_fases", titulo="Wyckoff: as fases do mercado", min=5,
         iniciante="Richard Wyckoff estudou o mercado no início do século 20. Para ele, o preço alterna entre quatro fases:\n\n"
                   "**Acumulação:** o preço anda de lado depois de uma queda, enquanto grandes participantes compram aos poucos.\n"
                   "**Alta (markup):** o preço sobe.\n"
                   "**Distribuição:** o preço anda de lado depois de uma alta, enquanto grandes participantes vendem aos poucos.\n"
                   "**Baixa (markdown):** o preço cai.\n\n"
                   "**Na prática:** Wyckoff ajuda a pensar em \"quem está comprando e quem está vendendo\", olhando preço e volume juntos.",
         intermediario="As três leis de Wyckoff: **oferta e demanda** (o preço se move pelo desequilíbrio), **causa e efeito** (uma lateralização longa é a "
                       "\"causa\" de um movimento maior) e **esforço × resultado** (o volume, que é o esforço, deve combinar com o movimento do preço, o resultado)."),
    dict(_A, id="at_wyckoff_acumulacao", titulo="Wyckoff: acumulação e distribuição", min=5,
         iniciante="Na **acumulação**, alguns eventos costumam aparecer: uma queda forte com volume alto (**selling climax**), uma reação de alta, testes do "
                   "fundo e, às vezes, uma falsa quebra para baixo que volta rápido (**spring**). Depois, o preço rompe a lateralização para cima.\n\n"
                   "Na **distribuição**, acontece o espelho: um topo com volume alto (**buying climax**), testes do topo, uma falsa quebra para cima "
                   "(**upthrust**) e o rompimento para baixo.\n\n"
                   "**Na prática:** esses nomes são um mapa, não uma regra. Nem toda lateralização é acumulação ou distribuição.",
         intermediario="O **spring** e o **upthrust** são armadilhas para quem opera rompimentos: o preço passa do limite, pega os stops e volta. Observe se o "
                       "volume confirma: rompimento com pouco volume e retorno rápido costuma ser falso."),
    dict(_A, id="at_stop", titulo="Stop loss e take profit", min=4,
         iniciante="**Stop loss** é o preço em que você aceita sair com perda, para que uma perda pequena não vire grande. **Take profit** (alvo) é o preço em que "
                   "você realiza o lucro.\n\n"
                   "**Exemplo (hipotético):** compra a R$ 20, stop a R$ 19 e alvo a R$ 22. Se der errado, perde R$ 1 por ação; se der certo, ganha R$ 2.\n\n"
                   "**Na prática:** defina o stop **antes** de entrar, num ponto em que a sua ideia deixa de fazer sentido (como abaixo de um suporte), e "
                   "não mude o stop para longe quando o preço chega perto.",
         intermediario="Stop muito apertado é acionado pelo sobe e desce normal; muito largo deixa a perda grande. Uma referência é usar a volatilidade do ativo "
                       "e a estrutura do gráfico. O **stop móvel** acompanha o preço a favor e protege parte do lucro."),
    dict(_A, id="at_risco_retorno", titulo="Risco-retorno e tamanho da posição", min=5,
         iniciante="**Relação risco-retorno:** quanto você pode ganhar comparado a quanto pode perder. Arriscar R$ 1 para ganhar R$ 2 é uma relação de **1:2**.\n\n"
                   "**Tamanho da posição:** decida primeiro **quanto aceita perder** na operação e calcule quantas ações comprar.\n\n"
                   "**Conta (hipotética):** capital de R$ 10.000 e risco de 1% = R$ 100 por operação. Entrada a R$ 20 e stop a R$ 19 = R$ 1 de risco por ação. "
                   "Posição: 100 ÷ 1 = **100 ações**.\n\n"
                   "**Na prática:** muitos operadores limitam o risco a 1% ou 2% do capital por operação.",
         intermediario="Com risco-retorno de 1:2, você pode acertar só 40% das vezes e ainda ter resultado positivo (antes de custos). A taxa de acerto e a "
                       "relação risco-retorno andam juntas: estratégia com alvo curto precisa acertar muito mais. Custos e impostos reduzem o resultado."),
    dict(_A, id="at_psicologia", titulo="Psicologia do trader", min=4,
         iniciante="No trading, as emoções pesam tanto quanto a técnica. As armadilhas mais comuns são:\n\n"
                   "**Medo:** sair cedo demais ou não entrar quando o plano manda.\n"
                   "**Ganância:** aumentar a posição ou tirar o alvo para \"ganhar mais\".\n"
                   "**Revanche:** depois de uma perda, operar de novo correndo para recuperar.\n"
                   "**Excesso de confiança:** depois de ganhos, arriscar demais.\n\n"
                   "**Na prática:** tenha um limite de perda diária e pare quando ele for atingido.",
         intermediario="Um **diário de operações** (motivo da entrada, stop, alvo, resultado e emoção) mostra padrões que a memória esconde. Avalie o "
                       "processo, não só o resultado: uma operação bem feita pode dar prejuízo, e uma mal feita pode dar lucro por sorte."),
    dict(_A, id="at_plano", titulo="Plano operacional", min=5,
         iniciante="O **plano operacional** é o seu manual: o que operar, quando entrar, onde pôr o stop e o alvo, quanto arriscar e quando parar.\n\n"
                   "**Itens de um plano:** ativos e tempo gráfico; condição de entrada; stop e alvo; risco por operação; limite de perda no dia ou no mês; "
                   "revisão periódica.\n\n"
                   "**Na prática:** escreva o plano e siga. Teste no **Trade Battle**, com dinheiro virtual, antes de usar dinheiro real.",
         intermediario="Um plano bom é **testável**: regras claras permitem medir taxa de acerto, risco-retorno e a maior sequência de perdas. Ajuste o plano "
                       "com base em muitas operações, não na última. A maioria das pessoas que opera com frequência perde dinheiro: comece pequeno."),
]

LICOES = [
    # -------- A bolsa por dentro
    dict(id="lt_bolsa", unidade="ut_bolsa", titulo="Como a bolsa funciona", icone="🏛️", aula="at_bolsa", exercicios=[
        dict(tipo="escolha", pergunta="Por onde um investidor pessoa física envia ordens para a bolsa?",
             opcoes=["Direto para a B3", "Por uma corretora", "Pelo Banco Central", "Pela Receita Federal"], correta=1,
             explicacao="A corretora é a intermediária que envia as suas ordens para a bolsa."),
        dict(tipo="vf", pergunta="Quando há mais gente querendo comprar do que vender, o preço tende a subir.", correta=True,
             explicacao="O preço se move pelo desequilíbrio entre oferta e demanda."),
        dict(tipo="vf", pergunta="Para alguém comprar uma ação, outra pessoa precisa vender.", correta=True,
             explicacao="Todo negócio tem as duas pontas: compradora e vendedora."),
        dict(tipo="escolha", pergunta="O que acontece em ativos com pouca liquidez?",
             opcoes=["Fica mais barato entrar e sair", "A diferença entre compra e venda costuma ser maior", "O preço não muda", "Não há riscos"], correta=1,
             explicacao="Com poucos negócios, o spread aumenta e encarece as operações."),
        dict(tipo="completar", pergunta="No Brasil, a bolsa de valores se chama ___.",
             opcoes=["B3", "CVM", "Copom", "Selic"], correta=0,
             explicacao="A B3 é a bolsa; a CVM é a reguladora do mercado de capitais."),
    ]),
    dict(id="lt_ordens", unidade="ut_bolsa", titulo="Ordens e book", icone="📋", aula="at_ordens", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada tipo de ordem ao que ela faz.",
             pares=[("A mercado", "Executa já, pelo melhor preço disponível"), ("Limitada", "Só executa no preço que você definir ou melhor"),
                    ("Stop", "É enviada quando o preço atinge um valor")],
             explicacao="Cada ordem troca rapidez por controle de preço de um jeito diferente."),
        dict(tipo="escolha", pergunta="O que é o spread no book de ofertas?",
             opcoes=["A taxa da corretora", "A diferença entre a melhor oferta de compra e a de venda", "O lucro da operação", "O volume do dia"], correta=1,
             explicacao="Quanto menor o spread, mais barato é entrar e sair do ativo."),
        dict(tipo="vf", pergunta="As ordens que aparecem no book são garantidas e não podem ser canceladas.", correta=False,
             explicacao="O book mostra intenções; ordens podem ser canceladas a qualquer momento."),
        dict(tipo="escolha", pergunta="Em um ativo com pouca liquidez, qual ordem costuma ser mais prudente?",
             opcoes=["A mercado", "Limitada", "Nenhuma", "Qualquer uma, tanto faz"], correta=1,
             explicacao="A limitada evita comprar muito caro ou vender muito barato quando o book está vazio."),
        dict(tipo="completar", pergunta="Quando a execução sai longe do preço do stop num movimento brusco, isso se chama ___.",
             opcoes=["slippage", "dividendo", "spread", "volume"], correta=0,
             explicacao="Em mercados rápidos, o stop pode ser executado a um preço pior do que o planejado."),
    ]),
    dict(id="lt_candles", unidade="ut_bolsa", titulo="Candlesticks", icone="🕯️", aula="at_candles", exercicios=[
        dict(tipo="escolha", pergunta="Quais quatro preços um candle mostra?",
             opcoes=["Abertura, fechamento, máxima e mínima", "Compra, venda, taxa e imposto", "Só a abertura e o fechamento", "Média, volume, topo e fundo"], correta=0,
             explicacao="O candle resume o período em abertura, fechamento, máxima e mínima."),
        dict(tipo="vf", pergunta="Um candle de alta fecha acima do preço de abertura.", correta=True,
             explicacao="O corpo vai da abertura ao fechamento; na alta, o fechamento fica acima."),
        dict(tipo="escolha", pergunta="Caso: abertura R$ 10, fechamento R$ 12, máxima R$ 13 e mínima R$ 9. De quanto é o corpo?",
             opcoes=["R$ 1", "R$ 2", "R$ 3", "R$ 4"], correta=1,
             explicacao="Corpo = fechamento − abertura = 12 − 10 = 2. A distância total (13 − 9 = 4) inclui as sombras."),
        dict(tipo="pares", pergunta="Ligue cada parte do candle ao que ela mostra.",
             pares=[("Corpo", "Da abertura ao fechamento"), ("Sombra superior", "Até onde foi a máxima"), ("Sombra inferior", "Até onde foi a mínima")],
             explicacao="Corpo e sombras juntos contam a disputa entre compradores e vendedores no período."),
        dict(tipo="vf", pergunta="Um único candle, sozinho, é suficiente para decidir uma operação.", correta=False,
             explicacao="O que importa é o conjunto e o contexto: onde o candle aparece e o que veio antes."),
    ]),
    # -------- Leitura do gráfico
    dict(id="lt_tendencia", unidade="ut_grafico", titulo="Tendências", icone="↗️", aula="at_tendencia", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada tendência à sua característica.",
             pares=[("Alta", "Topos e fundos mais altos"), ("Baixa", "Topos e fundos mais baixos"), ("Lateral", "Preço andando de lado")],
             explicacao="Topos e fundos são a forma mais simples de ler a tendência."),
        dict(tipo="escolha", pergunta="Caso: fundos em 10 e 12, topos em 14 e 16. Qual é a tendência?",
             opcoes=["Alta", "Baixa", "Lateral", "Não dá para saber"], correta=0,
             explicacao="Fundos e topos estão subindo: é uma tendência de alta."),
        dict(tipo="vf", pergunta="Um ativo pode estar em alta no gráfico diário e em baixa no de 15 minutos.", correta=True,
             explicacao="A tendência depende do tempo gráfico. Defina o seu e olhe um maior para o contexto."),
        dict(tipo="completar", pergunta="As ___ ajudam a ver a direção do preço, suavizando o sobe e desce.",
             opcoes=["médias móveis", "notícias", "taxas", "ordens a mercado"], correta=0,
             explicacao="A média móvel suaviza o preço e facilita ver a direção."),
        dict(tipo="vf", pergunta="Uma tendência, uma vez formada, nunca termina.", correta=False,
             explicacao="Toda tendência acaba um dia. Por isso existe o stop."),
    ]),
    dict(id="lt_suporte", unidade="ut_grafico", titulo="Suporte e resistência", icone="🧱", aula="at_suporte", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada região ao que costuma acontecer nela.",
             pares=[("Suporte", "O preço costuma parar de cair"), ("Resistência", "O preço costuma parar de subir")],
             explicacao="No suporte aparecem compradores; na resistência, vendedores."),
        dict(tipo="vf", pergunta="Um suporte rompido pode virar resistência.", correta=True,
             explicacao="É a chamada troca de papéis: a região que segurava a queda pode passar a segurar a alta."),
        dict(tipo="escolha", pergunta="Caso: o preço bateu em R$ 20 três vezes e voltou a subir. O que R$ 20 virou?",
             opcoes=["Uma resistência", "Um suporte", "Um stop", "Um dividendo"], correta=1,
             explicacao="Uma região onde o preço para de cair e volta a subir é um suporte."),
        dict(tipo="escolha", pergunta="Como é melhor pensar em suporte e resistência?",
             opcoes=["Como preços exatos", "Como regiões", "Como garantias", "Como ordens do banco"], correta=1,
             explicacao="O mercado raramente respeita um centavo exato. Pense em regiões."),
        dict(tipo="vf", pergunta="Rompimentos falsos são raros e podem ser ignorados.", correta=False,
             explicacao="São comuns; muitos operadores esperam o fechamento do candle ou um reteste antes de agir."),
    ]),
    dict(id="lt_volume", unidade="ut_grafico", titulo="Volume", icone="📶", aula="at_volume", exercicios=[
        dict(tipo="completar", pergunta="Volume é a ___ negociada num período.",
             opcoes=["quantidade", "taxa", "previsão", "garantia"], correta=0,
             explicacao="O volume mostra quanta participação houve no movimento."),
        dict(tipo="escolha", pergunta="Uma alta com volume muito baixo costuma indicar:",
             opcoes=["Muita força", "Pouca participação, possível fraqueza", "Garantia de continuação", "Nada"], correta=1,
             explicacao="Movimento com pouco volume tem menos gente por trás."),
        dict(tipo="vf", pergunta="Volume crescente na direção da tendência costuma confirmá-la.", correta=True,
             explicacao="Mais participação a favor da tendência é um sinal de força."),
        dict(tipo="escolha", pergunta="Um pico enorme de volume numa queda forte às vezes indica:",
             opcoes=["Um momento de pânico (capitulação)", "Que a empresa vai falir", "Um dividendo", "Um erro da bolsa"], correta=0,
             explicacao="Picos de volume em quedas fortes podem marcar vendas em pânico."),
        dict(tipo="vf", pergunta="O volume deve ser olhado sozinho, sem o preço.", correta=False,
             explicacao="Volume ganha sentido junto com o preço, principalmente em rompimentos."),
    ]),
    dict(id="lt_price_action", unidade="ut_grafico", titulo="Price action", icone="👁️", aula="at_price_action", exercicios=[
        dict(tipo="escolha", pergunta="O que é price action?",
             opcoes=["Ler o que o próprio preço está fazendo", "Seguir dicas de grupos", "Comprar só ações que pagam dividendos", "Usar dez indicadores ao mesmo tempo"], correta=0,
             explicacao="Price action foca em candles, topos e fundos, suportes e resistências."),
        dict(tipo="pares", pergunta="Ligue cada padrão à sua descrição.",
             pares=[("Martelo", "Sombra inferior longa num fundo"), ("Engolfo", "Candle que cobre o corpo do anterior"), ("Pullback", "Volta à região rompida antes de seguir")],
             explicacao="São padrões comuns, mas sempre dependem do contexto."),
        dict(tipo="vf", pergunta="Um padrão de candle sem contexto já é um sinal confiável.", correta=False,
             explicacao="O mesmo padrão vale mais perto de um suporte ou resistência importante."),
        dict(tipo="completar", pergunta="Antes de entrar, defina o que ___ a sua leitura, ou seja, onde fica o stop.",
             opcoes=["invalida", "confirma", "garante", "multiplica"], correta=0,
             explicacao="Saber onde a ideia está errada protege o capital."),
        dict(tipo="escolha", pergunta="Onde testar regras de price action antes de usar dinheiro real?",
             opcoes=["Direto com todo o capital", "Em dados passados ou no Trade Battle", "Em grupos de mensagem", "Não é preciso testar"], correta=1,
             explicacao="Testar com dinheiro virtual mostra se as regras funcionam, sem risco."),
    ]),
    # -------- Wyckoff
    dict(id="lt_wyckoff_fases", unidade="ut_wyckoff", titulo="As fases de Wyckoff", icone="🔁", aula="at_wyckoff_fases", exercicios=[
        dict(tipo="ordenar", pergunta="Coloque as fases do ciclo de Wyckoff na ordem, começando depois de uma queda.",
             itens=["Acumulação", "Alta (markup)", "Distribuição", "Baixa (markdown)"],
             explicacao="Lateraliza comprando, sobe, lateraliza vendendo e cai."),
        dict(tipo="escolha", pergunta="O que acontece na fase de acumulação?",
             opcoes=["O preço sobe forte", "O preço anda de lado enquanto grandes participantes compram", "O preço cai forte", "A bolsa fecha"], correta=1,
             explicacao="A acumulação é uma lateralização depois de uma queda, com compras graduais."),
        dict(tipo="pares", pergunta="Ligue cada lei de Wyckoff ao seu significado.",
             pares=[("Oferta e demanda", "O preço se move pelo desequilíbrio"), ("Causa e efeito", "Lateralização longa gera movimento maior"),
                    ("Esforço × resultado", "O volume deve combinar com o movimento")],
             explicacao="As três leis ajudam a ler preço e volume juntos."),
        dict(tipo="vf", pergunta="Wyckoff olha preço e volume juntos para entender quem está comprando e vendendo.", correta=True,
             explicacao="Essa é a essência do método."),
        dict(tipo="vf", pergunta="Pelo método de Wyckoff, toda lateralização é uma acumulação.", correta=False,
             explicacao="Uma lateralização pode ser acumulação, distribuição ou só uma pausa."),
    ]),
    dict(id="lt_wyckoff_acumulacao", unidade="ut_wyckoff", titulo="Acumulação e distribuição", icone="🧲", aula="at_wyckoff_acumulacao", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada evento de Wyckoff à fase em que aparece.",
             pares=[("Selling climax", "Acumulação"), ("Buying climax", "Distribuição")],
             explicacao="O clímax de venda marca o início da acumulação; o de compra, o da distribuição."),
        dict(tipo="escolha", pergunta="O que é um spring?",
             opcoes=["Uma falsa quebra para baixo que volta rápido", "Um dividendo extra", "Uma alta com volume alto", "Uma ordem limitada"], correta=0,
             explicacao="O spring pega os stops abaixo do suporte e volta para dentro da faixa."),
        dict(tipo="completar", pergunta="Na distribuição, a falsa quebra para cima se chama ___.",
             opcoes=["upthrust", "spring", "markup", "spread"], correta=0,
             explicacao="O upthrust é o espelho do spring, no topo."),
        dict(tipo="vf", pergunta="Rompimento com pouco volume e retorno rápido costuma ser falso.", correta=True,
             explicacao="Sem volume para confirmar, o rompimento tem pouca força."),
        dict(tipo="escolha", pergunta="Como usar os nomes dos eventos de Wyckoff?",
             opcoes=["Como um mapa para entender o mercado", "Como uma regra que sempre acontece", "Como garantia de lucro", "Para ignorar o volume"], correta=0,
             explicacao="São um mapa, não uma regra. O mercado nem sempre segue o roteiro."),
    ]),
    # -------- Gestão e psicologia
    dict(id="lt_stop", unidade="ut_gestao", titulo="Stop loss e take profit", icone="🛑", aula="at_stop", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada ordem ao seu objetivo.",
             pares=[("Stop loss", "Limitar a perda"), ("Take profit", "Realizar o lucro"), ("Stop móvel", "Proteger parte do ganho")],
             explicacao="Stop e alvo transformam a operação num plano com começo, meio e fim."),
        dict(tipo="escolha", pergunta="Caso: compra a R$ 20, stop a R$ 19 e alvo a R$ 22. Quanto se perde por ação se der errado?",
             opcoes=["R$ 1", "R$ 2", "R$ 3", "Nada"], correta=0,
             explicacao="20 − 19 = R$ 1 por ação. Se der certo, o ganho é 22 − 20 = R$ 2."),
        dict(tipo="escolha", pergunta="Quando o stop deve ser definido?",
             opcoes=["Antes de entrar na operação", "Depois que o preço cair muito", "Nunca", "Só no fim do dia"], correta=0,
             explicacao="Definido antes, o stop não é contaminado pela emoção do momento."),
        dict(tipo="vf", pergunta="Afastar o stop quando o preço chega perto dele é uma boa forma de evitar perdas.", correta=False,
             explicacao="Afastar o stop transforma uma perda pequena e planejada numa perda grande."),
        dict(tipo="vf", pergunta="Um stop apertado demais pode ser acionado pelo sobe e desce normal do preço.", correta=True,
             explicacao="Use a volatilidade do ativo e a estrutura do gráfico para posicionar o stop."),
    ]),
    dict(id="lt_risco_retorno", unidade="ut_gestao", titulo="Risco-retorno e posição", icone="⚖️", aula="at_risco_retorno", exercicios=[
        dict(tipo="escolha", pergunta="Arriscar R$ 1 para ganhar R$ 3 é uma relação risco-retorno de:",
             opcoes=["3:1", "1:3", "1:1", "3:3"], correta=1,
             explicacao="Risco primeiro, retorno depois: 1 para 3."),
        dict(tipo="escolha", pergunta="Caso: capital de R$ 10.000, risco de 1% por operação, entrada a R$ 20 e stop a R$ 19. Quantas ações comprar?",
             opcoes=["10", "50", "100", "500"], correta=2,
             explicacao="Risco = 1% de 10.000 = R$ 100. Risco por ação = R$ 1. 100 ÷ 1 = 100 ações."),
        dict(tipo="ordenar", pergunta="Coloque na ordem o cálculo do tamanho da posição.",
             itens=["Decidir quanto aceita perder na operação", "Calcular o risco por ação (entrada − stop)", "Dividir um pelo outro"],
             explicacao="O tamanho da posição sai do risco aceito, não da vontade de ganhar."),
        dict(tipo="vf", pergunta="Com relação risco-retorno de 1:2, é possível ter resultado positivo acertando menos da metade das vezes.", correta=True,
             explicacao="Ganhar 2 quando acerta e perder 1 quando erra permite acertar cerca de 40% (antes de custos)."),
        dict(tipo="vf", pergunta="Custos e impostos não afetam o resultado de quem opera com frequência.", correta=False,
             explicacao="Quanto mais operações, mais os custos pesam no resultado."),
    ]),
    dict(id="lt_psicologia", unidade="ut_gestao", titulo="Psicologia do trader", icone="🧘", aula="at_psicologia", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada emoção ao comportamento típico.",
             pares=[("Medo", "Sair cedo demais"), ("Ganância", "Tirar o alvo para ganhar mais"), ("Revanche", "Operar correndo depois de perder")],
             explicacao="Reconhecer a emoção é o primeiro passo para não ser guiado por ela."),
        dict(tipo="escolha", pergunta="Depois de uma sequência de perdas, o que é mais prudente?",
             opcoes=["Dobrar a posição para recuperar", "Respeitar o limite de perda do dia e parar", "Tirar o stop", "Seguir dicas de grupos"], correta=1,
             explicacao="O limite diário protege contra a operação de revanche."),
        dict(tipo="vf", pergunta="Uma operação bem feita pode dar prejuízo, e uma mal feita pode dar lucro por sorte.", correta=True,
             explicacao="Por isso se avalia o processo, não só o resultado."),
        dict(tipo="completar", pergunta="Um ___ de operações registra motivo, stop, alvo, resultado e emoção.",
             opcoes=["diário", "extrato", "boleto", "dividendo"], correta=0,
             explicacao="O diário mostra padrões que a memória esconde."),
        dict(tipo="escolha", pergunta="Depois de vários ganhos seguidos, qual é o risco comum?",
             opcoes=["Excesso de confiança e arriscar demais", "Ficar com medo de tudo", "Nenhum risco", "Perder o acesso à corretora"], correta=0,
             explicacao="Ganhos seguidos podem levar a aumentar o risco além do plano."),
    ]),
    dict(id="lt_plano", unidade="ut_gestao", titulo="Plano operacional", icone="📘", aula="at_plano", exercicios=[
        dict(tipo="escolha", pergunta="O que NÃO costuma fazer parte de um plano operacional?",
             opcoes=["Condição de entrada", "Stop e alvo", "Risco por operação", "Seguir a dica do dia de um influenciador"], correta=3,
             explicacao="O plano é feito de regras suas, testáveis, e não de dicas soltas."),
        dict(tipo="vf", pergunta="Um plano bom tem regras claras, que permitem medir taxa de acerto e risco-retorno.", correta=True,
             explicacao="Regras claras são testáveis; regras vagas não."),
        dict(tipo="ordenar", pergunta="Coloque na ordem a forma prudente de começar.",
             itens=["Escrever o plano", "Testar no Trade Battle com dinheiro virtual", "Começar pequeno com dinheiro real", "Revisar com base em muitas operações"],
             explicacao="Testar antes e começar pequeno protege o capital enquanto você aprende."),
        dict(tipo="vf", pergunta="O plano deve ser mudado depois de cada operação com prejuízo.", correta=False,
             explicacao="Ajuste com base em muitas operações; uma só não diz nada sobre o plano."),
        dict(tipo="escolha", pergunta="O que é um limite de perda diário?",
             opcoes=["O valor máximo que você aceita perder no dia antes de parar", "O lucro mínimo do dia", "O limite do cartão", "A taxa da corretora"], correta=0,
             explicacao="Ele impede que um dia ruim vire um prejuízo grande."),
    ]),
]

for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
