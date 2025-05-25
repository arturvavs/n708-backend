import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///feedback.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = os.getenv('FLASK_ENV') == 'development'

CORS(app)
db = SQLAlchemy(app)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)

@app.before_request
def setup():
    if not hasattr(app, 'has_run'):
        print("Rodando setup inicial e criando tabelas")
        db.create_all()
        app.has_run = True

@app.route('/feedback', methods=['POST'])
def create_comment():
    data = request.get_json()
    if not data or not all(k in data for k in ('ticket_id', 'user_id', 'content')):
        return jsonify({'error': 'Campos obrigatórios: ticket_id, user_id, content'}), 400
    comment = Comment(ticket_id=data['ticket_id'], user_id=data['user_id'], content=data['content'])
    db.session.add(comment)
    db.session.commit()
    return jsonify({'id': comment.id}), 201

@app.route('/feedback/<int:id>', methods=['GET'])
def get_comment(id):
    comment = Comment.query.get_or_404(id)
    return jsonify({'id': comment.id, 'ticket_id': comment.ticket_id, 'user_id': comment.user_id, 'content': comment.content})

@app.route('/feedback', methods=['GET'])
def list_comments():
    ticket_id = request.args.get('ticket_id', type=int)
    query = Comment.query
    if ticket_id:
        query = query.filter_by(ticket_id=ticket_id)
    comments = query.all()
    return jsonify([{'id': c.id, 'ticket_id': c.ticket_id, 'user_id': c.user_id, 'content': c.content} for c in comments])

@app.route('/feedback/<int:id>', methods=['PATCH'])
def update_comment(id):
    comment = Comment.query.get_or_404(id)
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Campo "content" é obrigatório para atualização'}), 400
    comment.content = data['content']
    db.session.commit()
    return jsonify({'id': comment.id, 'ticket_id': comment.ticket_id, 'user_id': comment.user_id, 'content': comment.content})

@app.route('/feedback/<int:id>', methods=['DELETE'])
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': f'Comentário {id} deletado com sucesso'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'online',
        'service': 'feedback'
    })

if __name__ == '__main__':
    try:
        port = int(os.getenv('PORT', '5003'))
    except ValueError:
        print("⚠️  Porta inválida. Usando 5003 como padrão.")
        port = 5003

    debug_mode = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
