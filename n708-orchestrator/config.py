import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

class Config:
    # Configuração da aplicação Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-orchestrator')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    
    # Configuração dos serviços
    AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')
    TICKETS_SERVICE_URL = os.environ.get('TICKETS_SERVICE_URL', 'http://localhost:5002')
    FEEDBACK_SERVICE_URL = os.environ.get('FEEDBACK_SERVICE_URL', 'http://localhost:5003')
