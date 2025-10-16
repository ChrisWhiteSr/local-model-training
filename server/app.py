from __future__ import annotations

import os
from typing import List, Optional, Dict, Any
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .clients.lmstudio import LMStudioEmbeddings, LMStudioChat
from .ingest import Ingestor
from .retrieval import Retriever
from .settings import get_settings
from .vector_store import ChromaStore
from .event_log import JSONLLogger
from .logging_config import configure_logging
from .event_bus import EventBus


configure_logging()
app = FastAPI(title="Local LLM + RAG API", version="0.1.0")

# CORS for local UI
s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.UI_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-process event bus for ingest events
event_bus = EventBus()


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
async def ingest(req: IngestRequest, force: bool = False) -> Dict[str, Any]:
    settings = get_settings()
    if not os.path.isdir(settings.PDF_SOURCE_DIR):
        raise HTTPException(status_code=400, detail=f"PDF_SOURCE_DIR not found: {settings.PDF_SOURCE_DIR}")
    store = _store()
    emb, _ = _lm_clients()
    ingest_logger = JSONLLogger(settings.INGEST_LOG_PATH)
    ingestor = Ingestor(store=store, embedder=emb, ingest_logger=ingest_logger, event_bus=event_bus)

    # Clear index if force=True
    if force:
        ingestor.clear_index()

    result = await ingestor.ingest_paths(paths=req.paths)
    return {
        "files_processed": result.files_processed,
        "files_skipped": result.files_skipped,
        "files_found": result.files_found,
        "pages_processed": result.pages_processed,
        "chunks_upserted": result.chunks_upserted,
        "errors": result.errors,
        "ocr_events": result.ocr_events,
        "processed_list": result.processed_list,
        "skipped_list": result.skipped_list,
    }


@app.get("/logs/ingest")
async def ingest_logs(limit: int = 200) -> Dict[str, Any]:
    settings = get_settings()
    logger = JSONLLogger(settings.INGEST_LOG_PATH)
    records = logger.tail(limit=limit)
    return {"items": records, "count": len(records)}


@app.post("/query")
async def query(req: QueryRequest) -> Dict[str, Any]:
    settings = get_settings()
    store = _store()
    emb, chat = _lm_clients()
    retriever = Retriever(store=store, embedder=emb, chat=chat)
    top_k = req.top_k or settings.TOP_K
    t0 = time.perf_counter()
    qlog = JSONLLogger(settings.QUERY_LOG_PATH)
    try:
        result = await retriever.query(query=req.query, top_k=top_k, similarity_threshold=settings.SIMILARITY_THRESHOLD)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        # lightweight record
        qlog.append({
            "event": "query",
            "query": req.query,
            "top_k": top_k,
            "chunks_retrieved": result.get("chunks_retrieved", 0),
            "sources_used": result.get("sources_used", []),
            "latency_ms": latency_ms,
            "ok": True,
        })
        return result
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        qlog.append({
            "event": "query_error",
            "query": req.query,
            "top_k": top_k,
            "error": str(e),
            "latency_ms": latency_ms,
            "ok": False,
        })
        raise


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


@app.get("/logs/query")
async def query_logs(limit: int = 200) -> Dict[str, Any]:
    settings = get_settings()
    logger = JSONLLogger(settings.QUERY_LOG_PATH)
    records = logger.tail(limit=limit)
    return {"items": records, "count": len(records)}


@app.get("/events/ingest")
async def events_ingest():
    import json
    import asyncio
    from starlette.responses import StreamingResponse

    async def event_stream():
        q = await event_bus.subscribe()
        last_heartbeat = asyncio.get_event_loop().time()
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=5.0)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    last_heartbeat = asyncio.get_event_loop().time()
                except asyncio.TimeoutError:
                    # Send heartbeat every 5s if no events
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= 5.0:
                        yield f"data: {json.dumps({'event': 'heartbeat'}, ensure_ascii=False)}\n\n"
                        last_heartbeat = now
        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(q)

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
