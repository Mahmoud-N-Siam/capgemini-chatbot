import logging
import json
import queue
import threading
from flask import Blueprint, request, jsonify, Response, stream_with_context
from pydantic import ValidationError
from src.api.capgemini_client import CapgeminiClient
from src.core.chatbot import CapgeminiChatbot
from src.models.schemas import ChatRequest
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
        chat_request = ChatRequest.model_validate(data or {})
        chatbot = get_chatbot()
        events = queue.Queue()

        def on_token(token):
            events.put({'type': 'token', 'content': token})

        def run_chat():
            response = chatbot.chat(message=chat_request.message, temperature=chat_request.temperature,
                                    max_tokens=chat_request.max_tokens, doc_ids=chat_request.document_ids,
                                    use_search=chat_request.use_search, web_search=chat_request.web_search,
                                    model=chat_request.model, on_token=on_token)
            events.put({'type': 'done', 'response': response})

        threading.Thread(target=run_chat, daemon=True).start()

        def stream_events():
            while True:
                event = events.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event['type'] == 'done':
                    break

        return Response(stream_with_context(stream_events()), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
    except ValidationError as e:
        return jsonify({'error': 'Invalid chat request', 'details': e.errors()}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_routes.route('/models', methods=['GET'])
def list_models():
    try:
        return jsonify(CapgeminiClient().get_models()), 200
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
        if success:
            return jsonify({'message': 'Document deleted successfully'}), 200
        return jsonify({'error': 'Document not found'}), 404
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