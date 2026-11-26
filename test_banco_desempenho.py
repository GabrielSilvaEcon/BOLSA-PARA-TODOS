"""Etapa 2 · conexões HTTP reaproveitadas, operador 'in', pré-carga de estados por requisição."""
import threading

import pytest
import requests

import banco
from test_trader_mesa import _contas, banco_isolado


@pytest.fixture
def bd():
    with banco_isolado():
        _contas()
        yield


class Resp:
    def __init__(self, code=200, corpo=None):
        self.status_code, self._c, self.text = code, corpo if corpo is not None else [], ""

    def json(self):
        return self._c


class SessaoFalsa:
    contagem = 0

    def __init__(self, roteiro=None):
        SessaoFalsa.contagem += 1
        self.id = SessaoFalsa.contagem
        self.roteiro = list(roteiro or [])
        self.chamadas = []
        self.fechada = False

    def request(self, metodo, url, **kw):
        self.chamadas.append((metodo, url, kw))
        x = self.roteiro.pop(0) if self.roteiro else Resp()
        if isinstance(x, Exception):
            raise x
        return x

    def close(self):
        self.fechada = True


@pytest.fixture
def rest(monkeypatch):
    banco._SESSOES.__dict__.clear()
    SessaoFalsa.contagem = 0
    fabrica = {"roteiros": []}
    criadas = []

    def nova():
        s = SessaoFalsa(fabrica["roteiros"].pop(0) if fabrica["roteiros"] else None)
        criadas.append(s)
        return s
    monkeypatch.setattr(banco, "_nova_sessao", nova)
    monkeypatch.setattr(banco, "_supabase", lambda: ("https://x.supabase.co", "chave"))
    yield fabrica, criadas
    banco._SESSOES.__dict__.clear()


def test_a_mesma_thread_reaproveita_uma_sessao_e_cada_thread_tem_a_sua(rest):
    _, criadas = rest
    for _ in range(5):
        banco._rest("GET", "contas", params=[("select", "email")])
    assert len(criadas) == 1 and len(criadas[0].chamadas) == 5                       # 5 consultas, 1 sessão (conexões reaproveitadas)
    ids = []
    t = threading.Thread(target=lambda: (banco._rest("GET", "contas"), ids.append(len(criadas))))
    t.start(); t.join()
    assert len(criadas) == 2                                                          # outra thread, outra sessão (sem compartilhar Session entre threads)


def test_headers_e_timeout_continuam_os_de_antes(rest):
    _, criadas = rest
    banco._rest("GET", "contas")
    metodo, url, kw = criadas[0].chamadas[0]
    assert url == "https://x.supabase.co/rest/v1/contas" and kw["headers"]["apikey"] == "chave" and kw["timeout"] == banco.TIMEOUT_REST == (5, 10)


def test_leitura_com_conexao_derrubada_refaz_uma_vez_com_sessao_nova(rest):
    fabrica, criadas = rest
    fabrica["roteiros"] = [[requests.exceptions.ConnectionError("derrubada")], []]
    r = banco._rest("GET", "contas")
    assert r.status_code == 200 and len(criadas) == 2 and criadas[0].fechada            # a velha foi descartada


def test_escrita_nunca_e_repetida_e_o_erro_sobe(rest):
    fabrica, criadas = rest
    fabrica["roteiros"] = [[requests.exceptions.ConnectionError("derrubada")]]
    with pytest.raises(banco.ErroBanco):
        banco._rest("POST", "contas", corpo={"a": 1})
    assert len(criadas[0].chamadas) == 1                                              # uma tentativa só: nada de gravar duas vezes


def test_timeout_vira_erro_do_banco_sem_repetir(rest):
    fabrica, criadas = rest
    fabrica["roteiros"] = [[requests.exceptions.ReadTimeout("lento")]]
    with pytest.raises(banco.ErroBanco, match="tempo esgotado"):
        banco._rest("GET", "contas")
    assert len(criadas[0].chamadas) == 1


def test_leitura_que_falha_duas_vezes_vira_erro(rest):
    fabrica, _ = rest
    fabrica["roteiros"] = [[requests.exceptions.ConnectionError("a")], [requests.exceptions.ConnectionError("b")]]
    with pytest.raises(banco.ErroBanco, match="conexão"):
        banco._rest("GET", "contas")


def test_adaptador_so_repete_falha_de_conexao_nunca_leitura_ou_escrita():
    sessao = banco._nova_sessao()
    ad = sessao.get_adapter("https://x.supabase.co")
    assert ad.max_retries.connect == 2 and ad.max_retries.read == 0 and ad.max_retries.status == 0 and ad.max_retries.other == 0
    sessao.close()


def test_operador_in_no_rest_escapa_aspas_e_virgulas():
    p = banco._params("monitor_estado", {"id": ("in", ['a@x.com|perfil', 'b"@x,c|y'])})
    assert p == [("id", 'in.("a@x.com|perfil","b\\"@x,c|y")')]


def test_operador_in_no_sqlite_e_pre_carga_em_uma_so_consulta(bd, monkeypatch):
    banco.sis_estado_gravar("a@x.com", "k1", {"v": 1})
    banco.sis_estado_gravar("a@x.com", "k2", {"v": 2})
    banco.sis_estado_gravar("b@x.com", "k1", {"v": 99})
    chamadas = {"n": 0}
    orig = banco._con
    monkeypatch.setattr(banco, "_con", lambda *a, **k: (chamadas.__setitem__("n", chamadas["n"] + 1), orig(*a, **k))[1])
    with banco.pre_carregar_estados("a@x.com", ["k1", "k2", "k3"]):
        assert chamadas["n"] == 1                                                    # uma consulta para as três chaves
        assert banco.sis_estado_ler("a@x.com", "k1") == {"v": 1} and banco.sis_estado_ler("a@x.com", "k2") == {"v": 2}
        assert banco.sis_estado_ler("a@x.com", "k3") == {}                         # não existe: vazio, sem ir ao banco
        assert chamadas["n"] == 1
        d = banco.sis_estado_ler("a@x.com", "k1"); d["v"] = 555                    # alterar a cópia não contamina as próximas leituras
        assert banco.sis_estado_ler("a@x.com", "k1") == {"v": 1}
        assert banco.sis_estado_ler("b@x.com", "k1") == {"v": 99}                  # outra pessoa: leitura normal (isolamento)
        assert chamadas["n"] == 2
    chamadas["n"] = 0
    assert banco.sis_estado_ler("a@x.com", "k1") == {"v": 1} and chamadas["n"] == 1   # fora do bloco: leitura normal


def test_gravar_dentro_do_bloco_descarta_o_valor_pre_carregado(bd):
    banco.sis_estado_gravar("a@x.com", "k1", {"v": 1})
    with banco.pre_carregar_estados("a@x.com", ["k1"]):
        assert banco.sis_estado_ler("a@x.com", "k1") == {"v": 1}
        banco.sis_estado_gravar("a@x.com", "k1", {"v": 2})
        assert banco.sis_estado_ler("a@x.com", "k1") == {"v": 2}                  # nunca devolve o velho


def test_falha_na_pre_carga_cai_para_a_leitura_normal(bd, monkeypatch):
    banco.sis_estado_gravar("a@x.com", "k1", {"v": 1})
    orig = banco._selecionar
    estado = {"primeira": True}

    def falha_na_primeira(*a, **k):
        if estado["primeira"]:
            estado["primeira"] = False
            raise banco.ErroBanco("fora do ar")
        return orig(*a, **k)
    monkeypatch.setattr(banco, "_selecionar", falha_na_primeira)
    with banco.pre_carregar_estados("a@x.com", ["k1"]):
        assert banco.sis_estado_ler("a@x.com", "k1") == {"v": 1}
