# Bússola B3 — plataforma de análise de investimentos

App em Python e Streamlit para estudar e acompanhar investimentos: ações, FIIs, ETFs, fundos, renda fixa e criptomoedas, com análise,
carteira, risco, simuladores, relatórios, notificações e educação financeira. **Ferramenta educacional: nada aqui é recomendação de
investimento e o app nunca envia ordens nem altera posições.**

## Como rodar
1. `pip install -r requirements.txt` (Python 3.12 recomendado).
2. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha só o que for usar. Sem nenhum segredo o app abre como visitante.
3. `streamlit run app.py`. Testes: `pip install -r requirements-dev.txt` e `pytest`.

## Documentação
- `ARQUITETURA.md`: módulos, dados, banco, fontes, implantação, backup, manutenção e como adicionar uma nova classe de ativos.
- `AUDITORIA.md`: relatório final do Passo 25 (estado, testes, pendências).
- `SEGURANCA.md`, `NOTIFICACOES.md`, `EDUCACAO.md`: segurança/privacidade, alertas e monitor, educação financeira.
