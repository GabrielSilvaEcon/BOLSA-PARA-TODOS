"""Tutoriais do TickerHunters: conteúdo de cada tela, em etapas curtas (puro, sem Streamlit e sem consulta externa).

Cada etapa descreve só o que existe de verdade na tela (nomes de botões, abas e campos conferidos no código).
Campos: titulo · o_que (o que é/faz) · como (como usar) · onde (onde fica na tela) · cuidado (limites e riscos) ·
termos (entradas do glossário central, explicadas no nível da pessoa) · ini / avanc (aprofundamento opcional por nível) ·
exemplo (sempre ilustrativo, nunca apresentado como dado de mercado).
Nada aqui é recomendação de compra ou venda.
"""
from __future__ import annotations

CATEGORIAS = ("Primeiros passos", "Análises de investimentos", "Mercado e oportunidades", "Fundos de investimento", "Outros ativos",
              "Meus investimentos", "Ferramentas", "Educação", "Minha conta")


def _e(titulo, o_que, como, onde="", cuidado="", termos=(), ini="", avanc="", exemplo=""):
    return dict(titulo=titulo, o_que=o_que, como=como, onde=onde, cuidado=cuidado, termos=tuple(termos), ini=ini, avanc=avanc, exemplo=exemplo)


def _t(titulo, categoria, etapas, busca=""):
    return dict(titulo=titulo, categoria=categoria, etapas=list(etapas), busca=busca)


_AVISO = "Ferramenta educacional: nada aqui é recomendação de compra ou venda."

INTRO = [
    _e("Bem-vindo ao TickerHunters", "O TickerHunters reúne análises de ações, FIIs, ETFs, fundos, renda fixa e criptomoedas em um só lugar e explica cada resultado no seu nível.",
       "Você não precisa ver tudo agora. Esta introdução tem poucos passos e pode ser pulada ou revista depois, na Ajuda.",
       "Esta janela, aberta uma única vez no Início.", _AVISO,
       ini="Pense no app como um mapa: ele mostra onde você está e o que cada número quer dizer, mas quem escolhe o caminho é você."),
    _e("Como se movimentar", "O menu lateral agrupa tudo em categorias: Meus investimentos, Análises de investimentos, Mercado e oportunidades, Fundos de investimento, Outros ativos, Ferramentas, Educação e Minha conta.",
       "Toque numa categoria para abrir os itens dela. A categoria da página em que você está já fica aberta.",
       "Barra lateral à esquerda (no celular, pelo botão de menu no canto superior).", "Todas as ferramentas estão disponíveis em todos os níveis e planos; o limite de uso diário muda conforme o plano."),
    _e("Como encontrar um ativo", "No Início, você escolhe o tipo de ativo e digita o nome ou o código.",
       "Toque em Ações, Ações EUA, FIIs, ETFs, Fundos, Renda fixa ou Criptomoedas e use o campo de busca daquela classe.",
       "Abas logo abaixo de 'O que você quer analisar?'.", "Cada classe usa indicadores próprios; o app não mostra o que não se aplica a ela."),
    _e("Como ler os indicadores", "Cada número vem com um nome completo, uma cor de status e, em muitas telas, um quadro recolhido 'O que significa cada indicador'.",
       "Abra o quadro para ver a explicação no seu nível. Cores resumem faixas gerais e não substituem a leitura do setor e do contexto.",
       "Quadro recolhido no topo de cada análise.", "Um indicador isolado pode enganar: compare com o setor, com o histórico e com outros indicadores.", termos=("P/L", "ROE")),
    _e("Onde pedir ajuda", "Em toda página existe o botão 'Como utilizar esta página?', com um tutorial curto daquela tela. Na Central de Ajuda ficam todos os tutoriais, o glossário e seu histórico.",
       "Toque no botão quando quiser. Nada abre sozinho depois desta introdução, e você pode mudar seu nível em Minha conta.",
       "Botão no topo de cada página; menu Ajuda.", ""),
]


TUTORIAIS: dict[str, dict] = {}


def _add(url, titulo, categoria, etapas, busca=""):
    TUTORIAIS[url] = _t(titulo, categoria, etapas, busca)


# ---------------------------------------------------------------------------------------------------------- início
_add("inicio", "Início", "Primeiros passos", [
    _e("Pesquise um ativo", "O Início tem um único campo, 'Pesquisar ativo'. Digite o nome ou o código de qualquer ativo do app: ação, FII, ETF, fundo, renda fixa ou criptomoeda (ex.: Petrobras, HGLG11, BOVA11, Bitcoin, Tesouro IPCA).",
       "Digite e toque em Pesquisar. Se o código for exato, o app abre direto; se houver várias opções, elas aparecem em grupos por tipo, com o botão Abrir.",
       "Campo 'Pesquisar ativo' no topo do Início.", "O app descobre o tipo do ativo e leva você à análise certa; não precisa escolher a classe antes."),
    _e("Leia o resumo das ações", "Ao abrir uma ação, aparece o resumo dela, com cartões de cada análise conforme o detalhe escolhido.",
       "Em 'Empresas em análise' dá para tirar empresas tocando no nome. Você também pode tocar num dos atalhos de empresas populares.",
       "Lista 'Empresas em análise' e cartões abaixo.", "Os cartões usam faixas gerais de referência; cada setor tem os seus patamares.", termos=("P/L", "Margem de segurança")),
    _e("Perfil do investidor", "O perfil (Conservador, Moderado ou Arrojado) ajusta as réguas do resumo, como margem de segurança exigida e rendimento de dividendos desejado.",
       "Escolha em 'Perfil do investidor'. Troque quando quiser; é só uma régua de leitura.", "Seletor 'Perfil do investidor' perto dos cartões.",
       "O perfil do app não substitui o questionário de perfil (suitability) da sua corretora.", termos=("Margem de segurança", "Bazin")),
    _e("Escolha a profundidade da análise", "A análise tem três profundidades: Essencial (veredito, preço atual, preço justo e principais informações), Detalhada (fundamentos, indicadores, riscos e comparações relevantes) e Aprofundada (análise completa, histórico, gráficos, cálculos e indicadores avançados).",
       "Toque em Essencial, Detalhada ou Aprofundada. Ela começa no que combina com o seu modo de uso, e você troca quando quiser.", "Seletor 'Escolha a profundidade da análise', logo abaixo de 'Suas empresas'.",
       "A leitura rápida é educativa: não recomenda compra nem venda."),
    _e("Siga para as análises", "O Início resume. Os detalhes ficam em Análise de ativos no menu lateral: Preço justo, Múltiplos, Dividendos, Saúde financeira e, na análise Aprofundada, Fluxo de caixa (DCF).",
       "Abra a categoria e escolha a análise. As empresas escolhidas aqui continuam selecionadas nas outras telas.", "Menu lateral > Análise de ativos.", _AVISO),
])

_add("preco-justo", "Preço justo", "Análises de investimentos", [
    _e("O que a tela mostra", "Compara o preço de hoje com um valor justo estimado por dois métodos: Graham (lucro e patrimônio por ação) e Bazin (dividendos).",
       "Veja o cartão de cada método e a margem entre o preço justo e o preço atual.", "Aba Painel, com um cartão por empresa e por método.",
       "O preço justo é uma referência estimada, não uma previsão nem um alvo.", termos=("Graham", "Bazin", "Margem de segurança"),
       ini="Pense em estimar quanto um imóvel deveria custar pelo aluguel e pelo tamanho. É uma conta de referência; o preço de venda real pode ser outro.",
       avanc="Graham: √(22,5 × LPA × VPA). Bazin: dividendo médio ÷ rendimento mínimo desejado. Ambos supõem empresa estável e lucrativa."),
    _e("Escolha empresas e perfil", "Você pode analisar várias empresas ao mesmo tempo e o perfil define a margem de segurança e o rendimento de dividendos exigidos.",
       "Use 'Empresas em análise' para incluir empresas e 'Perfil do investidor' para trocar a régua. A aba Comparativo põe todas lado a lado.",
       "Seletores no topo; abas Painel e Comparativo.", "Compare empresas do mesmo setor. Bancos e empresas sem lucro ou sem dividendos combinam mal com esses métodos.", termos=("LPA", "VPA", "DY")),
    _e("Confira a qualidade dos dados", "Quando algum dado estiver faltando ou desatualizado, o app avisa.",
       "Abra o aviso 'Qualidade dos dados' para ver o que falta e de onde veio cada informação.", "Bloco 'Qualidade dos dados (n aviso(s))'.",
       "Sem dado confiável, o resultado deve ser descartado, não completado de cabeça."),
    _e("Guarde na carteira", "Se quiser acompanhar a empresa, registre uma compra na sua carteira.",
       "Use 'Adicionar à carteira', escolha a carteira (fictícia ou real), a quantidade e a data e toque em Confirmar. Nenhuma ordem é enviada a corretora.",
       "Botão 'Adicionar à carteira' na tela.", "É só registro para acompanhamento: o app não compra nem vende nada."),
])

_add("valuation", "Múltiplos", "Análises de investimentos", [
    _e("Para que servem os múltiplos", "Múltiplos relacionam o preço da ação a algum resultado da empresa, como lucro (P/L) e patrimônio (P/VP), para comparar empresas de tamanhos diferentes.",
       "Leia a tabela comparativa: cada linha é uma empresa e cada coluna é um indicador, com nome completo.", "Tabela principal da página.",
       "Múltiplo baixo não significa 'barato': pode refletir queda esperada do lucro.", termos=("P/L", "P/VP", "EV/EBITDA", "DY", "ROE"),
       ini="P/L é como perguntar: 'em quantos anos o lucro da empresa pagaria o preço que estou pagando?'.",
       avanc="Prefira EV/EBITDA para comparar empresas com dívidas diferentes e P/L normalizado em setores cíclicos."),
    _e("Compare por um indicador", "O seletor 'Comparar por' reordena e destaca as empresas conforme o indicador escolhido.",
       "Escolha o indicador e veja quem tem o maior ou o menor valor. Use 'Ver todos os indicadores' para a lista completa.", "Seletor 'Comparar por' e bloco 'Ver todos os indicadores'.",
       "Compare só empresas do mesmo setor e da mesma moeda."),
    _e("Leia com contexto", "A leitura em palavras, no topo, resume o que os números dizem no seu nível.",
       "Use-a como guia e confirme na tabela. Cada nome tem explicação no quadro 'O que significa cada indicador'.", "Caixa 'Leitura do resultado'.",
       "Indicadores dependem da data do balanço usado.", termos=("Valuation",)),
])

_add("dcf", "Fluxo de caixa (DCF)", "Análises de investimentos", [
    _e("O que é o DCF", "Estima o valor da empresa trazendo para hoje o caixa que ela deve gerar no futuro. É o método mais sensível às premissas.",
       "Escolha o ativo no seletor 'Ativo' e olhe o valor por ação estimado e a margem em relação ao preço atual.", "Seletor 'Ativo' e cartões de resultado.",
       "Pequenas mudanças na taxa de desconto ou no crescimento alteram muito o valor: pense em faixa, não em número exato.", termos=("DCF", "FCL", "WACC", "Margem de segurança"),
       ini="É como avaliar uma máquina pelo dinheiro que ela vai render nos próximos anos, descontando o fato de que dinheiro hoje vale mais que dinheiro amanhã.",
       avanc="Valor = Σ FCLt ÷ (1+r)^t + valor terminal. O crescimento na perpetuidade deve ficar abaixo do crescimento esperado da economia."),
    _e("Ajuste as premissas", "Você controla horizonte, média de fluxos, taxa de desconto, crescimento no período e na perpetuidade.",
       "Abra 'Premissas' e mexa nos controles deslizantes. Veja os Cenários (pessimista, base e otimista) para sentir a variação.", "Bloco 'Premissas' e seção Cenários.",
       "As premissas iniciais vêm do seu perfil; elas são suposições, não fatos."),
    _e("Leia os termos e compare", "O bloco 'O que significam os termos do DCF?' explica cada premissa. 'Todos os ativos selecionados' aplica as mesmas premissas a todos.",
       "Abra os blocos quando tiver dúvida. Compare o valor com o preço sem tratá-lo como alvo.", "Expansores abaixo das premissas.", _AVISO, termos=("WACC",)),
])

_add("dividendos", "Dividendos", "Análises de investimentos", [
    _e("O que a tela mostra", "O quanto cada empresa distribuiu aos acionistas e quanto isso representa sobre o preço.",
       "Veja o rendimento de dividendos (DY), os proventos dos últimos 12 meses e a média de 5 anos.", "Cartões e tabela da página.",
       "DY alto pode ser sinal de preço caído ou de pagamento extraordinário, que não se repete.", termos=("DY", "Payout"),
       ini="É como a renda de um aluguel: quanto entrou no seu bolso em um ano comparado com o preço do imóvel.",
       avanc="Verifique payout e fluxo de caixa livre para julgar a sustentabilidade do pagamento."),
    _e("Compare empresas", "Escolha várias empresas em 'Empresas em análise' para ver quem paga mais e com mais regularidade.",
       "Compare o DY de 12 meses com a média de 5 anos: grandes diferenças pedem explicação.", "Seletor 'Empresas em análise'.", "Dividendos passados não garantem dividendos futuros."),
    _e("Use o perfil", "O perfil do investidor define o rendimento mínimo desejado usado no método de Bazin.",
       "Mude em 'Perfil do investidor' e veja se o preço está abaixo do preço-teto.", "Seletor de perfil.", "O preço-teto de Bazin é uma referência, não uma ordem.", termos=("Bazin",)),
])

_add("micro", "Saúde financeira", "Análises de investimentos", [
    _e("O que se avalia", "Mostra se a empresa é lucrativa, quanto deve e quão eficiente é: LPA, VPA, ROE, margem líquida e dívida sobre patrimônio.",
       "Leia os cartões de cada empresa; cada um traz nome completo e cor de status.", "Cartões da página.",
       "Cada setor tem patamares normais de dívida e margem; compare com pares.", termos=("LPA", "VPA", "ROE", "Margem líquida", "Dív./PL")),
    _e("Dívida e lucro juntos", "Dívida alta é mais perigosa quando o lucro é instável.",
       "Combine o indicador de dívida com ROE e margem. Dívida líquida sobre EBITDA mostra em quantos anos a geração operacional pagaria a dívida.",
       "Cartões de dívida e rentabilidade.", "Bancos e seguradoras têm estrutura própria; indicadores de dívida comuns não se aplicam bem a eles.", termos=("Dívida líquida/EBITDA", "EBITDA", "Fluxo de caixa")),
    _e("Qualidade dos dados", "Os indicadores vêm de balanços de datas diferentes.",
       "Abra o aviso 'Qualidade dos dados' para saber a data e a fonte.", "Bloco 'Qualidade dos dados'.", "Balanço antigo pode já ter mudado."),
])

_add("tecnica", "Análise técnica (ações)", "Análises de investimentos", [
    _e("Leia o gráfico", "A análise técnica estuda o comportamento do preço e do volume. Aqui você escolhe a bolsa, o ativo e o intervalo.",
       "Escolha a Bolsa, o Ativo (ou a Ação americana) e o Intervalo, e observe a tendência indicada: Alta, Lateral ou Baixa.", "Seletores 'Bolsa', 'Ativo' e 'Intervalo'.",
       "Tendência descreve o passado e pode mudar; não garante o futuro.", termos=("Média móvel", "IFR", "MACD"),
       ini="É como olhar a trilha por onde a pessoa caminhou: ajuda a ver a direção, mas ela pode mudar de rumo.",
       avanc="Sinais isolados geram falsos positivos; combine tendência, volume e contexto de risco."),
    _e("Indicadores do gráfico", "Médias móveis suavizam o preço; IFR mede a força recente; MACD compara médias de períodos diferentes.",
       "Veja onde o preço está em relação às médias e se o IFR está em extremos.", "Gráfico principal e cartões de sinais.",
       "Em tendências fortes, IFR pode ficar muito tempo em extremos.", termos=("IFR", "MACD", "Volatilidade")),
    _e("Guarde na carteira", "Registre uma compra para acompanhar o ativo.", "Use 'Adicionar à carteira'. Nenhuma ordem é enviada.", "Botão 'Adicionar à carteira'.", _AVISO),
])

_add("tecnica-avancada", "Análise técnica avançada", "Análises de investimentos", [
    _e("Para quem já lê gráficos", "Reúne gráfico, sinais, padrões e níveis, análise multitemporal, backtest, alertas, carteira e ajuda dos dados.",
       "Percorra as abas: Gráfico, Sinais, Padrões e níveis, Multitemporal, Backtest, Alertas, Carteira e Dados e ajuda. Em 'Visão' você pode comparar com outros ativos e índices.",
       "Abas no topo da página.", "Um setup por vez; sinais técnicos são educacionais.", termos=("Média móvel", "IFR", "MACD", "Drawdown")),
    _e("Teste antes de confiar", "O Backtest mostra como um setup teria se comportado no histórico.",
       "Abra a aba Backtest, escolha o setup e veja acertos, perdas e queda máxima.", "Aba Backtest.",
       "Bom desempenho no passado não garante o futuro; custos e liquidez reduzem o resultado real.",
       avanc="Cuidado com ajuste excessivo aos dados históricos (overfitting) e viés de sobrevivência."),
    _e("Alertas", "Defina alertas para ser avisado quando um nível ou sinal ocorrer.", "Use a aba Alertas e acompanhe as notificações.", "Aba Alertas.", "Alertas avisam, não decidem por você."),
])

_add("tecnica-cripto", "Análise técnica (criptomoedas)", "Análises de investimentos", [
    _e("Escolha o par e o intervalo", "Mostra o gráfico de preços ao vivo da Binance para pares de criptomoedas.",
       "Escolha o Par de criptomoedas, o Intervalo e o tipo de Velas; ative 'Atualizar a cada 30 s' se quiser acompanhar ao vivo.", "Seletores no topo da página.",
       "Criptomoedas oscilam muito mais que ações: olhe o risco antes do retorno.", termos=("Volatilidade", "Média móvel", "IFR", "MACD")),
    _e("Sinais dos últimos candles", "O app pode destacar sinais como cruzamentos e setups nos três últimos candles.",
       "Ligue 'Mostrar sinais dos últimos 3 candles' e escolha o tipo de gráfico.", "Chave 'Mostrar sinais...' e seletor 'Gráfico'.", "Sinais são educacionais e podem errar."),
])

_add("stock-picking", "Ranking", "Análises de investimentos", [
    _e("Para que serve o ranking", "Ordena empresas por uma nota de 0 a 100 que resume vários critérios (valor, qualidade, dividendos, solidez, risco e, opcionalmente, tendência).",
       "Escolha o perfil, o que ranquear e os setores, e toque em 'Calcular o ranking'.", "Seletores no topo e botão 'Calcular o ranking'.",
       "A nota é um modelo simplificado e depende da qualidade dos dados; não é recomendação.", termos=("Valuation", "ROE", "Volatilidade")),
    _e("Entenda os pilares", "Cada empresa tem uma nota por pilar. Olhe os pilares, não só o total.",
       "Abra 'Pesos e critérios' para ver e ajustar a importância de cada pilar; 'Radar por ativo' compara os pilares visualmente.", "Blocos 'Pesos e critérios' e 'Radar por ativo'.",
       "Mudar pesos muda a ordem: teste se a conclusão se mantém."),
    _e("Compare setores", "O filtro 'Setores' restringe o ranking a segmentos específicos.", "Selecione os setores desejados antes de calcular.", "Seletor 'Setores'.",
       "Rankear setores diferentes juntos mistura realidades distintas."),
])

_add("macro", "Economia", "Mercado e oportunidades", [
    _e("O cenário geral", "A aba 'Resumo' classifica a economia brasileira em BOM, NEUTRO ou RUIM, explica o motivo e mostra o quanto a análise é confiável.",
       "Leia o cartão do veredito e depois os blocos 'O que está acontecendo', pontos a favor, pontos contra e riscos.", "Aba 'Resumo'.",
       "O cenário descreve o ambiente. Não diz que uma ação vai subir ou cair.", termos=("Selic", "IPCA", "Juro real", "Cenário econômico"),
       ini="BOM significa condições relativamente favoráveis; RUIM, desfavoráveis; NEUTRO, sinais mistos.",
       avanc="A nota vai de -1 a +1: média ponderada de 12 fatores com dado atual, com histerese e cobertura mínima de 50%."),
    _e("Indicadores e histórico", "A aba 'Indicadores' traz cada indicador com valor, unidade, período, fonte e estado: atualizado, provisório, revisado, desatualizado ou indisponível.",
       "Escolha o 'Grupo' e, mais abaixo, o 'Indicador' e o 'Período' para ver o gráfico e baixar o histórico.", "Aba 'Indicadores', seletores 'Grupo', 'Indicador' e 'Período'.",
       "Dado desatualizado nunca entra no cálculo do cenário.", termos=("IBC-Br", "INCC", "PNAD", "Focus"),
       avanc="Cada indicador tenta Banco Central, IBGE, Ipeadata, FRED e Focus em ordem, e só aceita dado com frequência e faixa plausíveis."),
    _e("Setores e classes de ativos", "O mesmo cenário ajuda um setor e prejudica outro. A aba 'Setores' mostra quais estão favorecidos e quais pressionados.",
       "Abra 'Escolha o setor ou a classe' para ver o veredito, os indicadores que pesaram e o que poderia mudar.", "Aba 'Setores', seletor 'Escolha o setor ou a classe'.",
       "Poucos dados significam confiança baixa e leitura neutra.", termos=("Cenário econômico", "Risco-país", "Câmbio")),
    _e("Minha carteira real e alertas", "A aba 'Minha carteira real' mostra o impacto do cenário nos ativos que você realmente registrou. Mudanças relevantes viram alertas.",
       "Veja as sensibilidades de cada ativo (juros, inflação, câmbio...) e acompanhe os avisos na aba 'Alertas'. Escolha o que receber em Notificações.", "Abas 'Minha carteira real' e 'Alertas'.",
       "Ativos pesquisados, exemplos e a carteira fictícia nunca geram alerta econômico."),
    _e("Fontes e limites", "A aba 'Fontes' lista cada indicador, de onde veio e por que algum continua sem dado.",
       "Abra os itens indisponíveis para ver a causa registrada em cada fonte.", "Aba 'Fontes'.", "Nada é inventado para preencher lacunas."),
])

_add("noticias", "Central de notícias e eventos", "Mercado e oportunidades", [
    _e("O que a central reúne", "Notícias e eventos dos seus ativos, de feeds públicos, com classificação automática de relevância.",
       "Toque em 'Atualizar notícias' e use 'Filtros' para refinar.", "Botão 'Atualizar notícias' e bloco 'Filtros'.",
       "A relevância é automática: leia a fonte antes de tirar conclusões."),
    _e("Filtre o que importa", "Filtre por classe, ativo, empresa ou palavra, setor, país, fonte, data e relevância mínima.",
       "Combine filtros para chegar rápido ao que interessa.", "Bloco 'Filtros'.", "Notícia não é recomendação nem garantia de movimento de preço."),
])

_add("inteligencia", "Central de inteligência", "Mercado e oportunidades", [
    _e("Sua leitura de mercado", "Cruza seus ativos e preferências para destacar situações que merecem atenção.",
       "Toque em 'Atualizar leitura' e veja a lista; escolha 'Ver o detalhe de um ativo' para aprofundar.", "Botão 'Atualizar leitura' e seletor de ativo.", "Resultados apontam atenção, não ordens."),
    _e("Configure o que acompanhar", "Defina classes de interesse, ativos favoritos, nível de risco, horizonte e tipos de alerta.",
       "Preencha as preferências e ajuste a frequência das notificações.", "Campos de preferências no topo.", "Poucos alertas, bem escolhidos, funcionam melhor que muitos."),
    _e("Entenda os limites", "O bloco 'O que ainda depende de novas fontes' mostra o que a leitura não cobre.", "Abra 'Como a leitura é feita, por classe'.", "Expansores da página.", "Sem fonte, sem dado."),
])

_add("notificacoes", "Alertas", "Mercado e oportunidades", [
    _e("Caixa de entrada", "Reúne os avisos do app com importância e categoria.", "Abra a aba Caixa de entrada e filtre por Categoria, Importância ou Ativo.", "Aba Caixa de entrada.",
       "Comece pelos de importância alta."),
    _e("Meus alertas", "Crie alertas de preço, variação e outros eventos para seus ativos.", "Na aba Meus alertas, informe ativo, tipo e valor. O monitor avalia as regras periodicamente.",
       "Aba Meus alertas.", "O monitor roda em ciclos: o aviso pode chegar com atraso."),
    _e("Preferências e canais", "Escolha como receber os avisos e faça um teste do e-mail.", "Use a aba Preferências e canais e o botão 'Testar e-mail'.", "Aba Preferências e canais.", ""),
])

# ---------------------------------------------------------------------------------------------------------- carteira e gestão
_add("carteira", "Carteira", "Meus investimentos", [
    _e("Fictícia ou real", "A carteira fictícia serve para praticar sem dinheiro de verdade; a real registra suas compras.",
       "Escolha a aba Carteira fictícia ou Carteira real.", "Abas no topo.", "O app só registra: não compra nem vende nada."),
    _e("Registre uma compra", "Informe empresa ou código, quantidade, preço pago e data.", "Preencha os campos e toque em 'Adicionar à carteira'.", "Formulário no topo.",
       "Ativos do exterior usam dólar na data da compra para o custo em reais.", termos=("ROI",)),
    _e("Leia o resultado", "Mostra quanto você investiu, quanto vale hoje, ganho ou perda, melhor e pior posição e o peso de cada ativo.",
       "Veja a leitura em palavras e a tabela de Posições. Em 'Compras registradas e remoção' você corrige lançamentos.", "Cartões, tabela Posições e gráficos.",
       "O resultado usa preços de fechamento e não desconta impostos nem taxas.", termos=("Diversificação",)),
    _e("Salvar e carregar", "Exporte ou importe sua carteira em CSV.", "Abra 'Salvar ou carregar (CSV)' e use Exportar ou Importar.", "Expansor 'Salvar ou carregar (CSV)'.",
       "Zerar a carteira apaga os lançamentos; confirme com atenção."),
])

_add("gestao-carteira", "Gestão de carteira", "Meus investimentos", [
    _e("Como seu dinheiro está distribuído", "Mostra a distribuição por classe, setor, país, moeda e emissor ou gestor.",
       "Escolha a Carteira e navegue pelas abas Classe, Setor, País, Moeda e Emissor / gestor.", "Seção Distribuição.",
       "Concentração em poucos ativos aumenta o risco.", termos=("Diversificação", "Correlação")),
    _e("Metas de alocação", "Defina a alocação-alvo por classe e a tolerância.", "Preencha 'alvo (%)' e 'Tolerância (± p.p.)' e veja os pontos de atenção.", "Seção 'Meta de alocação por classe'.",
       "As metas são referências suas; não são recomendação."),
    _e("Registrar venda", "Registre uma venda ou retirada para manter a carteira correta.", "Use 'Registrar venda ou retirada' e informe ativo, quantidade, preço e data.",
       "Expansor 'Registrar venda ou retirada'.", "Só registro: nada é negociado."),
])

_add("risco", "Gestão de risco", "Meus investimentos", [
    _e("Meça o quanto oscila", "Mede volatilidade, queda máxima, VaR e outros indicadores de risco da sua carteira.",
       "Escolha a Carteira e o período dos indicadores e toque em 'Atualizar análise de risco'.", "Seletores e botão no topo.",
       "Risco histórico não prevê o futuro; crises mudam as correlações.", termos=("Volatilidade", "Drawdown", "VaR", "Beta", "Sharpe"),
       ini="Volatilidade é o tamanho do 'sobe e desce'. Queda máxima é o tamanho do pior tombo já visto.",
       avanc="VaR é um quantil de perdas e não informa a magnitude além do limite; considere também o CVaR."),
    _e("Quem contribui para o risco", "Mostra quais ativos e classes mais pesam no risco total.", "Use os filtros de Classes e Ativos e veja 'Quem contribui para o risco'.", "Seção de contribuição.", "", termos=("Correlação",)),
    _e("Limites e alertas", "Defina limites para ser avisado quando o risco passar de um patamar seu.", "Ajuste os limites configuráveis na página.", "Bloco de limites.", "Limites são seus, não regras do mercado."),
])

_add("relatorios", "Relatórios e dashboard", "Meus investimentos", [
    _e("Seu painel", "Resume sua carteira ao longo do tempo com gráficos e indicadores.", "Escolha a Carteira e o Período.", "Seletores no topo.", "Compare períodos iguais.", termos=("ROI", "CAGR")),
    _e("Filtre", "Filtre por classe, setor, país, moeda, ativo e conta.", "Abra 'Filtros e indicadores' e escolha o que ver; selecione os 'Gráficos do painel'.", "Expansor 'Filtros e indicadores'.", ""),
    _e("Exporte e compare datas", "Relatórios podem ser exportados e comparados entre datas.", "Use as opções de exportação e compare fotografias de datas diferentes.", "Botões de exportar.", "Relatórios usam seu histórico registrado."),
])

_add("simulador", "Simulador financeiro", "Ferramentas", [
    _e("Escolha a simulação", "Juros compostos, aposentadoria, renda passiva, aportes e metas, por classe, cenários, crises, carteira, histórico, inflação, assistente e fórmulas.",
       "Escolha a aba que combina com sua pergunta.", "Abas no topo.", "É uma conta com premissas: não é promessa de retorno.", termos=("CAGR", "Juro real")),
    _e("Mude os números", "Mude valores e taxas e veja o efeito.", "Preencha os campos de cada aba; os resultados se atualizam.", "Campos de cada aba.", "Taxas futuras são suposições."),
    _e("Entenda a conta", "A aba Fórmulas mostra como cada resultado é calculado.", "Abra a aba Fórmulas para conferir as contas.", "Aba Fórmulas.", ""),
])

_add("calculadoras", "Calculadoras", "Ferramentas", [
    _e("Contas rápidas", "Juros compostos, rentabilidade real, CDB × LCI/LCA e meta de patrimônio.", "Escolha a aba, preencha os campos e leia o resultado.", "Abas no topo.",
       "As taxas são as que você informa; o futuro pode ser diferente.", termos=("Juro real", "CDI", "IPCA")),
    _e("Quando precisar de mais", "Para aposentadoria, cenários e carteira, use o Simulador financeiro.", "Toque no atalho para o Simulador no fim da página.", "Link no fim da página.", ""),
])

_add("comparar", "Comparar ativos", "Ferramentas", [
    _e("O que comparar", "Compara ações, ETFs e criptomoedas lado a lado, ou carteiras entre si.", "Escolha Ativos ou Carteiras e preencha as listas.", "Seletor 'O que comparar'.",
       "Misturar classes usa só critérios comuns.", termos=("Benchmark", "Volatilidade", "Sharpe")),
    _e("Escolha os ativos", "Selecione ações, digite ETFs e outros códigos e escolha criptomoedas.", "Preencha os campos e toque em 'Comparar'. Marque 'Incluir crescimento histórico' se quiser o CAGR.",
       "Campos 'Ações', 'ETFs e outros códigos' e 'Criptomoedas'.", "Compare ativos parecidos.", termos=("CAGR",)),
    _e("Leia o resultado", "Veja tabelas e gráficos de desempenho, risco e indicadores próprios de cada classe.", "Observe pontos fortes e fracos de cada ativo.", "Resultado abaixo do botão.", "Nota maior não significa melhor para você."),
])

_add("evolucao", "Evolução e crescimento", "Análises de investimentos", [
    _e("Como a empresa cresceu", "Mostra o crescimento ao longo do tempo para ações, FIIs, ETFs, fundos, renda fixa e criptomoedas.", "Escolha a Classe e o ativo.",
       "Seletor 'Classe'.", "Compare períodos de ciclo parecido.", termos=("CAGR",)),
    _e("Abas de leitura", "Resumo e análise, CAGR, Anual, Trimestral e Preço e dividendos.", "Navegue pelas abas; use 'Comparar o crescimento com outros ativos' para colocar ativos lado a lado.",
       "Abas no topo.", "CAGR esconde as oscilações do caminho; olhe também o gráfico.", termos=("CAGR", "ROI")),
])

# ---------------------------------------------------------------------------------------------------------- fundos e outros ativos
_add("fiis", "FIIs", "Fundos de investimento", [
    _e("O que são FIIs", "Fundos imobiliários reúnem dinheiro de várias pessoas para investir em imóveis ou títulos imobiliários e distribuem renda, em geral mensal.",
       "Escolha o FII em 'FII' ou digite o código e veja a Visão geral.", "Seletor 'FII' e abas no topo.", "Rendimento passado não garante o futuro.", termos=("P/VP", "DY", "Vacância"),
       ini="É como ser dono de uma pequena parte de vários imóveis e receber uma parte dos aluguéis."),
    _e("Abas de análise", "Visão geral, Indicadores, Dividendos, Histórico, Imóveis ou recebíveis, Riscos, Comparação e Análise inteligente.",
       "Percorra as abas. Em Dividendos veja a regularidade; em Imóveis ou recebíveis veja vacância e composição.", "Abas no topo.",
       "FIIs de papel e de tijolo têm indicadores diferentes; vacância vale para tijolo.", termos=("Liquidez", "Payout")),
    _e("Compare e confira a fonte", "Compare com semelhantes no ranking e confira 'De onde vem cada dado'.", "Use 'Ranking entre os semelhantes' e o expansor das fontes.", "Aba Comparação e expansor de fontes.",
       "Para o histórico oficial da CVM, informe o CNPJ do fundo."),
])

for _u, _tit, _tipo in (("fundos-acoes", "Fundos de ações", "fundos que investem em ações"), ("multimercados", "Multimercados", "fundos multimercados"),
                        ("fundos-renda-fixa", "Fundos de renda fixa", "fundos de renda fixa")):
    _add(_u, _tit, "Fundos de investimento", [
        _e("O que você está analisando", f"Análise de {_tipo}, com dados oficiais da CVM.", "Digite o nome do fundo em 'Fundo' e toque em Buscar; escolha em 'Fundos encontrados'.",
           "Campo 'Fundo' e botão Buscar.", "Fundos podem ter regras de cotização e resgate que demoram dias.", termos=("Taxa de administração", "Benchmark", "Come-cotas")),
        _e("Retorno e risco", "Veja retorno em várias janelas, volatilidade, pior queda e a nota educacional.", "Compare com a referência (CDI ou índice) e olhe também o risco.",
           "Abas da página (Visão geral, Rentabilidade, Risco, Custos).", "Janela de 12 meses é curta; confira 3 e 5 anos.", termos=("Volatilidade", "Drawdown", "Sharpe")),
        _e("Custos e carteira", "A taxa de administração reduz o rendimento ano após ano.", "Veja a aba de Custos e, se quiser, carregue a carteira divulgada pela CVM.",
           "Aba Custos; botão 'Carregar a carteira divulgada pela CVM'.", "O arquivo da carteira é grande e pode demorar.", termos=("Taxa de administração",)),
    ])

_add("etfs", "ETFs", "Fundos de investimento", [
    _e("O que é um ETF", "ETFs são fundos que acompanham um índice e são negociados na bolsa como ações.", "Digite o código (ex.: BOVA11, IVVB11, VOO) e toque em Analisar, ou use um atalho.",
       "Campo 'ETF' e botão Analisar.", "Verifique o que o ETF replica e quanto cobra.", termos=("Tracking error", "Taxa de administração", "Liquidez"),
       ini="É uma cesta já pronta de ativos que você compra de uma vez."),
    _e("Custos e fidelidade ao índice", "Taxa e erro de rastreamento mostram quanto o ETF custa e o quanto copia bem o índice.", "Leia as abas de custos, tracking e risco.",
       "Abas da página.", "Spread e liquidez afetam o preço real de compra e venda.", termos=("Spread", "Benchmark")),
    _e("Composição", "Veja o que há dentro do ETF.", "Use 'Carregar a carteira divulgada pela CVM' quando disponível.", "Aba Composição.", "Pode demorar."),
])

_add("renda-fixa", "Análise de títulos", "Outros ativos", [
    _e("Títulos e simulação", "Analisa títulos do Tesouro Direto (preço oficial) e títulos privados informados por você.", "Escolha a Origem, o Título e o valor para simular.",
       "Seletor 'Origem' e 'Título'.", "Títulos privados dependem dos dados que você informa.", termos=("Selic", "CDI", "IPCA", "Marcação a mercado")),
    _e("Cenários e resgate antecipado", "Veja projeções em cenários e o efeito de resgatar antes do vencimento.", "Use 'Cenário para projeções', marque 'Resgatar antes' e ajuste 'Mudança das taxas'.",
       "Controles da simulação.", "Títulos prefixados podem render menos que o contratado se vendidos antes.", termos=("Juro real",)),
    _e("Compare com outras opções", "Compare com CDI, IPCA ou outros títulos.", "Escolha em 'Comparar com' e leia a diferença.", "Seletor 'Comparar com'.", "Considere imposto e liquidez."),
])

_add("tesouro-cdi", "Tesouro Direto e CDI", "Outros ativos", [
    _e("Simule", "Estima quanto um investimento em Tesouro, CDB ou LCI/LCA pode render, com imposto e custódia.", "Informe valor inicial, aporte mensal, indexador, CDI, IPCA esperado, custódia e prazo.",
       "Campos no topo.", "O resultado depende das taxas que você informar.", termos=("CDI", "IPCA", "Juro real")),
    _e("Leia a simulação", "A leitura em palavras mostra quanto você colocaria, quanto renderia e quanto vai de imposto.", "Compare bruto e líquido.", "Caixa 'O que esta simulação mostra'.", "Imposto cai com o tempo na renda fixa."),
])

_add("criptomoedas", "Criptomoedas: visão geral", "Outros ativos", [
    _e("Encontre uma moeda", "Visão geral e tokenomics: preço, valor de mercado e como as moedas são emitidas.", "Busque por nome ou setor, escolha em 'Moedas em análise' e veja os cartões.",
       "Seletor 'Buscar por' e 'Moedas em análise'.", "Criptoativos têm volatilidade e risco regulatório muito acima da média.", termos=("Market cap", "FDV", "Volatilidade"),
       ini="Valor de mercado é o preço vezes a quantidade que existe; FDV é como se todas as moedas futuras já existissem."),
    _e("Ler tokenomics", "Mostra oferta circulante, oferta máxima e inflação da oferta.", "Compare valor de mercado e FDV: uma diferença grande indica muita oferta ainda a liberar.", "Cartões de oferta.",
       "Os dados vêm de fontes públicas e podem falhar.", termos=("FDV",)),
])

_add("cripto-onchain", "Adoção e on-chain", "Outros ativos", [
    _e("Uso real da rede", "Mostra números lidos direto da blockchain e estimativas de provedores.", "Escolha a moeda e olhe os indicadores de adoção.", "Cartões da página.",
       "Dado lido da rede é mais confiável que estimativa de provedor.", termos=("TVL", "Liquidez")),
    _e("Limites", "Nem toda rede tem dado gratuito integrado.", "Veja 'sem dado' como ausência de fonte, não como zero.", "Cartões marcados 'n/d'.", ""),
])

_add("cripto-receitas", "Receitas e emissão", "Outros ativos", [
    _e("Quanto o protocolo ganha", "Receita, taxas e emissão de moedas por protocolo.", "Escolha a moeda e compare receita e emissão.", "Cartões da página.",
       "Receita do protocolo não é o mesmo que valor para quem tem o token.", termos=("TVL", "FDV", "Valuation")),
])

_add("cripto-fundamentalista", "Análise fundamentalista de cripto", "Outros ativos", [
    _e("A nota de 0 a 100", "Sete pilares formam uma nota: utilidade, adoção, saúde econômica, tokenomics, segurança, desenvolvimento e valuation.", "Escolha o tipo do ativo e a moeda e leia a nota e os pilares.",
       "Seletores e cartões da página.", "Sem dado, sem nota; a nota provisória avisa quando a cobertura é baixa.", termos=("Market cap", "TVL", "Valuation")),
    _e("Ajuste os pesos", "Os pesos mudam conforme o tipo do ativo e podem ser ajustados.", "Abra 'Pesos dos pilares e dados informados por você'.", "Expansor de pesos.",
       "Mudar pesos muda a nota; teste se a conclusão se mantém."),
    _e("Justificativa", "A justificativa mostra de onde vem cada nota.", "Abra 'Justificativa das notas' e 'Como a nota é calculada'.", "Expansores da página.", _AVISO),
])

_add("cripto-avancada", "Análise avançada de cripto", "Outros ativos", [
    _e("Abas de análise", "Visão geral, Mercado, Fundamentos, Tokenomics, On-chain, Segurança, Valuation, Histórico, Comparação e Análise inteligente.", "Escolha a moeda e percorra as abas.",
       "Seletor 'Moeda em análise' e abas.", "Cada aba mostra o que não foi possível medir.", termos=("Market cap", "FDV", "TVL", "Valuation")),
    _e("Valuation e pares", "Compara múltiplos com concorrentes da categoria.", "Na aba Valuation, marque a comparação com concorrentes (consulta até 6 projetos).", "Aba Valuation.",
       "A mediana só aparece com 3 ou mais pares.", termos=("Valuation",)),
    _e("Desbloqueios", "Acompanhe eventos de liberação de tokens que podem pressionar o preço.", "Na aba Tokenomics, registre data, quantidade e fonte do desbloqueio.", "Seção 'Desbloqueios que você acompanha'.",
       "O registro é seu e não é validado pelo app."),
])

# ---------------------------------------------------------------------------------------------------------- educação, conta, planos, ajuda
_add("educacao", "Educação financeira", "Educação", [
    _e("Painel e exploração", "Painel, Explorar (ativos reais e simulações) e Professor (o assistente virtual). O Glossário tem página própria. As aulas e perguntas ficam na Jornada.", "Siga uma trilha por vez e responda os exercícios; seu progresso fica salvo.",
       "Abas no topo.", "Educação não é recomendação de investimento."),
    _e("Glossário", "Pesquise qualquer termo do app, com definição, exemplo, fórmula e limitações.", "Abra a aba Glossário e busque por sigla ou nome completo.", "Aba Glossário.", "", termos=("P/L",)),
])

_add("planos", "Planos", "Minha conta", [
    _e("O que cada plano oferece", "Mostra os limites diários de cada plano. Todas as ferramentas e os três níveis de conhecimento valem em todos.", "Compare os cartões e a tabela de comparação.",
       "Cartões e 'Comparar os planos'.", "O que muda é a quantidade de uso por dia."),
])

_add("conta", "Minha conta", "Minha conta", [
    _e("Seu modo de uso", "Escolha como o app se apresenta: Iniciante, Intermediário ou Avançado.", "Em 'Modo de uso', escolha, confira a prévia e confirme.", "Bloco 'Modo de uso'.",
       "Grátis, sem limite de trocas, e nenhum dado seu é alterado."),
    _e("Preferências", "Moeda, tema, período padrão, favoritos, ordem do painel e notificações.", "Ajuste e salve; as preferências ficam na sua conta.", "Seções da página.", ""),
    _e("Segurança e plano", "Veja seu plano e gerencie seus dados.", "Use as seções da conta e o atalho para Planos.", "Seções da página.", ""),
])

_add("ajuda", "Central de Ajuda", "Primeiros passos", [
    _e("Tutoriais por página", "Todos os tutoriais ficam aqui, organizados por categoria.", "Use a busca ou as categorias e abra o tutorial desejado.", "Seção Tutoriais.", ""),
    _e("Seu aprendizado", "Veja o que você já concluiu e continue de onde parou.", "Abra 'Meu aprendizado' e use Continuar ou Rever.", "Seção Meu aprendizado.", ""),
    _e("Termos e fontes", "Glossário rápido e diagnóstico das fontes de dados.", "Abra 'Termos básicos' ou 'Fontes de dados'.", "Seções da página.", ""),
])


# ---------------------------------------------------------------------------------------------------------- consulta
REGIOES = {"menu": "Menu lateral", "topo": "Topo da página", "abas": "Abas", "busca": "Busca", "cartoes": "Cartões e resultados", "conteudo": "Conteúdo da página"}


def regiao(onde: str) -> str:
    """Parte da tela que a etapa destaca no mapa, deduzida do 'Onde fica' (menu, topo, abas, busca, cartões ou conteúdo)."""
    o = (onde or "").lower()
    if "menu" in o or "barra lateral" in o:
        return "menu"
    if "topo" in o and ("botão" in o or "caixa" in o or "página" in o or "tela" in o) and "início" not in o:
        return "topo"
    if "aba" in o:
        return "abas"
    if any(x in o for x in ("campo", "busca", "analisar", "pesquis")):
        return "busca"
    if any(x in o for x in ("cartão", "cartões", "painel", "tabela", "gráfico", "grafico", "cartao")):
        return "cartoes"
    if "topo" in o:
        return "topo"
    return "conteudo"


def existe(url_path: str) -> bool:
    return url_path in TUTORIAIS


def get(url_path: str) -> dict | None:
    return TUTORIAIS.get(url_path)


def por_categoria() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in CATEGORIAS}
    for u, t in TUTORIAIS.items():
        out.setdefault(t["categoria"], []).append(u)
    return {c: v for c, v in out.items() if v}


def buscar(consulta: str) -> list[str]:
    import unicodedata

    def n(s):
        return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")
    q = n(consulta).strip()
    if not q:
        return list(TUTORIAIS)
    achados = []
    for u, t in TUTORIAIS.items():
        txt = n(" ".join([t["titulo"], t["categoria"], t["busca"]] + [e["titulo"] + " " + e["o_que"] + " " + e["como"] for e in t["etapas"]]))
        if q in txt:
            achados.append(u)
    return achados


def etapa_para_nivel(etapa: dict, modo: str) -> dict:
    """Blocos da etapa no nível: 'aprofundar' traz o texto do nível (ini/avanc) e o resto é comum."""
    extra = etapa["ini"] if modo == "iniciante" else (etapa["avanc"] if modo == "avancado" else "")
    return {**etapa, "nivel_extra": extra}
