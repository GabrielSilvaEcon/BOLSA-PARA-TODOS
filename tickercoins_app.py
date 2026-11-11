"""Telas do TickerCoins: Economia Ticker (saldo, Recompensas, Loja e Extrato numa página global), chip do cabeçalho e seção do painel admin.
Toda regra e todo saldo ficam em tickercoins.py (servidor); aqui só se desenha e se chama. O cliente nunca envia quantidades."""
from __future__ import annotations

import estilo_app as ES
import html
import time
import uuid

import streamlit as st

import banco
import planos
import moedas_arte as MA
import loja_aparencia as LA
import loja_catalogo as LC
import loja_vitrine as VT
import jornada_icones as IC
import arte_tickerhunters as AT
import visual_loja as VL
from datetime import date, datetime, timedelta, timezone
import tickercoins as TC
import usuarios

CSS = """<style>
html body .stApp.stApp .tc-saldo{background:linear-gradient(135deg,#3A2A75,#1E1747);border:1px solid #F2B84B55;border-radius:20px;padding:18px;text-align:center;margin:6px 0 12px;}
html body .stApp.stApp .tc-saldo .v{font-size:2.4rem;font-weight:900;color:#FFD66B;line-height:1.1;}
html body .stApp.stApp .tc-saldo .l{color:#CFC8EE;font-size:.85rem;margin-top:2px;}
html body .stApp.stApp .tc-chip{display:inline-flex;align-items:center;gap:6px;background:#2A2058;border:1px solid #F2B84B66;border-radius:999px;padding:4px 12px;color:#FFD66B;font-weight:800;font-size:.9rem;}
html body .stApp.stApp .tc-card{background:#241C4D;border:1px solid #3B3170;border-radius:16px;padding:12px 14px;margin:6px 0;}
html body .stApp.stApp .tc-card .t{font-weight:800;color:#F6F3FF;}
html body .stApp.stApp .tc-card .d{color:#CFC8EE;font-size:.85rem;margin-top:2px;}
html body .stApp.stApp .tc-card .m{color:#9C94C9;font-size:.78rem;margin-top:4px;}
html body .stApp.stApp .tc-pos{color:#3DDC97;font-weight:800;}
html body .stApp.stApp .tc-neg{color:#FF6B8A;font-weight:800;}
html body .stApp.stApp .tc-pre{border-style:dashed;opacity:.9;}
html body .stApp.stApp .tc-aviso{color:#9C94C9;font-size:.78rem;margin-top:10px;}
</style>"""


def _vazio(pose: str, titulo: str, texto: str) -> str:
    """Estado vazio com o Caramelo (decorativo): cartão centralizado, sem animação."""
    return (f"<div class='tc-card' style='text-align:center;padding:16px 14px'>{AT.img(AT.pose(pose), 72)}"
            f"<div class='t' style='margin-top:6px'>{_e(titulo)}</div><div class='d'>{_e(texto)}</div></div>")


def _e(x) -> str:
    return html.escape(str(x))


def _conta() -> dict | None:
    return usuarios.usuario()


def _plano() -> str:
    c = _conta()
    return planos.plano_de(c["email"], c["papel"]) if c else "visitante"


def _fmt(iso) -> str:
    d = TC._de_iso(iso)
    return d.astimezone(TC.timezone(TC.timedelta(hours=-3))).strftime("%d/%m %H:%M") if d else ""


def _sinal(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def saldo_atual(forcar: bool = False) -> int | None:
    """Saldo da conta logada (None se visitante ou sem banco). Cache de 30 s na sessão para o cabeçalho não consultar o banco
    a cada clique; `esquecer_saldo()` zera o cache depois de compra ou recompensa. Nunca levanta erro."""
    try:
        c = _conta()
        if not c:
            return None
        ss = st.session_state
        cache = ss.get("_tc_saldo")
        if not forcar and cache and cache[0] == c["id"] and time.time() - cache[1] < 30:
            return cache[2]
        v = TC.saldo(c["id"])
        ss["_tc_saldo"] = (c["id"], time.time(), v)
        return v
    except Exception:
        return None


def esquecer_saldo() -> None:
    st.session_state.pop("_tc_saldo", None)


def _precisa_login() -> bool:
    if _conta():
        return False
    st.markdown("<div class='tc-card'><div class='t'>Entre na sua conta</div><div class='d'>Seu saldo de TickerCoins fica salvo na sua conta. "
                "Entre ou crie uma conta gratuita para ganhar e usar moedas.</div></div>", unsafe_allow_html=True)
    return True


def _banco_ok() -> bool:
    ok, motivo = TC.disponivel()
    if not ok:
        st.markdown(f"<div class='tc-card'><div class='t'>TickerCoins em preparação</div><div class='d'>{_e(motivo)}</div></div>", unsafe_allow_html=True)
    return ok


def _rodape() -> None:
    st.markdown(f"<div class='tc-aviso'>{_e(TC.AVISO)}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ Minha Carteira de Moedas
def _linha_hist(x: dict) -> str:
    d = int(x["delta"])
    pend = x["estado"] == "pendente"
    cor = "tc-pos" if d > 0 else "tc-neg" if d < 0 else ""
    val = "aguardando" if pend else _sinal(d)
    return (f"<div class='tc-card{' tc-pre' if pend else ''}'><div class='t'>{_e(x['descricao'] or x['origem'])} "
            f"<span class='{cor}' style='float:right'>{_e(val)} TC</span></div>"
            f"<div class='m'>{_e(_fmt(x['criado_em']))} · {_e(TC.ROTULO_ESTADO.get(x['estado'], x['estado']))} · saldo depois: {int(x['saldo_apos'])} TC</div></div>")


def _extrato() -> None:
    """Extrato: totais, benefícios ativos e histórico (créditos, débitos, datas e descrições). Parte da Economia Ticker, não uma carteira à parte."""
    c = _conta()
    t = TC.totais(c["id"])
    a, b = st.columns(2)
    a.markdown(f"<div class='tc-card'><div class='d'>Total recebido</div><div class='t tc-pos'>{t['recebido']} TC</div></div>", unsafe_allow_html=True)
    b.markdown(f"<div class='tc-card'><div class='d'>Total usado</div><div class='t'>{t['usado']} TC</div></div>", unsafe_allow_html=True)
    ativos = TC.beneficios_ativos(c["id"])
    if ativos:
        st.markdown("<div class='tc-sec'>Benefícios ativos</div>", unsafe_allow_html=True)
        for x in ativos:
            p = TC.produto(x["produto_id"]) or {}
            val = "Permanente" if not x.get("expira_em") else f"até {_fmt(x['expira_em'])}"
            st.markdown(f"<div class='tc-card'><div class='t'>{_e(p.get('nome', x['produto_id']))}</div><div class='m'>{_e(val)}</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='tc-sec'>Histórico</div>", unsafe_allow_html=True)
    hist = TC.historico(c["id"], 60)
    if not hist:
        st.markdown(_vazio("pensativo", "Nenhuma movimentação ainda", "Conclua uma lição na Jornada para ganhar suas primeiras moedas."), unsafe_allow_html=True)
    for x in hist:
        st.markdown(_linha_hist(x), unsafe_allow_html=True)


# ------------------------------------------------------------------ Central de Recompensas
def _recompensas() -> None:
    c = _conta()
    cfg = TC.config()
    ganho, teto = TC.ganhos_hoje(c["id"]), int(cfg["limite_diario_ganhos"])
    mult, camp = TC._multiplicador(TC._agora())
    st.markdown(f"<div class='tc-card'><div class='t'>Hoje: {ganho} de {teto} TC por estudo</div>"
                f"<div class='d'>O limite diário renova à meia-noite (horário de Brasília).</div></div>", unsafe_allow_html=True)
    if camp:
        st.markdown(f"<div class='tc-card'><div class='t'>🎉 {_e(camp)}: recompensas x{mult}</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='tc-sec'>Como ganhar moedas</div>", unsafe_allow_html=True)
    for k, r in cfg["recompensas"].items():
        if r.get("ativo") and int(r["valor"]) > 0:
            st.markdown(f"<div class='tc-card'><div class='t'>{_e(r['rotulo'])} <span class='tc-pos' style='float:right'>+{int(r['valor'])} TC</span></div></div>", unsafe_allow_html=True)
    st.markdown("<div class='tc-card'><div class='d'>As moedas de estudo entram sozinhas quando você conclui a atividade. O XP da Jornada continua separado.</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='tc-sec'>Anúncios recompensados</div>", unsafe_allow_html=True)
    stt = TC.anuncios_status()
    a = cfg["anuncios"]
    if stt["disponivel"]:
        st.markdown(f"<div class='tc-card'><div class='t'>Assista e ganhe {int(a['valor'])} TC</div><div class='d'>Até {int(a['limite_dia'])} por dia, com {int(a['intervalo_min'])} min de intervalo.</div></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='tc-card tc-pre'><div class='t'>Indisponível por enquanto</div><div class='d'>{_e(stt['motivo'])}</div></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ Loja Ticker
def _pedir(pid: str) -> None:
    st.session_state["tc_conf"] = {"pid": pid, "req": uuid.uuid4().hex}


def _cancelar() -> None:
    st.session_state.pop("tc_conf", None)


def _confirmar() -> None:
    cf = st.session_state.pop("tc_conf", None)
    c = _conta()
    if not cf or not c:
        return
    r = TC.comprar(c["id"], cf["pid"], cf["req"], _plano())
    TC.esquecer_cache(c["id"])
    esquecer_saldo()
    LA.invalidar()
    st.session_state["tc_res"] = {**r, "pid": cf["pid"]}


def _usar(pid: str | None, tipo: str) -> None:
    """Equipa (pid) ou tira (None) o emblema ou a moldura. O servidor só aceita item que a conta possui."""
    c = _conta()
    if not c:
        return
    try:
        TC.equipar(c["id"], c["email"], pid, tipo)
        LA.invalidar()
        st.session_state["tc_aviso_loja"] = ("ok", ("Tema aplicado! O app já está com o novo visual." if tipo == "tema" else "Pronto! Sua escolha já está valendo.") if pid else ("Tema padrão de volta." if tipo == "tema" else "Item retirado."))
    except TC.ErroTC as e:
        st.session_state["tc_aviso_loja"] = ("erro", str(e))


CSS_LOJA = """<style>
.lj-card{display:flex;align-items:center;gap:12px;margin:8px 0 2px;padding:12px;border-radius:18px;background:#241C4D;border:1px solid rgba(197,179,255,.3);box-shadow:0 3px 0 rgba(0,0,0,.25)}
.lj-card.tem{border-color:rgba(61,220,151,.7);background:linear-gradient(135deg,rgba(61,220,151,.14),#241C4D)}
.lj-pv{flex:0 0 54px;width:54px;height:54px;border-radius:50%;display:grid;place-items:center;font-size:1.7rem;font-weight:900;color:#fff !important;
background:radial-gradient(circle at 30% 20%,rgba(255,255,255,.35),transparent 55%),var(--c)}
.lj-pv.anel{background:#1A1438;border:5px solid var(--c);box-shadow:0 0 14px var(--c)}
.lj-tx{min-width:0;flex:1}
.lj-n{font-weight:800;font-size:.95rem;line-height:1.15;color:#F6F3FF !important}
.lj-d{margin-top:2px;font-size:.78rem;line-height:1.3;color:#CFC8EE !important}
.lj-m{margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.lj-p{padding:2px 10px;border-radius:999px;font-weight:800;font-size:.78rem;background:#2A2058;border:1px solid rgba(242,184,75,.45);color:#FFD66B !important}
.lj-s{padding:2px 10px;border-radius:999px;font-weight:800;font-size:.72rem;border:1px solid;color:#CFC8EE !important;border-color:rgba(255,255,255,.25)}
.lj-s.ok{color:#3DDC97 !important;border-color:#3DDC97}
.lj-s.uso{color:#FFD66B !important;border-color:#FFD66B}
.lj-s.falta{color:#FF9BB0 !important;border-color:#FF6B8A}
.lj-v{font-size:.72rem;color:#9C94C9 !important}
.lj-pre{margin:10px 0;padding:16px;border-radius:18px;border:1.5px dashed rgba(197,179,255,.4);background:#1A1438;text-align:center}
.lj-pre b{display:block;font-size:1rem;color:#F6F3FF !important}
.lj-pre span{display:block;margin-top:4px;font-size:.82rem;color:#CFC8EE !important}
.lj-fest{position:relative;overflow:hidden;margin:6px 0 22px;padding:18px 14px;border-radius:24px;text-align:center;background:linear-gradient(135deg,#4B34A8,#1B1545);border:1px solid rgba(255,214,107,.7);box-shadow:0 0 22px rgba(255,214,107,.25)}
.lj-fest .t{font-weight:900;font-size:1.25rem;color:#FFD66B !important}
.lj-fest .s{margin-top:4px;font-size:.88rem;color:#EDE9FF !important}
.lj-fest .lj-pvw{display:flex;justify-content:center;margin:10px 0 6px;padding:0 !important;background:none !important;border:0 !important;box-shadow:none !important}
.lj-fest .nm{font-weight:800;font-size:1rem;color:#fff !important}
.lj-fest i{position:absolute;top:-12px;width:8px;height:14px;border-radius:2px;opacity:.9;animation:lj-cai 2.6s linear infinite}
@keyframes lj-cai{to{transform:translateY(260px) rotate(300deg);opacity:0}}
.lj-fest i:nth-child(1){left:8%;background:#FFD66B;animation-delay:0s}
.lj-fest i:nth-child(2){left:24%;background:#3DDC97;animation-delay:.5s}
.lj-fest i:nth-child(3){left:41%;background:#FF6B8A;animation-delay:.2s}
.lj-fest i:nth-child(4){left:58%;background:#8B6CFF;animation-delay:.8s}
.lj-fest i:nth-child(5){left:74%;background:#2BA7C9;animation-delay:.35s}
.lj-fest i:nth-child(6){left:90%;background:#FFD66B;animation-delay:1s}
@media (prefers-reduced-motion:reduce){.lj-fest i{animation:none;display:none}}
@media (max-width:380px){.lj-card{gap:10px;padding:10px}.lj-pv{flex-basis:44px;width:44px;height:44px;font-size:1.4rem}.lj-n{font-size:.9rem}}
.lj-card{border-color:color-mix(in srgb,var(--rc,#C5B3FF) 55%,transparent)}
.lj-card.r-lendario{background:linear-gradient(135deg,rgba(255,185,56,.16),#241C4D 70%);box-shadow:0 0 18px -6px rgba(255,185,56,.55),0 3px 0 rgba(0,0,0,.25)}
.lj-card.r-epico{background:linear-gradient(135deg,rgba(176,107,255,.15),#241C4D 70%)}
.lj-card.r-raro{background:linear-gradient(135deg,rgba(77,163,255,.12),#241C4D 70%)}
.lj-r{padding:2px 9px;border-radius:999px;font-weight:900;font-size:.68rem;letter-spacing:.03em;text-transform:uppercase;background:color-mix(in srgb,var(--rc) 22%,#1A1438);color:var(--rc) !important;border:1px solid var(--rc)}
.lj-s.fora{color:#FFB38A !important;border-color:#FF9B3D}
.lj-ev{font-size:.72rem;color:#FFD66B !important}
.lj-sec{margin:12px 2px 2px;font-size:.8rem;font-weight:800;color:#C5B3FF !important;text-transform:uppercase;letter-spacing:.04em}
html body .stApp.stApp.stApp .lj-card{margin:8px 0 8px !important}
html body .stApp.stApp.stApp [class*="st-key-tc_c_"] button,html body .stApp.stApp.stApp [class*="st-key-tc_usa_"] button,html body .stApp.stApp.stApp [class*="st-key-tc_ok_"] button{min-height:46px !important;border-radius:16px !important;border:1.5px solid rgba(255,214,107,.8) !important;background:linear-gradient(135deg,#F2B84B,#D98E1F) !important;box-shadow:0 4px 0 #7A4D0B !important}
html body .stApp.stApp.stApp [class*="st-key-tc_usa_"] button{border-color:rgba(61,220,151,.85) !important;background:linear-gradient(135deg,#2FBF84,#17805A) !important;box-shadow:0 4px 0 #0A3F2C !important}
html body .stApp.stApp.stApp [class*="st-key-tc_c_"] button :is(p,span),html body .stApp.stApp.stApp [class*="st-key-tc_ok_"] button :is(p,span){color:#2A1A00 !important;-webkit-text-fill-color:#2A1A00 !important;font-weight:900 !important}
html body .stApp.stApp.stApp [class*="st-key-tc_usa_"] button :is(p,span){color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:900 !important}
html body .stApp.stApp.stApp [class*="st-key-tc_tira_"] button,html body .stApp.stApp.stApp [class*="st-key-tc_no_"] button{min-height:46px !important;border-radius:16px !important;background:rgba(255,255,255,.06) !important;border:1.5px solid rgba(197,179,255,.5) !important;box-shadow:0 3px 0 rgba(10,8,40,.5) !important}
html body .stApp.stApp.stApp [class*="st-key-tc_tira_"] button :is(p,span),html body .stApp.stApp.stApp [class*="st-key-tc_no_"] button :is(p,span){color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important}
html body .stApp.stApp.stApp [class*="st-key-tc_c_"] button:active,html body .stApp.stApp.stApp [class*="st-key-tc_usa_"] button:active{transform:translateY(3px)}
html body .stApp.stApp.stApp [class*="st-key-tc_c_"] button:disabled{opacity:.5 !important;filter:grayscale(.5)}
</style>"""


def _previa_html(p: dict, extra: str = "") -> str:
    return VL.html_previa(VT.previa(p))


def _celebracao(p: dict) -> str:
    """Confirmação visual da compra (fx_arte.html_compra). Com 'animações' desligadas na sessão mostra só o resultado, parado."""
    try:
        import fx_arte as FX
        return FX.CSS + FX.html_compra(p["nome"], _previa_html(p), int(p["preco"]), p.get("raridade") or "comum", FX.animar_padrao(st.session_state))
    except Exception:
        return (f"<div class='lj-fest'><div class='t'>Compra feita!</div><div class='lj-pvw'>{_previa_html(p)}</div><div class='nm'>{_e(p['nome'])}</div></div>")


def _hoje() -> date:
    return datetime.now(timezone(timedelta(hours=-3))).date()


def _card_produto(p: dict, c: dict, s: int, possui: set, eq: dict) -> None:
    ok, motivo = TC.pode_comprar(c["id"], p["id"], _plano())
    stt = VT.status(p, possui, eq, s, _hoje())
    rr = VT.raridade(p)
    jan = LC.texto_janela(p)
    st.markdown(f"<div class='lj-card r-{rr['id']}{' tem' if stt['tem'] else ''}' style='--rc:{_e(rr['cor'])}'>{_previa_html(p)}<div class='lj-tx'><div class='lj-n'>{_e(p['nome'])}</div>"
                f"<div class='lj-d'>{_e(p['descricao'])}</div><div class='lj-m'><span class='lj-r'>{_e(rr['rotulo'])}</span><span class='lj-p'>🪙 {p['preco']} TC</span>"
                f"<span class='lj-s {stt['cls']}'>{_e(stt['rotulo'])}</span>"
                + (f"<span class='lj-ev'>{_e(jan)}</span>" if jan else (f"<span class='lj-v'>{_e(TC.rotulo_validade(p['validade_h']))}</span>" if p['validade_h'] is not None else ""))
                + "</div></div></div>", unsafe_allow_html=True)
    cf = st.session_state.get("tc_conf")
    kind = p["efeito"]["kind"]
    if cf and cf["pid"] == p["id"]:
        st.markdown(f"Confirmar a compra de **{_e(p['nome'])}** por **{p['preco']} TC**? Saldo depois: {s - p['preco']} TC.")
        x, y = st.columns(2)
        x.button("Confirmar compra", key=f"tc_ok_{p['id']}", type="primary", width="stretch", on_click=_confirmar)
        y.button("Cancelar", key=f"tc_no_{p['id']}", width="stretch", on_click=_cancelar)
    elif stt["tem"] and VT.equipavel(p):
        tema = kind == "tema"
        if eq.get(kind) == p["id"]:
            st.button("Voltar ao tema padrão" if tema else "Tirar", key=f"tc_tira_{p['id']}", width="stretch", on_click=_usar, args=(None, kind))
        else:
            st.button("Aplicar tema" if tema else "Usar", key=f"tc_usa_{p['id']}", type="primary", width="stretch", on_click=_usar, args=(p["id"], kind))
    elif stt["tem"]:
        pass
    elif not ok:
        st.caption(motivo)
    elif s < p["preco"]:
        pass                                                   # a etiqueta "Faltam X TC" do cartão já diz isso
    else:
        st.button("Comprar", key=f"tc_c_{p['id']}", width="stretch", on_click=_pedir, args=(p["id"],))


_ICONES_LOJA = {"temas": ("estrela", "#B89CFF"), "especiais": ("escudo", "#F2B84B"), "beneficios": ("raio", "#3DDC97"),
                "molduras": ("escudo", "#F2B84B"), "fundos": ("grafico", "#5CC8FF"), "efeitos": ("raio", "#FF8AD8"), "selos": ("estrela", "#FFD66B")}


def _nav_loja() -> list:
    n = st.session_state.get("loja_nav")
    return [x for x in n if isinstance(x, str)][:2] if isinstance(n, list) else []


def _ir(caminho: list) -> None:
    st.session_state["loja_nav"] = list(caminho)


def _voltar_loja() -> None:
    st.session_state["loja_nav"] = _nav_loja()[:-1]


def _contar(sub: str) -> int:
    return len(VT.itens_da_categoria(TC.produtos(), sub))


def _sub_grupo(grupo: str) -> str:
    subs = VT.subs_do_grupo(grupo)
    if len(subs) == 1:
        n = _contar(subs[0])
        return f"{n} {'item' if n == 1 else 'itens'}" if n else "Em breve"
    return " · ".join(VT.ROTULOS[x] for x in subs[:2]) + ("…" if len(subs) > 2 else "")


def _css_cartoes_loja(prefixo: str, ids: list, icones: dict, subs: dict) -> str:
    q = "html body .stApp.stApp.stApp"
    v = "".join(f'.st-key-{prefixo}_{i}{{--ac:{icones.get(i, ("estrela", "#B89CFF"))[1]};--ic:url("{IC.uri(*icones.get(i, ("estrela", "#B89CFF")))}");--sub:"{subs.get(i, "")}"}}' for i in ids)
    k = f'[class*="st-key-{prefixo}_"] button'
    return ("<style>" + v
            + f'{q} .st-key-{prefixo}{{display:flex !important;flex-direction:column !important;gap:10px !important;margin:8px 0}}'
            + f'{q} {k}{{width:100% !important;min-height:76px !important;height:auto !important;padding:10px 40px 10px 70px !important;position:relative !important;border-radius:20px !important;text-align:left !important;'
            'background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 18%,#1B1B5E),#17154F 75%) !important;border:1.5px solid color-mix(in srgb,var(--ac) 65%,transparent) !important;'
            'box-shadow:0 4px 0 color-mix(in srgb,var(--ac) 25%,#0B0821),0 0 16px -8px var(--ac) !important}'
            + f'{q} {k}:before{{content:"";position:absolute;left:14px;top:50%;width:44px;height:44px;margin-top:-22px;background:var(--ic) center/contain no-repeat;filter:drop-shadow(0 0 6px var(--ac))}}'
            + f'{q} {k}:after{{content:"\\203A";position:absolute;right:16px;top:50%;margin-top:-17px;font-size:1.7rem;font-weight:800;color:var(--ac)}}'
            + f'{q} {k}>div{{width:100% !important;justify-content:flex-start !important;text-align:left !important;margin:0 !important}}'
            + f'{q} {k} [data-testid="stMarkdownContainer"]{{width:100% !important;text-align:left !important}}'
            + f'{q} {k} p{{margin:0 !important;text-align:left !important;font-size:1.02rem !important;font-weight:800 !important;color:#fff !important;-webkit-text-fill-color:#fff !important}}'
            + f'{q} {k} p:after{{content:var(--sub);display:block;font-size:.76rem;font-weight:500;color:#C5B3FF;-webkit-text-fill-color:#C5B3FF;margin-top:2px}}'
            + f'{q} {k}:active{{transform:translateY(3px)}}</style>')


def _cartoes_loja(itens: list, prefixo: str, icones: dict, caminho: list | None = None) -> None:
    """Cartões de navegação (padrão da Home): tocar abre a tela seguinte, sem empilhar seletores."""
    ids = [i for i, _r, _s in itens]
    st.markdown(_css_cartoes_loja(prefixo, ids, icones, {i: _e(sub) for i, _r, sub in itens}), unsafe_allow_html=True)
    with st.container(key=prefixo):
        for i, rot, _sub in itens:
            st.button(rot, key=f"{prefixo}_{i}", on_click=_ir, args=((caminho or []) + [i],), use_container_width=True)


def _loja_tela(caminho: list, c: dict, s, possui: set, eq: dict) -> None:
    grupo = caminho[0]
    if grupo not in VT.GRUPO_IDS:
        _ir([])
        st.rerun()
    subs = VT.subs_do_grupo(grupo)
    sub = caminho[1] if len(caminho) > 1 and caminho[1] in subs else None
    if len(subs) == 1:
        sub = subs[0]
    st.markdown(ES.css_voltar("lj_voltar"), unsafe_allow_html=True)
    st.button("‹ Voltar", key="lj_voltar", on_click=_voltar_loja)
    if sub is None:
        st.markdown(f"<div class='tc-sec'>{_e(VT.GRUPO_ROTULOS[grupo])}</div>", unsafe_allow_html=True)
        _cartoes_loja([(x, VT.ROTULOS[x], _sub_grupo(x)) for x in subs], "lj_s", _ICONES_LOJA, [grupo])
        return
    st.markdown(f"<div class='tc-sec'>{_e(VT.ROTULOS[sub] if len(subs) > 1 else VT.GRUPO_ROTULOS[grupo])}</div>", unsafe_allow_html=True)
    itens = VT.itens_da_categoria(TC.produtos(), sub)
    if not itens:
        st.markdown(f"<div class='lj-pre'><b>Em preparação</b><span>{_e(VT.texto_preparacao(sub) or 'Nenhum item disponível agora.')}</span></div>", unsafe_allow_html=True)
    st.markdown(VL.CSS_PREVIA + VL.CSS_MOLDURA, unsafe_allow_html=True)
    for p in itens:
        _card_produto(p, c, s, possui, eq)



def _loja() -> None:
    u = _conta()
    c = {"id": u["id"]}
    st.markdown(CSS_LOJA, unsafe_allow_html=True)
    r = st.session_state.pop("tc_res", None)
    aviso = st.session_state.pop("tc_aviso_loja", None)
    if aviso:
        (st.success if aviso[0] == "ok" else st.error)(aviso[1])
    if r:
        if r.get("ok") and r.get("duplicada"):
            st.info("Esta compra já tinha sido feita (nada foi cobrado de novo).")
        elif r.get("ok") and TC.produto(r.get("pid") or ""):
            st.markdown(_celebracao(TC.produto(r["pid"])), unsafe_allow_html=True)
        elif r.get("ok"):
            st.success("Compra feita! O benefício já está ativo.")
        else:
            st.error(r.get("erro", "Não foi possível concluir a compra."))
    s = TC.saldo(c["id"])
    possui = {b["produto_id"] for b in TC.beneficios_ativos(c["id"])}
    eq = TC.equipado(u["email"])
    caminho = _nav_loja()
    if caminho:
        _loja_tela(caminho, c, s, possui, eq)
        return
    _cartoes_loja([(g, VT.GRUPO_ROTULOS[g], _sub_grupo(g)) for g in VT.GRUPO_IDS], "lj_g", _ICONES_LOJA)
    st.markdown("<div class='tc-sec'>Minhas compras</div>", unsafe_allow_html=True)
    cs = TC.compras(c["id"], 20)
    if not cs:
        st.markdown(_vazio("animado", "Nenhuma compra ainda", "Escolha um tema, moldura ou selo acima para personalizar seu perfil."), unsafe_allow_html=True)
    for x in cs:
        p = TC.produto(x["produto_id"]) or {}
        est = TC.ROTULO_ESTADO.get(x["estado"], x["estado"])
        st.markdown(f"<div class='tc-card'><div class='t'>{_e(p.get('nome', x['produto_id']))} <span class='tc-neg' style='float:right'>-{int(x['preco'])} TC</span></div>"
                    f"<div class='m'>{_e(_fmt(x['criado_em']))} · {_e(est)}</div></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ Economia Ticker (área global)
CSS_PAG = (
    'html body .stApp.stApp.stApp .st-key-eco_abas [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:6px !important;}'
    'html body .stApp.stApp.stApp .st-key-eco_abas [data-testid="stColumn"]{flex:1 1 0 !important;min-width:0 !important;width:auto !important;}'
    'html body .stApp.stApp .st-key-eco_abas button{min-height:40px;padding:0 6px !important;}'
    'html body .stApp.stApp .st-key-eco_abas button p{font-size:.85rem !important;font-weight:700;white-space:nowrap;}'
    'html body .stApp.stApp [data-testid="stMain"] .tc-saldo,html body .stApp.stApp [data-testid="stMain"] .tc-card{box-sizing:border-box;max-width:100%;overflow-wrap:anywhere;}'
    'html body .stApp.stApp .tc-sec{font-weight:800;color:#F6F3FF;margin:14px 2px 4px;font-size:1rem;}'
)


SECOES = ["Recompensas", "Loja", "Extrato"]
_CORPOS = {"Recompensas": _recompensas, "Loja": _loja, "Extrato": _extrato}


def ir_para(secao: str = "Recompensas") -> None:
    """Escolhe a seção que a Economia Ticker abre (use antes de navegar para a página 'economia')."""
    if secao in SECOES:
        st.session_state["eco_sec"] = secao


def pagina_economia() -> None:
    """Centro único das TickerCoins: saldo, Central de recompensas, Loja Ticker e Extrato. Reaproveita o que já existia (sem telas duplicadas)."""
    st.markdown(CSS + "<style>" + CSS_PAG + "</style>", unsafe_allow_html=True)
    st.title("🪙 Loja Ticker")
    if _precisa_login() or not _banco_ok():
        _rodape()
        return
    c = _conta()
    s = saldo_atual(True)
    st.markdown(f"<div class='tc-saldo'><div>{MA.img('tc', 64)}</div><div class='v'>{'—' if s is None else s} TC</div><div class='l'>Saldo disponível de TickerCoins</div></div>", unsafe_allow_html=True)
    if st.session_state.get("eco_sec") not in SECOES:
        st.session_state["eco_sec"] = SECOES[0]
    sec = st.session_state["eco_sec"]
    sec = ES.abas("eco_sec", SECOES, colunas=3)               # três abas iguais, sempre na mesma linha (celular, tablet e computador)
    try:
        _CORPOS[sec]()
    except Exception as e:
        banco.registrar_erro("tickercoins_app.economia", e)
        st.markdown("<div class='tc-card'><div class='t'>Não consegui carregar esta seção agora.</div><div class='d'>Tente de novo em instantes.</div></div>", unsafe_allow_html=True)
    _rodape()


# ------------------------------------------------------------------ indicador do cabeçalho (um só, global)
CSS_CAB = (
    'html,body{overflow-x:hidden !important;max-width:100vw;}'
    'html body .stApp.stApp,html body [data-testid="stAppViewContainer"],html body [data-testid="stMain"]{overflow-x:clip !important;max-width:100vw;}'
    'html body .stApp.stApp [data-testid="stMain"] .block-container{max-width:100vw !important;box-sizing:border-box;overflow-x:clip;}'
    'html body .stApp.stApp .st-key-topo_perfil{max-width:100vw;overflow:hidden;}'
    'html body .stApp.stApp .st-key-topo_perfil .st-key-topo_tc{flex:0 0 auto;}'
    'html body .stApp.stApp .st-key-topo_perfil .st-key-topo_tc button{width:auto !important;min-width:44px;padding:0 8px !important;gap:3px;'
    'background:rgba(242,184,75,.12) !important;border:1px solid rgba(242,184,75,.45) !important;border-radius:999px !important;height:34px;min-height:34px;}'
    'html body .stApp.stApp .st-key-topo_perfil .st-key-topo_tc button p{display:block !important;color:#FFD66B !important;font-weight:800;font-size:.85rem;margin:0;white-space:nowrap;}'
    'html body .stApp.stApp .st-key-topo_perfil .st-key-topo_tc button [data-testid="stIconMaterial"]{font-size:20px !important;color:#FFD66B !important;}'
)


def _css_cab() -> str:
    """CSS do chip; com moeda_tc.webp no repositório, a moeda dourada substitui o ícone genérico."""
    u = MA.uri("tc")
    if not u:
        return CSS_CAB + '@media (max-width:1100px){html body .stApp.stApp .st-key-topo_tc{display:none !important}}'
    return CSS_CAB + ('@media (max-width:1100px){html body .stApp.stApp .st-key-topo_tc{display:none !important}}'      # no celular/tablet o TC vive na linha de status
                      'html body .stApp.stApp .st-key-topo_perfil .st-key-topo_tc button [data-testid="stIconMaterial"]{font-size:0 !important;color:transparent !important;'
                      f'width:24px;height:24px;background:url("{u}") center/contain no-repeat;display:inline-block;flex:none}}')


def _abrir_economia() -> None:
    st.session_state["_nav_pend"] = "economia"


def chip_cabecalho() -> None:
    """Botão 'moeda + saldo' do cabeçalho; leva à Economia Ticker. Só para quem está logado e com o banco pronto."""
    s = saldo_atual()
    if s is None:
        return
    st.markdown("<style>" + _css_cab() + "</style>", unsafe_allow_html=True)
    st.button(f"{s if s < 10000 else '9999+'} TC", key="topo_tc", icon=":material/toll:", type="tertiary", on_click=_abrir_economia)


# ------------------------------------------------------------------ painel administrativo (seção "TickerCoins")
def admin(a) -> None:
    """Visão geral, conta, preços/recompensas, compras e tentativas suspeitas. Cada operação confere a permissão e é auditada em tickercoins.py."""
    TC.exigir(a, "admin.tickercoins.ver")
    pode = TC.permissoes.tem(a.papel, "admin.tickercoins")
    est = TC.admin_estatisticas(a)
    st.markdown(f"**Contas com moedas:** {est['contas_com_moedas']} · **Recebido:** {est['recebido']} TC · **Usado:** {est['usado']} TC · "
                f"**Compras:** {est['compras']} · **Tentativas suspeitas:** {est['fraudes']}")
    st.caption(f"Base: {est['amostra']}.")
    ok, motivo = TC.disponivel()
    if not ok:
        st.warning(motivo)
        return
    st.markdown("**Conta**")
    email = st.text_input("E-mail da conta", key="tc_adm_email")
    d = TC.admin_conta(a, email) if email.strip() else None
    if email.strip() and not d:
        st.info("Conta não encontrada.")
    if d:
        st.markdown(f"Saldo: **{d['saldo']} TC** · recebido {d['totais']['recebido']} · usado {d['totais']['usado']} · "
                    f"integridade do livro: {'ok' if d['integridade']['ok'] else 'INCONSISTENTE'}")
        for x in d["historico"][:15]:
            st.markdown(_linha_hist(x), unsafe_allow_html=True)
        if pode:
            v = st.number_input("Quantidade (negativa remove)", value=0, step=1, key="tc_adm_val")
            j = st.text_input("Justificativa (obrigatória)", key="tc_adm_just")
            if st.button("Aplicar ajuste", key="tc_adm_go"):
                try:
                    TC.admin_ajustar(a, d["conta"]["id"], int(v), j)
                    st.success("Ajuste feito e auditado.")
                    st.rerun()
                except (TC.ErroTC, banco.ErroBanco, banco.SemPermissao) as e:
                    st.error(str(e))
    if pode:
        _admin_config(a)
    st.markdown("**Compras recentes**")
    for x in TC.admin_compras_recentes(a, 15):
        st.markdown(f"<div class='tc-card'><div class='t'>{_e(x['produto_id'])} · {int(x['preco'])} TC · {_e(x['estado'])}</div>"
                    f"<div class='m'>{_e(_fmt(x['criado_em']))} · conta {_e(x['conta_id'][:8])}</div></div>", unsafe_allow_html=True)
        if pode and x["estado"] == "confirmada":
            if st.button("Estornar", key=f"tc_est_{x['id']}"):
                try:
                    TC.estornar_compra(a, x["id"], "estorno pelo painel")
                    st.rerun()
                except (TC.ErroTC, banco.ErroBanco) as e:
                    st.error(str(e))
    st.markdown("**Tentativas inválidas (anúncios)**")
    fr = TC.admin_fraudes(a, 15)
    if not fr:
        st.caption("Nenhuma.")
    for x in fr:
        st.caption(f"{_fmt(x['quando'])} · {x['detalhes']}")


def _admin_config(a) -> None:
    cfg = TC.config(True)
    st.markdown("**Economia (valores em TC)**")
    novo = {"recompensas": {}, "anuncios": {}, "produtos": {}}
    for k, r in cfg["recompensas"].items():
        c1, c2 = st.columns([3, 1])
        v = c1.number_input(r["rotulo"], 0, 1000, int(r["valor"]), key=f"tc_cf_r_{k}")
        on = c2.checkbox("Ativa", bool(r["ativo"]), key=f"tc_cf_ra_{k}")
        novo["recompensas"][k] = {"valor": int(v), "ativo": on}
    novo["limite_diario_ganhos"] = int(st.number_input("Limite diário de ganhos por estudo", 0, 10000, int(cfg["limite_diario_ganhos"]), key="tc_cf_lim"))
    an = cfg["anuncios"]
    novo["anuncios"] = {"ativo": st.checkbox("Anúncios recompensados ligados (exige provedor configurado)", bool(an["ativo"]), key="tc_cf_an"),
                        "valor": int(st.number_input("Valor por anúncio", 0, 1000, int(an["valor"]), key="tc_cf_anv")),
                        "limite_dia": int(st.number_input("Anúncios por dia", 0, 100, int(an["limite_dia"]), key="tc_cf_and")),
                        "intervalo_min": int(st.number_input("Intervalo entre anúncios (min)", 0, 1440, int(an["intervalo_min"]), key="tc_cf_ani"))}
    st.markdown("**Produtos**")
    for p in TC.produtos(None, so_ativos=False):
        c1, c2 = st.columns([2, 1])
        preco = c1.number_input(p["nome"], 0, TC.MAX_VALOR, int(p["preco"]), key=f"tc_cf_p_{p['id']}")
        on = c2.checkbox("À venda", bool(p["ativo"]), key=f"tc_cf_pa_{p['id']}")
        novo["produtos"][p["id"]] = {"preco": int(preco), "ativo": on}
    j = st.text_input("Justificativa da alteração", key="tc_cf_just")
    if st.button("Salvar configuração", key="tc_cf_go", type="primary"):
        if len(j.strip()) < 5:
            st.error("Informe a justificativa (mínimo 5 caracteres).")
            return
        try:
            TC.salvar_config(a, novo, j)
            st.success("Configuração salva e auditada.")
        except (TC.ErroTC, banco.ErroBanco, banco.SemPermissao) as e:
            st.error(str(e))
