"""Tela inicial em formato de aplicativo (banner de boas-vindas + 6 atalhos). Só visual: os atalhos usam as páginas que já existem."""
from __future__ import annotations

import html

import jornada_arte as ART
import jornada_icones as IC
import tema

# (id, título, subtítulo, ícone, cor, página de destino, estado a gravar antes de abrir)
CARTOES = [
    ("analise", "Analisar", "Explore o mercado", "grafico", "#3DDC97", "analisar", {}),
    ("wallet", "Wallet Game", "Jogue e ganhe recompensas", "moeda", "#F2B84B", "competicao", {}),
    ("carteira", "Carteira", "Gerencie seus ativos", "cofre", "#7A8CFF", "carteira", {}),
    ("conquistas", "Conquistas", "Veja seus troféus", "estrela", "#FF8A3D", "conta", {"conta_secao": "Perfil"}),
    ("aprender", "Aprender", "Estude e evolua", "livro", "#8B6CFF", "jornada", {}),
    ("loja", "Loja Ticker", "Troque suas moedas", "carrinho", "#D23FC8", "economia", {"eco_sec": "Loja"}),
]


def html_mascote() -> str:
    return "<div class='hh-mas'>" + ART.mascote(humor="inicio", tamanho=190) + "</div>"


def html_texto() -> str:
    return ("<div class='hh-txt'><div class='hh-b'>Bem-vindo ao</div>"
            "<div class='hh-t'>Ticker<span>Hunters!</span></div>"
            "<div class='hh-l'>Aprenda. Analise. Conquiste.</div></div>")


def html_desafio() -> str:
    return (f"<div class='hh-des'><span class='hh-tr'>{tema.icone('trofeu', 38)}</span>"
            "<span>Você está pronto<br>para mais desafios?</span></div>")


def css() -> str:
    ic = "".join(f'.st-key-in_c_{i}{{--ac:{cor};--ic:url("{IC.uri(n, cor)}");--sub:"{sub}"}}' for i, _t, sub, n, cor, _d, _e in CARTOES)
    return "<style>" + ic + _CSS + "</style>"


_Q = "html body .stApp.stApp.stApp"
_CSS = f"""
{_Q} .st-key-in_hero{{display:grid !important;grid-template-columns:minmax(0,42%) minmax(0,1fr);grid-template-rows:auto auto;column-gap:6px !important;row-gap:8px !important;
  padding:12px 12px 12px 6px !important;border-radius:26px;align-items:center;overflow:visible;
  background:radial-gradient(circle at 12% 40%,rgba(60,110,255,.45),transparent 55%),linear-gradient(135deg,#142468,#1B1442 70%);
  border:1px solid rgba(120,150,255,.55);box-shadow:0 0 28px -8px rgba(80,120,255,.6);margin:6px 0 14px}}
{_Q} .st-key-in_hero>[data-testid="stElementContainer"],{_Q} .st-key-in_hero>.st-key-in_hero_m{{min-width:0;width:100% !important}}
{_Q} .st-key-in_hero>[data-testid="stElementContainer"]:nth-child(1){{grid-column:1;grid-row:1 / span 2}}
{_Q} .st-key-in_hero>[data-testid="stElementContainer"]:nth-child(2){{grid-column:2;grid-row:1;align-self:end}}
{_Q} .st-key-in_hero>.st-key-in_hero_m{{grid-column:2;grid-row:2;align-self:start}}
@media (min-width:760px){{{_Q} .st-key-in_hero{{grid-template-columns:auto minmax(0,1.5fr) minmax(0,1fr);grid-template-rows:auto;column-gap:18px !important}}
  {_Q} .st-key-in_hero>[data-testid="stElementContainer"]:nth-child(1){{grid-row:1}}
  {_Q} .st-key-in_hero>[data-testid="stElementContainer"]:nth-child(2){{grid-column:2;grid-row:1;align-self:center}}
  {_Q} .st-key-in_hero>.st-key-in_hero_m{{grid-column:3;grid-row:1;align-self:center}}}}
.hh-mas{{margin:-26px 0 -14px -6px}}
.hh-mas img,.hh-mas svg{{width:clamp(130px,40vw,230px) !important;height:auto !important;filter:drop-shadow(0 8px 14px rgba(0,0,0,.45))}}
.hh-txt{{min-width:0;text-align:center}}
.hh-b{{font-size:clamp(1rem,4.2vw,1.7rem);font-weight:800;font-style:italic;color:#fff !important;line-height:1.1}}
.hh-t{{font-size:clamp(1.45rem,6.6vw,2.7rem);font-weight:900;font-style:italic;color:#fff !important;line-height:1.05;letter-spacing:-.03em}}
.hh-t span{{color:#A8E10C !important}}
.hh-l{{margin-top:4px;font-size:clamp(.78rem,3.1vw,1.25rem);font-style:italic;color:#CFCBFF !important;display:block}}
.hh-l:after{{content:"";display:block;height:3px;width:70%;margin:6px auto 0;border-radius:3px;background:linear-gradient(90deg,transparent,#F2B84B,transparent)}}
{_Q} .st-key-in_hero_m{{padding:10px !important;border-radius:18px;border:1.5px solid rgba(242,184,75,.7);background:rgba(10,8,40,.5);gap:.5rem !important}}
.hh-des,.hh-des span{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
.hh-des{{display:flex;align-items:center;gap:8px;color:#fff !important;font-weight:600;font-size:clamp(.78rem,2.9vw,1.05rem);line-height:1.2}}
.hh-tr,.hh-tr svg{{color:#F2B84B !important;-webkit-text-fill-color:#F2B84B !important;flex:none;display:grid}}
{_Q} .st-key-in_hero_m{{display:flex !important;flex-direction:column !important;gap:.6rem !important;height:auto !important;min-height:0 !important;overflow:visible !important}}
{_Q} .st-key-in_hero_m>[data-testid="stElementContainer"]{{height:auto !important;min-height:0 !important;overflow:visible !important;margin:0 !important;position:static !important;flex:0 0 auto !important}}
{_Q} .st-key-in_hero_m .hh-des{{padding:2px 2px 14px}}
.hh-txt{{padding-bottom:12px}}
{_Q} .st-key-in_hero{{row-gap:16px !important}}
{_Q} .st-key-in_hero_m button{{width:100% !important;min-height:44px !important;border-radius:16px !important;border:0 !important;
  background:linear-gradient(180deg,#FFC23D,#F29A1F) !important;box-shadow:0 4px 0 #B96F00 !important}}
{_Q} .st-key-in_hero_m button :is(p,span){{color:#1B1442 !important;-webkit-text-fill-color:#1B1442 !important;font-weight:900 !important}}
{_Q} [class*="st-key-in_cards"]{{display:grid !important;grid-template-columns:minmax(0,1fr) !important;gap:12px !important}}
@media (min-width:640px){{{_Q} [class*="st-key-in_cards"]{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}}}
@media (min-width:1200px){{{_Q} [class*="st-key-in_cards"]{{grid-template-columns:repeat(3,minmax(0,1fr)) !important}}}}
{_Q} [class*="st-key-in_cards"]>[data-testid="stElementContainer"]{{width:100% !important;min-width:0}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button{{width:100% !important;min-height:78px !important;height:auto !important;padding:8px 16px 8px 10px !important;border-radius:24px !important;
  display:flex !important;align-items:center !important;justify-content:flex-start !important;gap:14px !important;text-align:left !important;
  background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 18%,#1B1B5E),#17154F 75%) !important;
  border:1.5px solid color-mix(in srgb,var(--ac) 65%,transparent) !important;box-shadow:0 4px 0 color-mix(in srgb,var(--ac) 25%,#0B0821),0 0 18px -8px var(--ac) !important}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button:before{{content:"";flex:0 0 66px;height:56px;background:var(--ic) center/contain no-repeat;filter:drop-shadow(0 4px 6px rgba(0,0,0,.5)) drop-shadow(0 0 8px var(--ac))}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button:after{{content:"\\203A";margin-left:auto;font-size:2.2rem;line-height:1;color:#fff;opacity:.95}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button>div{{flex:1 1 auto;min-width:0;width:auto !important;margin:0 !important;justify-content:flex-start !important;text-align:left !important}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button [data-testid="stMarkdownContainer"]{{width:100% !important;text-align:left !important;justify-content:flex-start !important}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button p{{margin:0 !important;text-align:left !important;font-size:clamp(1.15rem,4.6vw,1.45rem) !important;font-weight:800 !important;line-height:1.15 !important;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button p:after{{content:var(--sub);display:block;font-size:.85rem;font-weight:500;color:#C5B3FF;-webkit-text-fill-color:#C5B3FF;margin-top:2px}}
{_Q} [class*="st-key-in_cards"] [class*="st-key-in_c_"] button:active{{transform:translateY(3px);box-shadow:0 1px 0 color-mix(in srgb,var(--ac) 25%,#0B0821) !important}}
"""
