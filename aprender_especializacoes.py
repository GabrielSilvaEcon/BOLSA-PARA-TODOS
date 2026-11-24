"""Aprender · área ESPECIALIZAÇÕES (fase 4) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Sete trilhas para públicos e momentos de vida: MEI e empreendedores, autônomos, família, financiamentos, aposentadoria, golpes
financeiros e economia brasileira. Regras de impostos, INSS, MEI e Pix mudam: o texto ensina a ideia geral e remete às fontes
oficiais (Portal do Empreendedor, Meu INSS, Receita Federal, Banco Central). Números são HIPOTÉTICOS.
"""
from __future__ import annotations

AREA = "especializacoes"

UNIDADES = [
    dict(id="ue_mei", area=AREA, titulo="Finanças para MEI e empreendedores", icone="🏪", icone_svg="predio", cor="#FF8A3D",
         descricao="Separar as contas, precificar, fluxo de caixa e o básico do MEI.",
         licoes=["le_separar", "le_preco", "le_caixa", "le_mei"]),
    dict(id="ue_autonomo", area=AREA, titulo="Finanças para autônomos", icone="🧰", icone_svg="livro", cor="#38D0E0",
         descricao="Renda que varia, \"salário\" para você e proteção.",
         licoes=["le_renda_variavel", "le_protecao_autonomo"]),
    dict(id="ue_familia", area=AREA, titulo="Planejamento familiar", icone="👨‍👩‍👧", icone_svg="escudo", cor="#FF6B8A",
         descricao="Dinheiro a dois, filhos e educação financeira em casa.",
         licoes=["le_casal", "le_filhos", "le_mesada"]),
    dict(id="ue_financiamento", area=AREA, titulo="Financiamentos e consórcio", icone="🏠", icone_svg="cofre", cor="#4DA3FF",
         descricao="SAC ou Price, consórcio e financiar ou alugar.",
         licoes=["le_sac_price", "le_consorcio", "le_alugar"]),
    dict(id="ue_aposentadoria", area=AREA, titulo="Aposentadoria", icone="🌅", icone_svg="grafico", cor="#F7C84A",
         descricao="INSS, previdência privada e independência financeira.",
         licoes=["le_inss", "le_pgbl_vgbl", "le_independencia"]),
    dict(id="ue_golpes", area=AREA, titulo="Proteção contra golpes", icone="🛡️", icone_svg="escudo", cor="#FF5A7A",
         descricao="Golpes mais comuns, como se proteger e o que fazer se cair.",
         licoes=["le_golpes_comuns", "le_protecao", "le_caiu"]),
    dict(id="ue_economia", area=AREA, titulo="Economia brasileira", icone="🇧🇷", icone_svg="alvo", cor="#2DD4A0",
         descricao="Juros e inflação, PIB e emprego, câmbio.",
         licoes=["le_selic_inflacao", "le_pib", "le_cambio"]),
]

NIVEIS = {"le_pgbl_vgbl": "intermediario", "le_sac_price": "intermediario", "le_independencia": "intermediario", "le_cambio": "intermediario"}

_A = dict(assunto="fundamentos", dificuldade="iniciante", fontes=["bcb"], relacionadas=[])
AULAS = [
    # -------- MEI e empreendedores
    dict(_A, id="ae_separar", titulo="Separar o dinheiro da empresa e o seu", min=4,
         iniciante="O erro mais comum de quem empreende é **misturar** o dinheiro do negócio com o pessoal. Assim, ninguém sabe se a empresa dá lucro.\n\n"
                   "**Como separar:** tenha uma conta só para a empresa; pague todas as despesas do negócio por ela; e defina um **pró-labore**, um "
                   "\"salário\" fixo que você transfere para a sua conta pessoal todo mês.\n\n"
                   "**Exemplo do dia a dia:** a padaria vendeu R$ 8 mil no mês, mas os gastos foram R$ 6 mil. O dono pode tirar no máximo o que sobrou, e não os R$ 8 mil.\n\n"
                   "**Na prática:** o dinheiro que entra no caixa não é todo seu. Parte dele é do fornecedor, do imposto e da reposição.",
         intermediario="Com as contas separadas, dá para ver o **lucro real** e decidir quanto reinvestir. O pró-labore deve caber no lucro médio, e não no "
                       "melhor mês. Guarde também uma reserva para a empresa, separada da sua reserva pessoal."),
    dict(_A, id="ae_preco", titulo="Como definir o preço", min=5,
         iniciante="O preço precisa cobrir **custos** e ainda deixar **lucro**.\n\n"
                   "**Custos variáveis:** mudam com cada venda (matéria-prima, embalagem, taxa da maquininha).\n"
                   "**Custos fixos:** existem mesmo sem vender (aluguel, internet, pró-labore).\n\n"
                   "**Exemplo (hipotético):** um bolo custa R$ 20 em ingredientes e embalagem. Se cada bolo também precisa cobrir R$ 10 dos custos fixos e você "
                   "quer R$ 10 de lucro, o preço mínimo fica em R$ 40.\n\n"
                   "**Na prática:** olhe também o preço dos concorrentes e o valor que o cliente percebe. Preço baixo demais pode quebrar o negócio.",
         intermediario="A **margem de contribuição** (preço − custos variáveis) é o que cada venda deixa para pagar os custos fixos. Dividindo os custos fixos "
                       "pela margem de contribuição, você encontra o **ponto de equilíbrio**: quantas vendas são necessárias para não ter prejuízo."),
    dict(_A, id="ae_caixa", titulo="Fluxo de caixa", min=4,
         iniciante="**Fluxo de caixa** é o controle do dinheiro que **entra** e **sai** do negócio, dia a dia. Uma empresa pode vender bem e quebrar por falta de caixa.\n\n"
                   "**Exemplo do dia a dia:** você vendeu R$ 5 mil no cartão parcelado, mas vai receber aos poucos, e o fornecedor precisa ser pago esta semana.\n\n"
                   "**Na prática:** anote as entradas e saídas previstas para as próximas semanas. Assim você vê o aperto antes dele chegar.",
         intermediario="Diferencie **lucro** (vendas − custos) de **caixa** (dinheiro disponível). Prazos de recebimento longos e de pagamento curtos drenam o caixa. "
                       "Antecipar recebíveis tem custo; compare com outras opções antes."),
    dict(_A, id="ae_mei", titulo="O básico do MEI", min=4, fontes=["receita"],
         iniciante="O **MEI** (Microempreendedor Individual) é um jeito simplificado de formalizar um pequeno negócio. Ele tem um **limite de faturamento por ano** "
                   "e paga um valor mensal fixo, o **DAS**, que inclui a contribuição ao INSS.\n\n"
                   "**Vantagens:** CNPJ, poder emitir nota fiscal e ter direitos previdenciários, como aposentadoria e auxílio-doença, cumprindo as regras.\n\n"
                   "**Obrigações:** pagar o DAS todo mês e entregar a declaração anual de faturamento.\n\n"
                   "**Na prática:** os valores e o limite mudam com o tempo. Confira sempre no **Portal do Empreendedor**, o canal oficial.",
         intermediario="Se o faturamento passar do limite, é preciso mudar de enquadramento (por exemplo, para microempresa) e o imposto muda. Planeje o "
                       "crescimento para não ser pego de surpresa. Guarde as notas e os comprovantes."),
    # -------- Autônomos
    dict(_A, id="ae_renda_variavel", titulo="Renda que varia", min=4,
         iniciante="Quem é autônomo tem meses bons e meses fracos. O segredo é **não viver do mês bom**.\n\n"
                   "**Como fazer:** calcule a **renda média** dos últimos 12 meses; pague-se um \"salário\" fixo abaixo dessa média; deixe a sobra dos meses bons "
                   "numa conta separada para cobrir os meses fracos.\n\n"
                   "**Exemplo (hipotético):** renda de R$ 3 mil, R$ 6 mil e R$ 3 mil em três meses. A média é R$ 4 mil; um \"salário\" de R$ 3.500 deixa folga.\n\n"
                   "**Na prática:** a reserva de emergência de quem tem renda variável costuma precisar ser maior.",
         intermediario="Separe também o dinheiro dos impostos e da contribuição ao INSS assim que receber. Para autônomos pessoa física, o Imposto de Renda "
                       "mensal pode ser recolhido pelo carnê-leão: confira as regras na Receita Federal."),
    dict(_A, id="ae_protecao_autonomo", titulo="Proteção para quem é autônomo", min=4, fontes=["receita"],
         iniciante="Autônomo não tem férias pagas, 13º salário nem FGTS automaticamente. Por isso, a proteção depende de você.\n\n"
                   "**O básico:** contribuir para o **INSS** (para ter aposentadoria e auxílios), ter **reserva de emergência** maior e pensar em **seguros** quando "
                   "fizer sentido, como um seguro de renda em caso de doença.\n\n"
                   "**Na prática:** separe todo mês um valor para \"férias\" e \"13º\", como se fosse um salário com benefícios.",
         intermediario="Compare o custo de um seguro com o tamanho do risco que ele cobre. Para quem depende só do próprio trabalho, ficar sem poder trabalhar "
                       "é o maior risco financeiro."),
    # -------- Família
    dict(_A, id="ae_casal", titulo="Dinheiro a dois", min=4,
         iniciante="Dinheiro é uma das maiores causas de briga entre casais. Conversar cedo evita problemas.\n\n"
                   "**Modelos comuns:** tudo junto; tudo separado, dividindo as contas; ou um **misto** (uma conta conjunta para as despesas da casa e cada um com "
                   "a sua parte).\n\n"
                   "**Exemplo (hipotético):** um ganha R$ 6 mil e o outro R$ 4 mil. Dividir as contas proporcionalmente à renda (60% e 40%) costuma ser mais justo.\n\n"
                   "**Na prática:** façam uma reunião mensal curta para ver o orçamento e as metas da família.",
         intermediario="Transparência sobre dívidas e gastos é essencial. Combinem um valor acima do qual uma compra precisa ser conversada antes. Metas comuns "
                       "(casa, filhos, viagem) ajudam a manter os dois na mesma direção."),
    dict(_A, id="ae_filhos", titulo="Filhos e educação", min=4,
         iniciante="Filhos trazem gastos novos: saúde, escola, roupas e, mais tarde, a faculdade. Planejar com antecedência ajuda muito.\n\n"
                   "**Dicas:** inclua os gastos com os filhos no orçamento; aumente a reserva de emergência; e comece cedo a guardar para a educação, aproveitando "
                   "os juros compostos.\n\n"
                   "**Exemplo (hipotético, sem juros):** guardar R$ 150 por mês por 15 anos dá R$ 27.000.\n\n"
                   "**Na prática:** separe esse dinheiro numa conta ou investimento só para isso.",
         intermediario="Objetivos de longo prazo, como a faculdade, combinam com investimentos que protegem da inflação. O Tesouro Educa+ foi criado para esse fim. "
                       "Seguros de vida fazem sentido quando a família depende da sua renda."),
    dict(_A, id="ae_mesada", titulo="Educação financeira para crianças", min=4,
         iniciante="Crianças aprendem sobre dinheiro observando e praticando. A **mesada** é uma ótima ferramenta.\n\n"
                   "**Como usar:** dê um valor fixo e combinado; deixe a criança decidir o que fazer com ele; e não cubra os gastos quando o dinheiro acabar. Errar "
                   "com pouco dinheiro ensina a não errar com muito.\n\n"
                   "**Exemplo do dia a dia:** três potes: **gastar**, **guardar** e **doar**.\n\n"
                   "**Na prática:** converse sobre preços no mercado e mostre que as coisas têm custo.",
         intermediario="Conforme a idade, aumente a responsabilidade: de um pote de moedas a uma conta digital para adolescentes. Ensine a comparar preços, a "
                       "esperar para comprar e o efeito dos juros, para o bem e para o mal."),
    # -------- Financiamentos
    dict(_A, id="ae_sac_price", titulo="SAC ou Price", min=5,
         iniciante="Num financiamento, a parcela tem duas partes: **amortização** (o que abate a dívida) e **juros**. Os dois sistemas mais comuns são:\n\n"
                   "**SAC:** a amortização é constante; as parcelas começam **mais altas** e vão **diminuindo**. No total, paga-se **menos juros**.\n\n"
                   "**Price:** as parcelas são **fixas**; no começo, a maior parte é juros. No total, paga-se **mais juros**.\n\n"
                   "**Na prática:** se a primeira parcela do SAC cabe no orçamento, ele costuma sair mais barato. Compare pelo **CET** e pelo valor total.",
         intermediario="Antecipar parcelas reduz os juros, porque abate o saldo devedor. Você pode escolher reduzir o **prazo** (economiza mais juros) ou o "
                       "**valor da parcela**. No financiamento imobiliário, o FGTS pode ajudar na entrada ou na amortização, conforme as regras."),
    dict(_A, id="ae_consorcio", titulo="Consórcio", min=4,
         iniciante="No **consórcio**, um grupo de pessoas paga parcelas mensais e, a cada mês, alguém é **contemplado** (por sorteio ou por lance) e recebe uma "
                   "carta de crédito para comprar o bem.\n\n"
                   "**Diferença do financiamento:** não há juros, mas há **taxa de administração**, e você não sabe quando vai receber.\n\n"
                   "**Na prática:** consórcio combina com quem não tem pressa e quer disciplina para juntar dinheiro. Leia bem o contrato e confira se a "
                   "administradora é autorizada pelo Banco Central.",
         intermediario="Some a taxa de administração, o fundo de reserva e o seguro para ver o custo total. Compare com a alternativa de investir as mesmas "
                       "parcelas por conta própria e comprar à vista depois."),
    dict(_A, id="ae_alugar", titulo="Financiar ou alugar?", min=5,
         iniciante="Não existe resposta única. Depende do preço do imóvel, do aluguel, dos juros e da sua vida.\n\n"
                   "**Comprar** dá estabilidade e patrimônio, mas tem entrada, juros, impostos e manutenção. **Alugar** dá flexibilidade e libera dinheiro para "
                   "investir, mas o aluguel não vira patrimônio.\n\n"
                   "**Exemplo (hipotético):** imóvel de R$ 300 mil e aluguel de R$ 1.200 (0,4% ao mês). Se o dinheiro investido renderia mais do que isso, alugar "
                   "e investir a diferença pode compensar.\n\n"
                   "**Na prática:** pense em quanto tempo vai morar ali e no que te deixa mais tranquilo.",
         intermediario="Compare o **custo de oportunidade**: o rendimento que a entrada e as parcelas teriam se fossem investidas, contra o aluguel mais a "
                       "valorização esperada do imóvel. Inclua ITBI, escritura, condomínio e manutenção na conta."),
    # -------- Aposentadoria
    dict(_A, id="ae_inss", titulo="INSS: o básico", min=4,
         iniciante="O **INSS** é a previdência pública. Quem trabalha com carteira assinada contribui automaticamente; autônomos e MEIs contribuem por conta própria.\n\n"
                   "**Para se aposentar** há uma **idade mínima** e um **tempo mínimo de contribuição**, que mudaram com a reforma de 2019.\n\n"
                   "**Além da aposentadoria,** o INSS paga auxílios, como em caso de doença, e a pensão por morte, cumprindo as regras.\n\n"
                   "**Na prática:** confira o seu tempo de contribuição no **Meu INSS** e se há períodos faltando.",
         intermediario="O valor da aposentadoria do INSS tem um teto. Quem ganha mais costuma precisar de uma renda complementar, de investimentos ou de "
                       "previdência privada, para manter o padrão de vida."),
    dict(_A, id="ae_pgbl_vgbl", titulo="Previdência privada: PGBL e VGBL", min=5, fontes=["receita", "anbima"],
         iniciante="A **previdência privada** é um investimento de longo prazo para complementar a aposentadoria. Há dois tipos:\n\n"
                   "**PGBL:** permite deduzir as contribuições do Imposto de Renda, até **12% da renda bruta tributável**, para quem faz a **declaração completa**. "
                   "No resgate, o IR incide sobre **todo o valor**.\n\n"
                   "**VGBL:** não deduz do IR; no resgate, o imposto incide só sobre os **rendimentos**.\n\n"
                   "**Na prática:** quem faz a declaração simplificada ou é isento costuma preferir o VGBL. Olhe sempre a **taxa de administração**.",
         intermediario="Há duas tabelas de IR: a **progressiva** (como a do salário) e a **regressiva**, cuja alíquota cai com o tempo e chega a 10% para "
                       "recursos aplicados há mais de 10 anos. A previdência também facilita a sucessão, mas as regras podem mudar: confira na Receita Federal."),
    dict(_A, id="ae_independencia", titulo="Independência financeira", min=5,
         iniciante="**Independência financeira** é quando os rendimentos dos seus investimentos pagam o seu custo de vida, e trabalhar vira escolha.\n\n"
                   "**Os três motores:** quanto você **guarda**, por quanto **tempo** e quanto o dinheiro **rende**.\n\n"
                   "**Exemplo (hipotético):** quem gasta R$ 4 mil por mês e tem investimentos que rendem, acima da inflação, 0,4% ao mês precisa de cerca de "
                   "R$ 1 milhão (4.000 ÷ 0,004).\n\n"
                   "**Na prática:** comece cedo e aumente o aporte sempre que a renda subir.",
         intermediario="Na conta, use o **retorno real** (acima da inflação), não o nominal, e seja conservador. Muitas pessoas planejam uma retirada anual "
                       "pequena do patrimônio para ele durar décadas. Reduzir o custo de vida diminui o valor necessário e aumenta o que você consegue guardar."),
    # -------- Golpes
    dict(_A, id="ae_golpes_comuns", titulo="Golpes mais comuns", min=4,
         iniciante="Os golpes financeiros mudam, mas os truques se repetem:\n\n"
                   "**Falso funcionário do banco:** liga dizendo que a sua conta foi invadida e pede para você transferir o dinheiro.\n"
                   "**Falso parente no WhatsApp:** \"troquei de número\", e logo pede um Pix.\n"
                   "**Boleto ou link falso:** imita uma empresa conhecida.\n"
                   "**Pirâmide e investimento milagroso:** promete ganho alto e garantido.\n\n"
                   "**Na prática:** banco **não** pede senha, código nem transferência por telefone. Na dúvida, desligue e ligue para o número oficial.",
         intermediario="Os golpistas usam **urgência**, **medo** e **autoridade**. Qualquer pedido de dinheiro com pressa é um alerta. Combine uma \"palavra "
                       "secreta\" com a família para confirmar pedidos por mensagem."),
    dict(_A, id="ae_protecao", titulo="Como se proteger", min=4,
         iniciante="Hábitos simples evitam a maioria dos golpes:\n\n"
                   "**Senhas fortes e diferentes**, com **verificação em duas etapas**; **não clicar** em links recebidos por mensagem; **conferir** o nome de quem "
                   "vai receber antes de confirmar um Pix; e usar só os **aplicativos oficiais**.\n\n"
                   "**Exemplo do dia a dia:** antes de pagar um boleto, confira o banco e o beneficiário que aparecem na tela.\n\n"
                   "**Na prática:** defina um **limite de Pix** baixo, principalmente à noite, no app do banco.",
         intermediario="Golpes de investimento costumam vir de empresas sem registro. Consulte a CVM antes de investir com alguém e desconfie de rendimentos "
                       "muito acima do mercado. Mantenha o celular atualizado e com bloqueio de tela."),
    dict(_A, id="ae_caiu", titulo="Caí num golpe. E agora?", min=4,
         iniciante="Agir **rápido** aumenta a chance de recuperar o dinheiro.\n\n"
                   "**Passo a passo:** (1) avise o seu banco **imediatamente**, pelo canal oficial; (2) se foi Pix, peça o **MED** (Mecanismo Especial de "
                   "Devolução); (3) registre um **boletim de ocorrência**; (4) troque as senhas e verifique outras contas.\n\n"
                   "**Na prática:** guarde prints, comprovantes e números. Eles ajudam o banco e a polícia.",
         intermediario="O MED permite ao banco bloquear valores na conta de quem recebeu e devolver, se ainda houver saldo. Quanto antes o pedido, melhor. Se o "
                       "banco não resolver, registre reclamação no Banco Central e no consumidor.gov.br."),
    # -------- Economia brasileira
    dict(_A, id="ae_selic_inflacao", titulo="Juros e inflação", min=5,
         iniciante="A **inflação** é o aumento geral dos preços. O **Banco Central** tem a missão de mantê-la perto de uma **meta**.\n\n"
                   "**A principal ferramenta** é a **Selic**: quando a inflação sobe demais, o Copom aumenta os juros. O crédito fica mais caro, as pessoas "
                   "compram menos e os preços tendem a desacelerar. Quando a inflação está controlada, os juros podem cair.\n\n"
                   "**Exemplo do dia a dia:** com a Selic alta, o financiamento fica mais caro, mas a renda fixa rende mais.\n\n"
                   "**Na prática:** acompanhe as decisões do Copom: elas mexem no seu crédito e nos seus investimentos.",
         intermediario="Os juros agem com **defasagem**: uma mudança na Selic leva meses para chegar aos preços. As expectativas importam: se as pessoas "
                       "acreditam que a inflação vai subir, reajustam preços antes, e o Banco Central reage a isso."),
    dict(_A, id="ae_pib", titulo="PIB e emprego", min=4,
         iniciante="O **PIB** (Produto Interno Bruto) é a soma de tudo o que o país produz num período. Quando cresce, a economia está aquecida; quando cai, "
                   "pode ser **recessão**.\n\n"
                   "**Emprego:** com a economia crescendo, as empresas contratam mais e a renda sobe. Na recessão, o desemprego aumenta.\n\n"
                   "**Exemplo do dia a dia:** em épocas de crise, ter reserva de emergência faz ainda mais diferença.\n\n"
                   "**Na prática:** esses números saem do **IBGE** e ajudam a entender o momento do país.",
         intermediario="PIB, emprego, inflação e juros se influenciam: economia muito aquecida pode pressionar a inflação, levando a juros maiores, que esfriam "
                       "a atividade. Os ciclos econômicos afetam setores e empresas de forma diferente."),
    dict(_A, id="ae_cambio", titulo="Câmbio e dólar", min=4,
         iniciante="**Câmbio** é o preço de uma moeda em outra, como quantos reais custa um dólar.\n\n"
                   "**O que mexe no dólar:** juros no Brasil e nos EUA, a confiança nas contas do governo, as exportações e o humor do mundo.\n\n"
                   "**Efeitos:** dólar alto encarece produtos importados, viagens e até combustível, e pode pressionar a inflação; dólar baixo barateia importados.\n\n"
                   "**Na prática:** para uma viagem futura, comprar a moeda aos poucos reduz o risco de pagar tudo num pico.",
         intermediario="Exportadores ganham com o dólar alto; importadores perdem. Ter uma parte dos investimentos exposta a outras moedas (como por ETFs "
                       "internacionais) pode diversificar o risco de concentrar tudo no real."),
]

def _ex(tipo, pergunta, explicacao, **kw):
    return dict(tipo=tipo, pergunta=pergunta, explicacao=explicacao, **kw)


LICOES = [
    # -------- MEI e empreendedores
    dict(id="le_separar", unidade="ue_mei", titulo="Separar as contas", icone="🗂️", aula="ae_separar", exercicios=[
        _ex("escolha", "Qual é o erro mais comum de quem empreende?", "Misturando as contas, ninguém sabe se a empresa dá lucro.",
            opcoes=["Ter uma conta só para a empresa", "Misturar o dinheiro do negócio com o pessoal", "Definir um pró-labore", "Anotar as despesas"], correta=1),
        _ex("completar", "O \"salário\" fixo que o dono tira da empresa se chama ___.", "O pró-labore deve caber no lucro médio do negócio.",
            opcoes=["pró-labore", "DAS", "faturamento", "capital de giro"], correta=0),
        _ex("escolha", "Caso: a padaria vendeu R$ 8 mil e gastou R$ 6 mil no mês. Quanto o dono pode tirar, no máximo?",
            "Só o que sobrou: 8.000 − 6.000 = 2.000. O resto pertence aos custos do negócio.", opcoes=["R$ 8.000", "R$ 6.000", "R$ 2.000", "R$ 14.000"], correta=2),
        _ex("vf", "Todo o dinheiro que entra no caixa da empresa é do dono.", "Parte é do fornecedor, do imposto e da reposição.", correta=False),
        _ex("vf", "A empresa também deve ter uma reserva própria, separada da reserva pessoal.", "Assim um mês ruim no negócio não desorganiza a vida pessoal.", correta=True),
    ]),
    dict(id="le_preco", unidade="ue_mei", titulo="Como definir o preço", icone="🏷️", aula="ae_preco", exercicios=[
        _ex("pares", "Ligue cada custo do negócio ao seu tipo.", "Custos variáveis mudam com cada venda; os fixos existem mesmo sem vender.",
            pares=[("Matéria-prima", "Custo variável"), ("Aluguel da loja", "Custo fixo"), ("Taxa da maquininha", "Custo variável por venda")]),
        _ex("escolha", "Caso: R$ 20 de ingredientes, R$ 10 de custos fixos por bolo e R$ 10 de lucro desejado. Qual o preço mínimo?",
            "20 + 10 + 10 = R$ 40.", opcoes=["R$ 20", "R$ 30", "R$ 40", "R$ 50"], correta=2),
        _ex("completar", "Preço menos custos variáveis é a margem de ___.", "É o que cada venda deixa para pagar os custos fixos.",
            opcoes=["contribuição", "erro", "segurança", "lucro garantido"], correta=0),
        _ex("vf", "Cobrar o preço mais baixo da cidade sempre faz o negócio crescer.", "Preço baixo demais pode não cobrir os custos e quebrar o negócio.", correta=False),
        _ex("escolha", "O ponto de equilíbrio mostra:", "É o número de vendas em que o negócio não tem lucro nem prejuízo.",
            opcoes=["Quantas vendas são necessárias para não ter prejuízo", "O preço do concorrente", "O valor do DAS", "O lucro máximo possível"], correta=0),
    ]),
    dict(id="le_caixa", unidade="ue_mei", titulo="Fluxo de caixa", icone="💧", aula="ae_caixa", exercicios=[
        _ex("vf", "Uma empresa pode vender bem e mesmo assim quebrar por falta de caixa.", "Se o dinheiro entra depois das contas vencerem, falta caixa.", correta=True),
        _ex("pares", "Ligue lucro e caixa ao que cada um significa.", "Lucro e caixa são coisas diferentes.",
            pares=[("Lucro", "Vendas menos custos"), ("Caixa", "Dinheiro disponível agora")]),
        _ex("escolha", "Caso: você vendeu R$ 5 mil parcelado no cartão e o fornecedor vence esta semana. Qual é o risco?",
            "O dinheiro da venda entra aos poucos, mas a conta vence agora.", opcoes=["Nenhum", "Faltar dinheiro para pagar o fornecedor", "Pagar menos imposto", "Ganhar mais"], correta=1),
        _ex("escolha", "O que ajuda a prever um aperto de caixa?", "Prever entradas e saídas mostra o aperto antes dele chegar.",
            opcoes=["Anotar as entradas e saídas das próximas semanas", "Ignorar as contas", "Vender mais barato", "Tirar mais pró-labore"], correta=0),
        _ex("completar", "Antecipar recebíveis tem ___, por isso compare com outras opções.", "A antecipação cobra juros ou taxas.",
            opcoes=["custo", "garantia", "isenção", "prêmio"], correta=0),
    ]),
    dict(id="le_mei", unidade="ue_mei", titulo="O básico do MEI", icone="🧾", aula="ae_mei", exercicios=[
        _ex("completar", "O MEI paga todo mês um valor fixo chamado ___.", "O DAS inclui a contribuição ao INSS.",
            opcoes=["DAS", "IPTU", "CET", "FGTS"], correta=0),
        _ex("vf", "O MEI tem um limite de faturamento por ano.", "Se passar do limite, é preciso mudar de enquadramento.", correta=True),
        _ex("escolha", "Qual é o canal oficial para conferir as regras e valores do MEI?",
            "As regras mudam com o tempo; confira sempre no canal oficial.", opcoes=["Grupos de mensagem", "Portal do Empreendedor", "Qualquer site", "O banco"], correta=1),
        _ex("pares", "Ligue cada item do MEI ao que ele é.", "Vantagens e obrigações andam juntas.",
            pares=[("CNPJ e nota fiscal", "Vantagem"), ("Declaração anual de faturamento", "Obrigação"), ("Auxílios do INSS", "Direito, cumprindo as regras")]),
        _ex("vf", "Pagando o DAS em dia, o MEI pode ter direitos previdenciários, como aposentadoria.", "O DAS inclui a contribuição ao INSS.", correta=True),
    ]),
    # -------- Autônomos
    dict(id="le_renda_variavel", unidade="ue_autonomo", titulo="Renda que varia", icone="🎢", aula="ae_renda_variavel", exercicios=[
        _ex("escolha", "Caso: rendas de R$ 3 mil, R$ 6 mil e R$ 3 mil em três meses. Qual é a média?", "(3 + 6 + 3) ÷ 3 = R$ 4 mil.",
            opcoes=["R$ 3 mil", "R$ 4 mil", "R$ 6 mil", "R$ 12 mil"], correta=1),
        _ex("vf", "Quem tem renda variável deve definir o padrão de vida pelo melhor mês.", "O certo é se pagar um \"salário\" abaixo da média.", correta=False),
        _ex("ordenar", "Coloque na ordem a organização de quem tem renda variável.", "Média, salário abaixo da média e reserva para os meses fracos.",
            itens=["Calcular a renda média", "Definir um \"salário\" abaixo da média", "Guardar a sobra dos meses bons"]),
        _ex("escolha", "A reserva de emergência de quem tem renda variável costuma ser:", "A incerteza maior pede uma reserva maior.",
            opcoes=["Menor", "Maior", "Igual à de qualquer pessoa", "Desnecessária"], correta=1),
        _ex("completar", "O autônomo pessoa física pode recolher o IR mensal pelo ___.", "Confira as regras atuais na Receita Federal.",
            opcoes=["carnê-leão", "DAS", "FGTS", "boleto do condomínio"], correta=0),
    ]),
    dict(id="le_protecao_autonomo", unidade="ue_autonomo", titulo="Proteção do autônomo", icone="☂️", aula="ae_protecao_autonomo", exercicios=[
        _ex("vf", "O autônomo recebe 13º salário e FGTS automaticamente.", "Esses direitos são do trabalho com carteira; o autônomo precisa se organizar.", correta=False),
        _ex("escolha", "Qual é o maior risco financeiro de quem depende só do próprio trabalho?",
            "Sem trabalhar, a renda para. Por isso INSS, reserva e seguros ajudam.", opcoes=["Ficar sem poder trabalhar", "Ter muitos clientes", "Pagar pouco imposto", "Ter tempo livre"], correta=0),
        _ex("pares", "Ligue cada proteção ao que ela cobre.", "Cada proteção cobre um tipo de risco.",
            pares=[("INSS", "Aposentadoria e auxílios"), ("Reserva de emergência", "Imprevistos e meses fracos"), ("Seguro de renda", "Afastamento por doença")]),
        _ex("escolha", "Uma boa prática para o autônomo é:", "Guardar como se fosse um salário com benefícios.",
            opcoes=["Separar todo mês um valor para \"férias\" e \"13º\"", "Gastar tudo no mês bom", "Não contribuir para nada", "Usar o cheque especial"], correta=0),
        _ex("vf", "Antes de contratar um seguro, compare o custo com o tamanho do risco que ele cobre.", "Seguro faz sentido quando protege de um risco relevante.", correta=True),
    ]),
    # -------- Família
    dict(id="le_casal", unidade="ue_familia", titulo="Dinheiro a dois", icone="💑", aula="ae_casal", exercicios=[
        _ex("escolha", "Caso: um ganha R$ 6 mil e o outro R$ 4 mil. Na divisão proporcional, quanto o primeiro paga das contas da casa?",
            "6 ÷ (6 + 4) = 60% das contas.", opcoes=["50%", "60%", "40%", "100%"], correta=1),
        _ex("pares", "Ligue cada modelo de organização ao seu formato.", "Não há modelo certo; o importante é combinar.",
            pares=[("Tudo junto", "Uma conta só para o casal"), ("Tudo separado", "Cada um paga a sua parte"), ("Misto", "Conta conjunta para a casa e o resto separado")]),
        _ex("vf", "Esconder dívidas do parceiro ajuda a evitar brigas.", "Transparência é essencial para planejar juntos.", correta=False),
        _ex("escolha", "Uma boa prática para o casal é:", "Uma conversa curta e regular evita surpresas.",
            opcoes=["Uma reunião mensal sobre o orçamento e as metas", "Nunca falar de dinheiro", "Cada um decidir tudo sozinho", "Usar só cartão de crédito"], correta=0),
        _ex("completar", "Combinem um valor acima do qual uma compra precisa ser ___ antes.", "Assim nenhum dos dois é pego de surpresa.",
            opcoes=["conversada", "parcelada", "escondida", "cancelada"], correta=0),
    ]),
    dict(id="le_filhos", unidade="ue_familia", titulo="Filhos e educação", icone="🎒", aula="ae_filhos", exercicios=[
        _ex("escolha", "Caso (sem juros): R$ 150 por mês durante 15 anos. Quanto vai juntar?", "150 × 12 × 15 = R$ 27.000.",
            opcoes=["R$ 2.700", "R$ 27.000", "R$ 18.000", "R$ 150.000"], correta=1),
        _ex("vf", "Com filhos, costuma ser bom aumentar a reserva de emergência.", "Mais pessoas dependendo da renda pedem mais proteção.", correta=True),
        _ex("completar", "O Tesouro ___ foi criado para quem quer guardar para a educação.", "Ele paga uma renda mensal durante os anos de estudo.",
            opcoes=["Educa+", "Selic", "Renda+", "Prefixado"], correta=0),
        _ex("escolha", "Quando o seguro de vida costuma fazer sentido?", "Ele protege quem depende da sua renda.",
            opcoes=["Quando a família depende da sua renda", "Nunca", "Só para quem é rico", "Só depois dos 80 anos"], correta=0),
        _ex("pares", "Ligue cada gasto ao prazo em que costuma aparecer.", "Planejar por prazo ajuda a separar o dinheiro certo.",
            pares=[("Fraldas e saúde", "Desde o início"), ("Material escolar", "Todo ano"), ("Faculdade", "Longo prazo")]),
    ]),
    dict(id="le_mesada", unidade="ue_familia", titulo="Mesada e crianças", icone="🐷", aula="ae_mesada", exercicios=[
        _ex("vf", "Se a mesada acaba antes do previsto, os pais devem cobrir os gastos sempre.", "Errar com pouco dinheiro ensina a não errar com muito.", correta=False),
        _ex("pares", "Ligue cada pote ao seu uso.", "Os três potes ensinam a dividir o dinheiro.",
            pares=[("Gastar", "Compras do dia a dia"), ("Guardar", "Objetivos futuros"), ("Doar", "Ajudar alguém")]),
        _ex("escolha", "Qual é um bom jeito de usar a mesada?", "Valor fixo e liberdade para decidir ensinam responsabilidade.",
            opcoes=["Valor fixo e combinado, com a criança decidindo o que fazer", "Dar dinheiro sempre que pedir", "Nunca dar dinheiro", "Pagar por tudo que a criança faz em casa"], correta=0),
        _ex("completar", "Ensinar a ___ para comprar ajuda a criança a controlar o impulso.", "Esperar faz muitas vontades passarem.",
            opcoes=["esperar", "pedir emprestado", "parcelar", "gastar logo"], correta=0),
        _ex("vf", "Conversar sobre preços no mercado ajuda a criança a entender que as coisas têm custo.", "Exemplos do dia a dia ensinam mais do que discursos.", correta=True),
    ]),
    # -------- Financiamentos
    dict(id="le_sac_price", unidade="ue_financiamento", titulo="SAC ou Price", icone="📊", aula="ae_sac_price", exercicios=[
        _ex("pares", "Ligue cada sistema de amortização à sua característica.", "No SAC as parcelas caem; na Price ficam iguais.",
            pares=[("SAC", "Parcelas começam altas e diminuem"), ("Price", "Parcelas fixas")]),
        _ex("escolha", "Em qual sistema se paga menos juros no total, em geral?", "Como a amortização é maior no início, o saldo cai mais rápido.",
            opcoes=["SAC", "Price", "Os dois pagam igual", "Depende da cor do contrato"], correta=0),
        _ex("vf", "Na tabela Price, no começo, a maior parte da parcela é juros.", "A amortização é pequena no início e cresce com o tempo.", correta=True),
        _ex("escolha", "Ao antecipar parcelas, o que economiza mais juros?", "Reduzir o prazo corta mais juros futuros.",
            opcoes=["Reduzir o prazo", "Reduzir o valor da parcela", "Não antecipar", "Pedir mais crédito"], correta=0),
        _ex("completar", "Para comparar financiamentos, use o ___ e o valor total pago.", "O CET inclui juros, tarifas e seguros.",
            opcoes=["CET", "IPCA", "limite do cartão", "DAS"], correta=0),
    ]),
    dict(id="le_consorcio", unidade="ue_financiamento", titulo="Consórcio", icone="🤝", aula="ae_consorcio", exercicios=[
        _ex("escolha", "Como alguém recebe a carta de crédito no consórcio?", "A contemplação é por sorteio ou por lance.",
            opcoes=["Por sorteio ou por lance", "Na primeira parcela, sempre", "Pagando juros extras", "Pela ordem alfabética"], correta=0),
        _ex("vf", "O consórcio não tem juros, mas tem taxa de administração.", "Some as taxas para ver o custo total.", correta=True),
        _ex("escolha", "Para quem o consórcio costuma combinar mais?", "Você não sabe quando vai ser contemplado.",
            opcoes=["Quem precisa do bem amanhã", "Quem não tem pressa e quer disciplina", "Quem quer o bem garantido em um mês", "Ninguém"], correta=1),
        _ex("completar", "Confira se a administradora de consórcio é autorizada pelo ___.", "Administradoras precisam de autorização para funcionar.",
            opcoes=["Banco Central", "IBGE", "Copom", "INSS"], correta=0),
        _ex("pares", "Ligue cada custo do consórcio ao que ele é.", "Esses custos somados formam o custo total do consórcio.",
            pares=[("Taxa de administração", "Remuneração da administradora"), ("Fundo de reserva", "Proteção do grupo contra inadimplência")]),
    ]),
    dict(id="le_alugar", unidade="ue_financiamento", titulo="Financiar ou alugar", icone="🔑", aula="ae_alugar", exercicios=[
        _ex("escolha", "Caso: imóvel de R$ 300 mil e aluguel de R$ 1.200. Quanto o aluguel representa por mês sobre o valor do imóvel?",
            "1.200 ÷ 300.000 = 0,4% ao mês.", opcoes=["0,04%", "0,4%", "4%", "1,2%"], correta=1),
        _ex("pares", "Ligue cada opção à sua principal vantagem.", "Não existe resposta única: depende da sua vida e dos números.",
            pares=[("Comprar", "Estabilidade e patrimônio"), ("Alugar", "Flexibilidade e dinheiro livre para investir")]),
        _ex("completar", "O rendimento que o dinheiro teria se fosse investido se chama custo de ___.", "Ele é a chave da comparação entre comprar e alugar.",
            opcoes=["oportunidade", "manutenção", "condomínio", "escritura"], correta=0),
        _ex("vf", "Na conta de comprar um imóvel, só o valor das parcelas importa.", "Inclua entrada, ITBI, escritura, condomínio e manutenção.", correta=False),
        _ex("escolha", "Uma pergunta importante antes de decidir é:", "Quem vai mudar logo perde a vantagem de ter comprado.",
            opcoes=["Quanto tempo pretendo morar ali?", "Qual é a cor das paredes?", "Qual banco tem o melhor app?", "O vizinho comprou?"], correta=0),
    ]),
    # -------- Aposentadoria
    dict(id="le_inss", unidade="ue_aposentadoria", titulo="INSS: o básico", icone="🏛️", aula="ae_inss", exercicios=[
        _ex("vf", "Para se aposentar pelo INSS há uma idade mínima e um tempo mínimo de contribuição.", "As regras mudaram com a reforma de 2019.", correta=True),
        _ex("escolha", "Onde conferir o seu tempo de contribuição?", "O Meu INSS é o canal oficial.",
            opcoes=["No Meu INSS", "Em grupos de mensagem", "Na fatura do cartão", "No extrato da corretora"], correta=0),
        _ex("pares", "Ligue cada trabalhador ao jeito de contribuir para o INSS.", "Todos podem contribuir, de formas diferentes.",
            pares=[("Carteira assinada", "Desconto automático no salário"), ("MEI", "Dentro do DAS mensal"), ("Autônomo", "Por conta própria")]),
        _ex("completar", "O valor da aposentadoria do INSS tem um ___.", "Quem ganha mais costuma precisar de renda complementar.",
            opcoes=["teto", "bônus", "prazo de validade", "spread"], correta=0),
        _ex("vf", "O INSS paga só a aposentadoria, e nenhum outro benefício.", "Também há auxílios e a pensão por morte, cumprindo as regras.", correta=False),
    ]),
    dict(id="le_pgbl_vgbl", unidade="ue_aposentadoria", titulo="PGBL e VGBL", icone="🧓", aula="ae_pgbl_vgbl", exercicios=[
        _ex("pares", "Ligue cada plano ao seu jeito de tributar.", "No PGBL o IR incide sobre tudo no resgate; no VGBL, só sobre os rendimentos.",
            pares=[("PGBL", "Deduz do IR e tributa tudo no resgate"), ("VGBL", "Não deduz e tributa só os rendimentos")]),
        _ex("escolha", "Até quanto da renda bruta tributável o PGBL permite deduzir, para quem faz a declaração completa?",
            "O limite é de 12% da renda bruta tributável.", opcoes=["5%", "12%", "27,5%", "50%"], correta=1),
        _ex("escolha", "Quem faz a declaração simplificada costuma preferir:", "Sem a dedução, o PGBL perde a principal vantagem.",
            opcoes=["PGBL", "VGBL", "Os dois são iguais para ele", "Nenhum, é proibido"], correta=1),
        _ex("completar", "Na tabela regressiva, a alíquota cai com o tempo e chega a ___ depois de 10 anos.", "A tabela regressiva premia o longo prazo.",
            opcoes=["10%", "0%", "27,5%", "15%"], correta=0),
        _ex("vf", "Na previdência privada, a taxa de administração não faz diferença no longo prazo.", "Taxas altas comem uma parte grande do resultado em décadas.", correta=False),
    ]),
    dict(id="le_independencia", unidade="ue_aposentadoria", titulo="Independência financeira", icone="🗽", aula="ae_independencia", exercicios=[
        _ex("escolha", "Caso: custo de vida de R$ 4 mil por mês e rendimento real de 0,4% ao mês. Qual patrimônio é necessário?",
            "4.000 ÷ 0,004 = R$ 1.000.000.", opcoes=["R$ 100 mil", "R$ 400 mil", "R$ 1 milhão", "R$ 4 milhões"], correta=2),
        _ex("pares", "Ligue cada motor da independência financeira ao que ele é.", "Os três motores trabalham juntos.",
            pares=[("Aporte", "Quanto você guarda"), ("Tempo", "Por quanto tempo investe"), ("Rentabilidade", "Quanto o dinheiro rende")]),
        _ex("vf", "Na conta da independência financeira, o certo é usar o retorno real, acima da inflação.", "O retorno nominal superestima o resultado.", correta=True),
        _ex("escolha", "Reduzir o custo de vida ajuda porque:", "Diminui o valor necessário e aumenta o que dá para guardar.",
            opcoes=["Diminui o patrimônio necessário e aumenta o aporte", "Aumenta os impostos", "Não faz diferença", "Reduz a rentabilidade"], correta=0),
        _ex("completar", "Independência financeira é quando os ___ dos investimentos pagam o seu custo de vida.", "Aí trabalhar vira uma escolha.",
            opcoes=["rendimentos", "boletos", "empréstimos", "limites"], correta=0),
    ]),
    # -------- Golpes
    dict(id="le_golpes_comuns", unidade="ue_golpes", titulo="Golpes mais comuns", icone="🎣", aula="ae_golpes_comuns", exercicios=[
        _ex("escolha", "Alguém liga dizendo ser do seu banco e pede para você transferir o dinheiro para uma \"conta segura\". O que fazer?",
            "Banco não pede transferência por telefone. Desligue e ligue para o número oficial.",
            opcoes=["Transferir logo", "Desligar e ligar para o número oficial do banco", "Passar a senha", "Mandar o código por SMS"], correta=1),
        _ex("pares", "Ligue cada golpe ao seu truque.", "Os truques se repetem: urgência, medo e autoridade.",
            pares=[("Falso parente", "\"Troquei de número, me faz um Pix\""), ("Falso funcionário", "\"Sua conta foi invadida, transfira\""), ("Boleto falso", "Imita uma empresa conhecida")]),
        _ex("vf", "Pedido de dinheiro com muita pressa é um sinal de alerta.", "A urgência é usada para você não pensar.", correta=True),
        _ex("completar", "Combine uma palavra ___ com a família para confirmar pedidos por mensagem.", "Assim fica fácil desmascarar o falso parente.",
            opcoes=["secreta", "pública", "difícil", "em inglês"], correta=0),
        _ex("vf", "Investimento que promete ganho alto e garantido costuma ser seguro.", "É o sinal clássico de pirâmide ou fraude.", correta=False),
    ]),
    dict(id="le_protecao", unidade="ue_golpes", titulo="Como se proteger", icone="🔒", aula="ae_protecao", exercicios=[
        _ex("escolha", "Antes de confirmar um Pix, o que conferir?", "O nome que aparece na tela deve ser o de quem você quer pagar.",
            opcoes=["O nome de quem vai receber", "A cor do app", "A hora", "Nada"], correta=0),
        _ex("vf", "Clicar em links recebidos por mensagem é seguro se a mensagem parecer oficial.", "Golpistas imitam mensagens oficiais. Use o app ou o site oficial.", correta=False),
        _ex("pares", "Ligue cada hábito ao que ele protege.", "Hábitos simples evitam a maioria dos golpes.",
            pares=[("Verificação em duas etapas", "A conta, mesmo se a senha vazar"), ("Limite de Pix baixo", "O saldo, num golpe ou roubo"), ("App oficial", "Contra sites e apps falsos")]),
        _ex("escolha", "Antes de investir com uma empresa desconhecida, o que fazer?", "A CVM informa quem é autorizado a atuar no mercado.",
            opcoes=["Consultar se ela tem registro na CVM", "Confiar no anúncio", "Investir pouco para testar", "Pedir para um amigo investir primeiro"], correta=0),
        _ex("completar", "Use senhas fortes e ___ em cada serviço.", "Se uma vazar, as outras continuam protegidas.",
            opcoes=["diferentes", "iguais", "curtas", "anotadas no celular"], correta=0),
    ]),
    dict(id="le_caiu", unidade="ue_golpes", titulo="Caí num golpe", icone="🆘", aula="ae_caiu", exercicios=[
        _ex("ordenar", "Coloque na ordem o que fazer depois de cair num golpe.", "Rapidez aumenta a chance de recuperar o dinheiro.",
            itens=["Avisar o banco imediatamente", "Pedir o MED, se foi Pix", "Registrar boletim de ocorrência", "Trocar as senhas"]),
        _ex("completar", "No Pix, o ___ permite ao banco tentar devolver o dinheiro.", "MED é o Mecanismo Especial de Devolução.",
            opcoes=["MED", "DAS", "CET", "FGC"], correta=0),
        _ex("vf", "Esperar alguns dias antes de avisar o banco não faz diferença.", "Quanto antes, maior a chance de o dinheiro ainda estar na conta do golpista.", correta=False),
        _ex("escolha", "O que guardar depois de um golpe?", "Provas ajudam o banco e a polícia.",
            opcoes=["Prints, comprovantes e números", "Nada", "Só a senha nova", "O app desinstalado"], correta=0),
        _ex("escolha", "Se o banco não resolver, onde registrar reclamação?", "Os canais oficiais ajudam a cobrar uma resposta.",
            opcoes=["No Banco Central e no consumidor.gov.br", "Nas redes sociais do golpista", "Em lugar nenhum", "Na loja onde comprou o celular"], correta=0),
    ]),
    # -------- Economia
    dict(id="le_selic_inflacao", unidade="ue_economia", titulo="Juros e inflação", icone="🔥", aula="ae_selic_inflacao", exercicios=[
        _ex("escolha", "Quando a inflação sobe demais, o que o Copom costuma fazer?", "Juros mais altos esfriam a economia e ajudam a segurar os preços.",
            opcoes=["Aumentar a Selic", "Diminuir a Selic", "Imprimir mais dinheiro", "Nada"], correta=0),
        _ex("vf", "Com a Selic alta, a renda fixa tende a render mais e o crédito fica mais caro.", "Os juros mexem nos dois lados: investimentos e dívidas.", correta=True),
        _ex("completar", "A inflação é o aumento ___ dos preços.", "Não é um preço só: é a média de muitos preços.",
            opcoes=["geral", "de um produto", "do dólar", "dos salários"], correta=0),
        _ex("vf", "Uma mudança na Selic chega aos preços no dia seguinte.", "Os juros agem com defasagem: leva meses.", correta=False),
        _ex("pares", "Ligue cada instituição ao seu papel.", "O Copom define a Selic; o IBGE mede a inflação.",
            pares=[("Copom", "Define a taxa Selic"), ("IBGE", "Mede a inflação oficial")]),
    ]),
    dict(id="le_pib", unidade="ue_economia", titulo="PIB e emprego", icone="🏭", aula="ae_pib", exercicios=[
        _ex("completar", "O ___ é a soma de tudo o que o país produz num período.", "Ele mostra se a economia cresce ou encolhe.",
            opcoes=["PIB", "IPCA", "CDI", "FGC"], correta=0),
        _ex("vf", "Quando o PIB cai por um tempo, pode ser sinal de recessão.", "Na recessão, a produção e o emprego costumam cair.", correta=True),
        _ex("escolha", "Com a economia crescendo, o que costuma acontecer com o emprego?", "Empresas vendendo mais contratam mais.",
            opcoes=["Aumenta", "Diminui", "Não muda", "Some"], correta=0),
        _ex("escolha", "Por que a reserva de emergência faz ainda mais diferença em crises?", "Em crises, o risco de perder renda aumenta.",
            opcoes=["Porque o risco de perder a renda aumenta", "Porque rende mais", "Porque é obrigatória", "Não faz diferença"], correta=0),
        _ex("pares", "Ligue cada situação da economia ao efeito comum.", "Esses números se influenciam.",
            pares=[("Economia muito aquecida", "Pressão sobre a inflação"), ("Recessão", "Mais desemprego")]),
    ]),
    dict(id="le_cambio", unidade="ue_economia", titulo="Câmbio e dólar", icone="💱", aula="ae_cambio", exercicios=[
        _ex("completar", "Câmbio é o ___ de uma moeda em outra.", "Por exemplo, quantos reais custa um dólar.",
            opcoes=["preço", "imposto", "juro", "limite"], correta=0),
        _ex("pares", "Ligue cada efeito ao dólar alto ou baixo.", "O câmbio mexe no preço de muita coisa.",
            pares=[("Viagem para fora mais cara", "Dólar alto"), ("Importados mais baratos", "Dólar baixo")]),
        _ex("escolha", "Quem costuma ganhar com o dólar alto?", "Eles recebem em dólar e gastam boa parte em reais.",
            opcoes=["Exportadores", "Importadores", "Quem vai viajar para fora", "Ninguém"], correta=0),
        _ex("vf", "Comprar a moeda de uma viagem futura aos poucos reduz o risco de pagar tudo num pico.", "Comprar aos poucos faz uma média dos preços.", correta=True),
        _ex("escolha", "Ter parte dos investimentos em outras moedas pode:", "É uma forma de não concentrar todo o risco no real.",
            opcoes=["Diversificar o risco", "Garantir lucro", "Eliminar todo o risco", "Evitar todos os impostos"], correta=0),
    ]),
]

for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
