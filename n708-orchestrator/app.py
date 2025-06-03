# app.py (Aplicação Orquestradora)
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações de conexão com os microserviços
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')
TICKETS_SERVICE_URL = os.environ.get('TICKETS_SERVICE_URL', 'http://localhost:5002')

# Função para verificar se os serviços estão ativos
def check_services():
    services_status = {
        'auth_service': 'offline',
        'tickets_service': 'offline'
    }
    
    try:
        auth_response = requests.get(f"{AUTH_SERVICE_URL}/health", timeout=2)
        if auth_response.status_code == 200:
            services_status['auth_service'] = 'online'
    except:
        pass
    
    try:
        tickets_response = requests.get(f"{TICKETS_SERVICE_URL}/health", timeout=2)
        if tickets_response.status_code == 200:
            services_status['tickets_service'] = 'online'
    except:
        pass
    
    return services_status

# Rota para verificar a saúde da aplicação orquestradora
@app.route('/health', methods=['GET'])
def health_check():
    services_status = check_services()
    
    return jsonify({
        'status': 'online',
        'services': services_status
    })

# Middleware para extrair o token JWT
def get_token_from_header():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None

# Rotas para o serviço de autenticação
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/register",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de autenticação indisponível: {str(e)}'}), 503

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/login",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de autenticação indisponível: {str(e)}'}), 503

@app.route('/api/auth/profile', methods=['GET'])
def profile():
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/profile",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de autenticação indisponível: {str(e)}'}), 503

# Rotas para o serviço de tickets
@app.route('/api/tickets', methods=['GET'])
def get_tickets():
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    params = request.args.to_dict()
    
    try:
        response = requests.get(
            f"{TICKETS_SERVICE_URL}/tickets",
            params=params,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503

@app.route('/api/tickets', methods=['POST'])
def create_ticket():
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form.to_dict()
        files = {}
        
        if 'image' in request.files:
            image = request.files['image']
            files = {'image': (image.filename, image.read(), image.content_type)}
            
        try:
            response = requests.post(
                f"{TICKETS_SERVICE_URL}/tickets",
                data=data,
                files=files,
                headers={
                    'Authorization': f'Bearer {token}'
                }
            )
            return jsonify(response.json()), response.status_code
        except requests.RequestException as e:
            return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503
    else:
        data = request.get_json()
        
        try:
            response = requests.post(
                f"{TICKETS_SERVICE_URL}/tickets",
                json=data,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
            )
            return jsonify(response.json()), response.status_code
        except requests.RequestException as e:
            return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503

@app.route('/api/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    try:
        response = requests.get(
            f"{TICKETS_SERVICE_URL}/tickets/{ticket_id}",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503

# Nova rota para assumir ticket
@app.route('/api/tickets/<int:ticket_id>/assign', methods=['PATCH'])
def assign_ticket(ticket_id):
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    try:
        response = requests.patch(
            f"{TICKETS_SERVICE_URL}/tickets/{ticket_id}/assign",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503

# Nova rota para finalizar ticket
@app.route('/api/tickets/<int:ticket_id>/complete', methods=['PATCH'])
def complete_ticket(ticket_id):
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    try:
        response = requests.patch(
            f"{TICKETS_SERVICE_URL}/tickets/{ticket_id}/complete",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503

# Nova rota para adicionar feedback
@app.route('/api/tickets/<int:ticket_id>/feedback', methods=['PATCH'])
def add_feedback(ticket_id):
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    data = request.get_json()
    
    try:
        response = requests.patch(
            f"{TICKETS_SERVICE_URL}/tickets/{ticket_id}/feedback",
            json=data,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': f'Serviço de tickets indisponível: {str(e)}'}), 503

# Rota para servir imagens de uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return redirect(f"{TICKETS_SERVICE_URL}/uploads/{filename}")

# Tratamento de erros
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)