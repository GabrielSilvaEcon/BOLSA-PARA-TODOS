"""Design system v2 (Etapa 2 do redesign). Módulos puros: não importam o Streamlit nem alteram regra de negócio.

tokens.py      valores compartilhados (tipografia, espaço, raios, toque, movimento), exportáveis para JSON
temas.py       paletas dos três ambientes (aprender, analise, wallet) + a "concha" compartilhada (barra inferior)
componentes.py HTML dos componentes reutilizáveis (cartão, indicador, selo, skeleton)
css.py         gera o CSS a partir dos tokens e do tema da página aberta

Chave de desligamento: DESIGN_V2 no app.py (False = visual de antes).
"""
