"""Layout compacto para smartphones (até 640 px de largura). UMA camada de CSS para o app inteiro.

Regras desta camada (conferidas em test_layout_mobile.py):
 · Só mexe em ESPAÇO: padding, margin, gap, row-gap e min-height. Nenhuma cor, gradiente, fonte, ícone, borda, arredondamento ou sombra.
 · Tudo fica dentro de `@media (max-width:640px)`: tablet e computador continuam exatamente como estavam.
 · Nada é removido, escondido ou movido de lugar. A única coisa que some é o item VAZIO que cada `st.markdown("<style>...")` deixa na página
   (o Streamlit reserva um gap de 16 px para ele, e o app injeta vários no topo de cada tela). O CSS dentro dele continua valendo.
 · Os ajustes são os mesmos em todas as páginas, regulados por três variáveis no começo do bloco (`--m-gap`, `--m-pad`, `--m-sec`).
   Para afrouxar ou apertar tudo de uma vez, é só mudar esses três valores. Para desligar, `LAYOUT_COMPACTO = False` no app.py.
 · Seletores globais usam `:where()` (especificidade zero) para nunca vencer o CSS próprio de um componente; seletores de componentes
   usam o prefixo `.stApp` para vencer o CSS injetado depois por cada página.

Etapas (PLANO_LAYOUT_MOBILE.md): 1 auditoria · 2 base global · 3 componentes comuns · 4 telas específicas · 5 verificação.
"""
from __future__ import annotations

LARGURA_MAX = 640        # px: celulares. Acima disso nada muda.

# ---- Etapa 2 · base global: área útil, ritmo vertical e itens fantasma ----
_BASE = """
  :root{--m-gap:.6rem; --m-pad:12px; --m-sec:12px;}
  .block-container{padding-top:3.85rem !important; padding-bottom:6rem !important;
    padding-left:max(.75rem, env(safe-area-inset-left)) !important; padding-right:max(.75rem, env(safe-area-inset-right)) !important;}
  /* ritmo vertical: de 16 px (padrão do Streamlit) para ~10 px entre elementos; quem define gap próprio continua com o dele */
  :where([data-testid="stMain"]) [data-testid="stVerticalBlock"]{gap:var(--m-gap);}
  :where([data-testid="stMain"]) [data-testid="stHorizontalBlock"]{gap:.5rem; row-gap:.5rem;}
  /* itens fantasma: st.markdown só com <style> ocupa 0 px, mas o gap do Streamlit reserva 16 px para cada um */
  [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] > [data-testid="stMarkdownContainer"] > style:only-child),
  [data-testid="stElementContainer"]:has(> [data-testid="stMarkdownContainer"] > style:only-child),
  [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] > [data-testid="stMarkdownContainer"]:empty){display:none;}
  /* texto corrido e títulos */
  [data-testid="stMain"] [data-testid="stMarkdownContainer"] p{margin-bottom:.45rem;}
  [data-testid="stMain"] [data-testid="stMarkdownContainer"] > :last-child{margin-bottom:0;}
  [data-testid="stMain"] :is(h1,h2,h3,h4,h5,h6){padding-top:.3rem !important; padding-bottom:.15rem !important;}
  .stApp hr{margin:var(--m-sec) 0 !important;}
"""

# ---- Etapa 3 · componentes comuns (mesmos valores em todas as telas) ----
_COMPONENTES = """
  .stApp .pghead{margin:0 0 var(--m-sec) !important; padding:var(--m-pad) 14px !important;}
  .stApp .card{padding:var(--m-pad) 14px; margin-bottom:10px;}
  .stApp :is(.kpi,.mini,.ctx){padding:var(--m-pad);}
  .stApp .cartao{padding:16px; margin-bottom:10px;}
  .stApp .vazio{padding:20px 16px;}
  .stApp .sc{padding:var(--m-pad) 14px !important;}
  .stApp .rc{padding:var(--m-pad) 14px !important; margin-bottom:6px;}
  .stApp .rs-top{padding:var(--m-pad) 14px !important;}
  .stApp .rs-box{padding:var(--m-pad) 14px;}
  .stApp .rs-concl{padding:10px 14px;}
  .stApp .pv{padding:10px 14px; margin:6px 0;}
  .stApp .sec-sub{margin:var(--m-sec) 0 6px;}
  .stApp [data-testid="stMetric"]{padding:10px 12px;}
  .stApp [data-testid="stForm"]{padding:.75rem;}
  .stApp [data-testid="stExpanderDetails"]{padding:.5rem .75rem .75rem;}
  .stApp [data-testid="stAlert"]{padding:.6rem .75rem;}
"""

# ---- Etapa 4 · telas específicas ----
_TELAS = """
  /* Início: faixa do topo e busca flutuante (a busca continua sobrepondo a faixa, com a mesma proporção) */
  .stApp .hero2{padding:22px 16px 70px;}
  .stApp .hero2.com-abas{padding-top:22px;}
  .stApp .hero2.com-abas h1{margin-top:var(--m-gap);}
  .stApp .st-key-home_busca_box{margin-top:-52px !important; padding:var(--m-pad) !important;}
  /* Jornada */
  .stApp .jor-stats{margin:0 0 4px;}
  .stApp .jor-un{margin:12px auto 10px;}
  .stApp .jor-real{margin:12px auto 4px; padding:10px 14px;}
  /* Jogar */
  .stApp .jg-pills{margin:2px 0 6px;}
  .stApp .jg-sec{margin:var(--m-sec) 0 4px;}
  .stApp .jg-card{margin:6px 0; padding:10px 12px;}
  /* Educação */
  .stApp .ed-card{margin:6px 0; padding:10px 12px;}
  .stApp .ed-ind{margin:4px 0 8px;}
"""


def css() -> str:
    """Bloco <style> único, para ser injetado uma vez por execução, depois de todo o CSS global e antes de a página rodar."""
    corpo = _BASE + _COMPONENTES + _TELAS
    return f"<style>/* layout compacto para smartphones */\n@media (max-width:{LARGURA_MAX}px){{{corpo}}}\n</style>"
