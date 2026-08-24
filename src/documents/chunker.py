import re
from typing import List
from config.settings import Settings

class TextChunker:
    def __init__(self, chunk_size: int = None, overlap: int = 200):
        self.chunk_size = chunk_size or Settings.CHUNK_SIZE
        self.overlap = overlap
        if self.chunk_size <= 0 or self.overlap < 0 or self.overlap >= self.chunk_size:
            raise ValueError("chunk_size must be positive and greater than overlap")

    def chunk_by_size(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - self.overlap if end < len(text) else end
        return chunks

    def chunk_by_sentences(self, text: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk += (" " + sentence) if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def chunk_by_paragraphs(self, text: str) -> List[str]:
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += ("\n\n" + para) if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def chunk(self, text: str, strategy: str = "sentences") -> List[str]:
        strategy_methods = {
            'size': self.chunk_by_size,
            'sentences': self.chunk_by_sentences,
            'paragraphs': self.chunk_by_paragraphs
        }
        method = strategy_methods.get(strategy, self.chunk_by_sentences)
        return method(text)