"""Fechamento diário da competição. Roda FORA do Streamlit (GitHub Actions, depois do pregão), igual ao monitor.

Por que fora do Streamlit: precisa rodar todo dia útil mesmo com o app fechado e valorizar todas as carteiras de uma vez, com uma única
rodada de consultas de preço (e não uma por pessoa). Cada execução: trava o dia no banco (não roda duas vezes), baixa o fechamento do
universo líquido, aplica o pregão a cada carteira (proventos, desdobramentos, ordens a preço de fechamento, reinvestimento, valorização),
calcula o ranking e publica só apelido e retorno %. Etapa 2: monta também o ranking de cada liga de amigos e avisa quem mudou de posição
("você subiu para 3º"). Só funciona com o Supabase (com SQLite local não há banco compartilhado com o app).

Variáveis de ambiente: BPT_SUPABASE_URL e BPT_SUPABASE_KEY (as mesmas do monitor). Uso manual: `python competicao_job.py --forcar`.
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import yf_config  # noqa: F401
import banco
import canais
import ativos_jogo as A
import competicao as C
import competicao_ligas as L
import ranking_parcial as RP
import cotacoes_jogo as CJ
import wallet_game as WG
import notif as N
import seguranca as seg

BRT = timezone(timedelta(hours=-3))
HORA_MINIMA = 18               # só depois do fim do pregão (a B3 encerra por volta das 17h55)
MAX_PARTICIPANTES = 5000
TAXA_FALHA_MAX = 0.5           # se mais da metade das cotações falhar, a fonte caiu: não publica números errados


def agora_brt() -> datetime:
    return datetime.now(BRT).replace(tzinfo=None)


def coletor_yahoo(ticker: str) -> dict:
    """Último mês de fechamentos (sem ajuste por proventos), proventos e desdobramentos de um ticker da B3."""
    return CJ.coletor_yahoo_b3(ticker)


def baixar_universo(tickers: list[str], coletor, dormir=time.sleep, paralelo: int = 4) -> tuple[dict, list[str]]:
    """{ticker: dados} dos que deram certo e a lista dos que falharam (2 tentativas cada)."""
    def um(tk):
        for i in range(2):
            try:
                return tk, coletor(tk), None
            except Exception as e:
                erro = e.__class__.__name__
                dormir(1.0 if i == 0 else 0)
        return tk, None, erro
    ok, falhas = {}, []
    with ThreadPoolExecutor(max_workers=paralelo) as ex:
        for tk, d, erro in ex.map(um, tickers):
            if d and d.get("fech"):
                ok[tk] = d
            else:
                falhas.append(tk)
    return ok, falhas


def dados_do_dia(cotacoes: dict, dia: str) -> dict:
    """{ativo: {'c': preço, 'div': provento por cota, 'split': fator}} no pregão `dia`. Ações, FIIs e ETFs da B3 usam o fechamento exato do dia;
    cripto, fundos, Tesouro, CDI e ETFs dos EUA usam o último preço disponível até o dia (ver `cotacoes_jogo.valor_no_dia`)."""
    return {tk: {"c": CJ.valor_no_dia(tk, d["fech"], dia), "div": d["div"].get(dia, 0.0), "split": d["spl"].get(dia, 1.0)}
            for tk, d in cotacoes.items()}


def publicar_precos(cotacoes: dict, dia: str) -> dict:
    precos = {}
    for tk, d in cotacoes.items():
        c = CJ.valor_no_dia(tk, d["fech"], dia)
        if not c:
            continue
        ant = [v for k, v in sorted(d["fech"].items()) if k < dia]
        precos[tk] = {"c": round(c, 4), "v": round((c / ant[-1] - 1) * 100, 2) if ant else 0.0}
    return {"dia": dia, "gerado": seg.iso(), "precos": precos}


def avisar_posicoes(avisos: dict, agora_utc: datetime, entregar=canais.entregar, url_app: str = "", dormir=time.sleep) -> dict:
    """avisos: {email: [notificação]}. Grava no app (deduplicado) respeitando as preferências de notificação da pessoa e, se ela ligou
    e-mail/Telegram/push, entrega também por lá (as mesmas regras de horário e importância do monitor). Falha de uma conta não derruba as outras."""
    res = {"avisos": 0, "entregas": 0, "erros": 0}
    try:
        if not avisos or not banco.notif_disponivel():
            return res
    except Exception:
        return res
    for em, lista in avisos.items():
        try:
            prefs = N.normalizar_prefs((banco.sis_dados_de(em) or {}).get("notif_prefs"))
            destinos = {"email": em, "telegram": prefs["telegram_chat"], "ntfy": prefs["ntfy_topico"]}
            for n in lista:
                if not N.passa_prefs(n, prefs):
                    continue
                nid = banco.sis_notif_inserir(em, n)
                if not nid:
                    continue
                res["avisos"] += 1
                ent = entregar(n, prefs, destinos, agora_utc, 0, url_app, dormir)
                if ent:
                    res["entregas"] += sum(1 for v in ent.values() if v.get("ok"))
                    n["dados"]["entregas"] = ent
                    banco.sis_notif_atualizar_dados(nid, n["dados"])
        except Exception as e:
            res["erros"] += 1
            banco.registrar_erro("competicao_job.aviso", e)
    return res


def executar(agora: datetime | None = None, coletor=None, forcar: bool = False, dormir=time.sleep,
             entregar=canais.entregar, url_app: str = "", refazer: bool = False) -> dict:
    """refazer: repete o fechamento de hoje mesmo que já tenha rodado (libera a trava do dia e ignora o horário). É seguro: avisos e selos
    são deduplicados, então nada é enviado ou concedido duas vezes. Útil depois de publicar uma versão nova das regras."""
    agora = agora or agora_brt()
    forcar = forcar or refazer
    hoje = agora.date()
    if coletor is None:
        coletor = CJ.Coletor(hoje)
    if not forcar and (hoje.weekday() >= 5 or agora.hour < HORA_MINIMA):
        return {"status": "fora_do_horario"}
    slot = f"comp-{hoje.isoformat()}"
    if refazer:
        banco.sis_exec_liberar(slot)
    if not banco.sis_exec_iniciar(slot):
        return {"status": "ja_rodou"}
    try:
        ativos = {c["email"] for c in banco.sis_contas_monitoraveis(MAX_PARTICIPANTES)}      # contas suspensas saem da competição
        perfis = {r["email"]: C.sanear_perfil(r["dados"]) for r in banco.sis_comp_todos("comp_ordens", MAX_PARTICIPANTES)}
        perfis = {em: p for em, p in perfis.items() if em in ativos and p["aceite"] and p["apelido"]}
        carteiras = {r["email"]: r["dados"] for r in banco.sis_comp_todos("comp_cart", MAX_PARTICIPANTES)}
        base = C.universo_base()
        precisa = {tk for em in perfis for tk in list((carteiras.get(em) or {}).get("pos", {}))}
        precisa |= {o["t"] for p in perfis.values() for o in p["pend"]}
        extras = coletor.preparar(precisa) if hasattr(coletor, "preparar") else []      # Tesouro e fundos: arquivos baixados uma vez
        tickers = sorted(set(base) | set(extras) | precisa)
        cotacoes, falhas = baixar_universo(tickers, coletor, dormir)
        nucleo = [t for t in tickers if A.eh_b3(t)] or tickers                         # só a B3 decide se a fonte caiu; cripto ou fundo fora do ar não param o jogo
        falhas_nucleo = [t for t in falhas if t in set(nucleo)]
        if nucleo and len(falhas_nucleo) / len(nucleo) > TAXA_FALHA_MAX:
            banco.sis_exec_liberar(slot)                       # libera para a nova tentativa do agendador
            return {"status": "falhou", "motivo": f"{len(falhas_nucleo)} de {len(nucleo)} cotações falharam"}

        # os dias de fechamento são os pregões da B3: cripto (todo dia) e fundos (com atraso) não criam dias novos
        com_calendario = [c for tk, c in cotacoes.items() if A.eh_b3(tk)] or list(cotacoes.values())
        datas = sorted({d for c in com_calendario for d in c["fech"] if d <= hoje.isoformat()})
        if not datas:
            banco.sis_exec_liberar(slot)
            return {"status": "falhou", "motivo": "nenhuma data de pregão"}
        dia_alvo = datas[-1]
        if dia_alvo < hoje.isoformat() and not forcar:
            banco.sis_exec_finalizar(slot, "sem_pregao", {"ultimo": dia_alvo})                  # feriado: nada a fazer hoje
            return {"status": "sem_pregao", "ultimo_pregao": dia_alvo}

        dias_cache: dict[str, dict] = {}
        estados, processados = {}, 0
        try:                                                  # Wallet Game: bônus e recompensas em dinheiro virtual ainda não aplicados às carteiras
            creditos = WG.creditos_todos()
        except Exception as e:
            banco.registrar_erro("competicao_job.creditos", e)
            creditos = {}
        for em, p in perfis.items():
            est = carteiras.get(em) or C.novo_estado(p["entrada"] or dia_alvo)
            if est.get("v") != 1:
                est = C.novo_estado(p["entrada"] or dia_alvo)
            est, _ = C.aplicar_creditos(est, creditos.get(em, []))
            ini = est.get("inicio") or p["entrada"] or dia_alvo
            falta = [d for d in datas if d >= ini and (est.get("ult_dia") is None or d > est["ult_dia"])]
            for d in falta:
                dias_cache.setdefault(d, dados_do_dia(cotacoes, d))
                est = C.processar_dia(est, p["pend"], d, dias_cache[d], reinvestir=p["drip"])
            estados[em] = est
            processados += 1 if falta else 0

        # apelido repetido (cadastro simultâneo): fica o mais antigo; os demais saem do ranking até trocarem
        vistos, conflito = {}, set()
        for em in sorted(perfis, key=lambda e: (perfis[e]["entrada"], e)):
            k = perfis[em]["apelido_k"]
            if k in vistos:
                conflito.add(em)
            else:
                vistos[k] = em
        part = [{"apelido": perfis[em]["apelido"], "email": em, "estado": estados[em]} for em in perfis if em not in conflito]
        rk = C.montar_ranking(part, date.fromisoformat(dia_alvo))
        totais = {n: rk["listas"].get(n + "_n", 0) for n in ("geral", "mes", "semana")}
        dia_d = date.fromisoformat(dia_alvo)
        avisos: dict[str, list[dict]] = {}
        agora_utc = agora.replace(tzinfo=BRT).astimezone(timezone.utc)
        for em, est in estados.items():
            ant = est.get("rank") or {}
            est["rank"] = {**(rk["posicoes"].get(em) or {}), "n": totais, "conflito": em in conflito, "em": dia_alvo}
            banco.sis_estado_gravar(em, "comp_cart", est)
            try:
                lista = L.avisos_de_posicao(ant, est["rank"], dia_alvo, None, agora_utc)
                if lista and em not in conflito:
                    avisos[em] = lista
            except Exception as e:
                banco.registrar_erro("competicao_job.avisos", e)

        if banco.cfg_disponivel():
            banco.sis_comp_publicar("comp_ranking", {"gerado": seg.iso(), "dia": dia_alvo, "listas": rk["listas"]})
            banco.sis_comp_publicar("comp_precos", publicar_precos(cotacoes, dia_alvo))
        av = avisar_posicoes(avisos, agora_utc, entregar, url_app, dormir)
        resumo = {"dia": dia_alvo, "carteiras": len(estados), "atualizadas": processados, "cotacoes": len(cotacoes), "falhas": len(falhas),
                  "avisos": av["avisos"]}
        banco.sis_exec_finalizar(slot, "ok", resumo)
        return {"status": "ok", **resumo}
    except Exception as e:
        banco.registrar_erro("competicao_job", e)
        banco.sis_exec_liberar(slot)
        return {"status": "falhou", "motivo": e.__class__.__name__}


def executar_meio_dia(agora: datetime | None = None, coletor=coletor_yahoo, forcar: bool = False, dormir=time.sleep) -> dict:
    """Execução do meio-dia: ordens com f="M" do dia entram ao preço atual de cada ativo (cotação do Yahoo, com atraso de alguns minutos).
    Não fecha o dia nem mexe no ranking. Falha ou ordem sem preço: a ordem fica pendente e executa no fechamento."""
    agora = agora or agora_brt()
    hoje = agora.date()
    if not forcar and (hoje.weekday() >= 5 or not (C.HORA_MEIO_DIA <= agora.hour < C.HORA_CORTE)):
        return {"status": "fora_do_horario"}
    dia = hoje.isoformat()
    slot = f"comp-meio-{dia}"
    if not banco.sis_exec_iniciar(slot):
        return {"status": "ja_rodou"}
    try:
        ativos = {c["email"] for c in banco.sis_contas_monitoraveis(MAX_PARTICIPANTES)}
        perfis = {r["email"]: C.sanear_perfil(r["dados"]) for r in banco.sis_comp_todos("comp_ordens", MAX_PARTICIPANTES)}
        perfis = {em: p for em, p in perfis.items() if em in ativos and p["aceite"] and p["apelido"]}
        do_meio = lambda p: [o for o in p["pend"] if o.get("f") == "M" and o.get("x") == dia]
        perfis = {em: p for em, p in perfis.items() if do_meio(p)}
        if not perfis:
            banco.sis_exec_finalizar(slot, "sem_ordens", {})
            return {"status": "sem_ordens"}
        tickers = sorted({o["t"] for p in perfis.values() for o in do_meio(p)})
        cotacoes, falhas = baixar_universo(tickers, coletor, dormir)
        precos = {tk: d["fech"][dia] for tk, d in cotacoes.items() if d["fech"].get(dia)}
        if not precos:
            banco.sis_exec_liberar(slot)
            return {"status": "falhou", "motivo": "nenhum preço de hoje"}
        carteiras = {r["email"]: r["dados"] for r in banco.sis_comp_todos("comp_cart", MAX_PARTICIPANTES)}
        feitas = 0
        for em, p in perfis.items():
            est = carteiras.get(em)
            if not est or est.get("v") != 1:
                continue                                       # carteira ainda sem fechamento: executa no fechamento
            novo = C.processar_meio_dia(est, p["pend"], dia, precos)
            if novo != est:
                banco.sis_estado_gravar(em, "comp_cart", novo)
                feitas += 1
        banco.sis_exec_finalizar(slot, "ok", {"carteiras": feitas, "precos": len(precos), "sem_preco": len(falhas)})
        return {"status": "ok", "carteiras": feitas, "sem_preco": len(falhas)}
    except Exception:
        banco.sis_exec_liberar(slot)
        raise


def executar_parcial(agora: datetime | None = None, coletor=coletor_yahoo, forcar: bool = False, dormir=time.sleep) -> dict:
    """Ranking parcial (10h30 e 14h30): recalcula a classificação com os preços do momento e grava no campo "parcial" do documento público.
    Só para acompanhar: não altera carteiras, selos nem prêmios (isso é só do fechamento, ~18h30). Falha: o ranking oficial segue como está."""
    agora = agora or agora_brt()
    hoje = agora.date()
    if not forcar and (hoje.weekday() >= 5 or not (10 <= agora.hour < HORA_MINIMA)):
        return {"status": "fora_do_horario"}
    dia = hoje.isoformat()
    slot = f"comp-parcial-{dia}-{'a' if agora.hour < 14 else 'b'}"
    if not banco.sis_exec_iniciar(slot):
        return {"status": "ja_rodou"}
    try:
        ativos = {c["email"] for c in banco.sis_contas_monitoraveis(MAX_PARTICIPANTES)}
        perfis = {r["email"]: C.sanear_perfil(r["dados"]) for r in banco.sis_comp_todos("comp_ordens", MAX_PARTICIPANTES)}
        perfis = {em: p for em, p in perfis.items() if em in ativos and p["aceite"] and p["apelido"]}
        carteiras = {r["email"]: r["dados"] for r in banco.sis_comp_todos("comp_cart", MAX_PARTICIPANTES)}
        vistos, conflito = {}, set()
        for em in sorted(perfis, key=lambda e: (perfis[e]["entrada"], e)):
            if perfis[em]["apelido_k"] in vistos:
                conflito.add(em)
            else:
                vistos[perfis[em]["apelido_k"]] = em
        part = [{"apelido": perfis[em]["apelido"], "email": em, "estado": carteiras[em]}
                for em in perfis if em not in conflito and isinstance(carteiras.get(em), dict)]
        tickers = sorted({tk for p in part for tk in (p["estado"].get("pos") or {})})
        cotacoes, falhas = baixar_universo(tickers, coletor, dormir) if tickers else ({}, [])
        if tickers and len(falhas) / len(tickers) > TAXA_FALHA_MAX:
            banco.sis_exec_liberar(slot)
            return {"status": "falhou", "motivo": f"{len(falhas)} de {len(tickers)} cotações falharam"}
        precos = {tk: d["fech"][dia] for tk, d in cotacoes.items() if d["fech"].get(dia)}      # sem preço de hoje: usa o último conhecido
        listas = RP.montar(part, precos, hoje)
        if not listas:
            banco.sis_exec_finalizar(slot, "sem_participantes", {})
            return {"status": "sem_participantes"}
        atual = banco.cfg_ler("comp_ranking") or {}
        banco.sis_comp_publicar("comp_ranking", {**atual, "parcial": {"gerado": seg.iso(), "dia": dia, "hora": RP.hora_br(agora), "listas": listas}})
        banco.sis_exec_finalizar(slot, "ok", {"participantes": listas.get("geral_n", 0), "precos": len(precos)})
        return {"status": "ok", "participantes": listas.get("geral_n", 0), "sem_preco": len(falhas)}
    except Exception as e:
        banco.registrar_erro("competicao_job.parcial", e)
        banco.sis_exec_liberar(slot)
        return {"status": "falhou", "motivo": e.__class__.__name__}


def main() -> int:
    try:
        __import__("protecao").iniciar()
    except Exception as e:
        print("aviso: proteção de rede não iniciada:", e.__class__.__name__)
    try:
        url = __import__("email_envio").url_base()
    except Exception:
        url = ""
    if "--parcial" in sys.argv:
        r = executar_parcial(forcar="--forcar" in sys.argv)
        print(r)
        return 1 if r["status"] == "falhou" else 0
    if "--meio-dia" in sys.argv:
        r = executar_meio_dia(forcar="--forcar" in sys.argv)
        print(r)
        return 1 if r["status"] == "falhou" else 0
    r = executar(forcar="--forcar" in sys.argv, url_app=url, refazer="--refazer" in sys.argv)
    print(r)
    return 1 if r["status"] == "falhou" else 0


if __name__ == "__main__":
    sys.exit(main())
