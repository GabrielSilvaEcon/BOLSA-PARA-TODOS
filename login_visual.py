"""Visual da tela de entrada (azul-marinho com dourado): fundo com velas e seta de alta, mascote em anel dourado, abas sublinhadas em
dourado, campos em caixa com ícone, botão ENTRAR dourado e Google em pílula azul. Só aparência: nenhuma regra de login mora aqui.
A folha é uma linha só (st.markdown trata o que vem depois de </style> como texto) e entra DEPOIS do CSS base de usuarios._css_login."""
from __future__ import annotations

import base64

_Q = "html body .stApp"
_C = "html body .st-key-login_card"


def _svg_velas() -> str:
    """Velas azuis + curva luminosa + seta dourada de alta (decoração do topo do cartão). Largura 400, altura 230."""
    velas = [(14, 120, 40, 30), (34, 100, 36, 38), (54, 130, 34, 26), (74, 90, 50, 40), (94, 105, 40, 30), (114, 80, 46, 34), (134, 96, 38, 28),
             (254, 90, 40, 34), (274, 70, 46, 36), (294, 84, 38, 30), (314, 52, 50, 40), (334, 64, 42, 32), (354, 36, 46, 34), (374, 48, 38, 28)]
    corpo = "".join(f'<line x1="{x + 4}" y1="{y - 12}" x2="{x + 4}" y2="{y + h + 14}" stroke="#2F4FC8" stroke-width="1.5" opacity=".55"/>'
                    f'<rect x="{x}" y="{y}" width="8" height="{h}" rx="1.5" fill="#2A4BD0" opacity=".6"/>' for x, y, h, _w in velas)
    s = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 230" preserveAspectRatio="xMidYMin slice">'
         '<defs><linearGradient id="o" x1="0" x2="1"><stop offset="0" stop-color="#F2B84B" stop-opacity="0"/><stop offset="1" stop-color="#FFD66B"/></linearGradient>'
         '<linearGradient id="a" x1="0" x2="1"><stop offset="0" stop-color="#2F6BFF" stop-opacity="0"/><stop offset=".6" stop-color="#3D7BFF"/><stop offset="1" stop-color="#2F6BFF" stop-opacity="0"/></linearGradient></defs>'
         + corpo +
         '<path d="M0 150 C60 118 110 112 150 150" fill="none" stroke="url(#a)" stroke-width="3" opacity=".8"/>'
         '<path d="M250 118 C300 108 340 84 372 44" fill="none" stroke="url(#o)" stroke-width="5" stroke-linecap="round"/>'
         '<path d="M356 40 L378 32 L370 58 Z" fill="#FFD66B"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()


def _svg_arcos() -> str:
    """Arcos dourados nos cantos da página (decoração de fundo)."""
    s = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 800" preserveAspectRatio="none">'
         '<path d="M-20 120 C60 40 140 0 230 -10" fill="none" stroke="#F2B84B" stroke-width="3" opacity=".7"/>'
         '<path d="M-20 150 C70 70 150 20 250 6" fill="none" stroke="#FFD66B" stroke-width="1.5" opacity=".45"/>'
         '<path d="M-20 760 C120 800 280 790 430 690" fill="none" stroke="#F2B84B" stroke-width="3" opacity=".7"/>'
         '<path d="M-20 790 C140 830 300 810 430 730" fill="none" stroke="#FFD66B" stroke-width="1.5" opacity=".45"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()


def css() -> str:
    r = [
        # fundo da página e cartão
        f'{_Q}[class],html body [data-testid="stAppViewContainer"][class],html body [data-testid="stMain"][class]{{background:url("{_svg_arcos()}") center/100% 100% no-repeat,'
        'radial-gradient(700px 500px at 50% 10%,rgba(46,92,255,.30),transparent 70%),linear-gradient(170deg,#0C1858 0%,#09113F 50%,#050924 100%) !important;background-attachment:fixed !important}',
        f'{_C}{{max-width:420px !important;border-radius:28px !important;border:1.5px solid rgba(110,140,255,.42) !important;'
        f'background:url("{_svg_velas()}") top center/100% auto no-repeat,linear-gradient(180deg,rgba(22,36,120,.62),rgba(9,16,66,.82)) !important;'
        'box-shadow:0 30px 60px -22px rgba(0,0,0,.7),inset 0 1px 0 rgba(160,180,255,.25) !important}',
        # mascote em anel dourado e nome
        'html body .lg-ringav,html body .lg-ringdog{background:linear-gradient(135deg,#FFE08A,#F2B84B 55%,#C98A1B) !important;box-shadow:0 0 34px rgba(242,184,75,.45),0 12px 26px rgba(0,0,0,.5) !important}',
        'html body .lg-ringdog{width:124px !important;height:124px !important}',
        'html body .lg-marca2{font-size:2.05rem !important;letter-spacing:-.02em !important;font-weight:900 !important}',
        'html body .lg-marca2 span{color:#fff !important}',
        'html body .lg-marca2 b{background:linear-gradient(180deg,#FFE08A,#F2B84B 70%);-webkit-background-clip:text;background-clip:text;color:transparent !important;-webkit-text-fill-color:transparent !important}',
        'html body .lg-s h2{font-size:1.3rem !important;font-weight:900 !important;color:#fff !important}',
        'html body .lg-s p{color:#D5DBFF !important;font-size:.84rem !important}',
        'html body .lg-dots i{background:rgba(160,175,235,.45) !important}',
        '@keyframes lgdot2{0%,30%{width:28px;background:#F2B84B}34%,100%{width:7px;background:rgba(160,175,235,.45)}}',
        'html body .lg-dots i{animation-name:lgdot2 !important}',
        'html body .lg-ou::before,html body .lg-ou::after{background:rgba(120,140,240,.45) !important}',
        'html body .lg-ou,html body .lg-ou span{color:#D5DBFF !important;-webkit-text-fill-color:#D5DBFF !important}',
        # abas: sublinhado dourado
        f'{_Q} .st-key-login_card .stTabs [data-baseweb="tab-list"]{{border-bottom:1.5px solid rgba(120,140,240,.4) !important}}',
        f'{_Q} .st-key-login_card .stTabs [data-baseweb="tab"] p{{color:#E6EAFF !important;-webkit-text-fill-color:#E6EAFF !important;font-weight:600 !important}}',
        f'{_Q} .st-key-login_card .stTabs [data-baseweb="tab"][aria-selected="true"]{{border:0 !important;box-shadow:inset 0 -3px 0 #F2B84B !important}}',
        f'{_Q} .st-key-login_card .stTabs [data-baseweb="tab"][aria-selected="true"] p{{color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important;font-weight:800 !important}}',
        f'{_Q} .st-key-login_card .stTabs [data-baseweb="tab-highlight"]{{background:#F2B84B !important;height:3px !important}}',
        # campos em caixa com ícone (o rótulo vira placeholder); a caixa é o elemento raiz do campo
        f'{_Q} .st-key-login_card [data-testid="stTextInputRootElement"]{{background:rgba(24,36,118,.55) !important;border:1.5px solid rgba(120,140,240,.45) !important;border-radius:18px !important;min-height:52px !important;overflow:hidden}}',
        f'{_Q} .st-key-login_card [data-testid="stTextInputRootElement"]:focus-within{{border-color:#F2B84B !important;box-shadow:0 0 0 3px rgba(242,184,75,.2) !important}}',
        f'{_Q} .st-key-login_card [data-testid="stTextInputRootElement"] :is([data-baseweb="input"],[data-baseweb="base-input"]){{border:0 !important;border-radius:0 !important;box-shadow:none !important;background:transparent !important}}',
        f'{_Q} .st-key-login_card [data-baseweb="input"] input{{padding-left:54px !important;font-size:1rem !important}}',
        f'{_Q} .st-key-login_card [data-baseweb="input"]::before{{left:18px !important;width:22px !important;height:22px !important}}',
        f'{_Q} .st-key-login_card [data-baseweb="input"] input::placeholder{{color:#AEB8F0 !important;-webkit-text-fill-color:#AEB8F0 !important}}',
        # marcar "manter conectado"
        f'{_C} [data-baseweb="checkbox"] span:first-child{{border-radius:7px !important;border:2px solid rgba(150,165,255,.7) !important;background:rgba(24,36,118,.55) !important}}',
        f'{_C} [data-baseweb="checkbox"] p{{color:#E6EAFF !important;-webkit-text-fill-color:#E6EAFF !important;font-size:.92rem !important}}',
        # botão principal dourado
        f'{_Q} .st-key-login_card button[data-testid^="stBaseButton-primary"]{{background:linear-gradient(180deg,#FFD66B,#F2A81D) !important;border:1.5px solid #FFE08A !important;'
        'box-shadow:0 8px 22px -8px rgba(242,168,29,.8),0 3px 0 #B97A0C !important;min-height:3.2rem !important}',
        f'{_Q} .st-key-login_card button[data-testid^="stBaseButton-primary"] :is(p,span){{color:#1B1B3A !important;-webkit-text-fill-color:#1B1B3A !important;font-weight:900 !important;letter-spacing:.06em !important}}',
        # Google: pílula azul, texto branco em maiúsculas
        f'{_Q} .st-key-login_card .stButton.st-key-login_google button[data-testid^="stBaseButton-primary"]{{background:linear-gradient(180deg,rgba(40,62,160,.85),rgba(24,38,112,.9)) !important;border:1.5px solid rgba(120,140,240,.55) !important;box-shadow:0 6px 16px -8px rgba(0,0,0,.7) !important}}',
        f'{_Q} .st-key-login_card .stButton.st-key-login_google button[data-testid^="stBaseButton-primary"]:is(button,:hover) :is(p,span,[data-testid="stIconMaterial"]){{color:#fff !important;-webkit-text-fill-color:#fff !important;text-transform:uppercase !important;letter-spacing:.04em !important;font-size:.88rem !important;font-weight:800 !important;padding-left:1.4rem}}',
        f'{_Q} .st-key-login_card .stButton.st-key-login_google button[data-testid^="stBaseButton-primary"]:hover{{background:linear-gradient(180deg,rgba(54,80,190,.9),rgba(30,46,130,.95)) !important}}',
        # expansores discretos: cabeçalho e conteúdo na mesma cor, sem cantos quadrados soltos
        f'{_Q} .st-key-login_card [data-testid="stExpander"]{{border:1.5px solid rgba(120,140,240,.4) !important;border-radius:18px !important;background:rgba(24,36,118,.4) !important;overflow:hidden !important}}',
        f'{_Q} .st-key-login_card [data-testid="stExpander"] :is(details,summary,[data-testid="stExpanderDetails"]){{background:transparent !important;border:0 !important;border-radius:0 !important;box-shadow:none !important}}',
        f'{_Q} .st-key-login_card [data-testid="stExpander"] summary{{border-bottom:1px solid rgba(120,140,240,.25) !important}}',
        f'{_Q} .st-key-login_card [data-testid="stExpander"] summary p{{color:#E6EAFF !important;-webkit-text-fill-color:#E6EAFF !important;font-weight:700 !important}}',
        f'{_Q} .st-key-login_card [data-testid="stExpanderDetails"]{{padding:10px 12px 12px !important}}',
        f'{_Q} .st-key-login_card [data-testid="stExpanderDetails"] [data-testid="stMarkdownContainer"] p{{font-size:.86rem !important;line-height:1.45 !important;color:#D5DBFF !important;-webkit-text-fill-color:#D5DBFF !important}}',
        f'{_Q} .st-key-login_card .ct-li{{background:rgba(24,36,118,.55) !important;border:1px solid rgba(120,140,240,.35) !important;border-radius:14px !important;padding:8px 12px !important;margin:6px 0 !important;gap:6px !important}}',
        f'{_Q} .st-key-login_card .ct-li .t{{font-size:.84rem !important;font-weight:700 !important;color:#E6EAFF !important;-webkit-text-fill-color:#E6EAFF !important;min-width:0;overflow-wrap:anywhere}}',
        f'{_Q} .st-key-login_card .ct-chip{{max-width:100%;overflow-wrap:anywhere;font-size:.74rem !important;padding:2px 10px !important}}',
    ]
    return "<style>" + "".join(r) + "</style>"
