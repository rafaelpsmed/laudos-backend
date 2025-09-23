#!/usr/bin/env python
"""
Script para testar a configuração de segurança do projeto Laudos Backend
Execute: python test_security.py
"""

import os
import sys
from pathlib import Path

def test_security_configuration():
    """
    Testa se a configuração de segurança está adequada
    """
    print("="*60)
    print("🔍 TESTE DE CONFIGURAÇÃO DE SEGURANÇA")
    print("="*60)

    issues = []
    warnings = []

    # Testa se arquivo .env existe
    env_file = Path('.env')
    if not env_file.exists():
        warnings.append("⚠️  Arquivo .env não encontrado. Usando variáveis do sistema.")

    # Testa SECRET_KEY
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        issues.append("❌ SECRET_KEY não configurada!")
    elif secret_key == 'django-insecure-change-this-in-production-to-a-secure-random-key':
        issues.append("❌ SECRET_KEY está usando valor padrão inseguro!")
    elif len(secret_key) < 32:
        warnings.append("⚠️  SECRET_KEY muito curta (mínimo recomendado: 32 caracteres)")

    # Testa DEBUG
    debug = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes', 'on')
    if debug:
        warnings.append("⚠️  DEBUG=True detectado. Certifique-se de que não está em produção!")

    # Testa ALLOWED_HOSTS
    allowed_hosts = os.getenv('ALLOWED_HOSTS', '')
    if not allowed_hosts:
        warnings.append("⚠️  ALLOWED_HOSTS não configurado")
    elif allowed_hosts == '*':
        warnings.append("⚠️  ALLOWED_HOSTS='*' detectado. Use domínios específicos em produção!")

    # Testa configurações do banco
    db_vars = ['DB_ENGINE', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    db_configured = all(os.getenv(var) for var in db_vars)

    if not db_configured:
        missing = [var for var in db_vars if not os.getenv(var)]
        warnings.append(f"⚠️  Variáveis de banco não configuradas: {', '.join(missing)}")

    # Testa APIs de IA
    apis = ['OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY']
    configured_apis = [api for api in apis if os.getenv(api)]

    if not configured_apis:
        warnings.append("⚠️  Nenhuma API de IA configurada")
    else:
        print(f"✅ APIs configuradas: {', '.join(configured_apis)}")

    # Verifica se arquivos sensíveis não estão no Git
    sensitive_files = ['.env', 'secrets.json', 'config/secrets.json']
    for file in sensitive_files:
        if Path(file).exists():
            print(f"⚠️  Arquivo sensível encontrado: {file}")
            print("   Certifique-se de que está no .gitignore!")

    # Resultado final
    print("\n" + "="*60)
    print("📊 RESULTADO DA ANÁLISE")
    print("="*60)

    if issues:
        print("❌ PROBLEMAS CRÍTICOS ENCONTRADOS:")
        for issue in issues:
            print(f"   {issue}")
        print("\n🔧 CORRIJA OS PROBLEMAS ACIMA ANTES DE USAR EM PRODUÇÃO!")
        return False

    if warnings:
        print("⚠️  AVISOS:")
        for warning in warnings:
            print(f"   {warning}")
        print("\n✅ CONFIGURAÇÃO BÁSICA OK, MAS REVEJA OS AVISOS ACIMA")

    if not issues and not warnings:
        print("✅ TODAS AS CONFIGURAÇÕES DE SEGURANÇA ESTÃO CORRETAS!")
        print("🎉 SEU PROJETO ESTÁ SEGURO PARA USO!")

    print("\n" + "="*60)

    return len(issues) == 0

if __name__ == '__main__':
    success = test_security_configuration()
    sys.exit(0 if success else 1)
