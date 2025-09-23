#!/usr/bin/env python
"""
Script para gerar uma SECRET_KEY segura para Django
Execute: python generate_secret_key.py
"""

import secrets
import string

def generate_secret_key():
    """
    Gera uma SECRET_KEY segura para Django usando caracteres aleatórios
    """
    # Caracteres permitidos na SECRET_KEY do Django
    chars = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'

    # Gera uma chave de 50 caracteres
    secret_key = ''.join(secrets.choice(chars) for _ in range(50))

    return secret_key

if __name__ == '__main__':
    secret_key = generate_secret_key()
    print("="*60)
    print("🔐 SECRET_KEY GERADA COM SUCESSO!")
    print("="*60)
    print(f"SECRET_KEY={secret_key}")
    print()
    print("📋 Instruções:")
    print("1. Copie a linha acima")
    print("2. Cole no seu arquivo .env")
    print("3. Nunca compartilhe esta chave!")
    print("="*60)
