# 🔐 Guia de Segurança - Laudos Backend

Este documento explica como configurar corretamente a segurança do projeto Laudos Backend.

## 📋 Pré-requisitos

- Python 3.8+
- MySQL ou PostgreSQL (recomendado para produção)
- Ambiente virtual configurado

## 🚀 Configuração Inicial

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 2. Gerar SECRET_KEY Segura

```bash
python generate_secret_key.py
```

Copie a SECRET_KEY gerada para usar no próximo passo.

### 3. Configurar Variáveis de Ambiente

#### **Opção A: Arquivo .env (Recomendado)**

1. Copie o arquivo de exemplo:
```bash
cp env_example.txt .env
```

2. Edite o arquivo `.env` com suas configurações reais:
```bash
# Edite com suas informações reais
SECRET_KEY=sua-secret-key-gerada-aqui
DEBUG=False
ALLOWED_HOSTS=seudominio.com,www.seudominio.com

# Banco de dados
DB_ENGINE=django.db.backends.postgresql
DB_NAME=nome_do_banco
DB_USER=usuario_do_banco
DB_PASSWORD=senha_segura_aqui
DB_HOST=localhost
DB_PORT=5432

# APIs (use apenas chaves de desenvolvimento/teste)
OPENAI_API_KEY=sk-proj-sua-chave-aqui
OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
ANTHROPIC_API_KEY=sk-ant-api03-sua-chave-aqui
```

#### **Opção B: Variáveis de Ambiente do Sistema**

Configure as variáveis no sistema operacional:

**Windows (PowerShell):**
```powershell
$env:SECRET_KEY="sua-secret-key-aqui"
$env:DEBUG="False"
$env:DB_PASSWORD="sua-senha-segura"
```

**Linux/macOS:**
```bash
export SECRET_KEY="sua-secret-key-aqui"
export DEBUG="False"
export DB_PASSWORD="sua-senha-segura"
```

## 🔒 Configurações de Segurança

### SECRET_KEY
- **CRÍTICA**: Deve ser única e secreta
- Use o script `generate_secret_key.py` para gerar uma chave segura
- **Nunca** use a chave padrão do Django
- **Nunca** commite no Git

### DEBUG
- **Produção**: Sempre `False`
- **Desenvolvimento**: `True` apenas localmente

### ALLOWED_HOSTS
- Liste apenas domínios confiáveis
- Use `['*']` apenas em desenvolvimento
- Em produção, especifique domínios exatos

### Banco de Dados
- Use PostgreSQL em produção (mais seguro)
- Use senhas fortes (mínimo 12 caracteres)
- Configure conexões SSL quando possível
- Use usuários com permissões mínimas

## 🛡️ Recursos de Segurança Ativos

### 1. Validação de Variáveis
- Verifica se variáveis obrigatórias estão presentes
- Mostra avisos para configurações inseguras

### 2. Headers de Segurança
Quando `DEBUG=False`, ativa automaticamente:
- `SECURE_BROWSER_XSS_FILTER`
- `SECURE_CONTENT_TYPE_NOSNIFF`
- `SECURE_HSTS_SECONDS`
- `SECURE_SSL_REDIRECT`
- Cookies seguros (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)

### 3. Proteção de Dados Sensíveis
- Senhas não são exibidas nos logs
- Apenas primeiros 8 caracteres são mostrados
- Dados criptografados quando aplicável

## 📊 Verificação de Segurança

Ao iniciar o servidor, você verá:

```
✅ SECRET_KEY: dj4k8m2p...
✅ DEBUG: False
✅ DB_PASSWORD: ****
✅ ALLOWED_HOSTS: 3 hosts
✅ Banco de dados: postgresql

🚀 SERVIDOR DJANGO INICIADO COM SUCESSO
```

## 🚨 Avisos de Segurança

### Em Desenvolvimento
```
⚠️  MODO DESENVOLVIMENTO ATIVADO
⚠️  AVISO: Variável DB_PASSWORD não configurada. Usando SQLite como fallback.
```

### Problemas Críticos
```
❌ SECRET_KEY: usando valor padrão inseguro!
❌ DEBUG: deve ser False em produção!
```

## 🔧 Manutenção de Segurança

### Atualizações Regulares
```bash
pip install --upgrade -r requirements.txt
pip install --upgrade Django djangorestframework
```

### Rotação de Chaves
1. Gere nova SECRET_KEY
2. Atualize todas as sessões ativas
3. Reinicie o servidor

### Monitoramento
- Monitore logs por tentativas de acesso suspeitas
- Configure alertas para erros de segurança
- Faça backup regular das configurações seguras

## 🚫 O Que NÃO Fazer

### ❌ Nunca
- Commite arquivos `.env` no Git
- Use senhas fracas
- Configure `DEBUG=True` em produção
- Use `ALLOWED_HOSTS = ['*']` em produção
- Compartilhe SECRET_KEY

### ❌ Evite
- Armazenar senhas em texto plano
- Usar chaves de API de produção em desenvolvimento
- Configurar permissões excessivas no banco

## 📞 Suporte

Se encontrar problemas de segurança:
1. Verifique os logs do servidor
2. Confirme se todas as variáveis estão configuradas
3. Execute `python manage.py check --settings=laudos_backend.settings`

## 🔗 Recursos Adicionais

- [Django Security Checklist](https://docs.djangoproject.com/en/stable/topics/security/)
- [OWASP Security Guidelines](https://owasp.org/www-project-top-ten/)
- [12 Factor App](https://12factor.net/config)
