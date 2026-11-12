"""Visual da tela Analisar: cartão de abertura com o mascote e um cartão colorido por tipo de ativo, com arte própria ao fundo.
Só aparência (HTML e CSS): as páginas, os planos e os botões continuam em app._pagina_hub."""
from __future__ import annotations

import html

import arte_analisar as AA
import jornada_arte as ART
import tema

Q = "html body .stApp.stApp.stApp"

# arte de fundo de cada cartão (traço simples na cor do tipo; fica atrás do texto, com pouca opacidade)
_ARTE = {
    "acoes": "<path d='M8 70h104' /><rect x='18' y='48' width='10' height='22'/><rect x='40' y='38' width='10' height='32'/><rect x='62' y='26' width='10' height='44'/>"
             "<rect x='84' y='12' width='10' height='58'/><path d='M12 52l30-14 22-8 44-22M92 8h14v14'/>",
    "fundos": "<path d='M4 70h112'/><rect x='14' y='38' width='24' height='32'/><rect x='46' y='14' width='30' height='56'/><rect x='84' y='30' width='24' height='40'/>"
              "<path d='M54 24h4M64 24h4M54 36h4M64 36h4M54 48h4M64 48h4M22 48h4M22 58h4M92 40h4M92 50h4'/>",
    "rf": "<rect x='30' y='6' width='56' height='66' rx='5'/><path d='M40 22h36M40 34h36M40 46h22'/><circle cx='80' cy='58' r='10'/><path d='M76 58l3 3 6-7'/>",
    "cripto": "<circle cx='60' cy='40' r='30'/><circle cx='60' cy='40' r='22'/><path d='M52 28h14a7 7 0 0 1 0 14H52zm0 14h16a7 7 0 0 1 0 14H52zM52 24v36M60 22v4M60 58v4'/>",
    "cart": "<rect x='22' y='22' width='66' height='46' rx='8'/><path d='M22 36h66'/><circle cx='76' cy='52' r='4'/><path d='M30 22l40-12 6 12'/>",
    "ferr": "<path d='M84 8a20 20 0 0 0-22 26L14 66l10 8 48-32a20 20 0 0 0 26-22l-12 8-10-4-4-10z'/>",
}
# arte 3D de cada cartão (assets da cartela; se faltar, volta ao ícone de linha)
_ARTE3D = {"acoes": "cl_acoes", "fundos": "cl_fiis", "rf": "cl_renda_fixa", "cripto": "cl_cripto", "cart": "c_escudo_coroa", "ferr": "i_alvo"}
_ICONE_SEC = ("<svg width='34' height='34' viewBox='0 0 24 24' fill='none' stroke-linecap='round' aria-hidden='true'><rect x='3' y='13' width='4' height='8' rx='1' fill='#F2B84B'/>"
              "<rect x='10' y='8' width='4' height='13' rx='1' fill='#F2B84B'/><rect x='17' y='3' width='4' height='18' rx='1' fill='#F2B84B'/></svg>")
_FUNDO_HERO = ("<svg class='ah-bg' viewBox='0 0 200 90' preserveAspectRatio='xMaxYMax meet' aria-hidden='true'><g fill='#3D7BFF' opacity='.28'>"
               "<rect x='120' y='52' width='10' height='38'/><rect x='136' y='40' width='10' height='50'/><rect x='152' y='46' width='10' height='44'/>"
               "<rect x='168' y='24' width='10' height='66'/><rect x='184' y='8' width='10' height='82'/></g>"
               "<path d='M118 60l24-10 20 6 34-34' fill='none' stroke='#F2B84B' stroke-width='1.6' opacity='.8'/></svg>")


def arte(cid: str) -> str:
    corpo = _ARTE.get(cid, "")
    return (f"<svg class='an-art' viewBox='0 0 120 80' fill='none' stroke='currentColor' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{corpo}</svg>"
            if corpo else "")


def html_hero(titulo: str, subtitulo: str) -> str:
    return (f"<div class='ah'>{_FUNDO_HERO}<div class='ah-m'>{ART.mascote(humor='analise', tamanho=190)}</div>"
            f"<div class='ah-t'><div class='ah-h'>{html.escape(titulo)}</div><div class='ah-s'>{html.escape(subtitulo)}</div></div>"
            "<details class='ah-i'><summary aria-label='Sobre esta página'>i</summary><div>Escolha um tipo de ativo e abra as análises dele: "
            "preço justo, dividendos, risco e mais. Tudo é educativo, não é recomendação de compra ou venda.</div></details></div>")


def html_secao(texto: str) -> str:
    return f"<div class='an-sec2'>{_ICONE_SEC}<b>{html.escape(texto)}</b><i></i></div>"


def html_cartao(cid: str, titulo: str, descricao: str, n: int, icone: str) -> str:
    a3 = _ARTE3D.get(cid, "")
    ico = (f"<span class='an-ci an-3d'>{AA.img(a3, '', '')}</span>" if AA.existe(a3) else f"<span class='an-ci'>{tema.icone(icone, 26)}</span>")
    return (f"{arte(cid)}<div class='an-ch'>{ico}"
            f"<div class='an-ct'><b>{html.escape(titulo)}</b><span>{html.escape(descricao)}</span></div>"
            f"<span class='an-n'>{n}</span><span class='an-chev'>›</span></div>")


CSS = f"""
{Q} .st-key-an_busca{{margin:4px 0 0 !important}}
.ah{{position:relative;display:flex;align-items:center;gap:6px;padding:10px 14px 10px 6px;margin:4px 0 14px;border-radius:26px;overflow:hidden;
  background:radial-gradient(circle at 15% 35%,rgba(60,110,255,.40),transparent 55%),linear-gradient(160deg,#122259,#0F1740 80%);border:1.5px solid rgba(110,140,255,.5);box-shadow:0 0 26px -10px rgba(80,120,255,.6)}}
.ah-bg{{position:absolute;right:0;bottom:0;width:70%;height:100%;pointer-events:none;opacity:.55}}
.ah-m{{position:relative;flex:0 0 auto;margin:-10px 0 -12px -6px}}
.ah-m img,.ah-m svg{{width:clamp(110px,34vw,190px) !important;height:auto !important;filter:drop-shadow(0 8px 12px rgba(0,0,0,.45))}}
.ah-t{{position:relative;min-width:0;padding-right:30px}}
.ah-h{{font-size:clamp(1.7rem,7.5vw,2.5rem);font-weight:900;color:#fff !important;line-height:1.1}}
.ah-h:after{{content:"";display:block;height:4px;width:70%;margin-top:4px;border-radius:4px;background:linear-gradient(90deg,#F2B84B,transparent)}}
.ah-s{{margin-top:10px;font-size:clamp(.84rem,3.3vw,1.1rem);line-height:1.3;color:#CFCBFF !important}}
.ah-i{{position:absolute;top:10px;right:10px;z-index:2}}
.ah-i summary{{list-style:none;cursor:pointer;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-style:italic;font-weight:800;color:#fff;background:rgba(10,8,40,.6);border:1.5px solid rgba(140,160,255,.6)}}
.ah-i summary::-webkit-details-marker{{display:none}}
.ah-i[open] div{{position:absolute;right:0;top:40px;width:min(78vw,300px);padding:10px 12px;border-radius:12px;background:#1B1442;border:1px solid #3D3182;color:#EDE9FF !important;font-size:.86rem;line-height:1.35}}
.an-sec2{{display:flex;align-items:center;gap:10px;margin:14px 2px 16px}}
.an-sec2 b{{color:#fff !important;font-size:clamp(1.05rem,4.4vw,1.4rem);font-weight:800;white-space:nowrap}}
.an-sec2 i{{flex:1;height:2px;border-radius:2px;background:linear-gradient(90deg,rgba(120,150,255,.8),transparent)}}
{Q} [class*="st-key-an_card_"]{{position:relative;overflow:hidden;padding:12px 14px 14px !important;border-radius:26px !important;gap:.55rem !important;
  background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 40%,#120D36),color-mix(in srgb,var(--ac) 10%,#0E0A2B) 85%) !important;
  border:1.5px solid color-mix(in srgb,var(--ac) 85%,transparent) !important;box-shadow:0 0 22px -8px var(--ac),0 4px 0 rgba(0,0,0,.3) !important}}
{Q} [class*="st-key-an_card_"]::before{{display:none !important}}
{Q} [class*="st-key-an_card_"] .an-art{{position:absolute;right:64px;top:10px;width:auto;height:64px;max-width:40%;color:var(--ac);opacity:.3;pointer-events:none;filter:brightness(1.6);z-index:0}}
{Q} [class*="st-key-an_card_"] .an-ch{{position:relative;z-index:1;padding:0 0 12px !important;gap:12px}}
{Q} [class*="st-key-an_card_"] .an-ci{{width:56px !important;height:56px !important;border-radius:16px !important;color:#fff !important;
  background:linear-gradient(160deg,color-mix(in srgb,var(--ac) 80%,#fff 0%),color-mix(in srgb,var(--ac) 45%,#120D36)) !important;border:1px solid color-mix(in srgb,var(--ac) 70%,#fff) !important;
  box-shadow:0 4px 12px -4px var(--ac)}}
{Q} [class*="st-key-an_card_"] .an-ci svg{{width:30px !important;height:30px !important}}
{Q} [class*="st-key-an_card_"] .an-ct b{{font-size:clamp(1.1rem,4.4vw,1.4rem) !important}}
{Q} [class*="st-key-an_card_"] .an-ct span{{color:#E2DDFF !important}}
{Q} [class*="st-key-an_card_"] .an-n{{background:rgba(10,8,40,.55) !important;border:1.5px solid color-mix(in srgb,var(--ac) 80%,transparent) !important;color:#fff !important;min-width:32px !important;height:32px !important}}
.an-chev{{flex:none;color:#fff;font-size:2rem;line-height:1;margin-left:2px}}
{Q} [class*="st-key-an_card_"] button{{position:relative;z-index:1;width:100% !important;min-height:42px !important;border-radius:14px !important;
  background:linear-gradient(180deg,color-mix(in srgb,var(--ac) 30%,#0F0B2B),color-mix(in srgb,var(--ac) 16%,#0F0B2B)) !important;
  border:1px solid color-mix(in srgb,var(--ac) 55%,transparent) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important}}
{Q} [class*="st-key-an_card_"] button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important}}
{Q} [class*="st-key-an_card_"] button [data-testid="stIconMaterial"]{{color:var(--ac) !important;-webkit-text-fill-color:var(--ac) !important}}

/* arte 3D: sem caixa, com halo e flutuação suave */
@keyframes ahBoia{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
@keyframes ahEntra{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
@keyframes ahBrilho{{0%{{transform:translateX(-130%)}}60%,100%{{transform:translateX(230%)}}}}
{Q} [class*="st-key-an_card_"] .an-ci.an-3d{{position:relative;width:64px !important;height:64px !important;border:0 !important;box-shadow:none !important;background:none !important;
  display:grid;place-items:center;overflow:visible}}
{Q} [class*="st-key-an_card_"] .an-ci.an-3d::before{{content:"";position:absolute;inset:-6px;border-radius:50%;background:radial-gradient(circle,color-mix(in srgb,var(--ac) 55%,transparent),transparent 68%);opacity:.85}}
{Q} [class*="st-key-an_card_"] .an-ci.an-3d img{{position:relative;width:60px;height:auto;max-height:60px;object-fit:contain;animation:ahBoia 3.4s ease-in-out infinite;
  filter:drop-shadow(0 6px 8px rgba(0,0,0,.5))}}
{Q} [class*="st-key-an_card_"]{{animation:ahEntra .45s ease both;transition:transform .18s ease,box-shadow .2s ease,border-color .2s ease}}
{Q} .st-key-an_card_acoes{{animation-delay:0s}}{Q} .st-key-an_card_fundos{{animation-delay:.06s}}{Q} .st-key-an_card_rf{{animation-delay:.12s}}
{Q} .st-key-an_card_cripto{{animation-delay:.18s}}{Q} .st-key-an_card_cart{{animation-delay:.24s}}{Q} .st-key-an_card_ferr{{animation-delay:.3s}}
{Q} [class*="st-key-an_card_"]:hover{{transform:translateY(-3px);box-shadow:0 0 30px -6px var(--ac),0 6px 0 rgba(0,0,0,.3) !important}}
{Q} [class*="st-key-an_card_"]:active{{transform:scale(.98)}}
{Q} [class*="st-key-an_card_"]::after{{content:"";position:absolute;top:0;bottom:0;left:0;width:38%;pointer-events:none;
  background:linear-gradient(100deg,transparent,rgba(255,255,255,.10),transparent);animation:ahBrilho 6s ease-in-out infinite}}
{Q} [class*="st-key-an_card_"] button:active{{transform:scale(.97)}}
.ah-m{{animation:ahBoia 3.8s ease-in-out infinite}}
@media (prefers-reduced-motion:reduce){{{Q} [class*="st-key-an_card_"],{Q} [class*="st-key-an_card_"]::after,.ah-m,{Q} [class*="st-key-an_card_"] .an-ci.an-3d img{{animation:none !important}}}}
/* cabeçalho em grade: arte e contagem em cima, título e descrição ocupando a largura toda (cabe nas duas colunas do celular) */
{Q} [class*="st-key-an_card_"] .an-ch{{display:grid !important;grid-template-columns:auto 1fr auto;align-items:center;column-gap:8px;row-gap:6px}}
{Q} [class*="st-key-an_card_"] .an-ct{{display:contents !important}}
{Q} [class*="st-key-an_card_"] .an-ci{{grid-column:1;grid-row:1}}
{Q} [class*="st-key-an_card_"] .an-n{{grid-column:3;grid-row:1;justify-self:end;align-self:start}}
{Q} [class*="st-key-an_card_"] .an-chev{{display:none !important}}
{Q} [class*="st-key-an_card_"] .an-ct b{{grid-column:1/-1;grid-row:2;line-height:1.15}}
{Q} [class*="st-key-an_card_"] .an-ct span{{grid-column:1/-1;grid-row:3;font-size:clamp(.74rem,3vw,.9rem) !important;line-height:1.3}}
"""
