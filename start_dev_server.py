#!/usr/bin/env python
"""
Script para iniciar o servidor de desenvolvimento com configurações seguras
"""
import os
import sys
import subprocess
from pathlib import Path

def setup_development():
    """Configura o ambiente de desenvolvimento"""

    print("="*60)
    print("INICIANDO SERVIDOR DE DESENVOLVIMENTO")
    print("="*60)

    # Verifica se existe arquivo .env
    env_file = Path('.env')
    if not env_file.exists():
        print("⚠️  Arquivo .env não encontrado!")
        env_dev = Path('env_development.txt')
        if env_dev.exists():
            print("💡 Usando configurações de desenvolvimento...")
            print("   Renomeie 'env_development.txt' para '.env' para usar as configurações")
        else:
            print("❌ Nenhum arquivo de configuração encontrado!")
            print("   Crie um arquivo .env baseado em env_example.txt")
            return False

    # Testa conexão com MySQL se for MySQL
    from dotenv import load_dotenv
    load_dotenv()

    db_engine = os.getenv('DB_ENGINE', '')
    if 'mysql' in db_engine.lower():
        print("Detectado MySQL. Testando conexao...")
        try:
            import pymysql

            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'user': os.getenv('DB_USER', 'root'),
                'password': os.getenv('DB_PASSWORD', 'proview2'),
                'database': os.getenv('DB_NAME', 'laudos_db'),
                'port': int(os.getenv('DB_PORT', '3306')),
                'charset': 'utf8mb4',
                'autocommit': True
            }

            connection = pymysql.connect(**db_config)
            connection.close()
            print("Conexao MySQL estabelecida com sucesso!")
        except ImportError:
            print("PyMySQL nao instalado. Instalando...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'PyMySQL'], check=True)
            print("PyMySQL instalado!")
        except Exception as e:
            print(f"Erro na conexao MySQL: {e}")
            print("Execute: python test_mysql_connection.py para diagnosticar")
            print("Ou use SQLite temporariamente alterando DB_ENGINE no .env")
            return False

    # Verifica se as migrações foram executadas
    db_name = os.getenv('DB_NAME', 'db.sqlite3')
    db_file = Path(db_name)

    # Para MySQL, sempre tenta executar migrações
    if 'mysql' in db_engine.lower() or not db_file.exists():
        print("Executando migracoes...")
        result = subprocess.run([sys.executable, 'manage.py', 'migrate'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Erro nas migracoes: {result.stderr}")
            return False
        print("Migracoes executadas com sucesso!")

    # Verifica se existe superusuário
    print("Verificando superusuario...")
    result = subprocess.run([sys.executable, 'manage.py', 'shell', '-c',
                           'from django.contrib.auth import get_user_model; User = get_user_model(); print(len(User.objects.filter(is_superuser=True)))'],
                           capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip() == '0':
        print("Nenhum superusuario encontrado!")
        print("Execute: python manage.py createsuperuser")
        print("Ou use as credenciais padrao do sistema se ja configuradas")

    return True

def start_server():
    """Inicia o servidor Django"""
    if not setup_development():
        print("Falha na configuracao. Abortando...")
        return

    print("\n" + "="*60)
    print("INICIANDO SERVIDOR DJANGO")
    print("URL: http://localhost:8000")
    print("Pressione Ctrl+C para parar")
    print("="*60)

    try:
        # Inicia o servidor
        subprocess.run([sys.executable, 'manage.py', 'runserver', '8000'])
    except KeyboardInterrupt:
        print("\nServidor parado pelo usuario")
    except Exception as e:
        print(f"\nErro ao iniciar servidor: {e}")

if __name__ == '__main__':
    start_server()
