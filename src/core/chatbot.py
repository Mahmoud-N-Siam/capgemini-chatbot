import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from config.settings import Settings
from src.api.capgemini_client import CapgeminiClient
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

    def add_document(self, file_path: Union[str, Path], chunk_strategy: str = "sentences") -> dict:
        file_path = Path(file_path)
        file_info = self.processor.get_file_info(file_path)
        text = self.processor.extract_text(file_path)
        chunks = self.chunker.chunk(text, strategy=chunk_strategy)
        if chunks:
            self.document_search.add_documents(
                chunks,
                metadatas=[{'document_id': file_info['file_name'], 'file_name': file_info['file_name'],
                           'chunk_index': i, 'total_chunks': len(chunks)} for i in range(len(chunks))]
            )
        doc_id = str(uuid.uuid4())
        document = {'id': doc_id, 'file_name': file_info['file_name'], 'file_path': str(file_path),
                    'file_size': file_info['file_size'], 'content': text, 'chunks': chunks,
                    'created_at': datetime.now()}
        self.documents[doc_id] = document
        return document

    def remove_document(self, doc_id: str) -> bool:
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False

    def clear_documents(self):
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
             doc_ids: Optional[List[str]] = None, use_search: bool = True) -> dict:
        temperature = temperature or Settings.TEMPERATURE
        max_tokens = max_tokens or Settings.MAX_TOKENS
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
            results = self.document_search.search(message, k=3)
            if results:
                relevant_context = "\n\n".join([f"Relevant document: {meta.get('file_name', 'Unknown')}\n{text}" for _, _, text, meta in results])
                messages[-1]['content'] = f"{relevant_context}\n\n{message}"
        try:
            response = self.client.chat(messages=messages, temperature=temperature, max_tokens=max_tokens)
            self.conversation_history.extend([{'role': 'user', 'content': message}, {'role': 'assistant', 'content': response['content']}])
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
        import os
        filename = f"{uuid.uuid4()}_{file_storage.filename}"
        file_path = self.upload_folder / filename
        file_storage.save(str(file_path))
        return self.add_document(file_path)