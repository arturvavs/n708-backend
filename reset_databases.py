#!/usr/bin/env python3
"""
Script para resetar os bancos de dados dos microserviços
Execute este script antes de iniciar os serviços pela primeira vez
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

def reset_auth_database():
    """Reseta o banco de dados de autenticação"""
    print("Resetando banco de dados de autenticação...")
    
    # Remover banco existente
    if os.path.exists('n708-authentication/users.db'):
        os.remove('n708-authentication/users.db')
    
    # Criar novo banco
    conn = sqlite3.connect('n708-authentication/users.db')
    cursor = conn.cursor()
    
    # Criar tabela users
    cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        document_type TEXT NOT NULL,
        document TEXT UNIQUE NOT NULL,
        address TEXT,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Inserir usuários de exemplo
    users = [
        ('Admin Sistema', 'admin@example.com', 'admin123', 'cpf', '00000000000', '{}', 'admin'),
        ('João Silva', 'joao@example.com', '123456', 'cpf', '12345678901', '{}', 'user'),
        ('Maria Santos', 'maria@example.com', '123456', 'cpf', '98765432100', '{}', 'user'),
        ('Empresa ABC Ltda', 'empresa@example.com', '123456', 'cnpj', '12345678000195', '{}', 'organization'),
        ('Construtora XYZ', 'construtora@example.com', '123456', 'cnpj', '98765432000111', '{}', 'organization'),
    ]
    
    for name, email, password, doc_type, document, address, role in users:
        hashed_password = generate_password_hash(password)
        cursor.execute(
            '''INSERT INTO users 
               (name, email, password, document_type, document, address, role) 
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (name, email, hashed_password, doc_type, document, address, role)
        )
    
    conn.commit()
    conn.close()
    print("✓ Banco de autenticação criado com sucesso!")
    
    # Mostrar usuários criados
    print("\n--- Usuários criados ---")
    print("PESSOA FÍSICA:")
    print("  joao@example.com / 123456")
    print("  maria@example.com / 123456")
    print("\nEMPRESA:")
    print("  empresa@example.com / 123456")
    print("  construtora@example.com / 123456")
    print("\nADMIN:")
    print("  admin@example.com / admin123")

def reset_tickets_database():
    """Reseta o banco de dados de tickets"""
    print("\nResetando banco de dados de tickets...")
    
    # Remover banco existente
    if os.path.exists('n708-ticket/tickets.db'):
        os.remove('n708-ticket/tickets.db')
    
    # Criar novo banco
    conn = sqlite3.connect('n708-ticket/tickets.db')
    cursor = conn.cursor()
    
    # Criar tabela tickets
    cursor.execute('''
    CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        assigned_company_id INTEGER,
        image_url TEXT,
        address TEXT NOT NULL,
        status TEXT NOT NULL,
        feedback TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Banco de tickets criado com sucesso!")

def main():
    print("=== RESET DOS BANCOS DE DADOS ===\n")
    
    # Verificar se os diretórios existem
    if not os.path.exists('n708-authentication'):
        print("❌ Diretório 'n708-authentication' não encontrado!")
        return
    
    if not os.path.exists('n708-ticket'):
        print("❌ Diretório 'n708-ticket' não encontrado!")
        return
    
    try:
        reset_auth_database()
        reset_tickets_database()
        
        print("\n=== RESET CONCLUÍDO COM SUCESSO! ===")
        print("\nPróximos passos:")
        print("1. Inicie o serviço de autenticação: cd n708-authentication && python app.py")
        print("2. Inicie o serviço de tickets: cd n708-ticket && python app.py")
        print("3. Inicie o orquestrador: cd n708-orchestrator && python app.py")
        print("4. Inicie o frontend React: npm start")
        
    except Exception as e:
        print(f"❌ Erro durante o reset: {str(e)}")

if __name__ == "__main__":
    main()