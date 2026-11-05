# Auditoria final — custos, planos e segurança (Etapa 19)

Escopo: tudo que foi criado nas Fases 1 a 3 (controle de APIs, planos, assinaturas, custos, abuso, backup, carga). Data: 05/11/2026.
Método: leitura do código novo, testes automatizados (suíte completa passando), testes de concorrência e buscas por segredos/e-mails no repositório.
O que **não** foi possível verificar aqui está na seção "Ainda não comprovado".

## 1. Rentabilidade

| Pergunta | Resposta hoje |
|---|---|
| Alguma fonte de dados é paga? | Não. Todas as fontes usam cota gratuita; o custo variável de dados é **R$ 0,00**. |
| Quanto custa manter? | Só o que você informar em Administração > Custos (hospedagem, domínio). O app não vê faturas. |
| O que impede estourar a cota grátis? | Contagem central (consumo.py), cache central com cópia no banco, reserva de 70% para o aquecimento, pausa automática por falhas (disjuntor) e modo "bloquear" opcional por fonte. |
| Há receita? | Ainda não: preços dos planos começam em R$ 0 até você definir (Administração > Preços). Cobrança automática **não** foi ligada (trabalho sujo, item 8). |
| Como saber se dá lucro? | Preços > receita líquida, custo projetado, margem, ponto de equilíbrio por plano e preço mínimo para a margem alvo. Uso > custo médio por usuário de cada plano e quanto sobra por assinatura. |
| Risco de prejuízo? | Baixo enquanto tudo é gratuito. Passa a existir se (a) uma fonte virar paga, (b) o uso de IA por conta passar do que o plano paga. Os dois têm alerta ao administrador (80% do orçamento; contas fora do padrão). |

Fórmulas conferidas por teste com números conhecidos: líquido = preço × (1 − taxa%) − taxa fixa; margem = lucro ÷ receita líquida; preço mínimo = (custo ÷ (N × (1 − margem)) + taxa fixa) ÷ (1 − taxa%).

## 2. Segurança e privacidade

Verificado e em ordem:
- Nenhum segredo, chave ou e-mail pessoal no código ou nos documentos (varredura + teste `test_nenhum_arquivo_versionado_tem_credencial` na suíte). Nenhum e-mail em User-Agent.
- Todo texto de usuário que entra nos painéis passa por `_e()` (escape de HTML): e-mails, códigos de cupom, motivos. Sem injeção de HTML nos cartões.
- Painéis novos exigem permissão (`admin.banco` / `admin.backup`) e só o administrador vê e-mails de assinantes e de quem mais usa.
- Cupom: código validado (3–20 caracteres), 5 tentativas por dia por conta, uma vez por conta, trinco contra uso duplo; não rebaixa plano.
- Restauração de backup: arquivo cifrado com a chave dos Secrets; só chaves conhecidas, só dados no formato esperado; versão conferida; chave errada é recusada.
- LGPD: ao excluir a conta, plano/validade e uso diário (que guardam o e-mail) são apagados. Ficam só marcas sem e-mail (hash) que impedem reaproveitar teste grátis e cupom.
- Nada altera posições nem envia ordens; nenhuma etapa usa serviço pago.
- Banco: buscas por prefixo da chave; faxina diária de contadores antigos (uso 40 dias, consumo 120, tentativas de cupom 3).

Falhas **encontradas e corrigidas** nesta etapa (pelos testes de carga):
1. **Corrida no limite diário do plano**: 12 pedidos simultâneos da mesma conta deixavam passar 15 de um limite de 3. Corrigido com trinco por conta (agora exato).
2. **Corrida no limite de uma fonte (modo bloquear)**: passava até ~38 pedidos do teto. Corrigido: checar e contar viraram uma operação só (agora exato).
3. **Uso duplo de cupom** no mesmo instante: corrigido com trinco.
4. **Rajada de visitantes**: o limite por minuto seria compartilhado por todos os visitantes; agora é por sessão.

## 3. Medidas de carga (processo único, SQLite local, 16 threads)

| Operação | Resultado |
|---|---|
| Contar pedidos de uma fonte | ≈ 4.000/s, sem perder contagem (20.000 pedidos) |
| Cache central, acerto | ≈ 68.000/s; 60 pedidos iguais simultâneos geram **1** chamada à fonte |
| Limite do plano | ≈ 350 usos/s com 20 contas, exato |

Com Supabase cada gravação leva dezenas de ms; mesmo assim as contas diferentes não se bloqueiam (trincos por faixa de conta).

## 4. Ainda não comprovado (precisa do app no ar — "trabalho sujo")
- Carga real no Streamlit Cloud com muitos navegadores; tempo de resposta com Supabase.
- Aparência dos painéis novos no tablet e no celular.
- Disjuntor e dado antigo com falhas reais de fonte; contagem de usos do Yahoo fora de dados.py e de chamadas de IA diretas (não contadas).
- Monitor no GitHub Actions: atraso do cron e pausa após 60 dias sem atividade.
- Restauração de backup em produção (testada com banco temporário).
- Custos reais e preços: os valores iniciais são pontos de partida, não medições.

## 5. Limitações conhecidas
- Trincos e rajada valem por processo do app (reiniciam com ele); o monitor externo não usa esses limites.
- O custo por usuário só enxerga recursos limitados por plano (IA, atualizar dados); o custo de leitura de dados é compartilhado e aparece em Custos.
- O app não suspende nem bloqueia ninguém sozinho por abuso: avisa, e você decide.
- Sem cobrança automática: ativar e renovar planos é manual.
