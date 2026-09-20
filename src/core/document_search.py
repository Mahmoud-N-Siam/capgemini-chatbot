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

    def _post_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Send a single embeddings request for the given batch."""
        url = f"{self.api_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {"input": texts, "model": self.model_name}

        logger.debug(f"Requesting embeddings for {len(texts)} texts")
        response = requests.post(url, headers=headers, json=payload,
                                 timeout=Settings.EMBEDDING_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if 'data' not in data:
            raise ValueError("Invalid response format from embeddings API")

        # The API is not required to preserve input order, so sort by index
        # when it is provided.
        items = data['data']
        if all(isinstance(item, dict) and 'index' in item for item in items):
            items = sorted(items, key=lambda item: item['index'])
        embeddings = [np.asarray(item['embedding'], dtype=np.float32) for item in items]
        if len(embeddings) != len(texts) or any(embedding.ndim != 1 for embedding in embeddings):
            raise ValueError("Invalid embedding count or shape from embeddings API")
        return embeddings

    def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Get embeddings from Generative Engine API in bounded batches."""
        try:
            batch_size = max(1, Settings.EMBEDDING_BATCH_SIZE)
            embeddings: List[np.ndarray] = []
            for start in range(0, len(texts), batch_size):
                embeddings.extend(self._post_embeddings(texts[start:start + batch_size]))
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
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

    def search(self, query: str, k: Optional[int] = None, threshold: Optional[float] = None,
               document_ids: Optional[List[str]] = None) -> List[Tuple[int, float, str, dict]]:
        """Search for similar documents using vectorized cosine similarity."""
        if not self.documents:
            logger.warning("No documents to search")
            return []

        k = Settings.SEARCH_TOP_K if k is None else k
        threshold = Settings.SEARCH_THRESHOLD if threshold is None else threshold

        try:
            query_embedding = self._get_embeddings([query])[0]
            query_norm = float(np.linalg.norm(query_embedding))
            if query_norm == 0:
                return []

            candidate_indices = [
                idx for idx in range(len(self.embeddings))
                if document_ids is None
                or self.metadata[idx].get('document_id') in document_ids
            ]
            if not candidate_indices:
                return []

            # One matrix product instead of a per-document Python loop.
            matrix = np.vstack([self.embeddings[idx] for idx in candidate_indices])
            document_norms = np.linalg.norm(matrix, axis=1)
            valid = document_norms > 0
            if not valid.any():
                return []

            scores = np.full(len(candidate_indices), -np.inf, dtype=np.float64)
            scores[valid] = (matrix[valid] @ query_embedding) / (document_norms[valid] * query_norm)

            order = np.argsort(scores)[::-1][:max(0, k)]
            results = []
            for position in order:
                similarity = float(scores[position])
                if similarity < threshold or not np.isfinite(similarity):
                    continue
                idx = candidate_indices[int(position)]
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
