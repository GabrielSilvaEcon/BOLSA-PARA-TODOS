"""Ticker Battle · telas (Streamlit). As regras do duelo estão em battle.py, os dados das cartas e o histórico em battle_dados.py.

Cinco telas ligadas por `bt_tela`: central → baralho → preparar → arena → resultado. O duelo vive no servidor (st.session_state) e cada
jogada é validada por battle.jogar_rodada com as cartas CONGELADAS no início do duelo: o navegador só envia "qual carta" e "qual atributo".
Sem XP, TickerCoins, conquistas, ranking, loja ou recompensas (fase 2). Animações só em CSS, com opção de reduzir/pular.
"""
from __future__ import annotations

import html
import time
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st

import arte_battle as ART
import arte_cartas as ACAR
import banco
import battle as B
import battle_dados as BD
import usuarios

_e = lambda x: html.escape(str(x), quote=True)
BRT = timezone(timedelta(hours=-3))
_P = "html body .stApp.stApp.stApp"
TELAS = ("central", "baralho", "preparar", "arena", "resultado")
TELAS_ONLINE = ("busca", "sala", "espera", "oarena", "oresultado")

_CSS = f"""
{_P} [data-testid="stMainBlockContainer"],{_P} .block-container{{max-width:560px !important}}
{_P} .bt-hero{{position:relative;text-align:center;margin:0 -4px 4px}}
{_P} .bt-hero img{{display:block;width:100%;max-width:420px;margin:0 auto}}
{_P} .bt-tag{{margin:2px 0 2px;text-align:center;font-weight:900;font-size:1.05rem;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .bt-sub{{margin:0 12px 10px;text-align:center;font-size:.88rem;line-height:1.35;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .bt-box{{position:relative;overflow:hidden;border-radius:18px;padding:12px;margin:10px 0;background:radial-gradient(circle at 100% 0,rgba(139,108,255,.25),transparent 55%),linear-gradient(160deg,#1A1250,#0E0A2C 88%);border:1px solid rgba(124,92,255,.45);box-shadow:0 3px 0 rgba(0,0,0,.3)}}
{_P} .bt-box .t{{display:flex;align-items:center;gap:8px;font-weight:900;font-size:1rem;color:#fff !important;-webkit-text-fill-color:#fff !important;margin-bottom:6px}}
{_P} .bt-box .t span.m{{font-size:1.15rem}}
{_P} .bt-box p,{_P} .bt-box li{{margin:3px 0;font-size:.84rem;line-height:1.35;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .bt-box ul{{margin:4px 0 0;padding-left:18px}}
{_P} .bt-vazio{{font-size:.84rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important;text-align:center;padding:8px 4px}}
{_P} .bt-passos{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:6px}}
{_P} .bt-passos div{{border-radius:12px;padding:8px 6px;text-align:center;font-size:.72rem;font-weight:700;line-height:1.25;background:rgba(255,255,255,.06);border:1px solid rgba(197,179,255,.25);color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .bt-passos b{{display:block;font-size:1.2rem}}
{_P} .bt-lin{{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid rgba(255,255,255,.1)}}
{_P} .bt-lin:first-of-type{{border-top:0}}
{_P} .bt-lin .r{{flex:0 0 64px;text-align:center;border-radius:10px;padding:5px 0;font-size:.72rem;font-weight:900}}
{_P} .bt-lin .r.vitoria{{background:rgba(61,220,151,.18);color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important;border:1px solid #3DDC97}}
{_P} .bt-lin .r.derrota{{background:rgba(255,107,138,.16);color:#FF6B8A !important;-webkit-text-fill-color:#FF6B8A !important;border:1px solid #FF6B8A}}
{_P} .bt-lin .r.empate{{background:rgba(242,184,75,.16);color:#F2B84B !important;-webkit-text-fill-color:#F2B84B !important;border:1px solid #F2B84B}}
{_P} .bt-lin .x{{min-width:0;font-size:.8rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .bt-lin .x small{{display:block;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important;font-size:.7rem}}
/* cartas */
{_P} .bt-c{{position:relative;overflow:hidden;box-sizing:border-box;border-radius:16px;padding:8px 8px 7px;min-height:136px;background:radial-gradient(circle at 80% 0,color-mix(in srgb,var(--c) 38%,transparent),transparent 62%),linear-gradient(165deg,#1B1450,#0B0825 92%);border:2px solid var(--c);box-shadow:0 0 12px color-mix(in srgb,var(--c) 45%,transparent)}}
{_P} .bt-c .ilu{{position:absolute;right:-4px;bottom:-8px;font-size:3.6rem;opacity:.13;line-height:1;pointer-events:none}}
{_P} .bt-c .tk{{font-weight:900;font-size:.95rem;color:#fff !important;-webkit-text-fill-color:#fff !important;letter-spacing:.02em;overflow-wrap:anywhere}}
{_P} .bt-c .nm{{font-size:.68rem;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important;line-height:1.2;margin-bottom:5px}}
{_P} .bt-c .ct{{display:inline-block;padding:1px 7px;border-radius:999px;font-size:.62rem;font-weight:800;background:color-mix(in srgb,var(--c) 28%,transparent);border:1px solid var(--c);color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} :is(.bt-c,.bt-ci) .ix{{display:flex;justify-content:space-between;gap:6px;font-size:.7rem;margin-top:3px;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} :is(.bt-c,.bt-ci) .ix b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} :is(.bt-c,.bt-ci) .dt{{margin-top:5px;font-size:.6rem;color:#9D96CF !important;-webkit-text-fill-color:#9D96CF !important}}
{_P} .bt-c .ok{{display:none;position:absolute;top:-1px;right:-1px;width:24px;height:24px;border-radius:0 12px 0 12px;background:#22d3ee;color:#06131f;font-size:.85rem;font-weight:900;line-height:24px;text-align:center}}
{_P} .bt-c.sel{{border-color:#22d3ee;box-shadow:0 0 16px rgba(34,211,238,.7)}}
{_P} .bt-c.sel .ok{{display:block}}
{_P} .bt-c.trv{{filter:grayscale(.85);opacity:.6}}
{_P} :is(.bt-c,.bt-ci) .mot{{margin-top:4px;font-size:.62rem;color:#FFB4A8 !important;-webkit-text-fill-color:#FFB4A8 !important}}
{_P} [class*="st-key-bt_grade_"][data-testid="stVerticalBlock"],{_P} [class*="st-key-bt_grade_"]>[data-testid="stVerticalBlock"],{_P} .st-key-bt_mao[data-testid="stVerticalBlock"],{_P} .st-key-bt_mao>[data-testid="stVerticalBlock"]{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:10px !important}}
{_P} [class*="st-key-btc_"]{{position:relative;gap:0 !important;height:100%}}
{_P} [class*="st-key-btc_"] [data-testid="stMarkdownContainer"],{_P} [class*="st-key-btc_"] [data-testid="stElementContainer"]:has(.bt-c){{margin:0 !important;height:100%}}
{_P} [class*="st-key-btc_"] [data-testid="stElementContainer"]:has(button){{position:absolute !important;inset:0;z-index:3;width:100% !important;height:100% !important}}
{_P} [class*="st-key-btc_"] button{{width:100% !important;height:100% !important;min-height:100% !important;opacity:0;cursor:pointer;padding:0 !important}}
@media (min-width:700px){{{_P} [class*="st-key-bt_grade_"][data-testid="stVerticalBlock"],{_P} [class*="st-key-bt_grade_"]>[data-testid="stVerticalBlock"]{{grid-template-columns:repeat(3,minmax(0,1fr)) !important}}}}
{_P} .bt-ci{{position:relative;overflow:hidden;box-sizing:border-box;border-radius:14px;background:#0B0825;box-shadow:0 0 10px rgba(139,108,255,.4);transition:transform .12s,box-shadow .12s}}
{_P} .bt-ci img.art{{display:block;width:100%;height:auto}}
{_P} .bt-ci .st{{padding:6px 8px 7px;background:linear-gradient(180deg,#140E3F,#0B0825)}}
{_P} .bt-ci .ok{{display:none;position:absolute;top:6px;right:6px;width:24px;height:24px;border-radius:50%;background:#22d3ee;color:#06131f;font-size:.85rem;font-weight:900;line-height:24px;text-align:center;box-shadow:0 0 10px #22d3ee}}
{_P} .bt-ci.sel{{box-shadow:0 0 0 2px #22d3ee,0 0 16px rgba(34,211,238,.75);transform:translateY(-1px)}}
{_P} .bt-ci.sel .ok{{display:block}}
{_P} .bt-ci.trv{{filter:grayscale(.85);opacity:.6}}
{_P} .bt-ci.venceu{{box-shadow:0 0 0 2px #3DDC97,0 0 22px rgba(61,220,151,.85)}}
{_P} .bt-ci.venceu .big{{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}}
{_P} .bt-ci.perdeu{{filter:saturate(.6) brightness(.85)}}
{_P} .bt-ci .big{{margin-top:0}}
/* baralho */
{_P} .bt-conta{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:6px 0}}
{_P} .bt-conta b{{font-size:1.05rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-msg{{margin:6px 0;padding:7px 10px;border-radius:12px;font-size:.8rem;font-weight:700}}
{_P} .bt-msg.ok{{background:rgba(61,220,151,.14);border:1px solid #3DDC97;color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}}
{_P} .bt-msg.er{{background:rgba(255,107,138,.14);border:1px solid #FF6B8A;color:#FFB4C2 !important;-webkit-text-fill-color:#FFB4C2 !important}}
{_P} .bt-det .b{{margin-top:8px}}
{_P} .bt-det .b div{{display:flex;justify-content:space-between;font-size:.8rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .bt-det .b i{{display:block;height:6px;border-radius:999px;margin:2px 0 6px;background:linear-gradient(90deg,var(--c),#22d3ee);width:var(--w)}}
{_P} .bt-det .reg{{margin-top:2px;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
/* preparar */
{_P} .bt-opc{{display:flex;gap:10px;align-items:center;padding:10px;border-radius:14px;background:linear-gradient(160deg,#17114A,#0E0A2C 85%);border:2px solid #8B6CFF;box-shadow:0 0 14px rgba(139,108,255,.5)}}
{_P} .bt-opc .ic{{font-size:1.8rem}}
{_P} .bt-opc b{{display:block;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-opc span{{font-size:.78rem;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}}
{_P} .bt-chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
{_P} .bt-chips span{{padding:3px 9px;border-radius:999px;font-size:.74rem;font-weight:800;background:rgba(139,108,255,.2);border:1px solid rgba(197,179,255,.4);color:#fff !important;-webkit-text-fill-color:#fff !important}}
/* arena */
{_P} .bt-top{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:2px 0 6px}}
{_P} .bt-rod{{padding:4px 14px;border-radius:999px;font-weight:900;font-size:.82rem;background:rgba(242,184,75,.2);border:1px solid #F2B84B;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .bt-pl{{display:flex;gap:6px;align-items:center;font-weight:900;font-size:.82rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-pl b{{padding:2px 9px;border-radius:8px;background:#1B1442;border:1px solid rgba(197,179,255,.35)}}
{_P} .bt-arena{{position:relative;overflow:hidden;border-radius:20px;padding:12px 8px;margin:6px 0;background:radial-gradient(circle at 50% 50%,rgba(124,92,255,.35),transparent 60%),linear-gradient(180deg,#120C3A,#08061D);border:1px solid rgba(124,92,255,.5)}}
{_P} .bt-duelo{{position:relative;display:grid;grid-template-columns:1fr 54px 1fr;align-items:center;gap:2px}}
{_P} .bt-duelo .vs{{width:54px;height:54px;object-fit:contain;justify-self:center}}
{_P} .bt-duelo .bt-c{{min-height:150px}}
{_P} :is(.bt-c,.bt-ci) .big{{margin-top:6px;text-align:center;font-weight:900;font-size:1.7rem;line-height:1.1;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} :is(.bt-c,.bt-ci) .big small{{display:block;font-size:.66rem;font-weight:800;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}}
{_P} .bt-c.venceu{{border-color:#3DDC97;box-shadow:0 0 22px rgba(61,220,151,.85)}}
{_P} .bt-c.venceu .big{{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}}
{_P} .bt-c.perdeu{{filter:saturate(.6) brightness(.85)}}
{_P} .bt-oculto{{margin-top:8px;text-align:center;font-weight:900;font-size:1.5rem;color:#8B6CFF !important;-webkit-text-fill-color:#8B6CFF !important}}
{_P} .bt-barra{{margin:10px 6px 2px}}
{_P} .bt-barra .rt{{text-align:center;font-weight:900;font-size:.8rem;margin-bottom:4px;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .bt-barra .tr{{display:flex;height:12px;border-radius:999px;overflow:hidden;background:rgba(255,255,255,.1)}}
{_P} .bt-barra .tr i{{display:block;height:100%;width:var(--w)}}
{_P} .bt-barra .tr i.a{{background:linear-gradient(90deg,#3DDC97,#22d3ee)}}
{_P} .bt-barra .tr i.b{{background:linear-gradient(90deg,#8B6CFF,#D23FC8)}}
{_P} .bt-res{{margin:10px 0 4px;padding:10px;border-radius:16px;text-align:center;font-weight:900;font-size:1.15rem}}
{_P} .bt-res.vitoria{{background:linear-gradient(135deg,rgba(61,220,151,.28),rgba(34,211,238,.12));border:1px solid #3DDC97;color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}}
{_P} .bt-res.derrota{{background:linear-gradient(135deg,rgba(255,107,138,.28),rgba(139,108,255,.12));border:1px solid #FF6B8A;color:#FF8FA8 !important;-webkit-text-fill-color:#FF8FA8 !important}}
{_P} .bt-res.empate{{background:linear-gradient(135deg,rgba(242,184,75,.26),rgba(139,108,255,.12));border:1px solid #F2B84B;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .bt-res small{{display:block;font-weight:600;font-size:.78rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .bt-atr{{margin:8px 0 2px;text-align:center;font-weight:800;font-size:.85rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .bt-atr b{{color:#22d3ee !important;-webkit-text-fill-color:#22d3ee !important}}
{_P} .bt-bloq{{font-size:.72rem;line-height:1.35;color:#FFB4A8 !important;-webkit-text-fill-color:#FFB4A8 !important;margin:2px 0}}
{_P} .bt-edu{{margin:8px 0;padding:10px 12px;border-radius:14px;font-size:.82rem;line-height:1.4;background:rgba(255,255,255,.06);border:1px solid rgba(197,179,255,.3);color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .bt-edu b{{color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} details.bt-rx{{margin:8px 0 0;border-radius:12px;background:rgba(255,255,255,.05);border:1px solid rgba(197,179,255,.3);padding:6px 10px}}
{_P} details.bt-rx summary{{cursor:pointer;font-weight:800;font-size:.82rem;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} details.bt-rx p{{margin:6px 0 0;font-size:.78rem;line-height:1.4;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} details.bt-rx p b{{color:#22d3ee !important;-webkit-text-fill-color:#22d3ee !important}}
{_P} .bt-final{{text-align:center;margin:4px 0 6px}}
{_P} .bt-final .tt{{font-size:2.1rem;font-weight:900;font-style:italic;line-height:1.1}}
{_P} .bt-final.vitoria .tt{{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important;text-shadow:0 0 22px rgba(61,220,151,.7)}}
{_P} .bt-final.derrota .tt{{color:#FF6B8A !important;-webkit-text-fill-color:#FF6B8A !important;text-shadow:0 0 22px rgba(255,107,138,.6)}}
{_P} .bt-final.empate .tt{{color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .bt-final .pl{{margin-top:4px;font-weight:900;font-size:1.3rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-final .rs{{font-size:.82rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
/* central (layout da referência) */
{_P} .bt-hero2{{margin:-6px -6px 0;text-align:center}}
{_P} .bt-hero2 img{{display:block;width:100%;max-width:560px;margin:0 auto}}
{_P} .st-key-on_jogar{{position:relative;margin:2px -4px 4px !important}}
{_P} .on-jg img{{display:block;width:100%;height:auto;filter:drop-shadow(0 0 12px rgba(242,184,75,.45))}}
{_P} :is(.st-key-on_card_sis,.st-key-on_card_on,.st-key-on_jogar) .stButton{{position:absolute;inset:0;margin:0;z-index:3}}
{_P} :is(.st-key-on_card_sis,.st-key-on_card_on,.st-key-on_jogar) .stButton>button{{width:100%;height:100%;min-height:0;opacity:0;border-radius:22px}}
{_P} .st-key-on_jogar:has(button:disabled) .on-jg img{{filter:grayscale(.85) brightness(.6)}}
{_P} .bt-alerta{{display:flex;align-items:center;gap:10px;margin:8px 0;padding:10px 12px;border-radius:16px;border:1.5px solid #FF4D6D;
  background:linear-gradient(160deg,rgba(255,77,109,.2),rgba(60,10,40,.55));box-shadow:0 0 12px rgba(255,77,109,.35)}}
{_P} .bt-alerta .ic{{font-size:1.5rem}}
{_P} .bt-alerta .tx{{flex:1;font-weight:800;font-size:.86rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-alerta details{{flex:0 0 auto;max-width:48%}}
{_P} .bt-alerta summary{{list-style:none;cursor:pointer;padding:5px 11px;border-radius:999px;font-size:.74rem;font-weight:800;border:1px solid rgba(255,255,255,.55);color:#fff !important;-webkit-text-fill-color:#fff !important;text-align:center;white-space:nowrap}}
{_P} .bt-alerta summary::-webkit-details-marker{{display:none}}
{_P} .bt-alerta details p{{margin:6px 0 0;font-size:.72rem;line-height:1.3;color:#FFD6DD !important;-webkit-text-fill-color:#FFD6DD !important}}
{_P} .bt-baralho{{display:grid;grid-template-columns:92px minmax(0,1fr);gap:8px;align-items:center;padding:10px;border-radius:20px;border:2px solid #4B8BFF;
  background:radial-gradient(circle at 12% 60%,rgba(139,108,255,.4),transparent 55%),linear-gradient(160deg,#150F45,#0A0720 92%);box-shadow:0 0 16px rgba(75,139,255,.5)}}
{_P} .bt-baralho img{{width:92px;height:auto}}
{_P} .bt-baralho .tp{{display:flex;align-items:center;justify-content:space-between;gap:6px}}
{_P} .bt-baralho .tp b{{font-size:1.1rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-baralho .ed{{padding:4px 11px;border-radius:999px;font-size:.74rem;font-weight:800;border:1.5px solid #8B6CFF;color:#fff !important;-webkit-text-fill-color:#fff !important;white-space:nowrap}}
{_P} .bt-baralho p{{margin:4px 0 6px;padding-bottom:6px;font-size:.8rem;border-bottom:1px solid rgba(197,179,255,.25);color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .bt-baralho .ch{{display:flex;flex-wrap:wrap;gap:6px}}
{_P} .bt-baralho .ch span{{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border-radius:999px;font-size:.74rem;font-weight:900;border:1.5px solid var(--k);background:color-mix(in srgb,var(--k) 16%,transparent);color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .bt-baralho .ch svg{{width:15px;height:15px}}
{_P} .st-key-btc_baralho{{position:relative;margin:8px 0 !important}}
{_P} .st-key-bt_gerenciar button{{height:50px !important;border-radius:16px !important;border:2px solid #8B6CFF !important;font-weight:900 !important;letter-spacing:.02em;
  background:linear-gradient(90deg,#1C1457,#2A1A7A 50%,#1C1457) !important;box-shadow:0 0 14px rgba(139,108,255,.55)}}
{_P} .st-key-bt_gerenciar button:after{{content:"»";position:absolute;right:16px;font-size:1.4rem;color:#7C9BFF}}
/* cartões de modo (Central) */
{_P} .st-key-on_modos[data-testid="stVerticalBlock"],{_P} .st-key-on_modos>[data-testid="stVerticalBlock"]{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:8px !important;margin:0 0 6px;align-items:end !important}}
{_P} :is(.st-key-on_card_sis,.st-key-on_card_on)[data-testid="stVerticalBlock"]{{position:relative;gap:0 !important;min-width:0;border-radius:22px;transition:opacity .15s,box-shadow .15s}}
{_P} .on-cm img{{display:block;width:100%;height:auto}}
/* animações (só transform/opacity; "reduzir" e prefers-reduced-motion as desligam; o estado final é o mesmo) */
@keyframes btInL{{from{{transform:translateX(-120%);opacity:0}}to{{transform:none;opacity:1}}}}
@keyframes btInR{{from{{transform:translateX(120%);opacity:0}}to{{transform:none;opacity:1}}}}
@keyframes btVs{{0%{{transform:scale(0);opacity:0}}70%{{transform:scale(1.3);opacity:1}}100%{{transform:scale(1)}}}}
@keyframes btFlash{{0%{{opacity:0}}40%{{opacity:.9}}100%{{opacity:0}}}}
@keyframes btFade{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@keyframes btBar{{from{{width:0}}}}
@keyframes btPulse{{0%,100%{{box-shadow:0 0 0 rgba(34,211,238,0)}}50%{{box-shadow:0 0 18px rgba(34,211,238,.9)}}}}
@keyframes btWin{{0%{{transform:scale(1)}}40%{{transform:scale(1.07)}}100%{{transform:scale(1)}}}}
{_P} .bt-anim .bt-duelo>.ca{{animation:btInL .5s ease-out both}}
{_P} .bt-anim .bt-duelo>.cb{{animation:btInR .5s ease-out both}}
{_P} .bt-anim .bt-duelo .vs{{animation:btVs .45s .45s both}}
{_P} .bt-anim .fl{{position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 50% 50%,rgba(255,255,255,.85),rgba(124,92,255,.5) 30%,transparent 62%);animation:btFlash .6s .4s both}}
{_P} .bt-anim .bt-atr b{{display:inline-block;padding:1px 8px;border-radius:8px;animation:btPulse 1s .8s 2}}
{_P} .bt-anim .big{{animation:btFade .4s 1.2s both}}
{_P} .bt-anim .bt-barra .tr i{{animation:btBar .7s 1.4s both}}
{_P} .bt-anim :is(.bt-c,.bt-ci).venceu{{animation:btWin .6s 2s both}}
{_P} .bt-res.bt-anim{{animation:btFade .4s 2.2s both}}
@media (prefers-reduced-motion:reduce){{{_P} .bt-anim *{{animation:none !important}}}}
"""
CSS = "<style>" + "".join(l.strip() for l in _CSS.splitlines()) + "</style>"

_PONTOS = {"acao": "📈", "fii": "🏢", "etf": "🧺", "cripto": "🪙"}


# ------------------------------------------------------------------ estado / dados
def _agora() -> datetime:
    return datetime.now(BRT)


def _hoje():
    return _agora().date()


def _email() -> str | None:
    u = usuarios.usuario()
    return (u or {}).get("email") or None


def _ir(tela: str) -> None:
    st.session_state["bt_tela"] = tela


def _pessoa() -> dict:
    """Baralho e histórico da pessoa. Conta logada: banco (uma leitura por sessão). Visitante: só nesta sessão."""
    ss = st.session_state
    if "bt_pessoa" not in ss:
        em = _email()
        ss["bt_pessoa"] = BD.ler_pessoa(banco, em) if em else BD.estado_vazio()
    return ss["bt_pessoa"]


def _salvar_pessoa(e: dict) -> None:
    st.session_state["bt_pessoa"] = BD.normalizar_estado(e)
    em = _email()
    if em:
        BD.gravar_pessoa(banco, em, e)


def _cartas(atualizar: bool = True) -> dict:
    """Snapshot das cartas (banco compartilhado). Na Central e no baralho completa/renova as cartas vencidas, poucas por vez; nunca durante o duelo."""
    ss = st.session_state
    agora = _agora().replace(tzinfo=None)
    if "bt_snap" not in ss or time.time() - ss.get("bt_snap_t", 0) > 180:
        ss["bt_snap"], ss["bt_snap_t"] = BD.ler_snapshot(banco), time.time()
    snap = ss["bt_snap"]
    if atualizar and ss.get("bt_tent", 0) < 10 and BD.pendentes(snap, agora):
        ss["bt_tent"] = ss.get("bt_tent", 0) + 1
        with st.spinner("Atualizando as cartas com dados reais…"):
            novo, falta = BD.atualizar(banco, agora)
        ss["bt_snap"], ss["bt_snap_t"] = novo, time.time()
        if falta and len(novo) > len(snap):
            st.rerun()
        snap = novo
    return snap


def _jogaveis(snap: dict) -> dict:
    h = _hoje()
    return {t: c for t, c in snap.items() if B.jogavel(c, h)[0]}


# ------------------------------------------------------------------ HTML das cartas
def _data(ref) -> str:
    try:
        return f"{str(ref)[8:10]}/{str(ref)[5:7]}/{str(ref)[:4]}"
    except Exception:
        return "—"


def carta_html(c: dict, sel: bool = False, trava: str = "", mostrar: list[str] | None = None, extra_cls: str = "", grande: str = "") -> str:
    """Carta com ilustração de fundo da categoria, ticker, nome, categoria, até 3 indicadores reais e a data de referência."""
    cat = B.CATEGORIAS.get(c.get("classe"), {"nome": "—", "cor": "#8B6CFF", "icone": "🃏"})
    ids = mostrar if mostrar is not None else B.indicadores_validos(c)[:3]
    art = ACAR.uri(c.get("tk", ""))
    if art:                                                  # carta com arte própria (cartela enviada); os números reais ficam na faixa abaixo da arte
        ix = "".join(f"<div class='ix'><span>{_e(B.INDICADORES[i]['curto'])}</span><b>{_e(B.formatar(i, (c.get('ind') or {}).get(i)))}</b></div>" for i in ids)
        mot = f"<div class='mot'>🔒 {_e(trava)}</div>" if trava else ""
        cls = f"bt-ci{' sel' if sel else ''}{' trv' if trava else ''}{(' ' + extra_cls) if extra_cls else ''}"
        return (f"<div class='{cls}'><div class='ok'>✓</div><img class='art' src='{art}' alt='{_e(c.get('nome', ''))}'>"
                f"<div class='st'>{grande}{ix}{mot}<div class='dt'>Dados de {_e(_data(c.get('ref')))}</div></div></div>")
    linhas = "".join(f"<div class='ix'><span>{_e(B.INDICADORES[i]['curto'])}</span><b>{_e(B.formatar(i, (c.get('ind') or {}).get(i)))}</b></div>" for i in ids)
    mot = f"<div class='mot'>🔒 {_e(trava)}</div>" if trava else ""
    cls = f"bt-c{' sel' if sel else ''}{' trv' if trava else ''}{(' ' + extra_cls) if extra_cls else ''}"
    return (f"<div class='{cls}' style='--c:{cat['cor']}'><div class='ok'>✓</div><div class='ilu'>{cat['icone']}</div>"
            f"<div class='tk'>{_e(c.get('tk', '').replace('CRIPTO:', ''))}</div><div class='nm'>{_e(c.get('nome', ''))}</div>"
            f"<span class='ct'>{_e(cat['nome'])}</span>{linhas}{grande}{mot}<div class='dt'>Dados de {_e(_data(c.get('ref')))}</div></div>")


def _grade_cartas(cartas: list[dict], marcadas: set, prefixo: str, ao_clicar, travadas: dict | None = None) -> None:
    travadas = travadas or {}
    with st.container(key=f"bt_grade_{prefixo}"):
        for c in cartas:
            with st.container(key=f"btc_{prefixo}_{c['tk'].replace(':', '_')}"):
                st.markdown(carta_html(c, c["tk"] in marcadas, travadas.get(c["tk"], "")), unsafe_allow_html=True)
                st.button(c["tk"], key=f"btb_{prefixo}_{c['tk'].replace(':', '_')}", on_click=ao_clicar, args=(c["tk"],), width="stretch")


def _voltar(destino: str, chave: str, antes=None) -> None:
    def _f():
        if antes:
            antes()
        _ir(destino)
    st.button("Voltar", key=chave, icon=":material/arrow_back:", on_click=_f)


# ------------------------------------------------------------------ TELA 1 · Central
_CORES_CHIP = ("#3DDC97", "#4B8BFF", "#F2B84B", "#B06BFF")
_SPARK = ("<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round' style='color:var(--k)'>"
          "<polyline points='2,19 8,12 12,15 21,5'/><polyline points='15,5 21,5 21,11'/></svg>")


def _limpar_baralho(snap: dict) -> list[str]:
    """Tira do baralho salvo as cartas que não existem mais no jogo (ex.: FIIs desativados) e grava o baralho limpo."""
    pes = _pessoa()
    if not snap:
        return list(pes["deck"])
    limpo = [t for t in pes["deck"] if t in snap]
    if limpo != list(pes["deck"]):
        _salvar_pessoa({**pes, "deck": limpo})
    return limpo


def _central() -> None:
    snap = _cartas()
    jog = _jogaveis(snap)
    _limpar_baralho(snap)
    pes = _pessoa()
    deck = [t for t in pes["deck"] if t in jog]
    ok_deck, msg_deck = B.validar_baralho(pes["deck"], snap, _hoje())
    st.markdown(f"<div class='bt-hero2'><img src='{ART.uri('modo_hero')}' alt='Ticker Battle'></div>", unsafe_allow_html=True)
    try:
        import battle_online_app as ON                       # modos de jogo e histórico online (se o módulo falhar, o Duelo contra Sistema segue)
    except Exception as e:
        banco.registrar_erro("battle_online_import", e)
        ON = None
    if ON:
        ON.cartoes_modo(ok_deck)
    else:
        st.button("JOGAR", key="bt_jogar", icon=":material/play_arrow:", type="primary", width="stretch", disabled=not ok_deck, on_click=_ir, args=("preparar",))
    if not snap:
        st.markdown("<div class='bt-msg er'>As cartas ainda não puderam ser carregadas (fontes de dados indisponíveis agora). Tente de novo em alguns minutos.</div>", unsafe_allow_html=True)
    if not ok_deck:
        txt = msg_deck if pes["deck"] else "Monte seu baralho para jogar."
        st.markdown(f"<div class='bt-alerta'><div class='ic'>⚠️</div><div class='tx'>{_e(txt)}</div><details><summary>Saiba Mais ⓘ</summary>"
                    f"<p>Para jogar, o baralho precisa de {B.BARALHO_MIN} a {B.BARALHO_MAX} cartas, sem repetição e com dados reais atualizados. Toque em Gerenciar Baralho para ajustar.</p></details></div>",
                    unsafe_allow_html=True)
    chips = "".join(f"<span style='--k:{_CORES_CHIP[i % 4]}'>{_SPARK}{_e(t.replace('CRIPTO:', ''))}</span>" for i, t in enumerate(deck[:12]))
    with st.container(key="btc_baralho"):
        st.markdown(f"<div class='bt-baralho'><img src='{ART.uri('pilha')}' alt=''><div><div class='tp'><b>🃏 Meu Baralho</b><span class='ed'>✎ Editar</span></div>"
                    f"<p><b>{len(deck)}</b> carta(s) no baralho · <b>{len(jog)}</b> disponível(is) no total</p><div class='ch'>{chips}</div></div></div>", unsafe_allow_html=True)
        st.button("Editar baralho", key="bt_editar_card", on_click=_ir, args=("baralho",), width="stretch")
    st.button("GERENCIAR BARALHO", key="bt_gerenciar", icon=":material/style:", width="stretch", on_click=_ir, args=("baralho",))
    if ON:
        ON.secao_online()

    st.markdown("<div class='bt-box'><div class='t'><span class='m'>❓</span>Como funciona</div><div class='bt-passos'>"
                "<div><b>🃏</b>Escolha sua carta</div><div><b>🎯</b>Escolha o atributo</div><div><b>⚔️</b>Vence quem tem o melhor valor</div></div>"
                f"<p style='margin-top:8px'>Duelo de {B.RODADAS} rodadas contra o sistema: vence quem ganhar 2. Os valores são indicadores financeiros reais, "
                "e cada indicador tem sua regra (às vezes o menor vence). Empate não pontua. Educacional: não é recomendação de investimento.</p></div>", unsafe_allow_html=True)

    hist = pes["hist"][:5]
    if hist:
        rot = {"vitoria": "Vitória", "derrota": "Derrota", "empate": "Empate"}
        linhas = ""
        for h in hist:
            p = h["placar"]
            linhas += (f"<div class='bt-lin'><div class='r {h['final']}'>{rot.get(h['final'], '—')}</div><div class='x'>"
                       f"{p['jogador']} × {p['adversario']} contra o sistema<small>{_e(h['ts'][8:10])}/{_e(h['ts'][5:7])}/{_e(h['ts'][:4])} · {_e(h['ts'][11:16])}</small></div></div>")
        corpo = linhas
    else:
        corpo = "<div class='bt-vazio'>🏆 Sua primeira batalha está esperando por você!</div>"
    st.markdown(f"<div class='bt-box'><div class='t'><span class='m'>🕘</span>Últimas Batalhas</div>{corpo}</div>", unsafe_allow_html=True)
    if snap:
        ult = max((c.get("gerado", "") for c in snap.values()), default="")
        if ult:
            st.caption(f"Cartas com dados reais (Yahoo Finance, Fundamentus e fontes do app). Última atualização: {ult[8:10]}/{ult[5:7]} {ult[11:16]}.")
    if not _email():
        st.caption("Sem login, o baralho e o histórico valem só nesta visita.")


# ------------------------------------------------------------------ TELA 2 · Coleção e baralho
def _alternar(tk: str) -> None:
    pes = dict(_pessoa())
    deck = list(pes["deck"])
    st.session_state["bt_foco"] = tk
    if tk in deck:
        deck.remove(tk)
    elif len(deck) < B.BARALHO_MAX:
        c = _cartas(False).get(tk)
        if c and B.jogavel(c, _hoje())[0]:
            deck.append(tk)
    _salvar_pessoa({**pes, "deck": deck})


def _focar(tk: str) -> None:
    st.session_state["bt_foco"] = tk


def _baralho() -> None:
    _voltar("central", "bt_v_baralho")
    st.markdown("<div class='bt-tag' style='text-align:left;color:#fff !important;-webkit-text-fill-color:#fff !important'>Meu Baralho</div>", unsafe_allow_html=True)
    snap = _cartas()
    pes = _pessoa()
    deck = [t for t in pes["deck"] if t in snap]
    h = _hoje()
    ok, msg = B.validar_baralho(deck, snap, h)
    st.markdown(f"<div class='bt-conta'><b>{len(deck)}/{B.BARALHO_MAX} cartas</b><span style='font-size:.78rem;color:#BDB5E6'>mín. {B.BARALHO_MIN} · sem repetir</span></div>"
                f"<div class='bt-msg {'ok' if ok else 'er'}'>{'Baralho válido: pronto para jogar!' if ok else _e(msg or 'Escolha as cartas abaixo.')}</div>", unsafe_allow_html=True)
    if not deck:
        st.button("Sugerir baralho inicial", key="bt_sugerir", icon=":material/auto_fix_high:", width="stretch",
                  on_click=lambda: _salvar_pessoa({**_pessoa(), "deck": B.baralho_padrao(_cartas(False), _hoje())}))
    presentes = [k for k in B.CATEGORIAS if any(c.get("classe") == k for c in snap.values())]
    filtro = "Todas"
    if len(presentes) > 1:                                     # com uma categoria só, o filtro não aparece
        filtro = st.radio("Categoria", ["Todas"] + [B.CATEGORIAS[k]["nome"] for k in presentes], horizontal=True, key="bt_filtro", label_visibility="collapsed")
    inv = {v["nome"]: k for k, v in B.CATEGORIAS.items()}
    lista = sorted((c for c in snap.values() if filtro == "Todas" or c.get("classe") == inv.get(filtro)), key=lambda c: (c.get("classe", ""), c["tk"]))
    if not lista:
        st.markdown("<div class='bt-vazio'>Nenhuma carta disponível nesta categoria agora.</div>", unsafe_allow_html=True)
    trav = {c["tk"]: B.jogavel(c, h)[1] for c in lista if not B.jogavel(c, h)[0]}
    _grade_cartas(lista, set(deck), "col", _focar, trav)

    foco = st.session_state.get("bt_foco")
    c = snap.get(foco) if foco else None
    if c:
        cat = B.CATEGORIAS.get(c["classe"], {"cor": "#8B6CFF", "nome": ""})
        barras = ""
        for i in B.indicadores_validos(c):
            v = (c.get("ind") or {}).get(i)
            w = min(100, max(6, abs(float(v)) * (100 if B.INDICADORES[i]["fmt"] == "pct" else 4)))
            barras += (f"<div><span>{_e(B.INDICADORES[i]['nome'])}</span><b>{_e(B.formatar(i, v))}</b></div><i style='--w:{w:.0f}%'></i>"
                       f"<div class='reg'>{_e(B.INDICADORES[i]['regra'])}</div>")
        avisos = "".join(f"<p>⚠️ {_e(a)}</p>" for a in c.get("avisos") or [])
        st.markdown(f"<div class='bt-box bt-det' style='--c:{cat['cor']}'><div class='t'><span class='m'>ℹ️</span>Detalhes da Carta</div>"
                    f"{carta_html(c, c['tk'] in deck)}<div class='b'>{barras or '<p>Sem indicadores disponíveis.</p>'}</div>{avisos}"
                    f"<p>Fonte: {_e(c.get('fonte') or '—')} · referência {_e(_data(c.get('ref')))}. As barras são só visuais; quem vence segue a regra de cada indicador.</p></div>",
                    unsafe_allow_html=True)
        pode, why = B.jogavel(c, h)
        if c["tk"] in deck:
            st.button("REMOVER DO BARALHO", key="bt_rem", icon=":material/remove:", width="stretch", on_click=_alternar, args=(c["tk"],))
        else:
            st.button("ADICIONAR AO BARALHO", key="bt_add", icon=":material/add:", type="primary", width="stretch", on_click=_alternar, args=(c["tk"],),
                      disabled=(not pode) or len(deck) >= B.BARALHO_MAX)
            if not pode:
                st.markdown(f"<div class='bt-msg er'>{_e(why)}</div>", unsafe_allow_html=True)
            elif len(deck) >= B.BARALHO_MAX:
                st.markdown(f"<div class='bt-msg er'>O baralho já tem {B.BARALHO_MAX} cartas. Remova uma para adicionar outra.</div>", unsafe_allow_html=True)
    else:
        st.caption("Toque em uma carta para ver os detalhes e adicioná-la ao baralho.")
    if ok:
        st.button("Preparar duelo", key="bt_ir_prep", icon=":material/sports_esports:", type="primary", width="stretch", on_click=_ir, args=("preparar",))


# ------------------------------------------------------------------ TELA 3 · Preparação
def _iniciar() -> None:
    ss = st.session_state
    snap = _cartas(False)
    pes = _pessoa()
    ok, msg = B.validar_baralho(pes["deck"], snap, _hoje())
    if not ok:
        ss["bt_erro"] = msg
        return
    ref = BD.referencia_dos_dados(snap, list(snap))
    congeladas = {t: dict(c) for t, c in snap.items()}               # dados congelados: o duelo inteiro usa estes valores
    ss["bt_cartas_duelo"] = congeladas
    ss["bt_duelo"] = B.novo_duelo(uuid.uuid4().hex[:12], uuid.uuid4().hex, list(pes["deck"]), _agora().replace(tzinfo=None), ref)
    for k in ("bt_jog", "bt_revelada", "bt_erro", "bt_ind"):
        ss.pop(k, None)
    _ir("arena")


def _preparar() -> None:
    _voltar("central", "bt_v_prep")
    st.markdown("<div class='bt-tag' style='text-align:left;color:#fff !important;-webkit-text-fill-color:#fff !important'>Preparar Duelo</div>", unsafe_allow_html=True)
    snap = _cartas(False)
    pes = _pessoa()
    ok, msg = B.validar_baralho(pes["deck"], snap, _hoje())
    st.markdown("<div class='bt-box'><div class='t'><span class='m'>⚔️</span>Modalidade</div><div class='bt-opc'><div class='ic'>⚔️</div>"
                f"<div><b>Duelo Clássico</b><span>{B.RODADAS} rodadas, uma carta por rodada. Vence quem ganhar 2.</span></div></div></div>"
                "<div class='bt-box'><div class='t'><span class='m'>🤖</span>Adversário</div><div class='bt-opc'><div class='ic'>🤖</div>"
                "<div><b>Sistema</b><span>Escolhe a carta dele por regra fixa e pública, sem olhar seus valores.</span></div></div></div>", unsafe_allow_html=True)
    chips = "".join(f"<span>{_e(t.replace('CRIPTO:', ''))}</span>" for t in pes["deck"])
    st.markdown(f"<div class='bt-box'><div class='t'><span class='m'>🃏</span>Seu baralho ({len(pes['deck'])} cartas)</div><div class='bt-chips'>{chips}</div></div>", unsafe_allow_html=True)
    st.button("Editar baralho", key="bt_edit", icon=":material/edit:", width="stretch", on_click=_ir, args=("baralho",))
    st.markdown("<div class='bt-box'><div class='t'><span class='m'>📘</span>Resumo das regras</div><ul>"
                "<li>Você escolhe a carta e o atributo; o sistema escolhe a adversária e compara.</li>"
                "<li>Cada indicador tem sua regra: maior vence, menor vence ou menor positivo vence.</li>"
                "<li>Só se comparam ativos da mesma categoria e com dados atualizados.</li>"
                "<li>Valores iguais = rodada empatada, sem ponto. Cada carta joga uma vez.</li></ul></div>", unsafe_allow_html=True)
    st.toggle("Reduzir animações", key="bt_sem_anim", help="Mostra os resultados sem os efeitos de entrada. O resultado do duelo não muda.")
    if not ok:
        st.markdown(f"<div class='bt-msg er'>{_e(msg)}</div>", unsafe_allow_html=True)
    if st.session_state.get("bt_erro"):
        st.markdown(f"<div class='bt-msg er'>{_e(st.session_state['bt_erro'])}</div>", unsafe_allow_html=True)
    st.button("INICIAR DUELO", key="bt_iniciar", icon=":material/sports_esports:", type="primary", width="stretch", disabled=not ok, on_click=_iniciar)


# ------------------------------------------------------------------ TELA 4 · Arena
def _escolher_carta(tk: str) -> None:
    ss = st.session_state
    ss["bt_jog"] = tk
    ss.pop("bt_ind", None)


def _trocar_carta() -> None:
    st.session_state.pop("bt_jog", None)
    st.session_state.pop("bt_ind", None)


def _escolher_ind(i: str) -> None:
    st.session_state["bt_ind"] = i


def _disputar() -> None:
    ss = st.session_state
    try:
        ss["bt_duelo"] = B.jogar_rodada(ss["bt_duelo"], ss["bt_cartas_duelo"], ss.get("bt_jog"), ss.get("bt_ind"), _hoje())
        ss["bt_revelada"] = True
        ss.pop("bt_erro", None)
    except (ValueError, KeyError) as e:
        ss["bt_erro"] = str(e)


def _proxima() -> None:
    ss = st.session_state
    for k in ("bt_jog", "bt_ind", "bt_revelada"):
        ss.pop(k, None)
    if B.terminou(ss["bt_duelo"]):
        _concluir()


def _concluir() -> None:
    """Guarda a partida no histórico (uma vez) e abre o resultado."""
    ss = st.session_state
    d = ss["bt_duelo"]
    if d.get("final") and not ss.get("bt_salvo") == d["id"]:
        reg = BD.registro_historico(d, ss["bt_cartas_duelo"])
        _salvar_pessoa(BD.adicionar_historico(_pessoa(), reg))
        ss["bt_salvo"] = d["id"]
    _ir("resultado")


def _abandonar() -> None:
    for k in ("bt_duelo", "bt_jog", "bt_ind", "bt_revelada", "bt_cartas_duelo", "bt_erro"):
        st.session_state.pop(k, None)


def _barra(reg: dict, a: dict, b: dict) -> str:
    m = B.INDICADORES[reg["ind"]]
    pa = reg["barra_a"] * 100
    return (f"<div class='bt-barra'><div class='rt'>{'Vence o maior' if m['melhor'] == 'maior' else 'Vence o menor'}</div>"
            f"<div class='tr'><i class='a' style='--w:{pa:.0f}%'></i><i class='b' style='--w:{100 - pa:.0f}%'></i></div></div>")


def _grande(ind: str, v, rotulo: str = "") -> str:
    return f"<div class='big'>{_e(B.formatar(ind, v))}<small>{_e(B.INDICADORES[ind]['nome'])}</small></div>"


def _arena() -> None:
    ss = st.session_state
    d = ss.get("bt_duelo")
    cartas = ss.get("bt_cartas_duelo")
    if not d or not cartas:
        _ir("central")
        st.rerun()
    h = _hoje()
    n = min(B.rodada_atual(d), B.RODADAS) if not ss.get("bt_revelada") else d["rodadas"][-1]["n"]
    _voltar("preparar", "bt_v_arena", antes=_abandonar)
    p = d["placar"]
    st.markdown(f"<div class='bt-top'><span class='bt-rod'>Rodada {n} de {B.RODADAS}</span><div class='bt-pl'>Você <b>{p['jogador']}</b> × <b>{p['adversario']}</b> Sistema</div></div>",
                unsafe_allow_html=True)
    anim = "" if ss.get("bt_sem_anim") else " bt-anim"
    if ss.get("bt_erro"):
        st.markdown(f"<div class='bt-msg er'>{_e(ss['bt_erro'])}</div>", unsafe_allow_html=True)

    # ---------- rodada já decidida: revelação
    if ss.get("bt_revelada"):
        r = d["rodadas"][-1]
        a, b = cartas[r["jog"]], cartas[r["adv"]]
        ga = r["venc"] == "jogador"
        gb = r["venc"] == "adversario"
        ca = carta_html(a, mostrar=[], extra_cls="venceu" if ga else ("perdeu" if gb else ""), grande=_grande(r["ind"], r["va"]))
        cb = carta_html(b, mostrar=[], extra_cls="venceu" if gb else ("perdeu" if ga else ""), grande=_grande(r["ind"], r["vb"]))
        rot = {"jogador": ("vitoria", "Você venceu a rodada!"), "adversario": ("derrota", "O sistema venceu a rodada."), "empate": ("empate", "Rodada empatada.")}[r["venc"]]
        e = B.explicar(r, cartas)
        st.markdown(f"<div class='bt-arena{anim}'><div class='fl'></div><div class='bt-duelo'><div class='ca'>{ca}</div><img class='vs' src='{ART.uri('vs')}' alt='VS'>"
                    f"<div class='cb'>{cb}</div></div><div class='bt-atr'>Atributo disputado: <b>{_e(B.INDICADORES[r['ind']]['nome'])}</b></div>{_barra(r, a, b)}</div>"
                    f"<div class='bt-res {rot[0]}{anim}'>{rot[1]}<small>{_e(a['tk'].replace('CRIPTO:', ''))} {_e(B.formatar(r['ind'], r['va']))} × {_e(B.formatar(r['ind'], r['vb']))} {_e(b['tk'].replace('CRIPTO:', ''))}</small></div>"
                    f"<div class='bt-edu'><b>Raio-X rápido · {_e(e['nome'])}.</b> {_e(e['significa'])} {_e(e['porque'])}</div>", unsafe_allow_html=True)
        fim = B.terminou(d)
        st.button("VER RESULTADO FINAL" if fim else "PRÓXIMA RODADA", key="bt_prox", icon=":material/arrow_forward:", type="primary", width="stretch", on_click=_proxima)
        st.toggle("Reduzir animações", key="bt_sem_anim")
        return

    # ---------- escolha da carta
    tk = ss.get("bt_jog")
    if not tk or tk not in B.cartas_disponiveis(d):
        st.markdown("<div class='bt-atr'>Escolha a carta que vai entrar nesta rodada</div>", unsafe_allow_html=True)
        mao = [cartas[t] for t in B.cartas_disponiveis(d) if t in cartas]
        sem = {c["tk"]: "Sem adversária compatível" for c in mao if B.adversaria_da_rodada(d, cartas, c["tk"], h) is None}
        if mao and len(sem) == len(mao):
            st.markdown("<div class='bt-msg er'>Nenhuma carta que sobrou tem adversária com dados compatíveis. O duelo não pode continuar; volte e atualize o baralho.</div>", unsafe_allow_html=True)
        with st.container(key="bt_mao"):
            for c in mao:
                bloq = sem.get(c["tk"], "")
                with st.container(key=f"btc_m_{c['tk'].replace(':', '_')}"):
                    st.markdown(carta_html(c, False, bloq), unsafe_allow_html=True)
                    st.button(c["tk"], key=f"btb_m_{c['tk'].replace(':', '_')}", on_click=_escolher_carta, args=(c["tk"],), width="stretch", disabled=bool(bloq))
        return

    # ---------- carta escolhida → adversária (regra fixa) → atributo
    a = cartas[tk]
    b = B.adversaria_da_rodada(d, cartas, tk, h)
    if b is None:
        st.markdown("<div class='bt-msg er'>Não há carta adversária compatível com esta carta. Escolha outra.</div>", unsafe_allow_html=True)
        st.button("Trocar carta", key="bt_troca0", icon=":material/swap_horiz:", on_click=_trocar_carta)
        return
    disp = B.atributos_disputaveis(a, b, h)
    ind = ss.get("bt_ind") if ss.get("bt_ind") in disp["ok"] else None
    oculto = "<div class='bt-oculto'>?</div>"
    ca = carta_html(a, mostrar=disp["ok"][:3] or None)
    cb = carta_html(b, mostrar=[], grande=oculto)
    st.markdown(f"<div class='bt-arena{anim}'><div class='fl'></div><div class='bt-duelo'><div class='ca'>{ca}</div><img class='vs' src='{ART.uri('vs')}' alt='VS'>"
                f"<div class='cb'>{cb}</div></div><div class='bt-atr'>Os valores do sistema aparecem quando você confirmar.</div></div>", unsafe_allow_html=True)
    st.button("Trocar carta", key="bt_troca", icon=":material/swap_horiz:", on_click=_trocar_carta)
    st.markdown("<div class='bt-atr'>Escolha qual atributo será disputado nesta rodada</div>", unsafe_allow_html=True)
    if not disp["ok"]:
        st.markdown("<div class='bt-msg er'>Estas cartas não têm nenhum indicador comparável. Troque a carta.</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for k, i in enumerate(disp["ok"]):
        m = B.INDICADORES[i]
        cols[k % 2].button(m["nome"], key=f"bt_i_{i}", icon=f":material/{m['icone']}:", width="stretch", type="primary" if ind == i else "secondary",
                           on_click=_escolher_ind, args=(i,))
    for i, mot in disp["bloqueados"].items():
        if a.get("classe") in B.INDICADORES[i]["classes"]:
            st.markdown(f"<div class='bt-bloq'>🔒 {_e(B.INDICADORES[i]['nome'])}: {_e(mot)}</div>", unsafe_allow_html=True)
    if ind:
        m = B.INDICADORES[ind]
        st.markdown(f"<div class='bt-edu'><b>{_e(m['nome'])}.</b> {_e(m['significa'])} <b>Regra:</b> {_e(m['regra'])}</div>", unsafe_allow_html=True)
    st.button("DISPUTAR", key="bt_disputar", icon=":material/bolt:", type="primary", width="stretch", disabled=ind is None, on_click=_disputar)
    if ind is None:
        st.markdown("<div class='bt-msg' style='text-align:center;color:#BDB5E6'>⏳ Aguardando sua escolha…</div>", unsafe_allow_html=True)
    st.toggle("Reduzir animações", key="bt_sem_anim")


# ------------------------------------------------------------------ TELA 5 · Resultado e Raio-X
def _outra() -> None:
    _abandonar()
    st.session_state.pop("bt_salvo", None)
    _ir("preparar")


def _resultado() -> None:
    ss = st.session_state
    d = ss.get("bt_duelo")
    cartas = ss.get("bt_cartas_duelo")
    if not d or not cartas or not d.get("final"):
        _ir("central")
        st.rerun()
    f = d["final"]
    p = d["placar"]
    titulo = {"vitoria": ("Vitória!", "Você venceu o duelo."), "derrota": ("Derrota", "O sistema venceu desta vez."), "empate": ("Empate", "O duelo terminou igual.")}[f]
    anim = "" if ss.get("bt_sem_anim") else " bt-anim"
    st.markdown(f"<div class='bt-final {f}'><div class='tt'>{titulo[0]}</div><div class='rs'>{titulo[1]}</div>"
                f"<div class='pl'>Você {p['jogador']} × {p['adversario']} Sistema</div>"
                f"<div class='rs'>{p['empates']} rodada(s) empatada(s)</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='bt-atr'>Resumo das rodadas e Raio-X da Batalha</div>", unsafe_allow_html=True)
    for k, r in enumerate(d["rodadas"]):
        a, b = cartas[r["jog"]], cartas[r["adv"]]
        e = B.explicar(r, cartas)
        rot = {"jogador": ("vitoria", "Você venceu"), "adversario": ("derrota", "Sistema venceu"), "empate": ("empate", "Empate")}[r["venc"]]
        ga, gb = r["venc"] == "jogador", r["venc"] == "adversario"
        ca = carta_html(a, mostrar=[], extra_cls="venceu" if ga else ("perdeu" if gb else ""), grande=_grande(r["ind"], r["va"]))
        cb = carta_html(b, mostrar=[], extra_cls="venceu" if gb else ("perdeu" if ga else ""), grande=_grande(r["ind"], r["vb"]))
        st.markdown(f"<div class='bt-box'><div class='t'>Rodada {r['n']} · {_e(B.INDICADORES[r['ind']]['nome'])}"
                    f"<span class='bt-lin' style='margin-left:auto;padding:0;border:0'><span class='r {rot[0]}'>{rot[1]}</span></span></div>"
                    f"<div class='bt-arena'><div class='bt-duelo'><div>{ca}</div><div></div><div>{cb}</div></div>{_barra(r, a, b)}</div>"
                    f"<p>Dados de referência: {_e(a['tk'].replace('CRIPTO:', ''))} em {_e(_data(r['ref_jog']))} · {_e(b['tk'].replace('CRIPTO:', ''))} em {_e(_data(r['ref_adv']))}.</p>"
                    f"<details class='bt-rx'{' open' if k == 0 else ''}><summary>🔎 Raio-X da rodada</summary>"
                    f"<p><b>O que significa:</b> {_e(e['significa'])}</p><p><b>Por que importa:</b> {_e(e['relevancia'])}</p>"
                    f"<p><b>Regra:</b> {_e(e['regra'])}</p><p><b>Resultado:</b> {_e(e['porque'])}</p>"
                    f"<p><b>Limitações:</b> {_e(e['limites'])}</p><p><b>O que não dá para concluir:</b> {_e(e['nao_conclui'])}</p></details></div>", unsafe_allow_html=True)
    st.caption("Educacional: carteira e cartas com dados reais, sem recomendação de investimento. Nada aqui paga XP, moedas ou recompensas.")
    st.button("PRÓXIMA PARTIDA", key="bt_outra", icon=":material/replay:", type="primary", width="stretch", on_click=_outra)
    st.button("Voltar à Central do Battle", key="bt_central", icon=":material/home:", width="stretch", on_click=lambda: (_abandonar(), _ir("central")))


# ------------------------------------------------------------------ página
def pagina_battle() -> None:
    ss = st.session_state
    st.markdown(CSS, unsafe_allow_html=True)
    if not banco.cfg_disponivel():
        st.markdown("<div class='bt-msg er'>O Ticker Battle precisa do banco de dados do sistema, que não está disponível agora.</div>", unsafe_allow_html=True)
        return
    tela = ss.get("bt_tela") if ss.get("bt_tela") in TELAS + TELAS_ONLINE + ("modo",) else "central"
    if tela == "modo":                                       # a antiga tela de escolha de modo agora é a própria Central
        tela = "central"
    if tela in TELAS_ONLINE:
        try:
            import battle_online_app as ON                  # import tardio: o Duelo contra Sistema não depende do módulo online
        except Exception as e:
            banco.registrar_erro("battle_online_import", e)
            ss["bt_tela"] = "central"
            _central()
            return
        ss["bt_tela"] = tela
        ON.pagina_online(tela)
        return
    if tela in ("arena", "resultado") and not ss.get("bt_duelo"):
        tela = "central"
    ss["bt_tela"] = tela
    {"central": _central, "baralho": _baralho, "preparar": _preparar, "arena": _arena, "resultado": _resultado}[tela]()
