# tickets_service/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import uuid
import json
import requests
from werkzeug.utils import secure_filename
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações
DB_PATH = os.environ.get('DB_PATH', 'tickets.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')

# Garantir que o diretório de uploads existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Extensões permitidas para imagens
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Função para obter conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Inicialização do banco de dados
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Criação da tabela de tickets
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
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

# Inicializar o banco de dados na inicialização da aplicação
init_db()

# Função para verificar extensão de arquivo permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Função para verificar token JWT e obter informações do usuário
def verify_token(token):
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/verify-token",
            json={"token": token},
            timeout=5
        )
        if response.status_code == 200:
            user_id = response.json()['user']
            
            # Buscar informações completas do usuário
            user_response = requests.get(
                f"{AUTH_SERVICE_URL}/user/{user_id}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=5
            )
            
            if user_response.status_code == 200:
                user_data = user_response.json()['user']
                return user_data, None
            else:
                # Fallback se não conseguir buscar dados do usuário
                return {
                    'id': int(user_id),
                    'role': 'user',
                    'document_type': 'cpf'
                }, None
        else:
            return None, response.json().get('error', 'Token inválido')
    except requests.RequestException as e:
        return None, f"Erro ao verificar token: {str(e)}"

# Cache simples para informações de usuários (evitar muitas chamadas à API)
users_cache = {}

def get_user_info(user_id, token):
    """Busca informações do usuário, usando cache quando possível"""
    if user_id in users_cache:
        return users_cache[user_id]
    
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/user/{user_id}",
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        
        if response.status_code == 200:
            user_data = response.json()['user']
            users_cache[user_id] = user_data
            return user_data
        else:
            # Retornar dados mínimos se não conseguir buscar
            fallback_data = {
                'id': user_id,
                'name': 'Usuário desconhecido',
                'email': ''
            }
            users_cache[user_id] = fallback_data
            return fallback_data
    except requests.RequestException:
        # Retornar dados mínimos em caso de erro
        fallback_data = {
            'id': user_id,
            'name': 'Usuário desconhecido',
            'email': ''
        }
        users_cache[user_id] = fallback_data
        return fallback_data

# Middleware para extrair e verificar token
def auth_required():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, "Token não fornecido"
    
    token = auth_header.split(' ')[1]
    return verify_token(token)

# Rota para verificação de saúde
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'online',
        'service': 'tickets_service'
    })

# Rota de teste para debug
@app.route('/test', methods=['POST'])
def test_endpoint():
    try:
        logger.info("=== TESTE DE REQUISIÇÃO ===")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        if request.content_type and 'multipart/form-data' in request.content_type:
            logger.info(f"Form data: {dict(request.form)}")
            logger.info(f"Files: {list(request.files.keys())}")
        else:
            logger.info(f"Raw data: {request.get_data()}")
            try:
                json_data = request.get_json()
                logger.info(f"JSON data: {json_data}")
            except:
                logger.info("Não foi possível parse JSON")
        
        return jsonify({"message": "Teste OK", "received": True}), 200
    except Exception as e:
        logger.error(f"Erro no teste: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Rota para servir imagens de uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Rota para obter todos os tickets (com filtros baseados no tipo de usuário)
@app.route('/tickets', methods=['GET'])
def get_tickets():
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401
    
    # Parâmetros de filtro
    status = request.args.get('status')
    location = request.args.get('location')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Query básica sem JOIN com tabela users
        query = 'SELECT * FROM tickets'
        params = []
        conditions = []
        
        # Lógica de filtros baseada no tipo de usuário
        if user.get('document_type') == 'cpf':
            # Pessoa Física: só vê seus próprios tickets
            conditions.append('user_id = ?')
            params.append(user['id'])
        elif user.get('document_type') == 'cnpj':
            # Empresa: vê tickets em aberto OU tickets que ela assumiu
            conditions.append('(status = ? OR assigned_company_id = ?)')
            params.extend(['aberto', user['id']])
        else:
            # Admin: vê todos os tickets
            pass
        
        # Filtros adicionais
        if status:
            conditions.append('status = ?')
            params.append(status)
        
        if location:
            conditions.append('address LIKE ?')
            params.append(f'%{location}%')
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        # Ordenar por data de criação (mais recentes primeiro)
        query += ' ORDER BY created_at DESC'
        
        tickets = cursor.execute(query, params).fetchall()
        
        # Converter para lista de dicionários e buscar informações dos usuários
        result = []
        for ticket in tickets:
            ticket_dict = dict(ticket)
            
            # Buscar informações do usuário que criou o ticket
            user_info = get_user_info(ticket['user_id'], request.headers.get('Authorization', '').replace('Bearer ', ''))
            ticket_dict['user'] = {
                'id': ticket['user_id'],
                'name': user_info.get('name', 'Usuário desconhecido'),
                'email': user_info.get('email', '')
            }
            
            # Buscar informações da empresa responsável (se houver)
            if ticket['assigned_company_id']:
                company_info = get_user_info(ticket['assigned_company_id'], request.headers.get('Authorization', '').replace('Bearer ', ''))
                ticket_dict['assigned_company'] = {
                    'id': ticket['assigned_company_id'],
                    'name': company_info.get('name', 'Empresa desconhecida'),
                    'email': company_info.get('email', '')
                }
            else:
                ticket_dict['assigned_company'] = None
            
            result.append(ticket_dict)
        
        conn.close()
        return jsonify({"tickets": result}), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para criar um novo ticket
@app.route('/tickets', methods=['POST'])
def create_ticket():
    try:
        logger.info(f"Recebendo requisição para criar ticket")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Verificar autenticação
        user, error = auth_required()
        if error:
            logger.error(f"Erro de autenticação: {error}")
            return jsonify({"error": error}), 401
        
        logger.info(f"Usuário autenticado: {user}")
        
        # Apenas pessoas físicas podem criar tickets
        if user.get('document_type') != 'cpf':
            logger.error(f"Usuário não é pessoa física: {user.get('document_type')}")
            return jsonify({"error": "Apenas pessoas físicas podem criar tickets"}), 403
        
        # Verificar se é multipart form data ou json
        if request.content_type and 'multipart/form-data' in request.content_type:
            logger.info("Processando como multipart/form-data")
            # Formulário com possível upload de imagem
            if 'title' not in request.form or 'description' not in request.form or 'address' not in request.form:
                logger.error(f"Campos obrigatórios ausentes no form: {list(request.form.keys())}")
                return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400
            
            title = request.form['title']
            description = request.form['description']
            address = request.form['address']
            
            logger.info(f"Dados do form - Title: {title}, Address: {address}")
            
            # Processar a imagem (se existir)
            image_url = None
            if 'image' in request.files:
                image = request.files['image']
                logger.info(f"Imagem recebida: {image.filename}")
                if image and image.filename and allowed_file(image.filename):
                    # Gerar nome único para o arquivo
                    filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(image.filename)[1])
                    image_path = os.path.join(UPLOAD_FOLDER, filename)
                    image.save(image_path)
                    image_url = f'/uploads/{filename}'
                    logger.info(f"Imagem salva: {image_url}")
        else:
            logger.info("Processando como JSON")
            # Requisição JSON
            try:
                raw_data = request.get_data()
                logger.info(f"Raw data recebido: {raw_data}")
                
                data = request.get_json()
                logger.info(f"JSON parsed: {data}")
                
                if not data:
                    logger.error("Dados JSON vazios ou inválidos")
                    return jsonify({"error": "Dados não fornecidos ou formato inválido"}), 400
                    
                if 'title' not in data or 'description' not in data or 'address' not in data:
                    logger.error(f"Campos obrigatórios ausentes no JSON: {list(data.keys()) if data else 'None'}")
                    return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400
                
                title = data['title']
                description = data['description']
                address = data['address']
                image_url = data.get('image_url')
                
                logger.info(f"Dados do JSON - Title: {title}, Address: {address}")
                
            except Exception as e:
                logger.error(f"Erro ao processar JSON: {str(e)}")
                return jsonify({"error": f"Formato de dados inválido: {str(e)}"}), 400
        
        # Validar se os campos não estão vazios
        if not title.strip() or not description.strip() or not address.strip():
            logger.error("Campos obrigatórios estão vazios")
            return jsonify({"error": "Título, descrição e endereço não podem estar vazios"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            logger.info(f"Inserindo ticket no banco de dados para usuário ID: {user['id']}")
            # Inserir o ticket no banco de dados
            cursor.execute(
                '''
                INSERT INTO tickets (title, description, user_id, image_url, address, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (title, description, user['id'], image_url, address, 'aberto')
            )
            conn.commit()
            
            # Obter o ID do ticket recém-criado
            ticket_id = cursor.lastrowid
            logger.info(f"Ticket criado com sucesso, ID: {ticket_id}")
            
            conn.close()
            return jsonify({
                "message": "Ticket criado com sucesso",
                "id": ticket_id
            }), 201
        
        except sqlite3.Error as e:
            conn.close()
            logger.error(f"Erro no banco de dados: {str(e)}")
            return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Erro geral na criação do ticket: {str(e)}")
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

# Rota para obter um ticket específico
@app.route('/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Buscar o ticket
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404
        
        # Verificar permissão para visualizar o ticket
        can_view = False
        
        if user.get('document_type') == 'cpf':
            # Pessoa física: só pode ver seus próprios tickets
            can_view = ticket['user_id'] == user['id']
        elif user.get('document_type') == 'cnpj':
            # Empresa: pode ver tickets em aberto ou que ela assumiu
            can_view = (ticket['status'] == 'aberto' or 
                       ticket['assigned_company_id'] == user['id'])
        else:
            # Admin: pode ver todos
            can_view = True
        
        if not can_view:
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403
        
        # Converter o objeto Row para dicionário
        ticket_dict = dict(ticket)
        
        # Buscar informações do usuário que criou o ticket
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_info = get_user_info(ticket['user_id'], token)
        ticket_dict['user'] = {
            "id": ticket['user_id'],
            "name": user_info.get('name', 'Usuário desconhecido'),
            "email": user_info.get('email', '')
        }
        
        # Buscar informações da empresa responsável (se houver)
        if ticket['assigned_company_id']:
            company_info = get_user_info(ticket['assigned_company_id'], token)
            ticket_dict['assigned_company'] = {
                'id': ticket['assigned_company_id'],
                'name': company_info.get('name', 'Empresa desconhecida'),
                'email': company_info.get('email', '')
            }
        else:
            ticket_dict['assigned_company'] = None
        
        conn.close()
        return jsonify({"ticket": ticket_dict}), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para assumir um ticket (empresas)
@app.route('/tickets/<int:ticket_id>/assign', methods=['PATCH'])
def assign_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401
    
    # Apenas empresas podem assumir tickets
    if user.get('document_type') != 'cnpj':
        return jsonify({"error": "Apenas empresas podem assumir tickets"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se o ticket existe e está em aberto
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404
        
        if ticket['status'] != 'aberto':
            conn.close()
            return jsonify({"error": "Ticket não está disponível para ser assumido"}), 400
        
        # Assumir o ticket
        cursor.execute(
            '''UPDATE tickets 
               SET assigned_company_id = ?, status = 'em andamento', updated_at = CURRENT_TIMESTAMP 
               WHERE id = ?''',
            (user['id'], ticket_id)
        )
        conn.commit()
        
        conn.close()
        return jsonify({
            "message": "Ticket assumido com sucesso",
            "ticket_id": ticket_id
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para finalizar um ticket (empresas)
@app.route('/tickets/<int:ticket_id>/complete', methods=['PATCH'])
def complete_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401
    
    # Apenas empresas podem finalizar tickets
    if user.get('document_type') != 'cnpj':
        return jsonify({"error": "Apenas empresas podem finalizar tickets"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se o ticket existe e está em andamento pela empresa
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404
        
        if ticket['status'] != 'em andamento' or ticket['assigned_company_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Você não pode finalizar este ticket"}), 400
        
        # Finalizar o ticket
        cursor.execute(
            'UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            ('resolvido', ticket_id)
        )
        conn.commit()
        
        conn.close()
        return jsonify({
            "message": "Ticket finalizado com sucesso",
            "ticket_id": ticket_id
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para adicionar feedback ao ticket (autor do ticket)
@app.route('/tickets/<int:ticket_id>/feedback', methods=['PATCH'])
def add_feedback(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401
    
    data = request.get_json()
    
    if 'feedback' not in data or not data['feedback'].strip():
        return jsonify({"error": "Feedback é obrigatório"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se o ticket existe, está resolvido e o usuário é o autor
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        
        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404
        
        if ticket['user_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Apenas o autor do ticket pode adicionar feedback"}), 403
        
        if ticket['status'] != 'resolvido':
            conn.close()
            return jsonify({"error": "Feedback só pode ser adicionado a tickets resolvidos"}), 400
        
        # Adicionar feedback
        cursor.execute(
            'UPDATE tickets SET feedback = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (data['feedback'], ticket_id)
        )
        conn.commit()
        
        conn.close()
        return jsonify({
            "message": "Feedback adicionado com sucesso",
            "ticket_id": ticket_id
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para obter estatísticas dos tickets
@app.route('/tickets/stats', methods=['GET'])
def get_ticket_stats():
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401
    
    # Verificar permissão para acessar estatísticas
    if user.get('role') not in ['admin'] and user.get('document_type') != 'cnpj':
        return jsonify({"error": "Não autorizado"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Estatísticas por status
        status_stats = []
        for status in ['aberto', 'em andamento', 'resolvido']:
            count = cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = ?', (status,)).fetchone()[0]
            status_stats.append({
                "status": status,
                "count": count
            })
        
        # Total de tickets
        total = cursor.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]
        
        # Tickets criados nos últimos 7 dias
        recent = cursor.execute(
            "SELECT COUNT(*) FROM tickets WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()[0]
        
        conn.close()
        return jsonify({
            "total": total,
            "recent_7_days": recent,
            "by_status": status_stats
        }), 200
    
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Tratamento de erros
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    # Obter porta do ambiente ou usar 5002 por padrão
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)