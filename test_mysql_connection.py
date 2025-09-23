#!/usr/bin/env python
"""
Script para testar a conexão com MySQL
"""
import os
import sys
import pymysql
from dotenv import load_dotenv

def test_mysql_connection():
    """Testa a conexão com o banco MySQL"""

    # Carregar variáveis de ambiente
    load_dotenv()

    print("="*50)
    print("🧪 TESTANDO CONEXÃO COM MYSQL")
    print("="*50)

    # Configurações do banco
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', 'proview2'),
        'database': os.getenv('DB_NAME', 'laudos_db'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'charset': 'utf8mb4',
        'autocommit': True
    }

    print(f"📍 Host: {db_config['host']}:{db_config['port']}")
    print(f"👤 Usuário: {db_config['user']}")
    print(f"🗄️  Banco: {db_config['database']}")

    try:
        # Tentar conectar
        print("🔌 Tentando conectar...")
        connection = pymysql.connect(**db_config)

        if connection:
            print("✅ Conexão estabelecida com sucesso!")

            # Testar se o banco existe
            with connection.cursor() as cursor:
                cursor.execute("SELECT DATABASE() as current_db")
                result = cursor.fetchone()
                print(f"✅ Banco atual: {result[0]}")

                # Verificar tabelas existentes
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f"📊 Tabelas encontradas: {len(tables)}")

                if tables:
                    print("📋 Lista de tabelas:")
                    for table in tables[:10]:  # Mostra apenas as primeiras 10
                        print(f"   - {table[0]}")
                    if len(tables) > 10:
                        print(f"   ... e mais {len(tables) - 10} tabelas")

            connection.close()
            print("✅ Conexão fechada com sucesso!")
            return True

    except pymysql.Error as e:
        print(f"❌ Erro na conexão MySQL: {e}")

        # Sugestões de solução
        if "Access denied" in str(e):
            print("💡 Possíveis soluções:")
            print("   - Verifique usuário e senha")
            print("   - Verifique se o usuário tem permissões no banco")
            print("   - Execute: CREATE USER 'root'@'localhost' IDENTIFIED BY 'proview2';")

        elif "Unknown database" in str(e):
            print("💡 Possíveis soluções:")
            print("   - Verifique se o banco 'laudos_db' existe")
            print("   - Execute: CREATE DATABASE laudos_db;")

        elif "Can't connect" in str(e):
            print("💡 Possíveis soluções:")
            print("   - Verifique se o MySQL está rodando")
            print("   - Execute: sudo service mysql start")
            print("   - Verifique se a porta 3306 está aberta")

        return False

    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

if __name__ == '__main__':
    success = test_mysql_connection()
    print("\n" + "="*50)
    if success:
        print("🎉 MYSQL CONFIGURADO CORRETAMENTE!")
        print("✅ Você pode usar o Django com MySQL")
    else:
        print("⚠️  PROBLEMA NA CONFIGURAÇÃO DO MYSQL")
        print("❌ Verifique as configurações acima")
    print("="*50)
    sys.exit(0 if success else 1)
