import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.core.chatbot import CapgeminiChatbot
from src.core.document_search import DocumentSearch
from src.documents.chunker import TextChunker
import src.web.routes.api as api_routes
from src.web.app import create_app


class FakeSearch:
    def __init__(self):
        self.removed_ids = []

    def add_documents(self, texts, metadatas=None):
        self.texts = texts
        self.metadata = metadatas

    def search(self, query, k=3, document_ids=None):
        return []

    def remove_documents(self, document_id):
        self.removed_ids.append(document_id)

    def clear(self):
        pass

    def __bool__(self):
        return True


class CoreBehaviorTests(unittest.TestCase):
    def test_chunker_rejects_non_progressing_overlap(self):
        with self.assertRaises(ValueError):
            TextChunker(chunk_size=10, overlap=10)

    def test_delete_removes_index_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            upload_folder = Path(directory)
            client = Mock()
            chatbot = CapgeminiChatbot(client=client, upload_folder=upload_folder)
            chatbot.document_search = FakeSearch()
            source = upload_folder / "document.txt"
            source.write_text("A document to index.", encoding="utf-8")

            document = chatbot.add_document(source)
            self.assertTrue(chatbot.remove_document(document["id"]))
            self.assertEqual(chatbot.document_search.removed_ids, [document["id"]])
            self.assertFalse(source.exists())

    def test_chat_history_contains_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Mock()
            client.chat.return_value = {"content": "Answer", "id": "response-1"}
            chatbot = CapgeminiChatbot(client=client, upload_folder=Path(directory))
            chatbot.document_search = FakeSearch()

            chatbot.chat("Question", temperature=0, max_tokens=1, use_search=False)

            history = chatbot.get_conversation_history()
            self.assertEqual(len(history), 2)
            self.assertIn("timestamp", history[0])
            client.chat.assert_called_once()
            self.assertEqual(client.chat.call_args.kwargs["temperature"], 0)
            self.assertEqual(client.chat.call_args.kwargs["max_tokens"], 1)


class SearchFilterTests(unittest.TestCase):
    def test_search_can_filter_document_ids(self):
        search = DocumentSearch()
        search.documents = ["first", "second"]
        search.embeddings = [__import__("numpy").array([1.0]), __import__("numpy").array([0.5])]
        search.metadata = [{"document_id": "one"}, {"document_id": "two"}]
        search._get_embeddings = Mock(return_value=[__import__("numpy").array([1.0])])

        results = search.search("query", k=3, threshold=0, document_ids=["two"])

        self.assertEqual([result[3]["document_id"] for result in results], ["two"])


class StreamingRouteTests(unittest.TestCase):
    def test_chat_route_streams_tokens(self):
        class FakeClient:
            def chat(self, messages, temperature=None, max_tokens=None, model=None, on_token=None):
                on_token("hel")
                on_token("lo")
                return {"id": "response-1", "content": "hello", "role": "assistant"}

        original_chatbot = api_routes.chatbot
        try:
            api_routes.chatbot = CapgeminiChatbot(client=FakeClient(), upload_folder=Path("uploads"))
            response = create_app().test_client().post("/api/chat", json={"message": "hey"})
            body = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "text/event-stream")
            self.assertIn('"type": "token"', body)
            self.assertIn('"content": "hel"', body)
            self.assertIn('"content": "lo"', body)
            self.assertIn('"type": "done"', body)
        finally:
            api_routes.chatbot = original_chatbot


class WebSearchPromptTests(unittest.TestCase):
    def test_live_sources_are_explicitly_identified_to_model(self):
        class FakeClient:
            def chat(self, messages, temperature=None, max_tokens=None, model=None, on_token=None):
                self.messages = messages
                return {"id": "response-1", "content": "answer", "role": "assistant"}

        class FakeWebSearch:
            def search(self, query):
                return [{"title": "Source", "url": "https://example.com", "snippet": "Live fact"}]

        client = FakeClient()
        chatbot = CapgeminiChatbot(client=client, upload_folder=Path("uploads"))
        chatbot.document_search = FakeSearch()
        chatbot.web_search = FakeWebSearch()

        chatbot.chat("What is the latest Python version?", use_search=False)

        self.assertIn("live web sources", client.messages[0]["content"])
        self.assertIn("https://example.com", client.messages[-1]["content"])

    def test_web_search_results_are_bounded_and_deduplicated(self):
        from src.api.web_search import WebSearch
        search = WebSearch()
        search._search_python_releases = Mock(return_value=[])
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "RelatedTopics": [
                {"Text": "First", "FirstURL": "https://example.com/one"},
                {"Text": "Duplicate", "FirstURL": "https://example.com/one"},
                {"Text": "Second", "FirstURL": "https://example.com/two"},
            ]
        }
        search_response = Mock(return_value=response)
        with unittest.mock.patch("src.api.web_search.requests.get", search_response):
            results = search.search("general query", max_results=5)
        self.assertEqual([result["url"] for result in results], [
            "https://example.com/one", "https://example.com/two"
        ])


if __name__ == "__main__":
    unittest.main()
