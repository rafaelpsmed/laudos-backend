"""
Arquivo de Signals do Django para automação de cópia de dados iniciais.

DESCRIÇÃO:
----------
Este arquivo contém signals que serão disparados automaticamente quando certos
eventos acontecerem no sistema, especificamente relacionados à criação de novos usuários.

FUNCIONALIDADE PRINCIPAL:
-------------------------
Quando um novo usuário for cadastrado no sistema (CustomUser criado), este signal
irá automaticamente:

1. Copiar modelos de laudo pré-definidos (modelos A, B, C, etc.)
   para o novo usuário, garantindo que ele já tenha acesso aos modelos padrão
   do sistema

2. Copiar todas as frases relacionadas aos modelos copiados, mantendo
   os relacionamentos ManyToMany entre frases e modelos de laudo

3. Copiar variáveis pré-definidas do sistema para o novo usuário,
   garantindo que ele já tenha as variáveis padrão disponíveis

RESULTADO:
----------
O novo usuário não entrará com uma conta "limpa", mas sim já terá acesso
aos modelos de laudo, frases e variáveis padrão do sistema, permitindo
que ele comece a trabalhar imediatamente sem precisar de configuração manual.

COMO FUNCIONA:
--------------
O signal post_save do Django será conectado ao modelo CustomUser.
Quando um novo usuário for criado (created=True), a função de callback
será executada automaticamente e fará as cópias necessárias no banco de dados.

BENEFÍCIOS:
-----------
- Automatização completa do processo
- Não requer intervenção manual via console MySQL
- Funciona independentemente de como o usuário foi criado (admin, API, etc.)
- Garante consistência: todos os novos usuários recebem os mesmos dados padrão
"""

