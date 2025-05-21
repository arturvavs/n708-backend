# auth_service/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import re
import json
from datetime import timedelta

app = Flask(__name__)
CORS(app)

# Configuração do JWT
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-dev-key-auth-service')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

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
            ('Admin', 'admin@example.com', generate_password_hash('admin123'), 'cpf', '00000000000', 'admin')
        )
    
    # Verificar se já existe um usuário organization
    org = cursor.execute('SELECT * FROM users WHERE role = ?', ('organization',)).fetchone()
    if not org:
        # Criar usuário organization padrão
        cursor.execute(
            'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
            ('Prefeitura', 'prefeitura@example.com', generate_password_hash('org123'), 'cnpj', '00000000000000', 'organization')
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
        hashed_password = generate_password_hash(data['password'])
        
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
                data.get('role', 'user')  # Por padrão, o papel é 'user'
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
        
        if not user or not check_password_hash(user['password'], data['password']):
            conn.close()
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        # Converter o objeto Row para dicionário
        user_data = dict(user)
        
        # Remover a senha do objeto de resposta
        user_data.pop('password', None)
        
        # Criar o token JWT
        access_token = create_access_token(identity={
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "document": user['document'],
            "document_type": user['document_type'],
            "role": user['role']
        })
        
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
    current_user = get_jwt_identity()
    
    return jsonify({
        "user": current_user
    }), 200

# Rota para listar todos os usuários (apenas para admin)
@app.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    current_user = get_jwt_identity()
    
    # Verificar se o usuário tem permissão de admin
    if current_user.get('role') != 'admin':
        return jsonify({"error": "Não autorizado"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
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
        # Usar a função do JWT Extended para decodificar o token
        from flask_jwt_extended.utils import decode_token
        user_data = decode_token(data['token'])
        
        # Se chegou aqui, o token é válido
        return jsonify({
            "valid": True,
            "user": user_data['sub']  # 'sub' contém o identity que passamos na criação do token
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