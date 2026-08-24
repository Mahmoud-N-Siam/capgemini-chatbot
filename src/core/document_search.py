import logging
from typing import List, Optional, Tuple
import faiss
from sentence_transformers import SentenceTransformer
from config.settings import Settings

logger = logging.getLogger(__name__)

class DocumentSearch:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or Settings.EMBEDDING_MODEL
        self.model = SentenceTransformer(self.model_name)
        self.index = None
        self.documents: List[str] = []
        self.metadata: List[dict] = []

    def add_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None):
        if not texts:
            return
        metadatas = metadatas or [{}] * len(texts)
        embeddings = self.model.encode(texts, show_progress_bar=False)
        if self.index is None:
            self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(embeddings)
        self.documents.extend(texts)
        self.metadata.extend(metadatas)

    def search(self, query: str, k: int = 3, threshold: float = 0.5) -> List[Tuple[int, float, str, dict]]:
        if self.index is None or len(self.documents) == 0:
            return []
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(query_embedding, k)
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx >= 0:
                similarity = 1.0 / (1.0 + distance)
                if similarity >= threshold:
                    results.append((int(idx), float(similarity), self.documents[idx],
                                   self.metadata[idx] if idx < len(self.metadata) else {}))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def clear(self):
        self.index = None
        self.documents = []
        self.metadata = []

    def __len__(self) -> int:
        return len(self.documents)