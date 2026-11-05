"""Serviço de contas (Passo 21): cadastro, confirmação de e-mail, login por senha, sessões, recuperação e exclusão.

Não depende do Streamlit (a tela vive em conta_app.py), então todos os fluxos são testáveis. Convive com o login do
Google (usuarios.py): as duas formas de entrar apontam para a MESMA conta (identificada pelo e-mail confirmado), então
os dados de quem já usava o app continuam onde estavam.

Decisões de segurança:
- Mensagens de login e recuperação são iguais para "e-mail inexistente" e "senha errada" (não revelam quem tem conta).
- Cadastro e recuperação só funcionam com envio de e-mail configurado: a posse do e-mail é provada pelo link.
- Conta por senha nasce 'pendente' e sem dados. Se alguém cadastrar o e-mail de outra pessoa, a senha escolhida é
  descartada quando o verdadeiro dono entra pelo Google ou redefine a senha.
- Tentativas excessivas são bloqueadas por e-mail e por navegador (tabela tentativas, vale entre sessões).
- Tokens de sessão/verificação/redefinição ficam só como SHA-256 no banco e são de uso único (os dois últimos).
"""
from __future__ import annotations

from typing import Any, NamedTuple

import banco
import email_envio as mail
import permissoes as perm
import seguranca as seg


class Res(NamedTuple):
    ok: bool
    msg: str
    dado: Any = None


# limites: (máximo de tentativas, janela em segundos)
LIMITE_LOGIN = (5, 900)
LIMITE_LOGIN_CLIENTE = (12, 900)
LIMITE_CADASTRO = (5, 3600)
LIMITE_REDEFINIR = (3, 3600)
LIMITE_SENHA_ATUAL = (5, 900)
VALIDADE_VERIFICAR = 24 * 3600
VALIDADE_REDEFINIR = 3600
SESSAO_PADRAO = {"ocioso": 3600, "absoluto": 12 * 3600}
SESSAO_LEMBRAR = {"ocioso": 7 * 86400, "absoluto": 30 * 86400}
TOQUE_SESSAO_S = 60          # atualiza "último uso" no banco no máximo a cada 60 s

MSG_LOGIN_FALHA = "E-mail ou senha incorretos. Se você costuma entrar com o Google, use o botão do Google."
MSG_BLOQUEIO = "Muitas tentativas seguidas. Por segurança, aguarde alguns minutos e tente de novo."
MSG_GENERICA_REDEFINIR = "Se existir uma conta com esse e-mail, enviamos um link para criar uma nova senha. Confira também o spam."

_ultima_limpeza = [0.0]


# ------------------------------------------------------------------ utilidades
def _pronto() -> Res | None:
    ok, motivo = banco.pronto()
    return None if ok else Res(False, "O cadastro e o login por senha estão indisponíveis agora. " + motivo)


def _excedeu(chave: str, tipo: str, limite: tuple[int, int]) -> bool:
    return banco.tentativas_desde(chave, tipo, seg.somar(-limite[1])) >= limite[0]


def _chaves_cliente(cliente: str) -> str:
    return "c:" + seg.hash_curto(cliente or "anonimo")


def _chave_email(email: str) -> str:
    return "e:" + seg.hash_curto(seg.normalizar_email(email))


def _limpeza_ocasional() -> None:
    agora = seg.agora().timestamp()
    if agora - _ultima_limpeza[0] > 3600:
        _ultima_limpeza[0] = agora
        banco.limpar_antigos()


def admins_dos_secrets() -> list[str]:
    try:
        return [str(e).strip().lower() for e in banco.secrets_secao("admin").get("emails", [])]
    except Exception:
        return []


def papel_da_conta(conta: dict) -> str:
    return perm.papel_efetivo(conta.get("papel"), conta.get("email", ""), admins_dos_secrets())


def ator_de(conta: dict) -> banco.Ator:
    return banco.Ator(id=conta["id"], email=conta["email"], papel=papel_da_conta(conta))


def _nova_conta(email: str, nome: str, provedor: str, status: str, verificado: int, senha_hash=None) -> dict:
    return {"id": seg.novo_id(), "email": email, "nome": nome, "senha_hash": senha_hash, "papel": "usuario",
            "status": status, "email_verificado": verificado, "provedor": provedor, "criado_em": seg.iso(),
            "ultimo_login": None, "aceite_em": seg.iso()}


def _emitir_token(conta_id: str, tipo: str, validade: int) -> str:
    banco.sis_invalidar_tokens(conta_id, tipo)
    token, h = seg.novo_token()
    banco.sis_gravar_token({"token_hash": h, "conta_id": conta_id, "tipo": tipo, "criado_em": seg.iso(),
                            "expira_em": seg.somar(validade), "usado": 0})
    return token


def _token_valido(token: str, tipo: str) -> dict | None:
    t = banco.sis_token(seg.hash_token(token))
    if not t or t["tipo"] != tipo or t["usado"] or t["expira_em"] < seg.iso():
        return None
    return t


# ------------------------------------------------------------------ cadastro e confirmação
def cadastrar(nome: str, email: str, senha: str, confirmacao: str, aceite: bool, cliente: str = "") -> Res:
    if (r := _pronto()):
        return r
    if not mail.configurado() or not mail.url_base():
        return Res(False, "O cadastro por e-mail ainda não está ativo neste app. Entre com o Google por enquanto.")
    ok, nome, m = seg.validar_nome(nome)
    if not ok:
        return Res(False, m)
    ok, email, m = seg.validar_email(email)
    if not ok:
        return Res(False, m)
    erros = seg.validar_senha(senha, email, nome)
    if erros:
        return Res(False, "Senha fraca. " + " ".join(erros))
    if senha != confirmacao:
        return Res(False, "As senhas não são iguais. Digite a mesma senha nos dois campos.")
    if not aceite:
        return Res(False, "Para criar a conta, marque que leu e aceita o tratamento dos dados descrito abaixo.")
    kc, ke = _chaves_cliente(cliente), _chave_email(email)
    if _excedeu(kc, "cadastro", LIMITE_CADASTRO) or _excedeu(ke, "cadastro", LIMITE_CADASTRO):
        return Res(False, "Muitos cadastros em pouco tempo. Aguarde um pouco e tente de novo.")
    banco.tentativa_registrar(kc, "cadastro")
    banco.tentativa_registrar(ke, "cadastro")

    existente = banco.sis_conta_por_email(email)
    h = seg.hash_senha(senha)
    if existente and existente["status"] != "pendente":
        if existente["provedor"] == "google":
            return Res(False, "Esse e-mail já entra com o Google. Use o botão do Google (e, se quiser, crie uma senha em "
                              "\"Esqueci minha senha\").")
        return Res(False, "Já existe uma conta com esse e-mail. Entre ou use \"Esqueci minha senha\".")
    try:
        if existente:   # cadastro anterior nunca confirmado: substitui os dados e reenvia
            conta_id = existente["id"]
            banco.sis_atualizar_conta(conta_id, {"nome": nome, "senha_hash": h, "aceite_em": seg.iso()})
        else:
            conta = _nova_conta(email, nome, "senha", "pendente", 0, h)
            banco.sis_criar_conta(conta)
            conta_id = conta["id"]
            banco.auditar(conta_id, "conta.criada", conta_id)
    except banco.Duplicado:
        return Res(False, "Já existe uma conta com esse e-mail. Entre ou use \"Esqueci minha senha\".")
    token = _emitir_token(conta_id, "verificar", VALIDADE_VERIFICAR)
    assunto, texto = mail.texto_verificacao(nome, mail.link("verificar", token))
    enviado, erro = mail.enviar(email, assunto, texto)
    if not enviado:
        return Res(False, "Sua conta foi criada, mas não consegui enviar o e-mail de confirmação. " + erro +
                          " Use \"Reenviar confirmação\" em alguns minutos.", {"conta_id": conta_id})
    return Res(True, "Conta criada! Enviamos um link de confirmação para o seu e-mail (vale por 24 horas). "
                     "Abra o link para ativar a conta.", {"conta_id": conta_id})


def reenviar_verificacao(email: str, cliente: str = "") -> Res:
    if (r := _pronto()):
        return r
    msg = "Se esse e-mail tiver um cadastro aguardando confirmação, enviamos um novo link. Confira também o spam."
    ok, email, _ = seg.validar_email(email)
    if not ok or not mail.configurado():
        return Res(True, msg) if ok else Res(False, "Informe um e-mail válido.")
    kc, ke = _chaves_cliente(cliente), _chave_email(email)
    if _excedeu(kc, "reenvio", LIMITE_REDEFINIR) or _excedeu(ke, "reenvio", LIMITE_REDEFINIR):
        return Res(False, "Você pediu links demais em pouco tempo. Aguarde um pouco.")
    banco.tentativa_registrar(kc, "reenvio")
    banco.tentativa_registrar(ke, "reenvio")
    conta = banco.sis_conta_por_email(email)
    if conta and conta["status"] == "pendente":
        token = _emitir_token(conta["id"], "verificar", VALIDADE_VERIFICAR)
        mail.enviar(email, *mail.texto_verificacao(conta["nome"], mail.link("verificar", token)))
    return Res(True, msg)


def verificar_email(token: str) -> Res:
    if (r := _pronto()):
        return r
    t = _token_valido(token, "verificar")
    if not t:
        return Res(False, "Esse link não é mais válido (já foi usado ou venceu). Peça um novo na tela de entrada.")
    conta = banco.sis_conta_por_id(t["conta_id"])
    if not conta:
        return Res(False, "Esse link não é mais válido.")
    banco.sis_usar_token(t["token_hash"])
    campos = {"email_verificado": 1}
    if conta["status"] == "pendente":
        campos["status"] = "ativa"
    banco.sis_atualizar_conta(conta["id"], campos)
    banco.auditar(conta["id"], "conta.verificada", conta["id"])
    return Res(True, "E-mail confirmado! Sua conta está ativa. Agora é só entrar.")


# ------------------------------------------------------------------ sessão
def criar_sessao(conta_id: str, lembrar: bool = False) -> str:
    cfg = SESSAO_LEMBRAR if lembrar else SESSAO_PADRAO
    token, h = seg.novo_token()
    agora = seg.iso()
    banco.sis_gravar_sessao({"token_hash": h, "conta_id": conta_id, "criado_em": agora, "ultimo_uso": agora,
                             "expira_em": seg.somar(cfg["absoluto"]), "ocioso_s": cfg["ocioso"], "revogada": 0})
    return token


def validar_sessao(token: str | None) -> dict | None:
    """Conta (campos públicos) dona da sessão, ou None se a sessão não existe, foi revogada, venceu, ficou ociosa
    demais ou a conta não está mais ativa."""
    if not token or len(token) > 200:
        return None
    s = banco.sis_sessao(seg.hash_token(token))
    if not s or s["revogada"]:
        return None
    agora = seg.agora()
    ult = seg.de_iso(s["ultimo_uso"])
    if s["expira_em"] < seg.iso(agora) or not ult or (agora - ult).total_seconds() > int(s["ocioso_s"]):
        banco.sis_revogar_sessao(s["token_hash"])
        return None
    conta = banco.sis_conta_por_id(s["conta_id"])
    if not conta or conta["status"] != "ativa":
        return None
    if (agora - ult).total_seconds() >= TOQUE_SESSAO_S:
        banco.sis_tocar_sessao(s["token_hash"], seg.iso(agora))
    return conta


def encerrar_sessao(token: str | None, conta_id: str | None = None) -> None:
    if token:
        banco.sis_revogar_sessao(seg.hash_token(token))
    if conta_id:
        banco.auditar(conta_id, "logout", conta_id)


def encerrar_todas(ator: banco.Ator, manter_token: str | None = None) -> Res:
    banco.sis_revogar_sessoes_da_conta(ator.id, seg.hash_token(manter_token) if manter_token else None)
    banco.auditar(ator.id, "sessoes.encerradas", ator.id)
    return Res(True, "Pronto: os outros aparelhos foram desconectados." if manter_token else "Todas as sessões foram encerradas.")


# ------------------------------------------------------------------ login por senha
def entrar(email: str, senha: str, cliente: str = "", lembrar: bool = False) -> Res:
    """Res.dado = {'token', 'conta'} quando ok."""
    if (r := _pronto()):
        return r
    _limpeza_ocasional()
    ok, email_n, _ = seg.validar_email(email)
    ke, kc = _chave_email(email_n or email), _chaves_cliente(cliente)
    if _excedeu(ke, "login", LIMITE_LOGIN) or _excedeu(kc, "login", LIMITE_LOGIN_CLIENTE):
        banco.auditar(None, "login.bloqueado", None, {"chave": ke[-10:]})
        return Res(False, MSG_BLOQUEIO)
    conta = banco.sis_conta_por_email(email_n, com_senha=True) if ok else None
    if not conta or not conta.get("senha_hash") or not seg.verificar_senha(senha or "", conta["senha_hash"]):
        if not conta or not conta.get("senha_hash"):
            seg.gastar_tempo_falso(senha or "")
        banco.tentativa_registrar(ke, "login")
        banco.tentativa_registrar(kc, "login")
        banco.auditar(conta["id"] if conta else None, "login.falha", conta["id"] if conta else None,
                      {"chave": ke[-10:], "cliente": kc[-10:]})
        return Res(False, MSG_LOGIN_FALHA)
    if conta["status"] == "pendente":
        return Res(False, "Falta confirmar seu e-mail. Abra o link que enviamos ou use \"Reenviar confirmação\".", {"pendente": True})
    if conta["status"] == "suspensa":
        banco.auditar(conta["id"], "login.negado", conta["id"], {"motivo": "conta suspensa"})
        return Res(False, "Esta conta está suspensa. Fale com o suporte para entender o motivo.")
    banco.tentativas_limpar(ke, "login")
    campos = {"ultimo_login": seg.iso()}
    if seg.precisa_rehash(conta["senha_hash"]):
        campos["senha_hash"] = seg.hash_senha(senha)
    banco.sis_atualizar_conta(conta["id"], campos)
    token = criar_sessao(conta["id"], lembrar)
    banco.auditar(conta["id"], "login", conta["id"])
    pub = {k: v for k, v in conta.items() if k != "senha_hash"}
    return Res(True, "Login realizado.", {"token": token, "conta": pub})


# ------------------------------------------------------------------ login com Google (mesma conta, mesmo e-mail)
def login_google(email: str, nome: str) -> Res:
    """Cria ou atualiza a conta de quem entrou pelo Google. O Google já comprovou o e-mail."""
    ok, e, _ = seg.validar_email(email)
    if not ok:
        e = seg.normalizar_email(email)   # login antigo sem e-mail ("sub:...") continua funcionando
    if not e:
        return Res(False, "Não foi possível identificar sua conta Google.")
    ok_p, pronto_msg = banco.pronto()
    if not ok_p:
        return Res(False, pronto_msg)
    conta = banco.sis_conta_por_email(e)
    if not conta:
        nova = _nova_conta(e, " ".join(str(nome or "").split())[:80] or e.split("@")[0], "google", "ativa", 1 if ok else 0)
        try:
            banco.sis_criar_conta(nova)
            banco.auditar(nova["id"], "conta.criada", nova["id"], {"via": "google"})
            conta = nova
        except banco.Duplicado:
            conta = banco.sis_conta_por_email(e)
    if conta["status"] == "suspensa":
        return Res(False, "Esta conta está suspensa. Fale com o suporte para entender o motivo.")
    campos = {"ultimo_login": seg.iso()}
    if conta["status"] == "pendente":     # alguém cadastrou este e-mail com senha sem confirmar: a senha é descartada
        campos.update({"status": "ativa", "email_verificado": 1, "senha_hash": None, "provedor": "google"})
    elif not conta["email_verificado"] and ok:
        campos["email_verificado"] = 1
    if conta["provedor"] == "senha" and conta["status"] == "ativa":
        campos["provedor"] = "ambos"
    banco.sis_atualizar_conta(conta["id"], campos)
    banco.auditar(conta["id"], "login.google", conta["id"])
    return Res(True, "", {**conta, **{k: v for k, v in campos.items() if k != "senha_hash"}})


def conta_ativa_por_email(email: str) -> dict | None:
    """Releitura leve (sem senha) para revalidar quem entrou pelo Google: pegamos suspensões feitas depois do login."""
    try:
        c = banco.sis_conta_por_email(email)
    except Exception as e:
        banco.registrar_erro("contas.revalidar", e)
        return None
    return c if c and c["status"] == "ativa" else None


# ------------------------------------------------------------------ recuperação e alteração de senha
def solicitar_redefinicao(email: str, cliente: str = "") -> Res:
    if (r := _pronto()):
        return r
    if not mail.configurado() or not mail.url_base():
        return Res(False, "A recuperação por e-mail ainda não está ativa neste app.")
    ok, email_n, m = seg.validar_email(email)
    if not ok:
        return Res(False, m)
    kc, ke = _chaves_cliente(cliente), _chave_email(email_n)
    if _excedeu(kc, "redefinir", LIMITE_REDEFINIR) or _excedeu(ke, "redefinir", LIMITE_REDEFINIR):
        return Res(False, "Você pediu links demais em pouco tempo. Aguarde um pouco e tente de novo.")
    banco.tentativa_registrar(kc, "redefinir")
    banco.tentativa_registrar(ke, "redefinir")
    conta = banco.sis_conta_por_email(email_n)
    banco.auditar(conta["id"] if conta else None, "senha.link_pedido", conta["id"] if conta else None, {"chave": ke[-10:]})
    if conta and conta["status"] != "suspensa":
        if conta["status"] == "pendente":
            token = _emitir_token(conta["id"], "verificar", VALIDADE_VERIFICAR)
            mail.enviar(email_n, *mail.texto_verificacao(conta["nome"], mail.link("verificar", token)))
        else:
            token = _emitir_token(conta["id"], "redefinir", VALIDADE_REDEFINIR)
            mail.enviar(email_n, *mail.texto_redefinicao(conta["nome"], mail.link("redefinir", token)))
    return Res(True, MSG_GENERICA_REDEFINIR)


def token_redefinicao_valido(token: str) -> bool:
    ok, _ = banco.pronto()
    return bool(ok and token and _token_valido(token, "redefinir"))


def redefinir_senha(token: str, nova: str, confirmacao: str) -> Res:
    if (r := _pronto()):
        return r
    t = _token_valido(token, "redefinir")
    if not t:
        return Res(False, "Esse link não é mais válido (já foi usado ou venceu). Peça um novo em \"Esqueci minha senha\".")
    conta = banco.sis_conta_por_id(t["conta_id"])
    if not conta or conta["status"] == "suspensa":
        return Res(False, "Não foi possível redefinir a senha desta conta.")
    erros = seg.validar_senha(nova, conta["email"], conta["nome"])
    if erros:
        return Res(False, "Senha fraca. " + " ".join(erros))
    if nova != confirmacao:
        return Res(False, "As senhas não são iguais. Digite a mesma senha nos dois campos.")
    banco.sis_usar_token(t["token_hash"])
    campos = {"senha_hash": seg.hash_senha(nova), "email_verificado": 1, "status": "ativa",
              "provedor": "ambos" if conta["provedor"] == "google" else conta["provedor"]}
    banco.sis_atualizar_conta(conta["id"], campos)
    banco.sis_revogar_sessoes_da_conta(conta["id"])
    banco.tentativas_limpar(_chave_email(conta["email"]), "login")
    banco.auditar(conta["id"], "senha.redefinida", conta["id"])
    return Res(True, "Senha criada! Todos os aparelhos foram desconectados. Agora entre com a nova senha.")


def alterar_senha(ator: banco.Ator, atual: str, nova: str, confirmacao: str, token_atual: str | None = None) -> Res:
    if (r := _pronto()):
        return r
    chave = "a:" + ator.id
    if _excedeu(chave, "senha_atual", LIMITE_SENHA_ATUAL):
        return Res(False, MSG_BLOQUEIO)
    conta = banco.sis_conta_por_id(ator.id, com_senha=True)
    if not conta or not conta.get("senha_hash"):
        return Res(False, "Sua conta entra só com o Google e ainda não tem senha. Para criar uma, use \"Esqueci minha senha\" na tela de entrada.")
    if not seg.verificar_senha(atual or "", conta["senha_hash"]):
        banco.tentativa_registrar(chave, "senha_atual")
        return Res(False, "A senha atual não confere.")
    erros = seg.validar_senha(nova, conta["email"], conta["nome"])
    if erros:
        return Res(False, "Senha fraca. " + " ".join(erros))
    if nova != confirmacao:
        return Res(False, "As senhas não são iguais. Digite a mesma senha nos dois campos.")
    if seg.verificar_senha(nova, conta["senha_hash"]):
        return Res(False, "A nova senha precisa ser diferente da atual.")
    banco.sis_atualizar_conta(ator.id, {"senha_hash": seg.hash_senha(nova)})
    banco.sis_revogar_sessoes_da_conta(ator.id, seg.hash_token(token_atual) if token_atual else None)
    banco.tentativas_limpar(chave, "senha_atual")
    banco.auditar(ator.id, "senha.alterada", ator.id)
    return Res(True, "Senha alterada. Os outros aparelhos foram desconectados.")


# ------------------------------------------------------------------ perfil, privacidade (LGPD)
def atualizar_nome(ator: banco.Ator, nome: str) -> Res:
    ok, n, m = seg.validar_nome(nome)
    if not ok:
        return Res(False, m)
    banco.sis_atualizar_conta(ator.id, {"nome": n})
    banco.auditar(ator.id, "perfil.nome", ator.id)
    return Res(True, "Nome atualizado.", n)


def exportar_meus_dados(ator: banco.Ator) -> dict:
    """Tudo que o app guarda sobre a própria pessoa (direito de acesso e portabilidade). Sem hash de senha."""
    conta = banco.sis_conta_por_id(ator.id) or {}
    banco.auditar(ator.id, "dados.exportados", ator.id)
    return {"gerado_em": seg.iso(), "conta": conta, "dados_e_preferencias": banco.ler_dados(ator, ator.email),
            "atividades": banco.atividades_do_ator(ator, 200), "sessoes_ativas": len(banco.sessoes_do_ator(ator))}


def excluir_conta(ator: banco.Ator, senha: str = "", confirmacao: str = "") -> Res:
    """Apaga a conta e tudo que é dela. Contas com senha pedem a senha; contas só-Google pedem digitar EXCLUIR."""
    if (r := _pronto()):
        return r
    conta = banco.sis_conta_por_id(ator.id, com_senha=True)
    if not conta:
        return Res(False, "Conta não encontrada.")
    if conta.get("senha_hash"):
        chave = "a:" + ator.id
        if _excedeu(chave, "senha_atual", LIMITE_SENHA_ATUAL):
            return Res(False, MSG_BLOQUEIO)
        if not seg.verificar_senha(senha or "", conta["senha_hash"]):
            banco.tentativa_registrar(chave, "senha_atual")
            return Res(False, "A senha não confere.")
    elif (confirmacao or "").strip().upper() != "EXCLUIR":
        return Res(False, "Digite EXCLUIR para confirmar.")
    banco.auditar(ator.id, "conta.excluida", None)    # o registro fica sem dados pessoais (só o código interno)
    banco.sis_apagar_conta(conta["id"], conta["email"])
    return Res(True, "Conta e dados apagados. Sentiremos sua falta!")
