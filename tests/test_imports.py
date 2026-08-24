import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    from config.settings import Settings
    from src.models.schemas import ChatMessage, Document, ChatRequest, ChatResponse
    from src.models.types import MessageRole
    from src.api.capgemini_client import CapgeminiClient, APIError
    from src.documents.processors import DocumentProcessor
    from src.documents.chunker import TextChunker
    from src.core.chatbot import CapgeminiChatbot
    from src.core.document_search import DocumentSearch
    from src.web.app import create_app
    from src.web.routes import api_routes, web_routes
    print("All imports successful!")

if __name__ == '__main__':
    test_imports()