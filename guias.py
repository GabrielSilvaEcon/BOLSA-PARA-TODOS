"""
Guias das páginas: no topo, para que serve o método e o que ele entrega;
no fim, um relatório escrito com prós e contras.

Uso no app.py (veja as instruções): guias.topo(pg.url_path) antes de pg.run()
e guias.fim(pg.url_path) depois. As chaves abaixo são os url_path das páginas.
"""

import streamlit as st

GUIAS = {
    "preco-justo": {
        "icone": "🎯", "titulo": "Preço justo (Graham + Bazin)",
        "serve": "Estimar quanto a ação deveria valer a partir do lucro, do patrimônio e dos dividendos da empresa, "
                 "e comparar com o preço de mercado.",
        "entrega": "O preço justo de cada ação, a margem de segurança (folga entre o preço justo e o preço atual), "
                   "um semáforo (abaixo, no ponto ou acima do justo) e a tendência do gráfico diário.",
        "resumo": "É o ponto de partida mais simples para saber se uma ação está cara ou barata. Graham olha para "
                  "lucro e patrimônio e é mais adequado a empresas lucrativas e estáveis. Bazin olha para os "
                  "dividendos e funciona melhor em boas pagadoras. Juntos dão uma referência rápida, mas ela "
                  "nasce de fórmulas fixas, que não enxergam crescimento, dívida nem mudanças recentes no negócio.",
        "pros": ["Simples, transparente e fácil de comparar entre empresas.",
                 "Foca na margem de segurança, que protege contra erros de estimativa.",
                 "Bazin valoriza empresas que distribuem renda; Graham valoriza lucro e patrimônio reais.",
                 "Resultado imediato, sem precisar projetar o futuro."],
        "contras": ["Graham ignora crescimento e fica distorcido quando LPA ou VPA são baixos, negativos ou instáveis.",
                    "Bazin depende dos dividendos passados e pune quem reinveste o lucro para crescer.",
                    "Não considera dívida, setor nem qualidade do negócio.",
                    "Preço justo é uma conta, não uma previsão: o mercado pode ficar longe dele por anos."],
        "veredito": "Boa para uma primeira triagem. Use junto com DCF, indicadores de saúde e a tendência antes de decidir.",
    },
    "dcf": {
        "icone": "🧮", "titulo": "Fluxo de caixa descontado (DCF)",
        "serve": "Estimar o valor da empresa pelo dinheiro que ela deve gerar nos próximos anos, trazido para valores de hoje.",
        "entrega": "O valor justo por ação, o potencial frente ao preço atual, uma tabela de sensibilidade "
                   "(taxa de desconto × crescimento) e cenários pessimista, base e otimista.",
        "resumo": "O DCF responde a pergunta \"quanto vale o caixa que esta empresa vai gerar?\". É o método mais "
                  "completo do painel, porque obriga você a explicitar suas premissas. Por isso mesmo é o mais "
                  "sensível: pequenas mudanças na taxa de desconto ou na perpetuidade mudam muito o resultado.",
        "pros": ["Baseia-se em caixa, que é mais difícil de maquiar do que o lucro contábil.",
                 "Premissas explícitas e ajustáveis: você vê o que está assumindo.",
                 "A sensibilidade mostra o quanto o resultado depende das premissas.",
                 "Considera o crescimento futuro, que Graham e Bazin ignoram."],
        "contras": ["Muito sensível à taxa de desconto e à perpetuidade; o valor terminal costuma ser a maior parte do valor.",
                    "Fluxo de caixa histórico é volátil e pode não representar o futuro.",
                    "Não se aplica bem a bancos e seguradoras.",
                    "Passa falsa sensação de precisão: o número final é fruto de opiniões."],
        "veredito": "Use como faixa de valor, não como número exato. Compare sempre os três cenários.",
    },
    "valuation": {
        "icone": "⚖️", "titulo": "Múltiplos (P/L, P/VP, EV/EBITDA...)",
        "serve": "Comparar rapidamente empresas e verificar se uma ação está cara ou barata em relação a lucro, "
                 "patrimônio e geração de caixa.",
        "entrega": "P/L, P/VP, EV/EBITDA, dividend yield, ROE, margem líquida e Dív./PL lado a lado, com gráfico e explicação de cada um.",
        "resumo": "Múltiplos são atalhos: dividem o preço (ou o valor da empresa) por algum resultado. Servem muito bem "
                  "para comparar empresas parecidas, mas dizem pouco sozinhos, porque um múltiplo baixo pode "
                  "indicar oportunidade ou um problema real no negócio.",
        "pros": ["Rápidos e padronizados: é a linguagem comum do mercado.",
                 "Permitem comparar empresas do mesmo setor.",
                 "Cada indicador mostra um ângulo (lucro, patrimônio, dívida, retorno).",
                 "Fáceis de acompanhar ao longo do tempo."],
        "contras": ["Só comparam bem dentro do mesmo setor; entre setores enganam.",
                    "Lucros extraordinários distorcem o P/L.",
                    "Empresa barata pode estar barata por um bom motivo (armadilha de valor).",
                    "Olham o passado; não mostram o futuro. EV/EBITDA não se aplica a bancos."],
        "veredito": "Ótimos para comparar pares e levantar perguntas, péssimos para decidir sozinhos.",
    },
    "dividendos": {
        "icone": "💰", "titulo": "Dividendos",
        "serve": "Ver quanto a empresa devolveu aos sócios e com que regularidade.",
        "entrega": "Dividendos por ação ano a ano, proventos dos últimos 12 meses, média de 5 anos e dividend yield.",
        "resumo": "Dividendos mostram caixa que realmente saiu da empresa para o acionista. A regularidade ao longo "
                  "dos anos importa mais do que um único ano alto, que pode ter sido um pagamento extraordinário "
                  "ou ter vindo de uma queda do preço da ação.",
        "pros": ["Renda concreta, que não depende de vender a ação.",
                 "Sinaliza geração de caixa e disciplina da gestão.",
                 "A regularidade indica previsibilidade do negócio.",
                 "Fácil de entender e acompanhar."],
        "contras": ["Yield muito alto pode ser sinal de problema (preço caiu) ou pagamento que não se repete.",
                    "O passado não garante pagamentos futuros.",
                    "Empresas em crescimento pagam pouco e podem ser ótimas mesmo assim.",
                    "Regras de tributação e tipos de provento (dividendos, JCP) podem mudar o retorno líquido."],
        "veredito": "Olhe a média de vários anos e a consistência, não o yield de um ano isolado.",
    },
    "tecnica": {
        "icone": "📉", "titulo": "Gráfico e análise técnica",
        "serve": "Ler o comportamento do preço e do volume: tendência, suportes, resistências e sinais de candle.",
        "entrega": "O gráfico limpo (TradingView) e um gráfico com sinais de candlestick, padrões gráficos e indicadores "
                   "(médias móveis, IFR, volume), com a contagem de sinais de alta, baixa e indecisão.",
        "resumo": "A análise técnica estuda o que o mercado já fez com o preço, e não o valor da empresa. É útil para "
                  "o momento de entrar e sair e para ver se a tendência ajuda ou atrapalha. Seus sinais são "
                  "probabilidades, não certezas, e erram com frequência.",
        "pros": ["Ajuda no timing: onde entrar, sair e colocar um limite de perda.",
                 "Mostra a tendência e a força do movimento.",
                 "Funciona em qualquer ativo com boa liquidez.",
                 "Reflete a psicologia dos participantes do mercado."],
        "contras": ["Gera muitos sinais falsos, principalmente em mercado lateral.",
                    "Padrões gráficos têm um grau de subjetividade.",
                    "Ignora a saúde e o valor da empresa.",
                    "Funciona pior em ações de baixa liquidez."],
        "veredito": "Boa como complemento da análise fundamentalista, para decidir o momento, nunca para escolher a empresa.",
    },
    "micro": {
        "icone": "🏢", "titulo": "Indicadores das empresas",
        "serve": "Avaliar a saúde do negócio: rentabilidade, margens e endividamento.",
        "entrega": "Uma matriz com preço, LPA, VPA, EV/EBITDA, dividend yield, ROE, margem líquida e Dív./PL.",
        "resumo": "Mostra se a empresa é boa em ganhar dinheiro e se está equilibrada financeiramente. É a base para "
                  "separar empresas sólidas de empresas frágeis antes mesmo de olhar o preço.",
        "pros": ["Mostra a qualidade do negócio, não só o preço.",
                 "Ajuda a evitar empresas muito endividadas ou pouco rentáveis.",
                 "Une rentabilidade, margem e dívida numa só tabela.",
                 "Fácil de acompanhar de um balanço para o outro."],
        "contras": ["É uma foto do último balanço, com defasagem.",
                    "Indicadores de setores diferentes não são comparáveis.",
                    "Dív./PL não faz sentido para bancos e seguradoras.",
                    "ROE alto pode vir de endividamento excessivo, não de eficiência."],
        "veredito": "Use para eliminar empresas frágeis e entender o porquê de um múltiplo estar alto ou baixo.",
    },
    "stock-picking": {
        "icone": "🏆", "titulo": "Ranking (Stock picking)",
        "serve": "Dar uma nota de 0 a 100 para cada empresa e ordená-las, reunindo vários critérios numa só leitura.",
        "entrega": "Nota geral e notas de seis pilares (valor, qualidade, dividendos, solidez, tendência e risco), com "
                   "pesos do seu perfil, ranking, gráfico de valor × qualidade e radar.",
        "resumo": "O ranking junta valor, qualidade, renda, solidez, tendência e risco numa nota comparável. É ótimo "
                  "para decidir quais empresas estudar primeiro. Mas a nota depende de pesos e limites escolhidos "
                  "por convenção, e uma nota alta não significa uma boa compra.",
        "pros": ["Combina várias visões em um número fácil de comparar.",
                 "Mostra os pilares, então dá para ver por que a nota saiu assim.",
                 "Pesos ajustáveis ao seu perfil de investidor.",
                 "Economiza tempo na triagem de muitas empresas."],
        "contras": ["Pesos e limites das notas são escolhas subjetivas.",
                    "Pilar sem dados é ignorado e os pesos são redistribuídos, o que pode inflar a nota.",
                    "Não enxerga governança, notícias ou riscos do negócio.",
                    "Nota alta não é recomendação: depende do que você já tem na carteira."],
        "veredito": "Use para organizar o estudo. A decisão final exige olhar os detalhes de cada empresa.",
    },
    "perfis": {
        "icone": "🧭", "titulo": "Perfis e cenários",
        "serve": "Ver como a mesma empresa é avaliada por um investidor Conservador, Moderado ou Arrojado.",
        "entrega": "Notas por perfil, potencial do DCF por perfil, cenários pessimista, base e otimista e a tabela com as premissas de cada perfil.",
        "resumo": "Mostra que \"boa\" ou \"cara\" depende de quanto risco e de que retorno você aceita. É uma forma "
                  "didática de entender o efeito das premissas, não um teste de perfil de investidor.",
        "pros": ["Mostra como a tolerância ao risco muda a conclusão.",
                 "Cenários ajudam a ver o intervalo de resultados possíveis.",
                 "Premissas ficam visíveis e comparáveis.",
                 "Didático para quem está começando."],
        "contras": ["Os perfis são simplificações educacionais; o suitability real é feito com sua corretora.",
                    "Os cenários são variações fixas sobre as premissas-base.",
                    "Depende do DCF, que não se aplica a bancos e seguradoras.",
                    "Pode dar impressão de precisão onde só há estimativa."],
        "veredito": "Use para entender o efeito do risco nas conclusões, e não para definir seu perfil.",
    },
    "oportunidades": {
        "icone": "🧪", "titulo": "Buscador de oportunidades",
        "serve": "Filtrar empresas do catálogo que atendam aos critérios que você considera de uma boa empresa.",
        "entrega": "Uma lista de empresas que passam nos critérios escolhidos, com os indicadores e o que cada uma falhou, e a opção de adicioná-las à análise.",
        "resumo": "É um funil: você define o que é uma boa empresa e o buscador mostra quem passa. Poupa tempo, mas só "
                  "enxerga números, e critérios muito rígidos podem descartar boas empresas.",
        "pros": ["Triagem rápida entre muitas empresas.",
                 "Critérios transparentes e ajustáveis.",
                 "Mostra onde cada empresa falhou, o que ajuda a aprender.",
                 "Já leva as escolhidas para as outras análises."],
        "contras": ["Limitado às empresas do catálogo.",
                    "Dado ausente conta como critério não atendido.",
                    "Critérios quantitativos não captam qualidade de gestão ou vantagens competitivas.",
                    "Os dados vêm do Yahoo Finance e podem ter falhas."],
        "veredito": "Ótimo para gerar uma lista de candidatas. Cada uma ainda precisa ser estudada.",
    },
    "macro": {
        "icone": "🌐", "titulo": "Cenário econômico",
        "serve": "Acompanhar os números da economia que influenciam as empresas: juros, inflação, câmbio, atividade, consumo e emprego.",
        "entrega": "Séries do Banco Central e do Ipeadata com a última leitura, a variação e uma nota sobre o que observar em cada indicador.",
        "resumo": "O ambiente econômico muda o valor das empresas: juros altos encarecem o capital, câmbio favorece "
                  "exportadoras ou importadoras, inflação mexe em custos e contratos. Aqui você vê o contexto, mas o "
                  "efeito em cada ação é indireto e depende do setor.",
        "pros": ["Dá contexto para interpretar os números das empresas.",
                 "Ajuda a entender ciclos de juros, inflação e atividade.",
                 "Mostra riscos que afetam setores inteiros.",
                 "Dados oficiais e gratuitos."],
        "contras": ["Os indicadores saem com defasagem de semanas.",
                    "A ligação com o preço de uma ação é indireta e nem sempre clara.",
                    "Muitas séries, difícil transformar em decisão prática.",
                    "Números são revisados depois da divulgação."],
        "veredito": "Use como pano de fundo da análise, e não como gatilho de compra ou venda.",
    },
    "carteira": {
        "icone": "💼", "titulo": "Minha carteira",
        "serve": "Simular uma carteira de ações sem risco (fictícia) ou registrar a sua carteira real para acompanhar o desempenho.",
        "entrega": "Posições, custo, valor atual, resultado em R$ e %, peso de cada ativo, alocação e evolução do valor da carteira no tempo.",
        "resumo": "Acompanhar a carteira transforma ideias em resultados que você pode medir. A carteira fictícia "
                  "permite testar uma tese sem arriscar dinheiro. Vale lembrar que o resultado aqui é simplificado: "
                  "não considera dividendos, custos nem impostos.",
        "pros": ["Testa estratégias sem risco real (carteira fictícia).",
                 "Mostra concentração: quanto cada ativo pesa no total.",
                 "Resultado e evolução acompanhados num só lugar.",
                 "Os dados podem ser exportados e importados em CSV."],
        "contras": ["Não inclui dividendos, corretagem nem impostos.",
                    "Preços do Yahoo Finance podem ter atraso.",
                    "Os dados ficam só nesta sessão; exporte o CSV para não perder.",
                    "Resultados de curto prazo não provam que uma estratégia funciona."],
        "veredito": "Boa para disciplinar o acompanhamento. Para decisões e impostos, confira sempre os extratos da sua corretora.",
    },
}


def topo(chave: str):
    """Caixa de orientação no início da página."""
    g = GUIAS.get(chave)
    if not g:
        return
    st.info(f"**{g['icone']} {g['titulo']}**\n\n"
            f"**Este método serve para:** {g['serve']}\n\n"
            f"**O que ele te entrega:** {g['entrega']}")


def fim(chave: str):
    """Relatório escrito com prós e contras no final da página."""
    g = GUIAS.get(chave)
    if not g:
        return
    st.divider()
    st.markdown(f"### 📝 Relatório: prós e contras de {g['titulo']}")
    st.write(g["resumo"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**✅ Prós**")
        st.markdown("\n".join(f"- {p}" for p in g["pros"]))
    with c2:
        st.markdown("**⚠️ Contras**")
        st.markdown("\n".join(f"- {c}" for c in g["contras"]))
    st.markdown(f"**Conclusão:** {g['veredito']}")
    st.caption("Texto educacional. Não é recomendação de compra ou venda.")
