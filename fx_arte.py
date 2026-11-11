"""Componentes de celebração do TickerHunters (Fase 9): baú, subida de nível, emblema, compra, recompensas, rank e raridade.
Módulo puro: só gera HTML/CSS (sem Streamlit, sem banco, sem rede). Use:  st.markdown(fx_arte.CSS + fx_arte.html_xxx(...), unsafe_allow_html=True)

Princípios
- Leve: só `transform` e `opacity` (rodam na GPU), até ~16 pontos de brilho, nada em loop infinito, cada efeito toca UMA vez (duração 0,5 a 3 s).
- Só em momentos importantes: o chamador decide quando mostrar (veja `primeira_vez`), nada aqui anima sozinho telas comuns.
- Acessível: com `prefers-reduced-motion` ou `animar=False` o estado FINAL aparece parado (sem movimento), o texto é o mesmo e vai em `role="status"`
  (leitor de tela anuncia). Imagens decorativas têm alt vazio; as que informam têm alt.
- Reutilizável: cada função recebe só dados simples (nome, raridade, texto) e devolve HTML autônomo; a identidade (Caramelo, baús, ranks) vem de arte_tickerhunters.
- Não concede nada: é só apresentação. XP, TC e T$ continuam nas regras do servidor.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

import arte_tickerhunters as AT

# ------------------------------------------------------------------ tokens de movimento (um lugar só)
DUR = {"curta": "0.5s", "media": "0.9s", "longa": "1.6s", "festa": "2.6s"}
EASE = {"saida": "cubic-bezier(.2,.8,.2,1)", "pulo": "cubic-bezier(.34,1.56,.64,1)"}
# raridade -> quantidade de brilhos (comum não tem: só o essencial)
BRILHOS = {"comum": 0, "raro": 6, "epico": 10, "lendario": 16}


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def animar_padrao(estado) -> bool:
    """Preferência da pessoa (st.session_state ou dict): chave 'fx_animacoes'. Padrão ligado. Falso = tudo parado, só o resultado."""
    try:
        return bool(estado.get("fx_animacoes", True))
    except Exception:
        return True


def primeira_vez(estado, chave: str) -> bool:
    """True só na primeira chamada para `chave` na sessão (evita repetir a celebração a cada atualização da tela)."""
    vistos = estado.get("_fx_vistos")
    if not isinstance(vistos, list):
        vistos = []
    if chave in vistos:
        return False
    estado["_fx_vistos"] = (vistos + [chave])[-200:]
    return True


def _uma_linha(css: str) -> str:
    """CSS em UMA linha: o st.markdown trata linhas depois de um </style> como texto (aparecia CSS solto na tela). Uma linha só evita isso."""
    return "".join(l.strip() for l in css.splitlines())


# ------------------------------------------------------------------ CSS (uma vez por tela)
CSS = f"""<style>
.fxa{{position:relative;overflow:hidden;margin:8px auto 12px;max-width:520px;padding:18px 14px 16px;border-radius:26px;text-align:center;
background:radial-gradient(circle at 50% 30%,color-mix(in srgb,var(--fc) 22%,#2B2070),#17124A 75%);border:1px solid var(--fc);
box-shadow:0 0 24px -8px var(--fc),0 4px 0 rgba(8,6,36,.6);--fc:#C5B3FF}}
.fxa *{{box-sizing:border-box}}
.fxa-t{{position:relative;z-index:3;font-weight:900;font-size:1.25rem;line-height:1.15;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
.fxa-s{{position:relative;z-index:3;margin-top:4px;font-size:.88rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
.fxa-rar{{display:inline-block;margin-top:8px;padding:2px 10px;border-radius:999px;font-weight:900;font-size:.68rem;letter-spacing:.04em;text-transform:uppercase;
color:var(--fc) !important;-webkit-text-fill-color:var(--fc) !important;border:1px solid var(--fc);background:rgba(10,8,40,.55);position:relative;z-index:3}}
.fxa img{{display:block;margin:0 auto;max-width:100%;height:auto;filter:drop-shadow(0 6px 8px rgba(0,0,0,.45))}}
.fxa-cena{{position:relative;z-index:2;display:grid;place-items:center;min-height:150px;margin-bottom:6px}}
.fxa-cena>*{{grid-area:1/1}}
.fxa-rays{{position:absolute;z-index:1;left:50%;top:44%;width:360px;height:360px;margin:-180px 0 0 -180px;border-radius:50%;pointer-events:none;
background:repeating-conic-gradient(from 0deg,color-mix(in srgb,var(--fc) 42%,transparent) 0 7deg,transparent 7deg 22deg);
-webkit-mask-image:radial-gradient(circle,#000 14%,transparent 66%);mask-image:radial-gradient(circle,#000 14%,transparent 66%);
animation:fxa-gira {DUR['festa']} linear 1 both,fxa-surge {DUR['festa']} ease-out 1 both}}
.fxa-sp{{position:absolute;z-index:2;left:var(--x);top:var(--y);width:9px;height:9px;border-radius:50%;background:var(--k,#FFD66B);box-shadow:0 0 8px var(--k,#FFD66B);
opacity:0;animation:fxa-brilha 1.7s ease-out var(--d) 1 both;pointer-events:none}}
.fxa-sp.e{{width:12px;height:12px;border-radius:0;clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)}}
.fxa-flash{{position:absolute;z-index:3;inset:0;background:radial-gradient(circle,#fff,transparent 62%);opacity:0;animation:fxa-flash .9s ease-out 1.0s 1 both;pointer-events:none}}
/* baú */
.fxa-bau img{{height:112px;width:auto}}
.fxa-bau .cx{{animation:fxa-treme 1s ease-in-out 1 both,fxa-some .5s ease-in 1.0s 1 both}}
.fxa-bau .pr{{display:grid;justify-items:center;gap:4px;animation:fxa-revela {DUR['longa']} {EASE['pulo']} 1.25s 1 both}}
.fxa-bau .pr img{{height:76px;width:auto}}
.fxa-bau.abrindo .fxa-t,.fxa-bau.abrindo .fxa-rar{{animation:fxa-pop .6s ease-out 1.4s 1 both}}
.fxa-bau.fechado .cx{{animation:none}}
.fxa-bau.fechado .pr,.fxa-bau.fechado .fxa-rays,.fxa-bau.fechado .fxa-flash{{display:none}}
.fxa-bau.aberto .cx,.fxa-bau.aberto .fxa-flash{{display:none}}
.fxa-pr-n{{font-weight:900;font-size:1.5rem;color:#fff !important;-webkit-text-fill-color:#fff !important;text-shadow:0 2px 0 rgba(0,0,0,.4)}}
.fxa-pr-l{{font-size:.85rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
/* nível e rank */
.fxa-nivel .caramelo{{height:150px;width:auto;animation:fxa-pula {DUR['longa']} {EASE['pulo']} 1 both}}
.fxa-sel{{position:relative;z-index:3;margin:-14px auto 4px;display:inline-grid;place-items:center;min-width:96px;padding:4px 18px;border-radius:999px;
background:linear-gradient(180deg,#FFD66B,#F2B84B);border:2px solid #FFF1B8;box-shadow:0 3px 0 #9A6B12;animation:fxa-pop .7s {EASE['pulo']} .5s 1 both}}
.fxa-sel b{{font-size:1.15rem;color:#3B2600 !important;-webkit-text-fill-color:#3B2600 !important;font-weight:900}}
.fxa-onda{{position:absolute;z-index:1;left:50%;top:48%;width:120px;height:120px;margin:-60px 0 0 -60px;border-radius:50%;border:3px solid var(--fc);opacity:0;
animation:fxa-onda 1.6s ease-out .35s 2 both;pointer-events:none}}
.fxa-rank .novo{{height:124px;width:auto;animation:fxa-entra {DUR['longa']} {EASE['pulo']} .35s 1 both}}
.fxa-rank .velho{{height:84px;width:auto;opacity:.0;animation:fxa-velho .9s ease-in 1 both}}
.fxa-rank.parado .velho{{display:none}}
/* emblema */
.fxa-emb .med{{position:relative;width:104px;height:104px;border-radius:50%;display:grid;place-items:center;font-size:3rem;overflow:hidden;
background:radial-gradient(circle at 30% 25%,rgba(255,255,255,.4),transparent 55%),color-mix(in srgb,var(--fc) 55%,#1A1438);border:4px solid var(--fc);
box-shadow:0 0 22px var(--fc);animation:fxa-gira-pop {DUR['longa']} {EASE['pulo']} 1 both}}
.fxa-emb .med img{{height:70px;width:auto}}
.fxa-emb .med:after{{content:"";position:absolute;top:-20%;left:-60%;width:40%;height:140%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.7),transparent);
transform:rotate(18deg);animation:fxa-brilho-passa 1.2s ease-in-out .9s 1 both}}
/* compra */
.fxa-compra .ck{{width:74px;height:74px;margin:0 auto 14px;display:block}}
.fxa-compra .ck circle{{fill:rgba(61,220,151,.16);stroke:#3DDC97;stroke-width:4;stroke-dasharray:226;animation:fxa-traco .7s ease-out 1 both}}
.fxa-compra .ck path{{fill:none;stroke:#3DDC97;stroke-width:6;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:60;animation:fxa-traco .5s ease-out .55s 1 both}}
.fxa-compra .it{{display:grid;place-items:center;margin:2px 0 6px;animation:fxa-pop .7s {EASE['pulo']} .7s 1 both}}
.fxa-compra .it img{{height:84px;width:auto}}
/* recompensas */
.fxa-rec .lin{{position:relative;z-index:3;display:flex;flex-wrap:wrap;justify-content:center;gap:10px;margin-top:10px}}
.fxa-rec .rc{{display:grid;justify-items:center;gap:2px;min-width:78px;padding:8px 10px;border-radius:18px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.22);
animation:fxa-pop .6s {EASE['pulo']} calc(.25s + var(--i)*.18s) 1 both}}
.fxa-rec .rc img{{height:46px;width:auto}}
.fxa-rec .rc b{{font-size:1.1rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
.fxa-rec .rc small{{font-size:.7rem;color:#C5B3FF !important;-webkit-text-fill-color:#C5B3FF !important}}
/* raridade em cartões */
.fxa-raro{{box-shadow:0 0 14px -4px #4DA3FF}}
.fxa-epico{{position:relative;overflow:hidden;box-shadow:0 0 16px -4px #B06BFF}}
.fxa-epico:after,.fxa-lendario:after{{content:"";position:absolute;top:0;left:-70%;width:45%;height:100%;pointer-events:none;
background:linear-gradient(100deg,transparent,rgba(255,255,255,.22),transparent);transform:skewX(-18deg);animation:fxa-brilho-passa 1.6s ease-in-out .3s 2 both}}
.fxa-lendario{{position:relative;overflow:hidden;box-shadow:0 0 20px -3px #FFB938,0 0 2px #FFB938;animation:fxa-halo 2.4s ease-in-out 2 both}}
.fxa-raro>*,.fxa-epico>*,.fxa-lendario>*{{margin:0 !important}}
/* modo parado: mesmo resultado, sem movimento */
.fxa-parado *,.fxa-parado *:after,.fxa-parado:after{{animation:none !important}}
.fxa-parado .fxa-rays,.fxa-parado .fxa-sp,.fxa-parado .fxa-flash,.fxa-parado .fxa-onda{{display:none}}
.fxa-parado.fxa-bau:not(.fechado) .cx{{display:none}}
@media (prefers-reduced-motion:reduce){{.fxa *,.fxa *:after,.fxa:after{{animation:none !important}}.fxa .fxa-rays,.fxa .fxa-sp,.fxa .fxa-flash,.fxa .fxa-onda{{display:none}}.fxa-bau:not(.fechado) .cx{{display:none}}}}
@media (max-width:380px){{.fxa{{padding:14px 10px 12px}}.fxa-t{{font-size:1.1rem}}.fxa-bau img{{height:96px}}.fxa-nivel .caramelo{{height:128px}}.fxa-rays{{width:280px;height:280px;margin:-140px 0 0 -140px}}}}
@keyframes fxa-gira{{from{{transform:rotate(0)}}to{{transform:rotate(120deg)}}}}
@keyframes fxa-surge{{0%{{opacity:0}}25%{{opacity:1}}100%{{opacity:.55}}}}
@keyframes fxa-brilha{{0%{{opacity:0;transform:translateY(8px) scale(.4)}}25%{{opacity:1}}100%{{opacity:0;transform:translateY(-34px) scale(1)}}}}
@keyframes fxa-flash{{0%{{opacity:0}}30%{{opacity:.85}}100%{{opacity:0}}}}
@keyframes fxa-treme{{0%,100%{{transform:rotate(0)}}15%{{transform:rotate(-7deg)}}35%{{transform:rotate(6deg)}}55%{{transform:rotate(-5deg)}}75%{{transform:rotate(3deg)}}}}
@keyframes fxa-some{{to{{opacity:0;transform:scale(.8) translateY(10px)}}}}
@keyframes fxa-revela{{0%{{opacity:0;transform:translateY(24px) scale(.4)}}100%{{opacity:1;transform:none}}}}
@keyframes fxa-pula{{0%{{opacity:0;transform:translateY(34px) scale(.7)}}100%{{opacity:1;transform:none}}}}
@keyframes fxa-pop{{0%{{opacity:0;transform:scale(.4)}}100%{{opacity:1;transform:none}}}}
@keyframes fxa-onda{{0%{{opacity:.8;transform:scale(.5)}}100%{{opacity:0;transform:scale(2.6)}}}}
@keyframes fxa-entra{{0%{{opacity:0;transform:scale(.3) rotate(-12deg)}}100%{{opacity:1;transform:none}}}}
@keyframes fxa-velho{{0%{{opacity:.9;transform:none}}100%{{opacity:0;transform:scale(.6) translateY(10px)}}}}
@keyframes fxa-gira-pop{{0%{{opacity:0;transform:scale(.3) rotate(-180deg)}}100%{{opacity:1;transform:none}}}}
@keyframes fxa-brilho-passa{{0%{{left:-70%}}100%{{left:140%}}}}
@keyframes fxa-traco{{from{{stroke-dashoffset:230}}to{{stroke-dashoffset:0}}}}
@keyframes fxa-halo{{0%,100%{{box-shadow:0 0 14px -3px #FFB938}}50%{{box-shadow:0 0 26px 0 #FFB938}}}}
</style>"""
CSS = _uma_linha(CSS)


# ------------------------------------------------------------------ blocos internos
_CORES = {"comum": ["#FFD66B", "#EDE9FF"], "raro": ["#7DB9FF", "#FFD66B", "#EDE9FF"], "epico": ["#C98BFF", "#FFD66B", "#7DE3FF"],
          "lendario": ["#FFD66B", "#FFF1B8", "#FFB938", "#FF8A3D"]}


def _brilhos(raridade: str, n: int | None = None, atraso: float = 1.1, cores: list | None = None) -> str:
    """Pontos de brilho espalhados (posições fixas: sem aleatório, mesmo HTML sempre, sem 'piscar' a cada atualização)."""
    n = BRILHOS[raridade] if n is None else n
    cores = [c for c in (cores or []) if isinstance(c, str)] or _CORES[raridade]
    out = []
    for i in range(n):
        x, y = 6 + (i * 37) % 88, 12 + (i * 53) % 70
        forma = " e" if raridade in ("epico", "lendario") and i % 2 == 0 else ""
        out.append(f"<i class='fxa-sp{forma}' style='--x:{x}%;--y:{y}%;--k:{cores[i % len(cores)]};--d:{atraso + (i * 0.11) % 0.9:.2f}s'></i>")
    return "".join(out)


def _raiz(cls: str, raridade: str, animar: bool, texto_leitor: str) -> str:
    r = AT.raridade_ok(raridade)
    parado = "" if animar else " fxa-parado"
    return f"<div class='fxa {cls}{parado}' role='status' aria-live='polite' aria-label='{_e(texto_leitor)}' style='--fc:{AT.RAR_COR[r]}'>"


# ------------------------------------------------------------------ 1. abertura de baú (pronto para a mecânica futura)
def html_bau(raridade: str = "comum", estado: str = "abrindo", premio: dict | None = None, animar: bool = True) -> str:
    """Baú. estado: 'fechado' (parado, para o botão 'Abrir' do chamador) | 'abrindo' (treme, luz, revela o prêmio) | 'aberto' (só o prêmio).
    premio = {"sprite": "tc", "valor": "+25", "rotulo": "TickerCoins"}  (sprite de arte_tickerhunters; opcional). Só apresenta: quem credita é o servidor."""
    r = AT.raridade_ok(raridade)
    estado = estado if estado in ("fechado", "abrindo", "aberto") else "abrindo"
    nome = f"Baú {AT.RAR_ROTULO[r]}"
    p = premio or {}
    pr = ""
    if p:
        sprite = p.get("sprite") if AT.existe(p.get("sprite", "")) else "tc"
        pr = (f"<div class='pr'>{AT.img(sprite, 64)}<div class='fxa-pr-n'>{_e(p.get('valor', ''))}</div><div class='fxa-pr-l'>{_e(p.get('rotulo', ''))}</div></div>")
    titulo = {"fechado": f"{nome} fechado", "abrindo": f"{nome} aberto!", "aberto": f"{nome} aberto!"}[estado]
    leitor = titulo + (f" Prêmio: {p.get('valor', '')} {p.get('rotulo', '')}" if p else "")
    mostra_luz = estado == "abrindo" and r != "comum"
    return (_raiz(f"fxa-bau {estado}", r, animar, leitor)
            + ("<div class='fxa-rays'></div>" if mostra_luz else "")
            + f"<div class='fxa-cena'><div class='cx'>{AT.img(AT.bau(r), 112, nome if estado == 'fechado' else '')}</div>"
            + ("<div class='fxa-flash'></div>" if estado == "abrindo" else "") + pr + "</div>"
            + (_brilhos(r) if estado != "fechado" else "") + f"<div class='fxa-t'>{_e(titulo)}</div><span class='fxa-rar'>{_e(AT.RAR_ROTULO[r])}</span></div>")


# ------------------------------------------------------------------ 2. subida de nível (Caramelo comemora)
def html_nivel(nivel: int, titulo: str = "", animar: bool = True, pose: str = "celebrando", cores: list | None = None) -> str:
    leitor = f"Você subiu para o nível {nivel}!" + (f" Novo título: {titulo}" if titulo else "")
    return (_raiz("fxa-nivel", "lendario", animar, leitor) + "<div class='fxa-onda'></div>"
            + f"<div class='fxa-cena'>{AT.img(AT.pose(pose), 150, 'Caramelo comemorando', 'caramelo')}</div>"
            + f"<div class='fxa-sel'><b>NÍVEL {int(nivel)}</b></div>" + _brilhos("epico", 10, 0.6, cores)
            + "<div class='fxa-t'>Você subiu de nível!</div>" + (f"<div class='fxa-s'>Novo título: {_e(titulo)}</div>" if titulo else "") + "</div>")


# ------------------------------------------------------------------ 3. emblema / conquista
def html_emblema(nome: str, descricao: str = "", raridade: str = "raro", emoji: str = "", sprite: str = "", animar: bool = True, cores: list | None = None) -> str:
    """Desbloqueio de emblema ou conquista. Dê `sprite` (arte) OU `emoji`."""
    r = AT.raridade_ok(raridade)
    miolo = AT.img(sprite, 70) if sprite and AT.existe(sprite) else _e(emoji or "🏅")
    return (_raiz("fxa-emb", r, animar, f"Emblema desbloqueado: {nome}. {descricao}") + f"<div class='fxa-cena'><div class='med'>{miolo}</div></div>"
            + _brilhos(r, None if r != "comum" else 4, 0.9, cores) + "<div class='fxa-t'>Emblema desbloqueado!</div>"
            + f"<div class='fxa-s'><b>{_e(nome)}</b>" + (f"<br>{_e(descricao)}" if descricao else "") + f"</div><span class='fxa-rar'>{_e(AT.RAR_ROTULO[r])}</span></div>")


# ------------------------------------------------------------------ 4. compra na Loja Ticker
def html_compra(nome: str, previa_html: str = "", preco: int | None = None, raridade: str = "comum", animar: bool = True) -> str:
    """Confirmação visual da compra. `previa_html` = miniatura do item (visual_loja.html_previa) ou vazio."""
    r = AT.raridade_ok(raridade)
    check = ("<svg class='ck' viewBox='0 0 80 80' aria-hidden='true'><circle cx='40' cy='40' r='36'/><path d='M24 41 l11 11 l22 -24'/></svg>")
    it = f"<div class='it'>{previa_html}</div>" if previa_html else ""
    return (_raiz("fxa-compra", r, animar, f"Compra feita: {nome}" + (f" por {preco} TC" if preco is not None else "")) + check + it
            + _brilhos(r, None if r != "comum" else 0, 1.0) + "<div class='fxa-t'>Compra feita!</div>"
            + f"<div class='fxa-s'><b>{_e(nome)}</b>" + (f" · {int(preco)} TC" if preco is not None else "") + "</div></div>")


# ------------------------------------------------------------------ 5. recompensas de missão e bônus diário
def html_recompensa(titulo: str, itens: list[dict], subtitulo: str = "", raridade: str = "comum", animar: bool = True) -> str:
    """itens = [{"sprite": "tc"|"xp"|"ts"|..., "valor": "+10", "rotulo": "TickerCoins"}]. Até 4 itens aparecem em sequência."""
    r = AT.raridade_ok(raridade)
    chips = []
    for i, it in enumerate((itens or [])[:4]):
        sp = it.get("sprite") if AT.existe(it.get("sprite", "")) else "tc"
        chips.append(f"<div class='rc' style='--i:{i}'>{AT.img(sp, 46)}<b>{_e(it.get('valor', ''))}</b><small>{_e(it.get('rotulo', ''))}</small></div>")
    leitor = f"{titulo}. " + ", ".join(f"{i.get('valor', '')} {i.get('rotulo', '')}" for i in (itens or [])[:4])
    return (_raiz("fxa-rec", r, animar, leitor) + _brilhos(r, None if r != "comum" else 0, 0.5) + f"<div class='fxa-t'>{_e(titulo)}</div>"
            + (f"<div class='fxa-s'>{_e(subtitulo)}</div>" if subtitulo else "") + "<div class='lin'>" + "".join(chips) + "</div></div>")


# ------------------------------------------------------------------ 6. promoção de rank
def html_rank(novo: str, anterior: str | None = None, animar: bool = True) -> str:
    """Promoção de rank (bronze, prata, ouro, platina, diamante, mestre). `anterior` mostra o rank antigo saindo."""
    n = novo if novo in AT.RANKS else "bronze"
    ant = ""
    if anterior in AT.RANKS and anterior != n:
        ant = f"<div class='velho'>{AT.img(AT.rank(anterior), 84)}</div>"
    r = {"bronze": "comum", "prata": "comum", "ouro": "raro", "platina": "epico", "diamante": "epico", "mestre": "lendario"}[n]
    return (_raiz("fxa-rank", r, animar, f"Promoção! Você chegou ao rank {AT.RANK_ROTULO[n]}.") + "<div class='fxa-onda'></div>"
            + f"<div class='fxa-cena'>{ant}<div class='novo'>{AT.img(AT.rank(n), 124, 'Rank ' + AT.RANK_ROTULO[n])}</div></div>"
            + _brilhos(r, None if r != "comum" else 5, 0.7) + "<div class='fxa-t'>Promoção de rank!</div>"
            + f"<div class='fxa-s'>Você chegou ao <b>{AT.RANK_ROTULO[n]}</b></div></div>")


# ------------------------------------------------------------------ 7. destaque por raridade (para cartões de item)
def moldura_raridade(conteudo_html: str, raridade: str) -> str:
    """Envolve um cartão com o brilho da raridade (raro: halo azul; épico: halo roxo + brilho que passa; lendário: halo dourado que pulsa 2 vezes).
    Comum devolve o conteúdo como está. Só decoração: o cartão continua com o mesmo texto."""
    r = AT.raridade_ok(raridade)
    if r == "comum":
        return conteudo_html
    return f"<div class='fxa-{r}' style='border-radius:18px'>{conteudo_html}</div>"
