from __future__ import annotations

import os
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .clients.lmstudio import LMStudioEmbeddings, LMStudioChat
from .ingest import Ingestor
from .retrieval import Retriever
from .settings import get_settings
from .vector_store import ChromaStore


app = FastAPI(title="Local LLM + RAG API", version="0.1.0")


class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    include_sources: Optional[bool] = True


class IngestRequest(BaseModel):
    paths: Optional[List[str]] = None


def _lm_clients():
    settings = get_settings()
    # Allow overriding LLM model id via env; if not set, attempt to use any default loaded model in LM Studio
    llm_model = os.getenv("LLM_MODEL_ID", "qwen")  # generic placeholder; user should set a valid model id
    emb = LMStudioEmbeddings(base_url=settings.EMBEDDINGS_BASE_URL, model=settings.EMBEDDINGS_MODEL_ID)
    chat = LMStudioChat(base_url=settings.LLM_BASE_URL, model=llm_model)
    return emb, chat


def _store():
    settings = get_settings()
    return ChromaStore(path=settings.CHROMA_PATH)


@app.get("/health")
async def health() -> Dict[str, Any]:
    settings = get_settings()
    checks: Dict[str, Any] = {"ok": True, "details": {}}
    # LM Studio chat
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.LLM_BASE_URL.rstrip('/')}/v1/models")
            checks["details"]["lmstudio_chat"] = r.status_code == 200
    except Exception:
        checks["details"]["lmstudio_chat"] = False
        checks["ok"] = False
    # LM Studio embeddings
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Probe with a cheap embed request
            r = await client.post(
                f"{settings.EMBEDDINGS_BASE_URL.rstrip('/')}/v1/embeddings",
                json={"model": settings.EMBEDDINGS_MODEL_ID, "input": ["health"]},
            )
            checks["details"]["lmstudio_embeddings"] = r.status_code == 200
    except Exception:
        checks["details"]["lmstudio_embeddings"] = False
        checks["ok"] = False
    # Chroma
    try:
        store = _store()
        _ = store.count()
        checks["details"]["chroma"] = True
    except Exception:
        checks["details"]["chroma"] = False
        checks["ok"] = False
    return checks


@app.post("/ingest")
async def ingest(req: IngestRequest) -> Dict[str, Any]:
    settings = get_settings()
    if not os.path.isdir(settings.PDF_SOURCE_DIR):
        raise HTTPException(status_code=400, detail=f"PDF_SOURCE_DIR not found: {settings.PDF_SOURCE_DIR}")
    store = _store()
    emb, _ = _lm_clients()
    ingestor = Ingestor(store=store, embedder=emb)
    result = await ingestor.ingest_paths(paths=req.paths)
    return {
        "files_processed": result.files_processed,
        "pages_processed": result.pages_processed,
        "chunks_upserted": result.chunks_upserted,
        "errors": result.errors,
    }


@app.post("/query")
async def query(req: QueryRequest) -> Dict[str, Any]:
    settings = get_settings()
    store = _store()
    emb, chat = _lm_clients()
    retriever = Retriever(store=store, embedder=emb, chat=chat)
    top_k = req.top_k or settings.TOP_K
    result = await retriever.query(query=req.query, top_k=top_k, similarity_threshold=settings.SIMILARITY_THRESHOLD)
    return result


@app.get("/documents")
async def documents() -> Dict[str, Any]:
    settings = get_settings()
    store = _store()
    items = store.get_all()
    # Aggregate by source_file
    counts: Dict[str, int] = {}
    for meta in items.get("metadatas", []):
        src = meta.get("source_file", "unknown")
        counts[src] = counts.get(src, 0) + 1
    docs = [{"source_file": k, "chunks": v} for k, v in sorted(counts.items())]
    return {"documents": docs, "total_chunks": store.count()}

