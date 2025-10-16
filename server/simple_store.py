from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List


def _cosine_distance(a: List[float], b: List[float]) -> float:
    num = 0.0
    da = 0.0
    db = 0.0
    for x, y in zip(a, b):
        num += x * y
        da += x * x
        db += y * y
    if da == 0.0 or db == 0.0:
        return 1.0
    return 1.0 - (num / (math.sqrt(da) * math.sqrt(db)))


class SimpleStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(self.path, exist_ok=True)
        self.doc_path = os.path.join(self.path, "docs.jsonl")
        # Memory cache
        self._docs: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        self._docs = []
        if os.path.exists(self.doc_path):
            with open(self.doc_path, "r", encoding="utf-8") as f:
                for ln in f:
                    try:
                        self._docs.append(json.loads(ln))
                    except Exception:
                        continue

    def _append(self, rec: Dict[str, Any]) -> None:
        with open(self.doc_path, "a", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
            f.write("\n")
        self._docs.append(rec)

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]], embeddings: List[List[float]]):
        for i, id_ in enumerate(ids):
            rec = {
                "id": id_,
                "document": documents[i],
                "metadata": metadatas[i],
                "embedding": embeddings[i],
            }
            self._append(rec)

    def query(self, query_embeddings: List[List[float]], n_results: int = 8) -> Dict[str, Any]:
        if not self._docs:
            return {"ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]}
        q = query_embeddings[0]
        scored = []
        for rec in self._docs:
            d = _cosine_distance(q, rec["embedding"])  # smaller is closer
            scored.append((d, rec))
        scored.sort(key=lambda x: x[0])
        top = scored[:n_results]
        return {
            "ids": [[r["id"] for _, r in top]],
            "distances": [[d for d, _ in top]],
            "documents": [[r["document"] for _, r in top]],
            "metadatas": [[r["metadata"] for _, r in top]],
        }

    def count(self) -> int:
        return len(self._docs)

    def get_all(self) -> Dict[str, Any]:
        return {"metadatas": [rec["metadata"] for rec in self._docs]}

