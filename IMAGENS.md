# Lista de imagens do TickerHunters (redesign mobile game)

Todas as artes que o app precisa, tela por tela. Ao chegar uma arte nova, basta salvar com o **nome e a pasta indicados**: o código já aponta para esse caminho, sem precisar mexer em nada (exceto nos itens marcados *precisa ligar no código*).

**Padrão para enviar:** PNG com fundo transparente (eu converto para WebP), no tamanho pedido ou maior. Imagens que ocupam a largura da tela devem ter pelo menos 1080 px de largura, para ficarem nítidas em celulares de alta densidade.

**Status:**
- ⏳ **Provisória:** recortada do mockup. Funciona, mas fica um pouco suave.
- 🎨 **Falta:** a tela vai precisar, mas ainda não existe arte.
- ✅ **Final:** arte definitiva já no app.

---

## 1. Tela inicial (Home)

| # | Arte | Arquivo | Onde aparece | Tamanho ideal | Fundo | Status |
|---|------|---------|--------------|---------------|-------|--------|
| 1.1 | Touro contra urso no anel neon (Pregão Orbit) | `static/home/arena.webp` | Centro da Home, com as cotações nos cantos | 1536 × 980 px (proporção 768:490) | Escuro, com as bordas se dissolvendo; **sem textos nem números na arte** | ⏳ Provisória |
| 1.2 | Cabeça do touro roxo (logo) | `static/home/touro.webp` | Banner TICKER HUNTERS e selo do ranking no topo | 512 × 512 px | Transparente | ⏳ Provisória |
| 1.3 | Troféu dourado no pedestal | `static/home/trofeu.webp` | Cartão Missões diárias (esquerda) | 512 × 512 px | Transparente | ⏳ Provisória |
| 1.4 | Cofre com pilhas de moedas | `static/home/cofre.webp` | Cartão Missões diárias (recompensa, direita) | 512 × 512 px | Transparente | ⏳ Provisória |
| 1.7 | Botão JOGAR AGORA (com o mascote) | `static/home/btn_jogar.webp` | No meio da fileira de botões, maior | 1300 × 970 px (≈ 1,34:1) | Ideal: PNG transparente | ✅ Arte do dono (texto na arte) |
| 1.8 | Botão CARTEIRA | `static/home/btn_carteira.webp` | À esquerda da fileira | 940 × 750 px (≈ 1,25:1) | Ideal: PNG transparente | ✅ Arte do dono (texto na arte) |
| 1.9 | Botão MERCADO | `static/home/btn_mercado.webp` | À direita da fileira | 940 × 750 px (≈ 1,25:1) | Ideal: PNG transparente | ✅ Arte do dono (texto na arte) |
| 1.5 | Coroa dourada (opcional) | `static/home/coroa.webp` | Em cima do saldo de Ticker Coins | 128 × 96 px | Transparente | Hoje é um desenho em código (SVG); *precisa ligar no código* |
| 1.6 | Fundo da Home: cidade neon roxa com grade (opcional) | `static/fundos/home.webp` | Atrás de toda a tela inicial | 1080 × 2340 px (retrato) | Escuro, sem elementos no centro | 🎨 Falta · *precisa ligar no código* |

---

## 2. Meu Perfil

Hoje os ícones desta tela são emojis (provisórios). As artes abaixo deixam a tela igual ao mockup; *precisam ligar no código* quando chegarem.

| # | Arte | Arquivo | Onde aparece | Tamanho ideal | Fundo | Status |
|---|------|---------|--------------|---------------|-------|--------|
| 2.1 | Fundo: cidade ao entardecer com o touro e gráficos | `static/fundos/perfil.webp` | Atrás de toda a tela (hoje usa `mesa.webp`) | 1080 × 2340 px (retrato) | Escuro nas áreas dos cartões | 🎨 Falta |
| 2.2 | Fogo (sequência de dias) | `static/perfil/fogo.webp` | Cartão Sequência | 128 × 128 px | Transparente | 🎨 Falta (emoji 🔥) |
| 2.3 | Troféu pequeno (ranking) | `static/perfil/ranking.webp` | Cartão Ranking | 128 × 128 px | Transparente | 🎨 Falta (emoji 🏆) |
| 2.4 | Moeda Ticker Coin | `static/perfil/tc.webp` | Cartão Ticker Coins | 128 × 128 px | Transparente | 🎨 Falta (emoji 🪙) |
| 2.5 | Saco de dinheiro (patrimônio) | `static/perfil/patrimonio.webp` | Cartão Patrimônio | 128 × 128 px | Transparente | 🎨 Falta (emoji 💰) |
| 2.6 | Ícones do Desempenho: partidas, vitórias, derrotas | `static/perfil/partidas.webp`, `vitorias.webp`, `derrotas.webp` | Cartão Desempenho | 96 × 96 px cada | Transparente | 🎨 Falta (emojis ▶️ 🏆 💀) |
| 2.7 | Hexágonos das conquistas (um por emblema + o bloqueado) | `static/perfil/conquistas/<emblema>.webp` | Cartão Conquistas | 160 × 180 px cada | Transparente | 🎨 Falta (emojis) |
| 2.8 | Ícones da fileira Conta: Minha conta, Loja Ticker, Planos, Ajuda, Administração, Sair | `static/perfil/conta_<nome>.webp` | Fileira "Conta" no fim da tela | 128 × 128 px cada | Transparente | 🎨 Falta (emojis) |

---

## 0. Mascote (todas as telas)

O mascote novo (touro-urso roxo de jaqueta TH) vai aparecer nas próximas telas. Hoje o app ainda usa o Caramelo (cachorro) em várias telas:
decidir se o novo **substitui** o Caramelo em tudo. Se sim, são estas poses:

| # | Pose | Arquivo | Onde aparece hoje (com o Caramelo) | Tamanho ideal | Fundo | Status |
|---|------|---------|-------------------------------------|---------------|-------|--------|
| 0.1 | Braços cruzados (pose principal) | `static/mascote/principal.webp` | Capa, login, banners | 1024 × 1024 px | Transparente | ⏳ Recebida com fundo (arte da conversa) |
| 0.2 | Apontando / chamando para jogar | `static/mascote/chamando.webp` | Botão JOGAR AGORA, convites | 1024 × 1024 px | Transparente | ⏳ Só dentro do botão |
| 0.3 | Rosto (para avatar, selos e ranking) | `static/mascote/rosto.webp` | Selo do ranking, banner da Home (no lugar do touro roxo) | 512 × 512 px | Transparente | 🎨 Falta |
| 0.4 | Animado | `static/mascote/animado.webp` | Boas-vindas, missões | 1024 × 1024 px | Transparente | 🎨 Falta |
| 0.5 | Pensativo | `static/mascote/pensativo.webp` | Telas vazias, Ajuda, Analisar | 1024 × 1024 px | Transparente | 🎨 Falta |
| 0.6 | Celebrando | `static/mascote/celebrando.webp` | Conquistas, lição concluída, vitória | 1024 × 1024 px | Transparente | 🎨 Falta |
| 0.7 | Surpreso | `static/mascote/surpreso.webp` | Novidades, baú aberto | 1024 × 1024 px | Transparente | 🎨 Falta |
| 0.8 | Triste | `static/mascote/triste.webp` | Erro, derrota, ofensiva perdida | 1024 × 1024 px | Transparente | 🎨 Falta |
| 0.9 | Dormindo | `static/mascote/dormindo.webp` | Mercado fechado, sem atividade | 1024 × 1024 px | Transparente | 🎨 Falta |

---

## 3. Ranking

Artes recortadas do mockup do Ranking (provisórias). O texto de cada aba e das linhas é escrito pelo código.

| # | Arte | Arquivo | Onde aparece | Tamanho ideal | Fundo | Status |
|---|------|---------|--------------|---------------|-------|--------|
| 3.1 | Mascote no topo (faixa larga) | `static/ranking/mascote.webp` | Topo da tela, atrás da sua ficha | 1500 × 670 px | Cena (sem texto) | ⏳ Recorte da arte do mascote |
| 3.2 | Ícone Ticker Battle (ingresso com coroa) | `static/ranking/ticker.webp` | Aba Ticker Battle | 256 × 170 px | Transparente | ⏳ Recortado do mockup |
| 3.3 | Ícone Trade Battle (setas) | `static/ranking/trade.webp` | Aba Trade Battle | 256 × 200 px | Transparente | ⏳ Recortado do mockup |
| 3.4 | Ícone Carteira (carteira verde) | `static/ranking/carteira.webp` | Aba Carteira | 256 × 210 px | Transparente | ⏳ Recortado do mockup |
| 3.5 | Faixa MODO RANQUEADO | `static/ranking/faixa.webp` | Abaixo de Global/Amigos | 1800 × 370 px | Cena | ⏳ Recortado do mockup (texto na arte) |
| 3.6 | Ícone da pontuação (ingresso com coroa) | `static/ranking/pts.webp` | À direita de cada linha | 128 × 128 px | Transparente | ⏳ Recortado do mockup |
| 3.7 | Coroa do título | `static/ranking/coroa.webp` | Acima de RANKING | 128 × 80 px | Transparente | ⏳ Recortado do mockup |

---

## 4. Carteira

Artes recortadas do mockup da Carteira (provisórias). O topo com o mascote é o mesmo do Ranking (`static/ranking/mascote.webp`).
FIIs e Renda fixa ainda usam emoji (🏢 🏦) porque o mockup não tem ícone para eles.

| # | Arte | Arquivo | Onde aparece | Tamanho ideal | Fundo | Status |
|---|------|---------|--------------|---------------|-------|--------|
| 4.1 | Carteira verde (ícone do título) | `static/carteira/carteira.webp` | Cartão "Carteira", à esquerda | 256 × 256 px | Transparente | ⏳ Recortado do mockup |
| 4.2 | Gráfico subindo (aba Todos) | `static/carteira/valor.webp` | Aba Todos | 128 × 128 px | Transparente | ⏳ Recortado do mockup |
| 4.3 | Ícone Ações | `static/carteira/acoes.webp` | Aba Ações | 128 × 128 px | Transparente | ⏳ Recortado do mockup |
| 4.4 | Ícone Cripto | `static/carteira/cripto.webp` | Aba Cripto | 128 × 128 px | Transparente | ⏳ Recortado do mockup |
| 4.5 | Ícone ETFs | `static/carteira/etf.webp` | Aba ETFs | 128 × 128 px | Transparente | ⏳ Recortado do mockup |
| 4.6 | Ícone Fundos | `static/carteira/fundo.webp` | Aba Fundos | 128 × 128 px | Transparente | ⏳ Recortado do mockup |
| 4.7 | Ícone FIIs | `static/carteira/fii.webp` | Aba FIIs | 128 × 128 px | Transparente | 🎨 Falta (emoji 🏢) · *precisa ligar no código* |
| 4.8 | Ícone Renda fixa | `static/carteira/rf.webp` | Aba Renda fixa | 128 × 128 px | Transparente | 🎨 Falta (emoji 🏦) · *precisa ligar no código* |

---

## 5. Analisar

| # | Arte | Arquivo | Onde aparece | Tamanho ideal | Fundo | Status |
|---|------|---------|--------------|---------------|-------|--------|
| 5.1 | Mascote apontando com o celular TickerHunters | `static/ilustracoes/analisar_touro.webp` | Cartão do topo "Escolha o que Analisar" (à direita) | 1200 × 920 px | Cena | ✅ Arte do dono |

---

## Próximas telas

_As telas seguintes entram aqui à medida que os mockups chegarem (Jogos, Aprender, Ranking, Loja, Carteira, Mercado...)._
