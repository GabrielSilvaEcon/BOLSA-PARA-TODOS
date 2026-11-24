"""Aprender · área CRIPTOMOEDAS (fase 4) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Três trilhas: fundamentos (Bitcoin, blockchain, altcoins e stablecoins), segurança (carteiras e golpes) e avançado (análise de
projetos, DeFi, riscos). Criptoativos são muito voláteis e podem perder quase todo o valor: o texto diz isso sem rodeios.
Nada recomenda moeda, corretora ou carteira específica; impostos e regras mudam (remete às fontes oficiais).
"""
from __future__ import annotations

AREA = "cripto"

UNIDADES = [
    dict(id="uk_fund", area=AREA, titulo="Fundamentos", icone="🪙", icone_svg="grafico", cor="#F7C84A",
         descricao="Bitcoin, blockchain, altcoins e stablecoins.",
         licoes=["lk_bitcoin", "lk_blockchain", "lk_altcoins"]),
    dict(id="uk_seg", area=AREA, titulo="Segurança", icone="🔐", icone_svg="escudo", cor="#2DD4A0",
         descricao="Carteiras digitais, chaves e golpes comuns.",
         licoes=["lk_carteiras", "lk_golpes"]),
    dict(id="uk_avanc", area=AREA, titulo="Além do básico", icone="🧪", icone_svg="alvo", cor="#B07CFF",
         descricao="Como analisar um projeto, DeFi e os riscos.",
         licoes=["lk_analise", "lk_defi", "lk_riscos"]),
]

NIVEIS = {"lk_analise": "intermediario", "lk_defi": "avancado", "lk_riscos": "intermediario"}

_A = dict(assunto="cripto", dificuldade="iniciante", fontes=["cvm", "bcb"], relacionadas=[])
AULAS = [
    dict(_A, id="ak_bitcoin", titulo="Introdução ao Bitcoin", min=5,
         iniciante="O **Bitcoin** é uma moeda digital criada em 2009 que funciona **sem um banco central**: as transações são registradas por uma rede de "
                   "computadores no mundo todo.\n\n"
                   "**Características:** a quantidade máxima é de **21 milhões** de bitcoins; ele pode ser dividido em partes bem pequenas (a menor se chama "
                   "\"satoshi\"); e, a cada cerca de quatro anos, a emissão de bitcoins novos cai pela metade (o **halving**).\n\n"
                   "**Exemplo do dia a dia:** dá para comprar uma fração, como R$ 50 em bitcoin, sem precisar de um bitcoin inteiro.\n\n"
                   "**Na prática:** o preço oscila muito, para cima e para baixo. Só invista o que você aceita ver cair bastante.",
         intermediario="A escassez programada e a descentralização são os principais argumentos de quem vê o Bitcoin como reserva de valor. Os argumentos "
                       "contrários incluem a alta volatilidade, o risco regulatório e o fato de não gerar fluxo de caixa (como lucro ou juros)."),
    dict(_A, id="ak_blockchain", titulo="Blockchain", min=5,
         iniciante="**Blockchain** é um registro público de transações, organizado em **blocos** ligados uns aos outros, como as páginas de um caderno que "
                   "não podem ser arrancadas.\n\n"
                   "**Como fica seguro:** cópias do registro ficam em milhares de computadores. Para mudar uma transação antiga, seria preciso mudar a maioria das "
                   "cópias ao mesmo tempo, o que é extremamente difícil.\n\n"
                   "**Mineração e validação:** quem valida os blocos recebe uma recompensa. No Bitcoin, isso é feito pela mineração (prova de trabalho); em "
                   "outras redes, por quem deixa moedas \"travadas\" como garantia (prova de participação).\n\n"
                   "**Na prática:** uma transação na blockchain, depois de confirmada, normalmente **não pode ser desfeita**. Confira o endereço antes de enviar.",
         intermediario="Prova de trabalho (PoW) gasta energia para tornar ataques caros; prova de participação (PoS) exige capital travado e pune quem valida "
                       "errado. Cada modelo troca segurança, velocidade e custo de jeitos diferentes."),
    dict(_A, id="ak_altcoins", titulo="Altcoins e stablecoins", min=4,
         iniciante="**Altcoins** são todas as criptomoedas além do Bitcoin. Algumas têm usos próprios, como redes para contratos inteligentes; muitas são "
                   "projetos pequenos, com risco muito alto.\n\n"
                   "**Stablecoins** são criptomoedas que tentam manter o valor **estável**, geralmente atreladas ao dólar. Elas são usadas para transferir valor "
                   "e como \"porto\" entre operações.\n\n"
                   "**Exemplo do dia a dia:** uma stablecoin atrelada ao dólar busca valer sempre cerca de US$ 1.\n\n"
                   "**Na prática:** \"estável\" não quer dizer sem risco. Depende de quem emite e de como as reservas são guardadas.",
         intermediario="Existem stablecoins lastreadas em reservas (dinheiro e títulos), em outras criptos e algorítmicas. As algorítmicas já perderam a "
                       "paridade de forma dramática. Verifique a transparência das reservas antes de confiar."),
    dict(_A, id="ak_carteiras", titulo="Carteiras digitais", min=5,
         iniciante="Uma **carteira** guarda as **chaves** que dão acesso às suas criptomoedas. Há dois jeitos de guardar:\n\n"
                   "**Custódia em corretora:** a corretora guarda as chaves por você. É mais simples, mas você depende da segurança e da saúde da empresa.\n\n"
                   "**Autocustódia:** você guarda as próprias chaves (em app ou dispositivo físico). Dá mais controle, mas a responsabilidade é toda sua.\n\n"
                   "**Frase de recuperação (seed):** são 12 ou 24 palavras que recuperam a carteira. Quem tem essas palavras tem as suas moedas.\n\n"
                   "**Na prática:** **nunca** digite nem fotografe a frase de recuperação, e nunca a envie para ninguém, nem para o \"suporte\".",
         intermediario="\"Not your keys, not your coins\": na corretora, o que você tem é um direito sobre a empresa. Na autocustódia, o risco passa a ser perder "
                       "as chaves. Muita gente combina os dois: um valor pequeno na corretora para operar e o resto em autocustódia."),
    dict(_A, id="ak_golpes", titulo="Golpes e segurança em cripto", min=4,
         iniciante="O mundo cripto atrai muitos golpes. Os mais comuns:\n\n"
                   "**Promessa de rendimento garantido** (às vezes uma pirâmide disfarçada); **falso suporte** que pede a sua frase de recuperação; **sites "
                   "falsos** que imitam corretoras; e **\"dobre seu bitcoin\"** em redes sociais.\n\n"
                   "**Exemplo do dia a dia:** um perfil famoso \"promete\" devolver o dobro de quem enviar cripto. É golpe: o dinheiro nunca volta.\n\n"
                   "**Na prática:** ative a verificação em duas etapas, desconfie de pressa e de ganho fácil, e confira se a empresa é autorizada a funcionar no Brasil.",
         intermediario="Golpes usam urgência, autoridade falsa e prova social (\"todo mundo está ganhando\"). Como transações em blockchain não se desfazem, "
                       "prevenir é quase a única defesa. Denuncie à polícia e às autoridades, e avise a corretora."),
    dict(_A, id="ak_analise", titulo="Como analisar um projeto cripto", min=5,
         iniciante="Antes de comprar uma cripto, faça algumas perguntas:\n\n"
                   "**Para que serve?** Que problema ela resolve e quem usa de verdade?\n"
                   "**Quem está por trás?** A equipe é conhecida? O código é aberto?\n"
                   "**Tokenomics:** quantas moedas existem, quantas ainda vão ser criadas e quantas estão com os fundadores?\n"
                   "**Liquidez:** dá para comprar e vender com facilidade?\n\n"
                   "**Exemplo do dia a dia:** um token com 90% das moedas nas mãos dos criadores pode cair muito quando eles venderem.\n\n"
                   "**Na prática:** se você não consegue explicar o projeto em uma frase, talvez seja melhor não comprar.",
         intermediario="Compare o **valor de mercado** com o **valor totalmente diluído** (todas as moedas que vão existir): uma diferença grande indica "
                       "emissão futura que pode pressionar o preço. Veja também a atividade real na rede e o histórico de segurança."),
    dict(_A, id="ak_defi", titulo="DeFi", min=5,
         iniciante="**DeFi** (finanças descentralizadas) são serviços financeiros feitos com **contratos inteligentes** na blockchain, sem um banco no meio: "
                   "empréstimos, trocas de moedas e rendimentos.\n\n"
                   "**Exemplos:** corretoras descentralizadas (DEX), onde as trocas acontecem direto entre carteiras, e protocolos de empréstimo com garantia em cripto.\n\n"
                   "**Riscos:** falhas no código do contrato, ataques de hackers, \"rug pull\" (os criadores somem com o dinheiro) e perda temporária em pools de liquidez.\n\n"
                   "**Na prática:** rendimento alto em DeFi costuma vir de risco alto. Comece entendendo, não investindo.",
         intermediario="Em pools de liquidez, a **perda impermanente** acontece quando o preço das duas moedas se afasta. Empréstimos com garantia podem ser "
                       "**liquidados** automaticamente se a garantia cair. Auditorias reduzem, mas não eliminam, o risco de código."),
    dict(_A, id="ak_riscos", titulo="Riscos e volatilidade", min=4,
         iniciante="Criptomoedas estão entre os investimentos **mais voláteis**: quedas de 50% ou mais já aconteceram várias vezes.\n\n"
                   "**Riscos principais:** volatilidade, golpes, falha da corretora, perda das chaves, mudanças de regras e projetos que simplesmente acabam.\n\n"
                   "**Exemplo (hipotético):** R$ 1.000 que caem 60% viram R$ 400. Para voltar aos R$ 1.000, é preciso subir 150%.\n\n"
                   "**Na prática:** se for investir, use uma **parte pequena** da carteira, depois de ter reserva de emergência, e nunca dinheiro de curto prazo.",
         intermediario="Pense em cripto como uma fração da carteira, definida pelo seu perfil, e rebalanceie. No Brasil, há regras de Imposto de Renda e de "
                       "declaração para criptoativos: confira na Receita Federal. O Banco Central regula as prestadoras de serviços de ativos virtuais."),
]

LICOES = [
    dict(id="lk_bitcoin", unidade="uk_fund", titulo="Introdução ao Bitcoin", icone="₿", aula="ak_bitcoin", exercicios=[
        dict(tipo="escolha", pergunta="Qual é a quantidade máxima de bitcoins que pode existir?",
             opcoes=["Ilimitada", "21 milhões", "1 bilhão", "100 mil"], correta=1,
             explicacao="O limite de 21 milhões está nas regras do próprio Bitcoin."),
        dict(tipo="vf", pergunta="É preciso comprar um bitcoin inteiro para investir em Bitcoin.", correta=False,
             explicacao="Ele pode ser dividido em partes bem pequenas; dá para comprar frações."),
        dict(tipo="completar", pergunta="A cada cerca de quatro anos, a emissão de bitcoins novos cai pela metade. Esse evento se chama ___.",
             opcoes=["halving", "spread", "staking", "split"], correta=0,
             explicacao="O halving reduz o ritmo de criação de novas moedas."),
        dict(tipo="vf", pergunta="O Bitcoin funciona sem um banco central controlando a emissão.", correta=True,
             explicacao="As regras estão no software e as transações são validadas pela rede."),
        dict(tipo="escolha", pergunta="Qual é um argumento contra o Bitcoin como investimento?",
             opcoes=["Ele não tem limite de emissão", "A alta volatilidade e o risco regulatório", "Ele não pode ser dividido", "Ele é emitido pelo governo"], correta=1,
             explicacao="Ele oscila muito, não gera fluxo de caixa e depende de regras que podem mudar."),
    ]),
    dict(id="lk_blockchain", unidade="uk_fund", titulo="Blockchain", icone="⛓️", aula="ak_blockchain", exercicios=[
        dict(tipo="escolha", pergunta="O que é uma blockchain?",
             opcoes=["Um banco digital", "Um registro público de transações em blocos ligados", "Uma senha", "Uma corretora"], correta=1,
             explicacao="É como um caderno público em que as páginas não podem ser arrancadas."),
        dict(tipo="vf", pergunta="Uma transação confirmada na blockchain normalmente pode ser desfeita pelo banco.", correta=False,
             explicacao="Em geral ela não pode ser desfeita. Por isso, confira o endereço antes de enviar."),
        dict(tipo="pares", pergunta="Ligue cada forma de validação à sua ideia.",
             pares=[("Prova de trabalho", "Mineração com gasto de energia"), ("Prova de participação", "Moedas travadas como garantia")],
             explicacao="As duas tornam caro atacar a rede, de jeitos diferentes."),
        dict(tipo="escolha", pergunta="Por que é difícil alterar uma transação antiga?",
             opcoes=["Porque é proibido por lei", "Porque cópias do registro ficam em milhares de computadores", "Porque a senha é longa", "Porque não existe internet"], correta=1,
             explicacao="Seria preciso mudar a maioria das cópias ao mesmo tempo."),
        dict(tipo="completar", pergunta="Quem valida os blocos recebe uma ___.",
             opcoes=["recompensa", "multa", "anuidade", "garantia do FGC"], correta=0,
             explicacao="A recompensa incentiva os participantes a manter a rede funcionando."),
    ]),
    dict(id="lk_altcoins", unidade="uk_fund", titulo="Altcoins e stablecoins", icone="🧩", aula="ak_altcoins", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada tipo de cripto à sua descrição.",
             pares=[("Altcoin", "Qualquer cripto além do Bitcoin"), ("Stablecoin", "Busca valor estável, geralmente em dólar")],
             explicacao="Altcoins variam muito; stablecoins tentam não variar."),
        dict(tipo="vf", pergunta="Stablecoins não têm nenhum risco.", correta=False,
             explicacao="Dependem de quem emite e das reservas; algumas já perderam a paridade."),
        dict(tipo="escolha", pergunta="Uma stablecoin atrelada ao dólar busca valer:",
             opcoes=["Cerca de US$ 1", "O mesmo que um bitcoin", "R$ 1", "Cada dia um valor"], correta=0,
             explicacao="A ideia é manter a paridade com a moeda de referência."),
        dict(tipo="escolha", pergunta="O que costuma acontecer com muitos projetos pequenos de altcoins?",
             opcoes=["Têm risco muito alto e podem acabar", "São garantidos pelo governo", "Rendem juros fixos", "Não oscilam"], correta=0,
             explicacao="Muitas altcoins perdem quase todo o valor."),
        dict(tipo="completar", pergunta="Antes de confiar numa stablecoin, verifique a transparência das ___.",
             opcoes=["reservas", "propagandas", "cores do site", "redes sociais"], correta=0,
             explicacao="Saber como as reservas são guardadas ajuda a avaliar o risco."),
    ]),
    dict(id="lk_carteiras", unidade="uk_seg", titulo="Carteiras digitais", icone="👛", aula="ak_carteiras", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada forma de guardar cripto à sua característica.",
             pares=[("Custódia em corretora", "Mais simples, depende da empresa"), ("Autocustódia", "Mais controle, responsabilidade sua")],
             explicacao="Cada forma troca praticidade por controle."),
        dict(tipo="escolha", pergunta="O \"suporte\" pede a sua frase de recuperação para resolver um problema. O que fazer?",
             opcoes=["Enviar logo", "Nunca enviar: é golpe", "Enviar só metade", "Mandar por foto"], correta=1,
             explicacao="Quem tem a frase de recuperação tem as suas moedas. Nenhum suporte de verdade pede isso."),
        dict(tipo="completar", pergunta="A frase de recuperação tem normalmente 12 ou ___ palavras.",
             opcoes=["24", "4", "100", "6"], correta=0,
             explicacao="São essas palavras que permitem recuperar a carteira."),
        dict(tipo="vf", pergunta="Guardar a frase de recuperação numa foto no celular é seguro.", correta=False,
             explicacao="Fotos e arquivos podem vazar. Guarde em papel, em local seguro."),
        dict(tipo="vf", pergunta="Na autocustódia, perder as chaves pode significar perder as moedas para sempre.", correta=True,
             explicacao="Sem as chaves nem a frase de recuperação, ninguém consegue recuperar o acesso."),
    ]),
    dict(id="lk_golpes", unidade="uk_seg", titulo="Golpes em cripto", icone="🚨", aula="ak_golpes", exercicios=[
        dict(tipo="escolha", pergunta="Um perfil famoso promete devolver o dobro de quem enviar cripto. O que é isso?",
             opcoes=["Uma promoção legítima", "Um golpe", "Um investimento seguro", "Um airdrop oficial"], correta=1,
             explicacao="\"Dobre sua cripto\" é um golpe clássico: o dinheiro enviado nunca volta."),
        dict(tipo="vf", pergunta="Promessa de rendimento garantido e alto em cripto é um sinal de alerta.", correta=True,
             explicacao="Muitas vezes é uma pirâmide disfarçada."),
        dict(tipo="pares", pergunta="Ligue cada golpe de cripto ao seu truque.",
             pares=[("Falso suporte", "Pede a sua frase de recuperação"), ("Site falso", "Imita uma corretora conhecida"), ("Pirâmide", "Paga os antigos com o dinheiro dos novos")],
             explicacao="Os golpes usam urgência, autoridade falsa e promessa de ganho fácil."),
        dict(tipo="escolha", pergunta="Qual medida protege a sua conta na corretora?",
             opcoes=["Usar a mesma senha em tudo", "Ativar a verificação em duas etapas", "Compartilhar a senha com amigos", "Desligar os avisos"], correta=1,
             explicacao="A verificação em duas etapas dificulta o acesso mesmo se a senha vazar."),
        dict(tipo="completar", pergunta="Como transações em blockchain não se desfazem, ___ é quase a única defesa.",
             opcoes=["prevenir", "reclamar", "esperar", "comprar mais"], correta=0,
             explicacao="Depois de enviar, recuperar o dinheiro é muito difícil."),
    ]),
    dict(id="lk_analise", unidade="uk_avanc", titulo="Analisar um projeto", icone="🔬", aula="ak_analise", exercicios=[
        dict(tipo="escolha", pergunta="Qual pergunta ajuda a analisar um projeto cripto?",
             opcoes=["Para que ele serve e quem usa de verdade?", "Qual é a cor do logo?", "Quantos seguidores ele tem?", "Ele já subiu muito esta semana?"], correta=0,
             explicacao="Uso real e problema resolvido importam mais do que barulho nas redes."),
        dict(tipo="completar", pergunta="___ é o estudo de quantas moedas existem, quantas vão ser criadas e com quem estão.",
             opcoes=["Tokenomics", "Halving", "Staking", "Spread"], correta=0,
             explicacao="A distribuição das moedas afeta muito o preço."),
        dict(tipo="escolha", pergunta="Caso: 90% das moedas estão com os criadores do token. Qual é o risco?",
             opcoes=["Nenhum", "Quedas fortes quando eles venderem", "Garantia de alta", "O token vira stablecoin"], correta=1,
             explicacao="Concentração alta significa que poucos podem derrubar o preço."),
        dict(tipo="vf", pergunta="Uma diferença grande entre o valor de mercado e o valor totalmente diluído indica emissão futura.", correta=True,
             explicacao="Muitas moedas ainda vão entrar no mercado e podem pressionar o preço."),
        dict(tipo="vf", pergunta="Se você não consegue explicar o projeto em uma frase, comprar é uma boa ideia.", correta=False,
             explicacao="Investir no que não entende aumenta muito o risco."),
    ]),
    dict(id="lk_defi", unidade="uk_avanc", titulo="DeFi", icone="🏗️", aula="ak_defi", exercicios=[
        dict(tipo="escolha", pergunta="O que é DeFi?",
             opcoes=["Serviços financeiros com contratos inteligentes, sem banco no meio", "Um banco digital", "Uma moeda estável", "Um imposto"], correta=0,
             explicacao="DeFi usa contratos inteligentes na blockchain para empréstimos, trocas e rendimentos."),
        dict(tipo="pares", pergunta="Ligue cada risco de DeFi ao que ele significa.",
             pares=[("Falha no contrato", "Erro no código explorado por hackers"), ("Rug pull", "Os criadores somem com o dinheiro"),
                    ("Liquidação", "Garantia vendida quando cai demais")],
             explicacao="Rendimento alto em DeFi costuma vir com esses riscos."),
        dict(tipo="vf", pergunta="Uma auditoria no código elimina totalmente o risco de um protocolo DeFi.", correta=False,
             explicacao="Auditorias reduzem, mas não eliminam, o risco."),
        dict(tipo="completar", pergunta="Em pools de liquidez, a perda ___ acontece quando o preço das duas moedas se afasta.",
             opcoes=["impermanente", "garantida", "tributária", "cambial"], correta=0,
             explicacao="É uma perda em relação a simplesmente segurar as moedas."),
        dict(tipo="escolha", pergunta="Qual é a atitude mais prudente com DeFi?",
             opcoes=["Investir tudo onde o rendimento é maior", "Primeiro entender, depois decidir com pouco", "Seguir dicas anônimas", "Ignorar os riscos"], correta=1,
             explicacao="Comece entendendo, não investindo."),
    ]),
    dict(id="lk_riscos", unidade="uk_avanc", titulo="Riscos e volatilidade", icone="🎢", aula="ak_riscos", exercicios=[
        dict(tipo="escolha", pergunta="Caso: R$ 1.000 caem 60%. Quanto precisam subir depois para voltar a R$ 1.000?",
             opcoes=["60%", "100%", "150%", "40%"], correta=2,
             explicacao="Caem para R$ 400; de 400 para 1.000 é preciso subir 150%."),
        dict(tipo="vf", pergunta="Quedas de 50% ou mais já aconteceram várias vezes com criptomoedas.", correta=True,
             explicacao="A volatilidade é uma característica deste mercado."),
        dict(tipo="ordenar", pergunta="Coloque na ordem o caminho prudente antes de investir em cripto.",
             itens=["Ter reserva de emergência", "Definir uma fatia pequena da carteira", "Investir só dinheiro de longo prazo"],
             explicacao="Cripto vem depois da base e com uma fatia que você aceita ver oscilar muito."),
        dict(tipo="escolha", pergunta="Quem regula as prestadoras de serviços de ativos virtuais no Brasil?",
             opcoes=["O Banco Central", "A Receita Federal", "O IBGE", "A própria blockchain"], correta=0,
             explicacao="O marco legal dos criptoativos deu essa atribuição ao Banco Central."),
        dict(tipo="vf", pergunta="Dinheiro que você vai precisar no mês que vem pode ficar em cripto sem problema.", correta=False,
             explicacao="Com tanta oscilação, dinheiro de curto prazo não deve ficar em cripto."),
    ]),
]

for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
