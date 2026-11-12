"""Aparência de 'painel de jogo' das telas de análise de ativos (ações, FIIs, fundos, ETFs, renda fixa e cripto).
Módulo puro (só HTML e CSS): não muda dados, indicadores, gráficos nem regras. Age sobre as classes que as análises já usam
(.card, .kpi, .mini, stMetric, cabeçalho), então vale para todas as classes de ativo sem mexer nas páginas.
Componentes reutilizáveis em outras áreas: css(), html_destaque(). Animações leves (só transform/opacity) e desligadas para quem prefere menos movimento."""
from __future__ import annotations

import html

import arte_analisar as AA

# páginas de análise de ativos (url_path); só nelas o CSS é aplicado
PAGINAS = frozenset({
    "tipo", "acoes", "preco-justo", "valuation", "micro", "dividendos", "dcf", "tecnica", "tecnica-avancada", "stock-picking",
    "fiis", "etfs", "fundos-acoes", "multimercados", "fundos-renda-fixa", "renda-fixa", "tesouro-cdi",
    "criptomoedas", "cripto-onchain", "cripto-receitas", "cripto-fundamentalista", "cripto-avancada", "tecnica-cripto",
})

Q = "html body .stApp.stApp.stApp"


def aplica(url_path: str) -> bool:
    return url_path in PAGINAS


def html_destaque(titulo: str, texto: str, pose: str = "m_lupa", cor: str = "#3DDC97") -> str:
    """Cartão com o Caramelo: título, uma linha de apoio e arte de fundo. Serve para dicas e estados vazios em qualquer área."""
    mascote = AA.img(pose, "ad-m", "Caramelo")
    return (f"<div class='ad' style='--ac:{html.escape(cor)}'><div class='ad-bg'>{AA.img('i_crescimento', 'ad-art')}</div>{mascote}"
            f"<div class='ad-t'><b>{html.escape(titulo)}</b><span>{html.escape(texto)}</span></div></div>")


def html_vazio(nome_ativo: str = "uma empresa") -> str:
    return html_destaque("Escolha para começar", f"Selecione {nome_ativo} no campo acima e veja a análise completa em cards.")


def _arte(sel: str, nome: str, tam: int, op: float) -> str:
    u = AA.uri(nome)
    if not u:
        return ""
    return (f"{Q} {sel}::after{{content:'';position:absolute;right:8px;bottom:6px;width:{tam}px;height:{tam}px;background:url('{u}') center/contain no-repeat;"
            f"opacity:{op};pointer-events:none;transition:transform .25s ease,opacity .25s ease}}\n"
            f"{Q} {sel}:hover::after{{opacity:{min(op + .12, .5)};transform:translateY(-2px) scale(1.06)}}\n")


def css() -> str:
    c = f"""
@keyframes anUp{{from{{opacity:.5;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@keyframes anBoia{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
@keyframes anBrilho{{0%{{background-position:-120% 0}}100%{{background-position:220% 0}}}}
{Q} .card,{Q} .kpi,{Q} .mini{{position:relative;border:1px solid rgba(124,140,255,.30) !important;
  transition:border-color .2s ease,box-shadow .2s ease,transform .2s ease}}
{Q} .kpi,{Q} .mini{{animation:anUp .35s ease both}}
{Q} .card:hover,{Q} .kpi:hover,{Q} .mini:hover{{border-color:rgba(139,108,255,.85) !important;
  box-shadow:0 0 0 1px rgba(139,108,255,.35),0 8px 22px -10px rgba(139,108,255,.65) !important}}
{Q} .card:active,{Q} .kpi:active,{Q} .mini:active{{transform:scale(.985)}}
{Q} [data-testid="stMetric"]{{position:relative;overflow:hidden;padding:10px 12px !important;border-radius:16px;
  background:linear-gradient(160deg,rgba(60,50,160,.38),rgba(15,11,43,.6));border:1px solid rgba(124,140,255,.32);
  transition:border-color .2s ease,box-shadow .2s ease}}
{Q} [data-testid="stMetric"]:hover{{border-color:rgba(61,220,151,.7);box-shadow:0 0 16px -6px rgba(61,220,151,.7)}}
{Q} [data-testid="stMetricDelta"]{{font-weight:800}}
{Q} [data-testid="stExpander"]{{border-radius:16px !important;border:1px solid rgba(124,140,255,.28) !important;overflow:hidden}}
{Q} .pgi{{box-shadow:0 0 18px -4px rgba(139,108,255,.9),inset 0 0 0 1px rgba(170,160,255,.45)}}
{Q} .pgm{{animation:anBoia 3.6s ease-in-out infinite}}
{Q} .pgm img,{Q} .pgm svg{{filter:drop-shadow(0 6px 10px rgba(0,0,0,.45))}}
/* destaque com o Caramelo */
{Q} .ad{{position:relative;overflow:hidden;display:flex;align-items:center;gap:8px;padding:10px 14px 10px 6px;margin:6px 0 12px;border-radius:22px;
  background:radial-gradient(circle at 12% 40%,color-mix(in srgb,var(--ac) 28%,transparent),transparent 55%),linear-gradient(160deg,#142060,#0F1740 85%);
  border:1.5px solid color-mix(in srgb,var(--ac) 75%,transparent);box-shadow:0 0 20px -8px var(--ac)}}
{Q} .ad-bg{{position:absolute;inset:0;pointer-events:none}}
{Q} .ad-art{{position:absolute;right:10px;bottom:6px;width:74px;height:auto;opacity:.18}}
{Q} .ad-m{{position:relative;flex:0 0 auto;width:clamp(78px,24vw,120px);height:auto;animation:anBoia 3.6s ease-in-out infinite;filter:drop-shadow(0 6px 10px rgba(0,0,0,.45))}}
{Q} .ad-t{{position:relative;min-width:0}}
{Q} .ad-t b{{display:block;color:#fff !important;-webkit-text-fill-color:#fff !important;font-size:clamp(1rem,4.2vw,1.3rem);font-weight:900}}
{Q} .ad-t span{{display:block;margin-top:2px;color:#CFCBFF !important;-webkit-text-fill-color:#CFCBFF !important;font-size:clamp(.8rem,3.2vw,.98rem);line-height:1.3}}
@media (prefers-reduced-motion:reduce){{{Q} .kpi,{Q} .mini,{Q} .pgm,{Q} .ad-m{{animation:none !important}}}}
"""
    c += _arte(".kpi", "i_crescimento", 46, .16)
    c += _arte(".mini", "i_lupa_grafico", 40, .15)
    c += _arte(".card", "i_relatorio", 52, .12)
    return "<style>" + c + "</style>"
