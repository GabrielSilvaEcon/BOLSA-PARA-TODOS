"""Trader Battle · interface (Streamlit). Mobile primeiro, no padrão visual do TickerHunters.

Toda regra mora em `trader_battle.py` e toda leitura de cenário em `trader_dados.py`. Aqui só se desenha o que `TB.visao()` entrega
(candles já revelados pelo relógio do servidor) e se coleta o que a pessoa registra. Independente do Ticker Battle.
"""
from __future__ import annotations

import html
import time

import streamlit as st

import arte_cartela as CT
import arte_trader as ART
import mascote_novo as MN
import trader_battle as TB
import trader_carteira as TCA
import trader_dados as TD
import trader_grafico as TG
import trader_online_dados as TOD

_e = html.escape
_P = "html body .stApp.stApp.stApp"
VERDE, VERM, ROXO, OURO, AZUL = "#26D07C", "#FF4D6D", "#8B6CFF", "#F2B84B", "#4B8BFF"
POLL_S = 1.0

_CSS = f"""
{_P} [data-testid="stMainBlockContainer"],{_P} .block-container{{max-width:560px !important}}
{_P} .tb-hero{{margin:-8px -6px 0;text-align:center}}
{_P} .tb-hero img{{display:block;width:100%;max-width:420px;margin:0 auto;-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 8%,#000 90%,transparent 100%);mask-image:linear-gradient(to bottom,transparent 0,#000 8%,#000 90%,transparent 100%)}}
{_P} .tb-demo{{margin:4px 0;padding:8px 12px;border-radius:14px;border:1.5px solid {OURO};background:rgba(242,184,75,.12);font-size:.8rem;font-weight:700;color:#FFE3A3 !important;-webkit-text-fill-color:#FFE3A3 !important}}
{_P} .tb-chips{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:6px 0}}
{_P} .tb-chips div{{text-align:center;padding:8px 4px;border-radius:14px;border:1px solid rgba(139,108,255,.45);background:linear-gradient(160deg,rgba(60,44,150,.5),rgba(18,12,56,.9));font-size:.68rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-chips b{{display:block;font-size:.92rem;white-space:nowrap;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-top{{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;padding:6px 10px;border-radius:14px;border:1px solid rgba(139,108,255,.45);background:linear-gradient(160deg,rgba(60,44,150,.5),rgba(18,12,56,.92))}}
{_P} .tb-top .tk{{font-weight:900;font-size:.95rem;color:#fff !important;-webkit-text-fill-color:#fff !important;line-height:1.1}}
{_P} .tb-top .tk small{{display:block;font-weight:600;font-size:.68rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-rod{{display:flex;align-items:center;gap:4px;padding:3px 10px 3px 4px;border-radius:999px;border:1px solid {ROXO};font-size:.74rem;font-weight:800;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-rod img{{width:20px;height:20px}}
{_P} .tb-rod .tb-rn{{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:linear-gradient(160deg,#E0903A,#9A5418);border:1px solid #F3B66B;font-size:.68rem;font-weight:900;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-rel{{font-weight:900;font-size:1.25rem;font-variant-numeric:tabular-nums;color:{VERDE} !important;-webkit-text-fill-color:{VERDE} !important}}
{_P} .tb-rel.fim{{color:{VERM} !important;-webkit-text-fill-color:{VERM} !important}}
{_P} .tb-pill{{display:inline-block;margin-left:4px;padding:1px 7px;border-radius:999px;font-size:.6rem;font-weight:900;background:{OURO};color:#1A1030 !important;-webkit-text-fill-color:#1A1030 !important}}
{_P} .tb-h{{font-weight:900;font-size:.9rem;color:#fff !important;-webkit-text-fill-color:#fff !important;margin:2px 0}}
{_P} .tb-cap{{font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-ok{{padding:6px 10px;border-radius:12px;border:1px solid {VERDE};background:rgba(38,208,124,.12);font-size:.78rem;font-weight:800;color:#8DF5C1 !important;-webkit-text-fill-color:#8DF5C1 !important}}
{_P} .tb-er{{padding:6px 10px;border-radius:12px;border:1px solid {VERM};background:rgba(255,77,109,.12);font-size:.78rem;font-weight:800;color:#FFB0BD !important;-webkit-text-fill-color:#FFB0BD !important}}
{_P} .tb-aviso{{padding:6px 10px;border-radius:12px;border:1px solid rgba(139,108,255,.5);background:rgba(139,108,255,.12);font-size:.76rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-card{{padding:10px 12px;border-radius:16px;border:1.5px solid rgba(139,108,255,.5);background:radial-gradient(circle at 100% 0,rgba(139,108,255,.25),transparent 60%),linear-gradient(160deg,#17114A,#0A0720 90%);margin:4px 0}}
{_P} .tb-card b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-card p{{margin:3px 0 0;font-size:.8rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-pts{{text-align:center;padding:12px;border-radius:18px;border:2px solid {VERDE};background:radial-gradient(circle at 50% 0,rgba(38,208,124,.3),transparent 65%),linear-gradient(160deg,#0E2A2A,#0A0720 90%);margin:4px 0}}
{_P} .tb-pts .n{{font-size:2.3rem;font-weight:900;line-height:1;color:{VERDE} !important;-webkit-text-fill-color:{VERDE} !important}}
{_P} .tb-pts small{{display:block;margin-top:2px;font-size:.76rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-troph{{text-align:center}}{_P} .tb-troph img{{width:60%;max-width:240px}}
{_P} .tb-lin-n{{display:inline-flex;align-items:center;gap:8px}}
{_P} .tb-lin{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-top:1px solid rgba(255,255,255,.1);font-size:.85rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-lin span{{font-weight:900;color:{VERDE} !important;-webkit-text-fill-color:{VERDE} !important}}
{_P} .tb-lin span.down{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .tb-fin{{text-align:center;border-width:2px !important}}
{_P} .tb-fin .t{{font-weight:800;font-size:.85rem;opacity:.9}}
{_P} .tb-fin .v{{font-weight:900;font-size:1.9rem;line-height:1.2}}
{_P} .tb-fin .s{{font-size:.78rem;margin-bottom:6px;opacity:.9}}
{_P} .tb-fin small{{display:block;margin-top:6px;font-size:.7rem;opacity:.75}}
{_P} .tb-fin.up{{border-color:#34E85E !important;background:linear-gradient(160deg,rgba(52,232,94,.18),rgba(10,7,32,.9)) !important}}
{_P} .tb-fin.up .v{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .tb-fin.down{{border-color:#FF3D63 !important;background:linear-gradient(160deg,rgba(255,61,99,.18),rgba(10,7,32,.9)) !important}}
{_P} .tb-fin.down .v{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .st-key-tb_jogar button,{_P} .st-key-tb_salvar button,{_P} .st-key-tb_prox button,{_P} .st-key-tb_de_novo button{{height:48px !important;border:0 !important;border-radius:14px !important;font-weight:900 !important;
  background:linear-gradient(90deg,#2EE86B,#14C9B5) !important;box-shadow:0 0 16px rgba(46,232,107,.4) !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_salvar,.st-key-tb_prox,.st-key-tb_de_novo) button :is(p,span){{color:#06240F !important;-webkit-text-fill-color:#06240F !important;font-weight:900 !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_salvar,.st-key-tb_prox,.st-key-tb_de_novo) button:disabled{{filter:grayscale(.8) brightness(.6)}}
{_P} .st-key-tb_sala button,{_P} .st-key-tb_voltar button,{_P} .st-key-tb_replay_ja button{{border-radius:14px !important;border:1.5px solid rgba(139,108,255,.6) !important}}
{_P} .st-key-tb_estr{{gap:.4rem !important;padding:8px 10px;border-radius:16px;border:1.5px solid rgba(139,108,255,.5);background:linear-gradient(160deg,#17114A,#0A0720 90%)}}
{_P} .st-key-tb_conf_l [data-testid="stHorizontalBlock"]{{align-items:center;flex-wrap:nowrap !important;gap:.4rem !important}}
{_P} .st-key-tb_ferr [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:.4rem !important}}
{_P} .st-key-tb_ferr button{{min-height:38px !important;border-radius:12px !important;padding:0 8px !important;font-size:.78rem !important;width:100% !important}}
{_P} .st-key-tb_ferr [data-testid="stPopover"]{{width:100%}}
{_P} .st-key-tb_estr [data-testid="stNumberInputStepUp"],{_P} .st-key-tb_estr [data-testid="stNumberInputStepDown"]{{display:none !important}}
{_P} .tb-faixa img{{display:block;width:100%;max-width:420px;margin:2px auto}}
{_P} .tb-fim-t{{margin:2px 0 4px;padding:10px 12px;text-align:center;border-radius:16px;border:2px solid #5B8BFF;background:linear-gradient(160deg,#2A1F8E,#120C48);box-shadow:0 0 16px rgba(91,139,255,.5);font-weight:900;font-style:italic;font-size:1.55rem;letter-spacing:.5px;color:#fff !important;-webkit-text-fill-color:#fff !important;text-shadow:0 0 12px rgba(124,108,255,.9)}}
{_P} .tb-fim-h{{display:flex;align-items:center;gap:8px;margin:4px 0}}
{_P} .tb-fim-h img{{width:44%;max-width:190px;flex:none;filter:drop-shadow(0 0 16px rgba(255,201,60,.45))}}
{_P} .tb-fim-lg{{flex:1;text-align:center;font-weight:800;font-size:1rem;line-height:1.2;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .tb-fim-lg b{{display:block;font-size:2.1rem;font-weight:900;font-style:italic;line-height:1.05;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important;text-shadow:0 0 14px rgba(255,201,60,.55)}}
{_P} .tb-fim-lg.n b{{color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important;text-shadow:0 0 12px rgba(139,124,255,.6)}}
{_P} .tb-fim-lg small{{display:block;margin-top:4px;font-size:.78rem;font-weight:700;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-st{{display:flex;gap:8px;margin:6px 0}}
{_P} .tb-st .bx{{flex:1 1 0;min-width:0;text-align:center;padding:8px 6px;border-radius:16px;border:2px solid #F2B84B;background:linear-gradient(160deg,rgba(242,184,75,.16),rgba(12,8,44,.92));box-shadow:0 0 14px rgba(242,184,75,.3)}}
{_P} .tb-st .bx small{{display:block;font-size:.8rem;font-weight:800;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .tb-st .bx b{{display:block;font-size:2rem;font-weight:900;line-height:1.1;white-space:nowrap;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-st .bx i{{display:block;font-style:normal;font-size:.7rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-st .bx.rt{{border-color:#8B7CFF;box-shadow:0 0 14px rgba(139,124,255,.3);background:linear-gradient(160deg,rgba(139,124,255,.18),rgba(12,8,44,.92))}}
{_P} .tb-st .bx.up{{border-color:#34E85E;background:linear-gradient(160deg,rgba(52,232,94,.18),rgba(12,8,44,.92));box-shadow:0 0 14px rgba(52,232,94,.35)}}
{_P} .tb-st .bx.up b{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .tb-st .bx.down{{border-color:#FF3D63;background:linear-gradient(160deg,rgba(255,61,99,.18),rgba(12,8,44,.92));box-shadow:0 0 14px rgba(255,61,99,.35)}}
{_P} .tb-st .bx.down b{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .tb-st .bx.pos b{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}{_P} .tb-st .bx.neg b{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .tb-pl{{margin:6px 0;padding:8px 10px;border-radius:16px;border:2px solid #5B4BD6;background:linear-gradient(160deg,#17114A,#0A0720 90%);box-shadow:0 0 12px rgba(91,75,214,.4)}}
{_P} .tb-pl .h{{font-weight:900;font-size:.95rem;margin-bottom:4px;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-pr{{display:grid;grid-template-columns:30px minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:7px 8px;border-top:1px solid rgba(255,255,255,.08);font-size:.92rem;font-weight:700;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-pr:nth-child(2){{border-top:0}}
{_P} .tb-pr .rk{{font-weight:900;font-size:1.05rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-pr.p1 .rk{{color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}{_P} .tb-pr.p2 .rk{{color:#E4E6F5 !important;-webkit-text-fill-color:#E4E6F5 !important}}{_P} .tb-pr.p3 .rk{{color:#F2B07A !important;-webkit-text-fill-color:#F2B07A !important}}
{_P} .tb-pr .nm{{display:flex;align-items:center;gap:8px;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
{_P} .tb-av{{flex:none;width:30px;height:30px;border-radius:50%;overflow:hidden;background:#1B1545;box-shadow:0 0 0 2px #6C5CFF}}
{_P} .tb-av img{{width:100%;height:100%;object-fit:cover;display:block}}
{_P} .tb-pr b{{font-variant-numeric:tabular-nums}}
{_P} .tb-pr em{{font-style:normal;font-weight:900;min-width:64px;text-align:right;font-variant-numeric:tabular-nums}}
{_P} .tb-pr em.up{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}{_P} .tb-pr em.down{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}{_P} .tb-pr em.zero{{color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-pr.eu{{border:2px solid #F2B84B;border-radius:12px;background:linear-gradient(90deg,rgba(242,184,75,.28),rgba(242,184,75,.06));box-shadow:0 0 12px rgba(242,184,75,.35)}}
{_P} .tb-ri{{display:flex;gap:10px;align-items:flex-start;margin:5px 0;padding:8px 10px;border-radius:14px;border:1px solid rgba(139,108,255,.45);border-left:4px solid #8B6CFF;background:linear-gradient(160deg,rgba(60,44,150,.45),rgba(18,12,56,.92))}}
{_P} .tb-ri.al{{border-left-color:#FF3D63}}{_P} .tb-ri.pt{{border-left-color:#F2B84B}}
{_P} .tb-ri .ic{{font-size:1.1rem;line-height:1.3}}
{_P} .tb-ri b{{display:block;font-size:.7rem;font-weight:900;letter-spacing:.3px;text-transform:uppercase;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_P} .tb-ri p{{margin:1px 0 0;font-size:.82rem;line-height:1.35;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-xp{{display:flex;align-items:center;justify-content:center;gap:8px;margin:6px 0;padding:8px 12px;border-radius:16px;border:2px solid #8B6CFF;background:linear-gradient(160deg,rgba(139,108,255,.3),rgba(12,8,44,.92));box-shadow:0 0 14px rgba(139,108,255,.45)}}
{_P} .tb-xp span{{font-size:1.3rem}}
{_P} .tb-xp b{{font-size:1.35rem;font-weight:900;color:#C9A8FF !important;-webkit-text-fill-color:#C9A8FF !important;text-shadow:0 0 10px rgba(176,107,255,.6)}}
{_P} .tb-xp small{{font-size:.78rem;font-weight:700;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-xp.n{{border-color:rgba(139,108,255,.45);box-shadow:none}}
{_P} .tb-rx-r{{margin:8px 0 2px;font-weight:900;font-size:.85rem;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .tb-fim-rod{{text-align:center;margin:6px 0 2px;font-style:italic;font-size:.8rem;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_P} [class*="st-key-tb_estr"] [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:.4rem !important}}
{_P} [class*="st-key-tb_estr"] [data-testid="stNumberInput"] input{{min-height:38px}}
{_P} .tb-graf [data-testid="stPlotlyChart"]{{border-radius:14px;overflow:hidden}}
"""
CSS = "<style>" + "".join(l.strip() for l in _CSS.splitlines()) + "</style>"

# Tela inicial (referência enviada), celular primeiro. Seletores fortes para vencer o relevo global dos botões do app.
_Q = f'{_P} [data-testid="stMain"]'


def _bt(chave: str) -> str:
    return f'{_Q} .st-key-{chave} .stButton > button[data-testid]'


_CSS_CENTRAL = "<style>" + "".join(l.strip() for l in f"""
{_P} .tb-hero{{margin:-4px 0 4px}}
{_P} .tb-hero img{{max-width:100% !important;border-radius:18px;-webkit-mask-image:none !important;mask-image:none !important;border:2px solid rgba(139,108,255,.6);box-shadow:0 0 18px rgba(139,108,255,.5)}}
{_P} .tb-demo2{{display:flex;align-items:center;gap:8px;margin:6px 0;padding:10px 6px 10px 14px;border-radius:18px;border:2px solid #F2B84B;
  background:linear-gradient(160deg,rgba(242,184,75,.16),rgba(18,12,56,.94));box-shadow:0 0 16px rgba(242,184,75,.35)}}
{_P} .tb-demo2 b{{display:flex;align-items:center;gap:8px;font-size:1rem;font-weight:900;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .tb-demo2 b span{{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#F2B84B;font-size:.8rem;font-style:italic;color:#1A1030 !important;-webkit-text-fill-color:#1A1030 !important}}
{_P} .tb-demo2 p{{margin:4px 0 0;font-size:.78rem;line-height:1.35;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .tb-demo2 img{{flex:none;width:78px;height:auto;border-radius:16px;border:2px solid rgba(242,184,75,.6);box-shadow:0 0 12px rgba(242,184,75,.35)}}
{_P} .tb-sec{{display:flex;align-items:center;gap:8px;margin:10px 0 2px;font-weight:800;font-size:1.02rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-sec span{{font-size:1.15rem}}
{_P} .st-key-tb_fmts{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem !important}}
{_P} .st-key-tb_fmts > div{{width:auto !important;min-width:0 !important}}
{_P} .st-key-tb_fmts > div:only-child{{grid-column:1/-1;display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem !important}}
{_P} :is(.st-key-tb_fmts,.st-key-tb_modos) [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:.5rem !important;overflow:visible !important}}
{_P} :is(.st-key-tb_fmts,.st-key-tb_modos) [data-testid="stColumn"]{{flex:1 1 0 !important;width:auto !important;min-width:0 !important;overflow:visible !important}}
{_bt('tb_fmtb_rapida')},{_bt('tb_fmtb_intermediaria')},{_bt('tb_fmtb_longa')}{{position:relative;min-height:62px !important;padding:6px 6px !important;border-radius:18px !important;
  border:2px solid #5B4BD6 !important;background:linear-gradient(160deg,#241A86,#150F55) !important;box-shadow:0 0 10px rgba(91,75,214,.4) !important;overflow:visible !important}}
{_P} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) button > div > span{{flex-direction:column !important;gap:2px !important;align-items:center !important}}
{_P} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa,.st-key-tb_jogar,.st-key-tb_amigos) button [data-testid="stMarkdownContainer"]{{width:100% !important}}
{_P} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) button p{{text-align:center !important}}
{_P} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) button [data-testid="stIconMaterial"]{{font-size:1.6rem !important;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) button p{{font-weight:900 !important;font-size:.95rem !important;line-height:1.1 !important;text-align:left !important;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) button p::after{{display:block;margin-top:2px;font-weight:600;font-size:.68rem;line-height:1.25;white-space:pre;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_Q} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) .stButton > button[data-testid="stBaseButton-primary"]{{border-color:#34E85E !important;
  background:linear-gradient(160deg,rgba(52,232,94,.22),#150F55 80%) !important;box-shadow:0 0 16px rgba(52,232,94,.5) !important}}
{_Q} :is(.st-key-tb_fmtb_rapida,.st-key-tb_fmtb_intermediaria,.st-key-tb_fmtb_longa) .stButton > button[data-testid="stBaseButton-primary"] p::after{{color:#8DF5C1 !important;-webkit-text-fill-color:#8DF5C1 !important}}
{_P} .st-key-tb_fmtb_intermediaria button::before{{content:"Recomendado";position:absolute;top:-10px;left:50%;transform:translateX(-50%);padding:1px 8px;border-radius:999px;background:#34E85E;
  font-size:.62rem;font-weight:900;white-space:nowrap;color:#06240F;-webkit-text-fill-color:#06240F;box-shadow:0 0 8px rgba(52,232,94,.6)}}
{_P} .st-key-tb_fmts{{padding-top:8px}}
{_bt('tb_jogar')},{_bt('tb_amigos')}{{position:relative;min-height:150px !important;padding:12px 10px 34px !important;border-radius:22px !important;overflow:visible !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_amigos) button > div > span{{flex-direction:column !important;gap:4px !important;align-items:center !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_amigos) button [data-testid="stIconMaterial"]{{font-size:2.8rem !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_amigos) button p{{font-weight:900 !important;font-size:1.05rem !important;text-align:center !important;white-space:normal !important;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_amigos) button p::after{{display:block;margin-top:4px;font-weight:500;font-size:.74rem;line-height:1.3;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .st-key-tb_jogar button p::after{{content:"Desafie-se e melhore seu desempenho!"}}
{_P} .st-key-tb_amigos button p::after{{content:"Convide seus amigos para uma batalha!"}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_amigos) button::after{{content:"→";position:absolute;right:10px;bottom:9px;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:900;font-size:.95rem;color:#fff;-webkit-text-fill-color:#fff}}
{_bt('tb_jogar')}{{border:2px solid #34E85E !important;background:linear-gradient(160deg,rgba(20,110,80,.75),rgba(10,26,40,.96)) !important;box-shadow:0 0 18px rgba(52,232,94,.45) !important}}
{_P} .st-key-tb_jogar button [data-testid="stIconMaterial"]{{color:#34E85E !important;-webkit-text-fill-color:#34E85E !important}}
{_P} .st-key-tb_jogar button::after{{border:2px solid #34E85E}}
{_bt('tb_amigos')}{{border:2px solid #8B6CFF !important;background:linear-gradient(160deg,rgba(110,70,230,.7),rgba(20,12,64,.96)) !important;box-shadow:0 0 18px rgba(139,108,255,.5) !important}}
{_P} .st-key-tb_amigos button [data-testid="stIconMaterial"]{{color:#A99BFF !important;-webkit-text-fill-color:#A99BFF !important}}
{_P} .st-key-tb_amigos button::after{{border:2px solid #B9A8FF}}
{_P} .st-key-tb_amigos button::before{{content:"👥 2-4";position:absolute;top:-1px;right:-1px;padding:2px 8px;border-radius:0 20px 0 12px;background:#1E7A3C;border:1.5px solid #34E85E;
  font-size:.7rem;font-weight:900;color:#fff;-webkit-text-fill-color:#fff}}
{_bt('tb_sala_row')}{{position:relative;min-height:58px !important;justify-content:flex-start !important;padding:6px 40px 6px 14px !important;border-radius:18px !important;
  border:2px solid #5B4BD6 !important;background:linear-gradient(160deg,#2A1F8E,#150F55) !important;box-shadow:0 0 12px rgba(91,75,214,.45) !important}}
{_P} .st-key-tb_sala_row button > div, {_P} .st-key-tb_sala_row button > div > span{{justify-content:flex-start !important;gap:12px !important}}
{_P} .st-key-tb_sala_row button [data-testid="stIconMaterial"]{{font-size:1.9rem !important;color:#E4DEFF !important}}
{_P} .st-key-tb_sala_row button p{{text-align:left !important;font-weight:900 !important;font-size:1rem !important;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .st-key-tb_sala_row button p::after{{content:"Digite o código de um amigo";display:block;font-weight:500;font-size:.76rem;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_P} .st-key-tb_sala_row button::after{{content:"›";position:absolute;right:16px;top:50%;transform:translateY(-52%);font-size:1.8rem;font-weight:400;color:#E4DEFF;-webkit-text-fill-color:#E4DEFF}}
{_P} .st-key-tb_painel{{gap:.5rem !important}}
{_P} .tb-sobre{{margin:10px 0 6px;padding:10px 8px;border-radius:18px;border:2px solid #5B4BD6;background:linear-gradient(160deg,#1B1470,#0E0840);box-shadow:0 0 12px rgba(91,75,214,.4)}}
{_P} .tb-sobre .h{{font-weight:900;font-size:.92rem;margin:0 0 6px 4px;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-sobre .g{{display:grid;grid-template-columns:repeat(4,1fr)}}
{_P} .tb-sobre .g div{{text-align:center;padding:2px 2px;border-left:1px solid rgba(139,108,255,.35)}}
{_P} .tb-sobre .g div:first-child{{border-left:0}}
{_P} .tb-sobre i{{display:block;font-style:normal;font-size:1.25rem}}
{_P} .tb-sobre b{{display:block;font-weight:900;font-size:.95rem;white-space:nowrap;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-sobre small{{display:block;font-size:.66rem;line-height:1.2;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
""".splitlines()) + "</style>"



# ------------------------------------------------------------------ estado da sessão
def _ss():
    return st.session_state


def _agora() -> float:
    return time.time()


def _conta() -> dict | None:
    try:
        import usuarios
        return usuarios.usuario()
    except Exception:
        return None


def _jogador() -> str:
    try:
        import usuarios
        u = usuarios.usuario()
        return (u or {}).get("email") or ""
    except Exception:
        return ""


def _partida() -> dict | None:
    return _ss().get("tb_p")


def _cen() -> dict:
    return _ss().get("tb_cen") or {}


def _cenario_atual(p: dict) -> dict:
    return _cen()[p["cenarios"][p["rodada"] - 1]]


def _zerar_rascunho() -> None:
    for k in [k for k in _ss() if k.startswith("tb_") and not k.startswith("tb_i_") and k not in ("tb_p", "tb_cen", "tb_tf")]:
        _ss().pop(k, None)


def _liquidar(p: dict, forcar: bool = False) -> None:
    """Lança no patrimônio da Wallet Game o resultado das rodadas encerradas (idempotente; só consulta o banco quando surge resultado novo)."""
    if not p.get("apostas"):
        return
    k, n = f"tb_liq_{p['id']}", len(p["resultados"])
    if forcar or _ss().get(k) != n:
        TCA.liquidar_seguro(p)
        _ss()[k] = n


def _stake_rodada(p: dict) -> None:
    """Mesa, modo individual: a aposta da rodada nova (1% do patrimônio de agora) é gravada uma vez, DEPOIS de lançar a rodada anterior no patrimônio."""
    if TB.motor_de(p) != TB.MOTOR_MESA or p["fase"] not in ("analise", "replay") or not p.get("apostas"):
        return
    for j, ap in p["apostas"].items():
        if TB._chave(p["rodada"], j) in (p.get("stakes") or {}):
            continue
        try:
            TCA.liquidar_seguro(p)
            a = TCA.aposta_rodada(j, ap.get("conta"))
            TB.definir_stake(p, j, p["rodada"], a["stake"], a["pat"])
        except Exception:
            pass                                                 # sem registro vale a aposta anterior (TB._stake): a partida não cai por isso


def _avancar(p: dict, agora: float) -> None:
    TB.avancar(p, agora, _cen())
    _liquidar(p)
    _stake_rodada(p)


def _formatos(tf: str) -> list[str]:
    """Formatos que existem para este timeframe (cenário que comporte as rodadas). Guardado na sessão para não consultar o banco a cada tela."""
    k = f"tb_fmts_{tf}"
    if k not in _ss():
        try:
            _ss()[k] = TD.formatos_disponiveis(tf)
        except Exception:
            _ss()[k] = [TB.FORMATO_PADRAO]
    return _ss()[k]


def _formato(tf: str) -> str:
    ok = _formatos(tf)
    f = _ss().get(f"tb_fmt_{tf}")
    return f if f in ok else (TB.FORMATO_PADRAO if TB.FORMATO_PADRAO in ok else (ok[0] if ok else TB.FORMATO_PADRAO))


def _corrida() -> str:
    f = _ss().get("tb_corrida")
    return f if f in TB.CORRIDAS else "intermediaria"


def _iniciar() -> None:
    try:
        fmt = _corrida()
        jog = _jogador()
        if not jog:                                              # o app só abre com conta; sem ela não há partida
            _ss()["tb_erro"] = "Entre na sua conta para jogar."
            return
        # só gráficos reais; o simulado fica para o administrador testar (sempre com o selo SIMULADO)
        cen = TD.escolher_corrida(fmt, int(_agora()) % 100000, permitir_demo=_admin())
        try:                                                     # capital da partida: 5% do saldo disponível (caixa livre) da Carteira
            apostas = {jog: TCA.capital_corrida(jog, (_conta() or {}).get("id"))}
        except TCA.SemSaldo as e:
            _ss()["tb_erro"] = str(e)
            return
        _ss()["tb_cen"] = TD.por_id([cen])
        _ss()["tb_p"] = TB.nova_partida(cen, cen["tf"], [jog], _agora(), apostas=apostas, corrida=fmt)
        _zerar_rascunho()
    except TB.ErroTrader as e:
        _ss()["tb_erro"] = str(e)
    except Exception:
        _ss()["tb_erro"] = "Não consegui carregar os cenários agora. Tente de novo em instantes."


def _admin() -> bool:
    try:
        import usuarios
        return bool(usuarios.pode("sistema.dados"))
    except Exception:
        return False


def _sair() -> None:
    for k in ("tb_p", "tb_cen"):
        _ss().pop(k, None)
    _zerar_rascunho()


def _fmt_t(seg: int) -> str:
    return f"{seg // 60:02d}:{seg % 60:02d}"


# ------------------------------------------------------------------ gráfico (plotly; só recebe candles já revelados)
def _ind_cfg() -> dict:
    """Lê as escolhas direto das chaves dos widgets (valores padrão constantes: o widget não é recriado a cada clique)."""
    g = _ss().get
    return {"vol": bool(g("tb_i_vol", True)), "sma": int(g("tb_i_nsma", 20)) if g("tb_i_sma", True) else 0,
            "ema": int(g("tb_i_nema", 9)) if g("tb_i_ema", False) else 0, "rsi": 14 if g("tb_i_rsi", False) else 0, "sr": bool(g("tb_i_sr", False))}


def _figura(v: dict, marcas: dict, linhas: dict | None = None, divisor: bool = False):
    """Figura do gráfico com só o que está em `v` (candles revelados). `linhas`: entrada/stop/alvo (aparecem só depois de travada a estratégia)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    cand = v["candles"]
    n = len(cand)
    cfg = _ind_cfg()
    ind = TB.indicadores(cand, cfg)
    lab = [TB.rotulo_horario(k) for k in TB.candles_sem_data(cand)]     # sem data: só dia da partida e horário
    na, total = v["n_analise"], v["total_replay"]
    linhas_h = [1.0] + ([0.22] if cfg["vol"] else []) + ([0.26] if cfg["rsi"] else [])
    fig = make_subplots(rows=len(linhas_h), cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[h / sum(linhas_h) for h in linhas_h])
    fig.add_trace(go.Candlestick(x=lab, open=[k["o"] for k in cand], high=[k["h"] for k in cand], low=[k["l"] for k in cand], close=[k["c"] for k in cand],
                                 increasing_line_color=VERDE, increasing_fillcolor=VERDE, decreasing_line_color=VERM, decreasing_fillcolor=VERM,
                                 showlegend=False, name=v["ticker"]), row=1, col=1)
    if ind["sma"]:
        fig.add_trace(go.Scatter(x=lab, y=ind["sma"], mode="lines", line=dict(color=OURO, width=1.6), name=f"SMA {cfg['sma']}", showlegend=False, hoverinfo="skip"), row=1, col=1)
    if ind["ema"]:
        fig.add_trace(go.Scatter(x=lab, y=ind["ema"], mode="lines", line=dict(color="#4DD0E1", width=1.6), name=f"EMA {cfg['ema']}", showlegend=False, hoverinfo="skip"), row=1, col=1)
    r = 2
    if cfg["vol"]:
        fig.add_trace(go.Bar(x=lab, y=[k["v"] for k in cand], marker_color=[VERDE if k["c"] >= k["o"] else VERM for k in cand], opacity=.6, showlegend=False,
                             name="Volume", hoverinfo="skip"), row=r, col=1)
        r += 1
    if cfg["rsi"] and ind["rsi"]:
        fig.add_trace(go.Scatter(x=lab, y=ind["rsi"], mode="lines", line=dict(color="#C4B5FF", width=1.5), name="RSI", showlegend=False, hoverinfo="skip"), row=r, col=1)
        for nivel in (30, 70):
            fig.add_hline(y=nivel, line=dict(color="rgba(255,255,255,.25)", width=1, dash="dot"), row=r, col=1)
        fig.update_yaxes(range=[0, 100], row=r, col=1)
    # suporte/resistência automáticos e marcações da pessoa
    for z in ind["sr"]["suportes"][:3]:
        fig.add_hline(y=z["preco"], line=dict(color="rgba(38,208,124,.7)", width=1.2, dash="dash"), row=1, col=1)
    for z in ind["sr"]["resistencias"][:3]:
        fig.add_hline(y=z["preco"], line=dict(color="rgba(255,77,109,.7)", width=1.2, dash="dash"), row=1, col=1)
    for m in marcas.get("niveis", []):
        fig.add_hline(y=m["preco"], line=dict(color="#C4B5FF", width=1.3, dash="dot"), annotation_text=m.get("rotulo") or None, annotation_position="top left",
                      annotation_font_size=10, row=1, col=1)
    x_fim = (n + 3) if v["fase"] == "analise" else (na + total + 1)        # análise: foco nos candles; replay: janela fixa que comporta todo o replay
    for t in marcas.get("tendencias", []):
        if t["i1"] < n and t["i2"] < n:
            incl = (t["p2"] - t["p1"]) / (t["i2"] - t["i1"])
            fig.add_shape(type="line", x0=t["i1"], y0=t["p1"], x1=x_fim, y1=t["p1"] + incl * (x_fim - t["i1"]), line=dict(color=OURO, width=1.5), row=1, col=1)
    for a in marcas.get("notas", []):
        if 0 <= a["i"] < n:
            fig.add_annotation(x=lab[a["i"]], y=a["preco"], text=a["texto"], showarrow=True, arrowhead=2, arrowcolor="#C4B5FF", font=dict(size=10, color="#fff"),
                               bgcolor="rgba(60,44,150,.85)", row=1, col=1)
    for nome, cor in (("entrada", AZUL), ("stop", VERM), ("alvo", VERDE)):
        if linhas and linhas.get(nome):
            fig.add_hline(y=linhas[nome], line=dict(color=cor, width=1.6), annotation_text=nome.capitalize(), annotation_position="bottom right",
                          annotation_font_size=10, row=1, col=1)
    if divisor and na - 1 < n:
        fig.add_vline(x=lab[na - 1], line=dict(color="rgba(255,255,255,.4)", width=1, dash="dot"), row="all", col=1)
    fig.update_xaxes(type="category", rangeslider_visible=False, showgrid=False, tickfont=dict(size=9, color="#9E96CE"), nticks=5, categoryorder="trace",
                     range=[max(-0.5, na - 45), x_fim], showspikes=False)
    fig.update_yaxes(side="right", gridcolor="rgba(255,255,255,.06)", tickfont=dict(size=10, color="#CFC8EE"), zeroline=False)
    fig.update_layout(margin=dict(l=2, r=2, t=4, b=2), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(10,7,32,.85)", dragmode="pan", hovermode="x",
                      font=dict(color="#CFC8EE"), uirevision=f"tb-{v['rodada']}-{v['tf']}", height=300 + (50 if cfg["vol"] else 0) + (70 if cfg["rsi"] else 0), showlegend=False)
    return fig


def _grafico(v: dict, marcas: dict, linhas: dict | None = None, divisor: bool = False, chave: str = "tb_graf") -> None:
    try:
        fig = _figura(v, marcas, linhas, divisor)
    except Exception as e:
        st.markdown(f"<div class='tb-er'>Não consegui montar o gráfico agora ({_e(e.__class__.__name__)}).</div>", unsafe_allow_html=True)
        return
    st.markdown("<div class='tb-graf'>", unsafe_allow_html=True)
    mexe = bool(_ss().get("tb_i_mov", True))
    st.plotly_chart(fig, width="stretch", theme=None, key=chave,
                    config={"scrollZoom": mexe, "staticPlot": not mexe, "displaylogo": False, "responsive": True,
                            "modeBarButtonsToAdd": ["drawline", "drawrect", "eraseshape"], "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]})
    st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ partes comuns
def _topo(v: dict, seg: int | None = None, rotulo: str = "") -> str:
    preco = v["candles"][-1]["c"]
    medalha = CT.img(f"rodada_{v['rodada']}", alt="") if 1 <= v["rodada"] <= 3 else f"<span class='tb-rn'>{v['rodada']}</span>"   # só há medalha pronta para as rodadas 1 a 3
    demo = "<span class='tb-pill'>SIMULADO</span>" if v["demo"] else ""
    rel = f"<div class='tb-rel{' fim' if (seg is not None and seg <= 10) else ''}'>{_fmt_t(seg)}</div>" if seg is not None else "<div></div>"
    return (f"<div class='tb-top'><div class='tk'>{_e(v['ticker'])}{demo}<small>R$ {preco:.2f} · {_e(TB.TIMEFRAMES[v['tf']]['nome'])}{(' · ' + _e(rotulo)) if rotulo else ''}</small></div>"
            f"<div class='tb-rod'>{medalha}Rodada {v['rodada']}/{v['rodadas']}</div>{rel}</div>")


def _saiu(est: dict, saida) -> None:
    """O Voltar agora fica dentro do cabeçalho do componente: quando ele pedir, a tela sai como o botão antigo saía."""
    if est.pop("voltar", None):
        saida()
        if est.pop("ranking", None):                  # botão Ranking da faixa de baixo: depois de sair, abre a tela de Ranking
            _ss()["rk_aba"] = "trade"
            _ss()["_nav_pend"] = "jogos-ranking"
        st.rerun(scope="app")


def _voltar() -> None:
    st.button("Voltar", key="tb_voltar", icon=":material/arrow_back:", on_click=_sair)


# ------------------------------------------------------------------ MULTIPLAYER · salas (o estado da partida vive no banco, não na sessão)
def _email_online() -> str | None:
    """Identidade validada pelo servidor (sessão de login). Sem login não há sala."""
    try:
        import usuarios
        return (usuarios.usuario() or {}).get("email") or None
    except Exception:
        return None


def _msg_online(e: Exception) -> str:
    return str(e) if isinstance(e, (TOD.ErroSala, TB.ErroTrader)) else "Servidor de salas indisponível agora. Confira se as tabelas do Trade Battle foram criadas no banco."


def _on_criar() -> None:
    em = _email_online()
    try:
        _ss()["tb_on_pid"] = TOD.criar_sala(em, TB.CORRIDAS[_corrida()]["tf"], _agora(), corrida=_corrida())["id"]
    except Exception as e:
        _ss()["tb_erro"] = _msg_online(e)


def _on_entrar() -> None:
    em = _email_online()
    try:
        _ss()["tb_on_pid"] = TOD.entrar_na_sala(em, _ss().get("tb_on_cod") or "", _agora())["id"]
    except Exception as e:
        _ss()["tb_erro"] = _msg_online(e)


def _on_voltar_partida(pid: str) -> None:
    _ss()["tb_on_pid"] = pid


def _on_desanexar() -> None:
    _ss().pop("tb_on_pid", None)


def _on_sair_sala(pid: str) -> None:
    try:
        TOD.sair(pid, _email_online(), _agora())
    except Exception:
        pass
    _ss().pop("tb_on_pid", None)


def _on_iniciar(pid: str) -> None:
    try:
        TOD.iniciar(pid, _email_online(), _agora())
    except Exception as e:
        _ss()["tb_erro"] = _msg_online(e)


def _rot_formato(f: str | None, corrida: str | None = None) -> str:
    if corrida in TB.CORRIDAS:
        return f"{TB.ROTULO_CORRIDA[corrida]} · partida corrida"
    return f"{TB.ROTULO_FORMATO[f]} · {TB.FORMATOS[f]} rodadas" if f in TB.FORMATOS else "regras anteriores · 10 rodadas"


def _painel(nome: str) -> None:
    _ss()["tb_painel"] = None if _ss().get("tb_painel") == nome else nome


def _central_online(painel: str | None) -> None:
    """Painel aberto pelos cards 'Jogar com Amigos' (criar sala) e 'Entrar em uma Sala' (código). Sala exige conta."""
    if not painel:
        return
    with st.container(key="tb_painel"):
        if painel == "amigos":
            st.markdown("<div class='tb-cap'>Crie a sala e passe o código para 1 a 3 amigos. Todos veem o mesmo gráfico, o mesmo relógio e a mesma rodada.</div>",
                        unsafe_allow_html=True)
            st.button("Criar sala", key="tb_on_criar", icon=":material/group_add:", width="stretch", on_click=_on_criar)
        else:
            st.text_input("Código da sala", key="tb_on_cod", max_chars=8, placeholder="Código de 6 letras/números", label_visibility="collapsed")
            st.button("Entrar com código", key="tb_on_entrar", icon=":material/vpn_key:", width="stretch", on_click=_on_entrar)


@st.fragment(run_every=2)
def _frag_sala(pid: str) -> None:
    em = _email_online()
    try:
        b = TOD.ler(pid, em, _agora())
    except Exception as e:
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = _msg_online(e)
        return st.rerun()
    if b["estado"] != "sala":
        return st.rerun()                                        # a partida começou (ou a sala foi cancelada): tela inteira muda
    sa = b["sala"]
    import amigos_app as AMA
    import perfis_app as PA

    def _av_sala(j):                                              # avatar equipado de quem está na sala (com a moldura da raridade)
        try:
            if j["voce"]:
                m = PA.meu_avatar()
                return PA.avatar_html(m["id"], m["foto"], 30)
            return AMA.avatar_por_apelido(j["nick"], 30) or f"<img src='{MN.uri('rosto')}' alt='' style='width:30px;height:30px;border-radius:50%'>"
        except Exception:
            return ""
    cards = "".join(f"<div class='tb-lin'><span class='tb-lin-n'>{_av_sala(j)}{_e(AMA.nome_exibicao(j['nick']) if not j['voce'] else (PA.meu_perfil() or {}).get('nome') or j['nick'])}{' (você)' if j['voce'] else ''}</span>"
                    f"<span>{'criador' if j['criador'] else 'jogador'}</span></div>" for j in sa["jogadores"])
    st.markdown(f"<div class='tb-pts'><div class='n'>{_e(sa['codigo'])}</div><small>código da sala · {_e(TB.TIMEFRAMES[sa['tf']]['nome'])} · {_e(_rot_formato(sa.get('formato'), sa.get('corrida')))}</small></div>"
                f"<div class='tb-card'><b>Jogadores {sa['n']}/{sa['max']}</b>{cards}</div>", unsafe_allow_html=True)
    import amigos_app as AMA
    for i, j in enumerate(x for x in sa["jogadores"] if not x["voce"]):
        AMA.botao_perfil(f"tb_sala_{i}", j["nick"])
    if sa["criador"]:
        st.button("Iniciar partida", key="tb_on_iniciar", icon=":material/play_arrow:", width="stretch", disabled=sa["n"] < sa["min"], on_click=_on_iniciar, args=(pid,))
        if sa["n"] < sa["min"]:
            st.markdown("<div class='tb-cap'>Aguardando pelo menos mais 1 jogador para começar.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='tb-cap'>Aguardando o criador iniciar a partida…</div>", unsafe_allow_html=True)


@st.fragment(run_every=1)
def _frag_mesa_online(pid: str) -> None:
    """Mesmo gráfico contínuo do modo individual, mas o estado vem do banco: cada segundo o servidor entrega a esta sessão só o que ela pode ver."""
    em, ag = _email_online(), _agora()
    try:
        b = TOD.ler(pid, em, ag)
    except Exception as e:
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = _msg_online(e)
        return st.rerun()
    if b["estado"] != "jogo" or b["p"]["fase"] == "fim":
        return st.rerun()
    v, p = b["v"], b["p"]
    est = _ss().setdefault(f"tb_ev_{pid}", {})
    try:
        val = TG.mesa(f"tb_mesa_{pid}", **_args(v, p, est, ag))
    except Exception:
        _ss()["tb_erro"] = "O gráfico não carregou neste navegador."
        _ss().pop("tb_on_pid", None)
        return st.rerun()
    if TG.processar(p, val, est, em, v["candles"][-1]["c"], ag, TOD.Ops(pid, em)):
        _saiu(est, _on_desanexar)
        return st.rerun(scope="fragment")


def _cartao_fin(fin: dict | None, corrida_fin: bool = False) -> str:
    """Cartão do dinheiro da partida: quanto os trades renderam (ou custaram) em T$ e em %, somando as rodadas. Vazio para quem jogou sem aposta."""
    if not fin:
        return ""
    import wallet_game as WG
    pnl = fin["pnl"]
    cor = "up" if pnl > 0 else ("down" if pnl < 0 else "zero")
    sg = TG._sinal(pnl)
    corrida = len(fin["rodadas"]) <= 1 and corrida_fin
    por_rod = "" if corrida else "".join(f"<div class='tb-lin'>Rodada {k + 1}<span class='{'up' if x > 0 else ('down' if x < 0 else '')}'>{TG._sinal(x)}{_e(WG.moeda(abs(x)))}</span></div>" for k, x in enumerate(fin["rodadas"]))
    base = f"sobre o capital de {_e(WG.moeda(fin['aposta']))} (5% do saldo disponível)" if corrida else f"sobre a aposta de {_e(WG.moeda(fin['aposta']))}"
    return (f"<div class='tb-card tb-fin {cor}'><div class='t'>Quanto seus trades renderam</div>"
            f"<div class='v'>{sg}{_e(WG.moeda(abs(pnl)))}</div>"
            f"<div class='s'>{sg}{TG._pc(fin['pct_aposta'])}% {base} · {sg}{TG._pc(fin['pct_pat'], 3)}% do patrimônio</div>"
            f"{por_rod}<small>Já somado ao seu patrimônio na carteira.</small></div>")


_RX_ICONE = (("Sua leitura", "🧭"), ("Estratégia", "🧭"), ("O mercado", "📈"), ("Opera", "💱"), ("Limite", "🛑"), ("Resultado", "🧮"), ("Qualidade", "⭐"), ("Pontos", "🏆"))


def _raiox_html(linhas: list) -> str:
    """Raio-X no padrão do app: um mini-cartão por item, com ícone, título e explicação (mesmo visual do cartão da rodada)."""
    out = []
    for titulo, txt in linhas:
        ic = next((i for k, i in _RX_ICONE if str(titulo).startswith(k)), "•")
        cls = " al" if str(titulo).startswith("Limite") else (" pt" if str(titulo).startswith("Pontos") else "")
        out.append(f"<div class='tb-ri{cls}'><span class='ic'>{ic}</span><div><b>{_e(titulo)}</b><p>{_e(txt)}</p></div></div>")
    return "".join(out)


def _sg(x: float) -> str:
    return "+" if x > 0 else ("−" if x < 0 else "")


def _pagar_xp(pid: str, info: dict) -> dict:
    """Credita o XP da partida no progresso de estudo da conta (mesmo XP da Jornada e das missões da Wallet Game), UMA vez por partida
    e só nas XP_PARTIDAS_DIA primeiras do dia. Nunca TickerCoins. Falha aqui nunca derruba a tela."""
    n = int((info or {}).get("xp") or 0)
    try:
        import usuarios
        if not usuarios.usuario():
            return {"xp": 0, "status": "erro"}
        import educacao_app as EA
        import jornada as JO
        p = dict(EA.prog())
        tx = dict(p.get("trader_xp") or {})
        if pid in tx:
            return {"xp": tx[pid]["xp"], "status": "pago"}
        if n <= 0:
            return {"xp": 0, "status": "zero"}
        hoje = JO.hoje().isoformat()
        if sum(1 for v in tx.values() if v.get("d") == hoje) >= TB.XP_PARTIDAS_DIA:
            return {"xp": 0, "status": "limite"}
        j = JO.normalizar_jornada(p.get("jornada"))
        j["xp"] += n
        j["xp_dia"][hoje] = int(j["xp_dia"].get(hoje, 0)) + n
        tx[pid] = {"d": hoje, "xp": n}
        p["jornada"], p["trader_xp"] = j, tx
        EA._set(p)
        return {"xp": n, "status": "pago"}
    except Exception:
        return {"xp": 0, "status": "erro"}


def _linha_xp(info: dict, pago: dict) -> str:
    st_, n = pago.get("status"), pago.get("xp", 0)
    if st_ == "pago" and n:
        onde = f"{info['pos']}º lugar entre {info['n']} jogadores" if info.get("pos") else "partida concluída"
        if info.get("xp_pts"):
            onde += f" ({info['xp_pos']} XP) + {info['xp_pts']} XP pela pontuação"
        return f"<div class='tb-xp'><span>⭐</span><b>+{n} XP</b><small>{onde}</small></div>"
    txt = {"limite": f"Você já ganhou XP em {TB.XP_PARTIDAS_DIA} partidas hoje: esta partida não deu XP.",
           "zero": "Sem XP: você não registrou a leitura em nenhuma rodada."}.get(st_)
    return f"<div class='tb-xp n'><span>⭐</span><small>{txt}</small></div>" if txt else ""


def _moldura() -> str | None:
    """Cor da moldura que a pessoa equipou na Loja Ticker (aro do avatar no placar). Sem login/sem item: None (aro padrão)."""
    try:
        import loja_aparencia as LA
        cor = (LA.efeito("moldura") or {}).get("cor")
        return cor if isinstance(cor, str) and len(cor) <= 9 and cor.startswith("#") else None
    except Exception:
        return None


def _args(v: dict, p: dict, est: dict, agora: float) -> dict:
    """Argumentos do componente da mesa + a moldura da conta (lida aqui, na tela, e não na montagem pura dos dados)."""
    a = TG.args_mesa(v, p, est, agora)
    if a.get("motor") == TB.MOTOR_MESA:
        a["moldura"] = _moldura()
        a["avatares"] = _avatares_assentos(p)
    return a


def _avatares_assentos(p: dict) -> dict:
    """{rótulo do placar ("Você", "Jogador N"): {src, cor}}: o avatar equipado de cada assento, com a cor da raridade. Montado no servidor
    a partir dos jogadores da partida; só imagem e cor vão para a tela (nunca o e-mail). Falha: {} (a mesa volta ao rosto do mascote por assento)."""
    try:
        import avatares as AV
        import perfis_app as PA
        em = _email_online()
        jogs = list(p.get("jogadores") or [])
        out = {}
        for n, j in enumerate(jogs, 1):
            eu = j == em or len(jogs) == 1
            if eu:
                m = PA.meu_avatar()
                av, foto = m["id"], m["foto"]
            elif "@" in str(j):
                av, foto = PA.avatar_de_email(j)
            else:
                continue
            if not foto and av == AV.PADRAO:                              # sem avatar escolhido: o rosto do mascote (não a raposa)
                out["Você" if eu else f"Jogador {n}"] = {"src": MN.uri("rosto"), "cor": "#34E85E"}
                continue
            src = foto or AV.url(av, True)
            src = src if src.startswith("data:") else "/" + src           # a mesa roda num iframe: endereço absoluto
            out["Você" if eu else f"Jogador {n}"] = {"src": src, "cor": "#34E85E" if foto else AV.RARIDADES[AV.raridade_de(av)]["cor"]}
        return out
    except Exception:
        return {}


_AV_COR = {1: "hue-rotate(185deg) saturate(1.2)", 2: "hue-rotate(95deg)", 3: "hue-rotate(260deg)", 4: "hue-rotate(320deg) saturate(1.3)"}   # igual ao placar da mesa


def _avatar_placar(x: dict) -> str:
    """Avatar no placar final: o equipado de cada assento (Coleção de Avatares); sem ele, o rosto do mascote por assento."""
    import re
    m = (_ss().get("tb_av_assentos") or {}).get(x["rotulo"])
    if m:
        return f"<span class='tb-av' style='box-shadow:0 0 0 2px {m['cor']},0 0 8px {m['cor']}'><img src='{m['src'].lstrip('/') if not m['src'].startswith('data:') else m['src']}' alt=''></span>"
    if x["voce"]:
        aro = _moldura() or "#34E85E"
        return f"<span class='tb-av' style='box-shadow:0 0 0 2px {aro},0 0 8px {aro}'><img src='{MN.uri('rosto')}' alt=''></span>"
    n = int((re.search(r"\d+", x["rotulo"]) or [0])[0] or 0)
    return f"<span class='tb-av'><img src='{MN.uri('rosto')}' alt='' style='filter:{_AV_COR.get(n, _AV_COR[1])}'></span>"


def _html_revelacao(rv: dict | None) -> str:
    """Partida corrida: qual era o ativo escondido e de quando eram os candles."""
    if not rv:
        return ""
    sim = " (cenário simulado)" if rv.get("demo") else ""
    return (f"<div class='tb-rev'><small>🔎 O ativo da partida era</small><b>{_e(rv['ticker'])}</b>"
            f"<span>{_e(rv['tf_nome'])} · de {_e(rv['de'])} a {_e(rv['ate'])}{sim}</span></div>")


def _tela_final(fz: dict, fin: dict | None, demo: bool, tickers: list[str], pago: dict | None = None, revelado: dict | None = None) -> None:
    """Fim da partida (visual de 'fim de rodada' da referência, nas cores do app): lugar, pontuação e retorno, placar da batalha,
    pontos por rodada, dinheiro da partida e a análise completa (Raio-X de cada rodada). `fz` = TB.resumo_final (já rotulado, sem e-mail)."""
    import wallet_game as WG
    pl, n_rod = fz["placar"], len(fz["rodadas"])
    meu = next(x for x in pl if x["voce"])
    multi = len(pl) > 1
    ret = fin["pct_aposta"] if fin and fin.get("pct_aposta") is not None else meu["ret_pct"]
    pts = meu["pontos"]
    if multi and meu["pos"] == 1:
        lg, troph = "<div class='tb-fim-lg'>👑 Você ficou em<b>1º lugar!</b></div>", True
    elif multi:
        lg, troph = f"<div class='tb-fim-lg n'>Você ficou em<b>{meu['pos']}º lugar</b><small>Continue evoluindo e conquiste novas vitórias!</small></div>", False
    elif pts > 0:
        lg, troph = "<div class='tb-fim-lg'>Partida concluída<b>Mandou bem!</b></div>", True
    else:
        lg, troph = "<div class='tb-fim-lg n'>Partida concluída<b>Bora treinar!</b><small>Veja o Raio-X de cada rodada e tente de novo.</small></div>", False
    img = f"<img src='{ART.uri('trofeu')}' alt=''>" if troph else ""
    topo = f"<div class='tb-fim-h'>{img}{lg}</div>"
    cor_r = "zero" if not ret else ("up" if ret > 0 else "down")
    ret_html = (f"<div class='bx rt {cor_r}'><small>📈 Retorno</small><b>{_sg(ret)}{TG._pc(ret)}%</b>"
                f"<i>{(_sg(fin['pnl']) + _e(WG.moeda(abs(fin['pnl']))) + ' · ') if fin else ''}da aposta</i></div>") if ret is not None else ""
    em_rod = "na partida" if revelado else f"em {n_rod} rodadas"
    if revelado:
        ret_html = ret_html.replace("da aposta</i>", "do capital</i>")
    stats = (f"<div class='tb-st'><div class='bx {'pos' if pts > 0 else ('neg' if pts < 0 else '')}'><small>⭐ Pontuação</small><b>{_sg(pts)}{TG._pc(pts, 1)}</b>"
             f"<i>{em_rod}{' · simulado' if demo else ''}</i></div>{ret_html}</div>")
    placar = ""
    if multi:
        lin = "".join(f"<div class='tb-pr p{x['pos']}{' eu' if x['voce'] else ''}'><span class='rk'>{x['pos']}º</span><span class='nm'>{_avatar_placar(x)}{_e(x['rotulo'])}</span>"
                      f"<b>{_sg(x['pontos'])}{TG._pc(x['pontos'], 1)}</b>"
                      + ("<em class='zero'>—</em>" if x["ret_pct"] is None else f"<em class='{'up' if x['ret_pct'] > 0 else ('down' if x['ret_pct'] < 0 else 'zero')}'>{_sg(x['ret_pct'])}{TG._pc(x['ret_pct'])}%</em>")
                      + "</div>" for x in pl)
        placar = f"<div class='tb-pl'><div class='h'>🏆 Placar da Batalha</div>{lin}</div>"
    rods = "".join(f"<div class='tb-lin'>Rodada {k} · {_e(tickers[k - 1] if k - 1 < len(tickers) else '')}<span class='{'down' if r < 0 else ''}'>{_sg(r)}{TG._pc(r, 1)}</span></div>"
                   for k, r in enumerate(fz["rodadas"], 1))
    xp = _linha_xp(fz.get("xp") or {}, pago or {})
    rods_html = "" if revelado else f"<div class='tb-card'>{rods}</div>"
    st.markdown(f"<div class='tb-fim-t'>FIM DE PARTIDA!</div>{topo}{_html_revelacao(revelado)}{stats}{xp}{placar}{rods_html}{_cartao_fin(fin, bool(revelado))}"
                "<style>html body .stApp .tb-rev{display:flex;flex-direction:column;align-items:center;gap:2px;margin:6px 0;padding:10px;border-radius:16px;"
                "border:1.5px solid #F2B84B;background:linear-gradient(160deg,rgba(242,184,75,.18),#150F55)}"
                "html body .stApp .tb-rev small{color:#FFE3A3 !important;font-weight:800}html body .stApp .tb-rev b{font-size:1.6rem;font-weight:900;color:#fff !important}"
                "html body .stApp .tb-rev span{color:#D9D4F7 !important;font-size:.82rem;font-weight:700}</style>", unsafe_allow_html=True)
    with st.expander("Ver análise completa", icon=":material/insights:"):
        for k, linhas in fz["raiox"]:
            st.markdown(("" if revelado else f"<div class='tb-rx-r'>Rodada {k}</div>") + _raiox_html(linhas), unsafe_allow_html=True)


@st.dialog("📊 Relatório da partida")
def _dialogo_relatorio(res: dict, revelado: dict | None, xp_txt: str) -> None:
    """Pop-up do fim da partida corrida: cabe na tela sem rolar (as informações ficam em abas)."""
    import trader_relatorio as TR
    st.markdown(TR.CSS, unsafe_allow_html=True)
    a1, a2, a3 = st.tabs(["Resumo", "Operações", "Raio-X"])
    with a1:
        st.markdown(TR.html_resumo(res, revelado, xp_txt), unsafe_allow_html=True)
    with a2:
        st.markdown(TR.html_operacoes(res), unsafe_allow_html=True)
    with a3:
        st.markdown(TR.html_raiox(TB.explicar_mesa(res)), unsafe_allow_html=True)


def _res_jogador(p: dict, jog: str | None, v: dict | None = None) -> dict | None:
    """Resultado do jogador na partida corrida. Na sala online a tela só recebe a visão dele (v["resultado"]); no individual, a partida inteira."""
    if v is not None and v.get("resultado"):
        return v["resultado"]
    return (p.get("resultados") or {}).get(TB._chave(1, jog)) if jog else None


def _relatorio(p: dict, jog: str | None, revelado: dict | None, xp: dict | None, v: dict | None = None) -> None:
    """Partida corrida terminada: abre o relatório sozinho UMA vez e deixa o botão para abrir de novo."""
    if not (TB.qtd_de(p) and jog):
        return
    res = _res_jogador(p, jog, v)
    if not res:
        return
    xp_txt = f"⭐ +{int(xp.get('xp') or 0)} XP nesta partida" if xp and xp.get("xp") else ""
    abrir = st.button("📊 Ver relatório da partida", key="tb_rel_ver", width="stretch")
    if abrir or _ss().get("tb_rel_aberto") != p["id"]:
        _ss()["tb_rel_aberto"] = p["id"]
        _dialogo_relatorio(res, revelado, xp_txt)


def _registrar_ranking(pid: str, fz: dict, p: dict, jog: str | None = None, v: dict | None = None) -> None:
    """Partida terminada entra no placar da Central de Jogos (pontos e colocação calculados aqui, no servidor)."""
    try:
        import jogos_app
        meu = next(x for x in fz["placar"] if x["voce"])
        n = len(fz["placar"])
        extra = {}
        if TB.qtd_de(p) and jog:                              # partida corrida: lucro (T$), retorno (% do capital) e nota de qualidade para o Ranking
            res = _res_jogador(p, jog, v) or {}
            fin = res.get("fin") or {}
            extra = {"lucro": fin.get("pnl"), "retorno": fin.get("pct_aposta"), "qualidade": res.get("qualidade_nota")}
            if extra["lucro"] is None or extra["retorno"] is None:
                extra.update(lucro=None, retorno=None)
        jogos_app.registrar_trade(pid, meu["pontos"], len(fz["rodadas"]), TB.cfg_de(p).get("formato") or "", meu["pos"] if n > 1 else None, n, **extra)
    except Exception:
        pass


def _fim_online(b: dict) -> None:
    v = b["v"]
    _ss()["tb_av_assentos"] = _avatares_assentos(b["p"])
    _registrar_ranking(b["p"]["id"], v["final"], b["p"], _email_online(), v)
    _tela_final(v["final"], v.get("fin_total"), v["demo"], [v["ticker"]] * v["rodadas"], _pagar_xp(b["p"]["id"], v["final"]["xp"]), v.get("revelado"))
    _relatorio(b["p"], _email_online(), v.get("revelado"), v["final"].get("xp"), v)
    st.markdown("<div class='tb-fim-rod'>Continue evoluindo e conquiste novas vitórias!</div>", unsafe_allow_html=True)
    try:                                          # quem jogou na sala: botão para o perfil de cada um (o placar mostra "Jogador N")
        import amigos_app as AMA
        em = _email_online()
        sala = (((TOD._row(b["p"]["id"]) or {}).get("dados") or {}).get("sala") or {})
        outros = [j for j in sala.get("jogadores") or [] if j.get("email") != em]
        if outros:
            st.markdown("<div class='tb-cap'>Quem jogou com você</div>", unsafe_allow_html=True)
        for i, j in enumerate(outros):
            AMA.botao_perfil(f"tb_fim_{i}", str(j.get("nick") or ""))
    except Exception:
        pass
    st.button("Voltar ao início do Trade Battle", key="tb_voltar", icon=":material/home:", width="stretch", on_click=_on_desanexar)


def _pagina_online(pid: str) -> None:
    em = _email_online()
    try:
        b = TOD.ler(pid, em, _agora())
    except Exception as e:
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = _msg_online(e)
        return st.rerun()
    if b["estado"] == "cancelada":
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = "A sala foi cancelada."
        return st.rerun()
    if b["estado"] == "sala":
        st.markdown(f"<div class='tb-hero'><img src='{ART.uri('hero')}' alt='Trade Battle'></div>", unsafe_allow_html=True)
        _frag_sala(pid)
        st.button("Sair da sala", key="tb_voltar", icon=":material/logout:", width="stretch", on_click=_on_sair_sala, args=(pid,))
        return
    if b["p"]["fase"] == "fim":
        return _fim_online(b)
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    _frag_mesa_online(pid)


# ------------------------------------------------------------------ TELA 1 · Central
def _n_reais(tf: str) -> int:
    k = f"tb_nreais_{tf}"
    if k not in _ss():
        try:
            _ss()[k] = len(TD.listar(tf))
        except Exception:
            _ss()[k] = 0
    return _ss()[k]


def _preparar_reais(tf: str, b24: bool = False) -> None:
    import analise_tecnica_app as ATA
    from datetime import datetime
    try:
        rel = TD.preparar(tf, lambda cod, per, iv: ATA._baixar(cod, per, "60m" if iv == "1h" else iv), datetime.now().isoformat(timespec="minutes"), b24=b24)
        _ss()["tb_prep"] = rel
        _ss().pop(f"tb_nreais_{tf}", None)
        _ss().pop(f"tb_fmts_{tf}", None)
    except Exception as e:
        _ss()["tb_prep"] = {"erro": f"{e.__class__.__name__}"}


_ICONE_FMT = {"rapida": ":material/bolt:", "normal": ":material/timer:", "longa": ":material/emoji_events:"}
_ICONE_CORRIDA = {"rapida": ":material/bolt:", "intermediaria": ":material/timer:", "longa": ":material/emoji_events:"}


def _min_corrida(f: str) -> int:
    """Duração aproximada da partida corrida (análise + replay), para o cartão não prometer menos do que o jogo dura."""
    return round((TB.T_ANALISE_S + TB.CORRIDAS[f]["n_replay"] * TB.SEG_POR_CANDLE) / 60)


def _escolher_corrida(f: str) -> None:
    _ss()["tb_corrida"] = f


def _n_reais_corrida(f: str) -> int:
    k = f"tb_nreais_c_{f}"
    if k not in _ss():
        try:
            _ss()[k] = len(TD.listar_corrida(f))
        except Exception:
            _ss()[k] = 0
    return _ss()[k]


def _preparar_corrida(f: str) -> None:
    import analise_tecnica_app as ATA
    from datetime import datetime
    try:
        _ss()["tb_prep"] = TD.preparar_corrida(f, lambda cod, per, iv: ATA._baixar(cod, per, iv), datetime.now().isoformat(timespec="minutes"))
        _ss().pop(f"tb_nreais_c_{f}", None)
    except Exception as e:
        _ss()["tb_prep"] = {"erro": f"{e.__class__.__name__}"}


def _min_formato(f: str) -> int:
    """Duração máxima aproximada da partida (análise + replay de cada rodada), para o card não prometer menos do que o jogo dura."""
    return round(TB.FORMATOS[f] * (TB.T_ANALISE_S + TB.T_REPLAY_MESA_S) / 60)


def _escolher_formato(tf: str, f: str) -> None:
    _ss()[f"tb_fmt_{tf}"] = f


def _central() -> None:
    st.markdown(_CSS_CENTRAL, unsafe_allow_html=True)
    try:
        import jogos_app
        jogos_app.navegacao("trader")
    except Exception:
        pass
    st.markdown(f"<div class='tb-hero'><img src='{ART.uri('hero')}' alt='Trade Battle'></div>", unsafe_allow_html=True)
    atual = _corrida()
    st.markdown("<div class='tb-sec'><span>🕒</span>Escolha a duração da partida</div>", unsafe_allow_html=True)
    with st.container(key="tb_fmts"):                               # grade própria (3 lado a lado no celular): a regra global quebra linhas de 3 colunas
        for f in TB.CORRIDAS:
            st.button(TB.ROTULO_CORRIDA[f], key=f"tb_fmtb_{f}", icon=_ICONE_CORRIDA[f], width="stretch",
                      type="primary" if f == atual else "secondary", on_click=_escolher_corrida, args=(f,))
    st.markdown("<style>" + "".join(f"{_P} .st-key-tb_fmtb_{f} button p::after{{content:'Gráfico de {TB.TIMEFRAMES[TB.CORRIDAS[f]['tf']]['nome']}\\A~{_min_corrida(f)} min'}}"
                                    for f in TB.CORRIDAS) + "</style>", unsafe_allow_html=True)
    if _n_reais_corrida(atual) < 1:
        extra = " Como administrador, você pode testar com um gráfico simulado (marcado como SIMULADO)." if _admin() else " Tente outra duração ou volte mais tarde."
        st.markdown(f"<div class='tb-demo2'><div><b><span>i</span>Gráficos em preparação</b><p>Os gráficos reais desta duração ainda estão sendo preparados.{extra}</p></div>"
                    f"<img src='{MN.uri('apontando')}' alt=''></div>", unsafe_allow_html=True)
    em = _email_online()
    try:
        ativa = TOD.partida_ativa(em) if em else None
    except Exception:
        ativa = None
    painel = _ss().get("tb_painel")
    with st.container(key="tb_modos"):
        c1, c2 = st.columns(2)
        with c1:
            st.button("Jogar Solo", key="tb_jogar", icon=":material/trending_up:", width="stretch", on_click=_iniciar)
        with c2:
            st.button("Jogar com Amigos", key="tb_amigos", icon=":material/groups:", width="stretch",
                      on_click=(_on_voltar_partida if ativa else _painel), args=((ativa,) if ativa else ("amigos",)))
    st.button("Voltar para sua sala/partida" if ativa else "Entrar em uma Sala", key="tb_sala_row", icon=":material/login:", width="stretch",
              on_click=(_on_voltar_partida if ativa else _painel), args=((ativa,) if ativa else ("entrar",)))
    _central_online(None if ativa else painel)
    try:
        import jogos_app
        jogos_app.faixa_jogo("trade")                         # ranking, posição e histórico da Central de Jogos
    except Exception:
        pass
    st.markdown("<div class='tb-sobre'><div class='h'>⭐ Sobre o Trade Battle</div><div class='g'>"
                "<div><i>👥</i><b>2-4</b><small>jogadores</small></div>"
                "<div><i>📊</i><b>15m · 1h · 1D</b><small>gráficos reais</small></div>"
                "<div><i>💰</i><b>5%</b><small>do saldo disponível</small></div>"
                "<div><i>🏆</i><b>XP</b><small>por colocação</small></div></div></div>", unsafe_allow_html=True)
    if _ss().get("tb_erro"):
        st.markdown(f"<div class='tb-er'>{_e(_ss().pop('tb_erro'))}</div>", unsafe_allow_html=True)
    with st.expander("Como funciona", icon=":material/help:"):
        st.markdown("<div class='tb-aviso'>Você recebe o gráfico de uma ação real da B3, parado num ponto do passado, sem o nome do ativo nem a data "
                    "(eles aparecem só no fim, para ninguém pesquisar o que aconteceu depois). Escolha a duração: <b>Rápida</b> usa candles de 15 minutos, "
                    "<b>Intermediária</b> de 1 hora e <b>Longa</b> de 1 dia. Cada candle se forma na sua frente com os candles menores reais daquele dia "
                    "(5 minutos, ou 1 hora no gráfico diário): dá para entrar no meio do candle, no preço que estava valendo. Você tem 120 s para analisar e registrar a sua leitura (direção, tipo e confiança); "
                    "depois o gráfico anda numa partida corrida, sem rodadas, e você opera ao vivo como num home broker: compra e vende a quantidade "
                    "de ações que quiser, aumenta ou reduz a posição, usa ordem a mercado, limite ou stop de entrada, e coloca stop e alvo. "
                    "<b>Capital:</b> a partida usa 5% do saldo disponível (caixa livre) da sua Carteira. O valor aplicado ao mesmo tempo nunca passa disso: "
                    "chegou ao teto, encerre ou reduza a posição para entrar de novo. A perda máxima é esse capital. "
                    "<b>Execução honesta:</b> a ordem a mercado executa no próximo preço real (a abertura do candle menor seguinte); stop e alvo são conferidos na ordem em que os preços "
                    "aconteceram e executam no preço ou, se o preço saltar além dele, no preço do salto; "
                    "cada execução paga a taxa da B3 (cerca de 0,03%). No fim, o resultado (lucro ou prejuízo) volta para a sua Carteira. "
                    f"Você ganha XP pela colocação e pela pontuação positiva (até {TB.XP_PARTIDAS_DIA} partidas por dia). Jogo educativo: nenhuma ordem real, nada de recomendação de investimento. "
                    "No modo individual a partida fica só neste navegador; em sala com amigos (2 a 4 jogadores) ela fica guardada no servidor.</div>", unsafe_allow_html=True)
    try:
        import usuarios
        admin = usuarios.pode("sistema.dados")
    except Exception:
        admin = False
    if admin:
        with st.expander("Preparar cenários reais (administração)", icon=":material/database:"):
            st.caption("Baixa o histórico gratuito UMA vez, valida candle a candle e guarda no banco. As partidas só leem o que já está guardado.")
            for f in TB.CORRIDAS:
                st.button(f"Preparar {TB.ROTULO_CORRIDA[f]} (gráfico de {TB.TIMEFRAMES[TB.CORRIDAS[f]['tf']]['nome']}) · {_n_reais_corrida(f)} guardados",
                          key=f"tb_prep_c_{f}", on_click=_preparar_corrida, args=(f,), width="stretch")
            st.caption("Os candles de 5 minutos só existem para os últimos 60 dias (limite gratuito). O workflow diário (trader_cenarios_job.py) prepara sozinho "
                       "depois do pregão e guarda tudo no banco: a biblioteca cresce todo dia.")
            rel = _ss().get("tb_prep")
            if rel:
                if rel.get("erro"):
                    st.markdown(f"<div class='tb-er'>Falhou ({_e(str(rel['erro']))}).</div>", unsafe_allow_html=True)
                else:
                    falhas = rel.get("falhas") or {}
                    st.markdown(f"<div class='tb-ok'>{rel.get('novos', 0)} cenário(s) novo(s) · {rel.get('total', 0)} guardado(s) · {len(falhas)} ativo(s) com falha</div>", unsafe_allow_html=True)
                    for cod, why in list(falhas.items())[:6]:
                        st.markdown(f"<div class='tb-cap'>{_e(cod)}: {_e(str(why))}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ TELA 2 · Análise
def _ferr_indicadores(v: dict) -> None:
    with st.popover("Indicadores", icon=":material/show_chart:"):
        st.toggle("Volume", value=True, key="tb_i_vol")
        if st.toggle("Média móvel simples", value=True, key="tb_i_sma"):
            st.number_input("Período da média simples", 2, 100, 20, key="tb_i_nsma")
        if st.toggle("Média móvel exponencial", value=False, key="tb_i_ema"):
            st.number_input("Período da média exponencial", 2, 100, 9, key="tb_i_nema")
        st.toggle("RSI (14)", value=False, key="tb_i_rsi")
        st.toggle("Suporte e resistência automáticos", value=False, key="tb_i_sr")
        st.toggle("Mexer no gráfico com o dedo", value=True, key="tb_i_mov", help="Desligue para rolar a página passando o dedo sobre o gráfico.")


def _marcas() -> dict:
    return _ss().setdefault("tb_marcas", {"niveis": [], "tendencias": [], "notas": []})


def _add_nivel() -> None:
    v = _ss().get("tb_mk_preco")
    if v:
        _marcas()["niveis"].append({"preco": float(v), "rotulo": (_ss().get("tb_mk_rot") or "")[:20]})


def _add_tend(cand: list[dict]) -> None:
    n = len(cand)
    a, b = int(_ss().get("tb_mk_a", 20)), int(_ss().get("tb_mk_b", 3))
    i1, i2 = n - 1 - a, n - 1 - b
    if 0 <= i1 < i2 < n:
        col = "l" if _ss().get("tb_mk_ap", "Fundos") == "Fundos" else "h"
        _marcas()["tendencias"].append({"i1": i1, "p1": cand[i1][col], "i2": i2, "p2": cand[i2][col]})
    else:
        _ss()["tb_erro"] = "Na linha de tendência, o candle A precisa vir antes do B (A com número maior de candles atrás)."


def _add_nota(cand: list[dict]) -> None:
    n = len(cand)
    a = int(_ss().get("tb_mk_na", 3))
    txt = (_ss().get("tb_mk_nt") or "").strip()
    if txt and 0 <= n - 1 - a < n:
        _marcas()["notas"].append({"i": n - 1 - a, "preco": cand[n - 1 - a]["c"], "texto": txt[:40]})


def _limpar_marcas() -> None:
    _ss()["tb_marcas"] = {"niveis": [], "tendencias": [], "notas": []}


def _ferr_marcar(v: dict) -> None:
    cand = v["candles"]
    m = _marcas()
    with st.popover("Marcar", icon=":material/draw:"):
        st.caption("Níveis, tendências e notas ficam registrados junto com a estratégia. (Os desenhos livres da barra do gráfico servem de rascunho e não são salvos.)")
        st.markdown("<div class='tb-h'>Nível de preço</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([1.2, 1])
        c1.number_input("Preço", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_mk_preco", label_visibility="collapsed", placeholder="Preço")
        c2.text_input("Nome", key="tb_mk_rot", label_visibility="collapsed", placeholder="Nome (opcional)", max_chars=20)
        st.button("Adicionar nível", key="tb_add_n", on_click=_add_nivel, width="stretch", disabled=len(m["niveis"]) >= TB.MAX_MARCAS["niveis"])
        st.markdown("<div class='tb-h'>Linha de tendência</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.number_input("A (candles atrás)", 1, len(cand) - 1, 20, key="tb_mk_a")
        c2.number_input("B (candles atrás)", 0, len(cand) - 2, 3, key="tb_mk_b")
        c3.selectbox("Apoiar em", ["Fundos", "Topos"], key="tb_mk_ap")
        st.button("Adicionar tendência", key="tb_add_t", on_click=_add_tend, args=(cand,), width="stretch", disabled=len(m["tendencias"]) >= TB.MAX_MARCAS["tendencias"])
        st.markdown("<div class='tb-h'>Anotação</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        c1.text_input("Texto", key="tb_mk_nt", label_visibility="collapsed", placeholder="Texto curto", max_chars=40)
        c2.number_input("Candles atrás", 0, len(cand) - 1, 3, key="tb_mk_na", label_visibility="collapsed")
        st.button("Adicionar anotação", key="tb_add_a", on_click=_add_nota, args=(cand,), width="stretch", disabled=len(m["notas"]) >= TB.MAX_MARCAS["notas"])
        st.caption(f"{len(m['niveis'])} nível(is) · {len(m['tendencias'])} tendência(s) · {len(m['notas'])} nota(s)")
        st.button("Limpar marcações", key="tb_lim_m", on_click=_limpar_marcas, width="stretch")


def _mudar_conf(d: int) -> None:
    _ss()["tb_conf"] = max(1, min(5, int(_ss().get("tb_conf", 3)) + d))


def _montar_est(ref: float) -> dict:
    s = _ss()
    return {"direcao": s.get("tb_dir"), "tipo": s.get("tb_tipo"), "confianca": int(s.get("tb_conf", 3)),
            "entrada": s.get("tb_ent"), "stop": s.get("tb_stop"), "alvo": s.get("tb_alvo")}


def _salvar(p: dict, ref: float) -> None:
    try:
        TB.salvar_estrategia(p, _jogador(), _montar_est(ref), _marcas(), ref, _agora())
        _ss()["tb_salva"] = True
        _ss().pop("tb_erro", None)
    except TB.ErroTrader as e:
        _ss()["tb_erro"] = str(e)


def _replay_ja(p: dict) -> None:
    try:
        TB.iniciar_replay(p, _jogador(), _agora())
    except TB.ErroTrader as e:
        _ss()["tb_erro"] = str(e)


@st.fragment(run_every=POLL_S)
def _frag_relogio_analise() -> None:
    p = _partida()
    if not p:
        return
    _avancar(p, _agora())
    if p["fase"] != "analise":
        return st.rerun()
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    st.markdown(_topo(v, v["segundos"], "análise"), unsafe_allow_html=True)
    if v["segundos"] <= 15 and not v["estrategia"]:
        st.markdown("<div class='tb-er'>⏱ Poucos segundos! Salve a estratégia ou a rodada conta como Aguardar.</div>", unsafe_allow_html=True)


def _analise_classica(p: dict) -> None:
    """Montagem por formulário (plano B: usada se a mesa de operações não estiver disponível)."""
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    ref = v["candles"][-1]["c"]
    _voltar()
    _frag_relogio_analise()
    if v["demo"]:
        st.markdown("<div class='tb-demo'>DADOS SIMULADOS (modo demonstração)</div>", unsafe_allow_html=True)
    _grafico(v, _marcas(), None, chave="tb_graf_a")
    st.markdown("<div class='tb-cap'>Não atualize a página: a partida em andamento não é salva.</div>", unsafe_allow_html=True)
    with st.container(key="tb_ferr"):
        c1, c2, c3 = st.columns([0.7, 1.2, 1])
        c1.markdown(f"<div class='tb-rod' style='justify-content:center;height:38px'>{_e(v['tf'])}</div>", unsafe_allow_html=True)
        with c2:
            _ferr_indicadores(v)
        with c3:
            _ferr_marcar(v)
    with st.container(key="tb_estr"):
        st.markdown("<div class='tb-h'>Sua Estratégia</div>", unsafe_allow_html=True)
        st.segmented_control("Direção", ["alta", "baixa", "lateral"], key="tb_dir", label_visibility="collapsed",
                             format_func=lambda k: {"alta": "▲ Alta", "baixa": "▼ Baixa", "lateral": "↔ Lateral"}[k])
        st.segmented_control("Estratégia", list(TB.ESTRATEGIAS), key="tb_tipo", label_visibility="collapsed", format_func=lambda k: TB.ROTULO_ESTRATEGIA[k])
        operar = _ss().get("tb_tipo") not in (None, "aguardar") and _ss().get("tb_dir") in ("alta", "baixa")
        if operar:
            c1, c2, c3 = st.columns(3)
            c1.number_input("Entrada", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_ent", placeholder=f"{ref:.2f}")
            c2.number_input("Stop", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_stop")
            c3.number_input("Alvo", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_alvo")
        elif _ss().get("tb_tipo") == "aguardar":
            st.markdown("<div class='tb-cap'>Aguardar é uma decisão válida: você fica de fora desta rodada.</div>", unsafe_allow_html=True)
        with st.container(key="tb_conf_l"):
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"<div class='tb-h' style='margin-top:6px'>Confiança: {int(_ss().get('tb_conf', 3))}/5</div>", unsafe_allow_html=True)
            c2.button("−", key="tb_conf_m", on_click=_mudar_conf, args=(-1,), width="stretch")
            c3.button("+", key="tb_conf_p", on_click=_mudar_conf, args=(1,), width="stretch")
        st.button("Salvar Estratégia", key="tb_salvar", icon=":material/check:", width="stretch", on_click=_salvar, args=(p, ref))
        if _ss().get("tb_erro"):
            st.markdown(f"<div class='tb-er'>{_e(_ss().pop('tb_erro'))}</div>", unsafe_allow_html=True)
        elif p["estrategias"].get(f"{p['rodada']}:{_jogador()}"):
            st.markdown("<div class='tb-ok'>✔ Estratégia salva. Você pode ajustar até o tempo acabar.</div>", unsafe_allow_html=True)
            st.button("Iniciar replay agora", key="tb_replay_ja", icon=":material/fast_forward:", width="stretch", on_click=_replay_ja, args=(p,))


_CSS_MESA = ("<style>" + "".join(l.strip() for l in f"""
{_P} .block-container,{_P} [data-testid="stMainBlockContainer"]{{padding-top:.5rem !important;padding-bottom:.2rem !important}}
{_P} [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{{gap:.3rem !important}}
{_P} .st-key-tb_voltar button{{min-height:32px !important;height:32px !important;padding:0 12px !important}}
{_P} iframe[data-testid="stCustomComponentV1"]{{border:0 !important;display:block;width:100%}}
{_P} .st-key-tb_fragsil{{display:none !important}}
""".splitlines()) + "</style>")


@st.fragment(run_every=2)
def _frag_fase_silencioso() -> None:
    """Sem desenho: só garante que, quando o relógio do servidor encerrar a análise, a tela passe para o replay."""
    p = _partida()
    if not p:
        return
    _avancar(p, _agora())
    if p["fase"] != "analise":
        return st.rerun()


def _analise(p: dict) -> None:
    """Análise em tela útil inteira: gráfico com as marcações de Entrada, Stop e Alvo feitas direto nele (componente trader_front)."""
    if _ss().get("tb_sem_mesa") or not TG.disponivel():
        return _analise_classica(p)
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    ref = v["candles"][-1]["c"]
    chave = f"tb_mesa_{p['id']}_{p['rodada']}"
    est = _ss().setdefault(f"tb_ev_{chave}", {})
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    try:
        val = TG.mesa(chave, **_args(v, p, est, _agora()))
    except Exception:
        _ss()["tb_sem_mesa"] = True                       # componente indisponível neste ambiente: cai para o formulário
        return st.rerun()
    if TG.processar(p, val, est, _jogador(), ref, _agora(), cen=_cenario_atual(p)):
        _saiu(est, _sair)
        return st.rerun()
    with st.container(key="tb_fragsil"):
        _frag_fase_silencioso()


# ------------------------------------------------------------------ MESA CONTÍNUA · análise, replay e resultado no MESMO gráfico
@st.fragment(run_every=1)
def _frag_mesa() -> None:
    """Um único componente por partida (chave estável): as rodadas seguem em sequência cronológica no mesmo gráfico, sem fechar nem reabrir.
    O servidor decide o que aparece (candles revelados e entradas de adversários autorizadas); o componente só desenha."""
    p = _partida()
    if not p:
        return
    ag, jog = _agora(), _jogador()
    _avancar(p, ag)
    if p["fase"] == "fim":
        return st.rerun()
    cen = _cenario_atual(p)
    if p["fase"] == "resultado" and f"{p['rodada']}:{jog}" not in p["resultados"]:
        TB.fechar_rodada(p, cen)
    est = _ss().setdefault(f"tb_ev_{p['id']}", {})
    v = TB.visao(p, cen, ag, jog)
    ref = v["candles"][-1]["c"]
    try:
        val = TG.mesa(f"tb_mesa_{p['id']}", **_args(v, p, est, ag))
    except Exception:
        _ss()["tb_sem_mesa"] = True                       # componente indisponível neste ambiente: cai para as telas clássicas
        return st.rerun()
    if TG.processar(p, val, est, jog, ref, ag, cen=cen):
        _saiu(est, _sair)
        return st.rerun(scope="app" if p["fase"] == "fim" else "fragment")


def _mesa_continua(p: dict) -> None:
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    _frag_mesa()


# ------------------------------------------------------------------ TELA 3 · Replay
def _txt_operacao(op: dict) -> str:
    """Texto simples da situação da operação (tela clássica, sem o gráfico)."""
    nome = {"aguardando": "Ordem aguardando o preço de entrada", "cancelada": "Ordem cancelada por você", "aberta": "Operação aberta", "fechada": "Operação encerrada"}[op["estado"]]
    return nome + (f" · resultado {op['pct']:+.2f}%".replace(".", ",") if op["estado"] in ("aberta", "fechada") else "")


def _encerrar(p: dict) -> None:
    try:
        TB.encerrar_operacao(p, _cenario_atual(p), _jogador(), _agora())
    except TB.ErroTrader as e:
        _ss()["tb_erro_enc"] = str(e)


@st.fragment(run_every=POLL_S)
def _frag_replay() -> None:
    p = _partida()
    if not p:
        return
    _avancar(p, _agora())
    if p["fase"] != "replay":
        return st.rerun()
    cen = _cenario_atual(p)
    v = TB.visao(p, cen, _agora(), _jogador())
    est = v["estrategia"] or {}
    st.markdown(_topo(v, v["segundos"], "replay"), unsafe_allow_html=True)
    _grafico(v, est.get("marcas") or {"niveis": [], "tendencias": [], "notas": []}, est if est.get("entrada") else None, chave="tb_graf_r")
    nd = {"alta": "Alta", "baixa": "Baixa", "lateral": "Lateral"}
    if est.get("sem_registro"):
        st.markdown("<div class='tb-aviso'>🔒 Estratégia travada: você não registrou nada, então esta rodada conta como Aguardar.</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='tb-ok'>🔒 Estratégia travada · {_e(nd.get(est.get('direcao'), ''))} · {_e(TB.ROTULO_ESTRATEGIA.get(est.get('tipo'), ''))} · confiança {est.get('confianca')}/5</div>",
                    unsafe_allow_html=True)
    frac = min(1.0, (TB.T_REPLAY_S - v["segundos"]) / TB.T_REPLAY_S)
    st.progress(frac, text=f"Replay em andamento · {v['revelados']}/{v['total_replay']} candles revelados")
    st.markdown("<div class='tb-card'><b>Acompanhe o movimento</b><p>Os candles aparecem na ordem em que aconteceram. Veja se a sua estratégia se confirma!</p></div>", unsafe_allow_html=True)
    op = v.get("operacao")
    if op:
        st.markdown(f"<div class='tb-card'><b>Sua operação</b><p>{_e(_txt_operacao(op))}</p></div>", unsafe_allow_html=True)
        if op["encerravel"]:
            st.button("Encerrar operação", key="tb_encerrar", icon=":material/stop_circle:", width="stretch", on_click=_encerrar, args=(p,))
        if _ss().get("tb_erro_enc"):
            st.caption(_ss().pop("tb_erro_enc"))


@st.fragment(run_every=1)
def _frag_replay_mesa() -> None:
    """Replay na mesa (canvas): a tela continua montada e só recebe os candles que o servidor já liberou; a animação é local e suave."""
    p = _partida()
    if not p:
        return
    _avancar(p, _agora())
    if p["fase"] != "replay":
        return st.rerun()
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    try:
        TG.mesa(f"tb_mesa_r_{p['id']}_{p['rodada']}", **_args(v, p, {}, _agora()))
    except Exception:
        _ss()["tb_sem_mesa"] = True
        return st.rerun()


def _replay(p: dict) -> None:
    if _ss().get("tb_sem_mesa") or not TG.disponivel():
        _voltar()
        return _frag_replay()
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    _voltar()
    _frag_replay_mesa()


# ------------------------------------------------------------------ TELA 4 · Resultado da rodada
def _proxima(p: dict) -> None:
    TB.proxima_rodada(p, _agora())
    _zerar_rascunho_rodada()


def _zerar_rascunho_rodada() -> None:
    for k in [k for k in _ss() if k.startswith("tb_") and not k.startswith("tb_i_") and k not in ("tb_p", "tb_cen", "tb_tf")]:
        _ss().pop(k, None)


def _resultado(p: dict) -> None:
    cen = _cenario_atual(p)
    if f"{p['rodada']}:{_jogador()}" not in p["resultados"]:
        TB.fechar_rodada(p, cen)
    v = TB.visao(p, cen, _agora(), _jogador())
    r = v["resultado"]
    st.markdown(_topo(v, None, "resultado"), unsafe_allow_html=True)
    est = r["estrategia"]
    _grafico(v, est.get("marcas") or {"niveis": [], "tendencias": [], "notas": []}, est if est.get("entrada") else None, divisor=True, chave="tb_graf_x")
    fx = {True: "faixa_vitoria", False: "faixa_derrota"}.get(r.get("acertou_direcao"), "faixa_empate")
    st.markdown(f"<div class='tb-faixa'>{CT.img(fx, alt='')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='tb-pts'><div class='n'>{r['pontos']:.1f}</div><small>pontos nesta rodada · total {p['pontos'][_jogador()]:.1f}</small></div>", unsafe_allow_html=True)
    with st.expander("Raio-X da rodada", icon=":material/search:", expanded=False):
        st.markdown(_raiox_html(TB.explicar(r)), unsafe_allow_html=True)
        st.markdown(f"<div class='tb-cap'>{'Dados simulados (modo demonstração).' if v['demo'] else 'Fonte: ' + _e(v['fonte']) + '.'} Pontuação educativa; não mede lucro real nem é recomendação.</div>",
                    unsafe_allow_html=True)
    ultima = p["rodada"] >= TB.cfg_de(p)["rodadas"]
    st.button("Ver resultado final" if ultima else "Próxima rodada", key="tb_prox", icon=":material/arrow_forward:", width="stretch", on_click=_proxima, args=(p,))


# ------------------------------------------------------------------ TELA 5 · Fim da partida
def _de_novo() -> None:
    _sair()
    _iniciar()


def _fim(p: dict) -> None:
    j = _jogador()
    _liquidar(p, forcar=True)
    fz = TB.resumo_final(p, j)
    _ss()["tb_av_assentos"] = _avatares_assentos(p)
    _registrar_ranking(p["id"], fz, p, j)
    rv = TB.revelacao(p, _cen()[p["cenarios"][0]]) if TB.qtd_de(p) else None
    _tela_final(fz, TB.resumo_financeiro(p, j), bool(p["demo"]), [_cen()[cid]["ticker"] for cid in p["cenarios"]], _pagar_xp(p["id"], fz["xp"]), rv)
    _relatorio(p, j, rv, fz.get("xp"))
    st.button("Jogar novamente", key="tb_de_novo", icon=":material/replay:", width="stretch", on_click=_de_novo)
    st.button("Voltar ao início do Trade Battle", key="tb_voltar", icon=":material/home:", width="stretch", on_click=_sair)


# ------------------------------------------------------------------ página
def pagina_trader() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    p = _partida()
    em = _email_online()
    if em and not p and not _ss().get("tb_on_visto"):
        _ss()["tb_on_visto"] = True                              # voltou à página (ou atualizou): retoma a partida em sala/andamento, se houver
        try:
            ativa = TOD.partida_ativa(em)
            if ativa:
                _ss()["tb_on_pid"] = ativa
        except Exception:
            pass
    if em and not p and _ss().get("tb_on_pid"):
        return _pagina_online(_ss()["tb_on_pid"])
    if not p:
        _central()
        return
    try:
        _avancar(p, _agora())
        if p["fase"] != "fim" and not _ss().get("tb_sem_mesa") and TG.disponivel():
            _mesa_continua(p)
        elif p["fase"] != "fim" and TB.motor_de(p) == TB.MOTOR_MESA:
            st.markdown("<div class='tb-er'>A mesa de operações precisa do gráfico interativo, e ele não carregou neste navegador. Tente atualizar a página ou usar outro navegador.</div>", unsafe_allow_html=True)
            st.button("Sair da partida", key="tb_sem_mesa_sair", icon=":material/logout:", width="stretch", on_click=_sair)
        else:
            {"analise": _analise, "replay": _replay, "resultado": _resultado, "fim": _fim}[p["fase"]](p)
    except KeyError:                                           # cenário sumiu da sessão: volta ao início sem derrubar a página
        _sair()
        return st.rerun()
