import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from werkzeug.utils import secure_filename
from config.settings import Settings
from src.api.capgemini_client import CapgeminiClient
from src.api.web_search import WebSearch
from src.documents.processors import DocumentProcessor
from src.documents.chunker import TextChunker
from src.core.document_search import DocumentSearch

logger = logging.getLogger(__name__)

class CapgeminiChatbot:
    def __init__(self, client: Optional[CapgeminiClient] = None, upload_folder: Optional[Path] = None):
        self.client = client or CapgeminiClient()
        self.upload_folder = upload_folder or Settings.UPLOAD_FOLDER
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.documents: Dict[str, dict] = {}
        self.document_search = DocumentSearch()
        self.conversation_history: List[dict] = []
        self.processor = DocumentProcessor()
        self.chunker = TextChunker()
        self.web_search = WebSearch()

    @staticmethod
    def _needs_web_search(message: str) -> bool:
        message_lower = message.lower()
        current_terms = ("latest", "current", "today", "now", "news", "release", "version")
        return any(term in message_lower for term in current_terms)

    def add_document(self, file_path: Union[str, Path], chunk_strategy: str = "sentences") -> dict:
        file_path = Path(file_path)
        doc_id = str(uuid.uuid4())
        file_info = self.processor.get_file_info(file_path)
        text = self.processor.extract_text(file_path)
        if not text.strip():
            raise ValueError("Document contains no extractable text")
        chunks = self.chunker.chunk(text, strategy=chunk_strategy)
        if chunks:
            self.document_search.add_documents(
                chunks,
                metadatas=[{'document_id': doc_id, 'file_name': file_info['file_name'],
                           'chunk_index': i, 'total_chunks': len(chunks)} for i in range(len(chunks))]
            )
        document = {'id': doc_id, 'file_name': file_info['file_name'], 'file_path': str(file_path),
                    'file_size': file_info['file_size'], 'content': text, 'chunks': chunks,
                    'created_at': datetime.now()}
        self.documents[doc_id] = document
        return document

    def remove_document(self, doc_id: str) -> bool:
        if doc_id in self.documents:
            document = self.documents.pop(doc_id)
            self.document_search.remove_documents(doc_id)
            Path(document['file_path']).unlink(missing_ok=True)
            return True
        return False

    def clear_documents(self):
        for document in self.documents.values():
            Path(document['file_path']).unlink(missing_ok=True)
        self.documents.clear()
        self.document_search.clear()

    def _build_context_prompt(self, doc_ids: Optional[List[str]] = None) -> str:
        if not self.documents:
            return ""
        docs_to_include = [self.documents[doc_id] for doc_id in (doc_ids or list(self.documents.keys())) if doc_id in self.documents]
        if not docs_to_include:
            return ""
        context_parts = []
        for doc in docs_to_include:
            doc_summary = doc['chunks'][0] if doc['chunks'] else doc['content'][:500]
            context_parts.append(f"Document: {doc['file_name']}\nContent: {doc_summary}...")
        return "\n\n".join(context_parts)

    def chat(self, message: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None,
             doc_ids: Optional[List[str]] = None, use_search: bool = True,
             on_token=None, web_search: bool = False, model: Optional[str] = None) -> dict:
        temperature = Settings.TEMPERATURE if temperature is None else temperature
        max_tokens = Settings.MAX_TOKENS if max_tokens is None else max_tokens
        messages = []
        context_prompt = self._build_context_prompt(doc_ids)
        if context_prompt:
            messages.append({'role': 'system',
                            'content': f"You are a helpful AI assistant with access to the following documents:\n{context_prompt}\n\nAnswer questions based on these documents when relevant."})
        else:
            messages.append({'role': 'system', 'content': 'You are a helpful AI assistant.'})
        for msg in self.conversation_history:
            messages.append({'role': msg['role'], 'content': msg['content']})
        messages.append({'role': 'user', 'content': message})
        if use_search and self.document_search:
            results = self.document_search.search(message, k=3, document_ids=doc_ids)
            if results:
                relevant_context = "\n\n".join([f"Relevant document: {meta.get('file_name', 'Unknown')}\n{text}" for _, _, text, meta in results])
                messages[-1]['content'] = f"{relevant_context}\n\n{message}"
        if web_search or self._needs_web_search(message):
            web_results = self.web_search.search(message)
            if web_results:
                messages[0]['content'] += (
                    "\n\nThe application fetched the following live web sources for this request. "
                    "Treat them as current evidence, use them when answering, and cite the "
                    "provided URLs. Do not claim you cannot browse when these sources are "
                    "present. If the sources do not fully answer the question, say so clearly."
                )
                web_context = "\n\n".join(
                    f"Web source: {result['title']}\nURL: {result['url']}\n{result['snippet']}"
                    for result in web_results
                )
                messages[-1]['content'] = f"{web_context}\n\n{messages[-1]['content']}"
        try:
            response = self.client.chat(messages=messages, temperature=temperature,
                                        max_tokens=max_tokens, model=model, on_token=on_token)
            self.conversation_history.extend([
                {'role': 'user', 'content': message, 'timestamp': datetime.now()},
                {'role': 'assistant', 'content': response['content'], 'timestamp': datetime.now()}
            ])
            return response
        except Exception as e:
            return {'id': str(uuid.uuid4()), 'content': f"Sorry, I encountered an error: {str(e)}",
                    'role': 'assistant', 'finish_reason': 'error'}

    def reset_conversation(self):
        self.conversation_history = []

    def get_conversation_history(self) -> List[dict]:
        return self.conversation_history.copy()

    def get_documents(self) -> List[dict]:
        return list(self.documents.values())

    def upload_document(self, file_storage) -> dict:
        original_name = secure_filename(file_storage.filename or '') or 'uploaded_file'
        filename = f"{uuid.uuid4()}_{original_name}"
        file_path = self.upload_folder / filename
        file_storage.save(str(file_path))
        try:
            return self.add_document(file_path)
        except Exception:
            file_path.unlink(missing_ok=True)
            raise