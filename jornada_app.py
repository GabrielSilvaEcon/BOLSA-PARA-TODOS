"""Aba "Jornada" da Educação financeira: trilha em zigue-zague, estilo Duolingo.

- Só desenha o mapa a partir de jornada.mapa(); a lógica (XP, sessão, ofensiva) fica em jornada.py e os ícones em jornada_icones.py.
- Nada é trancado: a lição "próxima" é só destacada (balão COMEÇAR); as demais ficam livres.
- Não importa educacao_app (evita import circular): a função da aba recebe `prog` (devolve o progresso atual).
- Cada nó é um st.button de verdade (clicável) estilizado por CSS: a classe `st-key-<key>` do Streamlit identifica o estado
  (jor_nc_ concluída, jor_np_ próxima, jor_nl_ livre) e o ícone entra como imagem de fundo.
- Clicar num nó inicia a lição e a aba passa a mostrar o player (jornada_player.py) até a pessoa concluir ou sair.
"""
from __future__ import annotations

import html

import streamlit as st

import conta_app as C
import jornada as JO
import jornada_arte as ART
import jornada_icones as IC
import jornada_liga_app as LIGA
import jornada_player as PLAYER
import nivel_app as NVA

COLUNAS = 5
ONDA = (2, 3, 2, 1)          # coluna do nó em cada linha (0..4): centro, direita, centro, esquerda
LARGURA = 380                # largura máxima do mapa (px), centralizado
PREFIXO = {"concluida": "jor_nc_", "proxima": "jor_np_", "livre": "jor_nl_"}

CSS_BASE = f"""<style>
.jor-stats{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:2px 0 6px;}}
.jor-pill{{display:flex;align-items:center;gap:7px;background:#1B1442;border:1px solid #3D3182;border-radius:99px;padding:5px 13px 5px 9px;color:#F6F3FF !important;font-weight:800;font-size:.92rem;}}
.jor-pill img{{width:20px;height:20px;display:block;}}
.jor-pill.viva img{{animation:jor-chama 1.4s ease-in-out infinite;transform-origin:50% 80%;}}
.jor-metabar{{max-width:{LARGURA}px;margin:0 auto 4px;height:8px;border-radius:99px;background:#2A2060;overflow:hidden;}}
.jor-metabar i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#2DD4A0,#6CF0C8);animation:jor-enche-meta .8s ease-out;}}
@keyframes jor-enche-meta{{from{{width:0}}}}
@media (prefers-reduced-motion:reduce){{.jor-pill.viva img,.jor-metabar i,.jor-bolha,div[class*="st-key-jor_n"] button,div[class*="st-key-jor_n"] button:after{{animation:none !important;}}}}
.jor-pill small{{color:#BDB5E6 !important;font-weight:600;font-size:.72rem;}}
.jor-un{{max-width:{LARGURA}px;margin:20px auto 18px;border-radius:18px;padding:14px 16px;box-shadow:0 5px 0 rgba(0,0,0,.38);}}
.jor-un .top{{display:flex;align-items:center;gap:12px;}}
.jor-un .ic{{flex:0 0 46px;width:46px;height:46px;border-radius:13px;background:rgba(0,0,0,.18);display:flex;align-items:center;justify-content:center;}}
.jor-un .ic img{{width:28px;height:28px;display:block;}}
.jor-un .tx{{flex:1;min-width:0;}}
.jor-un .t{{font-weight:900;font-size:1.05rem;line-height:1.25;}}
.jor-un .s{{font-size:.84rem;line-height:1.3;opacity:.9;margin-top:2px;}}
.jor-un .n{{font-weight:900;font-size:.95rem;white-space:nowrap;}}
.jor-un .bar{{height:8px;background:rgba(0,0,0,.28);border-radius:99px;overflow:hidden;margin-top:11px;}}
.jor-un .bar i{{display:block;height:100%;background:#fff;border-radius:99px;}}
.jor-real{{max-width:{LARGURA}px;margin:18px auto 6px;border-radius:16px;padding:12px 14px;background:#1B1442;border:2px dashed #3D3182;color:#F6F3FF !important;}}
.jor-real .t{{font-weight:900;font-size:.98rem;}}
.jor-real .s{{font-size:.84rem;line-height:1.35;color:#BDB5E6 !important;margin-top:3px;}}
.jor-con{{max-width:{LARGURA}px;margin:-8px auto;height:30px;}}
.jor-con svg{{display:block;width:100%;height:100%;overflow:visible;}}
.jor-leg{{position:relative;left:50%;transform:translateX(-50%);width:128px;text-align:center;color:#EDE9FF !important;font-weight:700;font-size:.8rem;line-height:1.2;margin-top:12px;}}
.jor-bolha{{position:relative;left:50%;width:max-content;transform:translateX(-50%);background:#fff;color:#5B3FD6 !important;font-weight:900;font-size:.7rem;letter-spacing:.07em;padding:5px 11px;border-radius:11px;margin-bottom:9px;animation:jor-quica 1.5s ease-in-out infinite;}}
.jor-bolha:after{{content:"";position:absolute;left:50%;bottom:-6px;margin-left:-6px;border:6px solid transparent;border-bottom:0;border-top-color:#fff;}}
@keyframes jor-chama{{0%,100%{{transform:rotate(-6deg) scale(1)}}50%{{transform:rotate(6deg) scale(1.15)}}}}
@keyframes jor-conquista{{0%{{transform:scale(.85)}}45%{{transform:scale(1.18)}}100%{{transform:scale(1)}}}}
@keyframes jor-selo{{0%{{transform:scale(0) rotate(-90deg)}}70%{{transform:scale(1.35) rotate(8deg)}}100%{{transform:scale(1) rotate(0)}}}}
@keyframes jor-quica{{0%,100%{{transform:translate(-50%,0)}}50%{{transform:translate(-50%,-5px)}}}}
@keyframes jor-pulso{{0%{{box-shadow:0 6px 0 #5B3FD6,0 0 0 0 rgba(139,108,255,.55)}}100%{{box-shadow:0 6px 0 #5B3FD6,0 0 0 16px rgba(139,108,255,0)}}}}
/* mantém o zigue-zague no celular: o Streamlit empilha colunas em telas estreitas, e aqui isso desmancharia o caminho */
div[data-testid="stHorizontalBlock"]:has(.jor-zz){{flex-wrap:nowrap !important;gap:0 !important;max-width:{LARGURA}px;margin:0 auto;width:100%;}}
div[data-testid="stHorizontalBlock"]:has(.jor-zz) > div[data-testid="stColumn"],
div[data-testid="stHorizontalBlock"]:has(.jor-zz) > div[data-testid="column"]{{min-width:0 !important;flex:1 1 0 !important;width:auto !important;}}
/* nó redondo em 3D */
div[class*="st-key-jor_n"]{{display:flex;justify-content:center;}}
div[class*="st-key-jor_n"] button{{position:relative;width:76px !important;height:76px !important;min-height:76px !important;padding:0 !important;border-radius:50% !important;
  border:0 !important;background-repeat:no-repeat !important;background-position:center !important;background-size:38px !important;
  box-shadow:0 6px 0 var(--sh) !important;transition:transform .08s,box-shadow .08s,filter .15s;}}
div[class*="st-key-jor_n"] button *{{font-size:0 !important;color:transparent !important;}}
div[class*="st-key-jor_n"] button:hover{{filter:brightness(1.1);}}
div[class*="st-key-jor_n"] button:active,div[class*="st-key-jor_n"] button:focus:active{{transform:translateY(4px);box-shadow:0 2px 0 var(--sh) !important;}}
div[class*="st-key-jor_n"] button:focus{{outline:none !important;}}
div[class*="st-key-jor_nc_"] button{{--sh:#178A68;background-color:#2DD4A0 !important;}}
div[class*="st-key-jor_np_"] button{{--sh:#5B3FD6;background-color:#8B6CFF !important;animation:jor-pulso 1.8s ease-out infinite;}}
div[class*="st-key-jor_nl_"] button{{--sh:#150F38;background-color:#2A2060 !important;border:2px solid #4B3E99 !important;}}
div[class*="st-key-jor_nc_"] button:after{{content:"";position:absolute;top:-3px;right:-3px;width:26px;height:26px;border-radius:50%;border:3px solid #110C2E;
  background:#FFC94D url("{IC.uri('check', '#5A3B00')}") center/13px no-repeat;}}
</style>"""

CSS_ARTE = f"""<style>
div[class*="st-key-jor_cena_"]{{max-width:{LARGURA}px;margin:0 auto;width:100%;background-repeat:repeat-y;background-size:100% 560px;background-position:center top;border-radius:22px;}}
div[class*="st-key-jor_n"] button:before{{content:"";position:absolute;inset:0;border-radius:50%;pointer-events:none;background:radial-gradient(circle at 30% 20%,rgba(255,255,255,.5),rgba(255,255,255,0) 48%),radial-gradient(circle at 50% 120%,rgba(0,0,0,.22),rgba(0,0,0,0) 55%);}}
div[class*="st-key-jor_nc_"] button{{background-color:var(--c) !important;box-shadow:0 6px 0 var(--sh),0 0 0 7px color-mix(in srgb,var(--c) 24%,transparent) !important;}}
div[class*="st-key-jor_np_"] button{{background-color:var(--c) !important;animation:jor-pulso2 1.8s ease-out infinite !important;}}
div[class*="st-key-jor_nl_"] button{{background-color:color-mix(in srgb,var(--c) 22%,#1B1442) !important;border:2px solid color-mix(in srgb,var(--c) 50%,#1B1442) !important;box-shadow:0 6px 0 var(--sh) !important;}}
div[class*="st-key-jor_nl_"] button:before{{opacity:.35;}}
@keyframes jor-pulso2{{0%{{box-shadow:0 6px 0 var(--sh),0 0 0 0 color-mix(in srgb,var(--c) 65%,transparent)}}100%{{box-shadow:0 6px 0 var(--sh),0 0 0 18px transparent}}}}
.jor-leg{{width:max-content;max-width:150px;background:rgba(27,20,66,.88);border:1px solid #3D3182;border-radius:99px;padding:3px 11px;margin-top:14px;}}
.jor-un{{position:relative;overflow:hidden;}}
.jor-un .top,.jor-un .bar{{position:relative;z-index:1;}}
.jor-un .art{{position:absolute;right:-30px;bottom:-34px;opacity:.1;transform:rotate(-14deg);pointer-events:none;}}
.jor-un .art2{{position:absolute;right:92px;top:-18px;width:70px;height:70px;border-radius:50%;background:rgba(255,255,255,.1);pointer-events:none;}}
.jor-hero{{display:flex;align-items:flex-end;gap:6px;max-width:{LARGURA}px;margin:6px auto 12px;}}
.jor-tico{{flex:0 0 124px;animation:jor-tico 3.2s ease-in-out infinite;transform-origin:50% 100%;}}
.jor-tico svg{{display:block;}}
.jor-fala{{position:relative;flex:1;margin-bottom:26px;background:#fff;color:#2A1F5E !important;border-radius:16px;padding:10px 14px;font-weight:700;font-size:.9rem;line-height:1.3;box-shadow:0 4px 0 rgba(0,0,0,.3);}}
.jor-fala:before{{content:"";position:absolute;left:-8px;bottom:14px;border:8px solid transparent;border-left:0;border-right-color:#fff;}}
.jor-pill{{background:linear-gradient(180deg,#26195E,#1B1442);box-shadow:0 3px 0 rgba(0,0,0,.3);}}
@keyframes jor-tico{{0%,100%{{transform:translateY(0) rotate(-2deg)}}50%{{transform:translateY(-4px) rotate(2deg)}}}}
@media (prefers-reduced-motion:reduce){{.jor-tico,div[class*="st-key-jor_np_"] button{{animation:none !important;}}}}
</style>"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _cor_ok(cor: str) -> str:
    c = str(cor)
    return c if len(c) == 7 and c[0] == "#" and all(h in "0123456789abcdefABCDEF" for h in c[1:]) else "#2DD4A0"


def _texto_sobre(cor: str) -> str:
    """Texto escuro sobre cor clara e branco sobre cor escura (contraste legível)."""
    c = _cor_ok(cor)
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#0B0821" if lum > 0.45 else "#FFFFFF"


# ------------------------------------------------------------------ pedaços de HTML (funções puras, testáveis sem Streamlit)
def css_icones(mapa: list[dict], recente: str | None = None) -> str:
    """Ícone de cada lição como fundo do botão, na cor da unidade, e o cenário atrás de cada unidade.
    `recente` = lição que acabou de ser concluída: o botão dá um pulinho e o selo de concluída 'estampa' (uma vez só)."""
    regras = []
    for u in mapa:
        cor = _cor_ok(u["cor"])
        regras.append(f'div[class*="st-key-jor_cena_{u["id"]}"]{{background-image:url("{ART.tile(cor)}");}}')
        for l in u["licoes"]:
            livre = l["estado"] == "livre"
            icone = ART.clarear(cor, .6) if livre else _texto_sobre(cor)
            regras.append(f'div[class*="st-key-{PREFIXO[l["estado"]]}{l["id"]}"] button{{--c:{cor};--sh:{ART.escurecer(cor, .5)};background-image:url("{IC.uri(l["svg"], icone)}") !important;}}')
        if recente and any(l["id"] == recente and l["estado"] == "concluida" for l in u["licoes"]):
            regras.append(f'div[class*="st-key-jor_nc_{recente}"] button{{animation:jor-conquista .7s ease-out !important;}}'
                          f'div[class*="st-key-jor_nc_{recente}"] button:after{{animation:jor-selo .7s .25s cubic-bezier(.2,1.4,.4,1) both !important;}}')
    return "<style>" + "".join(regras) + "</style>"


def html_stats(r: dict) -> str:
    def pill(icone, cor, valor, rotulo, viva=False):
        return f"<div class='jor-pill{' viva' if viva else ''}'><img src='{IC.uri(icone, cor)}' alt=''>{_e(valor)} <small>{_e(rotulo)}</small></div>"
    return ("<div class='jor-stats'>" + pill("chama", "#FF9B3D", r["ofensiva"], "dia seguido" if r["ofensiva"] == 1 else "dias seguidos", viva=r["xp_hoje"] > 0 and r["ofensiva"] > 0) + pill("raio", "#FFC94D", r["xp"], "XP")
            + "</div>")


def html_pct(r: dict) -> int:
    """Percentual (0..100) da meta diária já cumprido, para a barrinha abaixo dos indicadores."""
    return int(max(0, min(100, round(100 * r["xp_hoje"] / r["meta_dia"])))) if r.get("meta_dia") else 0


def html_unidade(u: dict) -> str:
    cor = _cor_ok(u["cor"])
    txt = _texto_sobre(cor)
    pct = (u["feitas"] / u["total"]) if u["total"] else 0.0
    return (f"<div class='jor-un' style='background:linear-gradient(135deg,rgba(255,255,255,.18),rgba(0,0,0,.2)),{cor};color:{txt} !important'>"
            f"<div class='art2'></div><div class='art'>{IC.svg(u['svg'], txt, 130)}</div>"
            f"<div class='top'><div class='ic'><img src='{IC.uri(u['svg'], txt)}' alt=''></div>"
            f"<div class='tx'><div class='t' style='color:{txt} !important'>{_e(u['titulo'])}</div><div class='s' style='color:{txt} !important'>{_e(u['descricao'])}</div></div>"
            f"<div class='n' style='color:{txt} !important'>{u['feitas']}/{u['total']}</div></div>"
            f"<div class='bar'><i style='width:{pct * 100:.0f}%;background:#fff'></i></div></div>")


def _x(coluna: int) -> float:
    return (coluna * 2 + 1) / (COLUNAS * 2) * 300


def html_estudo_real(e: dict) -> str:
    """Card do fim da unidade: convida (sem obrigar) a estudar com um ativo real."""
    return (f"<div class='jor-real'><div class='t'>Unidade concluída. Pratique com dado real</div>"
            f"<div class='s'><b>{_e(e['titulo'])}</b><br>{_e(e['dica'])} Opcional e sem XP: é só para ligar a lição ao mercado de verdade.</div></div>")


def html_conector(col_a: int, col_b: int, feito: bool) -> str:
    """Linha pontilhada curva entre dois nós. Verde quando a lição de cima já foi concluída."""
    xa, xb = _x(col_a), _x(col_b)
    cor = "#2DD4A0" if feito else "#4B3E99"
    return (f"<div class='jor-con'><svg viewBox='0 0 300 30' preserveAspectRatio='none'><path d='M{xa:.1f} 0 C{xa:.1f} 15 {xb:.1f} 15 {xb:.1f} 30' fill='none' "
            f"stroke='{cor}' stroke-width='4' stroke-linecap='round' stroke-dasharray='1 9' vector-effect='non-scaling-stroke'/></svg></div>")


def html_legenda(titulo: str) -> str:
    return f"<div class='jor-leg'>{_e(titulo)}</div>"


HTML_BOLHA = "<div class='jor-bolha'>COMEÇAR</div>"
HTML_MARCADOR = "<span class='jor-zz'></span>"


# ------------------------------------------------------------------ ações
def _comecar(lid: str) -> None:
    PLAYER.iniciar(lid)


def _no(col, l: dict) -> None:
    """Um nó da trilha: balão (só na próxima), botão redondo com o ícone e o título embaixo."""
    feita = l["estado"] == "concluida"
    if l["estado"] == "proxima":
        col.markdown(HTML_BOLHA, unsafe_allow_html=True)
    ajuda = f"{l['titulo']} · {l['exercicios']} exercícios" + (f" · melhor resultado {l['melhor'] * 100:.0f}%" if feita else "")
    col.button("\u200b", key=f"{PREFIXO[l['estado']]}{l['id']}", help=ajuda, on_click=_comecar, args=(l["id"],))
    col.markdown(html_legenda(l["titulo"]), unsafe_allow_html=True)


OPCOES_META = (10, 20, 30, 50, 100)


def _revisar(prog) -> None:
    PLAYER.iniciar_revisao(prog())


def _mudar_meta(prog, set_prog) -> None:
    set_prog(JO.definir_meta(prog(), int(st.session_state.get("jor_meta", JO.META_DIA_PADRAO))))


def texto_meta(r: dict) -> str:
    """Frase curta sobre a meta de hoje (puro, testável)."""
    if r["meta_atingida"]:
        return "Meta de hoje concluída. Amanhã a sequência continua."
    falta = max(0, r["meta_dia"] - r["xp_hoje"])
    if r["ofensiva"] and r["xp_hoje"] == 0:
        return f"Estude hoje para manter {r['ofensiva']} {'dia' if r['ofensiva'] == 1 else 'dias'} seguido(s). Faltam {falta} XP para a meta."
    return f"Faltam {falta} XP para a meta de hoje."


CSS_NOVO = f"""<style>
html body .stApp.stApp.stApp .st-key-jor_hero{{max-width:560px;margin:4px auto 14px;padding:14px !important;border-radius:26px;gap:.7rem !important;
  background:radial-gradient(circle at 18% 30%,rgba(60,110,255,.38),transparent 55%),linear-gradient(160deg,#122259,#10183F 75%);border:1.5px solid rgba(110,140,255,.5);box-shadow:0 0 26px -10px rgba(80,120,255,.6)}}
.jh{{position:relative;display:flex;align-items:center;gap:8px}}
.jh-m{{flex:0 0 auto;margin:-8px 0 -8px -4px}}
.jh-m img,.jh-m svg{{width:clamp(110px,34vw,170px) !important;height:auto !important;filter:drop-shadow(0 8px 12px rgba(0,0,0,.45))}}
.jh-t{{min-width:0;padding-right:30px}}
.jh-h{{font-size:clamp(1.6rem,7vw,2.3rem);font-weight:900;color:#fff !important;line-height:1.1}}
.jh-h:after{{content:"";display:block;height:4px;width:70%;margin-top:4px;border-radius:4px;background:linear-gradient(90deg,#F2B84B,transparent)}}
.jh-s{{margin-top:10px;font-size:clamp(.88rem,3.4vw,1.15rem);line-height:1.3;color:#CFCBFF !important}}
.jh-i{{position:absolute;top:0;right:0}}
.jh-i summary{{list-style:none;cursor:pointer;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-style:italic;font-weight:800;color:#fff;
  background:rgba(10,8,40,.6);border:1.5px solid rgba(140,160,255,.6)}}
.jh-i summary::-webkit-details-marker{{display:none}}
.jh-i[open] div{{position:absolute;right:0;top:40px;width:min(78vw,300px);z-index:6;padding:10px 12px;border-radius:12px;background:#1B1442;border:1px solid #3D3182;color:#EDE9FF !important;font-size:.86rem;line-height:1.35}}
.jh-fala{{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:18px;background:rgba(10,8,40,.55);border:1px solid rgba(110,140,255,.35);color:#fff !important;font-weight:600;font-size:clamp(.9rem,3.4vw,1.1rem)}}
html body .stApp.stApp.stApp .st-key-jor_hero button,html body .stApp.stApp.stApp .st-key-jor_hero [data-testid="stBaseButton-primary"]{{width:100% !important;min-height:54px !important;border-radius:999px !important;border:0 !important;
  background:linear-gradient(180deg,#FFC93D,#F29A1F) !important;box-shadow:0 5px 0 #B96F00 !important}}
html body .stApp.stApp.stApp .st-key-jor_hero button :is(p,span){{color:#1B1442 !important;-webkit-text-fill-color:#1B1442 !important;font-weight:900 !important;font-size:1.1rem !important}}
.jor-un2{{max-width:{LARGURA}px;margin:16px auto 14px;padding:14px 16px;border-radius:22px;
  background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 12%,#0F1B3D),#0F1736 80%);border:1.5px solid color-mix(in srgb,var(--ac) 50%,transparent);box-shadow:0 4px 0 rgba(0,0,0,.3)}}
.jor-un2 .top{{display:flex;align-items:center;gap:12px}}
.jor-un2 .ic{{flex:0 0 52px;display:grid;place-items:center}}
.jor-un2 .ic img{{width:46px;height:46px;display:block;filter:drop-shadow(0 0 8px var(--ac))}}
.jor-un2 .tx{{flex:1;min-width:0}}
.jor-un2 .t{{font-weight:800;font-size:1.15rem;color:#fff !important;line-height:1.2}}
.jor-un2 .s{{font-size:.88rem;line-height:1.3;color:#CFCBFF !important;margin-top:2px}}
.jor-un2 .n{{padding:4px 14px;border-radius:99px;font-weight:900;font-size:1rem;white-space:nowrap;color:#fff !important;background:color-mix(in srgb,var(--ac) 25%,#0B1430);border:1.5px solid color-mix(in srgb,var(--ac) 60%,transparent)}}
.jor-un2 .bar{{height:10px;margin-top:12px;border-radius:99px;background:rgba(255,255,255,.1);overflow:hidden}}
.jor-un2 .bar i{{display:block;height:100%;border-radius:99px;background:var(--ac)}}
html body .stApp.stApp.stApp .st-key-jor_wg{{max-width:560px;margin:14px auto;padding:12px 14px !important;border-radius:24px;gap:.5rem !important;
  background:radial-gradient(circle at 12% 40%,rgba(255,190,60,.25),transparent 50%),linear-gradient(135deg,#3A1C8F,#2A1470 70%);border:1.5px solid rgba(170,130,255,.7)}}
.jw{{display:flex;align-items:center;gap:12px}}
.jw-a{{flex:0 0 auto}}
.jw-t{{min-width:0}}
.jw-h{{font-size:clamp(1.15rem,4.8vw,1.6rem);font-weight:900;color:#fff !important;line-height:1.1}}
.jw-h b{{display:inline-block;margin-left:6px;padding:2px 10px;border-radius:99px;background:#F2B84B;color:#1B1442 !important;font-size:.72rem;vertical-align:middle}}
.jw-s{{margin-top:4px;font-size:clamp(.8rem,3.2vw,1rem);line-height:1.3;color:#E6DEFF !important}}
html body .stApp.stApp.stApp .st-key-jor_wg button{{width:100% !important;min-height:46px !important;border-radius:999px !important;background:rgba(10,8,40,.45) !important;border:1.5px solid #C5B3FF !important;box-shadow:none !important}}
html body .stApp.stApp.stApp .st-key-jor_wg button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important}}
.jor-mapa-t{{max-width:{LARGURA}px;margin:18px auto 0;font-weight:800;color:#C5B3FF !important;font-size:.9rem;letter-spacing:.04em;text-transform:uppercase}}
</style>"""

_GAMEPAD = ("<svg width='96' height='72' viewBox='0 0 96 72' aria-hidden='true'><defs><linearGradient id='jg' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#3B3F7A'/><stop offset='1' stop-color='#15183F'/></linearGradient></defs>"
            "<path d='M20 18h56c10 0 16 10 18 26l2 14c1 7-6 11-12 7L72 54H24L12 65c-6 4-13 0-12-7l2-14c2-16 8-26 18-26z' fill='url(#jg)' stroke='#8B8FFF' stroke-width='2'/>"
            "<path d='M28 28v14M21 35h14' stroke='#F2B84B' stroke-width='5' stroke-linecap='round'/>"
            "<circle cx='66' cy='30' r='4' fill='#3DDC97'/><circle cx='75' cy='37' r='4' fill='#F2B84B'/><circle cx='57' cy='37' r='4' fill='#2BA7C9'/><circle cx='66' cy='44' r='4' fill='#FF6B8A'/></svg>")


def html_hero_jornada(mascote_html: str) -> str:
    return (f"<div class='jh'><div class='jh-m'>{mascote_html}</div><div class='jh-t'><div class='jh-h'>Jornada</div>"
            "<div class='jh-s'>Aprenda, evolua e se torne um verdadeiro TickerHunter!</div></div>"
            "<details class='jh-i'><summary aria-label='Sobre esta página'>i</summary><div>Lições curtas, uma de cada vez, no seu ritmo. "
            "Cada lição concluída rende XP e mantém a sua sequência de estudo.</div></details></div>"
            "<div class='jh-fala'><span>💡</span><span>Vamos aprender um pouco hoje?</span></div>")


def html_unidade_card(u: dict) -> str:
    cor = _cor_ok(u["cor"])
    pct = (u["feitas"] / u["total"]) if u["total"] else 0.0
    return (f"<div class='jor-un2' style='--ac:{cor}'><div class='top'><div class='ic'><img src='{IC.uri(u['svg'], cor)}' alt=''></div>"
            f"<div class='tx'><div class='t'>{_e(u['titulo'])}</div><div class='s'>{_e(u['descricao'])}</div></div>"
            f"<div class='n'>{u['feitas']}/{u['total']}</div></div><div class='bar'><i style='width:{pct * 100:.0f}%'></i></div></div>")


def html_wallet_jornada() -> str:
    return (f"<div class='jw'><div class='jw-a'>{_GAMEPAD}</div><div class='jw-t'><div class='jw-h'>Wallet Game<b>Novo!</b></div>"
            "<div class='jw-s'>Teste seus conhecimentos, ganhe recompensas e divirta-se aprendendo!</div></div></div>")


def _proxima_licao(mapa: list[dict]) -> str | None:
    todas = [l for u in mapa for l in u["licoes"]]
    for estado in ("proxima", "livre"):
        for l in todas:
            if l["estado"] == estado:
                return l["id"]
    return todas[0]["id"] if todas else None


def _ir_wallet() -> None:
    st.session_state["_nav_pend"] = "competicao"


def _topo_novo(p: dict, mapa: list[dict], prog, set_prog) -> None:
    """Topo no formato do app: cartão da Jornada com o desafio do dia, resumo da unidade atual e atalho do Wallet Game."""
    st.markdown(CSS_NOVO, unsafe_allow_html=True)
    r = JO.resumo(p)
    with st.container(key="jor_hero"):
        st.markdown(html_hero_jornada(ART.mascote(humor=ART.pose_da_area("Jornada"), tamanho=170)), unsafe_allow_html=True)
        lid = _proxima_licao(mapa)
        if lid:
            st.button("Iniciar Desafio", key="jor_iniciar", type="primary", icon=":material/play_arrow:", on_click=_comecar, args=(lid,), width="stretch")
    if r["erros"] > 0:
        st.button(f"Revisar erros ({r['erros']})", key="jor_revisar", type="primary", width="stretch", on_click=_revisar, args=(prog,),
                  help="Refaz os exercícios que você errou antes. Vale XP e ajuda a fixar.")
    st.markdown(NVA.CSS + NVA.html_nivel(r["xp"], JO._jor(p)["xp_dia"]), unsafe_allow_html=True)
    atual = next((u for u in mapa if not u.get("completa")), mapa[0])
    st.markdown(html_unidade_card(atual), unsafe_allow_html=True)
    with st.container(key="jor_wg"):
        st.markdown(html_wallet_jornada(), unsafe_allow_html=True)
        st.button("Jogar", key="jor_jogar", icon=":material/chevron_right:", on_click=_ir_wallet, width="stretch")
    st.markdown("<div class='jor-mapa-t'>Mapa das lições</div>", unsafe_allow_html=True)


def _barra_topo(p: dict, prog, set_prog) -> None:
    r = JO.resumo(p)
    st.markdown(ART.hero("Vamos aprender um pouco hoje?"), unsafe_allow_html=True)
    st.markdown(html_stats(r), unsafe_allow_html=True)
    PLAYER._chave_som(prog, set_prog)
    if r["erros"] > 0:
        st.button(f"Revisar erros ({r['erros']})", key="jor_revisar", type="primary", width="stretch", on_click=_revisar, args=(prog,),
                  help="Refaz os exercícios que você errou antes. Vale XP e ajuda a fixar.")


def aba(prog, set_prog, real_fn=None) -> None:
    """Desenha a trilha ou, com uma lição em andamento, o player. `prog` devolve o progresso normalizado e `set_prog` o grava (educacao_app).
    `real_fn(unidade_id, roteiro)` (opcional, vem de educacao_app) desenha o estudo com dado real no fim da unidade concluída."""
    st.markdown(CSS_BASE, unsafe_allow_html=True)
    st.markdown(CSS_ARTE, unsafe_allow_html=True)
    C._css()
    if st.session_state.get("jor_sessao"):
        PLAYER.tela(prog, set_prog)
        return
    p = prog()
    mapa = JO.mapa(p)
    if not mapa:
        st.markdown(C._msg("A jornada ainda não tem lições.", "info"), unsafe_allow_html=True)
        return
    recente = st.session_state.pop("jor_recente", None)         # anima o ícone da lição recém-concluída uma única vez
    st.markdown(css_icones(mapa, recente), unsafe_allow_html=True)
    _topo_novo(p, mapa, prog, set_prog)
    for u in mapa:
        st.markdown(html_unidade_card(u), unsafe_allow_html=True)
        with st.container(key=f"jor_cena_{u['id']}"):
            anterior = None
            for i, l in enumerate(u["licoes"]):
                pos = ONDA[i % len(ONDA)]
                if anterior is not None:
                    st.markdown(html_conector(anterior[0], pos, anterior[1]), unsafe_allow_html=True)
                cols = st.columns(COLUNAS)
                cols[0].markdown(HTML_MARCADOR, unsafe_allow_html=True)      # marcador usado pelo CSS do zigue-zague
                _no(cols[pos], l)
                anterior = (pos, l["estado"] == "concluida")
        roteiro = JO.estudo_real(u["id"])
        if real_fn and roteiro and u["completa"]:
            st.markdown(html_estudo_real(roteiro), unsafe_allow_html=True)
            if st.toggle("Estudar com um ativo real", key=f"jor_real_{u['id']}"):      # toggle (e não expander): o estudo usa expanders por dentro
                try:
                    real_fn(u["id"], roteiro)
                except Exception as e:                       # dado real nunca derruba a trilha
                    st.markdown(C._msg("Não consegui carregar o estudo com dados reais agora. A trilha continua normal.", "aviso"), unsafe_allow_html=True)
                    try:
                        import banco
                        banco.registrar_erro("jornada_app.estudo_real", e)
                    except Exception:
                        pass
    PLAYER._chave_som(prog, set_prog)                          # chave do som das lições (saiu do topo)
    try:
        LIGA.secao(prog)
    except Exception as e:                                   # a liga é opcional: nunca derruba a trilha
        st.caption("A liga de estudo está indisponível agora.")
        try:
            import banco
            banco.registrar_erro("jornada_app.liga", e)
        except Exception:
            pass
    st.caption("Conteúdo educacional. XP e conquistas premiam só o estudo, nunca operações ou risco.")
