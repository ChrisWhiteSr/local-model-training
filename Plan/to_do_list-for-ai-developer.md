# AI Developer To‑Do List — Local LLM + RAG with Citations

This checklist operationalizes the architecture in `Plan/codex_architectural.md` and adds concrete implementation tasks, configs, and acceptance criteria.

## Scope & Goals
- Local‑first system answering strictly from PDFs with page‑level citations.
 - Base LLM: Qwen3 4B Thinking 2507 via LM Studio (`http://localhost:1234`).
 - Embeddings: Qwen3-Embedding-4B via LM Studio `/v1/embeddings` (model id: `text-embedding-qwen3-embedding-4b`).
- OCR: PaddleOCR (PP‑OCRv4) + optional VLM correction using OpenAI `gpt-5-mini`.
- Vector DB: ChromaDB. Orchestration: LangChain. API: FastAPI. UI: React + Vite.
 - Source PDFs live in `training_data`.

## Sequencing
- Build Backend first (ingestion, retrieval, citations, API), then wire a live Front-End (no mocks) to those endpoints.

## Environment & Configuration
- Create `.env` with at least:
  - `PDF_SOURCE_DIR=training_data`
  - `LLM_RUNNER=lmstudio`
  - `LLM_BASE_URL=http://localhost:1234`
  - `EMBEDDINGS_PROVIDER=lmstudio`
  - `EMBEDDINGS_BASE_URL=http://localhost:1234`
  - `EMBEDDINGS_MODEL_ID=text-embedding-qwen3-embedding-4b`
  - `VLM_PROVIDER=openai`
  - `OPENAI_API_KEY=<key>`
  - Optional fallbacks: `EMBEDDINGS_PROVIDER=nomic|bge-small`, `EMBEDDINGS_BASE_URL=http://localhost:11434`
- Add config schema (pydantic) mapping env → runtime settings with validation and defaults.
- Implement runtime switching for runners (LM Studio, Ollama, Custom URL) and persistence in a small `settings.json`.

## Backend: Ingestion & OCR
- Implement directory watcher or on-demand ingestion for `training_data`.
- For each PDF:
  - Compute document hash/version; store per‑page checksum to support incremental updates.
  - Extract text per page via PyMuPDF; store metadata: `doc_id`, `filename`, `title`, `page`, `checksum`, `has_text_layer`.
  - If text layer missing/low‑density, run PaddleOCR (onnxruntime) and persist:
    - OCR text (raw + normalized), bounding boxes, confidence per block/line/word.
  - If OCR confidence low or layout complex, call VLM correction (`gpt-5-mini`) to repair reading order and table structure; capture a `vlm_correction_applied` flag.
  - Chunk using sentence‑aware splitter: size ≈ 1000 chars, overlap 200; retain page and bbox references for citation snippets.
  - Embed chunks using LM Studio `/v1/embeddings` with `EMBEDDINGS_MODEL_ID`; backoff/retry and rate limit.
  - Upsert into Chroma collection `pdf_collection` with metadata: `source_file`, `page_number`, `chunk_id`, `doc_title`, `checksum`, `ocr_confidence`, `vlm_correction_applied`.

## Backend: Retrieval, Rerank, Generation, Citations
- Retrieval:
  - Similarity search `top_k=8` with `similarity_threshold=0.7`.
  - Optional: integrate `bge-reranker-v2-m3` CPU reranker to refine to top 4-6 chunks (disabled by default initially).
- Prompt assembly:
  - System: “Use ONLY provided context; cite as [filename.pdf, p X]. If not found, say so.”
  - Insert chunks with headers `{filename} p{page}` and delimiters.
- LLM call (Qwen3 4B Thinking):
  - Temperature 0.1, top_p 0.9, max_tokens 2048. Instruct to output final answers only (no chain‑of‑thought).
- Citation mapping:
  - Align each sentence/claim in the answer to supporting chunk(s) using cosine similarity and reranker scores; include `confidence`.
  - Response JSON: `answer`, `citations[] {source,page,quote,confidence}`, `sources_used[]`, `chunks_retrieved`.
- Guardrails:
  - If max supporting score < threshold, label claim as `unsupported` and add note in answer.
  - If overall retrieval weak, return “not found in documents.”

## Backend: API (FastAPI)
- Endpoints:
  - `POST /ingest` body: `{paths?: string[]}` → processed counts, per‑file stats.
  - `POST /query` body: `{query: string, top_k?: number, include_sources?: boolean}` → answer JSON.
  - `GET /documents` → document list with chunk counts, last_ingested_at, errors.
  - `GET /health` → runner checks (LM Studio chat, LM Studio embeddings), Chroma ping.
  - `GET /config` and `POST /config` → read/update runtime settings (runners, base URLs, params).
  - `GET /events/ingest` (SSE) → ingestion progress.
  - `GET /events/query` (SSE) → token stream for responses.
- Error handling: structured errors with codes; timeouts and retries for HTTP runners.

## Front‑End (React + Vite + Mantine)
- Pages: Dashboard, Documents, Queries, Settings, Logs.
- Settings:
  - Runner selection: `LM Studio (default)` | `Ollama` | `Custom URL` with editable `LLM_BASE_URL`.
  - Embeddings provider: `LM Studio (default)` | `Ollama: nomic-embed-text` | `SentenceTransformers: bge-small` | `Custom` with `EMBEDDINGS_BASE_URL` and `EMBEDDINGS_MODEL_ID`.
  - VLM toggle: `OpenAI gpt-5-mini` enabled/disabled.
  - Chunk/retrieval parameters and thresholds.
  - Data path selector for `training_data`.
- Documents view: upload PDFs, show ingest queue, per‑doc pages/chunks counts, OCR/VLM flags, re‑ingest button.
- Queries view: chat console with streaming and inline citations; expandable source snippets.
- Dashboard: health indicators for runners, DB, storage, and recent activity.

## Evaluation & QA
- Build a small gold QA set (10–20 queries) from your PDFs.
- Metrics: retrieval precision@k, citation accuracy, groundedness (RAGAS or lightweight checks), latency, throughput.
- Scripts to run batch queries and export results to CSV/JSON.

## Logging & Observability
- Structured JSON logging: request IDs, timings, cache hits, errors.
- Persist ingestion and query events for the UI’s Logs page.
- Optional: simple Prometheus metrics export (requests, latency, failures) if needed later.

## Performance & Caching
- Cache embeddings for unchanged chunks; re‑embed on checksum change only.
- Consider query cache keyed by normalized query + top_k.
- Tune Chroma HNSW parameters for >100 PDFs.

## Security & Ops
- Store `OPENAI_API_KEY` securely in .env (local only). Avoid logging secrets.
- CORS: restrict to local UI origin by default.
- Validate and sanitize PDF uploads; size limits; reject executables.

## Optional Enhancements
- OCR table structure recovery into Markdown for higher‑fidelity chunks.
- Multi‑query expansion for harder questions and ensemble retrieval.
- Export answers and citations as a Markdown report.

## Acceptance Criteria (Definition of Done)
- Can ingest PDFs in `training_data` without errors; OCR applied only when needed; confidence stored.
- `/query` returns grounded answers with correct `[filename.pdf, p X]` citations; structured JSON response.
- Runner switching works from Settings; LM Studio endpoints on `:1234` verified.
- UI shows live ingestion progress and streaming responses.
- Evaluation script reports precision@k ≥ 0.75 and citation accuracy ≥ 0.85 on the gold set.

## Open Questions / Inputs Needed
- Reranker: keep disabled for v1 or enable after baseline metrics?
- Confirm preferred `top_k` and `similarity_threshold` once initial QA results are available.
- Any documents that require custom parsers (tables, forms) beyond OCR?
