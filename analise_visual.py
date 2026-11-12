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


def html_roteiro(itens: list[dict], cores: dict) -> str:
    """Roteiro de decisão em cartões paralelos (2 por linha). itens: [{'cor','pergunta','texto'}]; cores: nome → hex."""
    caixas = "".join(
        f"<div class='ck' style='--ck:{cores.get(i.get('cor'), '#BDB5E6')}'><div class='ck-p'><i></i>{html.escape(str(i.get('pergunta', '')))}</div>"
        f"<div class='ck-t'>{html.escape(str(i.get('texto', '')))}</div></div>" for i in itens)
    return (f"<style>{_ROTEIRO}</style><div class='ck-w'><div class='ck-h'>{AA.img('i_alvo', 'ck-i')}Roteiro de decisão (educativo)</div><div class='ck-g'>{caixas}</div>"
            "<div class='ck-f'>Verde: ok · Amarelo: atenção · Vermelho: ponto fraco. É um roteiro para pensar, não recomendação de compra ou venda.</div></div>")


def html_grade(cartoes: list[str]) -> str:
    """Cartões de resultado lado a lado (2 por linha), tudo num bloco só de HTML: não depende da estrutura do Streamlit."""
    return f"<style>{_GRADE}</style><div class='rcg'>{''.join(cartoes)}</div>"


def _arte(sel: str, nome: str, tam: int, op: float) -> str:
    u = AA.uri(nome)
    if not u:
        return ""
    return (f"{Q} {sel}::after{{content:'';position:absolute;right:8px;bottom:6px;width:{tam}px;height:{tam}px;background:url('{u}') center/contain no-repeat;"
            f"opacity:{op};pointer-events:none;transition:transform .25s ease,opacity .25s ease}}\n"
            f"{Q} {sel}:hover::after{{opacity:{min(op + .12, .5)};transform:translateY(-2px) scale(1.06)}}\n")


_COMPACTO = f"""
/* leitura rápida e resumo executivo mais enxutos (menos rolagem) */
{Q} .rc{{padding:10px 12px;margin-bottom:6px;min-height:0}}
{Q} .rc-ic{{width:30px;height:30px;font-size:.95rem}}
{Q} .rc-t{{font-size:.92rem}}
{Q} .rc-b{{padding:3px 9px;font-size:.66rem}}
{Q} .rc-n{{font-size:.76rem;margin-top:4px;line-height:1.3}}
{Q} .rc-g{{grid-template-columns:repeat(auto-fit,minmax(88px,1fr));gap:6px;margin-top:8px}}
{Q} .rc-m{{padding:6px 9px;border-radius:11px}}
{Q} .rc-l{{font-size:.58rem;letter-spacing:.05em}}
{Q} .rc-v{{font-size:.98rem;margin-top:1px}}
{Q} .rc-w{{font-size:.72rem;margin-top:8px}}
{Q} .rs{{gap:8px;margin:4px 0 10px}}
{Q} .rs-top{{flex-direction:row !important;align-items:center;gap:10px;padding:10px 12px}}
{Q} .rs-seal{{min-width:74px;padding:7px 8px;font-size:.95rem;border-radius:12px}}
{Q} .rs-seal small{{font-size:.5rem}}
{Q} .rs-k{{font-size:.6rem}}
{Q} .rs-tx{{font-size:.8rem;line-height:1.35;margin-top:2px}}
{Q} .rs-grid{{grid-template-columns:1fr 1fr !important;gap:8px}}
{Q} .rs-box{{padding:9px 10px;border-radius:16px}}
{Q} .rs-h{{font-size:.82rem;margin-bottom:4px}}
{Q} .rs-box li{{font-size:.72rem;line-height:1.3;margin:5px 0;padding-left:13px}}
{Q} .rs-box li::before{{width:6px;height:6px;top:.5em}}
/* nome do ativo e botão de carteira na mesma linha */
{Q} [data-testid="stHorizontalBlock"]:has(.tk){{flex-wrap:nowrap !important;gap:8px !important;align-items:center}}
{Q} [data-testid="stHorizontalBlock"]:has(.tk)>[data-testid="stColumn"]{{min-width:0 !important}}
{Q} [data-testid="stHorizontalBlock"]:has(.tk) button,{Q} [data-testid="stHorizontalBlock"]:has(.tk) summary{{font-size:.74rem !important;padding:4px 8px !important;min-height:38px !important}}
{Q} [data-testid="stMain"] [data-testid="stVerticalBlock"]{{gap:.6rem}}
/* menus expansivos por categoria */
{Q} [data-testid="stExpander"] summary{{padding:9px 12px !important;background:linear-gradient(160deg,rgba(80,60,190,.40),rgba(15,11,43,.55))}}
{Q} [data-testid="stExpander"] summary p{{font-size:.95rem !important;font-weight:800 !important;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{Q} [data-testid="stExpander"] summary svg{{color:#8CFFB4}}
{Q} [data-testid="stExpander"] [data-testid="stExpanderDetails"]{{padding:8px 6px 6px !important}}
"""


_GRADE = f"""
/* resultados em cartões paralelos (2 por linha) */
{Q} .rcg{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:8px !important;margin:4px 0 8px;align-items:start}}
{Q} .rcg .rc{{padding:8px 9px;margin:0;min-height:0;height:100%;border-radius:18px;box-sizing:border-box}}
{Q} .rcg .rc-h{{gap:7px;flex-wrap:wrap}}
{Q} .rcg .rc-ic{{width:26px;height:26px;border-radius:10px;font-size:.95rem}}
{Q} .rcg .rc-t{{font-size:.82rem;flex:1 1 60px}}
{Q} .rcg .rc-b{{padding:2px 8px;font-size:.62rem;white-space:normal;text-align:center}}
{Q} .rcg .rc-g{{display:flex !important;flex-direction:column;gap:4px;margin-top:8px}}
{Q} .rcg .rc-m{{display:flex;justify-content:space-between;align-items:baseline;gap:6px;padding:5px 8px;border-radius:10px}}
{Q} .rcg .rc-l{{font-size:.58rem;letter-spacing:.04em}}
{Q} .rcg .rc-v{{font-size:.92rem;margin:0;text-align:right}}
{Q} .rcg .rc-n,{Q} .rcg .rc-w{{font-size:.72rem;margin-top:6px}}
"""


_ROTEIRO = f"""
/* roteiro em 2x2 */
{Q} .ck-w{{margin:6px 0 4px;padding:10px;border-radius:18px;border:1px solid rgba(189,181,230,.28);background:linear-gradient(160deg,#1B1442,#120D36)}}
{Q} .ck-h{{display:flex;align-items:center;gap:8px;color:#C5B3FF !important;-webkit-text-fill-color:#C5B3FF;font-weight:800;font-size:.9rem;margin-bottom:8px}}
{Q} .ck-i{{width:26px;height:auto}}
{Q} .ck-g{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
{Q} .ck{{position:relative;padding:8px 9px 9px;border-radius:14px;border:1px solid color-mix(in srgb,var(--ck) 55%,transparent);
  background:linear-gradient(160deg,color-mix(in srgb,var(--ck) 16%,#150F38),#120D36)}}
{Q} .ck-p{{display:flex;gap:6px;align-items:flex-start;color:#fff !important;-webkit-text-fill-color:#fff;font-weight:800;font-size:.78rem;line-height:1.2}}
{Q} .ck-p i{{flex:0 0 10px;height:10px;margin-top:3px;border-radius:50%;background:var(--ck);box-shadow:0 0 8px var(--ck)}}
{Q} .ck-t{{margin-top:4px;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF;font-size:.74rem;line-height:1.3}}
{Q} .ck-f{{margin-top:8px;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6;font-size:.68rem;line-height:1.3}}
"""


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

/* cabeçalho enxuto (menos rolagem) */
{Q} .pghead{{padding:6px 54px 6px 8px !important;margin:0 0 6px !important}}
{Q} .pghead .pgm{{margin:-4px 8px -4px 0}}
{Q} .pghead .pgm img,{Q} .pghead .pgm svg{{width:72px !important;height:auto !important}}
/* busca no mesmo padrão do Wallet Game: cartão com o Caramelo, campo em pílula e sugestões logo abaixo */
{Q} .st-key-ux_cb_acoes{{min-height:0 !important;padding:10px 12px !important;margin:2px 0 6px !important}}
{Q} .st-key-ux_cb_acoes .cux-tr img{{max-height:74px !important}}
{Q} .st-key-ux_cb_acoes .cux-bal{{font-size:.66rem !important}}
{Q} .st-key-ux_cb_acoes [data-testid="stTextInputRootElement"]{{border-radius:999px !important;border:2px solid #36B7E8 !important;background:#0B1433 !important;
  min-height:48px;box-shadow:0 0 14px rgba(54,183,232,.28);padding-left:6px}}
{Q} .st-key-ux_cb_acoes :is([data-baseweb="input"],[data-baseweb="base-input"],input){{border:0 !important;outline:none !important;box-shadow:none !important;
  background:transparent !important;color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:700 !important}}
{Q} .st-key-an_sugs{{background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C;border-radius:18px;padding:6px 8px;margin:0 0 8px;gap:.35rem !important}}
{Q} .st-key-an_sugs button{{min-height:42px !important;justify-content:flex-start;border-radius:12px !important;
  background:rgba(54,183,232,.10) !important;border:1px solid rgba(54,183,232,.35) !important}}
{Q} .st-key-an_sugs button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:700 !important;font-size:.9rem !important}}
{Q} .st-key-an_chips{{display:flex !important;flex-direction:row !important;flex-wrap:wrap;gap:6px !important;margin:0 0 6px}}
{Q} .st-key-an_chips>div{{width:auto !important;flex:0 0 auto !important}}
{Q} .st-key-an_chips button{{min-height:34px !important;padding:0 12px !important;border-radius:999px !important;background:rgba(139,108,255,.28) !important;
  border:1px solid rgba(139,108,255,.8) !important}}
{Q} .st-key-an_chips button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important;font-size:.85rem !important}}
{_GRADE}
{_COMPACTO}
{_ROTEIRO}
@media (prefers-reduced-motion:reduce){{{Q} .kpi,{Q} .mini,{Q} .pgm,{Q} .ad-m{{animation:none !important}}}}
"""
    c += _arte(".kpi", "i_crescimento", 46, .16)
    c += _arte(".mini", "i_lupa_grafico", 40, .15)
    c += _arte(".card", "i_relatorio", 52, .12)
    return "<style>" + c + "</style>"
