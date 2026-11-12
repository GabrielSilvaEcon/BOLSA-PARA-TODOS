"""Etapa 3 — Player da lição (estilo Duolingo): um exercício por vez, verificação, feedback e tela final com XP.

Fluxo (st.session_state):
  jor_sessao   sessão em andamento (jornada.iniciar_sessao)
  jor_fase     "pergunta" -> "feedback" -> (próxima pergunta ... ) -> "fim"
  jor_ultimo   {"ex": id, "ok": bool} do exercício que acabou de ser respondido
  jor_n        contador que muda a cada pergunta (renova os widgets: ninguém herda a resposta anterior)
  jor_ord      itens já escolhidos no exercício "ordenar"
  jor_resultado  resultado da sessão, mostrado na tela final
  jor_som      nome do efeito sonoro pendente (tocado uma única vez, na próxima vez que a tela for desenhada)
  jor_som_n    contador de sons já tocados (dá chave nova ao áudio: o navegador sempre cria um player novo e toca de novo)
  jor_recente  id da última lição concluída (o mapa anima o ícone dela uma vez); sobrevive a sair()

Regras: nada bloqueia nem tira vidas. Erro volta para o fim da fila e a explicação aparece na hora. A lógica fica em jornada.py;
aqui só existe tela e o encadeamento dos passos. O progresso só é gravado ao terminar a lição (jornada.concluir_sessao).
"""
from __future__ import annotations

import html

import streamlit as st

import educacao as ED
import jornada as JO
import jornada_arte as ART
import moedas_arte as MA
import jornada_conteudo as J
import jornada_icones as IC
import jornada_som as SOM
import jornada_player_ref as REF
import estilo_app as ES

DICA = {"escolha": "Escolha a resposta certa", "completar": "Complete a frase", "vf": "Verdadeiro ou falso?",
        "ordenar": "Toque nos itens na ordem certa", "pares": "Ligue cada item ao seu par"}
CHAVES = ("jor_sessao", "jor_fase", "jor_ultimo", "jor_n", "jor_ord", "jor_resultado", "jor_som")

CSS = """<style>
div[class*="st-key-jor_player"]{max-width:560px;margin:0 auto;}
.jor-top{display:flex;align-items:center;gap:10px;margin:2px 0 14px;}
.jor-top .nome{flex:0 0 auto;max-width:42%;font-weight:800;font-size:.82rem;color:#CFC8EE !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.jor-trilho{flex:1;height:14px;background:#2A2060;border-radius:99px;overflow:hidden;}
.jor-trilho i{display:block;height:100%;background:linear-gradient(90deg,#2DD4A0,#6CF0C8);border-radius:99px;position:relative;overflow:hidden;}
.jor-trilho i.anima{animation:jor-enche .5s ease-out;}
.jor-trilho i.anima:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);transform:translateX(-100%);animation:jor-brilha .7s .1s ease-out;}
.jor-dica{font-size:.78rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#C5B3FF !important;margin:4px 0 6px;}
.jor-q{font-weight:900;font-size:1.28rem;line-height:1.35;color:#F6F3FF !important;margin:0 0 14px;word-break:break-word;}
.jor-q .lacuna{display:inline-block;min-width:64px;border-bottom:3px solid #C5B3FF;margin:0 4px;}
.jor-chips{display:flex;flex-wrap:wrap;gap:8px;min-height:50px;padding:10px;border:2px dashed #3D3182;border-radius:14px;margin:0 0 12px;}
.jor-chip{background:#8B6CFF;color:#fff !important;font-weight:800;font-size:.9rem;border-radius:12px;padding:8px 12px;box-shadow:0 3px 0 #5B3FD6;}
.jor-chip b{opacity:.75;margin-right:6px;}
.jor-vazio{color:#8F86C7 !important;font-size:.9rem;align-self:center;}
.jor-par{font-weight:800;color:#F6F3FF !important;margin:10px 0 4px;}
.jor-fb{border-radius:16px;padding:14px 16px;margin:10px 0 14px;}
.jor-fb.ok{background:#0F3329;border:2px solid #2DD4A0;animation:jor-sobe .28s ease-out;}
.jor-fb.err{background:#3A1630;border:2px solid #FF6B8A;animation:jor-sobe .28s ease-out,jor-treme .45s .05s;}
.jor-fb .t{font-weight:900;font-size:1.1rem;} .jor-fb.ok .t{color:#5FF0C0 !important;} .jor-fb.err .t{color:#FF9DB3 !important;}
.jor-fb .c{margin-top:6px;color:#EDE9FF !important;font-size:.95rem;line-height:1.45;}
.jor-cert{display:flex;align-items:center;gap:10px;margin:8px 0 2px;padding:10px 12px;border-radius:14px;background:#0F3329;border:2px solid #2DD4A0;box-shadow:0 0 0 3px rgba(45,212,160,.15),0 0 18px -6px #2DD4A0;}
.jor-cert i{flex:0 0 28px;height:28px;border-radius:50%;background:#2DD4A0;display:grid;place-items:center;font-style:normal;font-weight:900;color:#06281D !important;-webkit-text-fill-color:#06281D !important;}
.jor-cert span{min-width:0;display:block;} .jor-cert small{display:block;font-size:.7rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#5FF0C0 !important;-webkit-text-fill-color:#5FF0C0 !important;}
.jor-cert b{display:block;font-size:1.02rem;font-weight:900;line-height:1.3;color:#fff !important;-webkit-text-fill-color:#fff !important;overflow-wrap:anywhere;}
.jor-fb .d{margin-top:8px;color:#CFC8EE !important;font-size:.85rem;}
.jor-fim{text-align:center;padding:10px 0 4px;}
.jor-fim{position:relative;}
.jor-fim .medalha{width:96px;height:96px;border-radius:50%;margin:8px auto 12px;display:flex;align-items:center;justify-content:center;background:#FFC94D;box-shadow:0 7px 0 #B98A00;
  animation:jor-pop .6s cubic-bezier(.2,1.4,.4,1) both,jor-brilho 1.2s .55s ease-out;}
.jor-fim .medalha img{width:52px;height:52px;display:block;}
.jor-fim h2{margin:0 0 4px;color:#F6F3FF !important;font-size:1.5rem;font-weight:900;}
.jor-fim p{margin:0;color:#CFC8EE !important;}
.jor-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0;}
.jor-kpi{text-align:center;border-radius:14px;padding:10px 6px;background:#1B1442;border:2px solid #3D3182;animation:jor-sobe .4s ease-out both;}
.jor-kpi:nth-child(1){animation-delay:.25s;} .jor-kpi:nth-child(2){animation-delay:.4s;} .jor-kpi:nth-child(3){animation-delay:.55s;}
.jor-kpi .v{font-weight:900;font-size:1.25rem;color:#F6F3FF !important;} .jor-kpi .l{font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#BDB5E6 !important;}
.jor-kpi.xp{border-color:#FFC94D;} .jor-kpi.xp .v{color:#FFC94D !important;} .jor-kpi.ac{border-color:#2DD4A0;} .jor-kpi.ac .v{color:#2DD4A0 !important;}
.jor-kpi.of{border-color:#FF9B3D;} .jor-kpi.of .v{color:#FF9B3D !important;}
.jor-meta,.jor-conq{animation:jor-pop .5s .9s cubic-bezier(.2,1.4,.4,1) both;}
.jor-conq{margin:0 0 12px;padding:10px 12px;border-radius:12px;background:#2B2150;border:1px solid #FFC94D;color:#FFE08A !important;font-size:.9rem;}
.jor-conq small{display:block;font-size:.68rem;letter-spacing:.07em;text-transform:uppercase;color:#C5B3FF !important;font-weight:800;}
.jor-conq b{font-weight:900;color:#FFE08A !important;}
.jor-kpi .v .jor-cnt,.jor-kpi .v .jor-cnt:before{color:inherit !important;}
.jor-kpi .v,.jor-kpi .v *{-webkit-text-fill-color:currentColor !important;opacity:1 !important;}
.jor-meta{margin:0 0 12px;padding:9px 12px;border-radius:12px;background:#0F3329;border:1px solid #2DD4A0;color:#5FF0C0 !important;font-weight:800;font-size:.9rem;}
/* confete e contagem de XP: só CSS (sem script), então funciona dentro do Streamlit */
.jor-confete{position:absolute;left:0;right:0;top:0;height:0;overflow:visible;pointer-events:none;z-index:2;}
.jor-confete i{position:absolute;top:0;width:8px;height:14px;border-radius:2px;opacity:0;animation:jor-queda 1.9s ease-in forwards;}
@property --v{syntax:'<integer>';inherits:false;initial-value:0;}
.jor-cnt{--v:var(--alvo);counter-reset:jn var(--v);animation:jor-conta 1s .35s ease-out both;}
.jor-cnt:before{content:counter(jn);} .jor-cnt.mais:before{content:"+" counter(jn);}
div[data-testid="stHorizontalBlock"]:has(.jor-tl){flex-wrap:nowrap !important;gap:8px !important;align-items:center !important;}
div[data-testid="stHorizontalBlock"]:has(.jor-tl) > div[data-testid="stColumn"],div[data-testid="stHorizontalBlock"]:has(.jor-tl) > div[data-testid="column"]{min-width:0 !important;}
@keyframes jor-enche{from{width:var(--de)}}
@keyframes jor-brilha{to{transform:translateX(100%)}}
@keyframes jor-sobe{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes jor-treme{10%,90%{transform:translateX(-2px)}20%,80%{transform:translateX(4px)}30%,50%,70%{transform:translateX(-6px)}40%,60%{transform:translateX(6px)}}
@keyframes jor-pop{0%{transform:scale(.2);opacity:0}60%{transform:scale(1.15);opacity:1}100%{transform:scale(1)}}
@keyframes jor-brilho{0%{box-shadow:0 7px 0 #B98A00,0 0 0 0 rgba(255,201,77,.6)}100%{box-shadow:0 7px 0 #B98A00,0 0 0 28px rgba(255,201,77,0)}}
@keyframes jor-queda{0%{transform:translateY(-10px) rotate(0);opacity:1}100%{transform:translateY(280px) rotate(560deg);opacity:0}}
@keyframes jor-conta{from{--v:0}}
div[class*="st-key-jor_som_"]{position:absolute !important;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;}
@media (prefers-reduced-motion:reduce){.jor-trilho i,.jor-trilho i:after,.jor-fb,.jor-fim .medalha,.jor-kpi,.jor-meta,.jor-conq,.jor-cnt{animation:none !important;}.jor-confete{display:none;}}
/* opções como cartões */
div[class*="st-key-jor_r_"] label{width:100%;background:#1B1442;border:2px solid #3D3182;border-radius:14px;padding:12px 14px;margin:0 0 8px;cursor:pointer;}
div[class*="st-key-jor_r_"] label:hover{border-color:#8B6CFF;}
div[class*="st-key-jor_r_"] label:has(input:checked){border-color:#8B6CFF;background:#2A2060;}
div[class*="st-key-jor_oi_"] button{width:100%;border-radius:14px;border:2px solid #3D3182;background:#1B1442;padding:12px 14px;}
div[class*="st-key-jor_oi_"] button:hover{border-color:#8B6CFF;}
/* ---- visual com o Tico ---- */
.jor-dica{display:inline-flex;align-items:center;gap:7px;background:#2A2060;border:1px solid #4B3E99;border-radius:99px;padding:4px 12px 4px 9px;text-transform:none;letter-spacing:0;font-size:.82rem;color:#E4DCFF !important;margin:6px 0 10px;}
.jor-dica img{width:16px;height:16px;display:block;}
.jor-ask{display:flex;align-items:flex-end;gap:6px;margin:0 0 6px;}
.jor-tico2{flex:0 0 104px;animation:jor-tico2 3.2s ease-in-out infinite;transform-origin:50% 100%;}
.jor-tico2 svg{display:block;}
.jor-ask .jor-q{position:relative;flex:1;margin:0 0 20px;background:#fff;color:#2A1F5E !important;border-radius:18px;padding:12px 15px;font-size:1.06rem;box-shadow:0 4px 0 rgba(0,0,0,.3);}
.jor-ask .jor-q:before{content:"";position:absolute;left:-8px;bottom:16px;border:8px solid transparent;border-left:0;border-right-color:#fff;}
.jor-ask .lacuna{border-bottom-color:#5B3FD6;}
@keyframes jor-tico2{0%,100%{transform:rotate(-2deg)}50%{transform:translateY(-3px) rotate(2deg)}}
.jor-trilho{height:16px;box-shadow:inset 0 2px 0 rgba(0,0,0,.25);}
.jor-trilho i:before{content:"";position:absolute;left:6px;right:6px;top:3px;height:4px;border-radius:99px;background:rgba(255,255,255,.4);}
.jor-fb{display:flex;align-items:center;gap:12px;box-shadow:0 4px 0 rgba(0,0,0,.3);}
.jor-fb .jor-fbt{flex:0 0 92px;} .jor-fb .jor-fbt svg{display:block;} .jor-fb .jor-fbc{flex:1;min-width:0;}
/* opções viram cartões com letra */
div[class*="st-key-jor_r_"] [role="radiogroup"]{display:flex !important;flex-direction:column;gap:10px;counter-reset:op;}
div[class*="st-key-jor_r_"] label{display:flex !important;align-items:center;gap:12px;width:100% !important;box-sizing:border-box;margin:0 !important;counter-increment:op;box-shadow:0 4px 0 #150F38;transition:transform .08s,box-shadow .08s,border-color .15s;}
div[class*="st-key-jor_r_"] label > div:first-child{display:none !important;}
div[class*="st-key-jor_r_"] label:before{content:counter(op,upper-alpha);flex:0 0 32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:.9rem;color:#C5B3FF;background:#110C2E;border:2px solid #3D3182;}
div[class*="st-key-jor_r_"] label:active{transform:translateY(3px);box-shadow:0 1px 0 #150F38;}
div[class*="st-key-jor_r_"] label:has(input:checked){border-color:#8B6CFF;background:linear-gradient(135deg,#3A2A86,#2A2060);box-shadow:0 4px 0 #5B3FD6,0 0 0 4px rgba(139,108,255,.22);}
div[class*="st-key-jor_r_"] label:has(input:checked):before{background:#8B6CFF;border-color:#C5B3FF;color:#fff;}
@media (prefers-reduced-motion:reduce){.jor-tico2{animation:none !important;}}
/* ---- ajuste para celular: compacto, opções 100%, sem cortar atrás da barra inferior ---- */
div[class*="st-key-jor_player"]{padding-bottom:84px;overflow-wrap:anywhere;}
div[class*="st-key-jor_player"] [data-testid="stVerticalBlock"]{gap:.55rem !important;}
.jor-top{margin:0 0 8px;}
.jor-dica{margin:2px 0 6px;}
.jor-ask{gap:4px;margin:0 0 2px;}
.jor-tico2{flex:0 0 84px;}
.jor-tico2 svg{width:60px;height:auto;}
.jor-tico2 img{width:84px !important;height:84px !important;}
.jor-ask .jor-q{min-width:0;margin:0 0 12px;padding:10px 13px;font-size:1.02rem;line-height:1.3;overflow-wrap:anywhere;}
div[class*="st-key-jor_r_"],div[class*="st-key-jor_r_"] [data-testid="stRadio"],div[class*="st-key-jor_r_"] [role="radiogroup"]{width:100% !important;max-width:100% !important;}
div[class*="st-key-jor_r_"] [role="radiogroup"]{gap:8px !important;}
div[class*="st-key-jor_r_"] label{min-width:0;padding:10px 12px !important;}
div[class*="st-key-jor_r_"] label p,div[class*="st-key-jor_r_"] label div{min-width:0;overflow-wrap:anywhere;word-break:break-word;white-space:normal;}
div[class*="st-key-jor_oi_"] button{min-height:44px;overflow-wrap:anywhere;white-space:normal;}
html body .stApp.stApp div[class*="st-key-jor_sv"] button{min-height:46px !important;padding-top:.45rem !important;padding-bottom:.45rem !important;}
html body .stApp.stApp div[class*="st-key-jor_ss"] button{min-height:36px !important;padding:.2rem .7rem !important;font-size:.82rem !important;background:transparent !important;border:0 !important;box-shadow:none !important;color:#BDB5E6 !important;width:auto !important;}
div[class*="st-key-jor_player"] [data-testid="stExpander"] summary{min-height:36px !important;padding:.3rem .7rem !important;font-size:.85rem;}
div[class*="st-key-jor_player"] [data-testid="stExpander"] [data-testid="stExpanderDetails"]{padding:.3rem .7rem .5rem !important;}
/* reforço: sem bolinha do rádio, largura total garantida e botão Sair discreto */
html body .stApp.stApp div[class*="st-key-jor_r_"] label{display:flex !important;width:100% !important;max-width:100% !important;flex:1 1 100% !important;}
html body .stApp.stApp div[class*="st-key-jor_r_"] label > div:not(:has(p)):not(:has(span)){display:none !important;}
html body .stApp.stApp div[class*="st-key-jor_r_"] label [data-testid="stMarkdownContainer"]{flex:1;min-width:0;}
html body .stApp.stApp div[class*="st-key-jor_r_"] label input{position:absolute;opacity:0;width:0;height:0;}
html body .stApp.stApp div[class*="st-key-jor_ss"] button,html body .stApp.stApp div[class*="st-key-jor_ss"] button[kind]{background:transparent !important;background-image:none !important;border:0 !important;box-shadow:none !important;min-height:34px !important;padding:.2rem .6rem !important;color:#BDB5E6 !important;font-size:.82rem !important;width:auto !important;}
/* lição como um cartão centralizado */
html body .stApp.stApp div[class*="st-key-jor_player"]{background:linear-gradient(180deg,#1B1442,#150F38);border:2px solid #3D3182;border-radius:22px;box-shadow:0 6px 0 #0E0A28;padding:14px 14px 16px !important;margin:6px auto 96px !important;width:100% !important;max-width:560px !important;box-sizing:border-box;}
html body .stApp.stApp div[class*="st-key-jor_player"] > div[data-testid="stElementContainer"],html body .stApp.stApp div[class*="st-key-jor_r_"] [data-testid="stRadio"] > div{width:100% !important;}
html body .stApp.stApp div[class*="st-key-jor_r_"] [role="radiogroup"]{display:flex !important;flex-direction:column !important;align-items:stretch !important;width:100% !important;}
html body .stApp.stApp div[class*="st-key-jor_r_"] [role="radiogroup"] > *{width:100% !important;max-width:100% !important;align-self:stretch !important;box-sizing:border-box;}
/* alternativas A-D sempre na largura toda (a estrutura interna do rádio mudou no Streamlit novo) e botões Continuar com respiro do cartão de resposta */
html body .stApp.stApp div[class*="st-key-jor_r_"] div:has(label){width:100% !important;max-width:100% !important;}
html body .stApp.stApp div[class*="st-key-jor_r_"] div:has(> label){display:flex !important;flex-direction:column !important;align-items:stretch !important;gap:10px !important;}
html body .stApp.stApp div[class*="st-key-jor_r_"] label > *:not(:has(p)):not([data-testid="stMarkdownContainer"]){display:none !important;}
html body .stApp.stApp div[class*="st-key-jor_sc"],html body .stApp.stApp div[class*="st-key-jor_sf"]{margin-top:16px !important;}
html body .stApp.stApp div[class*="st-key-jor_player"] .jor-fb{margin-bottom:6px !important;}
html body .stApp.stApp div[class*="st-key-jor_ss"]{display:flex;justify-content:center;}
html body .stApp.stApp div[class*="st-key-jor_player"] .jor-ask .jor-q{box-shadow:0 3px 0 rgba(0,0,0,.25);}
</style>"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _ss():
    return st.session_state


# ------------------------------------------------------------------ pedaços de HTML (puros, testáveis sem Streamlit)
def html_barra(pct: float, nome: str = "", de: float | None = None) -> str:
    """Barra de progresso da lição. Com `de` (fração anterior) menor que `pct`, a barra enche animada de `de` até `pct`."""
    pct = max(0.0, min(1.0, float(pct)))
    anima = de is not None and 0.0 <= float(de) < pct
    extra = f" class='anima' style='width:{pct * 100:.0f}%;--de:{max(0.0, float(de)) * 100:.0f}%'" if anima else f" style='width:{pct * 100:.0f}%'"
    return f"<div class='jor-top'><div class='nome'>{_e(nome)}</div><div class='jor-trilho'><i{extra}></i></div></div>"


ICONE_TIPO = {"escolha": "alvo", "completar": "livro", "vf": "escudo", "ordenar": "grafico", "pares": "estrela"}


def html_pergunta(ex: dict, tico: bool = True) -> str:
    """Pílula com o tipo do exercício + a pergunta num balão do Tico (tico=False: só o texto, usado na tela de feedback)."""
    texto = _e(ex["pergunta"])
    if ex["tipo"] == "completar":
        texto = texto.replace("___", "<span class='lacuna'></span>")
    dica = f"<div class='jor-dica'><img src='{IC.uri(ICONE_TIPO.get(ex['tipo'], 'estrela'), '#FFC94D')}' alt=''>{_e(DICA[ex['tipo']])}</div>"
    if not tico:
        return f"{dica}<div class='jor-q'>{texto}</div>"
    return f"{dica}<div class='jor-ask'><div class='jor-tico2'>{ART.mascote(humor='pensa', tamanho=104)}</div><div class='jor-q'>{texto}</div></div>"


def html_chips(escolhidos: list[str], total: int) -> str:
    if not escolhidos:
        return f"<div class='jor-chips'><span class='jor-vazio'>Toque nos itens abaixo, do primeiro ao último ({total}).</span></div>"
    return "<div class='jor-chips'>" + "".join(f"<span class='jor-chip'><b>{i}</b>{_e(x)}</span>" for i, x in enumerate(escolhidos, 1)) + "</div>"


def html_feedback(ok: bool, ex: dict) -> str:
    if ok:
        return (f"<div class='jor-fb ok'><div class='jor-fbt'>{ART.mascote(humor='festa', tamanho=92)}</div>"
                f"<div class='jor-fbc'><div class='t'>Correto!</div><div class='c'>{_e(ex['explicacao'])}</div></div></div>")
    return (f"<div class='jor-fb err'><div class='jor-fbt'>{ART.mascote(humor='triste', tamanho=92)}</div><div class='jor-fbc'><div class='t'>Não foi dessa vez</div>"
            f"<div class='jor-cert' role='note'><i aria-hidden='true'>✓</i><span><small>Resposta certa</small><b>{_e(JO.resposta_certa_texto(ex))}</b></span></div>"
            f"<div class='c'>{_e(ex['explicacao'])}</div>"
            f"<div class='d'>Esta pergunta volta no fim da lição para você tentar de novo.</div></div></div>")


CORES_CONFETE = ("#FFC94D", "#2DD4A0", "#8B6CFF", "#FF6B8A", "#6CF0C8", "#FF9B3D")


def html_confete(n: int = 22) -> str:
    """Chuva de confete só em CSS. Posições e atrasos são determinísticos (sem aleatoriedade), então o HTML é testável."""
    pecas = "".join(f"<i style='left:{(i * 37) % 97 + 1}%;background:{CORES_CONFETE[i % len(CORES_CONFETE)]};animation-delay:{(i % 7) * 0.09:.2f}s;"
                    f"animation-duration:{1.6 + (i % 5) * 0.2:.1f}s'></i>" for i in range(n))
    return f"<div class='jor-confete' aria-hidden='true'>{pecas}</div>"


def html_contagem(valor: int, mais: bool = False) -> str:
    """Número que 'conta' de 0 até o valor (animação CSS). Sem suporte do navegador, mostra direto o valor final."""
    v = int(valor)
    return f"<span class='jor-cnt{' mais' if mais else ''}' style='--alvo:{v}' role='img' aria-label='{'+' if mais else ''}{v}'></span>"


def html_conquistas(titulos: list[str]) -> str:
    return "".join(f"<div class='jor-conq'><div style='display:flex;align-items:center;gap:10px'>{ART.mascote(humor='conquistas', tamanho=48)}<div><small>Conquista desbloqueada</small><br><b>{_e(t)}</b></div></div></div>" for t in titulos)


def html_moedas(n: int) -> str:
    """Faixa 'Você ganhou N TickerCoins' (vazia se não houve crédito novo)."""
    if n <= 0:
        return ""
    faixa = f"<div class='jor-meta' style='background:#2A2058;color:#FFD66B;border:1px solid #F2B84B66'>{MA.img('tc', 22)} +{n} TickerCoins</div>"
    try:                                     # recompensa em ficha animada (fx_arte); a faixa simples é a reserva
        import fx_arte as FX
        return FX.CSS + FX.html_recompensa("Você ganhou moedas!", [{"sprite": "tc", "valor": f"+{int(n)}", "rotulo": "TickerCoins"}],
                                           "", "comum", animar=FX.animar_padrao(_ss()))
    except Exception:
        return faixa


def html_fim(r: dict) -> str:
    if r.get("revisao"):
        titulo, sub = "Revisão concluída!", "Você revisou o que tinha errado antes."
    elif r.get("perfeita"):
        titulo, sub = "Lição perfeita!", "Nenhum erro de primeira. Bônus de XP garantido."
    else:
        titulo, sub = "Lição concluída!", "Os erros ficam na sua lista de revisão."
    of = int(r.get("ofensiva", 0))
    meta = "<div class='jor-meta'>Meta de hoje batida!</div>" if r.get("meta_atingida") else ""
    festa = html_confete() if (r.get("perfeita") or r.get("meta_nova")) and not r.get("revisao") else ""
    try:
        import nivel_app as _nva
        nv = _nva.CSS + _nva.celebracao_html(int(r.get("xp_antes", 0)), int(r.get("xp_depois", 0)))
        nv = nv if "Você subiu" in nv else ""
    except Exception:
        nv = ""
    return (f"<div class='jor-fim'>{festa}<div class='medalha'><img src='{IC.uri('estrela', '#5A3B00')}' alt=''></div><h2>{_e(titulo)}</h2><p>{_e(sub)}</p></div>"
            f"<div class='jor-kpis'><div class='jor-kpi xp'><div class='v'>{html_contagem(int(r['xp']), True)}</div><div class='l'>XP</div></div>"
            f"<div class='jor-kpi ac'><div class='v'>{html_contagem(int(r['acertos_primeira']))}/{int(r['total'])}</div><div class='l'>De primeira</div></div>"
            f"<div class='jor-kpi of'><div class='v'>{html_contagem(of)}</div><div class='l'>{'Dia seguido' if of == 1 else 'Dias seguidos'}</div></div></div>"
            f"{meta}{nv}{html_moedas(int(r.get('tc') or 0))}{html_conquistas(list(r.get('conquistas_novas') or []))}")


# ------------------------------------------------------------------ som
def _tocar(nome: str) -> None:
    """Toca um efeito (autoplay, invisível). Qualquer falha é ignorada: o app continua funcionando, só sem som."""
    try:
        if not SOM.existe(nome):
            return
        n = _ss().get("jor_som_n", 0) + 1
        _ss()["jor_som_n"] = n
        with st.container(key=f"jor_som_{n}"):                    # chave nova a cada som: o navegador monta um player novo e toca
            st.audio(SOM.wav(nome), format="audio/wav", autoplay=True)
    except Exception:
        pass


def _som_pendente(ligado: bool) -> None:
    """Toca (uma vez) o som que a última ação deixou pendente. Com o som desligado, só descarta."""
    nome = _ss().pop("jor_som", None)
    if nome and ligado:
        _tocar(nome)


def _mudar_som(prog, set_prog) -> None:
    set_prog(JO.definir_som(prog(), bool(_ss().get("jor_som_sw", True))))


def _chave_som(prog, set_prog) -> None:
    """Botão 'Som' (ligado/desligado), gravado na conta. O estado do widget sempre parte do que está salvo."""
    _ss()["jor_som_sw"] = JO.som_ligado(prog())
    st.toggle("Som", key="jor_som_sw", on_change=_mudar_som, args=(prog, set_prog), help="Liga ou desliga os efeitos sonoros da Jornada. Fica salvo na sua conta.")


# ------------------------------------------------------------------ ações (callbacks)
def iniciar(licao_id: str) -> None:
    """Começa uma lição: zera o estado do player e guarda a sessão. Id inexistente não faz nada."""
    s = JO.iniciar_sessao(licao_id)
    if s:
        sair()
        _ss().update({"jor_sessao": s, "jor_fase": "pergunta", "jor_n": 0, "jor_ord": []})


def iniciar_revisao(p: dict) -> None:
    """Começa uma revisão com os exercícios errados antes. Sem erros, não faz nada."""
    s = JO.iniciar_revisao(p)
    if s:
        sair()
        _ss().update({"jor_sessao": s, "jor_fase": "pergunta", "jor_n": 0, "jor_ord": []})


def iniciar_sessao(s: dict | None) -> None:
    """Começa uma sessão já montada (ex.: desafio temático da área Jogar, ver jogar.py). Sessão vazia não faz nada."""
    if s and s.get("fila"):
        sair()
        _ss().update({"jor_sessao": s, "jor_fase": "pergunta", "jor_n": 0, "jor_ord": []})


def sair() -> None:
    for k in CHAVES:
        _ss().pop(k, None)


def _verificar(eid: str, resposta) -> None:
    s = _ss().get("jor_sessao")
    if not s or JO.exercicio_atual(s) is None or JO.exercicio_atual(s)["id"] != eid:      # clique atrasado/duplo: ignora
        return
    ok, s2 = JO.responder(s, resposta)
    _ss().update({"jor_sessao": s2, "jor_fase": "feedback", "jor_ultimo": {"ex": eid, "ok": ok, "de": JO.progresso_sessao(s)}, "jor_som": SOM.som_da_resposta(ok)})


def _moedas(r: dict, antes: set, p) -> int:
    """TickerCoins ganhas nesta sessão (0 se visitante, desligado ou já pagas antes). Nunca atrapalha o fim da lição; XP não muda."""
    try:
        conta = _ss().get("_conta")
        if not conta:
            return 0
        import tickercoins as TC
        novas = [c["id"] for c in ED.conquistas(p) if c["ok"] and c["id"] not in antes]
        linhas = TC.recompensar_sessao(conta["id"], {**r, "ok": True}, novas)
        if linhas:
            _ss().pop("_tc_saldo", None)                         # o cabeçalho relê o saldo
        return sum(int(x["delta"]) for x in linhas)
    except Exception:
        return 0


def _continuar(prog, set_prog) -> None:
    s = _ss().get("jor_sessao")
    if not s:
        return
    if JO.terminada(s):
        antes = {c["id"] for c in ED.conquistas(prog()) if c["ok"]}
        p, r = JO.concluir_sessao(prog(), s)
        set_prog(p)
        r["conquistas_novas"] = [c["titulo"] for c in ED.conquistas(p) if c["ok"] and c["id"] not in antes]
        r["tc"] = _moedas(r, antes, p)
        _ss().update({"jor_resultado": r, "jor_fase": "fim", "jor_som": SOM.som_do_resultado(r)})
        if r.get("licao"):
            _ss()["jor_recente"] = r["licao"]                  # o mapa anima o ícone dessa lição uma vez
    else:
        _ss().update({"jor_fase": "pergunta", "jor_n": _ss().get("jor_n", 0) + 1, "jor_ord": []})


def _add_item(item: str) -> None:
    ordem = list(_ss().get("jor_ord") or [])
    if item not in ordem:
        ordem.append(item)
    _ss()["jor_ord"] = ordem


def _desfazer() -> None:
    _ss()["jor_ord"] = list(_ss().get("jor_ord") or [])[:-1]


# ------------------------------------------------------------------ entradas por tipo (devolvem a resposta pronta ou None se incompleta)
def _entrada(ex: dict, n: int):
    t, eid = ex["tipo"], ex["id"]
    if t in ("escolha", "completar"):
        esc = st.radio("Resposta", ex["opcoes"], index=None, key=f"jor_r_{eid}_{n}", label_visibility="collapsed")
        return None if esc is None else ex["opcoes"].index(esc)
    if t == "vf":
        esc = st.radio("Resposta", ["Verdadeiro", "Falso"], index=None, key=f"jor_r_{eid}_{n}", label_visibility="collapsed")
        return None if esc is None else esc == "Verdadeiro"
    if t == "ordenar":
        return _entrada_ordenar(ex, n)
    return _entrada_pares(ex, n)


def _entrada_ordenar(ex: dict, n: int):
    ordem = list(_ss().get("jor_ord") or [])
    todos = JO.embaralhar_itens(ex)
    st.markdown(html_chips(ordem, len(todos)), unsafe_allow_html=True)
    for i, item in enumerate(todos):
        if item not in ordem:
            st.button(item, key=f"jor_oi_{n}_{i}", on_click=_add_item, args=(item,), width="stretch")
    if ordem:
        st.button("Desfazer último", key=f"jor_od_{n}", on_click=_desfazer, icon=":material/undo:")
    return ordem if len(ordem) == len(todos) else None


def _entrada_pares(ex: dict, n: int):
    direitas = JO.embaralhar_pares(ex)
    escolhas = []
    for i, (a, _b) in enumerate(ex["pares"]):
        st.markdown(f"<div class='jor-par'>{_e(a)}</div>", unsafe_allow_html=True)
        escolhas.append(st.selectbox(a, direitas, index=None, placeholder="Escolha o par", key=f"jor_pa_{ex['id']}_{n}_{i}", label_visibility="collapsed"))
    if any(e is None for e in escolhas):
        return None
    return {a: e for (a, _b), e in zip(ex["pares"], escolhas)}


# ------------------------------------------------------------------ telas
def _nome_sessao(s: dict) -> str:
    if s.get("nome"):
        return str(s["nome"])
    return J.LICAO_POR_ID[s["licao"]]["titulo"] if s.get("licao") in J.LICAO_POR_ID else "Revisão"


def tela(prog, set_prog) -> None:
    """Desenha a fase atual. `prog` devolve o progresso; `set_prog` grava (só chamado ao terminar a lição)."""
    st.markdown(CSS + REF.css(), unsafe_allow_html=True)
    s, fase = _ss().get("jor_sessao"), _ss().get("jor_fase", "pergunta")
    if not s:
        return
    with st.container(key="jor_player"):
        if fase == "fim":
            r = _ss().get("jor_resultado")
            if not r:
                sair()
                st.rerun()
                return
            st.markdown(html_fim(r), unsafe_allow_html=True)
            _som_pendente(JO.som_ligado(prog()))
            st.button("Continuar", key="jor_sf", type="primary", width="stretch", on_click=sair)
            return
        ult = _ss().get("jor_ultimo") or {}
        de = ult.get("de") if fase == "feedback" else None            # só anima a barra logo depois de responder
        if fase == "feedback":
            ex = J.EX_POR_ID.get(ult.get("ex"))
            if ex is None:
                sair()
                st.rerun()
                return
            ok = bool(ult.get("ok"))
            st.markdown(REF.css_resposta(ok), unsafe_allow_html=True)
            _som_pendente(JO.som_ligado(prog()))
            xp = JO.XP_REVISAO if s.get("revisao") else JO.XP_LICAO
            st.markdown(REF.html_resposta(ok, ex, s, xp), unsafe_allow_html=True)
            st.button("Continuar", key=f"jor_sc_{'ok' if ok else 'err'}", type="primary", width="stretch", on_click=_continuar, args=(prog, set_prog))
            st.markdown(REF.html_dica(ok, ex["id"]), unsafe_allow_html=True)
            return
        st.markdown(ES.css_voltar("jor_voltar_q"), unsafe_allow_html=True)
        bv, bt = st.columns([1, 6], vertical_alignment="center")
        bv.button("Voltar", key="jor_voltar_q", icon=":material/arrow_back:", on_click=sair, help="Sair da lição")
        bt.markdown(REF.html_topo(_nome_sessao(s), s), unsafe_allow_html=True)
        st.markdown(REF.html_trilho(JO.progresso_sessao(s), de), unsafe_allow_html=True)
        _som_pendente(JO.som_ligado(prog()))
        ex = JO.exercicio_atual(s)
        if ex is None:                                       # sessão sem exercício restante: fecha direto
            _continuar(prog, set_prog)
            st.rerun()
            return
        n = _ss().get("jor_n", 0)
        st.markdown(REF.html_pergunta(ex, DICA[ex["tipo"]]), unsafe_allow_html=True)
        resposta = _entrada(ex, n)
        st.button("Verificar", key="jor_sv", type="primary", width="stretch", disabled=resposta is None, on_click=_verificar, args=(ex["id"], resposta),
                  icon=":material/check:")
        rodape, chave = st.columns([3, 2], vertical_alignment="center")
        with rodape:
            st.button("Sair da lição", key="jor_ss", on_click=sair, icon=":material/close:")
        with chave:
            _chave_som(prog, set_prog)
