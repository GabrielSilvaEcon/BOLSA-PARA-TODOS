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

## Próximas telas

_As telas seguintes entram aqui à medida que os mockups chegarem (Jogos, Aprender, Ranking, Loja, Carteira, Mercado...)._
