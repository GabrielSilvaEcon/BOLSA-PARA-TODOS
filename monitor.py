"""Passo 23 — Monitor automático. Roda FORA do Streamlit (GitHub Actions, gratuito) e não depende de ninguém estar com o app aberto.

Por que fora do Streamlit: o Streamlit Cloud só executa código quando alguém abre a página, e hiberna apps parados. Qualquer "tarefa em
segundo plano" dentro dele morreria junto. Por isso o agendador é externo: .github/workflows/monitor.yml chama `python monitor.py`
(a cada 15 minutos em dias úteis; o GitHub pode atrasar alguns minutos e não garante o horário exato).

Cada execução: trava a janela de tempo no banco (impede execução duplicada), percorre as contas ativas, lê as regras de cada uma,
busca cotações com cache e limite por execução, avalia (motores já existentes + regras novas), deduplica, grava as notificações e
entrega pelos canais escolhidos, com retentativas. Tudo fica registrado em `monitor_exec`. Só funciona com o Supabase: com SQLite local
não haveria banco compartilhado entre o app e o monitor.

Variáveis de ambiente (GitHub > Settings > Secrets and variables > Actions): BPT_SUPABASE_URL, BPT_SUPABASE_KEY (chave SECRETA),
BPT_EMAIL_SERVIDOR/PORTA/USUARIO/SENHA/REMETENTE (opcional), BPT_TELEGRAM_BOT_TOKEN (opcional), BPT_APP_URL (opcional).
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta

import banco
import canais
import notif as N
import seguranca as seg

JANELA_MIN = 15               # uma execução por janela de 15 minutos (trava no banco)
MAX_ATIVOS_EXECUCAO = 80      # consultas distintas por execução: protege os limites das fontes gratuitas
MAX_ATIVOS_CONTA = 25
MAX_CONTAS = 500
FALHAS_PARA_PARAR = 4         # fonte caiu: após 4 falhas seguidas a execução para de insistir nela


# ------------------------------------------------------------------ coleta de dados (única parte que usa a rede de mercado)
def _fund_de(info: dict) -> dict:
    def n(k):
        v = info.get(k)
        return float(v) if isinstance(v, (int, float)) and v == v else None
    pr, lpa, vpa = n("preco"), n("lpa"), n("vpa")
    d12 = info.get("div_12m")
    d12 = float(d12) if isinstance(d12, (int, float)) and d12 == d12 else None
    return {k: v for k, v in {"pl": pr / lpa if pr and lpa and lpa > 0 else None, "pvp": pr / vpa if pr and vpa and vpa > 0 else None,
                              "dy": d12 / pr * 100 if pr and d12 else None, "roe": n("roe"), "margem_liq": n("margem_liq"),
                              "div_pl": n("div_pl"), "ev_ebitda": n("ev_ebitda")}.items() if v is not None}


def _df_para_dados(df, classe: str, ind: dict | None = None) -> dict | None:
    if df is None or len(df) == 0:
        return None
    fech = [float(x) for x in df["Close"].tolist() if x == x]
    if len(fech) < 2:
        return None
    return {"classe": classe, "preco": fech[-1], "fech": fech, "df": df, "ind": ind or {}}


def coletor_padrao(ativo: str, classe: str, com_fund: bool = False) -> dict | None:
    """Histórico diário (~1 ano) e, se pedido, indicadores. Cripto: Binance (endereço de dados públicos, sem chave). Demais: Yahoo, com Brapi de reserva."""
    import pandas as pd
    if classe == "cripto":
        import requests
        r = requests.get("https://data-api.binance.vision/api/v3/klines", params={"symbol": f"{ativo}USDT", "interval": "1d", "limit": 300}, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        linhas = r.json()
        df = pd.DataFrame([{"Open": float(x[1]), "High": float(x[2]), "Low": float(x[3]), "Close": float(x[4]), "Volume": float(x[5])} for x in linhas],
                          index=pd.to_datetime([x[0] for x in linhas], unit="ms"))
        return _df_para_dados(df, classe)
    import dados
    df, err = dados.historico_yahoo(ativo, "1y", "1d")
    if df is None or df.empty:
        df, err2 = dados.historico_brapi(ativo, "1y", "1d")
        if df is None or df.empty:
            raise RuntimeError("sem dados nas fontes")
    ind = {}
    if com_fund:
        try:
            ind = _fund_de(dados.buscar_yahoo(ativo))
        except Exception:
            ind = {}
    return _df_para_dados(df, classe, ind)


# ------------------------------------------------------------------ classe do ativo e regras de cada conta
def classe_do_ticker(tk: str) -> str:
    tk = str(tk).upper()
    try:
        import recursos as rec
        i = rec.info(tk) or {}
        setor = str(i.get("setor") or "").lower()
        if "imobili" in setor or "fii" in setor:
            return "fii"
        if "etf" in setor:
            return "etf"
        if "eua" in setor:
            return "acao"
    except Exception:
        pass
    return "fii" if tk.endswith("11") and len(tk) == 6 else "acao"


def _lotes(dados: dict) -> list[dict]:
    """Posições da carteira real: soma as compras por ativo."""
    soma: dict = {}
    for l in dados.get("cart_real") or []:
        try:
            tk, q = str(l["ticker"]).upper(), float(l["qtd"])
        except (KeyError, TypeError, ValueError):
            continue
        if q > 0:
            soma[tk] = soma.get(tk, 0.0) + q
    return [{"ativo": tk, "qtd": q, "classe": classe_do_ticker(tk)} for tk, q in soma.items()]


def _necessidades(dados: dict, lotes: list[dict]) -> dict:
    """{(ativo, classe): precisa_de_fundamentos} que esta conta exige."""
    precisa: dict = {}
    cl_lote = {l["ativo"]: l["classe"] for l in lotes}
    for r in dados.get("mon_regras") or []:
        if r.get("ativa", True) and r.get("origem", "monitor") == "monitor" and r.get("ativo") and r.get("classe") in N.CLASSES:
            k = (r["ativo"], r["classe"])
            precisa[k] = precisa.get(k, False) or r["tipo"] == "fund_mudanca"
    for chave in ("tec_av_regras", "intel_regras"):
        for r in dados.get(chave) or []:
            a = str(r.get("ativo") or "*").upper()
            if r.get("ativa", True) and a != "*" and a not in ("CARTEIRA",):
                precisa.setdefault((a, cl_lote.get(a) or classe_do_ticker(a)), False)
    if any(r.get("ativa", True) and r.get("tipo") in ("variacao_preco", "nivel_preco", "volatilidade", "liquidez") and str(r.get("ativo")) == "*"
           for r in dados.get("intel_regras") or []) or dados.get("risco_limites") is not None or lotes:
        for l in lotes:
            precisa.setdefault((l["ativo"], l["classe"]), False)
    return precisa


def _estado_intel(dd: dict, met: dict | None) -> dict:
    est: dict = {}
    for a, d in dd.items():
        f = d.get("fech") or []
        if len(f) < 2:
            continue
        e = {"preco": d["preco"], "var_1d": (f[-1] / f[-2] - 1) * 100 if f[-2] else None, "var_5d": (f[-1] / f[-6] - 1) * 100 if len(f) > 6 and f[-6] else None}
        df = d.get("df")
        try:
            if df is not None and len(df) >= 60:
                import numpy as np
                r = np.log(df["Close"]).diff().dropna()
                if r.iloc[-120:].std() > 0:
                    e["vol_razao"] = float(r.iloc[-20:].std() / r.iloc[-120:].std())
                vm = df["Volume"].iloc[-61:-1].median()
                if vm and vm > 0:
                    e["volume_x"] = float(df["Volume"].iloc[-1] / vm)
        except Exception:
            pass
        est[a] = e
    if met:
        est["_carteira"] = {"maior_peso": met["maior_peso"], "pesos_classe": met["pesos_classe"]}
    return est


def avaliar_conta(dados: dict, dd: dict, estado: dict, agora: datetime) -> tuple[list[dict], dict]:
    """Roda todos os motores sobre os dados já coletados. Devolve (notificações ainda sem filtro de preferências, novo estado)."""
    import analise_tecnica as AT
    import intel as I
    notifs: list[dict] = []
    lotes = _lotes(dados)
    cl = {l["ativo"]: l["classe"] for l in lotes}
    novo = {"hit": {}, "carteira": {}}

    # 1) regras do monitor (preço, percentuais, extremos, variação incomum, fundamentos)
    disp, est = N.avaliar_monitor(dados.get("mon_regras") or [], dd, {"hit": (estado.get("hit") or {}), "ind": (estado.get("ind") or {})}, agora)
    novo["hit"], novo["ind"] = est["hit"], est["ind"]
    notifs += [N.de_disparo(d, "monitor", agora, (dd.get(d["ativo"]) or {}).get("classe")) for d in disp]

    # 2) carteira: limites do usuário (os mesmos de Gestão de risco) e alocação-alvo
    met = N.metricas_carteira(lotes, dd)
    prefs = N.normalizar_prefs(dados.get("notif_prefs"))
    disp_c, est_c = N.avaliar_carteira(dados.get("risco_limites"), met, estado.get("carteira") or {}, prefs.get("alvo_classes") or None, agora)
    novo["carteira"] = est_c
    notifs += [N.de_disparo(d, "carteira", agora) for d in disp_c]

    # 3) regras já existentes da Central de inteligência (preço, volatilidade, liquidez, carteira)
    ri = [r for r in (dados.get("intel_regras") or []) if r.get("tipo") in ("variacao_preco", "nivel_preco", "volatilidade", "liquidez", "carteira")]
    if ri:
        for d in I.avaliar_alertas(ri, _estado_intel(dd, met), agora):
            notifs.append(N.de_disparo(d, "intel", agora, (dd.get(d["ativo"]) or {}).get("classe")))

    # 4) regras técnicas já existentes (Análise técnica avançada)
    rt = [r for r in (dados.get("tec_av_regras") or []) if r.get("ativa", True)]
    if rt:
        series = {a: {"df": d["df"], "classe": d["classe"]} for a, d in dd.items() if d.get("df") is not None}
        disp_t, _av = AT.avaliar_alertas_tec(rt, series, agora)
        notifs += [N.de_disparo(d, "tecnica", agora, (dd.get(d["ativo"]) or {}).get("classe")) for d in disp_t]
    return notifs, novo


# ------------------------------------------------------------------ execução
def _janela(agora: datetime) -> str:
    base = agora.replace(minute=agora.minute - agora.minute % JANELA_MIN, second=0, microsecond=0)
    return "mon-" + base.strftime("%Y%m%dT%H%M")


def avisar_cotas(agora) -> int:
    """Etapa 6: avisa os administradores (Central de notificações) quando uma fonte passa de 80% e de 100% do limite. Uma vez por nível/dia."""
    import consumo
    import custos
    avisos = consumo.avisos_de_cota()
    calc = custos.calcular(consumo.usos_do_mes(), agora.date())
    extras = custos.alertas(calc)
    if not avisos and not extras:
        return 0
    admins = [c["email"] for c in banco.sis_contas_monitoraveis(500) if c.get("papel") == "admin"]
    n = 0
    for x in extras:
        for email in admins:
            ok = banco.sis_notif_inserir(email, {"dedup": f"custo|{x['nivel']}|{agora:%Y-%m}", "categoria": "sistema",
                                                 "importancia": "alta" if x["nivel"] == "erro" else "media", "titulo": x["titulo"][:200],
                                                 "texto": x["texto"], "origem": "custos", "pagina": "administracao"})
            n += 1 if ok else 0
    for a in avisos:
        grave = a["nivel"] >= 100
        for email in admins:
            ok = banco.sis_notif_inserir(email, {
                "dedup": f"cota|{a['id']}|{a['nivel']}|{agora:%Y-%m-%d}", "categoria": "sistema", "importancia": "alta" if grave else "media",
                "titulo": f"{a['nome']}: {a['pct']}% do limite gratuito usado"[:200],
                "texto": ("O limite foi atingido: as consultas a esta fonte estão barradas até renovar. " if grave else
                          "O aquecimento do cache pausa a partir da reserva configurada. ") + "Veja Administração > Consumo.",
                "origem": "consumo", "pagina": "administracao"})
            n += 1 if ok else 0
    return n


class _SemAquecer(Exception):
    pass


def executar(agora: datetime | None = None, coletor=None, entregar=canais.entregar, dormir=time.sleep, url_app: str = "",
             aquecer: bool | None = None) -> dict:
    agora = agora or seg.agora()
    aquecer = (coletor is None) if aquecer is None else aquecer      # aquecimento só com o coletor real (nos testes, só se pedido)
    coletor = coletor or coletor_padrao
    t0 = time.monotonic()
    ok, motivo = banco.pronto(True)
    if not ok:
        return {"status": "falhou", "motivo": motivo}
    if banco.backend() != "supabase" and not banco._forcar_sqlite:
        return {"status": "falhou", "motivo": "O monitor automático exige o Supabase (banco compartilhado com o app)."}
    slot = _janela(agora)
    if not banco.sis_exec_iniciar(slot):
        return {"status": "ignorada", "motivo": "Esta janela de tempo já foi (ou está sendo) executada."}
    res = {"janela": slot, "contas": 0, "avaliadas": 0, "ativos_lidos": 0, "notificacoes": 0, "entregas_ok": 0, "entregas_falha": 0,
           "suprimidas": 0, "agrupadas": 0, "adiadas": 0, "erros": [], "fontes_com_erro": []}
    cache: dict = {}
    falhas_seguidas = 0

    def obter(ativo, classe, fund):
        nonlocal falhas_seguidas
        k = (ativo, classe)
        if k in cache and (cache[k] is None or not fund or cache[k].get("ind")):
            return cache[k]
        if len([c for c in cache if cache[c] is not None]) + 0 >= MAX_ATIVOS_EXECUCAO or falhas_seguidas >= FALHAS_PARA_PARAR:
            res["adiadas"] += 1
            return None
        for tent in (1, 2):
            try:
                d = coletor(ativo, classe, fund) if fund else coletor(ativo, classe)
                cache[k] = d
                falhas_seguidas = 0
                if d:
                    res["ativos_lidos"] += 1
                return d
            except Exception as e:
                if tent == 1:
                    dormir(2)
                    continue
                falhas_seguidas += 1
                res["fontes_com_erro"].append(f"{ativo}: {e.__class__.__name__}")
                cache[k] = None
                return None

    try:
        contas = banco.sis_contas_monitoraveis(MAX_CONTAS)
        for c in contas:
            res["contas"] += 1
            try:
                dados = banco.sis_dados_de(c["email"])
                prefs = N.normalizar_prefs(dados.get("notif_prefs"))
                if not prefs["ativo"]:
                    continue
                estado = banco.sis_estado_ler(c["email"], "mon")
                ult = seg.de_iso(estado.get("ultima_execucao"))
                try:                                            # Etapa 5: o plano define o intervalo mínimo entre verificações
                    import planos
                    freq = max(prefs["verificar_a_cada_min"], planos.intervalo_minimo(c["email"], c.get("papel")))
                except Exception:
                    freq = prefs["verificar_a_cada_min"]
                if ult and agora - ult < timedelta(minutes=max(1, freq - 2)):
                    continue                                    # ainda não é hora desta conta (frequência escolhida)
                lotes = _lotes(dados)
                precisa = _necessidades(dados, lotes)
                if not precisa:
                    continue
                dd = {}
                for (a, cl), fund in list(precisa.items())[:MAX_ATIVOS_CONTA]:
                    d = obter(a, cl, fund)
                    if d:
                        dd[a] = d
                if not dd:
                    continue
                notifs, novo = avaliar_conta(dados, dd, estado, agora)
                res["avaliadas"] += 1
                peso = (N.metricas_carteira(lotes, dd) or {}).get("pesos", {})
                notifs = [n for n in notifs if N.passa_prefs(n, prefs)]
                for n in notifs:
                    n["importancia"], mot = N.pontuar(n, peso)
                    if mot:
                        n["dados"]["prioridade_motivo"] = mot
                recentes = banco.sis_notif_recentes(c["email"], seg.somar(-7 * 86400, agora))
                notifs, sup = N.suprimir(notifs, recentes, prefs, agora)
                res["suprimidas"] += sup
                if prefs["agrupar"]:
                    notifs, jun = N.agrupar(notifs)
                    res["agrupadas"] += jun
                hoje = [r for r in recentes if (seg.de_iso(r["quando"]) or agora) > agora - timedelta(hours=24)
                        and any(v.get("ok") for v in ((r.get("dados") or {}).get("entregas") or {}).values())]
                enviadas = len(hoje)
                destinos = {"email": c["email"], "telegram": prefs["telegram_chat"], "ntfy": prefs["ntfy_topico"]}
                for n in notifs:
                    n["dados"]["monitor"] = True
                    nid = banco.sis_notif_inserir(c["email"], n)
                    if not nid:
                        continue
                    res["notificacoes"] += 1
                    ent = entregar(n, prefs, destinos, agora, enviadas, url_app, dormir)
                    if ent:
                        enviadas += 1
                        res["entregas_ok"] += sum(1 for v in ent.values() if v["ok"])
                        res["entregas_falha"] += sum(1 for v in ent.values() if not v["ok"])
                        n["dados"]["entregas"] = ent
                        banco.sis_notif_atualizar_dados(nid, n["dados"])
                novo["ultima_execucao"] = seg.iso(agora)
                banco.sis_estado_gravar(c["email"], "mon", novo)
            except Exception as e:      # falha de uma conta não derruba as outras; só o tipo do erro é guardado
                res["erros"].append(e.__class__.__name__)
                banco.registrar_erro("monitor.conta", e)
        try:                                # Etapa 4: aquece o cache dos ativos prioritários e limpa cópias velhas
            import prioridade
            if not aquecer:
                raise _SemAquecer()
            res["aquecidos"] = prioridade.aquecer(coletor, dormir, ja_lidos=[k[0] for k in cache],
                                                  orcamento=max(0, MAX_ATIVOS_EXECUCAO - len(cache)))
            banco.cfg_limpar_cache(seg.somar(-3 * 86400, agora))
            res["avisos_cota"] = avisar_cotas(agora)
        except _SemAquecer:
            pass
        except Exception as e:
            res["erros"].append("aquecimento:" + e.__class__.__name__)
        try:                                # Etapa 11: avisos de vencimento/carência das assinaturas
            import assinaturas
            res["avisos_assinatura"] = assinaturas.avisar_vencimentos(agora)
        except Exception as e:
            res["erros"].append("assinaturas:" + e.__class__.__name__)
        try:                                # Etapa 15: avisa o administrador sobre contas que batem no limite muitas vezes
            import abuso
            res["avisos_abuso"] = abuso.avisar(agora)
        except Exception as e:
            res["erros"].append("abuso:" + e.__class__.__name__)
        try:                                # Etapa 16: faxina diária dos contadores antigos
            import manutencao
            res["faxina"] = manutencao.limpar_se_for_a_vez(agora.date())
        except Exception as e:
            res["erros"].append("manutencao:" + e.__class__.__name__)
        banco.limpar_antigos()
        status = "ok" if not res["erros"] and not res["fontes_com_erro"] else "parcial"
    except Exception as e:
        res["erros"].append(e.__class__.__name__)
        banco.registrar_erro("monitor", e)
        status = "falhou"
    res["duracao_s"] = round(time.monotonic() - t0, 1)
    res["erros"], res["fontes_com_erro"] = res["erros"][:20], res["fontes_com_erro"][:20]
    try:
        banco.sis_exec_finalizar(slot, status, res)
    except Exception as e:
        banco.registrar_erro("monitor.final", e)
    return {"status": status, **res}


def verificar_agora(ator, dados: dict, agora: datetime | None = None, coletor=None, dormir=time.sleep) -> dict:
    """Mesma avaliação do monitor, mas para a PRÓPRIA conta e disparada à mão (botão da Central). Só grava no app: não envia e-mail,
    Telegram nem push (evita enviar sem querer enquanto a pessoa testa). Usa a sessão aberta, então não vale como monitoramento contínuo."""
    agora = agora or seg.agora()
    coletor = coletor or coletor_padrao
    prefs = N.normalizar_prefs(dados.get("notif_prefs"))
    lotes = _lotes(dados)
    precisa = _necessidades(dados, lotes)
    res = {"ativos": len(precisa), "lidos": 0, "novas": 0, "suprimidas": 0, "agrupadas": 0, "erros": []}
    if not precisa:
        return {**res, "aviso": "Nada para verificar: crie um alerta ou registre posições na Carteira."}
    dd, falhas = {}, 0
    for (a, cl), fund in list(precisa.items())[:MAX_ATIVOS_CONTA]:
        if falhas >= FALHAS_PARA_PARAR:
            res["erros"].append("Fonte instável: o restante foi pulado para não travar.")
            break
        try:
            d = coletor(a, cl, fund) if fund else coletor(a, cl)
        except Exception as e:
            falhas += 1
            res["erros"].append(f"{a}: {e.__class__.__name__}")
            continue
        if d:
            dd[a] = d
            res["lidos"] += 1
            falhas = 0
    if not dd:
        return {**res, "aviso": "Nenhuma fonte respondeu agora. Tente de novo em alguns minutos."}
    estado = banco.monitor_estado_ler(ator)
    notifs, novo = avaliar_conta(dados, dd, estado, agora)
    peso = (N.metricas_carteira(lotes, dd) or {}).get("pesos", {})
    notifs = [n for n in notifs if N.passa_prefs(n, prefs)]
    for n in notifs:
        n["importancia"], mot = N.pontuar(n, peso)
        if mot:
            n["dados"]["prioridade_motivo"] = mot
    recentes = banco.notif_listar(ator, None, False, limite=300)
    notifs, res["suprimidas"] = N.suprimir(notifs, recentes, prefs, agora)
    if prefs["agrupar"]:
        notifs, res["agrupadas"] = N.agrupar(notifs)
    for n in notifs:
        n["dados"]["manual"] = True
        if banco.notif_inserir(ator, n):
            res["novas"] += 1
    novo["ultima_execucao"] = estado.get("ultima_execucao") or seg.iso(agora)
    banco.monitor_estado_gravar(ator, novo)
    return res


def main() -> int:
    try:                                   # Etapa 2: mesma proteção de rede e contagem de consumo do app
        __import__("protecao").iniciar()
    except Exception as e:
        print("aviso: proteção de rede não iniciada:", e.__class__.__name__)
    r = executar(url_app=__import__("email_envio").url_base())
    try:
        __import__("consumo").gravar_agora()
    except Exception:
        pass
    print({k: v for k, v in r.items() if k not in ("erros", "fontes_com_erro")})
    if r.get("erros") or r.get("fontes_com_erro"):
        print("erros:", r.get("erros"), "| fontes:", r.get("fontes_com_erro"))
    return 1 if r["status"] == "falhou" else 0


if __name__ == "__main__":
    sys.exit(main())
