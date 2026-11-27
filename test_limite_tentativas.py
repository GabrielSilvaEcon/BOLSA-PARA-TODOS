"""Limite de tentativas por IP (login e buscas) e /saude/banco sem detalhes internos."""
from fastapi.testclient import TestClient

import api.main as M


def test_login_bloqueia_na_11a_tentativa_e_libera_depois_da_janela():
    M._TENTATIVAS.clear()
    for i in range(10):
        assert not M.excedeu_limite("/auth/entrar", "1.1.1.1", agora=100.0 + i)
    assert M.excedeu_limite("/auth/entrar", "1.1.1.1", agora=111.0)
    assert not M.excedeu_limite("/auth/entrar", "2.2.2.2", agora=111.0)       # outro IP não é afetado
    assert not M.excedeu_limite("/auth/entrar", "1.1.1.1", agora=200.0)       # a janela de 60 s passou


def test_rota_sem_limite_nunca_bloqueia():
    for _ in range(500):
        assert not M.excedeu_limite("/home", "3.3.3.3", agora=1.0)


def test_http_devolve_429_com_retry_after():
    M._TENTATIVAS.clear()
    c = TestClient(M.app)
    codigos = [c.post("/auth/entrar", json={"email": "a@b.c", "senha": "x"}, headers={"x-forwarded-for": "9.9.9.9"}).status_code for _ in range(12)]
    assert 429 in codigos and codigos.index(429) == 10
    assert c.post("/auth/entrar", json={"email": "a@b.c", "senha": "x"}, headers={"x-forwarded-for": "9.9.9.9"}).headers["retry-after"] == "60"
    M._TENTATIVAS.clear()


def test_saude_banco_nao_revela_detalhe():
    assert "detalhe" not in TestClient(M.app).get("/saude/banco").json()
