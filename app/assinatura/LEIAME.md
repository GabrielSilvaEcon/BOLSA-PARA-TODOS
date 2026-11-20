# Chave do APK de teste

`teste.keystore` assina o APK de teste (link `apk-teste`). É uma chave de teste no padrão "debug" do Android
(senha `android`, apelido `androiddebugkey`), sem valor secreto. Ela existe só para que todo APK novo tenha a
MESMA assinatura: assim o celular atualiza o app por cima, sem precisar desinstalar.

A versão da Play Store vai usar outra chave, privada, guardada nos segredos do GitHub (nunca no repositório).
