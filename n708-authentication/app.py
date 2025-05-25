from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_jwt_extended.utils import decode_token
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import re
import json
from datetime import timedelta

app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-dev-key-auth-service')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

DB_PATH = os.environ.get('DB_PATH', 'users.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
    
    admin = cursor.execute('SELECT * FROM users WHERE role = ?', ('admin',)).fetchone()
    if not admin:
        cursor.execute(
            'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
            ('Admin', 'admin@example.com', generate_password_hash('admin123'), 'cpf', '00000000000', 'admin')
        )
    
    org = cursor.execute('SELECT * FROM users WHERE role = ?', ('organization',)).fetchone()
    if not org:
        cursor.execute(
            'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
            ('Prefeitura', 'prefeitura@example.com', generate_password_hash('org123'), 'cnpj', '00000000000000', 'organization')
        )
    
    conn.commit()
    conn.close()

init_db()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'online',
        'service': 'authentication'
    })

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    required_fields = ['name', 'email', 'password', 'documentType', 'document']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"O campo {field} é obrigatório"}), 400
    
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, data['email']):
        return jsonify({"error": "E-mail inválido"}), 400
    
    document_type = data['documentType']
    document = data['document']
    document = re.sub(r'\D', '', document)
    
    if document_type == 'cpf' and len(document) != 11:
        return jsonify({"error": "CPF inválido"}), 400
    elif document_type == 'cnpj' and len(document) != 14:
        return jsonify({"error": "CNPJ inválido"}), 400
    
    address = data.get('address', {})
    address_json = json.dumps(address) if address else '{}'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
        if user:
            conn.close()
            return jsonify({"error": "E-mail já cadastrado"}), 409
        
        user = cursor.execute('SELECT * FROM users WHERE document = ?', (document,)).fetchone()
        if user:
            conn.close()
            return jsonify({"error": f"{'CPF' if document_type == 'cpf' else 'CNPJ'} já cadastrado"}), 409
        
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
                data.get('role', 'user')
            )
        )
        conn.commit()
        
        user_id = cursor.lastrowid
        
        conn.close()
        return jsonify({"message": "Usuário cadastrado com sucesso", "id": user_id}), 201
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if 'email' not in data or 'password' not in data:
        return jsonify({"error": "E-mail e senha são obrigatórios"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
        
        if not user or not check_password_hash(user['password'], data['password']):
            conn.close()
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        user_data = dict(user)
        
        user_data.pop('password', None)
        
        access_token = create_access_token(
            identity=str(user["id"]),
            additional_claims={
                "email": user["email"],
                "name": user["name"],
                "document": user["document"],
                "document_type": user["document_type"],
                "role": user["role"]
            }
        )
        
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

@app.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    claims = get_jwt()
    
    return jsonify({
        "user": {
            "id": user_id,
            "email": claims["email"],
            "name": claims["name"],
            "document": claims["document"],
            "document_type": claims["document_type"],
            "role": claims["role"]
        }
    }), 200

@app.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    claims = get_jwt()

    if claims.get('role') != 'admin':
        return jsonify({"error": "Não autorizado"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        users = cursor.execute('SELECT id, name, email, document_type, document, role FROM users').fetchall()
        
        users_list = [dict(user) for user in users]
        
        conn.close()
        return jsonify({"users": users_list}), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/verify-token', methods=['POST'])
def verify_token():
    data = request.get_json()
    
    if 'token' not in data:
        return jsonify({"error": "Token não fornecido"}), 400
    
    try:
        user_data = decode_token(data['token'])
        
        user_claims = {
            "id": user_data['sub'],
            "email": user_data.get('email'),
            "name": user_data.get('name'),
            "document": user_data.get('document'),
            "document_type": user_data.get('document_type'),
            "role": user_data.get('role'),
        }
        
        return jsonify({
            "valid": True,
            "user": user_claims
        }), 200
    
    except Exception as e:
        return jsonify({
            "valid": False,
            "error": str(e)
        }), 401

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    try:
        port = int(os.getenv('PORT', '5001'))
    except ValueError:
        print("⚠️  Porta inválida. Usando 5001 como padrão.")
        port = 5001

    debug_mode = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)