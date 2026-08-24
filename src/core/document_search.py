import logging
import numpy as np
from typing import List, Optional, Tuple
import requests
from config.settings import Settings

logger = logging.getLogger(__name__)

class DocumentSearch:
    """API-based document search using Generative Engine embeddings"""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or Settings.EMBEDDING_MODEL
        self.api_key = Settings.CAPGEMINI_API_KEY
        self.api_url = Settings.OPENAI_API_URL
        self.documents: List[str] = []
        self.embeddings: List[np.ndarray] = []
        self.metadata: List[dict] = []

        logger.info(f"Initialized DocumentSearch with model: {self.model_name}")

    def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Get embeddings from Generative Engine API"""
        url = f"{self.api_url}/embeddings"

        # Use both headers for OpenAI-compatible endpoint
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,  # Added this
            "Content-Type": "application/json"
        }

        try:
            # API accepts string or list of strings
            payload = {
                "input": texts,
                "model": self.model_name
            }

            logger.debug(f"Requesting embeddings for {len(texts)} texts")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract embeddings from response
            if 'data' in data:
                embeddings = [np.array(item['embedding']) for item in data['data']]
                if len(embeddings) != len(texts) or any(embedding.ndim != 1 for embedding in embeddings):
                    raise ValueError("Invalid embedding count or shape from embeddings API")
                logger.debug(f"Generated {len(embeddings)} embeddings")
                return embeddings
            else:
                raise ValueError("Invalid response format from embeddings API")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get embeddings: {e}")
            raise RuntimeError(f"Embeddings API request failed: {str(e)}")

    def add_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None):
        """Add documents with their embeddings"""
        if not texts:
            return

        metadatas = metadatas or [{}] * len(texts)

        try:
            # Get embeddings from API
            new_embeddings = self._get_embeddings(texts)

            # Store documents and embeddings
            self.documents.extend(texts)
            self.embeddings.extend(new_embeddings)
            self.metadata.extend(metadatas)

            logger.info(f"Added {len(texts)} documents. Total: {len(self.documents)}")

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def search(self, query: str, k: int = 3, threshold: float = 0.5,
               document_ids: Optional[List[str]] = None) -> List[Tuple[int, float, str, dict]]:
        """Search for similar documents using cosine similarity"""
        if not self.documents:
            logger.warning("No documents to search")
            return []

        try:
            # Get query embedding
            query_embeddings = self._get_embeddings([query])
            query_embedding = query_embeddings[0]

            # Calculate cosine similarity with all documents
            similarities = []
            for idx, doc_embedding in enumerate(self.embeddings):
                if document_ids is not None and self.metadata[idx].get('document_id') not in document_ids:
                    continue
                # Cosine similarity
                query_norm = np.linalg.norm(query_embedding)
                document_norm = np.linalg.norm(doc_embedding)
                if query_norm == 0 or document_norm == 0:
                    continue
                similarity = np.dot(query_embedding, doc_embedding) / (query_norm * document_norm)
                similarities.append((idx, float(similarity)))

            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)

            # Filter by threshold and take top k
            results = []
            for idx, similarity in similarities[:k]:
                if similarity >= threshold:
                    results.append((
                        idx,
                        similarity,
                        self.documents[idx],
                        self.metadata[idx] if idx < len(self.metadata) else {}
                    ))

            logger.debug(f"Found {len(results)} results for query")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def remove_documents(self, document_id: str) -> None:
        """Remove all indexed chunks belonging to a document."""
        retained = [
            (text, embedding, metadata)
            for text, embedding, metadata in zip(self.documents, self.embeddings, self.metadata)
            if metadata.get('document_id') != document_id
        ]
        self.documents = [item[0] for item in retained]
        self.embeddings = [item[1] for item in retained]
        self.metadata = [item[2] for item in retained]

    def clear(self):
        """Clear all documents and embeddings"""
        self.documents = []
        self.embeddings = []
        self.metadata = []
        logger.info("Cleared all documents")

    def __len__(self) -> int:
        return len(self.documents)
