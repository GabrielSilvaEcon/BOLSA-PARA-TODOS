"""Telas de conta (Passo 21): entrada (login, cadastro, recuperação), painel do usuário, perfil, preferências,
segurança, atividades, privacidade (LGPD) e painel administrativo.

Tudo aparece em cards e cores (nada de texto cru). Esta camada só desenha e chama contas.py / banco.py: as regras de
segurança e de permissão ficam lá, não aqui. Textos vindos do usuário passam por html.escape antes de entrar no HTML.
"""
from __future__ import annotations

import html
import json
from datetime import timedelta, timezone

import streamlit as st

import secoes

import banco
import contas
import email_envio as mail
import permissoes as perm
import experiencia as EXP
import experiencia_app
import prefs as P
import seguranca as seg
import usuarios

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # sem base de fusos: horário de Brasília fixo
    _TZ = timezone(timedelta(hours=-3))

PAGINAS: dict = {}     # app.py registra aqui as páginas para os atalhos do painel


TODAS: dict = {}       # url_path -> título de todas as páginas (app.py registra); usado em "Páginas por plano"


def _PAGINAS_PLANO() -> dict:
    return dict(TODAS)


def registrar_paginas(**paginas) -> None:
    PAGINAS.update({k: v for k, v in paginas.items() if v is not None})


# ------------------------------------------------------------------ visual
CSS = """<style>
.ct-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 14px;}
.ct-k{--c:#8EA2FF;background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-left:4px solid var(--c);
  border-radius:14px;padding:12px 14px;color:#EDE9FF !important;}
.ct-k .l{font-size:.74rem;text-transform:uppercase;letter-spacing:.05em;color:#CFC8F0 !important;font-weight:700;}
.ct-k .v{font-size:1.4rem;font-weight:800;color:#F6F3FF !important;line-height:1.25;word-break:break-word;}
.ct-k .d{font-size:.8rem;color:#CFC8F0 !important;line-height:1.35;}
.ct-k.ok{--c:#34D399;} .ct-k.aviso{--c:#F59E0B;} .ct-k.erro{--c:#F87171;} .ct-k.na{--c:#94A3B8;}
.ct-m{--c:#8EA2FF;display:flex;gap:10px;align-items:flex-start;background:rgba(142,162,255,.12);border:1px solid var(--c);
  border-radius:14px;padding:12px 14px;margin:8px 0;color:#EDE9FF !important;line-height:1.5;}
.ct-m b{color:#F6F3FF !important;} .ct-m i{font-style:normal;font-size:1.15rem;line-height:1.3;}
.ct-m, .ct-m *, .ct-li, .ct-li .t, .ct-k, .stApp .ct-sec {color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;}
.ct-li .s, .ct-sub, .ct-k .l, .ct-k .d {color:#CFC8F0 !important;-webkit-text-fill-color:#CFC8F0 !important;}
.ct-k .v, .ct-li .t, .stApp .ct-sec {color:#F6F3FF !important;-webkit-text-fill-color:#F6F3FF !important;}
.ct-m.ok{--c:#34D399;background:rgba(52,211,153,.12);} .ct-m.aviso{--c:#F59E0B;background:rgba(245,158,11,.13);}
.ct-m.erro{--c:#F87171;background:rgba(248,113,113,.13);}
.ct-li{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;background:#1A1342;
  border:1px solid #382C78;border-radius:12px;padding:10px 12px;margin:6px 0;color:#EDE9FF !important;}
.ct-li .t{font-weight:700;color:#F6F3FF !important;} .ct-li .s{font-size:.82rem;color:#CFC8F0 !important;}
.ct-chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.75rem;font-weight:700;margin:2px 4px 2px 0;
  background:rgba(142,162,255,.18);color:#D0D8FF !important;border:1px solid rgba(142,162,255,.45);}
.ct-chip.ok{background:rgba(52,211,153,.16);color:#A7F3D0 !important;border-color:rgba(52,211,153,.5);}
.ct-chip.aviso{background:rgba(245,158,11,.16);color:#FDE68A !important;border-color:rgba(245,158,11,.5);}
.ct-chip.erro{background:rgba(248,113,113,.16);color:#FECACA !important;border-color:rgba(248,113,113,.5);}
.ct-chip.na{background:rgba(148,163,184,.16);color:#CBD5E1 !important;border-color:rgba(148,163,184,.4);}
.ct-sec{margin:14px 0 4px;font-weight:800;font-size:1.05rem;color:#F6F3FF !important;}
.ct-sub{margin:0 0 8px;font-size:.88rem;color:#CFC8F0 !important;}
.ct-forca{height:8px;border-radius:99px;background:#382C78;overflow:hidden;margin:2px 0 4px;}
.ct-forca i{display:block;height:100%;border-radius:99px;}
.st-key-acesso_card{background:linear-gradient(160deg,#1E1650,#150E34);border:1px solid #3D3182;border-radius:20px;
  padding:16px 16px 10px;box-shadow:0 14px 30px rgba(42,31,122,.28);}
.st-key-acesso_card label, .st-key-acesso_card p, .st-key-acesso_card li, .st-key-acesso_card span,
.st-key-acesso_card [data-testid="stWidgetLabel"] {color:#EDE9FF !important;}
.st-key-acesso_card button[role="tab"] p {color:#E3DDFA !important;font-weight:700;}
.st-key-acesso_card button[role="tab"][aria-selected="true"] p {color:#7EE0B0 !important;}
.st-key-acesso_card .stButton button, .st-key-acesso_card [data-testid="stFormSubmitButton"] button {border-radius:999px;font-weight:800;}
</style>"""


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _kpi(rot, valor, cls="info", detalhe="") -> str:
    d = f"<div class='d'>{_e(detalhe)}</div>" if detalhe else ""
    return f"<div class='ct-k {cls}'><div class='l'>{_e(rot)}</div><div class='v'>{_e(valor)}</div>{d}</div>"


def _grade(itens: list[str]) -> str:
    return "<div class='ct-grid'>" + "".join(itens) + "</div>"


def _msg(texto, cls="info", icone=None) -> str:
    ic = icone or {"ok": "✔", "aviso": "⚠", "erro": "✖", "info": "ℹ"}.get(cls, "ℹ")
    return f"<div class='ct-m {cls}'><i>{ic}</i><div>{_e(texto)}</div></div>"


def _chip(txt, cls="") -> str:
    return f"<span class='ct-chip {cls}'>{_e(txt)}</span>"


def _linha(titulo, sub="", selo="") -> str:
    return f"<div class='ct-li'><div><div class='t'>{_e(titulo)}</div><div class='s'>{_e(sub)}</div></div><div>{selo}</div></div>"


def _titulo(txt, sub="") -> str:
    s = f"<div class='ct-sub'>{_e(sub)}</div>" if sub else ""
    return f"<div class='ct-sec'>{_e(txt)}</div>{s}"


def _fmt(iso) -> str:
    d = seg.de_iso(iso)
    return d.astimezone(_TZ).strftime("%d/%m/%Y %H:%M") if d else "—"


def _css():
    st.markdown(CSS, unsafe_allow_html=True)


def _enviar(rot, **k):
    """Botão de envio de formulário; se esta versão do Streamlit não aceitar `width`, usa o padrão."""
    try:
        return st.form_submit_button(rot, **k)
    except TypeError:
        k.pop("width", None)
        return st.form_submit_button(rot, **k)


def _sem_senha() -> bool:
    """Os formulários aparecem sempre; se o e-mail/banco ainda não foram configurados, avisa em vez de tentar."""
    if usuarios.senha_disponivel():
        return False
    st.markdown(_msg("Entrar e criar conta com e-mail e senha ainda não estão ativos neste app. "
                     "Use o Google para entrar.", "aviso"), unsafe_allow_html=True)
    return True


def _resultado(res) -> None:
    st.markdown(_msg(res.msg, "ok" if res.ok else "erro"), unsafe_allow_html=True)


# ------------------------------------------------------------------ tela de entrada
def _limpar_url():
    try:
        st.query_params.clear()
    except Exception:
        pass


def _param(nome: str) -> str:
    try:
        v = st.query_params.get(nome)
        return str(v or "")[:200] if not isinstance(v, list) else str(v[0])[:200]
    except Exception:
        return ""


def _barra_forca(senha: str) -> str:
    n, rot = seg.forca_senha(senha)
    cor = ("#F87171", "#F59E0B", "#FBBF24", "#34D399", "#10B981")[n]
    return f"<div class='ct-forca'><i style='width:{(n + 1) * 20}%;background:{cor}'></i></div><div class='ct-sub'>Força: {rot}</div>"


def _regras_senha() -> str:
    return (f"<div class='ct-sub'>A senha precisa de {seg.SENHA_MIN}+ caracteres, com letras e números, e não pode ser "
            "comum nem conter seu e-mail ou nome.</div>")


def _acesso_verificar(token: str) -> None:
    if st.session_state.get("_ver_token") != token:
        st.session_state["_ver_token"] = token
        st.session_state["_ver_res"] = contas.verificar_email(token)
    res = st.session_state["_ver_res"]
    _resultado(res)
    st.button("Ir para a entrada", key="ver_voltar", type="primary", width="stretch",
              on_click=lambda: (_limpar_url(), st.session_state.pop("_ver_token", None)))


def _acesso_redefinir(token: str) -> None:
    if not contas.token_redefinicao_valido(token):
        st.markdown(_msg("Esse link não é mais válido (já foi usado ou venceu). Peça outro em \"Esqueci minha senha\".", "erro"),
                    unsafe_allow_html=True)
        st.button("Voltar para a entrada", key="red_voltar", width="stretch", on_click=_limpar_url)
        return
    if st.session_state.get("_red_ok"):
        _resultado(st.session_state["_red_ok"])
        st.button("Ir para a entrada", key="red_ok_voltar", type="primary", width="stretch",
                  on_click=lambda: (_limpar_url(), st.session_state.pop("_red_ok", None)))
        return
    st.markdown(_titulo("Crie sua nova senha", "Escolha uma senha que você não usa em outros lugares."), unsafe_allow_html=True)
    with st.form("f_nova"):
        nova = st.text_input("Nova senha", type="password", key="nova_senha")
        conf = st.text_input("Repita a nova senha", type="password", key="nova_senha2")
        ok = _enviar("Salvar nova senha", type="primary", width="stretch")
    st.markdown(_regras_senha(), unsafe_allow_html=True)
    if ok:
        res = contas.redefinir_senha(token, nova, conf)
        if res.ok:
            st.session_state["_red_ok"] = res
            st.rerun()
        _resultado(res)


def _form_entrar():
    with st.form("f_entrar"):
        email = st.text_input("E-mail", key="in_email", autocomplete="email")
        senha = st.text_input("Senha", type="password", key="in_senha", autocomplete="current-password")
        lembrar = st.checkbox("Manter conectado neste aparelho por até 30 dias", key="in_lembrar")
        ok = _enviar("Entrar", type="primary", width="stretch")
    if ok and not _sem_senha():
        res = contas.entrar(email, senha, usuarios.cliente_id(), lembrar)
        if res.ok:
            res.dado["lembrar"] = lembrar
            usuarios.iniciar_sessao_senha(res)
            st.rerun()
        _resultado(res)
    with st.expander("Não recebi o e-mail de confirmação"):
        e2 = st.text_input("E-mail do cadastro", key="reenv_email")
        if st.button("Reenviar confirmação", key="reenv_btn", width="stretch") and not _sem_senha():
            _resultado(contas.reenviar_verificacao(e2, usuarios.cliente_id()))


def _form_criar():
    with st.form("f_criar"):
        nome = st.text_input("Nome", key="cr_nome", autocomplete="name")
        email = st.text_input("E-mail", key="cr_email", autocomplete="email")
        senha = st.text_input("Senha", type="password", key="cr_senha", autocomplete="new-password")
        conf = st.text_input("Repita a senha", type="password", key="cr_senha2", autocomplete="new-password")
        aceite = st.checkbox("Li e aceito que o app guarde meu nome, e-mail e o que eu salvar, só para funcionar (LGPD)", key="cr_aceite")
        ok = _enviar("Criar conta", type="primary", width="stretch")
    st.markdown(_regras_senha(), unsafe_allow_html=True)
    if ok and not _sem_senha():
        _resultado(contas.cadastrar(nome, email, senha, conf, aceite, usuarios.cliente_id()))


def _form_esqueci():
    st.markdown(_titulo("Recuperar acesso", "Enviaremos um link para criar uma nova senha. Vale por 1 hora e só funciona uma vez."),
                unsafe_allow_html=True)
    with st.form("f_esqueci"):
        email = st.text_input("E-mail da conta", key="es_email", autocomplete="email")
        ok = _enviar("Enviar link", type="primary", width="stretch")
    if ok and not _sem_senha():
        _resultado(contas.solicitar_redefinicao(email, usuarios.cliente_id()))


_CSS_LOGIN_COMPACTO = (
    "<style>"
    "html body .stApp [data-testid=\"stMain\"] .block-container{padding-top:.5rem !important;padding-bottom:.5rem !important}"
    "html body .stApp [data-testid=\"stHeader\"]{height:0 !important;min-height:0 !important}"
    "html body .st-key-login_card{margin:0 auto !important;padding:12px 18px 10px !important;gap:.4rem !important;border-radius:24px !important}"
    "html body .st-key-login_card [data-testid=\"stVerticalBlock\"]{gap:.4rem !important}"
    "html body .st-key-login_card [data-testid=\"stElementContainer\"]{margin:0 !important}"
    ".lg-hero{margin:0 !important}"
    ".lg-marca{margin:0 !important}"
    ".lg-slides{min-height:64px !important;margin:0 !important}"
    ".lg-s h2{font-size:1rem !important;margin:2px 0 3px !important}"
    ".lg-s p{font-size:.78rem !important;line-height:1.3 !important;max-width:340px !important}"
    ".lg-dots{margin:0 0 4px !important}"
    ".lg-ou{margin:2px 0 2px !important}"
    "html body .stApp .st-key-login_card button{min-height:2.5rem !important}"
    "html body .stApp .st-key-login_card .stTabs [data-baseweb=\"tab\"]{padding:4px 4px !important}"
    "html body .stApp .st-key-login_card [data-testid=\"stForm\"]{padding:.1rem 0 0 !important}"
    "html body .stApp .st-key-login_card [data-testid=\"stWidgetLabel\"]{margin-bottom:0 !important;min-height:0 !important}"
    "html body .stApp .st-key-login_card [data-baseweb=\"input\"] input{padding-top:6px !important;padding-bottom:6px !important}"
    "</style>"
)


def tela_acesso(logo_uri: str = "", nome: str = "TickerHunters") -> None:
    """Tela de entrada: Google e e-mail e senha (se configurado); não há acesso como visitante. Também recebe os links dos e-mails."""
    st.markdown(usuarios._css_login() + _CSS_LOGIN_COMPACTO, unsafe_allow_html=True)
    _css()
    img = f'<img src="{_e(logo_uri)}" alt="{_e(nome)}">' if logo_uri else ""
    ss = st.session_state
    with st.container(key="login_card"):
        pose = None
        try:
            import jornada_arte as _arte
            pose = _arte._uri_pose("inicio")
        except Exception:
            pose = None
        if pose:   # mascote acenando num anel igual ao do app + nome em duas cores (mesma linguagem do vidro roxo)
            abertura = (f'<div class="lg-hero"><div class="lg-ringav lg-ringdog"><div class="lg-av"><img src="{pose}" alt="Mascote {_e(nome)}"></div></div></div>'
                        '<div class="lg-marca lg-marca2"><span>Ticker</span><b>Hunters</b></div>'
                        '<style>.lg-ringdog{width:112px !important;height:112px !important}'
                        '.lg-ringdog .lg-av{overflow:hidden;background:radial-gradient(circle at 50% 40%,#3A2A75,#1B1442 75%)}'
                        '.lg-ringdog .lg-av img{width:100% !important;height:100% !important;border-radius:0 !important;object-fit:cover;object-position:50% 20%;transform:scale(1.12)}'
                        '.lg-marca2{text-transform:none !important;letter-spacing:-.01em !important;font-size:1.35rem !important;font-weight:900;padding-left:0 !important}'
                        '.lg-marca2 span{color:#fff}.lg-marca2 b{color:#8BE04E}</style>')
        else:
            abertura = (f'<div class="lg-hero"><div class="lg-ringav"><div class="lg-av">{img}</div></div></div>'
                        f'<div class="lg-marca">{_e(nome)}</div>')
        st.markdown(
            abertura +
            '<div class="lg-slides">'
                        '<div class="lg-s s1"><h2>Analise com clareza</h2>'
            '<p>Preço justo, gráficos e indicadores explicados em linguagem simples.</p></div>'
            '<div class="lg-s s2"><h2>Aprenda no seu ritmo</h2>'
            '<p>Lições curtas, quizzes e uma Jornada que dá XP e TickerCoins.</p></div>'
            '<div class="lg-s s3"><h2>Evolua jogando</h2>'
            '<p>Treine com dinheiro virtual (T$) na Wallet Game, suba de rank e acompanhe sua carteira em qualquer aparelho.</p></div></div>'
'<div class="lg-dots"><i></i><i></i><i></i></div>', unsafe_allow_html=True)
        tok_ver, tok_red = _param("verificar"), _param("redefinir")
        if tok_ver or tok_red:
            with st.container(key="acesso_card"):
                _acesso_verificar(tok_ver) if tok_ver else _acesso_redefinir(tok_red)
            return
        aviso = ss.pop("_aviso", None)
        if aviso:
            st.markdown(_msg(aviso, "aviso"), unsafe_allow_html=True)
        if ss.get("_negado"):
            st.markdown(_msg(ss["_negado"], "erro"), unsafe_allow_html=True)
            st.button("Sair do Google", key="negado_sair", icon=":material/logout:", on_click=usuarios.sair, width="stretch")
        if True:
            with st.container(key="acesso_card"):
                t1, t2, t3 = st.tabs(["Entrar", "Criar conta", "Esqueci a senha"])
                with t1:
                    _form_entrar()
                with t2:
                    _form_criar()
                with t3:
                    _form_esqueci()
        if usuarios._configurado():
            st.markdown('<div class="lg-ou"><span>ou continue com</span></div>', unsafe_allow_html=True)
        if usuarios._configurado():
            if st.button("Continuar com o Google", key="login_google", type="primary", width="stretch"):
                try:
                    st.login("google")
                except Exception as e:
                    st.markdown(_msg(f"Não foi possível iniciar o login ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
        with st.expander("Problemas para entrar?"):
            st.write("Abra o app direto no Chrome ou no Safari (não pelo navegador de dentro de outro app) e deixe os cookies liberados.")
            linhas = []
            for rot, val in usuarios._diagnostico().items():
                cls = "ok" if val is True else "erro" if val is False or str(val).startswith("erro") else "info"
                linhas.append(_linha(rot, "", _chip(str(val)[:60], cls)))
            st.markdown("".join(linhas), unsafe_allow_html=True)


# ------------------------------------------------------------------ painel do usuário
_ROTULO_ACAO = {
    "conta.criada": ("Conta criada", "ok"), "conta.verificada": ("E-mail confirmado", "ok"),
    "login": ("Entrou com e-mail e senha", "info"), "login.google": ("Entrou com o Google", "info"),
    "logout": ("Saiu da conta", "na"), "senha.alterada": ("Senha alterada", "aviso"),
    "senha.redefinida": ("Senha redefinida por e-mail", "aviso"), "perfil.nome": ("Nome atualizado", "info"),
    "sessoes.encerradas": ("Outros aparelhos desconectados", "aviso"), "dados.exportados": ("Dados baixados", "info"),
    "conta.suspensa": ("Conta suspensa pela administração", "erro"), "conta.reativada": ("Conta reativada", "ok"),
    "preferencias.salvas": ("Preferências salvas", "info"),
}
_SECOES = ["Painel", "Perfil", "Preferências", "Segurança", "Atividades", "Privacidade"]


def _cabecalho(titulo: str, sub: str) -> None:
    st.markdown(f'<div class="pghead"><div class="pgt">{_e(titulo)}</div><div class="pgsub">{_e(sub)}</div></div>',
                unsafe_allow_html=True)


def _atalho(chave: str, rotulo: str, icone: str) -> None:
    p = PAGINAS.get(chave)
    if p is not None:
        try:
            st.page_link(p, label=rotulo, icon=icone)
        except Exception:
            pass


def _data_br(iso) -> str:
    try:
        a, m, d = str(iso).split("-")
        return f"{int(d):02d}/{int(m):02d}/{a}"
    except Exception:
        return "—"


def _cartoes_plano(email, papel) -> None:
    """Etapa 5: plano da pessoa e quanto já usou hoje de cada recurso limitado."""
    import planos
    r = planos.resumo_do_usuario(email, papel)
    st.markdown(_titulo(f"Seu plano: {r['rotulo']}", "Limites de uso diário. Os três modos (Iniciante, Intermediário, Avançado) valem em todos os planos."), unsafe_allow_html=True)
    cards = []
    ass = r.get("assinatura") or {}
    if ass.get("vencida"):
        st.markdown(_msg(f"Sua assinatura {planos.ROTULO[ass['contratado']]} venceu em {_data_br(ass['ate'])}. Você voltou ao plano Gratuito; seus dados continuam guardados.", "aviso"), unsafe_allow_html=True)
    elif ass.get("carencia"):
        st.markdown(_msg(f"Sua assinatura {planos.ROTULO[ass['contratado']]} venceu em {_data_br(ass['ate'])}. Você está na carência: os limites do plano valem por mais "
                         f"{ass['carencia_dias'] + ass['dias']} dia(s). Peça a renovação ao administrador.", "aviso"), unsafe_allow_html=True)
    elif ass.get("dias") is not None and ass["plano"] in ("plus", "premium"):
        cards.append(_kpi("Validade do plano", _data_br(ass["ate"]), "erro" if ass["dias"] <= 3 else "aviso" if ass["dias"] <= 7 else "ok",
                          ("vence hoje" if ass["dias"] == 0 else f"faltam {ass['dias']} dias") + (" · renovação cancelada" if ass.get("cancelado") else "")))
    for x in r["linhas"]:
        if x["tipo"] == "dia" and x["aplicado"]:
            pct = x["usado"] / x["limite"] if x["limite"] else 1
            cards.append(_kpi(x["rotulo"], f"{x['usado']} de {x['limite']}", "erro" if pct >= 1 else "aviso" if pct >= .8 else "ok", "hoje · renova à meia-noite"))
        elif x["aplicado"]:
            cards.append(_kpi(x["rotulo"], x["limite"], "info", "mínimo entre verificações" if x["tipo"] == "min" else "máximo permitido"))
    st.markdown(_grade(cards), unsafe_allow_html=True)


def _assinatura_acoes(email, papel) -> None:
    """Etapas 11-13: teste grátis, cupom e cancelamento/reativação da renovação (só para contas reais, não equipe)."""
    import assinaturas
    import planos
    if papel in ("admin", "suporte"):
        return
    ass = planos.assinatura_de(email, papel)
    ok_teste, rot_teste = assinaturas.teste_disponivel(email, papel)
    with st.expander("Assinatura: cupom, teste grátis e cancelamento"):
        if ok_teste:
            st.markdown(_msg(rot_teste + ". Sem cartão, sem cobrança. Termina sozinho.", "info"), unsafe_allow_html=True)
            if st.button("Começar teste grátis", key="ass_teste", type="primary"):
                try:
                    st.markdown(_msg(assinaturas.iniciar_teste(email, papel), "ok"), unsafe_allow_html=True)
                except ValueError as e:
                    st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
        cod = st.text_input("Tem um cupom?", key="ass_cupom", max_chars=20, placeholder="Digite o código")
        if st.button("Usar cupom", key="ass_cupom_ok"):
            ok, msg = assinaturas.resgatar_cupom(email, cod, papel)
            st.markdown(_msg(msg, "ok" if ok else "erro"), unsafe_allow_html=True)
        if ass["contratado"] in ("plus", "premium") and not ass["vencida"]:
            if ass["cancelado"]:
                st.markdown(_msg(f"Renovação cancelada: seu plano vale até {_data_br(ass['ate'])} e depois volta ao Gratuito.", "aviso"), unsafe_allow_html=True)
                if st.button("Desfazer cancelamento", key="ass_reativar"):
                    try:
                        assinaturas.reativar_renovacao(email)
                        st.markdown(_msg("Cancelamento desfeito.", "ok"), unsafe_allow_html=True)
                    except ValueError as e:
                        st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
            elif st.button("Cancelar renovação", key="ass_cancelar"):
                try:
                    r = assinaturas.cancelar_renovacao(email)
                    st.markdown(_msg("Você voltou ao plano Gratuito." if r == "agora" else
                                     f"Renovação cancelada. Você mantém o plano até {_data_br(ass['ate'])}.", "ok"), unsafe_allow_html=True)
                except ValueError as e:
                    st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
        if ass["historico"]:
            _tabela([{"quando": _data_br(h[0]), "evento": h[1], "detalhe": h[2]} for h in reversed(ass["historico"][-8:])],
                    {"quando": "Quando", "evento": "O que aconteceu", "detalhe": "Detalhe"})


def _secao_painel(u: dict) -> None:
    ss = st.session_state
    try:
        _cartoes_plano(u["email"], u["papel"])
        if u["papel"] not in ("admin", "suporte"):
            import pagamentos_app
            pagamentos_app.bloco_pendente(u["email"], "pgc")
        _assinatura_acoes(u["email"], u["papel"])
    except Exception as e:
        banco.registrar_erro("conta_app.plano", e)
    pr = usuarios.preferencias()
    lotes = len(ss.get("cart_ficticia", [])) + len(ss.get("cart_real", []))
    regras = sum(len(ss.get(k) or []) for k in ("risco_regras", "intel_regras", "tec_av_regras", "ne_regras"))
    modelos = len(ss.get("cart_cmp_modelos") or [])
    blocos = {
        "resumo": lambda: st.markdown(_grade([
            _kpi("Empresas em análise", len(ss.get("sel_ativos", [])), "info"),
            _kpi("Perfil de investidor", ss.get("perfil", "—"), "info"),
            _kpi("Moedas cripto", len(ss.get("cripto_ativos", [])), "info"),
            _kpi("Compras na carteira", lotes, "ok" if lotes else "na")]), unsafe_allow_html=True),
        "carteira": lambda: (st.markdown(_titulo("Minha carteira", "Visão rápida do que você registrou."), unsafe_allow_html=True),
                             st.markdown(_grade([_kpi("Compras registradas", lotes, "ok" if lotes else "na"),
                                                 _kpi("Carteiras-modelo", modelos, "info")]), unsafe_allow_html=True),
                             _atalho("gestao", "Abrir gestão de carteira", ":material/pie_chart:")),
        "favoritos": lambda: (st.markdown(_titulo("Ativos favoritos", "Escolha-os em Preferências."), unsafe_allow_html=True),
                              st.markdown("".join(_chip(t) for t in pr["ativos_favoritos"]) or
                                          _msg("Você ainda não marcou ativos favoritos.", "info"), unsafe_allow_html=True)),
        "alertas": lambda: (st.markdown(_titulo("Alertas", "Regras de alerta que você criou nas centrais."), unsafe_allow_html=True),
                            st.markdown(_grade([_kpi("Regras de alerta ativas", regras, "ok" if regras else "na")]), unsafe_allow_html=True),
                            _atalho("inteligencia", "Abrir central de inteligência", ":material/psychology:")),
        "relatorios": lambda: (st.markdown(_titulo("Relatórios", "Fotografias do histórico e relatórios da sua carteira."), unsafe_allow_html=True),
                               st.markdown(_grade([_kpi("Fotografias guardadas", len(ss.get("rel_fotos") or []), "info")]), unsafe_allow_html=True),
                               _atalho("relatorios", "Abrir relatórios e dashboard", ":material/monitoring:")),
        "noticias": lambda: (st.markdown(_titulo("Notícias", "Eventos e notícias dos seus ativos."), unsafe_allow_html=True),
                             _atalho("noticias", "Abrir central de notícias", ":material/newspaper:")),
    }
    d = pr["dashboard"]
    for b in EXP.blocos_do_painel(pr):
        blocos[b]()
    if usuarios.pode("admin.resumo"):
        _atalho("admin", "Abrir painel administrativo", ":material/admin_panel_settings:")


def _secao_perfil(u: dict) -> None:
    a = usuarios.ator()
    conta = banco.sis_conta_por_id(u["id"]) if not u["id"].startswith("legado:") else None
    prov = {"google": "Google", "senha": "E-mail e senha", "ambos": "Google e senha"}.get(u["provedor"], u["provedor"])
    st.markdown(_grade([
        _kpi("Nome", u["nome"], "info"), _kpi("E-mail", u["email"], "info"),
        _kpi("Cadastro", _fmt(conta["criado_em"]) if conta else "—", "na"),
        _kpi("Entra com", prov, "info"), _kpi("Tipo de conta", perm.ROTULOS.get(u["papel"], "Usuário"), "ok" if u["papel"] != "usuario" else "na"),
        _kpi("E-mail confirmado", "Sim" if (conta and conta["email_verificado"]) else "Não", "ok" if (conta and conta["email_verificado"]) else "aviso")]),
        unsafe_allow_html=True)
    if u["id"].startswith("legado:"):
        st.markdown(_msg("O banco ainda não recebeu a atualização do Passo 21: a edição do perfil fica disponível depois.", "aviso"),
                    unsafe_allow_html=True)
        return
    st.markdown(_titulo("Editar informações", "Você pode mudar o nome. O e-mail identifica a conta e não pode ser trocado."), unsafe_allow_html=True)
    with st.form("f_perfil"):
        nome = st.text_input("Nome", value=u["nome"], key="pf_nome")
        ok = _enviar("Salvar nome", type="primary")
    if ok:
        res = contas.atualizar_nome(a, nome)
        if res.ok:
            st.session_state["_conta"]["nome"] = res.dado
        _resultado(res)


def _salvar_prefs(novas: dict) -> None:
    st.session_state["prefs"] = P.normalizar(novas)
    banco.auditar(usuarios.ator().id, "preferencias.salvas", usuarios.ator().id)


def _secao_prefs(u: dict) -> None:
    pr = usuarios.preferencias()
    experiencia_app.pagina_bloco()
    st.markdown("---")
    pr = usuarios.preferencias()
    st.markdown(_msg("Suas preferências ficam salvas só na sua conta e acompanham você em qualquer aparelho. "
                     "Tema e idioma já ficam guardados; a aplicação visual de cada preferência nas telas chega aos poucos.", "info"),
                unsafe_allow_html=True)
    with st.form("f_prefs"):
        st.markdown(_titulo("Exibição"), unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        moeda = c1.selectbox("Moeda de exibição", list(P.MOEDAS), index=list(P.MOEDAS).index(pr["moeda"]), format_func=P.MOEDAS.get)
        pais = c2.selectbox("País de referência", list(P.PAISES), index=list(P.PAISES).index(pr["pais"]), format_func=P.PAISES.get)
        idioma = c3.selectbox("Idioma", list(P.IDIOMAS), index=list(P.IDIOMAS).index(pr["idioma"]), format_func=P.IDIOMAS.get)
        c4, c5 = st.columns(2)
        tema = c4.selectbox("Tema", list(P.TEMAS), index=list(P.TEMAS).index(pr["tema"]), format_func=P.TEMAS.get)
        periodo = c5.selectbox("Período padrão de análise", list(P.PERIODOS), index=list(P.PERIODOS).index(pr["periodo"]),
                               format_func=P.PERIODOS.get)
        st.markdown(_titulo("Gráficos"), unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        g = pr["grafico"]
        gtipo = g1.selectbox("Tipo", list(P.GRAFICO_TIPOS), index=list(P.GRAFICO_TIPOS).index(g["tipo"]), format_func=P.GRAFICO_TIPOS.get)
        galt = g2.selectbox("Altura", list(P.GRAFICO_ALTURAS), index=list(P.GRAFICO_ALTURAS).index(g["altura"]), format_func=P.GRAFICO_ALTURAS.get)
        ggrade = g3.checkbox("Mostrar grade", value=g["grade"])
        st.markdown(_titulo("Favoritos"), unsafe_allow_html=True)
        indicadores = st.multiselect("Indicadores favoritos", list(P.INDICADORES), default=pr["indicadores"])
        ativos = st.text_input("Ativos favoritos (separe por vírgula)", value=", ".join(pr["ativos_favoritos"]),
                               placeholder="PETR4, VALE3, HGLG11")
        carteiras = st.text_input("Carteiras favoritas (separe por vírgula)", value=", ".join(pr["carteiras_favoritas"]))
        st.markdown(_titulo("Notificações"), unsafe_allow_html=True)
        n = pr["notificacoes"]
        n1, n2, n3 = st.columns(3)
        nal = n1.checkbox("Alertas na tela", value=n["alertas"])
        nre = n2.checkbox("Relatórios prontos", value=n["relatorios"])
        nem = n3.checkbox("Avisos por e-mail", value=n["email"], help="Atalho antigo. Os canais (e-mail, Telegram, push) são configurados na Central de notificações.")
        st.markdown(_titulo("Painel do usuário", "Escolha os blocos e a ordem em que aparecem (a ordem de seleção vale)."), unsafe_allow_html=True)
        vis = [b for b in pr["dashboard"]["ordem"] if b not in pr["dashboard"]["ocultos"]]
        blocos = st.multiselect("Blocos visíveis", list(P.BLOCOS), default=vis, format_func=P.BLOCOS.get)
        ok = _enviar("Salvar preferências", type="primary")
    if ok:
        def lista(t):
            return [x.strip() for x in t.replace(";", ",").split(",") if x.strip()]
        ordem = blocos + [b for b in P.BLOCOS if b not in blocos]
        novas = {"moeda": moeda, "pais": pais, "idioma": idioma, "tema": tema, "periodo": periodo,
                 "grafico": {"tipo": gtipo, "altura": galt, "grade": ggrade}, "indicadores": indicadores,
                 "ativos_favoritos": lista(ativos), "carteiras_favoritas": lista(carteiras),
                 "notificacoes": {"alertas": nal, "relatorios": nre, "email": nem},
                 "dashboard": {"ordem": ordem, "ocultos": [b for b in P.BLOCOS if b not in blocos]},
                 "modo": pr["modo"], "exp": pr["exp"]}
        _salvar_prefs(novas)
        st.markdown(_msg("Preferências salvas.", "ok"), unsafe_allow_html=True)
        final = usuarios.preferencias()
        if len(final["ativos_favoritos"]) < len(lista(ativos)):
            st.markdown(_msg("Alguns códigos de ativos não eram válidos ou estavam repetidos e foram ignorados.", "aviso"),
                        unsafe_allow_html=True)


def _secao_seguranca(u: dict) -> None:
    a = usuarios.ator()
    if u["id"].startswith("legado:"):
        st.markdown(_msg("Os recursos de segurança da conta ficam disponíveis assim que o banco receber a atualização do Passo 21.", "aviso"),
                    unsafe_allow_html=True)
        return
    conta = banco.sis_conta_por_id(u["id"], com_senha=True)
    tem_senha = bool(conta and conta.get("senha_hash"))
    st.markdown(_grade([
        _kpi("Senha", "Definida" if tem_senha else "Não definida", "ok" if tem_senha else "aviso",
             "Entra com e-mail e senha" if tem_senha else "Esta conta entra só com o Google"),
        _kpi("Verificação em duas etapas", "Em breve", "na", "A arquitetura já está preparada; ainda não ativa."),
        _kpi("Expiração da sessão", "60 min parado" if u.get("provedor") != "google" else "Controlada pelo Google/Streamlit", "info")]),
        unsafe_allow_html=True)
    if tem_senha:
        st.markdown(_titulo("Alterar senha", "Ao alterar, os outros aparelhos são desconectados."), unsafe_allow_html=True)
        with st.form("f_alt_senha"):
            atual = st.text_input("Senha atual", type="password", key="alt_atual")
            nova = st.text_input("Nova senha", type="password", key="alt_nova")
            conf = st.text_input("Repita a nova senha", type="password", key="alt_conf")
            ok = _enviar("Alterar senha", type="primary")
        st.markdown(_regras_senha(), unsafe_allow_html=True)
        if ok:
            _resultado(contas.alterar_senha(a, atual, nova, conf, usuarios.token_sessao()))
    elif mail.configurado():
        st.markdown(_titulo("Criar uma senha", "Assim você também poderá entrar com e-mail e senha."), unsafe_allow_html=True)
        if st.button("Enviar link para criar senha", key="criar_senha_btn"):
            _resultado(contas.solicitar_redefinicao(u["email"], usuarios.cliente_id()))
    sess = banco.sessoes_do_ator(a)
    st.markdown(_titulo("Sessões com e-mail e senha", "Aparelhos conectados agora."), unsafe_allow_html=True)
    if sess:
        st.markdown("".join(_linha("Sessão ativa", f"Último uso {_fmt(s['ultimo_uso'])} · vence em {_fmt(s['expira_em'])}",
                                   _chip("válida", "ok")) for s in sess), unsafe_allow_html=True)
        if st.button("Desconectar os outros aparelhos", key="desc_outros"):
            _resultado(contas.encerrar_todas(a, usuarios.token_sessao()))
    else:
        st.markdown(_msg("Nenhuma sessão por senha aberta (quem entra com o Google tem a sessão gerenciada pelo Google).", "info"),
                    unsafe_allow_html=True)


def _secao_atividades(u: dict) -> None:
    if u["id"].startswith("legado:"):
        st.markdown(_msg("O histórico de atividades aparece depois da atualização do banco (Passo 21).", "aviso"), unsafe_allow_html=True)
        return
    itens = banco.atividades_do_ator(usuarios.ator(), 40)
    st.markdown(_titulo("Atividades relevantes da sua conta", "Entradas, mudanças de senha, preferências e downloads de dados."),
                unsafe_allow_html=True)
    if not itens:
        st.markdown(_msg("Ainda não há atividades registradas.", "info"), unsafe_allow_html=True)
        return
    def item(i):
        rot, cls = _ROTULO_ACAO.get(i["acao"], (i["acao"], "info"))
        return _linha(rot, _fmt(i["quando"]), _chip({"ok": "sucesso", "aviso": "atenção", "erro": "alerta"}.get(cls, "info"),
                                                    cls if cls != "info" else ""))
    st.markdown("".join(item(i) for i in itens), unsafe_allow_html=True)


def _secao_privacidade(u: dict) -> None:
    a = usuarios.ator()
    st.markdown(_titulo("O que guardamos e por quê", "Só o necessário para o app funcionar (minimização)."), unsafe_allow_html=True)
    st.markdown(_grade([
        _kpi("Dados da conta", "Nome e e-mail", "info", "Para identificar você e proteger o acesso."),
        _kpi("Seus dados no app", "Carteira, perfil, favoritos", "info", "Só você enxerga. Nem a administração vê."),
        _kpi("Registros de segurança", "Entradas e alterações", "info", "Para detectar abusos e mostrar seu histórico."),
        _kpi("Senha", "Nunca em texto", "ok", "Guardamos apenas um hash irreversível (scrypt).")]), unsafe_allow_html=True)
    if u["id"].startswith("legado:"):
        st.markdown(_msg("Baixar dados e excluir a conta ficam disponíveis depois da atualização do banco (Passo 21).", "aviso"),
                    unsafe_allow_html=True)
        return
    st.markdown(_titulo("Baixar meus dados", "Cópia de tudo que o app guarda sobre você, em arquivo JSON."), unsafe_allow_html=True)
    if st.button("Preparar download", key="prep_export"):
        st.session_state["_export"] = json.dumps(contas.exportar_meus_dados(a), ensure_ascii=False, indent=2, default=str)
    if st.session_state.get("_export"):
        st.download_button("Baixar meus dados (JSON)", st.session_state["_export"].encode("utf-8"), "meus_dados_bussola.json",
                           "application/json", key="dl_export", icon=":material/download:")
    st.markdown(_titulo("Apagar meus dados salvos", "Remove carteiras, favoritos e preferências, mantendo a conta."), unsafe_allow_html=True)
    ok1 = st.checkbox("Entendi que isso não pode ser desfeito", key="conf_apagar_dados")
    if st.button("Apagar dados salvos", key="btn_apagar_dados", disabled=not ok1):
        if usuarios.apagar_dados_salvos():
            st.markdown(_msg("Dados salvos apagados.", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(_msg("Não consegui apagar agora. Tente de novo.", "erro"), unsafe_allow_html=True)
    st.markdown(_titulo("Excluir minha conta", "Apaga a conta, os dados e as sessões. Não pode ser desfeito."), unsafe_allow_html=True)
    conta = banco.sis_conta_por_id(u["id"], com_senha=True)
    com_senha = bool(conta and conta.get("senha_hash"))
    with st.form("f_excluir"):
        senha = st.text_input("Digite sua senha para confirmar", type="password", key="ex_senha") if com_senha else ""
        conf = "" if com_senha else st.text_input("Digite EXCLUIR para confirmar", key="ex_conf")
        ok = _enviar("Excluir minha conta definitivamente")
    if ok:
        res = contas.excluir_conta(a, senha, conf)
        if res.ok:
            via = st.session_state.get("_conta", {}).get("via")
            usuarios._purgar()
            st.session_state["_cookie_pend"] = ("limpar", "")
            st.session_state["_aviso"] = res.msg
            if via == "google":
                st.logout()
            st.rerun()
        _resultado(res)


def pagina_conta() -> None:
    """Minha conta: painel do usuário, perfil, preferências, segurança, atividades e privacidade."""
    _css()
    _cabecalho("Minha conta", "Seu painel, seus dados e como mantê-los protegidos.")
    u = usuarios.usuario()
    if not u:
        st.markdown(_msg("Você está como visitante e nada fica salvo. Entre para guardar suas empresas, seu perfil e suas carteiras.", "info"),
                    unsafe_allow_html=True)
        if usuarios.acesso_obrigatorio():
            st.button("Entrar", icon=":material/login:", type="primary", on_click=usuarios.sair_visitante, key="entrar_conta")
        return
    st.markdown(f"<div class='ct-li'><div><div class='t'>{_e(u['nome'])}</div><div class='s'>{_e(u['email'])}</div></div>"
                f"<div>{_chip(perm.ROTULOS.get(u['papel'], 'Usuário'), 'ok' if u['papel'] != 'usuario' else '')}</div></div>",
                unsafe_allow_html=True)
    if banco.backend() == "sqlite" and not u["id"].startswith("legado:"):
        st.markdown(_msg("Seus dados estão sendo guardados só neste servidor e podem se perder quando o app for atualizado.", "aviso"),
                    unsafe_allow_html=True)
    sec = st.segmented_control("Seção", _SECOES, default="Painel", key="conta_secao", label_visibility="collapsed") or "Painel"
    {"Painel": _secao_painel, "Perfil": _secao_perfil, "Preferências": _secao_prefs, "Segurança": _secao_seguranca,
     "Atividades": _secao_atividades, "Privacidade": _secao_privacidade}[sec](u)
    st.button("Sair da conta", icon=":material/logout:", on_click=usuarios.sair, key="sair_conta")


# ------------------------------------------------------------------ painel administrativo
def _nomes_por_id(a) -> dict:
    try:
        return {c["id"]: c["email"] for c in banco.admin_listar_usuarios(a, limite=500)}
    except Exception:
        return {}


def _tabela(linhas: list[dict], colunas: dict):
    import pandas as pd
    df = pd.DataFrame([{rot: l.get(k, "") for k, rot in colunas.items()} for l in linhas])
    st.dataframe(df, hide_index=True, width="stretch")


def pagina_admin() -> None:
    """Painel administrativo. A permissão é conferida aqui E em cada função de banco.admin_*."""
    _css()
    _cabecalho("Administração", "Contas, auditoria e saúde do sistema. Sem acesso a senhas, carteiras ou preferências de ninguém.")
    a = usuarios.ator()
    if not a or not usuarios.pode("admin.resumo"):
        st.markdown(_msg("Esta área é exclusiva para administradores e suporte.", "erro"), unsafe_allow_html=True)
        return
    secs = ["Resumo", "Usuários", "Auditoria", "Erros", "Sistema"] + (["Segurança"] if perm.tem(a.papel, "admin.seguranca") else []) \
        + (["TickerCoins"] if perm.tem(a.papel, "admin.tickercoins.ver") else []) \
        + (["Consumo", "Custos", "Preços", "Assinaturas", "Uso", "Continuidade"] if perm.tem(a.papel, "admin.banco") else [])
    _caixas = dict(zip(secs, secoes.abas(secs, key="admin")))
    sec = secoes.aberta("admin")                      # só a seção aberta é calculada
    if sec is None:
        return
    try:
        with _caixas[sec]:
            {"Resumo": _adm_resumo, "Usuários": _adm_usuarios, "Auditoria": _adm_auditoria, "Erros": _adm_erros,
             "Sistema": _adm_sistema, "TickerCoins": _adm_tickercoins, "Segurança": _adm_seguranca, "Consumo": _adm_consumo, "Custos": _adm_custos, "Preços": _adm_precos, "Assinaturas": _adm_assinaturas, "Uso": _adm_uso, "Continuidade": _adm_continuidade}[sec](a)
    except banco.SemPermissao as e:
        st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
    except Exception as e:
        banco.registrar_erro("conta_app.admin", e)
        st.markdown(_msg(f"Não consegui carregar esta seção agora ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


def _adm_tickercoins(a) -> None:
    import tickercoins_app
    tickercoins_app.admin(a)


def _adm_resumo(a) -> None:
    r = banco.admin_resumo(a)
    inativos = max(0, r["ativas"] - r["ativos_30d"])
    st.markdown(_titulo("Usuários"), unsafe_allow_html=True)
    st.markdown(_grade([
        _kpi("Cadastrados", r["total"], "info"), _kpi("Ativos (entraram em 30 dias)", r["ativos_30d"], "ok"),
        _kpi("Inativos (30 dias+)", inativos, "na"), _kpi("Novos em 7 dias", r["novos_7d"], "ok" if r["novos_7d"] else "na"),
        _kpi("Novos em 30 dias", r["novos_30d"], "info"), _kpi("Aguardando confirmação", r["pendentes"], "aviso" if r["pendentes"] else "na"),
        _kpi("Suspensas", r["suspensas"], "erro" if r["suspensas"] else "na"),
        _kpi("Administradores / suporte", f"{r['admins']} / {r['suporte']}", "info",
             "Admins definidos nos secrets podem não aparecer aqui.")]), unsafe_allow_html=True)
    st.markdown(_titulo("Operação"), unsafe_allow_html=True)
    st.markdown(_grade([
        _kpi("Sessões válidas (senha)", r["sessoes_validas"], "info"),
        _kpi("Erros em 24 h", r["erros_24h"], "erro" if r["erros_24h"] else "ok"),
        _kpi("Tentativas de login falhas (24 h)", r["logins_falhos_24h"], "aviso" if r["logins_falhos_24h"] > 20 else "ok"),
        _kpi("Banco", "Supabase" if r["backend"] == "supabase" else "Arquivo local", "ok" if r["backend"] == "supabase" else "aviso")]),
        unsafe_allow_html=True)


def _adm_usuarios(a) -> None:
    c1, c2 = st.columns([2, 1])
    busca = c1.text_input("Buscar por e-mail", key="adm_busca")
    status = c2.selectbox("Situação", ["todas", "ativa", "pendente", "suspensa"], key="adm_status")
    lista = banco.admin_listar_usuarios(a, busca, None if status == "todas" else status, 200)
    if not lista:
        st.markdown(_msg("Nenhuma conta encontrada.", "info"), unsafe_allow_html=True)
        return
    _tabela([{**c, "criado_em": _fmt(c["criado_em"]), "ultimo_login": _fmt(c["ultimo_login"])} for c in lista],
            {"email": "E-mail", "nome": "Nome", "papel": "Papel", "status": "Situação", "provedor": "Entra com",
             "criado_em": "Cadastro", "ultimo_login": "Último acesso"})
    st.markdown(_titulo("Gerenciar uma conta"), unsafe_allow_html=True)
    emails = {c["email"]: c for c in lista}
    escolhido = st.selectbox("Conta", list(emails), key="adm_conta")
    c = emails[escolhido]
    cls = {"ativa": "ok", "pendente": "aviso", "suspensa": "erro"}[c["status"]]
    st.markdown(_grade([_kpi("Situação", c["status"], cls), _kpi("Papel", perm.ROTULOS.get(c["papel"], c["papel"]), "info"),
                        _kpi("Cadastro", _fmt(c["criado_em"]), "na"), _kpi("Último acesso", _fmt(c["ultimo_login"]), "na")]),
                unsafe_allow_html=True)
    if c["id"] == a.id:
        st.markdown(_msg("Esta é a sua conta: ela não pode ser alterada por aqui.", "info"), unsafe_allow_html=True)
        return
    motivo = st.text_input("Motivo (fica no registro de auditoria)", key="adm_motivo", max_chars=120)
    b1, b2, b3 = st.columns(3)
    try:
        if c["status"] != "suspensa" and perm.tem(a.papel, "admin.usuarios.suspender"):
            if b1.button("Suspender conta", key="adm_susp"):
                banco.admin_definir_status(a, c["id"], "suspensa", motivo)
                st.markdown(_msg("Conta suspensa e sessões encerradas.", "ok"), unsafe_allow_html=True)
        if c["status"] == "suspensa" and perm.tem(a.papel, "admin.usuarios.reativar"):
            if b2.button("Reativar conta", key="adm_reat"):
                banco.admin_definir_status(a, c["id"], "ativa", motivo)
                st.markdown(_msg("Conta reativada.", "ok"), unsafe_allow_html=True)
        if perm.tem(a.papel, "admin.usuarios.papel") and c["status"] == "ativa":
            novo = b3.selectbox("Papel", list(perm.PAPEIS), index=list(perm.PAPEIS).index(c["papel"]), key="adm_papel",
                                format_func=perm.ROTULOS.get)
            if novo != c["papel"] and st.button(f"Mudar para {perm.ROTULOS[novo]}", key="adm_papel_btn"):
                banco.admin_definir_papel(a, c["id"], novo)
                st.markdown(_msg("Papel atualizado.", "ok"), unsafe_allow_html=True)
    except (banco.SemPermissao, banco.ErroBanco) as e:
        st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)


def _adm_auditoria(a) -> None:
    acoes = ["todas"] + sorted({*banco.ACOES_VISIVEIS_AO_USUARIO, "login.negado", "conta.papel", "conta.excluida", "backup.contas"})
    acao = st.selectbox("Tipo de evento", acoes, key="adm_acao")
    linhas = banco.admin_auditoria(a, 300, None if acao == "todas" else acao)
    if not linhas:
        st.markdown(_msg("Nenhum registro encontrado.", "info"), unsafe_allow_html=True)
        return
    nomes = _nomes_por_id(a)
    _tabela([{**x, "quando": _fmt(x["quando"]), "ator": nomes.get(x["ator_id"], (x["ator_id"] or "sistema")[:8]),
              "alvo": nomes.get(x["alvo_id"], (x["alvo_id"] or "")[:8])} for x in linhas],
            {"quando": "Quando", "acao": "Evento", "ator": "Quem", "alvo": "Alvo", "detalhes": "Detalhes"})


def _adm_erros(a) -> None:
    linhas = banco.admin_erros(a, 150)
    if not linhas:
        st.markdown(_msg("Nenhum erro registrado. Tudo certo por aqui.", "ok"), unsafe_allow_html=True)
        return
    _tabela([{**x, "quando": _fmt(x["quando"])} for x in linhas],
            {"quando": "Quando", "modulo": "Onde", "tipo": "Tipo", "mensagem": "Mensagem (sem dados pessoais)"})


# ------------------------------------------------------------------ Segurança (Passo 22)
_NIVEL_CLS = {"critico": "erro", "alto": "erro", "medio": "aviso", "baixo": "info"}
_NIVEL_ROT = {"critico": "Crítico", "alto": "Alto", "medio": "Médio", "baixo": "Baixo"}


def _adm_seguranca(a) -> None:
    import alertas_seg
    import auditoria_codigo as ac
    import backup_seg
    import http_seguro
    import protecao
    protecao.iniciar()
    ev = banco.admin_eventos_seguranca(a)
    alertas = alertas_seg.analisar(ev["auditoria"], ev["erros"], http_seguro.bloqueios())
    diag = protecao.diagnostico()
    falhas = [d for d in diag if d["ok"] is False]
    graves = [d for d in falhas if d["gravidade"] in ("critico", "alto")]
    n_alto = sum(1 for x in alertas if x["nivel"] == "alto")
    st.markdown(_grade([
        _kpi("Verificações de configuração", f"{sum(1 for d in diag if d['ok'])}/{len(diag)}", "ok" if not falhas else "aviso" if not graves else "erro",
             "itens aprovados"),
        _kpi("Pendências graves", len(graves), "erro" if graves else "ok", "críticas ou altas"),
        _kpi("Alertas de atividade", len(alertas), "erro" if n_alto else "aviso" if alertas else "ok", "últimas 48 h"),
        _kpi("Senhas guardadas com", seg.algoritmo_ativo().upper(), "ok" if seg.algoritmo_ativo() == "argon2id" else "aviso"),
        _kpi("Proteção de rede", "Ligada" if http_seguro.instalar() else "Desligada", "ok", f"domínios: modo {http_seguro.modo()}")]),
        unsafe_allow_html=True)
    st.markdown(_titulo("Alertas de atividade suspeita", "Padrões nos registros de auditoria. Nada é bloqueado por aqui: o bloqueio de tentativas já ocorre no login."),
                unsafe_allow_html=True)
    if not alertas:
        st.markdown(_msg("Nenhuma atividade suspeita nas últimas 48 horas.", "ok"), unsafe_allow_html=True)
    for x in alertas:
        st.markdown(_linha(x["titulo"], x["detalhe"], _chip(_NIVEL_ROT.get(x["nivel"], x["nivel"]), _NIVEL_CLS.get(x["nivel"], "info"))), unsafe_allow_html=True)
    st.markdown(_titulo("Configuração", "Só mostra se cada proteção existe; nenhum valor secreto aparece aqui."), unsafe_allow_html=True)
    for d in diag:
        selo = _chip("OK", "ok") if d["ok"] else _chip("Não se aplica", "na") if d["ok"] is None else _chip("Atenção" if d["gravidade"] in ("baixo", "medio") else "Corrigir", "aviso" if d["gravidade"] in ("baixo", "medio") else "erro")
        st.markdown(_linha(d["titulo"], d["detalhe"], selo), unsafe_allow_html=True)

    st.markdown(_titulo("Auditoria do código", "Procura segredos escritos no código, comandos perigosos, pedidos sem tempo limite e SQL montado por texto."), unsafe_allow_html=True)
    if st.button("Rodar auditoria do código", key="seg_cod", icon=":material/policy:"):
        import os
        raiz = os.path.dirname(os.path.abspath(ac.__file__))
        st.session_state["_seg_cod"] = [x.como_dict() for x in ac.varrer_repositorio(raiz)]
    res = st.session_state.get("_seg_cod")
    if res is not None:
        cont = {n: sum(1 for x in res if x["severidade"] == n) for n in ac.SEVERIDADES}
        st.markdown(_grade([_kpi(_NIVEL_ROT[n], cont[n], _NIVEL_CLS[n] if cont[n] else "ok") for n in ac.SEVERIDADES]), unsafe_allow_html=True)
        graves = [x for x in res if x["severidade"] in ("critico", "alto")]
        st.markdown(_msg("Nenhum achado crítico ou alto." if not graves else f"{len(graves)} achado(s) crítico(s) ou alto(s) para revisar.", "ok" if not graves else "erro"),
                    unsafe_allow_html=True)
        if res:
            _tabela(res[:80], {"severidade": "Gravidade", "arquivo": "Arquivo", "linha": "Linha", "categoria": "Tipo", "detalhe": "O que foi visto"})

    st.markdown(_titulo("Rede", "Pedidos externos recusados e domínios ainda fora da lista permitida."), unsafe_allow_html=True)
    bl = http_seguro.bloqueios()
    desc = http_seguro.hosts_desconhecidos()
    st.markdown(_grade([_kpi("Pedidos recusados", len(bl), "erro" if bl else "ok"),
                        _kpi("Domínios fora da lista", len(desc), "aviso" if desc else "ok"),
                        _kpi("Modo", http_seguro.modo().capitalize(), "ok" if http_seguro.modo() == "bloquear" else "info")]), unsafe_allow_html=True)
    if desc:
        for h, n in sorted(desc.items(), key=lambda kv: -kv[1])[:30]:
            st.markdown(_linha(h, f"{n} pedido(s)", _chip("fora da lista", "aviso")), unsafe_allow_html=True)
    for b in bl[-20:]:
        st.markdown(_linha(b["host"] or "(sem domínio)", b["motivo"], _chip("recusado", "erro")), unsafe_allow_html=True)

    st.markdown(_titulo("Backup e restauração", "Um backup só vale depois de restaurado e conferido."), unsafe_allow_html=True)
    chave = banco.secrets_secao("backup").get("chave")
    if st.button("Testar backup e restauração", key="seg_bk", icon=":material/restore:"):
        st.session_state["_seg_bk"] = banco.admin_testar_backup(a, chave)
    r = st.session_state.get("_seg_bk")
    if r:
        for nome, ok, det in r["etapas"]:
            st.markdown(_linha(nome, det, _chip("OK", "ok") if ok else _chip("Falhou", "erro")), unsafe_allow_html=True)
        st.caption("Testado em " + _fmt(r["quando"]))
    if chave and perm.tem(a.papel, "admin.backup"):
        if st.button("Gerar backup cifrado das contas", key="seg_bkc", icon=":material/lock:"):
            cif, imp = backup_seg.backup_json_cifrado(banco.admin_backup(a), chave)
            st.session_state["_seg_bkc"] = (cif, imp)
        if st.session_state.get("_seg_bkc"):
            cif, imp = st.session_state["_seg_bkc"]
            st.download_button("Baixar backup cifrado", cif, "backup_contas.enc", "application/octet-stream", key="seg_bkc_dl", icon=":material/download:")
            st.caption("SHA-256: " + imp)
    elif not chave:
        st.markdown(_msg("Para gerar backups cifrados, crie a chave nos Secrets: seção [backup], campo chave. Gere o valor com o botão abaixo e guarde uma cópia em local separado.", "info"),
                    unsafe_allow_html=True)
        if st.button("Gerar uma chave nova (aparece uma vez)", key="seg_chave"):
            st.session_state["_seg_chave"] = backup_seg.nova_chave()
        if st.session_state.get("_seg_chave"):
            st.code(st.session_state["_seg_chave"])

    st.markdown(_titulo("Se houver um incidente", "Passos curtos para agir com calma."), unsafe_allow_html=True)
    for i, (t, s) in enumerate([
        ("Conter", "Suspenda as contas envolvidas em Usuários e, se o app inteiro estiver em risco, ponha o app em modo privado no Streamlit Cloud."),
        ("Trocar o que foi exposto", "Só as credenciais comprovadamente expostas: Secrets do Streamlit, chave do Supabase, senha de app do Gmail, chaves de API."),
        ("Entender", "Veja Auditoria e Erros, e a lista de alertas acima. Anote horário, conta e o que foi acessado."),
        ("Restaurar", "Use o backup testado (aba Segurança) ou o backup do Supabase. Confira as contagens depois de restaurar."),
        ("Avisar", "Se dados pessoais de usuários foram expostos, avalie com orientação jurídica a comunicação à ANPD e aos titulares (LGPD, art. 48)."),
        ("Registrar", "Escreva o que aconteceu, a causa e o que mudou para não se repetir.")], 1):
        st.markdown(_linha(f"{i}. {t}", s), unsafe_allow_html=True)
    st.markdown(_titulo("Pontos que pedem avaliação jurídica", "Este app não declara conformidade automática com a LGPD."), unsafe_allow_html=True)
    for t, s in [("Base legal e finalidade", "Confirmar com advogado a base legal de cada dado coletado e o texto da política de privacidade."),
                 ("Prazos de retenção", f"Hoje: auditoria {banco.RETENCAO_AUDITORIA_DIAS} dias, erros {banco.RETENCAO_ERROS_DIAS} dias, sessões e tokens vencidos removidos. Validar se atendem à sua finalidade."),
                 ("Operadores e transferência internacional", "Supabase, Google, Streamlit Cloud e provedores de dados podem processar dados fora do Brasil."),
                 ("Encarregado (DPO) e canal do titular", "Definir quem responde pedidos de acesso, correção e exclusão.")]:
        st.markdown(_linha(t, s), unsafe_allow_html=True)


def _adm_sistema(a) -> None:
    ok, motivo = banco.pronto(True)
    chave = banco.tipo_de_chave()
    st.markdown(_grade([
        _kpi("Banco", "Supabase" if banco.backend() == "supabase" else "Arquivo local", "ok" if banco.backend() == "supabase" else "aviso",
             banco.host_do_banco()),
        _kpi("Esquema do Passo 21", "Atualizado" if ok else "Pendente", "ok" if ok else "erro", motivo),
        _kpi("Chave do Supabase", {"secreta": "Secreta (correta)", "publica": "Pública (trocar)"}.get(chave, "Não identificada"),
             "ok" if chave == "secreta" else "aviso" if banco.backend() == "supabase" else "na"),
        _kpi("Envio de e-mails", "Configurado" if mail.configurado() else "Não configurado", "ok" if mail.configurado() else "aviso",
             "Necessário para cadastro e recuperação de senha."),
        _kpi("Login com Google", "Configurado" if usuarios._configurado() else "Não configurado", "ok" if usuarios._configurado() else "aviso"),
        _kpi("Administradores nos secrets", len(contas.admins_dos_secrets()), "info"),
        _kpi("Tabelas de notificações (Passo 23)", "Prontas" if banco.notif_disponivel() else "Pendentes", "ok" if banco.notif_disponivel() else "aviso",
             "" if banco.notif_disponivel() else "Rode o script SQL de novo.")]), unsafe_allow_html=True)
    if perm.tem(a.papel, "admin.seguranca") and banco.notif_disponivel():
        st.markdown(_titulo("Monitor automático", "Últimas verificações feitas fora do app (GitHub Actions). Sem dados de usuários."), unsafe_allow_html=True)
        try:
            exe = banco.monitor_execucoes(a, 12)
        except Exception as e:
            banco.registrar_erro("conta_app.monitor", e)
            exe = []
        if not exe:
            st.markdown(_msg("O monitor ainda não executou. Veja NOTIFICACOES.md para ligar.", "aviso"), unsafe_allow_html=True)
        for x in exe:
            r = x.get("resumo") or {}
            st.markdown(_linha(f"{_fmt(x['inicio'])} · {x['status']}",
                               f"contas {r.get('contas', 0)} · avaliadas {r.get('avaliadas', 0)} · notificações {r.get('notificacoes', 0)} · "
                               f"enviadas {r.get('entregas_ok', 0)} · falhas de envio {r.get('entregas_falha', 0)} · {r.get('duracao_s', '?')} s",
                               _chip(x["status"], {"ok": "ok", "parcial": "aviso", "falhou": "erro"}.get(x["status"], "na"))), unsafe_allow_html=True)
    if perm.tem(a.papel, "admin.banco"):
        with st.expander("Script SQL do Supabase (Passo 21)"):
            st.caption("Cole no SQL Editor do Supabase e toque em Run. Pode rodar de novo sem problemas.")
            st.code(banco.sql_supabase(), language="sql")
        if st.button("Limpar registros antigos", key="adm_limpar"):
            banco.limpar_antigos()
            st.markdown(_msg("Limpeza feita (tentativas antigas, sessões e tokens vencidos).", "ok"), unsafe_allow_html=True)
    if perm.tem(a.papel, "admin.backup"):
        st.markdown(_titulo("Backup das contas", "Contas (sem senhas), auditoria e erros. Carteiras e preferências não entram: administradores não as veem."),
                    unsafe_allow_html=True)
        if st.button("Gerar backup", key="adm_bk"):
            st.session_state["_bk"] = json.dumps(banco.admin_backup(a), ensure_ascii=False, indent=2, default=str)
        if st.session_state.get("_bk"):
            st.download_button("Baixar backup (JSON)", st.session_state["_bk"].encode("utf-8"), "backup_contas.json",
                               "application/json", key="adm_bk_dl", icon=":material/download:")


def _adm_consumo(a) -> None:
    """Etapa 2: consumo das APIs por provedor, limites configuráveis e bloqueio opcional. Só administradores (admin.banco)."""
    import consumo
    if not perm.tem(a.papel, "admin.banco"):
        raise banco.SemPermissao("Sem permissão para ver o consumo.")
    st.markdown(_titulo("Consumo das APIs", "Quantos pedidos cada fonte recebeu. Padrão: só contar. Bloquear é opcional, por fonte."), unsafe_allow_html=True)
    if not banco.cfg_disponivel():
        st.markdown(_msg("A tabela de configuração ainda não existe no Supabase: a contagem vale só enquanto o app está ligado e os "
                         "limites não são salvos. Rode o script SQL novamente (Sistema > script do banco).", "aviso"), unsafe_allow_html=True)
    itens = consumo.resumo()
    rot = {"ok": "ok", "aviso": "aviso", "erro": "erro", "suspenso": "erro", "pausado": "erro", "na": "info"}
    cards = []
    for i in itens:
        lim = i["limites"]
        txt = " · ".join(f"{n} {lim[k]:,}".replace(",", ".") for k, n in (("min", "/min"), ("dia", "/dia"), ("mes", "/mês")) if lim.get(k)) or "limite não configurado"
        sit = {"ok": "Dentro do limite", "aviso": "Perto do limite", "erro": "Limite atingido", "suspenso": "Suspenso", "na": "Só contagem",
               "pausado": f"Pausada por falhas ({i['pausa_min']} min)"}[i["situacao"]]
        cards.append(_kpi(i["nome"], f"{i['dia']:,} hoje".replace(",", "."), rot[i["situacao"]],
                          f"{sit} · mês {i['mes']:,} · {txt} · modo {i['modo']}".replace(",", ".")))
    st.markdown(_grade(cards), unsafe_allow_html=True)
    st.markdown(_msg("Yahoo é contado nos pontos de chamada do app. Os números são pedidos, não créditos (alguns provedores cobram "
                     "créditos). A contagem soma app e monitor; pode perder poucos pedidos se os dois gravarem juntos.", "info"), unsafe_allow_html=True)
    import cache_central
    r = cache_central.resumo()
    st.markdown(_titulo("Cache central", "Quantas consultas o cache evitou de mandar para as fontes (vale desde que o app ligou)."), unsafe_allow_html=True)
    if not r["consultas"]:
        st.markdown(_msg("Ainda sem consultas contadas desde que o app ligou.", "info"), unsafe_allow_html=True)
    else:
        st.markdown(_grade([
            _kpi("Consultas evitadas", f"{r['economia_pct']:.0f}%".replace(".", ","), "ok" if r["economia_pct"] >= 50 else "aviso",
                 f"{r['acertos'] + r['coalescidos']} de {r['consultas']} atendidas sem ir à fonte"),
            _kpi("Pedidos à fonte", r["pedidos"], "info", f"{r['coalescidos']} duplicados no mesmo instante foram juntados"),
            _kpi("Dado antigo servido", r["antigos"], "aviso" if r["antigos"] else "ok", "fonte falhou e mostramos o último dado real, com aviso"),
            _kpi("Falhas de fonte", r["falhas"], "erro" if r["falhas"] else "ok", "falha não fica guardada por horas")]), unsafe_allow_html=True)
    import planos
    st.markdown(_titulo("Planos e limites", "Quanto cada plano pode usar por dia. Valores iniciais são pontos de partida: ajuste conforme o consumo real."), unsafe_allow_html=True)
    with st.expander("Editar limites por plano"):
        novos = {}
        for rid, rec in planos.RECURSOS.items():
            st.markdown(f"**{rec['rotulo']}**" + ("" if rec["aplicado"] else " · _ainda não aplicado no app_"))
            cols = st.columns(len(planos.ORDEM))
            for i, pl in enumerate(planos.ORDEM):
                novos.setdefault(pl, {})[rid] = cols[i].number_input(planos.ROTULO[pl], min_value=0, value=int(planos.limite(pl, rid)), step=1, key=f"pl_{pl}_{rid}")
        if st.button("Salvar limites dos planos", key="pl_salvar", type="primary"):
            try:
                planos.salvar_limites(novos)
                banco.auditar(a.id, "planos.limites", None, {"recursos": len(planos.RECURSOS)})
                st.markdown(_msg("Limites salvos. Valem em até 1 minuto.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.planos", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
    import paginas_plano
    st.markdown(_titulo("Páginas por plano", "A divisão sugerida já vale: Gratuito, Investidor Plus e Investidor Premium abrem páginas diferentes. Cada página trancada ganha cadeado no menu e fica bloqueada também por URL direta. Aqui você muda o plano mínimo de cada uma. Início, Alertas, Planos, Minha conta e Ajuda nunca são trancadas."), unsafe_allow_html=True)
    with st.expander("Escolher plano mínimo por página"):
        atuais = paginas_plano.ler()
        opcoes = ["todos"] + [p for p in paginas_plano.PLANOS_ORDEM if p != "visitante"]
        rot = lambda x: "Todos os planos" if x == "todos" else paginas_plano.ROTULO[x]
        novos_min = {}
        for url, titulo in sorted(_PAGINAS_PLANO().items(), key=lambda kv: kv[1]):
            if url in paginas_plano.NUNCA_TRANCAR:
                continue
            esc = st.selectbox(titulo, opcoes, index=opcoes.index(atuais.get(url, "todos")), format_func=rot, key=f"pp_{url}")
            if esc != "todos":
                novos_min[url] = esc
        if st.button("Voltar à divisão sugerida", key="pp_padrao"):
            try:
                paginas_plano.salvar(paginas_plano.PADRAO_MINIMOS)
                banco.auditar(a.id, "planos.paginas", None, {"paginas_com_plano": len(paginas_plano.PADRAO_MINIMOS), "padrao": True})
                st.markdown(_msg("Divisão sugerida restaurada. Vale em até 1 minuto; reabra esta tela para ver os valores.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.paginas_plano", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
        if st.button("Salvar páginas por plano", key="pp_salvar", type="primary"):
            try:
                paginas_plano.salvar(novos_min)
                banco.auditar(a.id, "planos.paginas", None, {"paginas_com_plano": len(novos_min)})
                st.markdown(_msg("Salvo. Vale em até 1 minuto.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.paginas_plano", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
    st.markdown(_titulo("Assinaturas", "Quem tem plano pago, até quando vale e quem está para vencer. Assinatura vencida volta ao Gratuito sozinha; nada é apagado."), unsafe_allow_html=True)
    try:
        lista = planos.listar_assinaturas()
    except Exception as e:
        banco.registrar_erro("conta_app.assin", e)
        lista = []
    cont = {k: len([x for x in lista if x["situacao"] == k]) for k in ("ativa", "vencendo", "carencia", "vencida", "sem_validade")}
    st.markdown(_grade([_kpi("Assinaturas em dia", cont["ativa"] + cont["sem_validade"], "ok", f"{cont['sem_validade']} sem data de validade"),
                        _kpi("Vencem em 7 dias", cont["vencendo"], "aviso" if cont["vencendo"] else "na"),
                        _kpi("Em carência", cont["carencia"], "aviso" if cont["carencia"] else "na", "venceram, mas ainda têm os limites do plano"),
                        _kpi("Vencidas", cont["vencida"], "erro" if cont["vencida"] else "na", "já voltaram ao Gratuito")]), unsafe_allow_html=True)
    if lista:
        rot = {"ativa": "Em dia", "vencendo": "Vence em breve", "carencia": "Em carência", "vencida": "Vencida", "sem_validade": "Sem validade"}
        _tabela([{**x, "plano": planos.ROTULO[x["plano"]], "ate": _data_br(x["ate"]) if x["ate"] else "—", "situacao": rot[x["situacao"]] + (" · cancelada" if x["cancelado"] else ""),
                  "dias": "—" if x["dias"] is None else x["dias"]} for x in lista],
                {"email": "E-mail", "plano": "Plano", "ate": "Válido até", "dias": "Dias", "situacao": "Situação", "origem": "Origem"})
    with st.expander("Dar, renovar ou cancelar um plano"):
        em = st.text_input("E-mail da conta", key="pl_email")
        novo_pl = st.selectbox("Plano", list(planos.PLANOS), format_func=planos.ROTULO.get, key="pl_novo")
        val = st.selectbox("Validade", [30, 90, 180, 365, 0], format_func=lambda d: "Sem validade" if d == 0 else f"{d} dias", key="pl_val")
        b1, b2 = st.columns(2)
        em_n = seg.normalizar_email(em)
        try:
            if b1.button("Aplicar plano", key="pl_aplicar", type="primary"):
                if not em_n or not banco.sis_conta_por_email(em_n):
                    st.markdown(_msg("Não encontrei uma conta com esse e-mail.", "erro"), unsafe_allow_html=True)
                else:
                    d = planos.definir_plano(em_n, novo_pl, dias=val or None)
                    banco.auditar(a.id, "planos.atribuir", None, {"plano": novo_pl, "ate": d["ate"]})
                    st.markdown(_msg(f"Plano {planos.ROTULO[novo_pl]} aplicado" + (f" até {_data_br(d['ate'])}." if d["ate"] else " (sem validade)."), "ok"), unsafe_allow_html=True)
            if b2.button("Renovar pelo prazo escolhido", key="pl_renovar"):
                if not em_n or not banco.sis_conta_por_email(em_n):
                    st.markdown(_msg("Não encontrei uma conta com esse e-mail.", "erro"), unsafe_allow_html=True)
                else:
                    d = planos.renovar(em_n, val or 30)
                    banco.auditar(a.id, "planos.renovar", None, {"plano": d["plano"], "ate": d["ate"]})
                    st.markdown(_msg(f"Renovado até {_data_br(d['ate'])}.", "ok"), unsafe_allow_html=True)
        except ValueError as e:
            st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
        except Exception as e:
            banco.registrar_erro("conta_app.planos", e)
            st.markdown(_msg(f"Não consegui aplicar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
        st.caption("Para cancelar, aplique o plano Gratuito.")
    import prioridade
    pc = prioridade.config()
    st.markdown(_titulo("Ativos prioritários", "O monitor lê estes ativos em rodízio e deixa o dado pronto no cache. Quem abre o app não espera a fonte."), unsafe_allow_html=True)
    st.markdown(_grade([_kpi("Aquecimento", "Ligado" if pc["ligado"] else "Desligado", "ok" if pc["ligado"] else "aviso", f"{pc['por_execucao']} ativos por execução (a cada ~15 min)"),
                        _kpi("Ativos na lista", len(pc["ativos"]), "info", "em rodízio"),
                        _kpi("Cache no banco", "Ativo" if banco.cfg_disponivel() else "Indisponível", "ok" if banco.cfg_disponivel() else "aviso",
                             "dados sobrevivem a reinícios do app")]), unsafe_allow_html=True)
    with st.expander("Editar ativos prioritários"):
        txt = st.text_area("Ativos (separe por espaço ou vírgula; use CÓDIGO:classe se precisar, ex.: IVVB11:etf)",
                           value=" ".join(f"{t}:{c}" if c == "etf" else t for t, c in pc["ativos"]), key="prio_txt", height=120)
        c1, c2 = st.columns(2)
        n_exec = c1.number_input("Ativos por execução", min_value=0, max_value=40, value=int(pc["por_execucao"]), step=1, key="prio_n")
        lig = c2.checkbox("Aquecimento ligado", value=bool(pc["ligado"]), key="prio_lig")
        if st.button("Salvar prioritários", key="prio_salvar", type="primary"):
            try:
                lista = prioridade.parse(txt)
                prioridade.salvar(lista, n_exec, lig)
                banco.auditar(a.id, "consumo.prioridade", None, {"ativos": len(lista), "por_execucao": int(n_exec), "ligado": bool(lig)})
                st.markdown(_msg(f"Salvo: {len(lista)} ativos.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.prioridade", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
    cfg = consumo.config()
    with st.expander("Editar limites e bloqueios"):
        novo = {"limites": {}, "modo": {}, "suspenso": []}
        for i in itens:
            pid, lim = i["id"], i["limites"]
            st.markdown(f"**{i['nome']}**")
            c = st.columns(5)
            v = {k: c[n].number_input(r, min_value=0, value=int(lim.get(k) or 0), step=1, key=f"cons_{pid}_{k}", help="0 = sem limite")
                 for n, (k, r) in enumerate((("min", "Por minuto"), ("dia", "Por dia"), ("mes", "Por mês")))}
            m = c[3].selectbox("Modo", ["avisar", "proteger", "bloquear"], index=["avisar", "proteger", "bloquear"].index(i["modo"]), key=f"cons_{pid}_m",
                               help="avisar: só conta · proteger: o aquecimento para na reserva e tudo para em 100% · bloquear: tudo para em 100%")
            s = c[4].checkbox("Suspender", value=pid in cfg["suspenso"], key=f"cons_{pid}_s")
            novo["limites"][pid], novo["modo"][pid] = v, m
            if s:
                novo["suspenso"].append(pid)
        r1, r2, r3 = st.columns(3)
        novo["reserva_pct"] = r1.number_input("Reserva do aquecimento (% do limite)", min_value=10, max_value=100, value=int(cfg["reserva_pct"]), step=5, key="cons_reserva",
                                              help="Acima disto o aquecimento do monitor para; o resto do limite fica para quem usa o app.")
        novo["circuito"] = {"falhas": r2.number_input("Falhas seguidas para pausar a fonte", min_value=2, max_value=50, value=int(cfg["circuito"]["falhas"]), step=1, key="cons_circ_f"),
                            "pausa_min": r3.number_input("Pausa (minutos)", min_value=1, max_value=240, value=int(cfg["circuito"]["pausa_min"]), step=1, key="cons_circ_p")}
        if st.button("Salvar limites", key="cons_salvar", type="primary"):
            try:
                consumo.salvar_config(novo)
                banco.auditar(a.id, "consumo.config", None, {"suspensos": novo["suspenso"], "bloqueando": [p for p, m in novo["modo"].items() if m == "bloquear"],
                                                             "reserva": novo["reserva_pct"]})
                st.markdown(_msg("Limites salvos. Valem em até 1 minuto.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.consumo", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def _hist_consumo(dias: int) -> dict:
    import consumo
    return consumo.historico(dias)


def _adm_custos(a) -> None:
    """Etapa 7: custos estimados, orçamento, consumo ao longo do tempo e uso por recurso. Só administradores (admin.banco)."""
    import consumo
    import custos
    import pandas as pd
    import planos
    from datetime import datetime, timedelta, timezone
    if not perm.tem(a.papel, "admin.banco"):
        raise banco.SemPermissao("Sem permissão para ver os custos.")
    hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).date()
    cfg = custos.config()
    mes = consumo.usos_do_mes()
    calc = custos.calcular(mes, hoje, cfg)
    st.markdown(_titulo("Custos do mês", "Estimativa a partir dos pedidos contados e dos valores que você informa. O app não vê faturas."), unsafe_allow_html=True)
    cls = {"ok": "ok", "aviso": "aviso", "erro": "erro", "sem_orcamento": "info"}[calc["situacao"]]
    st.markdown(_grade([
        _kpi("Gasto estimado no mês", custos.brl(calc["total"]), cls, f"fixos {custos.brl(calc['fixo'])} · variáveis {custos.brl(calc['variavel'])}"),
        _kpi("Projeção até o fim do mês", custos.brl(calc["projecao"]), cls, "pelo ritmo dos dias que já passaram"),
        _kpi("Orçamento do mês", custos.brl(calc["orcamento"]) if calc["orcamento"] else "Não definido", cls,
             f"{calc['pct_usado']:.0f}% usado · projeção {calc['pct_projetado']:.0f}%" if calc["orcamento"] else "defina abaixo para receber avisos"),
        _kpi("Fontes pagas", len(calc["fontes_pagas"]), "ok" if not calc["fontes_pagas"] else "aviso",
             "todas as fontes são gratuitas" if not calc["fontes_pagas"] else ", ".join(consumo.PROVEDORES[p][0] for p in calc["fontes_pagas"])),
        _kpi("Pedidos no mês", f"{calc['pedidos_mes']:,}".replace(",", "."), "info", "todas as fontes somadas")]), unsafe_allow_html=True)
    for x in custos.alertas(calc):
        st.markdown(_msg(x["texto"], x["nivel"]), unsafe_allow_html=True)

    st.markdown(_titulo("Pedidos por fonte no mês", "Quanto cada fonte recebeu e o custo estimado (R$ 0,00 enquanto for gratuita)."), unsafe_allow_html=True)
    cards = []
    for pid, (nome, _d, _c, _l) in consumo.PROVEDORES.items():
        n = int(mes.get(pid, 0))
        if n or pid in calc["variavel_por_fonte"]:
            lim = consumo.limites(pid).get("mes")
            cards.append(_kpi(nome, f"{n:,}".replace(",", "."), "info", f"custo {custos.brl(calc['variavel_por_fonte'].get(pid, 0))}" + (f" · limite do mês {lim:,}".replace(",", ".") if lim else "")))
    st.markdown(_grade(cards) if cards else _msg("Ainda sem pedidos contados neste mês.", "info"), unsafe_allow_html=True)

    st.markdown(_titulo("Consumo dos últimos 14 dias", "Pedidos por dia, por fonte."), unsafe_allow_html=True)
    try:
        hist = _hist_consumo(14)
        nomes = {pid: consumo.PROVEDORES[pid][0] for pid in consumo.PROVEDORES}
        df = pd.DataFrame({d: {nomes[p]: int(n) for p, n in v.items() if p in nomes} for d, v in hist.items()}).T.fillna(0).astype(int)
        df = df.loc[:, (df != 0).any()] if not df.empty else df
        if df.empty or not len(df.columns):
            st.markdown(_msg("Sem consumo registrado nos últimos 14 dias.", "info"), unsafe_allow_html=True)
        else:
            st.bar_chart(df, stack=True, height=280)
            st.download_button("Baixar histórico (CSV)", df.rename_axis("dia").to_csv().encode("utf-8"), file_name="consumo_14_dias.csv",
                               mime="text/csv", key="custos_csv")
    except Exception as e:
        banco.registrar_erro("conta_app.custos.hist", e)
        st.markdown(_msg(f"Não consegui carregar o histórico ({e.__class__.__name__}).", "aviso"), unsafe_allow_html=True)

    st.markdown(_titulo("Uso por recurso hoje", "Soma de todas as contas (sem identificar ninguém)."), unsafe_allow_html=True)
    try:
        ag = planos.uso_agregado_hoje()
        rot = {r: planos.RECURSOS[r]["rotulo"] for r in ag["total"]}
        st.markdown(_grade([_kpi("Contas que usaram recursos limitados", ag["contas"], "info", "hoje")] +
                           [_kpi(rot[r], n, "info", "hoje") for r, n in ag["total"].items()]), unsafe_allow_html=True)
    except Exception as e:
        banco.registrar_erro("conta_app.custos.uso", e)
        st.markdown(_msg(f"Não consegui carregar o uso por recurso ({e.__class__.__name__}).", "aviso"), unsafe_allow_html=True)

    with st.expander("Editar orçamento e custos"):
        orc = st.number_input("Orçamento mensal (R$, 0 = sem orçamento)", min_value=0.0, value=float(cfg["orcamento_mensal"]), step=10.0, key="cus_orc")
        txt = st.text_area("Custos fixos por mês (uma linha por custo, ex.: Domínio = 40,00)", value=custos.fixos_txt(cfg["fixos"]), key="cus_fixos", height=100)
        st.markdown("**Preço por 1.000 pedidos de cada fonte** (0 = gratuita). Só preencha se você contratar um plano pago, e só depois de decidir isso.")
        precos = {}
        cols = st.columns(3)
        for i, (pid, (nome, *_r)) in enumerate(consumo.PROVEDORES.items()):
            precos[pid] = cols[i % 3].number_input(nome, min_value=0.0, value=float(cfg["preco_por_mil"].get(pid, 0.0)), step=0.1, key=f"cus_p_{pid}")
        if st.button("Salvar custos", key="cus_salvar", type="primary"):
            try:
                custos.salvar({"orcamento_mensal": orc, "fixos": custos.parse_fixos(txt), "preco_por_mil": precos})
                banco.auditar(a.id, "custos.config", None, {"orcamento": bool(orc), "fixos": len(custos.parse_fixos(txt)),
                                                          "pagas": len([p for p, v in precos.items() if v > 0])})
                st.markdown(_msg("Custos salvos.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.custos", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


def _adm_precos(a) -> None:
    """Etapa 8: preço dos planos, receita, taxas, margem, ponto de equilíbrio e simulador. Só estimativa; ainda não cobra ninguém."""
    import consumo
    import custos
    import planos
    import precificacao as pr
    from datetime import datetime, timedelta, timezone
    if not perm.tem(a.papel, "admin.banco"):
        raise banco.SemPermissao("Sem permissão para ver preços e margens.")
    hoje = (datetime.now(timezone.utc) - timedelta(hours=3)).date()
    cfg = pr.config()
    custo = custos.calcular(consumo.usos_do_mes(), hoje)["projecao"]
    try:
        cont = planos.contagem_por_plano()
    except Exception as e:
        banco.registrar_erro("conta_app.precos.cont", e)
        cont = {p: 0 for p in planos.PLANOS}
    st.markdown(_titulo("Receita e margem do mês", "Estimativa: preços que você definiu × contas de cada plano, menos taxas e custos. Ainda não há cobrança."), unsafe_allow_html=True)
    r = pr.calcular(cont, custo, cfg)
    cls = {"ok": "ok", "aviso": "aviso", "erro": "erro", "sem_preco": "info", "sem_assinantes": "info"}[r["situacao"]]
    msg = {"sem_preco": "Defina o preço dos planos pagos abaixo para ver receita e margem.",
           "sem_assinantes": "Ainda não há contas em planos pagos: use o simulador abaixo.",
           "erro": "O custo do mês passa da receita líquida: prejuízo estimado.",
           "aviso": f"Margem abaixo da meta de {cfg['margem_alvo']:.0f}%.", "ok": "Margem dentro da meta."}[r["situacao"]]
    st.markdown(_grade([
        _kpi("Receita bruta", custos.brl(r["bruta"]), "info", "assinantes × preço"),
        _kpi("Taxas de pagamento", custos.brl(r["taxas"]), "na", "definidas abaixo"),
        _kpi("Receita líquida", custos.brl(r["liquida"]), "info"),
        _kpi("Custo do mês (projeção)", custos.brl(r["custo"]), "info", "fixos + fontes pagas"),
        _kpi("Lucro estimado", custos.brl(r["lucro"]), cls, msg),
        _kpi("Margem", f"{r['margem']:.0f}%" if r["margem"] is not None else "—", cls, f"meta {cfg['margem_alvo']:.0f}%")]), unsafe_allow_html=True)
    st.markdown(_titulo("Planos"), unsafe_allow_html=True)
    nomes = {"gratuito": "Gratuito", "plus": "Investidor Plus", "premium": "Investidor Premium"}
    cards = [_kpi("Gratuito", f"{cont.get('gratuito', 0)} contas com plano definido", "na", "R$ 0,00 · contas sem registro também são gratuitas")]
    for p in pr.PAGOS:
        eq = r["equilibrio"][p]
        cards.append(_kpi(nomes[p], f"{r['linhas'][p]['assinantes']} assinantes", "info",
                          f"{custos.brl(cfg['preco'][p])}/mês · líquido {custos.brl(r['linhas'][p]['liquida_unit'])} por assinante · "
                          + ("defina o preço" if eq is None else f"equilíbrio com {eq} sozinho")))
    st.markdown(_grade(cards), unsafe_allow_html=True)

    st.markdown(_titulo("Simulador", "E se eu tivesse esta quantidade de assinantes? Não altera nada."), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    n_plus = int(c1.number_input("Assinantes Plus", min_value=0, value=int(cont.get("plus", 0)), step=5, key="pre_sim_plus"))
    n_prem = int(c2.number_input("Assinantes Premium", min_value=0, value=int(cont.get("premium", 0)), step=5, key="pre_sim_prem"))
    s = pr.calcular({"plus": n_plus, "premium": n_prem}, custo, cfg)
    cs = {"ok": "ok", "aviso": "aviso", "erro": "erro"}.get(s["situacao"], "info")
    st.markdown(_grade([_kpi("Receita líquida simulada", custos.brl(s["liquida"]), "info"),
                        _kpi("Lucro simulado", custos.brl(s["lucro"]), cs),
                        _kpi("Margem simulada", f"{s['margem']:.0f}%" if s["margem"] is not None else "—", cs, f"meta {cfg['margem_alvo']:.0f}%")]),
                unsafe_allow_html=True)
    total = n_plus + n_prem
    pm = pr.preco_minimo(custo, total, cfg)
    if pm is not None and total:
        st.markdown(_msg(f"Com {total} assinantes pagantes, o preço mensal mínimo para atingir a meta de {cfg['margem_alvo']:.0f}% é {custos.brl(pm)}"
                         + (" (custo atual R$ 0,00: qualquer preço cobre)." if custo <= 0 else "."), "info"), unsafe_allow_html=True)

    with st.expander("Editar preços, taxas e meta"):
        p1, p2 = st.columns(2)
        preco = {"plus": p1.number_input("Preço mensal Investidor Plus (R$)", min_value=0.0, value=float(cfg["preco"]["plus"]), step=1.0, key="pre_plus"),
                 "premium": p2.number_input("Preço mensal Investidor Premium (R$)", min_value=0.0, value=float(cfg["preco"]["premium"]), step=1.0, key="pre_prem")}
        t1, t2, t3 = st.columns(3)
        pct = t1.number_input("Taxa do pagamento (%)", min_value=0.0, max_value=30.0, value=float(cfg["taxa_pct"]), step=0.1, key="pre_pct")
        fixa = t2.number_input("Taxa fixa por cobrança (R$)", min_value=0.0, max_value=10.0, value=float(cfg["taxa_fixa"]), step=0.1, key="pre_fixa")
        alvo = t3.number_input("Margem alvo (%)", min_value=0.0, max_value=90.0, value=float(cfg["margem_alvo"]), step=5.0, key="pre_alvo")
        st.caption("As taxas começam em zero porque o meio de pagamento ainda não foi escolhido (Etapa 9).")
        if st.button("Salvar preços", key="pre_salvar", type="primary"):
            try:
                pr.salvar({"preco": preco, "taxa_pct": pct, "taxa_fixa": fixa, "margem_alvo": alvo})
                banco.auditar(a.id, "precos.config", None, {"plus": preco["plus"] > 0, "premium": preco["premium"] > 0})
                st.markdown(_msg("Preços salvos.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.precos", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


def _adm_pagamento_online(a) -> None:
    """Estado da conexão com o Mercado Pago, desconto do plano anual e últimas cobranças."""
    import pagamentos
    lig = pagamentos.ligado()
    st.markdown(_titulo("Pagamento online", "Mercado Pago, Pix e cartão, pago por período. O plano é liberado sozinho quando o pagamento é aprovado."), unsafe_allow_html=True)
    st.markdown(_grade([
        _kpi("Mercado Pago", ("Modo de teste" if pagamentos.modo_teste() else "Ligado") if lig else "Desligado", "aviso" if lig and pagamentos.modo_teste() else "ok" if lig else "erro",
             "chave encontrada nos secrets" if lig else "falta [mercadopago] access_token nos secrets"),
        _kpi("Voltar ao app", "Configurado" if pagamentos._app_url() else "Não configurado", "ok" if pagamentos._app_url() else "aviso",
             "app_url nos secrets" if pagamentos._app_url() else "opcional: o app confere o pagamento mesmo assim"),
        _kpi("Desconto no anual", f"{pagamentos.config()['desconto_anual_pct']:g}%", "info", "sobre 12 vezes o preço mensal")]), unsafe_allow_html=True)
    with st.expander("Editar desconto do plano anual"):
        d = st.number_input("Desconto no plano de 12 meses (%)", min_value=0.0, max_value=50.0, value=float(pagamentos.config()["desconto_anual_pct"]), step=1.0, key="pg_desc")
        if st.button("Salvar desconto", key="pg_desc_ok", type="primary"):
            try:
                pagamentos.salvar({"desconto_anual_pct": d})
                banco.auditar(a.id, "pagamento.desconto", None, {"pct": float(d)})
                st.markdown(_msg("Desconto salvo.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.pagamento", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
    try:
        ult = pagamentos.listar(25)
    except Exception:
        ult = []
    if ult:
        rot = {"pendente": "Aguardando", "pago": "Pago"}
        _tabela([{"quando": str(x.get("criado") or "")[:16].replace("T", " "), "email": x.get("email"), "plano": planos_rotulo(x.get("plano")),
                  "periodo": pagamentos.PERIODOS.get(x.get("periodo"), {}).get("rotulo", "—"), "valor": pagamentos.brl(float(x.get("valor") or 0)),
                  "situacao": rot.get(x.get("status"), x.get("status")) + (" (teste)" if x.get("teste") else "")} for x in ult],
                {"quando": "Quando (UTC)", "email": "Conta", "plano": "Plano", "periodo": "Período", "valor": "Valor", "situacao": "Situação"})
    else:
        st.markdown(_msg("Nenhuma cobrança criada ainda.", "info"), unsafe_allow_html=True)


def planos_rotulo(pl) -> str:
    import planos
    return planos.ROTULO.get(pl, str(pl or "—"))


def _adm_assinaturas(a) -> None:
    """Etapas 11-13: carência, avisos, teste grátis e cupons. Só administradores (admin.banco)."""
    import assinaturas
    import planos
    if not perm.tem(a.papel, "admin.banco"):
        raise banco.SemPermissao("Sem permissão para ver as assinaturas.")
    _adm_pagamento_online(a)
    cfg = assinaturas.config()
    t = cfg["teste"]
    st.markdown(_titulo("Regras da assinatura", "Carência, avisos de vencimento e teste grátis. O pagamento online (Mercado Pago) libera o plano sozinho; você ainda pode ativar e renovar à mão."), unsafe_allow_html=True)
    st.markdown(_grade([
        _kpi("Carência após vencer", f"{cfg['carencia_dias']} dias", "info", "o plano continua valendo; depois volta ao Gratuito"),
        _kpi("Avisos ao usuário", ", ".join(str(x) for x in cfg["avisos_dias"]) + " dias antes" if cfg["avisos_dias"] else "Desligados", "info", "mais o dia do vencimento e a carência"),
        _kpi("Teste grátis", f"{planos.ROTULO[t['plano']]} · {t['dias']} dias" if t["ligado"] else "Desligado", "ok" if t["ligado"] else "na", "uma vez por conta")]), unsafe_allow_html=True)
    with st.expander("Editar regras"):
        c1, c2 = st.columns(2)
        car = c1.number_input("Carência (dias)", min_value=0, max_value=30, value=int(cfg["carencia_dias"]), step=1, key="as_car")
        av = c2.text_input("Avisos (dias antes, separados por vírgula)", value=", ".join(str(x) for x in cfg["avisos_dias"]), key="as_av")
        lig = st.checkbox("Teste grátis ligado", value=bool(t["ligado"]), key="as_t_lig")
        t1, t2 = st.columns(2)
        pl = t1.selectbox("Plano do teste", ["plus", "premium"], index=["plus", "premium"].index(t["plano"]), format_func=planos.ROTULO.get, key="as_t_pl")
        di = t2.number_input("Duração do teste (dias)", min_value=1, max_value=30, value=int(t["dias"]), step=1, key="as_t_di")
        if st.button("Salvar regras", key="as_salvar", type="primary"):
            try:
                assinaturas.salvar({"carencia_dias": car, "avisos_dias": assinaturas.parse_dias(av), "teste": {"ligado": lig, "plano": pl, "dias": di}})
                planos._cache["planos"].clear()
                banco.auditar(a.id, "assinaturas.config", None, {"carencia": int(car), "teste": bool(lig)})
                st.markdown(_msg("Regras salvas. Valem em até 1 minuto.", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.assinaturas", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)

    st.markdown(_titulo("Cupons", "Cada cupom dá dias de um plano pago. Uma vez por conta; com limite de usos e data opcionais."), unsafe_allow_html=True)
    try:
        cupons = assinaturas.listar_cupons()
    except Exception as e:
        banco.registrar_erro("conta_app.cupons", e)
        cupons = []
    if cupons:
        cards = []
        for c in cupons:
            lim = f" de {c['max_usos']}" if c["max_usos"] else ""
            venc = f" · até {_data_br(c['validade_ate'])}" if c["validade_ate"] else ""
            cards.append(_kpi(c["codigo"], f"{c['usos']}{lim} usos", "ok" if c["ativo"] else "na",
                              f"{planos.ROTULO[c['plano']]} · {c['dias']} dias{venc}" + ("" if c["ativo"] else " · desativado")))
        st.markdown(_grade(cards), unsafe_allow_html=True)
    else:
        st.markdown(_msg("Nenhum cupom criado ainda.", "info"), unsafe_allow_html=True)
    with st.expander("Criar ou atualizar cupom"):
        c1, c2, c3 = st.columns(3)
        cod = c1.text_input("Código", key="cp_cod", max_chars=20, placeholder="BEMVINDO30")
        pl = c2.selectbox("Plano", ["plus", "premium"], format_func=planos.ROTULO.get, key="cp_pl")
        di = c3.number_input("Dias de plano", min_value=1, max_value=365, value=30, step=1, key="cp_di")
        d1, d2 = st.columns(2)
        mx = d1.number_input("Máximo de usos (0 = ilimitado)", min_value=0, value=0, step=1, key="cp_mx")
        vd = d2.text_input("Vale até (AAAA-MM-DD, opcional)", key="cp_vd", placeholder="2026-12-31")
        if st.button("Salvar cupom", key="cp_salvar", type="primary"):
            try:
                d = assinaturas.criar_cupom(cod, pl, di, vd.strip() or None, mx)
                banco.auditar(a.id, "cupom.criar", None, {"plano": pl, "dias": int(di)})
                st.markdown(_msg(f"Cupom {d['codigo']} salvo.", "ok"), unsafe_allow_html=True)
            except ValueError as e:
                st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.cupons", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
        if cupons:
            sel = st.selectbox("Ligar ou desligar um cupom", [c["codigo"] for c in cupons], key="cp_sel")
            atual = next(c for c in cupons if c["codigo"] == sel)
            if st.button("Desativar" if atual["ativo"] else "Reativar", key="cp_tog"):
                try:
                    assinaturas.definir_ativo(sel, not atual["ativo"])
                    banco.auditar(a.id, "cupom.ativo", None, {"ativo": not atual["ativo"]})
                    st.markdown(_msg("Pronto.", "ok"), unsafe_allow_html=True)
                except Exception as e:
                    banco.registrar_erro("conta_app.cupons", e)
                    st.markdown(_msg(f"Não consegui alterar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def _uso_coletado(dias: int) -> dict:
    import custo_usuario
    return custo_usuario.coletar(dias)


def _adm_uso(a) -> None:
    """Etapas 14-15: custo por usuário, plano e recurso; contas com uso fora do padrão; limites de rajada. Só administradores."""
    import abuso
    import custos
    import planos
    if not perm.tem(a.papel, "admin.banco"):
        raise banco.SemPermissao("Sem permissão para ver o uso por usuário.")
    dias = int(st.selectbox("Período", [7, 3, 1], format_func=lambda d: f"últimos {d} dias" if d > 1 else "hoje", key="uso_dias"))
    try:
        r = _uso_coletado(dias)
    except Exception as e:
        banco.registrar_erro("conta_app.uso", e)
        st.markdown(_msg(f"Não consegui carregar o uso ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
        return
    st.markdown(_titulo("Custo por plano", "Estimativa: uso de IA e de atualização de dados × custo por uso que você informa. Projeção para 30 dias por usuário."), unsafe_allow_html=True)
    cards = []
    for p in planos.PLANOS:
        x = r["por_plano"][p]
        if p == "gratuito" or x["margem_por_usuario"] is None:
            cards.append(_kpi(planos.ROTULO[p], f"{x['usuarios']} usuários ativos", "info",
                              f"custo médio {custos.brl(x['custo_mensal_por_usuario'])}/mês por usuário · sem receita"))
        else:
            m = x["margem_por_usuario"]
            cards.append(_kpi(planos.ROTULO[p], f"{x['usuarios']} usuários ativos", "ok" if m >= 0 else "erro",
                              f"custo médio {custos.brl(x['custo_mensal_por_usuario'])}/mês · receita líquida {custos.brl(x['receita_liquida'])} · "
                              f"sobra {custos.brl(m)} por usuário"))
    st.markdown(_grade(cards), unsafe_allow_html=True)
    st.markdown(_titulo("Custo por recurso"), unsafe_allow_html=True)
    st.markdown(_grade([_kpi(planos.RECURSOS[k]["rotulo"], f"{v['usos']} usos", "info", f"{custos.brl(v['custo'])} no período · {custos.brl(v['unit'])} por uso")
                        for k, v in r["por_recurso"].items()]), unsafe_allow_html=True)
    st.markdown(_titulo("Quem mais usa", "Os 10 maiores consumos do período. Só você vê isto."), unsafe_allow_html=True)
    if not r["usuarios"]:
        st.markdown(_msg("Ainda sem uso registrado neste período.", "info"), unsafe_allow_html=True)
    else:
        _tabela([{"email": u["email"], "plano": planos.ROTULO[u["plano"]], "usos": u["total_usos"], "custo": custos.brl(u["custo"]),
                  "bloqueios": u["negadas"], "dias": u["dias_ativos"]} for u in r["usuarios"][:10]],
                {"email": "E-mail", "plano": "Plano", "usos": "Usos", "custo": "Custo estimado", "bloqueios": "Bateu no limite", "dias": "Dias de uso"})
    st.markdown(_titulo("Uso fora do padrão", "Contas que bateram no limite do plano muitas vezes hoje. O app não bloqueia ninguém sozinho."), unsafe_allow_html=True)
    try:
        sus = abuso.suspeitos()
    except Exception as e:
        banco.registrar_erro("conta_app.abuso", e)
        sus = []
    if not sus:
        st.markdown(_msg("Nenhuma conta fora do padrão hoje.", "ok"), unsafe_allow_html=True)
    else:
        st.markdown(_grade([_kpi(x["email"], f"{x['negadas']} bloqueios", "aviso", f"{x['rajadas']} por rajada · {x['usos']} usos hoje") for x in sus[:12]]), unsafe_allow_html=True)
        st.caption("Para agir, vá em Usuários e use Suspender conta.")
    cfg = abuso.config()
    cc = custos.config()
    with st.expander("Editar limites e custos por uso"):
        c1, c2 = st.columns(2)
        raj = c1.number_input("Máximo de usos por minuto (0 = sem limite)", min_value=0, max_value=120, value=int(cfg["rajada_por_min"]), step=1, key="uso_raj",
                              help="Vale para IA e Atualizar dados, por pessoa.")
        al = c2.number_input("Avisar a partir de quantos bloqueios no dia (0 = nunca)", min_value=0, max_value=1000, value=int(cfg["alerta_negadas_dia"]), step=1, key="uso_al")
        st.markdown("**Custo por uso de cada recurso (R$)**. Se vazio, a IA usa o preço por 1.000 pedidos da fonte IA (em Custos).")
        novos = {}
        cols = st.columns(3)
        for i, (rid, rec) in enumerate((k, v) for k, v in planos.RECURSOS.items() if v["tipo"] == "dia"):
            novos[rid] = cols[i % 3].number_input(rec["rotulo"], min_value=0.0, value=float((cc.get("custo_recurso") or {}).get(rid, 0.0)), step=0.01,
                                                  format="%.4f", key=f"uso_c_{rid}")
        if st.button("Salvar", key="uso_salvar", type="primary"):
            try:
                abuso.salvar({"rajada_por_min": raj, "alerta_negadas_dia": al})
                custos.salvar({**cc, "custo_recurso": novos})
                banco.auditar(a.id, "uso.config", None, {"rajada": int(raj), "alerta": int(al)})
                st.markdown(_msg("Salvo. Os custos por uso entram nas contas a partir da próxima atualização (até 5 minutos).", "ok"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.uso", e)
                st.markdown(_msg(f"Não consegui salvar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


def _adm_continuidade(a) -> None:
    """Etapas 16-17: saúde do que mantém o app de pé, tamanho do banco, backup e restauração das configurações. Só administradores."""
    import manutencao
    if not perm.tem(a.papel, "admin.backup"):
        raise banco.SemPermissao("Sem permissão para ver a continuidade.")
    st.markdown(_titulo("Continuidade", "O que mantém o app funcionando se alguma parte falhar. Verificações reais, feitas agora."), unsafe_allow_html=True)
    cls = {"ok": "ok", "aviso": "aviso", "erro": "erro"}
    try:
        itens = manutencao.continuidade()
    except Exception as e:
        banco.registrar_erro("conta_app.continuidade", e)
        itens = []
    st.markdown(_grade([_kpi(i["nome"], {"ok": "Em ordem", "aviso": "Atenção", "erro": "Problema"}[i["situacao"]], cls[i["situacao"]], i["detalhe"]) for i in itens])
                if itens else _msg("Não consegui fazer as verificações agora.", "aviso"), unsafe_allow_html=True)
    st.markdown(_titulo("Tamanho do banco", "Contadores antigos são apagados sozinhos uma vez por dia (uso: 40 dias · consumo: 120 dias · tentativas de cupom: 3 dias)."), unsafe_allow_html=True)
    try:
        tam = manutencao.tamanho()
        ult = banco.cfg_ler("manutencao_ultima") or {}
        st.markdown(_grade([_kpi(k, "—" if v is None else v, "info") for k, v in tam.items()] +
                           [_kpi("Última faxina", _data_br(ult.get("dia")) if ult.get("dia") else "Ainda não rodou", "info",
                                 "apagou " + str(sum((ult.get("apagados") or {}).values())) + " registros" if ult.get("dia") else "roda no monitor")]), unsafe_allow_html=True)
    except Exception as e:
        banco.registrar_erro("conta_app.tamanho", e)
    st.markdown(_titulo("Backup das configurações", "Planos e validades das contas, cupons, testes grátis e todas as regras. Vem cifrado com a chave de backup dos Secrets."), unsafe_allow_html=True)
    chave = banco.secrets_secao("backup").get("chave")
    if not chave:
        st.markdown(_msg("Falta a chave de backup nos Secrets (seção [backup], campo chave). Crie em Segurança > Backup e restauração.", "info"), unsafe_allow_html=True)
        return
    if st.button("Gerar backup das configurações", key="cont_gerar", icon=":material/lock:"):
        try:
            cif, imp = manutencao.backup_para_arquivo(chave)
            st.session_state["_cont_bk"] = (cif, imp)
            from datetime import date as _d
            banco.cfg_gravar("backup_config_ultimo", {"dia": _d.today().isoformat()})
            banco.auditar(a.id, "backup.config", None, {"bytes": len(cif)})
        except Exception as e:
            banco.registrar_erro("conta_app.backup_config", e)
            st.markdown(_msg(f"Não consegui gerar o backup ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
    if st.session_state.get("_cont_bk"):
        cif, imp = st.session_state["_cont_bk"]
        st.download_button("Baixar backup das configurações", cif, "backup_config.enc", "application/octet-stream", key="cont_dl", icon=":material/download:")
        st.caption("SHA-256: " + imp + " · guarde o arquivo fora do app.")
    with st.expander("Restaurar a partir de um backup"):
        st.markdown(_msg("Isto sobrescreve planos, cupons e regras com o que está no arquivo. Faça apenas se algo se perdeu.", "aviso"), unsafe_allow_html=True)
        arq = st.file_uploader("Arquivo backup_config.enc", key="cont_up")
        ok = st.checkbox("Entendo que isso sobrescreve as configurações atuais", key="cont_ok")
        if st.button("Restaurar", key="cont_rest", disabled=not (arq and ok)):
            try:
                r = manutencao.restaurar_de_arquivo(arq.getvalue(), chave)
                banco.auditar(a.id, "restaurar.config", None, r)
                st.markdown(_msg(f"Restaurado: {r['restaurados']} itens ({r['ignorados']} ignorados).", "ok"), unsafe_allow_html=True)
            except ValueError as e:
                st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
            except Exception as e:
                banco.registrar_erro("conta_app.restaurar_config", e)
                st.markdown(_msg(f"Não consegui restaurar ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
