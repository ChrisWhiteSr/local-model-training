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

6. Ingest PDFs from `training_data`:

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

- OCR via VLM (OpenAI `gpt-5-mini`) is enabled by default for pages without a text layer. Ensure `OPENAI_API_KEY` is set. PaddleOCR can be added later if desired.
- ChromaDB persists under `data/chroma`.
- LM Studio must be running with a chat model loaded and an embedding model available at `/v1/embeddings`.
