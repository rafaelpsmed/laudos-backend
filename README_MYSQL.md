# 🗄️ Configuração MySQL - Laudos Backend

## 📋 Configuração Rápida para MySQL

### 1. Instalar MySQL (se não tiver)
```bash
# Windows
# Baixe e instale do site oficial: https://dev.mysql.com/downloads/installer/

# Ubuntu/Debian
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
sudo mysql_secure_installation
```

### 2. Criar Banco de Dados
```sql
-- Conectar ao MySQL
mysql -u root -p

-- Criar banco de dados
CREATE DATABASE laudos_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Criar usuário (opcional, se quiser usar usuário específico)
CREATE USER 'laudos_user'@'localhost' IDENTIFIED BY 'sua_senha_segura';
GRANT ALL PRIVILEGES ON laudos_db.* TO 'laudos_user'@'localhost';
FLUSH PRIVILEGES;

-- Sair
EXIT;
```

### 3. Configurar Ambiente
```bash
cd laudos_backend

# Copiar configurações de desenvolvimento MySQL
cp env_development.txt .env

# Verificar se está correto
cat .env
```

### 4. Testar Conexão MySQL
```bash
# Testar conexão
python test_mysql_connection.py

# Se der erro, diagnosticar:
# - Verificar se MySQL está rodando
# - Verificar credenciais
# - Verificar se o banco existe
```

### 5. Executar Migrações
```bash
# Instalar dependências
pip install -r requirements.txt

# Executar migrações
python manage.py migrate
```

### 6. Iniciar Servidor
```bash
# Usar script automático
python start_dev_server.py

# Ou comando direto
python manage.py runserver 8000
```

## ✅ Verificação

Após executar os passos acima, você deve ver:
```
🗄️  Detectado MySQL. Testando conexão...
✅ Conexão MySQL estabelecida com sucesso!
✅ Configuração MySQL detectada e validada.
📊 Executando migrações...
✅ Migrações executadas com sucesso!
🚀 SERVIDOR DJANGO INICIADO COM SUCESSO
```

## 🔧 Configuração Personalizada

### Arquivo .env para Produção
```bash
# Configurações de produção
SECRET_KEY=sua-chave-segura-muito-longa-aqui
DEBUG=False
ALLOWED_HOSTS=seudominio.com,www.seudominio.com

# Banco MySQL de produção
DB_ENGINE=django.db.backends.mysql
DB_NAME=laudos_prod
DB_USER=laudos_user
DB_PASSWORD=sua_senha_muito_segura
DB_HOST=localhost
DB_PORT=3306
```

### Otimização MySQL
```sql
-- Configurações recomendadas no my.cnf
[mysqld]
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
innodb_buffer_pool_size=1G
max_connections=100
query_cache_size=128M
```

## 🚨 Problemas Comuns

### ❌ "Can't connect to MySQL server"
```bash
# Verificar se MySQL está rodando
sudo systemctl status mysql

# Iniciar MySQL
sudo systemctl start mysql

# Ou no Windows
# Services -> MySQL -> Start
```

### ❌ "Access denied for user"
```sql
-- Resetar senha do root
ALTER USER 'root'@'localhost' IDENTIFIED BY 'nova_senha';
FLUSH PRIVILEGES;
```

### ❌ "Unknown database"
```sql
CREATE DATABASE laudos_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### ❌ "Authentication plugin error"
```sql
-- Para MySQL 8.0+
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'senha';
FLUSH PRIVILEGES;
```

## 📊 Comandos Úteis

### Verificar tabelas criadas
```bash
python manage.py shell
```
```python
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    for table in tables:
        print(table[0])
```

### Backup do banco
```bash
mysqldump -u root -p laudos_db > backup_laudo.sql
```

### Restore do banco
```bash
mysql -u root -p laudos_db < backup_laudo.sql
```

## 🔒 Segurança MySQL

### Configurações importantes:
1. **Nunca use root em produção**
2. **Use senhas fortes**
3. **Configure firewall**
4. **Limite conexões remotas**
5. **Monitore logs de segurança**

### Comando para verificar usuários:
```sql
SELECT User, Host FROM mysql.user;
```

---

**🎉 Agora você tem MySQL configurado corretamente com o Django!**
