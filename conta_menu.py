"""Menu da conta (janela "Minha Conta"): cabeçalho com avatar, apelido, nível e XP, mais as linhas de atalho.
Só apresentação: os números (nível, XP) chegam prontos do chamador, que os lê dos mesmos serviços do cabeçalho do app."""
from __future__ import annotations

import html

import arte_conta as ART

_P = "html body [data-testid=\"stDialog\"] [role=\"dialog\"]:has(.cta-hd)"

_COROA = ("<svg width='18' height='18' viewBox='0 0 24 24' fill='#F6C453' aria-hidden='true'>"
          "<path d='M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z'/></svg>")
_USER = "<svg width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='#EDE9FF' stroke-width='1.8'><circle cx='12' cy='8' r='4'/><path d='M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7'/></svg>"


def _milhar(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def cabecalho_html(nome: str, nivel: int | None = None, xp_no_nivel: int = 0, faixa: int = 0, pct: float = 0.0, maximo: bool = False) -> str:
    """Título, subtítulo e cartão do usuário. Sem `nivel` (visitante), mostra só o nome."""
    av = ART.uri("avatar")
    arte = ART.uri("cabecalho")
    avatar = f"<div class='cta-av'><img src='{av}' alt=''></div>" if av else ""
    if nivel is None:
        info = ""
    else:
        p = max(0.0, min(1.0, float(pct))) * 100
        xp = "Nível máximo" if maximo else f"{_milhar(xp_no_nivel)} / {_milhar(faixa)} XP"
        info = (f"<div class='cta-xp'>{html.escape(xp)}</div><div class='cta-bar'><i style='width:{p:.0f}%'></i></div>")
    badge = f"<span class='cta-nv'>{_COROA}Nível {int(nivel)}</span>" if nivel is not None else ""
    fundo = f" style=\"--arte:url('{arte}')\"" if arte else ""
    return (f"<div class='cta-hd'{fundo}><div class='cta-ic'>{_USER}</div><div><div class='cta-t'>Minha Conta</div>"
            "<div class='cta-s'>Gerencie sua conta e acesse suas opções</div></div></div>"
            f"<div class='cta-card'>{avatar}<div class='cta-info'><div class='cta-l1'><span class='cta-nome'>{html.escape(nome)}</span>{badge}</div>{info}</div></div>")


def css() -> str:
    return f"""<style>
{_P}{{background:linear-gradient(165deg,#2B1A75,#160F4A 70%) !important;border:1.5px solid rgba(139,108,255,.7) !important;border-radius:26px !important;box-shadow:0 0 28px rgba(124,92,255,.35) !important}}
{_P} h2,{_P} [data-testid="stDialogHeader"] h2{{display:none !important}}
{_P} [data-testid="stDialogHeader"]{{padding:0 !important;margin:0 !important;min-height:0 !important}}
{_P} button[aria-label="Close"]{{position:absolute !important;top:14px;right:14px;z-index:30;background:transparent !important;border:0 !important;box-shadow:none !important;width:auto !important;min-height:0 !important;padding:4px !important}}
{_P} button[aria-label="Close"] *{{color:#fff !important;fill:#fff !important}}
{_P} .cta-hd{{position:relative;display:flex;align-items:center;gap:14px;padding:4px 40px 14px 2px;margin:0 0 12px;border-bottom:1px solid rgba(139,108,255,.55);
  background:var(--arte,none) right bottom/auto 100% no-repeat}}
{_P} .cta-ic{{display:grid;place-items:center;flex:0 0 auto;width:52px;height:52px;border-radius:50%;border:2px solid #8B5CF6;background:#1B1050;box-shadow:0 0 12px rgba(139,92,246,.55)}}
{_P} .cta-t{{font-size:1.55rem;font-weight:800;line-height:1.1;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .cta-s{{font-size:.84rem;color:#C4BEEA !important;-webkit-text-fill-color:#C4BEEA !important;margin-top:2px}}
{_P} .cta-card{{display:flex;align-items:center;gap:14px;padding:12px;margin:0 0 12px;border-radius:18px;background:rgba(20,12,70,.55)}}
{_P} .cta-av{{flex:0 0 auto;width:78px;height:78px;border-radius:50%;padding:3px;background:linear-gradient(160deg,#C084FC,#6D28D9);box-shadow:0 0 14px rgba(167,139,250,.65)}}
{_P} .cta-av img{{display:block;width:100%;height:100%;border-radius:50%;object-fit:cover}}
{_P} .cta-info{{min-width:0;flex:1}}
{_P} .cta-l1{{display:flex;align-items:center;flex-wrap:wrap;gap:8px}}
{_P} .cta-nome{{font-size:1.2rem;font-weight:800;color:#fff !important;-webkit-text-fill-color:#fff !important;overflow-wrap:anywhere}}
{_P} .cta-nv{{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:.8rem;font-weight:800;color:#fff !important;-webkit-text-fill-color:#fff !important;background:#1B1050;border:1.5px solid #8B5CF6}}
{_P} .cta-xp{{margin:6px 0 5px;font-size:.84rem;font-weight:600;color:#B9B2E6 !important;-webkit-text-fill-color:#B9B2E6 !important}}
{_P} .cta-bar{{height:9px;border-radius:999px;background:rgba(255,255,255,.1);overflow:hidden}}
{_P} .cta-bar i{{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#8B5CF6,#A78BFA)}}
/* linhas de atalho: ícone, texto à esquerda e seta à direita */
{_P} [data-testid="stVerticalBlock"]{{gap:.55rem !important}}
{_P} :is(a[data-testid="stPageLink-NavLink"], .stButton > button:not([aria-label="Close"])){{display:flex !important;align-items:center !important;justify-content:flex-start !important;gap:14px !important;width:100% !important;min-height:52px !important;padding:6px 14px !important;border-radius:18px !important;
  background:linear-gradient(160deg,#2A1B6B,#1C1252) !important;border:1.2px solid rgba(139,108,255,.75) !important;box-shadow:0 0 0 1px rgba(0,0,0,.25) inset !important}}
{_P} :is(a[data-testid="stPageLink-NavLink"], .stButton > button:not([aria-label="Close"])) :is(p,span,svg){{color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;fill:#EDE9FF !important;font-size:1.02rem !important;font-weight:600 !important}}
{_P} :is(a[data-testid="stPageLink-NavLink"], .stButton > button:not([aria-label="Close"]))::after{{content:"\\203A";margin-left:auto;font-size:1.7rem;line-height:1;color:#EDE9FF}}
{_P} [data-testid="stMarkdownContainer"],{_P} .stButton > button > div{{margin:0 !important}}
{_P} .stButton > button > div{{display:flex;align-items:center;gap:14px;flex:1;justify-content:flex-start}}
{_P} :is(a[data-testid="stPageLink-NavLink"], .stButton > button:not([aria-label="Close"])):hover{{border-color:#A78BFF !important;background:linear-gradient(160deg,#35238A,#231766) !important}}
{_P} .st-key-cta_modo{{position:relative}}
{_P} .st-key-cta_modo::after{{content:"Atual";position:absolute;right:46px;top:50%;transform:translateY(-50%);padding:2px 10px;border-radius:999px;font-size:.74rem;font-weight:800;color:#4ADE80;border:1.2px solid #34D399;background:rgba(16,80,60,.35);pointer-events:none}}
</style>"""
