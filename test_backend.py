#!/usr/bin/env python
"""
Script para testar se o backend está funcionando
"""
import urllib.request
import urllib.error
import sys

def test_backend():
    try:
        # Testa se o servidor está respondendo
        req = urllib.request.Request('http://localhost:8000/api/')
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print("Backend esta funcionando!")
                print(f"Status: {response.status}")
                return True
            else:
                print(f"Backend respondeu com status: {response.status}")
                return False
    except urllib.error.URLError as e:
        print("Erro de conexao: Backend nao esta rodando ou nao esta acessivel")
        print("Certifique-se de que o servidor Django esta rodando:")
        print("   python manage.py runserver 8000")
        print(f"Detalhes do erro: {e}")
        return False
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return False

if __name__ == '__main__':
    success = test_backend()
    sys.exit(0 if success else 1)
