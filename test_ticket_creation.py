#!/usr/bin/env python3
"""
Script para testar a criação de tickets
"""

import requests
import json

def test_login():
    """Testa o login e retorna o token"""
    print("=== TESTANDO LOGIN ===")
    
    login_data = {
        "email": "joao@example.com",
        "password": "123456"
    }
    
    response = requests.post(
        "http://localhost:5000/api/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        user = data.get('user')
        print(f"✓ Login bem-sucedido!")
        print(f"Token: {token[:50]}...")
        print(f"Usuário: {user.get('name')} ({user.get('document_type')})")
        return token, user
    else:
        print("❌ Falha no login")
        return None, None

def test_ticket_creation(token):
    """Testa a criação de um ticket"""
    print("\n=== TESTANDO CRIAÇÃO DE TICKET ===")
    
    ticket_data = {
        "title": "Teste de Ticket",
        "description": "Este é um ticket de teste criado via script Python",
        "address": "Rua de Teste, 123 - Centro"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Enviando dados: {ticket_data}")
    print(f"Headers: {headers}")
    
    response = requests.post(
        "http://localhost:5000/api/tickets",
        json=ticket_data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 201:
        data = response.json()
        print(f"✓ Ticket criado com sucesso! ID: {data.get('id')}")
        return data.get('id')
    else:
        print("❌ Falha na criação do ticket")
        return None

def test_endpoint(token):
    """Testa o endpoint de teste"""
    print("\n=== TESTANDO ENDPOINT DE TESTE ===")
    
    test_data = {
        "test": "dados de teste",
        "title": "Teste",
        "description": "Descrição de teste",
        "address": "Endereço de teste"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        "http://localhost:5002/test",  # Direto no serviço de tickets
        json=test_data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

def main():
    print("=== TESTE DE CRIAÇÃO DE TICKETS ===\n")
    
    # Testar login
    token, user = test_login()
    if not token:
        print("❌ Não foi possível fazer login. Verifique se os serviços estão rodando.")
        return
    
    # Testar endpoint de teste
    test_endpoint(token)
    
    # Testar criação de ticket
    ticket_id = test_ticket_creation(token)
    
    if ticket_id:
        print(f"\n✓ Todos os testes passaram! Ticket ID: {ticket_id}")
    else:
        print("\n❌ Falha nos testes")

if __name__ == "__main__":
    main()