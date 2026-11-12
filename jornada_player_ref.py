"""Tela de perguntas da lição no layout de referência (Quiz): cabeçalho com título e "Pergunta N de T", Caramelo pensativo com balão claro,
alternativas A-D em cartões com bolinha, botão Verificar verde largo e "Sair da lição" em contorno. Módulo puro (HTML/CSS, sem Streamlit).
Só a fase de pergunta usa estas peças; o feedback e a tela final continuam em jornada_player.py."""
from __future__ import annotations

import html
from urllib.parse import quote

import arte_feedback as AF
import arte_tickerhunters as AT
import jornada_icones as IC

P = 'html body .stApp.stApp.stApp div[class*="st-key-jor_player"]'


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def numero_pergunta(s: dict) -> tuple[int, int]:
    """(pergunta atual, total) da sessão: a atual é feitos+1, limitada ao total."""
    total = int(s.get("total") or 0)
    return min(int(s.get("feitos") or 0) + 1, max(total, 1)), total


def titulo_partes(nome: str) -> tuple[str, str]:
    """Separa a última palavra do título (ela ganha a cor lavanda, como na referência)."""
    partes = str(nome or "Lição").split()
    return (" ".join(partes[:-1]), partes[-1]) if len(partes) > 1 else ("", partes[0])


def html_topo(nome: str, s: dict) -> str:
    """Título e pílula "Pergunta N de T" (o botão Voltar do app fica à esquerda, numa coluna própria)."""
    atual, total = numero_pergunta(s)
    ini, fim = titulo_partes(nome)
    return (f"<span class='jor-tl'></span><div class='jr-top'><div class='jr-nm'><img src='{IC.uri('grafico', '#3DDC97')}' alt=''><span>{_e(ini)} <b>{_e(fim)}</b></span></div>"
            f"<div class='jr-pill'><span>💡</span>Pergunta {atual} de {total}</div></div>")


def html_trilho(pct: float, de: float | None = None) -> str:
    pct = max(0.0, min(1.0, float(pct)))
    anima = de is not None and 0.0 <= float(de) < pct
    barra = (f" class='anima' style='width:{pct * 100:.0f}%;--de:{max(0.0, float(de)) * 100:.0f}%'" if anima else f" style='width:{pct * 100:.0f}%'")
    return f"<div class='jor-trilho jr-trilho'><i{barra}></i></div>"


_ICONE_GRAFICO = ("<svg viewBox='0 0 48 40' aria-hidden='true'><rect x='4' y='24' width='9' height='14' rx='2'/><rect x='18' y='16' width='9' height='22' rx='2'/>"
                  "<rect x='32' y='8' width='9' height='30' rx='2'/><path d='M6 16l14-9 8 5 14-10' fill='none' stroke-width='3' stroke-linecap='round'/></svg>")


def html_pergunta(ex: dict, dica: str) -> str:
    texto = _e(ex["pergunta"])
    if ex["tipo"] == "completar":
        texto = texto.replace("___", "<span class='lacuna'></span>")
    return (f"<div class='jr-ask'><div class='jr-m'><i class='jr-halo'></i><img src='{AT.uri('caramelo_pensativo')}' alt='' aria-hidden='true'><b class='jr-qm'>?</b></div>"
            f"<div class='jr-q'><div class='t'>{texto}</div><div class='s'>{_e(dica)}</div>{_ICONE_GRAFICO}</div></div>")


def fundo_player() -> str:
    """Brilho azul no topo, velas ao fundo à direita, linha de luz e barras de alta no canto inferior direito."""
    velas = "".join(f"<line x1='{x + 5}' y1='{y - 12}' x2='{x + 5}' y2='{y + h + 10}' stroke='#6C8CFF' stroke-width='2' opacity='.18'/>"
                    f"<rect x='{x}' y='{y}' width='10' height='{h}' rx='2' fill='#6C8CFF' opacity='.16'/>" for x, y, h in ((250, 40, 36), (276, 24, 48), (302, 52, 28), (328, 16, 52), (354, 44, 34)))
    barras = "".join(f"<rect x='{x}' y='{y}' width='16' height='{500 - y}' rx='3' fill='url(#b)' opacity='.85'/>" for x, y in ((290, 462), (312, 448), (334, 430), (356, 412), (378, 386)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 500' preserveAspectRatio='xMaxYMax slice'><defs>"
           "<linearGradient id='b' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#6CF0A0'/><stop offset='1' stop-color='#3D5CFF' stop-opacity='.4'/></linearGradient>"
           "<linearGradient id='l' x1='0' y1='1' x2='1' y2='0'><stop offset='0' stop-color='#6C4DFF' stop-opacity='0'/><stop offset='1' stop-color='#7CFFA3' stop-opacity='.7'/></linearGradient>"
           "<radialGradient id='g' cx='.5' cy='0' r='.7'><stop offset='0' stop-color='#3D7CFF' stop-opacity='.3'/><stop offset='1' stop-color='#3D7CFF' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='500' fill='url(#g)'/>" + velas
           + "<path d='M0 500 Q160 470 400 392' fill='none' stroke='url(#l)' stroke-width='3'/>"
           + barras + "<polygon points='398,362 386,376 400,378' fill='#7CFFA3'/></svg>")
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def css() -> str:
    p = P
    return ("<style>"
            # cartão da lição
            f"{p}{{max-width:560px !important;padding:14px 14px 18px !important;border-radius:28px;border:2px solid #5B4BE0;"
            f"background:url(\"{fundo_player()}\") right bottom/cover no-repeat,linear-gradient(180deg,#16114F,#0A0832 90%) !important;"
            "box-shadow:0 0 30px -8px rgba(108,77,255,.75),inset 0 0 40px rgba(60,40,200,.18) !important}"
            # topo
            ".jr-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0}"
            ".jr-nm{display:flex;align-items:center;gap:8px;min-width:0;font-weight:900;font-size:clamp(1.05rem,4.6vw,1.45rem);color:#fff !important;line-height:1.1}"
            ".jr-nm img{width:34px;height:34px;flex:none}.jr-nm span{min-width:0;overflow-wrap:anywhere;color:#fff !important}.jr-nm b{color:#C5B3FF !important}"
            ".jr-pill{flex:none;display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:16px;border:1.5px solid #6C5CFF;background:rgba(20,14,80,.7);"
            "font-weight:700;font-size:.82rem;color:#E4DCFF !important;white-space:nowrap}"
            ".jr-trilho{margin:0 0 6px}"
            # mascote + balão
            ".jr-ask{display:flex;align-items:center;gap:0;margin:2px 0 8px}"
            ".jr-m{position:relative;flex:0 0 112px;margin:0 -2px 0 -8px}.jr-m img{position:relative;z-index:1;width:112px;height:auto;display:block;filter:drop-shadow(0 8px 10px rgba(0,0,0,.5))}"
            ".jr-halo{position:absolute;left:8px;right:8px;bottom:-2px;height:70%;border-radius:50%;background:radial-gradient(circle,rgba(61,220,151,.55),rgba(61,124,255,.25) 60%,transparent 72%);z-index:0}"
            ".jr-qm{position:absolute;z-index:2;right:-2px;top:-4px;font-size:2.2rem;font-weight:900;color:#5BE9A6 !important;text-shadow:0 0 14px rgba(61,220,151,.9)}"
            ".jr-q{position:relative;flex:1;min-width:0;padding:12px 56px 12px 16px;border-radius:24px;background:linear-gradient(135deg,#FFFFFF,#DCCFFF);box-shadow:0 0 24px -4px rgba(120,150,255,.7)}"
            ".jr-q:before{content:'';position:absolute;left:-9px;top:50%;margin-top:-9px;border:9px solid transparent;border-left:0;border-right-color:#F3EDFF}"
            ".jr-q .t{font-weight:900;font-size:clamp(1.02rem,4.4vw,1.35rem);line-height:1.2;color:#1D1450 !important;overflow-wrap:anywhere}"
            ".jr-q .s{margin-top:4px;font-style:italic;font-size:clamp(.78rem,3.2vw,.95rem);line-height:1.25;color:#4A3E8C !important}"
            ".jr-q svg{position:absolute;right:12px;top:50%;margin-top:-17px;width:38px;height:34px;fill:#7C6AE0;stroke:#7C6AE0;opacity:.85}"
            ".jr-q .lacuna{display:inline-block;min-width:60px;border-bottom:3px solid #5B3FD6;margin:0 4px}"
            # alternativas
            f"{p} div[class*='st-key-jor_r_'] label{{min-height:62px;padding:8px 12px !important;border-radius:22px !important;gap:10px !important;border:2px solid #5B4BE0 !important;"
            "background:linear-gradient(135deg,#1E1360,#140C42) !important;box-shadow:0 0 14px -6px rgba(108,77,255,.8) !important}"
            f"{p} div[class*='st-key-jor_r_'] label:before{{order:-2;flex:0 0 46px !important;height:46px !important;border-radius:13px !important;font-size:1.3rem !important;color:#fff !important;"
            "background:#120B3A !important;border:2px solid #6C5CFF !important}"
            f"{p} div[class*='st-key-jor_r_'] label:after{{content:'';order:-1;flex:0 0 26px;height:26px;border-radius:50%;border:2px solid #4B3E99;background:#0D0A2E;box-sizing:border-box}}"
            f"{p} div[class*='st-key-jor_r_'] label p{{font-size:clamp(1rem,4.2vw,1.25rem) !important;font-weight:600;color:#fff !important}}"
            f"{p} div[class*='st-key-jor_r_'] label:has(input:checked){{border-color:#7CFFA3 !important;background:linear-gradient(135deg,#1B4A66,#16286B) !important;box-shadow:0 0 18px -4px rgba(124,255,163,.7) !important}}"
            f"{p} div[class*='st-key-jor_r_'] label:has(input:checked):before{{background:#3D5CFF !important;border-color:#9FB4FF !important}}"
            f"{p} div[class*='st-key-jor_r_'] label:has(input:checked):after{{border-color:#7CFFA3;background:radial-gradient(circle,#7CFFA3 0 40%,#0D0A2E 46%)}}"
            # Verificar
            f"{p} div[class*='st-key-jor_sv'] button{{position:relative;min-height:62px !important;border-radius:999px !important;border:0 !important;"
            "background:linear-gradient(180deg,#8CFFA0,#2EE06A) !important;box-shadow:0 5px 0 #1B9A45,0 0 22px -4px rgba(61,220,151,.7) !important}"
            f"{p} div[class*='st-key-jor_sv'] button :is(p,span){{color:#08301A !important;-webkit-text-fill-color:#08301A !important;font-weight:900 !important;font-size:1.4rem !important}}"
            f"{p} div[class*='st-key-jor_sv'] button:before,{p} div[class*='st-key-jor_sv'] button:after{{position:absolute;top:50%;transform:translateY(-50%);font-weight:900;font-size:1.6rem;color:rgba(255,255,255,.75);letter-spacing:-3px}}"
            f"{p} div[class*='st-key-jor_sv'] button:before{{content:'»';left:20px}}{p} div[class*='st-key-jor_sv'] button:after{{content:'«';right:20px}}"
            f"{p} div[class*='st-key-jor_sv'] button:disabled{{opacity:.5 !important;filter:saturate(.7)}}"
            # Sair da lição
            f"html body .stApp.stApp.stApp.stApp div[class*='st-key-jor_ss']{{display:block !important}}"
            f"html body .stApp.stApp.stApp.stApp div[class*='st-key-jor_ss'] button{{min-height:48px !important;padding:0 18px !important;border-radius:999px !important;"
            "background:rgba(8,12,44,.6) !important;border:2px solid #3DDC97 !important;box-shadow:none !important;width:auto !important}"
            f"html body .stApp.stApp.stApp.stApp div[class*='st-key-jor_ss'] button :is(p,span,svg){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important;font-size:1rem !important}}"
            "</style>")


# ------------------------------------------------------------------ resposta (Correto! / Ops...)
DICAS_OK = ("Conhecimento é o primeiro passo para grandes conquistas!", "Quem estuda um pouco todo dia chega mais longe.",
            "Cada acerto fortalece o seu jeito de investir.")
DICAS_ERRO = ("Estude, tente de novo e fique mais forte!", "Errar faz parte: o erro de hoje é o acerto de amanhã.",
              "Leia a explicação com calma. A pergunta volta no fim da lição.")


def dica_caramelo(ok: bool, eid: str) -> str:
    """Frase motivacional fixa por exercício (sem sorteio: a tela não muda ao redesenhar)."""
    lista = DICAS_OK if ok else DICAS_ERRO
    return lista[sum(ord(c) for c in str(eid)) % len(lista)]


def letra_correta(ex: dict) -> str | None:
    """Letra (A-D) da alternativa certa em escolha/completar; nos outros tipos não há letra."""
    if ex["tipo"] in ("escolha", "completar"):
        return "ABCDEFGH"[int(ex["correta"]) % 8]
    return None


def _louro() -> str:
    folhas = "".join(f"<ellipse cx='{10 + i * 3}' cy='{44 - i * 9}' rx='3' ry='7' transform='rotate({-28 + i * 12} {10 + i * 3} {44 - i * 9})'/>" for i in range(5))
    return f"<svg class='jf-louro' viewBox='0 0 36 54' aria-hidden='true'><path d='M8 52C2 36 6 16 24 4' fill='none' stroke='#5BE9A6' stroke-width='2'/><g fill='#5BE9A6'>{folhas}</g></svg>"


def html_resposta(ok: bool, ex: dict, s: dict, xp_conclusao: int) -> str:
    """Tela de resposta: banner do Caramelo, faixa Correto!/Ops..., mensagem e caixa. Dados reais: progresso da lição e a explicação do exercício."""
    banner = (f"<div class='jf-ban {'ok' if ok else 'err'}'><img src='{AF.uri('ok' if ok else 'err')}' alt='' aria-hidden='true' "
              f"style='aspect-ratio:1/{AF.proporcao('ok' if ok else 'err'):.3f}'></div>")
    if ok:
        faixa = "<div class='jf-rib ok'><i>✓</i><span>Correto!</span></div>"
        msg = (f"<div class='jf-msg'><img src='{AT.uri('trofeu_louro')}' alt='' aria-hidden='true'><div><b>Você acertou a resposta!</b><span>Mandou bem, investidor!</span></div>{_louro()}</div>")
        feitos, total = int(s.get("feitos") or 0), int(s.get("total") or 0)
        faltam = max(total - feitos, 0)
        caixa = (f"<div class='jf-box'><div class='c'><span class='ic'>✓</span><div><b>Progresso</b><em>{feitos}/{total}</em><small>perguntas certas</small></div></div>"
                 f"<div class='c'><img src='{AT.uri('xp')}' alt=''><div><b>XP</b><em>+{xp_conclusao}</em><small>ao concluir a lição</small></div></div></div>")
        extra = f"<div class='jf-exp'><small>Por que está certo</small>{_e(ex['explicacao'])}</div>" if ex.get("explicacao") else ""
        return "<div class='jf-resp'>" + banner + faixa + msg + caixa + extra + "</div>"
    faixa = "<div class='jf-rib err'><i>✕</i><span>Ops...</span></div>"
    msg = "<div class='jf-msg2'><b>Resposta incorreta!</b><span>Não desanime, você aprende com cada tentativa!</span></div>"
    letra = letra_correta(ex)
    from jornada import resposta_certa_texto
    marca = _e(letra) if letra else "✓"
    caixa = (f"<div class='jf-ans'><small>Resposta correta:</small><div class='r'><i>{marca}</i><span>{_e(resposta_certa_texto(ex))}</span></div></div>")
    extra = (f"<div class='jf-exp'><small>Por que</small>{_e(ex['explicacao'])}<div class='d'>Esta pergunta volta no fim da lição para você tentar de novo.</div></div>"
             if ex.get("explicacao") else "<div class='jf-exp'><div class='d'>Esta pergunta volta no fim da lição para você tentar de novo.</div></div>")
    return "<div class='jf-resp'>" + banner + faixa + msg + caixa + extra + "</div>"


def html_dica(ok: bool, eid: str) -> str:
    return (f"<div class='jf-dica'><span class='b'>💡</span><div><b>Dica do Caramelo:</b><q>{_e(dica_caramelo(ok, eid))}</q></div>"
            "<svg viewBox='0 0 40 40' aria-hidden='true'><ellipse cx='20' cy='26' rx='9' ry='8'/><ellipse cx='8' cy='15' rx='4' ry='5'/><ellipse cx='16' cy='8' rx='4' ry='5'/>"
            "<ellipse cx='25' cy='8' rx='4' ry='5'/><ellipse cx='33' cy='15' rx='4' ry='5'/></svg></div>")


def fundo_resposta(ok: bool) -> str:
    cor, cor2 = ("#3DDC97", "#6CF0A0") if ok else ("#FF4D5E", "#FF8A8A")
    barras = "".join(f"<rect x='{x}' y='{y}' width='16' height='{500 - y}' rx='3' fill='{cor2}' opacity='.5'/>" for x, y in ((250, 468), (272, 452), (294, 440), (316, 424), (338, 404), (360, 384)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 500' preserveAspectRatio='xMaxYMax slice'><defs>"
           f"<radialGradient id='g' cx='.5' cy='.1' r='.7'><stop offset='0' stop-color='{cor}' stop-opacity='.28'/><stop offset='1' stop-color='{cor}' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='500' fill='url(#g)'/><path d='M0 500 Q160 476 400 396' fill='none' stroke='" + cor2 + "' stroke-width='3' opacity='.55'/>" + barras + "</svg>")
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def css_resposta(ok: bool) -> str:
    p = P
    cor = "#3DDC97" if ok else "#FF4D5E"
    return ("<style>"
            f"{p}{{padding:0 0 18px !important;overflow:hidden;border-color:{'#2EE59D' if ok else '#FF4D5E'} !important;"
            f"background:url(\"{fundo_resposta(ok)}\") right bottom/cover no-repeat,linear-gradient(180deg,{'#0E1F4A' if ok else '#25104A'},#0A0832 90%) !important;"
            f"box-shadow:0 0 34px -8px {'rgba(46,229,157,.7)' if ok else 'rgba(255,77,94,.7)'} !important}}"
            f"{p} > div[data-testid='stElementContainer']{{padding:0 14px}}{p} > div[data-testid='stElementContainer']:has(.jf-ban){{padding:0 !important}}"
            ".jf-resp>*:not(.jf-ban):not(.jf-rib){margin-left:14px !important;margin-right:14px !important}"
            ".jf-ban{margin:0;line-height:0}.jf-ban img{width:100%;height:auto;display:block}"
            ".jf-rib{position:relative;z-index:2;display:flex;align-items:center;justify-content:center;gap:14px;margin:-12px 18px 12px;padding:10px 18px;border-radius:20px;"
            "font-weight:900;font-size:clamp(1.7rem,8vw,2.4rem);color:#fff !important;transform:perspective(500px) rotateX(4deg)}"
            ".jf-rib span{color:#fff !important;text-shadow:0 2px 6px rgba(0,0,0,.45)}"
            ".jf-rib i{flex:none;width:52px;height:52px;border-radius:50%;display:grid;place-items:center;font-style:normal;font-size:1.9rem;border:4px solid #fff;color:#fff !important}"
            ".jf-rib.ok{background:linear-gradient(180deg,#0F5A35,#0A3D26);border:3px solid #5BFF8F;box-shadow:0 0 22px rgba(91,255,143,.65),inset 0 0 14px rgba(91,255,143,.25)}"
            ".jf-rib.ok i{background:#12803F;border-color:#CFFFE0}"
            ".jf-rib.err{background:linear-gradient(180deg,#E5313E,#A8141F);border:3px solid #FF8A8A;box-shadow:0 0 22px rgba(255,77,94,.6),inset 0 0 14px rgba(255,255,255,.18)}"
            ".jf-rib.err i{background:transparent}"
            ".jf-msg{display:flex;align-items:center;justify-content:center;gap:8px;margin:6px 0 12px;text-align:left}"
            ".jf-msg img{flex:none;width:64px;height:auto}.jf-msg b{display:block;font-size:clamp(1.05rem,4.6vw,1.35rem);font-weight:900;color:#fff !important;line-height:1.15}"
            ".jf-msg span{display:block;color:#D6DDF5 !important;font-size:clamp(.88rem,3.6vw,1.05rem)}.jf-louro{flex:none;width:36px;height:54px}"
            ".jf-msg2{text-align:center;margin:4px 0 12px}.jf-msg2 b{display:block;font-size:clamp(1.15rem,5vw,1.5rem);font-weight:900;color:#fff !important}"
            ".jf-msg2 span{display:block;margin-top:4px;color:#D6DDF5 !important;font-size:clamp(.9rem,3.8vw,1.1rem);line-height:1.3}"
            ".jf-box{display:grid;grid-template-columns:1fr 1fr;border-radius:22px;border:2px solid #6C5CFF;background:linear-gradient(135deg,#1E1360,#140C42);box-shadow:0 0 16px -6px rgba(108,92,255,.8);margin:0 0 12px}"
            ".jf-box .c{display:flex;align-items:center;gap:10px;padding:12px 14px}.jf-box .c+.c{border-left:1px solid rgba(255,255,255,.18)}"
            ".jf-box .c img{flex:none;width:40px;height:40px}.jf-box .ic{flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:#3DDC97;color:#06281A !important;font-weight:900}"
            ".jf-box b{display:block;font-size:.95rem;color:#E9E4FF !important}.jf-box em{display:block;font-style:normal;font-weight:900;font-size:1.7rem;line-height:1.05;color:#fff !important}"
            ".jf-box small{display:block;font-size:.8rem;color:#C9C2F0 !important}"
            ".jf-ans{border-radius:20px;border:2px solid #5B4BE0;background:linear-gradient(135deg,#1A1155,#120B3C);padding:12px 16px;margin:0 0 12px}"
            ".jf-ans small{display:block;font-weight:800;font-size:1rem;color:#E9E4FF !important}"
            ".jf-ans .r{display:flex;align-items:center;gap:14px;margin-top:8px}.jf-ans .r i{flex:none;width:44px;height:44px;border-radius:50%;display:grid;place-items:center;font-style:normal;font-weight:900;font-size:1.3rem;color:#fff !important;"
            "background:#0F3329;border:3px solid #3DDC97}.jf-ans .r span{font-weight:700;font-size:clamp(1rem,4.2vw,1.2rem);color:#fff !important;overflow-wrap:anywhere}"
            ".jf-exp{border-radius:18px;border:1px solid rgba(255,255,255,.16);background:rgba(10,8,50,.6);padding:10px 14px;margin:0 0 12px;color:#EDE9FF !important;font-size:.95rem;line-height:1.4}"
            ".jf-exp small{display:block;margin-bottom:3px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;font-size:.7rem;color:#C5B3FF !important}"
            ".jf-exp .d{margin-top:6px;font-size:.82rem;color:#C9C2F0 !important}"
            # Continuar
            f"{p} div[class*='st-key-jor_sc'] button{{position:relative;min-height:60px !important;border-radius:999px !important;border:0 !important;"
            + ("background:linear-gradient(180deg,#8CFFA0,#2EE06A) !important;box-shadow:0 5px 0 #1B9A45,0 0 22px -4px rgba(61,220,151,.7) !important}" if ok
               else "background:linear-gradient(180deg,#6C4DFF,#4326C9) !important;box-shadow:0 5px 0 #2A1790,0 0 22px -4px rgba(108,77,255,.7) !important}")
            + f"{p} div[class*='st-key-jor_sc'] button :is(p,span){{color:{'#08301A' if ok else '#fff'} !important;-webkit-text-fill-color:{'#08301A' if ok else '#fff'} !important;font-weight:900 !important;font-size:1.35rem !important}}"
            f"{p} div[class*='st-key-jor_sc'] button:after{{content:'»';position:absolute;right:22px;top:50%;transform:translateY(-50%);font-size:2rem;font-weight:900;color:{'#08301A' if ok else '#fff'}}}"
            # Dica do Caramelo
            ".jf-dica{display:flex;align-items:center;gap:12px;border-radius:20px;border:1.5px solid rgba(124,108,255,.5);background:rgba(14,10,60,.7);padding:10px 14px;margin:12px 0 0}"
            ".jf-dica .b{flex:none;font-size:1.9rem}.jf-dica div{flex:1;min-width:0}.jf-dica b{display:block;color:#FFD76A !important;font-weight:800;font-size:1rem}"
            ".jf-dica q{display:block;color:#EDE9FF !important;font-size:.95rem;line-height:1.3;quotes:'\\201C' '\\201D'}"
            ".jf-dica svg{flex:none;width:34px;height:34px;fill:#6C5CFF;opacity:.45}"
            "</style>")
