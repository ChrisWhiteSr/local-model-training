from __future__ import annotations

import os
from typing import List, Dict, Any, Tuple

import chromadb
from chromadb import PersistentClient
from chromadb.utils import embedding_functions


class ChromaStore:
    def __init__(self, path: str, collection_name: str = "pdf_collection"):
        os.makedirs(path, exist_ok=True)
        self.client: PersistentClient = chromadb.PersistentClient(path=path)
        # Using an external embedding function; we'll supply embeddings directly, so set None.
        self.collection = self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]], embeddings: List[List[float]]):
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def query(self, query_embeddings: List[List[float]], n_results: int = 8) -> Dict[str, Any]:
        return self.collection.query(query_embeddings=query_embeddings, n_results=n_results, include=["documents", "metadatas", "distances"])

    def count(self) -> int:
        return self.collection.count()

    def get_all(self) -> Dict[str, Any]:
        # Note: for large collections this is heavy; used only for simple stats
        return self.collection.get(include=["metadatas"])

