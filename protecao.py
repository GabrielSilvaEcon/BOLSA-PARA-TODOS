"""Camada central de proteção (Passo 22): um único ponto liga todas as defesas transversais do app.

`iniciar()` é chamado uma vez no começo do app.py e (a) mascara segredos em TODOS os logs, (b) liga a proteção de rede
(http_seguro) para todo pedido feito com `requests`, e (c) registra a configuração de domínios vinda dos secrets.
`diagnostico()` devolve a lista de verificações de configuração mostrada na aba Segurança do painel administrativo.
Não depende de nenhum módulo de ativo: vale igualmente para ações, FIIs, cripto, ETFs, fundos, renda fixa e o que vier.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import banco
import http_seguro
import seguranca as seg

_estado = {"ok": False}


class FiltroSegredos(logging.Filter):
    """Troca e-mails, senhas, tokens, chaves e hashes por marcadores antes de qualquer log ser escrito."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            limpa = seg.limpar_para_log(msg, 20000)
            if limpa != msg:
                record.msg, record.args = limpa, ()
        except Exception:
            pass
        return True


def _ligar_filtro_logs() -> None:
    alvo = [logging.getLogger()] + [logging.getLogger(n) for n in ("streamlit", "urllib3", "requests", "yfinance")]
    for lg in alvo:
        if not any(isinstance(f, FiltroSegredos) for f in lg.filters):
            lg.addFilter(FiltroSegredos())
        for h in lg.handlers:
            if not any(isinstance(f, FiltroSegredos) for f in h.filters):
                h.addFilter(FiltroSegredos())


def iniciar() -> dict:
    """Idempotente e à prova de erro: se algo falhar, o app continua (a proteção que falhar aparece no diagnóstico)."""
    if _estado["ok"]:
        return _estado
    cfg = banco.secrets_secao("seguranca")
    extras = list(cfg.get("dominios_extras") or [])
    sb = banco.secrets_secao("supabase").get("url")
    if sb:
        extras.append(urlparse(str(sb) if "//" in str(sb) else "https://" + str(sb)).hostname or "")
    try:
        http_seguro.configurar(modo=str(cfg.get("modo_dominios") or "avisar").lower(), extras=extras)
        _estado["rede"] = http_seguro.instalar()
    except Exception as e:
        _estado["rede"] = False
        banco.registrar_erro("protecao.rede", e)
    try:
        _ligar_filtro_logs()
        _estado["logs"] = True
    except Exception as e:
        _estado["logs"] = False
        banco.registrar_erro("protecao.logs", e)
    _estado["ok"] = True
    return _estado


# ------------------------------------------------------------------ diagnóstico de configuração
def _item(titulo: str, ok: bool | None, detalhe: str, grav: str = "medio") -> dict:
    return {"titulo": titulo, "ok": ok, "detalhe": detalhe, "gravidade": grav}


def diagnostico(raiz: str | None = None) -> list[dict]:
    """Verificações de configuração (não mostram valores de segredos, só se existem e se estão no formato esperado)."""
    import auditoria_codigo as ac
    out: list[dict] = []
    raiz = raiz or os.path.dirname(os.path.abspath(__file__))
    auth, sb = banco.secrets_secao("auth"), banco.secrets_secao("supabase")
    cs = str(auth.get("cookie_secret") or "")
    out.append(_item("Segredo do cookie de login", len(cs) >= 32, "definido e longo" if len(cs) >= 32 else "ausente ou curto (use 32+ caracteres aleatórios)", "alto"))
    ru = str(auth.get("redirect_uri") or "")
    out.append(_item("Endereço de retorno do login usa HTTPS", ru.startswith("https://") or not ru, "https" if ru.startswith("https://") else ("não configurado" if not ru else "use https://"), "alto"))
    tipo = banco.tipo_de_chave() if sb else None
    out.append(_item("Chave do Supabase é a de servidor (secreta)", (tipo == "secreta") if sb else None,
                     {"secreta": "chave secreta, nunca vai ao navegador", "publica": "chave pública: troque pela sb_secret_"}.get(tipo, "banco local ou tipo não reconhecido"), "alto"))
    out.append(_item("Banco de dados persistente (Supabase)", banco.backend() == "supabase",
                     banco.backend() + (": dados somem se o app for recriado" if banco.backend() != "supabase" else ""), "medio"))
    out.append(_item("Algoritmo de senha", seg.algoritmo_ativo() == "argon2id",
                     seg.algoritmo_ativo() + (" (instale argon2-cffi para usar Argon2id)" if seg.algoritmo_ativo() != "argon2id" else ""), "medio"))
    out.append(_item("Proteção de rede (SSRF, timeout, certificado)", bool(_estado.get("rede")),
                     "ligada" if _estado.get("rede") else "desligada", "alto"))
    out.append(_item("Modo de domínios permitidos", http_seguro.modo() == "bloquear",
                     f"modo '{http_seguro.modo()}'" + ("" if http_seguro.modo() == "bloquear" else ": domínios novos são só registrados. Veja a lista na aba Rede e, se estiver tudo certo, use modo_dominios = \"bloquear\" em [seguranca]."), "baixo"))
    out.append(_item("Máscara de segredos nos logs", bool(_estado.get("logs")), "ligada" if _estado.get("logs") else "desligada", "alto"))
    out.append(_item("Envio de e-mail configurado", bool(banco.secrets_secao("email")), "configurado" if banco.secrets_secao("email") else "não configurado: sem cadastro por e-mail", "baixo"))
    out.append(_item("Administradores definidos nos secrets", bool(banco.secrets_secao("admin").get("emails")), "definidos" if banco.secrets_secao("admin").get("emails") else "nenhum: o painel de administração fica oculto", "baixo"))
    out.append(_item("Chave de cifra dos backups", bool(banco.secrets_secao("backup").get("chave")), "definida" if banco.secrets_secao("backup").get("chave") else "não definida: gere uma em [backup] chave", "medio"))
    ign = os.path.join(raiz, ".gitignore")
    try:
        with open(ign, encoding="utf-8") as f:
            falhas = ac.checar_gitignore(f.read())
        out.append(_item(".gitignore protege segredos e bancos", not falhas, "completo" if not falhas else "; ".join(a.detalhe for a in falhas), "critico"))
    except OSError:
        out.append(_item(".gitignore protege segredos e bancos", None, "arquivo não encontrado neste ambiente", "medio"))
    sens = ac.arquivos_sensiveis_rastreados(raiz)
    out.append(_item("Nenhum arquivo secreto no repositório", not sens, "nenhum" if not sens else ", ".join(a.arquivo for a in sens[:5]), "critico"))
    return out
