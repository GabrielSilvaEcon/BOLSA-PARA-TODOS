"""Seção "Notícias do Mercado" da tela inicial: carrossel de manchetes reais (mesmas fontes da Central de notícias). Só leitura.

- Com uma leitura da Central já feita na sessão, usa os acontecimentos dela (inclui a carteira da pessoa).
- Sem leitura, busca só as fontes gerais (nenhum dado pessoal sai do app) e guarda o resultado 10 min na sessão.
- Foto só quando já existe (ou dentro do limite de fotos do plano); sem foto o cartão mostra um bloco colorido. Nada é inventado: sem notícias, o cartão diz isso.
"""
from __future__ import annotations

import html
import time

import streamlit as st

import noticias_app as NA
import noticias_eventos as N
import noticias_foto as NF
import intel as I

MAX_CARTOES = 5
VALIDADE_S = 600
_COR = {"positivo": "#3DDC97", "negativo": "#FF6B6B", "incerto": "#F2B84B", "neutro": "#8EA2FF"}
_ICONE = ("<svg width='34' height='34' viewBox='0 0 24 24' fill='none' stroke='#8EA2FF' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
          "<path d='M4 5h13v14H6a2 2 0 0 1-2-2V5z'/><path d='M17 9h3v8a2 2 0 0 1-2 2'/><path d='M7 9h7M7 12h7M7 15h4'/></svg>")


def _e(t) -> str:
    return html.escape(str(t if t is not None else ""), quote=True)


def grupos_home(n: int = MAX_CARTOES) -> list[dict]:
    """Os `n` acontecimentos mais relevantes (sem os desatualizados). Vazio se não deu para buscar."""
    ss = st.session_state
    res = NA.leitura()
    if res and res.get("grupos"):
        grupos = res["grupos"]
    else:
        c = ss.get("hn_cache")
        if c and time.time() - c[0] < VALIDADE_S:
            grupos = c[1]
        else:
            brutas, _ = NA.coletar_noticias([])
            grupos = N.agrupar_acontecimentos(N.processar(brutas, "", NA._agora()))
            ss["hn_cache"] = (time.time(), grupos)
    top = sorted([g for g in grupos if not g.get("desatualizada") and g.get("titulo")],
                 key=lambda x: (-x.get("relevancia", 0), x.get("ultima_publicacao") or ""))[:max(1, min(n, NA._lim("noticias_cartoes")))]
    if top and NA._lim("noticias_fotos") > 0:
        try:
            NF.pre_carregar([g for g in top if not g.get("imagem")], limite=len(top), tempo=4.0)
        except Exception:
            pass
        for g in top:
            NF.foto_do_grupo(g)
    return top


def cartao_html(g: dict) -> str:
    cor = _COR.get(g.get("sentimento_grupo") or g.get("sentimento"), _COR["neutro"])
    img = N.imagem_segura(g.get("imagem"))
    foto = (f"<div class='hn-f'><img src='{_e(img)}' alt='' loading='lazy' decoding='async' referrerpolicy='no-referrer' "
            "onerror=\"this.parentNode.classList.add('off');this.remove()\"></div>") if img else "<div class='hn-f off'></div>"
    idade = NA.idade_txt(g.get("ultima_publicacao") or g.get("publicada_em"))
    meta = f"{idade[:1].upper()}{idade[1:]} • {g.get('fonte') or 'Fonte n/d'}"
    url = I.url_segura(g.get("url"))
    corpo = f"{foto}<div class='hn-t'><b>{_e(g['titulo'])}</b><span>{_e(meta)}</span></div>"
    if url:
        return f"<a class='hn-c' style='--ac:{cor}' href='{_e(url)}' target='_blank' rel='noopener noreferrer nofollow'>{corpo}</a>"
    return f"<div class='hn-c' style='--ac:{cor}'>{corpo}</div>"


def secao(liberado: bool, ir) -> None:
    """Desenha a seção. `liberado`: a pessoa pode abrir a Central de notícias no plano atual (senão a seção nem aparece). `ir(destino)`: navega."""
    if not liberado:
        return
    try:
        top = grupos_home()
    except Exception:
        top = []
    st.markdown("<style>" + _CSS + "</style>", unsafe_allow_html=True)
    with st.container(key="in_news"):
        with st.container(key="in_news_h"):
            st.markdown(f"<div class='hn-h'>{_ICONE}<b>Notícias do Mercado</b></div>", unsafe_allow_html=True)
            st.button("Ver todas  ›", key="in_news_todas", type="tertiary", on_click=ir, args=("noticias",))
        if top:
            st.markdown("<div class='hn-car'>" + "".join(cartao_html(g) for g in top) + "</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='hn-vazio'>Não consegui carregar as manchetes agora. Toque em <b>Ver todas</b> para tentar de novo.</div>", unsafe_allow_html=True)


_Q = "html body .stApp.stApp.stApp"
_CSS = f"""
{_Q} .st-key-in_news{{margin-top:16px;padding:12px !important;border-radius:24px;gap:.6rem !important;
  background:linear-gradient(160deg,#17154F,#101440 80%);border:1.5px solid rgba(120,150,255,.35);box-shadow:0 4px 0 rgba(0,0,0,.3)}}
{_Q} .st-key-in_news_h{{display:flex !important;flex-direction:row !important;align-items:center !important;justify-content:space-between !important;gap:8px !important;flex-wrap:nowrap !important}}
{_Q} .st-key-in_news_h>[data-testid="stElementContainer"]{{width:auto !important;min-width:0}}
.hn-h{{display:flex;align-items:center;gap:10px;color:#fff !important;font-size:clamp(1.05rem,4.4vw,1.35rem)}}
.hn-h b{{font-weight:800}}
{_Q} .st-key-in_news_h button{{min-height:40px !important;padding:0 6px !important;background:transparent !important;border:0 !important;box-shadow:none !important}}
{_Q} .st-key-in_news_h button :is(p,span){{color:#8EA2FF !important;-webkit-text-fill-color:#8EA2FF !important;font-weight:700 !important;font-size:.92rem !important;white-space:nowrap}}
.hn-car{{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:6px;-webkit-overflow-scrolling:touch;scrollbar-width:none}}
.hn-car::-webkit-scrollbar{{display:none}}
.hn-c{{flex:0 0 min(86%,340px);scroll-snap-align:start;display:flex;gap:10px;align-items:center;box-sizing:border-box;padding:10px;border-radius:18px;text-decoration:none !important;
  background:rgba(255,255,255,.04);border:1px solid color-mix(in srgb,var(--ac) 40%,transparent);border-left:4px solid var(--ac)}}
.hn-f{{flex:0 0 84px;height:84px;border-radius:12px;overflow:hidden;background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 45%,#1B1442),#1B1442)}}
.hn-f img{{width:100%;height:100%;object-fit:cover;display:block}}
.hn-t{{min-width:0;display:flex;flex-direction:column;gap:6px}}
.hn-t b{{color:#fff !important;font-size:.95rem;line-height:1.25;font-weight:700;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.hn-t span{{color:#B9B3E6 !important;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
@media (min-width:760px){{.hn-c{{flex-basis:min(46%,380px)}}}}
.hn-vazio{{padding:12px 4px;color:#CFCBFF !important;font-size:.92rem}}
"""
