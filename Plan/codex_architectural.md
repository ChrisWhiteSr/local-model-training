# Codex Architectural Plan — Local LLM + RAG with Citations

## Goals
- Run entirely locally on a Windows PC; VPC-ready later.
- Use open-weights small LLM for responsiveness on modest GPUs/CPU.
- Answer strictly from your PDFs and cite sources (filename + page).
- Start with Retrieval-Augmented Generation (RAG); add optional fine‑tuning later.

## Recommended Stack (Local-First)
- Base model: Qwen3 4B Thinking 2507 (local). Runner: LM Studio HTTP at `http://localhost:1234` by default; alternative runner: Ollama (`http://localhost:11434`) or any custom HTTP base URL. Use 4-bit quantization where available. Configure prompts to return final answers only (no chain-of-thought).
- Embeddings: Qwen3-Embedding-4B (LM Studio model id: `text-embedding-qwen3-embedding-4b`) served by LM Studio `POST /v1/embeddings` at `http://localhost:1234`. Fallbacks: `nomic-embed-text` (Ollama) or `bge-small-en-v1.5` (SentenceTransformers).
- Optional reranker: bge-reranker-v2-m3 (CPU). Rationale: boosts precision@k and citation accuracy.
- Vector DB: ChromaDB (persistent, local directory store).
- PDF extraction: PyMuPDF; OCR: PaddleOCR (PP-OCRv4 via onnxruntime) instead of Tesseract. Default VLM assist: OpenAI `gpt-5-mini` (vision) for hard pages; local VLM fallback (e.g., Qwen2‑VL‑2B) is supported but disabled by default.
- Orchestration: LangChain (retriever + re-ranking + prompt assembly).
- API: FastAPI (endpoints: /ingest, /query, /documents, /health).
- Web front-end: React + Vite + TanStack Query; UI kit: Mantine (default). WebSocket/SSE for ingest progress; deploy locally with Node.

## High-Level Flow
```
PDFs → Ingestion → Chunking → Embeddings → ChromaDB
                                       ↑
User Query → Embed → Retrieve (k) → Re-rank (optional) → Context Builder → LLM → Answer + Citations
```

## Components
1) Ingestion
   - Walk a configured folder (default: `training_data`) and detect new/changed PDFs via hash.
   - Extract text per page (PyMuPDF) and capture metadata: filename, page, doc title, checksum.
   - Chunking: ~1,000 chars, 200 overlap, sentence-aware to reduce split claims.
   - Create embeddings and upsert to ChromaDB with metadata.
   - OCR policy (Tesseract-free):
     - If a page has little/no text layer, run PaddleOCR (PP-OCRv4 via onnxruntime, CPU).
     - Persist bounding boxes + confidence; keep raw OCR text and normalized text.
     - Optional corrective pass: VLM `gpt-5-mini` (default) to resolve reading order/table structures on complex pages; local VLM fallback is available but disabled by default.

2) Retrieval + Re-ranking
   - Similarity search top_k=8–12 from Chroma.
   - Optional cross-encoder rerank to top 4–6 chunks for improved grounding.
   - Guardrails: if below similarity_threshold, return “not found in documents.”

3) Generation + Citations
   - System prompt emphasizes: use ONLY provided context; cite as [filename.pdf, p X].
   - Build context window from reranked chunks with explicit per-chunk headers.
   - Map each answer sentence to the highest-scoring supporting chunk; include structured citation payload.
   - Qwen3 4B Thinking: request concise final answers; explicitly disable/exclude chain-of-thought in instructions.

4) API Endpoints
   - POST /ingest: trigger ingestion; optional body to limit files.
   - POST /query: { query, top_k?, include_sources? } → { answer, citations[], sources_used[], chunks_retrieved }.
   - GET /documents: list documents with chunk counts, last_ingested_at.
   - GET /health: Ollama, embeddings, DB checks.

5) Web Front-End (Admin UI)
   - Tech: Vite + React + TypeScript + TanStack Query; UI kit: Mantine.
   - Views:
     - Dashboard: system health, model status, storage and GPU/CPU usage.
     - Documents: upload PDFs, view ingest queue, per-document pages/chunks, OCR confidence.
     - Queries: test console with streaming answers and inline citations; open source snippets.
      - Settings: model selection, retrieval/rerank params, chunking and similarity thresholds.
        - LLM runner selection: `LM Studio (http)` | `Ollama` | `Custom URL` with editable base URL field (default `http://localhost:1234`).
        - VLM provider: `OpenAI gpt-5-mini (default)` | `Local VLM (disabled by default)`.
        - Embeddings provider: `LM Studio: Qwen3-Embedding-4B (text-embedding-qwen3-embedding-4b)` | `Ollama: nomic-embed-text` | `SentenceTransformers: bge-small` | `Custom URL`.
        - Embeddings base URL textbox (default `http://localhost:1234`).
        - Data path: editable `PDF_SOURCE_DIR` defaulting to `training_data`.
     - Logs: recent errors, slow queries, ingestion events.
   - Realtime: SSE/WebSocket to stream ingest progress and query tokens.

## Local Environment
- Install: Python 3.11, Git, Ollama, (optional) LM Studio for quick GUI testing.
- Python deps (minimal):
  - langchain, langchain-community, langchain-ollama
  - chromadb
  - fastapi, uvicorn
  - pymupdf
  - sentence-transformers (if using bge-small)
  - python-multipart
 - OCR stack (no Tesseract): onnxruntime, rapidocr-onnxruntime or paddleocr (CPU), opencv-python-headless
 - Optional: ragas (evaluation), pydantic v2.
  - LLM runner: LM Studio serving Qwen3 4B Thinking 2507 at `http://localhost:1234` (default). Alternatively, Ollama at `http://localhost:11434` or any custom base URL.
  - VLM (default): OpenAI `gpt-5-mini` vision. Requires `OPENAI_API_KEY`. Can be disabled or switched to a local VLM in Settings.
  - Suggested env vars:
    - `LLM_RUNNER=lmstudio` | `ollama` | `http`
    - `LLM_BASE_URL=http://localhost:1234`
    - `OPENAI_API_KEY=...` (for VLM)
    - `VLM_PROVIDER=openai` | `local`
   - `EMBEDDINGS_PROVIDER=lmstudio` | `nomic` | `bge-small` | `http`
   - `EMBEDDINGS_BASE_URL=http://localhost:1234` (LM Studio embeddings default)
    - `PDF_SOURCE_DIR=training_data`

### Embedding Server Notes (Qwen3‑Embedding‑4B‑GGUF)
- Option A — LM Studio embeddings (default):
  - LM Studio exposes `/v1/embeddings` at `http://localhost:1234`.
  - Set `.env`: `EMBEDDINGS_RUNNER=lmstudio`, `EMBEDDINGS_BASE_URL=http://localhost:1234`, `EMBEDDINGS_MODEL_ID=text-embedding-qwen3-embedding-4b`.
  - Discover model id: `GET http://localhost:1234/v1/models`.
  - Request example:
    - `curl http://localhost:1234/v1/embeddings -H "Content-Type: application/json" -d "{\"model\":\"text-embedding-qwen3-embedding-4b\",\"input\":[\"hello\"]}"`
  - Note: this is simplest to operate; ensure LM Studio’s active embeddings model remains loaded.
- Option B — Separate llama.cpp server (for high concurrency):
  - Run llama.cpp `server` with embeddings on port 1235.
  - `.env`: `EMBEDDINGS_RUNNER=llamacpp`, `EMBEDDINGS_BASE_URL=http://localhost:1235`.
  - Example (Windows, PowerShell):
    - `llama-server.exe -m C:\Models\qwen3-embedding-4b.q4_0.gguf --embedding -c 4096 -ngl 32 -t 8 -p 1235`
    - Test: `curl http://localhost:1235/v1/embeddings -H "Content-Type: application/json" -d '{"model":"qwen3-embedding-4b","input":"hello"}'`

## Why RAG First (vs. Fine‑Tuning)
- Your “cite from training set” requirement is best satisfied by retrieval + metadata-grounded prompts.
- Fine-tuning does not reliably teach exact source recall or page-level citation and may increase hallucinations.
- RAG provides traceability, incremental updates, and immediate results with small compute.

## Optional Fine‑Tuning Path (Later)
Goal: style/formatting alignment and domain phrasing; keep citations via RAG.
- Data: generate instruction-style Q&A from your PDFs (self-instruct or human-authored), include rationales.
- Method: LoRA/QLoRA on 3B–7B models using PEFT/Transformers; train on CPU/GPU.
- Do NOT bake document content into weights for citation—keep retrieval for provenance.
- Evaluate with held-out Q&A and regression on RAGAS-like faithfulness/groundedness.

## Mechanics: Pretraining vs. Fine‑Tuning (Weight Changes)
- Pretraining: initializes all weights by predicting next tokens on huge general corpora; establishes broad knowledge and syntax.
- Supervised fine‑tuning (SFT): adjusts a subset or all weights on task-specific examples (e.g., Q&A, instruction following) to change behavior/style.
- Parameter-efficient fine‑tuning (LoRA/QLoRA): learns small adaptor matrices while freezing base weights; merges at inference for low compute cost.
- None of these reliably “store” exact passages with page references; that’s why retrieval is used for provenance.

## Configuration Defaults
- Model: Qwen3 4B Thinking 2507 (quantized, 4-bit if available); temperature 0.1; top_p 0.9; max_tokens 2048; instruction to avoid reasoning traces and output concise final answers with citations.
- Embeddings: LM Studio `/v1/embeddings` (default) at `http://localhost:1234` with `EMBEDDINGS_MODEL_ID`. Fallback to `nomic-embed-text` (Ollama) or `bge-small`.
- Retrieval: top_k 8; similarity_threshold 0.7; chunk_size 1000; overlap 200.
- Reranker (optional): bge-reranker-v2-m3; top_k_reranked 4.
- OCR: PaddleOCR (PP-OCRv4) via onnxruntime; OCR trigger when text-layer yield < threshold per page; OCR correction with `gpt‑5‑mini` by default on low-confidence pages.
- Runners: default `LLM_RUNNER=lmstudio`, `LLM_BASE_URL=http://localhost:1234`; optional `ollama` with `http://localhost:11434`.

## Risks & Mitigations
- Low VRAM (RTX 5060 4GB): Qwen3 4B Thinking in 4‑bit should run on GPU; if memory pressure appears, switch to CPU or lower context; keep embeddings/reranker on CPU.
 - External calls: VLM uses OpenAI by default; provide a toggle to disable or switch to local VLM for fully offline runs.
 - Scanned PDFs: integrate OCR; flag low-confidence pages.
- Hallucinations: strict prompt + “only from context” + low temperature + return “not found” when retrieval weak.
- Scale: for 100+ PDFs, tune Chroma HNSW params; add reranker; cache frequent queries.

## Minimal Milestones
1) Day 1: Backend ingestion + `/query` with citations. Ingest 10–20 PDFs from `training_data`; `/query` returns grounded answers with filename/page. Implement `/documents` and `/health`.
2) Day 2: Front-end (Vite + React + Mantine) wired to live backend endpoints (no mocks). Implement Settings, Documents, Queries, and Logs pages.
3) Day 3+: Optional reranker (disabled by default); finalize OCR pipeline (PaddleOCR + OpenAI VLM assist for complex pages), add monitoring and small LoRA SFT for tone/formatting (keep RAG for facts). Add basic evaluation set and compute precision@k and citation accuracy.

## Implementation Notes
- Ollama is scripting-friendly and reproducible for headless deployments; LM Studio is great for ad‑hoc local testing. You can keep both.
- If you prefer no Ollama for embeddings, use sentence-transformers (bge-small) fully offline.
- Directory proposal: ./data/pdfs, ./data/chroma, ./configs/*.yaml
- Source documents are primarily PDFs; ingestion prioritizes text-layer extraction before OCR.

## Data Paths
- Default PDF source: `training_data`
- Windows path handling: no quoting needed for `training_data`; set `PDF_SOURCE_DIR=training_data` in `.env`.

## Hardware Assumptions (from your system)
- Windows 11 Pro, ~31GB RAM, RTX 5060 Laptop GPU (4GB VRAM), 1TB SSD.
- Recommendation: use Qwen3 4B Thinking 2507 in 4‑bit on GPU; consider CPU fallback for long contexts or batch jobs; keep 7B+ models off GPU.

## Follow-ups
- Reranker: keep disabled initially; revisit enabling after baseline metrics.
- Retrieval defaults: confirm preferred `top_k` and `similarity_threshold` once basic QA is in place.
