"""Passo 23 — Canais de entrega das notificações. Cada canal envia DE VERDADE ou devolve o motivo de não ter enviado; nada é simulado.

Canais reais e o que cada um exige:
  app       Sempre ligado: a notificação é gravada no banco e aparece na Central. Sem custo.
  email     SMTP já configurado no Passo 21 ([email] nos secrets). Gratuito com Gmail (senha de app). Limite do Gmail: ~500 e-mails/dia.
  telegram  Bot gratuito: crie com @BotFather, coloque [telegram] bot_token nos secrets. A pessoa vincula o próprio chat (código enviado ao bot).
  ntfy      Push no celular sem cadastro: instale o app ntfy e assine o tópico secreto da pessoa. Usa o servidor público ntfy.sh (gratuito, com
            limites) ou um servidor próprio em [ntfy] servidor. Quem souber o nome do tópico recebe os avisos: ele funciona como uma senha.
Não há push web nativo (exige service worker, impossível dentro do Streamlit) nem SMS/WhatsApp (pagos).
Os tokens só são lidos dos secrets; erros devolvem apenas o tipo da falha, nunca a URL (que no Telegram contém o token).
"""
from __future__ import annotations

import time

import banco
import email_envio
import notif as N
import seguranca as seg

TIMEOUT = 10
_PERMANENTES = {400, 401, 403, 404}        # não adianta tentar de novo


def _token_telegram() -> str:
    return str(banco.secrets_secao("telegram").get("bot_token") or "").strip()


def _servidor_ntfy() -> str:
    s = str(banco.secrets_secao("ntfy").get("servidor") or "https://ntfy.sh").strip().rstrip("/")
    return s if s.startswith("https://") else "https://ntfy.sh"


def disponiveis() -> dict:
    """{canal: (configurado, explicação)} — mostrado na tela para a pessoa saber o que realmente funciona."""
    em = email_envio.configurado()
    tg = bool(_token_telegram())
    return {
        "app": (True, "Sempre disponível."),
        "email": (em, "Pronto." if em else "O administrador ainda não configurou o envio de e-mails ([email] nos secrets)."),
        "telegram": (tg, "Pronto: vincule seu chat abaixo." if tg else "O administrador ainda não criou o bot do Telegram ([telegram] bot_token nos secrets)."),
        "ntfy": (True, f"Pronto: instale o app ntfy e assine o seu tópico (servidor {_servidor_ntfy().removeprefix('https://')})."),
    }


def _req():
    import requests
    return requests


# ------------------------------------------------------------------ envio (uma tentativa)
def enviar_email(destino: str, assunto: str, corpo: str) -> tuple[bool, str, bool]:
    """(ok, detalhe, tentar_de_novo)."""
    ok, msg = email_envio.enviar(destino, assunto, corpo)
    return ok, msg, (not ok and "configurado" not in msg)


def enviar_telegram(chat_id: str, assunto: str, corpo: str) -> tuple[bool, str, bool]:
    tok = _token_telegram()
    if not tok:
        return False, "Bot do Telegram não configurado.", False
    try:
        r = _req().post(f"https://api.telegram.org/bot{tok}/sendMessage",
                        json={"chat_id": chat_id, "text": corpo[:3900], "disable_web_page_preview": True}, timeout=TIMEOUT)
    except Exception as e:      # a exceção do requests pode citar a URL com o token: só o tipo sai
        return False, f"Falha de conexão com o Telegram ({e.__class__.__name__}).", True
    if r.status_code == 200:
        return True, "", False
    return False, f"O Telegram recusou o envio (HTTP {r.status_code}).", r.status_code not in _PERMANENTES


def enviar_ntfy(topico: str, assunto: str, corpo: str, prioridade: str = "default") -> tuple[bool, str, bool]:
    pr = {"alta": "high", "media": "default", "baixa": "low"}.get(prioridade, "default")
    try:
        r = _req().post(f"{_servidor_ntfy()}/{topico}", data=corpo.encode("utf-8"),
                        headers={"Title": assunto.encode("ascii", "ignore").decode()[:200] or "Bussola B3", "Priority": pr, "Tags": "chart_with_upwards_trend"},
                        timeout=TIMEOUT)
    except Exception as e:
        return False, f"Falha de conexão com o ntfy ({e.__class__.__name__}).", True
    if 200 <= r.status_code < 300:
        return True, "", False
    return False, f"O ntfy recusou o envio (HTTP {r.status_code}).", r.status_code not in _PERMANENTES


def enviar(canal: str, destino: str, assunto: str, corpo: str, importancia: str = "media") -> tuple[bool, str, bool]:
    if canal == "email":
        return enviar_email(destino, assunto, corpo)
    if canal == "telegram":
        return enviar_telegram(destino, assunto, corpo)
    if canal == "ntfy":
        return enviar_ntfy(destino, assunto, corpo, importancia)
    return False, "Canal desconhecido.", False


def enviar_com_retentativa(canal: str, destino: str, assunto: str, corpo: str, importancia: str = "media", tentativas: int = 3,
                           espera: float = 2.0, dormir=time.sleep) -> dict:
    """Tenta até `tentativas` vezes com espera crescente, só para falhas passageiras (rede, 5xx, 429). Devolve o resultado REAL."""
    ultimo = ""
    for i in range(1, max(1, tentativas) + 1):
        ok, det, de_novo = enviar(canal, destino, assunto, corpo, importancia)
        if ok:
            return {"ok": True, "tentativas": i, "quando": seg.iso(), "detalhe": ""}
        ultimo = det
        if not de_novo or i >= tentativas:
            break
        dormir(espera * i)
    return {"ok": False, "tentativas": i, "quando": seg.iso(), "detalhe": ultimo}


def entregar(n: dict, prefs: dict, destinos: dict, agora=None, enviadas_hoje: int = 0, url_app: str = "", dormir=time.sleep) -> dict:
    """Envia a notificação pelos canais externos permitidos e devolve {canal: resultado}. Vazio = nenhum canal externo elegível."""
    agora = agora or seg.agora()
    assunto, corpo = N.texto_externo(n, url_app)
    out = {}
    for c in N.canais_externos(n, prefs, destinos, agora, enviadas_hoje):
        out[c] = enviar_com_retentativa(c, destinos[c], assunto, corpo, n.get("importancia", "media"), dormir=dormir)
    return out


# ------------------------------------------------------------------ vínculo do Telegram (código enviado ao bot)
def telegram_bot() -> dict:
    """{'usuario': '@nome_do_bot'} se o token for válido."""
    tok = _token_telegram()
    if not tok:
        return {}
    try:
        r = _req().get(f"https://api.telegram.org/bot{tok}/getMe", timeout=TIMEOUT)
        if r.status_code == 200 and r.json().get("ok"):
            return {"usuario": "@" + str(r.json()["result"].get("username") or "")}
    except Exception:
        pass
    return {}


def novo_codigo_vinculo() -> str:
    import secrets
    return "BPT" + secrets.token_hex(4).upper()


def telegram_vincular(codigo: str) -> tuple[str | None, str]:
    """Procura nas mensagens recentes do bot uma que seja exatamente o código. Devolve (chat_id, mensagem)."""
    tok = _token_telegram()
    if not tok:
        return None, "Bot do Telegram não configurado."
    try:
        r = _req().get(f"https://api.telegram.org/bot{tok}/getUpdates", params={"limit": 100, "timeout": 0}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, f"O Telegram não respondeu (HTTP {r.status_code})."
        for u in reversed(r.json().get("result") or []):
            m = u.get("message") or {}
            if str(m.get("text") or "").strip().upper().removeprefix("/START ").strip() == str(codigo).upper():
                return str((m.get("chat") or {}).get("id")), "Chat vinculado."
    except Exception as e:
        return None, f"Falha de conexão com o Telegram ({e.__class__.__name__})."
    return None, "Não achei o código. Envie exatamente o código ao bot e toque em verificar de novo."
