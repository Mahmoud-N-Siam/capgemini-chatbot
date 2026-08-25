import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import Mock

from config.settings import Settings
from src.core.chatbot import CapgeminiChatbot
from src.core.document_search import DocumentSearch
from src.documents.chunker import TextChunker
from src.documents.processors import DocumentProcessor
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
        page = """
        <div><a class="result__a" href="https://example.com/one">First</a>
        <a class="result__snippet">Snippet one</a></div>
        <div><a class="result__a" href="https://example.com/one">Duplicate</a>
        <a class="result__snippet">Snippet duplicate</a></div>
        <div><a class="result__a" href="https://example.com/two">Second</a>
        <a class="result__snippet">Snippet two</a></div>
        <div><a class="result__a" href="https://example.com/three">Third</a>
        <a class="result__snippet">Snippet three</a></div>
        """
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = page
        search = WebSearch()
        with unittest.mock.patch("src.api.web_search.Settings.WEB_SEARCH_ENABLED", True), \
                unittest.mock.patch("src.api.web_search.requests.post", Mock(return_value=response)):
            results = search.search("general query", max_results=2)
        self.assertEqual([result["url"] for result in results], [
            "https://example.com/one", "https://example.com/two"
        ])
        self.assertEqual(results[0]["snippet"], "Snippet one")

    def test_web_search_unwraps_redirect_urls(self):
        from src.api.web_search import WebSearch
        page = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.example'
                '%2Fpage&amp;rut=abc">Real title</a><a class="result__snippet">Body</a>')
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = page
        search = WebSearch()
        with unittest.mock.patch("src.api.web_search.Settings.WEB_SEARCH_ENABLED", True), \
                unittest.mock.patch("src.api.web_search.requests.post", Mock(return_value=response)):
            results = search.search("query", max_results=5)
        self.assertEqual(results[0]["url"], "https://real.example/page")

    def test_web_search_disabled_makes_no_request(self):
        from src.api.web_search import WebSearch
        post = Mock()
        with unittest.mock.patch("src.api.web_search.Settings.WEB_SEARCH_ENABLED", False), \
                unittest.mock.patch("src.api.web_search.requests.post", post):
            self.assertEqual(WebSearch().search("query"), [])
        post.assert_not_called()


class RegressionTests(unittest.TestCase):
    def test_know_does_not_trigger_web_search(self):
        # "now" is a substring of "know"; only whole words may trigger a fetch.
        for phrase in ("I don't know the answer", "Tell me about your knowledge base",
                       "Which browser is known to work?"):
            self.assertFalse(CapgeminiChatbot._needs_web_search(phrase), phrase)

    def test_current_information_words_trigger_web_search(self):
        for phrase in ("What is the latest Python version?", "Any news today?",
                       "current release notes"):
            self.assertTrue(CapgeminiChatbot._needs_web_search(phrase), phrase)

    def test_history_is_bounded_in_prompt(self):
        class RecordingClient:
            def chat(self, messages, temperature=None, max_tokens=None, model=None, on_token=None):
                self.messages = messages
                return {"id": "r", "content": "ok", "role": "assistant"}

        with tempfile.TemporaryDirectory() as directory:
            client = RecordingClient()
            chatbot = CapgeminiChatbot(client=client, upload_folder=Path(directory))
            chatbot.document_search = FakeSearch()
            chatbot.web_search = Mock(search=Mock(return_value=[]))
            for index in range(chatbot.MAX_HISTORY_MESSAGES + 10):
                chatbot.conversation_history.append(
                    {"role": "user", "content": f"old {index}", "timestamp": None})
            chatbot.chat("new question", use_search=False)
            # 1 system + capped history + 1 current user message
            self.assertEqual(len(client.messages), chatbot.MAX_HISTORY_MESSAGES + 2)

    def test_upload_preserves_file_extension(self):
        class FakeUpload:
            filename = ".hidden.txt"

            def save(self, destination):
                Path(destination).write_text("Body text.", encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            chatbot = CapgeminiChatbot(client=Mock(), upload_folder=Path(directory))
            chatbot.document_search = FakeSearch()
            document = chatbot.upload_document(FakeUpload())
            self.assertTrue(document["file_name"].endswith(".txt"))

    def test_app_exposes_port_and_debug_config(self):
        app = create_app()
        self.assertEqual(app.config["PORT"], Settings.PORT)
        self.assertEqual(app.config["DEBUG"], Settings.DEBUG)
        self.assertFalse(app.json.sort_keys)

    def test_unknown_api_route_returns_json(self):
        response = create_app().test_client().get("/api/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn("error", response.get_json())

    def test_upload_rejects_disallowed_extension_as_json(self):
        import io
        client = create_app().test_client()
        response = client.post("/api/documents/upload", data={
            "file": (io.BytesIO(b"binary"), "payload.exe")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("File type not allowed", response.get_json()["error"])

    def test_chat_route_reports_worker_failure(self):
        class ExplodingClient:
            def chat(self, messages, temperature=None, max_tokens=None, model=None, on_token=None):
                raise RuntimeError("model exploded")

        original_chatbot = api_routes.chatbot
        try:
            with tempfile.TemporaryDirectory() as directory:
                api_routes.chatbot = CapgeminiChatbot(
                    client=ExplodingClient(), upload_folder=Path(directory))
                api_routes.chatbot.document_search = FakeSearch()
                api_routes.chatbot.web_search = Mock(search=Mock(return_value=[]))
                response = create_app().test_client().post("/api/chat", json={"message": "hey"})
                body = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn('"finish_reason": "error"', body)
            self.assertIn('"type": "done"', body)
        finally:
            api_routes.chatbot = original_chatbot

    def test_chunker_never_exceeds_chunk_size(self):
        chunker = TextChunker(chunk_size=50, overlap=10)
        single_long_sentence = "x" * 260
        for chunk in chunker.chunk(single_long_sentence, strategy="sentences"):
            self.assertLessEqual(len(chunk), 50)
        for chunk in chunker.chunk(single_long_sentence, strategy="paragraphs"):
            self.assertLessEqual(len(chunk), 50)

    def test_text_extraction_falls_back_to_legacy_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.txt"
            path.write_bytes("Café costs 5\u00a0EUR".encode("cp1252"))
            self.assertIn("Caf", DocumentProcessor.extract_text(path))

    def test_embeddings_are_requested_in_batches(self):
        search = DocumentSearch()
        calls = []

        def fake_post(texts):
            calls.append(list(texts))
            return [__import__("numpy").ones(3, dtype="float32") for _ in texts]

        search._post_embeddings = fake_post
        with unittest.mock.patch(
                "src.core.document_search.Settings.EMBEDDING_BATCH_SIZE", 2):
            search._get_embeddings([f"text {index}" for index in range(5)])
        self.assertEqual([len(batch) for batch in calls], [2, 2, 1])


if __name__ == "__main__":
    unittest.main()



