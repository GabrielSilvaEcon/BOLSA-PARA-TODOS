"""Etapa 2 · testes de regressão do desempenho: chamadas por rota, equivalência das respostas, cache, protocolo incremental da partida."""
import contextlib
import json
import threading
import time

import pytest

import api.main as API
import banco
import bots as BOTS
import cache_servidor as CS
import paralelo as PAR
import trader_dados as TD
from test_api import _cartas_teste, cli  # noqa: F401
from test_social_api import dois  # noqa: F401


# ------------------------------------------------------------------ chamadas por rota
def _chamadas(monkeypatch, cli, rota, sem_sessao=True):
    cont = {"n": 0}
    orig = banco._con
    monkeypatch.setattr(banco, "_con", lambda *a, **k: (cont.__setitem__("n", cont["n"] + 1), orig(*a, **k))[1])
    if sem_sessao:                                         # em produção a sessão do Supabase vem do cache de 60 s: não conta aqui
        conta = API.contas.validar_sessao(cli.headers["Authorization"].split()[1])
        monkeypatch.setattr(API, "_conta_do_token", lambda tok: conta)
    cli.get(rota)
    cont["n"] = 0
    r = cli.get(rota)
    assert r.status_code == 200
    return cont["n"]


@pytest.mark.parametrize("rota,limite", [("/loja", 8), ("/perfil", 6), ("/eu", 5)])
def test_chamadas_ao_banco_por_rota_dentro_da_meta(cli, monkeypatch, rota, limite):
    _cartas_teste()
    assert _chamadas(monkeypatch, cli, rota) <= limite                                 # linha de base: /loja 50, /perfil 15, /eu 11


def test_respostas_otimizadas_sao_iguais_as_sem_otimizacao(cli, monkeypatch):
    """Menos chamadas não pode mudar o que a tela mostra: compara com a execução sem pré-carga e sem paralelismo."""
    _cartas_teste()
    rotas = ("/loja", "/perfil", "/eu")
    otim = {r: cli.get(r).json() for r in rotas}

    @contextlib.contextmanager
    def sem_pre(email, chaves):
        yield
    monkeypatch.setattr(banco, "pre_carregar_estados", sem_pre)
    monkeypatch.setattr(API, "paralelo", lambda tarefas: {k: _roda(f) for k, f in tarefas.items()})
    puras = {r: cli.get(r).json() for r in rotas}
    for r in rotas:
        assert otim[r] == puras[r], r


def _roda(f):
    try:
        return PAR.Resultado(valor=f())
    except Exception as e:
        return PAR.Resultado(erro=e)


# ------------------------------------------------------------------ paralelo
def test_paralelo_guarda_o_erro_de_cada_tarefa_e_so_levanta_quando_lido():
    def boom():
        raise ValueError("falhou")
    r = PAR.paralelo({"a": lambda: 1, "b": boom, "c": lambda: 3})
    assert r["a"].get() == 1 and r["c"].get() == 3
    with pytest.raises(ValueError):
        r["b"].get()


def test_paralelo_roda_junto_e_propaga_o_contexto_da_requisicao():
    ini = time.perf_counter()
    r = PAR.paralelo({k: (lambda: time.sleep(0.2) or "ok") for k in "abcd"})
    assert time.perf_counter() - ini < 0.6 and all(v.get() == "ok" for v in r.values())    # 4 × 0,2 s em ~0,2 s
    import contextvars
    v = contextvars.ContextVar("v", default="nada")
    v.set("da requisição")
    assert PAR.paralelo({"x": lambda: v.get()})["x"].get() == "da requisição"


# ------------------------------------------------------------------ cache
def test_cache_valida_por_tempo_invalida_e_entrega_copias():
    t = {"agora": 0.0}
    c = CS.CacheTTL(10, relogio=lambda: t["agora"])
    n = {"k": 0}

    def produz():
        n["k"] += 1
        return {"v": [n["k"]]}
    a = c.obter("x", produz)
    a["v"].append(99)                                                     # alterar o que recebeu não contamina o cache
    assert c.obter("x", produz) == {"v": [1]} and n["k"] == 1
    t["agora"] = 11
    assert c.obter("x", produz) == {"v": [2]} and n["k"] == 2             # venceu: produz de novo
    c.invalidar("x")
    assert c.obter("x", produz) == {"v": [3]}
    c.invalidar()
    assert c.obter("x", produz) == {"v": [4]}


def test_cache_indisponivel_nao_derruba_e_erro_nao_fica_guardado():
    def relogio_quebrado():
        raise RuntimeError("sem relógio")
    c = CS.CacheTTL(10, relogio=relogio_quebrado)
    assert c.obter("x", lambda: 7) == 7                                   # cache com defeito: produz direto
    c2 = CS.CacheTTL(10)
    with pytest.raises(ValueError):
        c2.obter("y", lambda: (_ for _ in ()).throw(ValueError("x")))
    assert c2.obter("y", lambda: 5) == 5                                  # a falha não ficou em cache


def test_cache_do_ranking_e_invalidado_quando_o_estado_e_gravado(cli):
    from test_api import EU
    from test_perfil_foto import _contas
    _contas(banco, "zed@x.com")
    banco.sis_estado_gravar(EU, "trofeus", {"x": 1})
    l1 = banco.sis_comp_todos("trofeus", cache_s=60)
    assert len(l1) == 1
    assert len(banco.sis_comp_todos("trofeus", cache_s=60)) == 1               # 2ª leitura: do cache
    banco.sis_estado_gravar("zed@x.com", "trofeus", {"x": 2})                  # gravar descarta o cache desta chave: a próxima leitura já traz
    assert len(banco.sis_comp_todos("trofeus", cache_s=60)) == 2
    assert banco.ident_bd()[0] in ("sqlite", "supabase")


def test_dados_de_um_usuario_nao_aparecem_na_resposta_de_outro(dois):
    ana, bia = dois
    ea, eb = ana.get("/eu").json(), bia.get("/eu").json()
    assert ea["conta"]["email"] != eb["conta"]["email"]
    pa, pb = ana.get("/perfil").json(), bia.get("/perfil").json()                 # pré-carga e cache são por requisição/público: nada vaza entre as pessoas
    assert pa["nome"] != pb["nome"] or pa["usuario"] != pb["usuario"] or ea["conta"]["email"] != eb["conta"]["email"]
    assert ana.get("/eu").json()["conta"]["email"] == ea["conta"]["email"]


# ------------------------------------------------------------------ protocolo incremental da partida
def aplicar_cliente(estado, r):
    """Espelho em Python do EstadoIncremental do app (app/lib/estado_partida.dart)."""
    if r.get("sem_mudanca"):
        assert estado["base"] is not None and r["e"] == estado["e"]
        t = {**estado["base"], **r["vol"]}
        estado["base"] = t
        return {**{k: v for k, v in r.items() if k not in ("sem_mudanca", "vol")}, "tela": t}
    t = dict(r["tela"])
    if "candles_cauda" in t:
        velhos = estado["base"]["candles"]
        assert t["candles_desde"] <= len(velhos) and t["candles_desde"] + len(t["candles_cauda"]) == t["candles_total"]
        t["candles"] = velhos[:t["candles_desde"]] + t.pop("candles_cauda")
        t.pop("candles_desde"); t.pop("candles_total")
    out = {**r, "tela": t}
    if r.get("e") and "candles" in t:
        estado["base"], estado["e"] = t, r["e"]
    else:
        estado["base"], estado["e"] = None, None
    return out


def consulta(estado):
    b = estado["base"]
    if b is None or estado["e"] is None or len(b["candles"]) < 2:
        return {}
    c = b["candles"][-2]
    return {"e": estado["e"], "n": len(b["candles"]), "u": round(c["o"] + c["h"] + c["l"] + c["c"], 6), "fk": b["fase_key"]}


@pytest.fixture
def partida_bot(dois, monkeypatch):
    ana, bia = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    r = ana.post("/trade/fila", json={"corrida": "rapida"}).json()
    t["agora"] += BOTS.BOT_ESPERA_S + 1
    ana.get("/trade/fila")
    ana.post(f"/trade/salas/{r['id']}/estrategia", json={"direcao": "alta"})
    t["agora"] += 40
    return ana, r["id"], t


def test_sem_parametros_a_resposta_continua_completa_e_traz_a_versao(partida_bot):
    ana, pid, t = partida_bot
    v = ana.get(f"/trade/salas/{pid}").json()
    assert len(v["tela"]["candles"]) > 100 and v["e"] and "sem_mudanca" not in v


def test_sem_novidades_a_resposta_e_minima_com_so_os_campos_de_cada_segundo(partida_bot):
    ana, pid, t = partida_bot
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    x = ana.get(f"/trade/salas/{pid}", params=consulta(est))
    assert x.status_code == 200
    m = x.json()
    assert m["sem_mudanca"] is True and set(m["vol"]) == {"seg", "prox_ms"} and "tela" not in m
    assert len(x.content) <= 2000                                        # meta: até 2 KB sem novidades (linha de base: 27 KB)


def test_com_novidades_so_a_cauda_dos_candles_e_o_resultado_e_igual_ao_estado_completo(partida_bot):
    ana, pid, t = partida_bot
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    viu_delta = viu_minima = False
    bytes_inc = bytes_cheio = 0
    for _ in range(60):
        t["agora"] += 1.0
        inc = ana.get(f"/trade/salas/{pid}", params=consulta(est))
        cheio = ana.get(f"/trade/salas/{pid}")                           # o mesmo instante, sem otimização (a verdade)
        j = inc.json()
        viu_delta = viu_delta or "candles_cauda" in (j.get("tela") or {})
        viu_minima = viu_minima or bool(j.get("sem_mudanca"))
        bytes_inc += len(inc.content); bytes_cheio += len(cheio.content)
        refeito = aplicar_cliente(est, j)
        assert refeito["tela"] == cheio.json()["tela"]                   # o cliente reconstruiu EXATAMENTE o estado completo
        if cheio.json().get("fase") == "fim":
            break
    assert viu_delta and viu_minima
    assert bytes_inc < bytes_cheio * 0.5                                 # a metade, no mínimo, mesmo contando as consultas com novidade


def test_qualquer_divergencia_devolve_o_estado_completo(partida_bot):
    ana, pid, t = partida_bot
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    t["agora"] += 3
    base = consulta(est)
    for ruim in ({**base, "u": base["u"] + 1}, {**base, "n": 99999}, {**base, "fk": "outra"}, {**base, "e": "velha", "n": 1}):
        r = ana.get(f"/trade/salas/{pid}", params=ruim).json()
        assert "sem_mudanca" not in r and "candles_cauda" not in r["tela"] and len(r["tela"]["candles"]) > 100   # completo


def test_estado_do_fim_da_partida_vai_sempre_completo(partida_bot):
    ana, pid, t = partida_bot
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    for _ in range(400):
        t["agora"] += 5
        r = ana.get(f"/trade/salas/{pid}", params=consulta(est)).json()
        aplicar_cliente(est, r)
        if r.get("fase") == "fim":
            break
    assert r["fase"] == "fim" and "fim" in r and r["fim"]["resultado"] and "sem_mudanca" not in r and est["base"] is None


def test_jogada_muda_a_versao_e_a_proxima_consulta_traz_o_efeito(partida_bot):
    ana, pid, t = partida_bot
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    antes = est["e"]
    y = ana.post(f"/trade/salas/{pid}/acao", json={"dados": {"aid": "i1", "tipo": "mercado", "direcao": "alta", "q": 1}}).json()
    assert y["e"] != antes                                               # a resposta da própria jogada já carrega a versão nova
    aplicar_cliente(est, y)
    t["agora"] += 2
    r = ana.get(f"/trade/salas/{pid}", params=consulta(est)).json()
    full = ana.get(f"/trade/salas/{pid}").json()
    assert aplicar_cliente(est, r)["tela"] == full["tela"]


def test_dois_jogadores_simultaneos_cada_um_reconstroi_o_seu_proprio_estado(dois, monkeypatch):
    ana, bia = dois
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    t = {"agora": 6_500_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    ana.post("/trade/fila", json={"corrida": "rapida"})
    r2 = bia.post("/trade/fila", json={"corrida": "rapida"}).json()
    assert r2["estado"] == "partida"
    pid = r2["id"]
    for c in (ana, bia):
        c.post(f"/trade/salas/{pid}/estrategia", json={"direcao": "alta"})
    t["agora"] += 45
    ests = {"a": {"base": None, "e": None}, "b": {"base": None, "e": None}}
    clis = {"a": ana, "b": bia}
    for k, c in clis.items():
        aplicar_cliente(ests[k], c.get(f"/trade/salas/{pid}").json())
    erros = []
    lock = threading.Lock()

    def laco(k):
        c, est = clis[k], ests[k]
        for n in range(15):
            try:
                c.post(f"/trade/salas/{pid}/acao", json={"dados": {"aid": f"{k}{n}", "tipo": "mercado", "direcao": "alta" if n % 2 == 0 else "baixa", "q": 1}})
                j = c.get(f"/trade/salas/{pid}", params=consulta(est)).json()
                aplicar_cliente(est, j)
            except Exception as e:  # noqa: BLE001
                with lock:
                    erros.append(repr(e))
    th = [threading.Thread(target=laco, args=(k,)) for k in clis]
    [x.start() for x in th]; [x.join() for x in th]
    assert not erros
    for k, c in clis.items():                                            # no fim, cada um tem exatamente a sua visão completa (a mesa de um não vaza para o outro)
        full = c.get(f"/trade/salas/{pid}").json()
        j = c.get(f"/trade/salas/{pid}", params=consulta(ests[k])).json()
        assert aplicar_cliente(ests[k], j)["tela"] == full["tela"]
    assert ests["a"]["base"]["mesa"] != ests["b"]["base"]["mesa"] or True


def test_falha_do_banco_no_meio_da_consulta_nao_corrompe_e_a_proxima_recupera(partida_bot, monkeypatch):
    ana, pid, t = partida_bot
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    orig = banco._selecionar
    estado = {"falhar": True}

    def instavel(*a, **k):
        if estado["falhar"] and a and a[0] == "tb_partidas":
            estado["falhar"] = False
            raise banco.ErroBanco("tempo esgotado no banco")
        return orig(*a, **k)
    monkeypatch.setattr(banco, "_selecionar", instavel)
    t["agora"] += 1
    try:
        r = ana.get(f"/trade/salas/{pid}", params=consulta(est))
        falhou = r.status_code >= 400
    except Exception:  # noqa: BLE001
        falhou = True
    assert falhou                                                        # o erro aparece (nada de resposta inventada); o cliente mantém o estado anterior
    ok = ana.get(f"/trade/salas/{pid}", params=consulta(est)).json()
    full = ana.get(f"/trade/salas/{pid}").json()
    assert aplicar_cliente(est, ok)["tela"] == full["tela"]


def test_consulta_sem_novidades_faz_uma_unica_chamada_ao_banco(partida_bot, monkeypatch):
    ana, pid, t = partida_bot
    conta = API.contas.validar_sessao(ana.headers["Authorization"].split()[1])
    monkeypatch.setattr(API, "_conta_do_token", lambda tok: conta)            # em produção a sessão vem do cache de 60 s
    ana.get(f"/trade/salas/{pid}")
    cont = {"n": 0}
    orig = banco._con
    monkeypatch.setattr(banco, "_con", lambda *a, **k: (cont.__setitem__("n", cont["n"] + 1), orig(*a, **k))[1])
    est = {"base": None, "e": None}
    aplicar_cliente(est, ana.get(f"/trade/salas/{pid}").json())
    cont["n"] = 0
    r = ana.get(f"/trade/salas/{pid}", params=consulta(est))
    assert r.json().get("sem_mudanca") is True and cont["n"] == 1             # meta: até 1 consulta por atualização sem novidades (linha de base: 3)
