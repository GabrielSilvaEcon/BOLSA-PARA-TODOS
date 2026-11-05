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

import banco
import contas
import email_envio as mail
import permissoes as perm
import prefs as P
import seguranca as seg
import usuarios

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # sem base de fusos: horário de Brasília fixo
    _TZ = timezone(timedelta(hours=-3))

PAGINAS: dict = {}     # app.py registra aqui as páginas para os atalhos do painel


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
    if ok:
        res = contas.entrar(email, senha, usuarios.cliente_id(), lembrar)
        if res.ok:
            res.dado["lembrar"] = lembrar
            usuarios.iniciar_sessao_senha(res)
            st.rerun()
        _resultado(res)
    with st.expander("Não recebi o e-mail de confirmação"):
        e2 = st.text_input("E-mail do cadastro", key="reenv_email")
        if st.button("Reenviar confirmação", key="reenv_btn", width="stretch"):
            _resultado(contas.reenviar_verificacao(e2, usuarios.cliente_id()))


def _form_criar():
    with st.form("f_criar"):
        nome = st.text_input("Nome", key="cr_nome", autocomplete="name")
        email = st.text_input("E-mail", key="cr_email", autocomplete="email")
        senha = st.text_input("Senha", type="password", key="cr_senha", autocomplete="new-password")
        conf = st.text_input("Repita a senha", type="password", key="cr_senha2", autocomplete="new-password")
        aceite = st.checkbox("Li e aceito o tratamento dos meus dados descrito abaixo (LGPD)", key="cr_aceite")
        ok = _enviar("Criar conta", type="primary", width="stretch")
    st.markdown(_regras_senha(), unsafe_allow_html=True)
    if ok:
        _resultado(contas.cadastrar(nome, email, senha, conf, aceite, usuarios.cliente_id()))


def _form_esqueci():
    st.markdown(_titulo("Recuperar acesso", "Enviaremos um link para criar uma nova senha. Vale por 1 hora e só funciona uma vez."),
                unsafe_allow_html=True)
    with st.form("f_esqueci"):
        email = st.text_input("E-mail da conta", key="es_email", autocomplete="email")
        ok = _enviar("Enviar link", type="primary", width="stretch")
    if ok:
        _resultado(contas.solicitar_redefinicao(email, usuarios.cliente_id()))


def tela_acesso(logo_uri: str = "", nome: str = "Bússola B3") -> None:
    """Tela de entrada: Google, e-mail e senha (se configurado) ou visitante. Também recebe os links dos e-mails."""
    st.markdown(usuarios._css_login(), unsafe_allow_html=True)
    _css()
    img = f'<img src="{_e(logo_uri)}" alt="{_e(nome)}">' if logo_uri else ""
    ss = st.session_state
    with st.container(key="login_card"):
        st.markdown(
            f'<div class="lg-hero"><div class="lg-ringav"><div class="lg-av">{img}</div></div></div>'
            f'<div class="lg-marca">{_e(nome)}</div>'
            '<div class="lg-slides">'
            '<div class="lg-s s1"><h2>Seu norte no mercado brasileiro</h2>'
            '<p>Entenda, em linguagem simples, se o preço de uma ação está justo.</p></div>'
            '<div class="lg-s s2"><h2>Análise técnica sem mistério</h2>'
            '<p>Setups, médias e sinais marcados direto no gráfico.</p></div>'
            '<div class="lg-s s3"><h2>Sua carteira em qualquer aparelho</h2>'
            '<p>Entre e suas empresas, perfil e compras ficam guardados, só para você.</p></div></div>'
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
        if usuarios._configurado():
            if st.button("Continuar com o Google", key="login_google", type="primary", width="stretch"):
                try:
                    st.login("google")
                except Exception as e:
                    st.markdown(_msg(f"Não foi possível iniciar o login ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)
        if usuarios.senha_disponivel():
            if usuarios._configurado():
                st.markdown('<div class="lg-ou"><span>ou entre com e-mail e senha</span></div>', unsafe_allow_html=True)
            with st.container(key="acesso_card"):
                t1, t2, t3 = st.tabs(["Entrar", "Criar conta", "Esqueci a senha"])
                with t1:
                    _form_entrar()
                with t2:
                    _form_criar()
                with t3:
                    _form_esqueci()
        st.button("Continuar como visitante", icon=":material/person:", key="login_visit", width="stretch",
                  on_click=usuarios._virar_visitante)
        st.markdown(
            '<div class="lg-foot"><b>Seus dados e a LGPD:</b> guardamos só o necessário para o app funcionar (nome, e-mail, '
            'o que você salvar e registros de segurança). Nada é vendido ou compartilhado. Você pode baixar ou apagar tudo em '
            '<i>Minha conta &gt; Privacidade</i>. Como visitante nada fica salvo. Ferramenta educacional, sem recomendação de '
            'investimento.</div>', unsafe_allow_html=True)
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


def _secao_painel(u: dict) -> None:
    ss = st.session_state
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
    for b in d["ordem"]:
        if b not in d["ocultos"]:
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
        nem = n3.checkbox("Avisos por e-mail", value=n["email"], help="Guardamos a escolha; o envio de avisos por e-mail ainda não está ativo.")
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
                 "modo": pr["modo"]}
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
    secs = ["Resumo", "Usuários", "Auditoria", "Erros", "Sistema"]
    sec = st.segmented_control("Seção", secs, default="Resumo", key="admin_secao", label_visibility="collapsed") or "Resumo"
    try:
        {"Resumo": _adm_resumo, "Usuários": _adm_usuarios, "Auditoria": _adm_auditoria, "Erros": _adm_erros,
         "Sistema": _adm_sistema}[sec](a)
    except banco.SemPermissao as e:
        st.markdown(_msg(str(e), "erro"), unsafe_allow_html=True)
    except Exception as e:
        banco.registrar_erro("conta_app.admin", e)
        st.markdown(_msg(f"Não consegui carregar esta seção agora ({e.__class__.__name__}).", "erro"), unsafe_allow_html=True)


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
        _kpi("Administradores nos secrets", len(contas.admins_dos_secrets()), "info")]), unsafe_allow_html=True)
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
