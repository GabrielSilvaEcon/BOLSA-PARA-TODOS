"""Cartas colecionáveis do TickerHunters · CADASTRO GLOBAL (só dados, independente de qualquer jogador).

Para incluir uma empresa nova, basta acrescentar um item em EMPRESAS (o app e o servidor leem tudo daqui; nada fica em componentes
visuais). Os dados financeiros REAIS (P/L, DY e ROE) não ficam aqui: vêm do snapshot do Ticker Battle (battle_dados.py), com fonte e
data. A raridade sai de uma pontuação própria do TickerHunters:
    valor de mercado (0–50) + liquidez (0–30) + relevância de mercado (0–20) = 0–100
    0–34 Comum · 35–54 Rara · 55–79 Épica · 80–100 Lendária
A raridade é FIXADA no cadastro (campo `raridade_fixa`): revisões anuais da pontuação valem só para cartas novas ou correções de cadastro.
Os pontos abaixo são a CLASSIFICAÇÃO INICIAL do TickerHunters (ordem de grandeza de valor de mercado, liquidez e relevância), a revisar.
Sem logotipos oficiais: cada carta usa uma ilustração temática (arquivo em app/assets/cartas/) ou o ícone do setor enquanto não houver arte.
"""
from __future__ import annotations

RARIDADES = ("comum", "rara", "epica", "lendaria")
ROTULO_RARIDADE = {"comum": "Comum", "rara": "Rara", "epica": "Épica", "lendaria": "Lendária"}
FAIXAS = ((80, "lendaria"), (55, "epica"), (35, "rara"), (0, "comum"))
PESOS = {"mercado": 50, "liquidez": 30, "relevancia": 20}
REVISAO = "nov/2026"


def pontuacao(mercado: float, liquidez: float, relevancia: float) -> int:
    """Soma dos três critérios, cada um limitado ao seu teto."""
    return int(round(max(0, min(PESOS["mercado"], mercado)) + max(0, min(PESOS["liquidez"], liquidez)) + max(0, min(PESOS["relevancia"], relevancia))))


def raridade_da_pontuacao(p: float) -> str:
    for minimo, r in FAIXAS:
        if p >= minimo:
            return r
    return "comum"


def _e(tk, nome, setor, icone, atividade, fato, mercado, liquidez, relevancia, arte=None):
    p = pontuacao(mercado, liquidez, relevancia)
    return {"tk": tk, "nome": nome, "setor": setor, "icone": icone, "atividade": atividade, "fato": fato,
            "pontos": {"mercado": mercado, "liquidez": liquidez, "relevancia": relevancia, "total": p},
            "raridade_fixa": raridade_da_pontuacao(p), "arte": arte, "desde": REVISAO}


EMPRESAS = [
    _e("PETR4", "Petrobras", "Petróleo e gás", "🛢️", "Explora, produz e refina petróleo e gás natural.",
       "Maior produtora de petróleo do Brasil, com forte atuação no pré-sal.", 50, 30, 20, arte="arte_PETR4.webp"),
    _e("VALE3", "Vale", "Mineração", "⛏️", "Produz minério de ferro, níquel e cobre.",
       "Uma das maiores produtoras de minério de ferro do mundo.", 48, 29, 19, arte="arte_VALE3.webp"),
    _e("ITUB4", "Itaú Unibanco", "Bancos", "🏦", "Oferece contas, crédito, cartões, seguros e investimentos.",
       "Um dos maiores bancos privados da América Latina.", 48, 28, 19, arte="arte_ITUB4.webp"),
    _e("BBAS3", "Banco do Brasil", "Bancos", "🏦", "Banco com forte atuação no crédito ao agronegócio.",
       "Um dos bancos mais antigos do Brasil, fundado em 1808.", 36, 27, 15),
    _e("BBDC4", "Bradesco", "Bancos", "🏦", "Oferece contas, crédito, cartões, seguros e investimentos.",
       "Tem uma das maiores redes de atendimento bancário do país.", 36, 26, 15),
    _e("ABEV3", "Ambev", "Bebidas", "🍺", "Produz e vende cervejas, refrigerantes e outras bebidas.",
       "Faz parte de um dos maiores grupos cervejeiros do mundo.", 38, 22, 14, arte="arte_ABEV3.webp"),
    _e("WEGE3", "WEG", "Bens industriais", "⚙️", "Fabrica motores elétricos, geradores e equipamentos de energia.",
       "Nasceu em Jaraguá do Sul (SC) e exporta para muitos países.", 40, 20, 14, arte="arte_WEGE3.webp"),
    _e("B3SA3", "B3", "Serviços financeiros", "📈", "Opera a bolsa de valores brasileira e seus sistemas de negociação.",
       "É por ela que passam as negociações de ações no Brasil.", 30, 24, 16),
    _e("SANB11", "Santander Brasil", "Bancos", "🏦", "Banco de varejo e de empresas.",
       "Faz parte de um grupo financeiro espanhol com presença global.", 30, 14, 10),
    _e("SUZB3", "Suzano", "Papel e celulose", "🌳", "Produz celulose de eucalipto e papel.",
       "Uma das maiores produtoras de celulose de eucalipto do mundo.", 26, 16, 10),
    _e("EMBR3", "Embraer", "Aeronáutica", "✈️", "Fabrica aviões comerciais, executivos e de defesa.",
       "Uma das maiores fabricantes de jatos comerciais do mundo.", 24, 18, 11),
    _e("TIMS3", "TIM", "Telecomunicações", "📡", "Oferece telefonia móvel, internet e serviços digitais.",
       "Uma das principais operadoras de celular do Brasil.", 22, 12, 9),
    _e("UGPA3", "Ultrapar", "Combustíveis", "⛽", "Distribui combustíveis e gás pelo país.",
       "É a dona da rede de postos Ipiranga.", 14, 12, 7),
    _e("MGLU3", "Magazine Luiza", "Varejo", "🛍️", "Vende eletrônicos, móveis e muitos outros produtos em lojas e pela internet.",
       "Conhecida pelo marketplace e pela assistente virtual Lu.", 10, 16, 7),
    _e("CPFE3", "CPFL Energia", "Energia elétrica", "⚡", "Gera, transmite e distribui energia elétrica.",
       "Atende milhões de clientes, principalmente no interior de São Paulo.", 18, 8, 7),
    _e("BRKM5", "Braskem", "Petroquímica", "🧪", "Produz resinas plásticas e produtos químicos.",
       "Uma das maiores petroquímicas das Américas.", 8, 10, 7),
    _e("CVCB3", "CVC Brasil", "Turismo", "🏖️", "Oferece pacotes de viagens, passagens e serviços turísticos.",
       "Uma das maiores operadoras de turismo do Brasil.", 2, 6, 5, arte="arte_CVCB3.webp"),
    _e("VAMO3", "Vamos", "Transporte", "🚛", "Aluga e vende caminhões, máquinas e equipamentos pesados.",
       "Atende empresas que preferem alugar a frota em vez de comprar.", 4, 6, 4, arte="arte_VAMO3.webp"),
    _e("LWSA3", "LWSA", "Tecnologia", "☁️", "Oferece soluções de tecnologia, como serviços de nuvem e software.",
       "Atua em áreas como cloud, e-commerce e softwares.", 3, 7, 4, arte="arte_LWSA3.webp"),
    # ---- Petróleo e Gás ----
    _e("BRAV3", "Brava Energia", "Petróleo e gás", "⛽", "Explora e produz petróleo e gás offshore no Brasil.",
       "Especializada em revitalizar campos maduros de petróleo.", 16, 14, 9),
    _e("CSAN3", "Cosan", "Petróleo e gás", "🔋", "Atua em distribuição de combustíveis, gás natural e logística.",
       "Controla a Raízen e a Compass, cobrindo energia e logística.", 28, 18, 12),
    _e("PRIO3", "PRIO", "Petróleo e gás", "🛢️", "Produz petróleo em campos maduros no pré-sal e pós-sal.",
       "Especialista em revitalizar campos de petróleo já descobertos.", 18, 16, 10),
    _e("RAIZ4", "Raízen", "Petróleo e gás", "🌱", "Produz etanol, açúcar e distribui combustíveis no Brasil.",
       "Maior distribuidora com rede Shell e líder em etanol de cana.", 20, 14, 10),
    _e("VBBR3", "Vibra Energia", "Combustíveis", "⛽", "Distribui combustíveis para postos e clientes industriais.",
       "Ex-BR Distribuidora, maior distribuidora independente do Brasil.", 18, 14, 10),
    # ---- Bancos ----
    _e("ABCB4", "Banco ABC Brasil", "Bancos", "🏦", "Oferece crédito e serviços financeiros para médias e grandes empresas.",
       "Especializado em empresas do agronegócio e do mercado corporativo.", 12, 10, 8),
    _e("BPAC11", "BTG Pactual", "Bancos", "🏦", "Maior banco de investimento da América Latina.",
       "Atua em M&A, fundos, gestão de fortunas e corretagem.", 36, 22, 15),
    _e("BPAN4", "Banco Pan", "Bancos", "🏦", "Oferece crédito consignado, financiamento de veículos e conta digital.",
       "Focado em crédito acessível para servidores públicos e aposentados.", 10, 10, 7),
    _e("BRSR6", "Banrisul", "Bancos", "🏦", "Banco público com foco em financiamento de consumo e agronegócio.",
       "Um dos maiores bancos regionais do Brasil, com base no Rio Grande do Sul.", 12, 10, 8),
    _e("INBR32", "Banco Inter", "Bancos", "🏦", "Banco digital com conta sem tarifas, cartão e marketplace.",
       "Foi pioneiro na conta digital gratuita e no marketplace bancário.", 16, 12, 10),
    _e("ITSA3", "Itaúsa", "Bancos", "🏦", "Holding que controla o Itaú Unibanco e outras empresas.",
       "A mais famosa holding bancária do Brasil, muito popular em dividendos.", 32, 22, 13, arte="arte_ITSA3.webp"),
    _e("ITSA4", "Itaúsa", "Bancos", "🏦", "Holding que controla o Itaú Unibanco e outras empresas.",
       "A mais famosa holding bancária do Brasil, muito popular em dividendos.", 32, 22, 13),
    _e("ROXO34", "Nubank", "Bancos", "💜", "Banco digital com cartão sem anuidade, conta e investimentos.",
       "Maior banco digital do mundo em número de clientes.", 34, 15, 15),
    # ---- Construção e Imobiliário ----
    _e("ALOS3", "Allos", "Construção e Imobiliário", "🏬", "Administra shopping centers e empreendimentos de uso misto.",
       "Resultado da fusão entre Aliansce Sonae e brMalls, maior empresa de shoppings.", 16, 12, 10),
    _e("CURY3", "Cury", "Construção e Imobiliário", "🏗️", "Constrói imóveis econômicos e de médio padrão em SP e RJ.",
       "Focada nos programas habitacionais do governo federal.", 10, 10, 7),
    _e("CYRE3", "Cyrela", "Construção e Imobiliário", "🏗️", "Incorpora e constrói imóveis residenciais de médio e alto padrão.",
       "Uma das incorporadoras mais tradicionais de São Paulo.", 18, 14, 10),
    _e("DIRR3", "Direcional", "Construção e Imobiliário", "🏗️", "Constrói imóveis residenciais pelo programa Minha Casa Minha Vida.",
       "Especialista em habitação popular em diversas regiões do país.", 10, 10, 7),
    _e("EZTC3", "Eztec", "Construção e Imobiliário", "🏗️", "Incorpora e constrói imóveis de médio e alto padrão em São Paulo.",
       "Conhecida pela alta margem e forte geração de caixa.", 12, 10, 7),
    _e("IGTI11", "Iguatemi", "Construção e Imobiliário", "🏬", "Administra shopping centers e outlets premium no Brasil.",
       "É dona dos shoppings Iguatemi, JK Iguatemi e outros premium.", 14, 10, 9),
    _e("MRVE3", "MRV", "Construção e Imobiliário", "🏗️", "Maior construtora de habitação popular do Brasil.",
       "Atua em mais de 160 cidades com foco no programa Minha Casa Minha Vida.", 16, 12, 9),
    _e("MULT3", "Multiplan", "Construção e Imobiliário", "🏬", "Desenvolve, administra e aluga espaços em shoppings e condomínios.",
       "É dona do BarraShopping, ParkShopping e outros shoppings líderes.", 20, 14, 10),
    _e("PLPL3", "Plano&Plano", "Construção e Imobiliário", "🏗️", "Constrói imóveis econômicos com foco no programa habitacional popular.",
       "Atua principalmente na Grande São Paulo com foco em baixa renda.", 6, 6, 4),
    # ---- Consumo ----
    _e("NATU3", "Natura", "Cosméticos", "🌸", "Fabrica e vende cosméticos, perfumes e produtos de beleza.",
       "A criadora do modelo de venda por consultoras no Brasil.", 18, 14, 11),
    _e("SMFT3", "Smart Fit", "Academia e bem-estar", "💪", "Opera rede de academias de baixo custo na América Latina.",
       "Maior rede de academias da América Latina com milhões de alunos.", 16, 14, 10),
    # ---- Educação ----
    _e("COGN3", "Cogna", "Educação", "📚", "Opera universidades, cursos técnicos e plataformas de EAD.",
       "Uma das maiores redes de ensino superior do Brasil.", 10, 14, 8),
    _e("SEER3", "Ser Educacional", "Educação", "📚", "Oferece ensino superior em campi físicos e à distância.",
       "Forte atuação no Nordeste com foco em mensalidades acessíveis.", 6, 8, 5),
    _e("YDUQ3", "YDUQS", "Educação", "📚", "Oferece ensino superior presencial e EAD em todo o Brasil.",
       "É dona das marcas Estácio, IBMEC e outras faculdades.", 10, 12, 7),
    # ---- Energia Elétrica ----
    _e("ALUP11", "Alupar", "Energia elétrica", "⚡", "Transmite energia elétrica de alta tensão no Brasil.",
       "Especializada na construção e operação de linhas de transmissão.", 14, 12, 9),
    _e("AURE3", "Auren Energia", "Energia elétrica", "⚡", "Gera energia limpa de fontes hidráulica e eólica.",
       "Nasceu da aquisição dos ativos da AES Brasil pelo grupo Votorantim.", 14, 10, 8),
    _e("AXIA3", "Axia Energia", "Energia elétrica", "⚡", "Distribui energia elétrica em 11 estados brasileiros.",
       "Surgiu da privatização da Eletrobras em 2022.", 14, 10, 8),
    _e("CMIG4", "Cemig", "Energia elétrica", "⚡", "Gera, transmite e distribui energia elétrica em Minas Gerais.",
       "Uma das maiores distribuidoras de energia do Brasil.", 20, 14, 10),
    _e("CPLE3", "Copel", "Energia elétrica", "⚡", "Gera, transmite e distribui energia elétrica no Paraná.",
       "Empresa privatizada em 2021 que atende todo o estado do Paraná.", 18, 14, 10),
    _e("EGIE3", "Engie Brasil", "Energia elétrica", "⚡", "Gera energia elétrica de fontes hidráulica, eólica e solar.",
       "Maior geradora de energia privada do Brasil.", 24, 16, 12),
    _e("ENGI11", "Energisa", "Energia elétrica", "⚡", "Distribui energia elétrica em 11 estados brasileiros.",
       "Maior empresa privada de distribuição de energia elétrica do país.", 20, 14, 10),
    _e("EQTL3", "Equatorial", "Energia elétrica", "⚡", "Distribui energia e atua em saneamento em diversas regiões.",
       "Conhecida por recuperar distribuidoras de energia com alto índice de perdas.", 28, 16, 12, arte="arte_EQTL3.webp"),
    _e("ISAE4", "ISA Energia", "Energia elétrica", "⚡", "Transmite energia elétrica de alta tensão por linhas de longa distância.",
       "Faz parte de grupo colombiano líder em transmissão na América Latina.", 14, 12, 9),
    _e("NEOE3", "Neoenergia", "Energia elétrica", "⚡", "Distribui, gera e transmite energia elétrica em várias regiões.",
       "Controlada pelo grupo espanhol Iberdrola, opera várias distribuidoras.", 20, 14, 10),
    _e("TAEE11", "Taesa", "Energia elétrica", "⚡", "Transmite energia elétrica de alta tensão por todo o Brasil.",
       "Uma das maiores transmissoras privadas de energia do país.", 16, 14, 8),
    # ---- Indústria e Bens de Capital ----
    _e("POMO4", "Marcopolo", "Bens industriais", "🚌", "Fabrica carroçarias de ônibus e micro-ônibus.",
       "Maior fabricante de ônibus do Brasil, exporta para dezenas de países.", 14, 12, 9),
    _e("RAPT4", "Randon", "Bens industriais", "🔧", "Fabrica reboques, semirreboques e implementos rodoviários.",
       "Fornece para as maiores transportadoras do agronegócio brasileiro.", 12, 10, 7),
    _e("ROMI3", "Romi", "Bens industriais", "⚙️", "Fabrica máquinas e equipamentos industriais de alta precisão.",
       "Referência em tornos e centros de usinagem feitos no Brasil.", 8, 8, 6),
    _e("TUPY3", "Tupy", "Bens industriais", "⚙️", "Fabrica peças fundidas em ferro cinzento e nodular para motores.",
       "Líder mundial em fundição de ferro para motores a combustão.", 10, 10, 7),
    # ---- Mineração e Siderurgia ----
    _e("CMIN3", "CSN Mineração", "Mineração", "⛏️", "Produz e exporta minério de ferro do Brasil.",
       "Subsidiária da CSN focada exclusivamente em minério de ferro.", 20, 16, 10),
    _e("CSNA3", "CSN", "Siderurgia", "🏭", "Produz aço plano e atua em cimento, mineração e logística.",
       "Uma das maiores siderúrgicas do Brasil com operações diversificadas.", 18, 14, 10),
    _e("FESA4", "Ferbasa", "Mineração", "⛏️", "Produz ligas de cromo e ferrocromo para o mercado global.",
       "Maior produtora de ferrocromo do hemisfério sul.", 8, 8, 6),
    _e("GGBR4", "Gerdau", "Siderurgia", "🏭", "Produz aço longo para construção civil e setor industrial.",
       "Uma das maiores siderúrgicas das Américas, presente em vários países.", 24, 18, 12),
    _e("USIM5", "Usiminas", "Siderurgia", "🏭", "Produz aço plano para a indústria automobilística e de embalagens.",
       "Um dos maiores produtores de aço plano do Brasil.", 16, 14, 9),
    # ---- Papel e Celulose ----
    _e("KLBN11", "Klabin", "Papel e celulose", "🌳", "Produz celulose, papel e embalagens de papel kraft e cartão.",
       "Maior produtora e exportadora de papéis do Brasil.", 20, 16, 10),
    # ---- Agronegócio ----
    _e("AGRO3", "BrasilAgro", "Agronegócio", "🌾", "Compra, desenvolve e vende terras rurais no Brasil.",
       "Especializada em transformar áreas inexploradas em terras produtivas.", 10, 10, 7),
    _e("SLCE3", "SLC Agrícola", "Agronegócio", "🌾", "Produz soja, milho e algodão em grandes fazendas no cerrado.",
       "Uma das maiores produtoras agrícolas do mundo em área plantada.", 12, 10, 7),
    _e("SMTO3", "São Martinho", "Agronegócio", "🌾", "Produz açúcar, etanol e energia elétrica a partir da cana-de-açúcar.",
       "Um dos maiores grupos sucroalcooleiros do Brasil.", 10, 10, 7),
    _e("TTEN3", "3tentos", "Agronegócio", "🌾", "Produz e comercializa grãos, fertilizantes e defensivos agrícolas.",
       "Atua na cadeia completa do agronegócio no Rio Grande do Sul.", 8, 8, 6),
    # ---- Alimentos e Bebidas ----
    _e("BEEF3", "Minerva", "Alimentos e bebidas", "🥩", "Abate e exporta carne bovina para mais de 100 países.",
       "Uma das maiores exportadoras de carne bovina da América do Sul.", 16, 12, 9),
    _e("CAML3", "Camil", "Alimentos e bebidas", "🍚", "Produz e vende arroz, feijão, açúcar, café e pescados.",
       "A marca Camil está na cozinha de milhões de brasileiros.", 10, 10, 7),
    _e("JBSS3", "JBS", "Alimentos e bebidas", "🥩", "Maior processadora de proteína animal do mundo.",
       "Atua em carne bovina, suína, aves e alimentos processados globalmente.", 32, 20, 13, arte="arte_JBSS3.webp"),
    _e("MBRF3", "MBRF", "Alimentos e bebidas", "🥩", "Produz e vende carnes e alimentos processados no Brasil e no mundo.",
       "Resultado da fusão entre Marfrig e BRF, unindo força no agro global.", 20, 14, 10),
    _e("MDIA3", "M. Dias Branco", "Alimentos e bebidas", "🌾", "Produz biscoitos, macarrão, farinha e trigo para todo o Brasil.",
       "A dona das marcas Vitarella, Fortaleza e Piraquê.", 14, 10, 8),
    # ---- Química ----
    _e("UNIP6", "Unipar", "Petroquímica", "🧪", "Produz cloro, soda e derivados plásticos usados na indústria.",
       "Líder no Brasil na produção de cloro-soda, insumo essencial para plásticos.", 10, 8, 7),
    # ---- Saneamento ----
    _e("CSMG3", "Copasa", "Saneamento", "💧", "Fornece água tratada e coleta esgoto em Minas Gerais.",
       "Empresa pública que atende milhões de mineiros com saneamento básico.", 12, 10, 8),
    _e("SAPR11", "Sanepar", "Saneamento", "💧", "Fornece água tratada e coleta esgoto no Paraná.",
       "Empresa pública que abastece quase toda a população do Paraná.", 14, 10, 8),
    _e("SBSP3", "Sabesp", "Saneamento", "💧", "Maior empresa de saneamento básico do Brasil.",
       "Abastece a Grande São Paulo e outras regiões com água e esgoto.", 22, 16, 11),
    # ---- Saúde ----
    _e("DASA3", "Dasa", "Saúde", "🔬", "Realiza exames laboratoriais e de imagem em todo o Brasil.",
       "Uma das maiores redes de medicina diagnóstica da América Latina.", 14, 12, 8),
    _e("FLRY3", "Fleury", "Saúde", "🔬", "Realiza exames de diagnóstico com foco em alta complexidade.",
       "Referência em medicina diagnóstica de alta qualidade no Brasil.", 16, 12, 10),
    _e("HAPV3", "Hapvida", "Saúde", "🏥", "Opera hospitais, clínicas e planos de saúde próprios no Brasil.",
       "Modelo integrado de saúde com hospitais, clínicas e planos próprios.", 20, 16, 12),
    _e("HYPE3", "Hypera", "Saúde", "💊", "Produz e vende medicamentos de marca, genéricos e OTC.",
       "Dona das marcas Buscopan, Neosaldina e Benegrip.", 20, 14, 11),
    _e("ODPV3", "Odontoprev", "Saúde", "🦷", "Opera a maior rede de planos odontológicos do Brasil.",
       "Referência em planos dentários empresariais no país.", 14, 12, 9),
    _e("RADL3", "Raia Drogasil", "Saúde", "💊", "Opera a maior rede de farmácias do Brasil.",
       "Com Raia e Drogasil, presente em quase todo o território nacional.", 22, 18, 12),
    _e("RDOR3", "Rede D'Or", "Saúde", "🏥", "Opera a maior rede de hospitais privados do Brasil.",
       "Líder no setor de hospitais de alta complexidade no país.", 30, 18, 14),
    # ---- Seguros e Serviços Financeiros ----
    _e("BBSE3", "BB Seguridade", "Seguros e Serviços Financeiros", "🛡️", "Distribui seguros, previdência e capitalização pelo Banco do Brasil.",
       "Alta rentabilidade e dividendos generosos são sua marca.", 18, 14, 10),
    _e("CXSE3", "Caixa Seguridade", "Seguros e Serviços Financeiros", "🛡️", "Distribui seguros e previdência pela rede da Caixa Econômica.",
       "Acessa milhões de clientes pela maior rede bancária do Brasil.", 14, 10, 8),
    _e("PSSA3", "Porto Seguro", "Seguros e Serviços Financeiros", "🛡️", "Oferece seguros de automóvel, residência, vida e saúde.",
       "Uma das maiores seguradoras do Brasil com décadas de tradição.", 18, 14, 10),
    _e("XPBR31", "XP Inc.", "Seguros e Serviços Financeiros", "📊", "Plataforma de investimentos com corretora, fundos e banco digital.",
       "Maior corretora independente do Brasil, revolucionou os investimentos.", 20, 14, 12),
    # ---- Telecom e Tecnologia ----
    _e("INTB3", "Intelbras", "Tecnologia", "💻", "Fabrica equipamentos de segurança, redes Wi-Fi e energia solar.",
       "Do câmeras de segurança a roteadores, está em milhões de lares.", 14, 12, 9),
    _e("POSI3", "Positivo", "Tecnologia", "💻", "Fabrica computadores, tablets e soluções para educação e governo.",
       "Maior fabricante nacional de computadores, presente nas escolas públicas.", 8, 8, 6),
    _e("TOTS3", "TOTVS", "Tecnologia", "💻", "Desenvolve softwares de gestão empresarial para pequenas e médias empresas.",
       "Líder no mercado de ERP do Brasil, presente em dezenas de setores.", 20, 16, 12),
    _e("VIVT3", "Vivo", "Telecomunicações", "📱", "Maior operadora de telefonia móvel e fibra ótica do Brasil.",
       "Com a marca Vivo da Telefônica, está em quase todo o território nacional.", 28, 16, 13),
    # ---- Transporte e Logística ----
    _e("ECOR3", "Ecorodovias", "Transporte e Logística", "🛣️", "Administra rodovias pedagiadas em vários estados do Brasil.",
       "Opera concessões como a Anchieta-Imigrantes em São Paulo.", 14, 12, 9),
    _e("MOTV3", "Motiva", "Transporte e Logística", "🛣️", "Opera concessões de rodovias e aeroportos no Brasil.",
       "Ex-CCR, mudou de nome após reestruturação de suas concessões.", 20, 14, 10),
    _e("MOVI3", "Movida", "Transporte e Logística", "🚗", "Aluga carros para pessoas físicas e frotas para empresas.",
       "Concorrente da Localiza no mercado de aluguel e gestão de frotas.", 12, 12, 8),
    _e("RAIL3", "Rumo", "Transporte e Logística", "🚂", "Transporta grãos e outros produtos por malha ferroviária.",
       "Maior operadora ferroviária privada do Brasil.", 22, 16, 12),
    _e("RENT3", "Localiza", "Transporte e Logística", "🚗", "Maior locadora de veículos da América Latina.",
       "Presente em aeroportos e cidades por todo o continente americano.", 28, 20, 13, arte="arte_RENT3.webp"),
    _e("STBP3", "Santos Brasil", "Transporte e Logística", "⚓", "Opera terminais de contêineres e de veículos no Porto de Santos.",
       "O Porto de Santos é o maior porto da América Latina.", 12, 10, 8),
    # ---- Varejo ----
    _e("ASAI3", "Assaí", "Varejo", "🛒", "Opera atacarejos e hipermercados em todo o Brasil.",
       "O atacarejo é o formato que mais cresce no varejo alimentar brasileiro.", 20, 16, 11),
    _e("AZZA3", "Azzas 2154", "Varejo", "👟", "Vende calçados e roupas pelas marcas Arezzo, Schutz e outras.",
       "Dona das marcas Arezzo, Schutz, Vans e outras grifes de calçados.", 14, 12, 9),
    _e("BHIA3", "Casas Bahia", "Varejo", "📺", "Vende eletrodomésticos, móveis e eletrônicos em lojas e online.",
       "Marca icônica do varejo brasileiro com presença em todo o país.", 8, 12, 7),
    _e("CEAB3", "C&A", "Varejo", "👗", "Vende roupas e acessórios em lojas físicas e pelo e-commerce.",
       "Marca global de moda presente nos principais shoppings do Brasil.", 8, 8, 6),
    _e("CRFB3", "Carrefour Brasil", "Varejo", "🛒", "Opera hipermercados, atacados e lojas de vizinhança no Brasil.",
       "O maior grupo varejista alimentar do Brasil.", 20, 14, 11),
    _e("GMAT3", "Grupo Mateus", "Varejo", "🛒", "Opera supermercados e atacarejos no Nordeste e Norte do Brasil.",
       "Domina o varejo alimentar no Nordeste com lojas de formatos variados.", 12, 12, 8),
    _e("LJQQ3", "Lojas Quero-Quero", "Varejo", "🔨", "Vende materiais de construção e produtos para o lar no Sul do Brasil.",
       "Presença forte em pequenas cidades gaúchas e catarinenses.", 8, 8, 5),
    _e("LREN3", "Lojas Renner", "Varejo", "👗", "Maior varejista de moda do Brasil com financeiro próprio.",
       "Referência em moda acessível, presente nos principais shoppings do país.", 24, 18, 13, arte="arte_LREN3.webp"),
    _e("PCAR3", "Pão de Açúcar", "Varejo", "🛒", "Opera supermercados premium e minimercados no Brasil.",
       "Um dos supermercados mais tradicionais do país, focado em premium.", 14, 10, 8),
    _e("VIVA3", "Vivara", "Varejo", "💎", "Opera a maior rede de joalherias do Brasil.",
       "Com lojas em shoppings premium, vende joias e relógios de alto valor.", 12, 10, 8),
]
POR_TK = {e["tk"]: e for e in EMPRESAS}
EXTRAS: dict = {}          # empresas cadastradas pelo admin (tk → nome), preenchido por cartas_dados.catalogo()


def raridade(tk: str) -> str | None:
    e = POR_TK.get(tk)
    return e["raridade_fixa"] if e else None


def da_raridade(r: str) -> list[str]:
    return [e["tk"] for e in EMPRESAS if e["raridade_fixa"] == r]


def setores() -> list[str]:
    return sorted({e["setor"] for e in EMPRESAS})


# ---------------------------------------------------------------------------------------------------- progressão (configurável)
# Cópias EXTRAS (além da primeira) gastas para subir do nível n para n+1, por raridade. Nível máximo = 1 + len(lista).
EVOLUCAO = {
    "comum": [2, 4, 8, 14, 24, 40, 60, 90, 130],
    "rara": [2, 3, 6, 10, 16, 26, 40, 58, 80],
    "epica": [1, 2, 4, 7, 11, 17, 25, 36, 50],
    "lendaria": [1, 1, 2, 3, 5, 8, 12, 16, 22],
}
NIVEL_MAX = 10

# Indicadores do jogo e o bônus de cada melhoria escolhida (a raridade NÃO dá bônus: só nível e escolhas mudam os atributos de jogo).
# rel: fator relativo sobre o valor (P/L menor é melhor → bônus reduz o P/L); pp: soma em pontos (fração: 0,0025 = 0,25 p.p.).
INDICADORES = ("pl", "dy_12m", "roe")
ROTULO_IND = {"pl": "P/L", "dy_12m": "DY", "roe": "ROE"}
BONUS = {"pl": ("rel", -0.04), "dy_12m": ("pp", 0.0025), "roe": ("pp", 0.01)}

# ---------------------------------------------------------------------------------------------------- baús (configurável)
# Cada raridade de baú (as mesmas dos baús que já existem) dá `qtd` cartas, sorteadas por `chances` (pesos por raridade da carta).
# `garantia`: pelo menos uma carta desta raridade ou superior. Duplicatas são normais (são elas que evoluem as cartas).
BAUS = {
    "comum": {"qtd": 2, "chances": {"comum": 72, "rara": 23, "epica": 4, "lendaria": 1}, "garantia": None},
    "raro": {"qtd": 3, "chances": {"comum": 55, "rara": 33, "epica": 10, "lendaria": 2}, "garantia": "rara"},
    "epico": {"qtd": 4, "chances": {"comum": 40, "rara": 35, "epica": 20, "lendaria": 5}, "garantia": "epica"},
    "lendario": {"qtd": 6, "chances": {"comum": 25, "rara": 35, "epica": 28, "lendaria": 12}, "garantia": "lendaria"},
}
# Primeiro acesso à coleção: uma carta de cada raridade jogável no início (comum, rara e épica), para já montar um time de 3.
INICIAL = ()  # jogadores começam sem cartas; o tutorial entrega as primeiras via POST /ticker/tutorial/bau
