"""Envio de e-mails do app (confirmação de cadastro e recuperação de senha) por SMTP. Gratuito com Gmail, por exemplo.

Configuração nos secrets (Streamlit Cloud > Settings > Secrets):

    [email]
    servidor = "smtp.gmail.com"
    porta = 465                      # 465 = SSL, 587 = STARTTLS
    usuario = "seu_email@gmail.com"
    senha = "senha-de-app-de-16-letras"   # no Gmail: Conta Google > Segurança > Senhas de app
    remetente = "Bússola B3 <seu_email@gmail.com>"   # opcional

    [app]
    url = "https://seu-app.streamlit.app"   # usada nos links dos e-mails

A senha do SMTP só é lida dos secrets e nunca aparece em tela, log ou erro.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

import banco
import seguranca as seg


def config() -> dict:
    c = banco.secrets_secao("email")
    try:
        return {"servidor": str(c["servidor"]).strip(), "porta": int(c.get("porta", 465)),
                "usuario": str(c["usuario"]).strip(), "senha": str(c["senha"]),
                "remetente": str(c.get("remetente") or c["usuario"]).strip()}
    except Exception:
        return {}


def configurado() -> bool:
    return bool(config())


def url_base() -> str:
    """Endereço público do app (sem barra no fim), vindo de [app].url ou do redirect_uri do login Google."""
    u = str(banco.secrets_secao("app").get("url") or "").strip().rstrip("/")
    if not u:
        ru = str(banco.secrets_secao("auth").get("redirect_uri") or "").strip()
        u = ru.removesuffix("/oauth2callback").rstrip("/")
    return u


def link(tipo: str, token: str) -> str:
    """tipo: 'verificar' ou 'redefinir'. O token vai na URL uma única vez e só vale uma vez."""
    base = url_base()
    return f"{base}/?{tipo}={token}" if base else ""


def enviar(para: str, assunto: str, texto: str) -> tuple[bool, str]:
    c = config()
    if not c:
        return False, "O envio de e-mails ainda não foi configurado."
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = c["remetente"], para, assunto
    msg.set_content(texto)
    try:
        ctx = ssl.create_default_context()
        if c["porta"] == 465:
            with smtplib.SMTP_SSL(c["servidor"], c["porta"], timeout=15, context=ctx) as s:
                s.login(c["usuario"], c["senha"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(c["servidor"], c["porta"], timeout=15) as s:
                s.starttls(context=ctx)
                s.login(c["usuario"], c["senha"])
                s.send_message(msg)
        return True, ""
    except Exception as e:  # a mensagem do servidor pode citar usuário/senha: só o tipo do erro segue adiante
        banco.registrar_erro("email_envio", e)
        return False, f"Não consegui enviar o e-mail ({e.__class__.__name__})."


def texto_verificacao(nome: str, url: str, horas: int = 24) -> tuple[str, str]:
    return ("Confirme seu e-mail · Bússola B3",
            f"Olá, {nome.split()[0] if nome else ''}!\n\nPara ativar sua conta, abra o link abaixo (vale por {horas} horas e só pode ser usado uma vez):\n\n"
            f"{url}\n\nSe você não criou essa conta, ignore esta mensagem: nada será ativado.\n\n"
            "Bússola B3 · ferramenta educacional, sem recomendação de investimento.")


def texto_redefinicao(nome: str, url: str, minutos: int = 60) -> tuple[str, str]:
    return ("Redefinir sua senha · Bússola B3",
            f"Olá, {nome.split()[0] if nome else ''}!\n\nRecebemos um pedido para redefinir sua senha. Abra o link abaixo "
            f"(vale por {minutos} minutos e só pode ser usado uma vez):\n\n{url}\n\n"
            "Se não foi você, ignore esta mensagem: sua senha atual continua valendo.\n\n"
            "Bússola B3 · ferramenta educacional, sem recomendação de investimento.")


_ = seg  # (mantido para evitar importação circular futura)
