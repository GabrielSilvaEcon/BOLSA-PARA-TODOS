/// Configuração pública do Supabase. Nada aqui é segredo: a chave pública é feita para ficar no app.
/// A URL entra aqui depois de confirmada; a chave vem do segredo SUPABASE_PUBLISHABLE_KEY, pelo robô (--dart-define).
const String supabaseUrl = '';
const String supabaseKey = String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');

/// Endereço do link de teste (volta para ele depois de confirmar o e-mail ou redefinir a senha).
const String linkDeTeste = 'https://gabrielsilvaecon.github.io/BOLSA-PARA-TODOS/';
