from __future__ import annotations

from typing import List, Dict, Any

from .clients.lmstudio import LMStudioEmbeddings, LMStudioChat
from .settings import get_settings
from .vector_store import ChromaStore


SYSTEM_PROMPT = (
    "You are a helpful assistant that answers ONLY from the provided context. "
    "Cite sources using [filename.pdf, p X]. If the answer is not in the context, say you can't find it."
)


def _build_context(chunks: List[str], metadatas: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, (chunk, meta) in enumerate(zip(chunks, metadatas)):
        header = f"[{meta.get('source_file')}, p {meta.get('page_number')}]"
        lines.append(f"{header}\n{chunk}\n---")
    return "\n".join(lines)


class Retriever:
    def __init__(self, store: ChromaStore, embedder: LMStudioEmbeddings, chat: LMStudioChat):
        self.store = store
        self.embedder = embedder
        self.chat = chat

    async def query(self, query: str, top_k: int, similarity_threshold: float) -> Dict[str, Any]:
        query_emb = await self.embedder.embed([query])
        results = self.store.query(query_embeddings=query_emb, n_results=top_k)
        # results: { ids, distances, documents, metadatas }
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        # Filter by similarity threshold (cosine distance: smaller is closer). We treat threshold as cosine similarity.
        # Chroma returns distances for cosine where 0 is identical; convert to similarity = 1 - distance (approx).
        filtered: List[int] = []
        for i, d in enumerate(distances):
            sim = 1 - float(d)
            if sim >= similarity_threshold:
                filtered.append(i)
        if filtered:
            docs = [docs[i] for i in filtered]
            metas = [metas[i] for i in filtered]

        context = _build_context(docs, metas)
        user_prompt = f"Context follows. Use it only.\n\n{context}\n\nQuestion: {query}\nAnswer concisely with citations."
        answer = await self.chat.chat(SYSTEM_PROMPT, user_prompt)

        sources_used = []
        for m in metas:
            tag = {"source": m.get("source_file"), "page": m.get("page_number")}
            if tag not in sources_used:
                sources_used.append(tag)

        # Minimal citation mapping: reference the top N chunks
        citations = [
            {
                "source": m.get("source_file"),
                "page": m.get("page_number"),
                "quote": docs[i][:200],
                "confidence": 0.5,  # placeholder without reranking
            }
            for i, m in enumerate(metas[: min(4, len(metas))])
        ]

        return {
            "answer": answer.strip(),
            "citations": citations,
            "sources_used": sources_used,
            "chunks_retrieved": len(metas),
        }

