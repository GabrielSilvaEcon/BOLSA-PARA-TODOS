# Segurança — Bússola B3 (Passo 22)

Nenhum sistema é 100% seguro; isto reduz riscos e deixa tudo verificável.

## Camadas
- `seguranca.py`: hash de senha (Argon2id se `argon2-cffi` instalado, senão scrypt), validadores, máscara de logs, anti-injeção de CSV, minimização de dados para IA.
- `http_seguro.py`: guarda de rede (SSRF, timeout, TLS, lista de domínios) para tudo que usa `requests`.
- `protecao.py`: liga as proteções na partida e faz o diagnóstico.
- `alertas_seg.py`: alertas de atividade suspeita (Administração > Segurança).
- `backup_seg.py`: backup cifrado + teste de restauração.
- `auditoria_codigo.py`: varredura de segredos e padrões perigosos (marcador `# seg-ok` para falsos positivos justificados).
- `banco.py`: único lugar com SQL; verificação de dono em cada leitura/escrita; RLS no Supabase.

## Retenção
Erros 90 dias · auditoria 400 dias · sessões e tokens expiram sozinhos.

## Plano de incidente
1. Suspeitou? Suspenda a conta em Administração. 2. Gere novos segredos só se houver vazamento real. 3. Revise Auditoria. 4. Restaure o backup testado. 5. Avise os afetados (ver LGPD abaixo).

## Pontos para revisão jurídica (LGPD)
Base legal e política de privacidade; prazo de retenção; aviso de incidente à ANPD; contrato com Supabase/Google/provedor de IA; transferência internacional. O app oferece exportar e excluir dados, mas não declara conformidade automática.

## Ações manuais
- Adicionar `[admin] emails` nos secrets para ver o painel.
- Opcional: `[backup] chave` e `[seguranca] modo_dominios`.
- Ativar Dependabot/alertas e Secret scanning no GitHub (Settings > Code security).
- Supabase: ativar backups no painel.

## Limites conhecidos
Guarda de rede não cobre `httpx`, `curl_cffi` e `urllib`; cabeçalhos HTTP/CORS são do Streamlit Cloud; SQLite local perde dados em redeploy; Yahoo pode dar erro externo.
