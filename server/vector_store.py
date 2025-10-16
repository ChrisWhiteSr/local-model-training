from __future__ import annotations

import os
from typing import List, Dict, Any

try:
    import chromadb  # type: ignore
    from chromadb import PersistentClient  # type: ignore
    from chromadb.config import Settings as ChromaSettings  # type: ignore
    _HAS_CHROMA = True
except Exception:
    chromadb = None  # type: ignore
    PersistentClient = None  # type: ignore
    _HAS_CHROMA = False

from .simple_store import SimpleStore


class ChromaStore:
    def __init__(self, path: str, collection_name: str = "pdf_collection"):
        os.makedirs(path, exist_ok=True)
        self._use_simple = not _HAS_CHROMA
        if self._use_simple:
            self.simple = SimpleStore(path=path)
        else:
            # Disable telemetry explicitly via Chroma settings
            settings = ChromaSettings(anonymized_telemetry=False)
            self.client: PersistentClient = chromadb.PersistentClient(path=path, settings=settings)  # type: ignore
            self.collection = self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]], embeddings: List[List[float]]):
        if getattr(self, "_use_simple", False):
            self.simple.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)  # type: ignore[attr-defined]
        else:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def query(self, query_embeddings: List[List[float]], n_results: int = 8) -> Dict[str, Any]:
        if getattr(self, "_use_simple", False):
            return self.simple.query(query_embeddings=query_embeddings, n_results=n_results)  # type: ignore[attr-defined]
        return self.collection.query(query_embeddings=query_embeddings, n_results=n_results, include=["documents", "metadatas", "distances"])

    def count(self) -> int:
        if getattr(self, "_use_simple", False):
            return self.simple.count()  # type: ignore[attr-defined]
        return self.collection.count()

    def get_all(self) -> Dict[str, Any]:
        if getattr(self, "_use_simple", False):
            return self.simple.get_all()  # type: ignore[attr-defined]
        return self.collection.get(include=["metadatas"])
