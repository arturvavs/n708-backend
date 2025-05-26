# auth_service/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import sqlite3
import os
import re
import json
import hashlib
from datetime import timedelta

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuração do JWT
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-dev-key-auth-service')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

# Caminho do banco de dados
DB_PATH = os.environ.get('DB_PATH', 'users.db')

def simple_hash_password(password):
    """Hash simples usando SHA-256 para compatibilidade"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verifica senha usando hash simples"""
    return simple_hash_password(password) == hashed

# Caminho do banco de dados
DB_PATH = os.environ.get('DB_PATH', 'users.db')

# Função para obter conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Inicialização do banco de dados
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Criação da tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
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
    
    # Verificar se já existe um usuário admin
    admin = cursor.execute('SELECT * FROM users WHERE role = ?', ('admin',)).fetchone()
    if not admin:
        # Criar usuário admin padrão
        cursor.execute(
            'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
            ('Admin', 'admin@example.com', simple_hash_password('admin123'), 'cpf', '00000000000', 'admin')
        )
    
    # Verificar se já existe usuários de exemplo
    user_count = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if user_count < 3:
        # Criar usuários de exemplo
        examples = [
            ('João Silva', 'joao@example.com', 'cpf', '12345678901', 'user'),
            ('Empresa ABC Ltda', 'empresa@example.com', 'cnpj', '12345678000195', 'organization'),
        ]
        
        for name, email, doc_type, document, role in examples:
            existing = cursor.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if not existing:
                cursor.execute(
                    'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
                    (name, email, simple_hash_password('123456'), doc_type, document, role)
                )
    
    conn.commit()
    conn.close()

# Inicializar o banco de dados na inicialização da aplicação
init_db()

# Rota para verificação de saúde
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'online',
        'service': 'auth_service'
    })

# Rota de registro de usuário
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validação dos dados básicos
    required_fields = ['name', 'email', 'password', 'documentType', 'document']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"O campo {field} é obrigatório"}), 400
    
    # Validação de e-mail
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, data['email']):
        return jsonify({"error": "E-mail inválido"}), 400
    
    # Validação de documento (CPF ou CNPJ)
    document_type = data['documentType']
    document = data['document']
    # Remover caracteres não numéricos
    document = re.sub(r'\D', '', document)
    
    if document_type == 'cpf' and len(document) != 11:
        return jsonify({"error": "CPF inválido"}), 400
    elif document_type == 'cnpj' and len(document) != 14:
        return jsonify({"error": "CNPJ inválido"}), 400
    
    # Processar endereço (se fornecido)
    address = data.get('address', {})
    address_json = json.dumps(address) if address else '{}'
    
    # Definir role baseado no tipo de documento
    if document_type == 'cpf':
        role = 'user'
    elif document_type == 'cnpj':
        role = 'organization'
    else:
        role = data.get('role', 'user')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se o e-mail já existe
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
        if user:
            conn.close()
            return jsonify({"error": "E-mail já cadastrado"}), 409
        
        # Verificar se o documento já existe
        user = cursor.execute('SELECT * FROM users WHERE document = ?', (document,)).fetchone()
        if user:
            conn.close()
            return jsonify({"error": f"{'CPF' if document_type == 'cpf' else 'CNPJ'} já cadastrado"}), 409
        
        # Criar o novo usuário
        hashed_password = simple_hash_password(data['password'])
        
        cursor.execute(
            '''
            INSERT INTO users 
            (name, email, password, document_type, document, address, role) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data['name'], 
                data['email'], 
                hashed_password, 
                document_type,
                document,
                address_json,
                role
            )
        )
        conn.commit()
        
        # Obter o ID do usuário recém-criado
        user_id = cursor.lastrowid
        
        conn.close()
        return jsonify({"message": "Usuário cadastrado com sucesso", "id": user_id}), 201
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota de login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    # Validação dos dados
    if 'email' not in data or 'password' not in data:
        return jsonify({"error": "E-mail e senha são obrigatórios"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Buscar o usuário pelo e-mail
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
        
        if not user or not verify_password(data['password'], user['password']):
            conn.close()
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        # Criar o token JWT
        access_token = create_access_token(identity=str(user['id']))
        
        conn.close()
        return jsonify({
            "message": "Login realizado com sucesso",
            "token": access_token,
            "user": {
                "id": user['id'],
                "name": user['name'],
                "email": user['email'],
                "document": user['document'],
                "document_type": user['document_type'],
                "role": user['role']
            }
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para obter perfil do usuário
@app.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_user_id = get_jwt_identity()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        user = cursor.execute(
            'SELECT id, name, email, document, document_type, role FROM users WHERE id = ?', 
            (current_user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        conn.close()
        return jsonify({
            "user": dict(user)
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para obter informações de um usuário específico (usado pelos outros serviços)
@app.route('/user/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        user = cursor.execute(
            'SELECT id, name, email, document, document_type, role FROM users WHERE id = ?', 
            (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        conn.close()
        return jsonify({
            "user": dict(user)
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para listar todos os usuários (apenas para admin)
@app.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    current_user_id = get_jwt_identity()
    
    # Verificar se o usuário tem permissão de admin
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        current_user = cursor.execute('SELECT role FROM users WHERE id = ?', (current_user_id,)).fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403
        
        users = cursor.execute('SELECT id, name, email, document_type, document, role FROM users').fetchall()
        
        # Converter os objetos Row para dicionários
        users_list = [dict(user) for user in users]
        
        conn.close()
        return jsonify({"users": users_list}), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para verificar token (usada por outros serviços)
@app.route('/verify-token', methods=['POST'])
def verify_token():
    data = request.get_json()
    
    if 'token' not in data:
        return jsonify({"error": "Token não fornecido"}), 400
    
    try:
        from flask_jwt_extended.utils import decode_token
        decoded = decode_token(data['token'])
        
        # O 'sub' agora contém apenas o user_id como string
        user_id = decoded['sub']
        
        return jsonify({
            "valid": True,
            "user": user_id
        }), 200
    except Exception as e:
        return jsonify({
            "valid": False,
            "error": str(e)
        }), 401

# Tratamento de erros
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    # Obter porta do ambiente ou usar 5001 por padrão
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)