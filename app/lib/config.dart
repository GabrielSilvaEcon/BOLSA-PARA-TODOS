/// Configuração pública do Supabase. Nada aqui é segredo: a chave pública é feita para ficar no app.
/// A URL entra aqui depois de confirmada; a chave vem do segredo SUPABASE_PUBLISHABLE_KEY, pelo robô (--dart-define).
const String supabaseUrl = 'https://iygsizwnpenhumsbxryr.supabase.co';
const String supabaseKey = String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');

/// Endereço de volta do login com o Google no app de celular (o Android abre o app por este esquema; a URL tem que estar na lista de
/// redirecionamentos permitidos do Supabase e o esquema é registrado no AndroidManifest pelo workflow do APK).
const String linkGoogleApp = 'io.supabase.tickerhunters://login-callback/';

/// Endereço do link de teste (volta para ele depois de confirmar o e-mail ou redefinir a senha).
const String linkDeTeste = 'https://gabrielsilvaecon.github.io/BOLSA-PARA-TODOS/';
