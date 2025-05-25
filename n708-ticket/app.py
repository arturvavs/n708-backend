from flask import Flask, request, jsonify, send_from_directory
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import sqlite3
import os
import uuid
import json
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-dev-key-auth-service')
jwt = JWTManager(app)

DB_PATH = os.environ.get('DB_PATH', 'tickets.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            image_url TEXT,
            address TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_token(token):
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/verify-token",
            json={"token": token},
            timeout=5
        )
        if response.status_code == 200:
            user_data = response.json()['user']
            # Se user_data for string JSON, parse:
            if isinstance(user_data, str):
                user_data = json.loads(user_data)
            return user_data, None
        else:
            return None, response.json().get('error', 'Token inválido')
    except requests.RequestException as e:
        return None, f"Erro ao verificar token: {str(e)}"

def auth_required():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, "Token não fornecido"
    token = auth_header.split(' ')[1]
    return verify_token(token)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'online', 'service': 'tickets'})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/tickets', methods=['GET'])
def get_tickets():
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    status = request.args.get('status')
    location = request.args.get('location')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = 'SELECT * FROM tickets'
        params = []
        conditions = []

        if user['role'] == 'user':
            conditions.append('user_id = ?')
            params.append(user['id'])

        if status:
            conditions.append('status = ?')
            params.append(status)

        if location:
            conditions.append('address LIKE ?')
            params.append(f'%{location}%')

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        query += ' ORDER BY created_at DESC'
        tickets = cursor.execute(query, params).fetchall()
        result = [dict(ticket) for ticket in tickets]

        conn.close()
        return jsonify({"tickets": result}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/tickets', methods=['POST'])
def create_ticket():
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    image_url = None
    if request.content_type and 'multipart/form-data' in request.content_type:
        if 'title' not in request.form or 'description' not in request.form or 'address' not in request.form:
            return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400
        
        title = request.form['title']
        description = request.form['description']
        address = request.form['address']

        if 'image' in request.files:
            image = request.files['image']
            if image and allowed_file(image.filename):
                filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(image.filename)[1])
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                image.save(image_path)
                image_url = f'/uploads/{filename}'
    else:
        data = request.get_json()
        if not data or 'title' not in data or 'description' not in data or 'address' not in data:
            return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400
        
        title = data['title']
        description = data['description']
        address = data['address']
        image_url = data.get('image_url')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO tickets (title, description, user_id, image_url, address, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, user['id'], image_url, address, 'aberto'))
        conn.commit()
        ticket_id = cursor.lastrowid
        conn.close()
        return jsonify({"message": "Ticket criado com sucesso", "id": ticket_id}), 201
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        if user['role'] == 'user' and ticket['user_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403

        user_info = {
            "id": ticket['user_id'],
            "name": "Nome do Usuário",
            "email": "email@example.com"
        }

        ticket_dict = dict(ticket)
        ticket_dict['user'] = user_info

        conn.close()
        return jsonify({"ticket": ticket_dict}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/tickets/<int:ticket_id>/status', methods=['PATCH'])
def update_ticket_status(ticket_id):
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    if user['role'] not in ['admin', 'organization']:
        return jsonify({"error": "Não autorizado"}), 403

    data = request.get_json()
    if not data or 'status' not in data or data['status'] not in ['aberto', 'em andamento', 'resolvido']:
        return jsonify({"error": "Status inválido"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        cursor.execute('UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (data['status'], ticket_id))
        conn.commit()
        conn.close()

        return jsonify({"message": "Status atualizado com sucesso", "ticket_id": ticket_id, "new_status": data['status']}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/tickets/<int:ticket_id>', methods=['PUT'])
def update_ticket(ticket_id):
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        if user['role'] == 'user' and ticket['user_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403

        image_url = ticket['image_url']

        if request.content_type and 'multipart/form-data' in request.content_type:
            if 'title' not in request.form or 'description' not in request.form or 'address' not in request.form:
                conn.close()
                return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400

            title = request.form['title']
            description = request.form['description']
            address = request.form['address']

            if 'image' in request.files:
                image = request.files['image']
                if image and allowed_file(image.filename):
                    filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(image.filename)[1])
                    image_path = os.path.join(UPLOAD_FOLDER, filename)
                    image.save(image_path)

                    # Remove imagem antiga
                    if ticket['image_url']:
                        try:
                            old_image_path = os.path.join(UPLOAD_FOLDER, os.path.basename(ticket['image_url']))
                            if os.path.exists(old_image_path):
                                os.remove(old_image_path)
                        except Exception:
                            pass

                    image_url = f'/uploads/{filename}'
        else:
            data = request.get_json()
            if not data or 'title' not in data or 'description' not in data or 'address' not in data:
                conn.close()
                return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400

            title = data['title']
            description = data['description']
            address = data['address']
            image_url = data.get('image_url', image_url)

        cursor.execute('''
            UPDATE tickets
            SET title = ?, description = ?, image_url = ?, address = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title, description, image_url, address, ticket_id))
        conn.commit()
        conn.close()

        return jsonify({"message": "Ticket atualizado com sucesso", "ticket_id": ticket_id}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/tickets/<int:ticket_id>', methods=['DELETE'])
def delete_ticket(ticket_id):
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    if user['role'] not in ['admin', 'organization']:
        return jsonify({"error": "Não autorizado"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        if ticket['image_url']:
            try:
                image_path = os.path.join(UPLOAD_FOLDER, os.path.basename(ticket['image_url']))
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception:
                pass

        cursor.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
        conn.commit()
        conn.close()

        return jsonify({"message": "Ticket removido com sucesso"}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
