import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class ImportTests(unittest.TestCase):
    """Guard against packaging or circular-import regressions.

    This was previously a bare function, which unittest discovery collected as
    zero tests, so import breakage went unnoticed.
    """

    def test_public_modules_import(self):
        from config.settings import Settings
        from src.models.schemas import ChatMessage, Document, ChatRequest, ChatResponse
        from src.models.types import MessageRole
        from src.api.capgemini_client import CapgeminiClient, APIError
        from src.api.web_search import WebSearch
        from src.documents.processors import DocumentProcessor
        from src.documents.chunker import TextChunker
        from src.core.chatbot import CapgeminiChatbot
        from src.core.document_search import DocumentSearch
        from src.web.app import create_app
        from src.web.routes import api_routes, web_routes

        for imported in (Settings, ChatMessage, Document, ChatRequest, ChatResponse,
                         MessageRole, CapgeminiClient, APIError, WebSearch,
                         DocumentProcessor, TextChunker, CapgeminiChatbot,
                         DocumentSearch, create_app, api_routes, web_routes):
            self.assertIsNotNone(imported)


if __name__ == '__main__':
    unittest.main()