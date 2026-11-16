import shutil,subprocess,sys,os,tempfile
SRC=sys.argv[1]
M=[
 ("desliga bloqueio no simulador",'trader_battle.py','    if t in TIPOS_ENTRADA and st["bloq"]:','    if False and t in TIPOS_ENTRADA and st["bloq"]:'),
 ("desliga bloqueio no registro",'trader_battle.py','        if sim.get("bloq"):\n            raise','        if False:\n            raise'),
 ("usa sempre o stop do jogador (ignora limite)",'trader_battle.py','    if lim is not None and (stop is None','    if False and lim is not None and (stop is None'),
 ("trunca prejuízo no nível do limite (apaga gap)",'trader_battle.py','_fechar(st, k["o"] if gap else stop, i, motivo_stop)','_fechar(st, stop if motivo_stop=="limite" else (k["o"] if gap else stop), i, motivo_stop)'),
 ("ignora realizado no limite",'trader_battle.py','    falta = -limite_x - realizado','    falta = -limite_x'),
 ("não cancela pendentes",'trader_battle.py','        st["pend"] = None                                                         # ordens pendentes canceladas','        pass                                                         # ordens pendentes canceladas'),
 ("empate favorece o limite",'trader_battle.py','(lim > stop if lado == 1 else lim < stop)','(lim >= stop if lado == 1 else lim <= stop)'),
 ("limite de 4% em vez de 3%",'trader_battle.py','LIMITE_PERDA_PCT_PAT = 0.03','LIMITE_PERDA_PCT_PAT = 0.04'),
 ("gate de caixa exige só 1%",'trader_carteira.py','    if mesa:\n        minimo','    if False:\n        minimo'),
 ("vaza preço do limite ao adversário",'trader_battle.py','"preco": lim_preco}','"preco": lim_preco, "x": 0}'),  # neutra (controle): deve SOBREVIVER
 ("limite não reinicia por rodada (acumula entre rodadas)",'trader_battle.py','    st = {"pos": None, "pend": None, "trades": [], "ignoradas": 0, "bloq": False,','    st = {"pos": None, "pend": None, "trades": [], "ignoradas": 0, "bloq": True,'),
 ("pode_abrir ignora bloqueio",'trader_battle.py','bool(ativo and not st["bloq"] and not pos','bool(ativo and not pos'),
 ("resultado não marca limite_atingido",'trader_battle.py','res["limite_atingido"] = bool(sim["bloq"])','res["limite_atingido"] = False'),
]
for nome,f,a,b in M:
    d=tempfile.mkdtemp(prefix="mut_"); shutil.copytree(SRC,d+"/p",ignore=shutil.ignore_patterns("__pycache__",".pytest_cache"))
    p=d+"/p/"+f; s=open(p,encoding="utf-8").read()
    if a not in s: print("NAO APLICOU",nome); continue
    open(p,"w",encoding="utf-8").write(s.replace(a,b,1))
    r=subprocess.run([sys.executable,"-m","pytest","-q","-x","-p","no:cacheprovider","test_trader_operacao.py","test_trader_mesa.py"],cwd=d+"/p",capture_output=True,text=True)
    tail=r.stdout.strip().splitlines()[-1]
    print(("DETECTADA " if r.returncode else "SOBREVIVEU ")+nome+" | "+tail)
    shutil.rmtree(d)
