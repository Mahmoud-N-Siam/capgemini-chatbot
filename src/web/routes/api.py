import logging
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from src.api.capgemini_client import CapgeminiClient
from src.core.chatbot import CapgeminiChatbot
from config.settings import Settings

logger = logging.getLogger(__name__)
api_routes = Blueprint('api', __name__, url_prefix='/api')
chatbot = None

def get_chatbot():
    global chatbot
    if chatbot is None:
        chatbot = CapgeminiChatbot()
    return chatbot

@api_routes.route('/health', methods=['GET'])
def health_check():
    try:
        client = CapgeminiClient()
        is_healthy = client.health_check()
        return jsonify({'status': 'healthy' if is_healthy else 'unhealthy', 'api_status': 'connected' if is_healthy else 'disconnected'}), 200 if is_healthy else 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_routes.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        chatbot = get_chatbot()
        response = chatbot.chat(message=data['message'], temperature=data.get('temperature'),
                               max_tokens=data.get('max_tokens'), doc_ids=data.get('document_ids'),
                               use_search=data.get('use_search', True))
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/documents/upload', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        allowed_extensions = {ext.lstrip('.') for ext in Settings.ALLOWED_EXTENSIONS}
        file_extension = file.filename.rsplit('.', 1)[-1].lower()
        if file_extension not in allowed_extensions:
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(sorted(allowed_extensions))}'}), 400
        filename = secure_filename(file.filename)
        chatbot = get_chatbot()
        document = chatbot.upload_document(file)
        return jsonify({'id': document['id'], 'file_name': document['file_name'],
                        'file_size': document['file_size'], 'chunks': len(document['chunks']),
                        'message': 'Document uploaded successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/documents', methods=['GET'])
def list_documents():
    try:
        chatbot = get_chatbot()
        documents = chatbot.get_documents()
        return jsonify([{'id': doc['id'], 'file_name': doc['file_name'],
                        'file_size': doc['file_size'], 'created_at': doc['created_at'].isoformat()}
                       for doc in documents]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id: str):
    try:
        chatbot = get_chatbot()
        success = chatbot.remove_document(doc_id)
        return jsonify({'message': 'Document deleted successfully'}), 200 if success else jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/conversation', methods=['GET'])
def get_conversation():
    try:
        chatbot = get_chatbot()
        history = chatbot.get_conversation_history()
        return jsonify([{'role': msg['role'], 'content': msg['content'], 'timestamp': msg['timestamp'].isoformat()}
                       for msg in history]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/conversation', methods=['DELETE'])
def clear_conversation():
    try:
        chatbot = get_chatbot()
        chatbot.reset_conversation()
        return jsonify({'message': 'Conversation cleared'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/documents/clear', methods=['DELETE'])
def clear_documents():
    try:
        chatbot = get_chatbot()
        chatbot.clear_documents()
        return jsonify({'message': 'All documents cleared'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500