# app.py (Aplicação Orquestradora)
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app)

# Configurações de conexão com os microserviços
# Em um ambiente de produção, essas URLs viriam de variáveis de ambiente
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
    
    # Encaminha a requisição para o serviço de autenticação
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
    
    # Encaminha a requisição para o serviço de autenticação
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
    
    # Encaminha a requisição para o serviço de autenticação
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
    
    # Extrai parâmetros de query da URL
    params = request.args.to_dict()
    
    # Encaminha a requisição para o serviço de tickets
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
    
    # Verificar se é multipart form data (contém imagem) ou json
    if request.content_type and 'multipart/form-data' in request.content_type:
        # Tratar upload de imagem e outros dados
        data = request.form.to_dict()
        files = {}
        
        if 'image' in request.files:
            image = request.files['image']
            files = {'image': (image.filename, image.read(), image.content_type)}
            
        # Encaminha a requisição para o serviço de tickets
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
        # Requisição JSON padrão
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
    
    # Encaminha a requisição para o serviço de tickets
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

@app.route('/api/tickets/<int:ticket_id>/status', methods=['PATCH'])
def update_ticket_status(ticket_id):
    token = get_token_from_header()
    if not token:
        return jsonify({'error': 'Token não fornecido'}), 401
    
    data = request.get_json()
    
    # Encaminha a requisição para o serviço de tickets
    try:
        response = requests.patch(
            f"{TICKETS_SERVICE_URL}/tickets/{ticket_id}/status",
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
    # Apenas redireciona para o serviço de tickets
    return redirect(f"{TICKETS_SERVICE_URL}/uploads/{filename}")

# Tratamento de erros
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    # Obter porta do ambiente ou usar 5000 por padrão
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)