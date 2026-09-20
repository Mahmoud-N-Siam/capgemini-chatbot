#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.document_search import DocumentSearch

def test_embeddings():
    print("Testing Generative Engine Embeddings API...")
    
    # Initialize search
    search = DocumentSearch()
    
    # Add some test documents
    documents = [
        "The sky is blue and beautiful.",
        "Python is a programming language.",
        "Machine learning is fascinating.",
        "The ocean is deep and mysterious."
    ]
    
    print(f"Adding {len(documents)} documents...")
    search.add_documents(documents)
    
    # Test search
    query = "What color is the sky?"
    print(f"\nSearching for: '{query}'")
    results = search.search(query, k=2)
    
    print(f"\nFound {len(results)} results:")
    for idx, similarity, text, metadata in results:
        print(f"  - [{similarity:.3f}] {text}")
    
    print("\n✅ Embeddings API test passed!")

if __name__ == "__main__":
    test_embeddings()