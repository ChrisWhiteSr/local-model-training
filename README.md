# Local LLM + RAG (Backend)

Backend API for local-first PDF QA with citations.

## Quick Start

1. Python 3.11 recommended.
2. Create `.env` at repo root (key fields shown):

```
PDF_SOURCE_DIR=training_data
LLM_RUNNER=lmstudio
LLM_BASE_URL=http://localhost:1234
EMBEDDINGS_PROVIDER=lmstudio
EMBEDDINGS_BASE_URL=http://localhost:1234
EMBEDDINGS_MODEL_ID=text-embedding-qwen3-embedding-4b
VLM_PROVIDER=openai
OPENAI_API_KEY=sk-...  # only needed later for VLM OCR assist
# Optional: choose an LM Studio chat model id
LLM_MODEL_ID=qwen
```

3. Install deps:

```
pip install -r requirements.txt
```

4. Start API:

```
uvicorn server.app:app --reload
```

5. Check health: GET http://127.0.0.1:8000/health

6. Ingest PDFs from `training_data` (response includes `ocr_events` with which pages used VLM OCR):

```
POST http://127.0.0.1:8000/ingest
{}
```

7. Query:

```
POST http://127.0.0.1:8000/query
{
  "query": "What is the main claim of Scientific Advertising?"
}
```

## Notes

- OCR via VLM (OpenAI `gpt-5-mini`) is enabled by default for pages without a text layer and for low-text pages (threshold configurable via `OCR_LOW_TEXT_THRESHOLD_CHARS`). Ensure `OPENAI_API_KEY` is set.
- ChromaDB persists under `data/chroma`.
- LM Studio must be running with a chat model loaded and an embedding model available at `/v1/embeddings`.
  - On Windows: ensure “Microsoft Visual Studio 2022 Build Tools” with C++ workload is installed so `chroma-hnswlib` builds. Once installed, `pip install -r requirements.txt` will install ChromaDB and the backend will use it automatically.

## Frontend (Vite + React)

Dev server (default port 5174):

```
cd web
npm install
npm run dev
```

The app connects to the backend at `http://127.0.0.1:8000` by default. You can change the base URL in the Settings tab, or set `VITE_API_BASE` when building.

Change dev port:

```
# PowerShell
$env:VITE_PORT = '5180'; npm run dev

# bash
VITE_PORT=5180 npm run dev
```
If you change the port, set `UI_ORIGIN` in `.env` to match (e.g., `http://localhost:5180`) and restart the backend.


### Logs
- App log: `logs/app.log` (rotating)
- Ingest events: `logs/ingest.jsonl` (JSON lines)
- API: `GET /logs/ingest?limit=200` to fetch recent ingest events
